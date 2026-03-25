"""
Celery tasks for the Decision Center.
- collect_decision_items: morning scan that creates DecisionItem records
- generate_decision_briefing: AI summary of the day's decision queue
- send_daily_digest_emails: send digest emails at each user's preferred time
"""
import json
import logging
from datetime import timedelta

from celery import shared_task
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_or_create_settings(user):
    from decision_center.models import DecisionCenterSettings
    obj, _ = DecisionCenterSettings.objects.get_or_create(user=user)
    return obj


def _user_boards(user):
    """Return the queryset of boards a user can access.
    
    Includes demo boards if the user is a demo account or is viewing demo.
    """
    from kanban.models import Board
    from accounts.models import UserProfile

    # Check if this is a demo account or user is viewing demo
    is_demo_user = '_demo' in user.username
    try:
        profile = UserProfile.objects.get(user=user)
        is_viewing_demo = getattr(profile, 'is_viewing_demo', False)
    except UserProfile.DoesNotExist:
        is_viewing_demo = False

    if is_demo_user or is_viewing_demo:
        # Include demo boards
        return Board.objects.filter(
            Q(created_by=user) | Q(memberships__user=user) | Q(is_official_demo_board=True),
        ).distinct()

    return Board.objects.filter(
        Q(created_by=user) | Q(memberships__user=user),
        is_official_demo_board=False,
    ).distinct()


def _ensure_item(*, user, board, item_type, priority_level, title,
                 description='', suggested_action='', estimated_minutes=2,
                 source_obj=None, context_data=None):
    """
    Create or update a DecisionItem, avoiding duplicates.

    For board-grouped items (overdue_task, unassigned_task, stale_task)
    the source object is the Board itself — we use update_or_create so
    context_data is refreshed on each run.
    """
    from decision_center.models import DecisionItem

    defaults = {
        'priority_level': priority_level,
        'title': title,
        'description': description,
        'suggested_action': suggested_action,
        'estimated_minutes': estimated_minutes,
        'context_data': context_data or {},
    }
    lookup = {
        'created_for': user,
        'item_type': item_type,
        'status': 'pending',
    }

    if source_obj is not None:
        ct = ContentType.objects.get_for_model(source_obj)
        lookup['source_content_type'] = ct
        lookup['source_object_id'] = source_obj.pk
        defaults['board'] = board
    else:
        lookup['board'] = board
        lookup['source_content_type'] = None
        lookup['source_object_id'] = None

    DecisionItem.objects.update_or_create(defaults=defaults, **lookup)


# ── Task 1: Collect Decision Items ──────────────────────────────────────────

