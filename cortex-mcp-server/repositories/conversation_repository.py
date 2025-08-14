"""
Repository for conversation data access operations.

This module provides CRUD operations for conversations with proper error handling,
transaction management, and query optimization.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_, or_, desc, func

from models.database import Conversation, Project
from models.schemas import ConversationCreate, ConversationUpdate, MemoryQuery
from config.database import DatabaseManager, DatabaseConnectionError

logger = logging.getLogger(__name__)


class ConversationRepository:
    """Repository for conversation data access operations."""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize conversation repository.
        
        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager

    def create(self, conversation_data: ConversationCreate) -> Conversation:
        """
        Create a new conversation.
        
        Args:
            conversation_data: Conversation creation data
            
        Returns:
            Conversation: Created conversation instance
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                # Convert tags list to comma-separated string
                tags_str = None
                if conversation_data.tags:
                    tags_str = ", ".join(conversation_data.tags)
                
                conversation = Conversation(
                    tool_name=conversation_data.tool_name,
                    project_id=conversation_data.project_id,
                    content=conversation_data.content,
                    conversation_metadata=conversation_data.conversation_metadata,
                    tags=tags_str,
                    timestamp=datetime.utcnow()
                )
                
                session.add(conversation)
                session.flush()  # Get the ID without committing
                
                # Update project last_accessed if project_id is provided
                if conversation.project_id:
                    project = session.query(Project).filter(
                        Project.id == conversation.project_id
                    ).first()
                    if project:
                        project.update_last_accessed()
                
                session.commit()
                session.refresh(conversation)
                
                logger.info(f"Created conversation {conversation.id} for tool {conversation.tool_name}")
                return conversation
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to create conversation: {e}")
            raise DatabaseConnectionError(f"Failed to create conversation: {e}") from e

    def get_by_id(self, conversation_id: str) -> Optional[Conversation]:
        """
        Get conversation by ID.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Optional[Conversation]: Conversation if found, None otherwise
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                conversation = session.query(Conversation).filter(
                    Conversation.id == conversation_id
                ).first()
                
                if conversation:
                    logger.debug(f"Retrieved conversation {conversation_id}")
                else:
                    logger.debug(f"Conversation {conversation_id} not found")
                
                return conversation
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to get conversation {conversation_id}: {e}")
            raise DatabaseConnectionError(f"Failed to get conversation: {e}") from e

    def update(self, conversation_id: str, update_data: ConversationUpdate) -> Optional[Conversation]:
        """
        Update an existing conversation.
        
        Args:
            conversation_id: Conversation ID
            update_data: Update data
            
        Returns:
            Optional[Conversation]: Updated conversation if found, None otherwise
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                conversation = session.query(Conversation).filter(
                    Conversation.id == conversation_id
                ).first()
                
                if not conversation:
                    logger.warning(f"Conversation {conversation_id} not found for update")
                    return None
                
                # Update fields if provided
                if update_data.content is not None:
                    conversation.content = update_data.content
                
                if update_data.conversation_metadata is not None:
                    conversation.conversation_metadata = update_data.conversation_metadata
                
                if update_data.tags is not None:
                    conversation.tags = ", ".join(update_data.tags) if update_data.tags else None
                
                if update_data.project_id is not None:
                    old_project_id = conversation.project_id
                    conversation.project_id = update_data.project_id
                    
                    # Update project last_accessed for both old and new projects
                    if old_project_id:
                        old_project = session.query(Project).filter(
                            Project.id == old_project_id
                        ).first()
                        if old_project:
                            old_project.update_last_accessed()
                    
                    if conversation.project_id:
                        new_project = session.query(Project).filter(
                            Project.id == conversation.project_id
                        ).first()
                        if new_project:
                            new_project.update_last_accessed()
                
                session.commit()
                session.refresh(conversation)
                
                logger.info(f"Updated conversation {conversation_id}")
                return conversation
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to update conversation {conversation_id}: {e}")
            raise DatabaseConnectionError(f"Failed to update conversation: {e}") from e

    def delete(self, conversation_id: str) -> bool:
        """
        Delete a conversation.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            bool: True if deleted, False if not found
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                conversation = session.query(Conversation).filter(
                    Conversation.id == conversation_id
                ).first()
                
                if not conversation:
                    logger.warning(f"Conversation {conversation_id} not found for deletion")
                    return False
                
                session.delete(conversation)
                session.commit()
                
                logger.info(f"Deleted conversation {conversation_id}")
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to delete conversation {conversation_id}: {e}")
            raise DatabaseConnectionError(f"Failed to delete conversation: {e}") from e

    def list_all(self, limit: int = 100, offset: int = 0) -> List[Conversation]:
        """
        List all conversations with pagination.
        
        Args:
            limit: Maximum number of conversations to return
            offset: Number of conversations to skip
            
        Returns:
            List[Conversation]: List of conversations
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                conversations = session.query(Conversation).order_by(
                    desc(Conversation.timestamp)
                ).limit(limit).offset(offset).all()
                
                logger.debug(f"Retrieved {len(conversations)} conversations (limit={limit}, offset={offset})")
                return conversations
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to list conversations: {e}")
            raise DatabaseConnectionError(f"Failed to list conversations: {e}") from e

    def get_by_project(self, project_id: str, limit: int = 100, offset: int = 0) -> List[Conversation]:
        """
        Get conversations by project ID.
        
        Args:
            project_id: Project ID
            limit: Maximum number of conversations to return
            offset: Number of conversations to skip
            
        Returns:
            List[Conversation]: List of conversations for the project
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                conversations = session.query(Conversation).filter(
                    Conversation.project_id == project_id
                ).order_by(desc(Conversation.timestamp)).limit(limit).offset(offset).all()
                
                logger.debug(f"Retrieved {len(conversations)} conversations for project {project_id}")
                return conversations
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to get conversations for project {project_id}: {e}")
            raise DatabaseConnectionError(f"Failed to get conversations for project: {e}") from e

    def get_by_tool(self, tool_name: str, limit: int = 100, offset: int = 0) -> List[Conversation]:
        """
        Get conversations by tool name.
        
        Args:
            tool_name: Tool name
            limit: Maximum number of conversations to return
            offset: Number of conversations to skip
            
        Returns:
            List[Conversation]: List of conversations for the tool
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                conversations = session.query(Conversation).filter(
                    Conversation.tool_name == tool_name.lower()
                ).order_by(desc(Conversation.timestamp)).limit(limit).offset(offset).all()
                
                logger.debug(f"Retrieved {len(conversations)} conversations for tool {tool_name}")
                return conversations
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to get conversations for tool {tool_name}: {e}")
            raise DatabaseConnectionError(f"Failed to get conversations for tool: {e}") from e

    def search_by_content(self, query: str, limit: int = 50) -> List[Conversation]:
        """
        Search conversations by content (keyword search).
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List[Conversation]: List of matching conversations
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                # Simple keyword search using LIKE
                search_term = f"%{query}%"
                conversations = session.query(Conversation).filter(
                    Conversation.content.ilike(search_term)
                ).order_by(desc(Conversation.timestamp)).limit(limit).all()
                
                logger.debug(f"Found {len(conversations)} conversations matching '{query}'")
                return conversations
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to search conversations: {e}")
            raise DatabaseConnectionError(f"Failed to search conversations: {e}") from e

    def search_by_tags(self, tags: List[str], match_all: bool = False, limit: int = 50) -> List[Conversation]:
        """
        Search conversations by tags.
        
        Args:
            tags: List of tags to search for
            match_all: If True, conversation must have all tags; if False, any tag
            limit: Maximum number of results
            
        Returns:
            List[Conversation]: List of matching conversations
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            if not tags:
                return []
                
            with self.db_manager.get_session() as session:
                
                # Build tag search conditions
                tag_conditions = []
                for tag in tags:
                    # Search for tag in comma-separated tags string
                    tag_conditions.append(Conversation.tags.ilike(f"%{tag}%"))
                
                if match_all:
                    # All tags must be present
                    filter_condition = and_(*tag_conditions)
                else:
                    # Any tag can be present
                    filter_condition = or_(*tag_conditions)
                
                conversations = session.query(Conversation).filter(
                    filter_condition
                ).order_by(desc(Conversation.timestamp)).limit(limit).all()
                
                logger.debug(f"Found {len(conversations)} conversations with tags {tags} (match_all={match_all})")
                return conversations
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to search conversations by tags: {e}")
            raise DatabaseConnectionError(f"Failed to search conversations by tags: {e}") from e

    def get_recent_by_tool(self, tool_name: str, hours: int = 24, limit: int = 20) -> List[Conversation]:
        """
        Get recent conversations for a specific tool.
        
        Args:
            tool_name: Tool name
            hours: Number of hours to look back
            limit: Maximum number of conversations
            
        Returns:
            List[Conversation]: List of recent conversations
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                cutoff_time = datetime.utcnow() - timedelta(hours=hours)
                
                conversations = session.query(Conversation).filter(
                    and_(
                        Conversation.tool_name == tool_name.lower(),
                        Conversation.timestamp >= cutoff_time
                    )
                ).order_by(desc(Conversation.timestamp)).limit(limit).all()
                
                logger.debug(f"Retrieved {len(conversations)} recent conversations for {tool_name} (last {hours}h)")
                return conversations
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to get recent conversations for {tool_name}: {e}")
            raise DatabaseConnectionError(f"Failed to get recent conversations: {e}") from e

    def get_by_time_range(
        self, 
        start_time: datetime, 
        end_time: datetime, 
        limit: int = 50, 
        tool_name: Optional[str] = None
    ) -> List[Conversation]:
        """
        Get conversations within a specific time range.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            limit: Maximum number of conversations
            tool_name: Optional tool name filter
            
        Returns:
            List[Conversation]: List of conversations in time range
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                query = session.query(Conversation).filter(
                    and_(
                        Conversation.timestamp >= start_time,
                        Conversation.timestamp <= end_time
                    )
                )
                
                if tool_name:
                    query = query.filter(Conversation.tool_name == tool_name.lower())
                
                conversations = query.order_by(Conversation.timestamp).limit(limit).all()
                
                logger.debug(f"Retrieved {len(conversations)} conversations in time range "
                           f"{start_time} to {end_time}" + (f" for {tool_name}" if tool_name else ""))
                return conversations
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to get conversations by time range: {e}")
            raise DatabaseConnectionError(f"Failed to get conversations by time range: {e}") from e

    def get_recent(self, hours: int = 24, limit: int = 20, tool_name: Optional[str] = None) -> List[Conversation]:
        """
        Get recent conversations across all tools or for a specific tool.
        
        Args:
            hours: Number of hours to look back
            limit: Maximum number of conversations
            tool_name: Optional tool name filter
            
        Returns:
            List[Conversation]: List of recent conversations
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                cutoff_time = datetime.utcnow() - timedelta(hours=hours)
                
                query = session.query(Conversation).filter(
                    Conversation.timestamp >= cutoff_time
                )
                
                if tool_name:
                    query = query.filter(Conversation.tool_name == tool_name.lower())
                
                conversations = query.order_by(desc(Conversation.timestamp)).limit(limit).all()
                
                logger.debug(f"Retrieved {len(conversations)} recent conversations (last {hours}h)" + 
                           (f" for {tool_name}" if tool_name else ""))
                return conversations
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to get recent conversations: {e}")
            raise DatabaseConnectionError(f"Failed to get recent conversations: {e}") from e

    def count_total(self) -> int:
        """
        Get total count of conversations.
        
        Returns:
            int: Total number of conversations
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                count = session.query(func.count(Conversation.id)).scalar()
                logger.debug(f"Total conversations count: {count}")
                return count or 0
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to count conversations: {e}")
            raise DatabaseConnectionError(f"Failed to count conversations: {e}") from e

    def count_by_project(self, project_id: str) -> int:
        """
        Get count of conversations for a project.
        
        Args:
            project_id: Project ID
            
        Returns:
            int: Number of conversations for the project
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                count = session.query(func.count(Conversation.id)).filter(
                    Conversation.project_id == project_id
                ).scalar()
                
                logger.debug(f"Conversations count for project {project_id}: {count}")
                return count or 0
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to count conversations for project {project_id}: {e}")
            raise DatabaseConnectionError(f"Failed to count conversations for project: {e}") from e

    def get_conversation_stats(self) -> Dict[str, Any]:
        """
        Get conversation statistics.
        
        Returns:
            Dict[str, Any]: Statistics about conversations
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                stats = {}
                
                # Total count
                stats["total_conversations"] = session.query(func.count(Conversation.id)).scalar() or 0
                
                # Count by tool
                tool_counts = session.query(
                    Conversation.tool_name,
                    func.count(Conversation.id)
                ).group_by(Conversation.tool_name).all()
                stats["by_tool"] = {tool: count for tool, count in tool_counts}
                
                # Count by project (top 10)
                project_counts = session.query(
                    Conversation.project_id,
                    func.count(Conversation.id)
                ).filter(
                    Conversation.project_id.isnot(None)
                ).group_by(Conversation.project_id).order_by(
                    desc(func.count(Conversation.id))
                ).limit(10).all()
                stats["top_projects"] = {project_id: count for project_id, count in project_counts}
                
                # Date range
                date_range = session.query(
                    func.min(Conversation.timestamp),
                    func.max(Conversation.timestamp)
                ).first()
                if date_range[0] and date_range[1]:
                    stats["date_range"] = {
                        "oldest": date_range[0],
                        "newest": date_range[1]
                    }
                
                logger.debug("Retrieved conversation statistics")
                return stats
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to get conversation statistics: {e}")
            raise DatabaseConnectionError(f"Failed to get conversation statistics: {e}") from e