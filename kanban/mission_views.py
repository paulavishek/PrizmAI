"""
Mission & Strategy views.

Hierarchy:   Goal → Mission (problem) → Strategy (solution) → Board → Task

Access policy (RBAC Phase 3 — Upward Visibility Rule):
  - View access: view_goal / view_mission / view_strategy predicates.
  - Edit/Delete: edit_goal / edit_mission / edit_strategy predicates.
  - Goal creation: OrgAdmin only.
  - Board Members can SEE parent Strategy/Mission/Goal names (read-only)
    but CANNOT edit strategic-level records.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from kanban.decorators import demo_write_guard
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from django.conf import settings as django_settings
from django.http import Http404
from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from kanban.favorite_views import is_user_favorite as _is_fav

from .models import (
    OrganizationGoal, Mission, Strategy, Board, Task,
    GoalVersion, MissionVersion, StrategyVersion,
    StrategicUpdate, StrategicFollower,
)
from .forms.strategic_forms import GoalEditForm, MissionEditForm, StrategyEditForm
from accounts.models import Organization
from django.contrib.auth.models import User

import logging
logger = logging.getLogger(__name__)


def _handle_edit_cascade(request, record, change_reason, level):
    """
    Post-edit cascade logic based on change_reason.

    minor_tweak     → notify followers only (soft message, no AI regen)
    scope_change    → notify board members + followers + trigger AI regeneration
    strategic_pivot → same as scope_change + Spectra warning about linked boards
    """
    level_display = level.capitalize()

    # --- Always notify followers (even for minor tweaks) ---
    try:
        from messaging.models import Notification
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(record)
        followers_qs = StrategicFollower.objects.filter(
            content_type=ct, object_id=record.pk,
        ).select_related('user')
        follower_users = {f.user for f in followers_qs}

        if change_reason == 'minor_tweak':
            notification_text = f'{level_display} "{record.name}" was updated (minor edit).'
            recipients = follower_users - {request.user}
        else:
            # scope_change / strategic_pivot — also notify board members
            board_members = set()
            if level == 'goal':
                boards = Board.objects.filter(strategy__mission__organization_goal=record)
            elif level == 'mission':
                boards = Board.objects.filter(strategy__mission=record)
            else:  # strategy
                boards = Board.objects.filter(strategy=record)

            for board in boards.select_related():
                board_members.update(User.objects.filter(board_memberships__board=board))

            notification_text = f'{level_display} "{record.name}" was updated — review impact.'
            recipients = (board_members | follower_users) - {request.user}

        for recipient in recipients:
            Notification.objects.create(
                recipient=recipient,
                sender=request.user,
                notification_type='ACTIVITY',
                text=notification_text,
                action_url=record.get_absolute_url(),
            )
    except Exception as e:
        logger.warning("Failed to send edit notifications: %s", e)

    # Minor tweaks don't need AI regeneration — stop here
    if change_reason == 'minor_tweak':
        return

    # Collect boards reference for strategic_pivot logging below
    if level == 'goal':
        boards = Board.objects.filter(strategy__mission__organization_goal=record)
    elif level == 'mission':
        boards = Board.objects.filter(strategy__mission=record)
    else:
        boards = Board.objects.filter(strategy=record)

    # Trigger AI summary regeneration at this level + one level above
    try:
        if level == 'strategy':
            from kanban.tasks.ai_summary_tasks import (
                generate_strategy_summary_task,
                generate_mission_summary_task,
            )
            generate_strategy_summary_task.delay(record.id)
            if record.mission_id:
                generate_mission_summary_task.delay(record.mission_id)
        elif level == 'mission':
            from kanban.tasks.ai_summary_tasks import (
                generate_mission_summary_task,
                generate_goal_summary_task,
            )
            generate_mission_summary_task.delay(record.id)
            if hasattr(record, 'organization_goal') and record.organization_goal_id:
                generate_goal_summary_task.delay(record.organization_goal_id)
        elif level == 'goal':
            from kanban.tasks.ai_summary_tasks import generate_goal_summary_task
            generate_goal_summary_task.delay(record.id)
    except Exception as e:
        logger.warning("Failed to trigger AI regeneration: %s", e)

    # Strategic pivot: generate warning about linked boards
    if change_reason == 'strategic_pivot':
        board_count = boards.count()
        if board_count > 0:
            logger.info(
                "[StrategicPivot] %s '%s' pivoted — %d linked boards may need review.",
                level, record.name, board_count,
            )


def _compute_health_score(board_ids):
    """
    Derive a 0–100 health score from boards using the same 4-dimension model
    as the exit-protocol Hospice Risk Score:
        velocity (30%), budget (25%), missed deadlines (25%), activity (20%).

    Higher = healthier.  Returns (health_score_int, completion_pct, total, done).
    When no boards / no tasks exist returns (None, 0, 0, 0).
    """
    if not board_ids:
        return None, 0, 0, 0

    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)

    # ---- Shared task stats ----
    all_tasks = Task.objects.filter(column__board_id__in=board_ids, item_type='task')
    total = all_tasks.count()
    if total == 0:
        return None, 0, 0, 0
    done = all_tasks.filter(progress=100).count()
    completion_pct = round(done / total * 100, 1)

    # ---- Dimension 1: Velocity (30%) ----
    velocity_factor = None
    try:
        from kanban.burndown_models import TeamVelocitySnapshot
        snapshots = (
            TeamVelocitySnapshot.objects
            .filter(board_id__in=board_ids)
            .order_by('-period_end')[:30]
        )
        if snapshots.count() >= 6:
            recent = list(snapshots[:6])
            baseline = list(snapshots[6:])
            avg_recent = sum(s.tasks_completed for s in recent) / len(recent)
            if baseline:
                avg_baseline = sum(s.tasks_completed for s in baseline) / len(baseline)
                if avg_baseline > 0:
                    decline = ((avg_baseline - avg_recent) / avg_baseline) * 100
                    velocity_factor = min(max(decline / 100, 0.0), 1.0)
    except Exception:
        pass

    # ---- Dimension 2: Budget (25%) ----
    budget_factor = None
    try:
        from kanban.budget_models import ProjectBudget
        budgets = ProjectBudget.objects.filter(board_id__in=board_ids)
        if budgets.exists():
            spend_ratios = []
            for b in budgets:
                spent = b.get_budget_utilization_percent()
                b_total = Task.objects.filter(column__board=b.board).count()
                b_done = Task.objects.filter(column__board=b.board, completed_at__isnull=False).count()
                b_pct = (b_done / b_total * 100) if b_total > 0 else 0
                if spent is not None:
                    spend_ratios.append((spent / 100) * (1 - b_pct / 100))
            if spend_ratios:
                budget_factor = min(max(sum(spend_ratios) / len(spend_ratios), 0.0), 1.0)
    except Exception:
        pass

    # ---- Dimension 3: Deadlines (25%) ----
    deadline_factor = None
    with_deadline = all_tasks.filter(due_date__isnull=False).count()
    if with_deadline > 0:
        missed = all_tasks.filter(
            due_date__lt=now, due_date__gte=thirty_days_ago,
            completed_at__isnull=True,
        ).count()
        deadline_factor = min(missed / max(with_deadline * 0.3, 3), 1.0)

    # ---- Dimension 4: Activity (20%) ----
    last_activity = (
        Task.objects.filter(column__board_id__in=board_ids)
        .order_by('-updated_at')
        .values_list('updated_at', flat=True)
        .first()
    )
    days_inactive = (now - last_activity).days if last_activity else 30
    activity_factor = min(days_inactive / 30, 1.0)

    # ---- Weighted score (same as exit_protocol) ----
    weights = {
        'velocity': (0.30, velocity_factor),
        'budget':   (0.25, budget_factor),
        'deadline': (0.25, deadline_factor),
        'activity': (0.20, activity_factor),
    }
    available = {k: v for k, v in weights.items() if v[1] is not None}
    if len(available) < 2:
        return round(completion_pct), completion_pct, total, done

    total_weight = sum(w for w, _ in available.values())
    risk_score = sum((w / total_weight) * f for w, f in available.values())
    risk_score = min(max(risk_score, 0.0), 1.0)

    health = round((1 - risk_score) * 100)
    return health, completion_pct, total, done


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
        'can_create_goal': request.user.groups.filter(name='OrgAdmin').exists(),
    })


@login_required
def goal_detail(request, goal_id):
    """Show a single Organization Goal with 4-tab layout, health score, versions, updates, followers."""
    goal = get_object_or_404(OrganizationGoal, id=goal_id)

    if not request.user.has_perm('prizmai.view_goal', goal):
        raise Http404
    linked_missions = goal.missions.all().annotate(
        strategy_count=Count('strategies', distinct=True),
        board_count=Count('strategies__boards', distinct=True),
    ).order_by('-created_at')

    # Missions not yet linked (for the link dropdown)
    all_missions = Mission.objects.exclude(organization_goal=goal).order_by('name')

    # --- Board IDs under this goal ---
    goal_board_ids = list(Board.objects.filter(
        strategy__mission__organization_goal=goal
    ).values_list('id', flat=True))

    # --- Health score (0-100) ---
    health_score, completion_pct, total_tasks, done_tasks = _compute_health_score(goal_board_ids)

    # --- Per-mission health (light version for mission cards) ---
    for m in linked_missions:
        m_bids = list(Board.objects.filter(strategy__mission=m).values_list('id', flat=True))
        m_health, m_pct, m_total, m_done = _compute_health_score(m_bids)
        m.health_score = m_health
        m.health_pct = m_pct
        m.health_total = m_total
        m.health_done = m_done

    # --- Version history ---
    versions = GoalVersion.objects.filter(goal=goal).order_by('-version_number')

    # --- Strategic updates ---
    goal_ct = ContentType.objects.get_for_model(OrganizationGoal)
    updates = StrategicUpdate.objects.filter(
        content_type=goal_ct, object_id=goal.id,
    ).select_related('author').order_by('-created_at')

    # --- Followers ---
    followers = StrategicFollower.objects.filter(
        content_type=goal_ct, object_id=goal.id,
    ).select_related('user')
    is_following = followers.filter(user=request.user).exists()

    # --- Stale AI indicator ---
    ai_is_stale = False
    if goal.ai_summary and goal.ai_summary_generated_at:
        ai_is_stale = goal.ai_summary_generated_at < goal.updated_at

    # --- Days remaining ---
    days_remaining = None
    days_remaining_abs = None
    if goal.target_date:
        delta = goal.target_date - timezone.now().date()
        days_remaining = delta.days
        days_remaining_abs = abs(days_remaining)

    # ── Goal-Aware Analytics: portfolio + proxy metrics ──
    from kanban.utils.analytics_helpers import get_portfolio_analytics
    from kanban.models import GoalProxyMetric
    portfolio = get_portfolio_analytics(goal, 'goal')
    proxy_metrics = GoalProxyMetric.objects.filter(goal=goal).order_by('display_order')

    return render(request, 'kanban/goal_detail.html', {
        # Shared skeleton context
        'record': goal,
        'page_title': goal.name,
        'header_class': 'goal-header',
        'level_name': 'goal',
        'health_score': health_score,
        'completion_pct': completion_pct,
        'total_tasks': total_tasks,
        'done_tasks': done_tasks,
        'versions': versions,
        'updates': updates,
        'updates_count': updates.count(),
        'followers': followers,
        'is_following': is_following,
        'ai_is_stale': ai_is_stale,
        'days_remaining': days_remaining,
        'days_remaining_abs': days_remaining_abs,
        # Goal-specific context
        'goal': goal,
        'linked_missions': linked_missions,
        'all_missions': all_missions,
        'favorite_type': 'goal',
        'is_favorited': _is_fav(request.user, 'goal', goal.pk),
        # Goal-Aware Analytics
        'portfolio': portfolio,
        'proxy_metrics': proxy_metrics,
        'portfolio_narrative': goal.portfolio_narrative,
        # RBAC context
        'can_edit': request.user.has_perm('prizmai.edit_goal', goal),
        'can_delete': request.user.has_perm('prizmai.edit_goal', goal),
        'can_create_child': request.user.has_perm('prizmai.edit_goal', goal) or getattr(getattr(request.user, 'profile', None), 'is_viewing_demo', False),
    })


@login_required
@demo_write_guard
def create_goal(request):
    """Create a new Organization Goal."""
    if not request.user.groups.filter(name='OrgAdmin').exists():
        messages.error(request, 'Only organization administrators can create goals.')
        return redirect('goal_list')

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

        # Auto-generate proxy metrics in background
        try:
            from kanban.tasks.ai_summary_tasks import generate_proxy_metrics_on_goal_creation
            generate_proxy_metrics_on_goal_creation.delay(goal.id)
        except Exception:
            pass  # Celery/Redis may be unavailable in dev

        messages.success(request, f'Organization Goal "{goal.name}" created successfully!')
        return redirect('goal_detail', goal_id=goal.id)

    return render(request, 'kanban/create_goal.html', {
        'organizations': organizations,
    })


@login_required
@demo_write_guard
def edit_goal(request, goal_id):
    """Edit an existing Organization Goal with version history."""
    goal = get_object_or_404(OrganizationGoal, id=goal_id)

    if not request.user.has_perm('prizmai.edit_goal', goal):
        messages.error(request, 'You do not have permission to edit this goal.')
        return redirect('goal_detail', goal_id=goal.id)

    organizations = Organization.objects.all().order_by('name')

    if request.method == 'POST':
        form = GoalEditForm(request.POST, instance=goal)
        if form.is_valid():
            change_reason = form.cleaned_data['change_reason']
            change_notes = form.cleaned_data['change_notes']

            # Snapshot current values BEFORE saving
            GoalVersion.objects.create(
                goal=goal,
                version_number=goal.version,
                name=goal.name,
                description=goal.description or '',
                target_date=goal.target_date,
                owner=goal.owner,
                changed_by=request.user,
                change_reason=change_reason,
                change_notes=change_notes,
            )

            # Save new values and increment version
            updated_goal = form.save(commit=False)
            updated_goal.version = goal.version + 1
            # Handle organization field separately (not in form)
            org_id = request.POST.get('organization', '').strip()
            updated_goal.organization = Organization.objects.filter(id=org_id).first() if org_id else goal.organization
            updated_goal.save()

            # Post-edit cascade logic
            _handle_edit_cascade(request, goal, change_reason, 'goal')

            messages.success(request, f'Organization Goal "{goal.name}" updated (v{goal.version}).')
            return redirect('goal_detail', goal_id=goal.id)
    else:
        form = GoalEditForm(instance=goal)

    return render(request, 'kanban/edit_goal.html', {
        'goal': goal,
        'form': form,
        'organizations': organizations,
    })


@login_required
@demo_write_guard
def delete_goal(request, goal_id):
    """Delete an Organization Goal. Linked Missions become unlinked (SET_NULL)."""
    goal = get_object_or_404(OrganizationGoal, id=goal_id)

    if not request.user.has_perm('prizmai.edit_goal', goal):
        messages.error(request, 'You do not have permission to delete this goal.')
        return redirect('goal_detail', goal_id=goal.id)

    if request.method == 'POST':
        name = goal.name
        goal.delete()
        messages.success(request, f'Organization Goal "{name}" has been deleted.')
        return redirect('goal_list')

    return render(request, 'kanban/delete_goal.html', {'goal': goal})


@login_required
@demo_write_guard
def set_mission_goal(request, mission_id):
    """POST: Set (or clear) the parent Goal for a Mission — from the Mission's own detail page."""
    mission = get_object_or_404(Mission, id=mission_id)

    if not request.user.has_perm('prizmai.edit_mission', mission):
        messages.error(request, 'You do not have permission to modify this mission.')
        return redirect('mission_detail', mission_id=mission.id)

    if request.method == 'POST':
        goal_id = request.POST.get('goal_id', '').strip()
        if goal_id:
            goal = get_object_or_404(OrganizationGoal, id=goal_id)
            mission.organization_goal = goal
            mission.save(update_fields=['organization_goal'])
            messages.success(request, f'Mission linked to goal "{goal.name}".')
        else:
            mission.organization_goal = None
            mission.save(update_fields=['organization_goal'])
            messages.success(request, 'Mission unlinked from its goal.')

    return redirect('mission_detail', mission_id=mission.id)


