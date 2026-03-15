"""
Mission & Strategy views.

Hierarchy:   Mission (problem) → Strategy (solution) → Board → Task

Access policy: NO restrictions beyond simple login_required.
All authenticated users can view, create, edit and delete any mission or strategy.
This matches the same open-access model used for Boards in the rest of the app.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from django.conf import settings as django_settings
from datetime import timedelta

from .models import OrganizationGoal, Mission, Strategy, Board, Task
from accounts.models import Organization


# ---------------------------------------------------------------------------
# OrganizationGoal views  (apex of the hierarchy: Goal → Mission → Strategy → Board → Task)
# ---------------------------------------------------------------------------

@login_required
def goal_list(request):
    """Show all Organization Goals."""
    goals = OrganizationGoal.objects.all().annotate(
        mission_count=Count('missions', distinct=True),
    ).order_by('-created_at')

    return render(request, 'kanban/goal_list.html', {
        'goals': goals,
    })


@login_required
def goal_detail(request, goal_id):
    """Show a single Organization Goal and its linked Missions with health roll-ups."""
    goal = get_object_or_404(OrganizationGoal, id=goal_id)
    linked_missions = goal.missions.all().annotate(
        strategy_count=Count('strategies', distinct=True),
        board_count=Count('strategies__boards', distinct=True),
    ).order_by('-created_at')

    # All missions not yet linked to this goal (for the link dropdown)
    all_missions = Mission.objects.exclude(organization_goal=goal).order_by('name')

    # --- Health roll-up per mission ---
    _at_risk_days = getattr(django_settings, 'HEALTH_AT_RISK_DAYS_THRESHOLD', 3)
    _board_late_thresh = getattr(django_settings, 'HEALTH_BOARD_LATE_THRESHOLD', 0.20)
    _board_at_risk_thresh = getattr(django_settings, 'HEALTH_BOARD_AT_RISK_THRESHOLD', 0.20)
    _board_high_risk_thresh = getattr(django_settings, 'HEALTH_BOARD_HIGH_RISK_THRESHOLD', 0.30)
    _board_med_risk_thresh = getattr(django_settings, 'HEALTH_BOARD_MED_RISK_THRESHOLD', 0.10)
    _now = timezone.now()
    _at_risk_cutoff = _now + timedelta(days=_at_risk_days)

    # Gather board IDs for all missions under this goal
    _all_board_ids = list(Board.objects.filter(
        strategy__mission__organization_goal=goal
    ).values_list('id', flat=True))

    _active_qs = (
        Task.objects
        .filter(column__board_id__in=_all_board_ids, item_type='task')
        .exclude(progress=100)
        .values('column__board_id')
        .annotate(
            active_tasks=Count('id'),
            late_tasks=Count('id', filter=Q(due_date__lt=_now)),
            at_risk_tasks=Count('id', filter=Q(
                due_date__gte=_now, due_date__lte=_at_risk_cutoff, progress__lt=80,
            )),
            high_risk_tasks=Count('id', filter=Q(risk_level__in=['high', 'critical'])),
        )
    )
    _comp_qs = (
        Task.objects
        .filter(column__board_id__in=_all_board_ids, item_type='task')
        .values('column__board_id')
        .annotate(total_tasks=Count('id'), done_tasks=Count('id', filter=Q(progress=100)))
    )
    _comp_map = {r['column__board_id']: r for r in _comp_qs}
    _bstats = {}
    for row in _active_qs:
        bid = row['column__board_id']
        comp = _comp_map.get(bid, {})
        _bstats[bid] = {**row, 'total_tasks': comp.get('total_tasks', 0), 'done_tasks': comp.get('done_tasks', 0)}
    for bid, comp in _comp_map.items():
        if bid not in _bstats:
            _bstats[bid] = {
                'active_tasks': 0, 'late_tasks': 0, 'at_risk_tasks': 0, 'high_risk_tasks': 0,
                'total_tasks': comp.get('total_tasks', 0), 'done_tasks': comp.get('done_tasks', 0),
            }

    # Build per-mission health by aggregating boards under each mission's strategies
    mission_health_map = {}
    for m in linked_missions:
        m_board_ids = Board.objects.filter(strategy__mission=m).values_list('id', flat=True)
        m_total = 0; m_done = 0; m_active = 0; m_late = 0; m_at_risk = 0; m_high = 0
        for bid in m_board_ids:
            bs = _bstats.get(bid, {})
            m_total += bs.get('total_tasks', 0)
            m_done += bs.get('done_tasks', 0)
            m_active += bs.get('active_tasks', 0)
            m_late += bs.get('late_tasks', 0)
            m_at_risk += bs.get('at_risk_tasks', 0)
            m_high += bs.get('high_risk_tasks', 0)
        sched = 'on_track'
        if m_active > 0:
            if m_late / m_active > _board_late_thresh: sched = 'late'
            elif (m_late + m_at_risk) / m_active > _board_at_risk_thresh: sched = 'at_risk'
        risk = 'low'
        if m_active > 0:
            if m_high / m_active >= _board_high_risk_thresh: risk = 'high'
            elif m_high / m_active >= _board_med_risk_thresh: risk = 'medium'
        mission_health_map[m.id] = {
            'schedule_status': sched, 'risk_level': risk,
            'total_tasks': m_total, 'done_tasks': m_done,
            'completion_pct': round(m_done / m_total * 100, 1) if m_total else 0,
        }

    # Goal-level aggregate
    all_scheds = [v['schedule_status'] for v in mission_health_map.values()]
    all_risks = [v['risk_level'] for v in mission_health_map.values()]
    goal_schedule = 'on_track'
    if 'late' in all_scheds: goal_schedule = 'late'
    elif 'at_risk' in all_scheds: goal_schedule = 'at_risk'
    goal_risk = 'low'
    if 'high' in all_risks: goal_risk = 'high'
    elif 'medium' in all_risks: goal_risk = 'medium'
    goal_total = sum(v['total_tasks'] for v in mission_health_map.values())
    goal_done = sum(v['done_tasks'] for v in mission_health_map.values())
    goal_pct = round(goal_done / goal_total * 100, 1) if goal_total else 0

    # Attach health data directly to each mission for easy template access
    for m in linked_missions:
        h = mission_health_map.get(m.id, {})
        m.health_schedule = h.get('schedule_status', 'on_track')
        m.health_risk = h.get('risk_level', 'low')
        m.health_total = h.get('total_tasks', 0)
        m.health_done = h.get('done_tasks', 0)
        m.health_pct = h.get('completion_pct', 0)

    return render(request, 'kanban/goal_detail.html', {
        'goal': goal,
        'linked_missions': linked_missions,
        'all_missions': all_missions,
        'mission_health_map': mission_health_map,
        'goal_schedule_status': goal_schedule,
        'goal_risk_level': goal_risk,
        'goal_total_tasks': goal_total,
        'goal_done_tasks': goal_done,
        'goal_completion_pct': goal_pct,
    })


@login_required
def create_goal(request):
    """Create a new Organization Goal."""
    organizations = Organization.objects.all().order_by('name')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        target_metric = request.POST.get('target_metric', '').strip()
        target_date = request.POST.get('target_date', '').strip() or None
        status = request.POST.get('status', 'active')
        org_id = request.POST.get('organization', '').strip()

        if not name:
            messages.error(request, 'Goal name is required.')
            return render(request, 'kanban/create_goal.html', {
                'post': request.POST,
                'organizations': organizations,
            })

        organization = None
        if org_id:
            organization = Organization.objects.filter(id=org_id).first()

        goal = OrganizationGoal.objects.create(
            name=name,
            description=description or None,
            target_metric=target_metric or None,
            target_date=target_date,
            status=status,
            organization=organization,
            created_by=request.user,
        )
        messages.success(request, f'Organization Goal "{goal.name}" created successfully!')
        return redirect('goal_detail', goal_id=goal.id)

    return render(request, 'kanban/create_goal.html', {
        'organizations': organizations,
    })


@login_required
def edit_goal(request, goal_id):
    """Edit an existing Organization Goal."""
    goal = get_object_or_404(OrganizationGoal, id=goal_id)
    organizations = Organization.objects.all().order_by('name')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        target_metric = request.POST.get('target_metric', '').strip()
        target_date = request.POST.get('target_date', '').strip() or None
        status = request.POST.get('status', 'active')
        org_id = request.POST.get('organization', '').strip()

        if not name:
            messages.error(request, 'Goal name is required.')
            return render(request, 'kanban/edit_goal.html', {
                'goal': goal,
                'organizations': organizations,
            })

        goal.name = name
        goal.description = description or None
        goal.target_metric = target_metric or None
        goal.target_date = target_date
        goal.status = status
        goal.organization = Organization.objects.filter(id=org_id).first() if org_id else None
        goal.save()
        messages.success(request, f'Organization Goal "{goal.name}" updated.')
        return redirect('goal_detail', goal_id=goal.id)

    return render(request, 'kanban/edit_goal.html', {
        'goal': goal,
        'organizations': organizations,
    })


@login_required
def delete_goal(request, goal_id):
    """Delete an Organization Goal. Linked Missions become unlinked (SET_NULL)."""
    goal = get_object_or_404(OrganizationGoal, id=goal_id)

    if request.method == 'POST':
        name = goal.name
        goal.delete()
        messages.success(request, f'Organization Goal "{name}" has been deleted.')
        return redirect('goal_list')

    return render(request, 'kanban/delete_goal.html', {'goal': goal})


@login_required
def link_mission_to_goal(request, goal_id):
    """Link an existing Mission to this Organization Goal."""
    goal = get_object_or_404(OrganizationGoal, id=goal_id)

    if request.method == 'POST':
        mission_id = request.POST.get('mission_id')
        mission = get_object_or_404(Mission, id=mission_id)
        mission.organization_goal = goal
        mission.save(update_fields=['organization_goal'])
        messages.success(request, f'Mission "{mission.name}" linked to goal "{goal.name}".')

    return redirect('goal_detail', goal_id=goal.id)


@login_required
def unlink_mission_from_goal(request, goal_id, mission_id):
    """Remove the link between a Mission and an Organization Goal."""
    goal = get_object_or_404(OrganizationGoal, id=goal_id)
    mission = get_object_or_404(Mission, id=mission_id, organization_goal=goal)

    if request.method == 'POST':
        mission.organization_goal = None
        mission.save(update_fields=['organization_goal'])
        messages.success(request, f'Mission "{mission.name}" unlinked from goal.')

    return redirect('goal_detail', goal_id=goal.id)


# ---------------------------------------------------------------------------
# Mission views
# ---------------------------------------------------------------------------

@login_required
def mission_list(request):
    """Show all missions — no filtering, everyone sees everything (same as board list)."""
    missions = Mission.objects.select_related('organization_goal').all().annotate(
        strategy_count=Count('strategies', distinct=True),
        board_count=Count('strategies__boards', distinct=True),
    ).order_by('-created_at')

    return render(request, 'kanban/mission_list.html', {
        'missions': missions,
    })


@login_required
def mission_detail(request, mission_id):
    """Show a single mission and its strategies with health roll-ups."""
    mission = get_object_or_404(Mission.objects.select_related('organization_goal'), id=mission_id)
    strategies = mission.strategies.all().annotate(
        board_count=Count('boards', distinct=True)
    ).order_by('-created_at')

    # --- Health roll-up for strategies & boards under this mission ---
    board_ids = list(Board.objects.filter(
        strategy__mission=mission
    ).values_list('id', flat=True))

    _at_risk_days = getattr(django_settings, 'HEALTH_AT_RISK_DAYS_THRESHOLD', 3)
    _board_late_thresh = getattr(django_settings, 'HEALTH_BOARD_LATE_THRESHOLD', 0.20)
    _board_at_risk_thresh = getattr(django_settings, 'HEALTH_BOARD_AT_RISK_THRESHOLD', 0.20)
    _board_high_risk_thresh = getattr(django_settings, 'HEALTH_BOARD_HIGH_RISK_THRESHOLD', 0.30)
    _board_med_risk_thresh = getattr(django_settings, 'HEALTH_BOARD_MED_RISK_THRESHOLD', 0.10)
    _now = timezone.now()
    _at_risk_cutoff = _now + timedelta(days=_at_risk_days)

    _active_stats = (
        Task.objects
        .filter(column__board_id__in=board_ids, item_type='task')
        .exclude(progress=100)
        .values('column__board_id')
        .annotate(
            active_tasks=Count('id'),
            late_tasks=Count('id', filter=Q(due_date__lt=_now)),
            at_risk_tasks=Count('id', filter=Q(
                due_date__gte=_now, due_date__lte=_at_risk_cutoff, progress__lt=80,
            )),
            high_risk_tasks=Count('id', filter=Q(risk_level__in=['high', 'critical'])),
        )
    )
    _comp_stats = (
        Task.objects
        .filter(column__board_id__in=board_ids, item_type='task')
        .values('column__board_id')
        .annotate(
            total_tasks=Count('id'),
            done_tasks=Count('id', filter=Q(progress=100)),
        )
    )
    _comp_map = {r['column__board_id']: r for r in _comp_stats}
    _bstats_map = {}
    for row in _active_stats:
        bid = row['column__board_id']
        comp = _comp_map.get(bid, {})
        _bstats_map[bid] = {**row, 'total_tasks': comp.get('total_tasks', 0), 'done_tasks': comp.get('done_tasks', 0)}
    for bid, comp in _comp_map.items():
        if bid not in _bstats_map:
            _bstats_map[bid] = {
                'column__board_id': bid, 'active_tasks': 0, 'late_tasks': 0,
                'at_risk_tasks': 0, 'high_risk_tasks': 0,
                'total_tasks': comp.get('total_tasks', 0), 'done_tasks': comp.get('done_tasks', 0),
            }

    def _board_health(bs):
        active = bs.get('active_tasks', 0)
        late = bs.get('late_tasks', 0)
        at_risk = bs.get('at_risk_tasks', 0)
        high = bs.get('high_risk_tasks', 0)
        sched = 'on_track'
        if active > 0:
            if late / active > _board_late_thresh: sched = 'late'
            elif (late + at_risk) / active > _board_at_risk_thresh: sched = 'at_risk'
        risk = 'low'
        if active > 0:
            if high / active >= _board_high_risk_thresh: risk = 'high'
            elif high / active >= _board_med_risk_thresh: risk = 'medium'
        return sched, risk

    def _worst_sched(*s):
        if 'late' in s: return 'late'
        if 'at_risk' in s: return 'at_risk'
        return 'on_track'
    def _worst_risk(*r):
        if 'high' in r: return 'high'
        if 'medium' in r: return 'medium'
        return 'low'

    # Build strategy_tree with boards + health for the template
    strategy_tree = []
    for strategy in strategies:
        s_boards = Board.objects.filter(strategy=strategy).order_by('name')
        board_items = []
        for b in s_boards:
            bs = _bstats_map.get(b.id, {})
            total = bs.get('total_tasks', 0)
            done = bs.get('done_tasks', 0)
            pct = round(done / total * 100, 1) if total else 0
            b_sched, b_risk = _board_health(bs)
            board_items.append({
                'board': b, 'total_tasks': total, 'done_tasks': done,
                'completion_pct': pct, 'schedule_status': b_sched, 'risk_level': b_risk,
            })
        ss = [bi['schedule_status'] for bi in board_items]
        rs = [bi['risk_level'] for bi in board_items]
        strategy_tree.append({
            'strategy': strategy,
            'boards': board_items,
            'board_count': len(board_items),
            'schedule_status': _worst_sched(*ss) if ss else 'on_track',
            'risk_level': _worst_risk(*rs) if rs else 'low',
            'total_tasks': sum(bi['total_tasks'] for bi in board_items),
            'done_tasks': sum(bi['done_tasks'] for bi in board_items),
            'completion_pct': (
                round(sum(bi['done_tasks'] for bi in board_items) /
                      sum(bi['total_tasks'] for bi in board_items) * 100, 1)
                if sum(bi['total_tasks'] for bi in board_items) else 0
            ),
        })

    # Mission-level health
    m_ss = [s['schedule_status'] for s in strategy_tree]
    m_rs = [s['risk_level'] for s in strategy_tree]
    mission_schedule = _worst_sched(*m_ss) if m_ss else 'on_track'
    mission_risk = _worst_risk(*m_rs) if m_rs else 'low'
    mission_total = sum(s['total_tasks'] for s in strategy_tree)
    mission_done = sum(s['done_tasks'] for s in strategy_tree)
    mission_pct = round(mission_done / mission_total * 100, 1) if mission_total else 0

    # Pre-Mortem rollup: gather latest analysis per board under this mission
    from kanban.premortem_models import PreMortemAnalysis
    pm_analyses = (
        PreMortemAnalysis.objects
        .filter(board_id__in=board_ids)
        .select_related('board')
        .order_by('board_id', '-created_at')
    )
    premortem_boards = []
    seen_boards = set()
    all_board_ids = set(board_ids)
    for pm in pm_analyses:
        if pm.board_id not in seen_boards:
            seen_boards.add(pm.board_id)
            premortem_boards.append({
                'board': pm.board,
                'risk_level': pm.overall_risk_level,
                'created_at': pm.created_at,
            })
    unanalyzed_boards = Board.objects.filter(id__in=all_board_ids - seen_boards)
    for b in unanalyzed_boards:
        premortem_boards.append({'board': b, 'risk_level': None, 'created_at': None})
    high_risk_count = sum(1 for b in premortem_boards if b['risk_level'] == 'high')

    return render(request, 'kanban/mission_detail.html', {
        'mission': mission,
        'strategies': strategies,
        'strategy_tree': strategy_tree,
        'mission_schedule_status': mission_schedule,
        'mission_risk_level': mission_risk,
        'mission_total_tasks': mission_total,
        'mission_done_tasks': mission_done,
        'mission_completion_pct': mission_pct,
        'premortem_boards': premortem_boards,
        'premortem_high_risk_count': high_risk_count,
        'premortem_total_boards': len(premortem_boards),
    })


@login_required
def create_mission(request):
    """Create a new mission."""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        status = request.POST.get('status', 'active')

        if not name:
            messages.error(request, 'Mission name is required.')
            return render(request, 'kanban/create_mission.html', {
                'post': request.POST,
            })

        mission = Mission.objects.create(
            name=name,
            description=description or None,
            status=status,
            created_by=request.user,
        )
        messages.success(request, f'Mission "{mission.name}" created successfully!')
        return redirect('mission_detail', mission_id=mission.id)

    return render(request, 'kanban/create_mission.html', {})


@login_required
def edit_mission(request, mission_id):
    """Edit an existing mission."""
    mission = get_object_or_404(Mission, id=mission_id)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        status = request.POST.get('status', 'active')

        if not name:
            messages.error(request, 'Mission name is required.')
            return render(request, 'kanban/edit_mission.html', {'mission': mission})

        mission.name = name
        mission.description = description or None
        mission.status = status
        mission.save()
        messages.success(request, f'Mission "{mission.name}" updated.')
        return redirect('mission_detail', mission_id=mission.id)

    return render(request, 'kanban/edit_mission.html', {'mission': mission})


@login_required
def delete_mission(request, mission_id):
    """Delete a mission (and cascade-delete its strategies; boards become unlinked)."""
    mission = get_object_or_404(Mission, id=mission_id)

    if request.method == 'POST':
        name = mission.name
        # Boards FKed to strategies will have strategy set to NULL (SET_NULL) on cascade
        mission.delete()
        messages.success(request, f'Mission "{name}" has been deleted.')
        return redirect('mission_list')

    return render(request, 'kanban/delete_mission.html', {'mission': mission})


# ---------------------------------------------------------------------------
# Strategy views
# ---------------------------------------------------------------------------

@login_required
def create_strategy(request, mission_id):
    """Create a strategy under a mission."""
    mission = get_object_or_404(Mission, id=mission_id)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        status = request.POST.get('status', 'active')

        if not name:
            messages.error(request, 'Strategy name is required.')
            return render(request, 'kanban/create_strategy.html', {
                'mission': mission,
                'post': request.POST,
            })

        strategy = Strategy.objects.create(
            name=name,
            description=description or None,
            status=status,
            mission=mission,
            created_by=request.user,
        )
        messages.success(request, f'Strategy "{strategy.name}" created!')
        return redirect('strategy_detail', mission_id=mission.id, strategy_id=strategy.id)

    return render(request, 'kanban/create_strategy.html', {'mission': mission})


@login_required
def strategy_detail(request, mission_id, strategy_id):
    """Show a strategy and all boards linked to it."""
    mission = get_object_or_404(Mission, id=mission_id)
    strategy = get_object_or_404(Strategy, id=strategy_id, mission=mission)

    linked_boards = strategy.boards.all().order_by('-created_at')

    # All boards (for "link existing board" dropdown) — no restriction
    all_boards = Board.objects.exclude(strategy=strategy).order_by('name')

    return render(request, 'kanban/strategy_detail.html', {
        'mission': mission,
        'strategy': strategy,
        'linked_boards': linked_boards,
        'all_boards': all_boards,
    })


@login_required
def edit_strategy(request, mission_id, strategy_id):
    """Edit an existing strategy."""
    mission = get_object_or_404(Mission, id=mission_id)
    strategy = get_object_or_404(Strategy, id=strategy_id, mission=mission)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        status = request.POST.get('status', 'active')

        if not name:
            messages.error(request, 'Strategy name is required.')
            return render(request, 'kanban/edit_strategy.html', {
                'mission': mission,
                'strategy': strategy,
            })

        strategy.name = name
        strategy.description = description or None
        strategy.status = status
        strategy.save()
        messages.success(request, f'Strategy "{strategy.name}" updated.')
        return redirect('strategy_detail', mission_id=mission.id, strategy_id=strategy.id)

    return render(request, 'kanban/edit_strategy.html', {
        'mission': mission,
        'strategy': strategy,
    })


@login_required
def delete_strategy(request, mission_id, strategy_id):
    """Delete a strategy; boards linked to it become unlinked (SET_NULL)."""
    mission = get_object_or_404(Mission, id=mission_id)
    strategy = get_object_or_404(Strategy, id=strategy_id, mission=mission)

    if request.method == 'POST':
        name = strategy.name
        strategy.delete()
        messages.success(request, f'Strategy "{name}" has been deleted.')
        return redirect('mission_detail', mission_id=mission.id)

    return render(request, 'kanban/delete_strategy.html', {
        'mission': mission,
        'strategy': strategy,
    })


@login_required
def link_board_to_strategy(request, mission_id, strategy_id):
    """Link an existing board to this strategy (AJAX-friendly POST)."""
    mission = get_object_or_404(Mission, id=mission_id)
    strategy = get_object_or_404(Strategy, id=strategy_id, mission=mission)

    if request.method == 'POST':
        board_id = request.POST.get('board_id')
        board = get_object_or_404(Board, id=board_id)
        board.strategy = strategy
        board.save(update_fields=['strategy'])
        messages.success(request, f'Board "{board.name}" linked to strategy "{strategy.name}".')

    return redirect('strategy_detail', mission_id=mission.id, strategy_id=strategy.id)


@login_required
def unlink_board_from_strategy(request, mission_id, strategy_id, board_id):
    """Remove the link between a board and a strategy."""
    mission = get_object_or_404(Mission, id=mission_id)
    strategy = get_object_or_404(Strategy, id=strategy_id, mission=mission)
    board = get_object_or_404(Board, id=board_id, strategy=strategy)

    if request.method == 'POST':
        board.strategy = None
        board.save(update_fields=['strategy'])
        messages.success(request, f'Board "{board.name}" unlinked from strategy.')

    return redirect('strategy_detail', mission_id=mission.id, strategy_id=strategy.id)
