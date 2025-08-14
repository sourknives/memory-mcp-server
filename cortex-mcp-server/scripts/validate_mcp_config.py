#!/usr/bin/env python3
"""
MCP Configuration Validation Script

This script validates MCP configuration files and tests connectivity.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any
import httpx


def validate_json_structure(config: Dict[str, Any]) -> bool:
    """Validate the basic JSON structure of MCP config."""
    if "mcpServers" not in config:
        print("❌ Missing 'mcpServers' key")
        return False
    
    servers = config["mcpServers"]
    if not isinstance(servers, dict):
        print("❌ 'mcpServers' must be an object")
        return False
    
    for server_name, server_config in servers.items():
        print(f"🔍 Validating server: {server_name}")
        
        if "command" not in server_config:
            print(f"❌ Missing 'command' for server {server_name}")
            return False
        
        if "args" not in server_config:
            print(f"❌ Missing 'args' for server {server_name}")
            return False
        
        if not isinstance(server_config["args"], list):
            print(f"❌ 'args' must be an array for server {server_name}")
            return False
        
        print(f"✅ Server {server_name} structure is valid")
    
    return True


def validate_local_config(server_config: Dict[str, Any]) -> bool:
    """Validate local server configuration."""
    command = server_config["command"]
    args = server_config["args"]
    
    # Check if it's a Python command
    if command == "python" and len(args) >= 2:
        if args[0] == "-m" and args[1] == "cortex_mcp.main":
            print("✅ Local Python module configuration detected")
            
            # Check working directory
            cwd = server_config.get("cwd")
            if cwd and not os.path.exists(cwd):
                print(f"⚠️  Working directory does not exist: {cwd}")
                return False
            
            # Check environment variables
            env = server_config.get("env", {})
            db_path = env.get("CORTEX_MCP_DB_PATH", "memory.db")
            if cwd:
                full_db_path = os.path.join(cwd, db_path)
                if not os.path.exists(os.path.dirname(full_db_path)):
                    print(f"⚠️  Database directory does not exist: {os.path.dirname(full_db_path)}")
            
            return True
    
    return False


async def validate_remote_config(server_config: Dict[str, Any]) -> bool:
    """Validate remote server configuration."""
    env = server_config.get("env", {})
    server_url = env.get("CORTEX_MCP_SERVER_URL")
    
    if not server_url:
        print("❌ Missing CORTEX_MCP_SERVER_URL environment variable")
        return False
    
    print(f"🔍 Testing connection to: {server_url}")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test health endpoint
            health_url = f"{server_url.rstrip('/')}/health"
            response = await client.get(health_url)
            
            if response.status_code == 200:
                print("✅ Server health check passed")
                return True
            else:
                print(f"⚠️  Server returned status {response.status_code}")
                return False
                
    except httpx.ConnectError:
        print("❌ Cannot connect to server - is it running?")
        return False
    except httpx.TimeoutException:
        print("❌ Connection timeout - server may be slow or unreachable")
        return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False


def detect_config_type(server_config: Dict[str, Any]) -> str:
    """Detect if configuration is for local or remote server."""
    args = server_config.get("args", [])
    env = server_config.get("env", {})
    
    if "cortex_mcp.client.remote_client" in args:
        return "remote"
    elif "CORTEX_MCP_SERVER_URL" in env:
        return "remote"
    elif "cortex_mcp.main" in args:
        return "local"
    else:
        return "unknown"


async def validate_config_file(config_path: str) -> bool:
    """Validate a complete MCP configuration file."""
    print(f"🔍 Validating configuration file: {config_path}")
    
    if not os.path.exists(config_path):
        print(f"❌ Configuration file not found: {config_path}")
        return False
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        return False
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False
    
    # Validate JSON structure
    if not validate_json_structure(config):
        return False
    
    # Validate each server
    all_valid = True
    for server_name, server_config in config["mcpServers"].items():
        config_type = detect_config_type(server_config)
        print(f"📋 Server {server_name} type: {config_type}")
        
        if config_type == "local":
            if not validate_local_config(server_config):
                all_valid = False
        elif config_type == "remote":
            if not await validate_remote_config(server_config):
                all_valid = False
        else:
            print(f"⚠️  Unknown configuration type for server {server_name}")
            all_valid = False
    
    return all_valid


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate Cortex MCP configuration files"
    )
    parser.add_argument(
        "config_file",
        help="Path to MCP configuration file"
    )
    parser.add_argument(
        "--skip-connectivity",
        action="store_true",
        help="Skip remote server connectivity tests"
    )
    
    args = parser.parse_args()
    
    print("🚀 Cortex MCP Configuration Validator")
    print("=" * 40)
    
    # Override connectivity tests if requested
    if args.skip_connectivity:
        global validate_remote_config
        async def validate_remote_config(server_config):
            print("⏭️  Skipping connectivity test")
            return True
    
    success = await validate_config_file(args.config_file)
    
    print("=" * 40)
    if success:
        print("✅ Configuration validation passed!")
        sys.exit(0)
    else:
        print("❌ Configuration validation failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())