@shared_task(name='decision_center.collect_decision_items')
def collect_decision_items():
    """
    Scan all active boards for every active user and create DecisionItem
    records for anything that needs attention.  Runs once each morning.
    """
    now = timezone.now()
    today = now.date()

    # ── Un-snooze expired items ──────────────────────────────────────
    from decision_center.models import DecisionItem
    DecisionItem.objects.filter(
        status='snoozed',
        snoozed_until__lte=now,
    ).update(status='pending', snoozed_until=None)

    # ── Per-user collection ──────────────────────────────────────────
    active_users = User.objects.filter(is_active=True)
    stats = {'users': 0, 'items_created': 0}

    for user in active_users.iterator():
        boards = _user_boards(user)
        if not boards.exists():
            continue

        settings = _get_or_create_settings(user)
        stats['users'] += 1

        # ------------------------------------------------------------------
        # ACTION REQUIRED
        # ------------------------------------------------------------------

        # 1. Unresolved conflicts
        try:
            from kanban.conflict_models import ConflictDetection
            for conflict in ConflictDetection.objects.filter(
                status='active', board__in=boards,
            ).select_related('board'):
                _ensure_item(
                    user=user,
                    board=conflict.board,
                    item_type='conflict',
                    priority_level='action_required',
                    title=f"Conflict on {conflict.board.name}: {conflict.title}",
                    description=conflict.description[:500],
                    suggested_action='Review conflict and select a resolution strategy',
                    estimated_minutes=3,
                    source_obj=conflict,
                )
        except Exception:
            logger.exception("collect_decision_items: conflicts failed for user %s", user.pk)

        # 2. Unacknowledged high-risk Pre-Mortem analyses
        try:
            from kanban.premortem_models import (
                PreMortemAnalysis,
                PreMortemScenarioAcknowledgment,
            )
            for pm in PreMortemAnalysis.objects.filter(
                overall_risk_level='high', board__in=boards,
            ).select_related('board'):
                # Check if ALL scenarios are acknowledged by this user
                total_scenarios = 5  # always 5 scenarios
                acked = PreMortemScenarioAcknowledgment.objects.filter(
                    pre_mortem=pm, acknowledged_by=user,
                ).count()
                if acked < total_scenarios:
                    _ensure_item(
                        user=user,
                        board=pm.board,
                        item_type='premortem_risk',
                        priority_level='action_required',
                        title=f"High-risk Pre-Mortem unreviewed on {pm.board.name}",
                        description=(
                            f"{total_scenarios - acked} of {total_scenarios} "
                            f"scenarios still need acknowledgement"
                        ),
                        suggested_action=(
                            'Acknowledge or address high-risk scenarios '
                            'before work continues'
                        ),
                        estimated_minutes=5,
                        source_obj=pm,
                    )
        except Exception:
            logger.exception("collect_decision_items: premortem failed for user %s", user.pk)

        # 3. Overdue tasks (grouped by board)
        try:
            from kanban.models import Task
            threshold = now - timedelta(days=settings.min_overdue_days)
            for board in boards:
                overdue_tasks = Task.objects.filter(
                    column__board=board,
                    due_date__lt=threshold,
                    item_type='task',
                ).exclude(progress=100)
                count = overdue_tasks.count()
                if count > 0:
                    task_ids = list(overdue_tasks.values_list('id', flat=True)[:50])
                    most_overdue = (now - overdue_tasks.order_by('due_date').first().due_date).days
                    _ensure_item(
                        user=user,
                        board=board,
                        item_type='overdue_task',
                        priority_level='action_required',
                        title=f"{count} overdue task{'s' if count != 1 else ''} on {board.name}",
                        description=f"Most overdue: {most_overdue} days past deadline",
                        suggested_action='Review and update overdue tasks or adjust deadlines',
                        estimated_minutes=min(2 * count, 10),
                        context_data={'task_ids': task_ids, 'most_overdue_days': most_overdue},
                    )
        except Exception:
            logger.exception("collect_decision_items: overdue tasks failed for user %s", user.pk)

        # 4. Over-allocated team members
        try:
            from kanban.models import TeamCapacityAlert
            for alert in TeamCapacityAlert.objects.filter(
                status='active', board__in=boards,
            ).select_related('board', 'resource_user'):
                member_name = (
                    alert.resource_user.get_full_name()
                    or alert.resource_user.username
                ) if alert.resource_user else 'Team'
                _ensure_item(
                    user=user,
                    board=alert.board,
                    item_type='overallocated',
                    priority_level='action_required',
                    title=f"{member_name} is over-allocated on {alert.board.name}",
                    description=alert.message[:500],
                    suggested_action='Review and reassign tasks to balance workload',
                    estimated_minutes=4,
                    source_obj=alert,
                    context_data={'workload_percentage': alert.workload_percentage},
                )
        except Exception:
            logger.exception("collect_decision_items: capacity alerts failed for user %s", user.pk)

        # 5. Unacknowledged scope creep alerts
        try:
            from kanban.models import ScopeCreepAlert
            for alert in ScopeCreepAlert.objects.filter(
                status='active', board__in=boards,
            ).select_related('board'):
                _ensure_item(
                    user=user,
                    board=alert.board,
                    item_type='scope_change',
                    priority_level='action_required',
                    title=f"Scope change on {alert.board.name} (+{alert.scope_increase_percentage:.0f}%)",
                    description=alert.ai_summary[:500] if alert.ai_summary else '',
                    suggested_action='Acknowledge scope change or adjust timeline',
                    estimated_minutes=3,
                    source_obj=alert,
                )
        except Exception:
            logger.exception("collect_decision_items: scope alerts failed for user %s", user.pk)

        # ------------------------------------------------------------------
        # AWARENESS
        # ------------------------------------------------------------------

        # 6. Deadlines approaching
        try:
            deadline_threshold = today + timedelta(days=settings.deadline_warning_days)
            for board in boards.filter(
                project_deadline__isnull=False,
                project_deadline__gt=today,
                project_deadline__lte=deadline_threshold,
            ):
                days_left = (board.project_deadline - today).days
                _ensure_item(
                    user=user,
                    board=board,
                    item_type='deadline_approaching',
                    priority_level='awareness',
                    title=f"{board.name} deadline in {days_left} day{'s' if days_left != 1 else ''}",
                    estimated_minutes=1,
                    context_data={'days_left': days_left},
                )
        except Exception:
            logger.exception("collect_decision_items: deadlines failed for user %s", user.pk)

        # 7. Budget threshold crossed
        try:
            from kanban.budget_models import ProjectBudget
            for budget in ProjectBudget.objects.filter(
                board__in=boards,
            ).select_related('board'):
                pct = budget.get_budget_utilization_percent()
                if pct >= settings.budget_alert_threshold:
                    _ensure_item(
                        user=user,
                        board=budget.board,
                        item_type='budget_threshold',
                        priority_level='awareness',
                        title=f"{budget.board.name} budget at {pct:.0f}%",
                        estimated_minutes=1,
                        context_data={'utilization_percent': round(pct, 1)},
                    )
        except Exception:
            logger.exception("collect_decision_items: budget failed for user %s", user.pk)

        # 8. New auto-captured knowledge memories (since yesterday)
        try:
            from knowledge_graph.models import MemoryNode
            yesterday = now - timedelta(days=1)
            for board in boards:
                new_count = MemoryNode.objects.filter(
                    board=board,
                    is_auto_captured=True,
                    created_at__gte=yesterday,
                ).count()
                if new_count > 0:
                    _ensure_item(
                        user=user,
                        board=board,
                        item_type='memory_captured',
                        priority_level='awareness',
                        title=f"{new_count} new memor{'ies' if new_count != 1 else 'y'} captured on {board.name}",
                        estimated_minutes=1,
                        context_data={'count': new_count},
                    )
        except Exception:
            logger.exception("collect_decision_items: memory nodes failed for user %s", user.pk)

        # ------------------------------------------------------------------
        # QUICK WINS
        # ------------------------------------------------------------------

        # 9. Tasks with no assignee (grouped by board)
        try:
            from kanban.models import Task
            for board in boards:
                unassigned = Task.objects.filter(
                    column__board=board,
                    assigned_to__isnull=True,
                    item_type='task',
                ).exclude(progress=100)
                count = unassigned.count()
                if count > 0:
                    task_ids = list(unassigned.values_list('id', flat=True)[:50])
                    _ensure_item(
                        user=user,
                        board=board,
                        item_type='unassigned_task',
                        priority_level='quick_win',
                        title=f"{count} unassigned task{'s' if count != 1 else ''} on {board.name}",
                        suggested_action='Assign owners to these tasks',
                        estimated_minutes=1,
                        context_data={'task_ids': task_ids},
                    )
        except Exception:
            logger.exception("collect_decision_items: unassigned tasks failed for user %s", user.pk)

        # 10. Stale tasks (grouped by board)
        try:
            from kanban.models import Task
            stale_threshold = now - timedelta(days=settings.min_stale_days)
            for board in boards:
                stale = Task.objects.filter(
                    column__board=board,
                    updated_at__lt=stale_threshold,
                    item_type='task',
                ).exclude(progress=100)
                count = stale.count()
                if count > 0:
                    task_ids = list(stale.values_list('id', flat=True)[:50])
                    _ensure_item(
                        user=user,
                        board=board,
                        item_type='stale_task',
                        priority_level='quick_win',
                        title=(
                            f"{count} stale task{'s' if count != 1 else ''} on "
                            f"{board.name} — no updates in {settings.min_stale_days}+ days"
                        ),
                        suggested_action='Close completed tasks or reassign stalled work',
                        estimated_minutes=2,
                        context_data={'task_ids': task_ids},
                    )
        except Exception:
            logger.exception("collect_decision_items: stale tasks failed for user %s", user.pk)

    logger.info(
        "collect_decision_items complete: %d users scanned",
        stats['users'],
    )
    return stats


