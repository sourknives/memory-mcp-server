#!/usr/bin/env python3
"""
MCP Server entry point for Cortex MCP.

This script provides the MCP server functionality.
"""

import asyncio
import sys
from pathlib import Path

# Add the current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from server.mcp_server import main

if __name__ == "__main__":
    asyncio.run(main())