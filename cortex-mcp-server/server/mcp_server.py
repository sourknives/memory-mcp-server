"""
MCP Server implementation for cortex mcp.

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

from config.database import DatabaseManager, DatabaseConfig
from repositories.conversation_repository import ConversationRepository
from repositories.project_repository import ProjectRepository
from repositories.preferences_repository import PreferencesRepository
from services.context_manager import ContextManager
from services.search_engine import SearchEngine
from services.embedding_service import EmbeddingService
from services.vector_store import VectorStore
from services.storage_analyzer import StorageAnalyzer
from services.duplicate_detector import DuplicateDetector
from services.session_analyzer import SessionAnalyzer
from models.schemas import ConversationCreate, MemoryQuery, ProjectCreate
from utils.error_handling import graceful_degradation, error_recovery_manager
from utils.logging_config import get_component_logger, setup_default_logging
from utils.health_checks import get_health_checker

# Setup logging - only if not in MCP mode
import os
if not os.environ.get('DISABLE_LOGGING'):
    setup_default_logging()

logger = get_component_logger("mcp_server")


class StorageSuggestionManager:
    """Manages pending storage suggestions for user approval/rejection."""
    
    def __init__(self):
        """Initialize the suggestion manager."""
        self._pending_suggestions: Dict[str, Dict[str, Any]] = {}
        self._suggestion_counter = 0
    
    def create_suggestion(
        self, 
        user_message: str, 
        ai_response: str, 
        analysis_result: Dict[str, Any],
        tool_name: str = ""
    ) -> str:
        """
        Create a new storage suggestion.
        
        Args:
            user_message: The user's message
            ai_response: The AI's response
            analysis_result: Result from storage analyzer
            tool_name: Name of the AI tool
            
        Returns:
            Suggestion ID for tracking
        """
        self._suggestion_counter += 1
        suggestion_id = f"suggestion_{self._suggestion_counter}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        suggestion = {
            'id': suggestion_id,
            'user_message': user_message,
            'ai_response': ai_response,
            'analysis_result': analysis_result,
            'tool_name': tool_name,
            'created_at': datetime.now().isoformat(),
            'status': 'pending'
        }
        
        self._pending_suggestions[suggestion_id] = suggestion
        return suggestion_id
    
    def get_suggestion(self, suggestion_id: str) -> Optional[Dict[str, Any]]:
        """Get a suggestion by ID."""
        return self._pending_suggestions.get(suggestion_id)
    
    def approve_suggestion(self, suggestion_id: str) -> Optional[Dict[str, Any]]:
        """Mark a suggestion as approved and return it."""
        suggestion = self._pending_suggestions.get(suggestion_id)
        if suggestion:
            suggestion['status'] = 'approved'
            suggestion['approved_at'] = datetime.now().isoformat()
        return suggestion
    
    def reject_suggestion(self, suggestion_id: str, reason: str = "") -> Optional[Dict[str, Any]]:
        """Mark a suggestion as rejected and return it."""
        suggestion = self._pending_suggestions.get(suggestion_id)
        if suggestion:
            suggestion['status'] = 'rejected'
            suggestion['rejected_at'] = datetime.now().isoformat()
            suggestion['rejection_reason'] = reason
        return suggestion
    
    def cleanup_old_suggestions(self, max_age_hours: int = 24) -> None:
        """Remove old suggestions to prevent memory buildup."""
        from datetime import datetime, timedelta
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        to_remove = []
        for suggestion_id, suggestion in self._pending_suggestions.items():
            created_at = datetime.fromisoformat(suggestion['created_at'])
            if created_at < cutoff_time:
                to_remove.append(suggestion_id)
        
        for suggestion_id in to_remove:
            del self._pending_suggestions[suggestion_id]
    
    def get_pending_count(self) -> int:
        """Get count of pending suggestions."""
        return len([s for s in self._pending_suggestions.values() if s['status'] == 'pending'])


class MCPMemoryServer:
    """MCP Server for cortex mcp memory management."""
    
    def __init__(self, db_path: str = "memory.db"):
        """
        Initialize the MCP memory server.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.server = Server("cortex-mcp")
        
        # Initialize components
        self.db_manager: Optional[DatabaseManager] = None
        self.conversation_repo: Optional[ConversationRepository] = None
        self.project_repo: Optional[ProjectRepository] = None
        self.preferences_repo: Optional[PreferencesRepository] = None
        self.context_manager: Optional[ContextManager] = None
        self.search_engine: Optional[SearchEngine] = None
        self.storage_analyzer: Optional[StorageAnalyzer] = None
        self.duplicate_detector: Optional[DuplicateDetector] = None
        self.session_analyzer: Optional[SessionAnalyzer] = None
        self.learning_engine: Optional['LearningEngine'] = None
        self.suggestion_manager: StorageSuggestionManager = StorageSuggestionManager()
        
        # Register MCP handlers
        self._register_handlers()
    
    def _format_auto_storage_notification(
        self, 
        conversation_id: str, 
        analysis_result: Dict[str, Any], 
        tags: List[str]
    ) -> str:
        """
        Format a user-friendly notification for auto-stored content.
        
        Args:
            conversation_id: ID of the stored conversation
            analysis_result: Result from storage analyzer
            tags: Tags applied to the stored content
            
        Returns:
            Formatted notification message
        """
        notification = f"🤖 Auto-stored memory!\n\n"
        notification += f"🔗 Memory ID: {conversation_id}\n"
        notification += f"📂 Category: {analysis_result['category']}\n"
        notification += f"🎯 Confidence: {analysis_result['confidence']:.1%}\n"
        notification += f"💭 Reason: {analysis_result['reason']}\n"
        notification += f"🏷️  Tags: {', '.join(tags)}\n\n"
        
        # Add extracted information if available
        if analysis_result.get('extracted_info'):
            notification += f"📋 Key Information Extracted:\n"
            for key, value in analysis_result['extracted_info'].items():
                if isinstance(value, list) and value:
                    notification += f"  • {key}: {', '.join(str(v) for v in value[:2])}\n"
                elif value and str(value).strip():
                    notification += f"  • {key}: {str(value)[:80]}{'...' if len(str(value)) > 80 else ''}\n"
            notification += "\n"
        
        # Add content preview
        content_preview = analysis_result['suggested_content'][:200]
        notification += f"📝 Stored content preview:\n{content_preview}{'...' if len(analysis_result['suggested_content']) > 200 else ''}\n\n"
        
        # Add helpful note
        notification += f"💡 This memory is now searchable and will be available for future context retrieval."
        
        return notification
    
    async def auto_store_if_eligible(
        self, 
        user_message: str, 
        ai_response: str, 
        conversation_context: str = "",
        tool_name: str = ""
    ) -> Dict[str, Any]:
        """
        Automatically analyze and store content if it meets auto-storage criteria.
        
        This method implements the core auto-storage logic:
        - Confidence > 0.85: Auto-store
        - Confidence 0.60-0.85: Suggest storage
        - Confidence < 0.60: No action
        
        Args:
            user_message: The user's message/query
            ai_response: The AI's response
            conversation_context: Additional conversation context
            tool_name: Name of the AI tool
            
        Returns:
            Dict containing storage result and metadata
        """
        try:
            # Analyze content using StorageAnalyzer
            analysis_result = self.storage_analyzer.analyze_for_storage(
                user_message=user_message,
                ai_response=ai_response,
                conversation_context=conversation_context,
                tool_name=tool_name
            )
            
            if not analysis_result['should_store']:
                return {
                    'action': 'none',
                    'reason': analysis_result['reason'],
                    'confidence': analysis_result['confidence']
                }
            
            # Auto-store high confidence content
            if analysis_result['auto_store']:
                try:
                    # Check for duplicates and optimize storage decision
                    storage_metadata = {
                        "userQuery": user_message,
                        "aiResponse": ai_response,
                        "storage_reason": analysis_result['reason'],
                        "confidence": analysis_result['confidence'],
                        "auto_stored": True,
                        "analysis_category": analysis_result['category'],
                        "extracted_info": analysis_result['extracted_info'],
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # Run duplicate detection and content optimization
                    optimization = await self.duplicate_detector.optimize_storage_decision(
                        content=analysis_result['suggested_content'],
                        metadata=storage_metadata,
                        analysis_result=analysis_result,
                        tool_name=tool_name
                    )
                    
                    # Handle optimization decision
                    if optimization.action == 'skip':
                        return {
                            'action': 'skipped_duplicate',
                            'reason': f"Storage skipped: {'; '.join(optimization.optimization_reasons)}",
                            'confidence': analysis_result['confidence'],
                            'target_conversation_id': optimization.target_conversation_id
                        }
                    elif optimization.action == 'merge':
                        # Update existing conversation with merged content
                        existing_conversation = self.conversation_repo.get_by_id(optimization.target_conversation_id)
                        if existing_conversation and optimization.merged_content:
                            from models.schemas import ConversationUpdate
                            update_data = ConversationUpdate(
                                content=optimization.merged_content,
                                conversation_metadata={
                                    **existing_conversation.conversation_metadata,
                                    "merged_at": datetime.now().isoformat(),
                                    "merge_reason": "; ".join(optimization.optimization_reasons)
                                }
                            )
                            updated_conversation = self.conversation_repo.update(
                                optimization.target_conversation_id, update_data
                            )
                            
                            return {
                                'action': 'merged',
                                'conversation_id': optimization.target_conversation_id,
                                'reason': f"Content merged: {'; '.join(optimization.optimization_reasons)}",
                                'confidence': analysis_result['confidence'] + optimization.confidence_adjustment
                            }
                    
                    # Adjust confidence based on optimization
                    adjusted_confidence = analysis_result['confidence'] + optimization.confidence_adjustment
                    storage_metadata['confidence'] = adjusted_confidence
                    storage_metadata['optimization_applied'] = True
                    storage_metadata['optimization_reasons'] = optimization.optimization_reasons
                    
                    # Add intelligent storage tags
                    tags = ["auto_stored", analysis_result['category']]
                    if analysis_result['confidence'] >= 0.9:
                        tags.append("high_confidence")
                    
                    # Create conversation using existing repository
                    from models.schemas import ConversationCreate
                    conversation_data = ConversationCreate(
                        tool_name=tool_name.lower() if tool_name else "unknown",
                        content=analysis_result['suggested_content'],
                        conversation_metadata=storage_metadata,
                        project_id=None,  # Could be enhanced to detect project
                        tags=tags
                    )
                    conversation = self.conversation_repo.create(conversation_data)
                    
                    # Add to search index with enhanced metadata
                    search_metadata = {
                        "conversation_id": conversation.id,
                        "tool_name": conversation.tool_name,
                        "project_id": conversation.project_id,
                        "timestamp": conversation.timestamp.isoformat(),
                        "tags": tags,
                        "auto_stored": True,
                        "confidence": analysis_result['confidence'],
                        "category": analysis_result['category']
                    }
                    
                    await self.search_engine.add_document(
                        content=analysis_result['suggested_content'],
                        metadata=search_metadata,
                        document_id=conversation.id
                    )
                    
                    return {
                        'action': 'auto_stored',
                        'conversation_id': conversation.id,
                        'category': analysis_result['category'],
                        'confidence': analysis_result['confidence'],
                        'reason': analysis_result['reason'],
                        'tags': tags,
                        'content_preview': analysis_result['suggested_content'][:200]
                    }
                    
                except Exception as e:
                    logger.error(f"Auto-storage failed: {e}")
                    return {
                        'action': 'auto_store_failed',
                        'error': str(e),
                        'fallback_suggestion': analysis_result
                    }
            
            else:
                # Return suggestion for medium confidence content
                return {
                    'action': 'suggest',
                    'category': analysis_result['category'],
                    'confidence': analysis_result['confidence'],
                    'reason': analysis_result['reason'],
                    'suggested_content': analysis_result['suggested_content'],
                    'extracted_info': analysis_result['extracted_info']
                }
                
        except Exception as e:
            logger.error(f"Auto-storage analysis failed: {e}")
            return {
                'action': 'error',
                'error': str(e)
            }

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
                    description="Search stored memories with intelligent storage filtering and enhanced metadata",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "limit": {"type": "integer", "description": "Max results", "default": 10},
                            "project_id": {"type": "string", "description": "Optional project ID"},
                            "category_filter": {"type": "string", "description": "Filter by intelligent storage category (preference, solution, project_context, decision)", "default": ""},
                            "auto_stored_only": {"type": "boolean", "description": "Only return auto-stored memories", "default": False},
                            "confidence_threshold": {"type": "number", "description": "Minimum confidence score for results", "default": 0.0},
                            "search_type": {"type": "string", "description": "Search type: semantic, keyword, or hybrid", "default": "hybrid"}
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
                    name="browse_memories_by_category",
                    description="Browse memories by intelligent storage category with enhanced metadata",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "category": {"type": "string", "description": "Storage category to browse (preference, solution, project_context, decision)"},
                            "limit": {"type": "integer", "description": "Max results", "default": 10},
                            "auto_stored_only": {"type": "boolean", "description": "Only show auto-stored memories", "default": False},
                            "min_confidence": {"type": "number", "description": "Minimum confidence score", "default": 0.0},
                            "project_id": {"type": "string", "description": "Optional project ID filter"}
                        },
                        "required": ["category"]
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
                ),
                Tool(
                    name="get_enhanced_context",
                    description="Get enhanced context retrieval with intelligent storage insights and recommendations",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "include_preferences": {"type": "boolean", "description": "Include user preferences in context", "default": True},
                            "include_solutions": {"type": "boolean", "description": "Include relevant solutions", "default": True},
                            "include_project_context": {"type": "boolean", "description": "Include project context", "default": True},
                            "include_decisions": {"type": "boolean", "description": "Include past decisions", "default": True},
                            "limit": {"type": "integer", "description": "Max results per category", "default": 3},
                            "project_id": {"type": "string", "description": "Optional project ID filter"}
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="analyze_conversation_for_storage",
                    description="Analyze conversation content to determine storage value and get intelligent recommendations",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "user_message": {"type": "string", "description": "The user's message/query"},
                            "ai_response": {"type": "string", "description": "The AI's response"},
                            "conversation_context": {"type": "string", "description": "Additional conversation context", "default": ""},
                            "tool_name": {"type": "string", "description": "Name of the AI tool", "default": ""}
                        },
                        "required": ["user_message", "ai_response"]
                    }
                ),
                Tool(
                    name="suggest_memory_storage",
                    description="Get storage suggestions and optionally auto-store high-confidence content using existing store_context function",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "user_message": {"type": "string", "description": "The user's message/query"},
                            "ai_response": {"type": "string", "description": "The AI's response"},
                            "conversation_context": {"type": "string", "description": "Additional conversation context", "default": ""},
                            "tool_name": {"type": "string", "description": "Name of the AI tool", "default": ""},
                            "auto_approve": {"type": "boolean", "description": "Whether to auto-approve storage suggestions", "default": false}
                        },
                        "required": ["user_message", "ai_response"]
                    }
                ),
                Tool(
                    name="approve_storage_suggestion",
                    description="Approve and store a previously suggested memory with optional modifications",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "suggestion_id": {"type": "string", "description": "ID of the storage suggestion to approve"},
                            "modified_content": {"type": "string", "description": "Optional modified content to store instead"},
                            "additional_tags": {"type": "array", "items": {"type": "string"}, "description": "Additional tags to add"},
                            "tool_name": {"type": "string", "description": "Name of the AI tool", "default": ""}
                        },
                        "required": ["suggestion_id"]
                    }
                ),
                Tool(
                    name="reject_storage_suggestion",
                    description="Reject a storage suggestion and provide feedback for learning",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "suggestion_id": {"type": "string", "description": "ID of the storage suggestion to reject"},
                            "reason": {"type": "string", "description": "Reason for rejection (for learning)"},
                            "tool_name": {"type": "string", "description": "Name of the AI tool", "default": ""}
                        },
                        "required": ["suggestion_id"]
                    }
                ),
                Tool(
                    name="get_storage_learning_insights",
                    description="Get insights from storage feedback to understand learning patterns and performance",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "include_recommendations": {"type": "boolean", "description": "Include improvement recommendations", "default": True},
                            "category_filter": {"type": "string", "description": "Filter insights by category (preference, solution, project_context, decision)", "default": ""}
                        }
                    }
                ),
                Tool(
                    name="check_for_duplicates",
                    description="Check if content has similar existing memories before storing",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "content": {"type": "string", "description": "Content to check for duplicates"},
                            "metadata": {"type": "object", "description": "Content metadata", "default": {}},
                            "tool_name": {"type": "string", "description": "Name of the AI tool", "default": ""},
                            "project_id": {"type": "string", "description": "Optional project ID for scoped search"}
                        },
                        "required": ["content"]
                    }
                ),
                Tool(
                    name="cleanup_low_confidence_memories",
                    description="Clean up old, low-confidence memories to optimize storage",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "confidence_threshold": {"type": "number", "description": "Minimum confidence to keep", "default": 0.3},
                            "days_old": {"type": "integer", "description": "Minimum age in days for cleanup", "default": 30},
                            "dry_run": {"type": "boolean", "description": "If true, only show what would be cleaned", "default": true}
                        }
                    }
                ),
                Tool(
                    name="get_duplicate_statistics",
                    description="Get statistics about duplicate detection and storage optimization",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "days": {"type": "integer", "description": "Number of days to analyze", "default": 30}
                        }
                    }
                ),
                Tool(
                    name="get_optimization_config",
                    description="Get current duplicate detection and optimization configuration",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="update_optimization_config",
                    description="Update duplicate detection and optimization configuration",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "config": {"type": "object", "description": "Configuration updates"}
                        },
                        "required": ["config"]
                    }
                ),
                Tool(
                    name="analyze_session",
                    description="Analyze a session of conversations to identify key insights, themes, and patterns",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "conversation_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of conversation IDs to analyze as a session"
                            },
                            "tool_name": {"type": "string", "description": "Filter conversations by tool name", "default": ""},
                            "hours_back": {"type": "integer", "description": "Analyze conversations from the last N hours", "default": 24},
                            "session_context": {"type": "object", "description": "Optional context about the session", "default": {}}
                        }
                    }
                ),
                Tool(
                    name="get_session_conversations",
                    description="Get conversations that could form a session based on time proximity and content similarity",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "reference_conversation_id": {"type": "string", "description": "Reference conversation to build session around"},
                            "time_window_hours": {"type": "integer", "description": "Time window to look for related conversations", "default": 4},
                            "max_conversations": {"type": "integer", "description": "Maximum conversations to include in session", "default": 10},
                            "similarity_threshold": {"type": "number", "description": "Minimum similarity threshold for inclusion", "default": 0.3}
                        },
                        "required": ["reference_conversation_id"]
                    }
                ),
                Tool(
                    name="create_session_summary",
                    description="Create and store a session summary from analyzed session data",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_analysis": {"type": "object", "description": "Session analysis result from analyze_session"},
                            "tool_name": {"type": "string", "description": "Name of the tool creating the summary", "default": "session_analyzer"},
                            "force_storage": {"type": "boolean", "description": "Force storage even if confidence is low", "default": false}
                        },
                        "required": ["session_analysis"]
                    }
                ),
                Tool(
                    name="link_session_memories",
                    description="Create cross-reference links between session summary and individual conversations",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_memory_id": {"type": "string", "description": "ID of the stored session summary"},
                            "conversation_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of conversation IDs that were part of the session"
                            },
                            "relationship_type": {"type": "string", "description": "Type of relationship", "default": "session_member"}
                        },
                        "required": ["session_memory_id", "conversation_ids"]
                    }
                ),
                Tool(
                    name="review_auto_stored_memories",
                    description="Review auto-stored memories with filtering options for management and oversight",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "description": "Maximum number of memories to return", "default": 20},
                            "offset": {"type": "integer", "description": "Number of memories to skip for pagination", "default": 0},
                            "category_filter": {"type": "string", "description": "Filter by category (preference, solution, project_context, decision)"},
                            "confidence_min": {"type": "number", "description": "Minimum confidence threshold", "default": 0.0},
                            "confidence_max": {"type": "number", "description": "Maximum confidence threshold", "default": 1.0},
                            "days_back": {"type": "integer", "description": "Number of days to look back", "default": 30},
                            "tool_filter": {"type": "string", "description": "Filter by tool name"},
                            "project_filter": {"type": "string", "description": "Filter by project ID"},
                            "include_metadata": {"type": "boolean", "description": "Include full metadata in results", "default": true}
                        }
                    }
                ),
                Tool(
                    name="edit_memory",
                    description="Edit the content, metadata, or tags of an existing memory",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "memory_id": {"type": "string", "description": "ID of the memory to edit"},
                            "new_content": {"type": "string", "description": "New content for the memory"},
                            "new_tags": {"type": "array", "items": {"type": "string"}, "description": "New tags to replace existing tags"},
                            "add_tags": {"type": "array", "items": {"type": "string"}, "description": "Tags to add to existing tags"},
                            "remove_tags": {"type": "array", "items": {"type": "string"}, "description": "Tags to remove from existing tags"},
                            "metadata_updates": {"type": "object", "description": "Metadata fields to update"},
                            "update_search_index": {"type": "boolean", "description": "Whether to update search index", "default": true}
                        },
                        "required": ["memory_id"]
                    }
                ),
                Tool(
                    name="delete_memory",
                    description="Delete a specific memory by ID with confirmation",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "memory_id": {"type": "string", "description": "ID of the memory to delete"},
                            "confirm": {"type": "boolean", "description": "Confirmation flag to prevent accidental deletion", "default": false},
                            "remove_from_search": {"type": "boolean", "description": "Whether to remove from search index", "default": true}
                        },
                        "required": ["memory_id", "confirm"]
                    }
                ),
                Tool(
                    name="bulk_manage_memories",
                    description="Perform bulk operations on multiple memories (delete, tag, export)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "memory_ids": {"type": "array", "items": {"type": "string"}, "description": "List of memory IDs to operate on"},
                            "operation": {"type": "string", "enum": ["delete", "add_tags", "remove_tags", "export", "update_category"], "description": "Bulk operation to perform"},
                            "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags for add_tags/remove_tags operations"},
                            "new_category": {"type": "string", "description": "New category for update_category operation"},
                            "export_format": {"type": "string", "enum": ["json", "csv", "markdown"], "description": "Export format", "default": "json"},
                            "confirm": {"type": "boolean", "description": "Confirmation flag for destructive operations", "default": false}
                        },
                        "required": ["memory_ids", "operation"]
                    }
                ),
                Tool(
                    name="export_memories",
                    description="Export memories to various formats with filtering options",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "format": {"type": "string", "enum": ["json", "csv", "markdown"], "description": "Export format", "default": "json"},
                            "category_filter": {"type": "string", "description": "Filter by category"},
                            "confidence_min": {"type": "number", "description": "Minimum confidence threshold", "default": 0.0},
                            "days_back": {"type": "integer", "description": "Number of days to look back", "default": 30},
                            "tool_filter": {"type": "string", "description": "Filter by tool name"},
                            "project_filter": {"type": "string", "description": "Filter by project ID"},
                            "auto_stored_only": {"type": "boolean", "description": "Export only auto-stored memories", "default": false},
                            "include_metadata": {"type": "boolean", "description": "Include metadata in export", "default": true},
                            "output_file": {"type": "string", "description": "Optional output file path"}
                        }
                    }
                ),
                Tool(
                    name="get_memory_statistics",
                    description="Get detailed statistics about stored memories including auto-storage performance",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "days_back": {"type": "integer", "description": "Number of days to analyze", "default": 30},
                            "include_categories": {"type": "boolean", "description": "Include category breakdown", "default": true},
                            "include_tools": {"type": "boolean", "description": "Include tool breakdown", "default": true},
                            "include_confidence": {"type": "boolean", "description": "Include confidence analysis", "default": true},
                            "include_trends": {"type": "boolean", "description": "Include trend analysis", "default": true}
                        }
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
                        from models.schemas import ConversationCreate
                        
                        # Enhance metadata with intelligent storage fields if not present
                        enhanced_metadata = metadata.copy()
                        if "timestamp" not in enhanced_metadata:
                            enhanced_metadata["timestamp"] = datetime.now().isoformat()
                        
                        # Ensure tags include any intelligent storage tags
                        tags = metadata.get("tags", [])
                        if not isinstance(tags, list):
                            tags = []
                        
                        # Add manual storage tag if not auto-stored
                        if "auto_stored" not in tags and not enhanced_metadata.get("auto_stored", False):
                            tags.append("manual_stored")
                        
                        conversation_data = ConversationCreate(
                            tool_name=tool_name,
                            content=content,
                            conversation_metadata=enhanced_metadata,
                            project_id=arguments.get("project_id"),
                            tags=tags
                        )
                        conversation = self.conversation_repo.create(conversation_data)
                        
                        # Add to search index with enhanced metadata
                        search_metadata = {
                            "conversation_id": conversation.id,
                            "tool_name": tool_name,
                            "project_id": conversation.project_id,
                            "timestamp": conversation.timestamp.isoformat(),
                            "tags": tags,
                            "auto_stored": enhanced_metadata.get("auto_stored", False),
                            "confidence": enhanced_metadata.get("confidence", 1.0),
                            "category": enhanced_metadata.get("analysis_category", "manual")
                        }
                        
                        await self.search_engine.add_document(
                            content=content,
                            metadata=search_metadata,
                            document_id=conversation.id
                        )
                        
                        # Enhanced success message
                        success_msg = f"✅ Context stored successfully! ID: {conversation.id}\n"
                        success_msg += f"🔧 Tool: {tool_name}\n"
                        success_msg += f"🏷️  Tags: {', '.join(tags) if tags else 'None'}\n"
                        if enhanced_metadata.get("confidence"):
                            success_msg += f"🎯 Confidence: {enhanced_metadata['confidence']:.1%}\n"
                        if enhanced_metadata.get("analysis_category"):
                            success_msg += f"📂 Category: {enhanced_metadata['analysis_category']}\n"
                        success_msg += f"📝 Content: {content[:100]}..."
                        
                        return [{
                            "type": "text",
                            "text": success_msg
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
                                from models.database import Conversation
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
                
                elif name == "browse_memories_by_category":
                    category = arguments.get("category", "")
                    limit = arguments.get("limit", 10)
                    auto_stored_only = arguments.get("auto_stored_only", False)
                    min_confidence = arguments.get("min_confidence", 0.0)
                    project_id = arguments.get("project_id")
                    
                    if not category:
                        return [{
                            "type": "text",
                            "text": "❌ Missing required parameter: category"
                        }]
                    
                    valid_categories = ["preference", "solution", "project_context", "decision"]
                    if category not in valid_categories:
                        return [{
                            "type": "text",
                            "text": f"❌ Invalid category. Must be one of: {', '.join(valid_categories)}"
                        }]
                    
                    try:
                        # Query conversations with intelligent storage metadata
                        with self.conversation_repo.db_manager.get_session() as session:
                            from models.database import Conversation
                            from sqlalchemy import and_, or_
                            
                            query = session.query(Conversation)
                            
                            # Filter by category - check both metadata and tags
                            category_conditions = []
                            
                            # Check in metadata JSON
                            category_conditions.append(
                                Conversation.conversation_metadata.op('->>')('analysis_category') == category
                            )
                            
                            # Check in tags
                            category_conditions.append(
                                Conversation.tags.like(f'%{category}%')
                            )
                            
                            query = query.filter(or_(*category_conditions))
                            
                            # Filter by auto-stored if requested
                            if auto_stored_only:
                                auto_stored_conditions = []
                                auto_stored_conditions.append(
                                    Conversation.conversation_metadata.op('->>')('auto_stored') == 'true'
                                )
                                auto_stored_conditions.append(
                                    Conversation.tags.like('%auto_stored%')
                                )
                                query = query.filter(or_(*auto_stored_conditions))
                            
                            # Filter by confidence if specified
                            if min_confidence > 0.0:
                                query = query.filter(
                                    Conversation.conversation_metadata.op('->>')('confidence').cast(float) >= min_confidence
                                )
                            
                            # Filter by project if specified
                            if project_id:
                                query = query.filter(Conversation.project_id == project_id)
                            
                            # Order by timestamp descending and limit
                            conversations = query.order_by(Conversation.timestamp.desc()).limit(limit).all()
                        
                        if conversations:
                            browse_text = f"📂 Found {len(conversations)} memories in category '{category}'"
                            if auto_stored_only:
                                browse_text += " (auto-stored only)"
                            if min_confidence > 0.0:
                                browse_text += f" (confidence ≥ {min_confidence})"
                            browse_text += ":\n\n"
                            
                            for i, conv in enumerate(conversations, 1):
                                # Extract intelligent storage metadata
                                metadata = conv.conversation_metadata or {}
                                confidence = metadata.get("confidence", "N/A")
                                storage_reason = metadata.get("storage_reason", "N/A")
                                auto_stored = metadata.get("auto_stored", False)
                                extracted_info = metadata.get("extracted_info", {})
                                
                                # Format the result with enhanced metadata
                                browse_text += f"{i}. 🔗 ID: {conv.id}\n"
                                browse_text += f"📅 [{conv.tool_name}] {conv.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                                browse_text += f"🎯 Confidence: {confidence}\n"
                                browse_text += f"🤖 Auto-stored: {'Yes' if auto_stored else 'No'}\n"
                                browse_text += f"💭 Reason: {storage_reason}\n"
                                
                                if conv.project_id:
                                    browse_text += f"📁 Project: {conv.project_id}\n"
                                
                                if conv.tags_list:
                                    browse_text += f"🏷️  Tags: {', '.join(conv.tags_list)}\n"
                                
                                if extracted_info:
                                    browse_text += f"📋 Extracted Info:\n"
                                    for key, value in extracted_info.items():
                                        if isinstance(value, list) and value:
                                            browse_text += f"  • {key}: {', '.join(str(v) for v in value[:2])}\n"
                                        elif value and str(value).strip():
                                            browse_text += f"  • {key}: {str(value)[:80]}{'...' if len(str(value)) > 80 else ''}\n"
                                
                                # Show content preview
                                content_preview = conv.content[:300] + "..." if len(conv.content) > 300 else conv.content
                                browse_text += f"\n💬 Content:\n{content_preview}\n\n{'='*50}\n\n"
                        else:
                            browse_text = f"📂 No memories found in category '{category}'"
                            if auto_stored_only:
                                browse_text += " (auto-stored only)"
                            if min_confidence > 0.0:
                                browse_text += f" (confidence ≥ {min_confidence})"
                        
                        return [{
                            "type": "text",
                            "text": browse_text
                        }]
                    except Exception as e:
                        return [{
                            "type": "text",
                            "text": f"❌ Failed to browse memories by category: {str(e)}"
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
                
                elif name == "analyze_conversation_for_storage":
                    user_message = arguments.get("user_message", "")
                    ai_response = arguments.get("ai_response", "")
                    conversation_context = arguments.get("conversation_context", "")
                    tool_name = arguments.get("tool_name", "")
                    
                    if not user_message or not ai_response:
                        return [{
                            "type": "text",
                            "text": "❌ Missing required parameters: user_message and ai_response"
                        }]
                    
                    try:
                        # Analyze content using StorageAnalyzer
                        analysis_result = self.storage_analyzer.analyze_for_storage(
                            user_message=user_message,
                            ai_response=ai_response,
                            conversation_context=conversation_context,
                            tool_name=tool_name
                        )
                        
                        # Format analysis result for display
                        result_text = f"🧠 Storage Analysis Results:\\n\\n"
                        result_text += f"📊 Should Store: {'✅ Yes' if analysis_result['should_store'] else '❌ No'}\\n"
                        result_text += f"🎯 Confidence: {analysis_result['confidence']:.1%}\\n"
                        result_text += f"📂 Category: {analysis_result['category'] or 'None'}\\n"
                        result_text += f"💭 Reason: {analysis_result['reason']}\\n"
                        result_text += f"🤖 Auto-Store: {'✅ Yes' if analysis_result['auto_store'] else '❌ No'}\\n\\n"
                        
                        if analysis_result['extracted_info']:
                            result_text += f"📋 Extracted Information:\\n{json.dumps(analysis_result['extracted_info'], indent=2)}\\n\\n"
                        
                        if analysis_result['should_store']:
                            result_text += f"💡 Suggested Content:\\n{analysis_result['suggested_content'][:300]}{'...' if len(analysis_result['suggested_content']) > 300 else ''}\\n\\n"
                        
                        result_text += f"🔧 Full Analysis Data:\\n{json.dumps(analysis_result, indent=2)}"
                        
                        return [{
                            "type": "text",
                            "text": result_text
                        }]
                    except Exception as e:
                        return [{
                            "type": "text",
                            "text": f"❌ Analysis failed: {str(e)}"
                        }]
                
                elif name == "get_enhanced_context":
                    query = arguments.get("query", "")
                    include_preferences = arguments.get("include_preferences", True)
                    include_solutions = arguments.get("include_solutions", True)
                    include_project_context = arguments.get("include_project_context", True)
                    include_decisions = arguments.get("include_decisions", True)
                    limit = arguments.get("limit", 3)
                    project_id = arguments.get("project_id")
                    
                    if not query:
                        return [{
                            "type": "text",
                            "text": "❌ Missing required parameter: query"
                        }]
                    
                    try:
                        enhanced_context = {}
                        total_results = 0
                        
                        # Build base filters
                        base_filters = {}
                        if project_id:
                            base_filters["project_id"] = project_id
                        
                        # Search for preferences
                        if include_preferences:
                            pref_filters = {**base_filters, "category": "preference"}
                            pref_results = await self.search_engine.search(
                                query=query,
                                limit=limit,
                                filters=pref_filters,
                                search_type="hybrid"
                            )
                            enhanced_context["preferences"] = [
                                {
                                    "id": r.metadata.get("conversation_id"),
                                    "content": r.content[:200] + "..." if len(r.content) > 200 else r.content,
                                    "confidence": r.metadata.get("confidence", 0.0),
                                    "relevance": round(r.combined_score, 3),
                                    "timestamp": r.metadata.get("timestamp")
                                }
                                for r in pref_results
                            ]
                            total_results += len(pref_results)
                        
                        # Search for solutions
                        if include_solutions:
                            sol_filters = {**base_filters, "category": "solution"}
                            sol_results = await self.search_engine.search(
                                query=query,
                                limit=limit,
                                filters=sol_filters,
                                search_type="hybrid"
                            )
                            enhanced_context["solutions"] = [
                                {
                                    "id": r.metadata.get("conversation_id"),
                                    "content": r.content[:200] + "..." if len(r.content) > 200 else r.content,
                                    "confidence": r.metadata.get("confidence", 0.0),
                                    "relevance": round(r.combined_score, 3),
                                    "timestamp": r.metadata.get("timestamp")
                                }
                                for r in sol_results
                            ]
                            total_results += len(sol_results)
                        
                        # Search for project context
                        if include_project_context:
                            proj_filters = {**base_filters, "category": "project_context"}
                            proj_results = await self.search_engine.search(
                                query=query,
                                limit=limit,
                                filters=proj_filters,
                                search_type="hybrid"
                            )
                            enhanced_context["project_context"] = [
                                {
                                    "id": r.metadata.get("conversation_id"),
                                    "content": r.content[:200] + "..." if len(r.content) > 200 else r.content,
                                    "confidence": r.metadata.get("confidence", 0.0),
                                    "relevance": round(r.combined_score, 3),
                                    "timestamp": r.metadata.get("timestamp")
                                }
                                for r in proj_results
                            ]
                            total_results += len(proj_results)
                        
                        # Search for decisions
                        if include_decisions:
                            dec_filters = {**base_filters, "category": "decision"}
                            dec_results = await self.search_engine.search(
                                query=query,
                                limit=limit,
                                filters=dec_filters,
                                search_type="hybrid"
                            )
                            enhanced_context["decisions"] = [
                                {
                                    "id": r.metadata.get("conversation_id"),
                                    "content": r.content[:200] + "..." if len(r.content) > 200 else r.content,
                                    "confidence": r.metadata.get("confidence", 0.0),
                                    "relevance": round(r.combined_score, 3),
                                    "timestamp": r.metadata.get("timestamp")
                                }
                                for r in dec_results
                            ]
                            total_results += len(dec_results)
                        
                        # Format enhanced context response
                        context_text = f"🧠 Enhanced Context for: '{query}'\n\n"
                        context_text += f"📊 Total Results: {total_results}\n\n"
                        
                        for category, results in enhanced_context.items():
                            if results:
                                category_name = category.replace('_', ' ').title()
                                context_text += f"📂 {category_name} ({len(results)} results):\n"
                                for i, result in enumerate(results, 1):
                                    context_text += f"  {i}. 🔗 {result['id']} (relevance: {result['relevance']}, confidence: {result['confidence']})\n"
                                    context_text += f"     📅 {result['timestamp']}\n"
                                    context_text += f"     💬 {result['content']}\n\n"
                                context_text += "\n"
                        
                        if total_results == 0:
                            context_text += "❌ No relevant context found with intelligent storage metadata.\n"
                            context_text += "💡 Try using the regular search_memory tool for broader results."
                        
                        return [{
                            "type": "text",
                            "text": context_text
                        }]
                    except Exception as e:
                        return [{
                            "type": "text",
                            "text": f"❌ Failed to get enhanced context: {str(e)}"
                        }]
                
                elif name == "suggest_memory_storage":
                    user_message = arguments.get("user_message", "")
                    ai_response = arguments.get("ai_response", "")
                    conversation_context = arguments.get("conversation_context", "")
                    tool_name = arguments.get("tool_name", "")
                    auto_approve = arguments.get("auto_approve", False)
                    
                    if not user_message or not ai_response:
                        return [{
                            "type": "text",
                            "text": "❌ Missing required parameters: user_message and ai_response"
                        }]
                    
                    try:
                        # Analyze content using StorageAnalyzer
                        analysis_result = self.storage_analyzer.analyze_for_storage(
                            user_message=user_message,
                            ai_response=ai_response,
                            conversation_context=conversation_context,
                            tool_name=tool_name
                        )
                        
                        # Apply learning-based adjustments if learning engine is available
                        if self.learning_engine:
                            try:
                                learning_adjustments = await self.learning_engine.get_adjusted_confidence_thresholds()
                                analysis_result = self.storage_analyzer.apply_learning_adjustments(
                                    analysis_result, learning_adjustments
                                )
                            except Exception as e:
                                logger.warning(f"Failed to apply learning adjustments: {e}")
                        
                        if not analysis_result['should_store']:
                            return [{
                                "type": "text",
                                "text": f"💭 No storage recommended: {analysis_result['reason']}"
                            }]
                        
                        # Check if we should auto-store or suggest
                        if analysis_result['auto_store'] or auto_approve:
                            # Auto-store using existing store_context functionality
                            try:
                                # Prepare metadata with analysis results
                                storage_metadata = analysis_result['metadata'].copy()
                                storage_metadata.update({
                                    "userQuery": user_message,
                                    "aiResponse": ai_response,
                                    "extracted_info": analysis_result['extracted_info']
                                })
                                
                                # Add intelligent storage tags
                                tags = ["auto_stored", analysis_result['category']]
                                if analysis_result['confidence'] >= 0.9:
                                    tags.append("high_confidence")
                                
                                # Create conversation using existing store_context logic
                                from models.schemas import ConversationCreate
                                conversation_data = ConversationCreate(
                                    tool_name=tool_name.lower() if tool_name else "unknown",
                                    content=analysis_result['suggested_content'],
                                    conversation_metadata=storage_metadata,
                                    project_id=None,  # Could be enhanced to detect project
                                    tags=tags
                                )
                                conversation = self.conversation_repo.create(conversation_data)
                                
                                # Add to search index
                                search_metadata = {
                                    "conversation_id": conversation.id,
                                    "tool_name": conversation.tool_name,
                                    "project_id": conversation.project_id,
                                    "timestamp": conversation.timestamp.isoformat(),
                                    "tags": tags,
                                    "auto_stored": True,
                                    "confidence": analysis_result['confidence'],
                                    "category": analysis_result['category']
                                }
                                
                                await self.search_engine.add_document(
                                    content=analysis_result['suggested_content'],
                                    metadata=search_metadata,
                                    document_id=conversation.id
                                )
                                
                                # Return auto-storage notification
                                notification = self._format_auto_storage_notification(
                                    conversation.id, analysis_result, tags
                                )
                                return [{
                                    "type": "text",
                                    "text": notification
                                }]
                                
                            except Exception as e:
                                logger.error(f"Auto-storage failed: {e}")
                                return [{
                                    "type": "text",
                                    "text": f"❌ Auto-storage failed: {str(e)}\n"
                                           f"💡 Suggestion: {analysis_result['reason']}\n"
                                           f"📝 Content: {analysis_result['suggested_content'][:200]}..."
                                }]
                        
                        else:
                            # Create a storage suggestion for user approval
                            suggestion_id = self.suggestion_manager.create_suggestion(
                                user_message=user_message,
                                ai_response=ai_response,
                                analysis_result=analysis_result,
                                tool_name=tool_name
                            )
                            
                            # Clean up old suggestions to prevent memory buildup
                            self.suggestion_manager.cleanup_old_suggestions()
                            
                            # Format user-friendly suggestion with approval workflow
                            suggestion_text = f"💡 Storage Suggestion (ID: {suggestion_id})\n\n"
                            suggestion_text += f"📂 Category: {analysis_result['category']}\n"
                            suggestion_text += f"🎯 Confidence: {analysis_result['confidence']:.1%}\n"
                            suggestion_text += f"💭 Reason: {analysis_result['reason']}\n\n"
                            
                            if analysis_result['extracted_info']:
                                suggestion_text += f"📋 Extracted Information:\n"
                                for key, value in analysis_result['extracted_info'].items():
                                    if isinstance(value, list) and value:
                                        suggestion_text += f"  • {key}: {', '.join(str(v) for v in value[:3])}\n"
                                    elif value:
                                        suggestion_text += f"  • {key}: {str(value)[:100]}\n"
                                suggestion_text += "\n"
                            
                            suggestion_text += f"📝 Suggested content to store:\n{analysis_result['suggested_content'][:300]}{'...' if len(analysis_result['suggested_content']) > 300 else ''}\n\n"
                            
                            # Add approval workflow instructions
                            suggestion_text += f"🔄 Next Steps:\n"
                            suggestion_text += f"  ✅ To approve: Use approve_storage_suggestion with suggestion_id '{suggestion_id}'\n"
                            suggestion_text += f"  ❌ To reject: Use reject_storage_suggestion with suggestion_id '{suggestion_id}'\n"
                            suggestion_text += f"  ✏️  To modify: Use approve_storage_suggestion with modified_content parameter\n\n"
                            suggestion_text += f"⏰ This suggestion will expire in 24 hours if not acted upon."
                            
                            return [{
                                "type": "text",
                                "text": suggestion_text
                            }]
                        
                    except Exception as e:
                        logger.error(f"Storage suggestion failed: {e}")
                        return [{
                            "type": "text",
                            "text": f"❌ Storage analysis failed: {str(e)}"
                        }]
                
                elif name == "approve_storage_suggestion":
                    suggestion_id = arguments.get("suggestion_id", "")
                    modified_content = arguments.get("modified_content", "")
                    additional_tags = arguments.get("additional_tags", [])
                    tool_name = arguments.get("tool_name", "")
                    
                    if not suggestion_id:
                        return [{
                            "type": "text",
                            "text": "❌ Missing required parameter: suggestion_id"
                        }]
                    
                    try:
                        # Get the suggestion
                        suggestion = self.suggestion_manager.get_suggestion(suggestion_id)
                        if not suggestion:
                            return [{
                                "type": "text",
                                "text": f"❌ Suggestion not found: {suggestion_id}"
                            }]
                        
                        if suggestion['status'] != 'pending':
                            return [{
                                "type": "text",
                                "text": f"❌ Suggestion {suggestion_id} is not pending (status: {suggestion['status']})"
                            }]
                        
                        # Approve the suggestion
                        approved_suggestion = self.suggestion_manager.approve_suggestion(suggestion_id)
                        
                        # Process feedback for learning
                        await self._process_storage_approval_feedback(
                            suggestion, modified_content, tool_name
                        )
                        analysis_result = suggestion['analysis_result']
                        
                        # Use modified content if provided, otherwise use suggested content
                        content_to_store = modified_content if modified_content else analysis_result['suggested_content']
                        
                        # Prepare metadata with analysis results
                        storage_metadata = analysis_result['metadata'].copy()
                        storage_metadata.update({
                            "userQuery": suggestion['user_message'],
                            "aiResponse": suggestion['ai_response'],
                            "extracted_info": analysis_result['extracted_info'],
                            "suggestion_id": suggestion_id,
                            "user_approved": True,
                            "content_modified": bool(modified_content)
                        })
                        
                        # Add intelligent storage tags
                        tags = ["suggested", "user_approved", analysis_result['category']]
                        if analysis_result['confidence'] >= 0.9:
                            tags.append("high_confidence")
                        if additional_tags:
                            tags.extend(additional_tags)
                        
                        # Create conversation using existing store_context logic
                        from models.schemas import ConversationCreate
                        conversation_data = ConversationCreate(
                            tool_name=tool_name.lower() if tool_name else suggestion['tool_name'].lower(),
                            content=content_to_store,
                            conversation_metadata=storage_metadata,
                            project_id=None,  # Could be enhanced to detect project
                            tags=tags
                        )
                        conversation = self.conversation_repo.create(conversation_data)
                        
                        # Add to search index
                        search_metadata = {
                            "conversation_id": conversation.id,
                            "tool_name": conversation.tool_name,
                            "project_id": conversation.project_id,
                            "timestamp": conversation.timestamp.isoformat(),
                            "tags": tags,
                            "auto_stored": False,
                            "user_approved": True,
                            "confidence": analysis_result['confidence'],
                            "category": analysis_result['category']
                        }
                        
                        await self.search_engine.add_document(
                            content=content_to_store,
                            metadata=search_metadata,
                            document_id=conversation.id
                        )
                        
                        # Return approval confirmation
                        result_text = f"✅ Storage suggestion approved and stored!\n\n"
                        result_text += f"🔗 Memory ID: {conversation.id}\n"
                        result_text += f"📂 Category: {analysis_result['category']}\n"
                        result_text += f"🎯 Confidence: {analysis_result['confidence']:.1%}\n"
                        result_text += f"🏷️  Tags: {', '.join(tags)}\n"
                        if modified_content:
                            result_text += f"✏️  Content was modified by user\n"
                        result_text += f"\n📝 Stored content:\n{content_to_store[:300]}{'...' if len(content_to_store) > 300 else ''}"
                        
                        return [{
                            "type": "text",
                            "text": result_text
                        }]
                        
                    except Exception as e:
                        logger.error(f"Error approving suggestion: {e}")
                        return [{
                            "type": "text",
                            "text": f"❌ Failed to approve suggestion: {str(e)}"
                        }]
                
                elif name == "reject_storage_suggestion":
                    suggestion_id = arguments.get("suggestion_id", "")
                    reason = arguments.get("reason", "")
                    tool_name = arguments.get("tool_name", "")
                    
                    if not suggestion_id:
                        return [{
                            "type": "text",
                            "text": "❌ Missing required parameter: suggestion_id"
                        }]
                    
                    try:
                        # Get the suggestion
                        suggestion = self.suggestion_manager.get_suggestion(suggestion_id)
                        if not suggestion:
                            return [{
                                "type": "text",
                                "text": f"❌ Suggestion not found: {suggestion_id}"
                            }]
                        
                        if suggestion['status'] != 'pending':
                            return [{
                                "type": "text",
                                "text": f"❌ Suggestion {suggestion_id} is not pending (status: {suggestion['status']})"
                            }]
                        
                        # Reject the suggestion
                        rejected_suggestion = self.suggestion_manager.reject_suggestion(suggestion_id, reason)
                        
                        # Process feedback for learning
                        await self._process_storage_rejection_feedback(
                            suggestion, reason, tool_name
                        )
                        
                        result_text = f"❌ Storage suggestion rejected\n\n"
                        result_text += f"🔗 Suggestion ID: {suggestion_id}\n"
                        result_text += f"📂 Category: {suggestion['analysis_result']['category']}\n"
                        result_text += f"🎯 Confidence: {suggestion['analysis_result']['confidence']:.1%}\n"
                        if reason:
                            result_text += f"💭 Rejection reason: {reason}\n"
                        result_text += f"\n📝 Rejected content:\n{suggestion['analysis_result']['suggested_content'][:200]}..."
                        result_text += f"\n\n💡 This feedback will help improve future suggestions."
                        
                        return [{
                            "type": "text",
                            "text": result_text
                        }]
                        
                    except Exception as e:
                        logger.error(f"Error rejecting suggestion: {e}")
                        return [{
                            "type": "text",
                            "text": f"❌ Failed to reject suggestion: {str(e)}"
                        }]
                
                elif name == "get_storage_learning_insights":
                    include_recommendations = arguments.get("include_recommendations", True)
                    category_filter = arguments.get("category_filter", "")
                    
                    try:
                        if not self.learning_engine:
                            return [{
                                "type": "text",
                                "text": "❌ Learning engine not available"
                            }]
                        
                        # Get storage feedback insights
                        insights = await self.learning_engine.get_storage_feedback_insights()
                        
                        if not insights:
                            return [{
                                "type": "text",
                                "text": "📊 No learning insights available yet. Start using storage suggestions to build learning data."
                            }]
                        
                        # Filter by category if specified
                        if category_filter:
                            filtered_insights = {}
                            for key, value in insights.items():
                                if key == 'recommendations':
                                    # Filter recommendations that mention the category
                                    filtered_insights[key] = [
                                        rec for rec in value 
                                        if category_filter.lower() in rec.lower()
                                    ]
                                elif isinstance(value, dict):
                                    # Filter dictionary entries that contain the category
                                    filtered_insights[key] = {
                                        k: v for k, v in value.items()
                                        if category_filter.lower() in k.lower()
                                    }
                                else:
                                    filtered_insights[key] = value
                            insights = filtered_insights
                        
                        # Format insights for display
                        result_text = "📊 Storage Learning Insights\n\n"
                        
                        # Category Performance
                        if insights.get('category_performance'):
                            result_text += "📈 Category Performance:\n"
                            for category, performance in insights['category_performance'].items():
                                accuracy = performance.get('accuracy_rate', 0.0)
                                total = performance.get('total_suggestions', 0)
                                avg_confidence = performance.get('avg_confidence', 0.0)
                                
                                result_text += f"  • {category}: {accuracy:.1%} accuracy ({total} suggestions, avg confidence: {avg_confidence:.2f})\n"
                            result_text += "\n"
                        
                        # User Preferences
                        if insights.get('user_preferences'):
                            result_text += "👤 User Storage Preferences:\n"
                            for category, pref_data in insights['user_preferences'].items():
                                approval_rate = pref_data.get('approval_rate', 0.0)
                                total_interactions = pref_data.get('total_interactions', 0)
                                preferred_range = pref_data.get('preferred_confidence_range', [0.6, 1.0])
                                
                                result_text += f"  • {category}: {approval_rate:.1%} approval rate ({total_interactions} interactions)\n"
                                result_text += f"    Preferred confidence range: {preferred_range[0]:.2f} - {preferred_range[1]:.2f}\n"
                            result_text += "\n"
                        
                        # Confidence Calibration
                        if insights.get('confidence_calibration'):
                            result_text += "🎯 Confidence Calibration:\n"
                            calibration_summary = {}
                            for key, calibration in insights['confidence_calibration'].items():
                                confidence_bucket = calibration.get('confidence_bucket', 0.0)
                                calibration_score = calibration.get('calibration_score', 0.0)
                                total_predictions = calibration.get('total_predictions', 0)
                                
                                if total_predictions >= 3:  # Only show meaningful data
                                    bucket_key = f"{confidence_bucket:.1f}"
                                    if bucket_key not in calibration_summary:
                                        calibration_summary[bucket_key] = []
                                    calibration_summary[bucket_key].append(calibration_score)
                            
                            for bucket, scores in calibration_summary.items():
                                avg_score = sum(scores) / len(scores)
                                result_text += f"  • Confidence {bucket}: {avg_score:.1%} actual accuracy\n"
                            result_text += "\n"
                        
                        # Recommendations
                        if include_recommendations and insights.get('recommendations'):
                            result_text += "💡 Recommendations:\n"
                            for rec in insights['recommendations']:
                                result_text += f"  • {rec}\n"
                            result_text += "\n"
                        
                        # Learning Statistics
                        learning_stats = await self.learning_engine.get_learning_stats()
                        if learning_stats:
                            result_text += "📈 Learning Statistics:\n"
                            result_text += f"  • Patterns detected: {learning_stats.get('patterns_detected', 0)}\n"
                            result_text += f"  • Feedback processed: {learning_stats.get('feedback_processed', 0)}\n"
                            result_text += f"  • Corrections learned: {learning_stats.get('corrections_learned', 0)}\n"
                            
                            confidence_dist = learning_stats.get('confidence_distribution', {})
                            if confidence_dist:
                                result_text += f"  • Confidence distribution: "
                                result_text += f"Low: {confidence_dist.get('low', 0)}, "
                                result_text += f"Medium: {confidence_dist.get('medium', 0)}, "
                                result_text += f"High: {confidence_dist.get('high', 0)}\n"
                        
                        if not result_text.strip().endswith('\n\n'):
                            result_text += "\n"
                        
                        result_text += "🔄 The system continuously learns from your feedback to improve storage suggestions."
                        
                        return [{
                            "type": "text",
                            "text": result_text
                        }]
                        
                    except Exception as e:
                        logger.error(f"Error getting storage learning insights: {e}")
                        return [{
                            "type": "text",
                            "text": f"❌ Failed to get learning insights: {str(e)}"
                        }]
                
                elif name == "check_for_duplicates":
                    content = arguments.get("content", "")
                    metadata = arguments.get("metadata", {})
                    tool_name = arguments.get("tool_name", "")
                    project_id = arguments.get("project_id")
                    
                    if not content:
                        return [{
                            "type": "text",
                            "text": "❌ Missing required parameter: content"
                        }]
                    
                    try:
                        if not self.duplicate_detector:
                            return [{
                                "type": "text",
                                "text": "❌ Duplicate detector not available"
                            }]
                        
                        duplicates = await self.duplicate_detector.check_for_duplicates(
                            content=content,
                            metadata=metadata,
                            tool_name=tool_name,
                            project_id=project_id
                        )
                        
                        if not duplicates:
                            return [{
                                "type": "text",
                                "text": "✅ No duplicate or similar content found. Content is unique and safe to store."
                            }]
                        
                        result_text = f"🔍 Found {len(duplicates)} potential duplicate(s):\n\n"
                        
                        for i, duplicate in enumerate(duplicates[:5], 1):  # Show top 5
                            result_text += f"{i}. 🔗 Memory ID: {duplicate.conversation_id}\n"
                            result_text += f"   📊 Similarity: {duplicate.similarity_score:.1%}\n"
                            result_text += f"   🏷️  Type: {duplicate.match_type}\n"
                            result_text += f"   🎯 Confidence: {duplicate.confidence:.1%}\n"
                            result_text += f"   💭 Reasons: {', '.join(duplicate.reasons)}\n"
                            if duplicate.merge_candidate:
                                result_text += f"   🔄 Merge candidate: Yes\n"
                            result_text += "\n"
                        
                        if len(duplicates) > 5:
                            result_text += f"... and {len(duplicates) - 5} more potential duplicates\n\n"
                        
                        result_text += "💡 Consider reviewing these memories before storing new content to avoid duplication."
                        
                        return [{
                            "type": "text",
                            "text": result_text
                        }]
                        
                    except Exception as e:
                        logger.error(f"Error checking for duplicates: {e}")
                        return [{
                            "type": "text",
                            "text": f"❌ Error checking for duplicates: {str(e)}"
                        }]
                
                elif name == "cleanup_low_confidence_memories":
                    confidence_threshold = arguments.get("confidence_threshold", 0.3)
                    days_old = arguments.get("days_old", 30)
                    dry_run = arguments.get("dry_run", True)
                    
                    try:
                        if not self.duplicate_detector:
                            return [{
                                "type": "text",
                                "text": "❌ Duplicate detector not available"
                            }]
                        
                        cleanup_results = await self.duplicate_detector.cleanup_low_confidence_memories(
                            confidence_threshold=confidence_threshold,
                            days_old=days_old,
                            dry_run=dry_run
                        )
                        
                        if 'error' in cleanup_results:
                            return [{
                                "type": "text",
                                "text": f"❌ Cleanup error: {cleanup_results['error']}"
                            }]
                        
                        result_text = f"🧹 Memory Cleanup {'Analysis' if dry_run else 'Results'}\n\n"
                        result_text += f"📊 Total candidates found: {cleanup_results['total_candidates']}\n"
                        result_text += f"🎯 Confidence threshold: {confidence_threshold}\n"
                        result_text += f"📅 Age threshold: {days_old} days\n\n"
                        
                        if dry_run:
                            result_text += f"🔍 Would delete: {cleanup_results['would_delete']} memories\n"
                            result_text += f"💾 Estimated space saved: {cleanup_results['space_saved_estimate']} characters\n\n"
                            
                            if cleanup_results['cleanup_candidates']:
                                result_text += "📋 Sample cleanup candidates:\n"
                                for candidate in cleanup_results['cleanup_candidates']:
                                    result_text += f"  • ID: {candidate['id']}\n"
                                    result_text += f"    📅 Date: {candidate['timestamp'][:10]}\n"
                                    result_text += f"    🎯 Confidence: {candidate['confidence']:.2f}\n"
                                    result_text += f"    📏 Length: {candidate['content_length']} chars\n"
                                    result_text += f"    🔧 Tool: {candidate['tool_name']}\n\n"
                            
                            result_text += "⚠️  This was a dry run. Set dry_run=false to actually delete memories."
                        else:
                            result_text += f"✅ Actually deleted: {cleanup_results['actually_deleted']} memories\n"
                            result_text += f"💾 Space freed: {cleanup_results['space_saved_estimate']} characters\n\n"
                            result_text += "🎉 Cleanup completed successfully!"
                        
                        return [{
                            "type": "text",
                            "text": result_text
                        }]
                        
                    except Exception as e:
                        logger.error(f"Error during cleanup: {e}")
                        return [{
                            "type": "text",
                            "text": f"❌ Error during cleanup: {str(e)}"
                        }]
                
                elif name == "get_duplicate_statistics":
                    days = arguments.get("days", 30)
                    
                    try:
                        if not self.duplicate_detector:
                            return [{
                                "type": "text",
                                "text": "❌ Duplicate detector not available"
                            }]
                        
                        stats = await self.duplicate_detector.get_duplicate_statistics(days=days)
                        
                        if 'error' in stats:
                            return [{
                                "type": "text",
                                "text": f"❌ Statistics error: {stats['error']}"
                            }]
                        
                        result_text = f"📊 Duplicate Detection Statistics (Last {days} days)\n\n"
                        result_text += f"📈 Total conversations: {stats['total_conversations']}\n"
                        result_text += f"🤖 Auto-stored: {stats['auto_stored']}\n"
                        result_text += f"👤 Manual-stored: {stats['manual_stored']}\n"
                        result_text += f"🎯 High confidence (≥0.8): {stats['high_confidence']}\n"
                        result_text += f"⚠️  Low confidence (<0.5): {stats['low_confidence']}\n"
                        result_text += f"🔍 With duplicates detected: {stats['with_duplicates_detected']}\n\n"
                        result_text += f"📊 Average confidence: {stats['average_confidence']:.2f}\n"
                        result_text += f"⚡ Storage efficiency: {stats['storage_efficiency']:.1%}\n\n"
                        
                        # Add interpretation
                        if stats['storage_efficiency'] >= 0.7:
                            result_text += "✅ Storage efficiency is good - most stored content is high confidence."
                        elif stats['storage_efficiency'] >= 0.5:
                            result_text += "⚠️  Storage efficiency is moderate - consider adjusting confidence thresholds."
                        else:
                            result_text += "❌ Storage efficiency is low - many low-confidence memories are being stored."
                        
                        return [{
                            "type": "text",
                            "text": result_text
                        }]
                        
                    except Exception as e:
                        logger.error(f"Error getting statistics: {e}")
                        return [{
                            "type": "text",
                            "text": f"❌ Error getting statistics: {str(e)}"
                        }]
                
                elif name == "get_optimization_config":
                    try:
                        if not self.duplicate_detector:
                            return [{
                                "type": "text",
                                "text": "❌ Duplicate detector not available"
                            }]
                        
                        config = self.duplicate_detector.get_optimization_config()
                        
                        result_text = "⚙️  Duplicate Detection & Optimization Configuration\n\n"
                        
                        result_text += "🎯 Similarity Thresholds:\n"
                        for threshold_type, value in config['similarity_thresholds'].items():
                            result_text += f"  • {threshold_type}: {value:.2f}\n"
                        result_text += "\n"
                        
                        result_text += "📏 Content Filters:\n"
                        result_text += f"  • Minimum content length: {config['min_content_length']} characters\n"
                        result_text += f"  • Minimum confidence for storage: {config['min_confidence_for_storage']:.2f}\n"
                        result_text += f"  • Max similar memories per day: {config['max_similar_memories_per_day']}\n\n"
                        
                        result_text += "🧹 Cleanup Thresholds:\n"
                        for threshold_type, value in config['cleanup_thresholds'].items():
                            result_text += f"  • {threshold_type}: {value} days\n"
                        
                        return [{
                            "type": "text",
                            "text": result_text
                        }]
                        
                    except Exception as e:
                        logger.error(f"Error getting config: {e}")
                        return [{
                            "type": "text",
                            "text": f"❌ Error getting config: {str(e)}"
                        }]
                
                elif name == "update_optimization_config":
                    config_updates = arguments.get("config", {})
                    
                    if not config_updates:
                        return [{
                            "type": "text",
                            "text": "❌ Missing required parameter: config"
                        }]
                    
                    try:
                        if not self.duplicate_detector:
                            return [{
                                "type": "text",
                                "text": "❌ Duplicate detector not available"
                            }]
                        
                        # Get current config for comparison
                        old_config = self.duplicate_detector.get_optimization_config()
                        
                        # Update configuration
                        self.duplicate_detector.update_optimization_config(config_updates)
                        
                        # Get new config
                        new_config = self.duplicate_detector.get_optimization_config()
                        
                        result_text = "✅ Configuration updated successfully!\n\n"
                        result_text += "📝 Changes made:\n"
                        
                        # Show what changed
                        changes_found = False
                        for section, values in config_updates.items():
                            if section in old_config:
                                if isinstance(values, dict):
                                    for key, new_value in values.items():
                                        if key in old_config[section]:
                                            old_value = old_config[section][key]
                                            if old_value != new_value:
                                                result_text += f"  • {section}.{key}: {old_value} → {new_value}\n"
                                                changes_found = True
                                else:
                                    old_value = old_config.get(section)
                                    if old_value != values:
                                        result_text += f"  • {section}: {old_value} → {values}\n"
                                        changes_found = True
                        
                        if not changes_found:
                            result_text += "  • No changes detected (values may already be set)\n"
                        
                        result_text += "\n💡 New configuration is now active for all future duplicate detection operations."
                        
                        return [{
                            "type": "text",
                            "text": result_text
                        }]
                        
                    except Exception as e:
                        logger.error(f"Error updating config: {e}")
                        return [{
                            "type": "text",
                            "text": f"❌ Error updating config: {str(e)}"
                        }]
                
                elif name == "analyze_session":
                    conversation_ids = arguments.get("conversation_ids", [])
                    tool_name = arguments.get("tool_name", "")
                    hours_back = arguments.get("hours_back", 24)
                    session_context = arguments.get("session_context", {})
                    
                    try:
                        if not self.session_analyzer:
                            return [{
                                "type": "text",
                                "text": "❌ Session analyzer not available"
                            }]
                        
                        conversations = []
                        
                        # If specific conversation IDs provided, use those
                        if conversation_ids:
                            for conv_id in conversation_ids:
                                conv = self.conversation_repo.get_by_id(conv_id)
                                if conv:
                                    conversations.append(conv)
                        else:
                            # Otherwise, get recent conversations
                            if tool_name:
                                conversations = self.conversation_repo.get_recent_by_tool(
                                    tool_name, hours=hours_back, limit=20
                                )
                            else:
                                conversations = self.conversation_repo.get_recent(
                                    hours=hours_back, limit=20
                                )
                        
                        if not conversations:
                            return [{
                                "type": "text",
                                "text": "❌ No conversations found for session analysis"
                            }]
                        
                        # Analyze the session
                        session_analysis = await self.session_analyzer.analyze_session(
                            conversations, session_context
                        )
                        
                        # Format the results
                        result_text = f"🔍 **Session Analysis Complete**\n\n"
                        result_text += f"📊 **Session Overview**\n"
                        result_text += f"• Session ID: {session_analysis['session_id']}\n"
                        result_text += f"• Conversations: {session_analysis['conversation_count']}\n"
                        result_text += f"• Duration: {session_analysis['time_span']}\n"
                        result_text += f"• Value: {session_analysis['session_summary']['session_value']['classification']}\n\n"
                        
                        # Key themes
                        if session_analysis['recurring_themes']:
                            result_text += f"🎯 **Key Themes**\n"
                            for theme in session_analysis['recurring_themes'][:5]:
                                result_text += f"• {theme['term']} (mentioned {theme['frequency']} times)\n"
                            result_text += "\n"
                        
                        # Key insights
                        if session_analysis['key_insights']:
                            result_text += f"💡 **Key Insights**\n"
                            for insight in session_analysis['key_insights'][:3]:
                                result_text += f"• **{insight['title']}**: {insight['description']}\n"
                            result_text += "\n"
                        
                        # Problem solutions
                        if session_analysis['problem_solutions']:
                            result_text += f"🔧 **Problems Solved**: {len(session_analysis['problem_solutions'])}\n"
                            avg_time = sum(ps['time_to_resolution'] for ps in session_analysis['problem_solutions']) / len(session_analysis['problem_solutions'])
                            result_text += f"• Average resolution time: {avg_time:.1f} minutes\n\n"
                        
                        # Storage recommendation
                        storage_rec = session_analysis['storage_recommendation']
                        if storage_rec['should_store']:
                            result_text += f"💾 **Storage Recommendation**: {'Auto-store' if storage_rec['auto_store'] else 'Suggest storage'}\n"
                            result_text += f"• Confidence: {storage_rec['confidence']:.1%}\n"
                            result_text += f"• Reasons: {', '.join(storage_rec['reasons'])}\n\n"
                        
                        # Recommendations
                        if session_analysis['session_summary']['recommended_actions']:
                            result_text += f"📋 **Recommended Actions**\n"
                            for action in session_analysis['session_summary']['recommended_actions'][:3]:
                                result_text += f"• {action}\n"
                        
                        return [{
                            "type": "text",
                            "text": result_text
                        }]
                        
                    except Exception as e:
                        logger.error(f"Error analyzing session: {e}")
                        return [{
                            "type": "text",
                            "text": f"❌ Error analyzing session: {str(e)}"
                        }]
                
                elif name == "get_session_conversations":
                    reference_conversation_id = arguments.get("reference_conversation_id")
                    time_window_hours = arguments.get("time_window_hours", 4)
                    max_conversations = arguments.get("max_conversations", 10)
                    similarity_threshold = arguments.get("similarity_threshold", 0.3)
                    
                    if not reference_conversation_id:
                        return [{
                            "type": "text",
                            "text": "❌ Missing required parameter: reference_conversation_id"
                        }]
                    
                    try:
                        # Get the reference conversation
                        ref_conv = self.conversation_repo.get_by_id(reference_conversation_id)
                        if not ref_conv:
                            return [{
                                "type": "text",
                                "text": f"❌ Reference conversation not found: {reference_conversation_id}"
                            }]
                        
                        # Get conversations within time window
                        from datetime import timedelta
                        start_time = ref_conv.timestamp - timedelta(hours=time_window_hours)
                        end_time = ref_conv.timestamp + timedelta(hours=time_window_hours)
                        
                        # Get all conversations in the time window
                        all_conversations = self.conversation_repo.get_by_time_range(
                            start_time, end_time, limit=50
                        )
                        
                        # Filter by similarity and build session
                        session_conversations = [ref_conv]
                        
                        for conv in all_conversations:
                            if conv.id == reference_conversation_id:
                                continue
                            
                            # Calculate similarity with reference conversation
                            if self.session_analyzer:
                                similarity = self.session_analyzer._calculate_content_similarity(
                                    ref_conv.content, conv.content
                                )
                                
                                if similarity >= similarity_threshold:
                                    session_conversations.append(conv)
                        
                        # Sort by timestamp and limit
                        session_conversations.sort(key=lambda c: c.timestamp)
                        session_conversations = session_conversations[:max_conversations]
                        
                        # Format results
                        result_text = f"🔗 **Session Conversations Found**\n\n"
                        result_text += f"📊 **Summary**\n"
                        result_text += f"• Reference: {reference_conversation_id}\n"
                        result_text += f"• Time window: {time_window_hours} hours\n"
                        result_text += f"• Found: {len(session_conversations)} conversations\n"
                        result_text += f"• Similarity threshold: {similarity_threshold:.1%}\n\n"
                        
                        result_text += f"💬 **Conversations**\n"
                        for i, conv in enumerate(session_conversations, 1):
                            is_ref = " (reference)" if conv.id == reference_conversation_id else ""
                            result_text += f"{i}. **{conv.id}**{is_ref}\n"
                            result_text += f"   • Tool: {conv.tool_name}\n"
                            result_text += f"   • Time: {conv.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                            result_text += f"   • Preview: {conv.content[:100]}...\n\n"
                        
                        result_text += f"💡 **Next Steps**\n"
                        result_text += f"• Use `analyze_session` with these conversation IDs for detailed analysis\n"
                        result_text += f"• Conversation IDs: {', '.join(c.id for c in session_conversations)}"
                        
                        return [{
                            "type": "text",
                            "text": result_text
                        }]
                        
                    except Exception as e:
                        logger.error(f"Error getting session conversations: {e}")
                        return [{
                            "type": "text",
                            "text": f"❌ Error getting session conversations: {str(e)}"
                        }]
                
                elif name == "create_session_summary":
                    session_analysis = arguments.get("session_analysis")
                    tool_name = arguments.get("tool_name", "session_analyzer")
                    force_storage = arguments.get("force_storage", False)
                    
                    if not session_analysis:
                        return [{
                            "type": "text",
                            "text": "❌ Missing required parameter: session_analysis"
                        }]
                    
                    try:
                        if not self.session_analyzer:
                            return [{
                                "type": "text",
                                "text": "❌ Session analyzer not available"
                            }]
                        
                        # Check if storage is recommended or forced
                        storage_rec = session_analysis.get('storage_recommendation', {})
                        should_store = storage_rec.get('should_store', False) or force_storage
                        
                        if not should_store:
                            return [{
                                "type": "text",
                                "text": f"❌ Session analysis does not meet storage criteria\n"
                                       f"• Confidence: {storage_rec.get('confidence', 0):.1%}\n"
                                       f"• Reasons: {', '.join(storage_rec.get('reasons', ['No reasons provided']))}\n"
                                       f"• Use force_storage=true to override"
                            }]
                        
                        # Create the session memory
                        memory_id = await self.session_analyzer.create_session_memory(
                            session_analysis, tool_name
                        )
                        
                        if memory_id:
                            result_text = f"✅ **Session Summary Created**\n\n"
                            result_text += f"🆔 **Memory ID**: {memory_id}\n"
                            result_text += f"📊 **Session**: {session_analysis.get('session_id', 'Unknown')}\n"
                            result_text += f"💾 **Storage Type**: {'Auto-stored' if storage_rec.get('auto_store') else 'Manual storage'}\n"
                            result_text += f"🎯 **Confidence**: {storage_rec.get('confidence', 0):.1%}\n\n"
                            
                            result_text += f"📝 **Summary Content**\n"
                            result_text += f"• Conversations analyzed: {session_analysis.get('conversation_count', 0)}\n"
                            result_text += f"• Key insights: {len(session_analysis.get('key_insights', []))}\n"
                            result_text += f"• Problems solved: {len(session_analysis.get('problem_solutions', []))}\n"
                            result_text += f"• Session value: {session_analysis.get('session_summary', {}).get('session_value', {}).get('classification', 'Unknown')}\n\n"
                            
                            result_text += f"🔍 **Searchable Tags**: {', '.join(storage_rec.get('suggested_tags', []))}\n\n"
                            result_text += f"💡 **Next Steps**\n"
                            result_text += f"• Use `link_session_memories` to create cross-references\n"
                            result_text += f"• Session summary is now searchable with `search_memory`"
                            
                            return [{
                                "type": "text",
                                "text": result_text
                            }]
                        else:
                            return [{
                                "type": "text",
                                "text": "❌ Failed to create session summary - storage operation failed"
                            }]
                        
                    except Exception as e:
                        logger.error(f"Error creating session summary: {e}")
                        return [{
                            "type": "text",
                            "text": f"❌ Error creating session summary: {str(e)}"
                        }]
                
                elif name == "link_session_memories":
                    session_memory_id = arguments.get("session_memory_id")
                    conversation_ids = arguments.get("conversation_ids", [])
                    relationship_type = arguments.get("relationship_type", "session_member")
                    
                    if not session_memory_id:
                        return [{
                            "type": "text",
                            "text": "❌ Missing required parameter: session_memory_id"
                        }]
                    
                    if not conversation_ids:
                        return [{
                            "type": "text",
                            "text": "❌ Missing required parameter: conversation_ids"
                        }]
                    
                    try:
                        if not self.context_manager:
                            return [{
                                "type": "text",
                                "text": "❌ Context manager not available"
                            }]
                        
                        # Verify session memory exists
                        session_memory = self.conversation_repo.get_by_id(session_memory_id)
                        if not session_memory:
                            return [{
                                "type": "text",
                                "text": f"❌ Session memory not found: {session_memory_id}"
                            }]
                        
                        # Create links to all conversations in the session
                        created_links = []
                        failed_links = []
                        
                        for conv_id in conversation_ids:
                            conv = self.conversation_repo.get_by_id(conv_id)
                            if conv:
                                # Create bidirectional links
                                links = await self.context_manager.create_context_links(
                                    session_memory_id,
                                    [(conv, relationship_type, 0.9)]  # High confidence for session relationships
                                )
                                
                                # Also create reverse link
                                reverse_links = await self.context_manager.create_context_links(
                                    conv_id,
                                    [(session_memory, "session_summary", 0.9)]
                                )
                                
                                created_links.extend(links)
                                created_links.extend(reverse_links)
                            else:
                                failed_links.append(conv_id)
                        
                        # Format results
                        result_text = f"🔗 **Session Memory Links Created**\n\n"
                        result_text += f"📊 **Summary**\n"
                        result_text += f"• Session memory: {session_memory_id}\n"
                        result_text += f"• Target conversations: {len(conversation_ids)}\n"
                        result_text += f"• Links created: {len(created_links)}\n"
                        result_text += f"• Relationship type: {relationship_type}\n\n"
                        
                        if created_links:
                            result_text += f"✅ **Successfully Linked**\n"
                            linked_convs = set()
                            for link in created_links:
                                if link.source_conversation_id != session_memory_id:
                                    linked_convs.add(link.source_conversation_id)
                                if link.target_conversation_id != session_memory_id:
                                    linked_convs.add(link.target_conversation_id)
                            
                            for conv_id in list(linked_convs)[:5]:  # Show first 5
                                result_text += f"• {conv_id}\n"
                            
                            if len(linked_convs) > 5:
                                result_text += f"• ... and {len(linked_convs) - 5} more\n"
                            result_text += "\n"
                        
                        if failed_links:
                            result_text += f"❌ **Failed to Link**\n"
                            for conv_id in failed_links:
                                result_text += f"• {conv_id} (not found)\n"
                            result_text += "\n"
                        
                        result_text += f"💡 **Benefits**\n"
                        result_text += f"• Session summary and individual conversations are now cross-referenced\n"
                        result_text += f"• Use `find_related_context` to navigate between session and conversations\n"
                        result_text += f"• Enhanced context retrieval for future queries"
                        
                        return [{
                            "type": "text",
                            "text": result_text
                        }]
                        
                    except Exception as e:
                        logger.error(f"Error linking session memories: {e}")
                        return [{
                            "type": "text",
                            "text": f"❌ Error linking session memories: {str(e)}"
                        }]
                
                elif name == "review_auto_stored_memories":
                    limit = arguments.get("limit", 20)
                    offset = arguments.get("offset", 0)
                    category_filter = arguments.get("category_filter")
                    confidence_min = arguments.get("confidence_min", 0.0)
                    confidence_max = arguments.get("confidence_max", 1.0)
                    days_back = arguments.get("days_back", 30)
                    tool_filter = arguments.get("tool_filter")
                    project_filter = arguments.get("project_filter")
                    include_metadata = arguments.get("include_metadata", True)
                    
                    try:
                        from datetime import datetime, timedelta
                        cutoff_time = datetime.utcnow() - timedelta(days=days_back)
                        
                        # Build query for auto-stored memories
                        with self.conversation_repo.db_manager.get_session() as session:
                            from models.database import Conversation
                            from sqlalchemy import and_, or_, func
                            
                            query = session.query(Conversation).filter(
                                and_(
                                    Conversation.timestamp >= cutoff_time,
                                    Conversation.tags.like('%auto_stored%')
                                )
                            )
                            
                            # Apply filters
                            if category_filter:
                                query = query.filter(Conversation.tags.like(f'%{category_filter}%'))
                            
                            if tool_filter:
                                query = query.filter(Conversation.tool_name == tool_filter.lower())
                            
                            if project_filter:
                                query = query.filter(Conversation.project_id == project_filter)
                            
                            # Filter by confidence if metadata exists
                            if confidence_min > 0.0 or confidence_max < 1.0:
                                # This is a simplified filter - in practice, we'd need to parse JSON
                                pass  # Could be enhanced with JSON queries
                            
                            # Get total count for pagination info
                            total_count = query.count()
                            
                            # Apply pagination and ordering
                            memories = query.order_by(Conversation.timestamp.desc()).offset(offset).limit(limit).all()
                        
                        if not memories:
                            return [{
                                "type": "text",
                                "text": f"📚 No auto-stored memories found matching your criteria.\n\n🔍 **Search Criteria:**\n• Days back: {days_back}\n• Category: {category_filter or 'All'}\n• Tool: {tool_filter or 'All'}\n• Project: {project_filter or 'All'}"
                            }]
                        
                        # Format results
                        result_text = f"📚 **Auto-Stored Memories Review**\n\n"
                        result_text += f"📊 **Summary**\n"
                        result_text += f"• Total found: {total_count}\n"
                        result_text += f"• Showing: {len(memories)} (offset: {offset})\n"
                        result_text += f"• Time range: Last {days_back} days\n"
                        if category_filter:
                            result_text += f"• Category filter: {category_filter}\n"
                        if tool_filter:
                            result_text += f"• Tool filter: {tool_filter}\n"
                        if project_filter:
                            result_text += f"• Project filter: {project_filter}\n"
                        result_text += "\n"
                        
                        for i, memory in enumerate(memories, offset + 1):
                            result_text += f"**{i}. Memory {memory.id}**\n"
                            result_text += f"📅 {memory.timestamp.strftime('%Y-%m-%d %H:%M:%S')} | 🔧 {memory.tool_name}\n"
                            
                            if memory.project_id:
                                result_text += f"📁 Project: {memory.project_id}\n"
                            
                            if memory.tags:
                                result_text += f"🏷️  Tags: {memory.tags}\n"
                            
                            # Show confidence and category from metadata
                            if memory.conversation_metadata and include_metadata:
                                confidence = memory.conversation_metadata.get('confidence')
                                category = memory.conversation_metadata.get('analysis_category')
                                reason = memory.conversation_metadata.get('storage_reason')
                                
                                if confidence:
                                    result_text += f"🎯 Confidence: {confidence:.1%}\n"
                                if category:
                                    result_text += f"📂 Category: {category}\n"
                                if reason:
                                    result_text += f"💭 Reason: {reason}\n"
                            
                            # Content preview
                            content_preview = memory.content[:200]
                            result_text += f"💬 Content: {content_preview}{'...' if len(memory.content) > 200 else ''}\n"
                            
                            if include_metadata and memory.conversation_metadata:
                                result_text += f"📋 Metadata: {json.dumps(memory.conversation_metadata, indent=2)}\n"
                            
                            result_text += "\n" + "="*50 + "\n\n"
                        
                        # Pagination info
                        if total_count > offset + limit:
                            result_text += f"📄 **Pagination**\n"
                            result_text += f"• Use offset={offset + limit} to see next {limit} memories\n"
                            result_text += f"• Remaining: {total_count - offset - limit} memories\n"
                        
                        return [{
                            "type": "text",
                            "text": result_text
                        }]
                        
                    except Exception as e:
                        logger.error(f"Error reviewing auto-stored memories: {e}")
                        return [{
                            "type": "text",
                            "text": f"❌ Error reviewing memories: {str(e)}"
                        }]
                
                elif name == "edit_memory":
                    memory_id = arguments.get("memory_id")
                    new_content = arguments.get("new_content")
                    new_tags = arguments.get("new_tags")
                    add_tags = arguments.get("add_tags", [])
                    remove_tags = arguments.get("remove_tags", [])
                    metadata_updates = arguments.get("metadata_updates", {})
                    update_search_index = arguments.get("update_search_index", True)
                    
                    if not memory_id:
                        return [{
                            "type": "text",
                            "text": "❌ Missing required parameter: memory_id"
                        }]
                    
                    try:
                        # Get existing memory
                        memory = self.conversation_repo.get_by_id(memory_id)
                        if not memory:
                            return [{
                                "type": "text",
                                "text": f"❌ Memory not found: {memory_id}"
                            }]
                        
                        # Prepare update data
                        from models.schemas import ConversationUpdate
                        update_data = ConversationUpdate()
                        
                        # Update content if provided
                        if new_content:
                            update_data.content = new_content
                        
                        # Handle tags updates
                        current_tags = memory.tags_list if memory.tags else []
                        
                        if new_tags is not None:
                            # Replace all tags
                            updated_tags = new_tags
                        else:
                            # Add/remove tags from existing
                            updated_tags = current_tags.copy()
                            
                            # Add new tags
                            for tag in add_tags:
                                if tag not in updated_tags:
                                    updated_tags.append(tag)
                            
                            # Remove tags
                            for tag in remove_tags:
                                if tag in updated_tags:
                                    updated_tags.remove(tag)
                        
                        update_data.tags = updated_tags
                        
                        # Update metadata
                        if metadata_updates:
                            current_metadata = memory.conversation_metadata or {}
                            updated_metadata = current_metadata.copy()
                            updated_metadata.update(metadata_updates)
                            updated_metadata['last_edited'] = datetime.now().isoformat()
                            update_data.conversation_metadata = updated_metadata
                        
                        # Perform update
                        updated_memory = self.conversation_repo.update(memory_id, update_data)
                        
                        if not updated_memory:
                            return [{
                                "type": "text",
                                "text": f"❌ Failed to update memory: {memory_id}"
                            }]
                        
                        # Update search index if requested
                        if update_search_index and new_content:
                            search_metadata = {
                                "conversation_id": updated_memory.id,
                                "tool_name": updated_memory.tool_name,
                                "project_id": updated_memory.project_id,
                                "timestamp": updated_memory.timestamp.isoformat(),
                                "tags": updated_tags,
                                "auto_stored": "auto_stored" in updated_tags,
                                "confidence": updated_memory.conversation_metadata.get('confidence', 1.0) if updated_memory.conversation_metadata else 1.0,
                                "category": updated_memory.conversation_metadata.get('analysis_category', 'manual') if updated_memory.conversation_metadata else 'manual'
                            }
                            
                            await self.search_engine.add_document(
                                content=updated_memory.content,
                                metadata=search_metadata,
                                document_id=updated_memory.id
                            )
                        
                        # Format success response
                        result_text = f"✅ **Memory Updated Successfully**\n\n"
                        result_text += f"🔗 **Memory ID:** {memory_id}\n"
                        result_text += f"📅 **Last Modified:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                        
                        result_text += f"📝 **Changes Made:**\n"
                        if new_content:
                            result_text += f"• Content updated ({len(new_content)} characters)\n"
                        if new_tags is not None:
                            result_text += f"• Tags replaced: {', '.join(updated_tags) if updated_tags else 'None'}\n"
                        elif add_tags or remove_tags:
                            if add_tags:
                                result_text += f"• Tags added: {', '.join(add_tags)}\n"
                            if remove_tags:
                                result_text += f"• Tags removed: {', '.join(remove_tags)}\n"
                        if metadata_updates:
                            result_text += f"• Metadata updated: {', '.join(metadata_updates.keys())}\n"
                        if update_search_index and new_content:
                            result_text += f"• Search index updated\n"
                        
                        result_text += f"\n🏷️  **Current Tags:** {', '.join(updated_tags) if updated_tags else 'None'}\n"
                        result_text += f"💬 **Content Preview:** {updated_memory.content[:200]}{'...' if len(updated_memory.content) > 200 else ''}"
                        
                        return [{
                            "type": "text",
                            "text": result_text
                        }]
                        
                    except Exception as e:
                        logger.error(f"Error editing memory: {e}")
                        return [{
                            "type": "text",
                            "text": f"❌ Error editing memory: {str(e)}"
                        }]
                
                elif name == "delete_memory":
                    memory_id = arguments.get("memory_id")
                    confirm = arguments.get("confirm", False)
                    remove_from_search = arguments.get("remove_from_search", True)
                    
                    if not memory_id:
                        return [{
                            "type": "text",
                            "text": "❌ Missing required parameter: memory_id"
                        }]
                    
                    if not confirm:
                        return [{
                            "type": "text",
                            "text": f"⚠️  **Deletion Confirmation Required**\n\nYou are about to delete memory: {memory_id}\n\n🚨 **This action cannot be undone!**\n\nTo proceed, call this tool again with `confirm: true`"
                        }]
                    
                    try:
                        # Get memory details before deletion
                        memory = self.conversation_repo.get_by_id(memory_id)
                        if not memory:
                            return [{
                                "type": "text",
                                "text": f"❌ Memory not found: {memory_id}"
                            }]
                        
                        # Store details for confirmation message
                        memory_details = {
                            "id": memory.id,
                            "tool_name": memory.tool_name,
                            "timestamp": memory.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                            "content_preview": memory.content[:100],
                            "tags": memory.tags_list if memory.tags else [],
                            "project_id": memory.project_id
                        }
                        
                        # Delete from database
                        success = self.conversation_repo.delete(memory_id)
                        
                        if not success:
                            return [{
                                "type": "text",
                                "text": f"❌ Failed to delete memory: {memory_id}"
                            }]
                        
                        # Remove from search index if requested
                        if remove_from_search:
                            try:
                                await self.search_engine.remove_document(memory_id)
                            except Exception as e:
                                logger.warning(f"Failed to remove from search index: {e}")
                        
                        # Format success response
                        result_text = f"✅ **Memory Deleted Successfully**\n\n"
                        result_text += f"🗑️  **Deleted Memory Details:**\n"
                        result_text += f"• ID: {memory_details['id']}\n"
                        result_text += f"• Tool: {memory_details['tool_name']}\n"
                        result_text += f"• Created: {memory_details['timestamp']}\n"
                        if memory_details['project_id']:
                            result_text += f"• Project: {memory_details['project_id']}\n"
                        if memory_details['tags']:
                            result_text += f"• Tags: {', '.join(memory_details['tags'])}\n"
                        result_text += f"• Content: {memory_details['content_preview']}...\n\n"
                        
                        if remove_from_search:
                            result_text += f"🔍 **Search index updated** - Memory removed from search results\n\n"
                        
                        result_text += f"💡 **Note:** This memory is permanently deleted and cannot be recovered."
                        
                        return [{
                            "type": "text",
                            "text": result_text
                        }]
                        
                    except Exception as e:
                        logger.error(f"Error deleting memory: {e}")
                        return [{
                            "type": "text",
                            "text": f"❌ Error deleting memory: {str(e)}"
                        }]
                
                elif name == "bulk_manage_memories":
                    memory_ids = arguments.get("memory_ids", [])
                    operation = arguments.get("operation")
                    tags = arguments.get("tags", [])
                    new_category = arguments.get("new_category")
                    export_format = arguments.get("export_format", "json")
                    confirm = arguments.get("confirm", False)
                    
                    if not memory_ids:
                        return [{
                            "type": "text",
                            "text": "❌ Missing required parameter: memory_ids"
                        }]
                    
                    if not operation:
                        return [{
                            "type": "text",
                            "text": "❌ Missing required parameter: operation"
                        }]
                    
                    # Check confirmation for destructive operations
                    if operation == "delete" and not confirm:
                        return [{
                            "type": "text",
                            "text": f"⚠️  **Bulk Deletion Confirmation Required**\n\nYou are about to delete {len(memory_ids)} memories:\n{', '.join(memory_ids[:5])}{'...' if len(memory_ids) > 5 else ''}\n\n🚨 **This action cannot be undone!**\n\nTo proceed, call this tool again with `confirm: true`"
                        }]
                    
                    try:
                        results = {
                            "successful": [],
                            "failed": [],
                            "details": []
                        }
                        
                        if operation == "delete":
                            for memory_id in memory_ids:
                                try:
                                    memory = self.conversation_repo.get_by_id(memory_id)
                                    if memory:
                                        success = self.conversation_repo.delete(memory_id)
                                        if success:
                                            results["successful"].append(memory_id)
                                            # Remove from search index
                                            try:
                                                await self.search_engine.remove_document(memory_id)
                                            except Exception:
                                                pass  # Non-critical
                                        else:
                                            results["failed"].append(memory_id)
                                    else:
                                        results["failed"].append(memory_id)
                                except Exception as e:
                                    results["failed"].append(memory_id)
                                    results["details"].append(f"{memory_id}: {str(e)}")
                        
                        elif operation == "add_tags":
                            if not tags:
                                return [{
                                    "type": "text",
                                    "text": "❌ Missing tags parameter for add_tags operation"
                                }]
                            
                            for memory_id in memory_ids:
                                try:
                                    memory = self.conversation_repo.get_by_id(memory_id)
                                    if memory:
                                        current_tags = memory.tags_list if memory.tags else []
                                        updated_tags = current_tags.copy()
                                        
                                        for tag in tags:
                                            if tag not in updated_tags:
                                                updated_tags.append(tag)
                                        
                                        from models.schemas import ConversationUpdate
                                        update_data = ConversationUpdate(tags=updated_tags)
                                        updated_memory = self.conversation_repo.update(memory_id, update_data)
                                        
                                        if updated_memory:
                                            results["successful"].append(memory_id)
                                        else:
                                            results["failed"].append(memory_id)
                                    else:
                                        results["failed"].append(memory_id)
                                except Exception as e:
                                    results["failed"].append(memory_id)
                                    results["details"].append(f"{memory_id}: {str(e)}")
                        
                        elif operation == "remove_tags":
                            if not tags:
                                return [{
                                    "type": "text",
                                    "text": "❌ Missing tags parameter for remove_tags operation"
                                }]
                            
                            for memory_id in memory_ids:
                                try:
                                    memory = self.conversation_repo.get_by_id(memory_id)
                                    if memory:
                                        current_tags = memory.tags_list if memory.tags else []
                                        updated_tags = current_tags.copy()
                                        
                                        for tag in tags:
                                            if tag in updated_tags:
                                                updated_tags.remove(tag)
                                        
                                        from models.schemas import ConversationUpdate
                                        update_data = ConversationUpdate(tags=updated_tags)
                                        updated_memory = self.conversation_repo.update(memory_id, update_data)
                                        
                                        if updated_memory:
                                            results["successful"].append(memory_id)
                                        else:
                                            results["failed"].append(memory_id)
                                    else:
                                        results["failed"].append(memory_id)
                                except Exception as e:
                                    results["failed"].append(memory_id)
                                    results["details"].append(f"{memory_id}: {str(e)}")
                        
                        elif operation == "update_category":
                            if not new_category:
                                return [{
                                    "type": "text",
                                    "text": "❌ Missing new_category parameter for update_category operation"
                                }]
                            
                            for memory_id in memory_ids:
                                try:
                                    memory = self.conversation_repo.get_by_id(memory_id)
                                    if memory:
                                        current_metadata = memory.conversation_metadata or {}
                                        updated_metadata = current_metadata.copy()
                                        updated_metadata['analysis_category'] = new_category
                                        updated_metadata['category_updated'] = datetime.now().isoformat()
                                        
                                        from models.schemas import ConversationUpdate
                                        update_data = ConversationUpdate(conversation_metadata=updated_metadata)
                                        updated_memory = self.conversation_repo.update(memory_id, update_data)
                                        
                                        if updated_memory:
                                            results["successful"].append(memory_id)
                                        else:
                                            results["failed"].append(memory_id)
                                    else:
                                        results["failed"].append(memory_id)
                                except Exception as e:
                                    results["failed"].append(memory_id)
                                    results["details"].append(f"{memory_id}: {str(e)}")
                        
                        elif operation == "export":
                            # Get all memories for export
                            export_data = []
                            for memory_id in memory_ids:
                                try:
                                    memory = self.conversation_repo.get_by_id(memory_id)
                                    if memory:
                                        memory_data = {
                                            "id": memory.id,
                                            "tool_name": memory.tool_name,
                                            "project_id": memory.project_id,
                                            "timestamp": memory.timestamp.isoformat(),
                                            "content": memory.content,
                                            "metadata": memory.conversation_metadata,
                                            "tags": memory.tags_list if memory.tags else []
                                        }
                                        export_data.append(memory_data)
                                        results["successful"].append(memory_id)
                                    else:
                                        results["failed"].append(memory_id)
                                except Exception as e:
                                    results["failed"].append(memory_id)
                                    results["details"].append(f"{memory_id}: {str(e)}")
                            
                            # Format export data
                            if export_format == "json":
                                export_content = json.dumps(export_data, indent=2)
                            elif export_format == "csv":
                                import csv
                                import io
                                output = io.StringIO()
                                if export_data:
                                    fieldnames = ["id", "tool_name", "project_id", "timestamp", "content", "tags"]
                                    writer = csv.DictWriter(output, fieldnames=fieldnames)
                                    writer.writeheader()
                                    for item in export_data:
                                        row = {k: v for k, v in item.items() if k in fieldnames}
                                        row["tags"] = ", ".join(row.get("tags", []))
                                        writer.writerow(row)
                                export_content = output.getvalue()
                            elif export_format == "markdown":
                                export_content = "# Memory Export\n\n"
                                for item in export_data:
                                    export_content += f"## {item['id']}\n\n"
                                    export_content += f"**Tool:** {item['tool_name']}\n"
                                    export_content += f"**Date:** {item['timestamp']}\n"
                                    if item['project_id']:
                                        export_content += f"**Project:** {item['project_id']}\n"
                                    if item['tags']:
                                        export_content += f"**Tags:** {', '.join(item['tags'])}\n"
                                    export_content += f"\n**Content:**\n{item['content']}\n\n---\n\n"
                            
                            # Return export content
                            result_text = f"📦 **Bulk Export Complete**\n\n"
                            result_text += f"📊 **Summary:**\n"
                            result_text += f"• Exported: {len(results['successful'])} memories\n"
                            result_text += f"• Failed: {len(results['failed'])} memories\n"
                            result_text += f"• Format: {export_format}\n\n"
                            
                            if results["failed"]:
                                result_text += f"❌ **Failed exports:** {', '.join(results['failed'])}\n\n"
                            
                            result_text += f"📄 **Export Data:**\n```{export_format}\n{export_content[:2000]}{'...' if len(export_content) > 2000 else ''}\n```"
                            
                            return [{
                                "type": "text",
                                "text": result_text
                            }]
                        
                        else:
                            return [{
                                "type": "text",
                                "text": f"❌ Unknown operation: {operation}"
                            }]
                        
                        # Format results for non-export operations
                        result_text = f"✅ **Bulk {operation.title()} Complete**\n\n"
                        result_text += f"📊 **Summary:**\n"
                        result_text += f"• Successful: {len(results['successful'])} memories\n"
                        result_text += f"• Failed: {len(results['failed'])} memories\n"
                        result_text += f"• Operation: {operation}\n\n"
                        
                        if results["successful"]:
                            result_text += f"✅ **Successful:** {', '.join(results['successful'][:10])}{'...' if len(results['successful']) > 10 else ''}\n\n"
                        
                        if results["failed"]:
                            result_text += f"❌ **Failed:** {', '.join(results['failed'])}\n"
                            if results["details"]:
                                result_text += f"**Error details:**\n"
                                for detail in results["details"][:5]:
                                    result_text += f"• {detail}\n"
                                if len(results["details"]) > 5:
                                    result_text += f"• ... and {len(results['details']) - 5} more errors\n"
                        
                        return [{
                            "type": "text",
                            "text": result_text
                        }]
                        
                    except Exception as e:
                        logger.error(f"Error in bulk operation: {e}")
                        return [{
                            "type": "text",
                            "text": f"❌ Error in bulk operation: {str(e)}"
                        }]
                
                elif name == "export_memories":
                    format_type = arguments.get("format", "json")
                    category_filter = arguments.get("category_filter")
                    confidence_min = arguments.get("confidence_min", 0.0)
                    days_back = arguments.get("days_back", 30)
                    tool_filter = arguments.get("tool_filter")
                    project_filter = arguments.get("project_filter")
                    auto_stored_only = arguments.get("auto_stored_only", False)
                    include_metadata = arguments.get("include_metadata", True)
                    output_file = arguments.get("output_file")
                    
                    try:
                        from datetime import datetime, timedelta
                        cutoff_time = datetime.utcnow() - timedelta(days=days_back)
                        
                        # Build query
                        with self.conversation_repo.db_manager.get_session() as session:
                            from models.database import Conversation
                            from sqlalchemy import and_
                            
                            query = session.query(Conversation).filter(
                                Conversation.timestamp >= cutoff_time
                            )
                            
                            # Apply filters
                            if auto_stored_only:
                                query = query.filter(Conversation.tags.like('%auto_stored%'))
                            
                            if category_filter:
                                query = query.filter(Conversation.tags.like(f'%{category_filter}%'))
                            
                            if tool_filter:
                                query = query.filter(Conversation.tool_name == tool_filter.lower())
                            
                            if project_filter:
                                query = query.filter(Conversation.project_id == project_filter)
                            
                            memories = query.order_by(Conversation.timestamp.desc()).all()
                        
                        if not memories:
                            return [{
                                "type": "text",
                                "text": f"📦 No memories found matching export criteria.\n\n🔍 **Export Criteria:**\n• Days back: {days_back}\n• Format: {format_type}\n• Auto-stored only: {auto_stored_only}\n• Category: {category_filter or 'All'}\n• Tool: {tool_filter or 'All'}\n• Project: {project_filter or 'All'}"
                            }]
                        
                        # Prepare export data
                        export_data = []
                        for memory in memories:
                            memory_data = {
                                "id": memory.id,
                                "tool_name": memory.tool_name,
                                "project_id": memory.project_id,
                                "timestamp": memory.timestamp.isoformat(),
                                "content": memory.content,
                                "tags": memory.tags_list if memory.tags else []
                            }
                            
                            if include_metadata and memory.conversation_metadata:
                                memory_data["metadata"] = memory.conversation_metadata
                            
                            # Filter by confidence if metadata exists
                            if confidence_min > 0.0 and memory.conversation_metadata:
                                confidence = memory.conversation_metadata.get('confidence', 1.0)
                                if confidence < confidence_min:
                                    continue
                            
                            export_data.append(memory_data)
                        
                        # Format export data
                        if format_type == "json":
                            export_content = json.dumps(export_data, indent=2)
                        elif format_type == "csv":
                            import csv
                            import io
                            output = io.StringIO()
                            if export_data:
                                fieldnames = ["id", "tool_name", "project_id", "timestamp", "content", "tags"]
                                writer = csv.DictWriter(output, fieldnames=fieldnames)
                                writer.writeheader()
                                for item in export_data:
                                    row = {k: v for k, v in item.items() if k in fieldnames}
                                    row["tags"] = ", ".join(row.get("tags", []))
                                    writer.writerow(row)
                            export_content = output.getvalue()
                        elif format_type == "markdown":
                            export_content = f"# Memory Export\n\n"
                            export_content += f"**Export Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                            export_content += f"**Total Memories:** {len(export_data)}\n"
                            export_content += f"**Time Range:** Last {days_back} days\n\n"
                            
                            for item in export_data:
                                export_content += f"## {item['id']}\n\n"
                                export_content += f"**Tool:** {item['tool_name']}\n"
                                export_content += f"**Date:** {item['timestamp']}\n"
                                if item['project_id']:
                                    export_content += f"**Project:** {item['project_id']}\n"
                                if item['tags']:
                                    export_content += f"**Tags:** {', '.join(item['tags'])}\n"
                                export_content += f"\n**Content:**\n{item['content']}\n\n---\n\n"
                        
                        # Save to file if requested
                        if output_file:
                            try:
                                with open(output_file, 'w', encoding='utf-8') as f:
                                    f.write(export_content)
                                file_saved = True
                            except Exception as e:
                                file_saved = False
                                file_error = str(e)
                        else:
                            file_saved = False
                        
                        # Format response
                        result_text = f"📦 **Memory Export Complete**\n\n"
                        result_text += f"📊 **Export Summary:**\n"
                        result_text += f"• Total memories: {len(export_data)}\n"
                        result_text += f"• Format: {format_type}\n"
                        result_text += f"• Time range: Last {days_back} days\n"
                        result_text += f"• Auto-stored only: {auto_stored_only}\n"
                        if category_filter:
                            result_text += f"• Category filter: {category_filter}\n"
                        if tool_filter:
                            result_text += f"• Tool filter: {tool_filter}\n"
                        if project_filter:
                            result_text += f"• Project filter: {project_filter}\n"
                        
                        if output_file:
                            if file_saved:
                                result_text += f"💾 **File saved:** {output_file}\n"
                            else:
                                result_text += f"❌ **File save failed:** {file_error}\n"
                        
                        result_text += f"\n📄 **Export Preview:**\n```{format_type}\n{export_content[:1500]}{'...' if len(export_content) > 1500 else ''}\n```"
                        
                        return [{
                            "type": "text",
                            "text": result_text
                        }]
                        
                    except Exception as e:
                        logger.error(f"Error exporting memories: {e}")
                        return [{
                            "type": "text",
                            "text": f"❌ Error exporting memories: {str(e)}"
                        }]
                
                elif name == "get_memory_statistics":
                    days_back = arguments.get("days_back", 30)
                    include_categories = arguments.get("include_categories", True)
                    include_tools = arguments.get("include_tools", True)
                    include_confidence = arguments.get("include_confidence", True)
                    include_trends = arguments.get("include_trends", True)
                    
                    try:
                        from datetime import datetime, timedelta
                        cutoff_time = datetime.utcnow() - timedelta(days=days_back)
                        
                        with self.conversation_repo.db_manager.get_session() as session:
                            from models.database import Conversation
                            from sqlalchemy import and_, func
                            
                            # Basic statistics
                            total_memories = session.query(func.count(Conversation.id)).filter(
                                Conversation.timestamp >= cutoff_time
                            ).scalar()
                            
                            auto_stored_memories = session.query(func.count(Conversation.id)).filter(
                                and_(
                                    Conversation.timestamp >= cutoff_time,
                                    Conversation.tags.like('%auto_stored%')
                                )
                            ).scalar()
                            
                            manual_stored_memories = total_memories - auto_stored_memories
                            
                            # Get all memories for detailed analysis
                            memories = session.query(Conversation).filter(
                                Conversation.timestamp >= cutoff_time
                            ).all()
                        
                        # Analyze memories
                        stats = {
                            "total_memories": total_memories,
                            "auto_stored": auto_stored_memories,
                            "manual_stored": manual_stored_memories,
                            "auto_storage_rate": (auto_stored_memories / total_memories * 100) if total_memories > 0 else 0
                        }
                        
                        # Category breakdown
                        if include_categories:
                            categories = {}
                            for memory in memories:
                                if memory.conversation_metadata and 'analysis_category' in memory.conversation_metadata:
                                    category = memory.conversation_metadata['analysis_category']
                                    categories[category] = categories.get(category, 0) + 1
                                elif memory.tags and 'auto_stored' in memory.tags:
                                    # Try to extract category from tags
                                    tag_list = memory.tags_list
                                    category = 'unknown'
                                    for tag in tag_list:
                                        if tag in ['preference', 'solution', 'project_context', 'decision']:
                                            category = tag
                                            break
                                    categories[category] = categories.get(category, 0) + 1
                            stats["categories"] = categories
                        
                        # Tool breakdown
                        if include_tools:
                            tools = {}
                            auto_stored_by_tool = {}
                            for memory in memories:
                                tool = memory.tool_name
                                tools[tool] = tools.get(tool, 0) + 1
                                
                                if memory.tags and 'auto_stored' in memory.tags:
                                    auto_stored_by_tool[tool] = auto_stored_by_tool.get(tool, 0) + 1
                            
                            stats["tools"] = tools
                            stats["auto_stored_by_tool"] = auto_stored_by_tool
                        
                        # Confidence analysis
                        if include_confidence:
                            confidence_ranges = {
                                "high (0.85-1.0)": 0,
                                "medium (0.60-0.85)": 0,
                                "low (0.0-0.60)": 0,
                                "unknown": 0
                            }
                            
                            confidence_values = []
                            for memory in memories:
                                if memory.conversation_metadata and 'confidence' in memory.conversation_metadata:
                                    confidence = memory.conversation_metadata['confidence']
                                    confidence_values.append(confidence)
                                    
                                    if confidence >= 0.85:
                                        confidence_ranges["high (0.85-1.0)"] += 1
                                    elif confidence >= 0.60:
                                        confidence_ranges["medium (0.60-0.85)"] += 1
                                    else:
                                        confidence_ranges["low (0.0-0.60)"] += 1
                                else:
                                    confidence_ranges["unknown"] += 1
                            
                            stats["confidence_ranges"] = confidence_ranges
                            if confidence_values:
                                stats["average_confidence"] = sum(confidence_values) / len(confidence_values)
                        
                        # Trend analysis
                        if include_trends:
                            # Group by day
                            daily_stats = {}
                            for memory in memories:
                                day = memory.timestamp.date().isoformat()
                                if day not in daily_stats:
                                    daily_stats[day] = {"total": 0, "auto_stored": 0}
                                
                                daily_stats[day]["total"] += 1
                                if memory.tags and 'auto_stored' in memory.tags:
                                    daily_stats[day]["auto_stored"] += 1
                            
                            stats["daily_trends"] = daily_stats
                        
                        # Format results
                        result_text = f"📊 **Memory Statistics Report**\n\n"
                        result_text += f"📅 **Time Period:** Last {days_back} days\n"
                        result_text += f"📈 **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                        
                        result_text += f"🔢 **Overall Statistics:**\n"
                        result_text += f"• Total memories: {stats['total_memories']}\n"
                        result_text += f"• Auto-stored: {stats['auto_stored']} ({stats['auto_storage_rate']:.1f}%)\n"
                        result_text += f"• Manual-stored: {stats['manual_stored']} ({100 - stats['auto_storage_rate']:.1f}%)\n\n"
                        
                        if include_categories and "categories" in stats:
                            result_text += f"📂 **Category Breakdown:**\n"
                            for category, count in sorted(stats["categories"].items(), key=lambda x: x[1], reverse=True):
                                percentage = (count / stats['total_memories'] * 100) if stats['total_memories'] > 0 else 0
                                result_text += f"• {category}: {count} ({percentage:.1f}%)\n"
                            result_text += "\n"
                        
                        if include_tools and "tools" in stats:
                            result_text += f"🔧 **Tool Usage:**\n"
                            for tool, count in sorted(stats["tools"].items(), key=lambda x: x[1], reverse=True):
                                auto_count = stats["auto_stored_by_tool"].get(tool, 0)
                                auto_rate = (auto_count / count * 100) if count > 0 else 0
                                result_text += f"• {tool}: {count} total, {auto_count} auto-stored ({auto_rate:.1f}%)\n"
                            result_text += "\n"
                        
                        if include_confidence and "confidence_ranges" in stats:
                            result_text += f"🎯 **Confidence Analysis:**\n"
                            for range_name, count in stats["confidence_ranges"].items():
                                percentage = (count / stats['total_memories'] * 100) if stats['total_memories'] > 0 else 0
                                result_text += f"• {range_name}: {count} ({percentage:.1f}%)\n"
                            
                            if "average_confidence" in stats:
                                result_text += f"• Average confidence: {stats['average_confidence']:.1%}\n"
                            result_text += "\n"
                        
                        if include_trends and "daily_trends" in stats:
                            result_text += f"📈 **Daily Trends (Last 7 days):**\n"
                            sorted_days = sorted(stats["daily_trends"].items(), reverse=True)[:7]
                            for day, day_stats in sorted_days:
                                auto_rate = (day_stats["auto_stored"] / day_stats["total"] * 100) if day_stats["total"] > 0 else 0
                                result_text += f"• {day}: {day_stats['total']} total, {day_stats['auto_stored']} auto ({auto_rate:.1f}%)\n"
                            result_text += "\n"
                        
                        result_text += f"💡 **Insights:**\n"
                        if stats['auto_storage_rate'] > 70:
                            result_text += f"• High auto-storage rate indicates good intelligent storage performance\n"
                        elif stats['auto_storage_rate'] < 30:
                            result_text += f"• Low auto-storage rate - consider adjusting confidence thresholds\n"
                        
                        if include_confidence and "average_confidence" in stats:
                            if stats['average_confidence'] > 0.8:
                                result_text += f"• High average confidence suggests accurate pattern recognition\n"
                            elif stats['average_confidence'] < 0.6:
                                result_text += f"• Low average confidence may indicate need for pattern tuning\n"
                        
                        return [{
                            "type": "text",
                            "text": result_text
                        }]
                        
                    except Exception as e:
                        logger.error(f"Error generating memory statistics: {e}")
                        return [{
                            "type": "text",
                            "text": f"❌ Error generating statistics: {str(e)}"
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
            
            # Initialize storage analyzer
            self.storage_analyzer = StorageAnalyzer()
            
            # Initialize session analyzer
            self.session_analyzer = SessionAnalyzer(self.conversation_repo, self.storage_analyzer)
            
            # Initialize learning engine
            from services.learning_engine import LearningEngine
            self.learning_engine = LearningEngine(
                db_manager=self.db_manager,
                conversation_repo=self.conversation_repo,
                preferences_repo=self.preferences_repo
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
            
            # Initialize duplicate detector
            self.duplicate_detector = DuplicateDetector(
                conversation_repo=self.conversation_repo,
                search_engine=self.search_engine
            )
            
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
        """Handle retrieve_context tool call with intelligent storage enhancements."""
        query = arguments.get("query", "")
        project_id = arguments.get("project_id")
        tool_name = arguments.get("tool_name")
        limit = arguments.get("limit", 10)
        search_type = arguments.get("search_type", "hybrid")
        category_filter = arguments.get("category_filter", "")
        auto_stored_only = arguments.get("auto_stored_only", False)
        confidence_threshold = arguments.get("confidence_threshold", 0.0)
        
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
            
            # Add intelligent storage filters
            if auto_stored_only:
                filters["auto_stored"] = True
            if category_filter:
                filters["category"] = category_filter
            if confidence_threshold > 0.0:
                filters["confidence"] = {"$gte": confidence_threshold}
            
            # Perform search
            search_results = await self.search_engine.search(
                query=query,
                limit=limit * 2,  # Get more results to account for post-filtering
                filters=filters if filters else None,
                search_type=search_type
            )
            
            # Post-process results with intelligent storage metadata
            formatted_results = []
            for result in search_results:
                conversation_id = result.metadata.get("conversation_id")
                conversation = self.conversation_repo.get_by_id(conversation_id) if conversation_id else None
                
                # Apply intelligent storage filters that couldn't be handled at search level
                if not self._passes_intelligent_storage_filters(result, conversation, category_filter, auto_stored_only, confidence_threshold):
                    continue
                
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
                
                # Add intelligent storage metadata if available
                if conversation and conversation.conversation_metadata:
                    result_data["metadata"] = conversation.conversation_metadata
                    
                    # Extract intelligent storage specific metadata
                    if "auto_stored" in conversation.conversation_metadata:
                        result_data["auto_stored"] = conversation.conversation_metadata["auto_stored"]
                    if "confidence" in conversation.conversation_metadata:
                        result_data["storage_confidence"] = conversation.conversation_metadata["confidence"]
                    if "analysis_category" in conversation.conversation_metadata:
                        result_data["storage_category"] = conversation.conversation_metadata["analysis_category"]
                    if "storage_reason" in conversation.conversation_metadata:
                        result_data["storage_reason"] = conversation.conversation_metadata["storage_reason"]
                    if "extracted_info" in conversation.conversation_metadata:
                        result_data["extracted_info"] = conversation.conversation_metadata["extracted_info"]
                
                formatted_results.append(result_data)
                
                # Stop when we have enough results
                if len(formatted_results) >= limit:
                    break
            
            # Prepare response with enhanced metadata
            response_data = {
                "query": query,
                "search_type": search_type,
                "filters": {
                    **filters,
                    "category_filter": category_filter,
                    "auto_stored_only": auto_stored_only,
                    "confidence_threshold": confidence_threshold
                },
                "total_results": len(formatted_results),
                "results": formatted_results
            }
            
            # Add intelligent storage summary
            auto_stored_count = sum(1 for r in formatted_results if r.get("auto_stored", False))
            categories = {}
            for r in formatted_results:
                cat = r.get("storage_category", "unknown")
                categories[cat] = categories.get(cat, 0) + 1
            
            response_data["intelligent_storage_summary"] = {
                "auto_stored_results": auto_stored_count,
                "manual_stored_results": len(formatted_results) - auto_stored_count,
                "categories": categories
            }
            
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Retrieved {len(formatted_results)} relevant contexts with intelligent storage enhancements:\n{json.dumps(response_data, indent=2)}"
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
    
    def _passes_intelligent_storage_filters(
        self, 
        result: 'SearchResult', 
        conversation: Optional['Conversation'], 
        category_filter: str, 
        auto_stored_only: bool, 
        confidence_threshold: float
    ) -> bool:
        """Check if a search result passes intelligent storage filters."""
        if not conversation:
            return True
        
        metadata = conversation.conversation_metadata or {}
        tags = conversation.tags_list or []
        
        # Check auto-stored filter
        if auto_stored_only:
            if not (metadata.get("auto_stored", False) or "auto_stored" in tags):
                return False
        
        # Check category filter
        if category_filter:
            stored_category = metadata.get("analysis_category", "")
            if stored_category != category_filter:
                return False
        
        # Check confidence threshold
        if confidence_threshold > 0.0:
            stored_confidence = metadata.get("confidence", 0.0)
            if stored_confidence < confidence_threshold:
                return False
        
        return True

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
            from models.schemas import PreferenceCreate, PreferenceUpdate
            
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
    
    async def _process_storage_approval_feedback(
        self, suggestion: Dict[str, Any], modified_content: str, tool_name: str
    ) -> None:
        """Process feedback when a storage suggestion is approved."""
        try:
            from services.learning_engine import UserFeedback, FeedbackType
            
            analysis_result = suggestion.get('analysis_result', {})
            
            # Determine feedback type based on whether content was modified
            if modified_content:
                feedback_type = FeedbackType.STORAGE_MODIFICATION
                corrected_value = modified_content
            else:
                feedback_type = FeedbackType.STORAGE_APPROVAL
                corrected_value = None
            
            # Create feedback object
            feedback = UserFeedback(
                feedback_type=feedback_type,
                conversation_id=suggestion.get('id', ''),
                suggestion_id=suggestion.get('id'),
                original_suggestion=analysis_result.get('suggested_content', ''),
                corrected_value=corrected_value,
                timestamp=datetime.now(),
                context={
                    'analysis_result': analysis_result,
                    'tool_name': tool_name,
                    'suggestion_id': suggestion.get('id'),
                    'confidence': analysis_result.get('confidence', 0.0),
                    'category': analysis_result.get('category', 'unknown')
                }
            )
            
            # Process feedback through learning engine
            if hasattr(self, 'learning_engine') and self.learning_engine:
                await self.learning_engine.process_feedback(feedback)
                logger.info(f"Processed approval feedback for suggestion {suggestion.get('id')}")
            else:
                logger.warning("Learning engine not available for feedback processing")
                
        except Exception as e:
            logger.error(f"Error processing storage approval feedback: {e}")

    async def _process_storage_rejection_feedback(
        self, suggestion: Dict[str, Any], reason: str, tool_name: str
    ) -> None:
        """Process feedback when a storage suggestion is rejected."""
        try:
            from services.learning_engine import UserFeedback, FeedbackType
            
            analysis_result = suggestion.get('analysis_result', {})
            
            # Create feedback object
            feedback = UserFeedback(
                feedback_type=FeedbackType.STORAGE_REJECTION,
                conversation_id=suggestion.get('id', ''),
                suggestion_id=suggestion.get('id'),
                original_suggestion=analysis_result.get('suggested_content', ''),
                corrected_value=reason,  # Use rejection reason as corrected value
                timestamp=datetime.now(),
                context={
                    'analysis_result': analysis_result,
                    'tool_name': tool_name,
                    'suggestion_id': suggestion.get('id'),
                    'confidence': analysis_result.get('confidence', 0.0),
                    'category': analysis_result.get('category', 'unknown'),
                    'rejection_reason': reason
                }
            )
            
            # Process feedback through learning engine
            if hasattr(self, 'learning_engine') and self.learning_engine:
                await self.learning_engine.process_feedback(feedback)
                logger.info(f"Processed rejection feedback for suggestion {suggestion.get('id')}")
            else:
                logger.warning("Learning engine not available for feedback processing")
                
        except Exception as e:
            logger.error(f"Error processing storage rejection feedback: {e}")

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
                        server_name="cortex-mcp",
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
    logging.getLogger('cortex_mcp').setLevel(logging.CRITICAL)
    logging.getLogger('src.cortex_mcp').setLevel(logging.CRITICAL)
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
        data_dir = Path.home() / ".cortex_mcp" / "data"
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
            data_dir = Path.home() / ".cortex_mcp" / "data"
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