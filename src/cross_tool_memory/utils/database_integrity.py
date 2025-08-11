"""
Database integrity check utilities for the cross-tool memory system.

This module provides comprehensive database integrity checks, validation,
and repair utilities to ensure data consistency and reliability.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import text, func
from sqlalchemy.exc import SQLAlchemyError

from ..config.database import DatabaseManager, get_database_manager
from ..models.database import Conversation, Project, Preference, ContextLink
from ..utils.logging_config import get_component_logger, TimedOperation
from ..utils.error_handling import graceful_degradation

logger = get_component_logger("database_integrity")


class IntegrityIssueType(Enum):
    """Types of database integrity issues."""
    ORPHANED_RECORD = "orphaned_record"
    MISSING_REFERENCE = "missing_reference"
    INVALID_DATA = "invalid_data"
    CONSTRAINT_VIOLATION = "constraint_violation"
    CORRUPTED_JSON = "corrupted_json"
    DUPLICATE_RECORD = "duplicate_record"


@dataclass
class IntegrityIssue:
    """Represents a database integrity issue."""
    issue_type: IntegrityIssueType
    table_name: str
    record_id: str
    description: str
    severity: str  # "low", "medium", "high", "critical"
    auto_fixable: bool = False
    fix_suggestion: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class IntegrityCheckResult:
    """Results of a database integrity check."""
    timestamp: datetime
    total_checks: int
    issues_found: List[IntegrityIssue]
    duration_seconds: float
    tables_checked: List[str]
    summary: Dict[str, int]
    
    @property
    def is_healthy(self) -> bool:
        """Check if database is healthy (no critical or high severity issues)."""
        critical_issues = [
            issue for issue in self.issues_found 
            if issue.severity in ["critical", "high"]
        ]
        return len(critical_issues) == 0
    
    def get_issues_by_severity(self, severity: str) -> List[IntegrityIssue]:
        """Get issues filtered by severity level."""
        return [issue for issue in self.issues_found if issue.severity == severity]
    
    def get_auto_fixable_issues(self) -> List[IntegrityIssue]:
        """Get issues that can be automatically fixed."""
        return [issue for issue in self.issues_found if issue.auto_fixable]


class DatabaseIntegrityChecker:
    """Comprehensive database integrity checker."""
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """
        Initialize integrity checker.
        
        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager or get_database_manager()
        self.checks_run = 0
        self.issues_found = []
    
    async def run_full_integrity_check(self) -> IntegrityCheckResult:
        """
        Run comprehensive database integrity check.
        
        Returns:
            IntegrityCheckResult: Complete integrity check results
        """
        logger.info("Starting comprehensive database integrity check")
        start_time = time.time()
        
        self.checks_run = 0
        self.issues_found = []
        
        # List of all integrity checks to run
        checks = [
            self._check_orphaned_conversations,
            self._check_orphaned_context_links,
            self._check_missing_project_references,
            self._check_invalid_json_metadata,
            self._check_duplicate_conversations,
            self._check_constraint_violations,
            self._check_data_consistency,
            self._check_foreign_key_integrity,
            self._check_timestamp_validity,
            self._check_text_field_integrity
        ]
        
        # Run all checks
        for check in checks:
            try:
                with TimedOperation(f"integrity_check_{check.__name__}", logger):
                    await check()
            except Exception as e:
                logger.error(f"Integrity check {check.__name__} failed: {e}")
                self.issues_found.append(IntegrityIssue(
                    issue_type=IntegrityIssueType.CORRUPTED_JSON,
                    table_name="system",
                    record_id="check_failure",
                    description=f"Integrity check {check.__name__} failed: {str(e)}",
                    severity="high",
                    auto_fixable=False
                ))
        
        duration = time.time() - start_time
        
        # Generate summary
        summary = {
            "total_issues": len(self.issues_found),
            "critical": len([i for i in self.issues_found if i.severity == "critical"]),
            "high": len([i for i in self.issues_found if i.severity == "high"]),
            "medium": len([i for i in self.issues_found if i.severity == "medium"]),
            "low": len([i for i in self.issues_found if i.severity == "low"]),
            "auto_fixable": len([i for i in self.issues_found if i.auto_fixable])
        }
        
        result = IntegrityCheckResult(
            timestamp=datetime.now(),
            total_checks=self.checks_run,
            issues_found=self.issues_found.copy(),
            duration_seconds=duration,
            tables_checked=["conversations", "projects", "preferences", "context_links"],
            summary=summary
        )
        
        logger.info(f"Integrity check completed in {duration:.2f}s - Found {len(self.issues_found)} issues")
        return result
    
    async def _check_orphaned_conversations(self) -> None:
        """Check for conversations with invalid project references."""
        self.checks_run += 1
        
        try:
            async with self.db_manager.get_async_session() as session:
                # Find conversations with project_id that doesn't exist in projects table
                query = text("""
                    SELECT c.id, c.project_id 
                    FROM conversations c 
                    LEFT JOIN projects p ON c.project_id = p.id 
                    WHERE c.project_id IS NOT NULL AND p.id IS NULL
                """)
                
                result = await session.execute(query)
                orphaned = result.fetchall()
                
                for row in orphaned:
                    self.issues_found.append(IntegrityIssue(
                        issue_type=IntegrityIssueType.ORPHANED_RECORD,
                        table_name="conversations",
                        record_id=row.id,
                        description=f"Conversation references non-existent project: {row.project_id}",
                        severity="medium",
                        auto_fixable=True,
                        fix_suggestion="Set project_id to NULL or create missing project"
                    ))
                    
        except Exception as e:
            logger.error(f"Failed to check orphaned conversations: {e}")
    
    async def _check_orphaned_context_links(self) -> None:
        """Check for context links with invalid conversation references."""
        self.checks_run += 1
        
        try:
            async with self.db_manager.get_async_session() as session:
                # Check source conversation references
                query = text("""
                    SELECT cl.id, cl.source_conversation_id 
                    FROM context_links cl 
                    LEFT JOIN conversations c ON cl.source_conversation_id = c.id 
                    WHERE c.id IS NULL
                """)
                
                result = await session.execute(query)
                orphaned_sources = result.fetchall()
                
                for row in orphaned_sources:
                    self.issues_found.append(IntegrityIssue(
                        issue_type=IntegrityIssueType.ORPHANED_RECORD,
                        table_name="context_links",
                        record_id=str(row.id),
                        description=f"Context link references non-existent source conversation: {row.source_conversation_id}",
                        severity="high",
                        auto_fixable=True,
                        fix_suggestion="Delete orphaned context link"
                    ))
                
                # Check target conversation references
                query = text("""
                    SELECT cl.id, cl.target_conversation_id 
                    FROM context_links cl 
                    LEFT JOIN conversations c ON cl.target_conversation_id = c.id 
                    WHERE c.id IS NULL
                """)
                
                result = await session.execute(query)
                orphaned_targets = result.fetchall()
                
                for row in orphaned_targets:
                    self.issues_found.append(IntegrityIssue(
                        issue_type=IntegrityIssueType.ORPHANED_RECORD,
                        table_name="context_links",
                        record_id=str(row.id),
                        description=f"Context link references non-existent target conversation: {row.target_conversation_id}",
                        severity="high",
                        auto_fixable=True,
                        fix_suggestion="Delete orphaned context link"
                    ))
                    
        except Exception as e:
            logger.error(f"Failed to check orphaned context links: {e}")
    
    async def _check_missing_project_references(self) -> None:
        """Check for projects that should have conversations but don't."""
        self.checks_run += 1
        
        try:
            async with self.db_manager.get_async_session() as session:
                # Find projects with no conversations (might indicate data loss)
                query = text("""
                    SELECT p.id, p.name, p.created_at 
                    FROM projects p 
                    LEFT JOIN conversations c ON p.id = c.project_id 
                    WHERE c.id IS NULL 
                    AND p.created_at < datetime('now', '-1 day')
                """)
                
                result = await session.execute(query)
                empty_projects = result.fetchall()
                
                for row in empty_projects:
                    self.issues_found.append(IntegrityIssue(
                        issue_type=IntegrityIssueType.MISSING_REFERENCE,
                        table_name="projects",
                        record_id=row.id,
                        description=f"Project '{row.name}' has no conversations despite being created {row.created_at}",
                        severity="low",
                        auto_fixable=False,
                        fix_suggestion="Review if project should be deleted or if conversations are missing"
                    ))
                    
        except Exception as e:
            logger.error(f"Failed to check missing project references: {e}")
    
    async def _check_invalid_json_metadata(self) -> None:
        """Check for corrupted JSON in metadata fields."""
        self.checks_run += 1
        
        try:
            async with self.db_manager.get_async_session() as session:
                # Check conversations metadata
                conversations = await session.execute(
                    text("SELECT id, metadata FROM conversations WHERE metadata IS NOT NULL")
                )
                
                for row in conversations.fetchall():
                    try:
                        import json
                        if row.metadata:
                            json.loads(row.metadata)
                    except (json.JSONDecodeError, TypeError) as e:
                        self.issues_found.append(IntegrityIssue(
                            issue_type=IntegrityIssueType.CORRUPTED_JSON,
                            table_name="conversations",
                            record_id=row.id,
                            description=f"Invalid JSON in metadata field: {str(e)}",
                            severity="medium",
                            auto_fixable=True,
                            fix_suggestion="Reset metadata to empty JSON object"
                        ))
                        
        except Exception as e:
            logger.error(f"Failed to check invalid JSON metadata: {e}")
    
    async def _check_duplicate_conversations(self) -> None:
        """Check for potential duplicate conversations."""
        self.checks_run += 1
        
        try:
            async with self.db_manager.get_async_session() as session:
                # Find conversations with identical content and timestamps (within 1 minute)
                query = text("""
                    SELECT c1.id, c2.id, c1.content, c1.timestamp 
                    FROM conversations c1 
                    JOIN conversations c2 ON c1.content = c2.content 
                    AND c1.tool_name = c2.tool_name 
                    AND c1.project_id = c2.project_id 
                    AND abs(julianday(c1.timestamp) - julianday(c2.timestamp)) < 0.000694  -- 1 minute
                    AND c1.id < c2.id
                """)
                
                result = await session.execute(query)
                duplicates = result.fetchall()
                
                for row in duplicates:
                    self.issues_found.append(IntegrityIssue(
                        issue_type=IntegrityIssueType.DUPLICATE_RECORD,
                        table_name="conversations",
                        record_id=row[1],  # Second ID (newer)
                        description=f"Potential duplicate conversation (similar to {row[0]})",
                        severity="low",
                        auto_fixable=True,
                        fix_suggestion="Review and potentially delete duplicate conversation",
                        metadata={"original_id": row[0], "timestamp": str(row[3])}
                    ))
                    
        except Exception as e:
            logger.error(f"Failed to check duplicate conversations: {e}")
    
    async def _check_constraint_violations(self) -> None:
        """Check for constraint violations."""
        self.checks_run += 1
        
        try:
            async with self.db_manager.get_async_session() as session:
                # Check for NULL values in required fields
                required_fields = [
                    ("conversations", "id", "Conversation ID cannot be NULL"),
                    ("conversations", "tool_name", "Tool name cannot be NULL"),
                    ("conversations", "content", "Content cannot be NULL"),
                    ("projects", "id", "Project ID cannot be NULL"),
                    ("projects", "name", "Project name cannot be NULL"),
                    ("preferences", "key", "Preference key cannot be NULL"),
                    ("preferences", "value", "Preference value cannot be NULL")
                ]
                
                for table, field, description in required_fields:
                    query = text(f"SELECT COUNT(*) as count FROM {table} WHERE {field} IS NULL")
                    result = await session.execute(query)
                    count = result.scalar()
                    
                    if count > 0:
                        self.issues_found.append(IntegrityIssue(
                            issue_type=IntegrityIssueType.CONSTRAINT_VIOLATION,
                            table_name=table,
                            record_id="multiple",
                            description=f"{description} - Found {count} violations",
                            severity="critical",
                            auto_fixable=False,
                            fix_suggestion=f"Delete or fix records with NULL {field}"
                        ))
                        
        except Exception as e:
            logger.error(f"Failed to check constraint violations: {e}")
    
    async def _check_data_consistency(self) -> None:
        """Check for data consistency issues."""
        self.checks_run += 1
        
        try:
            async with self.db_manager.get_async_session() as session:
                # Check for conversations with empty content
                query = text("SELECT id FROM conversations WHERE content = '' OR LENGTH(TRIM(content)) = 0")
                result = await session.execute(query)
                empty_content = result.fetchall()
                
                for row in empty_content:
                    self.issues_found.append(IntegrityIssue(
                        issue_type=IntegrityIssueType.INVALID_DATA,
                        table_name="conversations",
                        record_id=row.id,
                        description="Conversation has empty content",
                        severity="medium",
                        auto_fixable=True,
                        fix_suggestion="Delete conversation with empty content"
                    ))
                
                # Check for projects with empty names
                query = text("SELECT id FROM projects WHERE name = '' OR LENGTH(TRIM(name)) = 0")
                result = await session.execute(query)
                empty_names = result.fetchall()
                
                for row in empty_names:
                    self.issues_found.append(IntegrityIssue(
                        issue_type=IntegrityIssueType.INVALID_DATA,
                        table_name="projects",
                        record_id=row.id,
                        description="Project has empty name",
                        severity="high",
                        auto_fixable=False,
                        fix_suggestion="Provide a valid name for the project"
                    ))
                    
        except Exception as e:
            logger.error(f"Failed to check data consistency: {e}")
    
    async def _check_foreign_key_integrity(self) -> None:
        """Check foreign key integrity."""
        self.checks_run += 1
        
        try:
            async with self.db_manager.get_async_session() as session:
                # Enable foreign key checking temporarily
                await session.execute(text("PRAGMA foreign_key_check"))
                
                # The above will raise an exception if there are foreign key violations
                # If we get here, foreign keys are intact
                
        except Exception as e:
            # Foreign key violations found
            self.issues_found.append(IntegrityIssue(
                issue_type=IntegrityIssueType.CONSTRAINT_VIOLATION,
                table_name="system",
                record_id="foreign_keys",
                description=f"Foreign key constraint violations detected: {str(e)}",
                severity="critical",
                auto_fixable=False,
                fix_suggestion="Run detailed foreign key analysis and fix violations"
            ))
    
    async def _check_timestamp_validity(self) -> None:
        """Check for invalid timestamps."""
        self.checks_run += 1
        
        try:
            async with self.db_manager.get_async_session() as session:
                # Check for future timestamps (more than 1 hour in the future)
                future_cutoff = datetime.now() + timedelta(hours=1)
                
                query = text("""
                    SELECT id, timestamp FROM conversations 
                    WHERE timestamp > :future_cutoff
                """)
                
                result = await session.execute(query, {"future_cutoff": future_cutoff})
                future_timestamps = result.fetchall()
                
                for row in future_timestamps:
                    self.issues_found.append(IntegrityIssue(
                        issue_type=IntegrityIssueType.INVALID_DATA,
                        table_name="conversations",
                        record_id=row.id,
                        description=f"Conversation has future timestamp: {row.timestamp}",
                        severity="medium",
                        auto_fixable=True,
                        fix_suggestion="Update timestamp to current time"
                    ))
                
                # Check for very old timestamps (before 2020)
                old_cutoff = datetime(2020, 1, 1)
                
                query = text("""
                    SELECT id, timestamp FROM conversations 
                    WHERE timestamp < :old_cutoff
                """)
                
                result = await session.execute(query, {"old_cutoff": old_cutoff})
                old_timestamps = result.fetchall()
                
                for row in old_timestamps:
                    self.issues_found.append(IntegrityIssue(
                        issue_type=IntegrityIssueType.INVALID_DATA,
                        table_name="conversations",
                        record_id=row.id,
                        description=f"Conversation has suspiciously old timestamp: {row.timestamp}",
                        severity="low",
                        auto_fixable=False,
                        fix_suggestion="Review timestamp validity"
                    ))
                    
        except Exception as e:
            logger.error(f"Failed to check timestamp validity: {e}")
    
    async def _check_text_field_integrity(self) -> None:
        """Check text field integrity and encoding."""
        self.checks_run += 1
        
        try:
            async with self.db_manager.get_async_session() as session:
                # Check for extremely long content that might cause issues
                query = text("""
                    SELECT id, LENGTH(content) as content_length 
                    FROM conversations 
                    WHERE LENGTH(content) > 1000000  -- 1MB
                """)
                
                result = await session.execute(query)
                long_content = result.fetchall()
                
                for row in long_content:
                    self.issues_found.append(IntegrityIssue(
                        issue_type=IntegrityIssueType.INVALID_DATA,
                        table_name="conversations",
                        record_id=row.id,
                        description=f"Conversation has extremely long content: {row.content_length} characters",
                        severity="low",
                        auto_fixable=False,
                        fix_suggestion="Review if content length is appropriate"
                    ))
                    
        except Exception as e:
            logger.error(f"Failed to check text field integrity: {e}")
    
    async def auto_fix_issues(self, issues: List[IntegrityIssue]) -> Dict[str, Any]:
        """
        Automatically fix issues that can be safely repaired.
        
        Args:
            issues: List of issues to fix
            
        Returns:
            Dict with fix results
        """
        logger.info(f"Attempting to auto-fix {len(issues)} issues")
        
        fixed_count = 0
        failed_fixes = []
        
        for issue in issues:
            if not issue.auto_fixable:
                continue
                
            try:
                success = await self._fix_single_issue(issue)
                if success:
                    fixed_count += 1
                    logger.info(f"Fixed issue: {issue.description}")
                else:
                    failed_fixes.append(issue)
                    
            except Exception as e:
                logger.error(f"Failed to fix issue {issue.record_id}: {e}")
                failed_fixes.append(issue)
        
        return {
            "total_issues": len(issues),
            "fixed_count": fixed_count,
            "failed_count": len(failed_fixes),
            "failed_fixes": [
                {"id": issue.record_id, "description": issue.description}
                for issue in failed_fixes
            ]
        }
    
    async def _fix_single_issue(self, issue: IntegrityIssue) -> bool:
        """
        Fix a single integrity issue.
        
        Args:
            issue: Issue to fix
            
        Returns:
            bool: True if fixed successfully
        """
        try:
            async with self.db_manager.get_async_session() as session:
                if issue.issue_type == IntegrityIssueType.ORPHANED_RECORD:
                    if issue.table_name == "conversations":
                        # Set project_id to NULL for orphaned conversations
                        await session.execute(
                            text("UPDATE conversations SET project_id = NULL WHERE id = :id"),
                            {"id": issue.record_id}
                        )
                    elif issue.table_name == "context_links":
                        # Delete orphaned context links
                        await session.execute(
                            text("DELETE FROM context_links WHERE id = :id"),
                            {"id": int(issue.record_id)}
                        )
                
                elif issue.issue_type == IntegrityIssueType.CORRUPTED_JSON:
                    if issue.table_name == "conversations":
                        # Reset corrupted metadata to empty JSON
                        await session.execute(
                            text("UPDATE conversations SET metadata = '{}' WHERE id = :id"),
                            {"id": issue.record_id}
                        )
                
                elif issue.issue_type == IntegrityIssueType.INVALID_DATA:
                    if "empty content" in issue.description:
                        # Delete conversations with empty content
                        await session.execute(
                            text("DELETE FROM conversations WHERE id = :id"),
                            {"id": issue.record_id}
                        )
                    elif "future timestamp" in issue.description:
                        # Update future timestamps to current time
                        await session.execute(
                            text("UPDATE conversations SET timestamp = CURRENT_TIMESTAMP WHERE id = :id"),
                            {"id": issue.record_id}
                        )
                
                elif issue.issue_type == IntegrityIssueType.DUPLICATE_RECORD:
                    # Delete duplicate conversations (keep the original)
                    await session.execute(
                        text("DELETE FROM conversations WHERE id = :id"),
                        {"id": issue.record_id}
                    )
                
                await session.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to fix issue {issue.record_id}: {e}")
            return False


