#!/usr/bin/env python3
"""
Demonstration of comprehensive error handling in the cross-tool memory system.

This script shows how the error handling, logging, and health check systems work
together to provide robust operation with graceful degradation.
"""

import asyncio
import logging
import tempfile
import time
from pathlib import Path

from src.cross_tool_memory.config.database import DatabaseManager, DatabaseConfig
from src.cross_tool_memory.services.search_engine import SearchEngine
from src.cross_tool_memory.services.vector_store import VectorStore
from src.cross_tool_memory.utils.error_handling import (
    retry_with_backoff, RetryConfig, graceful_degradation, error_recovery_manager
)
from src.cross_tool_memory.utils.logging_config import (
    setup_default_logging, get_component_logger, get_performance_logger, TimedOperation
)
from src.cross_tool_memory.utils.health_checks import get_health_checker, HealthStatus


async def demonstrate_retry_mechanism():
    """Demonstrate retry mechanism with exponential backoff."""
    print("\n=== Retry Mechanism Demo ===")
    
    logger = get_component_logger("retry_demo")
    attempt_count = 0
    
    @retry_with_backoff(
        config=RetryConfig(max_attempts=3, base_delay=0.5),
        service_name="demo_service"
    )
    async def unreliable_operation():
        nonlocal attempt_count
        attempt_count += 1
        logger.info(f"Attempt {attempt_count}")
        
        if attempt_count < 3:
            raise ConnectionError(f"Connection failed on attempt {attempt_count}")
        
        return "Success!"
    
    try:
        result = await unreliable_operation()
        logger.info(f"Operation succeeded: {result}")
    except Exception as e:
        logger.error(f"Operation failed after all retries: {e}")
    
    print(f"Total attempts made: {attempt_count}")


async def demonstrate_graceful_degradation():
    """Demonstrate graceful degradation with fallback."""
    print("\n=== Graceful Degradation Demo ===")
    
    logger = get_component_logger("degradation_demo")
    
    async def fallback_search(query: str, **kwargs):
        logger.warning("Using fallback search method")
        return [{"content": f"Fallback result for: {query}", "score": 0.5}]
    
    @graceful_degradation(fallback_func=fallback_search, service_name="search_demo")
    async def advanced_search(query: str, **kwargs):
        logger.info("Attempting advanced search")
        # Simulate failure
        raise Exception("Advanced search service unavailable")
    
    results = await advanced_search("test query")
    logger.info(f"Search results: {results}")


async def demonstrate_health_checks():
    """Demonstrate comprehensive health checking."""
    print("\n=== Health Check Demo ===")
    
    logger = get_component_logger("health_demo")
    
    # Create temporary database for demo
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "demo.db"
        
        # Initialize components
        db_config = DatabaseConfig(database_path=str(db_path))
        db_manager = DatabaseManager(db_config)
        db_manager.initialize_database()
        
        vector_store = VectorStore(dimension=384)
        await vector_store.initialize()
        
        search_engine = SearchEngine(
            embedding_service=None,  # Use keyword-only mode for demo
            vector_store=vector_store
        )
        await search_engine.initialize()
        
        # Create health checker
        health_checker = get_health_checker(
            db_manager=db_manager,
            search_engine=search_engine,
            vector_store=vector_store
        )
        
        # Perform system health check
        logger.info("Performing system health check...")
        system_health = await health_checker.check_system_health()
        
        print(f"Overall Status: {system_health.status.value}")
        print(f"Uptime: {system_health.uptime_seconds:.2f} seconds")
        print(f"Total Errors: {system_health.total_errors}")
        
        print("\nComponent Health:")
        for component in system_health.components:
            status_emoji = {
                HealthStatus.HEALTHY: "✅",
                HealthStatus.DEGRADED: "⚠️",
                HealthStatus.UNHEALTHY: "❌",
                HealthStatus.UNKNOWN: "❓"
            }.get(component.status, "❓")
            
            print(f"  {status_emoji} {component.name}: {component.status.value} - {component.message}")
            if component.response_time_ms:
                print(f"    Response time: {component.response_time_ms:.2f}ms")
            if component.error_count > 0:
                print(f"    Error count: {component.error_count}")


