"""Signal handlers for automatic memory capture.

These create MemoryNode records when significant project events happen.
"""
import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


def _node_exists(source_type, source_id, extra_tag=None):
    """Check if a MemoryNode already exists for this source object."""
    from knowledge_graph.models import MemoryNode
    qs = MemoryNode.objects.filter(
        source_object_type=source_type,
        source_object_id=source_id,
    )
    if extra_tag:
        qs = qs.filter(tags__contains=extra_tag)
    return qs.exists()


# ── Signal 1: Task Completed ────────────────────────────────────────────────

@receiver(pre_save, sender='kanban.Task')
def track_task_completion_for_memory(sender, instance, **kwargs):
    """Track whether this save transitions the task to completed."""
    if not instance.pk:
        instance._kg_just_completed = False
        return
    try:
        old = sender.objects.get(pk=instance.pk)
        instance._kg_just_completed = (
            old.progress < 100 and instance.progress >= 100
        )
        instance._kg_old_progress = old.progress
    except sender.DoesNotExist:
        instance._kg_just_completed = False


@receiver(post_save, sender='kanban.Task')
def capture_task_completed(sender, instance, created, **kwargs):
    """Capture a memory node when a significant task is completed."""
    if created:
        return
    if not getattr(instance, '_kg_just_completed', False):
        return
    if instance.item_type != 'task':
        return
    if _node_exists('Task', instance.pk):
        return

    # Filter trivial tasks — only capture if task existed for > 1 day
    if instance.created_at and (timezone.now() - instance.created_at).days < 1:
        return

    from knowledge_graph.models import MemoryNode
    board = instance.column.board if instance.column else None
    is_high_priority = instance.priority in ('high', 'urgent')

    MemoryNode.objects.create(
        board=board,
        mission=board.strategy.mission if board and board.strategy else None,
        node_type='milestone' if is_high_priority else 'outcome',
        title=f"Task completed: {instance.name[:150]}",
        content=(
            f"Task '{instance.name}' was completed"
            f"{' by ' + instance.assigned_to.get_full_name() if instance.assigned_to else ''}. "
            f"Priority: {instance.get_priority_display()}. "
            f"Board: {board.name if board else 'Unknown'}."
        ),
        context_data={
            'task_id': instance.pk,
            'task_name': instance.name,
            'priority': instance.priority,
            'assigned_to': instance.assigned_to_id,
            'board_name': board.name if board else None,
            'days_to_complete': (timezone.now() - instance.created_at).days if instance.created_at else None,
        },
        tags=['task-completed', instance.priority],
        created_by=instance.assigned_to,
        source_object_type='Task',
        source_object_id=instance.pk,
        importance_score=0.7 if is_high_priority else 0.4,
    )
    logger.info("Memory node created for task completion: %s", instance.name)


# ── Signal 3: Board Archived ────────────────────────────────────────────────

@receiver(pre_save, sender='kanban.Board')
def track_board_archive_for_memory(sender, instance, **kwargs):
    """Track whether this save transitions the board to archived."""
    if not instance.pk:
        instance._kg_just_archived = False
        return
    try:
        old = sender.objects.get(pk=instance.pk)
        instance._kg_just_archived = (not old.is_archived and instance.is_archived)
    except sender.DoesNotExist:
        instance._kg_just_archived = False


@receiver(post_save, sender='kanban.Board')
def capture_board_archived(sender, instance, created, **kwargs):
    """Capture a memory node when a board is archived."""
    if created:
        return
    if not getattr(instance, '_kg_just_archived', False):
        return
    if _node_exists('Board', instance.pk):
        return

    from knowledge_graph.models import MemoryNode
    from kanban.models import Task

    tasks = Task.objects.filter(column__board=instance, item_type='task')
    total = tasks.count()
    completed = tasks.filter(progress=100).count()
    pct = round((completed / total * 100), 1) if total else 0

    budget_info = {}
    try:
        budget = instance.budget
        budget_info = {
            'allocated_budget': float(budget.allocated_budget),
            'spent': float(budget.get_total_spent()),
            'utilization_pct': budget.get_budget_utilization_percent(),
        }
    except Exception:
        pass

    MemoryNode.objects.create(
        board=instance,
        mission=instance.strategy.mission if instance.strategy else None,
        node_type='outcome',
        title=f"Project completed: {instance.name[:150]}",
        content=(
            f"Board '{instance.name}' was archived. "
            f"{completed}/{total} tasks completed ({pct}%). "
            f"{'Budget: ' + str(budget_info.get('utilization_pct', 'N/A')) + '% utilized.' if budget_info else ''}"
        ),
        context_data={
            'board_id': instance.pk,
            'board_name': instance.name,
            'total_tasks': total,
            'completed_tasks': completed,
            'completion_pct': pct,
            'budget': budget_info,
            'project_deadline': str(instance.project_deadline) if instance.project_deadline else None,
        },
        tags=['board-archived', 'project-outcome'],
        created_by=instance.created_by,
        source_object_type='Board',
        source_object_id=instance.pk,
        importance_score=1.0,
    )
    logger.info("Memory node created for board archive: %s", instance.name)


