"""
Shadow Board Views and API Endpoints

Handles all HTTP requests for Shadow Board functionality:
- List view with Quantum Standup
- Branch creation from saved scenarios
- Branch detail with snapshot history
- Branch commitment with audit logging
- Merge conflict detection API
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
import json
import types
from django.views.generic import ListView, CreateView, DetailView
from django.views.decorators.http import require_POST, require_http_methods
from django.http import JsonResponse
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.db import models
from datetime import timedelta
import logging

from kanban.models import Board, Task, TaskActivity
from kanban.whatif_models import WhatIfScenario
from kanban.shadow_models import ShadowBranch, BranchSnapshot, BranchDivergenceLog
from kanban.audit_models import SystemAuditLog
from kanban.decorators import demo_write_guard

logger = logging.getLogger(__name__)


def _compute_initial_feasibility(board, params):
    """Compute feasibility score synchronously so branches don't start at 0%."""
    try:
        from kanban.utils.whatif_engine import WhatIfEngine
        from kanban.tasks.shadow_branch_tasks import scale_feasibility
        engine = WhatIfEngine(board)
        results = engine.simulate({
            'tasks_added': int(params.get('tasks_added', 0)),
            'team_size_delta': int(params.get('team_size_delta', 0)),
            'deadline_shift_days': int(params.get('deadline_shift_days', 0)),
        })
        return scale_feasibility(results.get('feasibility_score', 0))
    except Exception:
        logger.warning("Could not compute initial feasibility, defaulting to 50", exc_info=True)
        return 50

# Define predefined color palette for branches
BRANCH_COLOR_PALETTE = [
    '#0d6efd',  # Blue (default)
    '#198754',  # Green
    '#dc3545',  # Red
    '#fd7e14',  # Orange
    '#6f42c1',  # Purple
    '#20c997',  # Teal
    '#0dcaf0',  # Cyan
    '#ffc107',  # Warning (Amber)
    '#e92e8f',  # Pink
    '#6c757d',  # Gray
]