def demonstrate_logging_system():
    """Demonstrate comprehensive logging system."""
    print("\n=== Logging System Demo ===")
    
    # Setup logging with different levels
    setup_default_logging(log_level="DEBUG", structured_logs=False)
    
    # Component logger
    comp_logger = get_component_logger("logging_demo")
    comp_logger.info("This is an info message", operation="demo", user_id="test_user")
    comp_logger.warning("This is a warning message", error_code="WARN_001")
    comp_logger.error("This is an error message", exception_type="DemoError")
    
    # Performance logger
    perf_logger = get_performance_logger()
    perf_logger.log_operation_time("demo_operation", 1.5, {"records_processed": 100})
    perf_logger.log_search_performance("test query", 25, 0.8, "hybrid")
    perf_logger.log_database_performance("SELECT", "conversations", 0.05, 10)
    
    # Timed operation
    with TimedOperation("timed_demo_operation", comp_logger, {"complexity": "high"}):
        time.sleep(0.2)  # Simulate work
    
    print("Check the logs directory for detailed logging output")


async def demonstrate_error_recovery():
    """Demonstrate error recovery and circuit breaker."""
    print("\n=== Error Recovery Demo ===")
    
    logger = get_component_logger("recovery_demo")
    
    # Simulate multiple errors to trigger circuit breaker
    from src.cross_tool_memory.utils.error_handling import circuit_breaker, CircuitBreakerConfig
    
    call_count = 0
    
    @circuit_breaker(
        config=CircuitBreakerConfig(failure_threshold=3, recovery_timeout=2.0),
        service_name="demo_circuit"
    )
    async def failing_service():
        nonlocal call_count
        call_count += 1
        logger.info(f"Service call #{call_count}")
        
        if call_count <= 5:  # Fail first 5 calls
            raise Exception(f"Service failure #{call_count}")
        
        return f"Success on call #{call_count}"
    
    # Try calling the service multiple times
    for i in range(8):
        try:
            result = await failing_service()
            logger.info(f"Call {i+1}: {result}")
        except Exception as e:
            logger.warning(f"Call {i+1}: {e}")
        
        await asyncio.sleep(0.5)
    
    # Check error statistics
    stats = error_recovery_manager.get_error_stats("demo_circuit")
    print(f"Error statistics: {stats}")


async def demonstrate_database_error_handling():
    """Demonstrate database error handling with retry logic."""
    print("\n=== Database Error Handling Demo ===")
    
    logger = get_component_logger("db_demo")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "demo.db"
        
        # Initialize database
        db_config = DatabaseConfig(database_path=str(db_path))
        db_manager = DatabaseManager(db_config)
        db_manager.initialize_database()
        
        # Test normal operation
        logger.info("Testing normal database operation...")
        with db_manager.get_session() as session:
            result = session.execute("SELECT 1").scalar()
            logger.info(f"Database query result: {result}")
        
        # Test health check
        logger.info("Testing database health check...")
        is_healthy = db_manager.health_check()
        logger.info(f"Database health: {'Healthy' if is_healthy else 'Unhealthy'}")
        
        # Get database statistics
        stats = db_manager.get_database_stats()
        logger.info(f"Database statistics: {stats}")


async def main():
    """Run all error handling demonstrations."""
    print("Cross-Tool Memory Error Handling Demonstration")
    print("=" * 50)
    
    # Setup logging for the demo
    demonstrate_logging_system()
    
    # Run async demonstrations
    await demonstrate_retry_mechanism()
    await demonstrate_graceful_degradation()
    await demonstrate_health_checks()
    await demonstrate_error_recovery()
    await demonstrate_database_error_handling()
    
    print("\n=== Demo Complete ===")
    print("The error handling system provides:")
    print("✅ Automatic retry with exponential backoff")
    print("✅ Circuit breaker pattern for failing services")
    print("✅ Graceful degradation with fallback mechanisms")
    print("✅ Comprehensive health monitoring")
    print("✅ Structured logging with performance metrics")
    print("✅ Database connection recovery")
    print("✅ Search engine fallback to keyword-only mode")


if __name__ == "__main__":
    asyncio.run(main())