# ── Signal 4: Conflict Resolved ─────────────────────────────────────────────

@receiver(pre_save, sender='kanban.ConflictDetection')
def track_conflict_resolution_for_memory(sender, instance, **kwargs):
    """Track whether this save resolves the conflict."""
    if not instance.pk:
        instance._kg_just_resolved = False
        return
    try:
        old = sender.objects.get(pk=instance.pk)
        instance._kg_just_resolved = (
            old.status != 'resolved' and instance.status == 'resolved'
        )
    except sender.DoesNotExist:
        instance._kg_just_resolved = False


@receiver(post_save, sender='kanban.ConflictDetection')
def capture_conflict_resolved(sender, instance, created, **kwargs):
    """Capture a memory node when a conflict is resolved."""
    if created:
        return
    if not getattr(instance, '_kg_just_resolved', False):
        return
    if _node_exists('ConflictDetection', instance.pk):
        return

    from knowledge_graph.models import MemoryNode

    resolution_text = ''
    if instance.chosen_resolution:
        resolution_text = f" Resolution: {instance.chosen_resolution}"

    MemoryNode.objects.create(
        board=instance.board,
        mission=instance.board.strategy.mission if instance.board and instance.board.strategy else None,
        node_type='conflict_resolution',
        title=f"Conflict resolved: {instance.title[:150]}",
        content=(
            f"{instance.get_conflict_type_display()} conflict '{instance.title}' was resolved. "
            f"Severity: {instance.get_severity_display()}.{resolution_text}"
        ),
        context_data={
            'conflict_id': instance.pk,
            'conflict_type': instance.conflict_type,
            'severity': instance.severity,
            'board_name': instance.board.name if instance.board else None,
            'resolution_feedback': instance.resolution_feedback or '',
        },
        tags=['conflict-resolved', instance.conflict_type],
        source_object_type='ConflictDetection',
        source_object_id=instance.pk,
        importance_score=0.75,
    )
    logger.info("Memory node created for conflict resolution: %s", instance.title)


# ── Signal 5: AI Recommendation Acted On ────────────────────────────────────

@receiver(pre_save, sender='kanban.CoachingSuggestion')
def track_coaching_action_for_memory(sender, instance, **kwargs):
    """Track whether the user acted on this AI recommendation."""
    if not instance.pk:
        instance._kg_just_acted = False
        return
    try:
        old = sender.objects.get(pk=instance.pk)
        instance._kg_just_acted = (
            old.action_taken is None and instance.action_taken is not None
        )
    except sender.DoesNotExist:
        instance._kg_just_acted = False


