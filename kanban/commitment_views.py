"""
Living Commitment Protocol Views

Provides the dashboard, detail, create, betting, signal, and negotiation views
for the Living Commitment Protocols feature.
Follows the same patterns as kanban/whatif_views.py and kanban/shadow_views.py.
"""
import json
import logging
from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Avg

from kanban.decorators import demo_write_guard

from django.contrib.auth.models import User
from kanban.models import Board, Task
from kanban.commitment_models import (
    CommitmentProtocol,
    ConfidenceSignal,
    CommitmentBet,
    NegotiationSession,
    UserCredibilityScore,
)
from kanban.commitment_service import CommitmentService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Commitment Dashboard
# ---------------------------------------------------------------------------

@login_required
def commitment_dashboard(request, board_id):
    """
    Main dashboard for all active commitments on a board.
    Shows portfolio confidence, commitment cards, and health summary.
    """
    board = get_object_or_404(Board, id=board_id)

    # Preset guard: Commitments require Enterprise
    from kanban.preset_models import BoardPreset, build_feature_flags
    from django.contrib import messages as _msgs
    try:
        bp = BoardPreset.objects.get(board=board)
        flags = build_feature_flags(bp.effective_preset())
    except BoardPreset.DoesNotExist:
        flags = build_feature_flags('lean')
    if not flags.get('show_commitments'):
        _msgs.info(request, "Commitment Protocols are available in Enterprise mode. Upgrade your workspace to unlock them.")
        return redirect('board_detail', board_id=board.id)

    commitments = (
        CommitmentProtocol.objects.filter(board=board)
        .select_related('board', 'created_by')
        .prefetch_related('signals', 'bets')
        .order_by('status', 'target_date')
    )

    # Portfolio confidence = average of active commitments
    active = commitments.filter(status__in=['active', 'at_risk', 'critical'])
    avg_conf = active.aggregate(avg=Avg('current_confidence'))['avg']
    portfolio_confidence = round(avg_conf * 100, 1) if avg_conf is not None else None

    # Commitment health color
    if portfolio_confidence is None:
        portfolio_color = 'secondary'
    elif portfolio_confidence >= 70:
        portfolio_color = 'success'
    elif portfolio_confidence >= 40:
        portfolio_color = 'warning'
    else:
        portfolio_color = 'danger'

    context = {
        'board': board,
        'commitments': commitments,
        'portfolio_confidence': portfolio_confidence,
        'portfolio_color': portfolio_color,
        'active_count': active.count(),
        'at_risk_count': commitments.filter(status='at_risk').count(),
        'critical_count': commitments.filter(status='critical').count(),
    }
    return render(request, 'kanban/commitment_dashboard.html', context)


# ---------------------------------------------------------------------------
# 2. Commitment Create
# ---------------------------------------------------------------------------

