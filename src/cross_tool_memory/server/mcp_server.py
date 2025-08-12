"""
MCP Server implementation for cross-tool memory.

This module implements the Model Context Protocol (MCP) server that provides
intelligent memory storage and retrieval across AI development tools.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    ListToolsResult,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)

from ..config.database import DatabaseManager, DatabaseConfig
from ..repositories.conversation_repository import ConversationRepository
from ..repositories.project_repository import ProjectRepository
from ..repositories.preferences_repository import PreferencesRepository
from ..services.context_manager import ContextManager
from ..services.search_engine import SearchEngine
from ..services.embedding_service import EmbeddingService
from ..services.vector_store import VectorStore
from ..models.schemas import ConversationCreate, MemoryQuery, ProjectCreate
from ..utils.error_handling import graceful_degradation, error_recovery_manager
from ..utils.logging_config import get_component_logger, setup_default_logging
from ..utils.health_checks import get_health_checker

# Setup logging - only if not in MCP mode
import os
if not os.environ.get('DISABLE_LOGGING'):
    setup_default_logging()

logger = get_component_logger("mcp_server")


class MCPMemoryServer:
    """MCP Server for cross-tool memory management."""
    
    def __init__(self, db_path: str = "memory.db"):
        """
        Initialize the MCP memory server.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.server = Server("cross-tool-memory")
        
        # Initialize components
        self.db_manager: Optional[DatabaseManager] = None
        self.conversation_repo: Optional[ConversationRepository] = None
        self.project_repo: Optional[ProjectRepository] = None
        self.preferences_repo: Optional[PreferencesRepository] = None
        self.context_manager: Optional[ContextManager] = None
        self.search_engine: Optional[SearchEngine] = None
        
        # Register MCP handlers
        self._register_handlers()
    
    def _register_handlers(self) -> None:
        """Register MCP protocol handlers."""
        
        @self.server.list_tools()
        async def handle_list_tools():
            return [
                Tool(
                    name="store_context",
                    description="Store conversation context and content for future retrieval",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "content": {"type": "string", "description": "The conversation content to store"},
                            "tool_name": {"type": "string", "description": "Name of the AI tool"},
                            "metadata": {"type": "object", "description": "Optional metadata"},
                            "project_id": {"type": "string", "description": "Optional project ID"}
                        },
                        "required": ["content", "tool_name"]
                    }
                ),
                Tool(
                    name="search_memory",
                    description="Search stored memories",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "limit": {"type": "integer", "description": "Max results", "default": 10},
                            "project_id": {"type": "string", "description": "Optional project ID"}
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="get_conversation_history",
                    description="Get conversation history for a specific tool",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "tool_name": {"type": "string", "description": "Tool name"},
                            "hours": {"type": "integer", "description": "Hours to look back", "default": 24},
                            "limit": {"type": "integer", "description": "Max results", "default": 20}
                        },
                        "required": ["tool_name"]
                    }
                ),
                Tool(
                    name="browse_recent_memories",
                    description="Browse recent memories chronologically without needing to search",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "hours": {"type": "integer", "description": "Hours to look back", "default": 24},
                            "limit": {"type": "integer", "description": "Max results", "default": 10},
                            "tool_filter": {"type": "string", "description": "Optional tool name to filter by"}
                        }
                    }
                ),
                Tool(
                    name="find_related_context",
                    description="Find conversations related to a specific memory ID for context threading",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "memory_id": {"type": "string", "description": "ID of the memory to find related context for"},
                            "limit": {"type": "integer", "description": "Max related results", "default": 5}
                        },
                        "required": ["memory_id"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]):
            try:
                if name == "store_context":
                    content = arguments.get("content", "")
                    tool_name = arguments.get("tool_name", "").lower()
                    metadata = arguments.get("metadata", {})
                    
                    if not content or not tool_name:
                        return [{
                            "type": "text",
                            "text": "❌ Missing required parameters: content and tool_name"
                        }]
                    
                    # Store in database
                    try:
                        from ..models.schemas import ConversationCreate
                        conversation_data = ConversationCreate(
                            tool_name=tool_name,
                            content=content,
                            conversation_metadata=metadata,
                            project_id=arguments.get("project_id"),
                            tags=metadata.get("tags", [])
                        )
                        conversation = self.conversation_repo.create(conversation_data)
                        
                        # Add to search index
                        search_metadata = {
                            "conversation_id": conversation.id,
                            "tool_name": tool_name,
                            "project_id": conversation.project_id,
                            "timestamp": conversation.timestamp.isoformat(),
                            "tags": metadata.get("tags", [])
                        }
                        
                        await self.search_engine.add_document(
                            content=content,
                            metadata=search_metadata,
                            document_id=conversation.id
                        )
                        
                        return [{
                            "type": "text",
                            "text": f"✅ Context stored successfully! ID: {conversation.id}, Tool: {tool_name}, Content: {content[:100]}..."
                        }]
                    except Exception as e:
                        return [{
                            "type": "text",
                            "text": f"❌ Failed to store context: {str(e)}"
                        }]
                
                elif name == "search_memory":
                    query = arguments.get("query", "")
                    limit = arguments.get("limit", 10)
                    
                    if not query:
                        return [{
                            "type": "text",
                            "text": "❌ Missing required parameter: query"
                        }]
                    
                    # Search in database
                    try:
                        # Try search engine first
                        search_results = await self.search_engine.search(query=query, limit=limit)
                        
                        # If no results from search engine, try database keyword search
                        if not search_results:
                            conversations = self.conversation_repo.search_by_content(query, limit=limit)
                            if conversations:
                                results_text = f"🔍 Found {len(conversations)} results for '{query}' (database search):\\n\\n"
                                for i, conv in enumerate(conversations[:3], 1):
                                    # Show full content for better context preservation
                                    preview = conv.content
                                    
                                    # Add rich metadata
                                    metadata_info = ""
                                    if conv.conversation_metadata:
                                        metadata_info = f"\\n📋 Metadata: {json.dumps(conv.conversation_metadata, indent=2)}"
                                    
                                    tags_info = ""
                                    if conv.tags:
                                        tags_info = f"\\n🏷️  Tags: {', '.join(conv.tags_list)}"
                                    
                                    project_info = ""
                                    if conv.project_id:
                                        project_info = f"\\n📁 Project: {conv.project_id}"
                                    
                                    results_text += f"{i}. 🔗 ID: {conv.id}\\n📅 [{conv.tool_name}] {conv.timestamp.strftime('%Y-%m-%d %H:%M:%S')}{project_info}{tags_info}\\n\\n💬 Content:\\n{preview}{metadata_info}\\n\\n{'='*50}\\n\\n"
                                if len(conversations) > 3:
                                    results_text += f"... and {len(conversations) - 3} more results"
                            else:
                                results_text = f"🔍 No results found for '{query}'"
                        else:
                            results_text = f"🔍 Found {len(search_results)} results for '{query}' (search engine):\\n\\n"
                            for i, result in enumerate(search_results[:3], 1):
                                # Show full content for better context preservation
                                preview = result.content
                                
                                # Extract rich metadata
                                tool_name = result.metadata.get("tool_name", "unknown")
                                timestamp = result.metadata.get("timestamp", "unknown")
                                conv_id = result.metadata.get("conversation_id", "unknown")
                                project_id = result.metadata.get("project_id")
                                tags = result.metadata.get("tags", [])
                                
                                project_info = f"\\n📁 Project: {project_id}" if project_id else ""
                                tags_info = f"\\n🏷️  Tags: {', '.join(tags)}" if tags else ""
                                
                                results_text += f"{i}. 🔗 ID: {conv_id}\\n📅 [{tool_name}] {timestamp}{project_info}{tags_info}\\n\\n💬 Content:\\n{preview}\\n\\n{'='*50}\\n\\n"
                            if len(search_results) > 3:
                                results_text += f"... and {len(search_results) - 3} more results"
                        
                        return [{
                            "type": "text",
                            "text": results_text
                        }]
                    except Exception as e:
                        return [{
                            "type": "text",
                            "text": f"❌ Search failed: {str(e)}"
                        }]
                
                elif name == "browse_recent_memories":
                    hours = arguments.get("hours", 24)
                    limit = arguments.get("limit", 10)
                    tool_filter = arguments.get("tool_filter")
                    
                    try:
                        # Get recent conversations across all tools or filtered by tool
                        if tool_filter:
                            conversations = self.conversation_repo.get_recent_by_tool(
                                tool_name=tool_filter.lower(),
                                hours=hours,
                                limit=limit
                            )
                        else:
                            # Get recent conversations from all tools by using a broad search
                            from datetime import datetime, timedelta
                            cutoff_time = datetime.now() - timedelta(hours=hours)
                            
                            with self.conversation_repo.db_manager.get_session() as session:
                                from ..models.database import Conversation
                                conversations = session.query(Conversation).filter(
                                    Conversation.timestamp >= cutoff_time
                                ).order_by(Conversation.timestamp.desc()).limit(limit).all()
                        
                        if conversations:
                            browse_text = f"📚 Recent memories (last {hours}h):\\n\\n"
                            for i, conv in enumerate(conversations, 1):
                                # Show full content with rich context
                                preview = conv.content
                                
                                metadata_info = ""
                                if conv.conversation_metadata:
                                    metadata_info = f"\\n📋 Metadata: {json.dumps(conv.conversation_metadata, indent=2)}"
                                
                                tags_info = ""
                                if conv.tags:
                                    tags_info = f"\\n🏷️  Tags: {', '.join(conv.tags_list)}"
                                
                                project_info = ""
                                if conv.project_id:
                                    project_info = f"\\n📁 Project: {conv.project_id}"
                                
                                browse_text += f"{i}. 🔗 ID: {conv.id}\\n📅 [{conv.tool_name}] {conv.timestamp.strftime('%Y-%m-%d %H:%M:%S')}{project_info}{tags_info}\\n\\n💬 Content:\\n{preview}{metadata_info}\\n\\n{'='*50}\\n\\n"
                        else:
                            browse_text = f"📚 No recent memories found in the last {hours} hours"
                        
                        return [{
                            "type": "text",
                            "text": browse_text
                        }]
                    except Exception as e:
                        return [{
                            "type": "text",
                            "text": f"❌ Failed to browse memories: {str(e)}"
                        }]
                
                elif name == "find_related_context":
                    memory_id = arguments.get("memory_id", "")
                    limit = arguments.get("limit", 5)
                    
                    if not memory_id:
                        return [{
                            "type": "text",
                            "text": "❌ Missing required parameter: memory_id"
                        }]
                    
                    try:
                        # Get the original conversation
                        original_conv = self.conversation_repo.get_by_id(memory_id)
                        if not original_conv:
                            return [{
                                "type": "text",
                                "text": f"❌ Memory with ID {memory_id} not found"
                            }]
                        
                        # Find related conversations using content similarity
                        related_results = await self.search_engine.search(
                            query=original_conv.content[:200],  # Use first 200 chars as query
                            limit=limit + 1  # +1 to account for the original
                        )
                        
                        # Filter out the original conversation
                        related_results = [r for r in related_results if r.metadata.get("conversation_id") != memory_id][:limit]
                        
                        if related_results:
                            related_text = f"🔗 Found {len(related_results)} related conversations to memory {memory_id}:\\n\\n"
                            related_text += f"📌 Original Memory:\\n🔗 ID: {original_conv.id}\\n📅 [{original_conv.tool_name}] {original_conv.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\\n💬 {original_conv.content[:200]}...\\n\\n{'='*50}\\n\\n"
                            
                            for i, result in enumerate(related_results, 1):
                                conv_id = result.metadata.get("conversation_id", "unknown")
                                tool_name = result.metadata.get("tool_name", "unknown")
                                timestamp = result.metadata.get("timestamp", "unknown")
                                
                                related_text += f"{i}. 🔗 ID: {conv_id}\\n📅 [{tool_name}] {timestamp}\\n💬 Content:\\n{result.content}\\n\\n{'='*50}\\n\\n"
                        else:
                            related_text = f"🔗 No related conversations found for memory {memory_id}"
                        
                        return [{
                            "type": "text",
                            "text": related_text
                        }]
                    except Exception as e:
                        return [{
                            "type": "text",
                            "text": f"❌ Failed to find related context: {str(e)}"
                        }]
                
                elif name == "get_conversation_history":
                    tool_name = arguments.get("tool_name", "")
                    hours = arguments.get("hours", 24)
                    limit = arguments.get("limit", 20)
                    
                    if not tool_name:
                        return [{
                            "type": "text",
                            "text": "❌ Missing required parameter: tool_name"
                        }]
                    
                    # Get history from database
                    try:
                        conversations = self.conversation_repo.get_recent_by_tool(
                            tool_name=tool_name.lower(),
                            hours=hours,
                            limit=limit
                        )
                        
                        if conversations:
                            history_text = f"📜 Found {len(conversations)} conversations for {tool_name} (last {hours}h):\\n\\n"
                            for i, conv in enumerate(conversations[:3], 1):
                                # Show full content for complete context
                                preview = conv.content
                                
                                # Add rich metadata for context
                                metadata_info = ""
                                if conv.conversation_metadata:
                                    metadata_info = f"\\n📋 Metadata: {json.dumps(conv.conversation_metadata, indent=2)}"
                                
                                tags_info = ""
                                if conv.tags:
                                    tags_info = f"\\n🏷️  Tags: {', '.join(conv.tags_list)}"
                                
                                project_info = ""
                                if conv.project_id:
                                    project_info = f"\\n📁 Project: {conv.project_id}"
                                
                                history_text += f"{i}. 🔗 ID: {conv.id}\\n📅 {conv.timestamp.strftime('%Y-%m-%d %H:%M:%S')}{project_info}{tags_info}\\n\\n💬 Content:\\n{preview}{metadata_info}\\n\\n{'='*50}\\n\\n"
                            if len(conversations) > 3:
                                history_text += f"... and {len(conversations) - 3} more conversations"
                        else:
                            history_text = f"📜 No conversations found for {tool_name} in the last {hours} hours"
                        
                        return [{
                            "type": "text",
                            "text": history_text
                        }]
                    except Exception as e:
                        return [{
                            "type": "text",
                            "text": f"❌ Failed to get history: {str(e)}"
                        }]
                
                else:
                    return [{
                        "type": "text",
                        "text": f"❌ Unknown tool: {name}"
                    }]
                    
            except Exception as e:
                return [{
                    "type": "text",
                    "text": f"❌ Error executing {name}: {str(e)}"
                }]
        
        @self.server.list_prompts()
        async def handle_list_prompts():
            return []  # No prompts implemented yet
        
        @self.server.list_resources()
        async def handle_list_resources():
            return []  # No resources implemented yet
    
    async def _handle_call_tool(self, name: str, arguments: Dict[str, Any]) -> CallToolResult:
        """Handle MCP tool calls with error handling."""
        try:
            if name == "store_context":
                return await self._handle_store_context(arguments)
            elif name == "search_memory":
                return await self._handle_retrieve_context(arguments)
            elif name == "get_project_context":
                return await self._handle_get_project_context(arguments)
            elif name == "update_preferences":
                return await self._handle_update_preferences(arguments)
            elif name == "get_conversation_history":
                return await self._handle_get_conversation_history(arguments)
            elif name == "health_check":
                return await self._handle_health_check(arguments)
            else:
                return CallToolResult(
                    content=[TextContent(
                        type="text",
                        text=f"Unknown tool: {name}"
                    )],
                    isError=True
                )
        except Exception as e:
            logger.error(f"Error handling tool call {name}: {e}")
            error_recovery_manager.record_error("mcp_server", e)
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Error executing {name}: {str(e)}"
                )],
                isError=True
            )
    
    async def initialize(self) -> None:
        """Initialize the server components."""
        try:
            # Initialize database
            db_config = DatabaseConfig(database_path=self.db_path)
            self.db_manager = DatabaseManager(db_config)
            self.db_manager.initialize_database()
            
            # Initialize repositories
            self.conversation_repo = ConversationRepository(self.db_manager)
            self.project_repo = ProjectRepository(self.db_manager)
            self.preferences_repo = PreferencesRepository(self.db_manager)
            
            # Initialize services
            self.context_manager = ContextManager(
                self.db_manager,
                self.conversation_repo,
                self.project_repo
            )
            
            # Initialize search engine with embedding service
            try:
                embedding_service = EmbeddingService()
                await embedding_service.initialize()
                vector_store = VectorStore(dimension=384)  # all-MiniLM-L6-v2 dimension
                await vector_store.initialize()
                
                self.search_engine = SearchEngine(
                    embedding_service=embedding_service,
                    vector_store=vector_store
                )
                await self.search_engine.initialize()
                
                logger.info("Search engine initialized with embeddings")
            except Exception as e:
                logger.warning(f"Failed to initialize search engine with embeddings: {e}")
                # Fallback to keyword-only search
                vector_store = VectorStore(dimension=384)
                await vector_store.initialize()
                
                self.search_engine = SearchEngine(
                    embedding_service=None,
                    vector_store=vector_store
                )
                await self.search_engine.initialize()
                
                logger.info("Search engine initialized in keyword-only mode")
            
            logger.info("MCP Memory Server initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP Memory Server: {e}")
            raise
    
    async def _handle_store_context(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Handle store_context tool call."""
        content = arguments.get("content", "")
        tool_name = arguments.get("tool_name", "").lower()
        metadata = arguments.get("metadata", {})
        project_id = arguments.get("project_id")
        
        if not content or not tool_name:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text="Missing required parameters: content and tool_name"
                )],
                isError=True
            )
        
        try:
            # Extract tags from metadata
            tags = metadata.get("tags", [])
            
            # Create conversation
            conversation_data = ConversationCreate(
                tool_name=tool_name,
                content=content,
                conversation_metadata=metadata,
                project_id=project_id,
                tags=tags
            )
            
            conversation = self.conversation_repo.create(conversation_data)
            
            # Process context (project detection, categorization, linking)
            context_results = await self.context_manager.process_conversation_context(conversation)
            
            # Add to search index
            search_metadata = {
                "conversation_id": conversation.id,
                "tool_name": tool_name,
                "project_id": conversation.project_id,
                "timestamp": conversation.timestamp.isoformat(),
                "tags": tags
            }
            
            await self.search_engine.add_document(
                content=content,
                metadata=search_metadata,
                document_id=conversation.id
            )
            
            # Prepare response
            response_data = {
                "conversation_id": conversation.id,
                "stored_at": conversation.timestamp.isoformat(),
                "project_detected": context_results.get("project_detected", False),
                "project_id": context_results.get("project_id"),
                "categories": context_results.get("categories", {}),
                "related_conversations": len(context_results.get("related_conversations", [])),
                "context_links_created": context_results.get("context_links_created", 0)
            }
            
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Context stored successfully:\n{json.dumps(response_data, indent=2)}"
                )]
            )
            
        except Exception as e:
            logger.error(f"Error storing context: {e}")
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Failed to store context: {str(e)}"
                )],
                isError=True
            )
    
    async def _handle_retrieve_context(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Handle retrieve_context tool call."""
        query = arguments.get("query", "")
        project_id = arguments.get("project_id")
        tool_name = arguments.get("tool_name")
        limit = arguments.get("limit", 10)
        search_type = arguments.get("search_type", "hybrid")
        
        if not query:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text="Missing required parameter: query"
                )],
                isError=True
            )
        
        try:
            # Build search filters
            filters = {}
            if project_id:
                filters["project_id"] = project_id
            if tool_name:
                filters["tool_name"] = tool_name.lower()
            
            # Perform search
            search_results = await self.search_engine.search(
                query=query,
                limit=limit,
                filters=filters if filters else None,
                search_type=search_type
            )
            
            # Format results
            formatted_results = []
            for result in search_results:
                conversation_id = result.metadata.get("conversation_id")
                conversation = self.conversation_repo.get_by_id(conversation_id) if conversation_id else None
                
                result_data = {
                    "conversation_id": conversation_id,
                    "content": result.content[:500] + "..." if len(result.content) > 500 else result.content,
                    "tool_name": result.metadata.get("tool_name"),
                    "project_id": result.metadata.get("project_id"),
                    "timestamp": result.metadata.get("timestamp"),
                    "tags": result.metadata.get("tags", []),
                    "relevance_score": round(result.combined_score, 3),
                    "scores": {
                        "semantic": round(result.semantic_score, 3),
                        "keyword": round(result.keyword_score, 3),
                        "recency": round(result.recency_score, 3)
                    }
                }
                
                if conversation and conversation.conversation_metadata:
                    result_data["metadata"] = conversation.conversation_metadata
                
                formatted_results.append(result_data)
            
            response_data = {
                "query": query,
                "search_type": search_type,
                "filters": filters,
                "total_results": len(formatted_results),
                "results": formatted_results
            }
            
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Retrieved {len(formatted_results)} relevant contexts:\n{json.dumps(response_data, indent=2)}"
                )]
            )
            
        except Exception as e:
            logger.error(f"Error retrieving context: {e}")
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Failed to retrieve context: {str(e)}"
                )],
                isError=True
            )
    
    async def _handle_get_project_context(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Handle get_project_context tool call."""
        project_id = arguments.get("project_id", "")
        limit = arguments.get("limit", 50)
        include_stats = arguments.get("include_stats", True)
        
        if not project_id:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text="Missing required parameter: project_id"
                )],
                isError=True
            )
        
        try:
            # Get project information
            project = self.project_repo.get_by_id(project_id)
            if not project:
                return CallToolResult(
                    content=[TextContent(
                        type="text",
                        text=f"Project not found: {project_id}"
                    )],
                    isError=True
                )
            
            # Get project conversations
            conversations = self.conversation_repo.get_by_project(project_id, limit=limit)
            
            # Format conversations
            formatted_conversations = []
            for conv in conversations:
                conv_data = {
                    "conversation_id": conv.id,
                    "tool_name": conv.tool_name,
                    "timestamp": conv.timestamp.isoformat(),
                    "content": conv.content[:300] + "..." if len(conv.content) > 300 else conv.content,
                    "tags": conv.tags_list if conv.tags else []
                }
                
                if conv.conversation_metadata:
                    conv_data["metadata"] = conv.conversation_metadata
                
                formatted_conversations.append(conv_data)
            
            # Prepare response
            response_data = {
                "project": {
                    "id": project.id,
                    "name": project.name,
                    "description": project.description,
                    "path": project.path,
                    "technologies": project.technologies_list if project.technologies else [],
                    "created_at": project.created_at.isoformat(),
                    "last_accessed": project.last_accessed.isoformat()
                },
                "conversations": formatted_conversations,
                "total_conversations": len(formatted_conversations)
            }
            
            # Add statistics if requested
            if include_stats:
                total_conversations = self.conversation_repo.count_by_project(project_id)
                response_data["statistics"] = {
                    "total_conversations": total_conversations,
                    "conversations_returned": len(formatted_conversations),
                    "tools_used": list(set(conv["tool_name"] for conv in formatted_conversations))
                }
            
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Project context for '{project.name}':\n{json.dumps(response_data, indent=2)}"
                )]
            )
            
        except Exception as e:
            logger.error(f"Error getting project context: {e}")
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Failed to get project context: {str(e)}"
                )],
                isError=True
            )
    
    async def _handle_update_preferences(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Handle update_preferences tool call."""
        key = arguments.get("key", "")
        value = arguments.get("value", "")
        category = arguments.get("category")
        
        if not key or not value:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text="Missing required parameters: key and value"
                )],
                isError=True
            )
        
        try:
            # Update or create preference
            from ..models.schemas import PreferenceCreate, PreferenceUpdate
            
            existing_pref = self.preferences_repo.get_by_key(key)
            if existing_pref:
                # Update existing preference
                update_data = PreferenceUpdate(value=value, category=category)
                preference = self.preferences_repo.update(key, update_data)
            else:
                # Create new preference
                create_data = PreferenceCreate(key=key, value=value, category=category)
                preference = self.preferences_repo.create(create_data)
            
            response_data = {
                "key": preference.key,
                "value": preference.value,
                "category": preference.category,
                "updated_at": preference.updated_at.isoformat(),
                "action": "updated" if existing_pref else "created"
            }
            
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Preference {response_data['action']} successfully:\n{json.dumps(response_data, indent=2)}"
                )]
            )
            
        except Exception as e:
            logger.error(f"Error updating preferences: {e}")
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Failed to update preferences: {str(e)}"
                )],
                isError=True
            )
    
    async def _handle_get_conversation_history(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Handle get_conversation_history tool call."""
        tool_name = arguments.get("tool_name", "")
        hours = arguments.get("hours", 24)
        limit = arguments.get("limit", 20)
        
        if not tool_name:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text="Missing required parameter: tool_name"
                )],
                isError=True
            )
        
        try:
            # Get recent conversations
            conversations = self.conversation_repo.get_recent_by_tool(
                tool_name=tool_name.lower(),
                hours=hours,
                limit=limit
            )
            
            # Format conversations
            formatted_conversations = []
            for conv in conversations:
                conv_data = {
                    "conversation_id": conv.id,
                    "timestamp": conv.timestamp.isoformat(),
                    "project_id": conv.project_id,
                    "content": conv.content[:200] + "..." if len(conv.content) > 200 else conv.content,
                    "tags": conv.tags_list if conv.tags else []
                }
                
                if conv.conversation_metadata:
                    conv_data["metadata"] = conv.conversation_metadata
                
                formatted_conversations.append(conv_data)
            
            response_data = {
                "tool_name": tool_name,
                "time_range_hours": hours,
                "total_conversations": len(formatted_conversations),
                "conversations": formatted_conversations
            }
            
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Conversation history for {tool_name} (last {hours}h):\n{json.dumps(response_data, indent=2)}"
                )]
            )
            
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Failed to get conversation history: {str(e)}"
                )],
                isError=True
            )
    
    async def _handle_health_check(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Handle health_check tool call."""
        component = arguments.get("component")
        detailed = arguments.get("detailed", False)
        
        try:
            # Get health checker
            health_checker = get_health_checker(
                db_manager=self.db_manager,
                search_engine=self.search_engine,
                embedding_service=getattr(self.search_engine, 'embedding_service', None) if self.search_engine else None,
                vector_store=getattr(self.search_engine, 'vector_store', None) if self.search_engine else None
            )
            
            if component:
                # Check specific component
                component_health = await health_checker.check_component_health(component)
                
                response_data = {
                    "component": component,
                    "status": component_health.status.value,
                    "message": component_health.message,
                    "response_time_ms": component_health.response_time_ms,
                    "error_count": component_health.error_count,
                    "last_check": component_health.last_check.isoformat() if component_health.last_check else None
                }
                
                if detailed and component_health.details:
                    response_data["details"] = component_health.details
                
                return CallToolResult(
                    content=[TextContent(
                        type="text",
                        text=f"Health check for {component}:\n{json.dumps(response_data, indent=2)}"
                    )]
                )
            
            else:
                # Check overall system health
                system_health = await health_checker.check_system_health()
                
                if detailed:
                    response_data = system_health.to_dict()
                else:
                    response_data = {
                        "overall_status": system_health.status.value,
                        "timestamp": system_health.timestamp.isoformat(),
                        "uptime_seconds": system_health.uptime_seconds,
                        "total_errors": system_health.total_errors,
                        "components": [
                            {
                                "name": comp.name,
                                "status": comp.status.value,
                                "message": comp.message
                            }
                            for comp in system_health.components
                        ]
                    }
                
                return CallToolResult(
                    content=[TextContent(
                        type="text",
                        text=f"System health check:\n{json.dumps(response_data, indent=2)}"
                    )]
                )
                
        except Exception as e:
            logger.error(f"Error performing health check: {e}")
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Failed to perform health check: {str(e)}"
                )],
                isError=True
            )
    
    async def run(self) -> None:
        """Run the MCP server."""
        try:
            await self.initialize()
            
            # Run the server using stdio transport
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="cross-tool-memory",
                        server_version="0.1.0",
                        capabilities={}
                    )
                )
        except Exception as e:
            logger.error(f"Error running MCP server: {e}")
            raise
    
    async def cleanup(self) -> None:
        """Clean up server resources."""
        try:
            if self.search_engine:
                await self.search_engine.cleanup()
            
            if self.db_manager:
                self.db_manager.close()
            
            logger.info("MCP Memory Server cleaned up")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


