#!/usr/bin/env python3
"""
API Key Management CLI for Cortex MCP Server

This script provides command-line management of API keys including:
- Generate new API keys
- List existing keys
- Add/remove keys
- Key rotation
- Persistent storage
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import secrets
import hashlib

# Add the parent directory to Python path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from security.access_control import APIKeyAuth


class APIKeyManager:
    """Persistent API key management."""
    
    def __init__(self, keys_file: str = "api_keys.json"):
        self.keys_file = Path(keys_file)
        self.keys_data = self._load_keys()
    
    def _load_keys(self) -> Dict:
        """Load keys from persistent storage."""
        if self.keys_file.exists():
            try:
                with open(self.keys_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                print(f"⚠️  Warning: Could not read {self.keys_file}, starting fresh")
        
        return {
            "keys": {},
            "metadata": {
                "created": datetime.now().isoformat(),
                "version": "1.0"
            }
        }
    
    def _save_keys(self):
        """Save keys to persistent storage."""
        self.keys_data["metadata"]["updated"] = datetime.now().isoformat()
        
        # Create directory if it doesn't exist
        self.keys_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.keys_file, 'w') as f:
            json.dump(self.keys_data, f, indent=2)
    
    def _hash_key(self, key: str) -> str:
        """Hash an API key."""
        return hashlib.sha256(key.encode('utf-8')).hexdigest()
    
    def generate_key(self, name: str, length: int = 32, expires_days: Optional[int] = None) -> str:
        """Generate a new API key."""
        key = secrets.token_urlsafe(length)
        key_hash = self._hash_key(key)
        
        key_info = {
            "name": name,
            "hash": key_hash,
            "created": datetime.now().isoformat(),
            "last_used": None,
            "usage_count": 0,
            "active": True
        }
        
        if expires_days:
            expiry = datetime.now() + timedelta(days=expires_days)
            key_info["expires"] = expiry.isoformat()
        
        # Store with key ID (first 8 chars of hash)
        key_id = key_hash[:8]
        self.keys_data["keys"][key_id] = key_info
        self._save_keys()
        
        return key, key_id
    
    def list_keys(self) -> List[Dict]:
        """List all API keys with metadata."""
        keys = []
        for key_id, info in self.keys_data["keys"].items():
            key_info = {
                "id": key_id,
                "name": info["name"],
                "created": info["created"],
                "active": info["active"],
                "usage_count": info.get("usage_count", 0),
                "last_used": info.get("last_used"),
                "expires": info.get("expires")
            }
            
            # Check if expired
            if key_info["expires"]:
                expiry = datetime.fromisoformat(key_info["expires"])
                key_info["expired"] = datetime.now() > expiry
            else:
                key_info["expired"] = False
            
            keys.append(key_info)
        
        return keys
    
    def deactivate_key(self, key_id: str) -> bool:
        """Deactivate an API key."""
        if key_id in self.keys_data["keys"]:
            self.keys_data["keys"][key_id]["active"] = False
            self.keys_data["keys"][key_id]["deactivated"] = datetime.now().isoformat()
            self._save_keys()
            return True
        return False
    
    def delete_key(self, key_id: str) -> bool:
        """Permanently delete an API key."""
        if key_id in self.keys_data["keys"]:
            del self.keys_data["keys"][key_id]
            self._save_keys()
            return True
        return False
    
    def verify_key(self, key: str) -> Optional[str]:
        """Verify an API key and return key ID if valid."""
        key_hash = self._hash_key(key)
        
        for key_id, info in self.keys_data["keys"].items():
            if info["hash"] == key_hash and info["active"]:
                # Check expiry
                if info.get("expires"):
                    expiry = datetime.fromisoformat(info["expires"])
                    if datetime.now() > expiry:
                        continue
                
                # Update usage
                info["usage_count"] = info.get("usage_count", 0) + 1
                info["last_used"] = datetime.now().isoformat()
                self._save_keys()
                
                return key_id
        
        return None
    
    def get_active_keys(self) -> List[str]:
        """Get list of active API key hashes for APIKeyAuth."""
        active_hashes = []
        
        for info in self.keys_data["keys"].values():
            if not info["active"]:
                continue
            
            # Check expiry
            if info.get("expires"):
                expiry = datetime.fromisoformat(info["expires"])
                if datetime.now() > expiry:
                    continue
            
            active_hashes.append(info["hash"])
        
        return active_hashes
    
    def rotate_key(self, key_id: str, length: int = 32) -> Optional[str]:
        """Rotate an existing API key."""
        if key_id not in self.keys_data["keys"]:
            return None
        
        old_info = self.keys_data["keys"][key_id]
        new_key = secrets.token_urlsafe(length)
        new_hash = self._hash_key(new_key)
        
        # Update the key info
        old_info["hash"] = new_hash
        old_info["rotated"] = datetime.now().isoformat()
        old_info["usage_count"] = 0
        old_info["last_used"] = None
        
        self._save_keys()
        return new_key


def cmd_generate(args):
    """Generate a new API key."""
    manager = APIKeyManager(args.keys_file)
    
    key, key_id = manager.generate_key(
        name=args.name,
        length=args.length,
        expires_days=args.expires
    )
    
    print(f"✅ Generated new API key:")
    print(f"   ID: {key_id}")
    print(f"   Name: {args.name}")
    print(f"   Key: {key}")
    print()
    print("⚠️  Store this key securely - it won't be shown again!")
    
    if args.env:
        print(f"\n📝 Environment variable:")
        print(f"   export CORTEX_MCP_API_KEY='{key}'")


def cmd_list(args):
    """List all API keys."""
    manager = APIKeyManager(args.keys_file)
    keys = manager.list_keys()
    
    if not keys:
        print("No API keys found.")
        return
    
    print(f"📋 API Keys ({len(keys)} total):")
    print()
    
    for key in keys:
        status = "🟢 Active" if key["active"] and not key["expired"] else "🔴 Inactive"
        if key["expired"]:
            status = "⏰ Expired"
        
        print(f"   {status} {key['id']} - {key['name']}")
        print(f"      Created: {key['created'][:19]}")
        print(f"      Usage: {key['usage_count']} times")
        
        if key['last_used']:
            print(f"      Last used: {key['last_used'][:19]}")
        
        if key['expires']:
            print(f"      Expires: {key['expires'][:19]}")
        
        print()


def cmd_deactivate(args):
    """Deactivate an API key."""
    manager = APIKeyManager(args.keys_file)
    
    if manager.deactivate_key(args.key_id):
        print(f"✅ Deactivated API key: {args.key_id}")
    else:
        print(f"❌ API key not found: {args.key_id}")


def cmd_delete(args):
    """Delete an API key."""
    manager = APIKeyManager(args.keys_file)
    
    if not args.confirm:
        response = input(f"⚠️  Really delete API key {args.key_id}? (y/N): ")
        if response.lower() != 'y':
            print("Cancelled.")
            return
    
    if manager.delete_key(args.key_id):
        print(f"✅ Deleted API key: {args.key_id}")
    else:
        print(f"❌ API key not found: {args.key_id}")


def cmd_rotate(args):
    """Rotate an API key."""
    manager = APIKeyManager(args.keys_file)
    
    new_key = manager.rotate_key(args.key_id, args.length)
    
    if new_key:
        print(f"✅ Rotated API key: {args.key_id}")
        print(f"   New key: {new_key}")
        print()
        print("⚠️  Update your applications with the new key!")
        
        if args.env:
            print(f"\n📝 Environment variable:")
            print(f"   export CORTEX_MCP_API_KEY='{new_key}'")
    else:
        print(f"❌ API key not found: {args.key_id}")


def cmd_verify(args):
    """Verify an API key."""
    manager = APIKeyManager(args.keys_file)
    
    key_id = manager.verify_key(args.key)
    
    if key_id:
        print(f"✅ Valid API key (ID: {key_id})")
    else:
        print("❌ Invalid or expired API key")


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Cortex MCP Server API Key Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate a new API key
  python manage_api_keys.py generate --name "production-server"
  
  # List all keys
  python manage_api_keys.py list
  
  # Deactivate a key
  python manage_api_keys.py deactivate abc12345
  
  # Rotate a key
  python manage_api_keys.py rotate abc12345
        """
    )
    
    parser.add_argument(
        "--keys-file",
        default="./data/api_keys.json",
        help="Path to API keys storage file"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate a new API key")
    gen_parser.add_argument("--name", required=True, help="Name for the API key")
    gen_parser.add_argument("--length", type=int, default=32, help="Key length")
    gen_parser.add_argument("--expires", type=int, help="Expiry in days")
    gen_parser.add_argument("--env", action="store_true", help="Show environment variable")
    gen_parser.set_defaults(func=cmd_generate)
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all API keys")
    list_parser.set_defaults(func=cmd_list)
    
    # Deactivate command
    deact_parser = subparsers.add_parser("deactivate", help="Deactivate an API key")
    deact_parser.add_argument("key_id", help="API key ID to deactivate")
    deact_parser.set_defaults(func=cmd_deactivate)
    
    # Delete command
    del_parser = subparsers.add_parser("delete", help="Delete an API key")
    del_parser.add_argument("key_id", help="API key ID to delete")
    del_parser.add_argument("--confirm", action="store_true", help="Skip confirmation")
    del_parser.set_defaults(func=cmd_delete)
    
    # Rotate command
    rot_parser = subparsers.add_parser("rotate", help="Rotate an API key")
    rot_parser.add_argument("key_id", help="API key ID to rotate")
    rot_parser.add_argument("--length", type=int, default=32, help="New key length")
    rot_parser.add_argument("--env", action="store_true", help="Show environment variable")
    rot_parser.set_defaults(func=cmd_rotate)
    
    # Verify command
    ver_parser = subparsers.add_parser("verify", help="Verify an API key")
    ver_parser.add_argument("key", help="API key to verify")
    ver_parser.set_defaults(func=cmd_verify)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    args.func(args)


if __name__ == "__main__":
    main()