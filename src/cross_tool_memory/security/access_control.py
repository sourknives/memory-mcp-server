"""
Access control middleware and authentication for the memory server.

This module provides API key authentication and access control middleware
to secure the REST API endpoints.
"""

import hashlib
import hmac
import logging
import secrets
import time
from typing import Optional, Set, Dict, Any

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


class APIKeyAuth:
    """API key authentication handler."""
    
    def __init__(self, api_keys: Optional[Set[str]] = None, hash_keys: bool = True):
        """
        Initialize API key authentication.
        
        Args:
            api_keys: Set of valid API keys. If None, authentication is disabled.
            hash_keys: Whether to hash API keys for secure storage
        """
        self.enabled = api_keys is not None and len(api_keys) > 0
        self.hash_keys = hash_keys
        
        if self.enabled:
            if hash_keys:
                # Store hashed versions of API keys
                self.valid_keys = {self._hash_key(key) for key in api_keys}
            else:
                self.valid_keys = set(api_keys)
            
            logger.info(f"API key authentication enabled with {len(api_keys)} keys")
        else:
            self.valid_keys = set()
            logger.info("API key authentication disabled")
    
    def _hash_key(self, api_key: str) -> str:
        """Hash an API key using SHA-256."""
        return hashlib.sha256(api_key.encode('utf-8')).hexdigest()
    
    def verify_key(self, api_key: str) -> bool:
        """
        Verify an API key.
        
        Args:
            api_key: API key to verify
            
        Returns:
            bool: True if key is valid, False otherwise
        """
        if not self.enabled:
            return True  # Authentication disabled
        
        if self.hash_keys:
            hashed_key = self._hash_key(api_key)
            return hashed_key in self.valid_keys
        else:
            return api_key in self.valid_keys
    
    def generate_key(self, length: int = 32) -> str:
        """
        Generate a new API key.
        
        Args:
            length: Length of the API key in bytes
            
        Returns:
            str: New API key
        """
        return secrets.token_urlsafe(length)
    
    def add_key(self, api_key: str) -> None:
        """
        Add a new API key.
        
        Args:
            api_key: API key to add
        """
        if self.hash_keys:
            hashed_key = self._hash_key(api_key)
            self.valid_keys.add(hashed_key)
        else:
            self.valid_keys.add(api_key)
        
        self.enabled = True
        logger.info("New API key added")
    
    def remove_key(self, api_key: str) -> bool:
        """
        Remove an API key.
        
        Args:
            api_key: API key to remove
            
        Returns:
            bool: True if key was removed, False if not found
        """
        if self.hash_keys:
            hashed_key = self._hash_key(api_key)
            if hashed_key in self.valid_keys:
                self.valid_keys.remove(hashed_key)
                logger.info("API key removed")
                return True
        else:
            if api_key in self.valid_keys:
                self.valid_keys.remove(api_key)
                logger.info("API key removed")
                return True
        
        return False


