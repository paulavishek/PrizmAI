"""
Tests for calendar_event_reschedule — the lightweight PATCH endpoint that
persists a CalendarEvent move/resize from the calendar's drag-and-drop UI.

Covers:
- creator can move an all-day event; the stored date is stable (no tz drift,
  because all-day events are stored at UTC midnight — see calendar_create_event)
- creator can move a timed event (floating local datetime strings)
- a non-creator gets 403 (creator-only, matching edit/delete)
- end-before-start is rejected
"""
import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from kanban.models import CalendarEvent


class CalendarEventRescheduleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('ev_owner', password='x')
        cls.other = User.objects.create_user('ev_other', password='x')

        now = timezone.now()
        cls.all_day = CalendarEvent.objects.create(
            title='All Day Event', event_type='out_of_office', visibility='team',
            is_all_day=True,
            start_datetime=now, end_datetime=now,
            created_by=cls.owner,
        )
        cls.timed = CalendarEvent.objects.create(
            title='Timed Meeting', event_type='meeting', visibility='team',
            is_all_day=False,
            start_datetime=now, end_datetime=now + timezone.timedelta(hours=1),
            created_by=cls.owner,
        )

    def _patch(self, event_id, payload):
        return self.client.patch(
            reverse('calendar_event_reschedule', args=[event_id]),
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_creator_moves_all_day_event_date_is_stable(self):
        self.client.force_login(self.owner)
        resp = self._patch(self.all_day.id, {
            'is_all_day': True,
            'start_datetime': '2026-08-10',
            'end_datetime': '2026-08-12',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])

        self.all_day.refresh_from_db()
        # All-day events are stored at UTC midnight, so .date() equals the chosen
        # calendar date regardless of the active timezone.
        self.assertEqual(self.all_day.start_datetime.date().isoformat(), '2026-08-10')
        self.assertEqual(self.all_day.end_datetime.date().isoformat(), '2026-08-12')
        self.assertTrue(self.all_day.is_all_day)

    def test_creator_moves_timed_event(self):
        self.client.force_login(self.owner)
        resp = self._patch(self.timed.id, {
            'is_all_day': False,
            'start_datetime': '2026-08-10T14:00:00',
            'end_datetime': '2026-08-10T15:30:00',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])

        self.timed.refresh_from_db()
        local_start = timezone.localtime(self.timed.start_datetime)
        local_end = timezone.localtime(self.timed.end_datetime)
        self.assertEqual(local_start.strftime('%Y-%m-%dT%H:%M'), '2026-08-10T14:00')
        self.assertEqual(local_end.strftime('%Y-%m-%dT%H:%M'), '2026-08-10T15:30')
        self.assertFalse(self.timed.is_all_day)

    def test_non_creator_gets_403(self):
        self.client.force_login(self.other)
        resp = self._patch(self.all_day.id, {
            'is_all_day': True,
            'start_datetime': '2026-08-10',
            'end_datetime': '2026-08-12',
        })
        self.assertEqual(resp.status_code, 403)
        self.all_day.refresh_from_db()
        # Unchanged.
        self.assertNotEqual(self.all_day.start_datetime.date().isoformat(), '2026-08-10')

    def test_end_before_start_rejected(self):
        self.client.force_login(self.owner)
        resp = self._patch(self.timed.id, {
            'is_all_day': False,
            'start_datetime': '2026-08-10T15:00:00',
            'end_datetime': '2026-08-10T14:00:00',
        })
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()['success'])

    def test_missing_dates_rejected(self):
        self.client.force_login(self.owner)
        resp = self._patch(self.timed.id, {'is_all_day': False})
        self.assertEqual(resp.status_code, 400)
