"""
AI-Powered Requirements Analysis Service
Uses Gemini to analyze requirement quality, detect gaps, generate acceptance
criteria, assess impact, and suggest priorities.

Follows the same pattern as kanban/budget_ai.py — Gemini calls with
rule-based fallbacks, caching, and structured responses.
"""
import json
import logging
import re
from typing import Dict, List, Optional

from django.utils import timezone

logger = logging.getLogger(__name__)


class RequirementsAIAnalyzer:
    """AI-powered requirement analysis using Gemini."""

    def __init__(self, board):
        self.board = board

    # ── Public API ───────────────────────────────────────────────────

    def analyze_quality(self, requirement) -> Dict:
        """
        Score a requirement on clarity, completeness, testability,
        unambiguity, and feasibility.  Returns quality_score (0-100),
        dimension_scores, improvement_suggestions, and risk_flags.
        """
        prompt = self._build_quality_prompt(requirement)
        ai_response = self._call_gemini(
            prompt,
            cache_operation='requirement_quality',
        )
        if ai_response:
            parsed = self._parse_quality_response(ai_response, requirement)
            if parsed:
                return parsed

        # Rule-based fallback
        return self._fallback_quality_analysis(requirement)

    def detect_gaps(self) -> Dict:
        """
        Analyze all requirements against board objectives and tasks.
        Returns gap_report with missing_areas, underspecified_objectives,
        orphaned_tasks, and recommended_requirements.
        """
        from .models import Requirement, RequirementCategory
        from kanban.models import OrganizationGoal, Task

        reqs = list(Requirement.objects.filter(board=self.board).prefetch_related(
            'linked_tasks', 'linked_goals',
        ))
        # Scope goals to the board's WORKSPACE (the tenant boundary), not its
        # legacy organization — otherwise gap analysis mixes goals across
        # unrelated workspaces in the same org.
        workspace = getattr(self.board, 'workspace', None)
        goals = list(OrganizationGoal.objects.filter(workspace=workspace)) if workspace else []
        tasks = list(Task.objects.filter(column__board=self.board, item_type='task').select_related('column'))

        if not reqs and not tasks:
            return {
                'gaps': [],
                'orphaned_tasks': [],
                'uncovered_goals': [],
                'summary': 'No requirements or tasks to analyze.',
                'severity': 'info',
            }

        prompt = self._build_gap_prompt(reqs, goals, tasks)
        ai_response = self._call_gemini(
            prompt,
            cache_operation='requirement_gaps',
        )
        if ai_response:
            parsed = self._parse_gap_response(ai_response)
            if parsed:
                # Enrich with concrete data
                parsed['orphaned_tasks'] = self._find_orphaned_tasks(reqs, tasks)
                parsed['uncovered_goals'] = self._find_uncovered_goals(reqs, goals)
                return parsed

        # Rule-based fallback
        return self._fallback_gap_analysis(reqs, goals, tasks)

    def generate_acceptance_criteria(self, requirement) -> Dict:
        """
        Auto-generate acceptance criteria in Given/When/Then format
        from a requirement's title and description.
        """
        data = {
            'title': requirement.title,
            'description': requirement.description or '',
            'type': requirement.get_type_display(),
            'priority': requirement.get_priority_display(),
            'category': requirement.category.name if requirement.category else '',
        }
        prompt = self._build_criteria_prompt_from_data(data)
        ai_response = self._call_gemini(
            prompt,
            cache_operation='requirement_criteria',
        )
        if ai_response:
            parsed = self._parse_criteria_response(ai_response)
            if parsed:
                return parsed

        return self._fallback_criteria(requirement)

    def generate_acceptance_criteria_from_data(self, data: Dict) -> Dict:
        """
        Generate acceptance criteria from raw form data (no saved requirement needed).
        data keys: title, description, type, priority, category, objectives (optional list of strings)
        """
        prompt = self._build_criteria_prompt_from_data(data)
        ai_response = self._call_gemini(
            prompt,
            cache_operation='requirement_criteria',
        )
        if ai_response:
            parsed = self._parse_criteria_response(ai_response)
            if parsed:
                return parsed

        return self._fallback_criteria_from_data(data)

    def analyze_impact(self, requirement) -> Dict:
        """
        Analyze downstream impact of a requirement: linked tasks,
        dependent requirements, affected objectives.
        """
        linked_tasks = list(requirement.linked_tasks.select_related('column', 'assigned_to').all())
        children = list(requirement.children.all())
        related = list(requirement.related_requirements.all())
        linked_goals = list(requirement.linked_goals.all())

        prompt = self._build_impact_prompt(requirement, linked_tasks, children, related, linked_goals)
        ai_response = self._call_gemini(
            prompt,
            cache_operation='requirement_impact',
        )
        if ai_response:
            parsed = self._parse_impact_response(ai_response)
            if parsed:
                parsed['linked_tasks_count'] = len(linked_tasks)
                parsed['children_count'] = len(children)
                parsed['related_count'] = len(related)
                parsed['goals_count'] = len(linked_goals)
                return parsed

        return self._fallback_impact_analysis(requirement, linked_tasks, children, related, linked_goals)

    def suggest_priority(self, requirement) -> Dict:
        """
        AI-powered priority recommendation based on linked objectives,
        task dependencies, and board context.
        """
        prompt = self._build_priority_prompt(requirement)
        ai_response = self._call_gemini(
            prompt,
            cache_operation='requirement_priority',
        )
        if ai_response:
            parsed = self._parse_priority_response(ai_response)
            if parsed:
                return parsed

        return self._fallback_priority_suggestion(requirement)

    # ── Prompt Builders ──────────────────────────────────────────────

    def _build_quality_prompt(self, req) -> str:
        return f"""Analyze this software requirement for quality and return a JSON response.

REQUIREMENT:
- Identifier: {req.identifier}
- Title: {req.title}
- Description: {req.description or '(none)'}
- Type: {req.get_type_display()}
- Priority: {req.get_priority_display()}
- Acceptance Criteria: {req.acceptance_criteria or '(none)'}

Score each dimension 0-100:
1. Clarity — Is the requirement clearly written and easy to understand?
2. Completeness — Does it contain enough detail to implement?
3. Testability — Can acceptance criteria be derived or verified?
4. Unambiguity — Is there only one interpretation?
5. Feasibility — Is it technically and practically achievable?

Return ONLY valid JSON (no markdown fences):
{{
  "quality_score": <0-100 overall>,
  "dimensions": {{
    "clarity": <0-100>,
    "completeness": <0-100>,
    "testability": <0-100>,
    "unambiguity": <0-100>,
    "feasibility": <0-100>
  }},
  "improvement_suggestions": ["suggestion 1", "suggestion 2", ...],
  "risk_flags": ["flag 1", ...]
}}"""

    def _build_gap_prompt(self, reqs, goals, tasks) -> str:
        req_summaries = '\n'.join(
            f"- {r.identifier}: {r.title} (type={r.get_type_display()}, priority={r.get_priority_display()}, tasks={r.linked_tasks.count()})"
            for r in reqs
        ) or '(no requirements defined)'

        goal_summaries = '\n'.join(
            f"- {g.name}: {g.description[:100] if g.description else '(no description)'}"
            for g in goals
        ) or '(no goals defined)'

        task_summaries = '\n'.join(
            f"- {t.title} (column={t.column.name})"
            for t in tasks[:30]
        ) or '(no tasks)'

        return f"""Analyze this board's requirements for gaps and missing coverage.

GOALS:
{goal_summaries}

REQUIREMENTS ({len(reqs)} total):
{req_summaries}

TASKS ({len(tasks)} total, showing first 30):
{task_summaries}

Identify:
1. Missing requirement areas — goals or task areas with no requirements
2. Imbalanced coverage — areas with too many or too few requirements
3. Recommended new requirements to fill gaps

Return ONLY valid JSON (no markdown fences):
{{
  "gaps": [
    {{"area": "description of gap", "severity": "high|medium|low", "recommendation": "suggested requirement"}}
  ],
  "summary": "overall gap analysis narrative",
  "severity": "critical|high|medium|low|info",
  "coverage_assessment": "narrative of how well requirements cover goals and tasks"
}}"""

    def _build_criteria_prompt(self, req) -> str:
        data = {
            'title': req.title,
            'description': req.description or '',
            'type': req.get_type_display(),
            'priority': req.get_priority_display(),
            'category': req.category.name if req.category else '',
        }
        return self._build_criteria_prompt_from_data(data)

    def _build_criteria_prompt_from_data(self, data: Dict) -> str:
        title = data.get('title', '')
        description = data.get('description', '') or '(none)'
        req_type = data.get('type', 'Functional')
        priority = data.get('priority', 'Medium')
        category = data.get('category', '') or 'General'
        objectives = data.get('linked_goals', data.get('objectives', []))
        obj_str = (', '.join(objectives)) if objectives else 'none'

        return f"""You are a requirements analyst. Based on the following requirement details, generate 3-5 clear, testable acceptance criteria in Given/When/Then format.

Requirement Title: {title}
Description: {description}
Type: {req_type}
Priority: {priority}
Category: {category}
Linked Goals: {obj_str}

Rules:
- Each criterion must be specific and independently testable
- Use Given/When/Then format
- No vague language like "should work well" or "must be fast"
- If type is Non-Functional, include measurable thresholds (e.g. response time < 200ms, uptime > 99.9%)
- Cover the happy path, at least one error/edge case, and any security or permission concern if relevant
- Return only the criteria, no preamble

Return ONLY valid JSON (no markdown fences):
{{
  "criteria": [
    {{
      "scenario": "brief scenario name",
      "given": "the precondition",
      "when": "the action",
      "then": "the expected result"
    }}
  ],
  "notes": "any additional notes about edge cases or considerations"
}}"""

    def _build_impact_prompt(self, req, linked_tasks, children, related, linked_goals) -> str:
        tasks_info = ', '.join(t.title for t in linked_tasks[:10]) or 'none'
        children_info = ', '.join(f"{c.identifier}: {c.title}" for c in children[:10]) or 'none'
        related_info = ', '.join(f"{r.identifier}: {r.title}" for r in related[:10]) or 'none'
        goals_info = ', '.join(g.name for g in linked_goals[:10]) or 'none'

        return f"""Analyze the downstream impact of changes to this requirement.

REQUIREMENT:
- Identifier: {req.identifier}
- Title: {req.title}
- Status: {req.get_status_display()}
- Priority: {req.get_priority_display()}
- Linked Tasks: {tasks_info}
- Child Requirements: {children_info}
- Related Requirements: {related_info}
- Linked Goals: {goals_info}

Assess:
1. What would happen if this requirement's status changed (e.g., approved → rejected)?
2. What is the cascading impact on linked tasks and child requirements?
3. How critical is this requirement to the goals it supports?

Return ONLY valid JSON (no markdown fences):
{{
  "risk_level": "critical|high|medium|low",
  "impact_summary": "narrative of the downstream impact",
  "affected_areas": ["area 1", "area 2", ...],
  "change_risks": [
    {{"scenario": "status change description", "impact": "what would happen", "severity": "high|medium|low"}}
  ],
  "recommendations": ["recommendation 1", ...]
}}"""

    def _build_priority_prompt(self, req) -> str:
        linked_goals = list(req.linked_goals.all())
        goals_info = ', '.join(g.name for g in linked_goals) or 'none'
        task_count = req.linked_tasks.count()
        children_count = req.children.count()

        return f"""Recommend a priority level for this software requirement.

REQUIREMENT:
- Title: {req.title}
- Description: {req.description or '(none)'}
- Type: {req.get_type_display()}
- Current Priority: {req.get_priority_display()}
- Linked Tasks: {task_count}
- Child Requirements: {children_count}
- Linked Goals: {goals_info}

Consider: number of dependent items, goal importance, type of requirement, and implementation scope.

Return ONLY valid JSON (no markdown fences):
{{
  "recommended_priority": "critical|high|medium|low",
  "confidence": <0-100>,
  "reasoning": "explanation of why this priority is recommended",
  "factors": ["factor 1", "factor 2", ...]
}}"""

    # ── Gemini API ───────────────────────────────────────────────────

    def _get_ai_cache(self):
        try:
            from kanban_board.ai_cache import ai_cache_manager
            return ai_cache_manager
        except ImportError:
            return None

    def _call_gemini(self, prompt: str, cache_operation: str = 'requirement_analysis') -> Optional[str]:
        context_id = f"board_{self.board.id}" if self.board else None

        ai_cache = self._get_ai_cache()
        if ai_cache:
            cached = ai_cache.get(prompt, cache_operation, context_id)
            if cached:
                logger.debug("Requirements AI cache HIT for %s", cache_operation)
                return cached

        try:
            from ai_assistant.utils.ai_router import AIRouter
            from django.conf import settings

            if not getattr(settings, 'GEMINI_API_KEY', None) and not getattr(settings, 'OPENAI_API_KEY', None) and not getattr(settings, 'ANTHROPIC_API_KEY', None):
                logger.error("No AI API key configured")
                return None

            token_limits = {
                'requirement_quality': 2048,
                'requirement_gaps': 4096,
                'requirement_criteria': 2048,
                'requirement_impact': 2048,
                'requirement_priority': 1024,
            }

            router = AIRouter()
            result = router.complete(
                prompt=prompt,
                user=None,
                complexity='complex',
            )['text']

            if result:
                if ai_cache and result:
                    ai_cache.set(prompt, result, cache_operation, context_id)
                return result
            return None
        except Exception as e:
            logger.error("Requirements AI call failed: %s", e)
            return None

    # ── Response Parsers ─────────────────────────────────────────────

    def _extract_json(self, text: str) -> Optional[Dict]:
        """Extract JSON from AI response, handling markdown fences."""
        if not text:
            return None
        text = text.strip()
        # Remove markdown code fences
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            # Try to find JSON object in the text
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                try:
                    return json.loads(match.group())
                except (json.JSONDecodeError, ValueError):
                    pass
        return None

    def _parse_quality_response(self, response: str, requirement) -> Optional[Dict]:
        data = self._extract_json(response)
        if not data:
            return None
        score = data.get('quality_score', 0)
        if not isinstance(score, (int, float)) or score < 0 or score > 100:
            return None
        return {
            'quality_score': int(score),
            'dimensions': data.get('dimensions', {}),
            'improvement_suggestions': data.get('improvement_suggestions', []),
            'risk_flags': data.get('risk_flags', []),
            'requirement_id': requirement.identifier,
            'analyzed_at': timezone.now().isoformat(),
        }

    def _parse_gap_response(self, response: str) -> Optional[Dict]:
        data = self._extract_json(response)
        if not data:
            return None
        return {
            'gaps': data.get('gaps', []),
            'summary': data.get('summary', ''),
            'severity': data.get('severity', 'info'),
            'coverage_assessment': data.get('coverage_assessment', ''),
            'orphaned_tasks': [],
            'uncovered_goals': [],
            'analyzed_at': timezone.now().isoformat(),
        }

    def _parse_criteria_response(self, response: str) -> Optional[Dict]:
        data = self._extract_json(response)
        if not data:
            return None
        criteria = data.get('criteria', [])
        if not criteria:
            return None
        return {
            'criteria': criteria,
            'notes': data.get('notes', ''),
            'generated_at': timezone.now().isoformat(),
        }

    def _parse_impact_response(self, response: str) -> Optional[Dict]:
        data = self._extract_json(response)
        if not data:
            return None
        return {
            'risk_level': data.get('risk_level', 'medium'),
            'impact_summary': data.get('impact_summary', ''),
            'affected_areas': data.get('affected_areas', []),
            'change_risks': data.get('change_risks', []),
            'recommendations': data.get('recommendations', []),
            'analyzed_at': timezone.now().isoformat(),
        }

    def _parse_priority_response(self, response: str) -> Optional[Dict]:
        data = self._extract_json(response)
        if not data:
            return None
        valid_priorities = ('critical', 'high', 'medium', 'low')
        rec = data.get('recommended_priority', '').lower()
        if rec not in valid_priorities:
            return None
        return {
            'recommended_priority': rec,
            'confidence': min(100, max(0, int(data.get('confidence', 50)))),
            'reasoning': data.get('reasoning', ''),
            'factors': data.get('factors', []),
        }

    # ── Helper: concrete data enrichment ─────────────────────────────

    def _find_orphaned_tasks(self, reqs, tasks) -> List[Dict]:
        linked_task_ids = set()
        for r in reqs:
            linked_task_ids.update(r.linked_tasks.values_list('id', flat=True))
        orphaned = [t for t in tasks if t.id not in linked_task_ids]
        return [
            {'id': t.id, 'title': t.title, 'column': t.column.name if t.column else 'Unknown'}
            for t in orphaned[:20]
        ]

    def _find_uncovered_goals(self, reqs, goals) -> List[Dict]:
        covered_goal_ids = set()
        for r in reqs:
            covered_goal_ids.update(r.linked_goals.values_list('id', flat=True))
        uncovered = [g for g in goals if g.id not in covered_goal_ids]
        return [
            {'id': g.id, 'name': g.name}
            for g in uncovered
        ]

    # ── Fallback Analyzers (rule-based) ──────────────────────────────

    def _fallback_quality_analysis(self, req) -> Dict:
        score = 50
        suggestions = []
        risk_flags = []
        dims = {'clarity': 50, 'completeness': 50, 'testability': 50, 'unambiguity': 50, 'feasibility': 50}

        title_len = len(req.title) if req.title else 0
        desc_len = len(req.description) if req.description else 0

        # Clarity
        if title_len > 10:
            dims['clarity'] = min(80, 50 + title_len // 3)
        if title_len < 5:
            dims['clarity'] = 30
            suggestions.append('Requirement title is very short — add more descriptive detail.')

        # Completeness
        if desc_len > 50:
            dims['completeness'] = min(85, 50 + desc_len // 10)
        elif desc_len == 0:
            dims['completeness'] = 20
            suggestions.append('No description provided — add details about what this requirement entails.')

        # Testability
        if req.acceptance_criteria:
            dims['testability'] = 75
        else:
            dims['testability'] = 25
            suggestions.append('No acceptance criteria defined — add testable criteria to verify this requirement.')

        # Unambiguity
        ambiguous_words = ['etc', 'should', 'might', 'could', 'maybe', 'possibly', 'some']
        text = f"{req.title} {req.description or ''}".lower()
        ambig_count = sum(1 for w in ambiguous_words if w in text)
        if ambig_count > 2:
            dims['unambiguity'] = 30
            risk_flags.append(f'Contains {ambig_count} ambiguous terms (e.g., should, might, etc.)')
        elif ambig_count == 0:
            dims['unambiguity'] = 80

        # Feasibility (heuristic: higher priority with no tasks = less feasible)
        if req.priority in ('critical', 'high') and req.linked_tasks.count() == 0:
            dims['feasibility'] = 40
            risk_flags.append('High/critical priority requirement with no linked implementation tasks.')
        else:
            dims['feasibility'] = 65

        score = sum(dims.values()) // len(dims)

        return {
            'quality_score': score,
            'dimensions': dims,
            'improvement_suggestions': suggestions,
            'risk_flags': risk_flags,
            'requirement_id': req.identifier,
            'analyzed_at': timezone.now().isoformat(),
        }

    def _fallback_gap_analysis(self, reqs, goals, tasks) -> Dict:
        gaps = []
        orphaned = self._find_orphaned_tasks(reqs, tasks)
        uncovered_goals = self._find_uncovered_goals(reqs, goals)

        if uncovered_goals:
            for g in uncovered_goals:
                gaps.append({
                    'area': f"Goal \"{g['name']}\" has no linked requirements",
                    'severity': 'high',
                    'recommendation': f"Create requirements that address goal: {g['name']}",
                })

        if orphaned:
            gaps.append({
                'area': f"{len(orphaned)} tasks exist without linked requirements",
                'severity': 'medium',
                'recommendation': 'Link existing tasks to requirements for better traceability.',
            })

        # Check for type balance
        from .models import Requirement
        type_counts = {}
        for r in reqs:
            t = r.get_type_display()
            type_counts[t] = type_counts.get(t, 0) + 1

        if reqs and 'Non-functional' not in type_counts:
            gaps.append({
                'area': 'No non-functional requirements defined',
                'severity': 'medium',
                'recommendation': 'Consider adding non-functional requirements (performance, security, usability).',
            })

        severity = 'info'
        if any(g['severity'] == 'high' for g in gaps):
            severity = 'high'
        elif any(g['severity'] == 'medium' for g in gaps):
            severity = 'medium'

        total_issues = len(gaps) + len(orphaned) + len(uncovered_goals)
        summary = f"Found {total_issues} gap(s): {len(uncovered_goals)} uncovered goal(s), {len(orphaned)} orphaned task(s), {len(gaps)} structural gap(s)."

        return {
            'gaps': gaps,
            'orphaned_tasks': orphaned,
            'uncovered_goals': uncovered_goals,
            'summary': summary,
            'severity': severity,
            'coverage_assessment': f"{len(reqs)} requirements covering {len(goals)} goals and linked to tasks from {len(tasks)} total.",
            'analyzed_at': timezone.now().isoformat(),
        }

    def _fallback_criteria(self, req) -> Dict:
        return self._fallback_criteria_from_data({
            'title': req.title,
            'description': req.description or '',
        })

    def _fallback_criteria_from_data(self, data: Dict) -> Dict:
        title = data.get('title') or 'the feature'
        criteria = [
            {
                'scenario': f'{title} — basic functionality',
                'given': f'the system has the {title.lower()} feature configured',
                'when': 'a user performs the primary action',
                'then': 'the system responds with the expected result',
            },
            {
                'scenario': f'{title} — error handling',
                'given': f'the {title.lower()} feature is active',
                'when': 'invalid input is provided',
                'then': 'the system displays an appropriate error message',
            },
            {
                'scenario': f'{title} — edge case',
                'given': 'the system is in a boundary condition',
                'when': f'the {title.lower()} action is triggered',
                'then': 'the system handles the edge case gracefully',
            },
        ]
        return {
            'criteria': criteria,
            'notes': 'These are auto-generated placeholder criteria. Edit them to match your specific requirement.',
            'generated_at': timezone.now().isoformat(),
        }

    def _fallback_impact_analysis(self, req, linked_tasks, children, related, linked_goals) -> Dict:
        risk_level = 'low'
        areas = []
        change_risks = []
        recommendations = []

        if linked_tasks:
            areas.append(f"{len(linked_tasks)} linked task(s)")
            risk_level = 'medium'
        if children:
            areas.append(f"{len(children)} child requirement(s)")
            risk_level = 'high'
        if linked_goals:
            areas.append(f"{len(linked_goals)} goal(s)")

        if req.priority in ('critical', 'high'):
            risk_level = 'high' if risk_level != 'high' else 'critical'
            change_risks.append({
                'scenario': 'Rejecting this high-priority requirement',
                'impact': f"Would affect {len(linked_tasks)} task(s) and {len(children)} child requirement(s)",
                'severity': 'high',
            })

        if linked_tasks:
            recommendations.append('Review linked tasks before changing requirement status.')
        if children:
            recommendations.append('Update child requirements if parent scope changes.')

        return {
            'risk_level': risk_level,
            'impact_summary': f"This requirement affects {', '.join(areas) or 'no downstream items'}.",
            'affected_areas': areas,
            'change_risks': change_risks,
            'recommendations': recommendations,
            'linked_tasks_count': len(linked_tasks),
            'children_count': len(children),
            'related_count': len(related),
            'goals_count': len(linked_goals),
            'analyzed_at': timezone.now().isoformat(),
        }

    def _fallback_priority_suggestion(self, req) -> Dict:
        factors = []
        task_count = req.linked_tasks.count()
        children_count = req.children.count()

        score = 50
        if obj_count := req.linked_goals.count():
            score += 15
            factors.append(f"Linked to {obj_count} goal(s)")
        if task_count > 3:
            score += 10
            factors.append(f"Has {task_count} linked tasks")
        if children_count > 0:
            score += 10
            factors.append(f"Has {children_count} child requirements")
        if req.get_type_display() == 'Functional':
            score += 5
            factors.append('Functional requirement type')

        if score >= 80:
            rec = 'critical'
        elif score >= 65:
            rec = 'high'
        elif score >= 45:
            rec = 'medium'
        else:
            rec = 'low'

        return {
            'recommended_priority': rec,
            'confidence': min(100, score),
            'reasoning': f"Based on {len(factors)} factor(s): {'; '.join(factors) or 'default assessment'}.",
            'factors': factors,
        }