# ── Task 2: Generate AI Briefing ────────────────────────────────────────────

@shared_task(name='decision_center.generate_decision_briefing')
def generate_decision_briefing():
    """
    For every user with pending items, generate a short AI morning briefing
    using GeminiClient. Falls back to a deterministic summary if AI fails.
    """
    from decision_center.models import DecisionCenterBriefing, DecisionItem

    today = timezone.localdate()
    users_with_items = (
        DecisionItem.objects
        .filter(status='pending')
        .values_list('created_for', flat=True)
        .distinct()
    )

    generated = 0
    for user_id in users_with_items:
        # Skip if briefing already exists for today
        if DecisionCenterBriefing.objects.filter(
            user_id=user_id, generated_at__date=today,
        ).exists():
            continue

        pending = DecisionItem.objects.filter(
            created_for_id=user_id, status='pending',
        )
        action_items = list(
            pending.filter(priority_level='action_required')
            .values_list('title', flat=True)
        )
        awareness_items = list(
            pending.filter(priority_level='awareness')
            .values_list('title', flat=True)
        )
        quick_items = list(
            pending.filter(priority_level='quick_win')
            .values_list('title', flat=True)
        )
        total_est = sum(
            pending.values_list('estimated_minutes', flat=True)
        )
        counts = {
            'action_required': len(action_items),
            'awareness': len(awareness_items),
            'quick_win': len(quick_items),
        }

        # Attempt AI generation
        headline, briefing_text, top_board = _generate_ai_briefing(
            action_items, awareness_items, quick_items, total_est,
        )

        DecisionCenterBriefing.objects.create(
            user_id=user_id,
            headline=headline,
            briefing=briefing_text,
            estimated_minutes=total_est,
            top_priority_board=top_board,
            item_counts=counts,
        )
        generated += 1

    logger.info("generate_decision_briefing: %d briefings created", generated)
    return {'generated': generated}


