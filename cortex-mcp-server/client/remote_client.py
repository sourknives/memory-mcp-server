#!/usr/bin/env python3
"""
Remote MCP Client for Cortex MCP Server.

This module provides a bridge between MCP hosts and remote Cortex MCP servers,
translating MCP protocol calls to HTTP API calls.
"""

import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional
import httpx
from mcp import Server
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions
from mcp.types import (
    Resource,
    Tool,
    Prompt,
    TextContent,
    ImageContent,
    EmbeddedResource,
)


class RemoteMCPClient:
    """MCP Server that proxies requests to a remote Cortex MCP server via HTTP."""
    
    def __init__(self):
        self.server = Server("cortex-mcp-remote")
        self.base_url = os.getenv("CORTEX_MCP_SERVER_URL", "http://localhost:8000")
        self.api_key = os.getenv("CORTEX_MCP_API_KEY")
        self.timeout = int(os.getenv("CORTEX_MCP_TIMEOUT", "30"))
        self.use_tls = os.getenv("CORTEX_MCP_USE_TLS", "false").lower() == "true"
        self.verify_ssl = os.getenv("CORTEX_MCP_VERIFY_SSL", "true").lower() == "true"
        
        # Setup HTTP client
        self.http_client = httpx.AsyncClient(
            timeout=self.timeout,
            verify=self.verify_ssl if self.use_tls else True
        )
        
        self._register_handlers()
    
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for API requests."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    async def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make HTTP request to remote server."""
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        try:
            if method.upper() == "GET":
                response = await self.http_client.get(url, headers=self._get_headers())
            elif method.upper() == "POST":
                response = await self.http_client.post(
                    url, 
                    json=data or {}, 
                    headers=self._get_headers()
                )
            elif method.upper() == "PUT":
                response = await self.http_client.put(
                    url, 
                    json=data or {}, 
                    headers=self._get_headers()
                )
            elif method.upper() == "DELETE":
                response = await self.http_client.delete(url, headers=self._get_headers())
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
        
        except httpx.HTTPError as e:
            raise Exception(f"HTTP request failed: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON response: {e}")
    
    def _register_handlers(self):
        """Register MCP handlers that proxy to remote server."""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available tools from remote server."""
            try:
                response = await self._make_request("GET", "/api/v1/tools")
                tools = []
                for tool_data in response.get("tools", []):
                    tools.append(Tool(
                        name=tool_data["name"],
                        description=tool_data["description"],
                        inputSchema=tool_data.get("inputSchema", {})
                    ))
                return tools
            except Exception as e:
                # Return basic tools if remote fails
                return [
                    Tool(
                        name="store_memory",
                        description="Store a memory in the remote Cortex MCP server",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "content": {"type": "string", "description": "Memory content"},
                                "category": {"type": "string", "description": "Memory category"},
                                "tags": {"type": "array", "items": {"type": "string"}}
                            },
                            "required": ["content"]
                        }
                    ),
                    Tool(
                        name="retrieve_memories",
                        description="Retrieve memories from the remote Cortex MCP server",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Search query"},
                                "category": {"type": "string", "description": "Filter by category"},
                                "limit": {"type": "integer", "description": "Maximum results"}
                            }
                        }
                    ),
                    Tool(
                        name="search_memories",
                        description="Search memories in the remote Cortex MCP server",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Search query"},
                                "semantic": {"type": "boolean", "description": "Use semantic search"}
                            },
                            "required": ["query"]
                        }
                    )
                ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Call tool on remote server."""
            try:
                response = await self._make_request("POST", f"/api/v1/tools/{name}", {
                    "arguments": arguments
                })
                
                result = response.get("result", "")
                if isinstance(result, dict):
                    result = json.dumps(result, indent=2)
                elif not isinstance(result, str):
                    result = str(result)
                
                return [TextContent(type="text", text=result)]
            
            except Exception as e:
                error_msg = f"Error calling remote tool '{name}': {str(e)}"
                return [TextContent(type="text", text=error_msg)]
        
        @self.server.list_resources()
        async def handle_list_resources() -> List[Resource]:
            """List available resources from remote server."""
            try:
                response = await self._make_request("GET", "/api/v1/resources")
                resources = []
                for resource_data in response.get("resources", []):
                    resources.append(Resource(
                        uri=resource_data["uri"],
                        name=resource_data["name"],
                        description=resource_data.get("description", ""),
                        mimeType=resource_data.get("mimeType")
                    ))
                return resources
            except Exception:
                return []
        
        @self.server.read_resource()
        async def handle_read_resource(uri: str) -> str:
            """Read resource from remote server."""
            try:
                response = await self._make_request("GET", f"/api/v1/resources", {
                    "uri": uri
                })
                return response.get("content", "")
            except Exception as e:
                return f"Error reading resource: {str(e)}"
    
    async def run(self):
        """Run the remote MCP client."""
        from mcp.server.stdio import stdio_server
        
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="cortex-mcp-remote",
                    server_version="0.1.0",
                    capabilities={}
                )
            )


async def main():
    """Main entry point for remote MCP client."""
    client = RemoteMCPClient()
    await client.run()


if __name__ == "__main__":
    asyncio.run(main())