class AccessControlMiddleware(BaseHTTPMiddleware):
    """Middleware for access control and security headers."""
    
    def __init__(
        self,
        app,
        api_key_auth: Optional[APIKeyAuth] = None,
        allowed_origins: Optional[Set[str]] = None,
        allowed_ips: Optional[Set[str]] = None,
        require_https: bool = False,
        security_headers: bool = True
    ):
        """
        Initialize access control middleware.
        
        Args:
            app: FastAPI application
            api_key_auth: API key authentication handler
            allowed_origins: Set of allowed origins for CORS
            allowed_ips: Set of allowed IP addresses
            require_https: Whether to require HTTPS
            security_headers: Whether to add security headers
        """
        super().__init__(app)
        self.api_key_auth = api_key_auth
        self.allowed_origins = allowed_origins or {"localhost", "127.0.0.1"}
        self.allowed_ips = allowed_ips
        self.require_https = require_https
        self.security_headers = security_headers
        
        # Security headers to add
        self.default_security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'",
        }
        
        logger.info("Access control middleware initialized")
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request through access control middleware."""
        
        # Check IP allowlist if configured
        if self.allowed_ips:
            client_ip = self._get_client_ip(request)
            if client_ip not in self.allowed_ips:
                logger.warning(f"Access denied for IP: {client_ip}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied - IP not allowed"
                )
        
        # Check HTTPS requirement
        if self.require_https and request.url.scheme != "https":
            logger.warning(f"HTTPS required but got {request.url.scheme}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="HTTPS required"
            )
        
        # Check origin for CORS
        origin = request.headers.get("origin")
        if origin:
            origin_host = origin.replace("http://", "").replace("https://", "").split(":")[0]
            if origin_host not in self.allowed_origins:
                logger.warning(f"Access denied for origin: {origin}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied - origin not allowed"
                )
        
        # Process request
        response = await call_next(request)
        
        # Add security headers
        if self.security_headers:
            for header, value in self.default_security_headers.items():
                response.headers[header] = value
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request."""
        # Check for forwarded headers (behind proxy)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fallback to direct connection
        if hasattr(request.client, "host"):
            return request.client.host
        
        return "unknown"


class SecureHTTPBearer(HTTPBearer):
    """Secure HTTP Bearer token authentication."""
    
    def __init__(self, api_key_auth: APIKeyAuth, auto_error: bool = True):
        """
        Initialize secure HTTP Bearer authentication.
        
        Args:
            api_key_auth: API key authentication handler
            auto_error: Whether to automatically raise HTTP exceptions
        """
        super().__init__(auto_error=auto_error)
        self.api_key_auth = api_key_auth
    
    async def __call__(self, request: Request) -> Optional[HTTPAuthorizationCredentials]:
        """Authenticate request using Bearer token."""
        credentials = await super().__call__(request)
        
        if not credentials:
            if self.api_key_auth.enabled:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing authentication token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return None
        
        # Verify API key
        if not self.api_key_auth.verify_key(credentials.credentials):
            logger.warning("Invalid API key provided")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return credentials


def create_api_key_auth(
    api_keys: Optional[list] = None,
    env_var: str = "API_KEYS",
    hash_keys: bool = True
) -> APIKeyAuth:
    """
    Create API key authentication from configuration.
    
    Args:
        api_keys: List of API keys
        env_var: Environment variable containing comma-separated API keys
        hash_keys: Whether to hash API keys for secure storage
        
    Returns:
        APIKeyAuth: Configured API key authentication
    """
    import os
    
    keys = set()
    
    # Add keys from parameter
    if api_keys:
        keys.update(api_keys)
    
    # Add keys from environment variable
    env_keys = os.getenv(env_var)
    if env_keys:
        keys.update(key.strip() for key in env_keys.split(",") if key.strip())
    
    return APIKeyAuth(keys if keys else None, hash_keys=hash_keys)


def create_access_control_middleware(
    api_key_auth: Optional[APIKeyAuth] = None,
    allowed_origins: Optional[list] = None,
    allowed_ips: Optional[list] = None,
    require_https: bool = False,
    security_headers: bool = True
) -> type:
    """
    Create access control middleware with configuration.
    
    Args:
        api_key_auth: API key authentication handler
        allowed_origins: List of allowed origins
        allowed_ips: List of allowed IP addresses
        require_https: Whether to require HTTPS
        security_headers: Whether to add security headers
        
    Returns:
        type: Configured middleware class
    """
    class ConfiguredAccessControlMiddleware(AccessControlMiddleware):
        def __init__(self, app):
            super().__init__(
                app,
                api_key_auth=api_key_auth,
                allowed_origins=set(allowed_origins) if allowed_origins else None,
                allowed_ips=set(allowed_ips) if allowed_ips else None,
                require_https=require_https,
                security_headers=security_headers
            )
    
    return ConfiguredAccessControlMiddleware