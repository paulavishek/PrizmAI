"""
Triple Constraint Dashboard Views
Shows how Scope, Cost, and Time interact for a board and provides AI-powered
recommendations for the optimal project configuration.
"""
import logging
from datetime import date

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Avg, Max
from django.utils import timezone

from kanban.models import Board, Task
from kanban.budget_models import ProjectBudget, TaskCost
from kanban.burndown_models import BurndownPrediction, TeamVelocitySnapshot, SprintMilestone
from kanban.utils.triple_constraint_ai import analyze_triple_constraints

logger = logging.getLogger(__name__)


@login_required
def set_project_deadline(request, board_id):
    """Save the board's project deadline (Time constraint) and redirect back."""
    board = get_object_or_404(Board, id=board_id)
    if request.method == 'POST':
        raw = request.POST.get('project_deadline', '').strip()
        if raw:
            try:
                board.project_deadline = date.fromisoformat(raw)
                board.save(update_fields=['project_deadline'])
                messages.success(request, f'Project deadline set to {board.project_deadline.strftime("%b %d, %Y")}.')
            except ValueError:
                messages.error(request, 'Invalid date format. Please use YYYY-MM-DD.')
        else:
            board.project_deadline = None
            board.save(update_fields=['project_deadline'])
            messages.success(request, 'Project deadline cleared.')
    return redirect('triple_constraint_dashboard', board_id=board.id)


