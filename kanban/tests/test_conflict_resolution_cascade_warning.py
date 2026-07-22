"""
Regression tests for the conflict-resolution reschedule flow.

Two distinct bugs are locked in here:

1. Applying a "reschedule"/"adjust_dates" ConflictResolution used to compute the
   new start date from a STALE snapshot stored at suggestion time (or from a
   frozen ``new_start_date``). Because the demo date-refresh shifts task dates
   forward but never updates that snapshot, the computed start collapsed to the
   task's *current* start → applying did nothing visible. The fix recomputes
   from the blocking task's LIVE due date via ``after_task_id`` and preserves
   the rescheduled task's duration (see ConflictResolution._reschedule_task).

2. Applying a reschedule only moves the one named task — it never touches tasks
   that depend on it. apply_resolution's JSON response therefore surfaces the
   affected dependents so the frontend can offer the same "Shift N tasks"
   cascade the Gantt drag uses.
"""
import json
from datetime import date, datetime, time

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone


def _aware_due(d):
    return timezone.make_aware(datetime.combine(d, time(23, 59, 59)))


class ConflictResolutionCascadeWarningTest(TestCase):
    def setUp(self):
        from accounts.models import Organization, UserProfile
        from kanban.models import Workspace, Board, Column, Task
        from kanban.conflict_models import ConflictDetection, ConflictResolution

        self.user = User.objects.create_user(
            username='conflict_user', password='pw', email='conflict@example.com',
        )
        org = Organization.objects.create(name='Conflict Org', created_by=self.user)
        ws = Workspace.objects.create(
            name='Conflict WS', organization=org, created_by=self.user, is_demo=False,
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.organization = org
        profile.active_workspace = ws
        profile.save()

        self.board = Board.objects.create(
            name='Conflict Board', created_by=self.user, owner=self.user,
            organization=org, workspace=ws,
        )
        self.col = Column.objects.create(board=self.board, name='Backlog', position=0)

        # Mirrors the demo scenario: File Upload System / User Registration
        # Flow overlap, with two downstream tasks depending on User Reg Flow.
        self.file_upload = Task.objects.create(
            column=self.col, title='File Upload System', created_by=self.user,
            item_type='task', assigned_to=self.user,
            start_date=date(2026, 7, 9), due_date=_aware_due(date(2026, 7, 25)),
        )
        self.user_reg = Task.objects.create(
            column=self.col, title='User Registration Flow', created_by=self.user,
            item_type='task', assigned_to=self.user,
            start_date=date(2026, 7, 10), due_date=_aware_due(date(2026, 7, 27)),
        )
        self.oauth_google = Task.objects.create(
            column=self.col, title='Google OAuth 2.0 Integration', created_by=self.user,
            item_type='task', start_date=date(2026, 7, 21), due_date=_aware_due(date(2026, 7, 28)),
        )
        self.oauth_github = Task.objects.create(
            column=self.col, title='GitHub OAuth 2.0 Integration', created_by=self.user,
            item_type='task', start_date=date(2026, 7, 21), due_date=_aware_due(date(2026, 7, 28)),
        )
        self.oauth_google.dependencies.add(self.user_reg)
        self.oauth_github.dependencies.add(self.user_reg)

        self.conflict = ConflictDetection.objects.create(
            conflict_type='resource', board=self.board,
            title='Resource conflict: overbooked',
            description='Overlapping tasks',
        )
        self.conflict.tasks.add(self.file_upload, self.user_reg)

        # Same shape as the live "reschedule" suggestion: it carries the blocking
        # task (after_task_id) plus a new_start_date that is DELIBERATELY STALE
        # here (2026-07-10 == User Reg Flow's current start, i.e. the no-op value
        # the old snapshot bug produced). Apply must ignore it and recompute from
        # File Upload System's LIVE due date (2026-07-25) → start 2026-07-26.
        self.resolution = ConflictResolution.objects.create(
            conflict=self.conflict,
            resolution_type='reschedule',
            title="Reschedule 'User Registration Flow' to start after first task",
            description="Delay start of 'User Registration Flow' until 'File Upload System' is complete.",
            ai_confidence=93,
            auto_applicable=True,
            implementation_data={
                'task_id': self.user_reg.id,
                'after_task_id': self.file_upload.id,
                'new_start_date': str(date(2026, 7, 10)),  # stale no-op value
            },
        )

        self.client = Client()
        self.client.force_login(self.user)

    def test_apply_reschedule_recomputes_from_live_due_and_preserves_duration(self):
        """Applying recomputes the new start from File Upload System's LIVE due
        date (ignoring the stale new_start_date) and preserves User Reg Flow's
        duration; the response still flags the two OAuth dependents."""
        from kanban.models import Task

        url = reverse('apply_resolution', args=[self.conflict.id, self.resolution.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertTrue(data['success'])

        # Recomputed from live blocking due (07-25) + 1 = 07-26, NOT the stale
        # 07-10, and the 17-day duration is preserved (07-26 .. 08-12).
        user_reg = Task.objects.get(id=self.user_reg.id)
        self.assertEqual(user_reg.start_date, date(2026, 7, 26))
        self.assertEqual(user_reg.due_date.date(), date(2026, 8, 12))

        # Dependents are NOT auto-shifted (still start 07-21, before the new
        # 08-12 due date) — surfaced so the frontend can offer the cascade.
        google = Task.objects.get(id=self.oauth_google.id)
        github = Task.objects.get(id=self.oauth_github.id)
        self.assertEqual(google.start_date, date(2026, 7, 21))
        self.assertEqual(github.start_date, date(2026, 7, 21))

        self.assertIn('affected_dependents', data)
        titles = {d['title'] for d in data['affected_dependents']}
        self.assertEqual(titles, {'Google OAuth 2.0 Integration', 'GitHub OAuth 2.0 Integration'})
        self.assertEqual(data['total_dependents'], 2)
        self.assertEqual(data['rescheduled_task']['id'], self.user_reg.id)
        self.assertEqual(data['rescheduled_task']['start_date'], '2026-07-26')
        self.assertEqual(data['rescheduled_task']['due_date'], '2026-08-12')

    def test_cascade_endpoint_then_actually_moves_the_flagged_dependents(self):
        """End-to-end: apply the resolution, then invoke the same
        cascade-reschedule endpoint the Gantt "Shift N tasks" banner uses,
        and confirm the flagged dependents move to after the new due date."""
        from kanban.models import Task

        apply_url = reverse('apply_resolution', args=[self.conflict.id, self.resolution.id])
        apply_resp = self.client.post(apply_url)
        data = apply_resp.json()
        self.assertTrue(len(data['affected_dependents']) > 0)

        cascade_url = reverse('cascade_reschedule_task_api', args=[self.user_reg.id])
        cascade_resp = self.client.post(
            cascade_url,
            data=json.dumps({
                'start_date': data['rescheduled_task']['start_date'],
                'due_date': data['rescheduled_task']['due_date'],
            }),
            content_type='application/json',
        )
        self.assertEqual(cascade_resp.status_code, 200, cascade_resp.content)
        moved = {m['title'] for m in cascade_resp.json().get('updated', [])}
        self.assertEqual(moved, {'Google OAuth 2.0 Integration', 'GitHub OAuth 2.0 Integration'})

        # Cascade moves each dependent to no earlier than its predecessor's new
        # due date (08-12).
        google = Task.objects.get(id=self.oauth_google.id)
        self.assertEqual(google.start_date, date(2026, 8, 12))

    def test_apply_reschedule_without_after_task_falls_back_to_stored_start(self):
        """When a (legacy) resolution has no after_task_id, apply still works by
        falling back to the stored new_start_date, and preserves duration."""
        from kanban.models import Task
        from kanban.conflict_models import ConflictResolution

        legacy = ConflictResolution.objects.create(
            conflict=self.conflict,
            resolution_type='reschedule',
            title="Legacy reschedule",
            description="No after_task_id",
            ai_confidence=80,
            auto_applicable=True,
            implementation_data={
                'task_id': self.user_reg.id,
                'new_start_date': str(date(2026, 8, 1)),
            },
        )
        url = reverse('apply_resolution', args=[self.conflict.id, legacy.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200, resp.content)

        user_reg = Task.objects.get(id=self.user_reg.id)
        self.assertEqual(user_reg.start_date, date(2026, 8, 1))
        # 17-day duration preserved: 08-01 .. 08-18.
        self.assertEqual(user_reg.due_date.date(), date(2026, 8, 18))

    def test_legacy_resolution_derives_blocking_task_from_conflict_data(self):
        """The exact demo failure: a cloned/legacy reschedule resolution that
        has NO after_task_id and a stale new_start_date (07-10, i.e. a near-total
        overlap). Apply must derive the blocking task from the conflict's task
        pair and recompute from its LIVE due date so the overlap is actually
        cleared — not nudge the start by a stale one-day delta."""
        from kanban.models import Task
        from kanban.conflict_models import ConflictDetection, ConflictResolution

        conflict = ConflictDetection.objects.create(
            conflict_type='resource', board=self.board,
            title='Resource conflict: overbooked (legacy shape)',
            description='Overlapping tasks',
            # Snapshot is deliberately stale (07-09), like real demo data after
            # the daily date-refresh drift.
            conflict_data={
                'task1_id': self.file_upload.id,
                'task1_dates': {'due': '2026-07-09 06:30:00+00:00'},
                'task2_id': self.user_reg.id,
            },
        )
        legacy = ConflictResolution.objects.create(
            conflict=conflict,
            resolution_type='reschedule',
            title="Reschedule 'User Registration Flow' to start after first task",
            description="Delay start until File Upload System is complete.",
            ai_confidence=93,
            auto_applicable=True,
            implementation_data={
                'task_id': self.user_reg.id,
                'new_start_date': '2026-07-10',  # stale no-op value, NO after_task_id
            },
        )
        url = reverse('apply_resolution', args=[conflict.id, legacy.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200, resp.content)

        user_reg = Task.objects.get(id=self.user_reg.id)
        # Derived blocking = File Upload System (live due 07-25) + 1 = 07-26,
        # NOT the stale 07-10; 17-day duration preserved → 08-12.
        self.assertEqual(user_reg.start_date, date(2026, 7, 26))
        self.assertEqual(user_reg.due_date.date(), date(2026, 8, 12))
        # Overlap actually cleared: starts after File Upload System finishes.
        self.assertGreater(user_reg.start_date, self.file_upload.due_date.date())


class DependencyConflictAutoApplyTest(TestCase):
    """The dependency-conflict suggestion "Reschedule to after blocking tasks"
    used to be created with auto_applicable=False and empty implementation_data,
    so applying it silently did nothing. It must now be auto-applicable (when a
    dated blocking dependency exists) and actually move the task."""

    def setUp(self):
        from accounts.models import Organization, UserProfile
        from kanban.models import Workspace, Board, Column, Task
        from kanban.conflict_models import ConflictDetection

        self.user = User.objects.create_user(
            username='dep_user', password='pw', email='dep@example.com',
        )
        org = Organization.objects.create(name='Dep Org', created_by=self.user)
        ws = Workspace.objects.create(
            name='Dep WS', organization=org, created_by=self.user, is_demo=False,
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.organization = org
        profile.active_workspace = ws
        profile.save()

        self.board = Board.objects.create(
            name='Dep Board', created_by=self.user, owner=self.user,
            organization=org, workspace=ws,
        )
        self.col = Column.objects.create(board=self.board, name='Backlog', position=0)

        self.blocker = Task.objects.create(
            column=self.col, title='Backend API', created_by=self.user,
            item_type='task', start_date=date(2026, 7, 1), due_date=_aware_due(date(2026, 7, 20)),
        )
        self.blocked = Task.objects.create(
            column=self.col, title='Frontend Integration', created_by=self.user,
            item_type='task', start_date=date(2026, 7, 5), due_date=_aware_due(date(2026, 7, 15)),
        )
        self.blocked.dependencies.add(self.blocker)

        self.conflict = ConflictDetection.objects.create(
            conflict_type='dependency', board=self.board,
            title='Dependency conflict',
            description='Blocked task starts before blocker finishes',
            conflict_data={'task_id': self.blocked.id},
        )
        self.conflict.tasks.add(self.blocked)

        self.client = Client()
        self.client.force_login(self.user)

    def test_dependency_reschedule_is_auto_applicable_and_moves_task(self):
        from kanban.models import Task
        from kanban.utils.conflict_detection import ConflictResolutionSuggester

        suggester = ConflictResolutionSuggester(self.conflict)
        suggester.generate_suggestions()

        reschedule = self.conflict.resolutions.filter(
            resolution_type='adjust_dates',
            title__icontains='blocking',
        ).first()
        self.assertIsNotNone(reschedule)
        self.assertTrue(reschedule.auto_applicable)
        self.assertEqual(reschedule.implementation_data.get('after_task_id'), self.blocker.id)

        url = reverse('apply_resolution', args=[self.conflict.id, reschedule.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200, resp.content)

        blocked = Task.objects.get(id=self.blocked.id)
        # Recomputed from blocker's live due (07-20) + 1 = 07-21, duration
        # (10 days) preserved → 07-31.
        self.assertEqual(blocked.start_date, date(2026, 7, 21))
        self.assertEqual(blocked.due_date.date(), date(2026, 7, 31))
