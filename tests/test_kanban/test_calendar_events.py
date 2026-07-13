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
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from kanban.calendar_views import _ASSIGNEE_PALETTE, _build_assignee_color_map

from accounts.models import Organization, UserProfile
from kanban.models import Board, BoardMembership, CalendarEvent, CalendarEventParticipant, Workspace
from kanban.sandbox_views import _clone_calendar_events_for_user


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


class CloneCalendarEventsRsvpStatusTests(TestCase):
    """
    _clone_calendar_events_for_user (kanban/sandbox_views.py) copies the demo
    template board's CalendarEvents onto each user's own sandbox board copy.
    It must preserve each participant's real RSVP status (pending/declined/
    accepted) rather than flattening every clone to "accepted" — real users
    only ever see their own sandbox clone, so a hardcoded status would
    silently erase any RSVP variety seeded on the template board (see
    populate_calendar_demo_data).
    """
    @classmethod
    def setUpTestData(cls):
        cls.creator = User.objects.create_user('creator', password='x')
        cls.demo_org = Organization.objects.create(
            name='Demo Org', is_demo=True, created_by=cls.creator,
        )
        cls.demo_ws = Workspace.objects.create(
            name='Demo Workspace', organization=cls.demo_org,
            is_demo=True, is_active=True, created_by=cls.creator,
        )
        cls.template_board = Board.objects.create(
            name='Software Development', organization=cls.demo_org, workspace=cls.demo_ws,
            owner=cls.creator, created_by=cls.creator,
            is_official_demo_board=True, is_seed_demo_data=True,
        )
        cls.organizer = User.objects.create_user('organizer2', password='x')
        cls.pending_user = User.objects.create_user('pending_persona', password='x')
        cls.declined_user = User.objects.create_user('declined_persona', password='x')
        cls.accepted_user = User.objects.create_user('accepted_persona', password='x')

        now = timezone.now()
        cls.template_event = CalendarEvent.objects.create(
            title='Sprint Planning', event_type='meeting', visibility='team',
            start_datetime=now, end_datetime=now + timezone.timedelta(hours=1),
            board=cls.template_board, created_by=cls.organizer, is_demo=True,
        )
        cls.pending_responded_at = None
        cls.declined_responded_at = now - timezone.timedelta(days=1)
        cls.accepted_responded_at = now - timezone.timedelta(days=2)
        CalendarEventParticipant.objects.create(
            event=cls.template_event, user=cls.pending_user,
            status=CalendarEventParticipant.PENDING, responded_at=cls.pending_responded_at,
        )
        CalendarEventParticipant.objects.create(
            event=cls.template_event, user=cls.declined_user,
            status=CalendarEventParticipant.DECLINED, responded_at=cls.declined_responded_at,
        )
        CalendarEventParticipant.objects.create(
            event=cls.template_event, user=cls.accepted_user,
            status=CalendarEventParticipant.ACCEPTED, responded_at=cls.accepted_responded_at,
        )

    def test_clone_preserves_each_participant_real_rsvp_status(self):
        viewer = User.objects.create_user('demo_prospect', password='x')
        UserProfile.objects.get_or_create(user=viewer)
        sandbox_board = Board.objects.create(
            name='demo_prospect sandbox', organization=self.demo_org, workspace=self.demo_ws,
            owner=viewer, created_by=viewer, is_sandbox_copy=True,
            is_official_demo_board=False, is_seed_demo_data=False,
            cloned_from=self.template_board,
        )

        _clone_calendar_events_for_user(viewer)

        cloned_event = CalendarEvent.objects.get(board=sandbox_board, title='Sprint Planning')
        statuses = {
            link.user_id: link.status
            for link in cloned_event.participant_links.all()
        }
        self.assertEqual(statuses[self.pending_user.id], CalendarEventParticipant.PENDING)
        self.assertEqual(statuses[self.declined_user.id], CalendarEventParticipant.DECLINED)
        self.assertEqual(statuses[self.accepted_user.id], CalendarEventParticipant.ACCEPTED)

        # responded_at is carried over verbatim too, not just the status enum.
        pending_link = cloned_event.participant_links.get(user=self.pending_user)
        declined_link = cloned_event.participant_links.get(user=self.declined_user)
        self.assertIsNone(pending_link.responded_at)
        self.assertEqual(declined_link.responded_at, self.declined_responded_at)

        # created_by is remapped to the sandbox owner (existing behavior),
        # not flattened participant statuses.
        self.assertEqual(cloned_event.created_by_id, viewer.id)


