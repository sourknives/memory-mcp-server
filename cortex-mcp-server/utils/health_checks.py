"""
Health check utilities for monitoring system components.

This module provides comprehensive health checks for database, search engine,
and other system components with detailed diagnostics.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

from config.database import DatabaseManager
from services.search_engine import SearchEngine
from services.embedding_service import EmbeddingService
from services.vector_store import VectorStore
from utils.logging_config import get_component_logger
from utils.error_handling import error_recovery_manager

logger = get_component_logger("health_checks")


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health information for a system component."""
    name: str
    status: HealthStatus
    message: str
    response_time_ms: Optional[float] = None
    last_check: Optional[datetime] = None
    error_count: int = 0
    details: Optional[Dict[str, Any]] = None


@dataclass
class SystemHealth:
    """Overall system health information."""
    status: HealthStatus
    components: List[ComponentHealth]
    timestamp: datetime
    uptime_seconds: Optional[float] = None
    total_errors: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "status": self.status.value,
            "components": [asdict(comp) for comp in self.components],
            "timestamp": self.timestamp.isoformat(),
            "uptime_seconds": self.uptime_seconds,
            "total_errors": self.total_errors
        }


class HealthChecker:
    """Comprehensive health checker for system components."""
    
    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        search_engine: Optional[SearchEngine] = None,
        embedding_service: Optional[EmbeddingService] = None,
        vector_store: Optional[VectorStore] = None
    ):
        """
        Initialize health checker with system components.
        
        Args:
            db_manager: Database manager instance
            search_engine: Search engine instance
            embedding_service: Embedding service instance
            vector_store: Vector store instance
        """
        self.db_manager = db_manager
        self.search_engine = search_engine
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.start_time = time.time()
    
    async def check_database_health(self) -> ComponentHealth:
        """Check database health and connectivity."""
        start_time = time.time()
        
        try:
            if not self.db_manager:
                return ComponentHealth(
                    name="database",
                    status=HealthStatus.UNKNOWN,
                    message="Database manager not available",
                    last_check=datetime.now()
                )
            
            # Basic connectivity test
            is_healthy = await self.db_manager.health_check_async()
            
            if not is_healthy:
                return ComponentHealth(
                    name="database",
                    status=HealthStatus.UNHEALTHY,
                    message="Database connectivity test failed",
                    response_time_ms=(time.time() - start_time) * 1000,
                    last_check=datetime.now(),
                    error_count=error_recovery_manager.error_counts.get("database", 0)
                )
            
            # Get database statistics
            stats = self.db_manager.get_database_stats()
            
            # Check for errors in stats
            if "error" in stats:
                return ComponentHealth(
                    name="database",
                    status=HealthStatus.DEGRADED,
                    message=f"Database stats error: {stats['error']}",
                    response_time_ms=(time.time() - start_time) * 1000,
                    last_check=datetime.now(),
                    error_count=error_recovery_manager.error_counts.get("database", 0)
                )
            
            # Determine status based on error count
            error_count = error_recovery_manager.error_counts.get("database", 0)
            if error_count > 10:
                status = HealthStatus.DEGRADED
                message = f"Database healthy but has {error_count} recent errors"
            else:
                status = HealthStatus.HEALTHY
                message = "Database is healthy"
            
            return ComponentHealth(
                name="database",
                status=status,
                message=message,
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.now(),
                error_count=error_count,
                details=stats
            )
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return ComponentHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Health check error: {str(e)}",
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.now(),
                error_count=error_recovery_manager.error_counts.get("database", 0) + 1
            )
    
    async def check_search_engine_health(self) -> ComponentHealth:
        """Check search engine health and performance."""
        start_time = time.time()
        
        try:
            if not self.search_engine:
                return ComponentHealth(
                    name="search_engine",
                    status=HealthStatus.UNKNOWN,
                    message="Search engine not available",
                    last_check=datetime.now()
                )
            
            # Test search functionality with a simple query
            test_results = await self.search_engine.search(
                query="test health check",
                limit=1,
                search_type="keyword"  # Use keyword search for reliability
            )
            
            # Check document count
            doc_count = self.search_engine.document_count
            
            # Determine status
            error_count = error_recovery_manager.error_counts.get("search_engine", 0)
            
            if error_count > 20:
                status = HealthStatus.DEGRADED
                message = f"Search engine degraded with {error_count} recent errors"
            else:
                status = HealthStatus.HEALTHY
                message = "Search engine is healthy"
            
            return ComponentHealth(
                name="search_engine",
                status=status,
                message=message,
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.now(),
                error_count=error_count,
                details={
                    "document_count": doc_count,
                    "test_query_results": len(test_results) if test_results else 0,
                    "embedding_service_available": self.search_engine.embedding_service is not None
                }
            )
            
        except Exception as e:
            logger.error(f"Search engine health check failed: {e}")
            return ComponentHealth(
                name="search_engine",
                status=HealthStatus.UNHEALTHY,
                message=f"Health check error: {str(e)}",
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.now(),
                error_count=error_recovery_manager.error_counts.get("search_engine", 0) + 1
            )
    
    async def check_embedding_service_health(self) -> ComponentHealth:
        """Check embedding service health and model availability."""
        start_time = time.time()
        
        try:
            if not self.embedding_service:
                return ComponentHealth(
                    name="embedding_service",
                    status=HealthStatus.UNKNOWN,
                    message="Embedding service not available",
                    last_check=datetime.now()
                )
            
            # Test embedding generation with a simple text
            test_embedding = await self.embedding_service.generate_embedding("test")
            
            if not test_embedding or len(test_embedding) == 0:
                return ComponentHealth(
                    name="embedding_service",
                    status=HealthStatus.UNHEALTHY,
                    message="Embedding generation returned empty result",
                    response_time_ms=(time.time() - start_time) * 1000,
                    last_check=datetime.now()
                )
            
            # Check model information
            model_info = getattr(self.embedding_service, 'model_name', 'unknown')
            dimension = len(test_embedding)
            
            error_count = error_recovery_manager.error_counts.get("embedding_service", 0)
            
            if error_count > 5:
                status = HealthStatus.DEGRADED
                message = f"Embedding service degraded with {error_count} recent errors"
            else:
                status = HealthStatus.HEALTHY
                message = "Embedding service is healthy"
            
            return ComponentHealth(
                name="embedding_service",
                status=status,
                message=message,
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.now(),
                error_count=error_count,
                details={
                    "model_name": model_info,
                    "embedding_dimension": dimension,
                    "test_embedding_length": len(test_embedding)
                }
            )
            
        except Exception as e:
            logger.error(f"Embedding service health check failed: {e}")
            return ComponentHealth(
                name="embedding_service",
                status=HealthStatus.UNHEALTHY,
                message=f"Health check error: {str(e)}",
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.now(),
                error_count=error_recovery_manager.error_counts.get("embedding_service", 0) + 1
            )
    
    async def check_vector_store_health(self) -> ComponentHealth:
        """Check vector store health and index status."""
        start_time = time.time()
        
        try:
            if not self.vector_store:
                return ComponentHealth(
                    name="vector_store",
                    status=HealthStatus.UNKNOWN,
                    message="Vector store not available",
                    last_check=datetime.now()
                )
            
            # Get vector store statistics
            stats = {
                "dimension": self.vector_store.dimension,
                "total_vectors": getattr(self.vector_store, 'total_vectors', 0)
            }
            
            error_count = error_recovery_manager.error_counts.get("vector_store", 0)
            
            if error_count > 10:
                status = HealthStatus.DEGRADED
                message = f"Vector store degraded with {error_count} recent errors"
            else:
                status = HealthStatus.HEALTHY
                message = "Vector store is healthy"
            
            return ComponentHealth(
                name="vector_store",
                status=status,
                message=message,
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.now(),
                error_count=error_count,
                details=stats
            )
            
        except Exception as e:
            logger.error(f"Vector store health check failed: {e}")
            return ComponentHealth(
                name="vector_store",
                status=HealthStatus.UNHEALTHY,
                message=f"Health check error: {str(e)}",
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.now(),
                error_count=error_recovery_manager.error_counts.get("vector_store", 0) + 1
            )
    
    async def check_system_health(self) -> SystemHealth:
        """Perform comprehensive system health check."""
        logger.info("Starting comprehensive system health check")
        
        # Run all component health checks in parallel
        health_checks = await asyncio.gather(
            self.check_database_health(),
            self.check_search_engine_health(),
            self.check_embedding_service_health(),
            self.check_vector_store_health(),
            return_exceptions=True
        )
        
        components = []
        total_errors = 0
        
        for health_check in health_checks:
            if isinstance(health_check, Exception):
                logger.error(f"Health check failed with exception: {health_check}")
                components.append(ComponentHealth(
                    name="unknown",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Health check exception: {str(health_check)}",
                    last_check=datetime.now()
                ))
            else:
                components.append(health_check)
                total_errors += health_check.error_count
        
        # Determine overall system status
        statuses = [comp.status for comp in components]
        
        if any(status == HealthStatus.UNHEALTHY for status in statuses):
            overall_status = HealthStatus.UNHEALTHY
        elif any(status == HealthStatus.DEGRADED for status in statuses):
            overall_status = HealthStatus.DEGRADED
        elif any(status == HealthStatus.UNKNOWN for status in statuses):
            overall_status = HealthStatus.UNKNOWN
        else:
            overall_status = HealthStatus.HEALTHY
        
        uptime = time.time() - self.start_time
        
        system_health = SystemHealth(
            status=overall_status,
            components=components,
            timestamp=datetime.now(),
            uptime_seconds=uptime,
            total_errors=total_errors
        )
        
        logger.info(f"System health check completed - Status: {overall_status.value}")
        return system_health
    
    async def check_component_health(self, component_name: str) -> ComponentHealth:
        """Check health of a specific component."""
        if component_name == "database":
            return await self.check_database_health()
        elif component_name == "search_engine":
            return await self.check_search_engine_health()
        elif component_name == "embedding_service":
            return await self.check_embedding_service_health()
        elif component_name == "vector_store":
            return await self.check_vector_store_health()
        else:
            return ComponentHealth(
                name=component_name,
                status=HealthStatus.UNKNOWN,
                message=f"Unknown component: {component_name}",
                last_check=datetime.now()
            )


# Global health checker instance
_health_checker: Optional[HealthChecker] = None


def get_health_checker(
    db_manager: Optional[DatabaseManager] = None,
    search_engine: Optional[SearchEngine] = None,
    embedding_service: Optional[EmbeddingService] = None,
    vector_store: Optional[VectorStore] = None
) -> HealthChecker:
    """Get or create the global health checker instance."""
    global _health_checker
    
    if _health_checker is None:
        _health_checker = HealthChecker(
            db_manager=db_manager,
            search_engine=search_engine,
            embedding_service=embedding_service,
            vector_store=vector_store
        )
    
    return _health_checker


def reset_health_checker() -> None:
    """Reset the global health checker (mainly for testing)."""
    global _health_checker
    _health_checker = None