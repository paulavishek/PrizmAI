"""
Dynamic Demo Date Refresh Service
Automatically refreshes all demo data dates to be relative to the current date.
This ensures demo data always appears fresh regardless of when users access it.

IMPORTANT ARCHITECTURAL NOTES:
------------------------------
1. This service ONLY refreshes SEED/ORIGINAL demo data, NOT user-created content.
   - Seed demo data: created_by_session is NULL or empty
   - User-created data: created_by_session is set to their session ID
   
2. The refresh runs once per day (cached) to avoid performance impact.
   - First demo access of the day triggers the refresh
   - All subsequent accesses that day skip the refresh
"""

import threading
import time
from contextlib import contextmanager
from datetime import timedelta, date
from django.utils import timezone
from django.db import transaction, OperationalError
from django.core.cache import cache
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

# Cache key for last refresh timestamp
DEMO_DATE_REFRESH_CACHE_KEY = 'demo_data_last_refresh_date'

# Thread-local storage for board-scoped refresh
_local = threading.local()


@contextmanager
def _scoped_to_boards(board_ids):
    """Context manager to restrict _get_demo_board_ids() to a specific set."""
    _local.scoped_board_ids = board_ids
    try:
        yield
    finally:
        _local.scoped_board_ids = None


def _get_demo_board_ids():
    """
    Get all board IDs that should be refreshed: template boards from demo
    organisations AND sandbox copies.  When called inside a
    ``_scoped_to_boards([id])`` context manager the scope is narrowed to
    just the given IDs (used by ``refresh_single_board_dates``).
    """
    scoped = getattr(_local, 'scoped_board_ids', None)
    if scoped is not None:
        return list(scoped)

    try:
        from kanban.models import Board
        demo_org_ids = _get_demo_organizations()
        template_ids = list(
            Board.objects.filter(
                organization_id__in=demo_org_ids
            ).values_list('id', flat=True)
        ) if demo_org_ids else []
        sandbox_ids = list(
            Board.objects.filter(
                is_sandbox_copy=True
            ).values_list('id', flat=True)
        )
        return template_ids + sandbox_ids
    except Exception:
        return []


def should_refresh_demo_dates():
    """
    Check if demo dates need to be refreshed.
    Dates are refreshed once per day to keep demo data current.
    Returns True if refresh is needed.
    """
    last_refresh = cache.get(DEMO_DATE_REFRESH_CACHE_KEY)
    today = timezone.now().date()
    
    if last_refresh is None:
        return True
    
    # If last refresh was on a previous day, refresh is needed
    if isinstance(last_refresh, str):
        try:
            last_refresh = date.fromisoformat(last_refresh)
        except (ValueError, TypeError):
            return True
    
    return last_refresh < today


def mark_demo_dates_refreshed():
    """Mark that demo dates have been refreshed today."""
    today = timezone.now().date().isoformat()
    # Cache for 25 hours to ensure we refresh at least once per day
    cache.set(DEMO_DATE_REFRESH_CACHE_KEY, today, 60 * 60 * 25)


def refresh_single_board_dates(board_id):
    """
    Refresh dates for a single board only.

    Used after sandbox provisioning so that only the newly created board is
    updated instead of triggering a global refresh across all users'
    sandboxes.  Does NOT mark the daily cache so the full daily refresh still
    runs later.
    """
    with _scoped_to_boards([board_id]):
        return refresh_all_demo_dates(skip_mark_cache=True)


# How many times to re-run the whole demo-date refresh if a SQLite write lock
# poisons its single all-or-nothing transaction.
_MAX_DEMO_REFRESH_ATTEMPTS = 4


def refresh_all_demo_dates(skip_mark_cache=False):
    """
    Refresh all SEED demo data dates to be relative to the current date.

    Public entry point. Delegates to ``_refresh_all_demo_dates_once`` and retries
    the ENTIRE refresh if a SQLite write lock poisoned the transaction (raised as
    ``OperationalError``). The refresh is fully idempotent, so a retry re-runs it
    from scratch — this is what guarantees a demo Reset always converges on the
    same dates instead of committing whatever partial state a lock left behind
    (the "different Time Tracking data on every Reset" bug). ``transaction_mode:
    IMMEDIATE`` (settings) makes such locks rare in the first place; this is the
    belt-and-suspenders net for the ones that still slip through.
    """
    for attempt in range(_MAX_DEMO_REFRESH_ATTEMPTS):
        try:
            return _refresh_all_demo_dates_once(skip_mark_cache=skip_mark_cache)
        except OperationalError as e:
            if attempt < _MAX_DEMO_REFRESH_ATTEMPTS - 1:
                logger.warning(
                    f"Demo date refresh hit a DB lock (attempt {attempt + 1}/"
                    f"{_MAX_DEMO_REFRESH_ATTEMPTS}); retrying: {e}"
                )
                time.sleep(0.5 * (attempt + 1))
                continue
            logger.error(
                f"Demo date refresh failed after {_MAX_DEMO_REFRESH_ATTEMPTS} "
                f"attempts: {e}"
            )
            raise


def _refresh_all_demo_dates_once(skip_mark_cache=False):
    """
    Refresh all SEED demo data dates to be relative to the current date.

    IMPORTANT: This only refreshes original demo data, not user-created content.
    User-created content (tasks, boards with created_by_session set) is preserved
    and will be cleaned up by the 48-hour reset system instead.

    Runs as a single all-or-nothing transaction: if a SQLite write lock poisons
    it, this raises ``OperationalError`` (see the needs_rollback check) so the
    ``refresh_all_demo_dates`` wrapper can retry rather than commit a partial
    refresh. Returns a dict of statistics about what was updated.

    Args:
        skip_mark_cache: If True, do not mark the global "refreshed today"
            cache.  Used by ``refresh_single_board_dates`` so that the daily
            full refresh still runs later.
    """
    stats = {
        'tasks_updated': 0,
        'milestones_updated': 0,
        'time_entries_updated': 0,
        'engagement_records_updated': 0,
        'retrospectives_updated': 0,
        'retrospective_ai_model_updated': 0,
        'retrospective_metrics_updated': 0,
        'velocity_snapshots_updated': 0,
        'coaching_suggestions_updated': 0,
        'pm_metrics_updated': 0,
        'conflicts_updated': 0,
        'wiki_pages_updated': 0,
        'ai_sessions_updated': 0,
        'improvement_metrics_updated': 0,
        'action_items_updated': 0,
        'burndown_predictions_updated': 0,
        'resource_leveling_updated': 0,
        'scope_snapshots_updated': 0,
        'roi_snapshots_updated': 0,
        'trend_analysis_updated': 0,
        'sprint_milestones_updated': 0,
        'skill_development_plans_updated': 0,
        'task_activities_updated': 0,
        'completed_task_dates_updated': 0,
        'commitment_protocols_updated': 0,
        'comments_updated': 0,
        'chat_messages_updated': 0,
        'boards_deadline_updated': 0,
        'column_entered_at_updated': 0,
        'memory_nodes_updated': 0,
        'calendar_events_updated': 0,
    }
    
    now = timezone.now()
    base_date = now.date()
    
    try:
        with transaction.atomic():
            def _safe(fn, key):
                """
                Run a refresh sub-function inside its own savepoint so that
                any database error (e.g. IntegrityError from a unique
                constraint) is rolled back to the savepoint rather than
                corrupting the outer transaction.
                """
                try:
                    with transaction.atomic():
                        stats[key] = fn()
                except Exception as e:
                    logger.warning(f"Refresh sub-function '{key}' failed: {e}")

            # 1. Refresh Task dates
            stats['tasks_updated'] = _refresh_task_dates(now, base_date)

            # 1b. Refresh column-entry timestamps so Task Aging badges always show
            #     a realistic spread (grey / amber / red) on demo boards.
            stats['column_entered_at_updated'] = _refresh_column_entered_at(now, base_date)

            # 1c. Refresh CalendarEvent dates (meetings, OOO, busy blocks) so
            #     the demo calendar always shows current dates instead of
            #     drifting into the past.
            stats['calendar_events_updated'] = _refresh_calendar_event_dates(now, base_date)

            # 2. Refresh Time Entry dates
            stats['time_entries_updated'] = _refresh_time_entry_dates(base_date)

            # 3. Refresh Stakeholder Engagement dates
            stats['engagement_records_updated'] = _refresh_engagement_dates(base_date)

            # 4. Refresh Retrospective dates
            stats['retrospectives_updated'] = _refresh_retrospective_dates(base_date)

            # 4b. Keep "Model Used" in sync with the current AI tier config
            _safe(lambda: _refresh_retrospective_ai_model(), 'retrospective_ai_model_updated')

            # 4c. Keep task-derived retrospective metrics (Total Tasks,
            #     Completion Rate, Improvement Metrics) in sync with the
            #     live Task rows, since task dates just shifted in step 1.
            _safe(lambda: _refresh_retrospective_metrics(), 'retrospective_metrics_updated')

            # 5. Refresh Velocity Snapshot dates (uses savepoint: deletes +
            #    regenerates weekly snapshots, and the unique constraint can
            #    raise IntegrityError on the legacy non-weekly path).
            _safe(lambda: _refresh_velocity_snapshot_dates(base_date), 'velocity_snapshots_updated')

            # 6. Refresh Coaching Suggestion dates
            stats['coaching_suggestions_updated'] = _refresh_coaching_suggestion_dates(now)

            # 8. Refresh PM Metrics dates (uses savepoint: unique-constraint risk)
            _safe(lambda: _refresh_pm_metrics_dates(base_date), 'pm_metrics_updated')

            # 9. Refresh Conflict Detection dates
            stats['conflicts_updated'] = _refresh_conflict_dates(now)

            # 10. Refresh Wiki Page dates
            _safe(lambda: _refresh_wiki_dates(now), 'wiki_pages_updated')

            # 11. Refresh AI Assistant Session dates
            _safe(lambda: _refresh_ai_session_dates(now), 'ai_sessions_updated')

            # 12. Refresh Improvement Metrics dates
            stats['improvement_metrics_updated'] = _refresh_improvement_metrics_dates(base_date)

            # 13. Refresh Retrospective Action Items
            stats['action_items_updated'] = _refresh_action_item_dates(now, base_date)

            # 14. Refresh Burndown Predictions
            stats['burndown_predictions_updated'] = _refresh_burndown_prediction_dates(now, base_date)

            # 15. Refresh Resource Leveling Analysis
            stats['resource_leveling_updated'] = _refresh_resource_leveling_dates(now, base_date)

            # 16. Refresh ROI Snapshots
            stats['roi_snapshots_updated'] = _refresh_roi_snapshot_dates(base_date)

            # 17. Refresh Trend Analysis
            stats['trend_analysis_updated'] = _refresh_trend_analysis_dates(base_date)

            # 18. Refresh Sprint Milestones (burndown_models)
            stats['sprint_milestones_updated'] = _refresh_sprint_milestone_dates(base_date)

            # 19. Refresh Skill Development Plans
            stats['skill_development_plans_updated'] = _refresh_skill_development_plan_dates(now, base_date)

            # 20. Refresh Scope Snapshots and Alerts
            stats['scope_snapshots_updated'] = _refresh_scope_snapshot_dates(now, base_date)

            # 21. Refresh TaskActivity dates (for Completion Velocity chart)
            stats['task_activities_updated'] = _refresh_task_activity_dates(now)

            # 22. Spread updated_at for completed tasks (for Completion Velocity chart)
            stats['completed_task_dates_updated'] = _refresh_completed_task_updated_at(now)

            # 23. Refresh Commitment Protocol dates
            stats['commitment_protocols_updated'] = _refresh_commitment_protocol_dates(now, base_date)

            # 24. Refresh Comment timestamps
            stats['comments_updated'] = _refresh_comment_dates(now)

            # 25. Refresh Chat Message / TaskThreadComment timestamps
            stats['chat_messages_updated'] = _refresh_chat_message_dates(now)

            # 26. Refresh project_deadline on demo boards (always ~150 days ahead)
            stats['boards_deadline_updated'] = _refresh_board_deadlines(base_date)

            # 27. Refresh Organizational Memory (knowledge graph) node dates so
            #     they track the tasks/events they describe instead of drifting.
            _safe(lambda: _refresh_memory_node_dates(base_date), 'memory_nodes_updated')

            # 28. Refresh Exit Protocol wind-down dates (buried hospice session,
            #     extracted organs, health-signal history) so they stay relative
            #     to today instead of drifting from their frozen clone dates.
            _safe(lambda: _refresh_exit_protocol_dates(base_date), 'exit_protocol_dates_updated')

            # A "database is locked" swallowed by one of the directly-called
            # refreshers above (e.g. _refresh_task_dates) leaves the connection
            # flagged needs_rollback, silently no-opping every step after it and
            # rolling the whole atomic back on exit. That half-applied state is
            # exactly why demo Resets showed different Time Tracking data each
            # time. Turn it into a real error so the caller retries the entire
            # (idempotent) refresh instead of committing a partial one.
            if transaction.get_connection().needs_rollback:
                raise OperationalError(
                    "demo date refresh transaction was poisoned (likely a SQLite "
                    "write lock); rolling back to retry"
                )

        # Mark refresh as complete
        if not skip_mark_cache:
            mark_demo_dates_refreshed()

        logger.info(f"Demo dates refreshed: {stats}")
        return stats

    except Exception as e:
        logger.error(f"Error refreshing demo dates: {e}")
        raise


