"""
Populate demo data for the Calendar feature
=============================================
Creates 11 CalendarEvents (meetings, out-of-office, busy blocks, team events)
on the official "Software Development" demo board — realistic visibility mix,
RSVP status mix across the three personas, and at least one event tied to a
real seeded task deadline for narrative coherence.

Usage:
    python manage.py populate_calendar_demo_data
    python manage.py populate_calendar_demo_data --reset

Standalone or called automatically from populate_all_demo_data.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from datetime import timedelta, datetime, time

from accounts.models import Organization
from accounts.demo_personas import DEMO_PERSONAS
from kanban.models import Board, Task, CalendarEvent, CalendarEventParticipant


class Command(BaseCommand):
    help = 'Populate demo Calendar Events (meetings, OOO, busy blocks, team events)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing calendar demo data before creating new data',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('\n Populating Calendar Demo Data...'))

        # --- Get demo organization ---
        try:
            demo_org = Organization.objects.get(is_demo=True, name='Demo - Acme Corporation')
        except Organization.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                '[FAIL] Demo organization not found. Run create_demo_organization first.'
            ))
            return

        # --- Get demo board ---
        board = Board.objects.filter(
            organization=demo_org,
            is_official_demo_board=True,
            name__icontains='software',
        ).first()
        if not board:
            self.stdout.write(self.style.ERROR(
                '[FAIL] Software Development demo board not found.'
            ))
            return

        # --- Get demo users ---
        priya = User.objects.filter(username=DEMO_PERSONAS['lead']['username']).first()
        marcus = User.objects.filter(username=DEMO_PERSONAS['frontend']['username']).first()
        elena = User.objects.filter(username=DEMO_PERSONAS['devops']['username']).first()
        if not all([priya, marcus, elena]):
            self.stdout.write(self.style.ERROR(
                '[FAIL] Demo users not found. Run create_demo_organization first.'
            ))
            return

        # --- Reset if requested ---
        if options['reset']:
            deleted = CalendarEvent.objects.filter(board=board).delete()
            self.stdout.write(f'   [OK] Cleared calendar data ({deleted[0]} objects)')

        # --- Idempotency: skip if events already exist ---
        if CalendarEvent.objects.filter(board=board).exists():
            self.stdout.write(self.style.SUCCESS(
                '   [OK] Calendar events already exist - skipping'
            ))
            return

        now = timezone.now()
        today = now.date()

        # Real seeded tasks — looked up by title (not positional index) so this
        # stays correct if populate_all_demo_data's task list is ever reordered.
        task_registration = Task.objects.filter(column__board=board, title='User Registration Flow').first()
        task_auth = Task.objects.filter(column__board=board, title='Authentication System').first()
        task_upload = Task.objects.filter(column__board=board, title='File Upload System').first()

        def _dt(day_offset, hour, minute):
            return timezone.make_aware(datetime.combine(today + timedelta(days=day_offset), time(hour, minute)))

        def _all_day(day_offset):
            start = timezone.make_aware(datetime.combine(today + timedelta(days=day_offset), time(0, 0)))
            end = timezone.make_aware(datetime.combine(today + timedelta(days=day_offset), time(23, 59)))
            return start, end

        events = [
            {
                'title': 'Daily Standup',
                'description': 'Team sync: blockers, progress, and priorities for the day.',
                'event_type': 'meeting', 'visibility': 'team',
                'start_datetime': _dt(0, 9, 0), 'end_datetime': _dt(0, 9, 15),
                'location': 'Zoom - #standup',
                'created_by': priya,
                'participant_statuses': {priya: 'accepted', marcus: 'accepted', elena: 'accepted'},
            },
            {
                'title': 'Sprint 3 Planning',
                'description': 'Plan Sprint 3 scope. Review backlog priorities, estimate new tasks, and agree on capacity.',
                'event_type': 'meeting', 'visibility': 'team',
                'start_datetime': _dt(2, 10, 0), 'end_datetime': _dt(2, 11, 30),
                'location': 'Conference Room B',
                'created_by': priya, 'linked_task': task_registration,
                'participant_statuses': {priya: 'accepted', marcus: 'accepted', elena: 'pending'},
            },
            {
                'title': 'Architecture Review: Search Engine',
                'description': 'Deep-dive on Search & Indexing Engine design. Review Elasticsearch vs Meilisearch trade-offs.',
                'event_type': 'meeting', 'visibility': 'team',
                'start_datetime': _dt(4, 14, 0), 'end_datetime': _dt(4, 15, 0),
                'location': 'Zoom - #architecture',
                'created_by': marcus,
                'participant_statuses': {marcus: 'accepted', elena: 'declined'},
            },
            {
                'title': 'Sprint 2 Retrospective',
                'description': 'Reflect on Sprint 2 outcomes. Discuss what went well, what needs improvement, and action items.',
                'event_type': 'meeting', 'visibility': 'team',
                'start_datetime': _dt(-3, 15, 0), 'end_datetime': _dt(-3, 16, 0),
                'location': 'Conference Room A',
                'created_by': priya,
                'participant_statuses': {priya: 'accepted', marcus: 'accepted', elena: 'accepted'},
            },
            {
                'title': 'Team Lunch - Sprint 2 Celebration',
                'description': 'Celebrating successful Sprint 2 delivery! Dashboard UI and Authentication shipped on time.',
                'event_type': 'team_event', 'visibility': 'public',
                'start_datetime': _dt(7, 12, 0), 'end_datetime': _dt(7, 13, 30),
                'location': 'Downtown Bistro',
                'created_by': priya,
                'participant_statuses': {priya: 'accepted', marcus: 'accepted', elena: 'pending'},
            },
            # Deliberate narrative tie-in: Marcus is OOO the same day his own
            # "File Upload System" task (due_offset=2, see populate_all_demo_data)
            # is due — a realistic deadline-risk scenario for the demo.
            {
                'title': 'Marcus Chen - PTO',
                'description': 'Out of office for personal day. Elena covering API reviews.',
                'event_type': 'out_of_office', 'visibility': 'team',
                'is_all_day': True,
                'created_by': marcus,
                'participant_statuses': {marcus: 'accepted'},
                '_all_day_offset': 2,
            },
            {
                'title': 'Focus Block: Code Review',
                'description': 'Reserved time for reviewing Authentication System and File Upload PRs.',
                'event_type': 'busy_block', 'visibility': 'private',
                'start_datetime': _dt(1, 13, 0), 'end_datetime': _dt(1, 15, 0),
                'created_by': elena, 'linked_task': task_auth,
                'participant_statuses': {elena: 'accepted'},
            },
            {
                'title': 'Stakeholder Demo - Core Features',
                'description': 'Demo Authentication, Dashboard, and File Upload features to VP of Engineering and Product Lead.',
                'event_type': 'meeting', 'visibility': 'team',
                'start_datetime': _dt(6, 11, 0), 'end_datetime': _dt(6, 12, 0),
                'location': 'Main Conference Room',
                'created_by': priya,
                'participant_statuses': {priya: 'accepted', marcus: 'pending', elena: 'accepted'},
            },
            # Second, more direct tie-in via linked_task on the same File Upload
            # deadline day (day_offset=2).
            {
                'title': 'Focus Block: File Upload Review',
                'description': 'Reserved time to finish the File Upload System DOCX extraction before today’s deadline.',
                'event_type': 'busy_block', 'visibility': 'private',
                'start_datetime': _dt(2, 10, 0), 'end_datetime': _dt(2, 12, 0),
                'created_by': marcus, 'linked_task': task_upload,
                'participant_statuses': {marcus: 'accepted'},
            },
            {
                'title': '1:1: Priya & Marcus',
                'description': 'Weekly 1:1 check-in.',
                'event_type': 'meeting', 'visibility': 'team',
                'start_datetime': _dt(3, 16, 0), 'end_datetime': _dt(3, 16, 30),
                'location': 'Zoom - #1-1',
                'created_by': priya,
                'participant_statuses': {priya: 'accepted', marcus: 'pending'},
            },
            {
                'title': 'All-Hands: Q3 Roadmap Review',
                'description': 'Company-wide review of Q3 roadmap priorities and progress.',
                'event_type': 'team_event', 'visibility': 'public',
                'start_datetime': _dt(9, 11, 0), 'end_datetime': _dt(9, 12, 0),
                'location': 'Main Conference Room',
                'created_by': priya,
                'participant_statuses': {priya: 'accepted', marcus: 'accepted', elena: 'declined'},
            },
        ]

        count = 0
        with transaction.atomic():
            for ev_data in events:
                ev_data = dict(ev_data)
                participant_statuses = ev_data.pop('participant_statuses', {})
                all_day_offset = ev_data.pop('_all_day_offset', None)
                if all_day_offset is not None:
                    ev_data['start_datetime'], ev_data['end_datetime'] = _all_day(all_day_offset)

                ev = CalendarEvent.objects.create(
                    board=board,
                    is_demo=True,
                    **ev_data,
                )
                for user, status in participant_statuses.items():
                    CalendarEventParticipant.objects.create(
                        event=ev, user=user, status=status,
                        responded_at=(now - timedelta(days=1)) if status != 'pending' else None,
                    )
                count += 1

        self.stdout.write(f'   [OK] Created {count} calendar events')
