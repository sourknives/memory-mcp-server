#!/usr/bin/env python3
"""
Main entry point for Cortex MCP Client.

This module provides the command-line interface for the remote MCP client.
"""

import asyncio
import argparse
import sys
import os
from .client import RemoteMCPClient


async def test_connection(client: RemoteMCPClient) -> bool:
    """Test connection to remote server."""
    try:
        response = await client._make_request("GET", "/health")
        print(f"✅ Connection successful: {response}")
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


def print_config_info():
    """Print current configuration information."""
    print("🔧 Current Configuration:")
    print(f"   Server URL: {os.getenv('CORTEX_MCP_SERVER_URL', 'http://localhost:8000')}")
    print(f"   API Key: {'Set' if os.getenv('CORTEX_MCP_API_KEY') else 'Not set'}")
    print(f"   Timeout: {os.getenv('CORTEX_MCP_TIMEOUT', '30')}s")
    print(f"   Use TLS: {os.getenv('CORTEX_MCP_USE_TLS', 'false')}")
    print(f"   Verify SSL: {os.getenv('CORTEX_MCP_VERIFY_SSL', 'true')}")


async def main():
    """Main entry point for the remote MCP client."""
    parser = argparse.ArgumentParser(
        description="Cortex MCP Remote Client - Connect MCP hosts to remote Cortex servers"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test connection to remote server and exit"
    )
    parser.add_argument(
        "--config",
        action="store_true",
        help="Show current configuration and exit"
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version and exit"
    )
    
    args = parser.parse_args()
    
    if args.version:
        from . import __version__
        print(f"cortex-mcp-client {__version__}")
        return
    
    if args.config:
        print_config_info()
        return
    
    client = RemoteMCPClient()
    
    if args.test:
        print("🧪 Testing connection to remote Cortex MCP server...")
        print_config_info()
        print()
        success = await test_connection(client)
        sys.exit(0 if success else 1)
    
    # Normal MCP client operation
    try:
        await client.run()
    except KeyboardInterrupt:
        print("\n👋 Cortex MCP Client stopped")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def cli_main():
    """CLI entry point (for setuptools console_scripts)."""
    asyncio.run(main())


if __name__ == "__main__":
    cli_main()