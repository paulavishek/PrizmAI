"""
Ephemeral Sandbox Views — Phase 7 of RBAC implementation.

Each real user gets their own private 24-hour copy of the demo template boards.
Master Demo Template boards (is_official_demo_board=True) are NEVER modified.

Lifecycle:
  POST /sandbox/create/   → duplicate all template boards for requesting user
  POST /sandbox/save/     → designate one board to survive sandbox deletion
  POST /sandbox/delete/   → delete sandbox immediately (user pressed "I'm done")
  GET  /sandbox/status/   → JSON status for in-app banner polling
"""
import logging
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from kanban.decorators import demo_write_guard
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
        strategy=None,                          # Do not inherit strategic context
        num_phases=template_board.num_phases,
        task_prefix=template_board.task_prefix,
        project_type=template_board.project_type,
    )
    new_board.save()

    # Fresh owner membership (no copying of template's memberships)
    BoardMembership.objects.create(board=new_board, user=user, role='owner')

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
        .select_related('column')
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
            # Assign all sandbox tasks to the sandbox user
            assigned_to=user,
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

    return new_board


def _purge_existing_sandbox(user):
    """Delete any existing sandbox for the user (boards + DemoSandbox record)."""
    from kanban.models import DemoSandbox, Board
    try:
        sandbox = user.demo_sandbox
        # Delete sandbox boards (not the saved board)
        Board.objects.filter(
            owner=user,
            is_official_demo_board=False,
            created_at__gte=sandbox.created_at,
        ).exclude(
            pk=sandbox.saved_board_id
        ).delete()
        sandbox.delete()
    except Exception:
        pass


# ── Views ─────────────────────────────────────────────────────────────────────

@login_required
@demo_write_guard
@require_http_methods(["POST"])
def create_sandbox(request):
    """
    Create or enter an ephemeral sandbox for the requesting user.

    If the user already has an active (non-expired) sandbox, enter it by
    setting the session flag and redirecting.  If the POST body contains
    force_new=1, offer to replace the existing sandbox (confirm=1 to proceed).
    """
    from kanban.models import Board, DemoSandbox

    user = request.user

    # Check for existing sandbox
    try:
        existing = user.demo_sandbox
        # Check if expired
        if existing.expires_at > timezone.now():
            # Active sandbox exists
            if request.POST.get('force_new') == '1':
                # User wants to replace — ask for confirmation
                if request.POST.get('confirm') != '1':
                    return JsonResponse({
                        'status': 'confirm_needed',
                        'message': 'Starting a new sandbox deletes your current one. Continue?',
                        'expires_at': existing.expires_at.isoformat(),
                    }, status=409)
                _purge_existing_sandbox(user)
            else:
                # Enter existing sandbox (default behavior)
                request.session['in_sandbox'] = True
                # Find the first sandbox board
                sandbox_board = Board.objects.filter(
                    owner=user,
                    is_official_demo_board=False,
                    is_seed_demo_data=False,
                    created_at__gte=existing.created_at,
                ).exclude(pk=existing.saved_board_id).first()
                redirect_url = f'/boards/{sandbox_board.id}/' if sandbox_board else '/dashboard/'
                return JsonResponse({
                    'status': 'entered',
                    'redirect_url': redirect_url,
                    'expires_at': existing.expires_at.isoformat(),
                })
        else:
            # Expired — purge silently
            _purge_existing_sandbox(user)
    except DemoSandbox.DoesNotExist:
        pass

    template_boards = Board.objects.filter(is_official_demo_board=True).order_by('name')
    if not template_boards.exists():
        return JsonResponse({'error': 'No demo template boards found.'}, status=404)

    # Bypass demo protection: we are creating NEW user-owned copies, not
    # modifying the original demo data.
    new_boards = []
    with allow_demo_writes():
        for template in template_boards:
            try:
                new_board = _duplicate_board(template, user)
                new_boards.append(new_board)
            except Exception as e:
                logger.error(f"Error duplicating board '{template.name}' for {user.username}: {e}")

        if not new_boards:
            return JsonResponse({'error': 'Sandbox creation failed — no boards duplicated.'}, status=500)

        sandbox = DemoSandbox.objects.create(
            user=user,
            expires_at=timezone.now() + timedelta(hours=24),
        )

    # Activate sandbox session
    request.session['in_sandbox'] = True

    return JsonResponse({
        'status': 'created',
        'boards_created': len(new_boards),
        'expires_at': sandbox.expires_at.isoformat(),
        'redirect_url': f'/boards/{new_boards[0].id}/' if new_boards else '/dashboard/',
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
    """Immediately delete the user's sandbox (user pressed 'I'm done')."""
    from kanban.models import DemoSandbox

    user = request.user
    try:
        sandbox = user.demo_sandbox
    except DemoSandbox.DoesNotExist:
        return JsonResponse({'error': 'No active sandbox found.'}, status=404)

    from kanban.tasks.sandbox_tasks import _delete_sandbox
    _delete_sandbox(sandbox)
    sandbox.delete()

    # Clear sandbox session flag
    request.session.pop('in_sandbox', None)

    return JsonResponse({'status': 'deleted'})


@login_required
@require_http_methods(["POST"])
def exit_sandbox_mode(request):
    """Exit sandbox mode (return to Tier 1 read-only demo) without deleting sandbox data."""
    request.session.pop('in_sandbox', None)
    return JsonResponse({'status': 'exited'})


@login_required
@require_http_methods(["GET"])
def sandbox_status(request):
    """
    JSON status endpoint for the in-app sandbox banner.
    Polled every 60 seconds by the banner JS.
    """
    from kanban.models import DemoSandbox

    user = request.user
    in_sandbox = request.session.get('in_sandbox', False)
    try:
        sandbox = user.demo_sandbox
        now = timezone.now()
        time_left = sandbox.expires_at - now
        hours_left = time_left.total_seconds() / 3600

        if hours_left <= 0:
            # Sandbox expired — clear session flag
            request.session.pop('in_sandbox', None)
            in_sandbox = False

        return JsonResponse({
            'has_sandbox': True,
            'in_sandbox': in_sandbox and hours_left > 0,
            'expires_at': sandbox.expires_at.isoformat(),
            'hours_remaining': round(hours_left, 1),
            'warning_sent': sandbox.warning_sent,
            'saved_board_id': sandbox.saved_board_id,
            'show_warning_banner': in_sandbox and (hours_left <= 2 or sandbox.warning_sent),
        })
    except DemoSandbox.DoesNotExist:
        # No sandbox record — clear stale session flag
        if in_sandbox:
            request.session.pop('in_sandbox', None)
        return JsonResponse({'has_sandbox': False, 'in_sandbox': False})


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
