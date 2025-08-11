"""
Repository for project data access operations.

This module provides CRUD operations for projects with proper error handling,
transaction management, and relationship management with conversations.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import desc, func, and_

from ..models.database import Project, Conversation
from ..models.schemas import ProjectCreate, ProjectUpdate
from ..config.database import DatabaseManager, DatabaseConnectionError

logger = logging.getLogger(__name__)


class ProjectRepository:
    """Repository for project data access operations."""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize project repository.
        
        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager

    def create(self, project_data: ProjectCreate) -> Project:
        """
        Create a new project.
        
        Args:
            project_data: Project creation data
            
        Returns:
            Project: Created project instance
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                project = Project(
                    name=project_data.name,
                    path=project_data.path,
                    description=project_data.description,
                    created_at=datetime.utcnow(),
                    last_accessed=datetime.utcnow()
                )
                
                session.add(project)
                session.flush()  # Get the ID without committing
                session.commit()
                session.refresh(project)
                
                logger.info(f"Created project {project.id}: {project.name}")
                return project
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to create project: {e}")
            raise DatabaseConnectionError(f"Failed to create project: {e}") from e

    def get_by_id(self, project_id: str) -> Optional[Project]:
        """
        Get project by ID.
        
        Args:
            project_id: Project ID
            
        Returns:
            Optional[Project]: Project if found, None otherwise
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                project = session.query(Project).filter(
                    Project.id == project_id
                ).first()
                
                if project:
                    logger.debug(f"Retrieved project {project_id}: {project.name}")
                else:
                    logger.debug(f"Project {project_id} not found")
                
                return project
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to get project {project_id}: {e}")
            raise DatabaseConnectionError(f"Failed to get project: {e}") from e

    def get_by_name(self, name: str) -> Optional[Project]:
        """
        Get project by name.
        
        Args:
            name: Project name
            
        Returns:
            Optional[Project]: Project if found, None otherwise
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                project = session.query(Project).filter(
                    Project.name == name
                ).first()
                
                if project:
                    logger.debug(f"Retrieved project by name '{name}': {project.id}")
                else:
                    logger.debug(f"Project with name '{name}' not found")
                
                return project
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to get project by name '{name}': {e}")
            raise DatabaseConnectionError(f"Failed to get project by name: {e}") from e

    def get_by_path(self, path: str) -> Optional[Project]:
        """
        Get project by filesystem path.
        
        Args:
            path: Filesystem path
            
        Returns:
            Optional[Project]: Project if found, None otherwise
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                project = session.query(Project).filter(
                    Project.path == path
                ).first()
                
                if project:
                    logger.debug(f"Retrieved project by path '{path}': {project.id}")
                else:
                    logger.debug(f"Project with path '{path}' not found")
                
                return project
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to get project by path '{path}': {e}")
            raise DatabaseConnectionError(f"Failed to get project by path: {e}") from e

    def update(self, project_id: str, update_data: ProjectUpdate) -> Optional[Project]:
        """
        Update an existing project.
        
        Args:
            project_id: Project ID
            update_data: Update data
            
        Returns:
            Optional[Project]: Updated project if found, None otherwise
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                project = session.query(Project).filter(
                    Project.id == project_id
                ).first()
                
                if not project:
                    logger.warning(f"Project {project_id} not found for update")
                    return None
                
                # Update fields if provided
                if update_data.name is not None:
                    project.name = update_data.name
                
                if update_data.path is not None:
                    project.path = update_data.path
                
                if update_data.description is not None:
                    project.description = update_data.description
                
                # Always update last_accessed when project is modified
                project.update_last_accessed()
                
                session.commit()
                session.refresh(project)
                
                logger.info(f"Updated project {project_id}: {project.name}")
                return project
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to update project {project_id}: {e}")
            raise DatabaseConnectionError(f"Failed to update project: {e}") from e

    def delete(self, project_id: str, delete_conversations: bool = False) -> bool:
        """
        Delete a project.
        
        Args:
            project_id: Project ID
            delete_conversations: If True, delete associated conversations; 
                                 if False, set their project_id to None
            
        Returns:
            bool: True if deleted, False if not found
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                project = session.query(Project).filter(
                    Project.id == project_id
                ).first()
                
                if not project:
                    logger.warning(f"Project {project_id} not found for deletion")
                    return False
                
                # Handle associated conversations
                conversations = session.query(Conversation).filter(
                    Conversation.project_id == project_id
                ).all()
                
                if delete_conversations:
                    # Delete all associated conversations
                    for conversation in conversations:
                        session.delete(conversation)
                    logger.info(f"Deleted {len(conversations)} conversations with project {project_id}")
                else:
                    # Unlink conversations from project
                    for conversation in conversations:
                        conversation.project_id = None
                    logger.info(f"Unlinked {len(conversations)} conversations from project {project_id}")
                
                # Delete the project
                session.delete(project)
                session.commit()
                
                logger.info(f"Deleted project {project_id}: {project.name}")
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to delete project {project_id}: {e}")
            raise DatabaseConnectionError(f"Failed to delete project: {e}") from e

    def list_all(self, limit: int = 100, offset: int = 0, order_by: str = "last_accessed") -> List[Project]:
        """
        List all projects with pagination.
        
        Args:
            limit: Maximum number of projects to return
            offset: Number of projects to skip
            order_by: Field to order by ("last_accessed", "created_at", "name")
            
        Returns:
            List[Project]: List of projects
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                query = session.query(Project)
                
                # Apply ordering
                if order_by == "last_accessed":
                    query = query.order_by(desc(Project.last_accessed))
                elif order_by == "created_at":
                    query = query.order_by(desc(Project.created_at))
                elif order_by == "name":
                    query = query.order_by(Project.name)
                else:
                    # Default to last_accessed
                    query = query.order_by(desc(Project.last_accessed))
                
                projects = query.limit(limit).offset(offset).all()
                
                logger.debug(f"Retrieved {len(projects)} projects (limit={limit}, offset={offset}, order_by={order_by})")
                return projects
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to list projects: {e}")
            raise DatabaseConnectionError(f"Failed to list projects: {e}") from e

    def search_by_name(self, name_query: str, limit: int = 50) -> List[Project]:
        """
        Search projects by name (partial match).
        
        Args:
            name_query: Name search query
            limit: Maximum number of results
            
        Returns:
            List[Project]: List of matching projects
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                search_term = f"%{name_query}%"
                projects = session.query(Project).filter(
                    Project.name.ilike(search_term)
                ).order_by(desc(Project.last_accessed)).limit(limit).all()
                
                logger.debug(f"Found {len(projects)} projects matching name '{name_query}'")
                return projects
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to search projects by name: {e}")
            raise DatabaseConnectionError(f"Failed to search projects by name: {e}") from e

    def get_active_projects(self, days: int = 30, limit: int = 20) -> List[Project]:
        """
        Get recently active projects.
        
        Args:
            days: Number of days to look back for activity
            limit: Maximum number of projects
            
        Returns:
            List[Project]: List of active projects
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                
                projects = session.query(Project).filter(
                    Project.last_accessed >= cutoff_date
                ).order_by(desc(Project.last_accessed)).limit(limit).all()
                
                logger.debug(f"Retrieved {len(projects)} active projects (last {days} days)")
                return projects
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to get active projects: {e}")
            raise DatabaseConnectionError(f"Failed to get active projects: {e}") from e

    def update_last_accessed(self, project_id: str) -> bool:
        """
        Update the last_accessed timestamp for a project.
        
        Args:
            project_id: Project ID
            
        Returns:
            bool: True if updated, False if project not found
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                project = session.query(Project).filter(
                    Project.id == project_id
                ).first()
                
                if not project:
                    logger.warning(f"Project {project_id} not found for last_accessed update")
                    return False
                
                project.update_last_accessed()
                session.commit()
                
                logger.debug(f"Updated last_accessed for project {project_id}")
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to update last_accessed for project {project_id}: {e}")
            raise DatabaseConnectionError(f"Failed to update project last_accessed: {e}") from e

    def get_project_with_stats(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get project with conversation statistics.
        
        Args:
            project_id: Project ID
            
        Returns:
            Optional[Dict[str, Any]]: Project data with stats if found, None otherwise
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                project = session.query(Project).filter(
                    Project.id == project_id
                ).first()
                
                if not project:
                    return None
                
                # Get conversation statistics
                conversation_count = session.query(func.count(Conversation.id)).filter(
                    Conversation.project_id == project_id
                ).scalar() or 0
                
                # Get tool usage stats
                tool_stats = session.query(
                    Conversation.tool_name,
                    func.count(Conversation.id)
                ).filter(
                    Conversation.project_id == project_id
                ).group_by(Conversation.tool_name).all()
                
                # Get recent activity
                recent_conversation = session.query(Conversation).filter(
                    Conversation.project_id == project_id
                ).order_by(desc(Conversation.timestamp)).first()
                
                project_data = {
                    "id": project.id,
                    "name": project.name,
                    "path": project.path,
                    "description": project.description,
                    "created_at": project.created_at,
                    "last_accessed": project.last_accessed,
                    "stats": {
                        "conversation_count": conversation_count,
                        "tool_usage": {tool: count for tool, count in tool_stats},
                        "last_conversation": recent_conversation.timestamp if recent_conversation else None
                    }
                }
                
                logger.debug(f"Retrieved project {project_id} with statistics")
                return project_data
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to get project with stats {project_id}: {e}")
            raise DatabaseConnectionError(f"Failed to get project with stats: {e}") from e

    def count_total(self) -> int:
        """
        Get total count of projects.
        
        Returns:
            int: Total number of projects
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                count = session.query(func.count(Project.id)).scalar()
                logger.debug(f"Total projects count: {count}")
                return count or 0
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to count projects: {e}")
            raise DatabaseConnectionError(f"Failed to count projects: {e}") from e

    def get_project_stats(self) -> Dict[str, Any]:
        """
        Get project statistics.
        
        Returns:
            Dict[str, Any]: Statistics about projects
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            with self.db_manager.get_session() as session:
                stats = {}
                
                # Total count
                stats["total_projects"] = session.query(func.count(Project.id)).scalar() or 0
                
                # Projects with conversations
                projects_with_conversations = session.query(func.count(func.distinct(Conversation.project_id))).filter(
                    Conversation.project_id.isnot(None)
                ).scalar() or 0
                stats["projects_with_conversations"] = projects_with_conversations
                
                # Average conversations per project
                if projects_with_conversations > 0:
                    total_conversations = session.query(func.count(Conversation.id)).filter(
                        Conversation.project_id.isnot(None)
                    ).scalar() or 0
                    stats["avg_conversations_per_project"] = total_conversations / projects_with_conversations
                else:
                    stats["avg_conversations_per_project"] = 0
                
                # Date range
                date_range = session.query(
                    func.min(Project.created_at),
                    func.max(Project.last_accessed)
                ).first()
                if date_range[0] and date_range[1]:
                    stats["date_range"] = {
                        "oldest_created": date_range[0],
                        "most_recent_access": date_range[1]
                    }
                
                # Most active projects (by conversation count)
                active_projects = session.query(
                    Project.name,
                    func.count(Conversation.id).label("conversation_count")
                ).join(
                    Conversation, Project.id == Conversation.project_id
                ).group_by(Project.id, Project.name).order_by(
                    desc("conversation_count")
                ).limit(5).all()
                
                stats["most_active_projects"] = [
                    {"name": name, "conversation_count": count}
                    for name, count in active_projects
                ]
                
                logger.debug("Retrieved project statistics")
                return stats
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to get project statistics: {e}")
            raise DatabaseConnectionError(f"Failed to get project statistics: {e}") from e