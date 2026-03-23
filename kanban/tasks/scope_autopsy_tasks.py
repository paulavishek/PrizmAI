"""
Celery task for generating Scope Creep Autopsy reports.

Collects scope history, estimates cost impact, calls Gemini for forensic
analysis, and saves structured results.
"""
import json
import logging
import time

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='kanban.generate_scope_autopsy', max_retries=2)
def generate_scope_autopsy(self, report_id):
    """
    Asynchronously generate a full Scope Creep Autopsy report.

    Expects a pre-created ScopeAutopsyReport (status='generating').
    1. Collects baseline + scope history
    2. Estimates cost/delay per event
    3. Sends to Gemini for pattern analysis
    4. Saves structured results and timeline events
    5. Creates a MemoryNode in the Knowledge Graph
    """
    from kanban.models import Board, Task
    from kanban.scope_autopsy_models import ScopeAutopsyReport, ScopeTimelineEvent
    from kanban.utils.scope_autopsy import (
        calculate_baseline,
        collect_scope_history,
        estimate_cost_impact,
    )

    start_time = time.time()

    try:
        report = ScopeAutopsyReport.objects.select_related('board', 'created_by').get(pk=report_id)
    except ScopeAutopsyReport.DoesNotExist:
        logger.error("ScopeAutopsyReport %s not found", report_id)
        return {'status': 'error', 'message': 'Report not found'}

    board = report.board
    user = report.created_by

    try:
        # 2. Collect baseline
        baseline = calculate_baseline(board)
        report.baseline_task_count = baseline['task_count']
        report.baseline_date = baseline['baseline_date']

        # 3. Collect events
        events = collect_scope_history(board)
        events = estimate_cost_impact(events, board)

        # 4. Compute final numbers
        final_task_count = Task.objects.filter(column__board=board, item_type='task').count()
        report.final_task_count = final_task_count

        if baseline['task_count'] > 0:
            growth_pct = round(
                ((final_task_count - baseline['task_count']) / baseline['task_count']) * 100, 1
            )
        else:
            growth_pct = 0.0
        report.total_scope_growth_percentage = growth_pct

        total_delay = sum(e.get('estimated_delay_days', 0) for e in events)
        total_budget = sum(e.get('estimated_budget_impact', 0) for e in events)
        report.total_delay_days = total_delay
        report.total_budget_impact = total_budget

        # 5. Build board snapshot for AI prompt
        days_elapsed = (timezone.now() - board.created_at).days

        # Get project name context
        project_context = board.name
        if board.strategy:
            project_context = f"{board.name} (Strategy: {board.strategy.name})"

        board_snapshot = {
            'board_name': board.name,
            'project_context': project_context,
            'baseline_task_count': baseline['task_count'],
            'baseline_date': str(baseline['baseline_date']),
            'final_task_count': final_task_count,
            'growth_percentage': growth_pct,
            'days_elapsed': days_elapsed,
            'total_events': len(events),
        }
        report.board_snapshot = board_snapshot

        # 6. Query Knowledge Graph for similar past projects
        past_scope_notes = _get_past_scope_patterns(board, user)

        # 7. Call Gemini
        ai_result = _call_gemini_for_autopsy(
            board_snapshot, events, past_scope_notes, project_context
        )

        # 8. Save AI results
        report.ai_summary = ai_result.get('ai_summary', '')
        report.pattern_analysis = ai_result.get('pattern_analysis', '')
        report.recommendations = ai_result.get('recommendations', [])
        report.timeline_json = [
            {
                'date': str(e['date']),
                'title': e['title'],
                'description': e['description'],
                'source_type': e['source_type'],
                'tasks_added': e['tasks_added'],
                'net_task_change': e['net_task_change'],
                'is_major_event': e['is_major_event'],
                'estimated_delay_days': e.get('estimated_delay_days', 0),
                'estimated_budget_impact': e.get('estimated_budget_impact', 0),
                'added_by_name': e.get('added_by_name', ''),
            }
            for e in events
        ]
        report.status = 'complete'
        report.save()

        # 9. Create ScopeTimelineEvent records
        # Clamp cumulative to actual task count to avoid contradictions
        actual_task_count = report.final_task_count
        cumulative = baseline['task_count']
        for e in events:
            cumulative += e['net_task_change']
            if cumulative > actual_task_count:
                cumulative = actual_task_count
            ScopeTimelineEvent.objects.create(
                report=report,
                event_date=e['date'],
                title=e['title'],
                description=e['description'],
                source_type=e['source_type'],
                source_object_type=e.get('source_object_type', ''),
                source_object_id=e.get('source_object_id'),
                tasks_added=e['tasks_added'],
                tasks_removed=e.get('tasks_removed', 0),
                net_task_change=e['net_task_change'],
                added_by_id=e.get('added_by_id'),
                estimated_delay_days=e.get('estimated_delay_days', 0),
                estimated_budget_impact=e.get('estimated_budget_impact', 0),
                cumulative_task_count=cumulative,
                is_major_event=e['is_major_event'],
            )

        # 10. Create MemoryNode in Knowledge Graph
        _create_autopsy_memory_node(report, ai_result, user)

        # 11. Track AI usage
        try:
            from api.ai_usage_utils import track_ai_request
            response_time_ms = int((time.time() - start_time) * 1000)
            track_ai_request(
                user=user,
                feature='scope_autopsy',
                request_type='scope_autopsy_generation',
                board_id=board.id,
                success=True,
                response_time_ms=response_time_ms,
            )
        except Exception:
            logger.warning("Failed to track AI usage for scope autopsy", exc_info=True)

        # 12. Audit log
        try:
            from kanban.audit_utils import log_audit
            log_audit(
                'scope_autopsy.generated',
                user=user,
                object_type='ScopeAutopsyReport',
                object_id=report.id,
                object_repr=str(report),
                board_id=board.id,
                changes={
                    'baseline_tasks': {'old': None, 'new': baseline['task_count']},
                    'final_tasks': {'old': None, 'new': final_task_count},
                    'growth_pct': {'old': None, 'new': growth_pct},
                },
            )
        except Exception:
            logger.warning("Audit log for scope_autopsy.generated failed", exc_info=True)

        logger.info(
            "Scope autopsy completed for board %s: %s%% growth, %d events",
            board.pk, growth_pct, len(events),
        )
        return {'status': 'complete', 'report_id': report.id}

    except Exception as exc:
        report.status = 'failed'
        report.ai_summary = f"Analysis failed: {str(exc)[:500]}"
        report.save(update_fields=['status', 'ai_summary'])
        logger.error("Scope autopsy failed for report %s (board %s): %s", report_id, board.id, exc, exc_info=True)

        try:
            from api.ai_usage_utils import track_ai_request
            track_ai_request(
                user=user,
                feature='scope_autopsy',
                request_type='scope_autopsy_generation',
                board_id=board.id,
                success=False,
                error_message=str(exc)[:500],
            )
        except Exception:
            pass

        raise self.retry(exc=exc, countdown=30)


