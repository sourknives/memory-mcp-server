#!/usr/bin/env python3
"""
Security features demonstration for Cross-Tool Memory MCP Server.

This script demonstrates the security features including encryption,
authentication, rate limiting, and TLS configuration.
"""

import asyncio
import os
import tempfile
from pathlib import Path

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cross_tool_memory.services.encryption_service import EncryptionService
from cross_tool_memory.security.access_control import APIKeyAuth
from cross_tool_memory.security.rate_limiting import RateLimiter
from cross_tool_memory.security.tls_config import TLSConfig
from cross_tool_memory.config.security_config import SecurityConfig
from cross_tool_memory.server.rest_api import MemoryRestAPI


def demo_encryption():
    """Demonstrate encryption service."""
    print("=== Encryption Service Demo ===")
    
    # Initialize encryption service
    passphrase = "demo-encryption-passphrase-123"
    encryption_service = EncryptionService(passphrase)
    salt = encryption_service.initialize()
    
    print(f"✓ Encryption service initialized with salt: {salt.hex()[:16]}...")
    
    # Encrypt some sensitive data
    sensitive_data = "This is sensitive conversation data that needs protection"
    encrypted_data = encryption_service.encrypt(sensitive_data)
    
    print(f"✓ Original data: {sensitive_data}")
    print(f"✓ Encrypted data: {encrypted_data[:50]}...")
    
    # Decrypt the data
    decrypted_data = encryption_service.decrypt(encrypted_data)
    print(f"✓ Decrypted data: {decrypted_data}")
    
    assert decrypted_data == sensitive_data
    print("✓ Encryption/decryption successful!")
    
    # Demonstrate dictionary encryption
    conversation_metadata = {
        "tool_name": "claude",
        "user_query": "How do I implement authentication?",
        "ai_response": "Here's how to implement secure authentication...",
        "timestamp": "2024-01-01T12:00:00Z"
    }
    
    sensitive_fields = ["user_query", "ai_response"]
    encrypted_metadata = encryption_service.encrypt_dict(conversation_metadata, sensitive_fields)
    
    print(f"✓ Original metadata: {conversation_metadata}")
    print(f"✓ Encrypted metadata: {encrypted_metadata}")
    
    decrypted_metadata = encryption_service.decrypt_dict(encrypted_metadata, sensitive_fields)
    assert decrypted_metadata == conversation_metadata
    print("✓ Dictionary encryption/decryption successful!")
    
    print()


def demo_api_key_auth():
    """Demonstrate API key authentication."""
    print("=== API Key Authentication Demo ===")
    
    # Create API key authentication
    api_keys = {"demo-api-key-123", "another-valid-key-456"}
    api_auth = APIKeyAuth(api_keys, hash_keys=True)
    
    print(f"✓ API key authentication initialized with {len(api_keys)} keys")
    
    # Test valid keys
    valid_key = "demo-api-key-123"
    invalid_key = "invalid-key-789"
    
    print(f"✓ Testing valid key '{valid_key}': {api_auth.verify_key(valid_key)}")
    print(f"✓ Testing invalid key '{invalid_key}': {api_auth.verify_key(invalid_key)}")
    
    # Generate a new API key
    new_key = api_auth.generate_key()
    print(f"✓ Generated new API key: {new_key}")
    
    # Add the new key
    api_auth.add_key(new_key)
    print(f"✓ Added new key, verification: {api_auth.verify_key(new_key)}")
    
    print()


async def demo_rate_limiting():
    """Demonstrate rate limiting."""
    print("=== Rate Limiting Demo ===")
    
    # Create rate limiter (5 requests per minute for demo)
    rate_limiter = RateLimiter(max_requests=5, time_window=60)
    client_id = "demo-client"
    
    print(f"✓ Rate limiter initialized: 5 requests per 60 seconds")
    
    # Make requests up to the limit
    for i in range(5):
        allowed, info = rate_limiter.is_allowed(client_id)
        print(f"✓ Request {i+1}: allowed={allowed}, remaining={info['remaining']}")
        assert allowed
    
    # Try one more request (should be denied)
    allowed, info = rate_limiter.is_allowed(client_id)
    print(f"✓ Request 6: allowed={allowed}, remaining={info['remaining']}, retry_after={info['retry_after']}")
    assert not allowed
    
    # Check client statistics
    stats = rate_limiter.get_client_stats(client_id)
    print(f"✓ Client stats: {stats}")
    
    # Reset client rate limit
    rate_limiter.reset_client(client_id)
    allowed, info = rate_limiter.is_allowed(client_id)
    print(f"✓ After reset: allowed={allowed}, remaining={info['remaining']}")
    assert allowed
    
    print()


