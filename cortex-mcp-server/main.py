"""Main entry point for the Cortex MCP Server."""

import argparse
import asyncio
import logging
import os
from pathlib import Path

from server.mcp_server import MCPMemoryServer
from server.rest_api import run_server as run_rest_server


async def main():
    """Main entry point for the memory server."""
    parser = argparse.ArgumentParser(description="Cortex MCP Server")
    parser.add_argument(
        "--mode",
        choices=["mcp", "rest", "both"],
        default="mcp",
        help="Server mode: mcp (MCP protocol), rest (REST API), or both"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind REST API server (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for REST API server (default: 8000)"
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="Path to SQLite database file (default: memory.db)"
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key for REST API authentication (optional)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Get configuration
    db_path = args.db_path or os.getenv("MEMORY_DB_PATH", "memory.db")
    api_key = args.api_key or os.getenv("API_KEY")
    host = args.host or os.getenv("API_HOST", "127.0.0.1")
    port = args.port or int(os.getenv("API_PORT", "8000"))
    
    if args.mode == "mcp":
        logger.info("Starting Cortex MCP Server...")
        server = MCPMemoryServer(db_path=db_path)
        
        try:
            await server.run()
        except KeyboardInterrupt:
            logger.info("MCP Server interrupted by user")
        except Exception as e:
            logger.error(f"MCP Server error: {e}")
            raise
        finally:
            await server.cleanup()
    
    elif args.mode == "rest":
        logger.info(f"Starting Cortex MCP REST API Server on {host}:{port}...")
        
        try:
            await run_rest_server(
                host=host,
                port=port,
                db_path=db_path,
                api_key=api_key
            )
        except KeyboardInterrupt:
            logger.info("REST API Server interrupted by user")
        except Exception as e:
            logger.error(f"REST API Server error: {e}")
            raise
    
    elif args.mode == "both":
        logger.info("Starting both MCP and REST API servers...")
        
        # Run both servers concurrently
        mcp_server = MCPMemoryServer(db_path=db_path)
        
        async def run_mcp():
            try:
                await mcp_server.run()
            except Exception as e:
                logger.error(f"MCP Server error: {e}")
                raise
            finally:
                await mcp_server.cleanup()
        
        async def run_rest():
            try:
                await run_rest_server(
                    host=host,
                    port=port,
                    db_path=db_path,
                    api_key=api_key
                )
            except Exception as e:
                logger.error(f"REST API Server error: {e}")
                raise
        
        try:
            # Run both servers concurrently
            await asyncio.gather(
                run_mcp(),
                run_rest()
            )
        except KeyboardInterrupt:
            logger.info("Servers interrupted by user")
        except Exception as e:
            logger.error(f"Server error: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())