"""
Celery tasks for the Knowledge Graph feature.
- generate_memory_connections: AI-powered connection discovery between nodes
- check_missed_deadlines: captures missed-deadline events as memory nodes
- check_budget_thresholds: captures budget warning/critical events as memory nodes
"""
import json
import logging
import time

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Task 1: Generate Memory Connections ──────────────────────────────────────

@shared_task(name='knowledge_graph.generate_memory_connections')
def generate_memory_connections():
    """
    Discover connections between memory nodes using Gemini AI.
    Runs weekly — finds pairs of nodes that are similar, causal, or related.
    """
    from knowledge_graph.models import MemoryNode, MemoryConnection

    # Only process nodes from the last 30 days that don't already have many connections
    cutoff = timezone.now() - timezone.timedelta(days=30)
    recent_nodes = (
        MemoryNode.objects
        .filter(created_at__gte=cutoff)
        .order_by('-importance_score')[:60]
    )

    if len(recent_nodes) < 2:
        logger.info("generate_memory_connections: fewer than 2 recent nodes, skipping.")
        return {'status': 'skipped', 'reason': 'insufficient_nodes'}

    # Build compact descriptions for AI
    node_lines = []
    for n in recent_nodes:
        board_name = n.board.name if n.board_id else 'N/A'
        node_lines.append(
            f"NODE {n.pk}: [{n.node_type}] {n.title} | Board: {board_name}\n{n.content[:200]}"
        )
    nodes_text = "\n\n".join(node_lines)

    system_prompt = (
        "You are a knowledge graph analyst. Given a list of project memory nodes, "
        "identify meaningful connections between them. Only propose connections where "
        "there is a real relationship — not superficial word overlap.\n\n"
        "Connection types: caused, similar_to, led_to, prevented, repeated_from\n\n"
        "Return ONLY valid JSON. No markdown, no explanation outside JSON."
    )
    user_prompt = (
        f"MEMORY NODES:\n{nodes_text}\n\n"
        "Identify up to 10 connections.\n"
        "Return JSON:\n"
        '{"connections": [\n'
        '  {"from_id": 1, "to_id": 5, "type": "caused", "reason": "Brief reason"}\n'
        ']}'
    )

    from ai_assistant.utils.ai_router import AIRouter
    router = AIRouter()
    start_time = time.time()

    response = router.complete(
        prompt=user_prompt,
        user=None,  # Celery background task — no user context
        system_prompt=system_prompt,
        complexity='simple',
    )
    elapsed_ms = int((time.time() - start_time) * 1000)
    raw = response.get('text', '')

    try:
        cleaned = raw.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]
        parsed = json.loads(cleaned.strip())
    except (json.JSONDecodeError, IndexError):
        logger.warning("generate_memory_connections: Failed to parse AI response.")
        return {'status': 'error', 'reason': 'parse_failure'}

    valid_types = {t[0] for t in MemoryConnection.CONNECTION_TYPES}
    node_ids = {n.pk for n in recent_nodes}
    created = 0

    for conn in parsed.get('connections', [])[:10]:
        from_id = conn.get('from_id')
        to_id = conn.get('to_id')
        conn_type = conn.get('type')
        reason = conn.get('reason', '')

        if (
            from_id not in node_ids
            or to_id not in node_ids
            or from_id == to_id
            or conn_type not in valid_types
        ):
            continue

        _, was_created = MemoryConnection.objects.get_or_create(
            from_node_id=from_id,
            to_node_id=to_id,
            connection_type=conn_type,
            defaults={'reason': reason[:500], 'ai_generated': True},
        )
        if was_created:
            created += 1

    logger.info(f"generate_memory_connections: created {created} connections in {elapsed_ms}ms")
    return {'status': 'success', 'connections_created': created}


# ── Task 2: Check Missed Deadlines ──────────────────────────────────────────

@shared_task(name='knowledge_graph.check_missed_deadlines')
def check_missed_deadlines():
    """
    Detect tasks that just missed their deadlines and capture as risk_event nodes.
    Runs daily — looks for tasks whose due_date passed in the last 24 hours.
    """
    from kanban.models import Task
    from knowledge_graph.models import MemoryNode

    now = timezone.now()
    yesterday = now - timezone.timedelta(hours=24)

    # Task has no `status` field — workflow status is the column. Consider a
    # task "missed" only if it's NOT in a Done-type column (structural marker or
    # name heuristic — see kanban.column_semantics).
    from kanban.column_semantics import column_type_q
    overdue_tasks = (
        Task.objects
        .filter(
            due_date__range=(yesterday, now),
            item_type='task',
        )
        .exclude(column_type_q('done'))
        .select_related('column', 'column__board', 'assigned_to')
    )

    from knowledge_graph.demo_guard import is_demo_board

    created = 0
    for task in overdue_tasks:
        board = task.column.board if task.column_id else None
        if board is None or is_demo_board(board):
            continue  # demo memory is curated/deterministic — no live auto-capture
        # Skip if a risk_event for this task already exists
        exists = MemoryNode.objects.filter(
            source_object_type='Task',
            source_object_id=task.pk,
            node_type='risk_event',
        ).exists()
        if exists:
            continue

        assignee = ''
        if task.assigned_to:
            assignee = task.assigned_to.get_full_name() or task.assigned_to.username

        column_name = task.column.name if task.column_id else 'Unknown'
        MemoryNode.objects.create(
            board=board,
            node_type='risk_event',
            title=f"Missed deadline: {task.title[:150]}",
            content=(
                f"Task '{task.title}' missed its deadline of "
                f"{task.due_date.strftime('%b %d, %Y')}. "
                f"Status at deadline: {column_name}."
                + (f" Assigned to: {assignee}." if assignee else "")
            ),
            context_data={
                'task_id': task.pk,
                'task_title': task.title,
                'due_date': task.due_date.isoformat(),
                'status': column_name,
            },
            tags=['missed-deadline', 'risk'],
            importance_score=0.7,
            source_object_type='Task',
            source_object_id=task.pk,
            is_auto_captured=True,
        )
        created += 1

    logger.info(f"check_missed_deadlines: captured {created} missed deadlines.")
    return {'status': 'success', 'missed_deadlines_captured': created}


