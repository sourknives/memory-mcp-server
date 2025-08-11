"""
Security configuration for the cross-tool memory server.

This module provides configuration classes and utilities for security settings
including encryption, authentication, rate limiting, and TLS.
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import yaml

logger = logging.getLogger(__name__)


@dataclass
class EncryptionConfig:
    """Configuration for data encryption."""
    enabled: bool = True
    passphrase: Optional[str] = None
    passphrase_env_var: str = "ENCRYPTION_PASSPHRASE"
    auto_generate_salt: bool = True
    salt_file: Optional[str] = None
    
    def __post_init__(self):
        """Load passphrase from environment if not provided."""
        if not self.passphrase and self.passphrase_env_var:
            self.passphrase = os.getenv(self.passphrase_env_var)
        
        if not self.passphrase:
            self.enabled = False
            logger.warning("No encryption passphrase provided, encryption disabled")


@dataclass
class AuthenticationConfig:
    """Configuration for API authentication."""
    enabled: bool = True
    api_keys: List[str] = field(default_factory=list)
    api_keys_env_var: str = "API_KEYS"
    hash_keys: bool = True
    
    def __post_init__(self):
        """Load API keys from environment if not provided."""
        if not self.api_keys and self.api_keys_env_var:
            env_keys = os.getenv(self.api_keys_env_var)
            if env_keys:
                self.api_keys = [key.strip() for key in env_keys.split(",") if key.strip()]
        
        if not self.api_keys:
            self.enabled = False
            logger.warning("No API keys provided, authentication disabled")


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    enabled: bool = True
    max_requests: int = 100
    time_window: int = 60  # seconds
    burst_size: Optional[int] = None
    exempt_paths: List[str] = field(default_factory=lambda: ["/health", "/docs", "/redoc", "/openapi.json"])


@dataclass
class TLSConfig:
    """Configuration for TLS/HTTPS."""
    enabled: bool = False
    cert_file: Optional[str] = None
    key_file: Optional[str] = None
    ca_file: Optional[str] = None
    auto_generate: bool = True
    require_https: bool = False


@dataclass
class AccessControlConfig:
    """Configuration for access control."""
    allowed_origins: List[str] = field(default_factory=lambda: ["http://localhost:*", "http://127.0.0.1:*"])
    allowed_ips: Optional[List[str]] = None
    security_headers: bool = True


@dataclass
class SecurityConfig:
    """Complete security configuration."""
    encryption: EncryptionConfig = field(default_factory=EncryptionConfig)
    authentication: AuthenticationConfig = field(default_factory=AuthenticationConfig)
    rate_limiting: RateLimitConfig = field(default_factory=RateLimitConfig)
    tls: TLSConfig = field(default_factory=TLSConfig)
    access_control: AccessControlConfig = field(default_factory=AccessControlConfig)
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "SecurityConfig":
        """Create SecurityConfig from dictionary."""
        return cls(
            encryption=EncryptionConfig(**config_dict.get("encryption", {})),
            authentication=AuthenticationConfig(**config_dict.get("authentication", {})),
            rate_limiting=RateLimitConfig(**config_dict.get("rate_limiting", {})),
            tls=TLSConfig(**config_dict.get("tls", {})),
            access_control=AccessControlConfig(**config_dict.get("access_control", {}))
        )
    
    @classmethod
    def from_yaml_file(cls, file_path: str) -> "SecurityConfig":
        """Load SecurityConfig from YAML file."""
        try:
            with open(file_path, 'r') as f:
                config_dict = yaml.safe_load(f) or {}
            
            return cls.from_dict(config_dict.get("security", {}))
            
        except FileNotFoundError:
            logger.warning(f"Security config file not found: {file_path}, using defaults")
            return cls()
        except Exception as e:
            logger.error(f"Error loading security config from {file_path}: {e}")
            return cls()
    
    @classmethod
    def from_env(cls) -> "SecurityConfig":
        """Create SecurityConfig from environment variables."""
        return cls(
            encryption=EncryptionConfig(
                enabled=os.getenv("ENCRYPTION_ENABLED", "true").lower() == "true",
                passphrase=os.getenv("ENCRYPTION_PASSPHRASE"),
            ),
            authentication=AuthenticationConfig(
                enabled=os.getenv("AUTH_ENABLED", "true").lower() == "true",
                api_keys=os.getenv("API_KEYS", "").split(",") if os.getenv("API_KEYS") else [],
            ),
            rate_limiting=RateLimitConfig(
                enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
                max_requests=int(os.getenv("RATE_LIMIT_REQUESTS", "100")),
                time_window=int(os.getenv("RATE_LIMIT_WINDOW", "60")),
            ),
            tls=TLSConfig(
                enabled=os.getenv("TLS_ENABLED", "false").lower() == "true",
                cert_file=os.getenv("TLS_CERT_FILE"),
                key_file=os.getenv("TLS_KEY_FILE"),
                require_https=os.getenv("REQUIRE_HTTPS", "false").lower() == "true",
            ),
            access_control=AccessControlConfig(
                allowed_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:*,http://127.0.0.1:*").split(","),
                allowed_ips=os.getenv("ALLOWED_IPS", "").split(",") if os.getenv("ALLOWED_IPS") else None,
            )
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert SecurityConfig to dictionary."""
        return {
            "security": {
                "encryption": {
                    "enabled": self.encryption.enabled,
                    "passphrase_env_var": self.encryption.passphrase_env_var,
                    "auto_generate_salt": self.encryption.auto_generate_salt,
                    "salt_file": self.encryption.salt_file,
                },
                "authentication": {
                    "enabled": self.authentication.enabled,
                    "api_keys_env_var": self.authentication.api_keys_env_var,
                    "hash_keys": self.authentication.hash_keys,
                },
                "rate_limiting": {
                    "enabled": self.rate_limiting.enabled,
                    "max_requests": self.rate_limiting.max_requests,
                    "time_window": self.rate_limiting.time_window,
                    "burst_size": self.rate_limiting.burst_size,
                    "exempt_paths": self.rate_limiting.exempt_paths,
                },
                "tls": {
                    "enabled": self.tls.enabled,
                    "cert_file": self.tls.cert_file,
                    "key_file": self.tls.key_file,
                    "ca_file": self.tls.ca_file,
                    "auto_generate": self.tls.auto_generate,
                    "require_https": self.tls.require_https,
                },
                "access_control": {
                    "allowed_origins": self.access_control.allowed_origins,
                    "allowed_ips": self.access_control.allowed_ips,
                    "security_headers": self.access_control.security_headers,
                }
            }
        }
    
    def save_to_yaml_file(self, file_path: str) -> None:
        """Save SecurityConfig to YAML file."""
        try:
            config_dict = self.to_dict()
            
            with open(file_path, 'w') as f:
                yaml.dump(config_dict, f, default_flow_style=False, indent=2)
            
            logger.info(f"Security config saved to {file_path}")
            
        except Exception as e:
            logger.error(f"Error saving security config to {file_path}: {e}")
            raise


def load_security_config(
    config_file: Optional[str] = None,
    use_env: bool = True
) -> SecurityConfig:
    """
    Load security configuration from file or environment.
    
    Args:
        config_file: Path to YAML configuration file
        use_env: Whether to use environment variables as fallback
        
    Returns:
        SecurityConfig: Loaded configuration
    """
    if config_file:
        config = SecurityConfig.from_yaml_file(config_file)
    elif use_env:
        config = SecurityConfig.from_env()
    else:
        config = SecurityConfig()
    
    logger.info("Security configuration loaded")
    return config


def create_example_config_file(file_path: str) -> None:
    """Create an example security configuration file."""
    example_config = SecurityConfig()
    
    # Add some example values
    example_config.encryption.passphrase = "your-encryption-passphrase-here"
    example_config.authentication.api_keys = ["your-api-key-here"]
    example_config.tls.enabled = True
    example_config.tls.cert_file = "/path/to/cert.pem"
    example_config.tls.key_file = "/path/to/key.pem"
    
    example_config.save_to_yaml_file(file_path)
    logger.info(f"Example security config created at {file_path}")


if __name__ == "__main__":
    # Create example configuration file
    create_example_config_file("security_config_example.yml")