#!/usr/bin/env python3
"""Simple script to start the Cortex MCP Server for testing."""

import asyncio
import logging
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.rest_api import run_server

async def main():
    """Start the REST API server."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Starting Cortex MCP Server for testing...")
    
    try:
        await run_server(
            host="127.0.0.1",
            port=8000,
            db_path="memory.db",
            api_key=None
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())