@method_decorator(login_required, name='dispatch')
class ShadowBoardListView(ListView):
    """
    Display all shadow branches for a board in a card grid layout.
    
    Includes:
    - Quantum Standup section (today's progress + branch impacts)
    - Branch cards with feasibility badges and sparklines
    - Compare mode for side-by-side branch diff
    """
    model = ShadowBranch
    template_name = 'kanban/shadow_board_list.html'
    context_object_name = 'branches'
    paginate_by = None

    def get_queryset(self):
        """Get all branches (active + recently archived) for this board."""
        board_id = self.kwargs.get('board_id')
        board = get_object_or_404(Board, id=board_id)
        
        # RBAC: check board access
        if not self.request.user.has_perm('prizmai.view_board', board):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        
        # Return active, committed, and recently archived branches (last 7 days)
        cutoff_date = timezone.now() - timedelta(days=7)
        return ShadowBranch.objects.filter(
            board=board,
        ).filter(
            models.Q(status='active') |
            models.Q(status='committed') |
            models.Q(status='archived', updated_at__gte=cutoff_date)
        ).select_related('created_by', 'source_scenario').prefetch_related('snapshots')

    def get_context_data(self, **kwargs):
        """Add board, quantum standup data, and color palette to context."""
        board_id = self.kwargs.get('board_id')
        board = get_object_or_404(Board, id=board_id)
        
        context = super().get_context_data(**kwargs)
        context['board'] = board
        context['predefined_colors'] = BRANCH_COLOR_PALETTE
        context['has_archived_branches'] = any(
            b.status == 'archived' for b in context['branches']
        )
        context['has_active_branches'] = any(
            b.status == 'active' for b in context['branches']
        )

        # --- Quantum Standup Data ---
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        # Real Progress Today — driven by TaskActivity, not Task.completed_at.
        #
        # Why not completed_at: populate_all_demo_data calls Task.save() with
        # progress=100, which causes Task.save() to stamp completed_at=now() on
        # every seeded Done-column task.  After any demo reset all those tasks
        # carry today's completed_at, making them indistinguishable from tasks
        # a user genuinely completed today.
        #
        # TaskActivity records are only written by user-facing views (move_task
        # for drag-and-drop, update_task_fields_api for Gantt triage).  The
        # seeder never creates them, so they reliably represent real user work.
        #
        # A column-name guard at the end excludes tasks moved back out of Done
        # later in the same day (their activity still matches 'done' in the
        # description but their current column is no longer Done/Complete).
        move_activities_today = (
            TaskActivity.objects
            .filter(
                task__column__board=board,
                task__item_type='task',
                activity_type__in=['moved', 'updated'],
                created_at__gte=today_start,
                created_at__lt=today_end,
            )
            .filter(
                models.Q(description__icontains='done') |
                models.Q(description__icontains='complete')
            )
            .select_related('task', 'task__column', 'user')
            .order_by('task_id', '-created_at')
        )

        seen_task_ids: set = set()
        completed_today = []
        for act in move_activities_today:
            if act.task_id in seen_task_ids:
                continue
            seen_task_ids.add(act.task_id)
            col_lower = act.task.column.name.lower()
            if 'done' not in col_lower and 'complete' not in col_lower:
                continue  # moved back out of Done later today
            act.task.completer = act.user
            completed_today.append(act.task)
            if len(completed_today) >= 10:
                break

        context['tasks_completed_today'] = completed_today
        context['tasks_completed_count'] = len(completed_today)

        # Bug 4 fix: use BranchSnapshot records created today for "How It Affected
        # Your Branches" instead of BranchDivergenceLog (which only logs >5-point
        # changes). Compare each branch's latest-today snapshot against the snapshot
        # immediately before today to derive old_score / new_score / score_delta.
        today_snapshots_qs = BranchSnapshot.objects.filter(
            branch__board=board,
            branch__status='active',
            captured_at__gte=today_start,
            captured_at__lt=today_end,
        ).select_related('branch').order_by('branch_id', 'captured_at')

        latest_today: dict = {}
        for snap in today_snapshots_qs:
            latest_today[snap.branch_id] = snap

        branch_impacts = []
        for branch_id, latest_snap in latest_today.items():
            prev_snap = (
                BranchSnapshot.objects
                .filter(branch_id=branch_id, captured_at__lt=today_start)
                .order_by('-captured_at')
                .first()
            )
            old_score = prev_snap.feasibility_score if prev_snap else 0
            new_score = latest_snap.feasibility_score
            branch_impacts.append(types.SimpleNamespace(
                branch=latest_snap.branch,
                old_score=old_score,
                new_score=new_score,
                score_delta=new_score - old_score,
            ))

        branch_impacts.sort(key=lambda x: abs(x.score_delta), reverse=True)
        context['branch_impacts_today'] = branch_impacts

        # Auto-heal: if any active branches have no snapshots, re-trigger recalculation
        branches_without_snapshots = ShadowBranch.objects.filter(
            board=board, status='active',
        ).exclude(
            id__in=BranchSnapshot.objects.values_list('branch_id', flat=True)
        )
        if branches_without_snapshots.exists():
            try:
                from kanban.tasks.shadow_branch_tasks import recalculate_branches_for_board
                recalculate_branches_for_board.apply_async(
                    args=[board.id],
                    kwargs={'trigger_event': 'Auto-heal: branches missing snapshots'},
                    countdown=2,
                )
            except Exception:
                pass

        return context


