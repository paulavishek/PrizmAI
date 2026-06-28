"""
PrizmDiscovery Views.

RBAC summary (per PrizmAI RBAC and user flag conventions):
  - Viewers (is_viewer flag on the org workspace membership):
        Can READ the ideas inbox, idea detail, and matrix.
        CANNOT submit ideas, comment, change stage, score, or promote.
  - Members / any org user:
        Can READ + submit new ideas + comment on ideas.
  - Org Admin (profile.is_admin):
        Full access — approve / reject / promote ideas.
  - Lean tier:
        Redirected to upgrade prompt on any Discovery URL.

All views:
  1. Require @login_required
  2. Verify features.show_discovery (via org preset)
  3. Scope to request.user.profile.organization
"""
import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from kanban.preset_models import build_feature_flags

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_features(user):
    """Return the feature flags dict for the user's active-workspace preset."""
    try:
        ws = user.profile.active_workspace
        if ws is None:
            return build_feature_flags('lean')
        preset = ws.workspace_preset.global_preset
        return build_feature_flags(preset)
    except Exception:
        return build_feature_flags('lean')


def _require_discovery(request):
    """
    Return (org, features, None) if discovery is enabled and the user has an org.
    Return (None, None, HttpResponse) if access is blocked (redirect or 403).
    """
    # Scope org is derived from the active workspace (the tenant boundary),
    # falling back to the profile's org.  Behaviour-preserving: each owned
    # workspace lives under the user's own org.
    profile = getattr(request.user, 'profile', None)
    active_ws = getattr(profile, 'active_workspace', None)
    org = getattr(active_ws, 'organization', None) or getattr(profile, 'organization', None)
    features = _get_features(request.user)

    if not features.get('show_discovery'):
        messages.warning(
            request,
            'PrizmDiscovery is available on Professional and Enterprise plans. '
            'Upgrade your workspace in Settings to unlock it.',
        )
        return None, None, redirect('dashboard')

    if org is None:
        messages.warning(request, 'You need an organisation to use PrizmDiscovery.')
        return None, None, redirect('dashboard')

    return org, features, None


def _is_org_admin(user):
    """True if the user is an org admin (can approve/reject/promote).
    In demo/sandbox mode RBAC is disabled so all sandbox users get admin access.
    """
    try:
        profile = user.profile
        if user.is_superuser:
            return True
        if profile.is_admin:
            return True
        # Demo sandbox: RBAC disabled — treat user as admin so they can explore
        if getattr(profile, 'is_viewing_demo', False):
            return True
        return False
    except Exception:
        return False


def _is_viewer(user, org):
    """
    True if the user has the 'viewer' role at the workspace level.
    Viewers are read-only: they cannot submit, comment, stage-change, score, or promote.
    """
    try:
        from kanban.models import WorkspaceMembership
        membership = WorkspaceMembership.objects.filter(
            user=user, workspace__organization=org
        ).first()
        if membership:
            return getattr(membership, 'role', None) == 'viewer'
    except Exception:
        pass
    return False


def _demo_owner_filter(org, user):
    """Extra ORM filter that isolates per-user demo idea clones.

    Discovery ideas are organization-scoped, but in the demo org each user gets
    their own cloned set (sandbox_owner=user) — mirroring the per-user board
    copies. Scope every read/write to the current user's copies so nothing
    bleeds between demo users. Real orgs have no sandbox_owner, so no extra
    filter is applied there.
    """
    if getattr(org, 'is_demo', False):
        return {'sandbox_owner': user}
    return {}


def _idea_scope(request):
    """ORM filter kwargs scoping DiscoveryIdea queries to the active WORKSPACE.

    Workspace is the tenant boundary now (org is retired from access scoping).
    In the shared demo workspace, per-user isolation is still enforced via
    ``sandbox_owner`` (mirrors the per-user board copies).
    """
    profile = getattr(request.user, 'profile', None)
    ws = getattr(profile, 'active_workspace', None)
    scope = {'workspace': ws}
    if getattr(ws, 'is_demo', False) or getattr(profile, 'is_viewing_demo', False):
        scope['sandbox_owner'] = request.user
    return scope


# ── Views ─────────────────────────────────────────────────────────────────────