async def main():
    """Main entry point for the MCP server."""
    # Disable all logging to avoid interfering with MCP JSON protocol
    import os
    os.environ['DISABLE_LOGGING'] = '1'
    os.environ['NO_COLOR'] = '1'
    
    # Configure logging for MCP mode (no colors, minimal output)
    logging.getLogger().setLevel(logging.CRITICAL)
    logging.getLogger('cross_tool_memory').setLevel(logging.CRITICAL)
    logging.getLogger('src.cross_tool_memory').setLevel(logging.CRITICAL)
    logging.getLogger('uvicorn').setLevel(logging.CRITICAL)
    logging.getLogger('sqlalchemy').setLevel(logging.CRITICAL)
    
    # Remove all existing handlers to prevent any output
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Get database path from environment variable or use default
    db_path = os.getenv("MEMORY_DB_PATH")
    if not db_path:
        # Default to user's home directory
        data_dir = Path.home() / ".cross_tool_memory" / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = str(data_dir / "memory.db")
    else:
        # Ensure the directory exists for the specified path
        try:
            db_dir = Path(db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)
            # Test write permissions by creating a temporary file
            test_file = db_dir / ".test_write"
            test_file.touch()
            test_file.unlink()
        except Exception as e:
            # Fallback to home directory if specified path is not writable
            print(f"Warning: Cannot write to {db_path}, using fallback location: {e}", file=sys.stderr)
            data_dir = Path.home() / ".cross_tool_memory" / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "memory.db")
    
    server = MCPMemoryServer(db_path=db_path)
    
    try:
        await server.run()
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise
    finally:
        await server.cleanup()


if __name__ == "__main__":
    asyncio.run(main())