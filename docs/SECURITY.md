# Security Implementation

This document describes the comprehensive security features implemented for the Cross-Tool Memory MCP Server.

## Overview

The security implementation provides multiple layers of protection including data encryption, authentication, rate limiting, and secure communications. All security features are designed to work together seamlessly while maintaining performance and usability.

## Features Implemented

### 1. Data Encryption at Rest (AES-256)

**Location**: `src/cross_tool_memory/services/encryption_service.py`

- **Algorithm**: AES-256 encryption using Fernet (symmetric encryption)
- **Key Derivation**: Scrypt KDF with configurable parameters
- **Salt Management**: Automatic salt generation and storage
- **Field-Level Encryption**: Selective encryption of sensitive fields in dictionaries
- **Key Rotation**: Support for encryption key rotation with data migration

**Features**:
- Secure passphrase-based key derivation
- Automatic encryption/decryption of conversation content
- Metadata field encryption for sensitive data
- Graceful fallback when encryption is disabled
- Memory-safe cleanup of sensitive data

**Usage**:
```python
from cross_tool_memory.services.encryption_service import EncryptionService

# Initialize with passphrase
service = EncryptionService("your-secure-passphrase")
salt = service.initialize()

# Encrypt sensitive data
encrypted = service.encrypt("sensitive data")
decrypted = service.decrypt(encrypted)

# Encrypt dictionary fields
data = {"public": "data", "private": "sensitive"}
encrypted_data = service.encrypt_dict(data, ["private"])
```

### 2. API Key Authentication

**Location**: `src/cross_tool_memory/security/access_control.py`

- **Hashing**: Optional SHA-256 hashing of API keys for secure storage
- **Multiple Keys**: Support for multiple API keys
- **Key Management**: Add/remove keys dynamically
- **Environment Integration**: Load keys from environment variables

**Features**:
- Secure API key verification
- Automatic key generation
- Hash-based storage for security
- Integration with FastAPI security

**Usage**:
```python
from cross_tool_memory.security.access_control import APIKeyAuth

# Initialize with API keys
auth = APIKeyAuth({"key1", "key2"}, hash_keys=True)

# Verify keys
is_valid = auth.verify_key("key1")

# Generate new key
new_key = auth.generate_key()
```

### 3. Rate Limiting

**Location**: `src/cross_tool_memory/security/rate_limiting.py`

- **Algorithm**: Token bucket rate limiting
- **Per-Client Limits**: Individual rate limits per client IP/ID
- **Configurable Costs**: Different request costs for different operations
- **Background Cleanup**: Automatic cleanup of inactive clients
- **Burst Support**: Configurable burst capacity

**Features**:
- Sliding window rate limiting
- Request cost calculation
- Client statistics tracking
- Automatic bucket cleanup
- Rate limit reset functionality

**Usage**:
```python
from cross_tool_memory.security.rate_limiting import RateLimiter

# Initialize rate limiter
limiter = RateLimiter(max_requests=100, time_window=60)

# Check if request is allowed
allowed, info = limiter.is_allowed("client-id", cost=1)
```

### 4. TLS/HTTPS Configuration

**Location**: `src/cross_tool_memory/security/tls_config.py`

- **Auto-Generation**: Automatic self-signed certificate generation
- **Certificate Management**: Certificate validation and information extraction
- **SSL Context**: Secure SSL context creation with modern settings
- **Uvicorn Integration**: Direct integration with Uvicorn server

**Features**:
- Self-signed certificate generation for development
- Certificate validation and expiry checking
- Secure cipher suite configuration
- TLS 1.2+ enforcement
- Certificate file management

**Usage**:
```python
from cross_tool_memory.security.tls_config import TLSConfig

# Initialize TLS config
config = TLSConfig(auto_generate=True)

# Get certificate files (auto-generates if needed)
cert_file, key_file = config.get_cert_files()

# Create SSL context
ssl_context = config.create_ssl_context()
```

### 5. Access Control Middleware

**Location**: `src/cross_tool_memory/security/access_control.py`

- **IP Allowlisting**: Restrict access by IP address
- **Origin Validation**: CORS origin validation
- **Security Headers**: Automatic security header injection
- **HTTPS Enforcement**: Optional HTTPS requirement

**Security Headers Added**:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'`

### 6. Security Configuration

**Location**: `src/cross_tool_memory/config/security_config.py`

