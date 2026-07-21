"""
Time Health metrics for the unified calendar.

Answers "where did my scheduled time actually go this week, and do I have room
left for what's due?" using only data PrizmAI already stores — no new model
fields, no external calendar integration, no LLM calls.

WHY THE TWO HALVES ARE COMPUTED DIFFERENTLY
-------------------------------------------
Only ``CalendarEvent`` carries real durations (start_datetime/end_datetime), so
it is the *only* thing summed into the hours chart.

Tasks are deliberately NOT summed. On the calendar a task renders as an all-day
bar spanning ``start_date → due_date`` (see ``unified_calendar_events_api``) —
that is a *deadline window*, not worked hours. A task sitting on the board for
ten days is not ten days of labour, and boards routinely show 3–4 overlapping
multi-day bars per date, which would fabricate ~40h/day if summed.

Instead tasks contribute a separate, honest signal: how many commitments come
due inside the window, reported alongside the free hours left after meetings.
That pairing is the thing a meetings-only calendar analytics tool structurally
cannot produce.

ACTUALS OVERLAY
---------------
``TimeEntry`` (hours_spent + work_date, logged by hand) is the one source of
*real worked hours* in the system, so it overlays the scheduled picture as
"planned vs actual": scheduled time is what the calendar committed to, logged
time is what the person recorded doing. The two are deliberately NOT added
together — an hour can be both scheduled and logged, so summing them would
double-count. They are reported as parallel series.

TimeEntry rows are scoped by board, which matters: shared demo personas own
entries on many sandbox copies of the same board, so an unscoped read reports
absurd daily totals (200h+) by summing one person's work across every tenant.

Deliberately NO single 0–10 "score" — an opaque number invites "why 6.8?" with
no defensible answer. Named flags are returned instead.
"""

import zoneinfo
from collections import OrderedDict
from datetime import datetime, time, timedelta

from django.conf import settings
from django.db.models import Q, Sum

from kanban.budget_models import TimeEntry
from kanban.models import CalendarEvent, CalendarEventParticipant, Task

# Bucket keys, in the order they stack in the UI.
MEETING = 'meeting'
FOCUS = 'focus'
OOO = 'ooo'

# event_type → bucket. 'team_event' (all-hands, training) is meeting-shaped time:
# it is scheduled, attended, and not available for focused work.
_TYPE_TO_BUCKET = {
    'meeting': MEETING,
    'team_event': MEETING,
    'busy_block': FOCUS,
    'out_of_office': OOO,
}

# Fallbacks when a user has no profile row.
_DEFAULT_WEEKLY_CAPACITY = 40
_WORKING_DAYS_PER_WEEK = 5

# A meeting load above this share of capacity is worth flagging.
_MEETING_HEAVY_RATIO = 0.5


def _server_tz():
    """Explicit tz object rather than Django's thread-local ``timezone``.

    Mirrors the convention already used throughout ``calendar_views`` — the
    thread-local is unreliable under Daphne/ASGI thread-pool execution.
    """
    return zoneinfo.ZoneInfo(settings.TIME_ZONE)


def _daily_capacity_hours(user):
    """Working hours in a single WORKING day, from the user's weekly capacity."""
    profile = getattr(user, 'profile', None)
    weekly = getattr(profile, 'weekly_capacity_hours', None) or _DEFAULT_WEEKLY_CAPACITY
    return float(weekly) / _WORKING_DAYS_PER_WEEK


def _capacity_for(day, daily_capacity):
    """Capacity available on a specific date — zero on Sat/Sun.

    Without this a Mon–Sun window would total 7 × 8h = 56h of "capacity",
    overstating a 40h week by 40% and making genuine over-capacity weeks look
    comfortable. Weekend work still shows up as logged hours (and correctly
    reads as effort beyond capacity); it just never *grants* capacity.
    """
    return 0.0 if day.weekday() >= _WORKING_DAYS_PER_WEEK else daily_capacity


