"""
Time Tracking Context Provider — hours logged, utilization, time entries.

NEW provider — this data was previously invisible to Spectra.
"""

import logging
from datetime import timedelta

from django.db.models import Sum, Count, F
from django.utils import timezone

from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class TimeTrackingContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Time Tracking'
    FEATURE_TAGS = [
        'time', 'hours', 'logged', 'time entry', 'time tracking',
        'utilization', 'time spent', 'hours spent', 'how many hours',
        'time log', 'timesheet', 'work hours', 'billable',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        try:
            from kanban.budget_models import TimeEntry
        except ImportError:
            return ''

        if board:
            entries = TimeEntry.objects.filter(task__column__board=board)
        else:
            accessible = self._get_accessible_boards(user, is_demo_mode)
            entries = TimeEntry.objects.filter(task__column__board__in=accessible)

        total_hours = entries.aggregate(total=Sum('hours_spent'))['total'] or 0
        entry_count = entries.count()
        if entry_count == 0:
            return '⏱️ **Time Tracking:** No time entries logged.\n'

        # Last 7 days
        week_ago = timezone.now().date() - timedelta(days=7)
        recent = entries.filter(work_date__gte=week_ago).aggregate(
            total=Sum('hours_spent')
        )['total'] or 0

        return (
            f'⏱️ **Time Tracking:** {total_hours:.1f}h total logged '
            f'({entry_count} entries), {recent:.1f}h in last 7 days.\n'
        )

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        try:
            from kanban.budget_models import TimeEntry
        except ImportError:
            return ''

        if board:
            entries = TimeEntry.objects.filter(
                task__column__board=board
            ).select_related('task', 'user')
        else:
            accessible = self._get_accessible_boards(user, is_demo_mode)
            entries = TimeEntry.objects.filter(
                task__column__board__in=accessible
            ).select_related('task', 'user')

        total_hours = entries.aggregate(total=Sum('hours_spent'))['total'] or 0
        if not entries.exists():
            return '**⏱️ Time Tracking:** No entries logged.\n'

        ctx = f'**⏱️ Time Tracking Detail:**\n'
        ctx += f'  Total hours: {total_hours:.1f}h\n'

        # By user
        by_user = entries.values(
            'user__username', 'user__first_name', 'user__last_name'
        ).annotate(
            hours=Sum('hours_spent'), count=Count('id')
        ).order_by('-hours')

        ctx += '\n**Hours by Team Member:**\n'
        for row in by_user[:15]:
            name = f'{row["user__first_name"]} {row["user__last_name"]}'.strip()
            name = name or row['user__username']
            ctx += f'  {name}: {row["hours"]:.1f}h ({row["count"]} entries)\n'

        # By task (top 10)
        by_task = entries.values(
            'task__title'
        ).annotate(
            hours=Sum('hours_spent')
        ).order_by('-hours')[:10]

        if by_task:
            ctx += '\n**Top Tasks by Time:**\n'
            for row in by_task:
                ctx += f'  {row["task__title"]}: {row["hours"]:.1f}h\n'

        # Recent entries
        recent = entries.order_by('-work_date', '-created_at')[:10]
        if recent:
            ctx += '\n**Recent Time Entries:**\n'
            for e in recent:
                name = e.user.get_full_name() or e.user.username
                ctx += (
                    f'  {e.work_date} — {name}: {e.hours_spent:.1f}h '
                    f'on "{e.task.title}"'
                )
                if e.description:
                    ctx += f' ({e.description[:60]})'
                ctx += '\n'

        return ctx


registry.register(TimeTrackingContextProvider())