def _refresh_board_deadlines(base_date):
    """
    Keep project_deadline on every demo board (official templates and sandbox
    copies) at exactly 150 days from today.  This makes burn-rate projections
    and sustainability calculations always show a realistic future horizon,
    no matter when the demo is viewed.
    """
    try:
        from kanban.models import Board
        from datetime import timedelta

        target_deadline = base_date + timedelta(days=150)
        demo_board_ids = _get_demo_board_ids()
        if not demo_board_ids:
            return 0
        updated = Board.objects.filter(
            pk__in=demo_board_ids
        ).update(project_deadline=target_deadline)
        return updated
    except Exception as e:
        logger.warning(f"_refresh_board_deadlines failed: {e}")
        return 0


# Newest seeded memory sits this many days before "today" — matches the seeder,
# where the most recent auto-captured memory is created at past(7).
MEMORY_ANCHOR_OFFSET = 7


def _refresh_memory_node_dates(base_date):
    """
    Keep Organizational Memory (knowledge graph) node dates relative to "today",
    the same way task dates are kept current.

    Without this, MemoryNode.created_at values stay frozen at seed time while
    every other demo entity (tasks, conflicts, AI sessions, ...) is shifted
    forward on each daily refresh — so memory dates would slowly drift into the
    past relative to the tasks and events they describe.

    APPROACH: Offset-preserving uniform shift (same idea as _refresh_task_dates).
    Per demo board, the newest memory is anchored to MEMORY_ANCHOR_OFFSET days
    before today and every node is shifted by that single delta, so the relative
    spacing between memories — and their alignment with the events narrated in
    their content — is preserved.

    created_at is auto_now_add, so we bypass it with an F() update.
    """
    try:
        from knowledge_graph.models import MemoryNode
        from django.db.models import Max, F
        from datetime import timedelta

        demo_board_ids = _get_demo_board_ids()
        if not demo_board_ids:
            return 0

        total = 0
        for board_id in demo_board_ids:
            newest = MemoryNode.objects.filter(board_id=board_id).aggregate(
                newest=Max('created_at')
            )['newest']
            if not newest:
                continue

            target_newest = timezone.now() - timedelta(days=MEMORY_ANCHOR_OFFSET)
            shift = target_newest - newest
            # Skip churn when the board's memories are already current (e.g. right
            # after Reset Demo, the seed dates are correct and shift is ~0).
            if abs(shift) < timedelta(days=1):
                continue

            total += MemoryNode.objects.filter(board_id=board_id).update(
                created_at=F('created_at') + shift
            )
        return total
    except Exception as e:
        logger.warning(f"_refresh_memory_node_dates failed: {e}")
        return 0


# Exit Protocol wind-down anchors — how many days before "today" the demo's
# buried hospice session sits. Kept in step with the offsets used by the
# ``seed_exit_protocol_demo`` management command.
HOSPICE_INITIATED_DAYS_AGO = 90
HOSPICE_BURIED_DAYS_AGO = 75
ORGAN_EXTRACTED_DAYS_AGO = 77


def _refresh_exit_protocol_dates(base_date):
    """
    Keep Exit Protocol wind-down timestamps relative to "today".

    The demo's buried HospiceSession, its extracted ProjectOrgans, and the
    ProjectHealthSignal history are otherwise frozen at seed/clone time (the
    sandbox clone deliberately preserves the template's original dates), so
    without this they slowly drift into the past relative to every other demo
    entity that is shifted forward on each daily refresh.

    HospiceSession + ProjectOrgan carry a single logical event each, so they are
    re-anchored to fixed absolute offsets before today. ProjectHealthSignal is a
    time series whose relative spacing feeds the Health Signal History chart, so
    it gets an offset-preserving uniform shift (same idea as memory nodes).

    All three fields are auto-populated on insert, so we bypass them with .update().
    """
    try:
        from exit_protocol.models import HospiceSession, ProjectOrgan, ProjectHealthSignal
        from django.db.models import Max, F
        from datetime import timedelta

        demo_board_ids = _get_demo_board_ids()
        if not demo_board_ids:
            return 0

        now = timezone.now()
        total = 0

        # Buried sessions -> fixed offsets.
        total += HospiceSession.objects.filter(board_id__in=demo_board_ids).update(
            initiated_at=now - timedelta(days=HOSPICE_INITIATED_DAYS_AGO),
            buried_at=now - timedelta(days=HOSPICE_BURIED_DAYS_AGO),
        )
        total += ProjectOrgan.objects.filter(source_board_id__in=demo_board_ids).update(
            extracted_at=now - timedelta(days=ORGAN_EXTRACTED_DAYS_AGO),
        )

        # Health-signal history -> offset-preserving shift per board.
        for board_id in demo_board_ids:
            newest = ProjectHealthSignal.objects.filter(board_id=board_id).aggregate(
                newest=Max('recorded_at')
            )['newest']
            if not newest:
                continue
            shift = now - newest
            if abs(shift) < timedelta(days=1):
                continue
            total += ProjectHealthSignal.objects.filter(board_id=board_id).update(
                recorded_at=F('recorded_at') + shift
            )
        return total
    except Exception as e:
        logger.warning(f"_refresh_exit_protocol_dates failed: {e}")
        return 0


def _get_demo_organizations():
    """Get demo organization IDs for filtering."""
    try:
        from accounts.models import Organization
        demo_orgs = Organization.objects.filter(is_demo=True)
        return list(demo_orgs.values_list('id', flat=True))
    except Exception:
        return []


def _is_seed_demo_data(obj):
    """
    Check if an object is original seed demo data (not user-created).
    User-created content has created_by_session set to their session ID.
    Seed demo data has created_by_session as NULL or empty.
    """
    if hasattr(obj, 'created_by_session'):
        session = getattr(obj, 'created_by_session', None)
        return session is None or session == ''
    # If the model doesn't have created_by_session field, assume it's seed data
    return True



# Fixed day-offsets (from "today") for each demo CalendarEvent, keyed by
# title. Mirrors the small fixed-narrative-set pattern used by
# _OVERDUE_PINS in _refresh_task_dates below, rather than the generic
# created_at-relative shift used for bulk datasets — there are only a
# handful of these, each with a specific narrative role (see
# populate_calendar_demo_data), so pinning them directly to a day-offset
# from "today" is simpler and keeps them exactly in sync with the task
# deadlines they're written to overlap (e.g. "Marcus Chen - PTO" and
# "Focus Block: File Upload Review" both pin to the same day-offset as the
# "File Upload System" task's due date).
_CALENDAR_EVENT_PINS = {
    'Daily Standup':                       {'day_offset': 0,  'time': (9, 0),  'duration_min': 15},
    'Sprint 3 Planning':                   {'day_offset': 2,  'time': (10, 0), 'duration_min': 90},
    'Architecture Review: Search Engine':  {'day_offset': 4,  'time': (14, 0), 'duration_min': 60},
    'Sprint 2 Retrospective':              {'day_offset': -3, 'time': (15, 0), 'duration_min': 60},
    'Team Lunch - Sprint 2 Celebration':   {'day_offset': 7,  'time': (12, 0), 'duration_min': 90},
    'Marcus Chen - PTO':                   {'day_offset': 2,  'all_day': True},
    'Focus Block: Code Review':            {'day_offset': 1,  'time': (13, 0), 'duration_min': 120},
    'Stakeholder Demo - Core Features':    {'day_offset': 6,  'time': (11, 0), 'duration_min': 60},
    'Focus Block: File Upload Review':     {'day_offset': 2,  'time': (10, 0), 'duration_min': 120},
    '1:1: Priya & Marcus':                 {'day_offset': 3,  'time': (16, 0), 'duration_min': 30},
    'All-Hands: Q3 Roadmap Review':        {'day_offset': 9,  'time': (11, 0), 'duration_min': 60},
}


