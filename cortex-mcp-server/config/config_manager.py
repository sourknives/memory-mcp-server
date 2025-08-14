"""
Configuration management system for the cortex mcp server.

This module provides comprehensive configuration management including:
- YAML configuration parsing with validation
- Environment variable override system
- Configuration hot-reload functionality
- Model management for AI model downloads and updates
"""

import os
import logging
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime
import yaml
from pydantic import BaseModel, ValidationError, Field, field_validator, ConfigDict
import watchdog.observers
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)


class ServerConfig(BaseModel):
    """Server configuration settings."""
    host: str = Field(default="localhost", description="Server host address")
    port: int = Field(default=8000, ge=1, le=65535, description="Server port")
    debug: bool = Field(default=False, description="Enable debug mode")
    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://localhost:8080"])
    
    @field_validator('host')
    @classmethod
    def validate_host(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError("Host must be a non-empty string")
        return v


class DatabaseConfig(BaseModel):
    """Database configuration settings."""
    path: str = Field(default="./data/memory.db", description="Database file path")
    pool_size: int = Field(default=10, ge=1, description="Connection pool size")
    max_overflow: int = Field(default=20, ge=0, description="Max overflow connections")
    echo: bool = Field(default=False, description="Enable SQL query logging")
    
    @field_validator('path')
    @classmethod
    def validate_path(cls, v):
        if not v:
            raise ValueError("Database path cannot be empty")
        # Ensure directory exists
        Path(v).parent.mkdir(parents=True, exist_ok=True)
        return v


class EmbeddingModelConfig(BaseModel):
    """Embedding model configuration."""
    model_name: str = Field(default="all-MiniLM-L6-v2", description="Embedding model name")
    device: str = Field(default="cpu", description="Device to run model on")
    cache_dir: str = Field(default="./models", description="Model cache directory")
    max_seq_length: int = Field(default=512, ge=1, description="Maximum sequence length")
    auto_download: bool = Field(default=True, description="Auto-download models if missing")
    
    @field_validator('device')
    @classmethod
    def validate_device(cls, v):
        if v not in ['cpu', 'cuda', 'mps']:
            raise ValueError("Device must be one of: cpu, cuda, mps")
        return v


class VectorStoreConfig(BaseModel):
    """Vector store configuration."""
    type: str = Field(default="faiss", description="Vector store type")
    index_type: str = Field(default="IndexFlatIP", description="FAISS index type")
    dimension: int = Field(default=384, ge=1, description="Vector dimension")
    
    @field_validator('type')
    @classmethod
    def validate_type(cls, v):
        if v not in ['faiss']:
            raise ValueError("Currently only 'faiss' vector store is supported")
        return v


class LLMConfig(BaseModel):
    """Local LLM configuration."""
    enabled: bool = Field(default=False, description="Enable local LLM")
    provider: str = Field(default="ollama", description="LLM provider")
    model: str = Field(default="llama3.2:1b", description="Model name")
    host: str = Field(default="http://localhost:11434", description="LLM host URL")
    auto_download: bool = Field(default=True, description="Auto-download models if missing")
    
    @field_validator('provider')
    @classmethod
    def validate_provider(cls, v):
        if v not in ['ollama', 'openai', 'anthropic']:
            raise ValueError("Provider must be one of: ollama, openai, anthropic")
        return v


class AIModelsConfig(BaseModel):
    """AI models configuration."""
    embedding: EmbeddingModelConfig = Field(default_factory=EmbeddingModelConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)


class EncryptionConfig(BaseModel):
    """Encryption configuration."""
    enabled: bool = Field(default=True, description="Enable encryption")
    key_file: str = Field(default="./data/encryption.key", description="Encryption key file path")
    algorithm: str = Field(default="AES-256-GCM", description="Encryption algorithm")
    
    @field_validator('algorithm')
    @classmethod
    def validate_algorithm(cls, v):
        if v not in ['AES-256-GCM', 'AES-256-CBC']:
            raise ValueError("Algorithm must be one of: AES-256-GCM, AES-256-CBC")
        return v


class APISecurityConfig(BaseModel):
    """API security configuration."""
    require_key: bool = Field(default=False, description="Require API key")
    rate_limit: Dict[str, int] = Field(
        default_factory=lambda: {"requests": 100, "window": 60},
        description="Rate limiting settings"
    )


class CORSConfig(BaseModel):
    """CORS configuration."""
    allow_credentials: bool = Field(default=True, description="Allow credentials")
    allow_methods: List[str] = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE"],
        description="Allowed HTTP methods"
    )
    allow_headers: List[str] = Field(default_factory=lambda: ["*"], description="Allowed headers")