def _get_past_scope_patterns(board, user):
    """
    Query Knowledge Graph for scope_change MemoryNodes from other boards.
    Returns a summary string for the AI prompt.
    """
    try:
        from knowledge_graph.models import MemoryNode

        # Get boards accessible to user
        if user:
            user_board_ids = set(
                user.member_boards.values_list('id', flat=True)
            ) | set(
                user.created_boards.values_list('id', flat=True)
            )
        else:
            user_board_ids = set()

        # Exclude current board, get scope_change nodes from other projects
        nodes = MemoryNode.objects.filter(
            node_type='scope_change',
            board_id__in=user_board_ids,
        ).exclude(
            board_id=board.pk,
        ).order_by('-importance_score', '-created_at')[:10]

        if not nodes.exists():
            return "No previous scope change records found in organizational memory."

        lines = []
        for node in nodes:
            lines.append(
                f"- [{node.board.name if node.board else 'Unknown'}] {node.title}: "
                f"{node.content[:150]}"
            )

        return (
            f"SIMILAR PAST PROJECTS ({nodes.count()} scope events found):\n"
            + "\n".join(lines)
        )
    except Exception:
        logger.warning("Failed to query Knowledge Graph for past scope patterns", exc_info=True)
        return "Past project data unavailable."


def _call_gemini_for_autopsy(board_snapshot, events, past_scope_notes, project_context):
    """
    Call Gemini for forensic scope analysis.
    Returns parsed JSON dict with ai_summary, pattern_analysis, recommendations, etc.
    """
    import google.generativeai as genai

    genai.configure(api_key=settings.GEMINI_API_KEY)

    system_prompt = (
        "You are a forensic project analyst specializing in scope creep analysis. "
        "You will be given a project's complete history of scope changes. "
        "Your job is to:\n"
        "1. Identify patterns in how scope grew\n"
        "2. Assess which events were avoidable vs unavoidable\n"
        "3. Generate specific, actionable recommendations to prevent similar "
        "scope creep in future projects\n"
        "4. Write a clear executive summary of what happened\n\n"
        "Be specific and data-driven. Use the actual numbers provided. "
        "Do not be diplomatic — if scope was mismanaged, say so clearly.\n"
        "Return ONLY valid JSON. No markdown, no text outside JSON."
    )

    # Build event timeline text
    event_lines = []
    for e in events:
        added_by = e.get('added_by_name', 'Unknown') or 'Unknown'
        event_lines.append(
            f"DATE: {e['date']} | SOURCE: {e['source_type']} | "
            f"CHANGE: +{e['tasks_added']}/-{e.get('tasks_removed', 0)} tasks\n"
            f"   Added by: {added_by} | Description: {e['description'][:200]}\n"
            f"   Running total after event: {e.get('cumulative_task_count', '?')} tasks"
        )

    # Compute cumulative counts for prompt
    cumulative = board_snapshot['baseline_task_count']
    for e in events:
        cumulative += e['net_task_change']
        e['cumulative_task_count'] = cumulative

    # Rebuild event lines with cumulative
    event_lines = []
    for e in events:
        added_by = e.get('added_by_name', 'Unknown') or 'Unknown'
        event_lines.append(
            f"DATE: {e['date']} | SOURCE: {e['source_type']} | "
            f"CHANGE: +{e['tasks_added']}/-{e.get('tasks_removed', 0)} tasks\n"
            f"   Added by: {added_by} | Description: {e['description'][:200]}\n"
            f"   Running total after event: {e['cumulative_task_count']} tasks"
        )

    user_prompt = (
        f"Analyze this project's scope creep history.\n\n"
        f"PROJECT: {project_context}\n"
        f"Start date: {board_snapshot.get('baseline_date', 'Unknown')}\n"
        f"Baseline scope: {board_snapshot['baseline_task_count']} tasks at project start\n"
        f"Current scope: {board_snapshot['final_task_count']} tasks\n"
        f"Total growth: {board_snapshot['growth_percentage']}%\n"
        f"Timeline: {board_snapshot['days_elapsed']} days elapsed\n\n"
        f"SCOPE CHANGE EVENTS (chronological):\n"
        + ("\n\n".join(event_lines) if event_lines else "No specific events detected.")
        + f"\n\n{past_scope_notes}\n\n"
        "Return JSON:\n"
        "{\n"
        '  "ai_summary": "3-4 sentence executive summary of what happened to scope on this project",\n'
        '  "pattern_analysis": "2-3 sentences identifying recurring patterns, especially if similar to past projects",\n'
        '  "avoidable_events_count": N,\n'
        '  "unavoidable_events_count": N,\n'
        '  "primary_scope_driver": "The single biggest cause of scope growth on this project",\n'
        '  "recommendations": [\n'
        "    {\n"
        '      "title": "Short recommendation title",\n'
        '      "description": "One specific action to prevent this type of scope creep",\n'
        '      "applies_to": "planning" | "execution" | "stakeholder_management" | "technical"\n'
        "    }\n"
        "  ],\n"
        '  "confidence_note": "One sentence on data quality and what assumptions were made"\n'
        "}"
    )

    model = genai.GenerativeModel(
        'gemini-2.5-flash',
        system_instruction=system_prompt,
    )

    generation_config = {
        'temperature': 0.3,
        'top_p': 0.8,
        'top_k': 40,
        'max_output_tokens': 4096,
        'response_mime_type': 'application/json',
    }

    response = model.generate_content(user_prompt, generation_config=generation_config)
    raw = response.text.strip()

    # Strip markdown fences if accidentally returned
    if '```json' in raw:
        raw = raw.split('```json')[1].split('```')[0].strip()
    elif raw.startswith('```'):
        raw = raw.split('\n', 1)[1] if '\n' in raw else raw[3:]
        if raw.endswith('```'):
            raw = raw[:-3].strip()

    # Fix unescaped control characters inside JSON string values
    def _fix_unescaped(text):
        result = []
        in_string = False
        escape_next = False
        for ch in text:
            if escape_next:
                result.append(ch)
                escape_next = False
            elif ch == '\\' and in_string:
                result.append(ch)
                escape_next = True
            elif ch == '"':
                in_string = not in_string
                result.append(ch)
            elif in_string and ch == '\n':
                result.append('\\n')
            elif in_string and ch == '\r':
                result.append('\\r')
            elif in_string and ch == '\t':
                result.append('\\t')
            else:
                result.append(ch)
        return ''.join(result)

    # Fix Python-style booleans/None and trailing commas
    import re
    raw = _fix_unescaped(raw)
    raw = raw.replace('True', 'true').replace('False', 'false').replace('None', 'null')
    raw = re.sub(r',\s*([}\]])', r'\1', raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Attempt repair: close any unclosed strings/brackets
        text = raw.rstrip()
        in_str = False
        esc = False
        stack = []
        for ch in text:
            if esc:
                esc = False
                continue
            if ch == '\\' and in_str:
                esc = True
                continue
            if ch == '"':
                in_str = not in_str
            elif not in_str:
                if ch in ('{', '['):
                    stack.append(ch)
                elif ch == '}' and stack and stack[-1] == '{':
                    stack.pop()
                elif ch == ']' and stack and stack[-1] == '[':
                    stack.pop()
        suffix = ''
        if in_str:
            suffix += '"'
        for opener in reversed(stack):
            suffix += ']' if opener == '[' else '}'
        repaired = text + suffix
        # Strip control characters and retry
        repaired = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', repaired)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            logger.error("Failed to parse Gemini JSON even after repair. Raw (500 chars): %s", raw[:500])
            # Return a minimal valid response so the report completes
            return {
                'ai_summary': 'AI analysis completed but response could not be fully parsed. The scope data below is still accurate.',
                'pattern_analysis': '',
                'recommendations': [],
                'primary_scope_driver': 'Unknown (parsing error)',
                'confidence_note': 'AI response parsing failed; numeric data is accurate but text analysis may be incomplete.',
            }


def _create_autopsy_memory_node(report, ai_result, user):
    """
    Create a MemoryNode in the Knowledge Graph after a successful autopsy.
    Also check for cross-project patterns and update pattern_analysis.
    """
    try:
        from knowledge_graph.models import MemoryNode

        board = report.board
        primary_driver = ai_result.get('primary_scope_driver', 'Unknown')
        growth = report.total_scope_growth_percentage

        node = MemoryNode.objects.create(
            board=board,
            mission=board.strategy.mission if board.strategy else None,
            node_type='scope_change',
            title=f"Scope Autopsy: {board.name} grew {growth:.0f}% — {primary_driver[:100]}",
            content=(
                f"Forensic scope analysis of '{board.name}'. "
                f"Scope grew from {report.baseline_task_count} to {report.final_task_count} tasks "
                f"({growth:.1f}% increase) over {report.board_snapshot.get('days_elapsed', '?')} days. "
                f"Primary driver: {primary_driver}. "
                f"Estimated cost: +${report.total_budget_impact:.0f}, +{report.total_delay_days} days delay."
            ),
            context_data={
                'report_id': report.pk,
                'baseline_tasks': report.baseline_task_count,
                'final_tasks': report.final_task_count,
                'growth_pct': growth,
                'total_delay_days': report.total_delay_days,
                'total_budget_impact': float(report.total_budget_impact),
                'primary_scope_driver': primary_driver,
                'event_count': report.timeline_events.count(),
            },
            tags=['scope-autopsy', 'scope-creep', 'forensic'],
            source_object_type='ScopeAutopsyReport',
            source_object_id=report.pk,
            importance_score=0.9,
            created_by=user,
            is_auto_captured=True,
        )

        # Check for cross-project pattern count
        if user:
            user_board_ids = set(
                user.member_boards.values_list('id', flat=True)
            ) | set(
                user.created_boards.values_list('id', flat=True)
            )
            past_count = MemoryNode.objects.filter(
                node_type='scope_change',
                source_object_type='ScopeAutopsyReport',
                board_id__in=user_board_ids,
            ).exclude(pk=node.pk).count()

            if past_count >= 1:
                cross_project_note = (
                    f"\n\n🔁 Cross-project pattern: Scope autopsy reports have been "
                    f"generated for {past_count + 1} of your projects. "
                    f"Review organizational memory for recurring scope drivers."
                )
                report.pattern_analysis = (report.pattern_analysis or '') + cross_project_note
                report.save(update_fields=['pattern_analysis'])

        logger.info("MemoryNode created for scope autopsy report %s", report.pk)
    except Exception:
        logger.warning("Failed to create MemoryNode for scope autopsy", exc_info=True)