# ── Task 3: Check Budget Thresholds ─────────────────────────────────────────

@shared_task(name='knowledge_graph.check_budget_thresholds')
def check_budget_thresholds():
    """
    Check project budgets and capture warning/critical/over events as risk_event nodes.
    Runs daily — uses ProjectBudget.get_status() to detect threshold breaches.
    """
    from kanban.budget_models import ProjectBudget
    from knowledge_graph.models import MemoryNode

    from knowledge_graph.demo_guard import is_demo_board

    budgets = ProjectBudget.objects.select_related('board').all()
    created = 0

    for budget in budgets:
        if is_demo_board(budget.board):
            continue  # demo memory is curated/deterministic — no live auto-capture
        status = budget.get_status()
        if status == 'ok':
            continue

        # De-duplicate: check if we already captured this exact status
        existing = MemoryNode.objects.filter(
            source_object_type='ProjectBudget',
            source_object_id=budget.pk,
            node_type='risk_event',
        ).order_by('-created_at').first()

        if existing and existing.context_data.get('budget_status') == status:
            continue  # Same status already recorded

        utilization = budget.get_budget_utilization_percent()
        remaining = budget.get_remaining_budget()

        status_label = {'warning': 'Warning', 'critical': 'Critical', 'over': 'Over Budget'}
        title = f"Budget {status_label.get(status, status)}: {budget.board.name}"

        MemoryNode.objects.create(
            board=budget.board,
            node_type='risk_event',
            title=title[:200],
            content=(
                f"Project '{budget.board.name}' budget reached {status} level. "
                f"Utilization: {utilization:.1f}%. "
                f"Remaining: ${remaining:,.2f}."
            ),
            context_data={
                'budget_id': budget.pk,
                'budget_status': status,
                'utilization_pct': float(utilization),
                'remaining': float(remaining),
            },
            tags=['budget', status],
            importance_score=0.8 if status in ('critical', 'over') else 0.6,
            source_object_type='ProjectBudget',
            source_object_id=budget.pk,
            is_auto_captured=True,
        )
        created += 1

    logger.info(f"check_budget_thresholds: captured {created} budget alerts.")
    return {'status': 'success', 'budget_alerts_captured': created}


# ── Task 4: Analyze Memory Gaps (Spectra Gap Analysis) ──────────────────────

@shared_task(name='knowledge_graph.analyze_memory_gaps')
def analyze_memory_gaps(memory_node_id):
    """
    Lazily review a single memory node for missing context using Gemini.
    Dispatched (at most 5 per /memory/ page load) for memories that have not
    been analysed yet — especially thin auto-captured ones. Never retries and
    never crashes the worker.
    """
    from knowledge_graph.models import MemoryNode
    from knowledge_graph.views import gap_analysis_system_prompt, parse_gap_questions

    try:
        node = MemoryNode.objects.filter(pk=memory_node_id).first()
        if node is None or node.gaps_analyzed:
            return {'status': 'skipped', 'reason': 'missing_or_already_analyzed'}

        from ai_assistant.utils.ai_router import AIRouter
        response = AIRouter().complete(
            prompt='Generate the JSON array of questions now.',
            user=None,  # Celery background task — no user context
            system_prompt=gap_analysis_system_prompt(node.node_type, node.content),
            complexity='simple',
        )
        questions = parse_gap_questions(response.get('text', ''))

        if questions:
            node.gap_questions = questions
            node.has_gaps = True
            # Freeze the canonical checklist the first time gaps are detected;
            # later edits only mark which of these remain (anchored tracking).
            if not node.gap_questions_original:
                node.gap_questions_original = questions
        else:
            node.has_gaps = False
        node.gaps_analyzed = True
        node.save(update_fields=[
            'gap_questions', 'gap_questions_original', 'has_gaps', 'gaps_analyzed',
        ])
        return {'status': 'success', 'has_gaps': node.has_gaps, 'node_id': node.pk}
    except Exception as exc:
        # Never crash the worker; mark analysed so we don't retry in a loop.
        logger.warning(f"analyze_memory_gaps failed for node {memory_node_id}: {exc}")
        try:
            MemoryNode.objects.filter(pk=memory_node_id).update(
                gaps_analyzed=True, has_gaps=False
            )
        except Exception:
            pass
        return {'status': 'error', 'node_id': memory_node_id}