- **Centralized Config**: Single configuration class for all security settings
- **Environment Integration**: Load settings from environment variables
- **YAML Support**: Save/load configuration from YAML files
- **Validation**: Configuration validation and defaults

**Configuration Options**:
```yaml
security:
  encryption:
    enabled: true
    passphrase_env_var: "ENCRYPTION_PASSPHRASE"
    auto_generate_salt: true
  
  authentication:
    enabled: true
    api_keys_env_var: "API_KEYS"
    hash_keys: true
  
  rate_limiting:
    enabled: true
    max_requests: 100
    time_window: 60
    exempt_paths: ["/health", "/docs"]
  
  tls:
    enabled: false
    auto_generate: true
    require_https: false
  
  access_control:
    allowed_origins: ["http://localhost:*"]
    security_headers: true
```

## Integration with REST API

The security features are fully integrated into the REST API server:

```python
from cross_tool_memory.server.rest_api import MemoryRestAPI

# Create secure server
server = MemoryRestAPI(
    db_path="memory.db",
    api_key="your-api-key",
    encryption_passphrase="your-passphrase",
    enable_https=True,
    rate_limit_requests=100,
    rate_limit_window=60,
    allowed_origins=["https://yourdomain.com"],
    allowed_ips=["192.168.1.0/24"]
)

# Run with HTTPS
server.run(host="0.0.0.0", port=8443)
```

## Environment Variables

Configure security through environment variables:

```bash
# Encryption
export ENCRYPTION_PASSPHRASE="your-secure-passphrase-here"

# Authentication
export API_KEYS="key1,key2,key3"

# Rate Limiting
export RATE_LIMIT_REQUESTS=100
export RATE_LIMIT_WINDOW=60

# TLS
export TLS_ENABLED=true
export TLS_CERT_FILE="/path/to/cert.pem"
export TLS_KEY_FILE="/path/to/key.pem"

# Access Control
export ALLOWED_ORIGINS="https://app1.com,https://app2.com"
export ALLOWED_IPS="192.168.1.0/24,10.0.0.0/8"
```

## Security Best Practices

### For Development
1. Use auto-generated self-signed certificates
2. Set reasonable rate limits for testing
3. Use environment variables for secrets
4. Enable all security features to test integration

### For Production
1. **Use strong encryption passphrases** (minimum 32 characters, high entropy)
2. **Generate secure API keys** (use the built-in generator or cryptographically secure methods)
3. **Use proper TLS certificates** from a trusted CA
4. **Configure strict rate limits** based on expected usage
5. **Restrict allowed origins and IPs** to known clients only
6. **Enable HTTPS enforcement** for all communications
7. **Regularly rotate encryption keys and API keys**
8. **Monitor rate limit violations** for potential attacks
9. **Keep certificates up to date** and monitor expiry

### Security Monitoring
- Monitor rate limit violations
- Track authentication failures
- Log security events
- Monitor certificate expiry
- Regular security audits

## Testing

Comprehensive test suite available in `tests/test_security_integration.py`:

```bash
# Run security tests
python -m pytest tests/test_security_integration.py -v

# Run security demo
python examples/security_demo.py
```

## Performance Considerations

- **Encryption**: Minimal overhead (~1-2ms per operation)
- **Rate Limiting**: In-memory token buckets, very fast
- **Authentication**: Hashed key lookup, constant time
- **TLS**: Standard TLS overhead, negligible for most use cases

## Compliance

The implementation follows security best practices:
- **OWASP**: Addresses common web application security risks
- **NIST**: Uses approved cryptographic algorithms
- **RFC Standards**: Follows HTTP security header standards
- **Industry Standards**: Implements common security patterns

## Troubleshooting

### Common Issues

1. **Encryption fails**: Check passphrase is set correctly
2. **Authentication fails**: Verify API keys are configured
3. **Rate limiting too strict**: Adjust limits or exempt paths
4. **TLS certificate issues**: Check certificate files and permissions
5. **CORS errors**: Verify allowed origins configuration

### Debug Mode

Enable debug logging for security components:

```python
import logging
logging.getLogger('cross_tool_memory.security').setLevel(logging.DEBUG)
logging.getLogger('cross_tool_memory.services.encryption_service').setLevel(logging.DEBUG)
```

## Future Enhancements

Potential future security improvements:
- OAuth2/OIDC integration
- Certificate pinning
- Advanced threat detection
- Audit logging
- Multi-factor authentication
- Hardware security module (HSM) support
- Database-level encryption
- Field-level access controls