"""
Sandbox Views — single-tier personal demo system.

Each real user gets their own private 24-hour copy of the demo template boards.
Master Demo Template boards (is_official_demo_board=True) are NEVER modified.

Lifecycle:
  POST /toggle-demo-mode/           → provision sandbox (async via Celery) or re-enter existing
  POST /demo/start-experimenting/   → flip is_browsing to False (enable editing)
  POST /demo/reset-mine/            → wipe user's sandbox and re-provision
  POST /sandbox/save/               → designate one board to survive sandbox deletion
  POST /sandbox/delete/             → delete sandbox immediately
  GET  /sandbox/status/             → JSON status for in-app banner polling
  POST /sandbox/extend/             → extend sandbox expiry by 1 hour
"""
import logging
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from kanban.utils.demo_protection import allow_demo_writes

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _duplicate_board(template_board, user):
    """
    Deep-copy a single template board for a sandbox user.
    Returns the new Board instance.

    Per spec Edge Case 3:
    - Set pk=None and id=None on every record before .save()
    - Assign sandbox user as owner
    - Set is_official_demo_board = False on all copies
    - Do NOT copy BoardMembership records — create a fresh owner membership
    """
    from kanban.models import Board, BoardMembership, Column, TaskLabel, Task, Comment

    # --- Board ---
    # Build a fresh board from the template's field values, leaving M2M until after save
    new_board = Board(
        name=template_board.name,
        description=template_board.description,
        organization=None,                      # ← sandbox boards are user-owned, not demo org
        owner=user,
        created_by=user,
        is_official_demo_board=False,          # ← critical: not a template
        is_seed_demo_data=False,
        is_sandbox_copy=True,                    # ← tags this as a sandbox copy
        cloned_from=template_board,              # ← track which template it was cloned from
        strategy=None,                          # Do not inherit strategic context
        num_phases=template_board.num_phases,
        task_prefix=template_board.task_prefix,
        project_type=template_board.project_type,
        # Copy baseline for Scope Creep Index
        baseline_task_count=template_board.baseline_task_count,
        baseline_complexity_total=template_board.baseline_complexity_total,
        baseline_set_date=template_board.baseline_set_date,
    )
    new_board.save()

    # Fresh owner membership for the real user
    BoardMembership.objects.create(board=new_board, user=user, role='owner')

    # Copy demo persona memberships so assignees resolve correctly
    for membership in template_board.memberships.select_related('user').all():
        if membership.user != user:
            BoardMembership.objects.get_or_create(
                board=new_board, user=membership.user,
                defaults={'role': 'member'},
            )

    # --- TaskLabels (board FK) ---
    label_map = {}  # old label pk → new label instance
    for label in template_board.labels.all():
        new_label = TaskLabel(
            name=label.name,
            color=label.color,
            board=new_board,
            category=label.category,
        )
        new_label.save()
        label_map[label.pk] = new_label

    # --- Columns ---
    column_map = {}  # old column pk → new column instance
    for col in template_board.columns.order_by('position'):
        new_col = Column(
            name=col.name,
            board=new_board,
            position=col.position,
            wip_limit=col.wip_limit,
        )
        new_col.save()
        column_map[col.pk] = new_col

    # --- Tasks ---
    task_map = {}  # old task pk → new task instance
    for task in (
        Task.objects
        .filter(column__board=template_board)
        .select_related('column', 'assigned_to')
        .order_by('column__position', 'position')
    ):
        new_col = column_map.get(task.column.pk)
        if new_col is None:
            continue

        new_task = Task(
            title=task.title,
            description=task.description,
            column=new_col,
            position=task.position,
            priority=task.priority,
            progress=task.progress,
            due_date=task.due_date,
            start_date=task.start_date,
            phase=task.phase,
            item_type=task.item_type,
            milestone_status=task.milestone_status,
            created_by=user,
            # Keep original demo persona assignment (alex/sam/jordan)
            assigned_to=task.assigned_to,
            risk_level=task.risk_level,
            risk_likelihood=task.risk_likelihood,
            risk_impact=task.risk_impact,
            complexity_score=task.complexity_score,
            # Clear AI and personal operational data
            ai_summary=None,
            ai_summary_generated_at=None,
            ai_risk_score=None,
            ai_recommendations=None,
        )
        new_task.save()
        task_map[task.pk] = new_task

        # Re-assign labels via new label instances
        for old_label in task.labels.all():
            new_lab = label_map.get(old_label.pk)
            if new_lab:
                new_task.labels.add(new_lab)

    # --- Comments (keep demo comments for realism) ---
    for task in Task.objects.filter(column__board=template_board).select_related('column'):
        new_task = task_map.get(task.pk)
        if new_task is None:
            continue
        for comment in task.comments.order_by('created_at'):
            Comment.objects.create(
                task=new_task,
                user=user,
                content=comment.content,
            )

    # --- Task-to-Task Relationships (parent_task, dependencies, related, milestones) ---
    for old_pk, new_task in task_map.items():
        old_task = Task.objects.get(pk=old_pk)
        updated = False

        # Parent-child relationships (subtasks)
        if old_task.parent_task_id and old_task.parent_task_id in task_map:
            new_task.parent_task = task_map[old_task.parent_task_id]
            updated = True

        # Milestone positioning (position_after_task)
        if old_task.position_after_task_id and old_task.position_after_task_id in task_map:
            new_task.position_after_task = task_map[old_task.position_after_task_id]
            updated = True

        if updated:
            new_task.save(update_fields=['parent_task', 'position_after_task'])

        # Gantt chart dependencies (M2M)
        for dep in old_task.dependencies.all():
            if dep.pk in task_map:
                new_task.dependencies.add(task_map[dep.pk])

        # Related tasks (M2M)
        for related in old_task.related_tasks.all():
            if related.pk in task_map:
                new_task.related_tasks.add(task_map[related.pk])

    # --- Budget + TaskCost (for CPI calculation) ---
    try:
        from kanban.budget_models import ProjectBudget, TaskCost
        template_budget = ProjectBudget.objects.filter(board=template_board).first()
        if template_budget:
            ProjectBudget.objects.create(
                board=new_board,
                allocated_budget=template_budget.allocated_budget,
                currency=template_budget.currency,
                allocated_hours=template_budget.allocated_hours,
                warning_threshold=template_budget.warning_threshold,
                critical_threshold=template_budget.critical_threshold,
                ai_optimization_enabled=template_budget.ai_optimization_enabled,
                created_by=user,
            )
            for tc in TaskCost.objects.filter(task__column__board=template_board).select_related('task'):
                new_task = task_map.get(tc.task_id)
                if new_task:
                    TaskCost.objects.create(
                        task=new_task,
                        estimated_cost=tc.estimated_cost,
                        estimated_hours=tc.estimated_hours,
                        actual_cost=tc.actual_cost,
                        hourly_rate=tc.hourly_rate,
                        resource_cost=tc.resource_cost,
                    )
    except Exception:
        pass  # Budget copying is best-effort; don't block provisioning

    return new_board