class CalendarFeedBoardScopeTests(TestCase):
    """Regression: the unified events feed must return each seeded event exactly
    once, and must not leak one user's sandbox events into another's feed.

    Before the feed was board-scoped, a demo user saw BOTH their per-user clone
    (created_by=them, on their sandbox board) AND the original persona-created
    event still living on the shared official template board — the latter matched
    by the teammate-visibility clause because personas are members of the sandbox.
    Every seeded event rendered twice; public team_events showed as two identical
    full-title rows (the "Team Lunch appears twice" report). The fix scopes events
    to boards the viewer belongs to (plus board-less + explicitly-invited events),
    while a small persona-owned subset is kept on the sandbox so the "Team can see
    I'm busy" teammate blocks still render.
    """

    @classmethod
    def setUpTestData(cls):
        cls.priya = User.objects.create_user(
            'priya_scope', password='x', email='priya@demo.prizmai.local',
            first_name='Priya', last_name='Sharma',
        )
        cls.marcus = User.objects.create_user(
            'marcus_scope', password='x', email='marcus@demo.prizmai.local',
            first_name='Marcus', last_name='Chen',
        )
        cls.demo_org = Organization.objects.create(
            name='Demo Org Scope', is_demo=True, created_by=cls.priya,
        )
        cls.demo_ws = Workspace.objects.create(
            name='Demo WS Scope', organization=cls.demo_org,
            is_demo=True, is_active=True, created_by=cls.priya,
        )
        cls.template_board = Board.objects.create(
            name='Software Development', organization=cls.demo_org, workspace=cls.demo_ws,
            owner=cls.priya, created_by=cls.priya,
            is_official_demo_board=True, is_seed_demo_data=True,
        )
        BoardMembership.objects.create(board=cls.template_board, user=cls.priya, role='owner')
        BoardMembership.objects.create(board=cls.template_board, user=cls.marcus, role='member')

        now = timezone.now()
        # Public team_event — the visible duplicate in the bug report.
        cls.team_event = CalendarEvent.objects.create(
            title='Team Lunch - Sprint 2 Celebration', event_type='team_event',
            visibility='public', start_datetime=now, end_datetime=now + timezone.timedelta(hours=1),
            board=cls.template_board, created_by=cls.priya, is_demo=True,
        )
        # Persona-owned teammate block that must survive the clone as persona-owned
        # (title is in _clone_calendar_events_for_user._PERSONA_OWNED_TITLES).
        cls.ooo = CalendarEvent.objects.create(
            title='Marcus Chen - PTO', event_type='out_of_office', visibility='team',
            is_all_day=True, start_datetime=now, end_datetime=now + timezone.timedelta(hours=1),
            board=cls.template_board, created_by=cls.marcus, is_demo=True,
        )

    def _make_prospect(self, username, persona_members=True):
        user = User.objects.create_user(username, password='x')
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.organization = self.demo_org
        profile.active_workspace = self.demo_ws
        profile.is_viewing_demo = True
        profile.save()
        sandbox = Board.objects.create(
            name=f'{username} sandbox', organization=self.demo_org, workspace=self.demo_ws,
            owner=user, created_by=user, is_sandbox_copy=True,
            is_official_demo_board=False, is_seed_demo_data=False, cloned_from=self.template_board,
        )
        BoardMembership.objects.create(board=sandbox, user=user, role='owner')
        if persona_members:
            BoardMembership.objects.create(board=sandbox, user=self.priya, role='member')
            BoardMembership.objects.create(board=sandbox, user=self.marcus, role='member')
        _clone_calendar_events_for_user(user)
        return user, sandbox

    def _feed_events(self, user):
        self.client.force_login(user)
        resp = self.client.get(reverse('unified_calendar_events_api'))
        self.assertEqual(resp.status_code, 200)
        return [ev for ev in resp.json() if ev.get('source') == 'event']

    def test_seeded_team_event_appears_exactly_once(self):
        prospect, _ = self._make_prospect('scope_prospect_a')
        titles = [ev['title'] for ev in self._feed_events(prospect)]
        # Was 2 before board-scoping (owner clone + leaked template original).
        self.assertEqual(titles.count('Team Lunch - Sprint 2 Celebration'), 1)

    def test_persona_owned_ooo_kept_and_shown_as_teammate_block(self):
        prospect, sandbox = self._make_prospect('scope_prospect_b')
        # Clone keeps the OOO persona-owned (Marcus), not remapped to the owner.
        cloned_ooo = CalendarEvent.objects.get(board=sandbox, title='Marcus Chen - PTO')
        self.assertEqual(cloned_ooo.created_by_id, self.marcus.id)
        # ...and the owner sees exactly one sanitized OOO teammate-status block.
        ooo_blocks = [
            ev for ev in self._feed_events(prospect)
            if ev['extendedProps'].get('event_type_key') == 'out_of_office'
        ]
        self.assertEqual(len(ooo_blocks), 1)
        self.assertEqual(ooo_blocks[0]['extendedProps']['layer'], 'teammate_status')
        self.assertIn('Out of Office', ooo_blocks[0]['title'])

    def test_other_users_sandbox_events_do_not_leak(self):
        prospect_a, sandbox_a = self._make_prospect('scope_prospect_c')
        # prospect_d is a separate real user, NOT a member of prospect_c's sandbox.
        prospect_d, _ = self._make_prospect('scope_prospect_d')
        a_event_pks = set(CalendarEvent.objects.filter(board=sandbox_a).values_list('id', flat=True))
        feed_pks = {int(ev['id'].split('-')[1]) for ev in self._feed_events(prospect_d)}
        # prospect_d must see none of prospect_c's sandbox events — including the
        # Marcus-owned OOO, which the teammate clause matches (Marcus is in d's
        # board_member_ids) but the board scope correctly excludes.
        self.assertTrue(feed_pks.isdisjoint(a_event_pks))


