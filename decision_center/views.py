"""
Decision Center Views
Provides the full-page Decision Center, lightweight widget data endpoint,
and item action endpoints (resolve, snooze, dismiss).
"""
import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import DecisionCenterBriefing, DecisionCenterSettings, DecisionItem
from kanban.decorators import demo_write_guard


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_settings(user):
    """Return the user's DecisionCenterSettings, creating with defaults if needed."""
    obj, _ = DecisionCenterSettings.objects.get_or_create(user=user)
    return obj


def _widget_cache_key(user_id, demo_mode=False):
    mode = 'demo' if demo_mode else 'real'
    return f"dc_widget_{user_id}_{mode}"


def _invalidate_widget_cache(user_id):
    cache.delete(_widget_cache_key(user_id, demo_mode=False))
    cache.delete(_widget_cache_key(user_id, demo_mode=True))


def _get_item_or_404(user, item_id):
    """Get a DecisionItem that belongs to *this* user or 404."""
    return get_object_or_404(DecisionItem, pk=item_id, created_for=user)


def _pending_count(user):
    return DecisionItem.objects.filter(
        created_for=user, status='pending',
    ).count()


# ---------------------------------------------------------------------------
# Full-page view
# ---------------------------------------------------------------------------

@login_required
def decision_center_view(request):
    """Render the full Decision Center page."""
    user = request.user
    settings_obj = _get_settings(user)

    # Respect the user's current viewing mode — only show items relevant to
    # their active workspace (demo boards vs real boards)
    try:
        is_demo_mode = getattr(user.profile, 'is_viewing_demo', False)
    except Exception:
        is_demo_mode = False
    is_demo_account = '_demo' in user.username

    pending = DecisionItem.objects.filter(created_for=user, status='pending')
    if is_demo_mode or is_demo_account:
        pending = pending.filter(board__is_official_demo_board=True)
    else:
        pending = pending.filter(
            board__is_official_demo_board=False,
            board__is_sandbox_copy=False,
        ) | DecisionItem.objects.filter(
            created_for=user, status='pending', board__isnull=True
        )
        pending = pending.distinct()

    action_required = list(pending.filter(priority_level='action_required'))
    awareness = list(pending.filter(priority_level='awareness')) if settings_obj.show_awareness_items else []
    quick_wins = list(pending.filter(priority_level='quick_win')) if settings_obj.show_quick_wins else []

    today = timezone.localdate()
    briefing = (
        DecisionCenterBriefing.objects
        .filter(user=user, generated_at__date=today)
        .first()
    )

    total_est = sum(
        i.estimated_minutes
        for i in action_required + awareness + quick_wins
    )

    # Last resolved timestamp
    last_resolved = (
        DecisionItem.objects
        .filter(created_for=user, status='resolved')
        .order_by('-resolved_at')
        .values_list('resolved_at', flat=True)
        .first()
    )

    context = {
        'action_required': action_required,
        'awareness': awareness,
        'quick_wins': quick_wins,
        'briefing': briefing,
        'total_est': total_est,
        'last_resolved': last_resolved,
        'settings_obj': settings_obj,
        'snooze_options': [
            (24, '24 hours'),
            (48, '48 hours'),
            (168, '1 week'),
        ],
    }
    return render(request, 'decision_center/decision_center.html', context)


# ---------------------------------------------------------------------------
# Widget data (AJAX, cached 30 min)
# ---------------------------------------------------------------------------

@login_required
@require_GET
def decision_center_widget_data(request):
    """Lightweight JSON for the dashboard widget card."""
    user = request.user
    try:
        is_demo_mode = getattr(user.profile, 'is_viewing_demo', False)
    except Exception:
        is_demo_mode = False
    is_demo_account = '_demo' in user.username
    effective_demo = is_demo_mode or is_demo_account

    cache_key = _widget_cache_key(user.id, demo_mode=effective_demo)
    data = cache.get(cache_key)
    if data is not None:
        return JsonResponse(data)

    pending = DecisionItem.objects.filter(created_for=user, status='pending')
    if effective_demo:
        pending = pending.filter(board__is_official_demo_board=True)
    else:
        pending = (
            pending.filter(
                board__is_official_demo_board=False,
                board__is_sandbox_copy=False,
            )
            | DecisionItem.objects.filter(
                created_for=user, status='pending', board__isnull=True
            )
        ).distinct()

    settings_obj = _get_settings(user)
    counts = {
        'action_required_count': pending.filter(
            priority_level='action_required',
        ).count(),
        'awareness_count': (
            pending.filter(priority_level='awareness').count()
            if settings_obj.show_awareness_items else 0
        ),
        'quick_win_count': (
            pending.filter(priority_level='quick_win').count()
            if settings_obj.show_quick_wins else 0
        ),
    }

    today = timezone.localdate()
    briefing = (
        DecisionCenterBriefing.objects
        .filter(user=user, generated_at__date=today)
        .values_list('headline', flat=True)
        .first()
    )

    last_resolved = (
        DecisionItem.objects
        .filter(created_for=user, status='resolved')
        .order_by('-resolved_at')
        .values_list('resolved_at', flat=True)
        .first()
    )

    data = {
        **counts,
        'total_count': sum(counts.values()),
        'headline': briefing or '',
        'estimated_minutes': (
            pending.aggregate(
                total=Sum('estimated_minutes'),
            )['total'] or 0
        ),
        'last_cleared_at': (
            last_resolved.isoformat() if last_resolved else None
        ),
    }
    cache.set(cache_key, data, 60 * 30)  # 30 min
    return JsonResponse(data)


