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
from kanban.utils.demo_protection import get_user_boards, user_is_demo


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

    # Un-snooze any items whose timer has expired so they reappear immediately
    # on page load rather than waiting for the next 7:15 AM Celery run.
    now = timezone.now()
    DecisionItem.objects.filter(
        created_for=user,
        status='snoozed',
        snoozed_until__lte=now,
    ).update(status='pending', snoozed_until=None)

    # Respect the user's current viewing mode — only show items relevant to
    # their active workspace (demo boards vs real boards).  Uses the
    # canonical ``get_user_boards()`` so sandbox users see sandbox items
    # (not template-board items, which caused duplicates).
    user_boards = get_user_boards(user)
    pending = (
        DecisionItem.objects.filter(
            created_for=user, status='pending', board__in=user_boards,
        ) | DecisionItem.objects.filter(
            created_for=user, status='pending', board__isnull=True,
        )
    ).distinct()

    action_required = list(pending.filter(priority_level='action_required'))
    awareness = list(pending.filter(priority_level='awareness')) if settings_obj.show_awareness_items else []
    quick_wins = list(pending.filter(priority_level='quick_win')) if settings_obj.show_quick_wins else []

    today = timezone.localdate()
    briefing = (
        DecisionCenterBriefing.objects
        .filter(user=user, generated_at__date=today, is_demo=user_is_demo(user))
        .first()
    )

    total_est = sum(
        i.estimated_minutes
        for i in action_required + awareness + quick_wins
    )

    # If the briefing's item count is stale (e.g. items were cleaned up since
    # it was generated, or the user switched workspace mode), patch it so the
    # headline and top_priority_board match what we actually display.
    actual_total = len(action_required) + len(awareness) + len(quick_wins)
    if briefing:
        stored_total = sum(briefing.item_counts.values()) if briefing.item_counts else 0
        if stored_total != actual_total:
            briefing.headline = f"You have {actual_total} item{'s' if actual_total != 1 else ''} in your decision queue today."
            new_counts = {
                'action_required': len(action_required),
                'awareness': len(awareness),
                'quick_win': len(quick_wins),
            }
            briefing.item_counts = new_counts
            briefing.estimated_minutes = total_est

            # Re-derive top_priority_board from the current visible items so
            # that a briefing generated in demo mode doesn't leak a stale board
            # name into the real workspace (or vice-versa).
            from collections import Counter
            board_counter = Counter(
                item.board.name
                for item in action_required
                if item.board_id is not None
            )
            briefing.top_priority_board = board_counter.most_common(1)[0][0] if board_counter else ''

            parts = []
            if new_counts['action_required']:
                parts.append(f"{new_counts['action_required']} decision{'s' if new_counts['action_required'] != 1 else ''} need your attention.")
            if new_counts['awareness']:
                parts.append(f"{new_counts['awareness']} awareness item{'s' if new_counts['awareness'] != 1 else ''}.")
            if new_counts['quick_win']:
                parts.append(f"{new_counts['quick_win']} quick win{'s' if new_counts['quick_win'] != 1 else ''}.")
            parts.append(f"Estimated review time: {total_est} minutes.")
            briefing.briefing = ' '.join(parts)
            briefing.save()

    # Snoozed items – scoped to current workspace boards, ordered soonest first
    snoozed_items = (
        DecisionItem.objects.filter(
            created_for=user, status='snoozed', board__in=user_boards,
        ) | DecisionItem.objects.filter(
            created_for=user, status='snoozed', board__isnull=True,
        )
    ).distinct().order_by('snoozed_until')

    # Archive – last 30 days, scoped to current workspace boards
    archive_cutoff = now - timedelta(days=30)
    archive_items = (
        DecisionItem.objects.filter(
            created_for=user,
            archived_at__isnull=False,
            archived_at__gte=archive_cutoff,
            board__in=user_boards,
        ) | DecisionItem.objects.filter(
            created_for=user,
            archived_at__isnull=False,
            archived_at__gte=archive_cutoff,
            board__isnull=True,
        )
    ).distinct().order_by('-archived_at')

    # Last resolved timestamp
    last_resolved = (
        DecisionItem.objects
        .filter(created_for=user, status='resolved')
        .order_by('-resolved_at')
        .values_list('resolved_at', flat=True)
        .first()
    )

    inbox_count = actual_total

    context = {
        'action_required': action_required,
        'awareness': awareness,
        'quick_wins': quick_wins,
        'snoozed_items': snoozed_items,
        'archive_items': archive_items,
        'inbox_count': inbox_count,
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
    effective_demo = is_demo_mode or '_demo' in user.username

    cache_key = _widget_cache_key(user.id, demo_mode=effective_demo)
    data = cache.get(cache_key)
    if data is not None:
        return JsonResponse(data)

    # Un-snooze expired items before computing counts so the badge stays accurate.
    now = timezone.now()
    DecisionItem.objects.filter(
        created_for=user,
        status='snoozed',
        snoozed_until__lte=now,
    ).update(status='pending', snoozed_until=None)

    user_boards = get_user_boards(user)
    pending = (
        DecisionItem.objects.filter(
            created_for=user, status='pending', board__in=user_boards,
        ) | DecisionItem.objects.filter(
            created_for=user, status='pending', board__isnull=True,
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
        .filter(user=user, generated_at__date=today, is_demo=user_is_demo(user))
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
    """Mark a single item as resolved and move it to Archive."""
    item = _get_item_or_404(request.user, item_id)
    now = timezone.now()
    item.status = 'resolved'
    item.resolved_at = now
    item.resolved_by = request.user
    item.archived_at = now
    item.archive_reason = 'resolved'
    item.snoozed_until = None
    item.save(update_fields=['status', 'resolved_at', 'resolved_by', 'archived_at', 'archive_reason', 'snoozed_until'])

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
        'archived_at': item.archived_at.isoformat(),
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
        'snoozed_until': item.snoozed_until.isoformat(),
        'pending_count': _pending_count(request.user),
    })


@login_required
@require_POST
@demo_write_guard
def dismiss_decision_item(request, item_id):
    """Dismiss a single item and move it to Archive."""
    item = _get_item_or_404(request.user, item_id)
    now = timezone.now()
    item.status = 'dismissed'
    item.archived_at = now
    item.archive_reason = 'dismissed'
    item.snoozed_until = None
    item.save(update_fields=['status', 'archived_at', 'archive_reason', 'snoozed_until'])

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
        'archived_at': item.archived_at.isoformat(),
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
        archived_at=now,
        archive_reason='resolved',
    )

    _invalidate_widget_cache(request.user.id)
    return JsonResponse({
        'success': True,
        'resolved_count': count,
        'pending_count': _pending_count(request.user),
    })


