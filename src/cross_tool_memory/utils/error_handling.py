"""
Comprehensive error handling utilities for the cross-tool memory system.

This module provides retry logic, graceful degradation, and error recovery
mechanisms for database operations, search engine failures, and service errors.
"""

import asyncio
import functools
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union
from datetime import datetime, timedelta
import traceback

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Optional[List[Type[Exception]]] = None
    ):
        """
        Initialize retry configuration.
        
        Args:
            max_attempts: Maximum number of retry attempts
            base_delay: Base delay between retries in seconds
            max_delay: Maximum delay between retries in seconds
            exponential_base: Base for exponential backoff
            jitter: Whether to add random jitter to delays
            retryable_exceptions: List of exception types that should trigger retries
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or [
            ConnectionError,
            TimeoutError,
            OSError,
        ]


class CircuitBreakerConfig:
    """Configuration for circuit breaker pattern."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        """
        Initialize circuit breaker configuration.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time to wait before attempting recovery
            expected_exception: Exception type that triggers circuit breaker
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception


class CircuitBreakerState:
    """Circuit breaker state management."""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "closed"  # closed, open, half-open
    
    def record_success(self) -> None:
        """Record a successful operation."""
        self.failure_count = 0
        self.state = "closed"
        self.last_failure_time = None
    
    def record_failure(self) -> None:
        """Record a failed operation."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.config.failure_threshold:
            self.state = "open"
    
    def can_attempt(self) -> bool:
        """Check if an operation can be attempted."""
        if self.state == "closed":
            return True
        
        if self.state == "open":
            if (self.last_failure_time and 
                datetime.now() - self.last_failure_time > timedelta(seconds=self.config.recovery_timeout)):
                self.state = "half-open"
                return True
            return False
        
        # half-open state
        return True


class ErrorRecoveryManager:
    """Manages error recovery strategies across the system."""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreakerState] = {}
        self.error_counts: Dict[str, int] = {}
        self.last_errors: Dict[str, datetime] = {}
    
    def get_circuit_breaker(self, service_name: str, config: CircuitBreakerConfig) -> CircuitBreakerState:
        """Get or create a circuit breaker for a service."""
        if service_name not in self.circuit_breakers:
            self.circuit_breakers[service_name] = CircuitBreakerState(config)
        return self.circuit_breakers[service_name]
    
    def record_error(self, service_name: str, error: Exception) -> None:
        """Record an error for a service."""
        self.error_counts[service_name] = self.error_counts.get(service_name, 0) + 1
        self.last_errors[service_name] = datetime.now()
        
        logger.error(f"Error in {service_name}: {error}")
        logger.debug(f"Error traceback: {traceback.format_exc()}")
    
    def get_error_stats(self, service_name: str) -> Dict[str, Any]:
        """Get error statistics for a service."""
        return {
            "error_count": self.error_counts.get(service_name, 0),
            "last_error": self.last_errors.get(service_name),
            "circuit_breaker_state": self.circuit_breakers.get(service_name, {}).state if service_name in self.circuit_breakers else "closed"
        }


# Global error recovery manager
error_recovery_manager = ErrorRecoveryManager()


def retry_with_backoff(
    config: Optional[RetryConfig] = None,
    service_name: Optional[str] = None
) -> Callable:
    """
    Decorator for retrying operations with exponential backoff.
    
    Args:
        config: Retry configuration
        service_name: Name of the service for error tracking
    
    Returns:
        Decorated function with retry logic
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    if asyncio.iscoroutinefunction(func):
                        result = await func(*args, **kwargs)
                    else:
                        result = func(*args, **kwargs)
                    
                    # Success - reset error tracking
                    if service_name:
                        error_recovery_manager.error_counts.pop(service_name, None)
                    
                    return result
                
                except Exception as e:
                    last_exception = e
                    
                    # Record error
                    if service_name:
                        error_recovery_manager.record_error(service_name, e)
                    
                    # Check if this exception should trigger a retry
                    if not any(isinstance(e, exc_type) for exc_type in config.retryable_exceptions):
                        logger.warning(f"Non-retryable exception in {func.__name__}: {e}")
                        raise
                    
                    # Don't retry on the last attempt
                    if attempt == config.max_attempts - 1:
                        break
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        config.base_delay * (config.exponential_base ** attempt),
                        config.max_delay
                    )
                    
                    # Add jitter if enabled
                    if config.jitter:
                        import random
                        delay *= (0.5 + random.random() * 0.5)
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{config.max_attempts} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.2f}s"
                    )
                    
                    await asyncio.sleep(delay)
            
            # All attempts failed
            logger.error(f"All {config.max_attempts} attempts failed for {func.__name__}")
            raise last_exception
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    result = func(*args, **kwargs)
                    
                    # Success - reset error tracking
                    if service_name:
                        error_recovery_manager.error_counts.pop(service_name, None)
                    
                    return result
                
                except Exception as e:
                    last_exception = e
                    
                    # Record error
                    if service_name:
                        error_recovery_manager.record_error(service_name, e)
                    
                    # Check if this exception should trigger a retry
                    if not any(isinstance(e, exc_type) for exc_type in config.retryable_exceptions):
                        logger.warning(f"Non-retryable exception in {func.__name__}: {e}")
                        raise
                    
                    # Don't retry on the last attempt
                    if attempt == config.max_attempts - 1:
                        break
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        config.base_delay * (config.exponential_base ** attempt),
                        config.max_delay
                    )
                    
                    # Add jitter if enabled
                    if config.jitter:
                        import random
                        delay *= (0.5 + random.random() * 0.5)
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{config.max_attempts} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.2f}s"
                    )
                    
                    time.sleep(delay)
            
            # All attempts failed
            logger.error(f"All {config.max_attempts} attempts failed for {func.__name__}")
            raise last_exception
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def circuit_breaker(
    config: Optional[CircuitBreakerConfig] = None,
    service_name: str = "default"
) -> Callable:
    """
    Decorator implementing circuit breaker pattern.
    
    Args:
        config: Circuit breaker configuration
        service_name: Name of the service
    
    Returns:
        Decorated function with circuit breaker logic
    """
    if config is None:
        config = CircuitBreakerConfig()
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            breaker = error_recovery_manager.get_circuit_breaker(service_name, config)
            
            if not breaker.can_attempt():
                raise CircuitBreakerOpenError(f"Circuit breaker open for {service_name}")
            
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                breaker.record_success()
                return result
            
            except config.expected_exception as e:
                breaker.record_failure()
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            breaker = error_recovery_manager.get_circuit_breaker(service_name, config)
            
            if not breaker.can_attempt():
                raise CircuitBreakerOpenError(f"Circuit breaker open for {service_name}")
            
            try:
                result = func(*args, **kwargs)
                breaker.record_success()
                return result
            
            except config.expected_exception as e:
                breaker.record_failure()
                raise
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def graceful_degradation(
    fallback_func: Optional[Callable] = None,
    service_name: Optional[str] = None,
    log_errors: bool = True
) -> Callable:
    """
    Decorator for graceful degradation when operations fail.
    
    Args:
        fallback_func: Function to call when main function fails
        service_name: Name of the service for error tracking
        log_errors: Whether to log errors
    
    Returns:
        Decorated function with graceful degradation
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Optional[T]:
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            
            except Exception as e:
                if log_errors:
                    logger.warning(f"Operation {func.__name__} failed, attempting graceful degradation: {e}")
                
                if service_name:
                    error_recovery_manager.record_error(service_name, e)
                
                if fallback_func:
                    try:
                        if asyncio.iscoroutinefunction(fallback_func):
                            return await fallback_func(*args, **kwargs)
                        else:
                            return fallback_func(*args, **kwargs)
                    except Exception as fallback_error:
                        if log_errors:
                            logger.error(f"Fallback function also failed: {fallback_error}")
                
                return None
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Optional[T]:
            try:
                return func(*args, **kwargs)
            
            except Exception as e:
                if log_errors:
                    logger.warning(f"Operation {func.__name__} failed, attempting graceful degradation: {e}")
                
                if service_name:
                    error_recovery_manager.record_error(service_name, e)
                
                if fallback_func:
                    try:
                        return fallback_func(*args, **kwargs)
                    except Exception as fallback_error:
                        if log_errors:
                            logger.error(f"Fallback function also failed: {fallback_error}")
                
                return None
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Custom exceptions
class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


class ServiceDegradedError(Exception):
    """Raised when service is running in degraded mode."""
    pass


class RetryExhaustedError(Exception):
    """Raised when all retry attempts are exhausted."""
    pass