@receiver(post_save, sender='kanban.CoachingSuggestion')
def capture_ai_recommendation_acted(sender, instance, created, **kwargs):
    """Capture a memory node when a user acts on an AI coaching suggestion."""
    if created:
        return
    if not getattr(instance, '_kg_just_acted', False):
        return
    if _node_exists('CoachingSuggestion', instance.pk):
        return

    from knowledge_graph.models import MemoryNode

    MemoryNode.objects.create(
        board=instance.board,
        mission=instance.board.strategy.mission if instance.board and instance.board.strategy else None,
        node_type='ai_recommendation',
        title=f"AI suggestion {instance.action_taken}: {instance.title[:120]}",
        content=(
            f"AI coaching suggestion '{instance.title}' was {instance.get_action_taken_display()}. "
            f"Type: {instance.get_suggestion_type_display()}. "
            f"Severity: {instance.get_severity_display()}. "
            f"Helpful: {instance.was_helpful}."
        ),
        context_data={
            'suggestion_id': instance.pk,
            'suggestion_type': instance.suggestion_type,
            'severity': instance.severity,
            'action_taken': instance.action_taken,
            'was_helpful': instance.was_helpful,
            'board_name': instance.board.name if instance.board else None,
        },
        tags=['ai-recommendation', instance.action_taken, instance.suggestion_type],
        source_object_type='CoachingSuggestion',
        source_object_id=instance.pk,
        importance_score=0.6,
    )
    logger.info("Memory node created for AI recommendation: %s", instance.title)


# ── Signal 6: Scope Change Detected ─────────────────────────────────────────

@receiver(post_save, sender='kanban.ScopeCreepAlert')
def capture_scope_change(sender, instance, created, **kwargs):
    """Capture a memory node when a scope creep alert is created."""
    if not created:
        return
    if _node_exists('ScopeCreepAlert', instance.pk):
        return

    from knowledge_graph.models import MemoryNode

    MemoryNode.objects.create(
        board=instance.board,
        mission=instance.board.strategy.mission if instance.board and instance.board.strategy else None,
        node_type='scope_change',
        title=f"Scope creep detected: +{instance.scope_increase_percentage:.1f}% on {instance.board.name[:100]}",
        content=(
            f"Scope creep alert ({instance.get_severity_display()}) on '{instance.board.name}'. "
            f"Scope increased by {instance.scope_increase_percentage:.1f}% "
            f"({instance.tasks_added} tasks added). "
            f"{'Predicted delay: ' + str(instance.predicted_delay_days) + ' days.' if instance.predicted_delay_days else ''}"
        ),
        context_data={
            'alert_id': instance.pk,
            'severity': instance.severity,
            'scope_increase_pct': instance.scope_increase_percentage,
            'complexity_increase_pct': instance.complexity_increase_percentage,
            'tasks_added': instance.tasks_added,
            'predicted_delay_days': instance.predicted_delay_days,
            'board_name': instance.board.name,
        },
        tags=['scope-creep', instance.severity],
        source_object_type='ScopeCreepAlert',
        source_object_id=instance.pk,
        importance_score=0.85,
    )
    logger.info("Memory node created for scope change: %s", instance.board.name)


# ── Signal 7: Retrospective Finalized ───────────────────────────────────────

@receiver(pre_save, sender='kanban.ProjectRetrospective')
def track_retrospective_finalized_for_memory(sender, instance, **kwargs):
    """Track whether this save finalizes the retrospective."""
    if not instance.pk:
        instance._kg_just_finalized = False
        return
    try:
        old = sender.objects.get(pk=instance.pk)
        instance._kg_just_finalized = (
            old.status != 'finalized' and instance.status == 'finalized'
        )
    except sender.DoesNotExist:
        instance._kg_just_finalized = False


@receiver(post_save, sender='kanban.ProjectRetrospective')
def capture_retrospective_finalized(sender, instance, created, **kwargs):
    """Capture memory nodes from a finalized retrospective (lessons learned)."""
    if created:
        return
    if not getattr(instance, '_kg_just_finalized', False):
        return
    if _node_exists('ProjectRetrospective', instance.pk):
        return

    from knowledge_graph.models import MemoryNode

    # Combine the retrospective analysis into one rich memory node
    lessons = instance.lessons_learned if isinstance(instance.lessons_learned, list) else []
    lessons_text = "; ".join(str(l) for l in lessons[:10]) if lessons else "No specific lessons captured."

    MemoryNode.objects.create(
        board=instance.board,
        mission=instance.board.strategy.mission if instance.board and instance.board.strategy else None,
        node_type='lesson',
        title=f"Retrospective lessons: {instance.board.name[:120]}",
        content=(
            f"Retrospective for '{instance.board.name}' was finalized.\n"
            f"What went well: {(instance.what_went_well or 'N/A')[:500]}\n"
            f"What needs improvement: {(instance.what_needs_improvement or 'N/A')[:500]}\n"
            f"Lessons learned: {lessons_text}"
        ),
        context_data={
            'retrospective_id': instance.pk,
            'board_name': instance.board.name,
            'lessons_learned': lessons[:10],
            'what_went_well_excerpt': (instance.what_went_well or '')[:300],
            'what_needs_improvement_excerpt': (instance.what_needs_improvement or '')[:300],
        },
        tags=['retrospective', 'lessons-learned'],
        source_object_type='ProjectRetrospective',
        source_object_id=instance.pk,
        importance_score=0.9,
    )
    logger.info("Memory node created for retrospective: %s", instance.board.name)


