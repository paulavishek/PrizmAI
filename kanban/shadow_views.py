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
from django.views.generic import ListView, CreateView, DetailView
from django.views.decorators.http import require_POST, require_http_methods
from django.http import JsonResponse
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.db import models
from datetime import timedelta
import logging

from kanban.models import Board, Task
from kanban.whatif_models import WhatIfScenario
from kanban.shadow_models import ShadowBranch, BranchSnapshot, BranchDivergenceLog
from kanban.audit_models import SystemAuditLog

logger = logging.getLogger(__name__)

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
        
        # Check user is board member
        if self.request.user not in board.members.all() and self.request.user != board.created_by:
            self.permission_denied()
        
        # Return active + archived from last 7 days
        cutoff_date = timezone.now() - timedelta(days=7)
        return ShadowBranch.objects.filter(
            board=board,
        ).filter(
            models.Q(status='active') |
            models.Q(status='archived', updated_at__gte=cutoff_date)
        ).select_related('created_by', 'source_scenario').prefetch_related('snapshots')

    def get_context_data(self, **kwargs):
        """Add board, quantum standup data, and color palette to context."""
        board_id = self.kwargs.get('board_id')
        board = get_object_or_404(Board, id=board_id)
        
        context = super().get_context_data(**kwargs)
        context['board'] = board
        context['predefined_colors'] = BRANCH_COLOR_PALETTE

        # --- Quantum Standup Data ---
        # Today's real progress
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        # Tasks completed today
        completed_today = Task.objects.filter(
            column__board=board,
            progress=100,
            updated_at__gte=today_start,
            updated_at__lt=today_end,
        ).select_related('column', 'assigned_to').order_by('-updated_at')[:10]

        context['tasks_completed_today'] = completed_today
        context['tasks_completed_count'] = completed_today.count()

        # Branch impacts today: divergences logged in last 24 hours
        recent_divergences = BranchDivergenceLog.objects.filter(
            branch__board=board,
            logged_at__gte=today_start,
            logged_at__lt=today_end,
        ).select_related('branch').order_by('-logged_at')

        context['branch_impacts_today'] = recent_divergences

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

        # Check user is board member
        if self.request.user not in board.members.all() and self.request.user != board.created_by:
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

        branch.save()

        # Create initial snapshot from linked scenario's slider values
        if branch.source_scenario and branch.source_scenario.input_parameters:
            params = branch.source_scenario.input_parameters
            BranchSnapshot.objects.create(
                branch=branch,
                scope_delta=int(params.get('tasks_added', 0)),
                team_delta=int(params.get('team_size_delta', 0)),
                deadline_delta_weeks=int(params.get('deadline_shift_days', 0)) // 7,
                feasibility_score=0,
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

                branch = ShadowBranch.objects.create(
                    board=board,
                    created_by=request.user,
                    name=name,
                    description=description,
                    branch_color=color,
                    source_scenario_id=scenario_id if scenario_id else None,
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
                                feasibility_score=0,
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

        if self.request.user not in board.members.all() and self.request.user != board.created_by:
            self.permission_denied()

        return ShadowBranch.objects.filter(board=board).select_related(
            'board', 'created_by', 'source_scenario'
        ).prefetch_related('snapshots', 'divergence_logs')

    def get_context_data(self, **kwargs):
        """Add snapshot history and divergence logs."""
        context = super().get_context_data(**kwargs)
        branch = self.object

        # Add board to context so templates can generate back-links
        context['board'] = branch.board

        # Get last 30 snapshots for history
        snapshots = branch.snapshots.all()[:30]
        context['snapshots'] = snapshots

        # Get divergence logs
        divergence_logs = branch.divergence_logs.all()[:50]
        context['divergence_logs'] = divergence_logs

        # Get latest snapshot
        latest = branch.get_latest_snapshot()
        context['latest_snapshot'] = latest

        # Build feasibility history for chart
        history = branch.get_score_history(limit=30)
        context['feasibility_history'] = [
            {'date': dt.isoformat(), 'score': score} for dt, score in history
        ]

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

        # Check user is board member or admin
        if self.request.user not in board.members.all() and self.request.user != board.created_by:
            return JsonResponse({'error': 'Permission denied'}, status=403)

        # Check for confirmation
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

        if self.request.user not in board.members.all() and self.request.user != board.created_by:
            self.permission_denied()

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

        # Check user is board member
        if request.user not in board.members.all() and request.user != board.created_by:
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

        # Check user is board member
        if request.user not in board.members.all() and request.user != board.created_by:
            return JsonResponse({'error': 'Permission denied'}, status=403)

        # Handle both form-encoded and JSON data
        if request.content_type == 'application/json':
            import json
            data_dict = json.loads(request.body)
            scenario_id = data_dict.get('scenario_id')
            branch_name = data_dict.get('branch_name', '').strip()
            color = data_dict.get('color', BRANCH_COLOR_PALETTE[0])
        else:
            scenario_id = request.POST.get('scenario_id')
            branch_name = request.POST.get('branch_name', '').strip()
            color = request.POST.get('color', BRANCH_COLOR_PALETTE[0])

        if not scenario_id:
            return JsonResponse({'error': 'scenario_id required'}, status=400)

        scenario = get_object_or_404(WhatIfScenario, id=scenario_id, board=board)

        if not branch_name:
            branch_name = f'{scenario.name} (Promoted)'

        # Create branch linked to scenario
        branch = ShadowBranch.objects.create(
            board=board,
            created_by=request.user,
            name=branch_name,
            description=f'Promoted from scenario: {scenario.name}',
            source_scenario=scenario,
            branch_color=color,
        )

        # Create initial snapshot from scenario's slider values
        if scenario.input_parameters:
            params = scenario.input_parameters
            BranchSnapshot.objects.create(
                branch=branch,
                scope_delta=int(params.get('tasks_added', 0)),
                team_delta=int(params.get('team_size_delta', 0)),
                deadline_delta_weeks=int(params.get('deadline_shift_days', 0)) // 7,
                feasibility_score=0,  # Will be updated by recalculation
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

        # Check user is board member
        if request.user not in board.members.all() and request.user != board.created_by:
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

        # Check user is board member
        if request.user not in board.members.all() and request.user != board.created_by:
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
def delete_branch(request, board_id, branch_id):
    """
    API endpoint: Permanently delete a shadow branch and all its snapshots.
    """
    try:
        board = get_object_or_404(Board, id=board_id)

        if request.user not in board.members.all() and request.user != board.created_by:
            return JsonResponse({'error': 'Permission denied'}, status=403)

        branch = get_object_or_404(ShadowBranch, id=branch_id, board=board)
        branch_name = branch.name
        branch.delete()

        logger.info(f'Branch "{branch_name}" (id={branch_id}) deleted by {request.user.username}')
        return JsonResponse({
            'success': True,
            'message': f'Branch "{branch_name}" deleted.',
            'redirect_url': f'/boards/{board_id}/shadow/',
        })
    except Exception as e:
        logger.error(f'Error deleting branch {branch_id}: {e}', exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def toggle_star_branch(request, board_id, branch_id):
    """
    API endpoint: Toggle the is_starred flag on a branch.
    """
    try:
        board = get_object_or_404(Board, id=board_id)

        if request.user not in board.members.all() and request.user != board.created_by:
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