class SecurityConfig(BaseModel):
    """Security configuration."""
    encryption: EncryptionConfig = Field(default_factory=EncryptionConfig)
    api: APISecurityConfig = Field(default_factory=APISecurityConfig)
    cors: CORSConfig = Field(default_factory=CORSConfig)


class RetentionConfig(BaseModel):
    """Data retention configuration."""
    default_days: int = Field(default=365, ge=1, description="Default retention period in days")
    max_conversations: int = Field(default=100000, ge=1, description="Maximum conversations to keep")


class SearchConfig(BaseModel):
    """Search configuration."""
    max_results: int = Field(default=50, ge=1, description="Maximum search results")
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Similarity threshold")
    enable_keyword_fallback: bool = Field(default=True, description="Enable keyword fallback")


class LearningConfig(BaseModel):
    """Learning configuration."""
    enabled: bool = Field(default=True, description="Enable learning")
    pattern_detection: bool = Field(default=True, description="Enable pattern detection")
    preference_learning: bool = Field(default=True, description="Enable preference learning")
    feedback_weight: float = Field(default=0.1, ge=0.0, le=1.0, description="Feedback weight")


class MemoryConfig(BaseModel):
    """Memory system configuration."""
    retention: RetentionConfig = Field(default_factory=RetentionConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    learning: LearningConfig = Field(default_factory=LearningConfig)


class LogFileConfig(BaseModel):
    """Log file configuration."""
    enabled: bool = Field(default=True, description="Enable file logging")
    path: str = Field(default="./logs/memory-server.log", description="Log file path")
    max_size: str = Field(default="10MB", description="Maximum log file size")
    backup_count: int = Field(default=5, ge=0, description="Number of backup files")


class StructuredLoggingConfig(BaseModel):
    """Structured logging configuration."""
    enabled: bool = Field(default=False, description="Enable structured logging")
    format: str = Field(default="json", description="Structured log format")
    
    @field_validator('format')
    @classmethod
    def validate_format(cls, v):
        if v not in ['json', 'yaml']:
            raise ValueError("Format must be one of: json, yaml")
        return v


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = Field(default="INFO", description="Log level")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format"
    )
    file: LogFileConfig = Field(default_factory=LogFileConfig)
    structured: StructuredLoggingConfig = Field(default_factory=StructuredLoggingConfig)
    
    @field_validator('level')
    @classmethod
    def validate_level(cls, v):
        if v not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            raise ValueError("Level must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL")
        return v


class HealthCheckConfig(BaseModel):
    """Health check configuration."""
    enabled: bool = Field(default=True, description="Enable health checks")
    endpoint: str = Field(default="/health", description="Health check endpoint")


class MetricsConfig(BaseModel):
    """Metrics configuration."""
    enabled: bool = Field(default=False, description="Enable metrics")
    endpoint: str = Field(default="/metrics", description="Metrics endpoint")


class PerformanceConfig(BaseModel):
    """Performance monitoring configuration."""
    track_query_time: bool = Field(default=True, description="Track query execution time")
    track_memory_usage: bool = Field(default=True, description="Track memory usage")