def _visible_event_qs(user, range_start, range_end, scope_boards):
    """Events that consume THIS user's time in the window.

    Strictly first-person: events the user created, or was invited to and has
    not declined. Teammate "busy"/OOO blocks are excluded — they are shown on
    the grid only as sanitized ``teammate_status`` blocks with the reason
    redacted, so they are not this user's hours and must not be tallied here.
    """
    # Imported lazily: calendar_views imports nothing from this module, but
    # keeping the dependency one-directional avoids any future import cycle.
    from kanban.calendar_views import _event_workspace_scope

    qs = CalendarEvent.objects.filter(
        Q(created_by=user) |
        Q(
            participant_links__user=user,
            participant_links__status__in=[
                CalendarEventParticipant.PENDING,
                CalendarEventParticipant.ACCEPTED,
            ],
        )
    ).filter(
        # Demo / real workspace isolation, keyed on CalendarEvent.is_demo.
        _event_workspace_scope(user)
    ).filter(
        # Overlap test — an event straddling the window edge still contributes
        # its in-window portion (the per-day clipping below trims the rest).
        start_datetime__date__lte=range_end,
        end_datetime__date__gte=range_start,
    )

    if scope_boards is not None:
        # Board-less events (the "Board (optional)" default) have no board to
        # scope against and are already gated by the creator/participant match.
        qs = qs.filter(Q(board__in=scope_boards) | Q(board__isnull=True))

    return qs.distinct()


def _iter_days(range_start, range_end):
    day = range_start
    while day <= range_end:
        yield day
        day += timedelta(days=1)


def _logged_hours_by_day(user, range_start, range_end, scope_boards):
    """Map ``date.isoformat() -> hours`` of TimeEntry effort logged by ``user``.

    Board-scoped on purpose. Demo personas own time entries on every sandbox
    copy of the shared template board, so an unscoped sum reports one person
    logging 200+ hours in a day by adding up unrelated tenants' work.
    """
    qs = TimeEntry.objects.filter(
        user=user,
        work_date__gte=range_start,
        work_date__lte=range_end,
    )
    if scope_boards is not None:
        qs = qs.filter(task__column__board__in=scope_boards)

    rows = qs.values('work_date').annotate(total=Sum('hours_spent'))
    return {
        row['work_date'].isoformat(): float(row['total'] or 0)
        for row in rows
    }


