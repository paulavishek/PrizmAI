"""
Time Health metric tests (kanban/utils/calendar_analytics.py).

The panel's central design constraint is that ONLY CalendarEvents contribute
hours — a task renders on the calendar as an all-day bar spanning
start_date→due_date, which is a deadline window rather than worked time, so
tasks are counted (commitments due) and never summed as hours. These tests pin
that split, plus the bucketing rules that are easy to get subtly wrong:
multi-day clipping, the all-day/OOO capacity rule, declined invites, teammate
exclusion, and demo/real workspace isolation.
"""
import datetime
import zoneinfo
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from kanban.budget_models import TimeEntry
from kanban.models import (
    Board, BoardMembership, CalendarEvent, CalendarEventParticipant, Column, Task,
)
from kanban.utils.calendar_analytics import compute_time_health

TZ = zoneinfo.ZoneInfo(settings.TIME_ZONE)


def _local(year, month, day, hour=0, minute=0):
    """Build an aware datetime in the SERVER timezone.

    The helper matches how compute_time_health converts events for bucketing,
    so a "10:00–12:00 meeting" in a test is 2h on that local day regardless of
    what TIME_ZONE the suite runs under.
    """
    return datetime.datetime(year, month, day, hour, minute, tzinfo=TZ)


class TimeHealthTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('th_user', password='x')
        cls.teammate = User.objects.create_user('th_teammate', password='x')

        cls.board = Board.objects.create(name='TH Board', created_by=cls.user)
        BoardMembership.objects.create(board=cls.board, user=cls.user)
        BoardMembership.objects.create(board=cls.board, user=cls.teammate)
        cls.column = Column.objects.create(board=cls.board, name='To Do', position=1)

        # A fixed Mon–Sun window so weekday-sensitive assertions are stable.
        cls.start = datetime.date(2026, 7, 20)   # Monday
        cls.end = datetime.date(2026, 7, 26)     # Sunday

    def _health(self, user=None):
        return compute_time_health(user or self.user, self.start, self.end)

    def _make_event(self, **kwargs):
        kwargs.setdefault('created_by', self.user)
        kwargs.setdefault('event_type', 'meeting')
        kwargs.setdefault('board', self.board)
        return CalendarEvent.objects.create(title=kwargs.pop('title', 'Ev'), **kwargs)

    def _day(self, data, date_obj):
        return next(d for d in data['days'] if d['date'] == date_obj.isoformat())

    # -- bucketing ------------------------------------------------------

    def test_meeting_and_focus_split_into_their_buckets(self):
        self._make_event(
            title='Standup', event_type='meeting',
            start_datetime=_local(2026, 7, 21, 10), end_datetime=_local(2026, 7, 21, 12),
        )
        self._make_event(
            title='Code review', event_type='busy_block',
            start_datetime=_local(2026, 7, 21, 13), end_datetime=_local(2026, 7, 21, 16),
        )
        data = self._health()
        day = self._day(data, datetime.date(2026, 7, 21))
        self.assertEqual(day['meeting'], 2.0)
        self.assertEqual(day['focus'], 3.0)
        # Default capacity 40/5 = 8h/day, so 8 - 5 = 3h free.
        self.assertEqual(day['free'], 3.0)

    def test_team_event_counts_as_meeting_time(self):
        self._make_event(
            title='All hands', event_type='team_event',
            start_datetime=_local(2026, 7, 22, 9), end_datetime=_local(2026, 7, 22, 10),
        )
        self.assertEqual(self._day(self._health(), datetime.date(2026, 7, 22))['meeting'], 1.0)

    def test_multi_day_event_is_clipped_per_day_not_dumped_on_start(self):
        # 22nd 22:00 → 23rd 02:00 = 2h on the 22nd, 2h on the 23rd.
        self._make_event(
            title='Long call', event_type='meeting',
            start_datetime=_local(2026, 7, 22, 22), end_datetime=_local(2026, 7, 23, 2),
        )
        data = self._health()
        self.assertEqual(self._day(data, datetime.date(2026, 7, 22))['meeting'], 2.0)
        self.assertEqual(self._day(data, datetime.date(2026, 7, 23))['meeting'], 2.0)

    def test_all_day_ooo_removes_a_working_day_rather_than_booking_24h(self):
        self._make_event(
            title='Leave', event_type='out_of_office', is_all_day=True,
            start_datetime=_local(2026, 7, 24), end_datetime=_local(2026, 7, 24),
        )
        day = self._day(self._health(), datetime.date(2026, 7, 24))
        self.assertEqual(day['ooo'], 8.0)     # one working day, NOT 24
        self.assertEqual(day['free'], 0.0)

    def test_free_time_never_goes_negative_when_overbooked(self):
        self._make_event(
            title='Marathon', event_type='meeting',
            start_datetime=_local(2026, 7, 20, 6), end_datetime=_local(2026, 7, 20, 20),
        )
        self.assertEqual(self._day(self._health(), datetime.date(2026, 7, 20))['free'], 0.0)

    def test_weekend_days_grant_no_capacity(self):
        """A Mon–Sun window is 40h of capacity, not 7x8=56h.

        Counting weekends as working days overstated a 40h week by 40% and made
        genuinely over-capacity weeks read as comfortable.
        """
        data = self._health()
        self.assertEqual(data['totals']['capacity'], 40.0)
        self.assertEqual(self._day(data, datetime.date(2026, 7, 25))['capacity'], 0.0)
        self.assertEqual(self._day(data, datetime.date(2026, 7, 25))['free'], 0.0)
        self.assertEqual(self._day(data, datetime.date(2026, 7, 24))['capacity'], 8.0)

    def test_weekend_logged_time_still_counts_as_effort(self):
        # Weekends grant no capacity, but work done then is still real.
        task = self._task()
        TimeEntry.objects.create(
            task=task, user=self.user, hours_spent=Decimal('5.00'),
            work_date=datetime.date(2026, 7, 25),   # Saturday
        )
        data = self._health()
        self.assertEqual(data['totals']['logged'], 5.0)
        self.assertEqual(self._day(data, datetime.date(2026, 7, 25))['logged'], 5.0)

    # -- whose time counts ----------------------------------------------

    def test_declined_invite_contributes_no_hours(self):
        event = CalendarEvent.objects.create(
            title='Optional sync', event_type='meeting', board=self.board,
            start_datetime=_local(2026, 7, 21, 9), end_datetime=_local(2026, 7, 21, 11),
            created_by=self.teammate,
        )
        CalendarEventParticipant.objects.create(
            event=event, user=self.user, status=CalendarEventParticipant.DECLINED,
        )
        self.assertEqual(self._health()['totals']['meeting'], 0.0)

    def test_pending_invite_does_contribute_hours(self):
        event = CalendarEvent.objects.create(
            title='Kickoff', event_type='meeting', board=self.board,
            start_datetime=_local(2026, 7, 21, 9), end_datetime=_local(2026, 7, 21, 11),
            created_by=self.teammate,
        )
        CalendarEventParticipant.objects.create(
            event=event, user=self.user, status=CalendarEventParticipant.PENDING,
        )
        self.assertEqual(self._health()['totals']['meeting'], 2.0)

    def test_teammate_event_i_am_not_invited_to_is_excluded(self):
        # Visible on the grid as a sanitized "teammate — busy" block, but it is
        # not the viewer's time and must not be tallied.
        CalendarEvent.objects.create(
            title='Their focus', event_type='busy_block', visibility='team',
            board=self.board,
            start_datetime=_local(2026, 7, 21, 9), end_datetime=_local(2026, 7, 21, 17),
            created_by=self.teammate,
        )
        totals = self._health()['totals']
        self.assertEqual(totals['focus'], 0.0)
        self.assertEqual(totals['meeting'], 0.0)

    def test_demo_event_excluded_for_real_workspace_viewer(self):
        self._make_event(
            title='Demo meeting', event_type='meeting', is_demo=True,
            start_datetime=_local(2026, 7, 21, 9), end_datetime=_local(2026, 7, 21, 11),
        )
        self.assertEqual(self._health()['totals']['meeting'], 0.0)

    def test_event_outside_the_window_is_excluded(self):
        self._make_event(
            title='Next month', event_type='meeting',
            start_datetime=_local(2026, 8, 10, 9), end_datetime=_local(2026, 8, 10, 11),
        )
        self.assertEqual(self._health()['totals']['meeting'], 0.0)

    # -- commitments (tasks counted, never summed as hours) --------------

    def test_tasks_are_counted_not_converted_to_hours(self):
        # A 10-day task bar overlapping the window must add ZERO hours.
        Task.objects.create(
            title='RBAC', column=self.column, position=1, item_type='task',
            created_by=self.user, assigned_to=self.user,
            start_date=datetime.date(2026, 7, 15),
            due_date=_local(2026, 7, 22, 17), progress=0,
        )
        data = self._health()
        self.assertEqual(data['commitments_due'], 1)
        totals = data['totals']
        self.assertEqual(totals['meeting'] + totals['focus'] + totals['ooo'], 0.0)

    def test_completed_task_is_not_a_live_commitment(self):
        Task.objects.create(
            title='Done thing', column=self.column, position=2, item_type='task',
            created_by=self.user, assigned_to=self.user,
            due_date=_local(2026, 7, 22, 17), progress=100,
        )
        self.assertEqual(self._health()['commitments_due'], 0)

    def test_task_assigned_to_someone_else_is_not_my_commitment(self):
        Task.objects.create(
            title='Their task', column=self.column, position=3, item_type='task',
            created_by=self.user, assigned_to=self.teammate,
            due_date=_local(2026, 7, 22, 17), progress=0,
        )
        self.assertEqual(self._health()['commitments_due'], 0)

    # -- actuals overlay (TimeEntry) -------------------------------------

    def _task(self, title='Work', position=90, assignee=None):
        return Task.objects.create(
            title=title, column=self.column, position=position, item_type='task',
            created_by=self.user, assigned_to=assignee or self.user,
            start_date=datetime.date(2026, 7, 20), progress=10,
        )

    def test_logged_hours_reported_per_day_and_in_totals(self):
        task = self._task()
        TimeEntry.objects.create(
            task=task, user=self.user, hours_spent=Decimal('3.50'),
            work_date=datetime.date(2026, 7, 21),
        )
        TimeEntry.objects.create(
            task=task, user=self.user, hours_spent=Decimal('2.00'),
            work_date=datetime.date(2026, 7, 22),
        )
        data = self._health()
        self.assertTrue(data['has_logged_time'])
        self.assertEqual(data['totals']['logged'], 5.5)
        self.assertEqual(data['days_logged'], 2)
        self.assertEqual(self._day(data, datetime.date(2026, 7, 21))['logged'], 3.5)

    def test_logged_time_is_not_added_into_the_scheduled_stack(self):
        # The core "don't double-count" rule: an hour can be both scheduled and
        # logged, so logged hours must never inflate meeting/focus/free.
        task = self._task()
        self._make_event(
            title='Pairing', event_type='busy_block',
            start_datetime=_local(2026, 7, 21, 9), end_datetime=_local(2026, 7, 21, 12),
        )
        TimeEntry.objects.create(
            task=task, user=self.user, hours_spent=Decimal('3.00'),
            work_date=datetime.date(2026, 7, 21),
        )
        day = self._day(self._health(), datetime.date(2026, 7, 21))
        self.assertEqual(day['focus'], 3.0)
        self.assertEqual(day['logged'], 3.0)
        self.assertEqual(day['free'], 5.0)   # 8 capacity - 3 scheduled, NOT 8-6

    def test_another_users_logged_time_is_excluded(self):
        task = self._task(assignee=self.teammate)
        TimeEntry.objects.create(
            task=task, user=self.teammate, hours_spent=Decimal('6.00'),
            work_date=datetime.date(2026, 7, 21),
        )
        data = self._health()
        self.assertEqual(data['totals']['logged'], 0.0)
        self.assertFalse(data['has_logged_time'])

    def test_logged_time_outside_window_excluded(self):
        task = self._task()
        TimeEntry.objects.create(
            task=task, user=self.user, hours_spent=Decimal('4.00'),
            work_date=datetime.date(2026, 7, 5),
        )
        self.assertEqual(self._health()['totals']['logged'], 0.0)

    def test_logged_time_is_board_scoped(self):
        """A persona owning entries on many sandbox copies must not have them
        summed together — that is what produced 200h+ 'days' in demo data."""
        other_board = Board.objects.create(name='Other', created_by=self.user)
        other_col = Column.objects.create(board=other_board, name='To Do', position=1)
        other_task = Task.objects.create(
            title='Elsewhere', column=other_col, position=1, item_type='task',
            created_by=self.user, assigned_to=self.user, progress=0,
        )
        TimeEntry.objects.create(
            task=other_task, user=self.user, hours_spent=Decimal('7.00'),
            work_date=datetime.date(2026, 7, 21),
        )
        scoped = compute_time_health(
            self.user, self.start, self.end, scope_boards=Board.objects.filter(pk=self.board.pk),
        )
        self.assertEqual(scoped['totals']['logged'], 0.0)

        unscoped = compute_time_health(self.user, self.start, self.end)
        self.assertEqual(unscoped['totals']['logged'], 7.0)

    def test_unscheduled_effort_flag_when_logging_far_beyond_schedule(self):
        task = self._task()
        self._make_event(
            title='One meeting', event_type='meeting',
            start_datetime=_local(2026, 7, 21, 9), end_datetime=_local(2026, 7, 21, 10),
        )
        TimeEntry.objects.create(
            task=task, user=self.user, hours_spent=Decimal('9.00'),
            work_date=datetime.date(2026, 7, 21),
        )
        codes = {f['code'] for f in self._health()['flags']}
        self.assertIn('unscheduled_effort', codes)

    def test_over_capacity_flag_when_logged_exceeds_weekly_capacity(self):
        task = self._task()
        for day in range(20, 26):
            TimeEntry.objects.create(
                task=task, user=self.user, hours_spent=Decimal('9.00'),
                work_date=datetime.date(2026, 7, day),
            )
        codes = {f['code'] for f in self._health()['flags']}
        self.assertIn('over_capacity', codes)   # 54h logged vs 40h capacity

    def test_no_logged_time_leaves_overlay_off(self):
        self._make_event(
            title='Sync', event_type='meeting',
            start_datetime=_local(2026, 7, 21, 10), end_datetime=_local(2026, 7, 21, 11),
        )
        data = self._health()
        self.assertFalse(data['has_logged_time'])
        self.assertEqual(data['totals']['logged'], 0.0)
        self.assertNotIn(
            'unscheduled_effort', {f['code'] for f in data['flags']},
        )

    # -- flags -----------------------------------------------------------

    def test_overcommitted_flag_when_tasks_due_and_no_free_time(self):
        for day in range(20, 27):
            self._make_event(
                title=f'Booked {day}', event_type='meeting',
                start_datetime=_local(2026, 7, day, 6),
                end_datetime=_local(2026, 7, day, 20),
            )
        Task.objects.create(
            title='Due anyway', column=self.column, position=4, item_type='task',
            created_by=self.user, assigned_to=self.user,
            due_date=_local(2026, 7, 22, 17), progress=0,
        )
        codes = {f['code'] for f in self._health()['flags']}
        self.assertIn('overcommitted', codes)
        self.assertIn('meeting_heavy', codes)

    def test_quiet_week_raises_no_flags(self):
        self._make_event(
            title='Short sync', event_type='meeting',
            start_datetime=_local(2026, 7, 21, 10), end_datetime=_local(2026, 7, 21, 11),
        )
        self.assertEqual(self._health()['flags'], [])


class TimeHealthEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('th_api', password='x')
        cls.board = Board.objects.create(name='API Board', created_by=cls.user)
        BoardMembership.objects.create(board=cls.board, user=cls.user)

    def test_endpoint_requires_login(self):
        response = self.client.get(reverse('calendar_time_health_api'))
        self.assertIn(response.status_code, (302, 403))

    def test_endpoint_returns_expected_shape(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse('calendar_time_health_api'),
            {'start': '2026-07-20T00:00:00', 'end': '2026-07-27T00:00:00'},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for key in ('days', 'totals', 'commitments_due', 'flags'):
            self.assertIn(key, data)
        # FullCalendar's end is exclusive → 7 inclusive days, not 8.
        self.assertEqual(len(data['days']), 7)
        self.assertEqual(data['range_end'], '2026-07-26')

    def test_endpoint_defaults_to_current_week_without_params(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('calendar_time_health_api'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['days']), 7)
