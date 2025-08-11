"""
Storage usage monitoring and cleanup utilities.

This module provides comprehensive storage monitoring, usage analysis,
and automated cleanup capabilities for the cross-tool memory system.
"""

import os
import asyncio
import time
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import text, func, desc

from ..config.database import DatabaseManager, get_database_manager
from ..models.database import Conversation, Project, Preference, ContextLink
from ..utils.logging_config import get_component_logger, TimedOperation
from ..utils.error_handling import graceful_degradation

logger = get_component_logger("storage_monitor")


class CleanupAction(Enum):
    """Types of cleanup actions."""
    DELETE_OLD_CONVERSATIONS = "delete_old_conversations"
    DELETE_ORPHANED_DATA = "delete_orphaned_data"
    COMPRESS_OLD_DATA = "compress_old_data"
    VACUUM_DATABASE = "vacuum_database"
    CLEANUP_TEMP_FILES = "cleanup_temp_files"
    CLEANUP_LOG_FILES = "cleanup_log_files"


@dataclass
class StorageUsage:
    """Storage usage information."""
    database_size_bytes: int
    database_size_mb: float
    log_files_size_bytes: int
    log_files_size_mb: float
    temp_files_size_bytes: int
    temp_files_size_mb: float
    total_size_bytes: int
    total_size_mb: float
    available_space_bytes: int
    available_space_mb: float
    usage_percentage: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "database_size_mb": self.database_size_mb,
            "log_files_size_mb": self.log_files_size_mb,
            "temp_files_size_mb": self.temp_files_size_mb,
            "total_size_mb": self.total_size_mb,
            "available_space_mb": self.available_space_mb,
            "usage_percentage": self.usage_percentage
        }


@dataclass
class CleanupResult:
    """Result of a cleanup operation."""
    action: CleanupAction
    success: bool
    items_processed: int
    bytes_freed: int
    mb_freed: float
    duration_seconds: float
    error_message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class StorageReport:
    """Comprehensive storage usage report."""
    timestamp: datetime
    usage: StorageUsage
    conversation_stats: Dict[str, Any]
    project_stats: Dict[str, Any]
    cleanup_recommendations: List[Dict[str, Any]]
    warnings: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "usage": self.usage.to_dict(),
            "conversation_stats": self.conversation_stats,
            "project_stats": self.project_stats,
            "cleanup_recommendations": self.cleanup_recommendations,
            "warnings": self.warnings
        }


