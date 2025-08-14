"""
TLS configuration for HTTPS endpoints.

This module provides TLS/SSL configuration for securing HTTP communications
with the memory server.
"""

import logging
import os
import ssl
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class TLSConfig:
    """TLS/SSL configuration manager."""
    
    def __init__(
        self,
        cert_file: Optional[str] = None,
        key_file: Optional[str] = None,
        ca_file: Optional[str] = None,
        cert_dir: Optional[str] = None,
        auto_generate: bool = False,
        min_version: ssl.TLSVersion = ssl.TLSVersion.TLSv1_2,
        max_version: Optional[ssl.TLSVersion] = None,
        ciphers: Optional[str] = None
    ):
        """
        Initialize TLS configuration.
        
        Args:
            cert_file: Path to SSL certificate file
            key_file: Path to SSL private key file
            ca_file: Path to CA certificate file
            cert_dir: Directory to store generated certificates
            auto_generate: Whether to auto-generate self-signed certificates
            min_version: Minimum TLS version
            max_version: Maximum TLS version
            ciphers: Cipher suite specification
        """
        self.cert_file = cert_file
        self.key_file = key_file
        self.ca_file = ca_file
        self.cert_dir = cert_dir or os.path.expanduser("~/.cortex_mcp/certs")
        self.auto_generate = auto_generate
        self.min_version = min_version
        self.max_version = max_version
        self.ciphers = ciphers or "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS"
        
        # Ensure cert directory exists
        Path(self.cert_dir).mkdir(parents=True, exist_ok=True)
        
        logger.info("TLS configuration initialized")
    
    def _generate_self_signed_cert(self) -> tuple[str, str]:
        """
        Generate self-signed certificate and private key.
        
        Returns:
            tuple[str, str]: (cert_file_path, key_file_path)
        """
        try:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            import datetime
            import ipaddress
            
            # Generate private key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
            
            # Create certificate
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Local"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "Local"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Cortex MCP"),
                x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
            ])
            
            cert = x509.CertificateBuilder().subject_name(
                subject
            ).issuer_name(
                issuer
            ).public_key(
                private_key.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.datetime.utcnow()
            ).not_valid_after(
                datetime.datetime.utcnow() + datetime.timedelta(days=365)
            ).add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName("localhost"),
                    x509.DNSName("127.0.0.1"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                ]),
                critical=False,
            ).sign(private_key, hashes.SHA256())
            
            # Write certificate and key files
            cert_path = os.path.join(self.cert_dir, "server.crt")
            key_path = os.path.join(self.cert_dir, "server.key")
            
            with open(cert_path, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))
            
            with open(key_path, "wb") as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            
            # Set secure permissions
            os.chmod(cert_path, 0o644)
            os.chmod(key_path, 0o600)
            
            logger.info(f"Generated self-signed certificate: {cert_path}")
            return cert_path, key_path
            
        except ImportError as e:
            logger.error("cryptography package required for certificate generation")
            raise RuntimeError("Cannot generate certificates without cryptography package") from e
        except Exception as e:
            logger.error(f"Failed to generate self-signed certificate: {e}")
            raise
    
    def get_cert_files(self) -> tuple[str, str]:
        """
        Get certificate and key file paths.
        
        Returns:
            tuple[str, str]: (cert_file_path, key_file_path)
            
        Raises:
            FileNotFoundError: If certificate files don't exist and auto_generate is False
            RuntimeError: If certificate generation fails
        """
        cert_file = self.cert_file
        key_file = self.key_file
        
        # Use default paths if not specified
        if not cert_file:
            cert_file = os.path.join(self.cert_dir, "server.crt")
        if not key_file:
            key_file = os.path.join(self.cert_dir, "server.key")
        
        # Check if files exist
        if not (os.path.exists(cert_file) and os.path.exists(key_file)):
            if self.auto_generate:
                logger.info("Certificate files not found, generating self-signed certificate")
                cert_file, key_file = self._generate_self_signed_cert()
            else:
                raise FileNotFoundError(
                    f"Certificate files not found: {cert_file}, {key_file}. "
                    "Set auto_generate=True to generate self-signed certificates."
                )
        
        return cert_file, key_file
    
    def create_ssl_context(self) -> ssl.SSLContext:
        """
        Create SSL context with secure configuration.
        
        Returns:
            ssl.SSLContext: Configured SSL context
        """
        try:
            # Create SSL context
            context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            
            # Set TLS versions
            context.minimum_version = self.min_version
            if self.max_version:
                context.maximum_version = self.max_version
            
            # Set cipher suites
            if self.ciphers:
                context.set_ciphers(self.ciphers)
            
            # Load certificate and key
            cert_file, key_file = self.get_cert_files()
            context.load_cert_chain(cert_file, key_file)
            
            # Load CA certificates if specified
            if self.ca_file and os.path.exists(self.ca_file):
                context.load_verify_locations(self.ca_file)
            
            # Security settings
            context.check_hostname = False  # We're binding to localhost
            context.verify_mode = ssl.CERT_NONE  # No client certificate required
            
            # Disable weak protocols and ciphers
            context.options |= ssl.OP_NO_SSLv2
            context.options |= ssl.OP_NO_SSLv3
            context.options |= ssl.OP_NO_TLSv1
            context.options |= ssl.OP_NO_TLSv1_1
            context.options |= ssl.OP_SINGLE_DH_USE
            context.options |= ssl.OP_SINGLE_ECDH_USE
            
            logger.info(f"SSL context created with certificate: {cert_file}")
            return context
            
        except Exception as e:
            logger.error(f"Failed to create SSL context: {e}")
            raise
    
    def validate_certificates(self) -> Dict[str, Any]:
        """
        Validate certificate files and return information.
        
        Returns:
            Dict[str, Any]: Certificate validation information
        """
        try:
            from cryptography import x509
            from cryptography.hazmat.primitives import serialization
            import datetime
            
            cert_file, key_file = self.get_cert_files()
            
            # Load and parse certificate
            with open(cert_file, "rb") as f:
                cert_data = f.read()
                cert = x509.load_pem_x509_certificate(cert_data)
            
            # Load and parse private key
            with open(key_file, "rb") as f:
                key_data = f.read()
                private_key = serialization.load_pem_private_key(key_data, password=None)
            
            # Extract certificate information
            subject = cert.subject
            issuer = cert.issuer
            not_before = cert.not_valid_before
            not_after = cert.not_valid_after
            
            # Check if certificate is valid
            now = datetime.datetime.utcnow()
            is_valid = not_before <= now <= not_after
            days_until_expiry = (not_after - now).days
            
            # Get subject alternative names
            san_extension = None
            try:
                san_extension = cert.extensions.get_extension_for_oid(x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
                san_names = [name.value for name in san_extension.value]
            except x509.ExtensionNotFound:
                san_names = []
            
            return {
                "cert_file": cert_file,
                "key_file": key_file,
                "subject": str(subject),
                "issuer": str(issuer),
                "not_before": not_before.isoformat(),
                "not_after": not_after.isoformat(),
                "is_valid": is_valid,
                "days_until_expiry": days_until_expiry,
                "subject_alternative_names": san_names,
                "is_self_signed": subject == issuer,
                "key_size": private_key.key_size if hasattr(private_key, 'key_size') else None
            }
            
        except Exception as e:
            logger.error(f"Certificate validation failed: {e}")
            return {
                "error": str(e),
                "is_valid": False
            }


def create_ssl_context(
    cert_file: Optional[str] = None,
    key_file: Optional[str] = None,
    ca_file: Optional[str] = None,
    auto_generate: bool = True,
    min_version: ssl.TLSVersion = ssl.TLSVersion.TLSv1_2
) -> ssl.SSLContext:
    """
    Create SSL context with default configuration.
    
    Args:
        cert_file: Path to SSL certificate file
        key_file: Path to SSL private key file
        ca_file: Path to CA certificate file
        auto_generate: Whether to auto-generate self-signed certificates
        min_version: Minimum TLS version
        
    Returns:
        ssl.SSLContext: Configured SSL context
    """
    tls_config = TLSConfig(
        cert_file=cert_file,
        key_file=key_file,
        ca_file=ca_file,
        auto_generate=auto_generate,
        min_version=min_version
    )
    
    return tls_config.create_ssl_context()


def get_uvicorn_ssl_config(
    cert_file: Optional[str] = None,
    key_file: Optional[str] = None,
    auto_generate: bool = True
) -> Dict[str, Any]:
    """
    Get SSL configuration for Uvicorn server.
    
    Args:
        cert_file: Path to SSL certificate file
        key_file: Path to SSL private key file
        auto_generate: Whether to auto-generate self-signed certificates
        
    Returns:
        Dict[str, Any]: Uvicorn SSL configuration
    """
    tls_config = TLSConfig(
        cert_file=cert_file,
        key_file=key_file,
        auto_generate=auto_generate
    )
    
    cert_file, key_file = tls_config.get_cert_files()
    
    return {
        "ssl_keyfile": key_file,
        "ssl_certfile": cert_file,
        "ssl_version": ssl.PROTOCOL_TLS_SERVER,
        "ssl_cert_reqs": ssl.CERT_NONE,
        "ssl_ca_certs": None,
        "ssl_ciphers": "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS"
    }