@login_required
def triple_constraint_dashboard(request, board_id):
    """
    Triple Constraint Dashboard – shows Scope / Cost / Time interplay.
    Triggers AI analysis on POST with action=ai_analyze.
    """
    board = get_object_or_404(Board, id=board_id)

    # ── Scope ──────────────────────────────────────────────────────────────────
    scope_status = board.get_current_scope_status()
    has_baseline = scope_status is not None

    tasks = Task.objects.filter(column__board=board)
    total_tasks = tasks.count()
    total_complexity = tasks.aggregate(Sum('complexity_score'))['complexity_score__sum'] or 0

    # ── Budget / Cost ──────────────────────────────────────────────────────────
    budget = None
    budget_data = None
    try:
        budget = ProjectBudget.objects.get(board=board)
        spent = float(budget.get_spent_amount())
        allocated = float(budget.allocated_budget)
        utilization_pct = budget.get_budget_utilization_percent()
        remaining = float(budget.get_remaining_budget())
        budget_status = budget.get_status()
        budget_data = {
            'allocated_budget': allocated,
            'spent_amount': spent,
            'utilization_pct': utilization_pct,
            'remaining_budget': remaining,
            'currency': budget.currency,
            'status': budget_status,
            'warning_threshold': budget.warning_threshold,
            'critical_threshold': budget.critical_threshold,
        }
    except ProjectBudget.DoesNotExist:
        pass

    # Average cost-per-task (used by what-if simulator)
    avg_cost_per_task = 0
    if budget_data and total_tasks > 0:
        avg_cost_per_task = round(budget_data['spent_amount'] / total_tasks, 2)

    # ── Time / Schedule ────────────────────────────────────────────────────────
    latest_prediction = BurndownPrediction.objects.filter(
        board=board
    ).order_by('-prediction_date').first()

    # ── Effective deadline (tiered fallback) ───────────────────────────────────
    # 1) Board.project_deadline  (set explicitly on this page)
    # 2) Latest BurndownPrediction.target_completion_date
    # 3) Latest SprintMilestone.target_date
    # 4) Max Task.due_date across all tasks
    # 5) None → genuinely no target set
    deadline_source = None
    effective_deadline = None

    if board.project_deadline:
        effective_deadline = board.project_deadline
        deadline_source = 'board'
    elif latest_prediction and latest_prediction.target_completion_date:
        effective_deadline = latest_prediction.target_completion_date
        deadline_source = 'burndown'
    else:
        latest_milestone = SprintMilestone.objects.filter(board=board).order_by('-target_date').first()
        if latest_milestone:
            effective_deadline = latest_milestone.target_date
            deadline_source = 'milestone'
        else:
            max_due = tasks.filter(due_date__isnull=False).aggregate(
                Max('due_date'))['due_date__max']
            if max_due:
                effective_deadline = max_due.date() if hasattr(max_due, 'date') else max_due
                deadline_source = 'tasks'

    # ── Build time_data dict ───────────────────────────────────────────────────
    time_data = None
    if latest_prediction:
        predicted_date = latest_prediction.predicted_completion_date

        # Compute genuine variance only when both dates are available
        if effective_deadline and predicted_date:
            variance_days = (effective_deadline - predicted_date).days
        else:
            variance_days = None  # cannot compute without both dates

        time_data = {
            'target_date': effective_deadline.strftime('%Y-%m-%d') if effective_deadline else None,
            'predicted_date': predicted_date.strftime('%Y-%m-%d') if predicted_date else None,
            'days_ahead_behind': variance_days,
            'risk_level': latest_prediction.risk_level,
            'delay_probability': float(latest_prediction.delay_probability or 0),
            'velocity_tasks_per_week': float(
                latest_prediction.current_velocity) if latest_prediction.current_velocity else 0,
            'will_meet_target': latest_prediction.will_meet_target if effective_deadline else None,
            'confidence_pct': latest_prediction.confidence_percentage,
            'deadline_source': deadline_source,
        }
    elif effective_deadline:
        # We have a deadline but no burndown prediction yet
        time_data = {
            'target_date': effective_deadline.strftime('%Y-%m-%d'),
            'predicted_date': None,
            'days_ahead_behind': None,
            'risk_level': None,
            'delay_probability': None,
            'velocity_tasks_per_week': 0,
            'will_meet_target': None,
            'confidence_pct': None,
            'deadline_source': deadline_source,
        }

    # Latest velocity snapshot
    latest_velocity = TeamVelocitySnapshot.objects.filter(
        board=board
    ).order_by('-period_end').first()
    velocity_tasks_per_week = float(latest_velocity.tasks_completed) if latest_velocity else 0

    # What-if coefficients
    what_if = {
        'avg_cost_per_task': avg_cost_per_task,
        'velocity_tasks_per_week': velocity_tasks_per_week or 1,
        'total_tasks': total_tasks,
        'allocated_budget': budget_data['allocated_budget'] if budget_data else 0,
        # Coerce None to 0 for the JS simulator (None means no target, not "right on schedule")
        'days_ahead_behind': (time_data.get('days_ahead_behind') or 0) if time_data else 0,
    }

    # ── Status labels ──────────────────────────────────────────────────────────
    def scope_status_label(change_pct):
        if change_pct is None:
            return 'unknown'
        if change_pct <= 10:
            return 'on-track'
        if change_pct <= 25:
            return 'at-risk'
        return 'over'

    def budget_status_label(utilization):
        if utilization is None:
            return 'unknown'
        if utilization <= 80:
            return 'on-track'
        if utilization <= 95:
            return 'at-risk'
        return 'over'

    def time_status_label(td):
        """Requires both a target AND a predicted date to compute a meaningful status."""
        if td is None:
            return 'unknown'
        if td.get('target_date') is None:
            return 'no-target'
        if td.get('predicted_date') is None:
            return 'unknown'
        days = td.get('days_ahead_behind')
        if days is None:
            return 'unknown'
        if days >= 0:
            return 'on-track'
        if days >= -7:
            return 'at-risk'
        return 'over'

    scope_label = scope_status_label(
        scope_status.get('scope_change_percentage') if scope_status else None
    )
    budget_label = budget_status_label(
        budget_data['utilization_pct'] if budget_data else None
    )
    time_label = time_status_label(time_data)

    # ── AI Analysis (POST action=ai_analyze) ──────────────────────────────────
    ai_result = None
    ai_error = None
    if request.method == 'POST' and request.POST.get('action') == 'ai_analyze':
        try:
            ai_result = analyze_triple_constraints(
                board=board,
                scope_data=scope_status,
                budget_data=budget_data,
                time_data=time_data,
            )
            if 'error' in ai_result:
                ai_error = ai_result['error']
        except Exception as e:
            logger.error('Triple constraint AI view error: %s', e)
            ai_error = 'AI analysis failed. Please check your API key and try again.'

    context = {
        'board': board,
        # Scope
        'scope_status': scope_status,
        'has_baseline': has_baseline,
        'total_tasks': total_tasks,
        'total_complexity': total_complexity,
        'scope_label': scope_label,
        # Budget
        'budget': budget,
        'budget_data': budget_data,
        'budget_label': budget_label,
        # Time
        'latest_prediction': latest_prediction,
        'time_data': time_data,
        'time_label': time_label,
        'effective_deadline': effective_deadline,
        'deadline_source': deadline_source,
        # What-if coefficients
        'what_if': what_if,
        # AI
        'ai_result': ai_result,
        'ai_error': ai_error,
    }

    return render(request, 'kanban/triple_constraint_dashboard.html', context)