@login_required
@demo_write_guard
def link_mission_to_goal(request, goal_id):
    """Link an existing Mission to this Organization Goal."""
    goal = get_object_or_404(OrganizationGoal, id=goal_id)

    if not request.user.has_perm('prizmai.edit_goal', goal):
        messages.error(request, 'You do not have permission to modify this goal.')
        return redirect('goal_detail', goal_id=goal.id)

    if request.method == 'POST':
        mission_id = request.POST.get('mission_id')
        mission = get_object_or_404(Mission, id=mission_id)
        mission.organization_goal = goal
        mission.save(update_fields=['organization_goal'])
        messages.success(request, f'Mission "{mission.name}" linked to goal "{goal.name}".')

    return redirect('goal_detail', goal_id=goal.id)


@login_required
@demo_write_guard
def unlink_mission_from_goal(request, goal_id, mission_id):
    """Remove the link between a Mission and an Organization Goal."""
    goal = get_object_or_404(OrganizationGoal, id=goal_id)
    mission = get_object_or_404(Mission, id=mission_id, organization_goal=goal)

    if not request.user.has_perm('prizmai.edit_goal', goal):
        messages.error(request, 'You do not have permission to modify this goal.')
        return redirect('goal_detail', goal_id=goal.id)

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
    """Show missions filtered by current mode (sandbox/demo/real)."""
    from accounts.models import UserProfile
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = None

    demo_mode = getattr(profile, 'is_viewing_demo', False) if profile else False

    if demo_mode:
        # Sandbox: show only user-created non-demo missions
        missions = Mission.objects.filter(
            created_by=request.user, is_demo=False, is_seed_demo_data=False,
        )
    else:
        # Real workspace: show user's own missions (no demo)
        missions = Mission.objects.filter(
            created_by=request.user, is_demo=False, is_seed_demo_data=False,
        )

    missions = missions.select_related('organization_goal').annotate(
        strategy_count=Count('strategies', distinct=True),
        board_count=Count('strategies__boards', distinct=True),
    ).order_by('-created_at')

    return render(request, 'kanban/mission_list.html', {
        'missions': missions,
    })


