"""
AI-Powered Conflict Resolution using AI Router
Provides intelligent, context-aware resolution suggestions with reasoning.
"""
from ai_assistant.utils.ai_router import AIRouter
from django.conf import settings
from typing import List, Dict
import json
import time
from kanban_board.ai_cache import ai_cache_manager


class AIConflictResolutionEngine:
    """
    Uses AI Router to generate intelligent conflict resolution suggestions.
    Provides context-aware, reasoning-backed recommendations.
    """
    
    def __init__(self):
        """Initialize AI router client."""
        self.router = AIRouter()
    
    def generate_advanced_resolutions(self, conflict, user=None):
        """
        Generate AI-powered resolution suggestions for a conflict.
        
        Args:
            conflict: ConflictDetection instance
            user: User making the request (for AI tracking)
            
        Returns:
            List of resolution suggestions with AI reasoning
        """
        start_time = time.time()
        
        # Import tracking here to avoid circular imports
        from api.ai_usage_utils import track_ai_request
        
        # Build context prompt
        prompt = self._build_conflict_resolution_prompt(conflict)
        
        try:
            # Check cache first
            cache_context = f"conflict_{conflict.id}"
            cached = ai_cache_manager.get(prompt, 'conflict_suggestion', cache_context)
            if cached is not None:
                suggestions = self._parse_ai_suggestions(cached, conflict)
                if user:
                    response_time_ms = int((time.time() - start_time) * 1000)
                    track_ai_request(
                        user=user,
                        feature='conflict_resolution',
                        request_type='suggest',
                        board_id=conflict.board.id if conflict.board else None,
                        success=True,
                        response_time_ms=response_time_ms
                    )
                return suggestions

            # Generate AI response with proper config
            response = self.router.complete(
                prompt=prompt,
                user=user,
                complexity='complex',
            )
            ai_text = response.get('text', '')
            
            # Cache the raw response text
            ai_cache_manager.set(prompt, ai_text, 'conflict_suggestion', cache_context)
            
            # Parse suggestions
            suggestions = self._parse_ai_suggestions(ai_text, conflict)
            
            # Track successful AI request
            if user:
                response_time_ms = int((time.time() - start_time) * 1000)
                track_ai_request(
                    user=user,
                    feature='conflict_resolution',
                    request_type='suggest',
                    board_id=conflict.board.id if conflict.board else None,
                    success=True,
                    response_time_ms=response_time_ms
                )
            
            return suggestions
            
        except Exception as e:
            # Track failed AI request
            if user:
                response_time_ms = int((time.time() - start_time) * 1000)
                track_ai_request(
                    user=user,
                    feature='conflict_resolution',
                    request_type='suggest',
                    board_id=conflict.board.id if conflict.board else None,
                    success=False,
                    error_message=str(e),
                    response_time_ms=response_time_ms
                )
            
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
FORMAT YOUR RESPONSE AS JSON WITH FULL EXPLAINABILITY:
{
  "confidence_score": 0.XX,
  "conflict_analysis": {
    "root_cause": "Primary cause of this conflict",
    "contributing_factors": ["Factor 1", "Factor 2"],
    "severity_assessment": "Why this severity level is appropriate"
  },
  "resolutions": [
    {
      "type": "resolution_type",
      "title": "Short title",
      "description": "Detailed description",
      "confidence": 85,
      "confidence_reasoning": "Why this confidence level",
      "impact": "Impact description with quantified improvements where possible",
      "impact_timeline": "immediate|short_term|medium_term",
      "steps": ["Step 1", "Step 2", "Step 3"],
      "step_rationale": ["Why step 1 is needed", "Why step 2", "Why step 3"],
      "reasoning": "2-3 sentences written as a single clean paragraph: (a) why this specific action directly addresses the root cause of this conflict type — explain the causal mechanism, not just the action; (b) what the expected outcome is once applied, including any measurable improvement to the team or timeline; and (c) any important caveats or conditions required for this resolution to work effectively (e.g. team capacity, stakeholder approval, dependency on another task). Do not use bullet points or labeled sections — write as flowing prose.",
      "risks": ["Risk of implementing this resolution"],
      "risk_mitigation": ["How to mitigate the risks"],
      "success_indicators": ["How to know if resolution worked"],
      "alternative_if_fails": "Fallback approach if this doesn't work",
      "assumptions": ["Key assumption for this resolution"]
    }
  ],
  "resolution_comparison": {
    "recommended_first": 1,
    "recommendation_reasoning": "Why this resolution should be tried first",
    "combined_approach": "How resolutions could work together"
  },
  "prevention_insights": {
    "how_to_prevent_recurrence": ["Preventive measure 1", "Preventive measure 2"],
    "process_improvement": "System/process change to prevent similar conflicts"
  }
}

