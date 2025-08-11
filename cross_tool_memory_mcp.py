#!/usr/bin/env python3
"""
MCP Server entry point for Cross-Tool Memory.

This script provides the MCP server functionality for Claude Desktop integration.
"""

import asyncio
import sys
from pathlib import Path

# Add the src directory to Python path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from cross_tool_memory.server.mcp_server import main

if __name__ == "__main__":
    asyncio.run(main())