@login_required
def discovery_dashboard(request):
    """
    Main ideas inbox. Shows all ideas for the user's org filtered by stage tab.
    Includes 'ideas_to_score' and 'ideas_to_promote' counts for the dashboard widget.
    """
    from kanban.discovery_models import DiscoveryIdea

    org, features, blocked = _require_discovery(request)
    if blocked:
        return blocked

    scope = _idea_scope(request)

    stage_filter = request.GET.get('stage', 'all')
    qs = DiscoveryIdea.objects.filter(**scope).select_related(
        'submitted_by', 'promotion__board'
    )
    if stage_filter != 'all':
        qs = qs.filter(stage=stage_filter)

    ideas_to_score = DiscoveryIdea.objects.filter(
        stage__in=['new', 'under_review'], ai_score_impact__isnull=True,
        **scope,
    ).count()
    ideas_to_promote = DiscoveryIdea.objects.filter(
        stage='approved', **scope,
    ).exclude(promotion__isnull=False).count()

    is_admin = _is_org_admin(request.user)
    is_viewer = _is_viewer(request.user, org)

    stage_counts = {}
    for s, _ in [('new', ''), ('under_review', ''), ('approved', ''), ('rejected', '')]:
        stage_counts[s] = DiscoveryIdea.objects.filter(
            stage=s, **scope,
        ).count()

    return render(request, 'kanban/discovery_dashboard.html', {
        'ideas': qs,
        'stage_filter': stage_filter,
        'stage_counts': stage_counts,
        'ideas_to_score': ideas_to_score,
        'ideas_to_promote': ideas_to_promote,
        'is_admin': is_admin,
        'is_viewer': is_viewer,
        'features': features,
        'org': org,
    })


@login_required
def idea_detail(request, idea_id):
    """Full idea detail: metadata, AI score card, comment thread, promotion info."""
    from kanban.discovery_models import DiscoveryIdea, IdeaComment

    org, features, blocked = _require_discovery(request)
    if blocked:
        return blocked

    idea = get_object_or_404(
        DiscoveryIdea, pk=idea_id,
        **_idea_scope(request),
    )
    comments = IdeaComment.objects.filter(idea=idea).select_related('author')
    promotion = getattr(idea, 'promotion', None)

    is_admin = _is_org_admin(request.user)
    is_viewer = _is_viewer(request.user, org)

    # Boards available for the promote form.
    # In demo mode each user has their own sandbox copies — scope to the current
    # user's owned boards so we don't leak other users' sandbox boards.
    from kanban.models import Board
    demo_mode = getattr(getattr(request.user, 'profile', None), 'is_viewing_demo', False)
    if demo_mode:
        org_boards = Board.objects.filter(
            owner=request.user, is_sandbox_copy=True, is_archived=False
        ).order_by('name').values('id', 'name', 'num_phases')
    else:
        from kanban.utils.demo_protection import get_user_boards
        org_boards = get_user_boards(request.user).filter(
            is_archived=False
        ).order_by('name').values('id', 'name', 'num_phases')

    # Columns per board for the promote form's "Target Column" dropdown, so the
    # user can drop the new task straight into the right column (e.g. To Do)
    # rather than always landing in the auto-detected intake column.
    import json
    from kanban.models import Column
    org_boards = list(org_boards)
    board_columns = {}
    for col in (
        Column.objects.filter(board_id__in=[b['id'] for b in org_boards])
        .order_by('position').values('id', 'name', 'board_id')
    ):
        board_columns.setdefault(col['board_id'], []).append([col['id'], col['name']])

    return render(request, 'kanban/idea_detail.html', {
        'idea': idea,
        'comments': comments,
        'promotion': promotion,
        'is_admin': is_admin,
        'is_viewer': is_viewer,
        'features': features,
        'org': org,
        'org_boards': org_boards,
        'board_columns_json': json.dumps(board_columns),
    })


