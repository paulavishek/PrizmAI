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
            model = self.genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(prompt)
            
            if response and response.text:
                # Parse AI response and enhance suggestion
                ai_insights = self._parse_ai_enhancement(response.text)
                
                # Merge AI insights with base suggestion
                suggestion_data['reasoning'] = ai_insights.get('reasoning', suggestion_data.get('reasoning', ''))
                
                # Format actions properly - convert from detailed dict to string list for template
                ai_actions = ai_insights.get('actions', [])
                if ai_actions and isinstance(ai_actions, list):
                    formatted_actions = []
                    for action in ai_actions:
                        if isinstance(action, dict):
                            # Format: "Action: rationale → outcome"
                            action_text = action.get('action', '')
                            rationale = action.get('rationale', '')
                            outcome = action.get('expected_outcome', '')
                            hint = action.get('implementation_hint', '')
                            
                            # Build comprehensive action text
                            full_action = action_text
                            if rationale:
                                full_action += f" • Rationale: {rationale}"
                            if outcome:
                                full_action += f" • Expected outcome: {outcome}"
                            if hint:
                                full_action += f" • How to: {hint}"
                            formatted_actions.append(full_action)
                        else:
                            formatted_actions.append(str(action))
                    suggestion_data['recommended_actions'] = formatted_actions
                else:
                    # Keep original if AI didn't provide actions
                    if not suggestion_data.get('recommended_actions'):
                        suggestion_data['recommended_actions'] = []
                
                suggestion_data['expected_impact'] = (
                    ai_insights.get('impact', suggestion_data.get('expected_impact', ''))
                )
                
                # Add explainability fields
                suggestion_data['ai_model_used'] = 'gemini-2.5-flash'
                suggestion_data['generation_method'] = 'hybrid'
                suggestion_data['confidence_score'] = max(
                    suggestion_data['confidence_score'],
                    ai_insights.get('confidence', suggestion_data['confidence_score'])
                )
                
                logger.info(f"Enhanced suggestion with AI insights: {suggestion_data['title']}")
            else:
                logger.warning(f"No AI response received for: {suggestion_data['title']}")
            
            return suggestion_data
            
        except Exception as e:
            logger.error(f"Failed to enhance suggestion with AI: {e}")
            # Ensure base suggestions still have required fields
            if not suggestion_data.get('reasoning'):
                suggestion_data['reasoning'] = suggestion_data.get('message', '')
            if not suggestion_data.get('recommended_actions'):
                suggestion_data['recommended_actions'] = ["Review this issue with your team", "Monitor the situation closely"]
            if not suggestion_data.get('expected_impact'):
                suggestion_data['expected_impact'] = "Addressing this issue can help improve project outcomes."
            return suggestion_data
    
    def _build_enhancement_prompt(self, suggestion: Dict, context: Dict) -> str:
        """Build prompt for AI enhancement with full explainability"""
        return f"""You are an experienced project management coach helping a PM improve their project.
Your advice must be transparent, actionable, and concise.

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
Provide comprehensive coaching advice in JSON format.

**IMPORTANT FORMATTING RULES:**
1. "reasoning": 2-3 sentences max explaining root causes and business impact
2. "actions": Array of 3-5 detailed action objects, each with:
   - "action": Clear, specific step (1 sentence)
   - "rationale": Why it helps (1 sentence)
   - "expected_outcome": Measurable result (1 sentence)
   - "implementation_hint": Practical how-to (1 sentence, 30-60 minutes timeframe when applicable)
3. "impact": 1-2 sentences with quantifiable improvements if possible
4. "confidence": Number between 0.70 and 0.95 based on data quality

JSON Format:
{{
    "reasoning": "A 20% decrease in velocity signals potential team or process issues. This could stem from increased complexity, blockers, or team capacity problems. Addressing this prevents project delays and identifies systemic issues early.",
    "actions": [
        {{
            "action": "Hold a brief team retrospective focused on the past sprint/week",
            "rationale": "A retrospective provides a safe space for the team to discuss what went well and what didn't, helping identify impediments, distractions, or process inefficiencies",
            "expected_outcome": "Identify specific blockers or process issues causing the velocity drop",
            "implementation_hint": "Schedule a 30-60 minute session. Use Start, Stop, Continue format. Ensure psychological safety"
        }},
        {{
            "action": "Review the current sprint/week's task breakdown to identify task complexity changes",
            "rationale": "Tasks might be more complex than previously estimated, requiring more time and effort than anticipated",
            "expected_outcome": "Understand if task estimation needs adjustment or if complexity has genuinely increased",
            "implementation_hint": "Compare actual effort spent vs. estimated effort for completed tasks. Look for patterns"
        }},
        {{
            "action": "Conduct brief 1-on-1 check-ins with each team member",
            "rationale": "Individual conversations can uncover personal blockers, skill gaps, or external factors affecting productivity that might not surface in group settings",
            "expected_outcome": "Identify individual challenges and provide targeted support",
            "implementation_hint": "15-minute conversations. Ask: 'What's blocking you?' and 'What support do you need?'"
        }}
    ],
    "impact": "Addressing velocity drops early can improve team morale by 15-20%, increase productivity by resolving bottlenecks, and enable more accurate project forecasting.",
    "confidence": 0.85
}}

Generate a response following this exact structure. Be specific, actionable, and concise.
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
            model = self.genai.GenerativeModel('gemini-2.5-flash')
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
            model = self.genai.GenerativeModel('gemini-2.5-flash')
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
            model = self.genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(prompt)
            
            if response and response.text:
                return response.text.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to generate learning content: {e}")
            return None