def _generate_ai_briefing(action_items, awareness_items, quick_items, total_est):
    """
    Call Gemini for a natural-language briefing.
    Returns (headline, briefing_text, top_priority_board).
    Falls back to deterministic summary on failure.
    """
    try:
        from ai_assistant.utils.ai_clients import GeminiClient

        client = GeminiClient(default_model='gemini-2.5-flash-lite')
        if client.models is None:
            raise RuntimeError("Gemini API not initialised")

        # Build prompt
        lines = []
        if action_items:
            lines.append(f"ACTION REQUIRED ({len(action_items)} items):")
            for t in action_items[:10]:
                lines.append(f"- {t}")
        if awareness_items:
            lines.append(f"\nAWARENESS ({len(awareness_items)} items):")
            for t in awareness_items[:10]:
                lines.append(f"- {t}")
        if quick_items:
            lines.append(f"\nQUICK WINS ({len(quick_items)} items):")
            for t in quick_items[:10]:
                lines.append(f"- {t}")
        lines.append(f"\nTotal estimated review time: {total_est} minutes")

        user_prompt = (
            "Generate a morning briefing for this PM's decision queue.\n\n"
            + "\n".join(lines)
            + "\n\nReturn ONLY valid JSON with keys: "
            "headline (one sentence), briefing (2-3 sentences), "
            "top_priority_board (board name with most urgent items or empty string)"
        )
        system_prompt = (
            "You are a calm, efficient chief of staff summarizing a project "
            "manager's morning decision queue. Be concise, prioritized, and "
            "practical. Speak directly to the PM. No fluff. Return ONLY valid JSON."
        )

        result = client.get_response(
            prompt=f"{system_prompt}\n\n{user_prompt}",
            task_complexity='simple',
            temperature=0.4,
            use_cache=False,
        )
        text = result if isinstance(result, str) else str(result)

        # Parse JSON from response
        # Strip markdown code fences if present
        text = text.strip()
        if text.startswith('```'):
            text = text.split('\n', 1)[-1]
        if text.endswith('```'):
            text = text.rsplit('```', 1)[0]
        text = text.strip()

        data = json.loads(text)
        return (
            str(data.get('headline', ''))[:300],
            str(data.get('briefing', '')),
            str(data.get('top_priority_board', '')),
        )
    except Exception:
        logger.exception("AI briefing generation failed, using fallback")
        return _fallback_briefing(action_items, awareness_items, quick_items, total_est)


def _fallback_briefing(action_items, awareness_items, quick_items, total_est):
    """Deterministic fallback when AI is unavailable."""
    total = len(action_items) + len(awareness_items) + len(quick_items)
    headline = f"You have {total} item{'s' if total != 1 else ''} in your decision queue today."
    parts = []
    if action_items:
        parts.append(f"{len(action_items)} decision{'s' if len(action_items) != 1 else ''} need your attention")
    if awareness_items:
        parts.append(f"{len(awareness_items)} awareness item{'s' if len(awareness_items) != 1 else ''}")
    if quick_items:
        parts.append(f"{len(quick_items)} quick win{'s' if len(quick_items) != 1 else ''}")
    briefing = ". ".join(parts) + f". Estimated review time: {total_est} minutes."
    return headline, briefing, ''


# ── Task 3: Send Daily Digest Emails ────────────────────────────────────────