@login_required
def idea_create(request):
    """Submit a new idea. Viewers cannot access this view."""
    from kanban.discovery_models import DiscoveryIdea

    org, features, blocked = _require_discovery(request)
    if blocked:
        return blocked

    if _is_viewer(request.user, org):
        messages.error(request, 'Viewers cannot submit ideas.')
        return redirect('discovery_dashboard')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        source = request.POST.get('source', 'other')
        from kanban.discovery_models import IDEA_SOURCE_CHOICES
        valid_sources = {c[0] for c in IDEA_SOURCE_CHOICES}
        if source not in valid_sources:
            source = 'other'

        if not title:
            messages.error(request, 'Title is required.')
            return render(request, 'kanban/idea_form.html', {
                'action': 'create', 'features': features, 'org': org,
            })

        idea = DiscoveryIdea.objects.create(
            organization=org,
            workspace=getattr(getattr(request.user, 'profile', None), 'active_workspace', None),
            title=title,
            description=description,
            source=source,
            stage='new',
            submitted_by=request.user,
            # In demo mode, ideas the user submits belong to their private
            # sandbox set so they don't leak to other demo users.
            **_demo_owner_filter(org, request.user),
        )
        messages.success(request, f'Idea "{idea.title}" submitted to the Discovery inbox.')
        return redirect('idea_detail', idea_id=idea.pk)

    from kanban.discovery_models import IDEA_SOURCE_CHOICES
    return render(request, 'kanban/idea_form.html', {
        'action': 'create',
        'source_choices': IDEA_SOURCE_CHOICES,
        'features': features,
        'org': org,
    })


@login_required
def idea_edit(request, idea_id):
    """Edit an existing idea. Viewers cannot edit. Only submitter or admin."""
    from kanban.discovery_models import DiscoveryIdea, IDEA_SOURCE_CHOICES

    org, features, blocked = _require_discovery(request)
    if blocked:
        return blocked

    idea = get_object_or_404(
        DiscoveryIdea, pk=idea_id,
        **_idea_scope(request),
    )

    is_admin = _is_org_admin(request.user)
    is_owner = idea.submitted_by == request.user

    if _is_viewer(request.user, org) or (not is_admin and not is_owner):
        messages.error(request, 'You do not have permission to edit this idea.')
        return redirect('idea_detail', idea_id=idea_id)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        source = request.POST.get('source', idea.source)

        if not title:
            messages.error(request, 'Title is required.')
        else:
            idea.title = title
            idea.description = description
            idea.source = source
            idea.save(update_fields=['title', 'description', 'source', 'updated_at'])
            messages.success(request, 'Idea updated.')
            return redirect('idea_detail', idea_id=idea.pk)

    return render(request, 'kanban/idea_form.html', {
        'action': 'edit',
        'idea': idea,
        'source_choices': IDEA_SOURCE_CHOICES,
        'features': features,
        'org': org,
    })


@login_required
@require_POST
def idea_update_stage(request, idea_id):
    """
    AJAX POST: change the stage of an idea.
    Only org admins can approve / reject.
    Any non-viewer member can move to 'under_review'.
    """
    from kanban.discovery_models import DiscoveryIdea

    org, features, blocked = _require_discovery(request)
    if blocked:
        return JsonResponse({'error': 'Discovery not available.'}, status=403)

    idea = get_object_or_404(
        DiscoveryIdea, pk=idea_id,
        **_idea_scope(request),
    )
    is_admin = _is_org_admin(request.user)
    is_viewer = _is_viewer(request.user, org)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = {}
    new_stage = data.get('stage', '')

    admin_only_stages = {'approved', 'rejected'}
    valid_stages = {'new', 'under_review', 'approved', 'rejected'}

    if new_stage not in valid_stages:
        return JsonResponse({'error': 'Invalid stage.'}, status=400)
    if is_viewer:
        return JsonResponse({'error': 'Viewers cannot change idea stage.'}, status=403)
    if new_stage in admin_only_stages and not is_admin:
        return JsonResponse({'error': 'Only org admins can approve or reject ideas.'}, status=403)

    idea.stage = new_stage
    idea.save(update_fields=['stage', 'updated_at'])
    return JsonResponse({'ok': True, 'stage': idea.stage, 'stage_display': idea.get_stage_display()})