def demo_tls_config():
    """Demonstrate TLS configuration."""
    print("=== TLS Configuration Demo ===")
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create TLS config with auto-generated certificates
            tls_config = TLSConfig(cert_dir=temp_dir, auto_generate=True)
            
            print(f"✓ TLS config initialized with cert directory: {temp_dir}")
            
            # Get certificate files (will auto-generate)
            cert_file, key_file = tls_config.get_cert_files()
            
            print(f"✓ Certificate file: {cert_file}")
            print(f"✓ Private key file: {key_file}")
            
            # Validate certificates
            validation_info = tls_config.validate_certificates()
            
            if "error" not in validation_info:
                print(f"✓ Certificate validation successful:")
                print(f"  - Subject: {validation_info['subject']}")
                print(f"  - Valid: {validation_info['is_valid']}")
                print(f"  - Days until expiry: {validation_info['days_until_expiry']}")
                print(f"  - Self-signed: {validation_info['is_self_signed']}")
            else:
                print(f"✗ Certificate validation failed: {validation_info['error']}")
            
            # Create SSL context
            ssl_context = tls_config.create_ssl_context()
            print(f"✓ SSL context created successfully")
            
    except ImportError:
        print("✗ TLS demo skipped - cryptography package features not available")
    except Exception as e:
        print(f"✗ TLS demo failed: {e}")
    
    print()


def demo_security_config():
    """Demonstrate security configuration."""
    print("=== Security Configuration Demo ===")
    
    # Create security configuration
    config = SecurityConfig()
    
    print("✓ Default security configuration:")
    print(f"  - Encryption enabled: {config.encryption.enabled}")
    print(f"  - Authentication enabled: {config.authentication.enabled}")
    print(f"  - Rate limiting enabled: {config.rate_limiting.enabled}")
    print(f"  - TLS enabled: {config.tls.enabled}")
    print(f"  - Max requests: {config.rate_limiting.max_requests}")
    print(f"  - Time window: {config.rate_limiting.time_window}s")
    
    # Save to file and load back
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        config.save_to_yaml_file(f.name)
        print(f"✓ Configuration saved to: {f.name}")
        
        # Load it back
        loaded_config = SecurityConfig.from_yaml_file(f.name)
        print(f"✓ Configuration loaded successfully")
        
        # Verify it matches
        assert loaded_config.rate_limiting.max_requests == config.rate_limiting.max_requests
        print(f"✓ Configuration integrity verified")
        
        # Clean up
        os.unlink(f.name)
    
    print()


async def demo_secure_server():
    """Demonstrate secure server configuration."""
    print("=== Secure Server Demo ===")
    
    try:
        # Create a secure server configuration
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "demo.db")
            
            # Initialize secure REST API server
            server = MemoryRestAPI(
                db_path=db_path,
                api_key="demo-api-key-123",
                encryption_passphrase="demo-encryption-passphrase",
                enable_https=False,  # Disable HTTPS for demo
                rate_limit_requests=10,
                rate_limit_window=60,
                allowed_origins=["http://localhost:3000"],
                allowed_ips=None  # Allow all IPs for demo
            )
            
            print("✓ Secure server initialized with:")
            print("  - API key authentication")
            print("  - Data encryption")
            print("  - Rate limiting (10 req/min)")
            print("  - CORS protection")
            print("  - Security headers")
            
            # Initialize server components
            await server.initialize()
            print("✓ Server components initialized successfully")
            
            # Test health check
            health_status = await server._health_check()
            print(f"✓ Server health check: {health_status.status}")
            
            # Clean up
            await server.cleanup()
            print("✓ Server cleanup completed")
            
    except Exception as e:
        print(f"✗ Secure server demo failed: {e}")
    
    print()


async def main():
    """Run all security demonstrations."""
    print("Cross-Tool Memory MCP Server - Security Features Demo")
    print("=" * 60)
    print()
    
    # Run demonstrations
    demo_encryption()
    demo_api_key_auth()
    await demo_rate_limiting()
    demo_tls_config()
    demo_security_config()
    await demo_secure_server()
    
    print("=" * 60)
    print("✓ All security demonstrations completed successfully!")
    print()
    print("Key Security Features:")
    print("• AES-256 encryption for data at rest")
    print("• Secure key derivation using Scrypt KDF")
    print("• API key authentication with hashing")
    print("• Token bucket rate limiting")
    print("• TLS/HTTPS support with auto-generated certificates")
    print("• Access control and security headers")
    print("• Comprehensive security configuration")
    print()
    print("For production use:")
    print("1. Set strong encryption passphrase via ENCRYPTION_PASSPHRASE env var")
    print("2. Generate secure API keys and set via API_KEYS env var")
    print("3. Enable HTTPS with proper certificates")
    print("4. Configure appropriate rate limits")
    print("5. Restrict allowed origins and IPs as needed")


if __name__ == "__main__":
    asyncio.run(main())