"""
Conversation processor that orchestrates context management and tagging.

This service combines context management, tagging, and conversation linking
to provide comprehensive conversation processing capabilities.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..models.database import Conversation
from ..models.schemas import ConversationUpdate
from ..repositories.conversation_repository import ConversationRepository
from ..repositories.project_repository import ProjectRepository
from ..config.database import DatabaseManager
from .context_manager import ContextManager
from .tagging_service import TaggingService

logger = logging.getLogger(__name__)


class ConversationProcessor:
    """Orchestrates conversation processing including context and tagging."""
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        conversation_repo: ConversationRepository,
        project_repo: ProjectRepository,
        context_manager: Optional[ContextManager] = None,
        tagging_service: Optional[TaggingService] = None
    ):
        """
        Initialize conversation processor.
        
        Args:
            db_manager: Database manager instance
            conversation_repo: Conversation repository
            project_repo: Project repository
            context_manager: Optional context manager (will create if None)
            tagging_service: Optional tagging service (will create if None)
        """
        self.db_manager = db_manager
        self.conversation_repo = conversation_repo
        self.project_repo = project_repo
        
        # Initialize services
        self.context_manager = context_manager or ContextManager(
            db_manager, conversation_repo, project_repo
        )
        self.tagging_service = tagging_service or TaggingService()
        
        # Initialize NLP if available
        self._nlp_initialized = False

    async def initialize(self) -> None:
        """Initialize the processor and its services."""
        if not self._nlp_initialized:
            await self.tagging_service.initialize_nlp()
            self._nlp_initialized = True
            logger.info("Conversation processor initialized")

    async def process_conversation(
        self,
        conversation: Conversation,
        auto_tag: bool = True,
        auto_link: bool = True,
        auto_project_detect: bool = True
    ) -> Dict[str, Any]:
        """
        Process a conversation with context management and tagging.
        
        Args:
            conversation: Conversation to process
            auto_tag: Whether to automatically generate tags
            auto_link: Whether to automatically create context links
            auto_project_detect: Whether to automatically detect project
            
        Returns:
            Dict[str, Any]: Processing results
        """
        try:
            await self.initialize()
            
            results = {
                'conversation_id': conversation.id,
                'processing_timestamp': datetime.utcnow(),
                'tags_generated': [],
                'tags_added': 0,
                'project_detected': False,
                'project_id': conversation.project_id,
                'context_processed': False,
                'links_created': 0,
                'categories': {},
                'errors': []
            }
            
            # Generate and apply tags
            if auto_tag:
                try:
                    new_tags = await self._process_tags(conversation)
                    results['tags_generated'] = new_tags
                    results['tags_added'] = len(new_tags)
                except Exception as e:
                    logger.error(f"Error processing tags for conversation {conversation.id}: {e}")
                    results['errors'].append(f"Tag processing failed: {str(e)}")
            
            # Process context (project detection, categorization, linking)
            if auto_project_detect or auto_link:
                try:
                    context_results = await self.context_manager.process_conversation_context(
                        conversation
                    )
                    
                    results['project_detected'] = context_results.get('project_detected', False)
                    results['project_id'] = context_results.get('project_id') or conversation.project_id
                    results['context_processed'] = True
                    results['links_created'] = context_results.get('context_links_created', 0)
                    results['categories'] = context_results.get('categories', {})
                    
                    # Update conversation object with new project_id if detected
                    if context_results.get('project_detected') and context_results.get('project_id'):
                        conversation.project_id = context_results['project_id']
                    
                except Exception as e:
                    logger.error(f"Error processing context for conversation {conversation.id}: {e}")
                    results['errors'].append(f"Context processing failed: {str(e)}")
            
            logger.info(f"Processed conversation {conversation.id}: "
                       f"tags={results['tags_added']}, "
                       f"project_detected={results['project_detected']}, "
                       f"links={results['links_created']}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing conversation {conversation.id}: {e}")
            return {
                'conversation_id': conversation.id,
                'processing_timestamp': datetime.utcnow(),
                'tags_generated': [],
                'tags_added': 0,
                'project_detected': False,
                'project_id': conversation.project_id,
                'context_processed': False,
                'links_created': 0,
                'categories': {},
                'errors': [f"Processing failed: {str(e)}"]
            }

    async def _process_tags(self, conversation: Conversation) -> List[str]:
        """Process tags for a conversation."""
        try:
            # Generate new tags
            new_tags = self.tagging_service.generate_tags(
                conversation.content,
                conversation.conversation_metadata
            )
            
            if not new_tags:
                return []
            
            # Get existing tags
            existing_tags = set(conversation.tags_list) if conversation.tags else set()
            
            # Combine with existing tags (avoid duplicates)
            all_tags = list(existing_tags.union(set(new_tags)))
            
            # Update conversation if new tags were added
            if set(all_tags) != existing_tags:
                update_data = ConversationUpdate(tags=all_tags)
                updated_conversation = self.conversation_repo.update(conversation.id, update_data)
                
                if updated_conversation:
                    conversation.tags = updated_conversation.tags
                    logger.debug(f"Updated tags for conversation {conversation.id}: {all_tags}")
                
                # Return only the newly added tags
                return [tag for tag in new_tags if tag not in existing_tags]
            
            return []
            
        except Exception as e:
            logger.error(f"Error processing tags for conversation {conversation.id}: {e}")
            raise

    async def process_conversation_batch(
        self,
        conversations: List[Conversation],
        auto_tag: bool = True,
        auto_link: bool = True,
        auto_project_detect: bool = True
    ) -> Dict[str, Any]:
        """
        Process multiple conversations in batch.
        
        Args:
            conversations: List of conversations to process
            auto_tag: Whether to automatically generate tags
            auto_link: Whether to automatically create context links
            auto_project_detect: Whether to automatically detect project
            
        Returns:
            Dict[str, Any]: Batch processing results
        """
        try:
            await self.initialize()
            
            batch_results = {
                'total_conversations': len(conversations),
                'processed_successfully': 0,
                'failed_conversations': [],
                'total_tags_added': 0,
                'total_links_created': 0,
                'projects_detected': 0,
                'processing_timestamp': datetime.utcnow(),
                'individual_results': []
            }
            
            for conversation in conversations:
                try:
                    result = await self.process_conversation(
                        conversation, auto_tag, auto_link, auto_project_detect
                    )
                    
                    batch_results['individual_results'].append(result)
                    batch_results['processed_successfully'] += 1
                    batch_results['total_tags_added'] += result.get('tags_added', 0)
                    batch_results['total_links_created'] += result.get('links_created', 0)
                    
                    if result.get('project_detected'):
                        batch_results['projects_detected'] += 1
                    
                except Exception as e:
                    logger.error(f"Failed to process conversation {conversation.id}: {e}")
                    batch_results['failed_conversations'].append({
                        'conversation_id': conversation.id,
                        'error': str(e)
                    })
            
            logger.info(f"Batch processed {batch_results['processed_successfully']}/{batch_results['total_conversations']} conversations")
            return batch_results
            
        except Exception as e:
            logger.error(f"Error in batch processing: {e}")
            raise

    async def reprocess_project_conversations(
        self,
        project_id: str,
        force_retag: bool = False,
        force_relink: bool = False
    ) -> Dict[str, Any]:
        """
        Reprocess all conversations for a specific project.
        
        Args:
            project_id: Project ID to reprocess
            force_retag: Whether to regenerate all tags
            force_relink: Whether to recreate all context links
            
        Returns:
            Dict[str, Any]: Reprocessing results
        """
        try:
            # Get all conversations for the project
            conversations = self.conversation_repo.get_by_project(project_id, limit=1000)
            
            if not conversations:
                return {
                    'project_id': project_id,
                    'total_conversations': 0,
                    'processed': 0,
                    'message': 'No conversations found for project'
                }
            
            # If force_retag, clear existing tags
            if force_retag:
                for conversation in conversations:
                    update_data = ConversationUpdate(tags=[])
                    self.conversation_repo.update(conversation.id, update_data)
            
            # If force_relink, clear existing context links
            if force_relink:
                # This would require a context link repository method
                # For now, just log the intention
                logger.info(f"Force relink requested for project {project_id}")
            
            # Process all conversations
            results = await self.process_conversation_batch(
                conversations,
                auto_tag=True,
                auto_link=True,
                auto_project_detect=False  # Project already known
            )
            
            # Generate project-level tags
            project_tags = await self._generate_project_tags(project_id, conversations)
            
            results['project_id'] = project_id
            results['project_tags_suggested'] = project_tags
            
            return results
            
        except Exception as e:
            logger.error(f"Error reprocessing project {project_id}: {e}")
            raise

    async def _generate_project_tags(
        self,
        project_id: str,
        conversations: List[Conversation]
    ) -> List[str]:
        """Generate project-level tags based on conversations."""
        try:
            conversation_contents = [conv.content for conv in conversations]
            project_tags = self.tagging_service.suggest_tags_for_project(conversation_contents)
            
            logger.info(f"Generated {len(project_tags)} project-level tags for project {project_id}")
            return project_tags
            
        except Exception as e:
            logger.error(f"Error generating project tags for {project_id}: {e}")
            return []

    async def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        try:
            total_conversations = self.conversation_repo.count_total()
            
            # Get conversations with tags
            all_conversations = self.conversation_repo.list_all(limit=1000)
            tagged_conversations = sum(1 for conv in all_conversations if conv.tags)
            
            # Get project assignment stats
            assigned_conversations = sum(1 for conv in all_conversations if conv.project_id)
            
            stats = {
                'total_conversations': total_conversations,
                'tagged_conversations': tagged_conversations,
                'tagging_coverage': tagged_conversations / total_conversations if total_conversations > 0 else 0,
                'project_assigned_conversations': assigned_conversations,
                'project_assignment_coverage': assigned_conversations / total_conversations if total_conversations > 0 else 0,
                'nlp_initialized': self._nlp_initialized,
                'timestamp': datetime.utcnow()
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting processing stats: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.utcnow()
            }

    async def suggest_improvements(self, conversation_id: str) -> Dict[str, Any]:
        """
        Suggest improvements for a conversation's tags and context.
        
        Args:
            conversation_id: Conversation ID to analyze
            
        Returns:
            Dict[str, Any]: Improvement suggestions
        """
        try:
            conversation = self.conversation_repo.get_by_id(conversation_id)
            if not conversation:
                return {'error': 'Conversation not found'}
            
            suggestions = {
                'conversation_id': conversation_id,
                'current_tags': conversation.tags_list if conversation.tags else [],
                'suggested_additional_tags': [],
                'project_suggestions': [],
                'context_improvements': []
            }
            
            # Generate fresh tags to compare
            fresh_tags = self.tagging_service.generate_tags(
                conversation.content,
                conversation.conversation_metadata
            )
            
            current_tags = set(conversation.tags_list) if conversation.tags else set()
            new_tag_suggestions = [tag for tag in fresh_tags if tag not in current_tags]
            suggestions['suggested_additional_tags'] = new_tag_suggestions
            
            # Project suggestions
            if not conversation.project_id:
                project_id = await self.context_manager.detect_project_from_content(
                    conversation.content,
                    conversation.conversation_metadata
                )
                if project_id:
                    project = self.project_repo.get_by_id(project_id)
                    if project:
                        suggestions['project_suggestions'].append({
                            'project_id': project_id,
                            'project_name': project.name,
                            'confidence': 'medium'
                        })
            
            # Context improvements
            categories = await self.context_manager.categorize_conversation(conversation)
            if categories.get('technical_domain'):
                suggestions['context_improvements'].append({
                    'type': 'categorization',
                    'domains': categories['technical_domain'],
                    'activities': categories.get('activity_type', [])
                })
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Error generating suggestions for conversation {conversation_id}: {e}")
            return {'error': str(e)}

    def get_tag_statistics(self) -> Dict[str, Any]:
        """Get statistics about tag usage."""
        try:
            all_conversations = self.conversation_repo.list_all(limit=1000)
            
            tag_counts = {}
            total_tagged = 0
            
            for conversation in all_conversations:
                if conversation.tags:
                    total_tagged += 1
                    tags = conversation.tags_list
                    for tag in tags:
                        tag_counts[tag] = tag_counts.get(tag, 0) + 1
            
            # Sort tags by frequency
            sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
            
            return {
                'total_conversations': len(all_conversations),
                'tagged_conversations': total_tagged,
                'unique_tags': len(tag_counts),
                'most_common_tags': sorted_tags[:20],
                'tag_categories': self.tagging_service.get_tag_categories(),
                'timestamp': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error getting tag statistics: {e}")
            return {'error': str(e)}