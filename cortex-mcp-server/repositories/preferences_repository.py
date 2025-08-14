"""
Repository for user preferences data access operations.

This module provides CRUD operations for user preferences and settings
with proper error handling and type conversion.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import desc, func, and_

from models.database import Preference
from models.schemas import PreferenceCreate, PreferenceUpdate, PreferenceCategory
from config.database import DatabaseManager, DatabaseConnectionError

logger = logging.getLogger(__name__)


class PreferencesRepository:
    """Repository for user preferences data access operations."""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize preferences repository.
        
        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager

    def create(self, preference_data: PreferenceCreate) -> Preference:
        """
        Create a new preference or update existing one.
        
        Args:
            preference_data: Preference creation data
            
        Returns:
            Preference: Created or updated preference instance
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                # Check if preference already exists
                existing_preference = session.query(Preference).filter(
                    Preference.key == preference_data.key
                ).first()
                
                if existing_preference:
                    # Update existing preference
                    existing_preference.set_json_value(preference_data.value)
                    if preference_data.category:
                        existing_preference.category = preference_data.category.value
                    existing_preference.updated_at = datetime.utcnow()
                    
                    session.commit()
                    session.refresh(existing_preference)
                    
                    logger.info(f"Updated existing preference: {preference_data.key}")
                    return existing_preference
                else:
                    # Create new preference
                    preference = Preference(
                        key=preference_data.key,
                        category=preference_data.category.value if preference_data.category else None,
                        updated_at=datetime.utcnow()
                    )
                    preference.set_json_value(preference_data.value)
                    
                    session.add(preference)
                    session.flush()  # Get the key without committing
                    session.commit()
                    session.refresh(preference)
                    
                    logger.info(f"Created new preference: {preference_data.key}")
                    return preference
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to create/update preference {preference_data.key}: {e}")
            raise DatabaseConnectionError(f"Failed to create/update preference: {e}") from e

    def get_by_key(self, key: str) -> Optional[Preference]:
        """
        Get preference by key.
        
        Args:
            key: Preference key
            
        Returns:
            Optional[Preference]: Preference if found, None otherwise
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                preference = session.query(Preference).filter(
                    Preference.key == key
                ).first()
                
                if preference:
                    logger.debug(f"Retrieved preference: {key}")
                else:
                    logger.debug(f"Preference not found: {key}")
                
                return preference
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to get preference {key}: {e}")
            raise DatabaseConnectionError(f"Failed to get preference: {e}") from e

    def get_value(self, key: str, default: Any = None) -> Any:
        """
        Get preference value by key with default fallback.
        
        Args:
            key: Preference key
            default: Default value if preference not found
            
        Returns:
            Any: Preference value or default
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            preference = self.get_by_key(key)
            if preference:
                return preference.get_json_value()
            return default
            
        except DatabaseConnectionError:
            # Re-raise database errors
            raise
        except Exception as e:
            logger.error(f"Failed to get preference value {key}: {e}")
            return default

    def set_value(self, key: str, value: Any, category: Optional[PreferenceCategory] = None) -> Preference:
        """
        Set preference value (create or update).
        
        Args:
            key: Preference key
            value: Preference value
            category: Optional preference category
            
        Returns:
            Preference: Created or updated preference
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            preference_data = PreferenceCreate(
                key=key,
                value=value,
                category=category
            )
            return self.create(preference_data)
            
        except DatabaseConnectionError:
            # Re-raise database errors
            raise
        except Exception as e:
            logger.error(f"Failed to set preference value {key}: {e}")
            raise DatabaseConnectionError(f"Failed to set preference value: {e}") from e

    def update(self, key: str, update_data: PreferenceUpdate) -> Optional[Preference]:
        """
        Update an existing preference.
        
        Args:
            key: Preference key
            update_data: Update data
            
        Returns:
            Optional[Preference]: Updated preference if found, None otherwise
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                preference = session.query(Preference).filter(
                    Preference.key == key
                ).first()
                
                if not preference:
                    logger.warning(f"Preference {key} not found for update")
                    return None
                
                # Update value
                preference.set_json_value(update_data.value)
                
                # Update category if provided
                if update_data.category is not None:
                    preference.category = update_data.category.value
                
                preference.updated_at = datetime.utcnow()
                
                session.commit()
                session.refresh(preference)
                
                logger.info(f"Updated preference: {key}")
                return preference
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to update preference {key}: {e}")
            raise DatabaseConnectionError(f"Failed to update preference: {e}") from e

    def delete(self, key: str) -> bool:
        """
        Delete a preference.
        
        Args:
            key: Preference key
            
        Returns:
            bool: True if deleted, False if not found
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                preference = session.query(Preference).filter(
                    Preference.key == key
                ).first()
                
                if not preference:
                    logger.warning(f"Preference {key} not found for deletion")
                    return False
                
                session.delete(preference)
                session.commit()
                
                logger.info(f"Deleted preference: {key}")
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to delete preference {key}: {e}")
            raise DatabaseConnectionError(f"Failed to delete preference: {e}") from e

    def list_all(self, limit: int = 100, offset: int = 0) -> List[Preference]:
        """
        List all preferences with pagination.
        
        Args:
            limit: Maximum number of preferences to return
            offset: Number of preferences to skip
            
        Returns:
            List[Preference]: List of preferences
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                preferences = session.query(Preference).order_by(
                    Preference.key
                ).limit(limit).offset(offset).all()
                
                logger.debug(f"Retrieved {len(preferences)} preferences (limit={limit}, offset={offset})")
                return preferences
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to list preferences: {e}")
            raise DatabaseConnectionError(f"Failed to list preferences: {e}") from e

    def get_by_category(self, category: PreferenceCategory, limit: int = 100) -> List[Preference]:
        """
        Get preferences by category.
        
        Args:
            category: Preference category
            limit: Maximum number of preferences to return
            
        Returns:
            List[Preference]: List of preferences in the category
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                preferences = session.query(Preference).filter(
                    Preference.category == category.value
                ).order_by(Preference.key).limit(limit).all()
                
                logger.debug(f"Retrieved {len(preferences)} preferences for category {category.value}")
                return preferences
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to get preferences for category {category.value}: {e}")
            raise DatabaseConnectionError(f"Failed to get preferences for category: {e}") from e

    def search_by_key(self, key_pattern: str, limit: int = 50) -> List[Preference]:
        """
        Search preferences by key pattern.
        
        Args:
            key_pattern: Key search pattern (supports wildcards)
            limit: Maximum number of results
            
        Returns:
            List[Preference]: List of matching preferences
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                search_term = f"%{key_pattern}%"
                preferences = session.query(Preference).filter(
                    Preference.key.ilike(search_term)
                ).order_by(Preference.key).limit(limit).all()
                
                logger.debug(f"Found {len(preferences)} preferences matching key pattern '{key_pattern}'")
                return preferences
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to search preferences by key pattern: {e}")
            raise DatabaseConnectionError(f"Failed to search preferences by key pattern: {e}") from e

    def get_all_as_dict(self, category: Optional[PreferenceCategory] = None) -> Dict[str, Any]:
        """
        Get all preferences as a dictionary.
        
        Args:
            category: Optional category filter
            
        Returns:
            Dict[str, Any]: Dictionary of key-value pairs
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                query = session.query(Preference)
                
                if category:
                    query = query.filter(Preference.category == category.value)
                
                preferences = query.all()
                
                result = {}
                for preference in preferences:
                    try:
                        result[preference.key] = preference.get_json_value()
                    except Exception as e:
                        logger.warning(f"Failed to parse preference {preference.key}: {e}")
                        result[preference.key] = preference.value  # Fallback to raw value
                
                logger.debug(f"Retrieved {len(result)} preferences as dictionary")
                return result
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to get preferences as dictionary: {e}")
            raise DatabaseConnectionError(f"Failed to get preferences as dictionary: {e}") from e

    def bulk_set(self, preferences: Dict[str, Any], category: Optional[PreferenceCategory] = None) -> int:
        """
        Set multiple preferences in bulk.
        
        Args:
            preferences: Dictionary of key-value pairs
            category: Optional category for all preferences
            
        Returns:
            int: Number of preferences set
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            count = 0
            for key, value in preferences.items():
                try:
                    self.set_value(key, value, category)
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to set preference {key}: {e}")
            
            logger.info(f"Bulk set {count} preferences")
            return count
            
        except Exception as e:
            logger.error(f"Failed to bulk set preferences: {e}")
            raise DatabaseConnectionError(f"Failed to bulk set preferences: {e}") from e

    def get_recent_updates(self, hours: int = 24, limit: int = 20) -> List[Preference]:
        """
        Get recently updated preferences.
        
        Args:
            hours: Number of hours to look back
            limit: Maximum number of preferences
            
        Returns:
            List[Preference]: List of recently updated preferences
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                cutoff_time = datetime.utcnow() - timedelta(hours=hours)
                
                preferences = session.query(Preference).filter(
                    Preference.updated_at >= cutoff_time
                ).order_by(desc(Preference.updated_at)).limit(limit).all()
                
                logger.debug(f"Retrieved {len(preferences)} recently updated preferences (last {hours}h)")
                return preferences
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to get recent preference updates: {e}")
            raise DatabaseConnectionError(f"Failed to get recent preference updates: {e}") from e

    def count_total(self) -> int:
        """
        Get total count of preferences.
        
        Returns:
            int: Total number of preferences
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                count = session.query(func.count(Preference.key)).scalar()
                logger.debug(f"Total preferences count: {count}")
                return count or 0
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to count preferences: {e}")
            raise DatabaseConnectionError(f"Failed to count preferences: {e}") from e

    def count_by_category(self) -> Dict[str, int]:
        """
        Get count of preferences by category.
        
        Returns:
            Dict[str, int]: Count by category
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                category_counts = session.query(
                    Preference.category,
                    func.count(Preference.key)
                ).group_by(Preference.category).all()
                
                result = {}
                for category, count in category_counts:
                    category_name = category if category else "uncategorized"
                    result[category_name] = count
                
                logger.debug(f"Retrieved preference counts by category: {result}")
                return result
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to count preferences by category: {e}")
            raise DatabaseConnectionError(f"Failed to count preferences by category: {e}") from e

    def get_preference_stats(self) -> Dict[str, Any]:
        """
        Get preference statistics.
        
        Returns:
            Dict[str, Any]: Statistics about preferences
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                stats = {}
                
                # Total count
                stats["total_preferences"] = session.query(func.count(Preference.key)).scalar() or 0
                
                # Count by category
                stats["by_category"] = self.count_by_category()
                
                # Recent activity
                recent_count = session.query(func.count(Preference.key)).filter(
                    Preference.updated_at >= datetime.utcnow() - timedelta(days=7)
                ).scalar() or 0
                stats["updated_last_week"] = recent_count
                
                # Date range
                date_range = session.query(
                    func.min(Preference.updated_at),
                    func.max(Preference.updated_at)
                ).first()
                if date_range[0] and date_range[1]:
                    stats["date_range"] = {
                        "oldest_update": date_range[0],
                        "newest_update": date_range[1]
                    }
                
                logger.debug("Retrieved preference statistics")
                return stats
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to get preference statistics: {e}")
            raise DatabaseConnectionError(f"Failed to get preference statistics: {e}") from e

    def export_preferences(self, category: Optional[PreferenceCategory] = None) -> Dict[str, Any]:
        """
        Export preferences for backup or migration.
        
        Args:
            category: Optional category filter
            
        Returns:
            Dict[str, Any]: Exported preferences with metadata
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            preferences_dict = self.get_all_as_dict(category)
            
            export_data = {
                "preferences": preferences_dict,
                "metadata": {
                    "export_timestamp": datetime.utcnow().isoformat(),
                    "total_count": len(preferences_dict),
                    "category_filter": category.value if category else None
                }
            }
            
            logger.info(f"Exported {len(preferences_dict)} preferences")
            return export_data
            
        except Exception as e:
            logger.error(f"Failed to export preferences: {e}")
            raise DatabaseConnectionError(f"Failed to export preferences: {e}") from e

    def import_preferences(self, preferences_data: Dict[str, Any], overwrite: bool = False) -> int:
        """
        Import preferences from backup or migration.
        
        Args:
            preferences_data: Dictionary of preferences to import
            overwrite: Whether to overwrite existing preferences
            
        Returns:
            int: Number of preferences imported
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            imported_count = 0
            skipped_count = 0
            
            for key, value in preferences_data.items():
                try:
                    existing = self.get_by_key(key)
                    
                    if existing and not overwrite:
                        skipped_count += 1
                        continue
                    
                    self.set_value(key, value)
                    imported_count += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to import preference {key}: {e}")
            
            logger.info(f"Imported {imported_count} preferences, skipped {skipped_count}")
            return imported_count
            
        except Exception as e:
            logger.error(f"Failed to import preferences: {e}")
            raise DatabaseConnectionError(f"Failed to import preferences: {e}") from e