@login_required
def mission_detail(request, mission_id):
    """Show a single mission with 4-tab layout, health score, versions, updates, followers."""
    mission = get_object_or_404(Mission.objects.select_related('organization_goal'), id=mission_id)

    if not request.user.has_perm('prizmai.view_mission', mission):
        raise Http404

    strategies = mission.strategies.all().annotate(
        board_count=Count('boards', distinct=True)
    ).order_by('-created_at')

    # --- Board IDs under this mission ---
    board_ids = list(Board.objects.filter(
        strategy__mission=mission
    ).values_list('id', flat=True))

    # --- Health score (0-100) ---
    health_score, completion_pct, total_tasks, done_tasks = _compute_health_score(board_ids)

    # --- Per-strategy health for the strategy cards ---
    strategy_tree = []
    for strategy in strategies:
        s_bids = list(Board.objects.filter(strategy=strategy).values_list('id', flat=True))
        s_health, s_pct, s_total, s_done = _compute_health_score(s_bids)
        s_boards = Board.objects.filter(strategy=strategy).order_by('name')
        board_items = []
        for b in s_boards:
            b_bids = [b.id]
            b_health, b_pct, b_total, b_done = _compute_health_score(b_bids)
            board_items.append({
                'board': b, 'total_tasks': b_total, 'done_tasks': b_done,
                'completion_pct': b_pct, 'health_score': b_health,
            })
        strategy_tree.append({
            'strategy': strategy,
            'boards': board_items,
            'board_count': len(board_items),
            'health_score': s_health,
            'total_tasks': s_total,
            'done_tasks': s_done,
            'completion_pct': s_pct,
        })

    # --- Strategy status breakdown (based on health-score thresholds) ---
    on_track_count = sum(1 for s in strategy_tree if s['health_score'] is not None and s['health_score'] >= 70)
    at_risk_count = sum(1 for s in strategy_tree if s['health_score'] is not None and 40 <= s['health_score'] < 70)
    off_track_count = sum(1 for s in strategy_tree if s['health_score'] is not None and s['health_score'] < 40)

    # --- Version history ---
    versions = MissionVersion.objects.filter(mission=mission).order_by('-version_number')

    # --- Strategic updates ---
    mission_ct = ContentType.objects.get_for_model(Mission)
    updates = StrategicUpdate.objects.filter(
        content_type=mission_ct, object_id=mission.id,
    ).select_related('author').order_by('-created_at')

    # --- Followers ---
    followers = StrategicFollower.objects.filter(
        content_type=mission_ct, object_id=mission.id,
    ).select_related('user')
    is_following = followers.filter(user=request.user).exists()

    # --- Stale AI indicator ---
    ai_is_stale = False
    if mission.ai_summary and mission.ai_summary_generated_at:
        ai_is_stale = mission.ai_summary_generated_at < mission.updated_at

    # --- Days remaining ---
    days_remaining = None
    days_remaining_abs = None
    if mission.due_date:
        delta = mission.due_date - timezone.now().date()
        days_remaining = delta.days
        days_remaining_abs = abs(days_remaining)

    # --- Pre-Mortem rollup ---
    from kanban.premortem_models import PreMortemAnalysis
    pm_analyses = (
        PreMortemAnalysis.objects
        .filter(board_id__in=board_ids)
        .select_related('board')
        .order_by('board_id', '-created_at')
    )
    premortem_boards = []
    seen_boards = set()
    for pm in pm_analyses:
        if pm.board_id not in seen_boards:
            seen_boards.add(pm.board_id)
            premortem_boards.append({
                'board': pm.board,
                'risk_level': pm.overall_risk_level,
                'created_at': pm.created_at,
            })
    unanalyzed_boards = Board.objects.filter(id__in=set(board_ids) - seen_boards)
    for b in unanalyzed_boards:
        premortem_boards.append({'board': b, 'risk_level': None, 'created_at': None})
    high_risk_count = sum(1 for b in premortem_boards if b['risk_level'] == 'high')

    # ── Goal-Aware Analytics: portfolio analytics ──
    from kanban.utils.analytics_helpers import get_portfolio_analytics
    portfolio = get_portfolio_analytics(mission, 'mission')

    return render(request, 'kanban/mission_detail.html', {
        # Shared skeleton context
        'record': mission,
        'page_title': mission.name,
        'header_class': 'mission-header',
        'level_name': 'mission',
        'health_score': health_score,
        'completion_pct': completion_pct,
        'total_tasks': total_tasks,
        'done_tasks': done_tasks,
        'versions': versions,
        'updates': updates,
        'updates_count': updates.count(),
        'followers': followers,
        'is_following': is_following,
        'ai_is_stale': ai_is_stale,
        'days_remaining': days_remaining,
        'days_remaining_abs': days_remaining_abs,
        # Mission-specific context
        'mission': mission,
        'strategies': strategies,
        'strategy_tree': strategy_tree,
        'on_track_count': on_track_count,
        'at_risk_count': at_risk_count,
        'off_track_count': off_track_count,
        'premortem_boards': premortem_boards,
        'premortem_high_risk_count': high_risk_count,
        'premortem_total_boards': len(premortem_boards),
        'favorite_type': 'mission',
        'is_favorited': _is_fav(request.user, 'mission', mission.pk),
        # Goal-Aware Analytics
        'portfolio': portfolio,
        'portfolio_narrative': mission.portfolio_narrative,
        # RBAC context
        'can_edit': request.user.has_perm('prizmai.edit_mission', mission),
        'can_delete': request.user.has_perm('prizmai.edit_mission', mission),
        'can_create_child': request.user.has_perm('prizmai.edit_mission', mission) or getattr(getattr(request.user, 'profile', None), 'is_viewing_demo', False),
        # All goals for the "Link to Goal" sidebar widget
        'all_goals': OrganizationGoal.objects.order_by('name'),
    })


