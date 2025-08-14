"""
Session Analysis Service

This service analyzes multiple conversation turns within a session to identify
key insights, generate session summaries, and create cross-references between
session memories and individual conversations.
"""

import re
import json
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import logging

from models.database import Conversation, ContextLink
from repositories.conversation_repository import ConversationRepository
from services.storage_analyzer import StorageAnalyzer
from models.schemas import RelationshipType

logger = logging.getLogger(__name__)


class SessionAnalyzer:
    """
    Analyzes conversation sessions to identify key insights and generate summaries.
    
    Processes multiple conversation turns to find patterns, decisions, and valuable
    information that emerges from extended discussions.
    """
    
    def __init__(self, conversation_repo: ConversationRepository, storage_analyzer: StorageAnalyzer):
        """
        Initialize the session analyzer.
        
        Args:
            conversation_repo: Repository for conversation data access
            storage_analyzer: Storage analyzer for content analysis
        """
        self.conversation_repo = conversation_repo
        self.storage_analyzer = storage_analyzer
        self._initialize_session_patterns()
    
    def _initialize_session_patterns(self) -> None:
        """Initialize patterns for session analysis."""
        self.session_patterns = {
            'decision_evolution': [
                r'(?i)\b(?:initially|first|originally)\b.*(?:but|however|then|now)',
                r'(?i)\b(?:changed|switched|decided|reconsidered)\b.*(?:to|from)',
                r'(?i)\b(?:after|following|considering)\b.*(?:decided|chose|selected)'
            ],
            'problem_solving_flow': [
                r'(?i)\b(?:problem|issue|error)\b.*(?:solution|fix|resolve)',
                r'(?i)\b(?:tried|attempted|tested)\b.*(?:worked|failed|succeeded)',
                r'(?i)\b(?:alternative|another|different)\b.*(?:approach|method|way)'
            ],
            'learning_progression': [
                r'(?i)\b(?:learned|discovered|found out|realized)\b',
                r'(?i)\b(?:understand|got it|makes sense|clear now)\b',
                r'(?i)\b(?:ah|oh|i see|that explains)\b'
            ],
            'context_building': [
                r'(?i)\b(?:building|creating|developing|working on)\b.*(?:project|system|application)',
                r'(?i)\b(?:architecture|design|structure|framework)\b',
                r'(?i)\b(?:requirements|specifications|needs|goals)\b'
            ]
        }
        
        self.insight_keywords = {
            'technical_decision': ['architecture', 'framework', 'technology', 'approach', 'design'],
            'problem_resolution': ['solution', 'fix', 'resolve', 'workaround', 'debug'],
            'learning_outcome': ['learned', 'understand', 'discovered', 'insight', 'realization'],
            'process_improvement': ['optimize', 'improve', 'enhance', 'streamline', 'efficiency'],
            'requirement_clarification': ['requirement', 'specification', 'need', 'goal', 'objective']
        }
    
    async def analyze_session(
        self, 
        conversations: List[Conversation],
        session_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze a session of conversations for key insights.
        
        Args:
            conversations: List of conversations in chronological order
            session_context: Optional context about the session
            
        Returns:
            Dictionary containing session analysis results
        """
        try:
            if not conversations:
                return self._create_empty_session_result()
            
            # Sort conversations by timestamp
            sorted_conversations = sorted(conversations, key=lambda c: c.timestamp)
            
            # Extract session metadata
            session_metadata = self._extract_session_metadata(sorted_conversations, session_context)
            
            # Identify recurring themes
            themes = self._identify_recurring_themes(sorted_conversations)
            
            # Track decision evolution
            decisions = self._track_decision_evolution(sorted_conversations)
            
            # Find problem-solution patterns
            problem_solutions = self._find_problem_solution_patterns(sorted_conversations)
            
            # Identify learning progression
            learning_progression = self._identify_learning_progression(sorted_conversations)
            
            # Generate session insights
            insights = self._generate_session_insights(
                sorted_conversations, themes, decisions, problem_solutions, learning_progression
            )
            
            # Create session summary
            summary = self._generate_session_summary(
                sorted_conversations, themes, decisions, problem_solutions, insights
            )
            
            # Identify cross-references
            cross_references = self._identify_cross_references(sorted_conversations)
            
            return {
                'session_id': self._generate_session_id(sorted_conversations),
                'session_metadata': session_metadata,
                'conversation_count': len(sorted_conversations),
                'time_span': self._calculate_time_span(sorted_conversations),
                'recurring_themes': themes,
                'decision_evolution': decisions,
                'problem_solutions': problem_solutions,
                'learning_progression': learning_progression,
                'key_insights': insights,
                'session_summary': summary,
                'cross_references': cross_references,
                'storage_recommendation': self._generate_storage_recommendation(insights, summary),
                'analysis_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error analyzing session: {e}")
            return self._create_error_result(str(e))
    
    def _extract_session_metadata(
        self, 
        conversations: List[Conversation], 
        session_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract metadata about the session."""
        metadata = {
            'start_time': conversations[0].timestamp.isoformat(),
            'end_time': conversations[-1].timestamp.isoformat(),
            'tools_used': list(set(conv.tool_name for conv in conversations)),
            'projects_involved': list(set(conv.project_id for conv in conversations if conv.project_id)),
            'total_content_length': sum(len(conv.content) for conv in conversations)
        }
        
        if session_context:
            metadata.update(session_context)
        
        return metadata
    
    def _identify_recurring_themes(self, conversations: List[Conversation]) -> List[Dict[str, Any]]:
        """Identify themes that recur throughout the session."""
        themes = {}
        
        # Combine all conversation content
        all_content = " ".join(conv.content for conv in conversations)
        
        # Extract technical terms and concepts
        technical_terms = self._extract_technical_terms(all_content)
        
        # Count occurrences and track conversations
        for term in technical_terms:
            term_lower = term.lower()
            count = 0
            conversation_ids = []
            
            for conv in conversations:
                if term_lower in conv.content.lower():
                    count += 1
                    conversation_ids.append(conv.id)
            
            if count >= 2:  # Theme must appear in at least 2 conversations
                themes[term] = {
                    'term': term,
                    'frequency': count,
                    'conversation_ids': conversation_ids,
                    'first_mention': next(conv.timestamp for conv in conversations if conv.id in conversation_ids),
                    'last_mention': next(conv.timestamp for conv in reversed(conversations) if conv.id in conversation_ids)
                }
        
        # Sort by frequency and return top themes
        sorted_themes = sorted(themes.values(), key=lambda x: x['frequency'], reverse=True)
        return sorted_themes[:10]  # Return top 10 themes
    
    def _extract_technical_terms(self, content: str) -> List[str]:
        """Extract technical terms and concepts from content."""
        terms = set()
        
        # Programming languages
        lang_pattern = r'\b(?:Python|JavaScript|TypeScript|Java|C\+\+|C#|Go|Rust|PHP|Ruby|Swift|Kotlin)\b'
        terms.update(re.findall(lang_pattern, content, re.IGNORECASE))
        
        # Frameworks and libraries
        framework_pattern = r'\b(?:React|Vue|Angular|Django|Flask|Express|Spring|Laravel|Rails|Next\.js|Nuxt)\b'
        terms.update(re.findall(framework_pattern, content, re.IGNORECASE))
        
        # Technologies and tools
        tech_pattern = r'\b(?:Docker|Kubernetes|AWS|Azure|GCP|MongoDB|PostgreSQL|MySQL|Redis|Git|GitHub|GitLab)\b'
        terms.update(re.findall(tech_pattern, content, re.IGNORECASE))
        
        # Architecture patterns
        arch_pattern = r'\b(?:MVC|MVP|MVVM|microservices|monolith|serverless|REST|GraphQL|API)\b'
        terms.update(re.findall(arch_pattern, content, re.IGNORECASE))
        
        # Common technical concepts (2+ words)
        concept_pattern = r'\b(?:machine learning|artificial intelligence|data structure|algorithm|design pattern|code review|unit test|integration test|continuous integration|continuous deployment)\b'
        terms.update(re.findall(concept_pattern, content, re.IGNORECASE))
        
        return list(terms)
    
    def _track_decision_evolution(self, conversations: List[Conversation]) -> List[Dict[str, Any]]:
        """Track how decisions evolved throughout the session."""
        decisions = []
        
        for i, conv in enumerate(conversations):
            content = conv.content.lower()
            
            # Look for decision-making patterns
            for pattern in self.session_patterns['decision_evolution']:
                matches = re.finditer(pattern, content)
                for match in matches:
                    # Extract context around the decision
                    start = max(0, match.start() - 100)
                    end = min(len(content), match.end() + 100)
                    context = content[start:end].strip()
                    
                    decisions.append({
                        'conversation_id': conv.id,
                        'conversation_index': i,
                        'timestamp': conv.timestamp.isoformat(),
                        'decision_context': context,
                        'pattern_matched': pattern,
                        'evolution_type': self._classify_decision_evolution(context)
                    })
        
        return decisions
    
    def _classify_decision_evolution(self, context: str) -> str:
        """Classify the type of decision evolution."""
        if any(word in context for word in ['initially', 'first', 'originally']):
            return 'initial_decision'
        elif any(word in context for word in ['changed', 'switched', 'reconsidered']):
            return 'decision_change'
        elif any(word in context for word in ['after', 'following', 'considering']):
            return 'informed_decision'
        else:
            return 'general_decision'
    
    def _find_problem_solution_patterns(self, conversations: List[Conversation]) -> List[Dict[str, Any]]:
        """Find problem-solution patterns across the session."""
        patterns = []
        
        # Look for problems in early conversations and solutions in later ones
        problems = []
        solutions = []
        
        for i, conv in enumerate(conversations):
            content = conv.content.lower()
            
            # Identify problems
            problem_indicators = ['error', 'issue', 'problem', 'bug', 'fail', 'broken', 'not working']
            if any(indicator in content for indicator in problem_indicators):
                problems.append({
                    'conversation_id': conv.id,
                    'conversation_index': i,
                    'timestamp': conv.timestamp.isoformat(),
                    'content_snippet': self._extract_snippet(conv.content, problem_indicators)
                })
            
            # Identify solutions
            solution_indicators = ['solution', 'fix', 'resolve', 'solved', 'working', 'success']
            if any(indicator in content for indicator in solution_indicators):
                solutions.append({
                    'conversation_id': conv.id,
                    'conversation_index': i,
                    'timestamp': conv.timestamp.isoformat(),
                    'content_snippet': self._extract_snippet(conv.content, solution_indicators)
                })
        
        # Match problems with solutions
        for problem in problems:
            for solution in solutions:
                if solution['conversation_index'] > problem['conversation_index']:
                    # Check if they're related by content similarity or topic
                    similarity = self._calculate_content_similarity(
                        problem['content_snippet'], 
                        solution['content_snippet']
                    )
                    
                    # Also check for topic relatedness (lower threshold)
                    topic_related = similarity > 0.15 or self._are_topics_related(
                        problem['content_snippet'], solution['content_snippet']
                    )
                    
                    if topic_related:
                        patterns.append({
                            'problem_conversation_id': problem['conversation_id'],
                            'solution_conversation_id': solution['conversation_id'],
                            'problem_snippet': problem['content_snippet'],
                            'solution_snippet': solution['content_snippet'],
                            'time_to_resolution': (
                                datetime.fromisoformat(solution['timestamp']) - 
                                datetime.fromisoformat(problem['timestamp'])
                            ).total_seconds() / 60,  # minutes
                            'similarity_score': similarity
                        })
                        break  # Use first matching solution
        
        return patterns
    
    def _extract_snippet(self, content: str, keywords: List[str]) -> str:
        """Extract a relevant snippet containing keywords."""
        content_lower = content.lower()
        
        for keyword in keywords:
            if keyword in content_lower:
                # Find the position of the keyword
                pos = content_lower.find(keyword)
                
                # Extract context around the keyword
                start = max(0, pos - 150)
                end = min(len(content), pos + 150)
                
                snippet = content[start:end].strip()
                
                # Clean up the snippet
                if start > 0:
                    snippet = "..." + snippet
                if end < len(content):
                    snippet = snippet + "..."
                
                return snippet
        
        # Fallback: return first 200 characters
        return content[:200] + ("..." if len(content) > 200 else "")
    
    def _calculate_content_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two text snippets."""
        # Simple word-based similarity
        words1 = set(re.findall(r'\b\w+\b', text1.lower()))
        words2 = set(re.findall(r'\b\w+\b', text2.lower()))
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def _are_topics_related(self, text1: str, text2: str) -> bool:
        """Check if two texts are topically related."""
        # Extract technical terms from both texts
        terms1 = set(self._extract_technical_terms(text1))
        terms2 = set(self._extract_technical_terms(text2))
        
        # If they share technical terms, they're likely related
        if terms1.intersection(terms2):
            return True
        
        # Check for common problem-solution keywords
        problem_keywords = {'error', 'issue', 'problem', 'bug', 'fail', 'broken', 'trouble'}
        solution_keywords = {'solution', 'fix', 'resolve', 'solved', 'working', 'success', 'fixed'}
        
        text1_lower = text1.lower()
        text2_lower = text2.lower()
        
        has_problem_keywords = any(kw in text1_lower for kw in problem_keywords)
        has_solution_keywords = any(kw in text2_lower for kw in solution_keywords)
        
        return has_problem_keywords and has_solution_keywords
    
    def _identify_learning_progression(self, conversations: List[Conversation]) -> List[Dict[str, Any]]:
        """Identify learning progression throughout the session."""
        learning_moments = []
        
        for i, conv in enumerate(conversations):
            content = conv.content.lower()
            
            # Look for learning indicators
            for pattern in self.session_patterns['learning_progression']:
                matches = re.finditer(pattern, content)
                for match in matches:
                    # Extract context around the learning moment
                    start = max(0, match.start() - 100)
                    end = min(len(content), match.end() + 100)
                    context = content[start:end].strip()
                    
                    learning_moments.append({
                        'conversation_id': conv.id,
                        'conversation_index': i,
                        'timestamp': conv.timestamp.isoformat(),
                        'learning_context': context,
                        'learning_type': self._classify_learning_type(context)
                    })
        
        return learning_moments
    
    def _classify_learning_type(self, context: str) -> str:
        """Classify the type of learning moment."""
        if any(word in context for word in ['understand', 'got it', 'makes sense']):
            return 'comprehension'
        elif any(word in context for word in ['discovered', 'found out', 'realized']):
            return 'discovery'
        elif any(word in context for word in ['ah', 'oh', 'i see']):
            return 'insight'
        else:
            return 'general_learning'
    
    def _generate_session_insights(
        self, 
        conversations: List[Conversation],
        themes: List[Dict[str, Any]],
        decisions: List[Dict[str, Any]],
        problem_solutions: List[Dict[str, Any]],
        learning_progression: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate key insights from the session analysis."""
        insights = []
        
        # Theme-based insights
        if themes:
            top_theme = themes[0]
            insights.append({
                'type': 'dominant_theme',
                'title': f"Primary Focus: {top_theme['term']}",
                'description': f"The session heavily focused on {top_theme['term']}, mentioned {top_theme['frequency']} times across {len(top_theme['conversation_ids'])} conversations.",
                'confidence': min(top_theme['frequency'] / len(conversations), 1.0),
                'supporting_data': top_theme
            })
        
        # Decision evolution insights
        if decisions:
            decision_changes = [d for d in decisions if d['evolution_type'] == 'decision_change']
            if decision_changes:
                insights.append({
                    'type': 'decision_evolution',
                    'title': 'Decision Evolution Detected',
                    'description': f"Found {len(decision_changes)} instances where decisions evolved or changed during the session.",
                    'confidence': 0.8,
                    'supporting_data': decision_changes
                })
        
        # Problem-solving insights
        if problem_solutions:
            avg_resolution_time = sum(ps['time_to_resolution'] for ps in problem_solutions) / len(problem_solutions)
            insights.append({
                'type': 'problem_solving',
                'title': 'Problem-Solution Patterns',
                'description': f"Identified {len(problem_solutions)} problem-solution pairs with average resolution time of {avg_resolution_time:.1f} minutes.",
                'confidence': 0.9,
                'supporting_data': {
                    'pattern_count': len(problem_solutions),
                    'avg_resolution_time': avg_resolution_time,
                    'patterns': problem_solutions
                }
            })
        
        # Learning progression insights
        if learning_progression:
            learning_types = {}
            for lp in learning_progression:
                lt = lp['learning_type']
                learning_types[lt] = learning_types.get(lt, 0) + 1
            
            insights.append({
                'type': 'learning_progression',
                'title': 'Learning Journey',
                'description': f"Session showed {len(learning_progression)} learning moments across {len(learning_types)} different types.",
                'confidence': 0.7,
                'supporting_data': {
                    'total_moments': len(learning_progression),
                    'learning_types': learning_types,
                    'progression': learning_progression
                }
            })
        
        # Session complexity insight
        complexity_score = self._calculate_session_complexity(conversations, themes, decisions)
        insights.append({
            'type': 'session_complexity',
            'title': f"Session Complexity: {self._classify_complexity(complexity_score)}",
            'description': f"Based on conversation count, themes, and decisions, this session has {self._classify_complexity(complexity_score).lower()} complexity.",
            'confidence': 0.8,
            'supporting_data': {
                'complexity_score': complexity_score,
                'factors': {
                    'conversation_count': len(conversations),
                    'theme_count': len(themes),
                    'decision_count': len(decisions)
                }
            }
        })
        
        return insights
    
    def _calculate_session_complexity(
        self, 
        conversations: List[Conversation], 
        themes: List[Dict[str, Any]], 
        decisions: List[Dict[str, Any]]
    ) -> float:
        """Calculate a complexity score for the session."""
        score = 0.0
        
        # Conversation count factor
        score += min(len(conversations) / 10, 1.0) * 0.3
        
        # Theme diversity factor
        score += min(len(themes) / 5, 1.0) * 0.3
        
        # Decision complexity factor
        score += min(len(decisions) / 3, 1.0) * 0.2
        
        # Content length factor
        total_length = sum(len(conv.content) for conv in conversations)
        score += min(total_length / 10000, 1.0) * 0.2
        
        return score
    
    def _classify_complexity(self, score: float) -> str:
        """Classify complexity score into categories."""
        if score >= 0.8:
            return "High"
        elif score >= 0.5:
            return "Medium"
        else:
            return "Low"
    
    def _generate_session_summary(
        self,
        conversations: List[Conversation],
        themes: List[Dict[str, Any]],
        decisions: List[Dict[str, Any]],
        problem_solutions: List[Dict[str, Any]],
        insights: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate a comprehensive session summary."""
        summary = {
            'overview': self._generate_overview(conversations, themes, insights),
            'key_topics': [theme['term'] for theme in themes[:5]],
            'major_decisions': [d['decision_context'][:100] + "..." for d in decisions[:3]],
            'problems_solved': len(problem_solutions),
            'learning_outcomes': self._extract_learning_outcomes(insights),
            'session_value': self._assess_session_value(insights, problem_solutions, themes),
            'recommended_actions': self._generate_recommendations(insights, themes, decisions)
        }
        
        return summary
    
    def _generate_overview(
        self, 
        conversations: List[Conversation], 
        themes: List[Dict[str, Any]], 
        insights: List[Dict[str, Any]]
    ) -> str:
        """Generate a natural language overview of the session."""
        overview_parts = []
        
        # Basic session info
        duration = self._calculate_time_span(conversations)
        overview_parts.append(f"Session spanning {duration} with {len(conversations)} conversations")
        
        # Primary theme
        if themes:
            primary_theme = themes[0]['term']
            overview_parts.append(f"primarily focused on {primary_theme}")
        
        # Key insights
        insight_types = [insight['type'] for insight in insights]
        if 'problem_solving' in insight_types:
            overview_parts.append("involving problem-solving activities")
        if 'decision_evolution' in insight_types:
            overview_parts.append("with evolving decisions")
        if 'learning_progression' in insight_types:
            overview_parts.append("showing learning progression")
        
        return ". ".join(overview_parts) + "."
    
    def _extract_learning_outcomes(self, insights: List[Dict[str, Any]]) -> List[str]:
        """Extract learning outcomes from insights."""
        outcomes = []
        
        for insight in insights:
            if insight['type'] == 'learning_progression':
                learning_data = insight['supporting_data']
                for learning_type, count in learning_data['learning_types'].items():
                    outcomes.append(f"{count} {learning_type} moments")
            elif insight['type'] == 'problem_solving':
                outcomes.append(f"Resolved {insight['supporting_data']['pattern_count']} problems")
            elif insight['type'] == 'decision_evolution':
                outcomes.append("Evolved decision-making process")
        
        return outcomes
    
    def _assess_session_value(
        self, 
        insights: List[Dict[str, Any]], 
        problem_solutions: List[Dict[str, Any]], 
        themes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Assess the overall value of the session."""
        value_score = 0.0
        value_factors = []
        
        # Problem-solving value
        if problem_solutions:
            ps_value = min(len(problem_solutions) / 3, 1.0) * 0.3
            value_score += ps_value
            value_factors.append(f"Solved {len(problem_solutions)} problems")
        
        # Learning value
        learning_insights = [i for i in insights if i['type'] == 'learning_progression']
        if learning_insights:
            learning_value = 0.2
            value_score += learning_value
            value_factors.append("Demonstrated learning progression")
        
        # Decision value
        decision_insights = [i for i in insights if i['type'] == 'decision_evolution']
        if decision_insights:
            decision_value = 0.2
            value_score += decision_value
            value_factors.append("Evolved decision-making")
        
        # Theme consistency value
        if themes and themes[0]['frequency'] >= 3:
            theme_value = 0.2
            value_score += theme_value
            value_factors.append("Maintained focused discussion")
        
        # Complexity value
        complexity_insights = [i for i in insights if i['type'] == 'session_complexity']
        if complexity_insights and complexity_insights[0]['supporting_data']['complexity_score'] > 0.5:
            complexity_value = 0.1
            value_score += complexity_value
            value_factors.append("Handled complex topics")
        
        return {
            'score': value_score,
            'classification': self._classify_session_value(value_score),
            'factors': value_factors
        }
    
    def _classify_session_value(self, score: float) -> str:
        """Classify session value score."""
        if score >= 0.8:
            return "High Value"
        elif score >= 0.5:
            return "Medium Value"
        elif score >= 0.2:
            return "Low Value"
        else:
            return "Minimal Value"
    
    def _generate_recommendations(
        self, 
        insights: List[Dict[str, Any]], 
        themes: List[Dict[str, Any]], 
        decisions: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate actionable recommendations based on session analysis."""
        recommendations = []
        
        # Theme-based recommendations
        if themes:
            top_themes = themes[:3]
            recommendations.append(
                f"Consider creating documentation for {', '.join(t['term'] for t in top_themes)} "
                f"as they were central to this session"
            )
        
        # Decision-based recommendations
        decision_changes = [d for d in decisions if d['evolution_type'] == 'decision_change']
        if decision_changes:
            recommendations.append(
                "Document the decision evolution process to help with future similar decisions"
            )
        
        # Problem-solving recommendations
        problem_insights = [i for i in insights if i['type'] == 'problem_solving']
        if problem_insights:
            recommendations.append(
                "Create a knowledge base entry for the problem-solution patterns identified"
            )
        
        # Learning recommendations
        learning_insights = [i for i in insights if i['type'] == 'learning_progression']
        if learning_insights:
            recommendations.append(
                "Consider scheduling follow-up sessions to reinforce the learning outcomes"
            )
        
        # Complexity recommendations
        complexity_insights = [i for i in insights if i['type'] == 'session_complexity']
        if complexity_insights and complexity_insights[0]['supporting_data']['complexity_score'] > 0.7:
            recommendations.append(
                "Break down complex topics into smaller, focused sessions for better retention"
            )
        
        return recommendations
    
    def _identify_cross_references(self, conversations: List[Conversation]) -> List[Dict[str, Any]]:
        """Identify cross-references between conversations in the session."""
        cross_refs = []
        
        for i, conv1 in enumerate(conversations):
            for j, conv2 in enumerate(conversations[i+1:], i+1):
                # Calculate content similarity
                similarity = self._calculate_content_similarity(conv1.content, conv2.content)
                
                if similarity > 0.15:  # Lower threshold for cross-reference
                    cross_refs.append({
                        'source_conversation_id': conv1.id,
                        'target_conversation_id': conv2.id,
                        'relationship_type': RelationshipType.RELATED.value,
                        'similarity_score': similarity,
                        'time_gap_minutes': (conv2.timestamp - conv1.timestamp).total_seconds() / 60,
                        'reference_reason': self._determine_reference_reason(conv1.content, conv2.content)
                    })
        
        # Sort by similarity score
        cross_refs.sort(key=lambda x: x['similarity_score'], reverse=True)
        return cross_refs[:10]  # Return top 10 cross-references
    
    def _determine_reference_reason(self, content1: str, content2: str) -> str:
        """Determine the reason for cross-reference between two conversations."""
        # Simple heuristic based on common patterns
        common_words = set(re.findall(r'\b\w+\b', content1.lower())).intersection(
            set(re.findall(r'\b\w+\b', content2.lower()))
        )
        
        # Filter out common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        meaningful_words = common_words - stop_words
        
        if len(meaningful_words) > 5:
            return f"Shared concepts: {', '.join(list(meaningful_words)[:3])}"
        elif any(word in content1.lower() and word in content2.lower() 
                for word in ['error', 'problem', 'issue']):
            return "Related problem discussion"
        elif any(word in content1.lower() and word in content2.lower() 
                for word in ['solution', 'fix', 'resolve']):
            return "Related solution discussion"
        else:
            return "General topic similarity"
    
    def _generate_session_id(self, conversations: List[Conversation]) -> str:
        """Generate a unique session ID."""
        if not conversations:
            return f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        start_time = conversations[0].timestamp
        end_time = conversations[-1].timestamp
        
        return f"session_{start_time.strftime('%Y%m%d_%H%M%S')}_{end_time.strftime('%H%M%S')}"
    
    def _calculate_time_span(self, conversations: List[Conversation]) -> str:
        """Calculate and format the time span of the session."""
        if len(conversations) < 2:
            return "Single conversation"
        
        start_time = conversations[0].timestamp
        end_time = conversations[-1].timestamp
        duration = end_time - start_time
        
        if duration.days > 0:
            return f"{duration.days} days, {duration.seconds // 3600} hours"
        elif duration.seconds >= 3600:
            hours = duration.seconds // 3600
            minutes = (duration.seconds % 3600) // 60
            return f"{hours} hours, {minutes} minutes"
        else:
            minutes = duration.seconds // 60
            return f"{minutes} minutes"
    
    def _generate_storage_recommendation(
        self, 
        insights: List[Dict[str, Any]], 
        summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate recommendation for storing the session analysis."""
        # Calculate storage value based on insights and summary
        storage_score = 0.0
        reasons = []
        
        # High-value insights boost storage score
        high_value_insights = [i for i in insights if i['confidence'] > 0.8]
        if high_value_insights:
            storage_score += 0.3
            reasons.append(f"Contains {len(high_value_insights)} high-confidence insights")
        
        # Problem-solving sessions are valuable
        if summary['problems_solved'] > 0:
            storage_score += 0.3
            reasons.append(f"Resolved {summary['problems_solved']} problems")
        
        # Learning outcomes add value
        if summary['learning_outcomes']:
            storage_score += 0.2
            reasons.append("Demonstrated learning progression")
        
        # Session value assessment
        session_value = summary['session_value']['score']
        storage_score += session_value * 0.2
        
        # Determine storage recommendation
        should_store = storage_score >= 0.6
        auto_store = storage_score >= 0.8
        
        return {
            'should_store': should_store,
            'auto_store': auto_store,
            'confidence': storage_score,
            'reasons': reasons,
            'category': 'session_summary',
            'suggested_tags': ['session_analysis', 'multi_turn', summary['session_value']['classification'].lower().replace(' ', '_')]
        }
    
    def _create_empty_session_result(self) -> Dict[str, Any]:
        """Create result for empty session."""
        return {
            'session_id': f"empty_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'session_metadata': {},
            'conversation_count': 0,
            'time_span': "No conversations",
            'recurring_themes': [],
            'decision_evolution': [],
            'problem_solutions': [],
            'learning_progression': [],
            'key_insights': [],
            'session_summary': {
                'overview': "Empty session with no conversations",
                'key_topics': [],
                'major_decisions': [],
                'problems_solved': 0,
                'learning_outcomes': [],
                'session_value': {'score': 0.0, 'classification': 'No Value', 'factors': []},
                'recommended_actions': []
            },
            'cross_references': [],
            'storage_recommendation': {
                'should_store': False,
                'auto_store': False,
                'confidence': 0.0,
                'reasons': ['No conversations to analyze'],
                'category': 'empty_session',
                'suggested_tags': []
            },
            'analysis_timestamp': datetime.now().isoformat()
        }
    
    def _create_error_result(self, error_message: str) -> Dict[str, Any]:
        """Create result for analysis errors."""
        return {
            'session_id': f"error_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'error': error_message,
            'session_metadata': {},
            'conversation_count': 0,
            'analysis_timestamp': datetime.now().isoformat(),
            'storage_recommendation': {
                'should_store': False,
                'auto_store': False,
                'confidence': 0.0,
                'reasons': [f'Analysis error: {error_message}'],
                'category': 'error',
                'suggested_tags': []
            }
        }
    
    async def create_session_memory(
        self, 
        session_analysis: Dict[str, Any], 
        tool_name: str = "session_analyzer"
    ) -> Optional[str]:
        """
        Create a memory entry for the session analysis.
        
        Args:
            session_analysis: Result from analyze_session
            tool_name: Name of the tool creating the memory
            
        Returns:
            Optional conversation ID if stored successfully
        """
        try:
            if not session_analysis.get('storage_recommendation', {}).get('should_store'):
                return None
            
            # Create content for the session memory
            content = self._format_session_memory_content(session_analysis)
            
            # Create metadata
            metadata = {
                'session_id': session_analysis['session_id'],
                'conversation_count': session_analysis['conversation_count'],
                'time_span': session_analysis['time_span'],
                'session_value': session_analysis['session_summary']['session_value'],
                'insights': session_analysis['key_insights'],  # Renamed to avoid "key" validation issue
                'storage_reason': 'Session analysis with valuable insights',
                'analysis_timestamp': session_analysis['analysis_timestamp'],
                'session_metadata': session_analysis['session_metadata']
            }
            
            # Create conversation record
            from models.schemas import ConversationCreate
            conversation_data = ConversationCreate(
                tool_name=tool_name,
                content=content,
                conversation_metadata=metadata,
                tags=session_analysis['storage_recommendation']['suggested_tags']
            )
            
            # Store the conversation
            conversation = self.conversation_repo.create(conversation_data)
            
            if conversation:
                logger.info(f"Created session memory: {conversation.id}")
                return conversation.id
            
            return None
            
        except Exception as e:
            logger.error(f"Error creating session memory: {e}")
            return None
    
    def _format_session_memory_content(self, session_analysis: Dict[str, Any]) -> str:
        """Format session analysis into memory content."""
        content_parts = []
        
        # Session overview
        content_parts.append(f"# Session Analysis: {session_analysis['session_id']}")
        content_parts.append(f"\n## Overview")
        content_parts.append(session_analysis['session_summary']['overview'])
        
        # Key topics
        if session_analysis['session_summary']['key_topics']:
            content_parts.append(f"\n## Key Topics")
            for topic in session_analysis['session_summary']['key_topics']:
                content_parts.append(f"- {topic}")
        
        # Key insights
        if session_analysis['key_insights']:
            content_parts.append(f"\n## Key Insights")
            for insight in session_analysis['key_insights']:
                content_parts.append(f"### {insight['title']}")
                content_parts.append(insight['description'])
                content_parts.append(f"*Confidence: {insight['confidence']:.1%}*")
        
        # Problem solutions
        if session_analysis['problem_solutions']:
            content_parts.append(f"\n## Problems Solved")
            for i, ps in enumerate(session_analysis['problem_solutions'][:3], 1):
                content_parts.append(f"{i}. **Problem**: {ps['problem_snippet'][:100]}...")
                content_parts.append(f"   **Solution**: {ps['solution_snippet'][:100]}...")
                content_parts.append(f"   *Resolution time: {ps['time_to_resolution']:.1f} minutes*")
        
        # Learning outcomes
        if session_analysis['session_summary']['learning_outcomes']:
            content_parts.append(f"\n## Learning Outcomes")
            for outcome in session_analysis['session_summary']['learning_outcomes']:
                content_parts.append(f"- {outcome}")
        
        # Recommendations
        if session_analysis['session_summary']['recommended_actions']:
            content_parts.append(f"\n## Recommended Actions")
            for action in session_analysis['session_summary']['recommended_actions']:
                content_parts.append(f"- {action}")
        
        # Session metadata
        content_parts.append(f"\n## Session Details")
        content_parts.append(f"- **Duration**: {session_analysis['time_span']}")
        content_parts.append(f"- **Conversations**: {session_analysis['conversation_count']}")
        content_parts.append(f"- **Value**: {session_analysis['session_summary']['session_value']['classification']}")
        
        return "\n".join(content_parts)