@login_required
@require_POST
@demo_write_guard
def restore_decision_item(request, item_id):
    """Restore an archived item back to the Inbox (pending)."""
    item = _get_item_or_404(request.user, item_id)
    item.status = 'pending'
    item.archived_at = None
    item.archive_reason = None
    item.snoozed_until = None
    item.save(update_fields=['status', 'archived_at', 'archive_reason', 'snoozed_until'])
    _invalidate_widget_cache(request.user.id)
    return JsonResponse({'success': True})


@login_required
@require_POST
@demo_write_guard
def change_snooze_decision_item(request, item_id):
    """Update the snooze duration for an already-snoozed item."""
    item = _get_item_or_404(request.user, item_id)
    if item.status != 'snoozed':
        return JsonResponse({'error': 'Item is not snoozed'}, status=400)
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        body = {}
    duration = body.get('duration')
    try:
        duration = int(duration)
    except (TypeError, ValueError):
        duration = None
    if duration not in (24, 48, 168):
        return JsonResponse({'error': 'Invalid duration'}, status=400)
    new_snoozed_until = timezone.now() + timedelta(hours=duration)
    item.snoozed_until = new_snoozed_until
    item.save(update_fields=['snoozed_until'])
    return JsonResponse({
        'success': True,
        'new_snoozed_until': new_snoozed_until.isoformat(),
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
