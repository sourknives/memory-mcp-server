"""
Tagging service for automatic tag generation using NLP techniques.

This service analyzes conversation content to automatically generate relevant tags
for categorization and improved searchability.
"""

import logging
import re
from typing import List, Dict, Set, Optional, Tuple
from collections import Counter
from datetime import datetime

# Try to import optional NLP dependencies
try:
    import spacy
    from spacy.lang.en.stop_words import STOP_WORDS
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    STOP_WORDS = set()

logger = logging.getLogger(__name__)


class TaggingService:
    """Service for automatic tag generation from conversation content."""
    
    def __init__(self, max_tags: int = 10, min_tag_length: int = 2):
        """
        Initialize tagging service.
        
        Args:
            max_tags: Maximum number of tags to generate per conversation
            min_tag_length: Minimum length for generated tags
        """
        self.max_tags = max_tags
        self.min_tag_length = min_tag_length
        self._nlp_model = None
        
        # Predefined tag categories and keywords
        self.tag_categories = {
            'languages': {
                'python', 'javascript', 'typescript', 'java', 'cpp', 'c++', 'csharp', 'c#',
                'php', 'ruby', 'go', 'golang', 'rust', 'swift', 'kotlin', 'scala',
                'html', 'css', 'sql', 'bash', 'shell', 'powershell', 'r', 'matlab'
            },
            'frameworks': {
                'react', 'vue', 'angular', 'django', 'flask', 'fastapi', 'express',
                'spring', 'laravel', 'rails', 'nextjs', 'nuxt', 'gatsby', 'svelte',
                'electron', 'react-native', 'flutter', 'ionic', 'cordova', 'xamarin'
            },
            'tools': {
                'git', 'github', 'gitlab', 'bitbucket', 'docker', 'kubernetes', 'k8s',
                'jenkins', 'travis', 'circleci', 'webpack', 'vite', 'rollup', 'babel',
                'eslint', 'prettier', 'jest', 'cypress', 'playwright', 'selenium',
                'postman', 'insomnia', 'vscode', 'intellij', 'pycharm', 'vim', 'emacs'
            },
            'databases': {
                'mysql', 'postgresql', 'postgres', 'sqlite', 'mongodb', 'redis',
                'elasticsearch', 'cassandra', 'dynamodb', 'firebase', 'supabase'
            },
            'cloud': {
                'aws', 'azure', 'gcp', 'google-cloud', 'heroku', 'vercel', 'netlify',
                'digitalocean', 'linode', 'cloudflare', 's3', 'ec2', 'lambda'
            },
            'concepts': {
                'api', 'rest', 'graphql', 'microservices', 'authentication', 'authorization',
                'oauth', 'jwt', 'cors', 'websocket', 'sse', 'crud', 'mvc', 'mvvm',
                'solid', 'dry', 'kiss', 'yagni', 'tdd', 'bdd', 'ci/cd', 'devops'
            },
            'activities': {
                'debugging', 'testing', 'deployment', 'refactoring', 'optimization',
                'security', 'performance', 'monitoring', 'logging', 'documentation',
                'code-review', 'pair-programming', 'planning', 'design', 'architecture'
            }
        }
        
        # Common technical terms that make good tags
        self.technical_terms = set()
        for category_terms in self.tag_categories.values():
            self.technical_terms.update(category_terms)
        
        # Words to exclude from tags
        self.excluded_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
            'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
            'can', 'may', 'might', 'must', 'this', 'that', 'these', 'those',
            'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her',
            'us', 'them', 'my', 'your', 'his', 'her', 'its', 'our', 'their',
            'get', 'got', 'getting', 'make', 'making', 'made', 'take', 'taking',
            'took', 'give', 'giving', 'gave', 'put', 'putting', 'go', 'going',
            'went', 'come', 'coming', 'came', 'see', 'seeing', 'saw', 'know',
            'knowing', 'knew', 'think', 'thinking', 'thought', 'want', 'wanting',
            'wanted', 'need', 'needing', 'needed', 'use', 'using', 'used',
            'work', 'working', 'worked', 'try', 'trying', 'tried', 'help',
            'helping', 'helped', 'find', 'finding', 'found', 'look', 'looking',
            'looked', 'ask', 'asking', 'asked', 'tell', 'telling', 'told',
            'show', 'showing', 'showed', 'run', 'running', 'ran', 'start',
            'starting', 'started', 'stop', 'stopping', 'stopped', 'end',
            'ending', 'ended', 'create', 'creating', 'created', 'build',
            'building', 'built', 'add', 'adding', 'added', 'remove', 'removing',
            'removed', 'delete', 'deleting', 'deleted', 'update', 'updating',
            'updated', 'change', 'changing', 'changed', 'fix', 'fixing', 'fixed',
            'solve', 'solving', 'solved', 'handle', 'handling', 'handled'
        }
        
        # Add spacy stop words if available
        if SPACY_AVAILABLE and STOP_WORDS:
            self.excluded_words.update(STOP_WORDS)

    async def initialize_nlp(self) -> None:
        """Initialize NLP model if available."""
        if not SPACY_AVAILABLE:
            logger.warning("spaCy not available, using basic tagging methods")
            return
        
        try:
            # Try to load English model
            self._nlp_model = spacy.load("en_core_web_sm")
            logger.info("Loaded spaCy English model for advanced tagging")
        except OSError:
            try:
                # Fallback to basic English model
                self._nlp_model = spacy.load("en")
                logger.info("Loaded basic spaCy English model")
            except OSError:
                logger.warning("No spaCy English model found, using basic tagging methods")
                self._nlp_model = None

    def generate_tags(self, content: str, metadata: Optional[Dict] = None) -> List[str]:
        """
        Generate tags for conversation content.
        
        Args:
            content: Conversation content
            metadata: Optional conversation metadata
            
        Returns:
            List[str]: Generated tags
        """
        try:
            all_tags = set()
            
            # Extract predefined technical tags
            technical_tags = self._extract_technical_tags(content)
            all_tags.update(technical_tags)
            
            # Extract entity-based tags using NLP if available
            if self._nlp_model:
                entity_tags = self._extract_entity_tags(content)
                all_tags.update(entity_tags)
            
            # Extract keyword-based tags
            keyword_tags = self._extract_keyword_tags(content)
            all_tags.update(keyword_tags)
            
            # Extract pattern-based tags
            pattern_tags = self._extract_pattern_tags(content)
            all_tags.update(pattern_tags)
            
            # Extract metadata-based tags
            if metadata:
                metadata_tags = self._extract_metadata_tags(metadata)
                all_tags.update(metadata_tags)
            
            # Filter and rank tags
            filtered_tags = self._filter_and_rank_tags(list(all_tags), content)
            
            # Limit to max_tags
            return filtered_tags[:self.max_tags]
            
        except Exception as e:
            logger.error(f"Error generating tags: {e}")
            return []

    def _extract_technical_tags(self, content: str) -> Set[str]:
        """Extract predefined technical tags from content."""
        tags = set()
        content_lower = content.lower()
        
        # Check for exact matches of technical terms
        for term in self.technical_terms:
            # Use word boundaries to avoid partial matches
            pattern = rf'\b{re.escape(term)}\b'
            if re.search(pattern, content_lower):
                tags.add(term)
        
        # Check for common variations and aliases
        variations = {
            'js': 'javascript',
            'ts': 'typescript',
            'py': 'python',
            'cpp': 'c++',
            'cs': 'csharp',
            'rb': 'ruby',
            'k8s': 'kubernetes',
            'postgres': 'postgresql',
            'mongo': 'mongodb',
            'aws': 'amazon-web-services',
            'gcp': 'google-cloud-platform'
        }
        
        for alias, full_term in variations.items():
            if re.search(rf'\b{re.escape(alias)}\b', content_lower):
                tags.add(full_term)
        
        return tags

    def _extract_entity_tags(self, content: str) -> Set[str]:
        """Extract entity-based tags using NLP."""
        if not self._nlp_model:
            return set()
        
        tags = set()
        
        try:
            doc = self._nlp_model(content)
            
            # Extract named entities
            for ent in doc.ents:
                if ent.label_ in ['ORG', 'PRODUCT', 'LANGUAGE']:
                    entity_text = ent.text.lower().strip()
                    if (len(entity_text) >= self.min_tag_length and 
                        entity_text not in self.excluded_words):
                        # Clean entity text
                        cleaned = re.sub(r'[^\w\s-]', '', entity_text)
                        cleaned = re.sub(r'\s+', '-', cleaned.strip())
                        if cleaned:
                            tags.add(cleaned)
            
            # Extract noun phrases that might be technical terms
            for chunk in doc.noun_chunks:
                chunk_text = chunk.text.lower().strip()
                if (len(chunk_text.split()) <= 3 and  # Max 3 words
                    len(chunk_text) >= self.min_tag_length and
                    not any(word in self.excluded_words for word in chunk_text.split())):
                    
                    # Check if it contains technical indicators
                    if any(tech_term in chunk_text for tech_term in self.technical_terms):
                        cleaned = re.sub(r'[^\w\s-]', '', chunk_text)
                        cleaned = re.sub(r'\s+', '-', cleaned.strip())
                        if cleaned:
                            tags.add(cleaned)
            
        except Exception as e:
            logger.error(f"Error extracting entity tags: {e}")
        
        return tags

    def _extract_keyword_tags(self, content: str) -> Set[str]:
        """Extract keyword-based tags using frequency analysis."""
        tags = set()
        
        # Extract words and clean them
        words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9_-]*\b', content.lower())
        
        # Filter words
        filtered_words = [
            word for word in words
            if (len(word) >= self.min_tag_length and
                word not in self.excluded_words and
                not word.isdigit())
        ]
        
        # Count word frequencies
        word_counts = Counter(filtered_words)
        
        # Select frequent words that appear multiple times
        for word, count in word_counts.items():
            if count >= 2:  # Appears at least twice
                # Additional filtering for quality
                if (not word.startswith(('http', 'www', 'com')) and
                    len(word) >= self.min_tag_length and
                    not re.match(r'^[a-z]{1,2}$', word)):  # Skip very short words
                    tags.add(word)
        
        return tags

    def _extract_pattern_tags(self, content: str) -> Set[str]:
        """Extract tags based on common patterns."""
        tags = set()
        
        # File extension patterns
        file_extensions = re.findall(r'\.([a-zA-Z0-9]+)', content)
        for ext in file_extensions:
            if ext.lower() in {'py', 'js', 'ts', 'html', 'css', 'java', 'cpp', 'c', 'h', 'cs', 'php', 'rb', 'go', 'rs', 'swift', 'kt'}:
                tags.add(f"file-{ext.lower()}")
        
        # URL/domain patterns
        domains = re.findall(r'(?:https?://)?(?:www\.)?([a-zA-Z0-9-]+\.[a-zA-Z]{2,})', content)
        for domain in domains:
            domain_lower = domain.lower()
            if domain_lower in {'github.com', 'stackoverflow.com', 'npmjs.com', 'pypi.org'}:
                platform_name = domain_lower.split('.')[0]
                tags.add(platform_name)
        
        # Version patterns
        versions = re.findall(r'v?(\d+\.\d+(?:\.\d+)?)', content)
        if versions:
            tags.add('versioning')
        
        # Error/exception patterns
        error_patterns = [
            r'error:?\s+([a-zA-Z][a-zA-Z0-9_]*(?:Error|Exception))',
            r'([a-zA-Z][a-zA-Z0-9_]*(?:Error|Exception))',
            r'HTTP\s+(\d{3})',
            r'status\s+code\s+(\d{3})',
            r'(\d{3})\s+error',
            r'returning\s+(\d{3})\s+error'
        ]
        
        for pattern in error_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if match.isdigit():
                    if match in {'404', '500', '403', '401', '400'}:
                        tags.add(f"http-{match}")
                else:
                    error_name = match.lower().replace('error', '').replace('exception', '')
                    if error_name:
                        tags.add(f"error-{error_name}")
        
        # Command patterns
        command_patterns = [
            r'(?:^|\s)(npm|pip|git|docker|kubectl|yarn|pnpm)\s+([a-zA-Z-]+)',
            r'(?:^|\s)(python|node|java|javac|gcc|g\+\+)\s+'
        ]
        
        for pattern in command_patterns:
            matches = re.findall(pattern, content, re.MULTILINE)
            for match in matches:
                if isinstance(match, tuple):
                    tool, command = match
                    tags.add(tool.lower())
                    if command and len(command) > 1:
                        tags.add(f"{tool.lower()}-{command.lower()}")
                else:
                    tags.add(match.lower())
        
        return tags

    def _extract_metadata_tags(self, metadata: Dict) -> Set[str]:
        """Extract tags from conversation metadata."""
        tags = set()
        
        try:
            # Tool name
            if 'tool_name' in metadata:
                tags.add(metadata['tool_name'].lower())
            
            # File path information
            if 'file_path' in metadata:
                file_path = metadata['file_path']
                # Extract file extension
                if '.' in file_path:
                    ext = file_path.split('.')[-1].lower()
                    if len(ext) <= 4:  # Reasonable extension length
                        tags.add(f"file-{ext}")
                
                # Extract directory names that might be meaningful
                path_parts = file_path.split('/')
                for part in path_parts:
                    part_lower = part.lower()
                    if (part_lower in {'src', 'lib', 'components', 'pages', 'views', 'models', 
                                     'controllers', 'services', 'utils', 'tests', 'test', 'spec'} and
                        part_lower not in tags):
                        tags.add(f"directory-{part_lower}")
            
            # Project information
            if 'project_name' in metadata:
                project_name = metadata['project_name'].lower()
                # Clean project name for use as tag
                cleaned_name = re.sub(r'[^\w-]', '-', project_name)
                cleaned_name = re.sub(r'-+', '-', cleaned_name).strip('-')
                if cleaned_name:
                    tags.add(f"project-{cleaned_name}")
            
            # User query type
            if 'user_query' in metadata:
                query = metadata['user_query'].lower()
                # Detect query types
                if any(word in query for word in ['how to', 'how do', 'how can']):
                    tags.add('how-to')
                elif any(word in query for word in ['what is', 'what are', 'what does']):
                    tags.add('explanation')
                elif any(word in query for word in ['why', 'why does', 'why is']):
                    tags.add('explanation')
                elif any(word in query for word in ['error', 'bug', 'issue', 'problem']):
                    tags.add('troubleshooting')
                elif any(word in query for word in ['review', 'feedback', 'improve']):
                    tags.add('code-review')
            
        except Exception as e:
            logger.error(f"Error extracting metadata tags: {e}")
        
        return tags

    def _filter_and_rank_tags(self, tags: List[str], content: str) -> List[str]:
        """Filter and rank tags by relevance and quality."""
        if not tags:
            return []
        
        # Calculate relevance scores for each tag
        tag_scores = {}
        content_lower = content.lower()
        
        for tag in tags:
            score = 0
            
            # Base score from frequency in content
            tag_clean = tag.replace('-', ' ').replace('_', ' ')
            occurrences = content_lower.count(tag_clean.lower())
            score += occurrences
            
            # Bonus for technical terms
            if tag in self.technical_terms:
                score += 5
            
            # Bonus for category membership
            for category, terms in self.tag_categories.items():
                if tag in terms:
                    score += 3
                    break
            
            # Penalty for very common words
            if tag in {'code', 'file', 'function', 'method', 'class', 'variable'}:
                score -= 2
            
            # Bonus for compound tags (more specific)
            if '-' in tag or '_' in tag:
                score += 1
            
            # Length-based scoring
            if len(tag) < 3:
                score -= 1
            elif len(tag) > 15:
                score -= 1
            
            tag_scores[tag] = max(score, 0)  # Ensure non-negative
        
        # Sort by score (descending) and then alphabetically for consistency
        sorted_tags = sorted(
            tag_scores.items(),
            key=lambda x: (-x[1], x[0])
        )
        
        # Return only tags with positive scores
        return [tag for tag, score in sorted_tags if score > 0]

    def suggest_tags_for_project(self, project_conversations: List[str]) -> List[str]:
        """
        Suggest common tags for a project based on its conversations.
        
        Args:
            project_conversations: List of conversation contents
            
        Returns:
            List[str]: Suggested project-level tags
        """
        try:
            if not project_conversations:
                return []
            
            # Collect all tags from conversations
            all_tags = []
            for content in project_conversations:
                tags = self.generate_tags(content)
                all_tags.extend(tags)
            
            # Count tag frequencies
            tag_counts = Counter(all_tags)
            
            # Select tags that appear in multiple conversations
            min_frequency = max(2, len(project_conversations) // 3)  # At least 2 or 1/3 of conversations
            
            common_tags = [
                tag for tag, count in tag_counts.items()
                if count >= min_frequency
            ]
            
            # Sort by frequency and return top tags
            common_tags.sort(key=lambda x: tag_counts[x], reverse=True)
            return common_tags[:15]  # Return top 15 project tags
            
        except Exception as e:
            logger.error(f"Error suggesting project tags: {e}")
            return []

    def update_tag_quality_feedback(self, tag: str, is_useful: bool) -> None:
        """
        Update tag quality based on user feedback (for future improvements).
        
        Args:
            tag: Tag that received feedback
            is_useful: Whether the tag was useful to the user
        """
        # This could be implemented to store feedback and improve tag generation
        # For now, just log the feedback
        logger.info(f"Tag feedback: '{tag}' - useful: {is_useful}")

    def get_tag_categories(self) -> Dict[str, Set[str]]:
        """Get the predefined tag categories."""
        return self.tag_categories.copy()

    def is_technical_tag(self, tag: str) -> bool:
        """Check if a tag is a technical term."""
        return tag in self.technical_terms