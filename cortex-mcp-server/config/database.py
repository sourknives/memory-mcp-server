"""
Database configuration and connection management.

This module handles SQLite database connections, initialization,
and provides session management with comprehensive error handling and retry logic.
"""

import os
import logging
import time
from contextlib import contextmanager, asynccontextmanager
from typing import Generator, AsyncGenerator, Optional
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.exc import SQLAlchemyError, OperationalError, DisconnectionError, TimeoutError as SQLTimeoutError
import aiosqlite

from models.database import Base
from utils.error_handling import (
    retry_with_backoff, 
    RetryConfig, 
    graceful_degradation,
    error_recovery_manager
)
from utils.logging_config import get_component_logger, TimedOperation

logger = get_component_logger("database")


class DatabaseConfig:
    """Database configuration settings."""
    
    def __init__(
        self,
        database_url: Optional[str] = None,
        database_path: Optional[str] = None,
        echo: bool = False,
        pool_pre_ping: bool = True,
        pool_recycle: int = 3600,
    ):
        """
        Initialize database configuration.
        
        Args:
            database_url: Full database URL (overrides database_path)
            database_path: Path to SQLite database file
            echo: Enable SQL query logging
            pool_pre_ping: Enable connection health checks
            pool_recycle: Connection recycle time in seconds
        """
        if database_url:
            self.database_url = database_url
            self.async_database_url = database_url.replace("sqlite://", "sqlite+aiosqlite://")
        else:
            # Default to local data directory
            if not database_path:
                data_dir = Path.home() / ".cortex_mcp" / "data"
                data_dir.mkdir(parents=True, exist_ok=True)
                database_path = str(data_dir / "memory.db")
            
            self.database_url = f"sqlite:///{database_path}"
            self.async_database_url = f"sqlite+aiosqlite:///{database_path}"
        
        self.echo = echo
        self.pool_pre_ping = pool_pre_ping
        self.pool_recycle = pool_recycle
        
        logger.info(f"Database configured at: {self.database_url}")


