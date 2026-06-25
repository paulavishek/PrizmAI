"""
test_board_scope.py — Lock Spectra's board scope to the dashboard's source of truth.

Spectra's greeting ("I have analyzed your N active boards…") and its data context
both come from ``get_accessible_boards_for_spectra``. That helper used to build its
own query (creator / owner / any membership, across every workspace), which drifted
from the dashboard's canonical ``get_user_boards`` and over-counted — e.g. a board the
user owns in a *non-active* workspace was counted by Spectra but not the dashboard.

These tests pin the two helpers together in real (non-demo) mode.

Run with:
    python manage.py test ai_assistant.tests.test_board_scope
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from accounts.models import Organization, UserProfile
from kanban.models import Board, BoardMembership, Workspace
from kanban.utils.demo_protection import get_user_boards
from ai_assistant.utils.rbac_utils import get_accessible_boards_for_spectra


class SpectraBoardScopeTests(TestCase):
    def setUp(self):
        # Board/membership save signals queue Celery jobs; there's no broker in the
        # test env, so neutralize dispatch (mirrors test_spectra_accuracy setup).
        celery_patcher = patch('celery.app.task.Task.apply_async', return_value=None)
        celery_patcher.start()
        self.addCleanup(celery_patcher.stop)

        self.alice = User.objects.create_user('alice', password='x')
        self.bob = User.objects.create_user('bob', password='x')

        org = Organization.objects.create(name='Acme', created_by=self.alice)
        self.active_ws = Workspace.objects.create(
            name='Active', organization=org, created_by=self.alice)
        self.other_ws = Workspace.objects.create(
            name='Other', organization=org, created_by=self.alice)

        profile, _ = UserProfile.objects.get_or_create(user=self.alice)
        profile.active_workspace = self.active_ws
        profile.is_viewing_demo = False
        profile.save(update_fields=['active_workspace', 'is_viewing_demo'])

        # Owned board in the active workspace → in scope.
        self.owned_active = Board.objects.create(
            name='Owned (active ws)', created_by=self.alice, workspace=self.active_ws)
        BoardMembership.objects.get_or_create(
            board=self.owned_active, user=self.alice, defaults={'role': 'owner'})

        # Owned board in a *non-active* workspace → out of scope (this is the board
        # the old Spectra query over-counted vs. the dashboard).
        self.owned_other = Board.objects.create(
            name='Owned (other ws)', created_by=self.alice, workspace=self.other_ws)
        BoardMembership.objects.get_or_create(
            board=self.owned_other, user=self.alice, defaults={'role': 'owner'})

        # Board owned by bob, shared *to* alice as a member → in scope (shared).
        self.shared = Board.objects.create(
            name="Bob's board", created_by=self.bob, workspace=self.other_ws)
        BoardMembership.objects.get_or_create(
            board=self.shared, user=self.bob, defaults={'role': 'owner'})
        BoardMembership.objects.get_or_create(
            board=self.shared, user=self.alice, defaults={'role': 'member'})

    def test_spectra_scope_matches_dashboard(self):
        spectra = set(get_accessible_boards_for_spectra(self.alice).values_list('id', flat=True))
        dashboard = set(get_user_boards(self.alice).values_list('id', flat=True))
        self.assertEqual(spectra, dashboard)

    def test_includes_active_and_shared_excludes_non_active_owned(self):
        ids = set(get_accessible_boards_for_spectra(self.alice).values_list('id', flat=True))
        self.assertIn(self.owned_active.id, ids)   # owned in active ws
        self.assertIn(self.shared.id, ids)         # shared to alice as member
        self.assertNotIn(self.owned_other.id, ids)  # owned in a non-active ws → excluded
        self.assertEqual(len(ids), 2)