@method_decorator(login_required, name='dispatch')
class CreateBranchView(CreateView):
    """
    Create a new shadow branch.
    
    Accepts:
    - name: Branch name
    - description: Optional description
    - scenario_id: Optional FK to existing WhatIfScenario (pre-fills slider values)
    - color_hex: Hex color code from predefined palette
    """
    model = ShadowBranch
    template_name = 'kanban/create_branch_modal.html'
    fields = ['name', 'description', 'branch_color']

    def get_form_kwargs(self):
        """Pre-fill form with request data."""
        kwargs = super().get_form_kwargs()
        return kwargs

    def form_valid(self, form):
        """Handle branch creation."""
        board_id = self.kwargs.get('board_id')
        board = get_object_or_404(Board, id=board_id)

        # RBAC: check board access
        if not self.request.user.has_perm('prizmai.edit_board', board):
            return JsonResponse({'error': 'Permission denied'}, status=403)

        branch = form.save(commit=False)
        branch.board = board
        branch.created_by = self.request.user

        # Link to source scenario if provided
        scenario_id = self.request.POST.get('scenario_id')
        if scenario_id:
            try:
                scenario = WhatIfScenario.objects.get(id=scenario_id, board=board)
                branch.source_scenario = scenario
            except WhatIfScenario.DoesNotExist:
                scenario = None

        # Snapshot baseline velocity at creation time so live recalculations
        # can compare actual 7-day velocity against the projection's assumption.
        from kanban.tasks.shadow_branch_tasks import compute_baseline_velocity
        branch.baseline_velocity_per_week = compute_baseline_velocity(board)

        branch.save()

        # Create initial snapshot from linked scenario's slider values
        if branch.source_scenario and branch.source_scenario.input_parameters:
            params = branch.source_scenario.input_parameters
            BranchSnapshot.objects.create(
                branch=branch,
                scope_delta=int(params.get('tasks_added', 0)),
                team_delta=int(params.get('team_size_delta', 0)),
                deadline_delta_weeks=int(params.get('deadline_shift_days', 0)) // 7,
                feasibility_score=_compute_initial_feasibility(board, params),
            )

        # Trigger initial branch recalculation
        from kanban.tasks.shadow_branch_tasks import recalculate_branches_for_board
        recalculate_branches_for_board.apply_async(
            args=[board_id],
            kwargs={'trigger_event': f'Branch "{branch.name}" created'},
        )

        messages.success(self.request, f'Branch "{branch.name}" created and recalculating...')
        return redirect('shadow_board_list', board_id=board_id)

    def post(self, request, *args, **kwargs):
        """Handle both regular form POST and AJAX requests."""
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # AJAX request
            try:
                board_id = self.kwargs.get('board_id')
                board = get_object_or_404(Board, id=board_id)

                name = request.POST.get('name', '').strip()
                description = request.POST.get('description', '').strip()
                color = request.POST.get('branch_color', BRANCH_COLOR_PALETTE[0])
                scenario_id = request.POST.get('scenario_id')

                if not name:
                    return JsonResponse({'error': 'Branch name required'}, status=400)

                from kanban.tasks.shadow_branch_tasks import compute_baseline_velocity
                branch = ShadowBranch.objects.create(
                    board=board,
                    created_by=request.user,
                    name=name,
                    description=description,
                    branch_color=color,
                    source_scenario_id=scenario_id if scenario_id else None,
                    baseline_velocity_per_week=compute_baseline_velocity(board),
                )

                # Create initial snapshot from linked scenario's slider values
                if scenario_id:
                    try:
                        scenario = WhatIfScenario.objects.get(id=scenario_id, board=board)
                        if scenario.input_parameters:
                            params = scenario.input_parameters
                            BranchSnapshot.objects.create(
                                branch=branch,
                                scope_delta=int(params.get('tasks_added', 0)),
                                team_delta=int(params.get('team_size_delta', 0)),
                                deadline_delta_weeks=int(params.get('deadline_shift_days', 0)) // 7,
                                feasibility_score=_compute_initial_feasibility(board, params),
                            )
                    except WhatIfScenario.DoesNotExist:
                        pass

                # Trigger recalculation
                from kanban.tasks.shadow_branch_tasks import recalculate_branches_for_board
                recalculate_branches_for_board.apply_async(
                    args=[board_id],
                    kwargs={'trigger_event': f'Branch "{branch.name}" created'},
                )

                return JsonResponse({
                    'success': True,
                    'branch_id': branch.id,
                    'branch_name': branch.name,
                    'redirect_url': f'/boards/{board_id}/shadow/',
                })
            except Exception as e:
                logger.error(f'Error creating branch via AJAX: {e}', exc_info=True)
                return JsonResponse({'error': str(e)}, status=500)
        else:
            # Regular form POST
            return super().post(request, *args, **kwargs)