@login_required
@demo_write_guard
def commitment_create(request, board_id):
    """
    GET: Show the new commitment form.
    POST: Validate and create the CommitmentProtocol with a baseline snapshot.
    """
    board = get_object_or_404(Board, id=board_id)

    if request.method == 'POST':
        try:
            title = request.POST.get('title', '').strip()
            description = request.POST.get('description', '').strip()
            target_date_str = request.POST.get('target_date')
            initial_confidence = float(request.POST.get('initial_confidence', 85)) / 100
            halflife_days = int(request.POST.get('halflife_days', 14))
            decay_model = request.POST.get('decay_model', 'exponential')
            negotiation_threshold = float(request.POST.get('negotiation_threshold', 40)) / 100
            linked_task_ids = request.POST.getlist('linked_tasks')
            stakeholder_ids = request.POST.getlist('stakeholders')

            if not title:
                raise ValueError('Title is required.')
            if not target_date_str:
                raise ValueError('Target date is required.')

            target_date = date.fromisoformat(target_date_str)

            # Capture baseline snapshot
            all_tasks = Task.objects.filter(column__board=board, item_type='task')
            completed = all_tasks.filter(progress=100).count()
            two_weeks_ago = timezone.now() - timezone.timedelta(days=14)
            recent_done = all_tasks.filter(progress=100, updated_at__gte=two_weeks_ago).count()

            baseline_snapshot = {
                'task_count': all_tasks.count(),
                'completed_tasks': completed,
                'team_members': board.memberships.count(),
                'velocity_last_2_weeks': recent_done,
                'snapshot_date': str(date.today()),
            }

            protocol = CommitmentProtocol.objects.create(
                board=board,
                title=title,
                description=description,
                target_date=target_date,
                initial_confidence=initial_confidence,
                current_confidence=initial_confidence,
                confidence_halflife_days=halflife_days,
                decay_model=decay_model,
                negotiation_threshold=negotiation_threshold,
                created_by=request.user,
                baseline_snapshot=baseline_snapshot,
                last_signal_date=timezone.now(),
            )

            if linked_task_ids:
                tasks = Task.objects.filter(id__in=linked_task_ids, column__board=board)
                protocol.linked_tasks.set(tasks)

            if stakeholder_ids:
                from django.contrib.auth.models import User as DjangoUser
                stakeholders = DjangoUser.objects.filter(id__in=stakeholder_ids)
                protocol.stakeholders.set(stakeholders)

            # Ensure the creator has a credibility score record
            UserCredibilityScore.objects.get_or_create(user=request.user)

            # Log to Knowledge Graph
            try:
                CommitmentService._log_kg_event(
                    protocol=protocol,
                    event_type='commitment_created',
                    title=f'Commitment created: "{protocol.title}"',
                    content=(
                        f'New commitment "{protocol.title}" created for board '
                        f'"{board.name}" with initial confidence {initial_confidence:.0%} '
                        f'and target date {target_date}.'
                    ),
                )
            except Exception:
                pass

            return redirect('commitment_detail', board_id=board.id, commitment_id=protocol.id)

        except (ValueError, TypeError) as e:
            return render(request, 'kanban/commitment_create.html', {
                'board': board,
                'error': str(e),
                'form_data': request.POST,
            })

    # GET: collect context for the form
    tasks = Task.objects.filter(column__board=board, item_type='task').order_by('title')
    members = User.objects.filter(board_memberships__board=board)

    context = {
        'board': board,
        'tasks': tasks,
        'members': members,
    }
    return render(request, 'kanban/commitment_create.html', context)


# ---------------------------------------------------------------------------
# 3. Commitment Detail
# ---------------------------------------------------------------------------

@login_required
def commitment_detail(request, board_id, commitment_id):
    """
    Full detail view with 4 tabs:
    Overview / Betting Market / Signal History / Negotiations
    """
    board = get_object_or_404(Board, id=board_id)
    protocol = get_object_or_404(
        CommitmentProtocol.objects.select_related('board', 'created_by')
        .prefetch_related('signals', 'bets__bettor', 'negotiations', 'stakeholders'),
        id=commitment_id,
        board=board,
    )

    # Confidence curve data for Chart.js
    curve_data = CommitmentService.get_confidence_curve_data(protocol)

    # Market consensus
    market = CommitmentService.calculate_market_consensus(protocol)

    # Current user's bet (if any)
    user_bet = protocol.bets.filter(bettor=request.user).first()

    # User's credibility and token balance
    credibility, _ = UserCredibilityScore.objects.get_or_create(user=request.user)

    # Active negotiation if any
    active_negotiation = protocol.negotiations.filter(
        status__in=['draft', 'sent', 'acknowledged']
    ).first()

    context = {
        'board': board,
        'commitment': protocol,
        'curve_data_json': json.dumps(curve_data),
        'market': market,
        'user_bet': user_bet,
        'credibility': credibility,
        'active_negotiation': active_negotiation,
        'days_until_deadline': protocol.days_until_deadline(),
        'signals': protocol.signals.order_by('-timestamp')[:50],
        'past_negotiations': protocol.negotiations.filter(status='resolved').order_by('-resolved_at'),
    }
    return render(request, 'kanban/commitment_detail.html', context)


# ---------------------------------------------------------------------------
# 4. Place a Bet (AJAX POST)
# ---------------------------------------------------------------------------

