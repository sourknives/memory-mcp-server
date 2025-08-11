"""
Rate limiting middleware for the memory server.

This module provides rate limiting functionality to prevent abuse
and ensure fair usage of the API endpoints.
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from typing import Dict, Optional, Tuple, Any

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter implementation."""
    
    def __init__(
        self,
        max_requests: int = 100,
        time_window: int = 60,
        burst_size: Optional[int] = None
    ):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests allowed in time window
            time_window: Time window in seconds
            burst_size: Maximum burst size (defaults to max_requests)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.burst_size = burst_size or max_requests
        
        # Token bucket for each client
        self.buckets: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "tokens": self.burst_size,
            "last_refill": time.time(),
            "requests": deque()
        })
        
        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_interval = 300  # 5 minutes
        
        logger.info(f"Rate limiter initialized: {max_requests} req/{time_window}s")
    
    def _refill_tokens(self, bucket: Dict[str, Any]) -> None:
        """Refill tokens in the bucket based on elapsed time."""
        now = time.time()
        elapsed = now - bucket["last_refill"]
        
        # Calculate tokens to add based on elapsed time
        tokens_to_add = (elapsed / self.time_window) * self.max_requests
        bucket["tokens"] = min(self.burst_size, bucket["tokens"] + tokens_to_add)
        bucket["last_refill"] = now
    
    def _cleanup_old_requests(self, bucket: Dict[str, Any]) -> None:
        """Remove old requests from the sliding window."""
        now = time.time()
        cutoff = now - self.time_window
        
        while bucket["requests"] and bucket["requests"][0] < cutoff:
            bucket["requests"].popleft()
    
    def is_allowed(self, client_id: str, cost: int = 1) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is allowed for client.
        
        Args:
            client_id: Unique identifier for the client
            cost: Cost of the request in tokens
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (allowed, rate_limit_info)
        """
        bucket = self.buckets[client_id]
        now = time.time()
        
        # Refill tokens
        self._refill_tokens(bucket)
        
        # Clean up old requests
        self._cleanup_old_requests(bucket)
        
        # Check if request is allowed
        allowed = bucket["tokens"] >= cost
        
        if allowed:
            # Consume tokens
            bucket["tokens"] -= cost
            bucket["requests"].append(now)
        
        # Prepare rate limit info
        rate_limit_info = {
            "limit": self.max_requests,
            "remaining": max(0, int(bucket["tokens"])),
            "reset": int(bucket["last_refill"] + self.time_window),
            "retry_after": None
        }
        
        if not allowed:
            # Calculate retry after time
            if bucket["requests"]:
                oldest_request = bucket["requests"][0]
                rate_limit_info["retry_after"] = max(1, int(oldest_request + self.time_window - now))
            else:
                rate_limit_info["retry_after"] = 1
        
        return allowed, rate_limit_info
    
    def reset_client(self, client_id: str) -> None:
        """Reset rate limit for a specific client."""
        if client_id in self.buckets:
            del self.buckets[client_id]
            logger.info(f"Rate limit reset for client: {client_id}")
    
    def get_client_stats(self, client_id: str) -> Dict[str, Any]:
        """Get rate limit statistics for a client."""
        if client_id not in self.buckets:
            return {
                "tokens": self.burst_size,
                "requests_in_window": 0,
                "last_request": None
            }
        
        bucket = self.buckets[client_id]
        self._cleanup_old_requests(bucket)
        
        return {
            "tokens": int(bucket["tokens"]),
            "requests_in_window": len(bucket["requests"]),
            "last_request": bucket["requests"][-1] if bucket["requests"] else None
        }
    
    async def start_cleanup_task(self) -> None:
        """Start background cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Rate limiter cleanup task started")
    
    async def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("Rate limiter cleanup task stopped")
    
    async def _cleanup_loop(self) -> None:
        """Background task to clean up old buckets."""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                await self._cleanup_buckets()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in rate limiter cleanup: {e}")
    
    async def _cleanup_buckets(self) -> None:
        """Clean up inactive buckets."""
        now = time.time()
        cutoff = now - (self.time_window * 2)  # Keep buckets for 2x time window
        
        inactive_clients = []
        for client_id, bucket in self.buckets.items():
            if bucket["last_refill"] < cutoff and not bucket["requests"]:
                inactive_clients.append(client_id)
        
        for client_id in inactive_clients:
            del self.buckets[client_id]
        
        if inactive_clients:
            logger.debug(f"Cleaned up {len(inactive_clients)} inactive rate limit buckets")


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting requests."""
    
    def __init__(
        self,
        app,
        rate_limiter: RateLimiter,
        get_client_id: Optional[callable] = None,
        exempt_paths: Optional[set] = None,
        cost_calculator: Optional[callable] = None
    ):
        """
        Initialize rate limiting middleware.
        
        Args:
            app: FastAPI application
            rate_limiter: Rate limiter instance
            get_client_id: Function to extract client ID from request
            exempt_paths: Set of paths exempt from rate limiting
            cost_calculator: Function to calculate request cost
        """
        super().__init__(app)
        self.rate_limiter = rate_limiter
        self.get_client_id = get_client_id or self._default_get_client_id
        self.exempt_paths = exempt_paths or {"/health", "/docs", "/redoc", "/openapi.json"}
        self.cost_calculator = cost_calculator or self._default_cost_calculator
        
        logger.info("Rate limiting middleware initialized")
    
    def _default_get_client_id(self, request: Request) -> str:
        """Default client ID extraction from request."""
        # Try to get client IP
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        if hasattr(request.client, "host"):
            return request.client.host
        
        return "unknown"
    
    def _default_cost_calculator(self, request: Request) -> int:
        """Default request cost calculation."""
        # Different costs for different endpoints
        path = request.url.path
        method = request.method
        
        # Higher cost for expensive operations
        if "/context/search" in path or "/search" in path:
            return 3  # Search operations are more expensive
        elif method in ["POST", "PUT", "DELETE"]:
            return 2  # Write operations cost more
        else:
            return 1  # Read operations
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request through rate limiting middleware."""
        
        # Check if path is exempt
        if request.url.path in self.exempt_paths:
            return await call_next(request)
        
        # Get client ID and request cost
        client_id = self.get_client_id(request)
        cost = self.cost_calculator(request)
        
        # Check rate limit
        allowed, rate_limit_info = self.rate_limiter.is_allowed(client_id, cost)
        
        if not allowed:
            logger.warning(f"Rate limit exceeded for client: {client_id}")
            
            # Create rate limit exceeded response
            headers = {
                "X-RateLimit-Limit": str(rate_limit_info["limit"]),
                "X-RateLimit-Remaining": str(rate_limit_info["remaining"]),
                "X-RateLimit-Reset": str(rate_limit_info["reset"]),
            }
            
            if rate_limit_info["retry_after"]:
                headers["Retry-After"] = str(rate_limit_info["retry_after"])
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers=headers
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(rate_limit_info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(rate_limit_info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(rate_limit_info["reset"])
        
        return response


def create_rate_limiter(
    max_requests: int = 100,
    time_window: int = 60,
    burst_size: Optional[int] = None
) -> RateLimiter:
    """
    Create a rate limiter with configuration.
    
    Args:
        max_requests: Maximum requests per time window
        time_window: Time window in seconds
        burst_size: Maximum burst size
        
    Returns:
        RateLimiter: Configured rate limiter
    """
    return RateLimiter(
        max_requests=max_requests,
        time_window=time_window,
        burst_size=burst_size
    )


def create_rate_limiting_middleware(
    rate_limiter: RateLimiter,
    get_client_id: Optional[callable] = None,
    exempt_paths: Optional[list] = None,
    cost_calculator: Optional[callable] = None
) -> type:
    """
    Create rate limiting middleware with configuration.
    
    Args:
        rate_limiter: Rate limiter instance
        get_client_id: Function to extract client ID
        exempt_paths: List of exempt paths
        cost_calculator: Function to calculate request cost
        
    Returns:
        type: Configured middleware class
    """
    class ConfiguredRateLimitingMiddleware(RateLimitingMiddleware):
        def __init__(self, app):
            super().__init__(
                app,
                rate_limiter=rate_limiter,
                get_client_id=get_client_id,
                exempt_paths=set(exempt_paths) if exempt_paths else None,
                cost_calculator=cost_calculator
            )
    
    return ConfiguredRateLimitingMiddleware