class StorageMonitor:
    """Comprehensive storage monitoring and cleanup system."""
    
    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        data_dir: Optional[Path] = None,
        log_dir: Optional[Path] = None
    ):
        """
        Initialize storage monitor.
        
        Args:
            db_manager: Database manager instance
            data_dir: Data directory path
            log_dir: Log directory path
        """
        self.db_manager = db_manager or get_database_manager()
        
        # Set default directories
        if data_dir is None:
            data_dir = Path.home() / ".cross_tool_memory" / "data"
        if log_dir is None:
            log_dir = Path.home() / ".cross_tool_memory" / "logs"
            
        self.data_dir = Path(data_dir)
        self.log_dir = Path(log_dir)
        
        # Create directories if they don't exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    async def get_storage_usage(self) -> StorageUsage:
        """
        Get comprehensive storage usage information.
        
        Returns:
            StorageUsage: Current storage usage details
        """
        logger.info("Analyzing storage usage")
        
        with TimedOperation("storage_usage_analysis", logger):
            # Database size
            db_size = self._get_database_size()
            
            # Log files size
            log_size = self._get_directory_size(self.log_dir)
            
            # Temp files size
            temp_size = self._get_temp_files_size()
            
            # Total size
            total_size = db_size + log_size + temp_size
            
            # Available space
            available_space = self._get_available_space()
            
            # Usage percentage
            total_space = available_space + total_size
            usage_percentage = (total_size / total_space * 100) if total_space > 0 else 0
            
            return StorageUsage(
                database_size_bytes=db_size,
                database_size_mb=db_size / (1024 * 1024),
                log_files_size_bytes=log_size,
                log_files_size_mb=log_size / (1024 * 1024),
                temp_files_size_bytes=temp_size,
                temp_files_size_mb=temp_size / (1024 * 1024),
                total_size_bytes=total_size,
                total_size_mb=total_size / (1024 * 1024),
                available_space_bytes=available_space,
                available_space_mb=available_space / (1024 * 1024),
                usage_percentage=usage_percentage
            )
    
    async def get_conversation_stats(self) -> Dict[str, Any]:
        """Get detailed conversation statistics."""
        try:
            async with self.db_manager.get_async_session() as session:
                # Total conversations
                total_result = await session.execute(
                    text("SELECT COUNT(*) FROM conversations")
                )
                total_conversations = total_result.scalar()
                
                # Conversations by tool
                tool_result = await session.execute(
                    text("""
                        SELECT tool_name, COUNT(*) as count 
                        FROM conversations 
                        GROUP BY tool_name 
                        ORDER BY count DESC
                    """)
                )
                by_tool = {row.tool_name: row.count for row in tool_result.fetchall()}
                
                # Conversations by age
                age_result = await session.execute(
                    text("""
                        SELECT 
                            CASE 
                                WHEN timestamp >= datetime('now', '-1 day') THEN 'last_24h'
                                WHEN timestamp >= datetime('now', '-7 days') THEN 'last_week'
                                WHEN timestamp >= datetime('now', '-30 days') THEN 'last_month'
                                WHEN timestamp >= datetime('now', '-90 days') THEN 'last_3_months'
                                ELSE 'older'
                            END as age_group,
                            COUNT(*) as count
                        FROM conversations
                        GROUP BY age_group
                    """)
                )
                by_age = {row.age_group: row.count for row in age_result.fetchall()}
                
                # Average content length
                length_result = await session.execute(
                    text("SELECT AVG(LENGTH(content)) as avg_length FROM conversations")
                )
                avg_content_length = length_result.scalar() or 0
                
                # Largest conversations
                large_result = await session.execute(
                    text("""
                        SELECT id, LENGTH(content) as content_length 
                        FROM conversations 
                        ORDER BY content_length DESC 
                        LIMIT 10
                    """)
                )
                largest_conversations = [
                    {"id": row.id, "size_bytes": row.content_length}
                    for row in large_result.fetchall()
                ]
                
                return {
                    "total_conversations": total_conversations,
                    "by_tool": by_tool,
                    "by_age": by_age,
                    "avg_content_length": round(avg_content_length, 2),
                    "largest_conversations": largest_conversations
                }
                
        except Exception as e:
            logger.error(f"Failed to get conversation stats: {e}")
            return {"error": str(e)}
    
    async def get_project_stats(self) -> Dict[str, Any]:
        """Get detailed project statistics."""
        try:
            async with self.db_manager.get_async_session() as session:
                # Total projects
                total_result = await session.execute(
                    text("SELECT COUNT(*) FROM projects")
                )
                total_projects = total_result.scalar()
                
                # Projects with conversation counts
                project_result = await session.execute(
                    text("""
                        SELECT 
                            p.id, 
                            p.name, 
                            COUNT(c.id) as conversation_count,
                            p.last_accessed
                        FROM projects p
                        LEFT JOIN conversations c ON p.id = c.project_id
                        GROUP BY p.id, p.name, p.last_accessed
                        ORDER BY conversation_count DESC
                    """)
                )
                
                projects_with_counts = []
                empty_projects = 0
                
                for row in project_result.fetchall():
                    if row.conversation_count == 0:
                        empty_projects += 1
                    projects_with_counts.append({
                        "id": row.id,
                        "name": row.name,
                        "conversation_count": row.conversation_count,
                        "last_accessed": row.last_accessed
                    })
                
                # Most active projects (top 10)
                most_active = projects_with_counts[:10]
                
                # Inactive projects (no access in 30 days)
                inactive_cutoff = datetime.now() - timedelta(days=30)
                inactive_result = await session.execute(
                    text("""
                        SELECT COUNT(*) 
                        FROM projects 
                        WHERE last_accessed < :cutoff OR last_accessed IS NULL
                    """),
                    {"cutoff": inactive_cutoff}
                )
                inactive_projects = inactive_result.scalar()
                
                return {
                    "total_projects": total_projects,
                    "empty_projects": empty_projects,
                    "inactive_projects": inactive_projects,
                    "most_active": most_active,
                    "projects_with_counts": len(projects_with_counts)
                }
                
        except Exception as e:
            logger.error(f"Failed to get project stats: {e}")
            return {"error": str(e)}
    
    async def generate_cleanup_recommendations(
        self,
        usage: StorageUsage,
        conversation_stats: Dict[str, Any],
        project_stats: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate cleanup recommendations based on usage analysis."""
        recommendations = []
        
        # High storage usage warning
        if usage.usage_percentage > 80:
            recommendations.append({
                "priority": "high",
                "action": "immediate_cleanup",
                "description": f"Storage usage is {usage.usage_percentage:.1f}% - immediate cleanup recommended",
                "estimated_savings_mb": usage.total_size_mb * 0.3  # Estimate 30% savings
            })
        
        # Old conversations cleanup
        old_conversations = conversation_stats.get("by_age", {}).get("older", 0)
        if old_conversations > 1000:
            recommendations.append({
                "priority": "medium",
                "action": "delete_old_conversations",
                "description": f"Delete {old_conversations} conversations older than 90 days",
                "estimated_savings_mb": old_conversations * conversation_stats.get("avg_content_length", 1000) / (1024 * 1024)
            })
        
        # Empty projects cleanup
        empty_projects = project_stats.get("empty_projects", 0)
        if empty_projects > 10:
            recommendations.append({
                "priority": "low",
                "action": "delete_empty_projects",
                "description": f"Delete {empty_projects} empty projects",
                "estimated_savings_mb": 0.1  # Minimal savings
            })
        
        # Inactive projects
        inactive_projects = project_stats.get("inactive_projects", 0)
        if inactive_projects > 20:
            recommendations.append({
                "priority": "low",
                "action": "archive_inactive_projects",
                "description": f"Archive {inactive_projects} inactive projects (no access in 30+ days)",
                "estimated_savings_mb": 1.0  # Estimate
            })
        
        # Database vacuum
        if usage.database_size_mb > 100:
            recommendations.append({
                "priority": "medium",
                "action": "vacuum_database",
                "description": "Vacuum database to reclaim unused space",
                "estimated_savings_mb": usage.database_size_mb * 0.1  # Estimate 10% savings
            })
        
        # Log file cleanup
        if usage.log_files_size_mb > 50:
            recommendations.append({
                "priority": "low",
                "action": "cleanup_old_logs",
                "description": f"Clean up {usage.log_files_size_mb:.1f}MB of log files",
                "estimated_savings_mb": usage.log_files_size_mb * 0.8  # Keep recent logs
            })
        
        return recommendations
    
    async def generate_storage_report(self) -> StorageReport:
        """Generate comprehensive storage usage report."""
        logger.info("Generating storage usage report")
        
        with TimedOperation("storage_report_generation", logger):
            # Get usage information
            usage = await self.get_storage_usage()
            
            # Get statistics
            conversation_stats = await self.get_conversation_stats()
            project_stats = await self.get_project_stats()
            
            # Generate recommendations
            recommendations = await self.generate_cleanup_recommendations(
                usage, conversation_stats, project_stats
            )
            
            # Generate warnings
            warnings = []
            if usage.usage_percentage > 90:
                warnings.append("Critical: Storage usage above 90% - immediate action required")
            elif usage.usage_percentage > 80:
                warnings.append("Warning: Storage usage above 80% - cleanup recommended")
            
            if usage.available_space_mb < 100:
                warnings.append("Warning: Less than 100MB available space remaining")
            
            return StorageReport(
                timestamp=datetime.now(),
                usage=usage,
                conversation_stats=conversation_stats,
                project_stats=project_stats,
                cleanup_recommendations=recommendations,
                warnings=warnings
            )
    
    async def cleanup_old_conversations(
        self,
        days_old: int = 90,
        dry_run: bool = False
    ) -> CleanupResult:
        """
        Clean up conversations older than specified days.
        
        Args:
            days_old: Delete conversations older than this many days
            dry_run: If True, only count what would be deleted
            
        Returns:
            CleanupResult: Results of the cleanup operation
        """
        logger.info(f"Cleaning up conversations older than {days_old} days (dry_run={dry_run})")
        start_time = time.time()
        
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            async with self.db_manager.get_async_session() as session:
                # Count conversations to be deleted
                count_result = await session.execute(
                    text("SELECT COUNT(*) FROM conversations WHERE timestamp < :cutoff"),
                    {"cutoff": cutoff_date}
                )
                count = count_result.scalar()
                
                if count == 0:
                    return CleanupResult(
                        action=CleanupAction.DELETE_OLD_CONVERSATIONS,
                        success=True,
                        items_processed=0,
                        bytes_freed=0,
                        mb_freed=0,
                        duration_seconds=time.time() - start_time
                    )
                
                # Estimate bytes to be freed
                size_result = await session.execute(
                    text("SELECT SUM(LENGTH(content)) FROM conversations WHERE timestamp < :cutoff"),
                    {"cutoff": cutoff_date}
                )
                estimated_bytes = size_result.scalar() or 0
                
                if not dry_run:
                    # Delete old conversations
                    await session.execute(
                        text("DELETE FROM conversations WHERE timestamp < :cutoff"),
                        {"cutoff": cutoff_date}
                    )
                    await session.commit()
                
                duration = time.time() - start_time
                
                return CleanupResult(
                    action=CleanupAction.DELETE_OLD_CONVERSATIONS,
                    success=True,
                    items_processed=count,
                    bytes_freed=estimated_bytes,
                    mb_freed=estimated_bytes / (1024 * 1024),
                    duration_seconds=duration,
                    details={
                        "cutoff_date": cutoff_date.isoformat(),
                        "dry_run": dry_run
                    }
                )
                
        except Exception as e:
            logger.error(f"Failed to cleanup old conversations: {e}")
            return CleanupResult(
                action=CleanupAction.DELETE_OLD_CONVERSATIONS,
                success=False,
                items_processed=0,
                bytes_freed=0,
                mb_freed=0,
                duration_seconds=time.time() - start_time,
                error_message=str(e)
            )
    
    async def cleanup_orphaned_data(self, dry_run: bool = False) -> CleanupResult:
        """
        Clean up orphaned data (context links without conversations, etc.).
        
        Args:
            dry_run: If True, only count what would be deleted
            
        Returns:
            CleanupResult: Results of the cleanup operation
        """
        logger.info(f"Cleaning up orphaned data (dry_run={dry_run})")
        start_time = time.time()
        
        try:
            async with self.db_manager.get_async_session() as session:
                total_deleted = 0
                
                # Clean up orphaned context links
                orphaned_links_result = await session.execute(
                    text("""
                        SELECT COUNT(*) FROM context_links cl
                        LEFT JOIN conversations c1 ON cl.source_conversation_id = c1.id
                        LEFT JOIN conversations c2 ON cl.target_conversation_id = c2.id
                        WHERE c1.id IS NULL OR c2.id IS NULL
                    """)
                )
                orphaned_links_count = orphaned_links_result.scalar()
                
                if not dry_run and orphaned_links_count > 0:
                    await session.execute(
                        text("""
                            DELETE FROM context_links 
                            WHERE id IN (
                                SELECT cl.id FROM context_links cl
                                LEFT JOIN conversations c1 ON cl.source_conversation_id = c1.id
                                LEFT JOIN conversations c2 ON cl.target_conversation_id = c2.id
                                WHERE c1.id IS NULL OR c2.id IS NULL
                            )
                        """)
                    )
                
                total_deleted += orphaned_links_count
                
                # Clean up empty projects (no conversations)
                empty_projects_result = await session.execute(
                    text("""
                        SELECT COUNT(*) FROM projects p
                        LEFT JOIN conversations c ON p.id = c.project_id
                        WHERE c.id IS NULL 
                        AND p.created_at < datetime('now', '-7 days')
                    """)
                )
                empty_projects_count = empty_projects_result.scalar()
                
                if not dry_run and empty_projects_count > 0:
                    await session.execute(
                        text("""
                            DELETE FROM projects 
                            WHERE id IN (
                                SELECT p.id FROM projects p
                                LEFT JOIN conversations c ON p.id = c.project_id
                                WHERE c.id IS NULL 
                                AND p.created_at < datetime('now', '-7 days')
                            )
                        """)
                    )
                
                total_deleted += empty_projects_count
                
                if not dry_run:
                    await session.commit()
                
                duration = time.time() - start_time
                
                return CleanupResult(
                    action=CleanupAction.DELETE_ORPHANED_DATA,
                    success=True,
                    items_processed=total_deleted,
                    bytes_freed=total_deleted * 100,  # Estimate
                    mb_freed=total_deleted * 100 / (1024 * 1024),
                    duration_seconds=duration,
                    details={
                        "orphaned_links": orphaned_links_count,
                        "empty_projects": empty_projects_count,
                        "dry_run": dry_run
                    }
                )
                
        except Exception as e:
            logger.error(f"Failed to cleanup orphaned data: {e}")
            return CleanupResult(
                action=CleanupAction.DELETE_ORPHANED_DATA,
                success=False,
                items_processed=0,
                bytes_freed=0,
                mb_freed=0,
                duration_seconds=time.time() - start_time,
                error_message=str(e)
            )
    
    async def vacuum_database(self) -> CleanupResult:
        """
        Vacuum the database to reclaim unused space.
        
        Returns:
            CleanupResult: Results of the vacuum operation
        """
        logger.info("Vacuuming database")
        start_time = time.time()
        
        try:
            # Get database size before vacuum
            size_before = self._get_database_size()
            
            async with self.db_manager.get_async_session() as session:
                await session.execute(text("VACUUM"))
                await session.commit()
            
            # Get database size after vacuum
            size_after = self._get_database_size()
            bytes_freed = max(0, size_before - size_after)
            
            duration = time.time() - start_time
            
            return CleanupResult(
                action=CleanupAction.VACUUM_DATABASE,
                success=True,
                items_processed=1,
                bytes_freed=bytes_freed,
                mb_freed=bytes_freed / (1024 * 1024),
                duration_seconds=duration,
                details={
                    "size_before_mb": size_before / (1024 * 1024),
                    "size_after_mb": size_after / (1024 * 1024)
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to vacuum database: {e}")
            return CleanupResult(
                action=CleanupAction.VACUUM_DATABASE,
                success=False,
                items_processed=0,
                bytes_freed=0,
                mb_freed=0,
                duration_seconds=time.time() - start_time,
                error_message=str(e)
            )
    
    async def cleanup_log_files(self, days_old: int = 30) -> CleanupResult:
        """
        Clean up old log files.
        
        Args:
            days_old: Delete log files older than this many days
            
        Returns:
            CleanupResult: Results of the cleanup operation
        """
        logger.info(f"Cleaning up log files older than {days_old} days")
        start_time = time.time()
        
        try:
            cutoff_time = time.time() - (days_old * 24 * 60 * 60)
            files_deleted = 0
            bytes_freed = 0
            
            for log_file in self.log_dir.glob("*.log*"):
                if log_file.is_file() and log_file.stat().st_mtime < cutoff_time:
                    file_size = log_file.stat().st_size
                    log_file.unlink()
                    files_deleted += 1
                    bytes_freed += file_size
            
            duration = time.time() - start_time
            
            return CleanupResult(
                action=CleanupAction.CLEANUP_LOG_FILES,
                success=True,
                items_processed=files_deleted,
                bytes_freed=bytes_freed,
                mb_freed=bytes_freed / (1024 * 1024),
                duration_seconds=duration,
                details={"days_old": days_old}
            )
            
        except Exception as e:
            logger.error(f"Failed to cleanup log files: {e}")
            return CleanupResult(
                action=CleanupAction.CLEANUP_LOG_FILES,
                success=False,
                items_processed=0,
                bytes_freed=0,
                mb_freed=0,
                duration_seconds=time.time() - start_time,
                error_message=str(e)
            )
    
    def _get_database_size(self) -> int:
        """Get database file size in bytes."""
        try:
            db_url = self.db_manager.config.database_url
            if "sqlite:///" in db_url:
                db_path = Path(db_url.replace("sqlite:///", ""))
                if db_path.exists():
                    return db_path.stat().st_size
            return 0
        except Exception as e:
            logger.warning(f"Failed to get database size: {e}")
            return 0
    
    def _get_directory_size(self, directory: Path) -> int:
        """Get total size of all files in directory."""
        try:
            total_size = 0
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
            return total_size
        except Exception as e:
            logger.warning(f"Failed to get directory size for {directory}: {e}")
            return 0
    
    def _get_temp_files_size(self) -> int:
        """Get size of temporary files."""
        try:
            temp_size = 0
            # Check for common temp file patterns
            for pattern in ["*.tmp", "*.temp", "*.bak", "*~"]:
                for temp_file in self.data_dir.glob(pattern):
                    if temp_file.is_file():
                        temp_size += temp_file.stat().st_size
            return temp_size
        except Exception as e:
            logger.warning(f"Failed to get temp files size: {e}")
            return 0
    
    def _get_available_space(self) -> int:
        """Get available disk space in bytes."""
        try:
            stat = shutil.disk_usage(self.data_dir)
            return stat.free
        except Exception as e:
            logger.warning(f"Failed to get available space: {e}")
            return 0


@graceful_degradation(service_name="storage_monitor")
async def generate_storage_report(
    db_manager: Optional[DatabaseManager] = None,
    data_dir: Optional[Path] = None,
    log_dir: Optional[Path] = None
) -> StorageReport:
    """
    Generate a comprehensive storage usage report.
    
    Args:
        db_manager: Database manager instance
        data_dir: Data directory path
        log_dir: Log directory path
        
    Returns:
        StorageReport: Comprehensive storage report
    """
    monitor = StorageMonitor(db_manager, data_dir, log_dir)
    return await monitor.generate_storage_report()


@graceful_degradation(service_name="storage_cleanup")
async def run_automated_cleanup(
    db_manager: Optional[DatabaseManager] = None,
    data_dir: Optional[Path] = None,
    log_dir: Optional[Path] = None,
    dry_run: bool = False
) -> List[CleanupResult]:
    """
    Run automated cleanup based on storage analysis.
    
    Args:
        db_manager: Database manager instance
        data_dir: Data directory path
        log_dir: Log directory path
        dry_run: If True, only simulate cleanup
        
    Returns:
        List[CleanupResult]: Results of all cleanup operations
    """
    monitor = StorageMonitor(db_manager, data_dir, log_dir)
    results = []
    
    # Generate report to get recommendations
    report = await monitor.generate_storage_report()
    
    # Execute recommended cleanups
    for recommendation in report.cleanup_recommendations:
        if recommendation["priority"] in ["high", "medium"]:
            action = recommendation["action"]
            
            if action == "delete_old_conversations":
                result = await monitor.cleanup_old_conversations(days_old=90, dry_run=dry_run)
                results.append(result)
            
            elif action == "delete_orphaned_data":
                result = await monitor.cleanup_orphaned_data(dry_run=dry_run)
                results.append(result)
            
            elif action == "vacuum_database" and not dry_run:
                result = await monitor.vacuum_database()
                results.append(result)
            
            elif action == "cleanup_old_logs":
                result = await monitor.cleanup_log_files(days_old=30)
                results.append(result)
    
    return results