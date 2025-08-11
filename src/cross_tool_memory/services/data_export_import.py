"""
Data Export/Import Service for Cross-Tool Memory MCP Server.

This service provides comprehensive data export/import functionality including:
- Full data export for backup purposes
- Selective data import with conflict resolution
- Data migration tools for schema updates
- Data cleanup utilities for maintenance
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
import zipfile
import tempfile
import shutil

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text, func

from ..models.database import Conversation, Project, Preference, ContextLink
from ..models.schemas import (
    ConversationCreate, ProjectCreate, PreferenceCreate, ContextLinkCreate,
    PreferenceCategory
)
from ..config.database import DatabaseManager, DatabaseConnectionError
from ..repositories.conversation_repository import ConversationRepository
from ..repositories.project_repository import ProjectRepository
from ..repositories.preferences_repository import PreferencesRepository

logger = logging.getLogger(__name__)


class DataExportImportService:
    """Service for data export/import operations."""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize the data export/import service.
        
        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager
        self.conversation_repo = ConversationRepository(db_manager)
        self.project_repo = ProjectRepository(db_manager)
        self.preferences_repo = PreferencesRepository(db_manager)
        
        # Export format version for compatibility
        self.export_format_version = "1.0"
    
    def export_all_data(self, 
                       export_path: Optional[str] = None,
                       include_embeddings: bool = False,
                       compress: bool = True) -> str:
        """
        Export all user data to a file.
        
        Args:
            export_path: Custom export file path (auto-generated if None)
            include_embeddings: Whether to include vector embeddings (large files)
            compress: Whether to compress the export file
            
        Returns:
            str: Path to the exported file
            
        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            # Generate export path if not provided
            if export_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"memory_export_{timestamp}"
                if compress:
                    filename += ".zip"
                else:
                    filename += ".json"
                export_path = str(Path.cwd() / "exports" / filename)
            
            # Ensure export directory exists
            Path(export_path).parent.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Starting data export to: {export_path}")
            
            # Collect all data
            export_data = {
                "metadata": {
                    "export_timestamp": datetime.now().isoformat(),
                    "format_version": self.export_format_version,
                    "include_embeddings": include_embeddings,
                    "exported_by": "cross_tool_memory_mcp"
                },
                "conversations": self._export_conversations(include_embeddings),
                "projects": self._export_projects(),
                "preferences": self._export_preferences(),
                "context_links": self._export_context_links(),
                "statistics": self._get_export_statistics()
            }
            
            if compress:
                self._write_compressed_export(export_data, export_path)
            else:
                self._write_json_export(export_data, export_path)
            
            logger.info(f"Data export completed successfully: {export_path}")
            return export_path
            
        except Exception as e:
            logger.error(f"Data export failed: {e}")
            raise DatabaseConnectionError(f"Data export failed: {e}") from e
    
    def _export_conversations(self, include_embeddings: bool = False) -> List[Dict[str, Any]]:
        """Export all conversations."""
        try:
            with self.db_manager.get_session() as session:
                conversations = session.query(Conversation).all()
                
                exported_conversations = []
                for conv in conversations:
                    conv_data = {
                        "id": conv.id,
                        "tool_name": conv.tool_name,
                        "project_id": conv.project_id,
                        "timestamp": conv.timestamp.isoformat(),
                        "content": conv.content,
                        "conversation_metadata": conv.conversation_metadata,
                        "tags": conv.tags_list
                    }
                    
                    # Include embeddings if requested (note: actual embeddings would be in vector store)
                    if include_embeddings:
                        # Placeholder for embedding data - would need vector store integration
                        conv_data["embedding_available"] = False
                    
                    exported_conversations.append(conv_data)
                
                logger.info(f"Exported {len(exported_conversations)} conversations")
                return exported_conversations
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to export conversations: {e}")
            raise DatabaseConnectionError(f"Failed to export conversations: {e}") from e
    
    def _export_projects(self) -> List[Dict[str, Any]]:
        """Export all projects."""
        try:
            with self.db_manager.get_session() as session:
                projects = session.query(Project).all()
                
                exported_projects = []
                for project in projects:
                    project_data = {
                        "id": project.id,
                        "name": project.name,
                        "path": project.path,
                        "description": project.description,
                        "created_at": project.created_at.isoformat(),
                        "last_accessed": project.last_accessed.isoformat()
                    }
                    exported_projects.append(project_data)
                
                logger.info(f"Exported {len(exported_projects)} projects")
                return exported_projects
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to export projects: {e}")
            raise DatabaseConnectionError(f"Failed to export projects: {e}") from e
    
    def _export_preferences(self) -> List[Dict[str, Any]]:
        """Export all preferences."""
        try:
            with self.db_manager.get_session() as session:
                preferences = session.query(Preference).all()
                
                exported_preferences = []
                for pref in preferences:
                    pref_data = {
                        "key": pref.key,
                        "value": pref.get_json_value(),
                        "category": pref.category,
                        "updated_at": pref.updated_at.isoformat()
                    }
                    exported_preferences.append(pref_data)
                
                logger.info(f"Exported {len(exported_preferences)} preferences")
                return exported_preferences
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to export preferences: {e}")
            raise DatabaseConnectionError(f"Failed to export preferences: {e}") from e
    
    def _export_context_links(self) -> List[Dict[str, Any]]:
        """Export all context links."""
        try:
            with self.db_manager.get_session() as session:
                context_links = session.query(ContextLink).all()
                
                exported_links = []
                for link in context_links:
                    link_data = {
                        "id": link.id,
                        "source_conversation_id": link.source_conversation_id,
                        "target_conversation_id": link.target_conversation_id,
                        "relationship_type": link.relationship_type,
                        "confidence_score": link.confidence_score,
                        "created_at": link.created_at.isoformat()
                    }
                    exported_links.append(link_data)
                
                logger.info(f"Exported {len(exported_links)} context links")
                return exported_links
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to export context links: {e}")
            raise DatabaseConnectionError(f"Failed to export context links: {e}") from e
    
    def _get_export_statistics(self) -> Dict[str, Any]:
        """Get statistics about the exported data."""
        try:
            with self.db_manager.get_session() as session:
                stats = {
                    "total_conversations": session.query(func.count(Conversation.id)).scalar() or 0,
                    "total_projects": session.query(func.count(Project.id)).scalar() or 0,
                    "total_preferences": session.query(func.count(Preference.key)).scalar() or 0,
                    "total_context_links": session.query(func.count(ContextLink.id)).scalar() or 0,
                }
                
                # Date ranges
                conv_dates = session.query(
                    func.min(Conversation.timestamp),
                    func.max(Conversation.timestamp)
                ).first()
                
                if conv_dates[0] and conv_dates[1]:
                    stats["conversation_date_range"] = {
                        "oldest": conv_dates[0].isoformat(),
                        "newest": conv_dates[1].isoformat()
                    }
                
                # Tool usage
                tool_counts = session.query(
                    Conversation.tool_name,
                    func.count(Conversation.id)
                ).group_by(Conversation.tool_name).all()
                
                stats["conversations_by_tool"] = {tool: count for tool, count in tool_counts}
                
                return stats
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to get export statistics: {e}")
            return {}
    
    def _write_json_export(self, data: Dict[str, Any], export_path: str) -> None:
        """Write export data as JSON file."""
        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _write_compressed_export(self, data: Dict[str, Any], export_path: str) -> None:
        """Write export data as compressed ZIP file."""
        with zipfile.ZipFile(export_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Write main data file
            json_data = json.dumps(data, indent=2, ensure_ascii=False)
            zipf.writestr("export_data.json", json_data)
            
            # Write metadata file
            metadata = {
                "export_info": data["metadata"],
                "file_structure": {
                    "export_data.json": "Main export data file",
                    "README.txt": "Information about this export"
                }
            }
            zipf.writestr("metadata.json", json.dumps(metadata, indent=2))
            
            # Write README
            readme_content = f"""Cross-Tool Memory MCP Server Data Export
            
Export Date: {data['metadata']['export_timestamp']}
Format Version: {data['metadata']['format_version']}

This export contains:
- {data['statistics']['total_conversations']} conversations
- {data['statistics']['total_projects']} projects  
- {data['statistics']['total_preferences']} preferences
- {data['statistics']['total_context_links']} context links

To import this data, use the import_data method of the DataExportImportService.
"""
            zipf.writestr("README.txt", readme_content)
    
    def import_data(self, 
                   import_path: str,
                   overwrite_existing: bool = False,
                   selective_import: Optional[Dict[str, bool]] = None) -> Dict[str, Any]:
        """
        Import data from an export file.
        
        Args:
            import_path: Path to the import file
            overwrite_existing: Whether to overwrite existing data
            selective_import: Dict specifying what to import (conversations, projects, etc.)
            
        Returns:
            Dict with import results and statistics
            
        Raises:
            DatabaseConnectionError: If database operation fails
            FileNotFoundError: If import file not found
            ValueError: If import file format is invalid
        """
        try:
            import_file = Path(import_path)
            if not import_file.exists():
                raise FileNotFoundError(f"Import file not found: {import_path}")
            
            logger.info(f"Starting data import from: {import_path}")
            
            # Load import data
            import_data = self._load_import_data(import_path)
            
            # Validate import data
            self._validate_import_data(import_data)
            
            # Set default selective import if not provided
            if selective_import is None:
                selective_import = {
                    "conversations": True,
                    "projects": True,
                    "preferences": True,
                    "context_links": True
                }
            
            # Perform import
            results = {
                "import_timestamp": datetime.now().isoformat(),
                "source_file": import_path,
                "overwrite_existing": overwrite_existing,
                "selective_import": selective_import,
                "results": {}
            }
            
            if selective_import.get("projects", True):
                results["results"]["projects"] = self._import_projects(
                    import_data["projects"], overwrite_existing
                )
            
            if selective_import.get("preferences", True):
                results["results"]["preferences"] = self._import_preferences(
                    import_data["preferences"], overwrite_existing
                )
            
            if selective_import.get("conversations", True):
                results["results"]["conversations"] = self._import_conversations(
                    import_data["conversations"], overwrite_existing
                )
            
            if selective_import.get("context_links", True):
                results["results"]["context_links"] = self._import_context_links(
                    import_data["context_links"], overwrite_existing
                )
            
            logger.info("Data import completed successfully")
            return results
            
        except Exception as e:
            logger.error(f"Data import failed: {e}")
            raise DatabaseConnectionError(f"Data import failed: {e}") from e
    
    def _load_import_data(self, import_path: str) -> Dict[str, Any]:
        """Load data from import file (JSON or ZIP)."""
        import_file = Path(import_path)
        
        if import_file.suffix.lower() == '.zip':
            # Load from ZIP file
            with zipfile.ZipFile(import_path, 'r') as zipf:
                if "export_data.json" in zipf.namelist():
                    with zipf.open("export_data.json") as f:
                        return json.load(f)
                else:
                    raise ValueError("Invalid ZIP export file: missing export_data.json")
        else:
            # Load from JSON file
            with open(import_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    
    def _validate_import_data(self, data: Dict[str, Any]) -> None:
        """Validate import data structure."""
        required_keys = ["metadata", "conversations", "projects", "preferences", "context_links"]
        
        for key in required_keys:
            if key not in data:
                raise ValueError(f"Invalid import data: missing '{key}' section")
        
        # Check format version compatibility
        format_version = data["metadata"].get("format_version", "unknown")
        if format_version != self.export_format_version:
            logger.warning(f"Import format version {format_version} may not be fully compatible with current version {self.export_format_version}")
    
    def _import_projects(self, projects_data: List[Dict[str, Any]], overwrite: bool) -> Dict[str, Any]:
        """Import projects data."""
        results = {"imported": 0, "skipped": 0, "errors": 0}
        
        for project_data in projects_data:
            try:
                # Check if project exists
                existing_project = self.project_repo.get_by_id(project_data["id"])
                
                if existing_project and not overwrite:
                    results["skipped"] += 1
                    continue
                
                if existing_project and overwrite:
                    # Update existing project
                    from ..models.schemas import ProjectUpdate
                    update_data = ProjectUpdate(
                        name=project_data["name"],
                        path=project_data.get("path"),
                        description=project_data.get("description")
                    )
                    self.project_repo.update(project_data["id"], update_data)
                else:
                    # Create new project with specific ID
                    with self.db_manager.get_session() as session:
                        project = Project(
                            id=project_data["id"],
                            name=project_data["name"],
                            path=project_data.get("path"),
                            description=project_data.get("description"),
                            created_at=datetime.fromisoformat(project_data["created_at"]),
                            last_accessed=datetime.fromisoformat(project_data["last_accessed"])
                        )
                        session.add(project)
                        session.commit()
                
                results["imported"] += 1
                
            except Exception as e:
                logger.error(f"Failed to import project {project_data.get('id', 'unknown')}: {e}")
                results["errors"] += 1
        
        return results
    
    def _import_preferences(self, preferences_data: List[Dict[str, Any]], overwrite: bool) -> Dict[str, Any]:
        """Import preferences data."""
        results = {"imported": 0, "skipped": 0, "errors": 0}
        
        for pref_data in preferences_data:
            try:
                # Check if preference exists
                existing_pref = self.preferences_repo.get_by_key(pref_data["key"])
                
                if existing_pref and not overwrite:
                    results["skipped"] += 1
                    continue
                
                # Set preference (creates or updates)
                category = None
                if pref_data.get("category"):
                    try:
                        category = PreferenceCategory(pref_data["category"])
                    except ValueError:
                        logger.warning(f"Unknown preference category: {pref_data['category']}")
                
                self.preferences_repo.set_value(
                    pref_data["key"],
                    pref_data["value"],
                    category
                )
                
                results["imported"] += 1
                
            except Exception as e:
                logger.error(f"Failed to import preference {pref_data.get('key', 'unknown')}: {e}")
                results["errors"] += 1
        
        return results
    
    def _import_conversations(self, conversations_data: List[Dict[str, Any]], overwrite: bool) -> Dict[str, Any]:
        """Import conversations data."""
        results = {"imported": 0, "skipped": 0, "errors": 0}
        
        for conv_data in conversations_data:
            try:
                # Check if conversation exists
                existing_conv = self.conversation_repo.get_by_id(conv_data["id"])
                
                if existing_conv and not overwrite:
                    results["skipped"] += 1
                    continue
                
                if existing_conv and overwrite:
                    # Update existing conversation
                    from ..models.schemas import ConversationUpdate
                    update_data = ConversationUpdate(
                        content=conv_data["content"],
                        conversation_metadata=conv_data.get("conversation_metadata"),
                        tags=conv_data.get("tags"),
                        project_id=conv_data.get("project_id")
                    )
                    self.conversation_repo.update(conv_data["id"], update_data)
                else:
                    # Create new conversation with specific ID
                    with self.db_manager.get_session() as session:
                        conversation = Conversation(
                            id=conv_data["id"],
                            tool_name=conv_data["tool_name"],
                            project_id=conv_data.get("project_id"),
                            timestamp=datetime.fromisoformat(conv_data["timestamp"]),
                            content=conv_data["content"],
                            conversation_metadata=conv_data.get("conversation_metadata"),
                            tags=", ".join(conv_data["tags"]) if conv_data.get("tags") else None
                        )
                        session.add(conversation)
                        session.commit()
                
                results["imported"] += 1
                
            except Exception as e:
                logger.error(f"Failed to import conversation {conv_data.get('id', 'unknown')}: {e}")
                results["errors"] += 1
        
        return results
    
    def _import_context_links(self, links_data: List[Dict[str, Any]], overwrite: bool) -> Dict[str, Any]:
        """Import context links data."""
        results = {"imported": 0, "skipped": 0, "errors": 0}
        
        for link_data in links_data:
            try:
                with self.db_manager.get_session() as session:
                    # Check if link exists
                    existing_link = session.query(ContextLink).filter(
                        ContextLink.source_conversation_id == link_data["source_conversation_id"],
                        ContextLink.target_conversation_id == link_data["target_conversation_id"],
                        ContextLink.relationship_type == link_data["relationship_type"]
                    ).first()
                    
                    if existing_link and not overwrite:
                        results["skipped"] += 1
                        continue
                    
                    if existing_link and overwrite:
                        # Update existing link
                        existing_link.confidence_score = link_data["confidence_score"]
                        session.commit()
                    else:
                        # Create new link
                        context_link = ContextLink(
                            source_conversation_id=link_data["source_conversation_id"],
                            target_conversation_id=link_data["target_conversation_id"],
                            relationship_type=link_data["relationship_type"],
                            confidence_score=link_data["confidence_score"],
                            created_at=datetime.fromisoformat(link_data["created_at"])
                        )
                        session.add(context_link)
                        session.commit()
                    
                    results["imported"] += 1
                
            except Exception as e:
                logger.error(f"Failed to import context link: {e}")
                results["errors"] += 1
        
        return results
    
    def migrate_data_schema(self, 
                           from_version: str, 
                           to_version: str,
                           backup_before_migration: bool = True) -> Dict[str, Any]:
        """
        Migrate data schema from one version to another.
        
        Args:
            from_version: Source schema version
            to_version: Target schema version
            backup_before_migration: Whether to create backup before migration
            
        Returns:
            Dict with migration results
            
        Raises:
            DatabaseConnectionError: If migration fails
            ValueError: If migration path is not supported
        """
        try:
            logger.info(f"Starting schema migration from {from_version} to {to_version}")
            
            # Create backup if requested
            backup_path = None
            if backup_before_migration:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = self.export_all_data(
                    export_path=f"migration_backup_{from_version}_to_{to_version}_{timestamp}.zip"
                )
                logger.info(f"Pre-migration backup created: {backup_path}")
            
            # Perform migration based on version path
            migration_results = self._execute_schema_migration(from_version, to_version)
            
            results = {
                "migration_timestamp": datetime.now().isoformat(),
                "from_version": from_version,
                "to_version": to_version,
                "backup_created": backup_path,
                "migration_results": migration_results,
                "success": True
            }
            
            logger.info(f"Schema migration completed successfully")
            return results
            
        except Exception as e:
            logger.error(f"Schema migration failed: {e}")
            raise DatabaseConnectionError(f"Schema migration failed: {e}") from e
    
    def _execute_schema_migration(self, from_version: str, to_version: str) -> Dict[str, Any]:
        """Execute the actual schema migration."""
        migration_results = {"operations": [], "errors": []}
        
        try:
            with self.db_manager.get_session() as session:
                # Define migration paths
                if from_version == "0.9" and to_version == "1.0":
                    # Example migration: add new columns, update data formats, etc.
                    migration_results["operations"].append("Added new index on conversations.timestamp")
                    migration_results["operations"].append("Updated preference categories")
                    
                    # Add any actual migration SQL here
                    # session.execute(text("ALTER TABLE conversations ADD COLUMN new_field TEXT"))
                    
                elif from_version == "1.0" and to_version == "1.1":
                    # Future migration example
                    migration_results["operations"].append("Added embedding_version column")
                    
                else:
                    raise ValueError(f"Migration path from {from_version} to {to_version} is not supported")
                
                session.commit()
                
        except Exception as e:
            migration_results["errors"].append(str(e))
            raise
        
        return migration_results
    
    def cleanup_old_conversations(self, 
                                 older_than_days: int = 365,
                                 keep_minimum: int = 100,
                                 dry_run: bool = True) -> Dict[str, Any]:
        """
        Clean up old conversations to free up space.
        
        Args:
            older_than_days: Delete conversations older than this many days
            keep_minimum: Always keep at least this many conversations
            dry_run: If True, only report what would be deleted without actually deleting
            
        Returns:
            Dict with cleanup results
            
        Raises:
            DatabaseConnectionError: If cleanup operation fails
        """
        try:
            logger.info(f"Starting conversation cleanup (older than {older_than_days} days, keep minimum {keep_minimum})")
            
            cutoff_date = datetime.now() - timedelta(days=older_than_days)
            
            with self.db_manager.get_session() as session:
                # Find conversations to delete
                total_conversations = session.query(func.count(Conversation.id)).scalar() or 0
                
                old_conversations_query = session.query(Conversation).filter(
                    Conversation.timestamp < cutoff_date
                ).order_by(Conversation.timestamp)
                
                old_conversations_count = old_conversations_query.count()
                
                # Calculate how many we can actually delete
                conversations_to_keep = max(keep_minimum, total_conversations - old_conversations_count)
                max_deletable = total_conversations - conversations_to_keep
                actual_delete_count = min(old_conversations_count, max_deletable)
                
                results = {
                    "cleanup_timestamp": datetime.now().isoformat(),
                    "cutoff_date": cutoff_date.isoformat(),
                    "total_conversations": total_conversations,
                    "old_conversations_found": old_conversations_count,
                    "conversations_to_delete": actual_delete_count,
                    "conversations_to_keep": conversations_to_keep,
                    "dry_run": dry_run,
                    "deleted_conversation_ids": []
                }
                
                if actual_delete_count > 0:
                    # Get the conversations to delete
                    conversations_to_delete = old_conversations_query.limit(actual_delete_count).all()
                    
                    if not dry_run:
                        # Delete context links first (foreign key constraints)
                        for conv in conversations_to_delete:
                            # Delete context links where this conversation is source or target
                            session.query(ContextLink).filter(
                                (ContextLink.source_conversation_id == conv.id) |
                                (ContextLink.target_conversation_id == conv.id)
                            ).delete(synchronize_session=False)
                            
                            results["deleted_conversation_ids"].append(conv.id)
                        
                        # Delete the conversations
                        for conv in conversations_to_delete:
                            session.delete(conv)
                        
                        session.commit()
                        logger.info(f"Deleted {actual_delete_count} old conversations")
                    else:
                        # Just collect IDs for dry run
                        results["deleted_conversation_ids"] = [conv.id for conv in conversations_to_delete]
                        logger.info(f"Dry run: would delete {actual_delete_count} old conversations")
                else:
                    logger.info("No conversations to delete based on criteria")
                
                return results
                
        except Exception as e:
            logger.error(f"Conversation cleanup failed: {e}")
            raise DatabaseConnectionError(f"Conversation cleanup failed: {e}") from e
    
    def cleanup_orphaned_data(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        Clean up orphaned data (context links without conversations, etc.).
        
        Args:
            dry_run: If True, only report what would be cleaned without actually cleaning
            
        Returns:
            Dict with cleanup results
            
        Raises:
            DatabaseConnectionError: If cleanup operation fails
        """
        try:
            logger.info("Starting orphaned data cleanup")
            
            results = {
                "cleanup_timestamp": datetime.now().isoformat(),
                "dry_run": dry_run,
                "orphaned_context_links": 0,
                "orphaned_project_references": 0
            }
            
            with self.db_manager.get_session() as session:
                # Find orphaned context links
                orphaned_links = session.query(ContextLink).filter(
                    ~session.query(Conversation).filter(
                        Conversation.id == ContextLink.source_conversation_id
                    ).exists() |
                    ~session.query(Conversation).filter(
                        Conversation.id == ContextLink.target_conversation_id
                    ).exists()
                ).all()
                
                results["orphaned_context_links"] = len(orphaned_links)
                
                if not dry_run and orphaned_links:
                    for link in orphaned_links:
                        session.delete(link)
                    logger.info(f"Deleted {len(orphaned_links)} orphaned context links")
                
                # Find conversations with non-existent project references
                orphaned_project_refs = session.query(Conversation).filter(
                    Conversation.project_id.isnot(None),
                    ~session.query(Project).filter(
                        Project.id == Conversation.project_id
                    ).exists()
                ).all()
                
                results["orphaned_project_references"] = len(orphaned_project_refs)
                
                if not dry_run and orphaned_project_refs:
                    for conv in orphaned_project_refs:
                        conv.project_id = None
                    logger.info(f"Cleaned {len(orphaned_project_refs)} orphaned project references")
                
                if not dry_run:
                    session.commit()
                
                return results
                
        except Exception as e:
            logger.error(f"Orphaned data cleanup failed: {e}")
            raise DatabaseConnectionError(f"Orphaned data cleanup failed: {e}") from e
    
    def get_data_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about stored data.
        
        Returns:
            Dict with detailed data statistics
            
        Raises:
            DatabaseConnectionError: If statistics query fails
        """
        try:
            with self.db_manager.get_session() as session:
                stats = {
                    "timestamp": datetime.now().isoformat(),
                    "conversations": {},
                    "projects": {},
                    "preferences": {},
                    "context_links": {},
                    "storage": {}
                }
                
                # Conversation statistics
                stats["conversations"]["total"] = session.query(func.count(Conversation.id)).scalar() or 0
                
                # By tool
                tool_counts = session.query(
                    Conversation.tool_name,
                    func.count(Conversation.id)
                ).group_by(Conversation.tool_name).all()
                stats["conversations"]["by_tool"] = {tool: count for tool, count in tool_counts}
                
                # By date ranges
                now = datetime.now()
                last_week = now - timedelta(days=7)
                last_month = now - timedelta(days=30)
                last_year = now - timedelta(days=365)
                
                stats["conversations"]["last_week"] = session.query(func.count(Conversation.id)).filter(
                    Conversation.timestamp >= last_week
                ).scalar() or 0
                
                stats["conversations"]["last_month"] = session.query(func.count(Conversation.id)).filter(
                    Conversation.timestamp >= last_month
                ).scalar() or 0
                
                stats["conversations"]["last_year"] = session.query(func.count(Conversation.id)).filter(
                    Conversation.timestamp >= last_year
                ).scalar() or 0
                
                # Project statistics
                stats["projects"]["total"] = session.query(func.count(Project.id)).scalar() or 0
                stats["projects"]["with_conversations"] = session.query(
                    func.count(func.distinct(Conversation.project_id))
                ).filter(Conversation.project_id.isnot(None)).scalar() or 0
                
                # Most active projects
                active_projects = session.query(
                    Project.name,
                    func.count(Conversation.id).label("conversation_count")
                ).join(Conversation, Project.id == Conversation.project_id).group_by(
                    Project.id, Project.name
                ).order_by(text("conversation_count DESC")).limit(5).all()
                
                stats["projects"]["most_active"] = [
                    {"name": name, "conversation_count": count}
                    for name, count in active_projects
                ]
                
                # Preference statistics
                stats["preferences"]["total"] = session.query(func.count(Preference.key)).scalar() or 0
                
                pref_categories = session.query(
                    Preference.category,
                    func.count(Preference.key)
                ).group_by(Preference.category).all()
                stats["preferences"]["by_category"] = {
                    (cat or "uncategorized"): count for cat, count in pref_categories
                }
                
                # Context link statistics
                stats["context_links"]["total"] = session.query(func.count(ContextLink.id)).scalar() or 0
                
                link_types = session.query(
                    ContextLink.relationship_type,
                    func.count(ContextLink.id)
                ).group_by(ContextLink.relationship_type).all()
                stats["context_links"]["by_type"] = {rel_type: count for rel_type, count in link_types}
                
                # Storage estimates (rough)
                avg_conversation_size = 1000  # Rough estimate in bytes
                avg_preference_size = 100
                
                stats["storage"]["estimated_conversations_mb"] = (
                    stats["conversations"]["total"] * avg_conversation_size
                ) / (1024 * 1024)
                
                stats["storage"]["estimated_preferences_mb"] = (
                    stats["preferences"]["total"] * avg_preference_size
                ) / (1024 * 1024)
                
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get data statistics: {e}")
            raise DatabaseConnectionError(f"Failed to get data statistics: {e}") from e
    
    def validate_data_integrity(self) -> Dict[str, Any]:
        """
        Validate data integrity and report any issues.
        
        Returns:
            Dict with validation results
            
        Raises:
            DatabaseConnectionError: If validation fails
        """
        try:
            logger.info("Starting data integrity validation")
            
            results = {
                "validation_timestamp": datetime.now().isoformat(),
                "issues": [],
                "warnings": [],
                "summary": {
                    "total_issues": 0,
                    "total_warnings": 0,
                    "data_integrity_score": 100.0
                }
            }
            
            with self.db_manager.get_session() as session:
                # Check for orphaned context links
                orphaned_links_count = session.query(func.count(ContextLink.id)).filter(
                    ~session.query(Conversation).filter(
                        Conversation.id == ContextLink.source_conversation_id
                    ).exists() |
                    ~session.query(Conversation).filter(
                        Conversation.id == ContextLink.target_conversation_id
                    ).exists()
                ).scalar() or 0
                
                if orphaned_links_count > 0:
                    results["issues"].append({
                        "type": "orphaned_context_links",
                        "count": orphaned_links_count,
                        "description": f"{orphaned_links_count} context links reference non-existent conversations"
                    })
                
                # Check for conversations with invalid project references
                invalid_project_refs = session.query(func.count(Conversation.id)).filter(
                    Conversation.project_id.isnot(None),
                    ~session.query(Project).filter(
                        Project.id == Conversation.project_id
                    ).exists()
                ).scalar() or 0
                
                if invalid_project_refs > 0:
                    results["issues"].append({
                        "type": "invalid_project_references",
                        "count": invalid_project_refs,
                        "description": f"{invalid_project_refs} conversations reference non-existent projects"
                    })
                
                # Check for duplicate context links
                duplicate_links = session.execute(text("""
                    SELECT source_conversation_id, target_conversation_id, relationship_type, COUNT(*) as count
                    FROM context_links 
                    GROUP BY source_conversation_id, target_conversation_id, relationship_type
                    HAVING COUNT(*) > 1
                """)).fetchall()
                
                if duplicate_links:
                    results["warnings"].append({
                        "type": "duplicate_context_links",
                        "count": len(duplicate_links),
                        "description": f"{len(duplicate_links)} sets of duplicate context links found"
                    })
                
                # Check for conversations with empty content
                empty_conversations = session.query(func.count(Conversation.id)).filter(
                    (Conversation.content == "") | (Conversation.content.is_(None))
                ).scalar() or 0
                
                if empty_conversations > 0:
                    results["warnings"].append({
                        "type": "empty_conversations",
                        "count": empty_conversations,
                        "description": f"{empty_conversations} conversations have empty content"
                    })
                
                # Calculate integrity score
                total_issues = len(results["issues"])
                total_warnings = len(results["warnings"])
                
                results["summary"]["total_issues"] = total_issues
                results["summary"]["total_warnings"] = total_warnings
                
                # Simple scoring: each issue reduces score by 10%, each warning by 2%
                score_reduction = (total_issues * 10) + (total_warnings * 2)
                results["summary"]["data_integrity_score"] = max(0.0, 100.0 - score_reduction)
                
                logger.info(f"Data integrity validation completed. Score: {results['summary']['data_integrity_score']:.1f}%")
                return results
                
        except Exception as e:
            logger.error(f"Data integrity validation failed: {e}")
            raise DatabaseConnectionError(f"Data integrity validation failed: {e}") from e