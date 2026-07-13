"""
Calendar event feed visibility tests.

Covers the bug where a `visibility='private'` CalendarEvent was invisible on
an invited participant's own "My Calendar" feed, even after they accepted the
invitation — because unified_calendar_events_api's "invited participant"
Q() clause additionally required visibility in ('team', 'public'). Being an
explicit invitee should itself grant visibility, independent of `visibility`
(which only gates *other*, non-invited teammates) — see calendar_event_detail's
participant check for the equivalent, already-correct behavior.
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from kanban.models import CalendarEvent, CalendarEventParticipant


class PrivateEventParticipantVisibilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organizer = User.objects.create_user('organizer', password='x')
        cls.invitee = User.objects.create_user('invitee', password='x')
        cls.outsider = User.objects.create_user('outsider', password='x')

        now = timezone.now()
        cls.event = CalendarEvent.objects.create(
            title='Metting 1',
            event_type='meeting',
            visibility='private',
            start_datetime=now,
            end_datetime=now + timezone.timedelta(hours=1),
            created_by=cls.organizer,
        )
        cls.link = CalendarEventParticipant.objects.create(
            event=cls.event, user=cls.invitee, status=CalendarEventParticipant.PENDING,
        )

    def _feed_event_ids(self, response):
        return {ev['id'] for ev in response.json()}

    def test_invited_participant_sees_private_event_while_pending(self):
        self.client.force_login(self.invitee)
        response = self.client.get(reverse('unified_calendar_events_api'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(f'event-{self.event.id}', self._feed_event_ids(response))

    def test_invited_participant_sees_private_event_after_accepting(self):
        self.client.force_login(self.invitee)
        rsvp_response = self.client.post(
            reverse('calendar_event_rsvp', args=[self.event.id]), {'action': 'accept'},
        )
        self.assertEqual(rsvp_response.status_code, 302)
        self.link.refresh_from_db()
        self.assertEqual(self.link.status, CalendarEventParticipant.ACCEPTED)

        response = self.client.get(reverse('unified_calendar_events_api'))
        self.assertIn(f'event-{self.event.id}', self._feed_event_ids(response))

    def test_declined_participant_no_longer_sees_private_event(self):
        self.client.force_login(self.invitee)
        self.client.post(
            reverse('calendar_event_rsvp', args=[self.event.id]), {'action': 'decline'},
        )
        response = self.client.get(reverse('unified_calendar_events_api'))
        self.assertNotIn(f'event-{self.event.id}', self._feed_event_ids(response))

    def test_uninvited_user_does_not_see_private_event(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('unified_calendar_events_api'))
        self.assertNotIn(f'event-{self.event.id}', self._feed_event_ids(response))

    def test_organizer_sees_own_private_event(self):
        self.client.force_login(self.organizer)
        response = self.client.get(reverse('unified_calendar_events_api'))
        self.assertIn(f'event-{self.event.id}', self._feed_event_ids(response))
