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

    from ai_assistant.utils.ai_clients import GeminiClient
    client = GeminiClient(default_model='gemini-2.5-flash-lite')
    start_time = time.time()

    response = client.get_response(
        prompt=user_prompt,
        system_prompt=system_prompt,
        task_complexity='simple',
        temperature=0.3,
    )

    elapsed_ms = int((time.time() - start_time) * 1000)
    raw = response.get('content', '')

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

    overdue_tasks = (
        Task.objects
        .filter(
            due_date__range=(yesterday, now),
            status__in=['todo', 'in_progress', 'review'],
        )
        .select_related('board', 'assigned_to')
    )

    created = 0
    for task in overdue_tasks:
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

        MemoryNode.objects.create(
            board=task.board,
            node_type='risk_event',
            title=f"Missed deadline: {task.title[:150]}",
            content=(
                f"Task '{task.title}' missed its deadline of "
                f"{task.due_date.strftime('%b %d, %Y')}. "
                f"Status at deadline: {task.get_status_display()}."
                + (f" Assigned to: {assignee}." if assignee else "")
            ),
            context_data={
                'task_id': task.pk,
                'task_title': task.title,
                'due_date': task.due_date.isoformat(),
                'status': task.status,
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

    budgets = ProjectBudget.objects.select_related('board').all()
    created = 0

    for budget in budgets:
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