def _refresh_calendar_event_dates(now, base_date):
    """
    Refresh demo CalendarEvent start/end datetimes to fixed day-offsets from
    "today", keyed by title via _CALENDAR_EVENT_PINS.

    _get_demo_board_ids() already covers both template boards and every
    sandbox copy, and _clone_calendar_events_for_user (kanban/sandbox_views.py)
    clones events onto each sandbox with identical titles — so this single
    query refreshes the template board and every user's cloned events in one
    pass, no sandbox-specific logic needed.
    """
    try:
        import datetime as _dt
        from kanban.models import CalendarEvent

        demo_board_ids = _get_demo_board_ids()
        if not demo_board_ids:
            return 0

        events = CalendarEvent.objects.filter(
            board_id__in=demo_board_ids, title__in=_CALENDAR_EVENT_PINS.keys(),
        )

        updated = 0
        for ev in events:
            pin = _CALENDAR_EVENT_PINS[ev.title]
            target_date = base_date + timedelta(days=pin['day_offset'])
            if pin.get('all_day'):
                new_start = timezone.make_aware(_dt.datetime.combine(target_date, _dt.time(0, 0)))
                new_end = timezone.make_aware(_dt.datetime.combine(target_date, _dt.time(23, 59)))
            else:
                hour, minute = pin['time']
                new_start = timezone.make_aware(_dt.datetime.combine(target_date, _dt.time(hour, minute)))
                new_end = new_start + timedelta(minutes=pin['duration_min'])

            if ev.start_datetime != new_start or ev.end_datetime != new_end:
                CalendarEvent.objects.filter(pk=ev.pk).update(
                    start_datetime=new_start, end_datetime=new_end,
                )
                updated += 1

        return updated
    except Exception as e:
        logger.warning(f"Error refreshing calendar event dates: {e}")
        return 0