@login_required
@require_POST
@demo_write_guard
def commitment_place_bet(request, board_id, commitment_id):
    """
    Place or update a single bet (upsert — one per user per commitment).
    Validates token balance, creates/updates CommitmentBet.
    Returns JSON.
    """
    board = get_object_or_404(Board, id=board_id)
    protocol = get_object_or_404(CommitmentProtocol, id=commitment_id, board=board)

    if 'application/json' in (request.content_type or ''):
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'error': 'Invalid JSON body.'}, status=400)
    else:
        body = request.POST

    tokens_wagered = int(body.get('tokens_wagered') or body.get('tokens', 10))
    confidence_raw = float(body.get('confidence_estimate') or body.get('confidence', 50))
    # Accept both 0-1 and 0-100 scale
    if confidence_raw > 1:
        confidence_estimate = max(0.01, min(0.99, confidence_raw / 100))
    else:
        confidence_estimate = max(0.01, min(0.99, confidence_raw))
    reasoning = body.get('reasoning', '').strip()
    is_anonymous = bool(body.get('is_anonymous', True))

    if tokens_wagered < 1 or tokens_wagered > 100:
        return JsonResponse({'error': 'Tokens must be between 1 and 100.'}, status=400)

    # Get or create credibility score
    credibility, _ = UserCredibilityScore.objects.get_or_create(user=request.user)

    # Check if this is an existing bet (update) or new
    existing_bet = protocol.bets.filter(bettor=request.user).first()

    if existing_bet:
        # Refund old tokens, deduct new amount
        tokens_diff = tokens_wagered - existing_bet.tokens_wagered
        if tokens_diff > credibility.tokens_remaining:
            return JsonResponse(
                {'error': f'Insufficient tokens. You have {credibility.tokens_remaining} remaining.'},
                status=400,
            )
        existing_bet.tokens_wagered = tokens_wagered
        existing_bet.confidence_estimate = confidence_estimate
        existing_bet.reasoning = reasoning
        existing_bet.is_anonymous = is_anonymous
        existing_bet.save()
        if tokens_diff > 0:
            credibility.tokens_remaining -= tokens_diff
            credibility.save(update_fields=['tokens_remaining'])
    else:
        # New bet
        if tokens_wagered > credibility.tokens_remaining:
            return JsonResponse(
                {'error': f'Insufficient tokens. You have {credibility.tokens_remaining} remaining.'},
                status=400,
            )
        CommitmentBet.objects.create(
            protocol=protocol,
            bettor=request.user,
            tokens_wagered=tokens_wagered,
            confidence_estimate=confidence_estimate,
            reasoning=reasoning,
            is_anonymous=is_anonymous,
        )
        credibility.tokens_remaining -= tokens_wagered
        credibility.save(update_fields=['tokens_remaining'])

    # Invalidate market cache
    from django.core.cache import cache
    cache.delete(f'commitment_market_{protocol.pk}')

    # Return updated market data
    market = CommitmentService.calculate_market_consensus(protocol)

    return JsonResponse({
        'success': True,
        'market': market,
        'tokens_remaining': credibility.tokens_remaining,
        'message': 'Bet placed successfully.',
    })


# ---------------------------------------------------------------------------
# 5. Manual Signal (AJAX POST)
# ---------------------------------------------------------------------------

@login_required
@require_POST
@demo_write_guard
def commitment_signal_manual(request, board_id, commitment_id):
    """
    Board members can manually log a positive or negative signal.
    Returns JSON with updated confidence and signal record.
    """
    board = get_object_or_404(Board, id=board_id)
    protocol = get_object_or_404(CommitmentProtocol, id=commitment_id, board=board)

    if 'application/json' in (request.content_type or ''):
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'error': 'Invalid JSON body.'}, status=400)
    else:
        body = request.POST

    signal_type = body.get('signal_type', 'manual_positive')
    # Map specific signal types to positive/negative direction
    positive_types = {'manual_positive', 'milestone_hit', 'stakeholder_approval', 'dependency_resolved'}
    negative_types = {'manual_negative', 'blocker_emerged', 'team_change', 'requirement_change'}
    if signal_type not in positive_types | negative_types:
        return JsonResponse({'error': 'Invalid signal type.'}, status=400)

    signal_value = float(body.get('signal_value', 0.15))
    if signal_type in negative_types:
        signal_value = -abs(signal_value)
    else:
        signal_value = abs(signal_value)

    description = body.get('description', '').strip()
    if not description:
        return JsonResponse({'error': 'Description is required.'}, status=400)

    sig = CommitmentService.apply_signal(
        protocol=protocol,
        signal_type=signal_type,
        signal_value=signal_value,
        description=description,
        user=request.user,
        ai_generated=False,
    )

    return JsonResponse({
        'success': True,
        'new_confidence': protocol.current_confidence,
        'new_confidence_pct': round(protocol.current_confidence * 100, 1),
        'confidence_color': protocol.confidence_color,
        'signal_id': sig.pk,
        'message': 'Signal recorded.',
    })


# ---------------------------------------------------------------------------
# 6. Negotiation Session Detail
# ---------------------------------------------------------------------------

@login_required
def negotiation_session_detail(request, board_id, negotiation_id):
    """
    Full view of a negotiation session with the AI message and 3 options.
    """
    board = get_object_or_404(Board, id=board_id)
    session = get_object_or_404(
        NegotiationSession.objects.select_related('protocol'),
        id=negotiation_id,
        protocol__board=board,
    )

    protocol = session.protocol

    context = {
        'board': board,
        'negotiation': session,
        'protocol': protocol,
        'stakeholders': protocol.stakeholders.all(),
    }
    return render(request, 'kanban/negotiation_session.html', context)


