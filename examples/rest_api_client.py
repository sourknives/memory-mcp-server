#!/usr/bin/env python3
"""
Example REST API client for the Cross-Tool Memory server.

This script demonstrates how to interact with the REST API endpoints
for tools that don't support the Model Context Protocol.
"""

import asyncio
import json
import os
from typing import Dict, Any, Optional

import httpx


class MemoryAPIClient:
    """Client for the Cross-Tool Memory REST API."""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000", api_key: Optional[str] = None):
        """
        Initialize the API client.
        
        Args:
            base_url: Base URL of the memory server
            api_key: Optional API key for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.headers = {"Content-Type": "application/json"}
        
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
    
    async def health_check(self) -> Dict[str, Any]:
        """Check server health status."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/stats", headers=self.headers)
            response.raise_for_status()
            return response.json()
    
    async def store_context(
        self,
        content: str,
        tool_name: str,
        metadata: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Store conversation context."""
        data = {
            "content": content,
            "tool_name": tool_name,
            "metadata": metadata,
            "project_id": project_id
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/context",
                headers=self.headers,
                json=data
            )
            response.raise_for_status()
            return response.json()
    
    async def retrieve_context(
        self,
        query: str,
        project_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        limit: int = 10,
        search_type: str = "hybrid"
    ) -> Dict[str, Any]:
        """Search and retrieve relevant context."""
        data = {
            "query": query,
            "project_id": project_id,
            "tool_name": tool_name,
            "limit": limit,
            "search_type": search_type
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/context/search",
                headers=self.headers,
                json=data
            )
            response.raise_for_status()
            return response.json()
    
    async def get_project_context(
        self,
        project_id: str,
        limit: int = 50,
        include_stats: bool = True
    ) -> Dict[str, Any]:
        """Get all context for a specific project."""
        params = {
            "limit": limit,
            "include_stats": include_stats
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/projects/{project_id}/context",
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            return response.json()
    
    async def get_conversation_history(
        self,
        tool_name: str,
        hours: int = 24,
        limit: int = 20
    ) -> Dict[str, Any]:
        """Get conversation history for a tool."""
        data = {
            "tool_name": tool_name,
            "hours": hours,
            "limit": limit
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/history",
                headers=self.headers,
                json=data
            )
            response.raise_for_status()
            return response.json()
    
    async def create_project(
        self,
        name: str,
        path: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new project."""
        data = {
            "name": name,
            "path": path,
            "description": description
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/projects",
                headers=self.headers,
                json=data
            )
            response.raise_for_status()
            return response.json()
    
    async def list_projects(self, limit: int = 50) -> Dict[str, Any]:
        """List all projects."""
        params = {"limit": limit}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/projects",
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            return response.json()
    
    async def update_preference(
        self,
        key: str,
        value: Any,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create or update a preference."""
        data = {
            "key": key,
            "value": value,
            "category": category
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/preferences",
                headers=self.headers,
                json=data
            )
            response.raise_for_status()
            return response.json()
    
    async def get_preferences(self, category: Optional[str] = None) -> Dict[str, Any]:
        """List all preferences."""
        params = {}
        if category:
            params["category"] = category
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/preferences",
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            return response.json()


async def demo():
    """Demonstrate the REST API client."""
    # Initialize client
    api_key = os.getenv("API_KEY")  # Optional
    client = MemoryAPIClient(api_key=api_key)
    
    try:
        print("=== Cross-Tool Memory REST API Demo ===\n")
        
        # Health check
        print("1. Checking server health...")
        health = await client.health_check()
        print(f"   Status: {health['status']}")
        print(f"   Database connected: {health['database_connected']}")
        print(f"   Vector store ready: {health['vector_store_ready']}")
        print()
        
        # Create a project
        print("2. Creating a test project...")
        project = await client.create_project(
            name="Demo Project",
            description="A test project for API demonstration",
            path="/path/to/demo/project"
        )
        project_id = project["id"]
        print(f"   Created project: {project['name']} (ID: {project_id})")
        print()
        
        # Store some context
        print("3. Storing conversation context...")
        context_result = await client.store_context(
            content="I'm working on implementing a REST API for the memory server. The API should mirror the MCP functionality and provide proper authentication.",
            tool_name="cursor",
            metadata={
                "user_query": "How do I implement REST API authentication?",
                "ai_response": "You can use FastAPI's HTTPBearer for token-based authentication...",
                "tags": ["api", "authentication", "fastapi"]
            },
            project_id=project_id
        )
        conversation_id = context_result["conversation_id"]
        print(f"   Stored context: {conversation_id}")
        print(f"   Project detected: {context_result['project_detected']}")
        print()
        
        # Store another context
        print("4. Storing more context...")
        await client.store_context(
            content="The FastAPI server should include CORS middleware for cross-origin requests and proper error handling with structured error responses.",
            tool_name="claude",
            metadata={
                "user_query": "What middleware should I add to FastAPI?",
                "ai_response": "For a REST API, you should add CORS middleware...",
                "tags": ["fastapi", "middleware", "cors"]
            },
            project_id=project_id
        )
        print("   Stored additional context")
        print()
        
        # Search for context
        print("5. Searching for relevant context...")
        search_results = await client.retrieve_context(
            query="FastAPI authentication middleware",
            project_id=project_id,
            limit=5
        )
        print(f"   Found {search_results['total_results']} relevant contexts:")
        for i, result in enumerate(search_results['results'][:2], 1):
            print(f"   {i}. Score: {result['relevance_score']}")
            print(f"      Tool: {result['tool_name']}")
            print(f"      Content: {result['content'][:100]}...")
            print()
        
        # Get project context
        print("6. Getting project context...")
        project_context = await client.get_project_context(project_id)
        print(f"   Project: {project_context['project']['name']}")
        print(f"   Total conversations: {project_context['total_conversations']}")
        if project_context.get('statistics'):
            print(f"   Tools used: {project_context['statistics']['tools_used']}")
        print()
        
        # Get conversation history
        print("7. Getting conversation history...")
        history = await client.get_conversation_history("cursor", hours=24)
        print(f"   Found {history['total_conversations']} conversations for cursor in last 24h")
        print()
        
        # Set preferences
        print("8. Setting user preferences...")
        await client.update_preference(
            key="preferred_search_type",
            value="hybrid",
            category="search"
        )
        await client.update_preference(
            key="default_limit",
            value=20,
            category="general"
        )
        print("   Preferences updated")
        print()
        
        # Get preferences
        print("9. Getting preferences...")
        preferences = await client.get_preferences()
        print(f"   Found {len(preferences)} preferences:")
        for pref in preferences:
            print(f"   - {pref['key']}: {pref['value']} ({pref.get('category', 'general')})")
        print()
        
        # Get database stats
        print("10. Getting database statistics...")
        stats = await client.get_stats()
        print(f"    Total conversations: {stats['total_conversations']}")
        print(f"    Total projects: {stats['total_projects']}")
        print(f"    Total preferences: {stats['total_preferences']}")
        print(f"    Database size: {stats['database_size_mb']} MB")
        print()
        
        print("=== Demo completed successfully! ===")
        
    except httpx.HTTPStatusError as e:
        print(f"HTTP Error: {e.response.status_code}")
        print(f"Response: {e.response.text}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(demo())