"""
AI Coach Service

Uses Gemini AI to provide contextual coaching advice
Enhances rule-based suggestions with intelligent analysis
"""

import logging
import json
from typing import Dict, Optional, List
from django.conf import settings

logger = logging.getLogger(__name__)


class AICoachService:
    """
    AI-powered coaching service using Gemini
    Provides contextual advice and explanations
    """
    
    def __init__(self):
        """Initialize AI coach service"""
        self.gemini_available = hasattr(settings, 'GEMINI_API_KEY') and settings.GEMINI_API_KEY
        
        if self.gemini_available:
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.GEMINI_API_KEY)
                self.genai = genai
                logger.info("AI Coach Service initialized with Gemini")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")
                self.gemini_available = False
    
    def enhance_suggestion_with_ai(self, suggestion_data: Dict, context: Dict) -> Dict:
        """
        Enhance a rule-based suggestion with AI-generated insights
        
        Args:
            suggestion_data: Base suggestion from rules engine
            context: Additional board/project context
            
        Returns:
            Enhanced suggestion with AI insights
        """
        if not self.gemini_available:
            logger.debug("AI enhancement skipped - Gemini not available")
            return suggestion_data
        
        try:
            # Build prompt for contextual advice
            prompt = self._build_enhancement_prompt(suggestion_data, context)
            
            # Get AI response
            model = self.genai.GenerativeModel('gemini-2.0-flash-exp')
            response = model.generate_content(prompt)
            
            if response and response.text:
                # Parse AI response and enhance suggestion
                ai_insights = self._parse_ai_enhancement(response.text)
                
                # Merge AI insights with base suggestion
                suggestion_data['reasoning'] = ai_insights.get('reasoning', suggestion_data['reasoning'])
                suggestion_data['recommended_actions'] = (
                    ai_insights.get('actions', suggestion_data['recommended_actions'])
                )
                suggestion_data['expected_impact'] = (
                    ai_insights.get('impact', suggestion_data['expected_impact'])
                )
                suggestion_data['ai_model_used'] = 'gemini-2.0-flash-exp'
                suggestion_data['generation_method'] = 'hybrid'
                suggestion_data['confidence_score'] = max(
                    suggestion_data['confidence_score'],
                    ai_insights.get('confidence', suggestion_data['confidence_score'])
                )
                
                logger.info(f"Enhanced suggestion with AI insights: {suggestion_data['title']}")
            
            return suggestion_data
            
        except Exception as e:
            logger.error(f"Failed to enhance suggestion with AI: {e}")
            return suggestion_data
    
    def _build_enhancement_prompt(self, suggestion: Dict, context: Dict) -> str:
        """Build prompt for AI enhancement with full explainability"""
        return f"""You are an experienced project management coach helping a PM improve their project.
Your advice must be transparent and explainable so the PM understands your reasoning.

## Current Situation:
{suggestion['message']}

## Suggestion Type: {suggestion['suggestion_type']}
## Severity: {suggestion['severity']}

## Project Context:
- Board: {context.get('board_name', 'N/A')}
- Team Size: {context.get('team_size', 'N/A')} members
- Active Tasks: {context.get('active_tasks', 'N/A')}
- Project Phase: {context.get('project_phase', 'N/A')}
- Current Velocity: {context.get('velocity', 'N/A')} tasks/week

## Metrics:
{json.dumps(suggestion.get('metrics_snapshot', {}), indent=2)}

## Task:
As an expert PM coach, provide FULLY EXPLAINABLE coaching advice:

Format your response as JSON WITH FULL EXPLAINABILITY:
{{
    "reasoning": "Detailed explanation of WHY this situation needs attention - identify root causes and their business impact",
    "reasoning_factors": [
        {{
            "factor": "Key factor identified",
            "weight": "high|medium|low",
            "evidence": "What data supports this"
        }}
    ],
    "actions": [
        {{
            "action": "Specific actionable step",
            "rationale": "Why this action addresses the issue",
            "expected_outcome": "What improvement to expect",
            "implementation_hint": "How to implement this"
        }}
    ],
    "impact": "Expected positive outcomes with quantifiable improvements where possible",
    "impact_timeline": "short_term|medium_term|long_term",
    "confidence": 0.XX,
    "confidence_factors": [
        {{
            "factor": "What influences confidence",
            "direction": "increases|decreases",
            "explanation": "Why this affects confidence"
        }}
    ],
    "assumptions": [
        "Key assumption made in this advice"
    ],
    "alternative_approaches": [
        {{
            "approach": "Alternative strategy",
            "tradeoff": "What you gain/lose with this approach"
        }}
    ],
    "risk_of_inaction": "What happens if this advice is not followed"
}}

Focus on actionable advice that a PM can implement immediately. Consider the specific context and metrics provided.
Be transparent about your reasoning so the PM can make an informed decision.
"""
    
    def _parse_ai_enhancement(self, ai_response: str) -> Dict:
        """Parse AI response into structured enhancement data"""
        try:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{[\s\S]*\}', ai_response)
            
            if json_match:
                return json.loads(json_match.group())
            else:
                # Fallback: parse text response
                return {
                    'reasoning': ai_response[:500],
                    'actions': [],
                    'impact': '',
                    'confidence': 0.70
                }
        except Exception as e:
            logger.error(f"Failed to parse AI enhancement: {e}")
            return {}
    
    def generate_coaching_advice(self, board, pm_user, question: str) -> Optional[str]:
        """
        Generate coaching advice for a specific PM question
        
        Args:
            board: Board object for context
            pm_user: User asking for advice
            question: PM's question
            
        Returns:
            AI-generated coaching advice
        """
        if not self.gemini_available:
            return "AI coaching is not available. Please configure GEMINI_API_KEY."
        
        try:
            # Gather context
            from kanban.models import Task
            from kanban.burndown_models import TeamVelocitySnapshot
            
            active_tasks = Task.objects.filter(
                column__board=board,
                progress__lt=100
            ).count()
            
            latest_velocity = TeamVelocitySnapshot.objects.filter(
                board=board
            ).order_by('-period_end').first()
            
            # Build context prompt
            prompt = f"""You are an experienced project management coach helping a PM with their project.

## PM's Question:
{question}

## Project Context:
- Board: {board.name}
- Description: {board.description or 'N/A'}
- Team Size: {board.members.count()} members
- Active Tasks: {active_tasks}
- Current Velocity: {latest_velocity.tasks_completed if latest_velocity else 'N/A'} tasks/week

## Your Role:
Provide practical, actionable coaching advice to help this PM address their question.
Draw on project management best practices, agile methodologies, and leadership principles.

Keep your response:
- **Practical**: Give concrete steps they can take
- **Empathetic**: Acknowledge the challenge
- **Evidence-based**: Reference best practices when relevant
- **Concise**: 3-4 paragraphs maximum

Respond directly to their question with helpful guidance.
"""
            
            # Get AI response
            model = self.genai.GenerativeModel('gemini-2.0-flash-exp')
            response = model.generate_content(prompt)
            
            if response and response.text:
                return response.text.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to generate coaching advice: {e}")
            return f"Error generating advice: {str(e)}"
    
    def analyze_pm_performance(self, board, pm_user, time_period_days: int = 30) -> Optional[Dict]:
        """
        Analyze PM performance and provide insights
        
        Args:
            board: Board to analyze
            pm_user: PM user
            time_period_days: Number of days to analyze
            
        Returns:
            Analysis with strengths, improvement areas, and recommendations
        """
        if not self.gemini_available:
            return None
        
        try:
            from datetime import timedelta
            from django.utils import timezone
            from kanban.models import Task
            from kanban.burndown_models import TeamVelocitySnapshot
            from kanban.coach_models import CoachingSuggestion, CoachingFeedback
            
            start_date = timezone.now() - timedelta(days=time_period_days)
            
            # Gather performance data
            suggestions = CoachingSuggestion.objects.filter(
                board=board,
                created_at__gte=start_date
            )
            
            suggestions_received = suggestions.count()
            suggestions_acted_on = suggestions.filter(
                action_taken__in=['accepted', 'partially', 'modified']
            ).count()
            
            # Get velocity trend
            velocities = TeamVelocitySnapshot.objects.filter(
                board=board,
                period_end__gte=start_date.date()
            ).order_by('period_end')
            
            velocity_data = [
                {'period': v.period_end.isoformat(), 'velocity': v.tasks_completed}
                for v in velocities
            ]
            
            # Build analysis prompt
            prompt = f"""You are an executive project management coach analyzing a PM's performance.
Provide fully explainable insights so the PM understands your assessment methodology.

## PM Performance Data ({time_period_days} days):

### Coaching Engagement:
- Suggestions Received: {suggestions_received}
- Suggestions Acted On: {suggestions_acted_on}
- Action Rate: {(suggestions_acted_on/suggestions_received*100) if suggestions_received > 0 else 0:.0f}%

### Velocity Trend:
{json.dumps(velocity_data, indent=2)}

### Project Context:
- Board: {board.name}
- Team Size: {board.members.count()}

## Task:
Provide a comprehensive coaching analysis WITH FULL EXPLAINABILITY:

Format as JSON:
{{
    "confidence_score": 0.XX,
    "assessment_methodology": "How this assessment was derived from the data",
    "data_quality_note": "Any limitations in the data that affect this assessment",
    "strengths": [
        {{
            "strength": "What this PM does well",
            "evidence": "Data supporting this observation",
            "impact": "How this benefits the project"
        }}
    ],
    "improvement_areas": [
        {{
            "area": "Where they can grow",
            "evidence": "Data indicating this need",
            "priority": "high|medium|low",
            "impact_if_improved": "What improvement would bring"
        }}
    ],
    "recommendations": [
        {{
            "recommendation": "Specific action to take",
            "rationale": "Why this is recommended based on data",
            "expected_outcome": "What to expect if implemented",
            "implementation_tips": ["Tip 1", "Tip 2"],
            "priority": 1
        }}
    ],
    "performance_trend": {{
        "direction": "improving|stable|declining",
        "trend_evidence": "What data shows this trend",
        "forecast": "What to expect if current patterns continue"
    }},
    "overall_assessment": "Summary assessment with key takeaways",
    "assessment_confidence": {{
        "level": "high|medium|low",
        "factors": ["What influences this confidence level"]
    }},
    "comparative_context": "How this compares to typical PM performance (if inferrable)",
    "coaching_focus_suggestion": "What the PM should focus on in the next period"
}}

Be constructive, specific, and actionable. Focus on growth and development.
Make your reasoning transparent so the PM understands how you arrived at each conclusion.
"""
            
            # Get AI response
            model = self.genai.GenerativeModel('gemini-2.0-flash-exp')
            response = model.generate_content(prompt)
            
            if response and response.text:
                # Parse response
                import re
                json_match = re.search(r'\{[\s\S]*\}', response.text)
                
                if json_match:
                    return json.loads(json_match.group())
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to analyze PM performance: {e}")
            return None
    
    def generate_learning_content(self, topic: str, pm_experience_level: str = 'intermediate') -> Optional[str]:
        """
        Generate learning content for PMs on specific topics
        
        Args:
            topic: Topic to generate content for
            pm_experience_level: 'beginner', 'intermediate', or 'experienced'
            
        Returns:
            Educational content
        """
        if not self.gemini_available:
            return None
        
        try:
            prompt = f"""You are a project management educator creating training content.
Make your teaching transparent by explaining WHY each concept matters.

## Topic: {topic}
## Audience Level: {pm_experience_level} project managers

## Task:
Create educational content WITH FULL EXPLAINABILITY. Respond in JSON format:

{{
    "content_confidence": 0.XX,
    "topic_overview": "Brief introduction to the topic and why it matters for PMs",
    "key_concepts": [
        {{
            "concept": "Concept name",
            "explanation": "What it means",
            "why_important": "Why PMs need to understand this",
            "real_world_example": "Practical example",
            "common_misconception": "What people often get wrong"
        }}
    ],
    "best_practices": [
        {{
            "practice": "The practice",
            "rationale": "Why this works",
            "how_to_implement": "Steps to apply this",
            "evidence_base": "Where this practice comes from (methodology/research)"
        }}
    ],
    "common_pitfalls": [
        {{
            "pitfall": "What to avoid",
            "why_happens": "Why PMs fall into this trap",
            "consequences": "What goes wrong",
            "how_to_prevent": "Prevention strategies"
        }}
    ],
    "practical_tips": [
        {{
            "tip": "Actionable advice",
            "when_to_use": "Context where this applies",
            "expected_benefit": "What improvement to expect"
        }}
    ],
    "learning_path": {{
        "immediate_actions": ["What to try today"],
        "skill_building": ["How to develop deeper expertise"],
        "resources": ["Suggested further reading or tools"]
    }},
    "self_assessment_questions": [
        "Question to help PM evaluate their current practice"
    ],
    "content_assumptions": [
        "What we assumed about the learner"
    ]
}}

Make content practical and relevant to day-to-day PM work.
Write in a clear, friendly, educational tone.
Explain the 'why' behind every recommendation.
"""
            
            # Get AI response
            model = self.genai.GenerativeModel('gemini-2.0-flash-exp')
            response = model.generate_content(prompt)
            
            if response and response.text:
                return response.text.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to generate learning content: {e}")
            return None