@login_required
@demo_write_guard
def create_mission(request):
    """Create a new mission."""
    all_goals = OrganizationGoal.objects.order_by('name')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        status = request.POST.get('status', 'active')
        goal_id = request.POST.get('organization_goal_id', '').strip()

        if not name:
            messages.error(request, 'Mission name is required.')
            return render(request, 'kanban/create_mission.html', {
                'post': request.POST,
                'all_goals': all_goals,
            })

        organization_goal = None
        if goal_id:
            try:
                organization_goal = OrganizationGoal.objects.get(id=int(goal_id))
            except (OrganizationGoal.DoesNotExist, ValueError):
                pass

        mission = Mission.objects.create(
            name=name,
            description=description or None,
            status=status,
            organization_goal=organization_goal,
            created_by=request.user,
            owner=request.user,
        )
        messages.success(request, f'Mission "{mission.name}" created successfully!')
        return redirect('mission_detail', mission_id=mission.id)

    return render(request, 'kanban/create_mission.html', {'all_goals': all_goals})


@login_required
@demo_write_guard
def edit_mission(request, mission_id):
    """Edit an existing mission with version history."""
    mission = get_object_or_404(Mission, id=mission_id)

    if not request.user.has_perm('prizmai.edit_mission', mission):
        messages.error(request, 'You do not have permission to edit this mission.')
        return redirect('mission_detail', mission_id=mission.id)

    if request.method == 'POST':
        form = MissionEditForm(request.POST, instance=mission)
        if form.is_valid():
            change_reason = form.cleaned_data['change_reason']
            change_notes = form.cleaned_data['change_notes']

            # Snapshot current values BEFORE saving
            MissionVersion.objects.create(
                mission=mission,
                version_number=mission.version,
                name=mission.name,
                description=mission.description or '',
                due_date=mission.due_date,
                owner=mission.owner,
                changed_by=request.user,
                change_reason=change_reason,
                change_notes=change_notes,
            )

            # Save new values and increment version
            updated_mission = form.save(commit=False)
            updated_mission.version = mission.version + 1
            updated_mission.save()

            _handle_edit_cascade(request, mission, change_reason, 'mission')

            messages.success(request, f'Mission "{mission.name}" updated (v{mission.version}).')
            return redirect('mission_detail', mission_id=mission.id)
    else:
        form = MissionEditForm(instance=mission)

    return render(request, 'kanban/edit_mission.html', {
        'mission': mission,
        'form': form,
    })


