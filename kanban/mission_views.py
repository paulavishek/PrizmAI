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

from .models import OrganizationGoal, Mission, Strategy, Board
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
    """Show a single Organization Goal and its linked Missions."""
    goal = get_object_or_404(OrganizationGoal, id=goal_id)
    linked_missions = goal.missions.all().annotate(
        strategy_count=Count('strategies', distinct=True),
        board_count=Count('strategies__boards', distinct=True),
    ).order_by('-created_at')

    # All missions not yet linked to this goal (for the link dropdown)
    all_missions = Mission.objects.exclude(organization_goal=goal).order_by('name')

    return render(request, 'kanban/goal_detail.html', {
        'goal': goal,
        'linked_missions': linked_missions,
        'all_missions': all_missions,
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
    """Show a single mission and its strategies."""
    mission = get_object_or_404(Mission.objects.select_related('organization_goal'), id=mission_id)
    strategies = mission.strategies.all().annotate(
        board_count=Count('boards', distinct=True)
    ).order_by('-created_at')

    return render(request, 'kanban/mission_detail.html', {
        'mission': mission,
        'strategies': strategies,
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