@login_required
@require_POST
def idea_ai_score(request, idea_id):
    """
    POST: trigger Spectra AI scoring for a single idea.
    Saves the result on the DiscoveryIdea model and returns JSON.
    """
    from kanban.discovery_models import DiscoveryIdea
    from kanban.discovery_ai import DiscoveryAIScorer

    org, features, blocked = _require_discovery(request)
    if blocked:
        return JsonResponse({'error': 'Discovery not available.'}, status=403)

    if _is_viewer(request.user, org):
        return JsonResponse({'error': 'Viewers cannot trigger AI scoring.'}, status=403)

    idea = get_object_or_404(
        DiscoveryIdea, pk=idea_id,
        **_idea_scope(request),
    )

    scorer = DiscoveryAIScorer()
    result = scorer.score_idea(idea, org)

    idea.ai_score_impact = result['impact']
    idea.ai_score_effort = result['effort']
    idea.ai_score_confidence = result['confidence']
    idea.ai_score_recommendation = result.get('recommendation', '')
    idea.ai_score_reasoning = result.get('reasoning', '')
    idea.ai_scored_at = timezone.now()
    idea.save(update_fields=[
        'ai_score_impact', 'ai_score_effort', 'ai_score_confidence',
        'ai_score_recommendation', 'ai_score_reasoning', 'ai_scored_at', 'updated_at',
    ])

    return JsonResponse({
        'ok': True,
        'success': result.get('success', False),
        'impact': idea.ai_score_impact,
        'effort': idea.ai_score_effort,
        'confidence': idea.ai_score_confidence,
        'recommendation': idea.ai_score_recommendation,
        'reasoning': idea.ai_score_reasoning,
        'quadrant': idea.quadrant,
        'quadrant_label': idea.quadrant_label,
    })


@login_required
@require_POST
def idea_promote(request, idea_id):
    """
    POST: approve an idea and create an IdeaPromotion record.
    Only org admins can promote. Optionally links to a board_id from POST data.
    """
    from kanban.discovery_models import DiscoveryIdea, IdeaPromotion

    org, features, blocked = _require_discovery(request)
    if blocked:
        return JsonResponse({'error': 'Discovery not available.'}, status=403)

    if not _is_org_admin(request.user):
        return JsonResponse({'error': 'Only org admins can promote ideas.'}, status=403)

    idea = get_object_or_404(
        DiscoveryIdea, pk=idea_id,
        **_idea_scope(request),
    )

    board_id = request.POST.get('board_id') or None
    board = None
    if board_id:
        from kanban.models import Board
        demo_mode = getattr(getattr(request.user, 'profile', None), 'is_viewing_demo', False)
        if demo_mode:
            # Restrict to the current user's sandbox boards to prevent cross-user promotion
            board = Board.objects.filter(pk=board_id, owner=request.user, is_sandbox_copy=True).first()
        else:
            # Restrict to boards the user can access (workspace + membership)
            from kanban.utils.demo_protection import get_user_boards
            board = get_user_boards(request.user).filter(pk=board_id).first()

    # Optional phase for the promoted task. Ignore anything outside the board's
    # configured phase range so the task can't be put in a non-existent phase
    # (empty/None falls back to Unphased, preserving the original behaviour).
    phase = (request.POST.get('phase') or '').strip() or None
    if phase and board:
        import re as _re
        m = _re.fullmatch(r'Phase (\d+)', phase)
        if not (m and 1 <= int(m.group(1)) <= (board.num_phases or 0)):
            phase = None

    # Idempotent — if a promotion already exists, just update it
    promotion, _ = IdeaPromotion.objects.get_or_create(
        idea=idea,
        defaults={
            'board': board,
            'promoted_at': timezone.now(),
            'promoted_by': request.user,
        },
    )
    if board and not promotion.board:
        promotion.board = board
        promotion.save(update_fields=['board'])

    idea.stage = 'approved'
    idea.promoted_at = promotion.promoted_at
    idea.promoted_by = request.user
    idea.save(update_fields=['stage', 'promoted_at', 'promoted_by', 'updated_at'])

    # Create a Task on the target board so the idea surfaces as real work
    task = None
    if board:
        try:
            from kanban.models import Column, Task
            import re
            all_cols = list(Column.objects.filter(board=board).order_by('position'))
            # Honour an explicitly-chosen target column (must belong to this
            # board); otherwise fall back to the auto-detected intake column.
            target_col = None
            column_id = (request.POST.get('column_id') or '').strip()
            if column_id:
                target_col = next((c for c in all_cols if str(c.pk) == column_id), None)
            if target_col is None:
                _intake_names = re.compile(r'\b(to.?do|backlog|inbox|todo|open|new|ideas?|ready)\b', re.I)
                target_col = next((c for c in all_cols if _intake_names.search(c.name)), None) or (all_cols[0] if all_cols else None)
            if target_col:
                task = Task.objects.create(
                    title=idea.title,
                    description=(
                        f'Promoted from PrizmDiscovery.\n\n{idea.description}'
                        if idea.description
                        else 'Promoted from PrizmDiscovery.'
                    ),
                    column=target_col,
                    created_by=request.user,
                    position=Task.objects.filter(column=target_col).count(),
                    phase=phase,
                )
                promotion.tasks.add(task)
        except Exception as e:
            logger.warning('Could not create task for promoted idea %s: %s', idea.pk, e)

    return JsonResponse({
        'ok': True,
        'promotion_id': promotion.pk,
        'board_name': board.name if board else None,
        'task_id': task.pk if task else None,
    })