Provide practical, actionable suggestions that a project manager can implement immediately.
For the "reasoning" field, write 2-3 sentences of flowing prose explaining: (a) why this specific action addresses the root cause of this conflict type, (b) the expected outcome if applied, and (c) any key caveats or conditions for it to work. Avoid generic statements — be specific to the conflict and the tasks involved.
"""
        
        return prompt
    
    def _parse_ai_suggestions(self, ai_response: str, conflict) -> List[Dict]:
        """Parse AI response and create ConflictResolution objects."""
        from kanban.conflict_models import ConflictResolution
        
        suggestions = []
        
        try:
            # Strip markdown code fences if the AI wrapped the response (e.g. ```json ... ```)
            clean_response = ai_response.strip()
            if clean_response.startswith('```'):
                # Remove the opening fence line (e.g. "```json\n")
                clean_response = clean_response.split('\n', 1)[-1]
            if clean_response.endswith('```'):
                clean_response = clean_response.rsplit('```', 1)[0]

            # Try to extract JSON from response
            json_start = clean_response.find('{')
            json_end = clean_response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = clean_response[json_start:json_end]
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
            # Fallback: build a clean human-readable description instead of dumping raw JSON
            description = "AI analysis completed. Review the suggestions below."
            try:
                # Attempt to salvage root_cause / contributing_factors from the raw response
                salvage = ai_response.strip()
                if salvage.startswith('```'):
                    salvage = salvage.split('\n', 1)[-1]
                if salvage.endswith('```'):
                    salvage = salvage.rsplit('```', 1)[0]
                j_start = salvage.find('{')
                j_end = salvage.rfind('}') + 1
                if j_start >= 0 and j_end > j_start:
                    fallback_data = json.loads(salvage[j_start:j_end])
                    analysis = fallback_data.get('conflict_analysis', {})
                    root_cause = analysis.get('root_cause', '').strip()
                    factors = [f for f in analysis.get('contributing_factors', []) if f]
                    if root_cause:
                        description = root_cause
                        if factors:
                            description += ' Contributing factors include: ' + '; '.join(factors[:2]) + '.'
            except Exception:
                pass  # Keep the generic message

            resolution = ConflictResolution.objects.create(
                conflict=conflict,
                resolution_type='custom',
                title='AI Analysis Completed',
                description=description,
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
    
    def enhance_basic_suggestions(self, conflict, basic_suggestions, user=None):
        """
        Enhance basic rule-based suggestions with AI insights.
        
        Args:
            conflict: ConflictDetection instance
            basic_suggestions: List of ConflictResolution instances from rule-based system
            user: User making the request (for AI tracking)
            
        Returns:
            Enhanced suggestions with AI reasoning
        """
        if not basic_suggestions:
            return []
        
        start_time = time.time()
        
        # Import tracking here to avoid circular imports
        from api.ai_usage_utils import track_ai_request
        
        # Build prompt to enhance existing suggestions
        prompt = f"""You are an expert project management AI assistant.

CONFLICT: {conflict.title}
DESCRIPTION: {conflict.description}

EXISTING SUGGESTIONS:
"""
        
        for i, suggestion in enumerate(basic_suggestions, 1):
            prompt += f"\n{i}. {suggestion.title}\n   {suggestion.description}\n"
        
        prompt += """
TASK: For each suggestion above, provide enhanced analysis with full explainability:
1. An assessment of its feasibility and potential issues
2. Ways to improve the suggestion
3. Additional context or considerations
4. A revised confidence score (0-100)