@shared_task(name='decision_center.send_daily_digest_emails')
def send_daily_digest_emails():
    """
    Send a daily digest email to every user who has opted in and whose
    preferred digest_time has arrived.  Runs every 30 minutes so we can
    honour per-user time preferences with ±30 min accuracy.
    """
    from datetime import time as dt_time

    from django.core.mail import send_mail
    from django.template.loader import render_to_string

    from decision_center.models import (
        DecisionCenterBriefing,
        DecisionCenterSettings,
        DecisionItem,
    )

    now = timezone.localtime()  # server-local time (Asia/Kolkata per settings)
    current_time = now.time()
    today = now.date()

    # Build a 30-minute window: users whose digest_time falls within
    # [current - 15 min, current + 15 min) will be emailed now.
    window_start = _add_minutes_to_time(current_time, -15)
    window_end = _add_minutes_to_time(current_time, 15)

    settings_qs = DecisionCenterSettings.objects.filter(
        daily_digest_enabled=True,
    ).select_related('user')

    # Filter by time window (handles midnight wraparound)
    if window_start <= window_end:
        settings_qs = settings_qs.filter(
            digest_time__gte=window_start,
            digest_time__lt=window_end,
        )
    else:
        # Window wraps around midnight, e.g. 23:50 → 00:10
        settings_qs = settings_qs.filter(
            Q(digest_time__gte=window_start) | Q(digest_time__lt=window_end),
        )

    sent = 0
    for dc_settings in settings_qs.iterator():
        user = dc_settings.user
        if not user.is_active or not user.email:
            continue

        # Skip if we already emailed this user today (idempotency guard)
        cache_key = f'dc_digest_sent_{user.id}_{today.isoformat()}'
        from django.core.cache import cache
        if cache.get(cache_key):
            continue

        # Gather pending items
        pending = DecisionItem.objects.filter(
            created_for=user, status='pending',
        )
        action_items = list(
            pending.filter(priority_level='action_required')
            .only('title', 'description', 'suggested_action')[:15]
        )
        awareness_items = (
            list(pending.filter(priority_level='awareness').only('title')[:10])
            if dc_settings.show_awareness_items else []
        )
        quick_win_items = (
            list(pending.filter(priority_level='quick_win').only('title')[:10])
            if dc_settings.show_quick_wins else []
        )

        total_items = len(action_items) + len(awareness_items) + len(quick_win_items)
        if total_items == 0:
            continue  # Nothing to report

        est_minutes = sum(
            pending.values_list('estimated_minutes', flat=True)
        )

        # Today's AI briefing (if generated)
        briefing = (
            DecisionCenterBriefing.objects
            .filter(user=user, generated_at__date=today)
            .first()
        )

        context = {
            'user_name': user.get_full_name() or user.username,
            'briefing_headline': briefing.headline if briefing else '',
            'briefing_text': briefing.briefing if briefing else '',
            'action_count': len(action_items),
            'awareness_count': len(awareness_items),
            'quick_win_count': len(quick_win_items),
            'estimated_minutes': est_minutes,
            'action_items': action_items,
            'awareness_items': awareness_items,
            'quick_win_items': quick_win_items,
            'show_awareness': dc_settings.show_awareness_items,
            'show_quick_wins': dc_settings.show_quick_wins,
            'decision_center_url': _build_decision_center_url(),
        }

        subject = (
            f'PrizmAI Decision Center: {len(action_items)} action'
            f'{"s" if len(action_items) != 1 else ""} required'
        )
        body_text = render_to_string(
            'decision_center/email/daily_digest.txt', context,
        )
        body_html = render_to_string(
            'decision_center/email/daily_digest.html', context,
        )

        try:
            send_mail(
                subject=subject,
                message=body_text,
                from_email=None,  # uses DEFAULT_FROM_EMAIL
                recipient_list=[user.email],
                html_message=body_html,
                fail_silently=False,
            )
            cache.set(cache_key, True, 60 * 60 * 20)  # expires in 20 h
            sent += 1
            logger.info(
                'Decision Center digest sent to %s (%s)',
                user.email, user.pk,
            )
        except Exception:
            logger.exception(
                'Failed to send Decision Center digest to %s (%s)',
                user.email, user.pk,
            )

    logger.info('send_daily_digest_emails: %d emails sent', sent)
    return {'sent': sent}


def _add_minutes_to_time(t, minutes):
    """Return a datetime.time offset by *minutes* (may wrap around midnight)."""
    from datetime import datetime as dt, timedelta as td
    combined = dt.combine(dt.today(), t) + td(minutes=minutes)
    return combined.time()


def _build_decision_center_url():
    """Best-effort absolute URL to the Decision Center page."""
    try:
        from django.conf import settings as django_settings
        base = getattr(django_settings, 'SITE_URL', '') or 'http://127.0.0.1:8000'
        return f'{base.rstrip("/")}/decision-center/'
    except Exception:
        return 'http://127.0.0.1:8000/decision-center/'