# ---------------------------------------------------------------------------
# Item actions
# ---------------------------------------------------------------------------

@login_required
@require_POST
@demo_write_guard
def resolve_decision_item(request, item_id):
    """Mark a single item as resolved."""
    item = _get_item_or_404(request.user, item_id)
    now = timezone.now()
    item.status = 'resolved'
    item.resolved_at = now
    item.resolved_by = request.user
    item.save(update_fields=['status', 'resolved_at', 'resolved_by'])

    _invalidate_widget_cache(request.user.id)

    # Audit log (best-effort)
    try:
        from kanban.audit_utils import log_audit
        log_audit(
            'decision_item.resolved',
            user=request.user,
            request=request,
            object_type='DecisionItem',
            object_id_backup=str(item.id),
            object_repr=item.title,
        )
    except Exception:
        pass

    return JsonResponse({
        'success': True,
        'pending_count': _pending_count(request.user),
    })


@login_required
@require_POST
@demo_write_guard
def snooze_decision_item(request, item_id):
    """Snooze an item for 24, 48, or 168 hours."""
    item = _get_item_or_404(request.user, item_id)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        body = {}
    snooze_hours = body.get('snooze_hours', 24)
    if snooze_hours not in (24, 48, 168):
        return JsonResponse({'error': 'Invalid snooze_hours'}, status=400)

    item.status = 'snoozed'
    item.snoozed_until = timezone.now() + timedelta(hours=snooze_hours)
    item.save(update_fields=['status', 'snoozed_until'])

    _invalidate_widget_cache(request.user.id)
    return JsonResponse({
        'success': True,
        'pending_count': _pending_count(request.user),
    })


@login_required
@require_POST
@demo_write_guard
def dismiss_decision_item(request, item_id):
    """Dismiss a single item."""
    item = _get_item_or_404(request.user, item_id)
    item.status = 'dismissed'
    item.save(update_fields=['status'])

    _invalidate_widget_cache(request.user.id)

    try:
        from kanban.audit_utils import log_audit
        log_audit(
            'decision_item.dismissed',
            user=request.user,
            request=request,
            object_type='DecisionItem',
            object_id_backup=str(item.id),
            object_repr=item.title,
        )
    except Exception:
        pass

    return JsonResponse({
        'success': True,
        'pending_count': _pending_count(request.user),
    })


@login_required
@require_POST
@demo_write_guard
def resolve_all_quick_wins(request):
    """Bulk-resolve every pending quick-win item for the user."""
    now = timezone.now()
    qs = DecisionItem.objects.filter(
        created_for=request.user,
        status='pending',
        priority_level='quick_win',
    )
    count = qs.update(
        status='resolved',
        resolved_at=now,
        resolved_by=request.user,
    )

    _invalidate_widget_cache(request.user.id)
    return JsonResponse({
        'success': True,
        'resolved_count': count,
        'pending_count': _pending_count(request.user),
    })


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@login_required
@demo_write_guard
def decision_center_settings_view(request):
    """GET: return current settings. POST: update them."""
    settings_obj = _get_settings(request.user)

    if request.method == 'GET':
        return JsonResponse({
            'daily_digest_enabled': settings_obj.daily_digest_enabled,
            'digest_time': settings_obj.digest_time.strftime('%H:%M'),
            'show_awareness_items': settings_obj.show_awareness_items,
            'show_quick_wins': settings_obj.show_quick_wins,
            'min_overdue_days': settings_obj.min_overdue_days,
            'min_stale_days': settings_obj.min_stale_days,
            'budget_alert_threshold': settings_obj.budget_alert_threshold,
            'deadline_warning_days': settings_obj.deadline_warning_days,
        })

    # POST
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    changed = {}
    for field in (
        'daily_digest_enabled', 'show_awareness_items', 'show_quick_wins',
    ):
        if field in body:
            old = getattr(settings_obj, field)
            new = bool(body[field])
            if old != new:
                changed[field] = {'old': old, 'new': new}
                setattr(settings_obj, field, new)

    for field in (
        'min_overdue_days', 'min_stale_days',
        'budget_alert_threshold', 'deadline_warning_days',
    ):
        if field in body:
            old = getattr(settings_obj, field)
            try:
                new = int(body[field])
            except (TypeError, ValueError):
                continue
            if new < 0:
                continue
            if old != new:
                changed[field] = {'old': old, 'new': new}
                setattr(settings_obj, field, new)

    if 'digest_time' in body:
        parts = str(body['digest_time']).split(':')
        if len(parts) == 2:
            try:
                from datetime import time as dt_time
                new_time = dt_time(int(parts[0]), int(parts[1]))
                if settings_obj.digest_time != new_time:
                    changed['digest_time'] = {
                        'old': settings_obj.digest_time.strftime('%H:%M'),
                        'new': new_time.strftime('%H:%M'),
                    }
                    settings_obj.digest_time = new_time
            except (ValueError, TypeError):
                pass

    if changed:
        settings_obj.save()
        _invalidate_widget_cache(request.user.id)
        try:
            from kanban.audit_utils import log_audit
            log_audit(
                'decision_center.settings_changed',
                user=request.user,
                request=request,
                object_type='DecisionCenterSettings',
                object_id_backup=str(settings_obj.pk),
                changes=changed,
            )
        except Exception:
            pass

    return JsonResponse({'success': True, 'changed': changed})