# ── Signal 8: Meeting Transcript Analyzed ───────────────────────────────────

@receiver(pre_save, sender='wiki.WikiMeetingAnalysis')
def track_meeting_analysis_for_memory(sender, instance, **kwargs):
    """Track whether this save completes the meeting analysis."""
    if not instance.pk:
        instance._kg_just_completed = False
        return
    try:
        old = sender.objects.get(pk=instance.pk)
        instance._kg_just_completed = (
            old.processing_status != 'completed' and instance.processing_status == 'completed'
        )
    except sender.DoesNotExist:
        instance._kg_just_completed = False


@receiver(post_save, sender='wiki.WikiMeetingAnalysis')
def capture_meeting_analysis(sender, instance, created, **kwargs):
    """Capture memory nodes from decisions and risks found in meeting analysis."""
    if not getattr(instance, '_kg_just_completed', False):
        return
    if _node_exists('WikiMeetingAnalysis', instance.pk):
        return

    from knowledge_graph.models import MemoryNode

    results = instance.analysis_results or {}
    decisions = results.get('decisions', [])
    risks = results.get('risks', [])

    # Find linked board via wiki page tasks if any
    board = None
    mission = None
    try:
        from wiki.models import WikiMeetingTask
        meeting_task = WikiMeetingTask.objects.filter(analysis=instance).select_related(
            'task__column__board__strategy__mission'
        ).first()
        if meeting_task and meeting_task.task:
            board = meeting_task.task.column.board
            mission = board.strategy.mission if board.strategy else None
    except Exception:
        pass

    page_title = instance.wiki_page.title if instance.wiki_page else 'Unknown'

    # Create nodes for significant decisions
    for i, d in enumerate(decisions[:5]):
        decision_text = d.get('decision', '')
        if not decision_text:
            continue
        MemoryNode.objects.create(
            board=board,
            mission=mission,
            node_type='decision',
            title=f"Meeting decision: {decision_text[:150]}",
            content=(
                f"Decision from meeting '{page_title}': {decision_text}. "
                f"Context: {d.get('context', 'N/A')}. "
                f"Impact: {d.get('impact', 'N/A')}."
            ),
            context_data={
                'analysis_id': instance.pk,
                'wiki_page_id': instance.wiki_page_id,
                'page_title': page_title,
                'decision_index': i,
                'requires_action': d.get('requires_action', ''),
            },
            tags=['meeting-decision', 'meeting-notes'],
            source_object_type='WikiMeetingAnalysis',
            source_object_id=instance.pk,
            importance_score=0.7,
        )

    # Create nodes for significant risks
    for i, r in enumerate(risks[:3]):
        risk_text = r.get('risk', '')
        if not risk_text:
            continue
        MemoryNode.objects.create(
            board=board,
            mission=mission,
            node_type='risk_event',
            title=f"Meeting risk identified: {risk_text[:150]}",
            content=(
                f"Risk from meeting '{page_title}': {risk_text}. "
                f"Probability: {r.get('probability', 'N/A')}. "
                f"Mitigation: {r.get('mitigation', 'N/A')}."
            ),
            context_data={
                'analysis_id': instance.pk,
                'wiki_page_id': instance.wiki_page_id,
                'page_title': page_title,
                'risk_index': i,
            },
            tags=['meeting-risk', 'meeting-notes'],
            source_object_type='WikiMeetingAnalysis',
            source_object_id=instance.pk,
            importance_score=0.7,
        )

    if decisions or risks:
        logger.info(
            "Memory nodes created for meeting analysis %s: %d decisions, %d risks",
            instance.pk, len(decisions[:5]), len(risks[:3]),
        )