NUM_TASKS_TO_REASSIGN = 3  # How many demo tasks to reassign to the real user


def _reassign_demo_tasks_to_user(sandbox, user):
    """
    Pick NUM_TASKS_TO_REASSIGN tasks on the user's sandbox copy and reassign
    them from demo personas to the real user.  Store the mapping in
    sandbox.reassigned_tasks so we can restore on leave.

    Selection criteria: prefer variety — different priorities, with due dates,
    from different demo personas.
    """
    from kanban.models import Board, Task

    boards = Board.objects.filter(owner=user, is_sandbox_copy=True)
    if not boards.exists():
        return

    # Find tasks on sandbox boards that are assigned to demo personas
    candidates = (
        Task.objects
        .filter(
            column__board__in=boards,
            item_type='task',
            assigned_to__isnull=False,
            assigned_to__email__contains='@demo.prizmai.local',
        )
        .exclude(progress=100)
        .select_related('assigned_to', 'column__board')
        .order_by('priority', 'due_date')
    )

    # Pick up to NUM_TASKS_TO_REASSIGN from different assignees for variety
    picked = []
    seen_assignees = set()
    # First pass: one per assignee
    for t in candidates:
        if t.assigned_to_id not in seen_assignees and len(picked) < NUM_TASKS_TO_REASSIGN:
            picked.append(t)
            seen_assignees.add(t.assigned_to_id)
    # Second pass: fill remaining slots
    if len(picked) < NUM_TASKS_TO_REASSIGN:
        for t in candidates:
            if t not in picked and len(picked) < NUM_TASKS_TO_REASSIGN:
                picked.append(t)

    mapping = {}
    for task in picked:
        mapping[str(task.id)] = task.assigned_to_id
        task.assigned_to = user
        task.save(update_fields=['assigned_to'])

    sandbox.reassigned_tasks = mapping
    sandbox.save(update_fields=['reassigned_tasks'])


