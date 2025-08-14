"""
Encryption service for data at rest using AES-256.

This module provides encryption and decryption capabilities for sensitive data
stored in the database, using AES-256 encryption with secure key derivation.
"""

import base64
import hashlib
import logging
import os
import secrets
from typing import Optional, Tuple

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

logger = logging.getLogger(__name__)


class EncryptionError(Exception):
    """Base exception for encryption-related errors."""
    pass


class DecryptionError(EncryptionError):
    """Exception raised when decryption fails."""
    pass


class KeyDerivationError(EncryptionError):
    """Exception raised when key derivation fails."""
    pass


class EncryptionService:
    """Service for encrypting and decrypting data at rest."""
    
    def __init__(self, passphrase: Optional[str] = None):
        """
        Initialize the encryption service.
        
        Args:
            passphrase: User-provided passphrase for key derivation.
                       If None, will look for ENCRYPTION_PASSPHRASE env var.
        """
        self._fernet: Optional[Fernet] = None
        self._passphrase = passphrase or os.getenv("ENCRYPTION_PASSPHRASE")
        self._salt: Optional[bytes] = None
        
        if not self._passphrase:
            logger.warning("No encryption passphrase provided. Data will not be encrypted.")
    
    def _derive_key_from_passphrase(self, passphrase: str, salt: bytes) -> bytes:
        """
        Derive encryption key from user passphrase using Scrypt KDF.
        
        Args:
            passphrase: User-provided passphrase
            salt: Random salt for key derivation
            
        Returns:
            bytes: 32-byte encryption key
            
        Raises:
            KeyDerivationError: If key derivation fails
        """
        try:
            # Use Scrypt for key derivation (more secure than PBKDF2)
            kdf = Scrypt(
                length=32,  # 256 bits
                salt=salt,
                n=2**14,    # CPU/memory cost parameter (16384)
                r=8,        # Block size parameter
                p=1,        # Parallelization parameter
            )
            
            key = kdf.derive(passphrase.encode('utf-8'))
            return base64.urlsafe_b64encode(key)
            
        except Exception as e:
            logger.error(f"Key derivation failed: {e}")
            raise KeyDerivationError(f"Failed to derive encryption key: {e}") from e
    
    def _generate_salt(self) -> bytes:
        """Generate a random salt for key derivation."""
        return secrets.token_bytes(32)  # 256 bits
    
    def initialize(self, salt: Optional[bytes] = None) -> bytes:
        """
        Initialize the encryption service with a derived key.
        
        Args:
            salt: Optional salt for key derivation. If None, generates new salt.
            
        Returns:
            bytes: The salt used for key derivation (store this!)
            
        Raises:
            EncryptionError: If initialization fails
        """
        if not self._passphrase:
            logger.info("No passphrase provided, encryption disabled")
            return b""
        
        try:
            # Generate or use provided salt
            if salt is None:
                self._salt = self._generate_salt()
                logger.info("Generated new encryption salt")
            else:
                self._salt = salt
                logger.info("Using provided encryption salt")
            
            # Derive key from passphrase
            key = self._derive_key_from_passphrase(self._passphrase, self._salt)
            
            # Initialize Fernet cipher
            self._fernet = Fernet(key)
            
            logger.info("Encryption service initialized successfully")
            return self._salt
            
        except Exception as e:
            logger.error(f"Encryption service initialization failed: {e}")
            raise EncryptionError(f"Failed to initialize encryption: {e}") from e
    
    def is_enabled(self) -> bool:
        """Check if encryption is enabled and initialized."""
        return self._fernet is not None
    
    def encrypt(self, data: str) -> str:
        """
        Encrypt a string using AES-256.
        
        Args:
            data: Plain text data to encrypt
            
        Returns:
            str: Base64-encoded encrypted data
            
        Raises:
            EncryptionError: If encryption fails
        """
        if not self.is_enabled():
            # Return data as-is if encryption is disabled
            return data
        
        try:
            # Convert string to bytes and encrypt
            data_bytes = data.encode('utf-8')
            encrypted_bytes = self._fernet.encrypt(data_bytes)
            
            # Return base64-encoded encrypted data
            return base64.b64encode(encrypted_bytes).decode('ascii')
            
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise EncryptionError(f"Failed to encrypt data: {e}") from e
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt a string using AES-256.
        
        Args:
            encrypted_data: Base64-encoded encrypted data
            
        Returns:
            str: Decrypted plain text data
            
        Raises:
            DecryptionError: If decryption fails
        """
        if not self.is_enabled():
            # Return data as-is if encryption is disabled
            return encrypted_data
        
        try:
            # Decode base64 and decrypt
            encrypted_bytes = base64.b64decode(encrypted_data.encode('ascii'))
            decrypted_bytes = self._fernet.decrypt(encrypted_bytes)
            
            # Convert bytes back to string
            return decrypted_bytes.decode('utf-8')
            
        except InvalidToken as e:
            logger.error("Invalid token during decryption - wrong key or corrupted data")
            raise DecryptionError("Invalid encryption token - wrong passphrase or corrupted data") from e
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise DecryptionError(f"Failed to decrypt data: {e}") from e
    
    def encrypt_dict(self, data: dict, fields_to_encrypt: list) -> dict:
        """
        Encrypt specific fields in a dictionary.
        
        Args:
            data: Dictionary containing data to encrypt
            fields_to_encrypt: List of field names to encrypt
            
        Returns:
            dict: Dictionary with specified fields encrypted
        """
        if not self.is_enabled():
            return data
        
        encrypted_data = data.copy()
        
        for field in fields_to_encrypt:
            if field in encrypted_data and encrypted_data[field] is not None:
                try:
                    # Convert to string if not already
                    field_value = str(encrypted_data[field])
                    encrypted_data[field] = self.encrypt(field_value)
                except Exception as e:
                    logger.error(f"Failed to encrypt field '{field}': {e}")
                    # Keep original value if encryption fails
        
        return encrypted_data
    
    def decrypt_dict(self, data: dict, fields_to_decrypt: list) -> dict:
        """
        Decrypt specific fields in a dictionary.
        
        Args:
            data: Dictionary containing encrypted data
            fields_to_decrypt: List of field names to decrypt
            
        Returns:
            dict: Dictionary with specified fields decrypted
        """
        if not self.is_enabled():
            return data
        
        decrypted_data = data.copy()
        
        for field in fields_to_decrypt:
            if field in decrypted_data and decrypted_data[field] is not None:
                try:
                    decrypted_data[field] = self.decrypt(str(decrypted_data[field]))
                except Exception as e:
                    logger.error(f"Failed to decrypt field '{field}': {e}")
                    # Keep original value if decryption fails
        
        return decrypted_data
    
    def rotate_key(self, new_passphrase: str) -> Tuple[bytes, bytes]:
        """
        Rotate encryption key with a new passphrase.
        
        Args:
            new_passphrase: New passphrase for key derivation
            
        Returns:
            Tuple[bytes, bytes]: (old_salt, new_salt) for data migration
            
        Raises:
            EncryptionError: If key rotation fails
        """
        if not self.is_enabled():
            raise EncryptionError("Cannot rotate key - encryption not initialized")
        
        try:
            # Store old salt
            old_salt = self._salt
            
            # Generate new salt and derive new key
            new_salt = self._generate_salt()
            new_key = self._derive_key_from_passphrase(new_passphrase, new_salt)
            
            # Update internal state
            self._passphrase = new_passphrase
            self._salt = new_salt
            self._fernet = Fernet(new_key)
            
            logger.info("Encryption key rotated successfully")
            return old_salt, new_salt
            
        except Exception as e:
            logger.error(f"Key rotation failed: {e}")
            raise EncryptionError(f"Failed to rotate encryption key: {e}") from e
    
    def verify_passphrase(self, test_data: str = "test_encryption") -> bool:
        """
        Verify that the current passphrase can encrypt and decrypt data.
        
        Args:
            test_data: Test string to encrypt and decrypt
            
        Returns:
            bool: True if passphrase is correct, False otherwise
        """
        if not self.is_enabled():
            return True  # No encryption, so passphrase is "correct"
        
        try:
            # Encrypt and decrypt test data
            encrypted = self.encrypt(test_data)
            decrypted = self.decrypt(encrypted)
            
            return decrypted == test_data
            
        except Exception as e:
            logger.error(f"Passphrase verification failed: {e}")
            return False
    
    def get_salt(self) -> Optional[bytes]:
        """Get the current salt used for key derivation."""
        return self._salt
    
    def cleanup(self) -> None:
        """Clean up encryption service resources."""
        if self._fernet:
            # Clear sensitive data from memory
            self._fernet = None
        
        if self._passphrase:
            self._passphrase = None
        
        if self._salt:
            self._salt = None
        
        logger.info("Encryption service cleaned up")


# Global encryption service instance
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service(passphrase: Optional[str] = None) -> EncryptionService:
    """
    Get or create the global encryption service instance.
    
    Args:
        passphrase: Passphrase for encryption (only used on first call)
        
    Returns:
        EncryptionService: The encryption service instance
    """
    global _encryption_service
    
    if _encryption_service is None:
        _encryption_service = EncryptionService(passphrase)
    
    return _encryption_service


def reset_encryption_service() -> None:
    """Reset the global encryption service (mainly for testing)."""
    global _encryption_service
    if _encryption_service:
        _encryption_service.cleanup()
    _encryption_service = None