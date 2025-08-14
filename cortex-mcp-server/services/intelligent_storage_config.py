"""
Configuration management for intelligent storage settings.

This module provides utilities for managing intelligent storage preferences,
including default values, validation, and category-specific settings.
"""

import logging
from typing import Dict, Any, Optional, List
from enum import Enum

from repositories.preferences_repository import PreferencesRepository
from models.schemas import PreferenceCategory
from config.database import DatabaseManager, get_database_manager

logger = logging.getLogger(__name__)


class StorageCategory(str, Enum):
    """Categories of content that can be auto-stored."""
    PREFERENCES = "preferences"
    SOLUTIONS = "solutions"
    PROJECT_CONTEXT = "project_context"
    DECISIONS = "decisions"
    PATTERNS = "patterns"


class IntelligentStorageConfig:
    """Manages intelligent storage configuration and preferences."""
    
    # Default configuration values
    DEFAULT_CONFIG = {
        # Confidence thresholds
        "intelligent_storage.auto_store_threshold": 0.85,
        "intelligent_storage.suggestion_threshold": 0.60,
        
        # Privacy and general settings
        "intelligent_storage.privacy_mode": False,
        "intelligent_storage.enabled": True,
        
        # Category-specific auto-storage settings
        "intelligent_storage.auto_store_preferences": True,
        "intelligent_storage.auto_store_solutions": True,
        "intelligent_storage.auto_store_project_context": True,
        "intelligent_storage.auto_store_decisions": True,
        "intelligent_storage.auto_store_patterns": True,
        
        # Category-specific confidence thresholds (optional overrides)
        "intelligent_storage.preferences_threshold": None,  # Uses default if None
        "intelligent_storage.solutions_threshold": None,
        "intelligent_storage.project_context_threshold": None,
        "intelligent_storage.decisions_threshold": None,
        "intelligent_storage.patterns_threshold": None,
        
        # Notification settings
        "intelligent_storage.notify_auto_store": True,
        "intelligent_storage.notify_suggestions": True,
        
        # Learning and feedback settings
        "intelligent_storage.learn_from_feedback": True,
        "intelligent_storage.feedback_weight": 0.1,
        
        # Content filtering
        "intelligent_storage.min_content_length": 50,
        "intelligent_storage.max_suggestions_per_session": 5,
        
        # Duplicate detection
        "intelligent_storage.duplicate_detection": True,
        "intelligent_storage.similarity_threshold": 0.8,
    }
    
    # Configuration validation rules
    VALIDATION_RULES = {
        "intelligent_storage.auto_store_threshold": {
            "type": float,
            "min": 0.0,
            "max": 1.0,
            "description": "Confidence threshold for automatic storage (0.0-1.0)"
        },
        "intelligent_storage.suggestion_threshold": {
            "type": float,
            "min": 0.0,
            "max": 1.0,
            "description": "Confidence threshold for storage suggestions (0.0-1.0)"
        },
        "intelligent_storage.privacy_mode": {
            "type": bool,
            "description": "Disable all auto-storage when enabled"
        },
        "intelligent_storage.enabled": {
            "type": bool,
            "description": "Enable/disable intelligent storage system"
        },
        "intelligent_storage.feedback_weight": {
            "type": float,
            "min": 0.0,
            "max": 1.0,
            "description": "Weight for user feedback in learning (0.0-1.0)"
        },
        "intelligent_storage.min_content_length": {
            "type": int,
            "min": 10,
            "max": 1000,
            "description": "Minimum content length for storage consideration"
        },
        "intelligent_storage.max_suggestions_per_session": {
            "type": int,
            "min": 1,
            "max": 20,
            "description": "Maximum storage suggestions per conversation session"
        },
        "intelligent_storage.similarity_threshold": {
            "type": float,
            "min": 0.0,
            "max": 1.0,
            "description": "Similarity threshold for duplicate detection (0.0-1.0)"
        }
    }
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """
        Initialize intelligent storage configuration manager.
        
        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager or get_database_manager()
        self.preferences_repo = PreferencesRepository(self.db_manager)
        self._config_cache = {}
        self._cache_valid = False

    def initialize_defaults(self) -> bool:
        """
        Initialize default intelligent storage preferences if they don't exist.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            logger.info("Initializing intelligent storage default preferences...")
            
            # Get existing preference keys
            existing_prefs = self.preferences_repo.search_by_key("intelligent_storage.")
            existing_keys = {pref.key for pref in existing_prefs}
            
            # Create missing default preferences
            created_count = 0
            for key, default_value in self.DEFAULT_CONFIG.items():
                if key not in existing_keys:
                    try:
                        self.preferences_repo.set_value(
                            key=key,
                            value=default_value,
                            category=PreferenceCategory.LEARNING
                        )
                        created_count += 1
                        logger.debug(f"Created default preference: {key} = {default_value}")
                    except Exception as e:
                        logger.warning(f"Failed to create default preference {key}: {e}")
            
            if created_count > 0:
                logger.info(f"Created {created_count} default intelligent storage preferences")
                self._invalidate_cache()
            else:
                logger.info("All intelligent storage preferences already exist")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize default preferences: {e}")
            return False

    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value with caching.
        
        Args:
            key: Configuration key
            default: Default value if not found
            
        Returns:
            Any: Configuration value
        """
        try:
            # Use cache if valid
            if self._cache_valid and key in self._config_cache:
                return self._config_cache[key]
            
            # Get from database
            value = self.preferences_repo.get_value(key, default)
            
            # Validate the value
            validated_value = self._validate_config_value(key, value)
            
            # Cache the result
            self._config_cache[key] = validated_value
            
            return validated_value
            
        except Exception as e:
            logger.warning(f"Failed to get config value {key}: {e}")
            return default

    def set_config(self, key: str, value: Any) -> bool:
        """
        Set a configuration value with validation.
        
        Args:
            key: Configuration key
            value: Configuration value
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Validate the value
            validated_value = self._validate_config_value(key, value)
            
            # Store in database
            self.preferences_repo.set_value(
                key=key,
                value=validated_value,
                category=PreferenceCategory.LEARNING
            )
            
            # Update cache
            self._config_cache[key] = validated_value
            
            logger.info(f"Updated intelligent storage config: {key} = {validated_value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set config value {key}: {e}")
            return False

    def get_all_config(self) -> Dict[str, Any]:
        """
        Get all intelligent storage configuration values.
        
        Returns:
            Dict[str, Any]: All configuration values
        """
        try:
            config = {}
            
            for key in self.DEFAULT_CONFIG.keys():
                config[key] = self.get_config(key, self.DEFAULT_CONFIG[key])
            
            return config
            
        except Exception as e:
            logger.error(f"Failed to get all config values: {e}")
            return {}

    def reset_to_defaults(self) -> bool:
        """
        Reset all intelligent storage settings to default values.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info("Resetting intelligent storage configuration to defaults...")
            
            success_count = 0
            total_count = 0
            for key, default_value in self.DEFAULT_CONFIG.items():
                # Skip None values (they represent optional overrides)
                if default_value is None:
                    # For None values, delete the preference if it exists
                    try:
                        existing = self.preferences_repo.get_by_key(key)
                        if existing:
                            self.preferences_repo.delete(key)
                            success_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to delete preference {key}: {e}")
                    total_count += 1
                else:
                    if self.set_config(key, default_value):
                        success_count += 1
                    total_count += 1
            
            self._invalidate_cache()
            
            logger.info(f"Reset {success_count}/{total_count} config values to defaults")
            return success_count == total_count
            
        except Exception as e:
            logger.error(f"Failed to reset configuration to defaults: {e}")
            return False

    def is_auto_storage_enabled(self, category: Optional[StorageCategory] = None) -> bool:
        """
        Check if auto-storage is enabled globally or for a specific category.
        
        Args:
            category: Optional category to check
            
        Returns:
            bool: True if auto-storage is enabled
        """
        try:
            # Check global settings first
            if not self.get_config("intelligent_storage.enabled", True):
                return False
            
            if self.get_config("intelligent_storage.privacy_mode", False):
                return False
            
            # Check category-specific setting if provided
            if category:
                category_key = f"intelligent_storage.auto_store_{category.value}"
                return self.get_config(category_key, True)
            
            return True
            
        except Exception as e:
            logger.warning(f"Failed to check auto-storage status: {e}")
            return False

    def get_confidence_threshold(self, 
                                threshold_type: str = "auto_store",
                                category: Optional[StorageCategory] = None) -> float:
        """
        Get confidence threshold for auto-storage or suggestions.
        
        Args:
            threshold_type: "auto_store" or "suggestion"
            category: Optional category for category-specific threshold
            
        Returns:
            float: Confidence threshold (0.0-1.0)
        """
        try:
            # Check for category-specific threshold first
            if category:
                category_key = f"intelligent_storage.{category.value}_threshold"
                category_threshold = self.get_config(category_key)
                if category_threshold is not None:
                    return float(category_threshold)
            
            # Use global threshold
            global_key = f"intelligent_storage.{threshold_type}_threshold"
            default_value = self.DEFAULT_CONFIG.get(global_key, 0.85 if threshold_type == "auto_store" else 0.60)
            
            return float(self.get_config(global_key, default_value))
            
        except Exception as e:
            logger.warning(f"Failed to get confidence threshold: {e}")
            return 0.85 if threshold_type == "auto_store" else 0.60

    def get_category_settings(self, category: StorageCategory) -> Dict[str, Any]:
        """
        Get all settings for a specific storage category.
        
        Args:
            category: Storage category
            
        Returns:
            Dict[str, Any]: Category-specific settings
        """
        try:
            settings = {
                "enabled": self.is_auto_storage_enabled(category),
                "auto_store_enabled": self.get_config(f"intelligent_storage.auto_store_{category.value}", True),
                "confidence_threshold": self.get_confidence_threshold("auto_store", category),
                "suggestion_threshold": self.get_confidence_threshold("suggestion", category),
            }
            
            return settings
            
        except Exception as e:
            logger.error(f"Failed to get category settings for {category.value}: {e}")
            return {}

    def export_config(self) -> Dict[str, Any]:
        """
        Export all intelligent storage configuration for backup.
        
        Returns:
            Dict[str, Any]: Exported configuration
        """
        try:
            config = self.get_all_config()
            
            export_data = {
                "intelligent_storage_config": config,
                "metadata": {
                    "export_timestamp": logger.info("Exported intelligent storage configuration"),
                    "version": "1.0.0"
                }
            }
            
            return export_data
            
        except Exception as e:
            logger.error(f"Failed to export configuration: {e}")
            return {}

    def import_config(self, config_data: Dict[str, Any], overwrite: bool = False) -> bool:
        """
        Import intelligent storage configuration from backup.
        
        Args:
            config_data: Configuration data to import
            overwrite: Whether to overwrite existing settings
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if "intelligent_storage_config" not in config_data:
                logger.error("Invalid config data format")
                return False
            
            config = config_data["intelligent_storage_config"]
            imported_count = 0
            
            for key, value in config.items():
                if key.startswith("intelligent_storage."):
                    try:
                        # Check if setting already exists
                        if not overwrite and self.preferences_repo.get_by_key(key):
                            continue
                        
                        if self.set_config(key, value):
                            imported_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to import config {key}: {e}")
            
            logger.info(f"Imported {imported_count} intelligent storage configuration values")
            return imported_count > 0
            
        except Exception as e:
            logger.error(f"Failed to import configuration: {e}")
            return False

    def _validate_config_value(self, key: str, value: Any) -> Any:
        """
        Validate a configuration value against defined rules.
        
        Args:
            key: Configuration key
            value: Value to validate
            
        Returns:
            Any: Validated value
            
        Raises:
            ValueError: If validation fails
        """
        if key not in self.VALIDATION_RULES:
            # No validation rules defined, return as-is
            return value
        
        rules = self.VALIDATION_RULES[key]
        expected_type = rules["type"]
        
        # Type validation
        if not isinstance(value, expected_type):
            try:
                # Try to convert to expected type
                if expected_type == bool:
                    if isinstance(value, str):
                        value = value.lower() in ("true", "1", "yes", "on")
                    else:
                        value = bool(value)
                elif expected_type == float:
                    value = float(value)
                elif expected_type == int:
                    value = int(value)
            except (ValueError, TypeError):
                raise ValueError(f"Config {key} must be of type {expected_type.__name__}")
        
        # Range validation
        if "min" in rules and value < rules["min"]:
            raise ValueError(f"Config {key} must be >= {rules['min']}")
        
        if "max" in rules and value > rules["max"]:
            raise ValueError(f"Config {key} must be <= {rules['max']}")
        
        return value

    def _invalidate_cache(self) -> None:
        """Invalidate the configuration cache."""
        self._config_cache.clear()
        self._cache_valid = False

    def get_config_info(self) -> Dict[str, Any]:
        """
        Get information about all available configuration options.
        
        Returns:
            Dict[str, Any]: Configuration information
        """
        try:
            info = {}
            
            for key, default_value in self.DEFAULT_CONFIG.items():
                current_value = self.get_config(key, default_value)
                validation_info = self.VALIDATION_RULES.get(key, {})
                
                info[key] = {
                    "current_value": current_value,
                    "default_value": default_value,
                    "type": validation_info.get("type", type(default_value)).__name__,
                    "description": validation_info.get("description", "No description available"),
                    "validation": {
                        k: v for k, v in validation_info.items() 
                        if k in ["min", "max", "options"]
                    }
                }
            
            return info
            
        except Exception as e:
            logger.error(f"Failed to get configuration info: {e}")
            return {}


def get_intelligent_storage_config(db_manager: Optional[DatabaseManager] = None) -> IntelligentStorageConfig:
    """
    Get intelligent storage configuration manager instance.
    
    Args:
        db_manager: Optional database manager
        
    Returns:
        IntelligentStorageConfig: Configuration manager instance
    """
    return IntelligentStorageConfig(db_manager)