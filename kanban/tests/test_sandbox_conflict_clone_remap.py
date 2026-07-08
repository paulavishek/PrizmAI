"""
Regression test: cloning a sandbox must remap the task PKs embedded inside
ConflictDetection.conflict_data / ConflictResolution.implementation_data.

Bug: _duplicate_board correctly remaps the M2M fields (ConflictDetection.tasks,
Task.dependencies, ...) via `task_map`, but it copied conflict_data and
implementation_data verbatim. Those JSONFields embed raw task PKs (task_id,
task1_id, task2_id) captured against the TEMPLATE board's tasks. Left
unremapped, applying a cloned "reschedule"/"reassign" resolution in a user's
sandbox silently reads/writes the SHARED TEMPLATE BOARD's task instead of the
sandbox owner's own copy — the Kanban/Gantt views the user is looking at never
change, because the wrong (template) task was mutated.
"""
from datetime import date, datetime, time

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from accounts.models import Organization, UserProfile
from kanban.models import Board, Column, Task, Workspace
from kanban.conflict_models import ConflictDetection, ConflictResolution
from kanban.sandbox_views import _duplicate_board


def _aware_due(d):
    return timezone.make_aware(datetime.combine(d, time(23, 59, 59)))


class SandboxConflictCloneRemapTest(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user('demo_creator2', password='x')
        org = Organization.objects.create(name='Demo Org 2', is_demo=True, created_by=self.creator)
        ws = Workspace.objects.create(
            name='Demo WS 2', organization=org, is_demo=True, is_active=True, created_by=self.creator,
        )
        self.template_board = Board.objects.create(
            name='Software Development', organization=org, workspace=ws,
            is_official_demo_board=True, is_seed_demo_data=True, created_by=self.creator,
        )
        col = Column.objects.create(board=self.template_board, name='Backlog', position=0)

        self.tmpl_file_upload = Task.objects.create(
            column=col, title='File Upload System', created_by=self.creator,
            item_type='task', start_date=date(2026, 7, 10), due_date=_aware_due(date(2026, 7, 26)),
        )
        self.tmpl_user_reg = Task.objects.create(
            column=col, title='User Registration Flow', created_by=self.creator,
            item_type='task', start_date=date(2026, 7, 14), due_date=_aware_due(date(2026, 7, 28)),
        )

        conflict = ConflictDetection.objects.create(
            conflict_type='resource', board=self.template_board,
            title='Resource conflict: overbooked', description='Overlapping tasks',
            conflict_data={
                'user_id': self.creator.id,
                'task1_id': self.tmpl_file_upload.id,
                'task2_id': self.tmpl_user_reg.id,
            },
        )
        conflict.tasks.add(self.tmpl_file_upload, self.tmpl_user_reg)

        ConflictResolution.objects.create(
            conflict=conflict, resolution_type='reschedule',
            title="Reschedule 'User Registration Flow' to start after first task",
            description='...', auto_applicable=True,
            implementation_data={
                'task_id': self.tmpl_user_reg.id,
                'new_start_date': '2026-07-27',
            },
        )

        self.user = User.objects.create_user('sandbox_user', password='pw')
        profile, _ = UserProfile.objects.get_or_create(user=self.user)

    def test_cloned_conflict_and_resolution_reference_sandbox_tasks(self):
        new_board = _duplicate_board(self.template_board, self.user)

        sandbox_user_reg = Task.objects.get(column__board=new_board, title='User Registration Flow')
        sandbox_file_upload = Task.objects.get(column__board=new_board, title='File Upload System')

        cloned_conflict = ConflictDetection.objects.get(board=new_board)
        self.assertEqual(cloned_conflict.conflict_data['task1_id'], sandbox_file_upload.id)
        self.assertEqual(cloned_conflict.conflict_data['task2_id'], sandbox_user_reg.id)
        # Must NOT still point at the template board's tasks.
        self.assertNotEqual(cloned_conflict.conflict_data['task1_id'], self.tmpl_file_upload.id)
        self.assertNotEqual(cloned_conflict.conflict_data['task2_id'], self.tmpl_user_reg.id)

        cloned_resolution = ConflictResolution.objects.get(conflict=cloned_conflict)
        self.assertEqual(cloned_resolution.implementation_data['task_id'], sandbox_user_reg.id)
        self.assertNotEqual(cloned_resolution.implementation_data['task_id'], self.tmpl_user_reg.id)

    def test_apply_after_clone_mutates_the_sandbox_task_not_the_template(self):
        new_board = _duplicate_board(self.template_board, self.user)
        sandbox_user_reg = Task.objects.get(column__board=new_board, title='User Registration Flow')

        cloned_conflict = ConflictDetection.objects.get(board=new_board)
        cloned_resolution = ConflictResolution.objects.get(conflict=cloned_conflict)
        cloned_resolution.apply(self.user)

        sandbox_user_reg.refresh_from_db()
        self.assertEqual(sandbox_user_reg.start_date, date(2026, 7, 27))

        # The template board's own task must be untouched.
        self.tmpl_user_reg.refresh_from_db()
        self.assertEqual(self.tmpl_user_reg.start_date, date(2026, 7, 14))