def _refresh_task_dates(now, base_date):
    """
    Refresh task due_date and start_date fields.
    ONLY refreshes original seed demo data, not user-created content.

    APPROACH: Offset-preserving shift.
    ─────────────────────────────────
    Rather than rescheduling every task from scratch (which destroys the
    carefully designed parallel dependency chains in populate_demo_data),
    we shift ALL tasks in each board by a single uniform delta so that
    the earliest task in the board starts a fixed number of days before
    today.  This means:

    • The *relative* positions of tasks (offsets) are unchanged → the
      critical-path topology and slack values are preserved.
    • The *absolute* dates are updated to stay current so the Gantt chart
      always looks like an active project.
    • Task durations (due_date − start_date) are never modified.

    Edge-case: tasks that have no start_date are left untouched.
    """
    try:
        from kanban.models import Task, Column
        from django.db.models import Q
        import datetime as _dt

        demo_board_ids = _get_demo_board_ids()
        if not demo_board_ids:
            return 0

        # Only seed demo tasks (not user-created)
        tasks = list(Task.objects.filter(
            column__board_id__in=demo_board_ids
        ).filter(
            Q(created_by_session__isnull=True) | Q(created_by_session='')
        ).select_related('column'))

        if not tasks:
            return 0

        # ── Group by board ────────────────────────────────────────────────────
        tasks_by_board = {}
        for task in tasks:
            if task.start_date is None:
                continue  # milestones/tasks without start_date are left alone
            board_id = task.column.board_id if task.column else 0
            tasks_by_board.setdefault(board_id, []).append(task)

        tasks_to_update = []

        for board_id, board_tasks in tasks_by_board.items():
            # Find the earliest start_date across this entire board.
            min_start = min(t.start_date for t in board_tasks)

            # We want the first task to start `anchor_offset` days before today
            # so that "today" falls in Phase 1's active work zone: completed
            # tasks are in the past, in-progress tasks span today, and to-do
            # tasks are in the future.  With ~58-day Phase 1 and seed=42 gaps,
            # anchor=40 puts 5 done tasks + 2 overdue in-progress tasks before
            # today, giving a realistic SPI ≈ 0.71 and a clean Gantt layout.
            anchor_offset = 40  # days before today
            new_anchor = base_date - timedelta(days=anchor_offset)

            # Shift delta: how many days to move every date
            shift = (new_anchor - min_start).days  # can be positive or negative

            if shift == 0:
                continue  # dates are already current – nothing to do

            for task in board_tasks:
                # New start_date (always a date object on the model)
                new_start = task.start_date + timedelta(days=shift)

                # Preserve the original duration: due_date − start_date
                if task.due_date:
                    # due_date is a DateTimeField (datetime) stored in UTC.
                    # Convert to local time before extracting date to avoid
                    # off-by-one errors when the local tz is ahead of UTC
                    # (e.g. Asia/Kolkata midnight → previous day in UTC).
                    if hasattr(task.due_date, 'date'):
                        old_due_date = timezone.localtime(task.due_date).date()
                    else:
                        old_due_date = task.due_date
                    duration_days = (old_due_date - task.start_date).days
                else:
                    # Fallback duration from complexity when due_date is absent
                    complexity = getattr(task, 'complexity_score', 5) or 5
                    duration_days = max(3, min((complexity // 2) + 3, 6))

                new_due_date = new_start + timedelta(days=duration_days)
                # Use noon (12:00) to avoid date boundary issues across timezones
                new_due_datetime = timezone.make_aware(
                    _dt.datetime.combine(new_due_date, _dt.time(12, 0))
                )

                task.start_date = new_start
                task.due_date = new_due_datetime
                # Shift completed_at by the SAME uniform delta so a Done task's
                # completion stays aligned with its (shifted) start/due dates.
                # Without this, completed_at stays frozen in the old past while
                # start_date slides forward, leaving created_at AFTER completed_at
                # → negative cycle time → every task collapses into the "1 day"
                # bucket on the Cycle Time analytics chart.
                # Clamp to today: the uniform start-shift can over-advance the
                # most-recent completion past "now" (a Done task must not complete
                # in the future).
                if task.completed_at:
                    shifted_completed = task.completed_at + timedelta(days=shift)
                    today_noon = timezone.make_aware(
                        _dt.datetime.combine(base_date, _dt.time(12, 0))
                    )
                    task.completed_at = min(shifted_completed, today_noon)
                tasks_to_update.append(task)

        # After the uniform shift, pin known overdue scenarios to fixed offsets
        # from today so the demo always shows realistic deadline slippage
        # regardless of how many daily refreshes have elapsed.
        # days_started / days_overdue = how many days before today each date lands.
        # days_started must keep each task starting AFTER its predecessor
        # finishes (Security Architecture Patterns lands at today-12 after the
        # uniform shift), so the Gantt never shows a task beginning before the
        # work it depends on.
        _OVERDUE_PINS = {
            'Social Login Integration':     {'days_started': 12, 'days_overdue': 8},
            'Authentication System':        {'days_started': 10, 'days_overdue': 4},
            'Database Schema & Migrations': {'days_started': 15, 'days_overdue': 3},
        }
        for task in tasks_to_update:
            pin = _OVERDUE_PINS.get(task.title)
            if pin and getattr(task, 'progress', 100) < 100:
                task.start_date = base_date - timedelta(days=pin['days_started'])
                task.due_date = timezone.make_aware(
                    _dt.datetime.combine(
                        base_date - timedelta(days=pin['days_overdue']),
                        _dt.time(12, 0),
                    )
                )

        if tasks_to_update:
            Task.objects.bulk_update(
                tasks_to_update, ['due_date', 'start_date', 'completed_at'], batch_size=500
            )

        # Re-derive created_at (auto_now_add=True, so bypass via .update()) so the
        # analytics charts that key off task age look professional. This runs for
        # EVERY demo board on EVERY refresh — independent of the uniform shift
        # above (when dates are already current, shift==0 and tasks_to_update is
        # empty, but created_at still needs to be reshaped). It is type-aware and
        # ranked deterministically by id so the spread is stable across resets:
        #   • Done tasks      → created_at = completed_at - DESIRED_CYCLE[rank] so
        #     the Cycle Time Distribution fills every bucket instead of collapsing
        #     into "1-2 weeks"/"2+ weeks". (A short-cycle task may land created_at
        #     slightly after start_date — purely cosmetic; the Gantt uses
        #     start/due, and cycle = completed_at - created_at.)
        #   • Backlog tasks   → created_at = today - BACKLOG_AGE[rank] so the Task
        #     Age in Backlog chart spans <1wk … >1mo. (Backlog tasks have FUTURE
        #     start_dates, so the old start_date-based rule put every one in the
        #     "< 1 week" bucket.)
        #   • Everything else → keep the original start_date - (id%7+1) rule.
        DESIRED_CYCLE = [1, 3, 5, 6, 9, 12, 16, 20]   # days, spans all 5 buckets
        BACKLOG_AGE = [3, 6, 10, 16, 22, 30, 40, 50]  # days, spans all 4 buckets

        # Group ALL loaded demo tasks (not just shifted ones) by board. These are
        # the same objects mutated above, so completed_at reflects any shift.
        tasks_by_board_all = {}
        for task in tasks:
            board_id = task.column.board_id if task.column else 0
            tasks_by_board_all.setdefault(board_id, []).append(task)

        for board_id, board_tasks in tasks_by_board_all.items():
            # Match get_backlog_age_distribution()'s column selection so the tasks
            # we age are exactly the ones that chart reads.
            backlog_col = (
                Column.objects.filter(board_id=board_id)
                .filter(
                    Q(name__icontains='to do')
                    | Q(name__icontains='todo')
                    | Q(name__icontains='backlog')
                )
                .order_by('position')
                .first()
            )
            if not backlog_col:
                backlog_col = (
                    Column.objects.filter(board_id=board_id)
                    .order_by('position')
                    .first()
                )
            backlog_col_id = backlog_col.id if backlog_col else None

            # Restrict to item_type='task' so the ranking matches exactly the
            # tasks the Cycle Time / Backlog Age charts read (they exclude
            # milestones). Milestones fall through to the default rule below.
            done_tasks = sorted(
                (t for t in board_tasks
                 if getattr(t, 'item_type', 'task') == 'task'
                 and getattr(t, 'progress', 0) == 100 and t.completed_at),
                key=lambda t: t.id,
            )
            backlog_tasks = sorted(
                (t for t in board_tasks
                 if getattr(t, 'item_type', 'task') == 'task'
                 and getattr(t, 'progress', 0) != 100
                 and t.column and t.column_id == backlog_col_id),
                key=lambda t: t.id,
            )
            done_ids = {t.id for t in done_tasks}
            backlog_ids = {t.id for t in backlog_tasks}

            for rank, task in enumerate(done_tasks):
                cycle_days = DESIRED_CYCLE[rank % len(DESIRED_CYCLE)]
                created_dt = task.completed_at - timedelta(days=cycle_days)
                Task.objects.filter(pk=task.pk).update(created_at=created_dt)

            def _aware_noon(d):
                # created_at is a DateTimeField; build a tz-aware noon datetime so
                # the calendar date is stable and Django gets no naive datetime.
                return timezone.make_aware(_dt.datetime.combine(d, _dt.time(12, 0)))

            for rank, task in enumerate(backlog_tasks):
                age_days = BACKLOG_AGE[rank % len(BACKLOG_AGE)]
                created_dt = _aware_noon(base_date - timedelta(days=age_days))
                Task.objects.filter(pk=task.pk).update(created_at=created_dt)

            for task in board_tasks:
                if task.id in done_ids or task.id in backlog_ids:
                    continue
                if task.start_date:
                    days_before = (task.id % 7) + 1  # deterministic per task
                    created_dt = _aware_noon(task.start_date - timedelta(days=days_before))
                    Task.objects.filter(pk=task.pk).update(created_at=created_dt)

        return len(tasks_to_update)

    except Exception as e:
        logger.warning(f"Error refreshing task dates: {e}")
        return 0


# Days-in-current-column ages assigned to demo tasks, ranked per column. With the
# default 7/14 thresholds (grey "show" = 4) this leads with visible values so even a
# 1-2 task column shows a badge: amber → red → grey, then a spread that still includes
# fresh (hidden) cards for larger columns. Stable across resets (ranked by id).
_COLUMN_AGE_SPREAD = [9, 18, 5, 25, 12, 1, 3, 6]


def _refresh_column_entered_at(now, base_date):
    """
    Stamp a deterministic spread of ``column_entered_at`` values on SEED demo tasks
    so the Task Aging badges always render a realistic mix on demo boards — instead
    of every freshly provisioned/cloned task reading 0 days (badge hidden).

    Uses ``.update()`` to bypass the ``track_column_entry_time`` pre_save signal
    (which would otherwise reset the value to "now"). Only touches seed demo data
    (created_by_session NULL/empty), never user-created tasks. Done/Backlog columns
    are aging-disabled so their badges stay hidden regardless of the value here.
    """
    try:
        from kanban.models import Task
        from django.db.models import Q

        demo_board_ids = _get_demo_board_ids()
        if not demo_board_ids:
            return 0

        tasks = list(
            Task.objects.filter(
                column__board_id__in=demo_board_ids,
                item_type='task',
            ).filter(
                Q(created_by_session__isnull=True) | Q(created_by_session='')
            ).select_related('column')
        )
        if not tasks:
            return 0

        # Group by (board, column) and rank by id so the spread is stable.
        by_column = {}
        for t in tasks:
            key = (t.column.board_id if t.column else 0, t.column_id)
            by_column.setdefault(key, []).append(t)

        updated = 0
        for col_tasks in by_column.values():
            for rank, task in enumerate(sorted(col_tasks, key=lambda t: t.id)):
                age = _COLUMN_AGE_SPREAD[rank % len(_COLUMN_AGE_SPREAD)]
                Task.objects.filter(pk=task.pk).update(
                    column_entered_at=now - timedelta(days=age)
                )
                updated += 1
        return updated

    except Exception as e:
        logger.warning(f"Error refreshing column_entered_at: {e}")
        return 0



def _refresh_time_entry_dates(base_date):
    """
    Refresh time entry work_date fields.
    ONLY refreshes entries for original seed demo tasks, not user-created.

    Entries are spread WITHIN each task's (already-refreshed) work window,
    keyed off each entry's ordinal position among its task's entries — mirroring
    the seeder's spread (populate_all_demo_data._create_budget_and_time). The old
    implementation scattered dates by ``entry.id % 30``, which was NOT stable
    across a demo Reset: reseeding/re-cloning mints fresh primary keys, so the
    same logical entry landed on a different day every reset (users saw the Time
    Tracking dates shift on each Reset Demo). Anchoring to the task window +
    ordinal index is both deterministic across resets AND consistent with the
    task's actual start→completion span that the rest of the demo story tells.
    """
    try:
        from kanban.budget_models import TimeEntry
        from django.db.models import Q

        demo_board_ids = _get_demo_board_ids()
        # Only refresh time entries for SEED demo tasks (not user-created).
        # order_by('task_id', 'id') gives a STABLE per-task ordering: the entry's
        # position within its task drives the date, never its absolute PK.
        entries = list(TimeEntry.objects.filter(
            task__column__board_id__in=demo_board_ids
        ).filter(
            Q(task__created_by_session__isnull=True) | Q(task__created_by_session='')
        ).select_related('task').order_by('task_id', 'id'))

        if not entries:
            return 0

        entries_by_task = {}
        for entry in entries:
            entries_by_task.setdefault(entry.task_id, []).append(entry)

        entries_to_update = []
        for task_entries in entries_by_task.values():
            task = task_entries[0].task
            start = task.start_date
            if not start:
                continue  # no window to anchor to — leave existing dates alone
            if task.completed_at:
                end_date = timezone.localtime(task.completed_at).date()
            else:
                end_date = base_date
            span_days = max((end_date - start).days, 1)
            n = len(task_entries)
            for i, entry in enumerate(task_entries):
                if not entry.work_date:
                    continue
                # Same spread formula the seeder uses within the task window.
                offset = int((i + 1) * span_days / (n + 1))
                # On a SHORT window the formula above collapses: with
                # span_days=1 and n=3 every ordinal maps to offset 0, stacking
                # a task's whole logged effort onto one date (seen as 32h/day
                # in a single-day window). Totals-based views never noticed,
                # but any per-day-vs-capacity read (Calendar Time Health) shows
                # it as an impossible day. Give each entry its own day when the
                # window is too narrow to separate them, still anchored to the
                # task's start and capped at the window end.
                if span_days < n:
                    offset = min(i, span_days)
                entry.work_date = start + timedelta(days=offset)
                entries_to_update.append(entry)

        if entries_to_update:
            TimeEntry.objects.bulk_update(entries_to_update, ['work_date'], batch_size=500)

        return len(entries_to_update)

    except Exception as e:
        logger.warning(f"Error refreshing time entry dates: {e}")
        return 0


def _refresh_engagement_dates(base_date):
    """Refresh stakeholder engagement record dates."""
    try:
        from kanban.stakeholder_models import StakeholderEngagementRecord
        
        demo_board_ids = _get_demo_board_ids()
        records = list(StakeholderEngagementRecord.objects.filter(
            stakeholder__board_id__in=demo_board_ids
        ))
        
        if not records:
            return 0
        
        records_to_update = []
        
        for record in records:
            if not record.date:
                continue
            
            # Engagement records spread across the past 60 days
            days_offset = -(record.id % 60 + 1)
            record.date = base_date + timedelta(days=days_offset)

            # Keep pending follow-up dates in the near future so they never
            # look stale — 5 to 14 days ahead, varied by record id.
            if record.follow_up_required and not record.follow_up_completed:
                record.follow_up_date = base_date + timedelta(days=(record.id % 10 + 5))

            records_to_update.append(record)
        
        if records_to_update:
            StakeholderEngagementRecord.objects.bulk_update(
                records_to_update, ['date', 'follow_up_date'], batch_size=500,
            )
        
        return len(records_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing engagement dates: {e}")
        return 0


def _refresh_retrospective_dates(base_date):
    """Refresh retrospective period_start and period_end fields."""
    try:
        from kanban.retrospective_models import ProjectRetrospective
        
        demo_board_ids = _get_demo_board_ids()
        retrospectives = list(ProjectRetrospective.objects.filter(
            board_id__in=demo_board_ids
        ))
        
        if not retrospectives:
            return 0
        
        retrospectives_to_update = []
        
        for retro in retrospectives:
            status = getattr(retro, 'status', 'finalized')
            retro_type = getattr(retro, 'retrospective_type', 'sprint')
            
            # Determine period based on status and type
            if status in ['finalized', 'archived']:
                # Past retrospectives
                if retro_type == 'quarterly':
                    period_end_offset = -(retro.id % 90 + 30)  # 30-120 days ago
                    period_duration = 90
                elif retro_type == 'project':
                    period_end_offset = -(retro.id % 60 + 15)  # 15-75 days ago
                    period_duration = 30
                else:  # sprint
                    period_end_offset = -(retro.id % 45 + 7)  # 7-52 days ago
                    period_duration = 14
            else:
                # Current/draft retrospectives
                period_end_offset = -(retro.id % 14)  # 0-14 days ago
                period_duration = 14
            
            retro.period_end = base_date + timedelta(days=period_end_offset)
            retro.period_start = retro.period_end - timedelta(days=period_duration)
            retrospectives_to_update.append(retro)
        
        if retrospectives_to_update:
            ProjectRetrospective.objects.bulk_update(retrospectives_to_update, 
                                                     ['period_start', 'period_end'], batch_size=100)
        
        return len(retrospectives_to_update)

    except Exception as e:
        logger.warning(f"Error refreshing retrospective dates: {e}")
        return 0


def _refresh_retrospective_ai_model():
    """
    Recompute ai_model_used for demo retrospectives from the current AI
    tier config (GEMINI_MODEL_COMPLEX / workspace provider), so the "Model
    Used" shown in AI Analysis Metadata doesn't go stale after the model
    tier settings change post-seeding.
    """
    try:
        from kanban.retrospective_models import ProjectRetrospective
        from ai_assistant.utils.ai_router import AIRouter
        from ai_assistant.models import OrganizationAISettings

        demo_board_ids = _get_demo_board_ids()
        retrospectives = list(ProjectRetrospective.objects.filter(
            board_id__in=demo_board_ids
        ).select_related('board__workspace'))

        if not retrospectives:
            return 0

        retrospectives_to_update = []

        for retro in retrospectives:
            try:
                provider = retro.board.workspace.ai_settings.provider or 'gemini'
            except (OrganizationAISettings.DoesNotExist, AttributeError):
                provider = 'gemini'
            current_model = AIRouter.get_model_name(provider, 'complex')
            if retro.ai_model_used != current_model:
                retro.ai_model_used = current_model
                retrospectives_to_update.append(retro)

        if retrospectives_to_update:
            ProjectRetrospective.objects.bulk_update(
                retrospectives_to_update, ['ai_model_used'], batch_size=100
            )

        return len(retrospectives_to_update)

    except Exception as e:
        logger.warning(f"Error refreshing retrospective AI model: {e}")
        return 0


def _refresh_retrospective_metrics():
    """
    Recompute metrics_snapshot's task-derived numbers (total_tasks,
    completed_tasks, completion_rate, velocity, avg_completion_time) and
    the matching ImprovementMetric rows from the actual Task data, for any
    demo retrospective whose metrics_snapshot carries a 'phase_tag' marker
    (set by the seeder to say "this retrospective's numbers should track
    the live Task rows for this phase" instead of staying a frozen literal).

    Task *dates* drift forward on every demo refresh (see
    _refresh_task_dates), so without this, a retrospective's stat cards and
    Improvement Metrics would silently diverge from the task data they
    claim to summarize. Task *count* and *column* are untouched by date
    refreshes, so total_tasks/completed_tasks/completion_rate stay stable;
    only avg_completion_time genuinely varies run to run.
    """
    try:
        from kanban.models import Task
        from kanban.retrospective_models import ProjectRetrospective, ImprovementMetric

        demo_board_ids = _get_demo_board_ids()
        retrospectives = list(ProjectRetrospective.objects.filter(
            board_id__in=demo_board_ids
        ).exclude(metrics_snapshot__phase_tag__isnull=True).select_related('board'))

        if not retrospectives:
            return 0

        retrospectives_to_update = []
        metrics_to_update = []

        for retro in retrospectives:
            phase_tag = retro.metrics_snapshot.get('phase_tag')
            if not phase_tag:
                continue

            tasks = Task.objects.filter(
                column__board=retro.board, phase=phase_tag
            ).exclude(item_type='epic')

            total_tasks = tasks.count()
            if total_tasks == 0:
                continue
            completed_tasks = tasks.filter(progress=100).count()
            completion_rate = round(completed_tasks / total_tasks * 100, 1)

            durations = [
                (t.completed_at.date() - t.start_date).days
                for t in tasks
                if t.start_date and t.completed_at
            ]
            avg_completion_time = round(sum(durations) / len(durations), 1) if durations else None

            snapshot = dict(retro.metrics_snapshot)
            snapshot['total_tasks'] = total_tasks
            snapshot['completed_tasks'] = completed_tasks
            snapshot['completion_rate'] = completion_rate
            snapshot['velocity'] = completed_tasks
            if avg_completion_time is not None:
                snapshot['avg_completion_time'] = avg_completion_time
            retro.metrics_snapshot = snapshot
            retrospectives_to_update.append(retro)

            metric_values = {
                'velocity': completed_tasks,
                'quality': completion_rate,
            }
            if avg_completion_time is not None:
                metric_values['cycle_time'] = avg_completion_time

            for metric in retro.metrics.filter(metric_type__in=metric_values.keys()):
                metric.metric_value = metric_values[metric.metric_type]
                metrics_to_update.append(metric)

        if retrospectives_to_update:
            ProjectRetrospective.objects.bulk_update(
                retrospectives_to_update, ['metrics_snapshot'], batch_size=100
            )
        if metrics_to_update:
            ImprovementMetric.objects.bulk_update(
                metrics_to_update, ['metric_value'], batch_size=100
            )

        return len(retrospectives_to_update)

    except Exception as e:
        logger.warning(f"Error refreshing retrospective metrics: {e}")
        return 0


def _refresh_velocity_snapshot_dates(base_date):
    """Rebuild demo *weekly* velocity snapshots on the canonical ISO-week grid.

    The legacy implementation re-dated every snapshot using ``snapshot.id % 24``,
    which pushed weekly snapshots onto a non-ISO grid that never matched the
    Monday-Sunday keys used by ``BurndownPredictor._ensure_velocity_snapshots``.
    Because the predictor keys ``update_or_create`` on
    ``(board, period_start, period_end)``, the mismatched dates meant it could
    never update the existing rows — it created fresh ones every cycle, so demo
    boards accumulated dozens of duplicate, overlapping snapshots. Combined with
    ``id % 24`` collisions (ids 24 apart map to the same offset) this produced
    2-3 exact-duplicate buckets per week and diluted average velocity toward 0.

    Fix: let the predictor be the single source of truth for weekly velocity.
    Drop the demo weekly snapshots and regenerate them — the predictor derives
    ``tasks_completed`` from ``completed_at``, which ``_refresh_task_dates``
    already keeps current, so velocity rides on the dominant date mechanism
    instead of independently re-dating itself. Non-weekly snapshots (daily /
    sprint / monthly), which aren't subject to this bug, keep the legacy
    id-based re-dating.
    """
    try:
        from kanban.burndown_models import TeamVelocitySnapshot
        from kanban.utils.burndown_predictor import BurndownPredictor
        from kanban.models import Board

        demo_board_ids = _get_demo_board_ids()
        if not demo_board_ids:
            return 0

        refreshed = 0

        # --- Weekly: regenerate on the canonical Monday-Sunday grid ----------
        predictor = BurndownPredictor()
        for board in Board.objects.filter(id__in=demo_board_ids):
            TeamVelocitySnapshot.objects.filter(
                board=board, period_type='weekly'
            ).delete()
            predictor._ensure_velocity_snapshots(board)
            refreshed += TeamVelocitySnapshot.objects.filter(
                board=board, period_type='weekly'
            ).count()

        # --- Non-weekly: preserve legacy id-based re-dating ------------------
        other_snapshots = list(TeamVelocitySnapshot.objects.filter(
            board_id__in=demo_board_ids
        ).exclude(period_type='weekly'))

        snapshots_to_update = []
        for snapshot in other_snapshots:
            period_type = getattr(snapshot, 'period_type', 'weekly')
            if period_type == 'daily':
                period_end_offset = -(snapshot.id % 28 + 1)
                period_duration = 1
            elif period_type == 'sprint':
                period_end_offset = -(snapshot.id % 12 * 14 + 14)
                period_duration = 14
            else:  # monthly
                period_end_offset = -(snapshot.id % 6 * 30 + 30)
                period_duration = 30

            snapshot.period_end = base_date + timedelta(days=period_end_offset)
            snapshot.period_start = snapshot.period_end - timedelta(days=period_duration)
            snapshots_to_update.append(snapshot)

        if snapshots_to_update:
            TeamVelocitySnapshot.objects.bulk_update(
                snapshots_to_update, ['period_start', 'period_end'], batch_size=100)
            refreshed += len(snapshots_to_update)

        return refreshed

    except Exception as e:
        logger.warning(f"Error refreshing velocity snapshot dates: {e}")
        return 0


def _refresh_coaching_suggestion_dates(now):
    """Refresh coaching suggestion created_at and updated_at fields."""
    try:
        from kanban.coach_models import CoachingSuggestion
        
        demo_board_ids = _get_demo_board_ids()
        suggestions = list(CoachingSuggestion.objects.filter(
            board_id__in=demo_board_ids
        ))
        
        if not suggestions:
            return 0
        
        suggestions_to_update = []
        
        for suggestion in suggestions:
            status = getattr(suggestion, 'status', 'active')
            
            # Distribute suggestions based on status
            if status in ['resolved', 'dismissed', 'expired']:
                days_offset = -(suggestion.id % 30 + 3)  # 3-33 days ago
            elif status in ['acknowledged', 'in_progress']:
                days_offset = -(suggestion.id % 7 + 1)  # 1-7 days ago
            else:  # active
                days_offset = -(suggestion.id % 3)  # 0-2 days ago
            
            suggestion.created_at = now + timedelta(days=days_offset)
            suggestions_to_update.append(suggestion)
        
        if suggestions_to_update:
            CoachingSuggestion.objects.bulk_update(suggestions_to_update, 
                                                   ['created_at'], batch_size=100)
        
        return len(suggestions_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing coaching suggestion dates: {e}")
        return 0


def _refresh_pm_metrics_dates(base_date):
    """Refresh PM performance metrics dates."""
    try:
        from kanban.coach_models import PMMetrics
        
        demo_board_ids = _get_demo_board_ids()
        metrics = list(PMMetrics.objects.filter(
            board_id__in=demo_board_ids
        ))
        
        if not metrics:
            return 0
        
        metrics_to_update = []
        
        for i, metric in enumerate(metrics):
            # Metrics from various past periods.
            # Sequential weekly intervals: each metric gets a unique period,
            # avoiding UNIQUE constraint collisions on (board_id, pm_user_id,
            # period_start, period_end).  The global-index approach is safe
            # here because PMMetrics has no per-board chart dependency — the
            # slight shift when sandbox count changes is acceptable.
            days_offset = -(i * 7 + 1)  # Weekly intervals
            metric.period_start = base_date + timedelta(days=days_offset - 7)
            metric.period_end = base_date + timedelta(days=days_offset)
            metrics_to_update.append(metric)
        
        if metrics_to_update:
            PMMetrics.objects.bulk_update(metrics_to_update, 
                                          ['period_start', 'period_end'], batch_size=100)
        
        return len(metrics_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing PM metrics dates: {e}")
        return 0


def _refresh_conflict_dates(now):
    """Refresh conflict detection detected_at and resolved_at fields."""
    try:
        from kanban.conflict_models import ConflictDetection, ConflictResolution
        
        demo_board_ids = _get_demo_board_ids()
        
        # Refresh conflicts
        conflicts = list(ConflictDetection.objects.filter(
            board_id__in=demo_board_ids
        ))
        
        conflicts_to_update = []
        for conflict in conflicts:
            status = getattr(conflict, 'status', 'active')
            
            if status in ['resolved', 'auto_resolved']:
                days_offset = -(conflict.id % 30 + 3)
            elif status == 'ignored':
                days_offset = -(conflict.id % 14 + 1)
            else:  # active
                days_offset = -(conflict.id % 25 + 3)
            
            # ConflictDetection uses detected_at, not created_at
            if hasattr(conflict, 'detected_at'):
                conflict.detected_at = now + timedelta(days=days_offset)
            if hasattr(conflict, 'resolved_at') and conflict.resolved_at:
                conflict.resolved_at = now + timedelta(days=days_offset + 1)
            conflicts_to_update.append(conflict)
        
        if conflicts_to_update:
            fields_to_update = []
            if hasattr(conflicts[0], 'detected_at'):
                fields_to_update.append('detected_at')
            if hasattr(conflicts[0], 'resolved_at'):
                fields_to_update.append('resolved_at')
            if fields_to_update:
                ConflictDetection.objects.bulk_update(conflicts_to_update, 
                                                      fields_to_update, batch_size=100)
        
        # Refresh resolutions
        resolutions = list(ConflictResolution.objects.filter(
            conflict__board_id__in=demo_board_ids
        ))
        
        resolutions_to_update = []
        for resolution in resolutions:
            days_offset = -(resolution.id % 30 + 2)
            if hasattr(resolution, 'created_at'):
                resolution.created_at = now + timedelta(days=days_offset)
            resolutions_to_update.append(resolution)
        
        if resolutions_to_update and hasattr(resolutions[0], 'created_at'):
            ConflictResolution.objects.bulk_update(resolutions_to_update, 
                                                   ['created_at'], batch_size=100)
        
        return len(conflicts_to_update) + len(resolutions_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing conflict dates: {e}")
        return 0


def _refresh_wiki_dates(now):
    """Refresh wiki page created_at and updated_at fields."""
    try:
        from wiki.models import WikiPage, WikiPageVersion
        
        demo_org_ids = _get_demo_organizations()
        pages = list(WikiPage.objects.filter(
            organization_id__in=demo_org_ids
        ))
        
        if not pages:
            return 0
        
        pages_to_update = []
        
        for i, page in enumerate(pages):
            # Distribute page dates — use record ID so order is stable
            # when org content grows (no global-index dependency).
            created_days_ago = (page.id % 20) + 10  # 10–29 days ago
            updated_days_ago = page.id % 14           # 0–13 days ago

            page.created_at = now - timedelta(days=created_days_ago)
            page.updated_at = now - timedelta(days=updated_days_ago)
            pages_to_update.append(page)
        
        if pages_to_update:
            WikiPage.objects.bulk_update(pages_to_update, 
                                        ['created_at', 'updated_at'], batch_size=100)
        
        # Also update wiki page versions
        versions = list(WikiPageVersion.objects.filter(
            page__organization_id__in=demo_org_ids
        ))
        
        for i, version in enumerate(versions):
            days_offset = -(version.id % 14 + 1)  # 1–14 days ago, stable per record
            version.created_at = now + timedelta(days=days_offset)
        
        if versions:
            WikiPageVersion.objects.bulk_update(versions, ['created_at'], batch_size=100)
        
        return len(pages_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing wiki dates: {e}")
        return 0


def _refresh_ai_session_dates(now):
    """Refresh AI assistant session, message AND analytics dates.

    The Spectra Analytics dashboard (ai_assistant.views.analytics_dashboard /
    get_analytics_data) only looks at activity in a trailing 30-day window. If
    the seeded demo sessions/analytics are not slid forward they age out of that
    window and every metric/chart reads 0.

    SCOPING — by demo flag/workspace, NOT by a hard-coded username list.
    ──────────────────────────────────────────────────────────────────
    The previous implementation targeted a static username list
    (``demo_admin_solo`` etc.) that no longer owns the seeded data after the
    persona swap (the data now belongs to the legacy ``alex_chen_demo`` account,
    and future re-seeds use ``priya.sharma``). That made this function a silent
    no-op — the root cause of the empty analytics page. We now scope by the
    intrinsic ``is_demo`` flag (sessions) and the demo workspace (analytics),
    which survives any persona swap.
    """
    try:
        from ai_assistant.models import (
            AIAssistantSession, AIAssistantMessage, AIAssistantAnalytics,
        )

        # ── Sessions: seeded demo sessions carry is_demo=True ──────────────
        # Real users' own sessions (is_demo=False) keep their genuine dates.
        sessions = list(AIAssistantSession.objects.filter(is_demo=True))

        sessions_to_update = []
        for session in sessions:
            # Use record ID so session dates are stable when user/session
            # counts change (no global-index dependency).
            days_offset = -(session.id % 14)   # 0–13 days ago
            hours_offset = -(session.id % 8)   # 0–7 hours ago

            session.created_at = now + timedelta(days=days_offset, hours=hours_offset)
            session.updated_at = now + timedelta(days=days_offset) + timedelta(hours=hours_offset + 1)
            sessions_to_update.append(session)

        if sessions_to_update:
            AIAssistantSession.objects.bulk_update(sessions_to_update,
                                                   ['created_at', 'updated_at'], batch_size=100)

        # ── Messages within those demo sessions ───────────────────────────
        session_ids = [s.id for s in sessions]
        if session_ids:
            messages = list(AIAssistantMessage.objects.filter(session_id__in=session_ids))
            for message in messages:
                days_offset = -(message.id % 14)  # stable per record
                minutes_offset = message.id % 60
                message.created_at = now + timedelta(days=days_offset, minutes=minutes_offset)
            if messages:
                AIAssistantMessage.objects.bulk_update(messages, ['created_at'], batch_size=500)

        # ── Analytics rows: slide the whole series forward so it stays in the
        #    30-day window. Analytics has no is_demo flag, so scope by demo
        #    workspace + seed-persona owners (current + legacy). ─────────────
        _refresh_ai_analytics_dates(now)

        return len(sessions_to_update)

    except Exception as e:
        logger.warning(f"Error refreshing AI session dates: {e}")
        return 0


def _refresh_ai_analytics_dates(now):
    """Slide demo AIAssistantAnalytics rows forward into the trailing window.

    Uses an OFFSET-PRESERVING uniform shift (same approach as
    ``_refresh_task_dates``): the most recent seeded row is anchored to *today*
    and every other row is shifted by the same delta. This keeps the per-day
    spread (so the daily charts render across the window) and preserves the
    ``unique_together = (user, board, date)`` invariant.

    To stay safe under the unique constraint even when the shift is smaller than
    the date span (e.g. the +1 day shift on a daily refresh, where old and new
    date ranges overlap), rows are updated one at a time in an order that always
    writes into a currently-free date slot.
    """
    try:
        from ai_assistant.models import AIAssistantAnalytics
        from kanban.models import Workspace
        from accounts.demo_personas import DEMO_USERNAMES, LEGACY_DEMO_USERNAMES

        demo_ws_ids = list(
            Workspace.objects.filter(is_demo=True).values_list('id', flat=True)
        )
        if not demo_ws_ids:
            return 0

        seed_owners = set(DEMO_USERNAMES) | set(LEGACY_DEMO_USERNAMES)
        rows = list(AIAssistantAnalytics.objects.filter(
            workspace_id__in=demo_ws_ids,
            user__username__in=seed_owners,
        ))
        if not rows:
            return 0

        today = now.date()
        max_date = max(r.date for r in rows)
        shift = (today - max_date).days
        if shift == 0:
            return 0

        # Process larger dates first when shifting forward (and smaller dates
        # first when shifting back) so each per-row update lands on a free slot
        # and never transiently collides with a not-yet-moved row.
        rows.sort(key=lambda r: r.date, reverse=(shift > 0))
        for r in rows:
            AIAssistantAnalytics.objects.filter(pk=r.pk).update(
                date=r.date + timedelta(days=shift),
                created_at=r.created_at + timedelta(days=shift),
            )

        return len(rows)

    except Exception as e:
        logger.warning(f"Error refreshing AI analytics dates: {e}")
        return 0


def _refresh_improvement_metrics_dates(base_date):
    """Refresh improvement metrics dates from retrospectives."""
    try:
        from kanban.retrospective_models import ImprovementMetric
        
        demo_board_ids = _get_demo_board_ids()
        metrics = list(ImprovementMetric.objects.filter(
            retrospective__board_id__in=demo_board_ids
        ))
        
        if not metrics:
            return 0
        
        metrics_to_update = []
        
        for i, metric in enumerate(metrics):
            # Metrics from past periods.
            # Use record ID so measured_at is stable when sandbox count changes.
            days_offset = -(metric.id % 42 + 7)  # 7–48 days ago
            metric.measured_at = base_date + timedelta(days=days_offset)
            metrics_to_update.append(metric)
        
        if metrics_to_update:
            ImprovementMetric.objects.bulk_update(metrics_to_update, 
                                                  ['measured_at'], batch_size=100)
        
        return len(metrics_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing improvement metrics dates: {e}")
        return 0


def _refresh_action_item_dates(now, base_date):
    """Refresh retrospective action item dates."""
    try:
        from kanban.retrospective_models import RetrospectiveActionItem
        
        demo_board_ids = _get_demo_board_ids()
        action_items = list(RetrospectiveActionItem.objects.filter(
            retrospective__board_id__in=demo_board_ids
        ))
        
        if not action_items:
            return 0
        
        items_to_update = []
        
        for item in action_items:
            status = getattr(item, 'status', 'pending')
            
            if status == 'completed':
                # Completed items in the past
                created_offset = -(item.id % 30 + 7)
                due_offset = -(item.id % 20 + 3)
            elif status == 'in_progress':
                # In-progress items recent
                created_offset = -(item.id % 14 + 3)
                due_offset = (item.id % 7) + 3  # Due in near future
            else:  # pending
                created_offset = -(item.id % 7 + 1)
                due_offset = (item.id % 14) + 7  # Due in 1-2 weeks
            
            item.created_at = now + timedelta(days=created_offset)
            if hasattr(item, 'due_date'):
                item.due_date = base_date + timedelta(days=due_offset)
            items_to_update.append(item)
        
        if items_to_update:
            fields_to_update = ['created_at']
            if hasattr(action_items[0], 'due_date'):
                fields_to_update.append('due_date')
            RetrospectiveActionItem.objects.bulk_update(items_to_update, 
                                                        fields_to_update, batch_size=100)
        
        return len(items_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing action item dates: {e}")
        return 0


def _refresh_burndown_prediction_dates(now, base_date):
    """Refresh burndown prediction date fields."""
    try:
        from kanban.burndown_models import BurndownPrediction
        
        demo_board_ids = _get_demo_board_ids()
        predictions = list(BurndownPrediction.objects.filter(
            board_id__in=demo_board_ids
        ))
        
        if not predictions:
            return 0
        
        predictions_to_update = []
        
        for i, prediction in enumerate(predictions):
            # Adjust the completion date predictions to be future-relative.
            # Use record ID so offsets are stable when sandbox count changes.
            board_slot = prediction.id % 3  # 0 = current sprint, 1-2 = upcoming
            if board_slot == 0:
                target_date_offset = 7
            else:
                target_date_offset = 7 + board_slot * 14
            prediction.completion_date_lower_bound = base_date + timedelta(days=target_date_offset - 3)
            prediction.completion_date_upper_bound = base_date + timedelta(days=target_date_offset + 7)
            predictions_to_update.append(prediction)
        
        if predictions_to_update:
            BurndownPrediction.objects.bulk_update(predictions_to_update, 
                ['predicted_completion_date', 'completion_date_lower_bound', 'completion_date_upper_bound'], 
                batch_size=100)
        
        return len(predictions_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing burndown prediction dates: {e}")
        return 0


def _refresh_resource_leveling_dates(now, base_date):
    """Refresh resource leveling suggestion dates."""
    try:
        from kanban.resource_leveling_models import ResourceLevelingSuggestion, TaskAssignmentHistory
        
        demo_org_ids = _get_demo_organizations()
        
        # Update ResourceLevelingSuggestion
        suggestions = list(ResourceLevelingSuggestion.objects.filter(
            organization_id__in=demo_org_ids
        ))
        
        suggestions_to_update = []
        for i, suggestion in enumerate(suggestions):
            status = getattr(suggestion, 'status', 'pending')
            
            if status in ['accepted', 'rejected']:
                created_offset = -(suggestion.id % 30 + 3)
            elif status == 'expired':
                created_offset = -(suggestion.id % 14 + 5)
            else:  # pending
                created_offset = -(suggestion.id % 2)  # Recent
            
            # expires_at is 48 hours after creation
            suggestion.expires_at = now + timedelta(days=created_offset) + timedelta(hours=48)
            
            # Update projected dates if they exist
            if suggestion.current_projected_date:
                suggestion.current_projected_date = now + timedelta(days=7 + (suggestion.id % 14))
            if suggestion.suggested_projected_date:
                suggestion.suggested_projected_date = now + timedelta(days=5 + (suggestion.id % 10))
            
            suggestions_to_update.append(suggestion)
        
        if suggestions_to_update:
            fields = ['expires_at']
            if hasattr(suggestions[0], 'current_projected_date') and suggestions[0].current_projected_date:
                fields.append('current_projected_date')
            if hasattr(suggestions[0], 'suggested_projected_date') and suggestions[0].suggested_projected_date:
                fields.append('suggested_projected_date')
            ResourceLevelingSuggestion.objects.bulk_update(suggestions_to_update, fields, batch_size=100)
        
        # Update TaskAssignmentHistory
        demo_board_ids = _get_demo_board_ids()
        histories = list(TaskAssignmentHistory.objects.filter(
            task__column__board_id__in=demo_board_ids
        ))
        
        histories_to_update = []
        for i, history in enumerate(histories):
            # Use record ID so changed_at is stable when sandbox count changes.
            days_offset = -(history.id % 28 + 1)  # 1–28 days ago
            if hasattr(history, 'changed_at'):
                history.changed_at = now + timedelta(days=days_offset)
            histories_to_update.append(history)
        
        if histories_to_update and hasattr(histories[0], 'changed_at'):
            TaskAssignmentHistory.objects.bulk_update(histories_to_update, ['changed_at'], batch_size=100)
        
        return len(suggestions_to_update) + len(histories_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing resource leveling dates: {e}")
        return 0


def _refresh_roi_snapshot_dates(base_date):
    """Refresh ProjectROI snapshot dates.

    Snapshots were created in chronological order of project progress (cost,
    completion, and realized value all increase with snapshot.id). Assign
    weekly dates per-board in that same order so the timeline matches the
    data progression — the oldest snapshot lands furthest in the past and
    the newest snapshot sits ~7 days ago, producing a smooth historical
    series rather than a scrambled one with spikes.
    """
    try:
        from kanban.budget_models import ProjectROI

        demo_board_ids = _get_demo_board_ids()
        snapshots_to_update = []

        for board_id in demo_board_ids:
            board_snapshots = list(
                ProjectROI.objects.filter(board_id=board_id).order_by('id')
            )
            n = len(board_snapshots)
            if n == 0:
                continue

            for i, snapshot in enumerate(board_snapshots):
                # i=0 (earliest data) → furthest in past; i=n-1 (latest) → 7 days ago
                days_offset = -((n - 1 - i) * 7 + 7)
                snapshot.snapshot_date = timezone.now() + timedelta(days=days_offset)
                snapshots_to_update.append(snapshot)

        if snapshots_to_update:
            ProjectROI.objects.bulk_update(snapshots_to_update,
                                           ['snapshot_date'], batch_size=100)

        return len(snapshots_to_update)

    except Exception as e:
        logger.warning(f"Error refreshing ROI snapshot dates: {e}")
        return 0


def _refresh_trend_analysis_dates(base_date):
    """Refresh retrospective trend analysis dates."""
    try:
        from kanban.retrospective_models import RetrospectiveTrend
        
        demo_board_ids = _get_demo_board_ids()
        trends = list(RetrospectiveTrend.objects.filter(
            board_id__in=demo_board_ids
        ))
        
        if not trends:
            return 0
        
        trends_to_update = []
        
        for i, trend in enumerate(trends):
            # Trend analysis dates — use record ID so offsets are stable
            # when sandbox boards are added/removed (no global-index dependency).
            if hasattr(trend, 'analysis_date'):
                trend.analysis_date = base_date - timedelta(days=trend.id % 8 * 14)
            if hasattr(trend, 'period_start'):
                trend.period_start = base_date - timedelta(days=(trend.id % 4 + 1) * 90)
            if hasattr(trend, 'period_end'):
                trend.period_end = base_date - timedelta(days=trend.id % 8 * 14)
            trends_to_update.append(trend)
        
        if trends_to_update:
            fields = []
            if hasattr(trends[0], 'analysis_date'):
                fields.append('analysis_date')
            if hasattr(trends[0], 'period_start'):
                fields.append('period_start')
            if hasattr(trends[0], 'period_end'):
                fields.append('period_end')
            if fields:
                RetrospectiveTrend.objects.bulk_update(trends_to_update, fields, batch_size=100)
        
        return len(trends_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing trend analysis dates: {e}")
        return 0


def _refresh_sprint_milestone_dates(base_date):
    """Refresh sprint milestone target_date and actual_date fields."""
    try:
        from kanban.burndown_models import SprintMilestone
        
        demo_board_ids = _get_demo_board_ids()
        milestones = list(SprintMilestone.objects.filter(
            board_id__in=demo_board_ids
        ))
        
        if not milestones:
            return 0
        
        milestones_to_update = []
        
        for i, milestone in enumerate(milestones):
            if milestone.is_completed:
                # Completed milestones in the past
                target_offset = -(milestone.id % 30 + 7)  # 7-37 days ago
                actual_offset = target_offset + (milestone.id % 3)  # Completed around target date
                milestone.target_date = base_date + timedelta(days=target_offset)
                if milestone.actual_date:
                    milestone.actual_date = base_date + timedelta(days=actual_offset)
            else:
                # Future milestones
                target_offset = (milestone.id % 45) + 7  # 7-52 days in future
                milestone.target_date = base_date + timedelta(days=target_offset)
                milestone.actual_date = None  # Not completed yet
            
            milestones_to_update.append(milestone)
        
        if milestones_to_update:
            SprintMilestone.objects.bulk_update(milestones_to_update, 
                                                ['target_date', 'actual_date'], batch_size=100)
        
        return len(milestones_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing sprint milestone dates: {e}")
        return 0


def _refresh_skill_development_plan_dates(now, base_date):
    """
    Refresh skill development plan dates (start_date, target_completion_date, created_at).
    
    NOTE: Skill development plans don't have created_by_session field, so all plans
    in demo organizations are treated as seed data and will be refreshed.
    """
    try:
        from kanban.models import SkillDevelopmentPlan
        
        demo_board_ids = _get_demo_board_ids()
        plans = list(SkillDevelopmentPlan.objects.filter(
            board_id__in=demo_board_ids
        ).select_related('board'))
        
        if not plans:
            return 0
        
        plans_to_update = []
        
        for plan in plans:
            # Determine dates based on plan status
            if plan.status == 'completed':
                # Completed plans - in the past
                created_offset = -(plan.id % 60 + 30)  # 30-90 days ago
                start_offset = created_offset + (plan.id % 5 + 1)  # Started shortly after creation
                target_offset = -(plan.id % 30 + 5)  # Completed 5-35 days ago
                
                plan.created_at = now + timedelta(days=created_offset)
                if plan.start_date or plan.target_completion_date:
                    plan.start_date = base_date + timedelta(days=start_offset)
                    plan.target_completion_date = base_date + timedelta(days=target_offset)
                
            elif plan.status in ['in_progress', 'approved']:
                # Active plans - started in past, target in future
                created_offset = -(plan.id % 45 + 15)  # 15-60 days ago
                start_offset = -(plan.id % 30 + 5)  # Started 5-35 days ago
                target_offset = (plan.id % 30) + 7  # Target 7-37 days in future
                
                plan.created_at = now + timedelta(days=created_offset)
                if plan.start_date or plan.target_completion_date:
                    plan.start_date = base_date + timedelta(days=start_offset)
                    plan.target_completion_date = base_date + timedelta(days=target_offset)
                
            elif plan.status == 'proposed':
                # Proposed plans - recently created, target in future
                created_offset = -(plan.id % 14 + 1)  # 1-15 days ago
                start_offset = (plan.id % 7) + 3  # Start 3-10 days in future
                target_offset = (plan.id % 45) + 21  # Target 21-66 days in future
                
                plan.created_at = now + timedelta(days=created_offset)
                if plan.start_date or plan.target_completion_date:
                    plan.start_date = base_date + timedelta(days=start_offset)
                    plan.target_completion_date = base_date + timedelta(days=target_offset)
                
            elif plan.status == 'cancelled':
                # Cancelled plans - in the past
                created_offset = -(plan.id % 90 + 30)  # 30-120 days ago
                start_offset = created_offset + (plan.id % 7 + 1)  # Started shortly after
                
                plan.created_at = now + timedelta(days=created_offset)
                if plan.start_date:
                    plan.start_date = base_date + timedelta(days=start_offset)
                # Keep target date as is or set in past
                if plan.target_completion_date:
                    target_offset = -(plan.id % 30 + 5)
                    plan.target_completion_date = base_date + timedelta(days=target_offset)
            
            plans_to_update.append(plan)
        
        if plans_to_update:
            SkillDevelopmentPlan.objects.bulk_update(
                plans_to_update, 
                ['created_at', 'start_date', 'target_completion_date'], 
                batch_size=100
            )
        
        return len(plans_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing skill development plan dates: {e}")
        return 0
        
    except Exception as e:
        logger.warning(f"Error refreshing sprint milestone dates: {e}")
        return 0


def _refresh_scope_snapshot_dates(now, base_date):
    """
    Refresh ScopeChangeSnapshot and ScopeCreepAlert dates for demo boards.
    Also updates the board's baseline_set_date to keep it relative.
    
    This ensures scope tracking dashboard shows realistic, current dates.
    """
    try:
        from kanban.models import Board, ScopeChangeSnapshot, ScopeCreepAlert
        
        demo_org_ids = _get_demo_organizations()
        if not demo_org_ids:
            return 0
        
        # Get demo boards with scope baselines
        demo_boards = Board.objects.filter(
            organization_id__in=demo_org_ids,
            is_official_demo_board=True,
            baseline_task_count__isnull=False
        )
        
        total_updated = 0
        
        for board in demo_boards:
            # Update board's baseline_set_date to 2 weeks ago
            baseline_date = now - timedelta(days=14)
            Board.objects.filter(pk=board.pk).update(baseline_set_date=baseline_date)
            total_updated += 1
            
            # Get all snapshots for this board
            snapshots = list(ScopeChangeSnapshot.objects.filter(board=board).order_by('snapshot_date'))
            
            if not snapshots:
                continue
            
            # Update snapshot dates
            for i, snapshot in enumerate(snapshots):
                if snapshot.is_baseline:
                    # Baseline snapshots should be 2 weeks ago
                    new_date = now - timedelta(days=14)
                else:
                    # Non-baseline snapshots spread between baseline and now
                    # Based on their order, spread them evenly
                    days_ago = max(0, 13 - (i * 2))  # 13, 11, 9, 7, 5, 3, 1, etc.
                    new_date = now - timedelta(days=days_ago)
                
                ScopeChangeSnapshot.objects.filter(pk=snapshot.pk).update(snapshot_date=new_date)
                total_updated += 1
            
            # Update scope creep alerts for this board
            alerts = ScopeCreepAlert.objects.filter(board=board)
            for alert in alerts:
                # Alert detected_at should be based on when scope changed
                # Most recent alerts are from the last few days
                days_ago = alert.id % 7 + 1  # 1-7 days ago
                new_detected_at = now - timedelta(days=days_ago)
                
                update_fields = {'detected_at': new_detected_at}
                
                # If acknowledged, update that too
                if alert.acknowledged_at:
                    update_fields['acknowledged_at'] = new_detected_at + timedelta(hours=alert.id % 24 + 1)
                
                # If resolved, update that too
                if alert.resolved_at:
                    update_fields['resolved_at'] = new_detected_at + timedelta(days=alert.id % 3 + 1)
                
                ScopeCreepAlert.objects.filter(pk=alert.pk).update(**update_fields)
                total_updated += 1
        
        return total_updated
        
    except Exception as e:
        logger.warning(f"Error refreshing scope snapshot dates: {e}")
        return 0


def _refresh_task_activity_dates(now):
    """
    Refresh TaskActivity dates for demo boards so the Completion Velocity
    chart always shows data within the last 30 days.

    Only updates activities whose created_at is older than 30 days to avoid
    disturbing recently-created user activity records.
    """
    try:
        import random
        from kanban.models import TaskActivity

        demo_board_ids = _get_demo_board_ids()
        if not demo_board_ids:
            return 0

        cutoff = now - timedelta(days=30)

        # Only refresh stale activities on demo boards
        stale_activities = list(
            TaskActivity.objects.filter(
                task__column__board_id__in=demo_board_ids,
                created_at__lt=cutoff,
            ).select_related('task')
        )

        if not stale_activities:
            return 0

        # Assign new dates spread across the last 28 days
        for activity in stale_activities:
            new_date = now - timedelta(days=random.randint(1, 28))
            new_date = new_date.replace(
                hour=random.randint(8, 18),
                minute=random.randint(0, 59),
                second=0,
                microsecond=0,
            )
            activity.created_at = new_date

        TaskActivity.objects.bulk_update(stale_activities, ['created_at'], batch_size=200)
        return len(stale_activities)

    except Exception as e:
        logger.warning(f"Error refreshing task activity dates: {e}")
        return 0


def _refresh_completed_task_updated_at(now):
    """
    Spread the updated_at timestamps for completed (progress=100) demo tasks
    EVENLY across the last ~8 weeks so the weekly analytics charts
    (Deployment/Completion Frequency, Content Delivered per Week, On-Time vs
    Late Completion — all keyed on updated_at over an 8-week window) are filled
    across the whole window instead of bunching into the last 4 weeks and
    leaving the earlier week-buckets blank.

    Approach: a uniform linspace (the previous behaviour) put ~one completion in
    EVERY week, which renders as identical height-1 bars — it looks fake. Instead
    we distribute completions across the 8 weeks following a fixed, non-uniform
    "velocity curve" (WEEK_WEIGHTS) so some weeks have 0 and others 2-3. With
    only 8 completions over 8 weeks, variation REQUIRES empty weeks (8 tasks at
    min-1 each = all 1s = uniform), and zero-velocity weeks are realistic. Tasks
    are sorted by ID (foundational first) and mapped to a week by cumulative
    weight proportion, so the curve scales to any completion count (e.g. the
    historical archive board gets ~3-6/week with the same shape).

    Each board is processed INDEPENDENTLY so adding/removing sandbox boards
    never shifts another board's offsets. Uses .update() to bypass auto_now.
    """
    # Window roughly matches the 8-week analytics charts: oldest completion ~8
    # weeks back, newest ~5 days ago (keeps a little recent activity).
    SPREAD_OLDEST_DAYS = 56
    SPREAD_NEWEST_DAYS = 5
    # Relative completions per week, oldest (week 0) → newest (week 7). Sums to 8
    # so an 8-task board reproduces bar heights [1,0,2,1,2,0,1,1]. The two
    # intentionally-late Done tasks (4th & 6th by id) land in weeks 3 and 4, so
    # On-Time vs Late shows one all-late week and one mixed week.
    WEEK_WEIGHTS = [1, 0, 2, 1, 2, 0, 1, 1]
    _total_weight = sum(WEEK_WEIGHTS)
    _cum = []
    _running = 0
    for _w in WEEK_WEIGHTS:
        _running += _w
        _cum.append(_running / _total_weight)
    _weeks_n = len(WEEK_WEIGHTS)
    try:
        from kanban.models import Task

        demo_board_ids = _get_demo_board_ids()
        if not demo_board_ids:
            return 0

        total_updated = 0
        for board_id in demo_board_ids:
            tasks = list(
                Task.objects.filter(
                    item_type='task',
                    progress=100,
                    column__board_id=board_id,
                ).order_by('id')
            )
            if not tasks:
                continue

            total = len(tasks)

            for i, task in enumerate(tasks):
                if total == 1:
                    week = _weeks_n // 2
                else:
                    # Cumulative-weight bucketing: the first week whose running
                    # weight fraction covers this task's position. Zero-weight
                    # weeks share their predecessor's threshold so they are never
                    # selected (a lower index always matches first).
                    p = (i + 0.5) / total
                    week = next(
                        (w for w in range(_weeks_n) if p <= _cum[w]),
                        _weeks_n - 1,
                    )
                days_ago = SPREAD_OLDEST_DAYS - week * 7
                days_ago = max(SPREAD_NEWEST_DAYS, min(SPREAD_OLDEST_DAYS, days_ago))
                # Anchor to midnight so the calendar date (and therefore the week
                # bucket) is stable; vary only the time-of-day so same-week
                # completions never cross a date boundary.
                midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
                day_midnight = midnight - timedelta(days=days_ago)
                hours_offset = 9 + (task.id % 7)   # 9 am … 4 pm
                minutes_offset = (task.id * 11) % 60
                new_dt = day_midnight.replace(
                    hour=hours_offset, minute=minutes_offset
                )
                Task.objects.filter(pk=task.pk).update(updated_at=new_dt)
                total_updated += 1

        return total_updated

    except Exception as e:
        logger.warning(f"Error refreshing completed task updated_at: {e}")
        return 0


def _refresh_commitment_protocol_dates(now, base_date):
    """
    Refresh CommitmentProtocol, ConfidenceSignal, and CommitmentBet dates.

    Uses the same offset-preserving strategy as tasks: compute how many days
    each date is from the protocol's created_at, then re-anchor created_at
    so that target_date stays a fixed number of days in the future.
    """
    try:
        from kanban.commitment_models import (
            CommitmentProtocol, ConfidenceSignal, CommitmentBet,
        )

        demo_board_ids = _get_demo_board_ids()
        if not demo_board_ids:
            return 0

        protocols = list(CommitmentProtocol.objects.filter(
            board_id__in=demo_board_ids,
        ))

        if not protocols:
            return 0

        updated = 0

        for protocol in protocols:
            # Determine original offsets relative to created_at
            old_created = protocol.created_at
            if old_created is None:
                continue

            # Re-anchor: keep the gap between created_at and target_date
            # so the protocol always looks "active" relative to today.
            original_span_days = (protocol.target_date - old_created.date()).days
            # created_at was X days ago from the original target_date;
            # keep target_date the same number of days in the future.
            new_target = base_date + timedelta(days=max(original_span_days // 3, 14))
            new_created = now - timedelta(days=original_span_days - (new_target - base_date).days)
            # Simpler: preserve the age of the protocol
            age_days = (now - old_created).total_seconds() / 86400
            # If the age looks already correct (within 1 day), skip
            expected_age = (now.date() - (new_target - timedelta(days=original_span_days))).days
            # Use a straightforward shift like tasks:
            # shift = how many days to move everything
            shift = timedelta(days=(base_date - protocol.target_date).days + max(original_span_days // 3, 14))
            if abs(shift.days) < 1:
                continue

            new_target_date = protocol.target_date + shift
            new_created_at = old_created + shift

            # Update protocol dates
            CommitmentProtocol.objects.filter(pk=protocol.pk).update(
                target_date=new_target_date,
                created_at=new_created_at,
                last_decay_calculation=now,
            )
            # Shift last_signal_date if set
            if protocol.last_signal_date:
                new_signal_date = protocol.last_signal_date + shift
                CommitmentProtocol.objects.filter(pk=protocol.pk).update(
                    last_signal_date=new_signal_date,
                )

            # Shift all signal timestamps
            signals = ConfidenceSignal.objects.filter(protocol=protocol)
            for sig in signals:
                ConfidenceSignal.objects.filter(pk=sig.pk).update(
                    timestamp=sig.timestamp + shift,
                )

            # Shift all bet placed_at timestamps
            bets = CommitmentBet.objects.filter(protocol=protocol)
            for bet in bets:
                CommitmentBet.objects.filter(pk=bet.pk).update(
                    placed_at=bet.placed_at + shift,
                )

            updated += 1

        return updated

    except Exception as e:
        logger.warning(f"Error refreshing commitment protocol dates: {e}")
        return 0


def _refresh_comment_dates(now):
    """
    Refresh Comment.created_at timestamps on demo boards so comments
    don't show "180 days ago" after date staleness.

    Uses an offset-preserving shift per board (same approach as tasks):
    find the oldest comment, compute a single shift delta so the oldest
    comment falls ~30 days before today, then shift all comments by
    that delta.  This keeps conversation threads in chronological order.
    """
    try:
        from kanban.models import Comment

        demo_board_ids = _get_demo_board_ids()
        if not demo_board_ids:
            return 0

        comments = list(
            Comment.objects.filter(
                task__column__board_id__in=demo_board_ids,
            ).select_related('task__column')
        )

        if not comments:
            return 0

        # Group by board
        by_board = {}
        for c in comments:
            bid = c.task.column.board_id if c.task and c.task.column else 0
            by_board.setdefault(bid, []).append(c)

        to_update = []
        for board_id, board_comments in by_board.items():
            oldest = min(c.created_at for c in board_comments)
            target_oldest = now - timedelta(days=30)
            shift = target_oldest - oldest
            if abs(shift.total_seconds()) < 86400:
                continue  # already current
            for c in board_comments:
                c.created_at = c.created_at + shift
                to_update.append(c)

        if to_update:
            Comment.objects.bulk_update(to_update, ['created_at'], batch_size=500)

        return len(to_update)

    except Exception as e:
        logger.warning(f"Error refreshing comment dates: {e}")
        return 0


def _refresh_chat_message_dates(now):
    """
    Refresh ChatMessage and TaskThreadComment timestamps on demo boards.

    Same offset-preserving shift strategy as comments: keep thread order
    intact while moving absolute dates to the present.
    """
    try:
        from messaging.models import ChatMessage, TaskThreadComment

        demo_board_ids = _get_demo_board_ids()
        if not demo_board_ids:
            return 0

        total = 0

        # ── ChatMessage (via ChatRoom.board) ──────────────────────────────
        messages = list(
            ChatMessage.objects.filter(
                chat_room__board_id__in=demo_board_ids,
            ).select_related('chat_room')
        )

        if messages:
            by_room = {}
            for m in messages:
                by_room.setdefault(m.chat_room_id, []).append(m)

            msgs_to_update = []
            for room_id, room_msgs in by_room.items():
                oldest = min(m.created_at for m in room_msgs)
                target_oldest = now - timedelta(days=14)
                shift = target_oldest - oldest
                if abs(shift.total_seconds()) < 86400:
                    continue
                for m in room_msgs:
                    m.created_at = m.created_at + shift
                    msgs_to_update.append(m)

            if msgs_to_update:
                ChatMessage.objects.bulk_update(
                    msgs_to_update, ['created_at'], batch_size=500
                )
            total += len(msgs_to_update)

        # ── TaskThreadComment (via Task.column.board) ─────────────────────
        thread_comments = list(
            TaskThreadComment.objects.filter(
                task__column__board_id__in=demo_board_ids,
            ).select_related('task__column')
        )

        if thread_comments:
            by_task = {}
            for tc in thread_comments:
                by_task.setdefault(tc.task_id, []).append(tc)

            tcs_to_update = []
            for task_id, task_tcs in by_task.items():
                oldest = min(tc.created_at for tc in task_tcs)
                target_oldest = now - timedelta(days=14)
                shift = target_oldest - oldest
                if abs(shift.total_seconds()) < 86400:
                    continue
                for tc in task_tcs:
                    tc.created_at = tc.created_at + shift
                    tcs_to_update.append(tc)

            if tcs_to_update:
                TaskThreadComment.objects.bulk_update(
                    tcs_to_update, ['created_at'], batch_size=500
                )
            total += len(tcs_to_update)

        return total

    except Exception as e:
        logger.warning(f"Error refreshing chat message dates: {e}")
        return 0