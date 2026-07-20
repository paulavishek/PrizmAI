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
    
    def __init__(self, user=None):
        """Initialize AI coach service

        Args:
            user: (optional) the requesting user, used to apply their persisted
                AI response-style profile to coaching prose. Left None for
                non-interactive/batch generation (no directive applied).
        """
        from ai_assistant.utils.ai_router import AIRouter
        self.router = AIRouter()
        self.user = user
        self.gemini_available = True  # AIRouter handles availability internally
        
        # Initialize AI cache manager
        try:
            from kanban_board.ai_cache import ai_cache_manager
            self.ai_cache = ai_cache_manager
        except ImportError:
            self.ai_cache = None
            logger.warning("AI cache not available for AICoachService")
    
    def _get_cached_or_generate(self, prompt: str, operation: str, 
                                 context_id: str = None) -> Optional[str]:
        """
        Get AI response from cache or generate a new one.
        
        Args:
            prompt: The AI prompt
            operation: Operation type for TTL selection
            context_id: Optional context identifier
            
        Returns:
            AI response text or None
        """
        # Apply the requesting user's response-style profile (persisted custom
        # instructions). Empty unless they set non-default prefs. Prepended to
        # the prompt so the cache key naturally varies per style.
        from accounts.style_profile import directive_for_user
        style_directive = directive_for_user(self.user)
        if style_directive:
            prompt = style_directive + "\n\n" + prompt

        # Try cache first
        if self.ai_cache:
            cached = self.ai_cache.get(prompt, operation, context_id)
            if cached:
                logger.debug(f"AI Coach cache HIT for operation: {operation}")
                return cached
        
        # Generate new response
        if not self.gemini_available:
            return None
            
        try:
            result = self.router.complete(
                prompt=prompt,
                user=None,
                complexity='complex',
            )
            response_text = result.get('text', '').strip()

            if response_text:
                # Cache the result
                if self.ai_cache and response_text:
                    self.ai_cache.set(prompt, response_text, operation, context_id)
                    logger.debug(f"AI Coach response cached for operation: {operation}")
                return response_text
            return None
        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            return None
    
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
            
            # Create context ID for caching based on suggestion type and board
            context_id = f"{context.get('board_id', 'unknown')}:{suggestion_data.get('suggestion_type', 'unknown')}"
            
            # Get AI response (cached or fresh)
            response_text = self._get_cached_or_generate(
                prompt, 
                'coaching_suggestion',
                context_id
            )
            
            if response_text:
                # Parse AI response and enhance suggestion
                ai_insights = self._parse_ai_enhancement(response_text)
                
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
    
    def _build_team_roster_block(self, context: Dict) -> str:
        """
        Render a per-member workload/skill roster so the enhancement prompt's
        suggested reassignments (e.g. "give this to X") are grounded in the
        same UserPerformanceProfile data AI Resource Optimization uses —
        instead of the LLM inventing plausible-sounding teammates/actions
        from suggestion text alone, which can contradict the Resource
        Optimization panel (e.g. recommending work go TO someone who is
        already the most overloaded person on the board).
        """
        board_id = context.get('board_id')
        if not board_id:
            return ''

        try:
            from kanban.models import Board, BoardMembership
            from kanban.resource_leveling import ResourceLevelingService

            board = Board.objects.filter(id=board_id).first()
            if not board:
                return ''

            members = list(
                BoardMembership.objects.filter(board=board).select_related('user')[:25]
            )
            if not members:
                return ''

            service = ResourceLevelingService(workspace=getattr(board, 'workspace', None))

            lines = []
            for m in members:
                user = m.user
                try:
                    profile = service.get_or_create_profile(user, board=board)
                except Exception:
                    continue

                display = user.get_full_name() or user.username
                top_skills = sorted(
                    (profile.skill_keywords or {}).items(),
                    key=lambda kv: -kv[1]
                )[:5]
                skills_text = ', '.join(k for k, _ in top_skills) if top_skills else 'none recorded'

                lines.append(
                    f"  - {display} ({user.username}): {profile.current_active_tasks} active tasks, "
                    f"{profile.utilization_percentage:.0f}% capacity utilized, "
                    f"skills: {skills_text}"
                )

            if not lines:
                return ''

            return (
                "\n## Team Workload & Skills (live data — use this, not assumptions):\n"
                + "\n".join(lines)
                + "\nWhen recommending a specific person to take on work, only name someone "
                "from this list, and prefer people with LOWER capacity utilization and "
                "relevant skills. Do NOT recommend giving work to someone already at or "
                "above 90% capacity utilization unless no one else is qualified.\n"
            )
        except Exception as e:
            logger.warning(f"Failed to build team roster block for AI coach prompt: {e}")
            return ''

    def _build_enhancement_prompt(self, suggestion: Dict, context: Dict) -> str:
        """Build prompt for AI enhancement with full explainability"""
        # Render a compact "Custom Fields" section when the workspace has any.
        # See summarize_custom_fields_for_board() — exclude_from_ai fields are
        # already filtered out.
        custom_fields_block = ''
        cf_summary = context.get('custom_fields') or []
        if cf_summary:
            lines = []
            for entry in cf_summary:
                desc = f"- {entry['name']} ({entry['type']}, set on {entry['tasks_set']} tasks"
                top = entry.get('top_values') or []
                if top:
                    desc += f"; common: {', '.join(top)}"
                desc += ")"
                lines.append(desc)
            custom_fields_block = (
                "\n## Workspace Custom Fields (PM-defined task metadata):\n"
                + "\n".join(lines)
                + "\nReference these by name in your advice when relevant; the "
                + "user has chosen them as meaningful signals.\n"
            )

        team_roster_block = self._build_team_roster_block(context)

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
{custom_fields_block}
{team_roster_block}

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
   - If an action names a specific team member to take on, receive, or review work,
     that person MUST come from the "Team Workload & Skills" list above (if present)
     and must NOT already be at/above 90% capacity utilization — pick the least-loaded,
     most skill-relevant person instead. If no roster is provided, keep actions
     role-based ("a teammate with capacity") rather than inventing a name.
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
    
    def _build_board_snapshot(self, board) -> Dict:
        """
        Build a rich, Spectra-quality snapshot of a board's live state for the
        coaching prompt. Returns a dict with both a formatted text block (for
        the LLM) and structured counts (for explainability fallback).
        """
        from kanban.burndown_models import TeamVelocitySnapshot
        from kanban.utils.burndown_predictor import BurndownPredictor
        from ai_assistant.utils.spectra_data_fetchers import (
            fetch_board_tasks,
            fetch_column_distribution,
            fetch_milestones,
        )
        from kanban.models import BoardMembership

        # All real tasks (excludes milestones/epics)
        tasks = fetch_board_tasks(board, filters={'item_type': 'task'})
        incomplete = [t for t in tasks if not t.get('is_complete')]
        overdue = [t for t in incomplete if t.get('is_overdue')]
        unassigned = [t for t in incomplete if not t.get('assigned_to_username')]

        col_dist = fetch_column_distribution(board)
        milestones = fetch_milestones(board)

        # Velocity — use the latest *fully-elapsed* period only. The current
        # period is still in progress (a sprint week that started today has 0
        # completed on day one), so counting it makes velocity read as a ~100%
        # collapse and misleads the LLM. Mirrors
        # CoachingRuleEngine._check_velocity_drop (period_end < today).
        from django.utils import timezone
        velocity_text = 'N/A'
        try:
            today = timezone.now().date()
            BurndownPredictor()._ensure_velocity_snapshots(board)
            snap = (TeamVelocitySnapshot.objects
                    .filter(board=board, period_end__lt=today)
                    .order_by('-period_end').first())
            if snap:
                velocity_text = f"{snap.tasks_completed} tasks/week"
        except Exception as vel_err:
            logger.warning(f"Velocity calc failed for board {board.id}: {vel_err}")

        # Workload per assignee (active incomplete)
        workload: Dict[str, Dict[str, int]] = {}
        for t in incomplete:
            name = t.get('assigned_to_display') or t.get('assigned_to_username') or 'Unassigned'
            row = workload.setdefault(name, {'active': 0, 'overdue': 0})
            row['active'] += 1
            if t.get('is_overdue'):
                row['overdue'] += 1

        # Blocked tasks: incomplete tasks that depend on something not yet complete
        title_to_complete = {t['title']: t.get('is_complete') for t in tasks}
        blocked: List[Dict] = []
        for t in incomplete:
            deps = t.get('dependency_titles') or []
            open_deps = [d for d in deps if title_to_complete.get(d) is False]
            if open_deps:
                blocked.append({
                    'title': t['title'],
                    'assignee': t.get('assigned_to_display') or 'Unassigned',
                    'open_deps': open_deps[:4],
                })

        team = list(BoardMembership.objects.filter(board=board).select_related('user')[:25])

        # ── Format text block ─────────────────────────────────────────────
        lines: List[str] = []
        lines.append(f"Board: {board.name}")
        if board.description:
            lines.append(f"Description: {board.description[:200]}")
        lines.append(f"Team Size: {len(team)} members")
        lines.append(f"Active Tasks (incomplete): {len(incomplete)}")
        lines.append(f"Current Velocity: {velocity_text}")
        lines.append(f"Overdue: {len(overdue)} | Unassigned: {len(unassigned)} | Blocked: {len(blocked)}")

        if col_dist:
            lines.append("")
            lines.append("Column distribution:")
            for name, count in col_dist:
                lines.append(f"  - {name}: {count}")

        if team:
            lines.append("")
            lines.append("Team members:")
            for m in team:
                disp = m.user.get_full_name() or m.user.username
                lines.append(f"  - {disp} ({m.role})")

        if workload:
            lines.append("")
            lines.append("Workload per assignee (active / overdue):")
            for name, row in sorted(workload.items(), key=lambda kv: (-kv[1]['overdue'], -kv[1]['active'])):
                lines.append(f"  - {name}: {row['active']} active, {row['overdue']} overdue")

        if overdue:
            lines.append("")
            lines.append(f"Overdue tasks ({len(overdue)}):")
            for t in sorted(overdue, key=lambda x: -(x.get('overdue_days') or 0))[:15]:
                lines.append(
                    f"  - [{t['column_name']}] {t['title']} "
                    f"— {t.get('assigned_to_display') or 'Unassigned'} "
                    f"— {t.get('overdue_days', '?')} days overdue "
                    f"(priority: {t.get('priority_label') or 'N/A'})"
                )

        # Tasks due in next 7 days
        from datetime import date, timedelta
        today = date.today()
        next_week = today + timedelta(days=7)
        due_soon = [
            t for t in incomplete
            if t.get('due_date_date') and today <= t['due_date_date'] <= next_week
        ]
        if due_soon:
            lines.append("")
            lines.append(f"Due in next 7 days ({len(due_soon)}):")
            for t in sorted(due_soon, key=lambda x: x['due_date_date']):
                lines.append(
                    f"  - {t['title']} — due {t['due_date_date']} "
                    f"— {t.get('assigned_to_display') or 'Unassigned'}"
                )

        if blocked:
            lines.append("")
            lines.append(f"Blocked tasks ({len(blocked)}):")
            for b in blocked[:10]:
                lines.append(f"  - {b['title']} ({b['assignee']}) waiting on: {', '.join(b['open_deps'])}")

        if milestones:
            lines.append("")
            lines.append(f"Milestones ({len(milestones)}):")
            for m in milestones[:10]:
                status = '✅ Done' if m.get('is_complete') else m.get('column_name', 'In progress')
                due = ''
                if m.get('due_date_date'):
                    due = f" — due {m['due_date_date']}"
                    if m.get('is_overdue'):
                        due += ' ⚠️ OVERDUE'
                lines.append(f"  - {m['title']} [{status}]{due}")

        # Compact full task list (titles only) so the LLM can name any task
        # the user asks about, even if not in the highlighted subsets above.
        if incomplete:
            lines.append("")
            lines.append(f"All open task titles ({len(incomplete)}):")
            for t in incomplete[:80]:
                flag = ' ⚠️' if t.get('is_overdue') else ''
                lines.append(
                    f"  - [{t['column_name']}] {t['title']} "
                    f"→ {t.get('assigned_to_display') or 'Unassigned'}{flag}"
                )

        return {
            'text': '\n'.join(lines),
            'counts': {
                'team_size': len(team),
                'active_tasks': len(incomplete),
                'overdue': len(overdue),
                'unassigned': len(unassigned),
                'blocked': len(blocked),
                'velocity': velocity_text,
            },
        }

    def generate_coaching_advice(self, board, pm_user, question: str) -> Optional[Dict]:
        """
        Generate coaching advice for a specific PM question (with caching)

        Args:
            board: Board object for context
            pm_user: User asking for advice
            question: PM's question

        Returns:
            Dict with 'advice' text and 'explainability' metadata, or plain str on fallback
        """
        if not self.gemini_available:
            return "AI coaching is not available. Please configure GEMINI_API_KEY."

        try:
            snapshot = self._build_board_snapshot(board)
            counts = snapshot['counts']
            logger.info(
                f"[AICoach] Board '{board.name}' (id={board.id}) snapshot: "
                f"active={counts['active_tasks']} overdue={counts['overdue']} "
                f"blocked={counts['blocked']} velocity={counts['velocity']}"
            )

            prompt = f"""You are an experienced project management coach helping a PM with their project.
You have direct, live access to this board's data — use it. Cite specific task
names, assignees, and counts from the snapshot below in your answer. Do NOT
give generic advice or tell the PM to "check their board" — you are looking
at the board for them right now.

## PM's Question:
{question}

## Live Board Snapshot:
{snapshot['text']}

## Your Role:
Use the snapshot to give a concrete, board-specific answer. When relevant:
- Name the actual people who are overloaded or have overdue work
- Name the actual tasks that are blocked, overdue, or due soon
- Quantify with the real numbers above (do NOT invent figures)
- Suggest specific reassignments or interventions tied to who/what is in the data

If the question genuinely cannot be answered from the snapshot, say so and
explain what additional information would unlock a better answer.

## Response Format:
Return your response as a JSON object with this structure:
{{
  "advice": "Your full coaching response in markdown format (3-4 paragraphs, practical, empathetic, evidence-based). MUST reference specific task names, people, or numbers from the snapshot.",
  "explainability": {{
    "confidence": 0.85,
    "data_sources_used": ["List the specific snapshot fields you drew upon — e.g. 'Overdue tasks', 'Workload per assignee', 'Milestones'"],
    "assumptions": ["Key assumptions underlying this advice"],
    "applicable_frameworks": ["PM frameworks / methodologies this advice draws from"]
  }}
}}

Keep the advice:
- **Specific**: Reference real names/tasks/numbers from the snapshot
- **Practical**: Give concrete steps they can take today
- **Empathetic**: Acknowledge the challenge
- **Concise**: 3-4 paragraphs maximum

Return ONLY the JSON object.
"""

            # Cache key varies with question + board id; the prompt itself contains
            # the live snapshot so a hash-of-prompt cache naturally invalidates
            # when data changes.
            context_id = f"board_{board.id}:user_{pm_user.id}"
            result = self._get_cached_or_generate(prompt, 'coaching_advice', context_id)

            if not result:
                return None

            # Try to parse as JSON
            import json
            try:
                text = result.strip()
                if text.startswith('```json'):
                    text = text.split('```json')[1].split('```')[0].strip()
                elif text.startswith('```'):
                    text = text.split('```')[1].split('```')[0].strip()

                parsed = json.loads(text)
                if isinstance(parsed, dict) and 'advice' in parsed:
                    return parsed
            except (json.JSONDecodeError, IndexError):
                pass

            # Fallback: return as plain advice with generated explainability
            data_sources = [f"Board: {board.name}"]
            if counts['active_tasks']:
                data_sources.append(f"{counts['active_tasks']} active tasks")
            if counts['overdue']:
                data_sources.append(f"{counts['overdue']} overdue")
            if counts['blocked']:
                data_sources.append(f"{counts['blocked']} blocked")
            if counts['velocity'] != 'N/A':
                data_sources.append(f"Velocity: {counts['velocity']}")
            if counts['team_size']:
                data_sources.append(f"Team size: {counts['team_size']}")

            return {
                'advice': result,
                'explainability': {
                    'confidence': 0.70,
                    'data_sources_used': data_sources,
                    'assumptions': ['AI response did not include structured explainability.'],
                    'applicable_frameworks': [],
                },
            }

        except Exception as e:
            logger.error(f"Failed to generate coaching advice: {e}")
            return f"Error generating advice: {str(e)}"
    
    def analyze_pm_performance(self, board, pm_user, time_period_days: int = 30) -> Optional[Dict]:
        """
        Analyze PM performance and provide insights (with caching)
        
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
- Team Size: {board.memberships.count()}

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
            
            # Get AI response with caching
            context_id = f"board_{board.id}:user_{pm_user.id}:days_{time_period_days}"
            response_text = self._get_cached_or_generate(prompt, 'pm_performance', context_id)
            
            if response_text:
                # Parse response
                import re
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                
                if json_match:
                    return json.loads(json_match.group())
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to analyze PM performance: {e}")
            return None
    
    def generate_learning_content(self, topic: str, pm_experience_level: str = 'intermediate') -> Optional[str]:
        """
        Generate learning content for PMs on specific topics (with caching)
        
        Educational content has a long cache TTL (6 hours) as it's stable.
        
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
            
            # Get AI response with caching (learning content uses long TTL)
            context_id = f"topic:{topic}:level:{pm_experience_level}"
            result = self._get_cached_or_generate(prompt, 'learning_content', context_id)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to generate learning content: {e}")
            return None