@graceful_degradation(service_name="database_integrity")
async def run_integrity_check(
    db_manager: Optional[DatabaseManager] = None,
    auto_fix: bool = False
) -> IntegrityCheckResult:
    """
    Run a comprehensive database integrity check.
    
    Args:
        db_manager: Database manager instance
        auto_fix: Whether to automatically fix issues that can be safely repaired
        
    Returns:
        IntegrityCheckResult: Results of the integrity check
    """
    checker = DatabaseIntegrityChecker(db_manager)
    result = await checker.run_full_integrity_check()
    
    if auto_fix and result.get_auto_fixable_issues():
        logger.info("Auto-fixing issues...")
        fix_results = await checker.auto_fix_issues(result.get_auto_fixable_issues())
        logger.info(f"Auto-fix completed: {fix_results['fixed_count']} issues fixed")
    
    return result


@graceful_degradation(service_name="database_integrity")
def run_integrity_check_sync(
    db_manager: Optional[DatabaseManager] = None,
    auto_fix: bool = False
) -> IntegrityCheckResult:
    """
    Synchronous wrapper for integrity check.
    
    Args:
        db_manager: Database manager instance
        auto_fix: Whether to automatically fix issues
        
    Returns:
        IntegrityCheckResult: Results of the integrity check
    """
    return asyncio.run(run_integrity_check(db_manager, auto_fix))