class AssigneeColorMapTests(SimpleTestCase):
    """Regression: two displayed teammates must never share a colour, for any
    number of members. The old ``user_id % len(palette)`` hashing collided ids
    congruent mod the palette length (e.g. the viewer and Priya both red).
    """

    def test_no_collision_for_ids_congruent_mod_palette(self):
        n = len(_ASSIGNEE_PALETTE)
        cmap = _build_assignee_color_map([3, 3 + n])  # exact old-collision case
        self.assertNotEqual(cmap[3], cmap[3 + n])

    def test_distinct_colours_beyond_palette_size(self):
        ids = list(range(1, 26))  # 25 users > 10-colour palette
        cmap = _build_assignee_color_map(ids)
        self.assertEqual(len(set(cmap.values())), len(ids))  # all distinct

    def test_first_ten_use_curated_palette_in_order(self):
        cmap = _build_assignee_color_map(list(range(1, 11)))
        self.assertEqual([cmap[i] for i in range(1, 11)], _ASSIGNEE_PALETTE)

    def test_deterministic_regardless_of_input_order(self):
        # Same universe → same map, so the legend and the events feed agree.
        self.assertEqual(
            _build_assignee_color_map([9, 5, 1]),
            _build_assignee_color_map([1, 9, 5]),
        )
