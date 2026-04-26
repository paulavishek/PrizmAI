"""
Calendar Context Provider — events, deadlines, schedule.

NEW provider — calendar data was previously invisible to Spectra.
"""

import logging
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class CalendarContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Calendar'
    FEATURE_TAGS = [
        'calendar', 'event', 'events', 'schedule', 'meeting',
        'upcoming', 'this week', 'next week', 'today',
        'appointment', 'deadline', 'when', 'date',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        try:
            from kanban.models import CalendarEvent
        except ImportError:
            return ''

        now = timezone.now()
        week_ahead = now + timedelta(days=7)

        if board:
            events = CalendarEvent.objects.filter(
                Q(board=board) | Q(created_by=user, board__isnull=True),
                start_datetime__gte=now,
                start_datetime__lte=week_ahead,
            )
        else:
            accessible = self._get_accessible_boards(user, is_demo_mode)
            events = CalendarEvent.objects.filter(
                Q(board__in=accessible) | Q(created_by=user, board__isnull=True),
                start_datetime__gte=now,
                start_datetime__lte=week_ahead,
            )

        count = events.count()
        if count == 0:
            return '📅 **Calendar:** No events in the next 7 days.\n'

        next_event = events.order_by('start_datetime').first()
        next_str = ''
        if next_event:
            next_str = f' Next: "{next_event.title}" on {next_event.start_datetime.strftime("%b %d")}.'

        return f'📅 **Calendar:** {count} event(s) this week.{next_str}\n'

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        try:
            from kanban.models import CalendarEvent
        except ImportError:
            return ''

        now = timezone.now()
        month_ahead = now + timedelta(days=30)

        if board:
            events = CalendarEvent.objects.filter(
                Q(board=board) | Q(created_by=user, board__isnull=True),
                start_datetime__gte=now - timedelta(days=7),
                start_datetime__lte=month_ahead,
            ).order_by('start_datetime')
        else:
            accessible = self._get_accessible_boards(user, is_demo_mode)
            events = CalendarEvent.objects.filter(
                Q(board__in=accessible) | Q(created_by=user, board__isnull=True),
                start_datetime__gte=now - timedelta(days=7),
                start_datetime__lte=month_ahead,
            ).order_by('start_datetime')

        if not events.exists():
            return '**📅 Calendar:** No upcoming events.\n'

        ctx = f'**📅 Calendar (next 30 days, {events.count()} events):**\n'

        for event in events[:20]:
            start = event.start_datetime.strftime('%b %d, %I:%M %p')
            if event.is_all_day:
                start = event.start_datetime.strftime('%b %d') + ' (all day)'

            past = event.start_datetime < now
            marker = ' (past)' if past else ''

            ctx += f'  • {start}{marker} — {event.title}'
            if event.event_type:
                ctx += f' [{event.event_type}]'
            ctx += '\n'
            if event.description:
                ctx += f'    {event.description[:100]}\n'

        return ctx


registry.register(CalendarContextProvider())
