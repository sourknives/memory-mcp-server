"""
Intelligent Storage Analyzer Service

This service analyzes conversation content to determine storage value using
pattern recognition, confidence scoring, and category classification.
"""

import re
import json
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class StorageAnalyzer:
    """
    Analyzes conversation content to determine storage value and categorization.
    
    Uses pattern-based analysis with regex matching, keyword scoring, and
    confidence algorithms to identify valuable content for storage.
    """
    
    def __init__(self):
        """Initialize the storage analyzer with pattern definitions."""
        self._initialize_patterns()
        self._initialize_keywords()
        self._initialize_confidence_weights()
    
    def _initialize_patterns(self) -> None:
        """Initialize regex patterns for different content types."""
        self.patterns = {
            'preference': [
                r'(?i)\b(?:prefer|like|dislike)\b',
                r'(?i)\b(?:always|never|usually|typically)\b.*(?:use|do|write|format|choose)',
                r'(?i)\b(?:my|our)\s+(?:style|approach|way|method|preference)\b',
                r'(?i)\b(?:remember|note|keep in mind)\s+(?:that\s+)?(?:i|we)\b',
                r'(?i)\b(?:i|we)\s+(?:always|never|usually|typically|prefer to|like to)\b',
                r'(?i)\b(?:default|standard|usual|normal)\s+(?:approach|method|way)\b'
            ],
            'solution': [
                r'(?i)\b(?:solution|fix|resolve|solve|answer)\b.*(?:problem|issue|error|bug)',
                r'(?i)\b(?:here\'s how|try this|you can|to fix)\b',
                r'(?i)\b(?:error|exception|bug|issue)\b.*(?:fix|solve|resolve)',
                r'(?i)\b(?:problem|issue)\b.*(?:solution|fix|resolve)',
                r'(?i)\b(?:step|steps)\s+(?:\d+|one|two|three|first|second|third)\b',
                r'(?i)\b(?:workaround|alternative|instead)\b'
            ],
            'project_context': [
                r'(?i)\b(?:project|application|app|system|codebase)\b.*(?:uses|built|written|developed)',
                r'(?i)\b(?:architecture|structure|design|framework|stack)\b',
                r'(?i)\b(?:database|api|frontend|backend|server|client)\b',
                r'(?i)\b(?:technology|tech|framework|library|tool)\b.*(?:stack|choice|decision)',
                r'(?i)\b(?:repository|repo|git|github|gitlab)\b',
                r'(?i)\b(?:deployment|production|staging|environment)\b'
            ],
            'decision': [
                r'(?i)\b(?:decided|chosen|selected|picked)\b.*(?:because|since|due to)',
                r'(?i)\b(?:decision|choice|option)\b.*(?:made|taken|selected)',
                r'(?i)\b(?:rationale|reason|reasoning|justification)\b',
                r'(?i)\b(?:trade-off|tradeoff|pros and cons|advantages|disadvantages)\b',
                r'(?i)\b(?:alternative|option|approach)\b.*(?:considered|evaluated|rejected)',
                r'(?i)\b(?:why|because|since|due to)\b.*(?:chose|selected|decided|picked)\b'
            ],
            'explicit_request': [
                r'(?i)\b(?:remember|save|store|keep|note)\s+(?:this|that)\b',
                r'(?i)\b(?:don\'t forget|make sure to remember|important to note)\b',
                r'(?i)\b(?:for future reference|for later|remember for next time)\b',
                r'(?i)\b(?:store|save)\s+(?:in|to)\s+(?:memory|context|notes)\b'
            ]
        }
    
    def _initialize_keywords(self) -> None:
        """Initialize keyword lists for different categories with weights."""
        self.keywords = {
            'preference': {
                'high': ['prefer', 'always', 'never', 'style', 'approach', 'method'],
                'medium': ['like', 'dislike', 'usually', 'typically', 'way', 'standard'],
                'low': ['default', 'normal', 'common', 'general']
            },
            'solution': {
                'high': ['solution', 'fix', 'resolve', 'solve', 'error', 'bug', 'issue'],
                'medium': ['problem', 'workaround', 'alternative', 'try', 'step'],
                'low': ['help', 'assist', 'support', 'guide']
            },
            'project_context': {
                'high': ['architecture', 'framework', 'database', 'api', 'system'],
                'medium': ['project', 'application', 'codebase', 'technology', 'stack'],
                'low': ['code', 'development', 'build', 'structure']
            },
            'decision': {
                'high': ['decision', 'decided', 'chosen', 'rationale', 'trade-off'],
                'medium': ['choice', 'selected', 'reason', 'because', 'alternative'],
                'low': ['option', 'approach', 'consider', 'evaluate']
            }
        }
    
    def _initialize_confidence_weights(self) -> None:
        """Initialize confidence scoring weights."""
        self.confidence_weights = {
            'explicit_request': 1.0,  # Always store explicit requests
            'pattern_match': 0.5,     # Base score for pattern matches
            'keyword_high': 0.4,      # High-value keywords
            'keyword_medium': 0.25,   # Medium-value keywords  
            'keyword_low': 0.15,      # Low-value keywords
            'content_length': 0.1,    # Bonus for substantial content
            'code_presence': 0.15,    # Bonus for code snippets
            'question_answer': 0.2    # Bonus for Q&A patterns
        }
    
    def analyze_for_storage(
        self, 
        user_message: str, 
        ai_response: str, 
        conversation_context: str = "",
        tool_name: str = ""
    ) -> Dict[str, Any]:
        """
        Analyze conversation content for storage value.
        
        Args:
            user_message: The user's message/query
            ai_response: The AI's response
            conversation_context: Additional context from the conversation
            tool_name: Name of the tool being used
            
        Returns:
            Dictionary containing analysis results with storage recommendations
        """
        try:
            # Combine all content for analysis
            full_content = f"{user_message}\n{ai_response}\n{conversation_context}".strip()
            
            # Check for explicit storage requests first
            if self._has_explicit_request(user_message):
                return self._create_explicit_storage_result(user_message, ai_response, tool_name)
            
            # Analyze content for different categories
            category_scores = self._analyze_categories(full_content)
            
            # Get the best category and its confidence
            best_category, base_confidence = self._get_best_category(category_scores)
            
            if best_category is None:
                return self._create_no_storage_result()
            
            # Calculate final confidence with bonuses
            final_confidence = self._calculate_final_confidence(
                base_confidence, full_content, user_message, ai_response
            )
            
            # Extract structured information
            extracted_info = self._extract_structured_info(
                best_category, user_message, ai_response, full_content
            )
            
            # Generate storage recommendation
            return self._create_storage_result(
                best_category, final_confidence, user_message, ai_response, 
                extracted_info, tool_name
            )
            
        except Exception as e:
            logger.error(f"Error in storage analysis: {e}")
            return self._create_error_result(str(e))
    
    def _has_explicit_request(self, user_message: str) -> bool:
        """Check if user explicitly requested storage."""
        for pattern in self.patterns['explicit_request']:
            if re.search(pattern, user_message):
                return True
        return False
    
    def _analyze_categories(self, content: str) -> Dict[str, float]:
        """Analyze content against all category patterns."""
        category_scores = {}
        
        for category, patterns in self.patterns.items():
            if category == 'explicit_request':
                continue
                
            score = 0.0
            pattern_matches = 0
            
            # Check pattern matches
            for pattern in patterns:
                if re.search(pattern, content):
                    pattern_matches += 1
            
            if pattern_matches > 0:
                score += self.confidence_weights['pattern_match'] * min(pattern_matches / len(patterns), 1.0)
            
            # Check keyword matches
            keyword_score = self._calculate_keyword_score(category, content)
            score += keyword_score
            
            category_scores[category] = score
        
        return category_scores
    
    def _calculate_keyword_score(self, category: str, content: str) -> float:
        """Calculate keyword-based confidence score for a category."""
        if category not in self.keywords:
            return 0.0
        
        content_lower = content.lower()
        score = 0.0
        
        for weight_level, keywords in self.keywords[category].items():
            weight = self.confidence_weights[f'keyword_{weight_level}']
            matches = sum(1 for keyword in keywords if keyword in content_lower)
            score += weight * min(matches / len(keywords), 1.0)
        
        return score
    
    def _get_best_category(self, category_scores: Dict[str, float]) -> Tuple[Optional[str], float]:
        """Get the category with the highest confidence score."""
        if not category_scores:
            return None, 0.0
        
        best_category = max(category_scores.items(), key=lambda x: x[1])
        
        # Only return if score is above minimum threshold
        if best_category[1] < 0.05:
            return None, 0.0
        
        return best_category[0], best_category[1]
    
    def _calculate_final_confidence(
        self, base_confidence: float, full_content: str, 
        user_message: str, ai_response: str
    ) -> float:
        """Calculate final confidence with bonuses."""
        confidence = base_confidence
        
        # Content length bonus
        if len(full_content) > 200:
            confidence += self.confidence_weights['content_length']
        
        # Code presence bonus
        if self._has_code_content(full_content):
            confidence += self.confidence_weights['code_presence']
        
        # Question-answer pattern bonus
        if self._is_question_answer_pattern(user_message, ai_response):
            confidence += self.confidence_weights['question_answer']
        
        # Cap at 1.0
        return min(confidence, 1.0)
    
    def _has_code_content(self, content: str) -> bool:
        """Check if content contains code snippets."""
        code_indicators = [
            r'```',  # Code blocks
            r'`[^`]+`',  # Inline code
            r'\b(?:function|class|def|var|let|const|import|export)\b',  # Keywords
            r'[{}();]',  # Common code punctuation
            r'(?:\.py|\.js|\.ts|\.java|\.cpp|\.c|\.html|\.css)'  # File extensions
        ]
        
        for pattern in code_indicators:
            if re.search(pattern, content):
                return True
        return False
    
    def _is_question_answer_pattern(self, user_message: str, ai_response: str) -> bool:
        """Check if this follows a question-answer pattern."""
        question_indicators = [r'\?', r'\bhow\b', r'\bwhat\b', r'\bwhy\b', r'\bwhen\b', r'\bwhere\b']
        
        for pattern in question_indicators:
            if re.search(pattern, user_message, re.IGNORECASE):
                return len(ai_response) > 50  # Substantial response
        
        return False
    
    def _extract_structured_info(
        self, category: str, user_message: str, ai_response: str, full_content: str
    ) -> Dict[str, Any]:
        """Extract structured information based on category."""
        extracted = {}
        
        if category == 'preference':
            extracted = self._extract_preference_info(full_content)
        elif category == 'solution':
            extracted = self._extract_solution_info(user_message, ai_response)
        elif category == 'project_context':
            extracted = self._extract_project_info(full_content)
        elif category == 'decision':
            extracted = self._extract_decision_info(full_content)
        
        return extracted
    
    def _extract_preference_info(self, content: str) -> Dict[str, Any]:
        """Extract preference-specific information."""
        info = {
            'preference_type': 'general',
            'strength': 'medium',
            'context': []
        }
        
        # Determine preference strength
        strong_indicators = ['always', 'never', 'must', 'required', 'essential']
        medium_indicators = ['prefer', 'usually', 'typically', 'generally']
        
        content_lower = content.lower()
        
        if any(indicator in content_lower for indicator in strong_indicators):
            info['strength'] = 'strong'
        elif any(indicator in content_lower for indicator in medium_indicators):
            info['strength'] = 'medium'
        else:
            info['strength'] = 'weak'
        
        # Extract preference type
        if re.search(r'\b(?:code|coding|programming)\b', content_lower):
            info['preference_type'] = 'coding'
        elif re.search(r'\b(?:format|formatting|style)\b', content_lower):
            info['preference_type'] = 'formatting'
        elif re.search(r'\b(?:tool|tools|software)\b', content_lower):
            info['preference_type'] = 'tooling'
        elif re.search(r'\b(?:workflow|process|method)\b', content_lower):
            info['preference_type'] = 'workflow'
        
        # Extract context clues
        context_patterns = [
            r'(?i)\bwhen\s+(?:working|coding|developing|building)\s+(?:with|on|in)\s+([^.!?]+)',
            r'(?i)\bfor\s+([^.!?]+?)(?:\s+(?:projects|development|work))',
            r'(?i)\bin\s+([^.!?]+?)(?:\s+(?:context|situations|cases))'
        ]
        
        for pattern in context_patterns:
            matches = re.findall(pattern, content)
            info['context'].extend([match.strip() for match in matches])
        
        return info
    
    def _extract_solution_info(self, user_message: str, ai_response: str) -> Dict[str, Any]:
        """Extract solution-specific information."""
        info = {
            'problem_type': 'general',
            'solution_steps': [],
            'technologies': [],
            'complexity': 'medium'
        }
        
        # Determine problem type
        user_lower = user_message.lower()
        if re.search(r'\b(?:error|exception|bug|crash|fail)\b', user_lower):
            info['problem_type'] = 'error'
        elif re.search(r'\b(?:performance|slow|speed|optimize)\b', user_lower):
            info['problem_type'] = 'performance'
        elif re.search(r'\b(?:security|secure|vulnerability|auth)\b', user_lower):
            info['problem_type'] = 'security'
        elif re.search(r'\b(?:design|architecture|structure)\b', user_lower):
            info['problem_type'] = 'design'
        elif re.search(r'\b(?:implement|create|build|develop)\b', user_lower):
            info['problem_type'] = 'implementation'
        
        # Extract solution steps
        step_patterns = [
            r'(?i)(?:step\s+)?(?:\d+[.)]\s*|first|second|third|next|then|finally)\s*([^.!?\n]+)',
            r'(?i)(?:you\s+(?:can|should|need to)|try|do)\s+([^.!?\n]+)',
        ]
        
        for pattern in step_patterns:
            matches = re.findall(pattern, ai_response)
            info['solution_steps'].extend([match.strip() for match in matches if len(match.strip()) > 10])
        
        # Extract technologies mentioned
        tech_patterns = [
            r'\b(?:Python|JavaScript|TypeScript|Java|C\+\+|C#|Go|Rust|PHP|Ruby)\b',
            r'\b(?:React|Vue|Angular|Django|Flask|Express|Spring|Laravel)\b',
            r'\b(?:MySQL|PostgreSQL|MongoDB|Redis|SQLite|Docker|Kubernetes)\b',
            r'\b(?:AWS|Azure|GCP|Heroku|Vercel|Netlify)\b'
        ]
        
        full_content = f"{user_message} {ai_response}"
        for pattern in tech_patterns:
            matches = re.findall(pattern, full_content, re.IGNORECASE)
            info['technologies'].extend(matches)
        
        # Remove duplicates
        info['technologies'] = list(set(info['technologies']))
        info['solution_steps'] = info['solution_steps'][:5]  # Limit to 5 steps
        
        # Determine complexity
        if len(info['solution_steps']) > 3 or len(info['technologies']) > 2:
            info['complexity'] = 'high'
        elif len(info['solution_steps']) <= 1 and len(info['technologies']) <= 1:
            info['complexity'] = 'low'
        
        return info
    
    def _extract_project_info(self, content: str) -> Dict[str, Any]:
        """Extract project context information."""
        info = {
            'project_type': 'general',
            'technologies': [],
            'architecture_patterns': [],
            'components': []
        }
        
        content_lower = content.lower()
        
        # Determine project type
        if re.search(r'\b(?:web|website|webapp|frontend|backend)\b', content_lower):
            info['project_type'] = 'web'
        elif re.search(r'\b(?:mobile|app|ios|android|react native|flutter)\b', content_lower):
            info['project_type'] = 'mobile'
        elif re.search(r'\b(?:api|service|microservice|backend|server)\b', content_lower):
            info['project_type'] = 'api'
        elif re.search(r'\b(?:desktop|gui|electron|tkinter)\b', content_lower):
            info['project_type'] = 'desktop'
        elif re.search(r'\b(?:data|analytics|ml|ai|machine learning)\b', content_lower):
            info['project_type'] = 'data'
        
        # Extract architecture patterns
        arch_patterns = [
            r'\b(?:mvc|mvp|mvvm|microservices|monolith|serverless|event-driven)\b',
            r'\b(?:rest|graphql|grpc|soap)\b',
            r'\b(?:spa|ssr|ssg|pwa)\b'
        ]
        
        for pattern in arch_patterns:
            matches = re.findall(pattern, content_lower)
            info['architecture_patterns'].extend(matches)
        
        # Extract components
        component_patterns = [
            r'\b(?:database|db|cache|queue|storage)\b',
            r'\b(?:auth|authentication|authorization)\b',
            r'\b(?:logging|monitoring|metrics)\b',
            r'\b(?:testing|ci|cd|deployment)\b'
        ]
        
        for pattern in component_patterns:
            matches = re.findall(pattern, content_lower)
            info['components'].extend(matches)
        
        # Extract technologies (reuse from solution extraction)
        tech_patterns = [
            r'\b(?:Python|JavaScript|TypeScript|Java|C\+\+|C#|Go|Rust|PHP|Ruby)\b',
            r'\b(?:React|Vue|Angular|Django|Flask|Express|Spring|Laravel)\b',
            r'\b(?:MySQL|PostgreSQL|MongoDB|Redis|SQLite|Docker|Kubernetes)\b'
        ]
        
        for pattern in tech_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            info['technologies'].extend(matches)
        
        # Remove duplicates and limit results
        info['technologies'] = list(set(info['technologies']))[:10]
        info['architecture_patterns'] = list(set(info['architecture_patterns']))[:5]
        info['components'] = list(set(info['components']))[:10]
        
        return info
    
    def _extract_decision_info(self, content: str) -> Dict[str, Any]:
        """Extract decision-specific information."""
        info = {
            'decision_type': 'technical',
            'rationale': [],
            'alternatives': [],
            'outcome': None
        }
        
        content_lower = content.lower()
        
        # Determine decision type
        if re.search(r'\b(?:architecture|design|structure|pattern)\b', content_lower):
            info['decision_type'] = 'architectural'
        elif re.search(r'\b(?:technology|tool|framework|library)\b', content_lower):
            info['decision_type'] = 'technology'
        elif re.search(r'\b(?:process|workflow|methodology|approach)\b', content_lower):
            info['decision_type'] = 'process'
        elif re.search(r'\b(?:security|performance|scalability)\b', content_lower):
            info['decision_type'] = 'non-functional'
        
        # Extract rationale
        rationale_patterns = [
            r'(?i)(?:because|since|due to|reason|rationale)\s+([^.!?\n]+)',
            r'(?i)(?:this|we|i)\s+(?:chose|selected|decided|picked)\s+[^.!?\n]*?\s+(?:because|since|due to)\s+([^.!?\n]+)',
            r'(?i)(?:advantage|benefit|pro)\s+(?:is|of|:)\s*([^.!?\n]+)'
        ]
        
        for pattern in rationale_patterns:
            matches = re.findall(pattern, content)
            info['rationale'].extend([match.strip() for match in matches if len(match.strip()) > 10])
        
        # Extract alternatives
        alternative_patterns = [
            r'(?i)(?:alternative|option|instead of|rather than|could have)\s+([^.!?\n]+)',
            r'(?i)(?:considered|evaluated|looked at)\s+([^.!?\n]+)',
            r'(?i)(?:vs|versus|compared to)\s+([^.!?\n]+)'
        ]
        
        for pattern in alternative_patterns:
            matches = re.findall(pattern, content)
            info['alternatives'].extend([match.strip() for match in matches if len(match.strip()) > 5])
        
        # Extract outcome if mentioned
        outcome_patterns = [
            r'(?i)(?:result|outcome|consequence)\s+(?:is|was|will be)\s+([^.!?\n]+)',
            r'(?i)(?:this|it)\s+(?:resulted in|led to|caused)\s+([^.!?\n]+)'
        ]
        
        for pattern in outcome_patterns:
            matches = re.findall(pattern, content)
            if matches:
                info['outcome'] = matches[0].strip()
                break
        
        # Limit results
        info['rationale'] = info['rationale'][:3]
        info['alternatives'] = info['alternatives'][:3]
        
        return info
    
    def _create_explicit_storage_result(
        self, user_message: str, ai_response: str, tool_name: str
    ) -> Dict[str, Any]:
        """Create result for explicit storage requests."""
        return {
            'should_store': True,
            'confidence': 1.0,
            'category': 'explicit_request',
            'reason': 'User explicitly requested storage',
            'suggested_content': f"User Query: {user_message}\n\nAI Response: {ai_response}",
            'metadata': {
                'explicit_request': True,
                'tool_name': tool_name,
                'timestamp': datetime.now().isoformat()
            },
            'auto_store': True,
            'extracted_info': {
                'request_type': 'explicit',
                'user_intent': 'remember_for_later'
            }
        }
    
    def _create_storage_result(
        self, category: str, confidence: float, user_message: str, 
        ai_response: str, extracted_info: Dict[str, Any], tool_name: str
    ) -> Dict[str, Any]:
        """Create storage result for analyzed content."""
        auto_store = confidence >= 0.85
        should_store = confidence >= 0.60
        
        # Generate reason based on category and confidence
        reason_map = {
            'preference': f'Detected user preference with {confidence:.1%} confidence',
            'solution': f'Identified problem-solution pair with {confidence:.1%} confidence',
            'project_context': f'Found project context information with {confidence:.1%} confidence',
            'decision': f'Detected technical decision with {confidence:.1%} confidence'
        }
        
        reason = reason_map.get(category, f'Identified {category} content with {confidence:.1%} confidence')
        
        return {
            'should_store': should_store,
            'confidence': confidence,
            'category': category,
            'reason': reason,
            'suggested_content': f"User Query: {user_message}\n\nAI Response: {ai_response}",
            'metadata': {
                'analysis_category': category,
                'confidence': confidence,
                'auto_stored': auto_store,
                'tool_name': tool_name,
                'timestamp': datetime.now().isoformat(),
                'storage_reason': reason
            },
            'auto_store': auto_store,
            'extracted_info': extracted_info
        }
    
    def _create_no_storage_result(self) -> Dict[str, Any]:
        """Create result when no storage is recommended."""
        return {
            'should_store': False,
            'confidence': 0.0,
            'category': None,
            'reason': 'Content does not meet storage criteria',
            'suggested_content': '',
            'metadata': {},
            'auto_store': False,
            'extracted_info': {}
        }
    
    def _create_error_result(self, error_message: str) -> Dict[str, Any]:
        """Create result for analysis errors."""
        return {
            'should_store': False,
            'confidence': 0.0,
            'category': 'error',
            'reason': f'Analysis error: {error_message}',
            'suggested_content': '',
            'metadata': {'error': error_message},
            'auto_store': False,
            'extracted_info': {}
        }
    
    def get_category_info(self, category: str) -> Dict[str, Any]:
        """Get information about a specific category."""
        category_info = {
            'preference': {
                'description': 'User preferences, coding styles, and personal approaches',
                'examples': ['coding style preferences', 'tool preferences', 'workflow preferences'],
                'typical_confidence': '0.7-0.9'
            },
            'solution': {
                'description': 'Problem-solution pairs, fixes, and troubleshooting',
                'examples': ['error fixes', 'implementation solutions', 'workarounds'],
                'typical_confidence': '0.6-0.8'
            },
            'project_context': {
                'description': 'Project architecture, technology stack, and system design',
                'examples': ['tech stack decisions', 'architecture patterns', 'project structure'],
                'typical_confidence': '0.6-0.8'
            },
            'decision': {
                'description': 'Technical decisions, rationale, and trade-offs',
                'examples': ['technology choices', 'design decisions', 'process decisions'],
                'typical_confidence': '0.7-0.9'
            }
        }
        
        return category_info.get(category, {})
    
    def get_confidence_thresholds(self) -> Dict[str, float]:
        """Get the confidence thresholds used for storage decisions."""
        return {
            'auto_store_threshold': 0.85,
            'suggestion_threshold': 0.60,
            'minimum_threshold': 0.10
        }
    
    def apply_learning_adjustments(
        self, 
        analysis_result: Dict[str, Any], 
        learning_adjustments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply learning-based adjustments to analysis results."""
        try:
            category = analysis_result.get('category')
            confidence = analysis_result.get('confidence', 0.0)
            
            if not category or not learning_adjustments:
                return analysis_result
            
            # Get category-specific adjustments
            category_adjustments = learning_adjustments.get('category_adjustments', {})
            category_adjustment = category_adjustments.get(category, {})
            
            if category_adjustment:
                # Apply confidence adjustment
                auto_store_adjustment = category_adjustment.get('auto_store_adjustment', 0.0)
                suggestion_adjustment = category_adjustment.get('suggestion_adjustment', 0.0)
                
                # Adjust the confidence score based on learning
                adjusted_confidence = confidence + (auto_store_adjustment * 0.5)  # Moderate adjustment
                adjusted_confidence = max(0.0, min(1.0, adjusted_confidence))  # Clamp to [0,1]
                
                # Update thresholds for decision making
                base_auto_threshold = 0.85
                base_suggestion_threshold = 0.60
                
                adjusted_auto_threshold = base_auto_threshold + auto_store_adjustment
                adjusted_suggestion_threshold = base_suggestion_threshold + suggestion_adjustment
                
                # Update analysis result
                analysis_result = analysis_result.copy()
                analysis_result['confidence'] = adjusted_confidence
                analysis_result['original_confidence'] = confidence
                analysis_result['learning_adjusted'] = True
                analysis_result['adjustments_applied'] = {
                    'auto_store_adjustment': auto_store_adjustment,
                    'suggestion_adjustment': suggestion_adjustment,
                    'adjusted_auto_threshold': adjusted_auto_threshold,
                    'adjusted_suggestion_threshold': adjusted_suggestion_threshold
                }
                
                # Recalculate storage decisions with adjusted thresholds
                analysis_result['auto_store'] = adjusted_confidence >= adjusted_auto_threshold
                analysis_result['should_store'] = adjusted_confidence >= adjusted_suggestion_threshold
                
                # Update reason to include learning information
                original_reason = analysis_result.get('reason', '')
                analysis_result['reason'] = f"{original_reason} (adjusted based on user feedback)"
                
                logger.debug(f"Applied learning adjustments to {category}: "
                           f"confidence {confidence:.3f} -> {adjusted_confidence:.3f}")
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error applying learning adjustments: {e}")
            return analysis_result