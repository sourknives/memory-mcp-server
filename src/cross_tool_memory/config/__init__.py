"""
Configuration management for the cross-tool memory system.

This package contains database configuration, connection management,
configuration management with hot-reload, and other system configuration utilities.
"""

from .database import (
    DatabaseConfig,
    DatabaseManager,
    DatabaseError,
    DatabaseConnectionError,
    DatabaseInitializationError,
    get_database_manager,
    reset_database_manager,
)

from .config_manager import (
    AppConfig,
    ServerConfig,
    AIModelsConfig,
    EmbeddingModelConfig,
    VectorStoreConfig,
    LLMConfig,
    SecurityConfig,
    MemoryConfig,
    LoggingConfig,
    MonitoringConfig,
    ConfigManager,
    ModelInfo,
    get_config_manager,
    get_config,
    reset_config_manager,
)

from .model_manager import (
    ModelManager,
    ModelMetadata,
    ModelDownloadError,
    ModelValidationError,
    get_model_manager,
    reset_model_manager,
)

from .security_config import (
    SecurityConfig as LegacySecurityConfig,
    EncryptionConfig,
    AuthenticationConfig,
    RateLimitConfig,
    TLSConfig,
    AccessControlConfig,
    load_security_config,
    create_example_config_file,
)

__all__ = [
    # Database configuration
    "DatabaseConfig",
    "DatabaseManager", 
    "DatabaseError",
    "DatabaseConnectionError",
    "DatabaseInitializationError",
    "get_database_manager",
    "reset_database_manager",
    
    # Configuration management
    "AppConfig",
    "ServerConfig",
    "AIModelsConfig",
    "EmbeddingModelConfig",
    "VectorStoreConfig",
    "LLMConfig",
    "SecurityConfig",
    "MemoryConfig",
    "LoggingConfig",
    "MonitoringConfig",
    "ConfigManager",
    "ModelInfo",
    "get_config_manager",
    "get_config",
    "reset_config_manager",
    
    # Model management
    "ModelManager",
    "ModelMetadata",
    "ModelDownloadError",
    "ModelValidationError",
    "get_model_manager",
    "reset_model_manager",
    
    # Legacy security configuration
    "LegacySecurityConfig",
    "EncryptionConfig",
    "AuthenticationConfig",
    "RateLimitConfig",
    "TLSConfig",
    "AccessControlConfig",
    "load_security_config",
    "create_example_config_file",
]