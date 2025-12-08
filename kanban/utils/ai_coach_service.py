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
        """Build prompt for AI enhancement"""
        return f"""You are an experienced project management coach helping a PM improve their project.

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
As an expert PM coach, provide:

1. **Reasoning**: Explain WHY this situation needs attention (2-3 sentences, focusing on root causes)

2. **Recommended Actions**: List 3-5 specific, actionable steps the PM should take (be concrete and practical)

3. **Expected Impact**: Describe the positive outcomes if these actions are taken (1-2 sentences)

4. **Confidence**: Rate your confidence in this advice (0.0-1.0)

Format your response as JSON:
{{
  "reasoning": "Your explanation here",
  "actions": ["Action 1", "Action 2", "Action 3"],
  "impact": "Expected impact description",
  "confidence": 0.85
}}

Focus on actionable advice that a PM can implement immediately. Consider the specific context and metrics provided.
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
Provide a coaching analysis with:

1. **Strengths**: What is this PM doing well? (2-3 points)
2. **Improvement Areas**: Where can they grow? (2-3 points)
3. **Recommendations**: Specific actions to improve (3-5 recommendations)
4. **Overall Assessment**: Brief summary (1-2 sentences)

Format as JSON:
{{
  "strengths": ["Strength 1", "Strength 2"],
  "improvement_areas": ["Area 1", "Area 2"],
  "recommendations": ["Rec 1", "Rec 2", "Rec 3"],
  "overall_assessment": "Summary here"
}}

Be constructive, specific, and actionable. Focus on growth and development.
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

## Topic: {topic}
## Audience Level: {pm_experience_level} project managers

## Task:
Create concise educational content that includes:

1. **Key Concepts**: What this PM needs to understand (2-3 concepts)
2. **Best Practices**: Industry-standard approaches (3-4 practices)
3. **Common Pitfalls**: What to avoid (2-3 pitfalls)
4. **Practical Tips**: Immediately actionable advice (3-4 tips)

Keep it practical and relevant to day-to-day PM work.
Aim for 300-400 words total.

Write in a clear, friendly, educational tone.
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