def compute_time_health(user, range_start, range_end, scope_boards=None):
    """Return a Time Health summary dict for ``user`` over [range_start, range_end].

    ``range_start``/``range_end`` are inclusive ``date`` objects.
    ``scope_boards`` is an optional Board queryset limiting which boards count
    (the calendar's board chips); ``None`` means no board restriction.
    """
    tz = _server_tz()
    daily_capacity = _daily_capacity_hours(user)

    # Per-day buckets, pre-seeded so quiet days still appear on the chart.
    days = OrderedDict(
        (day.isoformat(), {MEETING: 0.0, FOCUS: 0.0, OOO: 0.0})
        for day in _iter_days(range_start, range_end)
    )

    for ev in _visible_event_qs(user, range_start, range_end, scope_boards):
        bucket = _TYPE_TO_BUCKET.get(ev.event_type)
        if bucket is None:
            continue

        local_start = ev.start_datetime.astimezone(tz)
        local_end = ev.end_datetime.astimezone(tz)

        # Walk each local day the event touches and add only that day's slice,
        # so a multi-day event is spread across days rather than dumped whole
        # onto its start date.
        day = max(local_start.date(), range_start)
        last_day = min(local_end.date(), range_end)
        while day <= last_day:
            key = day.isoformat()
            if key not in days:
                day += timedelta(days=1)
                continue

            if ev.is_all_day or bucket == OOO:
                # An all-day event must never book 24h against a working day.
                # OOO in particular is capacity REMOVED, not hours worked — it
                # is charged at exactly one working day so `free` collapses to 0.
                # Charged at that DAY's capacity, so OOO spanning a weekend
                # doesn't invent working hours on Sat/Sun.
                hours = _capacity_for(day, daily_capacity)
            else:
                day_start = datetime.combine(day, time.min, tzinfo=tz)
                day_end = day_start + timedelta(days=1)
                slice_start = max(local_start, day_start)
                slice_end = min(local_end, day_end)
                hours = max(0.0, (slice_end - slice_start).total_seconds() / 3600.0)

            days[key][bucket] += hours
            day += timedelta(days=1)

    # Real worked hours, overlaid on (never added to) the scheduled picture.
    logged_by_day = _logged_hours_by_day(user, range_start, range_end, scope_boards)

    # Per-day free time, then window totals.
    per_day = []
    totals = {
        MEETING: 0.0, FOCUS: 0.0, OOO: 0.0,
        'free': 0.0, 'capacity': 0.0, 'logged': 0.0,
    }
    for key, buckets in days.items():
        day_obj = datetime.fromisoformat(key).date()
        day_capacity = _capacity_for(day_obj, daily_capacity)
        booked = buckets[MEETING] + buckets[FOCUS] + buckets[OOO]
        free = max(0.0, day_capacity - booked)
        logged = logged_by_day.get(key, 0.0)
        per_day.append({
            'date': key,
            'meeting': round(buckets[MEETING], 2),
            'focus': round(buckets[FOCUS], 2),
            'ooo': round(buckets[OOO], 2),
            'free': round(free, 2),
            'capacity': round(day_capacity, 2),
            'logged': round(logged, 2),
        })
        totals[MEETING] += buckets[MEETING]
        totals[FOCUS] += buckets[FOCUS]
        totals[OOO] += buckets[OOO]
        totals['free'] += free
        totals['capacity'] += day_capacity
        totals['logged'] += logged

    # --- The differentiating signal: commitments due vs. time left ----------
    # Counted, never converted to hours. Tasks carry no trustworthy duration
    # (see module docstring), so inventing one here would be fabrication.
    task_qs = Task.objects.filter(
        assigned_to=user,
        item_type='task',
        due_date__isnull=False,
        due_date__date__gte=range_start,
        due_date__date__lte=range_end,
        progress__lt=100,
    )
    if scope_boards is not None:
        task_qs = task_qs.filter(column__board__in=scope_boards)
    commitments_due = task_qs.distinct().count()

    free_total = round(totals['free'], 2)
    meeting_total = round(totals[MEETING], 2)
    capacity_total = round(totals['capacity'], 2)
    logged_total = round(totals['logged'], 2)
    scheduled_total = round(
        totals[MEETING] + totals[FOCUS] + totals[OOO], 2
    )
    days_logged = sum(1 for d in per_day if d['logged'] > 0)

    # --- Named flags, in place of an opaque composite score ----------------
    flags = []
    if capacity_total > 0 and meeting_total > capacity_total * _MEETING_HEAVY_RATIO:
        pct = round(meeting_total / capacity_total * 100)
        flags.append({
            'level': 'warning',
            'code': 'meeting_heavy',
            'text': f'Meetings take up {pct}% of your capacity this window.',
        })

    meeting_free_days = sum(
        1 for d in per_day if d['meeting'] == 0 and d['ooo'] == 0
    )
    # Only meaningful for a week-shaped window. A month view spans ~42 cells, so
    # "no meeting-free day" across six weeks would be both near-impossible and
    # uninformative if it did fire.
    if not meeting_free_days and 5 <= len(per_day) <= 8:
        flags.append({
            'level': 'warning',
            'code': 'no_meeting_free_day',
            'text': 'No meeting-free day this week.',
        })

    if commitments_due and free_total <= 0:
        flags.append({
            'level': 'danger',
            'code': 'overcommitted',
            'text': (
                f'{commitments_due} task(s) due with no unscheduled time left.'
            ),
        })

    # Logged effort well past what the calendar accounts for: the work is
    # happening in time that was never scheduled (invisible workload). Only
    # meaningful once there IS a schedule to compare against.
    if logged_total and scheduled_total and logged_total > scheduled_total * 1.5:
        flags.append({
            'level': 'warning',
            'code': 'unscheduled_effort',
            'text': (
                f'You logged {logged_total:g}h but only {scheduled_total:g}h '
                'was on the calendar — most of this work was unscheduled.'
            ),
        })

    if logged_total > capacity_total > 0:
        flags.append({
            'level': 'danger',
            'code': 'over_capacity',
            'text': (
                f'Logged {logged_total:g}h against {capacity_total:g}h capacity.'
            ),
        })

    return {
        'range_start': range_start.isoformat(),
        'range_end': range_end.isoformat(),
        'days': per_day,
        'totals': {
            'meeting': meeting_total,
            'focus': round(totals[FOCUS], 2),
            'ooo': round(totals[OOO], 2),
            'free': free_total,
            'capacity': capacity_total,
            # Parallel series, NOT part of the scheduled stack — an hour can be
            # both scheduled and logged, so these must never be summed together.
            'logged': logged_total,
            'scheduled': scheduled_total,
        },
        'commitments_due': commitments_due,
        'meeting_free_days': meeting_free_days,
        'days_logged': days_logged,
        'has_logged_time': logged_total > 0,
        'flags': flags,
    }
