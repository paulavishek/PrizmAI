"""
AI-Powered Conflict Resolution using Google Gemini
Provides intelligent, context-aware resolution suggestions with reasoning.
"""
import google.generativeai as genai
from django.conf import settings
from typing import List, Dict
import json


class AIConflictResolutionEngine:
    """
    Uses Google Gemini AI to generate intelligent conflict resolution suggestions.
    Provides context-aware, reasoning-backed recommendations.
    """
    
    def __init__(self):
        """Initialize Gemini AI client."""
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-pro')
    
    def generate_advanced_resolutions(self, conflict):
        """
        Generate AI-powered resolution suggestions for a conflict.
        
        Args:
            conflict: ConflictDetection instance
            
        Returns:
            List of resolution suggestions with AI reasoning
        """
        # Build context prompt
        prompt = self._build_conflict_resolution_prompt(conflict)
        
        try:
            # Generate AI response
            response = self.model.generate_content(prompt)
            
            # Parse suggestions
            suggestions = self._parse_ai_suggestions(response.text, conflict)
            
            return suggestions
            
        except Exception as e:
            print(f"AI resolution generation error: {e}")
            return []
    
    def _build_conflict_resolution_prompt(self, conflict):
        """Build a detailed prompt for Gemini AI."""
        conflict_data = conflict.conflict_data
        
        # Base context
        prompt = f"""You are an expert project management AI assistant specializing in conflict resolution.

CONFLICT TYPE: {conflict.get_conflict_type_display()}
SEVERITY: {conflict.get_severity_display()}
TITLE: {conflict.title}
DESCRIPTION: {conflict.description}

CONFLICT DETAILS:
{json.dumps(conflict_data, indent=2)}

TASK INFORMATION:
"""
        
        # Add task details
        for task in conflict.tasks.all():
            prompt += f"""
- Task: {task.title}
  Priority: {task.get_priority_display()}
  Assigned to: {task.assigned_to.get_full_name() if task.assigned_to else 'Unassigned'}
  Due date: {task.due_date.strftime('%Y-%m-%d') if task.due_date else 'Not set'}
  Complexity: {getattr(task, 'complexity_score', 'Unknown')}
  Progress: {task.progress}%
"""
        
        # Add affected users
        prompt += f"\nAFFECTED TEAM MEMBERS:\n"
        for user in conflict.affected_users.all():
            # Get user's current workload
            active_tasks = user.assigned_tasks.exclude(
                column__name__icontains='done'
            ).exclude(
                column__name__icontains='complete'
            ).count()
            
            prompt += f"- {user.get_full_name() or user.username} (Currently assigned: {active_tasks} tasks)\n"
        
        # Specific instructions based on conflict type
        if conflict.conflict_type == 'resource':
            prompt += """
TASK: Suggest 3-5 practical resolutions for this resource conflict.

Consider:
1. Reassigning tasks to available team members
2. Rescheduling tasks to avoid overlap
3. Adjusting task timelines
4. Splitting complex tasks
5. Team collaboration approaches

For each resolution, provide:
- Resolution type (reassign/reschedule/adjust_dates/split_task/add_resources)
- Clear title (max 60 chars)
- Detailed description explaining the approach
- Confidence score (0-100) based on feasibility
- Estimated impact on project timeline
- Specific implementation steps
"""
        
        elif conflict.conflict_type == 'schedule':
            prompt += """
TASK: Suggest 3-5 practical resolutions for this schedule conflict.

Consider:
1. Extending deadlines realistically
2. Re-prioritizing tasks
3. Adding team resources
4. Breaking down tasks
5. Reducing scope where appropriate

For each resolution, provide:
- Resolution type (adjust_dates/reassign/reduce_scope/add_resources)
- Clear title (max 60 chars)
- Detailed description explaining the approach
- Confidence score (0-100) based on feasibility
- Estimated impact on project timeline
- Specific implementation steps
"""
        
        elif conflict.conflict_type == 'dependency':
            prompt += """
TASK: Suggest 3-5 practical resolutions for this dependency conflict.

Consider:
1. Rescheduling dependent tasks
2. Removing unnecessary dependencies
3. Parallel work opportunities
4. Breaking dependency chains
5. Priority adjustments

For each resolution, provide:
- Resolution type (adjust_dates/modify_dependency/remove_dependency/split_task)
- Clear title (max 60 chars)
- Detailed description explaining the approach
- Confidence score (0-100) based on feasibility
- Estimated impact on project timeline
- Specific implementation steps
"""
        
        prompt += """
FORMAT YOUR RESPONSE AS JSON:
{
  "resolutions": [
    {
      "type": "resolution_type",
      "title": "Short title",
      "description": "Detailed description",
      "confidence": 85,
      "impact": "Impact description",
      "steps": ["Step 1", "Step 2", "Step 3"],
      "reasoning": "Why this resolution is recommended"
    }
  ]
}

Provide practical, actionable suggestions that a project manager can implement immediately.
"""
        
        return prompt
    
    def _parse_ai_suggestions(self, ai_response: str, conflict) -> List[Dict]:
        """Parse AI response and create ConflictResolution objects."""
        from kanban.conflict_models import ConflictResolution
        
        suggestions = []
        
        try:
            # Try to extract JSON from response
            json_start = ai_response.find('{')
            json_end = ai_response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = ai_response[json_start:json_end]
                data = json.loads(json_str)
                
                for res_data in data.get('resolutions', []):
                    # Map AI type to model type
                    resolution_type = self._map_resolution_type(res_data.get('type', 'custom'))
                    
                    # Create resolution
                    resolution = ConflictResolution.objects.create(
                        conflict=conflict,
                        resolution_type=resolution_type,
                        title=res_data.get('title', 'AI Suggested Resolution')[:255],
                        description=res_data.get('description', ''),
                        ai_confidence=min(100, max(0, int(res_data.get('confidence', 70)))),
                        ai_reasoning=res_data.get('reasoning', ''),
                        estimated_impact=res_data.get('impact', '')[:255],
                        action_steps=res_data.get('steps', []),
                        auto_applicable=False  # AI suggestions require review
                    )
                    
                    suggestions.append(resolution)
            
        except Exception as e:
            print(f"Error parsing AI suggestions: {e}")
            # Fallback: create a generic suggestion
            resolution = ConflictResolution.objects.create(
                conflict=conflict,
                resolution_type='custom',
                title='AI Analysis Completed',
                description=ai_response[:500],  # Use raw response
                ai_confidence=60,
                ai_reasoning='Generated from AI analysis',
                auto_applicable=False
            )
            suggestions.append(resolution)
        
        return suggestions
    
    def _map_resolution_type(self, ai_type: str) -> str:
        """Map AI-generated type to model resolution type."""
        type_mapping = {
            'reassign': 'reassign',
            'reschedule': 'reschedule',
            'adjust_dates': 'adjust_dates',
            'adjust_timeline': 'adjust_dates',
            'remove_dependency': 'remove_dependency',
            'modify_dependency': 'modify_dependency',
            'split_task': 'split_task',
            'reduce_scope': 'reduce_scope',
            'add_resources': 'add_resources',
            'add_team_member': 'add_resources',
        }
        
        ai_type_lower = ai_type.lower().replace('_', ' ').strip()
        
        for key, value in type_mapping.items():
            if key in ai_type_lower or ai_type_lower in key:
                return value
        
        return 'custom'
    
    def enhance_basic_suggestions(self, conflict, basic_suggestions):
        """
        Enhance basic rule-based suggestions with AI insights.
        
        Args:
            conflict: ConflictDetection instance
            basic_suggestions: List of ConflictResolution instances from rule-based system
            
        Returns:
            Enhanced suggestions with AI reasoning
        """
        if not basic_suggestions:
            return []
        
        # Build prompt to enhance existing suggestions
        prompt = f"""You are an expert project management AI assistant.

CONFLICT: {conflict.title}
DESCRIPTION: {conflict.description}

EXISTING SUGGESTIONS:
"""
        
        for i, suggestion in enumerate(basic_suggestions, 1):
            prompt += f"\n{i}. {suggestion.title}\n   {suggestion.description}\n"
        
        prompt += """
TASK: For each suggestion above, provide:
1. An assessment of its feasibility and potential issues
2. Ways to improve the suggestion
3. Additional context or considerations
4. A revised confidence score (0-100)

FORMAT AS JSON:
{
  "enhancements": [
    {
      "suggestion_number": 1,
      "assessment": "Brief assessment",
      "improvements": "Suggested improvements",
      "considerations": "Important factors to consider",
      "revised_confidence": 85
    }
  ]
}
"""
        
        try:
            response = self.model.generate_content(prompt)
            
            # Parse and apply enhancements
            json_start = response.text.find('{')
            json_end = response.text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response.text[json_start:json_end]
                data = json.loads(json_str)
                
                for enhancement in data.get('enhancements', []):
                    idx = enhancement.get('suggestion_number', 1) - 1
                    if 0 <= idx < len(basic_suggestions):
                        suggestion = basic_suggestions[idx]
                        
                        # Update with AI insights
                        suggestion.ai_reasoning = (
                            f"Assessment: {enhancement.get('assessment', '')}\n\n"
                            f"Improvements: {enhancement.get('improvements', '')}\n\n"
                            f"Considerations: {enhancement.get('considerations', '')}"
                        )
                        
                        # Adjust confidence
                        revised_conf = enhancement.get('revised_confidence')
                        if revised_conf:
                            suggestion.ai_confidence = min(100, max(0, int(revised_conf)))
                        
                        suggestion.save()
        
        except Exception as e:
            print(f"Error enhancing suggestions: {e}")
        
        return basic_suggestions