def _restore_demo_task_assignments(sandbox):
    """
    Reassign tasks back to their original demo persona owners using the
    mapping stored in sandbox.reassigned_tasks.
    """
    from kanban.models import Task
    from django.contrib.auth.models import User

    mapping = sandbox.reassigned_tasks or {}
    if not mapping:
        return

    for task_id_str, original_user_id in mapping.items():
        try:
            task = Task.objects.get(pk=int(task_id_str))
            task.assigned_to_id = original_user_id
            task.save(update_fields=['assigned_to'])
        except Task.DoesNotExist:
            pass  # Task was deleted (board purged)

    sandbox.reassigned_tasks = {}
    sandbox.save(update_fields=['reassigned_tasks'])


def _join_demo_org(user):
    """Add the user to the demo organization and as a member of the demo board."""
    from accounts.models import Organization, UserProfile
    from kanban.models import Board, BoardMembership

    demo_org = Organization.objects.filter(is_demo=True).first()
    if not demo_org:
        return

    # Store original org so we can restore on leave
    profile = user.profile
    if not profile.organization or not profile.organization.is_demo:
        # Only update if not already in demo org
        profile._original_org_id = getattr(profile, '_original_org_id', profile.organization_id)
        profile.organization = demo_org
        profile.save(update_fields=['organization'])


def _leave_demo_org(user):
    """Remove the user from the demo organization, restoring their original org."""
    from accounts.models import UserProfile

    profile = user.profile
    if profile.organization and profile.organization.is_demo:
        profile.organization = None
        profile.save(update_fields=['organization'])


def _purge_existing_sandbox(user):
    """Delete any existing sandbox for the user (boards + DemoSandbox record)."""
    from kanban.models import DemoSandbox, Board
    try:
        sandbox = user.demo_sandbox
        # Restore assignments before deleting
        _restore_demo_task_assignments(sandbox)
        # Delete sandbox boards (not the saved board, never official demo boards)
        Board.objects.filter(
            owner=user,
            is_sandbox_copy=True,
            is_official_demo_board=False,
            is_seed_demo_data=False,
        ).exclude(
            pk=sandbox.saved_board_id
        ).delete()
        sandbox.delete()
    except Exception:
        pass


# ── Views ─────────────────────────────────────────────────────────────────────

@login_required
@require_http_methods(["POST"])
def toggle_browsing(request):
    """POST /demo/start-experimenting/ — flip is_browsing to False, or provision a new sandbox."""
    from kanban.models import DemoSandbox
    try:
        sandbox = request.user.demo_sandbox
        sandbox.is_browsing = False
        sandbox.save(update_fields=['is_browsing'])
        return JsonResponse({'status': 'ok', 'is_browsing': False})
    except DemoSandbox.DoesNotExist:
        # No sandbox exists — provision one (e.g. user exited and wants to start again)
        from kanban.tasks.sandbox_provisioning import provision_sandbox_task
        result = provision_sandbox_task.delay(request.user.id)
        return JsonResponse({'status': 'provisioning', 'task_id': result.id})


@login_required
@require_http_methods(["POST"])
def reset_my_demo(request):
    """POST /demo/reset-mine/ — wipe user's sandbox and re-provision via Celery."""
    from kanban.models import DemoSandbox

    _purge_existing_sandbox(request.user)

    # Re-provision asynchronously
    from kanban.tasks.sandbox_provisioning import provision_sandbox_task
    result = provision_sandbox_task.delay(request.user.id)

    return JsonResponse({
        'status': 'resetting',
        'task_id': result.id,
    })


