"""
Duplicate Detection and Content Optimization Service

This service provides duplicate detection, content merging, and storage optimization
capabilities to prevent storage spam and maintain clean, efficient memory storage.
"""

import logging
import re
import json
from typing import Dict, List, Optional, Tuple, Any, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
from difflib import SequenceMatcher

from models.database import Conversation
from repositories.conversation_repository import ConversationRepository
from services.search_engine import SearchEngine
from services.vector_store import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class DuplicateMatch:
    """Represents a potential duplicate match."""
    conversation_id: str
    similarity_score: float
    match_type: str  # 'exact', 'near_duplicate', 'similar_content', 'related'
    confidence: float
    reasons: List[str]
    merge_candidate: bool = False


@dataclass
class ContentOptimization:
    """Represents content optimization recommendations."""
    action: str  # 'skip', 'merge', 'store_as_new', 'update_existing'
    target_conversation_id: Optional[str] = None
    merged_content: Optional[str] = None
    optimization_reasons: List[str] = None
    confidence_adjustment: float = 0.0


class DuplicateDetector:
    """
    Service for detecting duplicate content and optimizing storage efficiency.
    
    Provides capabilities for:
    - Detecting similar existing memories before storing
    - Content merging for related conversations
    - Low-confidence content filtering
    - Storage cleanup utilities
    """
    
    def __init__(
        self,
        conversation_repo: ConversationRepository,
        search_engine: SearchEngine
    ):
        """
        Initialize the duplicate detector.
        
        Args:
            conversation_repo: Repository for conversation data access
            search_engine: Search engine for similarity detection
        """
        self.conversation_repo = conversation_repo
        self.search_engine = search_engine
        
        # Configuration for duplicate detection
        self.similarity_thresholds = {
            'exact_match': 0.95,
            'near_duplicate': 0.85,
            'similar_content': 0.70,
            'related_content': 0.50
        }
        
        # Content filtering thresholds
        self.min_content_length = 20
        self.min_confidence_for_storage = 0.15
        self.max_similar_memories_per_day = 5
        
        # Cleanup configuration
        self.cleanup_thresholds = {
            'low_confidence_days': 30,
            'duplicate_cleanup_days': 7,
            'unused_memory_days': 90
        }
    
    async def check_for_duplicates(
        self,
        content: str,
        metadata: Dict[str, Any],
        tool_name: str = "",
        project_id: Optional[str] = None
    ) -> List[DuplicateMatch]:
        """
        Check for duplicate or similar existing memories.
        
        Args:
            content: Content to check for duplicates
            metadata: Content metadata
            tool_name: Name of the AI tool
            project_id: Optional project ID for scoped search
            
        Returns:
            List of potential duplicate matches
        """
        try:
            duplicates = []
            
            # Search for similar content using the search engine
            search_filters = {}
            if project_id:
                search_filters['project_id'] = project_id
            if tool_name:
                search_filters['tool_name'] = tool_name.lower()
            
            # Search with higher limit to catch more potential duplicates
            search_results = await self.search_engine.search(
                query=content,
                limit=20,
                filters=search_filters,
                search_type="hybrid"
            )
            
            # Analyze each search result for duplicate potential
            for result in search_results:
                duplicate_match = await self._analyze_duplicate_potential(
                    content, metadata, result, tool_name
                )
                if duplicate_match:
                    duplicates.append(duplicate_match)
            
            # Sort by similarity score (highest first)
            duplicates.sort(key=lambda x: x.similarity_score, reverse=True)
            
            logger.debug(f"Found {len(duplicates)} potential duplicates for content")
            return duplicates
            
        except Exception as e:
            logger.error(f"Error checking for duplicates: {e}")
            return []
    
    async def _analyze_duplicate_potential(
        self,
        new_content: str,
        new_metadata: Dict[str, Any],
        search_result: Any,
        tool_name: str
    ) -> Optional[DuplicateMatch]:
        """Analyze a search result for duplicate potential."""
        try:
            # Get the existing conversation
            conversation_id = search_result.metadata.get('conversation_id')
            if not conversation_id:
                return None
            
            existing_conversation = self.conversation_repo.get_by_id(conversation_id)
            if not existing_conversation:
                return None
            
            # Calculate detailed similarity
            similarity_analysis = self._calculate_detailed_similarity(
                new_content, new_metadata, existing_conversation, tool_name
            )
            
            if similarity_analysis['overall_score'] < self.similarity_thresholds['related_content']:
                return None
            
            # Determine match type and confidence
            match_type, confidence = self._determine_match_type(similarity_analysis)
            
            # Check if this is a merge candidate
            merge_candidate = (
                similarity_analysis['overall_score'] >= self.similarity_thresholds['similar_content'] and
                similarity_analysis['content_overlap'] > 0.6 and
                similarity_analysis['time_proximity'] > 0.3
            )
            
            return DuplicateMatch(
                conversation_id=conversation_id,
                similarity_score=similarity_analysis['overall_score'],
                match_type=match_type,
                confidence=confidence,
                reasons=similarity_analysis['reasons'],
                merge_candidate=merge_candidate
            )
            
        except Exception as e:
            logger.error(f"Error analyzing duplicate potential: {e}")
            return None
    
    def _calculate_detailed_similarity(
        self,
        new_content: str,
        new_metadata: Dict[str, Any],
        existing_conversation: Conversation,
        tool_name: str
    ) -> Dict[str, Any]:
        """Calculate detailed similarity metrics between new and existing content."""
        analysis = {
            'content_similarity': 0.0,
            'content_overlap': 0.0,
            'metadata_similarity': 0.0,
            'time_proximity': 0.0,
            'context_similarity': 0.0,
            'overall_score': 0.0,
            'reasons': []
        }
        
        # Content similarity using sequence matcher
        content_similarity = SequenceMatcher(
            None, 
            new_content.lower().strip(), 
            existing_conversation.content.lower().strip()
        ).ratio()
        analysis['content_similarity'] = content_similarity
        
        # Content overlap (shared words/phrases)
        new_words = set(re.findall(r'\b\w+\b', new_content.lower()))
        existing_words = set(re.findall(r'\b\w+\b', existing_conversation.content.lower()))
        
        if new_words and existing_words:
            overlap = len(new_words.intersection(existing_words))
            union = len(new_words.union(existing_words))
            analysis['content_overlap'] = overlap / union if union > 0 else 0.0
        
        # Metadata similarity
        existing_metadata = existing_conversation.conversation_metadata or {}
        metadata_score = self._calculate_metadata_similarity(new_metadata, existing_metadata)
        analysis['metadata_similarity'] = metadata_score
        
        # Time proximity (recent conversations are more likely to be duplicates)
        time_score = self._calculate_time_proximity(existing_conversation.timestamp)
        analysis['time_proximity'] = time_score
        
        # Context similarity (same tool, project, tags)
        context_score = self._calculate_context_similarity(
            tool_name, new_metadata, existing_conversation
        )
        analysis['context_similarity'] = context_score
        
        # Calculate overall score with weights
        weights = {
            'content_similarity': 0.4,
            'content_overlap': 0.25,
            'metadata_similarity': 0.15,
            'time_proximity': 0.1,
            'context_similarity': 0.1
        }
        
        overall_score = sum(
            analysis[key] * weight for key, weight in weights.items()
        )
        analysis['overall_score'] = overall_score
        
        # Generate reasons
        if content_similarity > 0.9:
            analysis['reasons'].append("Nearly identical content")
        elif content_similarity > 0.7:
            analysis['reasons'].append("Very similar content")
        elif content_similarity > 0.5:
            analysis['reasons'].append("Similar content structure")
        
        if analysis['content_overlap'] > 0.7:
            analysis['reasons'].append("High word overlap")
        
        if time_score > 0.8:
            analysis['reasons'].append("Recent conversation")
        
        if context_score > 0.7:
            analysis['reasons'].append("Same context (tool/project)")
        
        return analysis
    
    def _calculate_metadata_similarity(
        self, 
        new_metadata: Dict[str, Any], 
        existing_metadata: Dict[str, Any]
    ) -> float:
        """Calculate similarity between metadata objects."""
        if not new_metadata or not existing_metadata:
            return 0.0
        
        # Compare key metadata fields
        similarity_score = 0.0
        comparison_fields = ['category', 'analysis_category', 'storage_reason', 'extracted_info']
        
        matches = 0
        total_fields = 0
        
        for field in comparison_fields:
            if field in new_metadata or field in existing_metadata:
                total_fields += 1
                if (field in new_metadata and field in existing_metadata and
                    new_metadata[field] == existing_metadata[field]):
                    matches += 1
        
        if total_fields > 0:
            similarity_score = matches / total_fields
        
        return similarity_score
    
    def _calculate_time_proximity(self, existing_timestamp: datetime) -> float:
        """Calculate time proximity score (higher for more recent conversations)."""
        try:
            now = datetime.now(existing_timestamp.tzinfo) if existing_timestamp.tzinfo else datetime.now()
            time_diff = abs((now - existing_timestamp).total_seconds())
            
            # Score based on time difference
            if time_diff < 300:  # 5 minutes
                return 1.0
            elif time_diff < 1800:  # 30 minutes
                return 0.8
            elif time_diff < 3600:  # 1 hour
                return 0.6
            elif time_diff < 86400:  # 1 day
                return 0.4
            elif time_diff < 604800:  # 1 week
                return 0.2
            else:
                return 0.1
                
        except Exception:
            return 0.0
    
    def _calculate_context_similarity(
        self,
        tool_name: str,
        new_metadata: Dict[str, Any],
        existing_conversation: Conversation
    ) -> float:
        """Calculate context similarity (tool, project, tags)."""
        score = 0.0
        factors = 0
        
        # Tool name match
        if tool_name and existing_conversation.tool_name:
            factors += 1
            if tool_name.lower() == existing_conversation.tool_name.lower():
                score += 1.0
        
        # Project match
        new_project = new_metadata.get('project_id')
        if new_project or existing_conversation.project_id:
            factors += 1
            if new_project == existing_conversation.project_id:
                score += 1.0
        
        # Tag overlap
        new_tags = set(new_metadata.get('tags', []))
        existing_tags = set(existing_conversation.tags_list)
        
        if new_tags or existing_tags:
            factors += 1
            if new_tags and existing_tags:
                overlap = len(new_tags.intersection(existing_tags))
                union = len(new_tags.union(existing_tags))
                score += overlap / union if union > 0 else 0.0
        
        return score / factors if factors > 0 else 0.0
    
    def _determine_match_type(self, similarity_analysis: Dict[str, Any]) -> Tuple[str, float]:
        """Determine the type of match and confidence level."""
        overall_score = similarity_analysis['overall_score']
        content_similarity = similarity_analysis['content_similarity']
        
        if content_similarity >= self.similarity_thresholds['exact_match']:
            return 'exact', 0.95
        elif overall_score >= self.similarity_thresholds['near_duplicate']:
            return 'near_duplicate', 0.85
        elif overall_score >= self.similarity_thresholds['similar_content']:
            return 'similar_content', 0.70
        else:
            return 'related', 0.50
    
    async def optimize_storage_decision(
        self,
        content: str,
        metadata: Dict[str, Any],
        analysis_result: Dict[str, Any],
        tool_name: str = "",
        project_id: Optional[str] = None
    ) -> ContentOptimization:
        """
        Optimize storage decision based on duplicate detection and content analysis.
        
        Args:
            content: Content to be stored
            metadata: Content metadata
            analysis_result: Result from storage analyzer
            tool_name: Name of the AI tool
            project_id: Optional project ID
            
        Returns:
            ContentOptimization with recommended action
        """
        try:
            # Check for duplicates first
            duplicates = await self.check_for_duplicates(
                content, metadata, tool_name, project_id
            )
            
            # Filter low-confidence content
            if not self._passes_quality_filters(content, analysis_result):
                return ContentOptimization(
                    action='skip',
                    optimization_reasons=[
                        'Content does not meet quality thresholds',
                        f'Confidence {analysis_result.get("confidence", 0):.2f} below minimum {self.min_confidence_for_storage}',
                        f'Content length {len(content)} below minimum {self.min_content_length}'
                    ],
                    confidence_adjustment=-0.2
                )
            
            # Handle exact duplicates
            exact_duplicates = [d for d in duplicates if d.match_type == 'exact']
            if exact_duplicates:
                return ContentOptimization(
                    action='skip',
                    target_conversation_id=exact_duplicates[0].conversation_id,
                    optimization_reasons=[
                        'Exact duplicate found',
                        f'Similarity score: {exact_duplicates[0].similarity_score:.2f}'
                    ],
                    confidence_adjustment=-0.5
                )
            
            # Handle near duplicates with potential merging
            near_duplicates = [d for d in duplicates if d.match_type == 'near_duplicate' and d.merge_candidate]
            if near_duplicates:
                best_candidate = near_duplicates[0]
                merged_content = await self._create_merged_content(
                    content, best_candidate.conversation_id
                )
                
                if merged_content:
                    return ContentOptimization(
                        action='merge',
                        target_conversation_id=best_candidate.conversation_id,
                        merged_content=merged_content,
                        optimization_reasons=[
                            'Near duplicate with merge potential',
                            f'Similarity score: {best_candidate.similarity_score:.2f}',
                            'Content can be merged to avoid duplication'
                        ],
                        confidence_adjustment=0.1
                    )
            
            # Check for too many similar memories recently
            if await self._has_too_many_similar_recent_memories(content, tool_name, project_id):
                return ContentOptimization(
                    action='skip',
                    optimization_reasons=[
                        'Too many similar memories stored recently',
                        f'Exceeds limit of {self.max_similar_memories_per_day} per day'
                    ],
                    confidence_adjustment=-0.3
                )
            
            # Default: store as new with potential confidence adjustment
            confidence_adjustment = 0.0
            reasons = ['Content passes all optimization checks']
            
            # Boost confidence if no similar content exists
            if not duplicates:
                confidence_adjustment += 0.1
                reasons.append('No similar content found - unique memory')
            
            return ContentOptimization(
                action='store_as_new',
                optimization_reasons=reasons,
                confidence_adjustment=confidence_adjustment
            )
            
        except Exception as e:
            logger.error(f"Error optimizing storage decision: {e}")
            return ContentOptimization(
                action='store_as_new',
                optimization_reasons=['Optimization failed, defaulting to storage'],
                confidence_adjustment=0.0
            )
    
    def _passes_quality_filters(self, content: str, analysis_result: Dict[str, Any]) -> bool:
        """Check if content passes quality filters for storage."""
        # Check minimum content length
        if len(content.strip()) < self.min_content_length:
            return False
        
        # Check minimum confidence
        confidence = analysis_result.get('confidence', 0.0)
        if confidence < self.min_confidence_for_storage:
            return False
        
        # Check for spam-like patterns
        if self._is_spam_like_content(content):
            return False
        
        return True
    
    def _is_spam_like_content(self, content: str) -> bool:
        """Detect spam-like content patterns."""
        content_lower = content.lower()
        
        # Check for excessive repetition
        words = content_lower.split()
        if len(words) > 5:
            unique_words = set(words)
            if len(unique_words) / len(words) < 0.3:  # Less than 30% unique words
                return True
        
        # Check for very short, low-value content
        if len(content.strip()) < 10:
            return True
        
        # Check for common low-value phrases
        low_value_patterns = [
            r'^(ok|okay|yes|no|thanks|thank you)\.?$',
            r'^(got it|understood|makes sense)\.?$',
            r'^(hello|hi|hey)\.?$'
        ]
        
        for pattern in low_value_patterns:
            if re.match(pattern, content_lower.strip()):
                return True
        
        return False
    
    async def _create_merged_content(
        self, 
        new_content: str, 
        existing_conversation_id: str
    ) -> Optional[str]:
        """Create merged content from new content and existing conversation."""
        try:
            existing_conversation = self.conversation_repo.get_by_id(existing_conversation_id)
            if not existing_conversation:
                return None
            
            existing_content = existing_conversation.content
            
            # Simple merge strategy: combine unique parts
            new_lines = set(line.strip() for line in new_content.split('\n') if line.strip())
            existing_lines = set(line.strip() for line in existing_content.split('\n') if line.strip())
            
            # Find unique lines in new content
            unique_new_lines = new_lines - existing_lines
            
            if not unique_new_lines:
                return None  # No new information to merge
            
            # Create merged content
            merged_content = existing_content
            if unique_new_lines:
                merged_content += "\n\n--- Additional Information ---\n"
                merged_content += "\n".join(sorted(unique_new_lines))
            
            return merged_content
            
        except Exception as e:
            logger.error(f"Error creating merged content: {e}")
            return None
    
    async def _has_too_many_similar_recent_memories(
        self,
        content: str,
        tool_name: str,
        project_id: Optional[str],
        hours: int = 24
    ) -> bool:
        """Check if too many similar memories have been stored recently."""
        try:
            # Get recent conversations
            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent_conversations = self.conversation_repo.get_recent_by_tool(
                tool_name, hours=hours, limit=50
            )
            
            if project_id:
                recent_conversations = [
                    conv for conv in recent_conversations 
                    if conv.project_id == project_id
                ]
            
            # Count similar conversations
            similar_count = 0
            content_words = set(re.findall(r'\b\w+\b', content.lower()))
            
            for conversation in recent_conversations:
                conv_words = set(re.findall(r'\b\w+\b', conversation.content.lower()))
                
                if content_words and conv_words:
                    overlap = len(content_words.intersection(conv_words))
                    union = len(content_words.union(conv_words))
                    similarity = overlap / union if union > 0 else 0.0
                    
                    if similarity > 0.6:  # 60% similarity threshold
                        similar_count += 1
            
            return similar_count >= self.max_similar_memories_per_day
            
        except Exception as e:
            logger.error(f"Error checking recent similar memories: {e}")
            return False
    
    async def cleanup_low_confidence_memories(
        self,
        confidence_threshold: float = 0.3,
        days_old: int = 30,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Clean up low-confidence memories that are old and unused.
        
        Args:
            confidence_threshold: Minimum confidence to keep
            days_old: Minimum age in days for cleanup
            dry_run: If True, only return what would be cleaned up
            
        Returns:
            Cleanup results and statistics
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            # Find low-confidence conversations
            all_conversations = self.conversation_repo.list_all()
            cleanup_candidates = []
            
            for conversation in all_conversations:
                if conversation.timestamp > cutoff_date:
                    continue
                
                metadata = conversation.conversation_metadata or {}
                confidence = metadata.get('confidence', 1.0)  # Default to high confidence for manual entries
                
                if confidence < confidence_threshold:
                    # Additional checks to avoid cleaning up valuable content
                    if not self._is_valuable_despite_low_confidence(conversation):
                        cleanup_candidates.append(conversation)
            
            results = {
                'total_candidates': len(cleanup_candidates),
                'would_delete': len(cleanup_candidates) if dry_run else 0,
                'actually_deleted': 0,
                'space_saved_estimate': sum(len(c.content) for c in cleanup_candidates),
                'cleanup_candidates': [
                    {
                        'id': c.id,
                        'timestamp': c.timestamp.isoformat(),
                        'confidence': c.conversation_metadata.get('confidence', 1.0) if c.conversation_metadata else 1.0,
                        'content_length': len(c.content),
                        'tool_name': c.tool_name
                    }
                    for c in cleanup_candidates[:10]  # Limit to first 10 for preview
                ]
            }
            
            if not dry_run:
                # Actually delete the conversations
                deleted_count = 0
                for conversation in cleanup_candidates:
                    try:
                        # Remove from search index
                        await self.search_engine.remove_document(
                            conversation.id  # Assuming internal_id matches conversation_id
                        )
                        
                        # Delete from database
                        self.conversation_repo.delete(conversation.id)
                        deleted_count += 1
                        
                    except Exception as e:
                        logger.error(f"Error deleting conversation {conversation.id}: {e}")
                
                results['actually_deleted'] = deleted_count
            
            logger.info(f"Cleanup analysis: {results['total_candidates']} candidates found")
            return results
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return {
                'error': str(e),
                'total_candidates': 0,
                'would_delete': 0,
                'actually_deleted': 0
            }
    
    def _is_valuable_despite_low_confidence(self, conversation: Conversation) -> bool:
        """Check if a conversation should be kept despite low confidence."""
        # Keep conversations with explicit user requests
        if 'explicit_request' in conversation.tags_list:
            return True
        
        # Keep conversations with manual storage
        if 'manual_stored' in conversation.tags_list:
            return True
        
        # Keep conversations that are referenced by others
        if conversation.target_links:  # Has incoming references
            return True
        
        # Keep conversations with substantial content
        if len(conversation.content) > 1000:
            return True
        
        # Keep conversations with code snippets
        if '```' in conversation.content or 'def ' in conversation.content or 'function ' in conversation.content:
            return True
        
        return False
    
    async def get_duplicate_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get statistics about duplicate detection and storage optimization."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            recent_conversations = [
                conv for conv in self.conversation_repo.list_all()
                if conv.timestamp >= cutoff_date
            ]
            
            stats = {
                'total_conversations': len(recent_conversations),
                'auto_stored': 0,
                'manual_stored': 0,
                'high_confidence': 0,
                'low_confidence': 0,
                'with_duplicates_detected': 0,
                'average_confidence': 0.0,
                'storage_efficiency': 0.0
            }
            
            confidence_sum = 0.0
            confidence_count = 0
            
            for conversation in recent_conversations:
                metadata = conversation.conversation_metadata or {}
                
                if 'auto_stored' in conversation.tags_list:
                    stats['auto_stored'] += 1
                elif 'manual_stored' in conversation.tags_list:
                    stats['manual_stored'] += 1
                
                confidence = metadata.get('confidence')
                if confidence is not None:
                    confidence_sum += confidence
                    confidence_count += 1
                    
                    if confidence >= 0.8:
                        stats['high_confidence'] += 1
                    elif confidence < 0.5:
                        stats['low_confidence'] += 1
                
                # Check if duplicates were detected during storage
                if metadata.get('duplicates_detected'):
                    stats['with_duplicates_detected'] += 1
            
            if confidence_count > 0:
                stats['average_confidence'] = confidence_sum / confidence_count
            
            # Calculate storage efficiency (high confidence / total)
            if stats['total_conversations'] > 0:
                stats['storage_efficiency'] = stats['high_confidence'] / stats['total_conversations']
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting duplicate statistics: {e}")
            return {'error': str(e)}
    
    def get_optimization_config(self) -> Dict[str, Any]:
        """Get current optimization configuration."""
        return {
            'similarity_thresholds': self.similarity_thresholds,
            'min_content_length': self.min_content_length,
            'min_confidence_for_storage': self.min_confidence_for_storage,
            'max_similar_memories_per_day': self.max_similar_memories_per_day,
            'cleanup_thresholds': self.cleanup_thresholds
        }
    
    def update_optimization_config(self, config: Dict[str, Any]) -> None:
        """Update optimization configuration."""
        if 'similarity_thresholds' in config:
            self.similarity_thresholds.update(config['similarity_thresholds'])
        
        if 'min_content_length' in config:
            self.min_content_length = config['min_content_length']
        
        if 'min_confidence_for_storage' in config:
            self.min_confidence_for_storage = config['min_confidence_for_storage']
        
        if 'max_similar_memories_per_day' in config:
            self.max_similar_memories_per_day = config['max_similar_memories_per_day']
        
        if 'cleanup_thresholds' in config:
            self.cleanup_thresholds.update(config['cleanup_thresholds'])
        
        logger.info("Optimization configuration updated")