@login_required
def discovery_matrix(request):
    """
    2×2 impact vs effort matrix view.
    Scored ideas are plotted in quadrants.
    Unscored ideas appear in a grey 'Awaiting Score' list below the grid.
    """
    from kanban.discovery_models import DiscoveryIdea

    org, features, blocked = _require_discovery(request)
    if blocked:
        return blocked

    all_ideas = DiscoveryIdea.objects.filter(**_idea_scope(request))

    scored = all_ideas.filter(ai_score_impact__isnull=False)
    unscored = all_ideas.filter(ai_score_impact__isnull=True).exclude(stage='rejected')

    quadrants = {
        'quick_win': [],
        'strategic_bet': [],
        'fill_in': [],
        'deprioritize': [],
    }
    for idea in scored:
        q = idea.quadrant
        if q:
            quadrants[q].append(idea)

    is_viewer = _is_viewer(request.user, org)

    return render(request, 'kanban/discovery_matrix.html', {
        'quadrants': quadrants,
        'scored_list': list(scored),
        'unscored': unscored,
        'is_viewer': is_viewer,
        'features': features,
        'org': org,
    })


@login_required
@require_POST
def add_idea_comment(request, idea_id):
    """POST: add a comment to an idea. Viewers cannot comment."""
    from kanban.discovery_models import DiscoveryIdea, IdeaComment

    org, features, blocked = _require_discovery(request)
    if blocked:
        return JsonResponse({'error': 'Discovery not available.'}, status=403)

    if _is_viewer(request.user, org):
        return JsonResponse({'error': 'Viewers cannot comment on ideas.'}, status=403)

    idea = get_object_or_404(
        DiscoveryIdea, pk=idea_id,
        **_idea_scope(request),
    )

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = {}
    content = data.get('content', '').strip()

    if not content:
        return JsonResponse({'error': 'Comment cannot be empty.'}, status=400)

    comment = IdeaComment.objects.create(
        idea=idea,
        author=request.user,
        content=content,
    )
    return JsonResponse({
        'ok': True,
        'comment_id': comment.pk,
        'author': comment.author.get_full_name() or comment.author.username,
        'content': comment.content,
        'created_at': comment.created_at.isoformat(),
    })


@login_required
def board_discovery_link(request, board_id):
    """
    GET JSON: ideas promoted to a specific board.
    Used by the board AI Tools panel echo to show "N ideas promoted".
    """
    from kanban.discovery_models import IdeaPromotion
    from kanban.models import Board
    from kanban.simple_access import check_access_or_403
    from django.urls import reverse

    board = get_object_or_404(Board, pk=board_id)
    check_access_or_403(request.user, board)
    promotions = IdeaPromotion.objects.filter(board=board).select_related('idea')
    data = [
        {
            'idea_id': p.idea.pk,
            'title': p.idea.title,
            'promoted_at': p.promoted_at.isoformat() if p.promoted_at else None,
            'url': reverse('idea_detail', args=[p.idea.pk]),
        }
        for p in promotions
    ]
    return JsonResponse({'count': len(data), 'ideas': data})