@login_required
@demo_write_guard
def delete_mission(request, mission_id):
    """Delete a mission (and cascade-delete its strategies; boards become unlinked)."""
    mission = get_object_or_404(Mission, id=mission_id)

    if not request.user.has_perm('prizmai.edit_mission', mission):
        messages.error(request, 'You do not have permission to delete this mission.')
        return redirect('mission_list')

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
def strategy_detail_shortcut(request, strategy_id):
    """Top-level /strategies/<id>/ — redirect to the canonical nested URL."""
    strategy = get_object_or_404(Strategy, id=strategy_id)
    return redirect('strategy_detail', mission_id=strategy.mission_id, strategy_id=strategy.id)


@login_required
@demo_write_guard
def create_strategy(request, mission_id):
    """Create a strategy under a mission."""
    mission = get_object_or_404(Mission, id=mission_id)

    is_demo_viewer = getattr(getattr(request.user, 'profile', None), 'is_viewing_demo', False)
    if not is_demo_viewer and not request.user.has_perm('prizmai.edit_mission', mission):
        messages.error(request, 'You do not have permission to create strategies under this mission.')
        return redirect('mission_detail', mission_id=mission.id)

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
    """Show a strategy with 4-tab layout, health score, milestones, versions, updates, followers."""
    mission = get_object_or_404(Mission.objects.select_related('organization_goal'), id=mission_id)
    strategy = get_object_or_404(Strategy, id=strategy_id, mission=mission)

    if not request.user.has_perm('prizmai.view_strategy', strategy):
        raise Http404

    linked_boards = strategy.boards.all().order_by('-created_at')

    # All boards (for "link existing board" dropdown) — no restriction
    all_boards = Board.objects.exclude(strategy=strategy).order_by('name')

    # --- Board IDs under this strategy ---
    board_ids = list(linked_boards.values_list('id', flat=True))

    # --- Health score (0-100) ---
    health_score, completion_pct, total_tasks, done_tasks = _compute_health_score(board_ids)

    # --- Per-board health for board cards ---
    board_items = []
    for b in linked_boards:
        b_health, b_pct, b_total, b_done = _compute_health_score([b.id])
        overdue_count = Task.objects.filter(
            column__board=b, due_date__lt=timezone.now(),
            completed_at__isnull=True, item_type='task',
        ).count()
        member_count = b.memberships.count()
        board_items.append({
            'board': b, 'total_tasks': b_total, 'done_tasks': b_done,
            'completion_pct': b_pct, 'health_score': b_health,
            'overdue_count': overdue_count, 'member_count': member_count,
        })

    # --- Milestones ---
    from .models import Milestone
    milestones = strategy.milestones.all().order_by('due_date')
    milestones_missed = milestones.filter(status='missed').count()
    milestones_complete = milestones.filter(status='complete').count()
    milestones_pending = milestones.filter(status='pending').count()

    # --- Version history ---
    versions = StrategyVersion.objects.filter(strategy=strategy).order_by('-version_number')

    # --- Strategic updates ---
    strategy_ct = ContentType.objects.get_for_model(Strategy)
    updates = StrategicUpdate.objects.filter(
        content_type=strategy_ct, object_id=strategy.id,
    ).select_related('author').order_by('-created_at')

    # --- Followers ---
    followers = StrategicFollower.objects.filter(
        content_type=strategy_ct, object_id=strategy.id,
    ).select_related('user')
    is_following = followers.filter(user=request.user).exists()

    # --- Stale AI indicator ---
    ai_is_stale = False
    if strategy.ai_summary and strategy.ai_summary_generated_at:
        ai_is_stale = strategy.ai_summary_generated_at < strategy.updated_at

    # --- Days remaining ---
    days_remaining = None
    days_remaining_abs = None
    if strategy.due_date:
        delta = strategy.due_date - timezone.now().date()
        days_remaining = delta.days
        days_remaining_abs = abs(days_remaining)

    # ── Goal-Aware Analytics: portfolio analytics ──
    from kanban.utils.analytics_helpers import get_portfolio_analytics
    portfolio = get_portfolio_analytics(strategy, 'strategy')

    return render(request, 'kanban/strategy_detail.html', {
        # Shared skeleton context
        'record': strategy,
        'page_title': strategy.name,
        'header_class': 'strategy-header',
        'level_name': 'strategy',
        'health_score': health_score,
        'completion_pct': completion_pct,
        'total_tasks': total_tasks,
        'done_tasks': done_tasks,
        'versions': versions,
        'updates': updates,
        'updates_count': updates.count(),
        'followers': followers,
        'is_following': is_following,
        'ai_is_stale': ai_is_stale,
        'days_remaining': days_remaining,
        'days_remaining_abs': days_remaining_abs,
        # Strategy-specific context
        'mission': mission,
        'strategy': strategy,
        'linked_boards': linked_boards,
        'board_items': board_items,
        'all_boards': all_boards,
        'milestones': milestones,
        'milestones_missed': milestones_missed,
        'milestones_complete': milestones_complete,
        'milestones_pending': milestones_pending,
        # Goal-Aware Analytics
        'portfolio': portfolio,
        'portfolio_narrative': strategy.portfolio_narrative,
        # RBAC context
        'can_edit': request.user.has_perm('prizmai.edit_strategy', strategy),
        'can_delete': request.user.has_perm('prizmai.edit_strategy', strategy),
        'can_create_child': request.user.has_perm('prizmai.edit_strategy', strategy) or getattr(getattr(request.user, 'profile', None), 'is_viewing_demo', False),
    })


