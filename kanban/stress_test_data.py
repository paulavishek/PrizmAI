"""
Stress Test Board Data Collector

Collects all live board data needed for the Red Team AI prompt.
Mirrors the data-gathering approach from premortem_views._collect_board_snapshot
but includes additional fields needed for stress testing.
"""
from datetime import date

from django.db.models import Count, Q
from django.utils import timezone

from kanban.models import Board, Task


def build_board_stress_test_data(board, user):
    """
    Collect all live board data for the stress test AI prompt.
    Returns a dictionary matching the keys used in build_stress_test_user_prompt.
    """
    tasks = Task.objects.filter(column__board=board, item_type='task')
    now = timezone.now()

    # Task counts
    total_tasks = tasks.count()

    # "Done" columns heuristic (same as premortem)
    done_q = Q(column__name__icontains='done') | Q(column__name__icontains='complete')
    completed_tasks = tasks.filter(done_q).count()
    overdue_tasks = tasks.filter(due_date__lt=now).exclude(done_q).count()
    unassigned_tasks = tasks.filter(assigned_to__isnull=True).count()
    high_priority_tasks = tasks.filter(priority__in=['high', 'urgent']).count()

    # Team members
    member_ids = set(board.members.values_list('id', flat=True))
    assignee_ids = set(
        tasks.filter(assigned_to__isnull=False)
        .values_list('assigned_to_id', flat=True)
        .distinct()
    )
    all_member_ids = member_ids | assignee_ids

    from django.contrib.auth import get_user_model
    User = get_user_model()
    team_members = User.objects.filter(id__in=all_member_ids)
    member_names = [
        u.get_full_name() or u.username for u in team_members
    ]
    member_count = len(all_member_ids)

    # Budget (from ProjectBudget model, same pattern as premortem)
    budget_info = None
    try:
        budget = board.budget  # OneToOneField reverse accessor
        allocated = float(budget.allocated_budget)
        spent = float(budget.get_spent_amount())
        budget_info = (
            f"{budget.currency} {allocated:,.2f} allocated, "
            f"{budget.currency} {spent:,.2f} spent "
            f"({budget.get_budget_utilization_percent():.0f}% used)"
        )
    except Exception:
        pass

    # Dates
    project_deadline = board.project_deadline
    earliest_start = (
        tasks.filter(start_date__isnull=False)
        .order_by('start_date')
        .values_list('start_date', flat=True)
        .first()
    )
    start_date = earliest_start or board.created_at.date()

    # Dependencies — tasks that have at least one dependency
    tasks_with_deps = tasks.filter(dependencies__isnull=False).distinct()
    dependency_count = tasks_with_deps.count()

    # Blocking dependencies — which tasks block which
    blocking_deps = []
    for task in tasks_with_deps.select_related('column').prefetch_related('dependencies')[:8]:
        for dep in task.dependencies.all()[:3]:
            blocking_deps.append({
                'task': task.title,
                'blocked_by': dep.title,
            })

    # Conflicts
    conflict_count = 0
    try:
        from kanban.conflict_models import ConflictDetection
        conflict_count = ConflictDetection.objects.filter(
            board=board, status='active'
        ).count()
    except Exception:
        pass

    # Column names
    column_names = list(board.columns.order_by('position').values_list('name', flat=True))

    # Pre-mortem count
    premortem_scenario_count = 0
    try:
        latest_premortem = board.pre_mortems.first()
        if latest_premortem and latest_premortem.analysis_json:
            scenarios = latest_premortem.analysis_json.get('failure_scenarios', [])
            premortem_scenario_count = len(scenarios)
    except Exception:
        pass

    # Previously applied vaccines (with descriptions for AI context)
    from kanban.stress_test_models import Vaccine, StressTestSession, StressTestScenario
    applied_vaccines = list(
        Vaccine.objects.filter(board=board, is_applied=True)
        .values_list('name', flat=True)
    )
    applied_vaccines_detail = list(
        Vaccine.objects.filter(board=board, is_applied=True)
        .values('name', 'description', 'effort_level')
    )

    # Previously addressed scenarios from all sessions
    addressed_scenarios = list(
        StressTestScenario.objects.filter(
            session__board=board, is_addressed=True
        ).values('title', 'attack_type', 'severity')
    )

    # Previous session immunity scores (most recent first, up to 5)
    previous_scores = list(
        StressTestSession.objects.filter(board=board)
        .select_related('immunity_score')
        .order_by('-created_at')[:5]
    )
    score_history = []
    for sess in previous_scores:
        try:
            score_history.append({
                'score': sess.immunity_score.overall,
                'band': sess.immunity_score.get_band(),
            })
        except Exception:
            pass

    # Assignee breakdown
    assignee_counts = (
        tasks.exclude(assigned_to=None)
        .values('assigned_to__username')
        .annotate(count=Count('id'))
    )
    assignee_breakdown = {
        row['assigned_to__username']: row['count']
        for row in assignee_counts
    }

    return {
        'name': board.name,
        'description': board.description or '',
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'overdue_tasks': overdue_tasks,
        'unassigned_tasks': unassigned_tasks,
        'high_priority_tasks': high_priority_tasks,
        'member_count': member_count,
        'member_names': member_names,
        'budget_info': budget_info,
        'start_date': str(start_date) if start_date else 'Not set',
        'project_deadline': str(project_deadline) if project_deadline else 'Not set',
        'conflict_count': conflict_count,
        'dependency_count': dependency_count,
        'column_names': column_names,
        'premortem_scenario_count': premortem_scenario_count,
        'applied_vaccines': applied_vaccines,
        'applied_vaccines_detail': applied_vaccines_detail,
        'addressed_scenarios': addressed_scenarios,
        'score_history': score_history,
        'assignee_breakdown': assignee_breakdown,
        'blocking_dependencies': blocking_deps,
    }