# ---------------------------------------------------------------------------
# 7. Resolve Negotiation (POST)
# ---------------------------------------------------------------------------

@login_required
@require_POST
@demo_write_guard
def negotiation_resolve(request, board_id, negotiation_id):
    """
    Mark a NegotiationSession as resolved with the chosen option.
    If Option B (extend deadline): updates the protocol's target_date.
    Creates a positive signal — renegotiation = fresh start.
    """
    board = get_object_or_404(Board, id=board_id)
    session = get_object_or_404(
        NegotiationSession,
        id=negotiation_id,
        protocol__board=board,
    )
    protocol = session.protocol

    chosen = request.POST.get('chosen_option') or request.POST.get('option')
    stakeholder_notes = request.POST.get('stakeholder_notes', '').strip()

    if chosen not in ['a', 'b', 'c', 'custom']:
        return JsonResponse({'error': 'Invalid option choice.'}, status=400)

    session.chosen_option = chosen
    session.stakeholder_notes = stakeholder_notes
    session.status = 'resolved'
    session.resolved_at = timezone.now()

    # If extending deadline, update target_date
    if chosen == 'b':
        option_b = session.option_b_impact or {}
        new_date_str = option_b.get('new_target_date') or request.POST.get('new_target_date')
        if new_date_str:
            try:
                protocol.target_date = date.fromisoformat(str(new_date_str)[:10])
                protocol.save(update_fields=['target_date'])
            except ValueError:
                pass

    session.save()

    # Fresh start signal — renegotiation resets confidence somewhat
    CommitmentService.apply_signal(
        protocol=protocol,
        signal_type='manual_positive',
        signal_value=0.25,
        description=f'Renegotiation completed — option {chosen.upper()} chosen. {stakeholder_notes[:100]}',
        user=request.user,
        ai_generated=False,
    )

    # Log to Knowledge Graph
    try:
        CommitmentService._log_kg_event(
            protocol=protocol,
            event_type='negotiation_resolved',
            title=f'Negotiation resolved for "{protocol.title}"',
            content=(
                f'Option {chosen.upper()} chosen. '
                f'{stakeholder_notes[:200]}'
            ),
        )
    except Exception:
        pass

    protocol.status = 'renegotiated'
    protocol.save(update_fields=['status'])

    return redirect('commitment_detail', board_id=board.id, commitment_id=protocol.id)


# ---------------------------------------------------------------------------
# 8. API: Confidence Curve Data (JSON)
# ---------------------------------------------------------------------------

@login_required
def commitment_curve_api(request, board_id, commitment_id):
    """JSON endpoint returning confidence curve data for Chart.js."""
    board = get_object_or_404(Board, id=board_id)
    protocol = get_object_or_404(CommitmentProtocol, id=commitment_id, board=board)
    data = CommitmentService.get_confidence_curve_data(protocol)
    return JsonResponse({'curve': data})


# ---------------------------------------------------------------------------
# 9. API: Market Data (JSON)
# ---------------------------------------------------------------------------

@login_required
def commitment_market_api(request, board_id, commitment_id):
    """JSON endpoint returning current market consensus data."""
    board = get_object_or_404(Board, id=board_id)
    protocol = get_object_or_404(CommitmentProtocol, id=commitment_id, board=board)
    market = CommitmentService.calculate_market_consensus(protocol)
    return JsonResponse(market)


# ---------------------------------------------------------------------------
# 10. API: List Commitments (JSON for auto-refresh)
# ---------------------------------------------------------------------------

@login_required
def commitments_list_api(request, board_id):
    """
    JSON endpoint used by the dashboard JS to refresh confidence values.
    """
    board = get_object_or_404(Board, id=board_id)
    protocols = CommitmentProtocol.objects.filter(board=board).values(
        'id', 'title', 'current_confidence', 'status', 'target_date',
    )
    data = []
    for p in protocols:
        conf = p['current_confidence']
        color = 'success' if conf >= 0.70 else ('warning' if conf >= 0.40 else 'danger')
        days = (p['target_date'] - date.today()).days
        data.append({
            **p,
            'current_confidence_pct': round(conf * 100, 1),
            'confidence_color': color,
            'days_until_deadline': days,
            'target_date': str(p['target_date']),
        })
    return JsonResponse({'commitments': data})