@login_required
@demo_write_guard
def edit_strategy(request, mission_id, strategy_id):
    """Edit an existing strategy with version history."""
    mission = get_object_or_404(Mission, id=mission_id)
    strategy = get_object_or_404(Strategy, id=strategy_id, mission=mission)

    if not request.user.has_perm('prizmai.edit_strategy', strategy):
        messages.error(request, 'You do not have permission to edit this strategy.')
        return redirect('strategy_detail', mission_id=mission.id, strategy_id=strategy.id)

    if request.method == 'POST':
        form = StrategyEditForm(request.POST, instance=strategy)
        if form.is_valid():
            change_reason = form.cleaned_data['change_reason']
            change_notes = form.cleaned_data['change_notes']

            # Snapshot current values BEFORE saving
            StrategyVersion.objects.create(
                strategy=strategy,
                version_number=strategy.version,
                name=strategy.name,
                description=strategy.description or '',
                due_date=strategy.due_date,
                owner=strategy.owner,
                changed_by=request.user,
                change_reason=change_reason,
                change_notes=change_notes,
            )

            # Save new values and increment version
            updated_strategy = form.save(commit=False)
            updated_strategy.version = strategy.version + 1
            updated_strategy.save()

            _handle_edit_cascade(request, strategy, change_reason, 'strategy')

            messages.success(request, f'Strategy "{strategy.name}" updated (v{strategy.version}).')
            return redirect('strategy_detail', mission_id=mission.id, strategy_id=strategy.id)
    else:
        form = StrategyEditForm(instance=strategy)

    return render(request, 'kanban/edit_strategy.html', {
        'mission': mission,
        'strategy': strategy,
        'form': form,
    })


