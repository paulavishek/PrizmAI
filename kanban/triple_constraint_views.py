"""
Triple Constraint Dashboard Views
Shows how Scope, Cost, and Time interact for a board and provides AI-powered
recommendations for the optimal project configuration.
"""
import logging

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Avg
from django.utils import timezone

from kanban.models import Board, Task
from kanban.budget_models import ProjectBudget, TaskCost
from kanban.burndown_models import BurndownPrediction, TeamVelocitySnapshot
from kanban.utils.triple_constraint_ai import analyze_triple_constraints

logger = logging.getLogger(__name__)


@login_required
def triple_constraint_dashboard(request, board_id):
    """
    Triple Constraint Dashboard – shows Scope / Cost / Time interplay.
    Triggers AI analysis on POST ?action=ai_analyze.
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

    # Average cost-per-task (for what-if coefficients)
    avg_cost_per_task = 0
    if budget_data and total_tasks > 0:
        avg_cost_per_task = round(budget_data['spent_amount'] / total_tasks, 2)

    # ── Time / Schedule ────────────────────────────────────────────────────────
    latest_prediction = BurndownPrediction.objects.filter(
        board=board
    ).order_by('-prediction_date').first()

    time_data = None
    if latest_prediction:
        time_data = {
            'target_date': (
                latest_prediction.target_completion_date.strftime('%Y-%m-%d')
                if latest_prediction.target_completion_date else 'Not set'
            ),
            'predicted_date': (
                latest_prediction.predicted_completion_date.strftime('%Y-%m-%d')
                if latest_prediction.predicted_completion_date else 'Not calculated'
            ),
            'days_ahead_behind': latest_prediction.days_ahead_behind_target or 0,
            'risk_level': latest_prediction.risk_level,
            'delay_probability': float(latest_prediction.delay_probability or 0),
            'velocity_tasks_per_week': (
                float(latest_prediction.current_velocity)
                if latest_prediction.current_velocity else 0
            ),
            'will_meet_target': latest_prediction.will_meet_target,
            'confidence_pct': latest_prediction.confidence_percentage,
        }

    # Latest velocity snapshot (for what-if coefficient)
    latest_velocity = TeamVelocitySnapshot.objects.filter(
        board=board
    ).order_by('-period_end').first()
    velocity_tasks_per_week = 0
    if latest_velocity:
        velocity_tasks_per_week = float(latest_velocity.tasks_completed or 0)

    # What-if coefficients (passed to JS for real-time slider simulation)
    what_if = {
        'avg_cost_per_task': avg_cost_per_task,
        'velocity_tasks_per_week': velocity_tasks_per_week or 1,  # avoid division by zero
        'total_tasks': total_tasks,
        'allocated_budget': budget_data['allocated_budget'] if budget_data else 0,
        'days_ahead_behind': time_data['days_ahead_behind'] if time_data else 0,
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

    def time_status_label(days):
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
    time_label = time_status_label(
        time_data['days_ahead_behind'] if time_data else None
    )

    # ── AI Analysis (POST only) ────────────────────────────────────────────────
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
        # What-if coefficients
        'what_if': what_if,
        # AI
        'ai_result': ai_result,
        'ai_error': ai_error,
    }

    return render(request, 'kanban/triple_constraint_dashboard.html', context)
