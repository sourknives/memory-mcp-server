"""
Cortex MCP Client

A lightweight MCP client for connecting to remote Cortex MCP servers.
"""

__version__ = "0.1.0"
__author__ = "Cortex MCP Team"
__email__ = "developer@example.com"

from .client import RemoteMCPClient

__all__ = ["RemoteMCPClient"]