@login_required
@demo_write_guard
def delete_strategy(request, mission_id, strategy_id):
    """Delete a strategy; boards linked to it become unlinked (SET_NULL)."""
    mission = get_object_or_404(Mission, id=mission_id)
    strategy = get_object_or_404(Strategy, id=strategy_id, mission=mission)

    if not request.user.has_perm('prizmai.edit_strategy', strategy):
        messages.error(request, 'You do not have permission to delete this strategy.')
        return redirect('strategy_detail', mission_id=mission.id, strategy_id=strategy.id)

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
@demo_write_guard
def link_board_to_strategy(request, mission_id, strategy_id):
    """Link an existing board to this strategy (AJAX-friendly POST)."""
    mission = get_object_or_404(Mission, id=mission_id)
    strategy = get_object_or_404(Strategy, id=strategy_id, mission=mission)

    if not request.user.has_perm('prizmai.edit_strategy', strategy):
        messages.error(request, 'You do not have permission to modify this strategy.')
        return redirect('strategy_detail', mission_id=mission.id, strategy_id=strategy.id)

    if request.method == 'POST':
        board_id = request.POST.get('board_id')
        board = get_object_or_404(Board, id=board_id)
        board.strategy = strategy
        board.save(update_fields=['strategy'])
        messages.success(request, f'Board "{board.name}" linked to strategy "{strategy.name}".')

    return redirect('strategy_detail', mission_id=mission.id, strategy_id=strategy.id)


@login_required
@demo_write_guard
def unlink_board_from_strategy(request, mission_id, strategy_id, board_id):
    """Remove the link between a board and a strategy."""
    mission = get_object_or_404(Mission, id=mission_id)
    strategy = get_object_or_404(Strategy, id=strategy_id, mission=mission)
    board = get_object_or_404(Board, id=board_id, strategy=strategy)

    if not request.user.has_perm('prizmai.edit_strategy', strategy):
        messages.error(request, 'You do not have permission to modify this strategy.')
        return redirect('strategy_detail', mission_id=mission.id, strategy_id=strategy.id)

    if request.method == 'POST':
        board.strategy = None
        board.save(update_fields=['strategy'])
        messages.success(request, f'Board "{board.name}" unlinked from strategy.')

    return redirect('strategy_detail', mission_id=mission.id, strategy_id=strategy.id)


# ---------------------------------------------------------------------------
# AJAX endpoints — shared across Goal / Mission / Strategy
# ---------------------------------------------------------------------------

_LEVEL_MODELS = {
    'goal': OrganizationGoal,
    'mission': Mission,
    'strategy': Strategy,
}

_LEVEL_EDIT_PERM = {
    'goal': 'prizmai.edit_goal',
    'mission': 'prizmai.edit_mission',
    'strategy': 'prizmai.edit_strategy',
}


@login_required
def post_strategic_update(request, level, pk):
    """AJAX POST — create a StrategicUpdate for any level (goal/mission/strategy)."""
    from django.http import JsonResponse
    from django.template.loader import render_to_string

    model_cls = _LEVEL_MODELS.get(level)
    if model_cls is None:
        return JsonResponse({'success': False, 'error': 'Invalid level.'}, status=400)

    record = get_object_or_404(model_cls, pk=pk)

    edit_perm = _LEVEL_EDIT_PERM.get(level)
    if edit_perm and not request.user.has_perm(edit_perm, record):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required.'}, status=405)

    status_val = request.POST.get('status', '').strip()
    message = request.POST.get('message', '').strip()

    valid_statuses = {c[0] for c in StrategicUpdate.STATUS_CHOICES}
    if status_val not in valid_statuses:
        return JsonResponse({'success': False, 'error': 'Invalid status.'}, status=400)
    if not message:
        return JsonResponse({'success': False, 'error': 'Message is required.'}, status=400)
    if len(message) > 500:
        return JsonResponse({'success': False, 'error': 'Message must be 500 characters or fewer.'}, status=400)

    ct = ContentType.objects.get_for_model(record)
    update = StrategicUpdate.objects.create(
        content_type=ct,
        object_id=record.pk,
        status=status_val,
        message=message,
        author=request.user,
    )

    count = StrategicUpdate.objects.filter(content_type=ct, object_id=record.pk).count()

    html = render_to_string('kanban/partials/_update_entry.html', {'u': update}, request=request)

    return JsonResponse({'success': True, 'html': html, 'count': count})


