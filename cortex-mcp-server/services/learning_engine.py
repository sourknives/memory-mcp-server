"""
Learning engine for user preference detection and pattern recognition.

This service analyzes conversation patterns, learns from user feedback,
and improves suggestions over time to provide personalized assistance.
"""

import logging
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any, Union
from dataclasses import dataclass
from enum import Enum

from models.database import Conversation, Preference
from models.schemas import PreferenceCategory, PreferenceCreate
from repositories.conversation_repository import ConversationRepository
from repositories.preferences_repository import PreferencesRepository
from config.database import DatabaseManager

logger = logging.getLogger(__name__)


class PatternType(str, Enum):
    """Types of patterns that can be detected."""
    CODING_STYLE = "coding_style"
    TECHNOLOGY_PREFERENCE = "technology_preference"
    WORKFLOW_PATTERN = "workflow_pattern"
    RESOURCE_USAGE = "resource_usage"
    PROBLEM_SOLVING = "problem_solving"
    COMMUNICATION_STYLE = "communication_style"


class FeedbackType(str, Enum):
    """Types of feedback from users."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    CORRECTION = "correction"
    PREFERENCE_UPDATE = "preference_update"
    STORAGE_APPROVAL = "storage_approval"
    STORAGE_REJECTION = "storage_rejection"
    STORAGE_MODIFICATION = "storage_modification"


@dataclass
class DetectedPattern:
    """Represents a detected user pattern."""
    pattern_type: PatternType
    pattern_key: str
    pattern_value: Any
    confidence_score: float
    evidence_count: int
    first_seen: datetime
    last_seen: datetime
    examples: List[str]


@dataclass
class UserFeedback:
    """Represents user feedback on suggestions or patterns."""
    feedback_type: FeedbackType
    conversation_id: str
    suggestion_id: Optional[str]
    original_suggestion: Optional[str]
    corrected_value: Optional[str]
    timestamp: datetime
    context: Dict[str, Any]


class LearningEngine:
    """Engine for learning user patterns and preferences."""
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        conversation_repo: ConversationRepository,
        preferences_repo: PreferencesRepository
    ):
        """
        Initialize learning engine.
        
        Args:
            db_manager: Database manager instance
            conversation_repo: Conversation repository
            preferences_repo: Preferences repository
        """
        self.db_manager = db_manager
        self.conversation_repo = conversation_repo
        self.preferences_repo = preferences_repo
        
        # Pattern detection configurations
        self.pattern_configs = {
            PatternType.CODING_STYLE: {
                'min_occurrences': 3,
                'confidence_threshold': 0.6,
                'patterns': {
                    'indentation': [r'(\s{2,4})', r'(\t+)'],
                    'quotes': [r"'([^']*)'", r'"([^"]*)"'],
                    'semicolons': [r';$', r'[^;]$'],
                    'brackets': [r'\{\s*$', r'\{.*\}'],
                    'naming_convention': [r'[a-z_]+', r'[A-Z][a-zA-Z]+', r'[a-z][A-Z]']
                }
            },
            PatternType.TECHNOLOGY_PREFERENCE: {
                'min_occurrences': 2,
                'confidence_threshold': 0.5,
                'keywords': {
                    'languages': ['python', 'javascript', 'typescript', 'java', 'go', 'rust', 'cpp'],
                    'frameworks': ['react', 'vue', 'angular', 'django', 'flask', 'express', 'spring'],
                    'databases': ['postgresql', 'mysql', 'mongodb', 'redis', 'sqlite'],
                    'tools': ['docker', 'kubernetes', 'git', 'vscode', 'vim', 'emacs']
                }
            },
            PatternType.WORKFLOW_PATTERN: {
                'min_occurrences': 2,
                'confidence_threshold': 0.4,
                'sequences': [
                    ['test', 'implement', 'refactor'],
                    ['plan', 'code', 'review'],
                    ['debug', 'fix', 'test'],
                    ['research', 'prototype', 'implement']
                ]
            }
        }
        
        # Feedback processing weights
        self.feedback_weights = {
            FeedbackType.POSITIVE: 1.2,
            FeedbackType.NEGATIVE: 0.8,
            FeedbackType.CORRECTION: 1.5,
            FeedbackType.PREFERENCE_UPDATE: 2.0,
            FeedbackType.STORAGE_APPROVAL: 1.1,
            FeedbackType.STORAGE_REJECTION: 0.9,
            FeedbackType.STORAGE_MODIFICATION: 1.3
        }
        
        # Storage feedback tracking
        self.storage_feedback_patterns = {
            'category_accuracy': {},  # Track accuracy by category
            'confidence_calibration': {},  # Track confidence vs approval rates
            'pattern_effectiveness': {},  # Track which patterns work best
            'user_preferences': {}  # Track user-specific preferences
        }

    async def detect_user_preferences(
        self,
        user_id: Optional[str] = None,
        time_window_days: int = 30,
        min_conversations: int = 5
    ) -> List[DetectedPattern]:
        """
        Detect user preferences from conversation patterns.
        
        Args:
            user_id: Optional user ID filter
            time_window_days: Days to look back for pattern detection
            min_conversations: Minimum conversations needed for detection
            
        Returns:
            List[DetectedPattern]: Detected patterns with confidence scores
        """
        try:
            # Get recent conversations
            cutoff_date = datetime.utcnow() - timedelta(days=time_window_days)
            conversations = self.conversation_repo.get_recent(
                hours=time_window_days * 24,
                limit=1000
            )
            
            if len(conversations) < min_conversations:
                logger.info(f"Not enough conversations ({len(conversations)}) for pattern detection")
                return []
            
            detected_patterns = []
            
            # Detect coding style patterns
            coding_patterns = self._detect_coding_style_patterns(conversations)
            if coding_patterns:
                logger.debug(f"Found {len(coding_patterns)} coding patterns")
                detected_patterns.extend(coding_patterns)
            
            # Detect technology preferences
            tech_patterns = self._detect_technology_preferences(conversations)
            if tech_patterns:
                logger.debug(f"Found {len(tech_patterns)} technology patterns")
                detected_patterns.extend(tech_patterns)
            
            # Detect workflow patterns
            workflow_patterns = self._detect_workflow_patterns(conversations)
            if workflow_patterns:
                logger.debug(f"Found {len(workflow_patterns)} workflow patterns")
                detected_patterns.extend(workflow_patterns)
            
            # Detect resource usage patterns
            resource_patterns = self._detect_resource_patterns(conversations)
            if resource_patterns:
                logger.debug(f"Found {len(resource_patterns)} resource patterns")
                detected_patterns.extend(resource_patterns)
            
            # Filter patterns by confidence threshold
            high_confidence_patterns = []
            for pattern in detected_patterns:
                if hasattr(pattern, 'confidence_score') and pattern.confidence_score >= 0.3:  # Lower threshold for testing
                    high_confidence_patterns.append(pattern)
            
            logger.info(f"Detected {len(high_confidence_patterns)} high-confidence patterns "
                       f"from {len(conversations)} conversations")
            
            return high_confidence_patterns
            
        except Exception as e:
            logger.error(f"Error detecting user preferences: {e}")
            return []

    def _detect_coding_style_patterns(self, conversations: List[Conversation]) -> List[DetectedPattern]:
        """Detect coding style patterns from conversations."""
        patterns = []
        
        try:
            # Extract code blocks from conversations
            code_blocks = []
            for conv in conversations:
                # Try multiple patterns to extract code blocks
                patterns = [
                    r'```[^\n]*\n(.*?)\n```',  # Standard pattern with language
                    r'```\n(.*?)\n```',        # Pattern without language
                    r'```(.*?)```'             # Simple pattern
                ]
                
                found_code = False
                for pattern in patterns:
                    code_matches = re.findall(pattern, conv.content, re.DOTALL)
                    if code_matches:
                        code_blocks.extend(code_matches)
                        found_code = True
                        break
                
                # If no matches with standard patterns, try extracting manually
                if not found_code and '```' in conv.content:
                    parts = conv.content.split('```')
                    for i in range(1, len(parts), 2):  # Every other part is code
                        code_content = parts[i].strip()
                        # Remove language identifier if it's on the first line
                        lines = code_content.split('\n')
                        if len(lines) > 1 and lines[0].strip() and not any(c in lines[0] for c in [' ', '(', '{', '=']):
                            code_content = '\n'.join(lines[1:])
                        if code_content.strip():
                            code_blocks.append(code_content)
            
            if not code_blocks:
                return patterns
            
            # Analyze indentation patterns
            indentation_counts = Counter()
            for code in code_blocks:
                lines = code.split('\n')
                for line in lines:
                    if line.strip():  # Skip empty lines
                        leading_spaces = len(line) - len(line.lstrip())
                        if leading_spaces > 0:
                            if '\t' in line[:leading_spaces]:
                                indentation_counts['tabs'] += 1
                            else:
                                indentation_counts[f'{leading_spaces}_spaces'] += 1
            
            if indentation_counts:
                most_common_indent = indentation_counts.most_common(1)[0]
                confidence = most_common_indent[1] / sum(indentation_counts.values())
                
                if confidence >= 0.6:
                    patterns.append(DetectedPattern(
                        pattern_type=PatternType.CODING_STYLE,
                        pattern_key="indentation",
                        pattern_value=most_common_indent[0],
                        confidence_score=confidence,
                        evidence_count=most_common_indent[1],
                        first_seen=conversations[-1].timestamp,
                        last_seen=conversations[0].timestamp,
                        examples=[f"Used {most_common_indent[0]} in {most_common_indent[1]} code blocks"]
                    ))
            
            # Analyze quote preferences
            quote_counts = Counter()
            for code in code_blocks:
                single_quotes = len(re.findall(r"'[^']*'", code))
                double_quotes = len(re.findall(r'"[^"]*"', code))
                quote_counts['single'] += single_quotes
                quote_counts['double'] += double_quotes
            
            if sum(quote_counts.values()) > 5:  # Minimum threshold
                most_common_quote = quote_counts.most_common(1)[0]
                confidence = most_common_quote[1] / sum(quote_counts.values())
                
                if confidence >= 0.7:
                    patterns.append(DetectedPattern(
                        pattern_type=PatternType.CODING_STYLE,
                        pattern_key="quotes",
                        pattern_value=most_common_quote[0],
                        confidence_score=confidence,
                        evidence_count=most_common_quote[1],
                        first_seen=conversations[-1].timestamp,
                        last_seen=conversations[0].timestamp,
                        examples=[f"Preferred {most_common_quote[0]} quotes in {most_common_quote[1]} instances"]
                    ))
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error detecting coding style patterns: {e}")
            return []

    def _detect_technology_preferences(self, conversations: List[Conversation]) -> List[DetectedPattern]:
        """Detect technology preference patterns."""
        patterns = []
        
        try:
            # Count technology mentions
            tech_mentions = defaultdict(int)
            tech_contexts = defaultdict(list)
            
            for conv in conversations:
                content_lower = conv.content.lower()
                
                # Check for technology keywords
                for category, technologies in self.pattern_configs[PatternType.TECHNOLOGY_PREFERENCE]['keywords'].items():
                    for tech in technologies:
                        if tech in content_lower:
                            tech_mentions[f"{category}:{tech}"] += 1
                            tech_contexts[f"{category}:{tech}"].append(conv.id)
            
            # Analyze preferences within categories
            categories = defaultdict(Counter)
            for tech_key, count in tech_mentions.items():
                category, tech = tech_key.split(':', 1)
                categories[category][tech] = count
            
            # Generate patterns for each category
            for category, tech_counts in categories.items():
                if len(tech_counts) >= 1:  # At least 1 technology mentioned
                    total_mentions = sum(tech_counts.values())
                    most_used = tech_counts.most_common(1)[0]
                    
                    # Calculate confidence based on frequency and repetition
                    confidence = min(most_used[1] / max(total_mentions, 3), 1.0)  # Cap at 1.0
                    
                    # Lower threshold for testing, but still meaningful
                    if confidence >= 0.3 and most_used[1] >= 2:  # At least 2 mentions
                        patterns.append(DetectedPattern(
                            pattern_type=PatternType.TECHNOLOGY_PREFERENCE,
                            pattern_key=category,
                            pattern_value=most_used[0],
                            confidence_score=confidence,
                            evidence_count=most_used[1],
                            first_seen=conversations[-1].timestamp,
                            last_seen=conversations[0].timestamp,
                            examples=[f"Mentioned {most_used[0]} {most_used[1]} times in {category} context"]
                        ))
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error detecting technology preferences: {e}")
            return []

    def _detect_workflow_patterns(self, conversations: List[Conversation]) -> List[DetectedPattern]:
        """Detect workflow and process patterns."""
        patterns = []
        
        try:
            # Extract workflow-related keywords
            workflow_keywords = {
                'planning': ['plan', 'design', 'architecture', 'requirements', 'spec'],
                'development': ['implement', 'code', 'build', 'create', 'develop'],
                'testing': ['test', 'verify', 'validate', 'check', 'debug'],
                'review': ['review', 'refactor', 'optimize', 'improve', 'clean'],
                'deployment': ['deploy', 'release', 'publish', 'launch', 'ship']
            }
            
            # Track workflow sequences
            workflow_sequences = []
            for conv in conversations:
                content_lower = conv.content.lower()
                conv_workflow = []
                
                for phase, keywords in workflow_keywords.items():
                    if any(keyword in content_lower for keyword in keywords):
                        conv_workflow.append(phase)
                
                if conv_workflow:
                    workflow_sequences.append((conv.timestamp, conv_workflow))
            
            # Sort by timestamp and look for common sequences
            workflow_sequences.sort(key=lambda x: x[0])
            
            # Analyze common workflow patterns
            sequence_patterns = Counter()
            for i in range(len(workflow_sequences) - 1):
                current_phases = workflow_sequences[i][1]
                next_phases = workflow_sequences[i + 1][1]
                
                for curr_phase in current_phases:
                    for next_phase in next_phases:
                        if curr_phase != next_phase:
                            sequence_patterns[f"{curr_phase} -> {next_phase}"] += 1
            
            # Generate patterns for common sequences
            if sequence_patterns:
                total_sequences = sum(sequence_patterns.values())
                for sequence, count in sequence_patterns.most_common(5):
                    confidence = count / total_sequences
                    
                    if confidence >= 0.3 and count >= 2:
                        patterns.append(DetectedPattern(
                            pattern_type=PatternType.WORKFLOW_PATTERN,
                            pattern_key="sequence",
                            pattern_value=sequence,
                            confidence_score=confidence,
                            evidence_count=count,
                            first_seen=conversations[-1].timestamp,
                            last_seen=conversations[0].timestamp,
                            examples=[f"Followed {sequence} pattern {count} times"]
                        ))
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error detecting workflow patterns: {e}")
            return []

    def _detect_resource_patterns(self, conversations: List[Conversation]) -> List[DetectedPattern]:
        """Detect frequently accessed resource patterns."""
        patterns = []
        
        try:
            # Extract URLs, file paths, and documentation references
            resource_mentions = Counter()
            resource_contexts = defaultdict(list)
            
            for conv in conversations:
                content = conv.content
                
                # Find URLs
                urls = re.findall(r'https?://[^\s]+', content)
                for url in urls:
                    # Extract domain for pattern detection
                    domain_match = re.search(r'https?://([^/]+)', url)
                    if domain_match:
                        domain = domain_match.group(1)
                        resource_mentions[f"url:{domain}"] += 1
                        resource_contexts[f"url:{domain}"].append(conv.id)
                
                # Find file paths
                file_paths = re.findall(r'[./][\w/.-]+\.\w+', content)
                for path in file_paths:
                    extension = path.split('.')[-1].lower()
                    resource_mentions[f"file_type:{extension}"] += 1
                    resource_contexts[f"file_type:{extension}"].append(conv.id)
                
                # Find documentation keywords
                doc_keywords = ['documentation', 'docs', 'readme', 'wiki', 'guide', 'tutorial']
                for keyword in doc_keywords:
                    if keyword.lower() in content.lower():
                        resource_mentions[f"doc_type:{keyword}"] += 1
                        resource_contexts[f"doc_type:{keyword}"].append(conv.id)
            
            # Generate patterns for frequently accessed resources
            for resource, count in resource_mentions.most_common(10):
                if count >= 2:  # Lower threshold for testing
                    confidence = min(count / 5, 1.0)  # Cap at 1.0, lower denominator
                    
                    patterns.append(DetectedPattern(
                        pattern_type=PatternType.RESOURCE_USAGE,
                        pattern_key=resource.split(':', 1)[0],
                        pattern_value=resource.split(':', 1)[1],
                        confidence_score=confidence,
                        evidence_count=count,
                        first_seen=conversations[-1].timestamp,
                        last_seen=conversations[0].timestamp,
                        examples=[f"Accessed {resource} {count} times"]
                    ))
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error detecting resource patterns: {e}")
            return []

    async def process_feedback(self, feedback: UserFeedback) -> bool:
        """
        Process user feedback to improve learning.
        
        Args:
            feedback: User feedback data
            
        Returns:
            bool: True if feedback was processed successfully
        """
        try:
            # Store feedback for future analysis
            feedback_key = f"feedback:{feedback.conversation_id}:{feedback.timestamp.isoformat()}"
            feedback_data = {
                'type': feedback.feedback_type.value,
                'conversation_id': feedback.conversation_id,
                'suggestion_id': feedback.suggestion_id,
                'original_suggestion': feedback.original_suggestion,
                'corrected_value': feedback.corrected_value,
                'context': feedback.context
            }
            
            self.preferences_repo.set_value(
                feedback_key,
                feedback_data,
                PreferenceCategory.LEARNING
            )
            
            # Process different types of feedback
            if feedback.feedback_type == FeedbackType.CORRECTION:
                await self._process_correction_feedback(feedback)
            elif feedback.feedback_type == FeedbackType.PREFERENCE_UPDATE:
                await self._process_preference_update(feedback)
            elif feedback.feedback_type in [FeedbackType.POSITIVE, FeedbackType.NEGATIVE]:
                await self._process_rating_feedback(feedback)
            elif feedback.feedback_type in [FeedbackType.STORAGE_APPROVAL, FeedbackType.STORAGE_REJECTION, FeedbackType.STORAGE_MODIFICATION]:
                await self._process_storage_feedback(feedback)
            
            logger.info(f"Processed {feedback.feedback_type.value} feedback for conversation {feedback.conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing feedback: {e}")
            return False

    async def _process_storage_feedback(self, feedback: UserFeedback) -> None:
        """Process storage-related feedback to improve analysis accuracy."""
        try:
            # Extract storage analysis details from context
            analysis_result = feedback.context.get('analysis_result', {})
            category = analysis_result.get('category')
            confidence = analysis_result.get('confidence', 0.0)
            
            if not category:
                logger.warning("Storage feedback missing category information")
                return
            
            # Update category accuracy tracking
            await self._update_category_accuracy(feedback.feedback_type, category, confidence)
            
            # Update confidence calibration
            await self._update_confidence_calibration(feedback.feedback_type, confidence, category)
            
            # Update pattern effectiveness
            await self._update_pattern_effectiveness(feedback, analysis_result)
            
            # Learn from modifications
            if feedback.feedback_type == FeedbackType.STORAGE_MODIFICATION:
                await self._learn_from_storage_modification(feedback, analysis_result)
            
            # Update user preferences based on feedback
            await self._update_user_storage_preferences(feedback, analysis_result)
            
            logger.info(f"Processed storage feedback: {feedback.feedback_type.value} for category {category}")
            
        except Exception as e:
            logger.error(f"Error processing storage feedback: {e}")

    async def _update_category_accuracy(self, feedback_type: FeedbackType, category: str, confidence: float) -> None:
        """Update accuracy tracking for storage categories."""
        try:
            accuracy_key = f"category_accuracy:{category}"
            default_data = {
                'total_suggestions': 0,
                'approved': 0,
                'rejected': 0,
                'modified': 0,
                'accuracy_rate': 0.0,
                'confidence_sum': 0.0,
                'last_updated': datetime.now().isoformat()
            }
            accuracy_data = self.preferences_repo.get_value(accuracy_key, default_data)
            
            # Ensure all required keys exist
            for key, default_value in default_data.items():
                if key not in accuracy_data:
                    accuracy_data[key] = default_value
            
            # Update counters
            accuracy_data['total_suggestions'] += 1
            accuracy_data['confidence_sum'] += confidence
            
            if feedback_type == FeedbackType.STORAGE_APPROVAL:
                accuracy_data['approved'] += 1
            elif feedback_type == FeedbackType.STORAGE_REJECTION:
                accuracy_data['rejected'] += 1
            elif feedback_type == FeedbackType.STORAGE_MODIFICATION:
                accuracy_data['modified'] += 1
            
            # Calculate accuracy rate (approvals + modifications as positive)
            positive_feedback = accuracy_data['approved'] + accuracy_data['modified']
            accuracy_data['accuracy_rate'] = positive_feedback / accuracy_data['total_suggestions']
            accuracy_data['avg_confidence'] = accuracy_data['confidence_sum'] / accuracy_data['total_suggestions']
            accuracy_data['last_updated'] = datetime.now().isoformat()
            
            # Store updated accuracy data
            self.preferences_repo.set_value(
                accuracy_key,
                accuracy_data,
                PreferenceCategory.LEARNING
            )
            
        except Exception as e:
            logger.error(f"Error updating category accuracy: {e}")

    async def _update_confidence_calibration(self, feedback_type: FeedbackType, confidence: float, category: str) -> None:
        """Update confidence calibration to improve threshold accuracy."""
        try:
            # Create confidence buckets (0.0-0.2, 0.2-0.4, etc.)
            confidence_bucket = int(confidence * 5) / 5  # Round to nearest 0.2
            calibration_key = f"confidence_calibration:{confidence_bucket:.1f}:{category}"
            
            default_data = {
                'total_predictions': 0,
                'correct_predictions': 0,
                'calibration_score': 0.0,
                'confidence_bucket': confidence_bucket,
                'category': category,
                'last_updated': datetime.now().isoformat()
            }
            calibration_data = self.preferences_repo.get_value(calibration_key, default_data)
            
            # Ensure all required keys exist
            for key, default_value in default_data.items():
                if key not in calibration_data:
                    calibration_data[key] = default_value
            
            calibration_data['total_predictions'] += 1
            
            # Consider approvals and modifications as correct predictions
            if feedback_type in [FeedbackType.STORAGE_APPROVAL, FeedbackType.STORAGE_MODIFICATION]:
                calibration_data['correct_predictions'] += 1
            
            # Calculate calibration score
            calibration_data['calibration_score'] = (
                calibration_data['correct_predictions'] / calibration_data['total_predictions']
            )
            calibration_data['last_updated'] = datetime.now().isoformat()
            
            self.preferences_repo.set_value(
                calibration_key,
                calibration_data,
                PreferenceCategory.LEARNING
            )
            
        except Exception as e:
            logger.error(f"Error updating confidence calibration: {e}")

    async def _update_pattern_effectiveness(self, feedback: UserFeedback, analysis_result: Dict[str, Any]) -> None:
        """Update effectiveness tracking for analysis patterns."""
        try:
            category = analysis_result.get('category')
            extracted_info = analysis_result.get('extracted_info', {})
            
            # Track pattern effectiveness by category and extracted features
            for info_key, info_value in extracted_info.items():
                pattern_key = f"pattern_effectiveness:{category}:{info_key}:{str(info_value)[:50]}"
                
                default_data = {
                    'usage_count': 0,
                    'approval_count': 0,
                    'rejection_count': 0,
                    'modification_count': 0,
                    'effectiveness_score': 0.0,
                    'category': category,
                    'pattern_type': info_key,
                    'last_seen': datetime.now().isoformat()
                }
                pattern_data = self.preferences_repo.get_value(pattern_key, default_data)
                
                # Ensure all required keys exist
                for key, default_value in default_data.items():
                    if key not in pattern_data:
                        pattern_data[key] = default_value
                
                pattern_data['usage_count'] += 1
                
                if feedback.feedback_type == FeedbackType.STORAGE_APPROVAL:
                    pattern_data['approval_count'] += 1
                elif feedback.feedback_type == FeedbackType.STORAGE_REJECTION:
                    pattern_data['rejection_count'] += 1
                elif feedback.feedback_type == FeedbackType.STORAGE_MODIFICATION:
                    pattern_data['modification_count'] += 1
                
                # Calculate effectiveness (approvals + modifications as positive)
                positive_outcomes = pattern_data['approval_count'] + pattern_data['modification_count']
                pattern_data['effectiveness_score'] = positive_outcomes / pattern_data['usage_count']
                pattern_data['last_seen'] = datetime.now().isoformat()
                
                self.preferences_repo.set_value(
                    pattern_key,
                    pattern_data,
                    PreferenceCategory.LEARNING
                )
                
        except Exception as e:
            logger.error(f"Error updating pattern effectiveness: {e}")

    async def _learn_from_storage_modification(self, feedback: UserFeedback, analysis_result: Dict[str, Any]) -> None:
        """Learn from user modifications to improve future suggestions."""
        try:
            original_content = feedback.original_suggestion
            modified_content = feedback.corrected_value
            category = analysis_result.get('category')
            
            if not original_content or not modified_content or not category:
                return
            
            # Analyze the type of modification
            modification_type = self._classify_storage_modification(original_content, modified_content)
            
            modification_key = f"storage_modification:{category}:{modification_type}"
            default_data = {
                'modification_count': 0,
                'examples': [],
                'patterns': {},
                'category': category,
                'modification_type': modification_type,
                'last_updated': datetime.now().isoformat()
            }
            modification_data = self.preferences_repo.get_value(modification_key, default_data)
            
            # Ensure all required keys exist
            for key, default_value in default_data.items():
                if key not in modification_data:
                    modification_data[key] = default_value
            
            modification_data['modification_count'] += 1
            
            # Store example (limit to 5 most recent)
            example = {
                'original': original_content[:200],
                'modified': modified_content[:200],
                'timestamp': feedback.timestamp.isoformat()
            }
            modification_data['examples'].append(example)
            if len(modification_data['examples']) > 5:
                modification_data['examples'] = modification_data['examples'][-5:]
            
            # Extract modification patterns
            if modification_type == 'content_expansion':
                # Learn what types of content users typically add
                added_content = modified_content.replace(original_content, '').strip()
                if added_content:
                    pattern_key = 'expansion_patterns'
                    if pattern_key not in modification_data['patterns']:
                        modification_data['patterns'][pattern_key] = []
                    modification_data['patterns'][pattern_key].append(added_content[:100])
            
            elif modification_type == 'content_reduction':
                # Learn what types of content users typically remove
                # This is more complex, but we can track common removal patterns
                modification_data['patterns']['reduction_preference'] = True
            
            elif modification_type == 'content_restructure':
                # Track restructuring preferences
                modification_data['patterns']['restructure_preference'] = True
            
            modification_data['last_updated'] = datetime.now().isoformat()
            
            self.preferences_repo.set_value(
                modification_key,
                modification_data,
                PreferenceCategory.LEARNING
            )
            
        except Exception as e:
            logger.error(f"Error learning from storage modification: {e}")

    def _classify_storage_modification(self, original: str, modified: str) -> str:
        """Classify the type of modification made to storage content."""
        try:
            original_len = len(original)
            modified_len = len(modified)
            
            # Determine modification type based on length and content changes
            if modified_len > original_len * 1.5:  # More significant expansion threshold
                return 'content_expansion'
            elif modified_len < original_len * 0.5:  # More significant reduction threshold
                return 'content_reduction'
            elif modified_len > original_len * 1.1:  # Moderate expansion
                return 'content_expansion'
            elif modified_len < original_len * 0.9:  # Moderate reduction
                return 'content_reduction'
            elif original.lower().strip() != modified.lower().strip():
                return 'content_restructure'
            else:
                return 'formatting_change'
                
        except Exception:
            return 'unknown_modification'

    async def _update_user_storage_preferences(self, feedback: UserFeedback, analysis_result: Dict[str, Any]) -> None:
        """Update user-specific storage preferences based on feedback."""
        try:
            category = analysis_result.get('category')
            confidence = analysis_result.get('confidence', 0.0)
            tool_name = feedback.context.get('tool_name', 'unknown')
            
            # Track user preferences by category
            pref_key = f"user_storage_pref:{category}"
            default_data = {
                'category': category,
                'approval_rate': 0.0,
                'preferred_confidence_range': [0.6, 1.0],
                'total_interactions': 0,
                'approvals': 0,
                'rejections': 0,
                'modifications': 0,
                'tool_preferences': {},
                'last_updated': datetime.now().isoformat()
            }
            pref_data = self.preferences_repo.get_value(pref_key, default_data)
            
            # Ensure all required keys exist
            for key, default_value in default_data.items():
                if key not in pref_data:
                    pref_data[key] = default_value
            
            pref_data['total_interactions'] += 1
            
            # Update interaction counts
            if feedback.feedback_type == FeedbackType.STORAGE_APPROVAL:
                pref_data['approvals'] += 1
            elif feedback.feedback_type == FeedbackType.STORAGE_REJECTION:
                pref_data['rejections'] += 1
            elif feedback.feedback_type == FeedbackType.STORAGE_MODIFICATION:
                pref_data['modifications'] += 1
            
            # Calculate approval rate
            positive_interactions = pref_data['approvals'] + pref_data['modifications']
            pref_data['approval_rate'] = positive_interactions / pref_data['total_interactions']
            
            # Update tool-specific preferences
            if tool_name not in pref_data['tool_preferences']:
                pref_data['tool_preferences'][tool_name] = {
                    'interactions': 0,
                    'approvals': 0,
                    'approval_rate': 0.0
                }
            
            tool_pref = pref_data['tool_preferences'][tool_name]
            tool_pref['interactions'] += 1
            if feedback.feedback_type in [FeedbackType.STORAGE_APPROVAL, FeedbackType.STORAGE_MODIFICATION]:
                tool_pref['approvals'] += 1
            tool_pref['approval_rate'] = tool_pref['approvals'] / tool_pref['interactions']
            
            # Adjust preferred confidence range based on feedback
            if feedback.feedback_type == FeedbackType.STORAGE_REJECTION and confidence > 0.7:
                # User rejected high-confidence suggestion, raise threshold
                current_min = pref_data['preferred_confidence_range'][0]
                pref_data['preferred_confidence_range'][0] = min(current_min + 0.05, 0.95)
            elif feedback.feedback_type == FeedbackType.STORAGE_APPROVAL and confidence < 0.7:
                # User approved low-confidence suggestion, lower threshold
                current_min = pref_data['preferred_confidence_range'][0]
                pref_data['preferred_confidence_range'][0] = max(current_min - 0.05, 0.3)
            
            pref_data['last_updated'] = datetime.now().isoformat()
            
            self.preferences_repo.set_value(
                pref_key,
                pref_data,
                PreferenceCategory.LEARNING
            )
            
        except Exception as e:
            logger.error(f"Error updating user storage preferences: {e}")

    async def get_storage_feedback_insights(self) -> Dict[str, Any]:
        """Get insights from storage feedback for improving analysis."""
        try:
            insights = {
                'category_performance': {},
                'confidence_calibration': {},
                'pattern_effectiveness': {},
                'user_preferences': {},
                'recommendations': []
            }
            
            # Get all learning preferences
            learning_prefs = self.preferences_repo.get_by_category(PreferenceCategory.LEARNING)
            
            # Analyze category performance
            for pref in learning_prefs:
                if pref.key.startswith('category_accuracy:'):
                    category = pref.key.split(':', 1)[1]
                    insights['category_performance'][category] = pref.value
            
            # Analyze confidence calibration
            for pref in learning_prefs:
                if pref.key.startswith('confidence_calibration:'):
                    parts = pref.key.split(':')
                    if len(parts) >= 3:
                        confidence_bucket = parts[1]
                        category = parts[2]
                        key = f"{confidence_bucket}_{category}"
                        insights['confidence_calibration'][key] = pref.value
            
            # Analyze pattern effectiveness
            for pref in learning_prefs:
                if pref.key.startswith('pattern_effectiveness:'):
                    parts = pref.key.split(':', 3)
                    if len(parts) >= 4:
                        category = parts[1]
                        pattern_type = parts[2]
                        key = f"{category}_{pattern_type}"
                        if key not in insights['pattern_effectiveness']:
                            insights['pattern_effectiveness'][key] = []
                        insights['pattern_effectiveness'][key].append(pref.value)
            
            # Analyze user preferences
            for pref in learning_prefs:
                if pref.key.startswith('user_storage_pref:'):
                    category = pref.key.split(':', 1)[1]
                    insights['user_preferences'][category] = pref.value
            
            # Generate recommendations
            insights['recommendations'] = self._generate_storage_recommendations(insights)
            
            return insights
            
        except Exception as e:
            logger.error(f"Error getting storage feedback insights: {e}")
            return {}

    def _generate_storage_recommendations(self, insights: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on feedback analysis."""
        recommendations = []
        
        try:
            # Analyze category performance
            for category, performance in insights['category_performance'].items():
                accuracy_rate = performance.get('accuracy_rate', 0.0)
                total_suggestions = performance.get('total_suggestions', 0)
                
                if total_suggestions >= 5:  # Enough data for recommendations
                    if accuracy_rate < 0.6:
                        recommendations.append(
                            f"Consider adjusting patterns for '{category}' category (accuracy: {accuracy_rate:.1%})"
                        )
                    elif accuracy_rate > 0.9:
                        recommendations.append(
                            f"'{category}' category performing well (accuracy: {accuracy_rate:.1%}) - consider lowering confidence threshold"
                        )
            
            # Analyze confidence calibration
            calibration_issues = []
            for key, calibration in insights['confidence_calibration'].items():
                confidence_bucket = float(key.split('_')[0])
                calibration_score = calibration.get('calibration_score', 0.0)
                total_predictions = calibration.get('total_predictions', 0)
                
                if total_predictions >= 3:  # Enough data
                    expected_accuracy = confidence_bucket
                    if abs(calibration_score - expected_accuracy) > 0.2:
                        calibration_issues.append(
                            f"Confidence {confidence_bucket:.1f} shows {calibration_score:.1%} accuracy"
                        )
            
            if calibration_issues:
                recommendations.append("Confidence calibration needs adjustment: " + "; ".join(calibration_issues))
            
            # Analyze user preferences
            for category, pref_data in insights['user_preferences'].items():
                approval_rate = pref_data.get('approval_rate', 0.0)
                total_interactions = pref_data.get('total_interactions', 0)
                
                if total_interactions >= 3:
                    if approval_rate < 0.4:
                        recommendations.append(
                            f"User frequently rejects '{category}' suggestions - consider raising confidence threshold"
                        )
                    elif approval_rate > 0.8:
                        recommendations.append(
                            f"User frequently approves '{category}' suggestions - consider lowering confidence threshold"
                        )
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating storage recommendations: {e}")
            return ["Error generating recommendations"]

    async def get_adjusted_confidence_thresholds(self) -> Dict[str, float]:
        """Get confidence thresholds adjusted based on feedback learning."""
        try:
            # Get default thresholds
            thresholds = {
                'auto_store_threshold': 0.85,
                'suggestion_threshold': 0.60,
                'category_adjustments': {}
            }
            
            # Get user preferences to adjust thresholds
            learning_prefs = self.preferences_repo.get_by_category(PreferenceCategory.LEARNING)
            
            for pref in learning_prefs:
                if pref.key.startswith('user_storage_pref:'):
                    category = pref.key.split(':', 1)[1]
                    pref_data = pref.value
                    
                    # Adjust thresholds based on user approval patterns
                    approval_rate = pref_data.get('approval_rate', 0.5)
                    total_interactions = pref_data.get('total_interactions', 0)
                    
                    if total_interactions >= 5:  # Enough data for adjustment
                        preferred_range = pref_data.get('preferred_confidence_range', [0.6, 1.0])
                        
                        # Adjust category-specific thresholds
                        if approval_rate < 0.4:
                            # User rejects frequently, raise thresholds
                            category_adjustment = 0.1
                        elif approval_rate > 0.8:
                            # User approves frequently, lower thresholds
                            category_adjustment = -0.1
                        else:
                            category_adjustment = 0.0
                        
                        thresholds['category_adjustments'][category] = {
                            'auto_store_adjustment': category_adjustment,
                            'suggestion_adjustment': category_adjustment * 0.5,
                            'preferred_min_confidence': preferred_range[0]
                        }
            
            return thresholds
            
        except Exception as e:
            logger.error(f"Error getting adjusted confidence thresholds: {e}")
            return {
                'auto_store_threshold': 0.85,
                'suggestion_threshold': 0.60,
                'category_adjustments': {}
            }

    async def _process_correction_feedback(self, feedback: UserFeedback) -> None:
        """Process correction feedback to update patterns."""
        try:
            if not feedback.corrected_value or not feedback.original_suggestion:
                return
            
            # Update pattern confidence based on correction
            correction_key = f"correction:{feedback.suggestion_id or 'general'}"
            existing_corrections = self.preferences_repo.get_value(correction_key, [])
            
            correction_data = {
                'original': feedback.original_suggestion,
                'corrected': feedback.corrected_value,
                'timestamp': feedback.timestamp.isoformat(),
                'context': feedback.context
            }
            
            existing_corrections.append(correction_data)
            self.preferences_repo.set_value(
                correction_key,
                existing_corrections,
                PreferenceCategory.LEARNING
            )
            
            # Learn from the correction pattern
            await self._learn_from_correction(feedback)
            
        except Exception as e:
            logger.error(f"Error processing correction feedback: {e}")

    async def _process_preference_update(self, feedback: UserFeedback) -> None:
        """Process explicit preference updates."""
        try:
            if not feedback.corrected_value:
                return
            
            # Extract preference from context
            preference_key = feedback.context.get('preference_key')
            if preference_key:
                self.preferences_repo.set_value(
                    preference_key,
                    feedback.corrected_value,
                    PreferenceCategory.GENERAL
                )
                
                logger.info(f"Updated user preference {preference_key} to {feedback.corrected_value}")
            
        except Exception as e:
            logger.error(f"Error processing preference update: {e}")

    async def _process_rating_feedback(self, feedback: UserFeedback) -> None:
        """Process positive/negative rating feedback."""
        try:
            # Update suggestion quality scores
            if feedback.suggestion_id:
                rating_key = f"rating:{feedback.suggestion_id}"
                existing_ratings = self.preferences_repo.get_value(rating_key, [])
                
                rating_data = {
                    'type': feedback.feedback_type.value,
                    'timestamp': feedback.timestamp.isoformat(),
                    'context': feedback.context
                }
                
                existing_ratings.append(rating_data)
                self.preferences_repo.set_value(
                    rating_key,
                    existing_ratings,
                    PreferenceCategory.LEARNING
                )
            
        except Exception as e:
            logger.error(f"Error processing rating feedback: {e}")

    async def _learn_from_correction(self, feedback: UserFeedback) -> None:
        """Learn patterns from user corrections."""
        try:
            original = feedback.original_suggestion
            corrected = feedback.corrected_value
            
            if not original or not corrected:
                return
            
            # Analyze the type of correction
            correction_type = self._classify_correction(original, corrected)
            
            # Update learning patterns based on correction type
            learning_key = f"learning_pattern:{correction_type}"
            existing_patterns = self.preferences_repo.get_value(learning_key, {})
            
            pattern_key = f"{original} -> {corrected}"
            if pattern_key in existing_patterns:
                existing_patterns[pattern_key]['count'] += 1
                existing_patterns[pattern_key]['confidence'] = min(
                    existing_patterns[pattern_key]['confidence'] * 1.1,
                    1.0
                )
            else:
                existing_patterns[pattern_key] = {
                    'count': 1,
                    'confidence': 0.6,
                    'first_seen': feedback.timestamp.isoformat()
                }
            
            existing_patterns[pattern_key]['last_seen'] = feedback.timestamp.isoformat()
            
            self.preferences_repo.set_value(
                learning_key,
                existing_patterns,
                PreferenceCategory.LEARNING
            )
            
        except Exception as e:
            logger.error(f"Error learning from correction: {e}")

    def _classify_correction(self, original: str, corrected: str) -> str:
        """Classify the type of correction made by the user."""
        try:
            # Simple classification based on content analysis
            if len(corrected) > len(original) * 1.5:
                return "expansion"
            elif len(corrected) < len(original) * 0.5:
                return "simplification"
            elif original.lower() != corrected.lower():
                return "rephrasing"
            else:
                return "formatting"
                
        except Exception:
            return "general"

    async def get_personalized_suggestions(
        self,
        context: Dict[str, Any],
        suggestion_type: str = "general",
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get personalized suggestions based on learned patterns.
        
        Args:
            context: Current context for suggestions
            suggestion_type: Type of suggestions to generate
            limit: Maximum number of suggestions
            
        Returns:
            List[Dict[str, Any]]: Personalized suggestions with confidence scores
        """
        try:
            suggestions = []
            
            # Get relevant patterns
            patterns = await self.detect_user_preferences(time_window_days=60)
            
            # Generate suggestions based on patterns
            for pattern in patterns[:limit]:
                suggestion = {
                    'id': f"suggestion_{pattern.pattern_type.value}_{pattern.pattern_key}",
                    'type': suggestion_type,
                    'content': self._generate_suggestion_content(pattern, context),
                    'confidence': pattern.confidence_score,
                    'pattern_type': pattern.pattern_type.value,
                    'evidence_count': pattern.evidence_count,
                    'reasoning': f"Based on {pattern.evidence_count} observations of {pattern.pattern_key} preference"
                }
                suggestions.append(suggestion)
            
            # Sort by confidence and return top suggestions
            suggestions.sort(key=lambda x: x['confidence'], reverse=True)
            return suggestions[:limit]
            
        except Exception as e:
            logger.error(f"Error generating personalized suggestions: {e}")
            return []

    def _generate_suggestion_content(self, pattern: DetectedPattern, context: Dict[str, Any]) -> str:
        """Generate suggestion content based on detected pattern."""
        try:
            if pattern.pattern_type == PatternType.CODING_STYLE:
                if pattern.pattern_key == "indentation":
                    return f"Use {pattern.pattern_value} for indentation (your preferred style)"
                elif pattern.pattern_key == "quotes":
                    return f"Use {pattern.pattern_value} quotes (your preferred style)"
            
            elif pattern.pattern_type == PatternType.TECHNOLOGY_PREFERENCE:
                return f"Consider using {pattern.pattern_value} for {pattern.pattern_key} (your preferred technology)"
            
            elif pattern.pattern_type == PatternType.WORKFLOW_PATTERN:
                return f"Follow your usual workflow: {pattern.pattern_value}"
            
            elif pattern.pattern_type == PatternType.RESOURCE_USAGE:
                return f"You might find {pattern.pattern_value} helpful (frequently accessed resource)"
            
            return f"Based on your patterns: {pattern.pattern_value}"
            
        except Exception as e:
            logger.error(f"Error generating suggestion content: {e}")
            return "Personalized suggestion based on your usage patterns"

    async def get_learning_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the learning engine performance.
        
        Returns:
            Dict[str, Any]: Learning statistics and metrics
        """
        try:
            stats = {
                'patterns_detected': 0,
                'feedback_processed': 0,
                'corrections_learned': 0,
                'preferences_stored': 0,
                'confidence_distribution': {},
                'pattern_types': {},
                'recent_activity': {}
            }
            
            # Count learning-related preferences
            learning_prefs = self.preferences_repo.get_by_category(PreferenceCategory.LEARNING)
            stats['preferences_stored'] = len(learning_prefs)
            
            # Analyze feedback
            feedback_count = 0
            correction_count = 0
            
            for pref in learning_prefs:
                if pref.key.startswith('feedback:'):
                    feedback_count += 1
                elif pref.key.startswith('correction:'):
                    correction_count += 1
            
            stats['feedback_processed'] = feedback_count
            stats['corrections_learned'] = correction_count
            
            # Get recent patterns
            recent_patterns = await self.detect_user_preferences(time_window_days=7)
            stats['patterns_detected'] = len(recent_patterns)
            
            # Analyze pattern types
            pattern_type_counts = Counter()
            confidence_ranges = {'low': 0, 'medium': 0, 'high': 0}
            
            for pattern in recent_patterns:
                pattern_type_counts[pattern.pattern_type.value] += 1
                
                if pattern.confidence_score < 0.5:
                    confidence_ranges['low'] += 1
                elif pattern.confidence_score < 0.8:
                    confidence_ranges['medium'] += 1
                else:
                    confidence_ranges['high'] += 1
            
            stats['pattern_types'] = dict(pattern_type_counts)
            stats['confidence_distribution'] = confidence_ranges
            
            # Recent activity (last 7 days)
            recent_prefs = self.preferences_repo.get_recent_updates(hours=168)  # 7 days
            stats['recent_activity'] = {
                'preferences_updated': len(recent_prefs),
                'last_update': recent_prefs[0].updated_at.isoformat() if recent_prefs else None
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting learning stats: {e}")
            return {}

    async def reset_learning_data(self, confirm: bool = False) -> bool:
        """
        Reset all learning data (use with caution).
        
        Args:
            confirm: Confirmation flag to prevent accidental resets
            
        Returns:
            bool: True if reset was successful
        """
        try:
            if not confirm:
                logger.warning("Reset learning data called without confirmation")
                return False
            
            # Get all learning-related preferences
            learning_prefs = self.preferences_repo.get_by_category(PreferenceCategory.LEARNING)
            
            # Delete learning preferences
            deleted_count = 0
            for pref in learning_prefs:
                if self.preferences_repo.delete(pref.key):
                    deleted_count += 1
            
            logger.info(f"Reset learning data: deleted {deleted_count} preferences")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting learning data: {e}")
            return False