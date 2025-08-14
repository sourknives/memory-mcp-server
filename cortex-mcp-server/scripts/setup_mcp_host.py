#!/usr/bin/env python3
"""
MCP Host Setup Script

This script helps users set up Cortex MCP configurations for various AI development tools.
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, Any, Optional


def get_claude_config_path() -> Optional[str]:
    """Get Claude Desktop configuration path."""
    if sys.platform == "darwin":  # macOS
        return os.path.expanduser("~/Library/Application Support/Claude/claude_desktop_config.json")
    elif sys.platform == "win32":  # Windows
        return os.path.expandvars(r"%APPDATA%\Claude\claude_desktop_config.json")
    else:  # Linux
        return os.path.expanduser("~/.config/claude/claude_desktop_config.json")


def get_kiro_config_paths() -> Dict[str, str]:
    """Get Kiro IDE configuration paths."""
    return {
        "user": os.path.expanduser("~/.kiro/settings/mcp.json"),
        "workspace": ".kiro/settings/mcp.json"
    }


def get_cursor_config_path() -> Optional[str]:
    """Get Cursor IDE configuration path."""
    if sys.platform == "darwin":  # macOS
        return os.path.expanduser("~/Library/Application Support/Cursor/User/settings.json")
    elif sys.platform == "win32":  # Windows
        return os.path.expandvars(r"%APPDATA%\Cursor\User\settings.json")
    else:  # Linux
        return os.path.expanduser("~/.config/Cursor/User/settings.json")


def load_existing_config(config_path: str) -> Dict[str, Any]:
    """Load existing configuration file."""
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            print(f"⚠️  Warning: Could not read existing config at {config_path}")
    return {}


def merge_mcp_config(existing_config: Dict[str, Any], new_server_config: Dict[str, Any], server_name: str) -> Dict[str, Any]:
    """Merge new MCP server configuration with existing configuration."""
    if "mcpServers" not in existing_config:
        existing_config["mcpServers"] = {}
    
    existing_config["mcpServers"][server_name] = new_server_config
    return existing_config


def save_config(config: Dict[str, Any], config_path: str, backup: bool = True) -> bool:
    """Save configuration file with optional backup."""
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        # Backup existing file
        if backup and os.path.exists(config_path):
            backup_path = f"{config_path}.backup"
            shutil.copy2(config_path, backup_path)
            print(f"📋 Backed up existing config to: {backup_path}")
        
        # Write new configuration
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"✅ Configuration saved to: {config_path}")
        return True
        
    except Exception as e:
        print(f"❌ Error saving configuration: {e}")
        return False


def setup_claude_desktop(server_config: Dict[str, Any], server_name: str = "cortex-mcp") -> bool:
    """Set up Claude Desktop configuration."""
    config_path = get_claude_config_path()
    if not config_path:
        print("❌ Could not determine Claude Desktop configuration path")
        return False
    
    print(f"🔧 Setting up Claude Desktop configuration...")
    
    existing_config = load_existing_config(config_path)
    merged_config = merge_mcp_config(existing_config, server_config, server_name)
    
    return save_config(merged_config, config_path)


def setup_kiro_ide(server_config: Dict[str, Any], server_name: str = "cortex-mcp", scope: str = "user") -> bool:
    """Set up Kiro IDE configuration."""
    config_paths = get_kiro_config_paths()
    config_path = config_paths.get(scope)
    
    if not config_path:
        print(f"❌ Invalid scope: {scope}")
        return False
    
    print(f"🔧 Setting up Kiro IDE configuration ({scope})...")
    
    existing_config = load_existing_config(config_path)
    merged_config = merge_mcp_config(existing_config, server_config, server_name)
    
    return save_config(merged_config, config_path)


def setup_cursor_ide(server_config: Dict[str, Any], server_name: str = "cortex-mcp") -> bool:
    """Set up Cursor IDE configuration."""
    config_path = get_cursor_config_path()
    if not config_path:
        print("❌ Could not determine Cursor IDE configuration path")
        return False
    
    print(f"🔧 Setting up Cursor IDE configuration...")
    
    existing_config = load_existing_config(config_path)
    
    # Cursor uses a different structure
    if "mcp" not in existing_config:
        existing_config["mcp"] = {"servers": {}}
    elif "servers" not in existing_config["mcp"]:
        existing_config["mcp"]["servers"] = {}
    
    existing_config["mcp"]["servers"][server_name] = server_config
    
    return save_config(existing_config, config_path)


def get_project_path() -> str:
    """Get the current project path."""
    return os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


def create_local_config(project_path: str) -> Dict[str, Any]:
    """Create local server configuration."""
    return {
        "command": "python",
        "args": ["-m", "cortex_mcp.main", "--mode", "mcp"],
        "cwd": project_path,
        "env": {
            "CORTEX_MCP_DB_PATH": "memory.db",
            "CORTEX_MCP_LOG_LEVEL": "INFO",
            "CORTEX_MCP_CONFIG_PATH": "config.yml"
        }
    }


def create_remote_config(server_url: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """Create remote server configuration."""
    env = {
        "CORTEX_MCP_SERVER_URL": server_url,
        "CORTEX_MCP_TIMEOUT": "30"
    }
    
    if api_key:
        env["CORTEX_MCP_API_KEY"] = api_key
    
    if server_url.startswith("https://"):
        env["CORTEX_MCP_USE_TLS"] = "true"
        env["CORTEX_MCP_VERIFY_SSL"] = "true"
    
    return {
        "command": "python",
        "args": ["-m", "cortex_mcp.client.remote_client"],
        "env": env
    }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Set up Cortex MCP configuration for AI development tools"
    )
    parser.add_argument(
        "host",
        choices=["claude", "kiro", "cursor"],
        help="MCP host to configure"
    )
    parser.add_argument(
        "--mode",
        choices=["local", "remote"],
        default="local",
        help="Server mode (local or remote)"
    )
    parser.add_argument(
        "--server-url",
        help="Remote server URL (required for remote mode)"
    )
    parser.add_argument(
        "--api-key",
        help="API key for remote server authentication"
    )
    parser.add_argument(
        "--server-name",
        default="cortex-mcp",
        help="Name for the MCP server configuration"
    )
    parser.add_argument(
        "--kiro-scope",
        choices=["user", "workspace"],
        default="user",
        help="Scope for Kiro IDE configuration"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Don't backup existing configuration files"
    )
    
    args = parser.parse_args()
    
    print("🚀 Cortex MCP Host Setup")
    print("=" * 30)
    
    # Validate arguments
    if args.mode == "remote" and not args.server_url:
        print("❌ --server-url is required for remote mode")
        sys.exit(1)
    
    # Create server configuration
    if args.mode == "local":
        project_path = get_project_path()
        server_config = create_local_config(project_path)
        print(f"📁 Using project path: {project_path}")
    else:
        server_config = create_remote_config(args.server_url, args.api_key)
        print(f"🌐 Using remote server: {args.server_url}")
    
    # Set up the specified host
    success = False
    if args.host == "claude":
        success = setup_claude_desktop(server_config, args.server_name)
    elif args.host == "kiro":
        success = setup_kiro_ide(server_config, args.server_name, args.kiro_scope)
    elif args.host == "cursor":
        success = setup_cursor_ide(server_config, args.server_name)
    
    print("=" * 30)
    if success:
        print("✅ Setup completed successfully!")
        print(f"🔧 Configured {args.host} for {args.mode} mode")
        if args.mode == "local":
            print("💡 Make sure to install the package: pip install -e .")
        print("🔄 Restart your AI development tool to apply changes")
    else:
        print("❌ Setup failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()