@login_required
def toggle_follow(request, level, pk):
    """AJAX POST/DELETE — follow or unfollow any level."""
    from django.http import JsonResponse

    model_cls = _LEVEL_MODELS.get(level)
    if model_cls is None:
        return JsonResponse({'success': False, 'error': 'Invalid level.'}, status=400)

    record = get_object_or_404(model_cls, pk=pk)
    ct = ContentType.objects.get_for_model(record)

    if request.method == 'POST':
        StrategicFollower.objects.get_or_create(
            content_type=ct, object_id=record.pk, user=request.user,
        )
    elif request.method == 'DELETE':
        StrategicFollower.objects.filter(
            content_type=ct, object_id=record.pk, user=request.user,
        ).delete()
    else:
        return JsonResponse({'success': False, 'error': 'POST or DELETE required.'}, status=405)

    count = StrategicFollower.objects.filter(content_type=ct, object_id=record.pk).count()
    return JsonResponse({'success': True, 'count': count})


@login_required
def regenerate_summary(request, level, pk):
    """AJAX POST — trigger Celery task to regenerate AI summary for any level."""
    from django.http import JsonResponse

    model_cls = _LEVEL_MODELS.get(level)
    if model_cls is None:
        return JsonResponse({'success': False, 'error': 'Invalid level.'}, status=400)

    get_object_or_404(model_cls, pk=pk)  # existence check

    record = model_cls.objects.get(pk=pk)
    edit_perm = _LEVEL_EDIT_PERM.get(level)
    if edit_perm and not request.user.has_perm(edit_perm, record):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required.'}, status=405)

    try:
        if level == 'goal':
            from kanban.tasks.ai_summary_tasks import generate_goal_summary_task
            generate_goal_summary_task.delay(pk)
        elif level == 'mission':
            from kanban.tasks.ai_summary_tasks import generate_mission_summary_task
            generate_mission_summary_task.delay(pk)
        elif level == 'strategy':
            from kanban.tasks.ai_summary_tasks import generate_strategy_summary_task
            generate_strategy_summary_task.delay(pk)
    except Exception as e:
        logger.warning("Failed to enqueue AI regeneration for %s %s: %s", level, pk, e)
        return JsonResponse({'success': False, 'error': 'Failed to enqueue task.'}, status=500)

    return JsonResponse({'success': True})


# ---------------------------------------------------------------------------
# Strategic Membership Invite Views  (Phase 4)
# ---------------------------------------------------------------------------

@login_required
def invite_strategic_member(request, level, pk):
    """AJAX POST — invite a user to a Goal/Mission/Strategy with a given role."""
    from django.http import JsonResponse
    from kanban.models import StrategicMembership

    model_cls = _LEVEL_MODELS.get(level)
    if model_cls is None:
        return JsonResponse({'success': False, 'error': 'Invalid level.'}, status=400)

    record = get_object_or_404(model_cls, pk=pk)

    # Only the record owner / OrgAdmin can invite
    edit_perm = _LEVEL_EDIT_PERM.get(level)
    if edit_perm and not request.user.has_perm(edit_perm, record):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required.'}, status=405)

    user_id = request.POST.get('user_id')
    role = request.POST.get('role', 'member')

    if role not in ('owner', 'member', 'viewer'):
        return JsonResponse({'success': False, 'error': 'Invalid role.'}, status=400)

    try:
        target_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User not found.'}, status=404)

    ct = ContentType.objects.get_for_model(record)
    _, created = StrategicMembership.objects.get_or_create(
        content_type=ct, object_id=record.pk, user=target_user,
        defaults={'role': role},
    )
    if not created:
        # Update existing membership role
        StrategicMembership.objects.filter(
            content_type=ct, object_id=record.pk, user=target_user,
        ).update(role=role)

    return JsonResponse({
        'success': True,
        'created': created,
        'username': target_user.username,
        'role': role,
    })


@login_required
def remove_strategic_member(request, level, pk, user_id):
    """AJAX POST — remove a user's StrategicMembership."""
    from django.http import JsonResponse
    from kanban.models import StrategicMembership

    model_cls = _LEVEL_MODELS.get(level)
    if model_cls is None:
        return JsonResponse({'success': False, 'error': 'Invalid level.'}, status=400)

    record = get_object_or_404(model_cls, pk=pk)

    edit_perm = _LEVEL_EDIT_PERM.get(level)
    if edit_perm and not request.user.has_perm(edit_perm, record):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required.'}, status=405)

    ct = ContentType.objects.get_for_model(record)
    deleted, _ = StrategicMembership.objects.filter(
        content_type=ct, object_id=record.pk, user_id=user_id,
    ).delete()

    return JsonResponse({'success': True, 'deleted': deleted > 0})


@login_required
def list_strategic_members(request, level, pk):
    """AJAX GET — list StrategicMembership entries for a record."""
    from django.http import JsonResponse
    from kanban.models import StrategicMembership

    model_cls = _LEVEL_MODELS.get(level)
    if model_cls is None:
        return JsonResponse({'success': False, 'error': 'Invalid level.'}, status=400)

    record = get_object_or_404(model_cls, pk=pk)

    ct = ContentType.objects.get_for_model(record)
    members = StrategicMembership.objects.filter(
        content_type=ct, object_id=record.pk,
    ).select_related('user').order_by('role', 'user__username')

    data = [
        {
            'user_id': m.user_id,
            'username': m.user.username,
            'role': m.role,
        }
        for m in members
    ]

    return JsonResponse({'success': True, 'members': data})