@method_decorator(login_required, name='dispatch')
class BranchDetailView(DetailView):
    """
    Display detailed view of a single shadow branch.
    
    Shows:
    - Latest snapshot data
    - Feasibility trend/sparkline
    - Snapshot history with dive-in capability
    - Divergence log
    """
    model = ShadowBranch
    template_name = 'kanban/branch_detail.html'
    context_object_name = 'branch'
    pk_url_kwarg = 'branch_id'

    def get_queryset(self):
        """Get branch if user is board member."""
        board_id = self.kwargs.get('board_id')
        board = get_object_or_404(Board, id=board_id)

        if not self.request.user.has_perm('prizmai.view_board', board):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied

        return ShadowBranch.objects.filter(board=board).select_related(
            'board', 'created_by', 'source_scenario'
        ).prefetch_related('snapshots', 'divergence_logs')

    def get_context_data(self, **kwargs):
        """Add snapshot history and divergence logs."""
        context = super().get_context_data(**kwargs)
        branch = self.object

        # Add board to context so templates can generate back-links
        context['board'] = branch.board

        # Pull a wider window than we display so collapsing runs of identical
        # snapshots still gives the user ~30 distinct rows to scroll through.
        raw_snapshots = list(branch.snapshots.all()[:200])

        # Collapse consecutive snapshots whose user-visible fields (score,
        # scope/team/deadline deltas) are identical into a single row.
        # Pre-existing snapshot bloat (from before the tighter creation-time
        # dedup landed) was making history feel broken — every row looked the
        # same.  Display-side collapsing fixes the perception immediately
        # without rewriting the DB.  We expose `repeat_count` and
        # `first_captured_at` so the template can show "Snapshot 12 (×5,
        # first seen 18:14)" instead of five back-to-back identical rows.
        collapsed = []
        # raw_snapshots is newest-first; iterate that order so the row labelled
        # with the latest captured_at survives, and we accumulate the earliest
        # captured_at as the "first seen" timestamp.
        for snap in raw_snapshots:
            key = (
                round(float(snap.feasibility_score), 2),
                snap.scope_delta,
                snap.team_delta,
                snap.deadline_delta_weeks,
            )
            if collapsed and collapsed[-1]['key'] == key:
                # Merge into the previous (newer) entry — bump repeat count and
                # push first_captured_at further back in time.
                collapsed[-1]['repeat_count'] += 1
                collapsed[-1]['first_captured_at'] = snap.captured_at
            else:
                collapsed.append({
                    'snapshot': snap,
                    'key': key,
                    'repeat_count': 1,
                    'first_captured_at': snap.captured_at,
                })
            if len(collapsed) >= 30:
                break

        context['snapshots'] = [
            {
                'snapshot': entry['snapshot'],
                'repeat_count': entry['repeat_count'],
                'first_captured_at': entry['first_captured_at'],
            }
            for entry in collapsed
        ]

        # Get divergence logs
        divergence_logs = branch.divergence_logs.all()[:50]
        context['divergence_logs'] = divergence_logs

        # Get latest snapshot
        latest = branch.get_latest_snapshot()
        context['latest_snapshot'] = latest

        # Build feasibility history for chart.
        # IMPORTANT: feasibility_score is a DecimalField; rendering it through
        # the template's |safe filter as Python repr produces `Decimal('40.75')`
        # which is not valid JS and throws "Decimal is not defined" in the
        # browser, blanking the Feasibility Trend chart.  Coerce to float and
        # serialize with json.dumps so the template can embed it via
        # |json_script (preferred) or |safe (legacy).
        history = branch.get_score_history(limit=30)
        feasibility_history = [
            {'date': dt.isoformat(), 'score': float(score)} for dt, score in history
        ]
        context['feasibility_history'] = feasibility_history
        context['feasibility_history_json'] = json.dumps(feasibility_history)

        return context


