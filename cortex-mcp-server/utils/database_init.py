"""
Database initialization and migration utilities.

This module provides utilities for initializing the database,
running migrations, and managing database schema changes.
"""

import logging
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from sqlalchemy import text, inspect
from sqlalchemy.exc import SQLAlchemyError

from config.database import DatabaseManager, DatabaseConfig, get_database_manager
from models.database import Base, Conversation, Project, Preference, ContextLink

logger = logging.getLogger(__name__)


class DatabaseInitializer:
    """Handles database initialization and schema management."""
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """
        Initialize database initializer.
        
        Args:
            db_manager: Database manager instance (creates default if None)
        """
        self.db_manager = db_manager or get_database_manager()

    def initialize_fresh_database(self) -> bool:
        """
        Initialize a fresh database with all tables and initial data.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            logger.info("Starting fresh database initialization...")
            
            # Initialize the database schema
            self.db_manager.initialize_database()
            
            # Create initial data
            self._create_initial_data()
            
            # Verify initialization
            if self._verify_database_structure():
                logger.info("Fresh database initialization completed successfully")
                return True
            else:
                logger.error("Database structure verification failed")
                return False
                
        except Exception as e:
            logger.error(f"Fresh database initialization failed: {e}")
            return False

    async def initialize_fresh_database_async(self) -> bool:
        """
        Initialize a fresh database asynchronously.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            logger.info("Starting fresh database initialization (async)...")
            
            # Initialize the database schema
            await self.db_manager.initialize_database_async()
            
            # Create initial data
            await self._create_initial_data_async()
            
            # Verify initialization
            if await self._verify_database_structure_async():
                logger.info("Fresh database initialization completed successfully (async)")
                return True
            else:
                logger.error("Database structure verification failed (async)")
                return False
                
        except Exception as e:
            logger.error(f"Fresh database initialization failed (async): {e}")
            return False

    def _create_initial_data(self) -> None:
        """Create initial data in the database."""
        try:
            with self.db_manager.get_session() as session:
                # Create default preferences
                default_preferences = [
                    Preference(
                        key="search.default_limit",
                        value="10",
                        category="search"
                    ),
                    Preference(
                        key="search.semantic_threshold",
                        value="0.7",
                        category="search"
                    ),
                    Preference(
                        key="ui.theme",
                        value="auto",
                        category="ui"
                    ),
                    Preference(
                        key="learning.auto_tag",
                        value="true",
                        category="learning"
                    ),
                    Preference(
                        key="learning.auto_link",
                        value="true",
                        category="learning"
                    ),
                    # Intelligent storage preferences
                    Preference(
                        key="intelligent_storage.auto_store_threshold",
                        value="0.85",
                        category="learning"
                    ),
                    Preference(
                        key="intelligent_storage.suggestion_threshold",
                        value="0.60",
                        category="learning"
                    ),
                    Preference(
                        key="intelligent_storage.privacy_mode",
                        value="false",
                        category="learning"
                    ),
                    Preference(
                        key="intelligent_storage.enabled",
                        value="true",
                        category="learning"
                    ),
                    Preference(
                        key="intelligent_storage.auto_store_preferences",
                        value="true",
                        category="learning"
                    ),
                    Preference(
                        key="intelligent_storage.auto_store_solutions",
                        value="true",
                        category="learning"
                    ),
                    Preference(
                        key="intelligent_storage.auto_store_project_context",
                        value="true",
                        category="learning"
                    ),
                    Preference(
                        key="intelligent_storage.auto_store_decisions",
                        value="true",
                        category="learning"
                    ),
                    Preference(
                        key="intelligent_storage.auto_store_patterns",
                        value="true",
                        category="learning"
                    ),
                    Preference(
                        key="intelligent_storage.notify_auto_store",
                        value="true",
                        category="learning"
                    ),
                    Preference(
                        key="intelligent_storage.learn_from_feedback",
                        value="true",
                        category="learning"
                    ),
                    Preference(
                        key="intelligent_storage.duplicate_detection",
                        value="true",
                        category="learning"
                    ),
                ]
                
                # Check if preferences already exist
                existing_keys = {pref.key for pref in session.query(Preference).all()}
                new_preferences = [
                    pref for pref in default_preferences 
                    if pref.key not in existing_keys
                ]
                
                if new_preferences:
                    session.add_all(new_preferences)
                    session.commit()
                    logger.info(f"Created {len(new_preferences)} default preferences")
                
        except Exception as e:
            logger.error(f"Failed to create initial data: {e}")
            raise

    async def _create_initial_data_async(self) -> None:
        """Create initial data in the database asynchronously."""
        try:
            async with self.db_manager.get_async_session() as session:
                # Create default preferences
                default_preferences = [
                    Preference(
                        key="search.default_limit",
                        value="10",
                        category="search"
                    ),
                    Preference(
                        key="search.semantic_threshold",
                        value="0.7",
                        category="search"
                    ),
                    Preference(
                        key="ui.theme",
                        value="auto",
                        category="ui"
                    ),
                    Preference(
                        key="learning.auto_tag",
                        value="true",
                        category="learning"
                    ),
                    Preference(
                        key="learning.auto_link",
                        value="true",
                        category="learning"
                    ),
                    # Intelligent storage preferences
                    Preference(
                        key="intelligent_storage.auto_store_threshold",
                        value="0.85",
                        category="learning"
                    ),
                    Preference(
                        key="intelligent_storage.suggestion_threshold",
                        value="0.60",
                        category="learning"
                    ),
                    Preference(
                        key="intelligent_storage.privacy_mode",
                        value="false",
                        category="learning"
                    ),
                    Preference(
                        key="intelligent_storage.enabled",
                        value="true",
                        category="learning"
                    ),
                    Preference(
                        key="intelligent_storage.auto_store_preferences",
                        value="true",
                        category="learning"
                    ),
                    Preference(
                        key="intelligent_storage.auto_store_solutions",
                        value="true",
                        category="learning"
                    ),
                    Preference(
                        key="intelligent_storage.auto_store_project_context",
                        value="true",
                        category="learning"
                    ),
                    Preference(
                        key="intelligent_storage.auto_store_decisions",
                        value="true",
                        category="learning"
                    ),
                    Preference(
                        key="intelligent_storage.auto_store_patterns",
                        value="true",
                        category="learning"
                    ),
                    Preference(
                        key="intelligent_storage.notify_auto_store",
                        value="true",
                        category="learning"
                    ),
                    Preference(
                        key="intelligent_storage.learn_from_feedback",
                        value="true",
                        category="learning"
                    ),
                    Preference(
                        key="intelligent_storage.duplicate_detection",
                        value="true",
                        category="learning"
                    ),
                ]
                
                # Check if preferences already exist
                result = await session.execute(text("SELECT key FROM preferences"))
                existing_keys = {row[0] for row in result.fetchall()}
                
                new_preferences = [
                    pref for pref in default_preferences 
                    if pref.key not in existing_keys
                ]
                
                if new_preferences:
                    session.add_all(new_preferences)
                    await session.commit()
                    logger.info(f"Created {len(new_preferences)} default preferences (async)")
                
        except Exception as e:
            logger.error(f"Failed to create initial data (async): {e}")
            raise

    def _verify_database_structure(self) -> bool:
        """
        Verify that all required tables and indexes exist.
        
        Returns:
            bool: True if structure is valid, False otherwise
        """
        try:
            with self.db_manager.get_session() as session:
                inspector = inspect(session.bind)
                
                # Check required tables
                required_tables = {"conversations", "projects", "preferences", "context_links"}
                existing_tables = set(inspector.get_table_names())
                
                missing_tables = required_tables - existing_tables
                if missing_tables:
                    logger.error(f"Missing required tables: {missing_tables}")
                    return False
                
                # Check table structures
                for table_name in required_tables:
                    columns = inspector.get_columns(table_name)
                    if not columns:
                        logger.error(f"Table {table_name} has no columns")
                        return False
                
                # Verify we can query each table
                session.execute(text("SELECT COUNT(*) FROM conversations")).scalar()
                session.execute(text("SELECT COUNT(*) FROM projects")).scalar()
                session.execute(text("SELECT COUNT(*) FROM preferences")).scalar()
                session.execute(text("SELECT COUNT(*) FROM context_links")).scalar()
                
                logger.info("Database structure verification passed")
                return True
                
        except Exception as e:
            logger.error(f"Database structure verification failed: {e}")
            return False

    async def _verify_database_structure_async(self) -> bool:
        """
        Verify database structure asynchronously.
        
        Returns:
            bool: True if structure is valid, False otherwise
        """
        try:
            async with self.db_manager.get_async_session() as session:
                # Basic verification - check we can query each table
                await session.execute(text("SELECT COUNT(*) FROM conversations"))
                await session.execute(text("SELECT COUNT(*) FROM projects"))
                await session.execute(text("SELECT COUNT(*) FROM preferences"))
                await session.execute(text("SELECT COUNT(*) FROM context_links"))
                
                logger.info("Database structure verification passed (async)")
                return True
                
        except Exception as e:
            logger.error(f"Database structure verification failed (async): {e}")
            return False

    def backup_database(self, backup_path: Optional[str] = None) -> str:
        """
        Create a backup of the database.
        
        Args:
            backup_path: Path for backup file (auto-generated if None)
            
        Returns:
            str: Path to backup file
            
        Raises:
            Exception: If backup fails
        """
        try:
            if backup_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_dir = Path.home() / ".cortex_mcp" / "backups"
                backup_dir.mkdir(parents=True, exist_ok=True)
                backup_path = str(backup_dir / f"memory_backup_{timestamp}.db")
            
            # For SQLite, we can use the backup API
            if "sqlite" in self.db_manager.config.database_url:
                import sqlite3
                
                source_path = self.db_manager.config.database_url.replace("sqlite:///", "")
                
                # Copy database file
                with sqlite3.connect(source_path) as source:
                    with sqlite3.connect(backup_path) as backup:
                        source.backup(backup)
                
                logger.info(f"Database backup created at: {backup_path}")
                return backup_path
            else:
                raise NotImplementedError("Backup not implemented for non-SQLite databases")
                
        except Exception as e:
            logger.error(f"Database backup failed: {e}")
            raise

    def restore_database(self, backup_path: str) -> bool:
        """
        Restore database from backup.
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            bool: True if restore successful, False otherwise
        """
        try:
            if not os.path.exists(backup_path):
                logger.error(f"Backup file not found: {backup_path}")
                return False
            
            # For SQLite, replace the current database file
            if "sqlite" in self.db_manager.config.database_url:
                import sqlite3
                import shutil
                
                current_path = self.db_manager.config.database_url.replace("sqlite:///", "")
                
                # Close current connections
                self.db_manager.close()
                
                # Create backup of current database
                if os.path.exists(current_path):
                    backup_current = f"{current_path}.backup_before_restore"
                    shutil.copy2(current_path, backup_current)
                    logger.info(f"Current database backed up to: {backup_current}")
                
                # Restore from backup
                shutil.copy2(backup_path, current_path)
                
                # Reinitialize database manager
                self.db_manager = get_database_manager()
                
                # Verify restored database
                if self._verify_database_structure():
                    logger.info(f"Database restored successfully from: {backup_path}")
                    return True
                else:
                    logger.error("Restored database failed verification")
                    return False
            else:
                raise NotImplementedError("Restore not implemented for non-SQLite databases")
                
        except Exception as e:
            logger.error(f"Database restore failed: {e}")
            return False

    def get_schema_version(self) -> Optional[str]:
        """
        Get current database schema version.
        
        Returns:
            Optional[str]: Schema version or None if not found
        """
        try:
            with self.db_manager.get_session() as session:
                # Check if we have a schema version preference
                result = session.query(Preference).filter_by(key="schema.version").first()
                return result.value if result else None
                
        except Exception as e:
            logger.warning(f"Could not get schema version: {e}")
            return None

    def set_schema_version(self, version: str) -> bool:
        """
        Set database schema version.
        
        Args:
            version: Schema version string
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with self.db_manager.get_session() as session:
                # Update or create schema version preference
                pref = session.query(Preference).filter_by(key="schema.version").first()
                if pref:
                    pref.value = version
                    pref.updated_at = datetime.utcnow()
                else:
                    pref = Preference(
                        key="schema.version",
                        value=version,
                        category="system"
                    )
                    session.add(pref)
                
                session.commit()
                logger.info(f"Schema version set to: {version}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to set schema version: {e}")
            return False


def initialize_database(
    database_path: Optional[str] = None,
    force_recreate: bool = False
) -> bool:
    """
    Initialize the database with proper error handling.
    
    Args:
        database_path: Path to database file (uses default if None)
        force_recreate: Whether to recreate existing database
        
    Returns:
        bool: True if initialization successful, False otherwise
    """
    try:
        # Create database config
        config = DatabaseConfig(database_path=database_path)
        
        # Check if database already exists
        if "sqlite" in config.database_url:
            db_file_path = config.database_url.replace("sqlite:///", "")
            if os.path.exists(db_file_path) and not force_recreate:
                logger.info(f"Database already exists at: {db_file_path}")
                # Just verify it's working
                db_manager = DatabaseManager(config)
                return db_manager.health_check()
        
        # Initialize database
        initializer = DatabaseInitializer(DatabaseManager(config))
        success = initializer.initialize_fresh_database()
        
        if success:
            # Set initial schema version
            initializer.set_schema_version("1.0.0")
        
        return success
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False


if __name__ == "__main__":
    # Command line interface for database initialization
    import argparse
    
    parser = argparse.ArgumentParser(description="Initialize Cortex MCP database")
    parser.add_argument("--database-path", help="Path to database file")
    parser.add_argument("--force-recreate", action="store_true", help="Force recreate existing database")
    parser.add_argument("--backup", help="Create backup before initialization")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Create backup if requested
    if args.backup and args.database_path and os.path.exists(args.database_path):
        initializer = DatabaseInitializer()
        backup_path = initializer.backup_database(args.backup)
        print(f"Backup created at: {backup_path}")
    
    # Initialize database
    success = initialize_database(
        database_path=args.database_path,
        force_recreate=args.force_recreate
    )
    
    if success:
        print("Database initialization completed successfully!")
    else:
        print("Database initialization failed!")
        exit(1)