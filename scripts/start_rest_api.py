#!/usr/bin/env python3
"""
Startup script for the Cross-Tool Memory REST API server.

This script provides a simple way to start the REST API server with
common configuration options.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cross_tool_memory.server.rest_api import run_server


def main():
    """Main entry point for the REST API startup script."""
    parser = argparse.ArgumentParser(
        description="Start the Cross-Tool Memory REST API server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start server on default port (8000)
  python scripts/start_rest_api.py

  # Start server on custom port with API key
  python scripts/start_rest_api.py --port 9000 --api-key my-secret-key

  # Start server with custom database path
  python scripts/start_rest_api.py --db-path /path/to/memory.db

  # Start server in development mode with auto-reload
  python scripts/start_rest_api.py --dev

Environment Variables:
  API_HOST        - Host to bind to (default: 127.0.0.1)
  API_PORT        - Port to bind to (default: 8000)
  API_KEY         - API key for authentication (optional)
  MEMORY_DB_PATH  - Path to SQLite database file (default: memory.db)
  DEBUG           - Enable debug mode (default: false)
        """
    )
    
    parser.add_argument(
        "--host",
        default=os.getenv("API_HOST", "127.0.0.1"),
        help="Host to bind to (default: 127.0.0.1)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("API_PORT", "8000")),
        help="Port to bind to (default: 8000)"
    )
    
    parser.add_argument(
        "--api-key",
        default=os.getenv("API_KEY"),
        help="API key for authentication (optional)"
    )
    
    parser.add_argument(
        "--db-path",
        default=os.getenv("MEMORY_DB_PATH", "memory.db"),
        help="Path to SQLite database file (default: memory.db)"
    )
    
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Enable development mode with auto-reload"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    
    args = parser.parse_args()
    
    # Set up logging level
    if args.debug or os.getenv("DEBUG"):
        import logging
        logging.basicConfig(level=logging.DEBUG)
    
    print(f"🚀 Starting Cross-Tool Memory REST API server...")
    print(f"   Host: {args.host}")
    print(f"   Port: {args.port}")
    print(f"   Database: {args.db_path}")
    print(f"   Authentication: {'Enabled' if args.api_key else 'Disabled'}")
    print(f"   Development mode: {'Enabled' if args.dev else 'Disabled'}")
    print()
    print(f"📖 API Documentation will be available at:")
    print(f"   http://{args.host}:{args.port}/docs")
    print()
    print(f"🔍 Health check endpoint:")
    print(f"   http://{args.host}:{args.port}/health")
    print()
    
    if args.api_key:
        print(f"🔐 API Key configured. Include in requests as:")
        print(f"   Authorization: Bearer {args.api_key}")
        print()
    
    print("Press Ctrl+C to stop the server")
    print("=" * 50)
    
    try:
        asyncio.run(run_server(
            host=args.host,
            port=args.port,
            db_path=args.db_path,
            api_key=args.api_key,
            reload=args.dev
        ))
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()