@login_required
@require_http_methods(["POST"])
def save_sandbox_board(request):
    """
    Designate one board to survive sandbox deletion.
    The board moves to the user's real workspace (it already effectively is — we
    just clear the created_at-range marker by updating the saved_board FK on
    the sandbox, which the cleanup task respects).
    """
    from kanban.models import DemoSandbox, Board, BoardMembership

    user = request.user
    board_id = request.POST.get('board_id')
    if not board_id:
        return JsonResponse({'error': 'board_id is required.'}, status=400)

    try:
        sandbox = user.demo_sandbox
    except DemoSandbox.DoesNotExist:
        return JsonResponse({'error': 'No active sandbox found.'}, status=404)

    try:
        board = Board.objects.get(pk=board_id, owner=user)
    except Board.DoesNotExist:
        return JsonResponse({'error': 'Board not found or not owned by you.'}, status=404)

    sandbox.saved_board = board
    sandbox.save(update_fields=['saved_board'])

    return JsonResponse({
        'status': 'saved',
        'board_id': board.id,
        'board_name': board.name,
    })


@login_required
@require_http_methods(["POST"])
def delete_sandbox(request):
    """Immediately delete the user's sandbox but keep them in demo view."""
    from kanban.models import DemoSandbox

    user = request.user
    try:
        sandbox = user.demo_sandbox
    except DemoSandbox.DoesNotExist:
        return JsonResponse({'error': 'No active sandbox found.'}, status=404)

    from kanban.tasks.sandbox_tasks import _delete_sandbox
    _restore_demo_task_assignments(sandbox)
    _delete_sandbox(sandbox)
    sandbox.delete()

    # Stay in demo view — user can start a new sandbox later
    # Do NOT set is_viewing_demo=False or leave demo org

    return JsonResponse({'status': 'deleted'})


@login_required
@require_http_methods(["GET"])
def sandbox_status(request):
    """
    JSON status endpoint for the in-app sandbox banner.
    Polled every 60 seconds by the banner JS.
    """
    from kanban.models import DemoSandbox

    user = request.user
    is_viewing_demo = getattr(getattr(user, 'profile', None), 'is_viewing_demo', False)
    try:
        sandbox = user.demo_sandbox
        now = timezone.now()
        time_left = sandbox.expires_at - now
        hours_left = time_left.total_seconds() / 3600

        if hours_left <= 0:
            # Sandbox expired
            is_viewing_demo = False

        return JsonResponse({
            'has_sandbox': True,
            'is_viewing_demo': is_viewing_demo and hours_left > 0,
            'is_browsing': sandbox.is_browsing,
            'expires_at': sandbox.expires_at.isoformat(),
            'hours_remaining': round(hours_left, 1),
            'warning_sent': sandbox.warning_sent,
            'saved_board_id': sandbox.saved_board_id,
            'show_warning_banner': is_viewing_demo and (hours_left <= 2 or sandbox.warning_sent),
        })
    except DemoSandbox.DoesNotExist:
        return JsonResponse({'has_sandbox': False, 'is_viewing_demo': False})


MAX_SANDBOX_EXTENSIONS = 3
EXTENSION_HOURS = 1


@login_required
@require_http_methods(["POST"])
def extend_demo_session(request):
    """
    Extend the user's sandbox expiry by EXTENSION_HOURS.
    Limited to MAX_SANDBOX_EXTENSIONS extensions total.
    """
    from kanban.models import DemoSandbox

    user = request.user
    try:
        sandbox = user.demo_sandbox
    except DemoSandbox.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'No active sandbox found.'}, status=404)

    # Track extensions via a simple counter stored on the sandbox
    extensions_used = getattr(sandbox, '_extensions_used', None)
    if extensions_used is None:
        # Calculate extensions used from the difference between current expiry and original 24h window
        original_expiry = sandbox.created_at + timedelta(hours=24)
        extra_hours = (sandbox.expires_at - original_expiry).total_seconds() / 3600
        extensions_used = max(0, int(round(extra_hours / EXTENSION_HOURS)))

    if extensions_used >= MAX_SANDBOX_EXTENSIONS:
        return JsonResponse({
            'status': 'error',
            'message': f'Maximum extensions ({MAX_SANDBOX_EXTENSIONS}) reached.',
            'extensions_remaining': 0,
        })

    sandbox.expires_at += timedelta(hours=EXTENSION_HOURS)
    sandbox.warning_sent = False  # Reset warning so banner updates
    sandbox.save(update_fields=['expires_at', 'warning_sent'])

    extensions_remaining = MAX_SANDBOX_EXTENSIONS - (extensions_used + 1)

    return JsonResponse({
        'status': 'success',
        'new_expiry_time': sandbox.expires_at.isoformat(),
        'extensions_remaining': extensions_remaining,
    })
