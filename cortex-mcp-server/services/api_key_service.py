"""
API Key Management Service

This service provides programmatic access to API key management functionality,
integrating with the existing CLI script while providing a clean interface
for the REST API endpoints.
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from models.schemas import APIKeyResponse, APIKeyCreateResponse, APIKeyCreate, APIKeyUpdate

# Add the scripts directory to Python path to import the API key manager
parent_dir = Path(__file__).parent.parent
scripts_dir = parent_dir / "scripts"
sys.path.insert(0, str(scripts_dir))

from manage_api_keys import APIKeyManager
# Import will be resolved at runtime when the full application is loaded
# from models.schemas import APIKeyResponse, APIKeyCreateResponse, APIKeyCreate, APIKeyUpdate

logger = logging.getLogger(__name__)


class APIKeyService:
    """Service for managing API keys through the REST API."""
    
    def __init__(self, keys_file: str = "./data/api_keys.json"):
        """
        Initialize the API key service.
        
        Args:
            keys_file: Path to the API keys storage file
        """
        self.keys_file = keys_file
        self.manager = APIKeyManager(keys_file)
        logger.info(f"API Key Service initialized with keys file: {keys_file}")
    
    def create_api_key(self, request: "APIKeyCreate") -> "APIKeyCreateResponse":
        """
        Create a new API key.
        
        Args:
            request: API key creation request
            
        Returns:
            APIKeyCreateResponse: Created API key with the actual key value
        """
        try:
            # Import schemas at runtime to avoid circular imports
            from models.schemas import APIKeyCreateResponse
            
            # Generate the key using the existing manager
            key, key_id = self.manager.generate_key(
                name=request.name,
                expires_days=request.expires_days
            )
            
            # Get the key info to build the response
            key_info = self.manager.keys_data["keys"][key_id]
            
            # Parse dates
            created = datetime.fromisoformat(key_info["created"])
            expires = None
            if key_info.get("expires"):
                expires = datetime.fromisoformat(key_info["expires"])
            
            # Check if expired
            expired = False
            if expires:
                expired = datetime.now() > expires
            
            response = APIKeyCreateResponse(
                id=key_id,
                name=key_info["name"],
                key_preview=key[:8],
                key=key,  # Only included in creation response
                created=created,
                last_used=None,
                usage_count=key_info.get("usage_count", 0),
                active=key_info["active"],
                expires=expires,
                expired=expired
            )
            
            logger.info(f"Created new API key: {key_id} ({request.name})")
            return response
            
        except Exception as e:
            logger.error(f"Failed to create API key: {e}")
            raise
    
    def list_api_keys(self) -> List["APIKeyResponse"]:
        """
        List all API keys.
        
        Returns:
            List[APIKeyResponse]: List of all API keys (without actual key values)
        """
        try:
            # Import schemas at runtime to avoid circular imports
            from models.schemas import APIKeyResponse
            
            keys_data = self.manager.list_keys()
            
            api_keys = []
            for key_data in keys_data:
                # Parse dates
                created = datetime.fromisoformat(key_data["created"])
                last_used = None
                if key_data.get("last_used"):
                    last_used = datetime.fromisoformat(key_data["last_used"])
                
                expires = None
                if key_data.get("expires"):
                    expires = datetime.fromisoformat(key_data["expires"])
                
                api_key = APIKeyResponse(
                    id=key_data["id"],
                    name=key_data["name"],
                    key_preview=key_data["id"],  # Use key ID as preview
                    created=created,
                    last_used=last_used,
                    usage_count=key_data.get("usage_count", 0),
                    active=key_data["active"],
                    expires=expires,
                    expired=key_data.get("expired", False)
                )
                api_keys.append(api_key)
            
            logger.info(f"Listed {len(api_keys)} API keys")
            return api_keys
            
        except Exception as e:
            logger.error(f"Failed to list API keys: {e}")
            raise
    
    def get_api_key(self, key_id: str) -> Optional["APIKeyResponse"]:
        """
        Get a specific API key by ID.
        
        Args:
            key_id: API key ID
            
        Returns:
            APIKeyResponse: API key details or None if not found
        """
        try:
            # Import schemas at runtime to avoid circular imports
            from models.schemas import APIKeyResponse
            
            keys_data = self.manager.list_keys()
            
            for key_data in keys_data:
                if key_data["id"] == key_id:
                    # Parse dates
                    created = datetime.fromisoformat(key_data["created"])
                    last_used = None
                    if key_data.get("last_used"):
                        last_used = datetime.fromisoformat(key_data["last_used"])
                    
                    expires = None
                    if key_data.get("expires"):
                        expires = datetime.fromisoformat(key_data["expires"])
                    
                    api_key = APIKeyResponse(
                        id=key_data["id"],
                        name=key_data["name"],
                        key_preview=key_data["id"],  # Use key ID as preview
                        created=created,
                        last_used=last_used,
                        usage_count=key_data.get("usage_count", 0),
                        active=key_data["active"],
                        expires=expires,
                        expired=key_data.get("expired", False)
                    )
                    
                    logger.info(f"Retrieved API key: {key_id}")
                    return api_key
            
            logger.warning(f"API key not found: {key_id}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get API key {key_id}: {e}")
            raise
    
    def update_api_key(self, key_id: str, update_data: "APIKeyUpdate") -> Optional["APIKeyResponse"]:
        """
        Update an API key.
        
        Args:
            key_id: API key ID
            update_data: Update data
            
        Returns:
            APIKeyResponse: Updated API key or None if not found
        """
        try:
            # Import schemas at runtime to avoid circular imports
            from models.schemas import APIKeyResponse
            
            # Check if key exists
            if key_id not in self.manager.keys_data["keys"]:
                logger.warning(f"API key not found for update: {key_id}")
                return None
            
            key_info = self.manager.keys_data["keys"][key_id]
            
            # Update fields
            if update_data.name is not None:
                key_info["name"] = update_data.name
            
            if update_data.active is not None:
                key_info["active"] = update_data.active
                if not update_data.active:
                    key_info["deactivated"] = datetime.now().isoformat()
            
            # Save changes
            self.manager._save_keys()
            
            # Return updated key
            updated_key = self.get_api_key(key_id)
            logger.info(f"Updated API key: {key_id}")
            return updated_key
            
        except Exception as e:
            logger.error(f"Failed to update API key {key_id}: {e}")
            raise
    
    def delete_api_key(self, key_id: str) -> bool:
        """
        Delete an API key.
        
        Args:
            key_id: API key ID
            
        Returns:
            bool: True if deleted, False if not found
        """
        try:
            success = self.manager.delete_key(key_id)
            if success:
                logger.info(f"Deleted API key: {key_id}")
            else:
                logger.warning(f"API key not found for deletion: {key_id}")
            return success
            
        except Exception as e:
            logger.error(f"Failed to delete API key {key_id}: {e}")
            raise
    
    def deactivate_api_key(self, key_id: str) -> bool:
        """
        Deactivate an API key (soft delete).
        
        Args:
            key_id: API key ID
            
        Returns:
            bool: True if deactivated, False if not found
        """
        try:
            success = self.manager.deactivate_key(key_id)
            if success:
                logger.info(f"Deactivated API key: {key_id}")
            else:
                logger.warning(f"API key not found for deactivation: {key_id}")
            return success
            
        except Exception as e:
            logger.error(f"Failed to deactivate API key {key_id}: {e}")
            raise
    
    def rotate_api_key(self, key_id: str) -> Optional["APIKeyCreateResponse"]:
        """
        Rotate an API key (generate new key, keep same metadata).
        
        Args:
            key_id: API key ID to rotate
            
        Returns:
            APIKeyCreateResponse: New API key with the actual key value, or None if not found
        """
        try:
            # Import schemas at runtime to avoid circular imports
            from models.schemas import APIKeyCreateResponse
            
            new_key = self.manager.rotate_key(key_id)
            if not new_key:
                logger.warning(f"API key not found for rotation: {key_id}")
                return None
            
            # Get updated key info
            key_info = self.manager.keys_data["keys"][key_id]
            
            # Parse dates
            created = datetime.fromisoformat(key_info["created"])
            expires = None
            if key_info.get("expires"):
                expires = datetime.fromisoformat(key_info["expires"])
            
            # Check if expired
            expired = False
            if expires:
                expired = datetime.now() > expires
            
            response = APIKeyCreateResponse(
                id=key_id,
                name=key_info["name"],
                key_preview=new_key[:8],
                key=new_key,  # Include the new key
                created=created,
                last_used=None,  # Reset after rotation
                usage_count=key_info.get("usage_count", 0),
                active=key_info["active"],
                expires=expires,
                expired=expired
            )
            
            logger.info(f"Rotated API key: {key_id}")
            return response
            
        except Exception as e:
            logger.error(f"Failed to rotate API key {key_id}: {e}")
            raise
    
    def verify_api_key(self, api_key: str) -> Optional[str]:
        """
        Verify an API key and return the key ID if valid.
        
        Args:
            api_key: API key to verify
            
        Returns:
            str: Key ID if valid, None if invalid
        """
        try:
            key_id = self.manager.verify_key(api_key)
            if key_id:
                logger.debug(f"API key verified: {key_id}")
            else:
                logger.warning("Invalid API key provided")
            return key_id
            
        except Exception as e:
            logger.error(f"Failed to verify API key: {e}")
            raise
    
    def get_active_key_hashes(self) -> List[str]:
        """
        Get list of active API key hashes for authentication.
        
        Returns:
            List[str]: List of active API key hashes
        """
        try:
            hashes = self.manager.get_active_keys()
            logger.debug(f"Retrieved {len(hashes)} active key hashes")
            return hashes
            
        except Exception as e:
            logger.error(f"Failed to get active key hashes: {e}")
            raise