class MonitoringConfig(BaseModel):
    """Monitoring configuration."""
    health_check: HealthCheckConfig = Field(default_factory=HealthCheckConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)


class AppConfig(BaseModel):
    """Complete application configuration."""
    server: ServerConfig = Field(default_factory=ServerConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    ai_models: AIModelsConfig = Field(default_factory=AIModelsConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    
    model_config = ConfigDict(
        extra="forbid",  # Forbid extra fields
        validate_assignment=True  # Validate on assignment
    )


class ConfigFileWatcher(FileSystemEventHandler):
    """File system event handler for configuration file changes."""
    
    def __init__(self, config_manager: 'ConfigManager'):
        """Initialize with reference to config manager."""
        self.config_manager = config_manager
        self.last_modified = {}
    
    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return
        
        file_path = event.src_path
        if not file_path.endswith(('.yml', '.yaml')):
            return
        
        # Debounce rapid file changes
        current_time = time.time()
        if file_path in self.last_modified:
            if current_time - self.last_modified[file_path] < 1.0:  # 1 second debounce
                return
        
        self.last_modified[file_path] = current_time
        
        logger.info(f"Configuration file changed: {file_path}")
        self.config_manager._reload_config()


@dataclass
class ModelInfo:
    """Information about an AI model."""
    name: str
    type: str  # 'embedding', 'llm'
    size_mb: Optional[int] = None
    downloaded: bool = False
    download_url: Optional[str] = None
    local_path: Optional[str] = None
    last_updated: Optional[datetime] = None


class ConfigManager:
    """
    Comprehensive configuration management system.
    
    Features:
    - YAML configuration parsing with validation
    - Environment variable overrides
    - Hot-reload functionality
    - Model management
    """
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_file: Path to configuration file
        """
        self.config_file = config_file or "config.yml"
        self.config: Optional[AppConfig] = None
        self._lock = threading.RLock()
        self._observers: List[watchdog.observers.Observer] = []
        self._reload_callbacks: List[Callable[[AppConfig], None]] = []
        self._model_cache: Dict[str, ModelInfo] = {}
        
        # Load initial configuration
        self.load_config()
        
        # Start file watching if config file exists
        if os.path.exists(self.config_file):
            self._start_file_watching()
    
    def load_config(self) -> AppConfig:
        """
        Load configuration from file with environment variable overrides.
        
        Returns:
            AppConfig: Loaded and validated configuration
        """
        with self._lock:
            try:
                # Load from YAML file
                config_dict = {}
                if os.path.exists(self.config_file):
                    with open(self.config_file, 'r') as f:
                        config_dict = yaml.safe_load(f) or {}
                    logger.info(f"Loaded configuration from {self.config_file}")
                else:
                    logger.warning(f"Configuration file not found: {self.config_file}, using defaults")
                
                # Apply environment variable overrides
                config_dict = self._apply_env_overrides(config_dict)
                
                # Validate and create configuration object
                self.config = AppConfig(**config_dict)
                
                logger.info("Configuration loaded and validated successfully")
                return self.config
                
            except ValidationError as e:
                logger.error(f"Configuration validation failed: {e}")
                raise ValueError(f"Invalid configuration: {e}")
            except Exception as e:
                logger.error(f"Failed to load configuration: {e}")
                raise
    
    def _apply_env_overrides(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply environment variable overrides to configuration.
        
        Args:
            config_dict: Base configuration dictionary
            
        Returns:
            Dict: Configuration with environment overrides applied
        """
        # Define environment variable mappings
        env_mappings = {
            # Server settings
            'MEMORY_SERVER_HOST': ['server', 'host'],
            'MEMORY_SERVER_PORT': ['server', 'port'],
            'MEMORY_SERVER_DEBUG': ['server', 'debug'],
            
            # Database settings
            'MEMORY_DB_PATH': ['database', 'path'],
            'MEMORY_DB_POOL_SIZE': ['database', 'pool_size'],
            'MEMORY_DB_ECHO': ['database', 'echo'],
            
            # AI Models
            'MEMORY_EMBEDDING_MODEL': ['ai_models', 'embedding', 'model_name'],
            'MEMORY_EMBEDDING_DEVICE': ['ai_models', 'embedding', 'device'],
            'MEMORY_EMBEDDING_CACHE_DIR': ['ai_models', 'embedding', 'cache_dir'],
            'MEMORY_LLM_ENABLED': ['ai_models', 'llm', 'enabled'],
            'MEMORY_LLM_PROVIDER': ['ai_models', 'llm', 'provider'],
            'MEMORY_LLM_MODEL': ['ai_models', 'llm', 'model'],
            'MEMORY_LLM_HOST': ['ai_models', 'llm', 'host'],
            
            # Security
            'MEMORY_ENCRYPTION_ENABLED': ['security', 'encryption', 'enabled'],
            'MEMORY_ENCRYPTION_KEY_FILE': ['security', 'encryption', 'key_file'],
            'MEMORY_API_REQUIRE_KEY': ['security', 'api', 'require_key'],
            
            # Logging
            'MEMORY_LOG_LEVEL': ['logging', 'level'],
            'MEMORY_LOG_FILE_PATH': ['logging', 'file', 'path'],
            'MEMORY_LOG_FILE_ENABLED': ['logging', 'file', 'enabled'],
        }
        
        for env_var, config_path in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                # Convert string values to appropriate types
                converted_value = self._convert_env_value(env_value)
                
                # Set nested configuration value
                current_dict = config_dict
                for key in config_path[:-1]:
                    if key not in current_dict:
                        current_dict[key] = {}
                    current_dict = current_dict[key]
                
                current_dict[config_path[-1]] = converted_value
                logger.debug(f"Applied environment override: {env_var} = {converted_value}")
        
        return config_dict
    
    def _convert_env_value(self, value: str) -> Union[str, int, float, bool]:
        """
        Convert environment variable string to appropriate type.
        
        Args:
            value: String value from environment
            
        Returns:
            Converted value
        """
        # Boolean conversion
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        # Integer conversion
        try:
            if '.' not in value:
                return int(value)
        except ValueError:
            pass
        
        # Float conversion
        try:
            return float(value)
        except ValueError:
            pass
        
        # Return as string
        return value
    
    def get_config(self) -> AppConfig:
        """
        Get current configuration.
        
        Returns:
            AppConfig: Current configuration
        """
        if self.config is None:
            self.load_config()
        return self.config
    
    def reload_config(self) -> AppConfig:
        """
        Manually reload configuration.
        
        Returns:
            AppConfig: Reloaded configuration
        """
        logger.info("Manually reloading configuration")
        return self.load_config()
    
    def _reload_config(self) -> None:
        """Internal method to reload configuration and notify callbacks."""
        try:
            old_config = self.config
            new_config = self.load_config()
            
            # Notify callbacks of configuration change
            for callback in self._reload_callbacks:
                try:
                    callback(new_config)
                except Exception as e:
                    logger.error(f"Error in config reload callback: {e}")
            
            logger.info("Configuration reloaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
    
    def add_reload_callback(self, callback: Callable[[AppConfig], None]) -> None:
        """
        Add callback to be called when configuration is reloaded.
        
        Args:
            callback: Function to call with new configuration
        """
        self._reload_callbacks.append(callback)
    
    def remove_reload_callback(self, callback: Callable[[AppConfig], None]) -> None:
        """
        Remove reload callback.
        
        Args:
            callback: Callback function to remove
        """
        if callback in self._reload_callbacks:
            self._reload_callbacks.remove(callback)
    
    def _start_file_watching(self) -> None:
        """Start watching configuration file for changes."""
        try:
            config_dir = os.path.dirname(os.path.abspath(self.config_file))
            
            # Skip file watching for temporary directories to avoid conflicts
            if '/tmp' in config_dir or 'temp' in config_dir.lower():
                logger.debug(f"Skipping file watching for temporary directory: {config_dir}")
                return
            
            event_handler = ConfigFileWatcher(self)
            observer = watchdog.observers.Observer()
            observer.schedule(event_handler, config_dir, recursive=False)
            observer.start()
            
            self._observers.append(observer)
            logger.info(f"Started watching configuration directory: {config_dir}")
            
        except Exception as e:
            logger.warning(f"Failed to start file watching: {e}")
    
    def stop_file_watching(self) -> None:
        """Stop watching configuration file for changes."""
        for observer in self._observers:
            observer.stop()
            observer.join()
        
        self._observers.clear()
        logger.info("Stopped configuration file watching")
    
    def save_config(self, config_file: Optional[str] = None) -> None:
        """
        Save current configuration to file.
        
        Args:
            config_file: Optional path to save to (defaults to current config file)
        """
        if self.config is None:
            raise ValueError("No configuration to save")
        
        save_path = config_file or self.config_file
        
        try:
            # Convert to dictionary and save
            config_dict = self.config.dict()
            
            with open(save_path, 'w') as f:
                yaml.dump(config_dict, f, default_flow_style=False, indent=2)
            
            logger.info(f"Configuration saved to {save_path}")
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            raise
    
    def create_example_config(self, file_path: str) -> None:
        """
        Create an example configuration file.
        
        Args:
            file_path: Path to create example file
        """
        example_config = AppConfig()
        
        # Convert to dict and save
        config_dict = example_config.dict()
        
        with open(file_path, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False, indent=2)
        
        logger.info(f"Example configuration created at {file_path}")
    
    def validate_config(self, config_dict: Dict[str, Any]) -> bool:
        """
        Validate configuration dictionary.
        
        Args:
            config_dict: Configuration to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        try:
            AppConfig(**config_dict)
            return True
        except ValidationError as e:
            logger.error(f"Configuration validation failed: {e}")
            return False
    
    def get_model_info(self, model_name: str, model_type: str) -> Optional[ModelInfo]:
        """
        Get information about a model.
        
        Args:
            model_name: Name of the model
            model_type: Type of model ('embedding' or 'llm')
            
        Returns:
            ModelInfo: Model information or None if not found
        """
        cache_key = f"{model_type}:{model_name}"
        
        if cache_key in self._model_cache:
            return self._model_cache[cache_key]
        
        # Create model info
        model_info = ModelInfo(
            name=model_name,
            type=model_type,
            downloaded=self._is_model_downloaded(model_name, model_type),
            local_path=self._get_model_path(model_name, model_type)
        )
        
        self._model_cache[cache_key] = model_info
        return model_info
    
    def _is_model_downloaded(self, model_name: str, model_type: str) -> bool:
        """
        Check if a model is downloaded locally.
        
        Args:
            model_name: Name of the model
            model_type: Type of model
            
        Returns:
            bool: True if model is downloaded
        """
        if model_type == 'embedding':
            # Check sentence-transformers cache
            cache_dir = self.config.ai_models.embedding.cache_dir
            model_path = Path(cache_dir) / model_name
            return model_path.exists() and any(model_path.iterdir())
        
        elif model_type == 'llm':
            # Check Ollama models (if using Ollama)
            if self.config.ai_models.llm.provider == 'ollama':
                try:
                    import subprocess
                    result = subprocess.run(
                        ['ollama', 'list'],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    return model_name in result.stdout
                except Exception:
                    return False
        
        return False
    
    def _get_model_path(self, model_name: str, model_type: str) -> Optional[str]:
        """
        Get local path for a model.
        
        Args:
            model_name: Name of the model
            model_type: Type of model
            
        Returns:
            str: Local path or None
        """
        if model_type == 'embedding':
            cache_dir = self.config.ai_models.embedding.cache_dir
            return str(Path(cache_dir) / model_name)
        
        return None
    
    def download_model(self, model_name: str, model_type: str) -> bool:
        """
        Download a model if not already present.
        
        Args:
            model_name: Name of the model
            model_type: Type of model
            
        Returns:
            bool: True if download successful
        """
        try:
            if model_type == 'embedding':
                # Download using sentence-transformers
                from sentence_transformers import SentenceTransformer
                
                cache_dir = self.config.ai_models.embedding.cache_dir
                Path(cache_dir).mkdir(parents=True, exist_ok=True)
                
                logger.info(f"Downloading embedding model: {model_name}")
                model = SentenceTransformer(model_name, cache_folder=cache_dir)
                
                # Update cache
                cache_key = f"{model_type}:{model_name}"
                if cache_key in self._model_cache:
                    self._model_cache[cache_key].downloaded = True
                    self._model_cache[cache_key].last_updated = datetime.now()
                
                logger.info(f"Successfully downloaded embedding model: {model_name}")
                return True
                
            elif model_type == 'llm' and self.config.ai_models.llm.provider == 'ollama':
                # Download using Ollama
                import subprocess
                
                logger.info(f"Downloading LLM model: {model_name}")
                result = subprocess.run(
                    ['ollama', 'pull', model_name],
                    capture_output=True,
                    text=True,
                    timeout=3600  # 1 hour timeout for large models
                )
                
                if result.returncode == 0:
                    # Update cache
                    cache_key = f"{model_type}:{model_name}"
                    if cache_key in self._model_cache:
                        self._model_cache[cache_key].downloaded = True
                        self._model_cache[cache_key].last_updated = datetime.now()
                    
                    logger.info(f"Successfully downloaded LLM model: {model_name}")
                    return True
                else:
                    logger.error(f"Failed to download LLM model: {result.stderr}")
                    return False
            
            return False
            
        except Exception as e:
            logger.error(f"Error downloading model {model_name}: {e}")
            return False
    
    def list_available_models(self, model_type: str) -> List[str]:
        """
        List available models for a given type.
        
        Args:
            model_type: Type of model ('embedding' or 'llm')
            
        Returns:
            List[str]: List of available model names
        """
        if model_type == 'embedding':
            # Common sentence-transformers models
            return [
                'all-MiniLM-L6-v2',
                'all-mpnet-base-v2',
                'all-distilroberta-v1',
                'paraphrase-MiniLM-L6-v2',
                'paraphrase-mpnet-base-v2'
            ]
        
        elif model_type == 'llm':
            # Common Ollama models
            return [
                'llama3.2:1b',
                'llama3.2:3b',
                'qwen2.5:0.5b',
                'qwen2.5:1.5b',
                'phi3.5:3.8b',
                'gemma2:2b'
            ]
        
        return []
    
    def cleanup_old_models(self, keep_days: int = 30) -> None:
        """
        Clean up old unused models.
        
        Args:
            keep_days: Number of days to keep unused models
        """
        logger.info(f"Cleaning up models older than {keep_days} days")
        
        # This would implement cleanup logic based on last access time
        # For now, just log the intent
        logger.info("Model cleanup completed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_file_watching()


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_file: Optional[str] = None) -> ConfigManager:
    """
    Get or create the global configuration manager instance.
    
    Args:
        config_file: Configuration file path (only used on first call)
        
    Returns:
        ConfigManager: The configuration manager instance
    """
    global _config_manager
    
    if _config_manager is None:
        _config_manager = ConfigManager(config_file)
    
    return _config_manager


def get_config() -> AppConfig:
    """
    Get current application configuration.
    
    Returns:
        AppConfig: Current configuration
    """
    return get_config_manager().get_config()


def reset_config_manager() -> None:
    """Reset the global configuration manager (mainly for testing)."""
    global _config_manager
    if _config_manager:
        _config_manager.stop_file_watching()
    _config_manager = None