FORMAT AS JSON WITH FULL EXPLAINABILITY:
{
  "analysis_confidence": 0.XX,
  "enhancements": [
    {
      "suggestion_number": 1,
      "assessment": "Detailed feasibility assessment",
      "assessment_factors": [
        {
          "factor": "Factor evaluated",
          "rating": "positive|neutral|negative",
          "evidence": "What indicates this"
        }
      ],
      "strengths": ["What's good about this suggestion"],
      "weaknesses": ["Potential issues or gaps"],
      "improvements": "Specific improvements to make this more effective",
      "improvement_rationale": "Why these improvements would help",
      "considerations": "Important factors to consider before implementing",
      "prerequisites": ["What needs to be in place first"],
      "revised_confidence": 85,
      "confidence_reasoning": "Why this confidence level after analysis",
      "reasoning": "2-3 sentences as flowing prose for the 'Why this works' summary card: (a) why this specific action addresses the root cause of this conflict type — explain the causal mechanism; (b) the expected outcome once applied; and (c) any important caveats or conditions required. Synthesise the assessment, improvements, and considerations into this concise paragraph — do not use bullet points or labeled sections.",
      "implementation_tips": ["Practical tip 1", "Practical tip 2"],
      "warning_signs": ["Signs that this isn't working"]
    }
  ],
  "overall_assessment": "Summary of the suggestion set quality",
  "gaps_identified": ["What the suggestions don't address"],
  "additional_recommendations": ["Any additional actions to consider"]
}
"""
        
        try:
            # Check cache first
            cache_context = f"enhance_conflict_{conflict.id}"
            cached_text = ai_cache_manager.get(prompt, 'conflict_suggestion', cache_context)
            if cached_text is None:
                response = self.router.complete(prompt=prompt, user=None, complexity='complex')
                cached_text = response.get('text', '')
                ai_cache_manager.set(prompt, cached_text, 'conflict_suggestion', cache_context)
            
            # Parse and apply enhancements
            json_start = cached_text.find('{')
            json_end = cached_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = cached_text[json_start:json_end]
                data = json.loads(json_str)
                
                for enhancement in data.get('enhancements', []):
                    idx = enhancement.get('suggestion_number', 1) - 1
                    if 0 <= idx < len(basic_suggestions):
                        suggestion = basic_suggestions[idx]
                        
                        # Update with AI insights — use the reasoning field for the card
                        # summary and fall back to synthesising from the detailed fields.
                        reasoning = enhancement.get('reasoning', '').strip()
                        if not reasoning:
                            # Build a clean paragraph from the detailed fields as fallback
                            parts = []
                            assessment = enhancement.get('assessment', '').strip()
                            improvements = enhancement.get('improvements', '').strip()
                            considerations = enhancement.get('considerations', '').strip()
                            if assessment:
                                parts.append(assessment)
                            if improvements:
                                parts.append(improvements)
                            if considerations:
                                parts.append(considerations)
                            reasoning = ' '.join(parts)
                        suggestion.ai_reasoning = reasoning
                        
                        # Adjust confidence
                        revised_conf = enhancement.get('revised_confidence')
                        if revised_conf:
                            suggestion.ai_confidence = min(100, max(0, int(revised_conf)))
                        
                        suggestion.save()
            
            # Track successful AI request
            if user:
                response_time_ms = int((time.time() - start_time) * 1000)
                track_ai_request(
                    user=user,
                    feature='conflict_resolution',
                    request_type='enhance',
                    board_id=conflict.board.id if conflict.board else None,
                    success=True,
                    response_time_ms=response_time_ms
                )
            
            return basic_suggestions
            
        except Exception as e:
            # Track failed AI request
            if user:
                response_time_ms = int((time.time() - start_time) * 1000)
                track_ai_request(
                    user=user,
                    feature='conflict_resolution',
                    request_type='enhance',
                    board_id=conflict.board.id if conflict.board else None,
                    success=False,
                    error_message=str(e),
                    response_time_ms=response_time_ms
                )
            
            print(f"Error enhancing suggestions: {e}")
            return basic_suggestions
