"""
Context management service for automatic project detection and categorization.

This service analyzes conversation content to automatically detect projects,
categorize conversations, and maintain context relationships.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Set, Tuple
from pathlib import Path

from models.database import Conversation, Project, ContextLink
from models.schemas import RelationshipType
from repositories.conversation_repository import ConversationRepository
from repositories.project_repository import ProjectRepository
from config.database import DatabaseManager, DatabaseConnectionError

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages conversation context, project detection, and categorization."""
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        conversation_repo: ConversationRepository,
        project_repo: ProjectRepository
    ):
        """
        Initialize context manager.
        
        Args:
            db_manager: Database manager instance
            conversation_repo: Conversation repository
            project_repo: Project repository
        """
        self.db_manager = db_manager
        self.conversation_repo = conversation_repo
        self.project_repo = project_repo
        
        # Common project indicators
        self.project_indicators = {
            'file_extensions': {
                '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h',
                '.cs', '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.scala',
                '.html', '.css', '.scss', '.sass', '.vue', '.svelte', '.json',
                '.xml', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf',
                '.md', '.rst', '.txt', '.sql', '.sh', '.bat', '.ps1'
            },
            'framework_keywords': {
                'react', 'vue', 'angular', 'django', 'flask', 'fastapi', 'express',
                'spring', 'laravel', 'rails', 'nextjs', 'nuxt', 'gatsby', 'svelte',
                'electron', 'react-native', 'flutter', 'ionic', 'cordova'
            },
            'tool_keywords': {
                'git', 'github', 'gitlab', 'bitbucket', 'docker', 'kubernetes',
                'jenkins', 'travis', 'circleci', 'webpack', 'vite', 'rollup',
                'babel', 'eslint', 'prettier', 'jest', 'cypress', 'playwright'
            },
            'language_keywords': {
                'python', 'javascript', 'typescript', 'java', 'cpp', 'c++',
                'csharp', 'c#', 'php', 'ruby', 'golang', 'go', 'rust',
                'swift', 'kotlin', 'scala', 'html', 'css', 'sql'
            }
        }
        
        # Path patterns that indicate project structure
        self.path_patterns = [
            r'(?:^|[\s/\\])([a-zA-Z0-9_-]+)[\s/\\](?:src|lib|app|components|pages|views|models|controllers|services|utils|tests?|spec)',
            r'(?:^|[\s/\\])([a-zA-Z0-9_-]+)[\s/\\](?:package\.json|requirements\.txt|Cargo\.toml|pom\.xml|build\.gradle|Gemfile|composer\.json)',
            r'(?:^|[\s/\\])([a-zA-Z0-9_-]+)[\s/\\](?:\.git|\.gitignore|README\.md|LICENSE)',
            r'(?:^|[\s/\\])([a-zA-Z0-9_-]+)[\s/\\](?:node_modules|venv|env|\.venv|target|build|dist|out)',
        ]

    async def detect_project_from_content(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Detect project from conversation content and metadata.
        
        Args:
            content: Conversation content
            metadata: Optional conversation metadata
            
        Returns:
            Optional[str]: Project ID if detected, None otherwise
        """
        try:
            # First check metadata for explicit project information
            if metadata:
                if 'project_id' in metadata and metadata['project_id']:
                    return metadata['project_id']
                
                if 'project_name' in metadata and metadata['project_name']:
                    project = await self._find_or_create_project_by_name(metadata['project_name'])
                    return project.id if project else None
                
                if 'file_path' in metadata and metadata['file_path']:
                    project_name = self._extract_project_from_path(metadata['file_path'])
                    if project_name:
                        project = await self._find_or_create_project_by_name(project_name)
                        return project.id if project else None
            
            # Extract potential project names from content
            project_candidates = self._extract_project_candidates(content)
            
            if not project_candidates:
                return None
            
            # Try to match with existing projects first
            existing_projects = self.project_repo.list_all()
            for candidate in project_candidates:
                for project in existing_projects:
                    if self._is_project_match(candidate, project.name, project.path):
                        # Update project last accessed
                        self.project_repo.update_last_accessed(project.id)
                        return project.id
            
            # If no existing project matches, create a new one for the best candidate
            best_candidate = self._select_best_project_candidate(project_candidates, content)
            if best_candidate:
                project = await self._find_or_create_project_by_name(best_candidate)
                return project.id if project else None
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting project from content: {e}")
            return None

    def _extract_project_candidates(self, content: str) -> List[str]:
        """Extract potential project names from content."""
        candidates = set()
        
        # Extract from file paths
        for pattern in self.path_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            candidates.update(matches)
        
        # Extract from common project structure mentions
        project_structure_patterns = [
            r'(?:project|repo|repository|codebase)\s+(?:called|named|is)\s+([a-zA-Z0-9_-]+)',
            r'(?:repository|repo)\s+(?:called|named|is)\s+([a-zA-Z0-9_-]+)',
            r'working\s+on\s+(?:the\s+)?([a-zA-Z0-9_-]+)\s+(?:project|app|application)',
            r'(?:^|\s)([a-zA-Z0-9_-]+)(?:\.git|/\.git)',
            r'(?:cd|clone|checkout)\s+([a-zA-Z0-9_-]+)',
            r'github\.com/[^/]+/([a-zA-Z0-9_-]+)',
            r'gitlab\.com/[^/]+/([a-zA-Z0-9_-]+)',
        ]
        
        for pattern in project_structure_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            candidates.update(matches)
        
        # Filter out common false positives
        false_positives = {
            'src', 'lib', 'app', 'test', 'tests', 'spec', 'build', 'dist',
            'node_modules', 'venv', 'env', 'target', 'out', 'bin', 'obj',
            'main', 'index', 'home', 'root', 'base', 'core', 'common',
            'utils', 'helpers', 'shared', 'public', 'static', 'assets'
        }
        
        filtered_candidates = [
            candidate for candidate in candidates
            if len(candidate) >= 2 and candidate.lower() not in false_positives
        ]
        
        return filtered_candidates

    def _extract_project_from_path(self, file_path: str) -> Optional[str]:
        """Extract project name from file path."""
        try:
            # Handle both Unix and Windows paths
            if '\\' in file_path:
                # Windows path
                parts = file_path.replace('\\', '/').split('/')
            else:
                # Unix path
                parts = file_path.split('/')
            
            # Remove empty parts
            parts = [part for part in parts if part]
            
            # Look for common project root indicators
            for i, part in enumerate(parts):
                if part in {'.git', 'package.json', 'requirements.txt', 'Cargo.toml', 'pom.xml'}:
                    if i > 0:
                        return parts[i - 1]
                
                # Check if this part looks like a project root
                if i < len(parts) - 1:  # Not the last part
                    next_part = parts[i + 1]
                    if next_part in {'src', 'lib', 'app', 'components', 'pages', 'views'}:
                        return part
            
            # Fallback: use the first non-root directory
            if len(parts) > 1:
                # Skip common root directories
                start_idx = 0
                if parts[0] in {'home', 'Users', 'projects', 'workspace', 'dev'}:
                    start_idx = 1
                if start_idx < len(parts):
                    return parts[start_idx]
            
            return None
            
        except Exception:
            return None

    def _is_project_match(self, candidate: str, project_name: str, project_path: Optional[str]) -> bool:
        """Check if a candidate matches an existing project."""
        # Exact name match
        if candidate.lower() == project_name.lower():
            return True
        
        # Check if candidate is contained in project name or vice versa
        if (candidate.lower() in project_name.lower() or 
            project_name.lower() in candidate.lower()):
            return True
        
        # Check path-based matching
        if project_path:
            path_parts = Path(project_path).parts
            if any(candidate.lower() == part.lower() for part in path_parts):
                return True
        
        return False

    def _select_best_project_candidate(self, candidates: List[str], content: str) -> Optional[str]:
        """Select the best project candidate based on content analysis."""
        if not candidates:
            return None
        
        if len(candidates) == 1:
            return candidates[0]
        
        # Score candidates based on frequency and context
        candidate_scores = {}
        
        for candidate in candidates:
            score = 0
            
            # Count occurrences
            score += content.lower().count(candidate.lower())
            
            # Bonus for appearing with project-related keywords
            project_context_patterns = [
                rf'\b{re.escape(candidate)}\b.*(?:project|repo|repository|codebase)',
                rf'(?:project|repo|repository|codebase).*\b{re.escape(candidate)}\b',
                rf'\b{re.escape(candidate)}\b.*(?:application|app|system)',
                rf'(?:working|developing|building).*\b{re.escape(candidate)}\b'
            ]
            
            for pattern in project_context_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    score += 2
            
            # Bonus for appearing with file extensions or framework keywords
            for keyword_set in [self.project_indicators['file_extensions'],
                              self.project_indicators['framework_keywords'],
                              self.project_indicators['language_keywords']]:
                for keyword in keyword_set:
                    if keyword in content.lower() and candidate.lower() in content.lower():
                        score += 1
            
            candidate_scores[candidate] = score
        
        # Return candidate with highest score
        return max(candidate_scores.items(), key=lambda x: x[1])[0]

    async def _find_or_create_project_by_name(self, project_name: str) -> Optional[Project]:
        """Find existing project by name or create a new one."""
        try:
            # Try to find existing project
            existing_projects = self.project_repo.list_all()
            for project in existing_projects:
                if self._is_project_match(project_name, project.name, project.path):
                    return project
            
            # Create new project
            from models.schemas import ProjectCreate
            project_data = ProjectCreate(
                name=project_name,
                description=f"Auto-detected project: {project_name}"
            )
            
            return self.project_repo.create(project_data)
            
        except Exception as e:
            logger.error(f"Error finding or creating project '{project_name}': {e}")
            return None

    async def categorize_conversation(self, conversation: Conversation) -> Dict[str, Any]:
        """
        Categorize a conversation based on its content and context.
        
        Args:
            conversation: Conversation to categorize
            
        Returns:
            Dict[str, Any]: Categorization results with categories and confidence scores
        """
        try:
            categories = {
                'technical_domain': [],
                'activity_type': [],
                'complexity_level': 'medium',
                'urgency_level': 'normal',
                'confidence_scores': {}
            }
            
            content = conversation.content.lower()
            
            # Technical domain categorization
            domain_keywords = {
                'frontend': ['react', 'vue', 'angular', 'html', 'css', 'javascript', 'typescript', 'ui', 'ux', 'component', 'styling'],
                'backend': ['api', 'server', 'database', 'sql', 'endpoint', 'service', 'microservice', 'authentication', 'authorization'],
                'mobile': ['ios', 'android', 'react-native', 'flutter', 'swift', 'kotlin', 'mobile', 'app store', 'play store'],
                'devops': ['docker', 'kubernetes', 'ci/cd', 'deployment', 'infrastructure', 'aws', 'azure', 'gcp', 'jenkins', 'github actions'],
                'data': ['data', 'analytics', 'machine learning', 'ml', 'ai', 'pandas', 'numpy', 'tensorflow', 'pytorch', 'sql'],
                'testing': ['test', 'testing', 'unit test', 'integration test', 'e2e', 'jest', 'cypress', 'selenium', 'mock'],
                'security': ['security', 'authentication', 'authorization', 'encryption', 'vulnerability', 'ssl', 'tls', 'oauth']
            }
            
            for domain, keywords in domain_keywords.items():
                score = sum(1 for keyword in keywords if keyword in content)
                if score > 0:
                    categories['technical_domain'].append(domain)
                    categories['confidence_scores'][f'domain_{domain}'] = min(score / len(keywords), 1.0)
            
            # Activity type categorization
            activity_keywords = {
                'debugging': ['error', 'bug', 'issue', 'problem', 'fix', 'debug', 'troubleshoot', 'exception', 'crash'],
                'development': ['implement', 'create', 'build', 'develop', 'code', 'function', 'class', 'method', 'feature', 'help', 'need help', 'working'],
                'review': ['review', 'feedback', 'suggestion', 'improve', 'optimize', 'refactor', 'clean up'],
                'planning': ['plan', 'design', 'architecture', 'structure', 'approach', 'strategy', 'requirements'],
                'learning': ['how to', 'what is', 'explain', 'understand', 'learn', 'tutorial', 'example', 'documentation'],
                'configuration': ['config', 'setup', 'install', 'configure', 'environment', 'settings', 'deployment']
            }
            
            for activity, keywords in activity_keywords.items():
                score = sum(1 for keyword in keywords if keyword in content)
                if score > 0:
                    categories['activity_type'].append(activity)
                    categories['confidence_scores'][f'activity_{activity}'] = min(score / len(keywords), 1.0)
            
            # Complexity level assessment
            complexity_indicators = {
                'high': ['complex', 'complicated', 'advanced', 'sophisticated', 'intricate', 'architecture', 'system design'],
                'low': ['simple', 'basic', 'easy', 'straightforward', 'quick', 'small change', 'minor']
            }
            
            high_complexity_score = sum(1 for indicator in complexity_indicators['high'] if indicator in content)
            low_complexity_score = sum(1 for indicator in complexity_indicators['low'] if indicator in content)
            
            if high_complexity_score > low_complexity_score:
                categories['complexity_level'] = 'high'
            elif low_complexity_score > high_complexity_score:
                categories['complexity_level'] = 'low'
            
            # Urgency level assessment
            urgency_indicators = {
                'high': ['urgent', 'asap', 'immediately', 'critical', 'emergency', 'blocking', 'broken', 'production'],
                'low': ['later', 'eventually', 'nice to have', 'when possible', 'low priority', 'future']
            }
            
            high_urgency_score = sum(1 for indicator in urgency_indicators['high'] if indicator in content)
            low_urgency_score = sum(1 for indicator in urgency_indicators['low'] if indicator in content)
            
            if high_urgency_score > low_urgency_score:
                categories['urgency_level'] = 'high'
            elif low_urgency_score > high_urgency_score:
                categories['urgency_level'] = 'low'
            
            return categories
            
        except Exception as e:
            logger.error(f"Error categorizing conversation {conversation.id}: {e}")
            return {
                'technical_domain': [],
                'activity_type': [],
                'complexity_level': 'medium',
                'urgency_level': 'normal',
                'confidence_scores': {}
            }

    async def find_related_conversations(
        self,
        conversation: Conversation,
        max_results: int = 10,
        time_window_hours: int = 168  # 1 week
    ) -> List[Tuple[Conversation, str, float]]:
        """
        Find conversations related to the given conversation.
        
        Args:
            conversation: Source conversation
            max_results: Maximum number of related conversations to return
            time_window_hours: Time window to search within (hours)
            
        Returns:
            List[Tuple[Conversation, str, float]]: List of (conversation, relationship_type, confidence_score)
        """
        try:
            related_conversations = []
            
            # Define time window
            cutoff_time = conversation.timestamp - timedelta(hours=time_window_hours)
            
            # Get potential related conversations
            candidates = []
            
            # Same project conversations
            if conversation.project_id:
                project_conversations = self.conversation_repo.get_by_project(
                    conversation.project_id, limit=50
                )
                candidates.extend([
                    (conv, 'project_related') for conv in project_conversations
                    if conv.id != conversation.id and conv.timestamp >= cutoff_time
                ])
            
            # Same tool conversations (recent)
            tool_conversations = self.conversation_repo.get_recent_by_tool(
                conversation.tool_name, hours=time_window_hours, limit=30
            )
            candidates.extend([
                (conv, 'tool_related') for conv in tool_conversations
                if conv.id != conversation.id and conv not in [c[0] for c in candidates]
            ])
            
            # Analyze content similarity
            for candidate_conv, base_relationship in candidates:
                similarity_score = self._calculate_content_similarity(
                    conversation, candidate_conv
                )
                
                if similarity_score > 0.2:  # Minimum similarity threshold
                    # Determine specific relationship type
                    relationship_type = self._determine_relationship_type(
                        conversation, candidate_conv, base_relationship
                    )
                    
                    related_conversations.append((
                        candidate_conv, relationship_type, similarity_score
                    ))
            
            # Sort by confidence score and limit results
            related_conversations.sort(key=lambda x: x[2], reverse=True)
            return related_conversations[:max_results]
            
        except Exception as e:
            logger.error(f"Error finding related conversations for {conversation.id}: {e}")
            return []

    def _calculate_content_similarity(self, conv1: Conversation, conv2: Conversation) -> float:
        """Calculate similarity score between two conversations."""
        try:
            content1 = conv1.content.lower()
            content2 = conv2.content.lower()
            
            # Simple keyword-based similarity
            words1 = set(re.findall(r'\b\w+\b', content1))
            words2 = set(re.findall(r'\b\w+\b', content2))
            
            # Remove common stop words
            stop_words = {
                'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
                'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
                'can', 'may', 'might', 'must', 'this', 'that', 'these', 'those'
            }
            
            words1 = words1 - stop_words
            words2 = words2 - stop_words
            
            if not words1 or not words2:
                return 0.0
            
            # Jaccard similarity
            intersection = len(words1.intersection(words2))
            union = len(words1.union(words2))
            
            jaccard_score = intersection / union if union > 0 else 0.0
            
            # Bonus for shared tags
            tags1 = set(conv1.tags_list) if conv1.tags else set()
            tags2 = set(conv2.tags_list) if conv2.tags else set()
            
            tag_similarity = 0.0
            if tags1 and tags2:
                tag_intersection = len(tags1.intersection(tags2))
                tag_union = len(tags1.union(tags2))
                tag_similarity = tag_intersection / tag_union if tag_union > 0 else 0.0
            
            # Combined score
            return (jaccard_score * 0.7) + (tag_similarity * 0.3)
            
        except Exception as e:
            logger.error(f"Error calculating content similarity: {e}")
            return 0.0

    def _determine_relationship_type(
        self,
        source_conv: Conversation,
        target_conv: Conversation,
        base_relationship: str
    ) -> str:
        """Determine the specific relationship type between conversations."""
        try:
            # Time-based relationships
            time_diff = abs((source_conv.timestamp - target_conv.timestamp).total_seconds())
            
            # If conversations are very close in time (< 30 minutes), likely continuation
            if time_diff < 1800:
                return RelationshipType.CONTINUATION.value
            
            # Content-based relationships
            source_content = source_conv.content.lower()
            target_content = target_conv.content.lower()
            
            # Reference indicators
            reference_patterns = [
                r'(?:as|like)\s+(?:i|we)\s+(?:mentioned|discussed|said)\s+(?:before|earlier)',
                r'(?:referring|going back)\s+to',
                r'(?:similar|same)\s+(?:issue|problem|question)',
                r'(?:follow(?:ing)?|continuing)\s+(?:up|from)'
            ]
            
            for pattern in reference_patterns:
                if re.search(pattern, source_content) or re.search(pattern, target_content):
                    return RelationshipType.REFERENCE.value
            
            # Default to related for same project or tool
            if base_relationship == 'project_related':
                return RelationshipType.RELATED.value
            
            return RelationshipType.RELATED.value
            
        except Exception as e:
            logger.error(f"Error determining relationship type: {e}")
            return RelationshipType.RELATED.value

    async def create_context_links(
        self,
        source_conversation_id: str,
        related_conversations: List[Tuple[Conversation, str, float]]
    ) -> List[ContextLink]:
        """
        Create context links between conversations.
        
        Args:
            source_conversation_id: Source conversation ID
            related_conversations: List of (conversation, relationship_type, confidence_score)
            
        Returns:
            List[ContextLink]: Created context links
        """
        try:
            created_links = []
            
            with self.db_manager.get_session() as session:
                for target_conv, relationship_type, confidence_score in related_conversations:
                    # Check if link already exists
                    existing_link = session.query(ContextLink).filter(
                        ContextLink.source_conversation_id == source_conversation_id,
                        ContextLink.target_conversation_id == target_conv.id
                    ).first()
                    
                    if existing_link:
                        # Update existing link if new confidence is higher
                        if confidence_score > existing_link.confidence_score:
                            existing_link.confidence_score = confidence_score
                            existing_link.relationship_type = relationship_type
                            session.commit()
                            created_links.append(existing_link)
                    else:
                        # Create new link
                        context_link = ContextLink(
                            source_conversation_id=source_conversation_id,
                            target_conversation_id=target_conv.id,
                            relationship_type=relationship_type,
                            confidence_score=confidence_score
                        )
                        
                        session.add(context_link)
                        session.flush()
                        created_links.append(context_link)
                
                session.commit()
                
            logger.info(f"Created {len(created_links)} context links for conversation {source_conversation_id}")
            return created_links
            
        except Exception as e:
            logger.error(f"Error creating context links: {e}")
            return []

    async def process_conversation_context(self, conversation: Conversation) -> Dict[str, Any]:
        """
        Process a conversation for context management (main entry point).
        
        Args:
            conversation: Conversation to process
            
        Returns:
            Dict[str, Any]: Processing results including project detection, categorization, and links
        """
        try:
            results = {
                'project_detected': False,
                'project_id': None,
                'categories': {},
                'related_conversations': [],
                'context_links_created': 0
            }
            
            # Detect and assign project if not already assigned
            if not conversation.project_id:
                project_id = await self.detect_project_from_content(
                    conversation.content,
                    conversation.conversation_metadata
                )
                
                if project_id:
                    # Update conversation with detected project
                    from models.schemas import ConversationUpdate
                    update_data = ConversationUpdate(project_id=project_id)
                    updated_conv = self.conversation_repo.update(conversation.id, update_data)
                    
                    if updated_conv:
                        conversation.project_id = project_id
                        results['project_detected'] = True
                        results['project_id'] = project_id
            
            # Categorize conversation
            categories = await self.categorize_conversation(conversation)
            results['categories'] = categories
            
            # Find related conversations
            related_conversations = await self.find_related_conversations(conversation)
            results['related_conversations'] = [
                {
                    'conversation_id': conv.id,
                    'relationship_type': rel_type,
                    'confidence_score': confidence
                }
                for conv, rel_type, confidence in related_conversations
            ]
            
            # Create context links
            if related_conversations:
                context_links = await self.create_context_links(
                    conversation.id, related_conversations
                )
                results['context_links_created'] = len(context_links)
            
            logger.info(f"Processed context for conversation {conversation.id}: "
                       f"project_detected={results['project_detected']}, "
                       f"categories={len(categories.get('technical_domain', []))}, "
                       f"related={len(related_conversations)}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing conversation context for {conversation.id}: {e}")
            return {
                'project_detected': False,
                'project_id': None,
                'categories': {},
                'related_conversations': [],
                'context_links_created': 0
            }