class DatabaseManager:
    """Manages database connections and sessions."""
    
    def __init__(self, config: DatabaseConfig):
        """Initialize database manager with configuration."""
        self.config = config
        self._engine: Optional[Engine] = None
        self._async_engine = None
        self._session_factory: Optional[sessionmaker] = None
        self._async_session_factory = None
        self._initialized = False

    @property
    def engine(self) -> Engine:
        """Get or create synchronous database engine."""
        if self._engine is None:
            self._engine = create_engine(
                self.config.database_url,
                echo=self.config.echo,
                pool_pre_ping=self.config.pool_pre_ping,
                pool_recycle=self.config.pool_recycle,
                # SQLite specific settings
                connect_args={"check_same_thread": False} if "sqlite" in self.config.database_url else {}
            )
            
            # Enable WAL mode for SQLite for better concurrency
            if "sqlite" in self.config.database_url:
                @event.listens_for(self._engine, "connect")
                def set_sqlite_pragma(dbapi_connection, connection_record):
                    cursor = dbapi_connection.cursor()
                    # Enable WAL mode for better concurrency
                    cursor.execute("PRAGMA journal_mode=WAL")
                    # Enable foreign key constraints
                    cursor.execute("PRAGMA foreign_keys=ON")
                    # Set reasonable timeout
                    cursor.execute("PRAGMA busy_timeout=30000")
                    cursor.close()
        
        return self._engine

    @property
    def async_engine(self):
        """Get or create asynchronous database engine."""
        if self._async_engine is None:
            self._async_engine = create_async_engine(
                self.config.async_database_url,
                echo=self.config.echo,
                pool_pre_ping=self.config.pool_pre_ping,
                pool_recycle=self.config.pool_recycle,
            )
        
        return self._async_engine

    @property
    def session_factory(self) -> sessionmaker:
        """Get or create session factory."""
        if self._session_factory is None:
            self._session_factory = sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False
            )
        
        return self._session_factory

    @property
    def async_session_factory(self):
        """Get or create async session factory."""
        if self._async_session_factory is None:
            self._async_session_factory = async_sessionmaker(
                bind=self.async_engine,
                class_=AsyncSession,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False
            )
        
        return self._async_session_factory

    def initialize_database(self) -> None:
        """Initialize database schema and perform setup."""
        try:
            logger.info("Initializing database schema...")
            
            # Create all tables
            Base.metadata.create_all(bind=self.engine)
            
            # Verify database connection directly without using get_session
            session = self.session_factory()
            try:
                session.execute(text("SELECT 1"))
                session.commit()
            finally:
                session.close()
            
            self._initialized = True
            logger.info("Database initialization completed successfully")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise DatabaseInitializationError(f"Failed to initialize database: {e}") from e

    async def initialize_database_async(self) -> None:
        """Initialize database schema asynchronously."""
        try:
            logger.info("Initializing database schema (async)...")
            
            # Create all tables
            async with self.async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            # Verify database connection
            async with self.get_async_session() as session:
                await session.execute(text("SELECT 1"))
                await session.commit()
            
            self._initialized = True
            logger.info("Database initialization completed successfully (async)")
            
        except Exception as e:
            logger.error(f"Database initialization failed (async): {e}")
            raise DatabaseInitializationError(f"Failed to initialize database: {e}") from e

    @contextmanager
    @retry_with_backoff(
        config=RetryConfig(
            max_attempts=3,
            base_delay=1.0,
            retryable_exceptions=[OperationalError, DisconnectionError, SQLTimeoutError, OSError]
        ),
        service_name="database"
    )
    def get_session(self) -> Generator[Session, None, None]:
        """
        Get a database session with automatic cleanup and retry logic.
        
        Yields:
            Session: SQLAlchemy session
            
        Raises:
            DatabaseConnectionError: If connection fails after retries
        """
        if not self._initialized:
            self.initialize_database()
        
        session = None
        try:
            with TimedOperation("database_session_create", logger):
                session = self.session_factory()
            
            yield session
            
            with TimedOperation("database_session_commit", logger):
                session.commit()
                
        except (OperationalError, DisconnectionError) as e:
            if session:
                session.rollback()
            logger.error(f"Database connection error: {e}")
            # Re-initialize connection pool on connection errors
            self._reinitialize_connection()
            raise DatabaseConnectionError(f"Database connection failed: {e}") from e
        except Exception as e:
            if session:
                session.rollback()
            logger.error(f"Database session error: {e}")
            raise DatabaseConnectionError(f"Database operation failed: {e}") from e
        finally:
            if session:
                try:
                    session.close()
                except Exception as close_error:
                    logger.warning(f"Error closing database session: {close_error}")

    @asynccontextmanager
    @retry_with_backoff(
        config=RetryConfig(
            max_attempts=3,
            base_delay=1.0,
            retryable_exceptions=[OperationalError, DisconnectionError, SQLTimeoutError, OSError]
        ),
        service_name="database_async"
    )
    async def get_async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get an async database session with automatic cleanup and retry logic.
        
        Yields:
            AsyncSession: SQLAlchemy async session
            
        Raises:
            DatabaseConnectionError: If connection fails after retries
        """
        if not self._initialized:
            await self.initialize_database_async()
        
        session = None
        try:
            with TimedOperation("database_async_session_create", logger):
                session = self.async_session_factory()
            
            yield session
            
            with TimedOperation("database_async_session_commit", logger):
                await session.commit()
                
        except (OperationalError, DisconnectionError) as e:
            if session:
                await session.rollback()
            logger.error(f"Database connection error (async): {e}")
            # Re-initialize connection pool on connection errors
            await self._reinitialize_connection_async()
            raise DatabaseConnectionError(f"Database connection failed: {e}") from e
        except Exception as e:
            if session:
                await session.rollback()
            logger.error(f"Database session error (async): {e}")
            raise DatabaseConnectionError(f"Database operation failed: {e}") from e
        finally:
            if session:
                try:
                    await session.close()
                except Exception as close_error:
                    logger.warning(f"Error closing database session (async): {close_error}")

    def _reinitialize_connection(self) -> None:
        """Reinitialize database connection after connection errors."""
        try:
            logger.info("Reinitializing database connection...")
            if self._engine:
                self._engine.dispose()
            self._engine = None
            self._session_factory = None
            # Force recreation on next access
            _ = self.engine
            logger.info("Database connection reinitialized successfully")
        except Exception as e:
            logger.error(f"Failed to reinitialize database connection: {e}")
    
    async def _reinitialize_connection_async(self) -> None:
        """Reinitialize async database connection after connection errors."""
        try:
            logger.info("Reinitializing async database connection...")
            if self._async_engine:
                await self._async_engine.dispose()
            self._async_engine = None
            self._async_session_factory = None
            # Force recreation on next access
            _ = self.async_engine
            logger.info("Async database connection reinitialized successfully")
        except Exception as e:
            logger.error(f"Failed to reinitialize async database connection: {e}")

    @graceful_degradation(service_name="database_health")
    def health_check(self) -> bool:
        """
        Check database health and connectivity with comprehensive diagnostics.
        
        Returns:
            bool: True if database is healthy, False otherwise
        """
        try:
            start_time = time.time()
            
            # Basic connectivity test
            with self.get_session() as session:
                session.execute(text("SELECT 1"))
            
            # Check database file accessibility (SQLite specific)
            if "sqlite" in self.config.database_url:
                db_path = self.config.database_url.replace("sqlite:///", "")
                if not os.path.exists(db_path):
                    logger.error(f"Database file does not exist: {db_path}")
                    return False
                
                # Check file permissions
                if not os.access(db_path, os.R_OK | os.W_OK):
                    logger.error(f"Insufficient permissions for database file: {db_path}")
                    return False
            
            duration = time.time() - start_time
            logger.debug(f"Database health check passed in {duration:.3f}s")
            return True
            
        except Exception as e:
            logger.warning(f"Database health check failed: {e}")
            error_recovery_manager.record_error("database_health", e)
            return False

    @graceful_degradation(service_name="database_health_async")
    async def health_check_async(self) -> bool:
        """
        Check database health and connectivity asynchronously with comprehensive diagnostics.
        
        Returns:
            bool: True if database is healthy, False otherwise
        """
        try:
            start_time = time.time()
            
            # Basic connectivity test
            async with self.get_async_session() as session:
                await session.execute(text("SELECT 1"))
            
            # Check database file accessibility (SQLite specific)
            if "sqlite" in self.config.database_url:
                db_path = self.config.database_url.replace("sqlite:///", "")
                if not os.path.exists(db_path):
                    logger.error(f"Database file does not exist: {db_path}")
                    return False
                
                # Check file permissions
                if not os.access(db_path, os.R_OK | os.W_OK):
                    logger.error(f"Insufficient permissions for database file: {db_path}")
                    return False
            
            duration = time.time() - start_time
            logger.debug(f"Database health check passed (async) in {duration:.3f}s")
            return True
            
        except Exception as e:
            logger.warning(f"Database health check failed (async): {e}")
            error_recovery_manager.record_error("database_health_async", e)
            return False

    def get_database_stats(self) -> dict:
        """
        Get database statistics and information.
        
        Returns:
            dict: Database statistics
        """
        try:
            with self.get_session() as session:
                stats = {}
                
                # Get table counts
                from models.database import Conversation, Project, Preference, ContextLink
                
                stats["conversations"] = session.query(Conversation).count()
                stats["projects"] = session.query(Project).count()
                stats["preferences"] = session.query(Preference).count()
                stats["context_links"] = session.query(ContextLink).count()
                
                # Get database file size if SQLite
                if "sqlite" in self.config.database_url:
                    db_path = self.config.database_url.replace("sqlite:///", "")
                    if os.path.exists(db_path):
                        stats["database_size_bytes"] = os.path.getsize(db_path)
                        stats["database_size_mb"] = stats["database_size_bytes"] / (1024 * 1024)
                
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {"error": str(e)}

    def close(self) -> None:
        """Close database connections."""
        if self._engine:
            self._engine.dispose()
            self._engine = None
        
        if self._async_engine:
            # Note: async engine disposal should be done in async context
            self._async_engine = None
        
        self._session_factory = None
        self._async_session_factory = None
        self._initialized = False
        
        logger.info("Database connections closed")

    async def close_async(self) -> None:
        """Close database connections asynchronously."""
        if self._async_engine:
            await self._async_engine.dispose()
            self._async_engine = None
        
        if self._engine:
            self._engine.dispose()
            self._engine = None
        
        self._session_factory = None
        self._async_session_factory = None
        self._initialized = False
        
        logger.info("Database connections closed (async)")


# Custom exceptions
class DatabaseError(Exception):
    """Base exception for database-related errors."""
    pass


class DatabaseConnectionError(DatabaseError):
    """Exception raised when database connection fails."""
    pass


class DatabaseInitializationError(DatabaseError):
    """Exception raised when database initialization fails."""
    pass


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_database_manager(config: Optional[DatabaseConfig] = None) -> DatabaseManager:
    """
    Get or create the global database manager instance.
    
    Args:
        config: Database configuration (only used on first call)
        
    Returns:
        DatabaseManager: The database manager instance
    """
    global _db_manager
    
    if _db_manager is None:
        if config is None:
            config = DatabaseConfig()
        _db_manager = DatabaseManager(config)
    
    return _db_manager


def reset_database_manager() -> None:
    """Reset the global database manager (mainly for testing)."""
    global _db_manager
    if _db_manager:
        _db_manager.close()
    _db_manager = None