@method_decorator(login_required, name='dispatch')
@method_decorator(require_POST, name='post')
class CommitBranchView(DetailView):
    """
    Commit a branch as the accepted reality.
    
    Actions:
    - Marks the branch as committed
    - Archives all other active branches on the board
    - Creates an audit log entry
    """
    model = ShadowBranch
    pk_url_kwarg = 'branch_id'

    def post(self, request, *args, **kwargs):
        """Handle branch commitment."""
        board_id = self.kwargs.get('board_id')
        board = get_object_or_404(Board, id=board_id)
        branch = self.get_object()

        # RBAC: check board edit permission
        if not self.request.user.has_perm('prizmai.edit_board', board):
            return JsonResponse({'error': 'Permission denied'}, status=403)

        # Check for confirmation (supports both JSON body and form POST)
        try:
            body_data = json.loads(request.body)
            confirm = body_data.get('confirm', False) is True
        except (json.JSONDecodeError, AttributeError):
            confirm = request.POST.get('confirm', 'false').lower() == 'true'
        if not confirm:
            return JsonResponse({'error': 'Confirmation required'}, status=400)

        try:
            # Mark target branch as committed
            branch.status = 'committed'
            branch.save(update_fields=['status'])

            # Archive all other active branches
            other_branches = ShadowBranch.objects.filter(
                board=board,
                status='active',
            ).exclude(id=branch.id)
            archived_count = other_branches.count()
            other_branches.update(status='archived')

            # Create audit log
            SystemAuditLog.objects.create(
                user=request.user,
                action_type='branch.committed',
                severity='high',
                object_type='shadow_branch',
                object_id_backup=branch.id,
                object_repr=str(branch),
                board_id=board.id,
                message=f'Committed branch "{branch.name}" and archived {archived_count} others',
                additional_data={
                    'branch_id': branch.id,
                    'branch_name': branch.name,
                    'archived_count': archived_count,
                },
                ip_address=self._get_client_ip(request),
            )

            messages.success(
                request,
                f'Branch "{branch.name}" committed. Other branches archived.'
            )
            return JsonResponse({
                'success': True,
                'redirect_url': f'/boards/{board_id}/shadow/',
            })

        except Exception as e:
            logger.error(f'Error committing branch {branch.id}: {e}', exc_info=True)
            return JsonResponse({'error': str(e)}, status=500)

    def get_object(self, queryset=None):
        """Get branch with board permission check."""
        board_id = self.kwargs.get('board_id')
        board = get_object_or_404(Board, id=board_id)

        if not self.request.user.has_perm('prizmai.view_board', board):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied

        return get_object_or_404(
            ShadowBranch,
            id=self.kwargs.get('branch_id'),
            board=board,
        )

    @staticmethod
    def _get_client_ip(request):
        """Extract client IP from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


@login_required
@require_http_methods(['GET'])
def merge_conflict_check(request, board_id):
    """
    API endpoint: Check for conflicts between two branches.
    
    Query params:
    - branch_a: ID of first branch
    - branch_b: ID of second branch
    
    Returns JSON with list of conflicting fields and indicators.
    """
    try:
        board = get_object_or_404(Board, id=board_id)

        # RBAC: check board access
        if not request.user.has_perm('prizmai.view_board', board):
            return JsonResponse({'error': 'Permission denied'}, status=403)

        branch_a_id = request.GET.get('branch_a')
        branch_b_id = request.GET.get('branch_b')

        if not branch_a_id or not branch_b_id:
            return JsonResponse(
                {'error': 'Both branch_a and branch_b required'},
                status=400
            )

        branch_a = get_object_or_404(ShadowBranch, id=branch_a_id, board=board)
        branch_b = get_object_or_404(ShadowBranch, id=branch_b_id, board=board)

        # Get latest snapshots
        snapshot_a = branch_a.get_latest_snapshot()
        snapshot_b = branch_b.get_latest_snapshot()

        if not snapshot_a or not snapshot_b:
            return JsonResponse({
                'conflicts': [],
                'message': 'One or both branches lack snapshots',
            })

        # Check for contradictory parameters
        conflicts = []

        # Scope conflict: one adds, other removes
        if (snapshot_a.scope_delta > 0 and snapshot_b.scope_delta < 0) or \
           (snapshot_a.scope_delta < 0 and snapshot_b.scope_delta > 0):
            conflicts.append({
                'type': 'scope',
                'branch_a_value': snapshot_a.scope_delta,
                'branch_b_value': snapshot_b.scope_delta,
                'contradictory': True,
                'severity': 'high',
                'description': f'Scope conflict: Branch A {snapshot_a.scope_delta:+d} tasks vs Branch B {snapshot_b.scope_delta:+d}',
            })

        # Team conflict
        if (snapshot_a.team_delta > 0 and snapshot_b.team_delta < 0) or \
           (snapshot_a.team_delta < 0 and snapshot_b.team_delta > 0):
            conflicts.append({
                'type': 'team',
                'branch_a_value': snapshot_a.team_delta,
                'branch_b_value': snapshot_b.team_delta,
                'contradictory': True,
                'severity': 'high',
                'description': f'Team conflict: Branch A {snapshot_a.team_delta:+d} members vs Branch B {snapshot_b.team_delta:+d}',
            })

        # Deadline conflict
        if (snapshot_a.deadline_delta_weeks > 0 and snapshot_b.deadline_delta_weeks < 0) or \
           (snapshot_a.deadline_delta_weeks < 0 and snapshot_b.deadline_delta_weeks > 0):
            conflicts.append({
                'type': 'deadline',
                'branch_a_value': snapshot_a.deadline_delta_weeks,
                'branch_b_value': snapshot_b.deadline_delta_weeks,
                'contradictory': True,
                'severity': 'medium',
                'description': f'Deadline conflict: Branch A {snapshot_a.deadline_delta_weeks:+d} weeks vs Branch B {snapshot_b.deadline_delta_weeks:+d}',
            })

        return JsonResponse({
            'success': True,
            'conflicts': conflicts,
            'conflict_count': len(conflicts),
        })

    except Exception as e:
        logger.error(f'Error in merge_conflict_check: {e}', exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(['POST'])
@demo_write_guard
def promote_scenario_to_branch(request, board_id):
    """
    API endpoint: Promote a What-If scenario to a Shadow Branch.
    
    POST params (form-encoded or JSON):
    - scenario_id: ID of WhatIfScenario to promote
    - branch_name: Optional override name (else uses scenario name)
    - color: Optional hex color
    
    Returns JSON with created branch ID and redirect URL.
    """
    try:
        board = get_object_or_404(Board, id=board_id)

        # RBAC: check board access
        if not request.user.has_perm('prizmai.edit_board', board):
            return JsonResponse({'error': 'Permission denied'}, status=403)

        # Handle both form-encoded and JSON data
        if request.content_type == 'application/json':
            import json
            data_dict = json.loads(request.body)
            scenario_id = data_dict.get('scenario_id')
            branch_name = data_dict.get('branch_name', '').strip()
            color = data_dict.get('color', BRANCH_COLOR_PALETTE[0])
            description = data_dict.get('description', '').strip()
        else:
            scenario_id = request.POST.get('scenario_id')
            branch_name = request.POST.get('branch_name', '').strip()
            color = request.POST.get('color', BRANCH_COLOR_PALETTE[0])
            description = request.POST.get('description', '').strip()

        if not scenario_id:
            return JsonResponse({'error': 'scenario_id required'}, status=400)

        scenario = get_object_or_404(WhatIfScenario, id=scenario_id, board=board)

        if not branch_name:
            branch_name = f'{scenario.name} (Promoted)'

        # Create branch linked to scenario
        from kanban.tasks.shadow_branch_tasks import compute_baseline_velocity
        branch = ShadowBranch.objects.create(
            board=board,
            created_by=request.user,
            name=branch_name,
            description=description or f'Promoted from scenario: {scenario.name}',
            source_scenario=scenario,
            branch_color=color,
            baseline_velocity_per_week=compute_baseline_velocity(board),
        )

        # Create initial snapshot from scenario's slider values
        if scenario.input_parameters:
            params = scenario.input_parameters
            BranchSnapshot.objects.create(
                branch=branch,
                scope_delta=int(params.get('tasks_added', 0)),
                team_delta=int(params.get('team_size_delta', 0)),
                deadline_delta_weeks=int(params.get('deadline_shift_days', 0)) // 7,
                feasibility_score=_compute_initial_feasibility(board, params),
            )

        # Trigger recalculation with scenario's parameters as seed
        from kanban.tasks.shadow_branch_tasks import recalculate_branches_for_board
        recalculate_branches_for_board.apply_async(
            args=[board_id],
            kwargs={'trigger_event': f'Scenario "{scenario.name}" promoted to branch "{branch.name}"'},
        )

        return JsonResponse({
            'success': True,
            'branch_id': branch.id,
            'branch_name': branch.name,
            'redirect_url': f'/boards/{board_id}/shadow/',
            'message': f'Scenario "{scenario.name}" promoted to branch "{branch.name}"',
        })

    except Exception as e:
        logger.error(f'Error promoting scenario: {e}', exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def get_branch_snapshots(request, board_id, branch_id):
    """
    API endpoint: Fetch snapshot history for a branch (for sparklines).
    
    Returns JSON with arrays of feasibility scores and captured_at timestamps.
    Limited to last 30 snapshots, oldest-first.
    """
    try:
        board = get_object_or_404(Board, id=board_id)

        # RBAC: check board access
        if not request.user.has_perm('prizmai.view_board', board):
            return JsonResponse({'error': 'Permission denied'}, status=403)

        branch = get_object_or_404(ShadowBranch, id=branch_id, board=board)

        # Fetch last 30 snapshots, oldest first
        snapshots = BranchSnapshot.objects.filter(
            branch=branch
        ).order_by('-captured_at')[:30]

        # Reverse to get oldest-first order
        snapshots = list(reversed(snapshots))

        scores = [s.feasibility_score for s in snapshots]
        timestamps = [s.captured_at.isoformat() for s in snapshots]

        return JsonResponse({
            'branch_id': branch.id,
            'branch_name': branch.name,
            'scores': scores,
            'timestamps': timestamps,
            'count': len(snapshots),
        })

    except Exception as e:
        logger.error(f'Error fetching branch snapshots: {e}', exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def get_branches_comparison(request, board_id, branch_a_id, branch_b_id):
    """
    API endpoint: Fetch both branches' latest snapshots for detailed comparison.
    
    Returns JSON with both branches and their latest snapshots.
    """
    try:
        board = get_object_or_404(Board, id=board_id)

        # RBAC: check board access
        if not request.user.has_perm('prizmai.view_board', board):
            return JsonResponse({'error': 'Permission denied'}, status=403)

        branch_a = get_object_or_404(ShadowBranch, id=branch_a_id, board=board)
        branch_b = get_object_or_404(ShadowBranch, id=branch_b_id, board=board)

        snapshot_a = branch_a.get_latest_snapshot()
        snapshot_b = branch_b.get_latest_snapshot()

        if not snapshot_a or not snapshot_b:
            return JsonResponse({
                'error': 'One or both branches lack snapshots',
                'branch_a': branch_a.name,
                'branch_b': branch_b.name,
            }, status=400)

        # Build comparison data
        comparison = {
            'branch_a': {
                'id': branch_a.id,
                'name': branch_a.name,
                'color': branch_a.branch_color,
                'snapshot': {
                    'scope_delta': snapshot_a.scope_delta,
                    'team_delta': snapshot_a.team_delta,
                    'deadline_delta_weeks': snapshot_a.deadline_delta_weeks,
                    'feasibility_score': snapshot_a.feasibility_score,
                    'projected_completion_date': snapshot_a.projected_completion_date.isoformat() if snapshot_a.projected_completion_date else None,
                    'projected_budget_utilization': snapshot_a.projected_budget_utilization,
                    'captured_at': snapshot_a.captured_at.isoformat(),
                }
            },
            'branch_b': {
                'id': branch_b.id,
                'name': branch_b.name,
                'color': branch_b.branch_color,
                'snapshot': {
                    'scope_delta': snapshot_b.scope_delta,
                    'team_delta': snapshot_b.team_delta,
                    'deadline_delta_weeks': snapshot_b.deadline_delta_weeks,
                    'feasibility_score': snapshot_b.feasibility_score,
                    'projected_completion_date': snapshot_b.projected_completion_date.isoformat() if snapshot_b.projected_completion_date else None,
                    'projected_budget_utilization': snapshot_b.projected_budget_utilization,
                    'captured_at': snapshot_b.captured_at.isoformat(),
                }
            }
        }

        return JsonResponse(comparison)

    except Exception as e:
        logger.error(f'Error fetching branches comparison: {e}', exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
@demo_write_guard
def delete_branch(request, board_id, branch_id):
    """
    API endpoint: Permanently delete a shadow branch and all its snapshots.

    If the deleted branch was active or committed, all archived branches on
    the same board are automatically restored to active (since they were
    archived because of that branch's commit).
    """
    try:
        board = get_object_or_404(Board, id=board_id)

        # RBAC: check board access
        if not request.user.has_perm('prizmai.edit_board', board):
            return JsonResponse({'error': 'Permission denied'}, status=403)

        branch = get_object_or_404(ShadowBranch, id=branch_id, board=board)
        branch_name = branch.name
        was_active_or_committed = branch.status in ('active', 'committed')

        branch.delete()

        # When an active/committed branch is removed, restore any archived branches
        # so the board isn't left with nothing to work with.
        restored_count = 0
        if was_active_or_committed:
            archived_qs = ShadowBranch.objects.filter(board=board, status='archived')
            restored_count = archived_qs.count()
            if restored_count:
                archived_qs.update(status='active')
                logger.info(
                    f'Restored {restored_count} archived branch(es) after deleting '
                    f'active/committed branch "{branch_name}" (id={branch_id}) '
                    f'by {request.user.username}'
                )

        logger.info(f'Branch "{branch_name}" (id={branch_id}) deleted by {request.user.username}')

        response_data = {
            'success': True,
            'message': f'Branch "{branch_name}" deleted.',
            'redirect_url': f'/boards/{board_id}/shadow/',
            'restored_count': restored_count,
        }
        if restored_count:
            response_data['restore_message'] = (
                f'{restored_count} archived branch{"es were" if restored_count > 1 else " was"} '
                f'automatically restored to active.'
            )
        return JsonResponse(response_data)
    except Exception as e:
        logger.error(f'Error deleting branch {branch_id}: {e}', exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
@demo_write_guard
def link_scenario_to_branch(request, board_id, branch_id):
    """
    API endpoint: Link (or unlink) a saved WhatIfScenario to an existing branch.

    POST body (JSON):
    - scenario_id: int ID of the scenario to link, or null/empty to unlink

    On link: updates branch.source_scenario and creates a new snapshot from the
    scenario's input_parameters, then triggers a recalculation.
    On unlink: clears branch.source_scenario only (existing snapshots are kept).
    """
    try:
        board = get_object_or_404(Board, id=board_id)

        # RBAC: check board access
        if not request.user.has_perm('prizmai.edit_board', board):
            return JsonResponse({'error': 'Permission denied'}, status=403)

        branch = get_object_or_404(ShadowBranch, id=branch_id, board=board)

        try:
            body = json.loads(request.body)
            scenario_id = body.get('scenario_id')
        except (json.JSONDecodeError, AttributeError):
            scenario_id = request.POST.get('scenario_id')

        if not scenario_id:
            # Unlink
            branch.source_scenario = None
            branch.save(update_fields=['source_scenario'])
            return JsonResponse({'success': True, 'linked': False, 'message': 'Scenario unlinked from branch.'})

        scenario = get_object_or_404(WhatIfScenario, id=scenario_id, board=board)
        branch.source_scenario = scenario
        branch.save(update_fields=['source_scenario'])

        # Trigger recalculation — extract_branch_params now reads directly from
        # source_scenario.input_parameters, so no zero-score seed snapshot is needed.
        from kanban.tasks.shadow_branch_tasks import recalculate_branches_for_board
        recalculate_branches_for_board.apply_async(
            args=[board_id],
            kwargs={'trigger_event': f'Linked scenario "{scenario.name}" to branch "{branch.name}"'},
        )

        return JsonResponse({
            'success': True,
            'linked': True,
            'scenario_name': scenario.name,
            'message': f'Scenario "{scenario.name}" linked to branch. Recalculating...',
        })

    except Exception as e:
        logger.error(f'Error linking scenario to branch {branch_id}: {e}', exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
@demo_write_guard
def restore_all_archived_branches(request, board_id):
    """
    API endpoint: Restore all archived branches on a board back to active.
    """
    try:
        board = get_object_or_404(Board, id=board_id)

        if not request.user.has_perm('prizmai.edit_board', board):
            return JsonResponse({'error': 'Permission denied'}, status=403)

        archived_qs = ShadowBranch.objects.filter(board=board, status='archived')
        count = archived_qs.count()
        archived_qs.update(status='active')

        logger.info(f'All {count} archived branch(es) restored by {request.user.username} on board {board_id}')
        return JsonResponse({
            'success': True,
            'restored_count': count,
            'message': f'{count} archived branch{"es" if count != 1 else ""} restored to active.',
        })
    except Exception as e:
        logger.error(f'Error restoring all archived branches: {e}', exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
@demo_write_guard
def restore_branch(request, board_id, branch_id):
    try:
        board = get_object_or_404(Board, id=board_id)

        # RBAC: check board access
        if not request.user.has_perm('prizmai.edit_board', board):
            return JsonResponse({'error': 'Permission denied'}, status=403)

        branch = get_object_or_404(ShadowBranch, id=branch_id, board=board)

        if branch.status != 'archived':
            return JsonResponse({'error': 'Only archived branches can be restored'}, status=400)

        branch.status = 'active'
        branch.save(update_fields=['status'])

        logger.info(f'Branch "{branch.name}" (id={branch_id}) restored by {request.user.username}')
        return JsonResponse({
            'success': True,
            'message': f'Branch "{branch.name}" restored to active.',
        })
    except Exception as e:
        logger.error(f'Error restoring branch {branch_id}: {e}', exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
@demo_write_guard
def toggle_star_branch(request, board_id, branch_id):
    try:
        board = get_object_or_404(Board, id=board_id)

        # RBAC: check board access
        if not request.user.has_perm('prizmai.edit_board', board):
            return JsonResponse({'error': 'Permission denied'}, status=403)

        branch = get_object_or_404(ShadowBranch, id=branch_id, board=board)
        branch.is_starred = not branch.is_starred
        branch.save(update_fields=['is_starred'])

        return JsonResponse({
            'success': True,
            'is_starred': branch.is_starred,
        })
    except Exception as e:
        logger.error(f'Error toggling star for branch {branch_id}: {e}', exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

