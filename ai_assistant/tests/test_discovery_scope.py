"""
test_discovery_scope.py — Spectra's Discovery fetchers must respect demo
sandbox isolation.

DiscoveryIdea is workspace-scoped, but the demo workspace is SHARED across all
demo users — per-user isolation is carried by ``sandbox_owner`` (each demo user
gets their own cloned idea set; the canonical templates have
sandbox_owner=None). The Spectra fetchers used to filter by workspace ONLY,
which in demo mode leaked every other demo user's cloned ideas plus the
templates into one user's answer.

These tests pin the fetchers to the same scoping as
kanban.discovery_views._idea_scope:
  • demo mode → only the caller's own clones (sandbox_owner=user)
  • real mode → only non-sandbox ideas (sandbox_owner IS NULL)

Exercises the VDF layer directly (no LLM / network).

Run with:
    python manage.py test ai_assistant.tests.test_discovery_scope
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from accounts.models import Organization, UserProfile
from kanban.models import Workspace
from kanban.discovery_models import DiscoveryIdea
from ai_assistant.utils.spectra_data_fetchers import (
    fetch_discovery_summary,
    fetch_discovery_detail,
)


def _make_idea(org, workspace, title, sandbox_owner):
    return DiscoveryIdea.objects.create(
        organization=org,
        workspace=workspace,
        title=title,
        description='d',
        stage='new',
        is_demo=bool(sandbox_owner) or workspace.is_demo,
        sandbox_owner=sandbox_owner,
    )


class DiscoveryDemoScopeTests(TestCase):
    def setUp(self):
        celery_patcher = patch('celery.app.task.Task.apply_async', return_value=None)
        celery_patcher.start()
        self.addCleanup(celery_patcher.stop)

        self.alice = User.objects.create_user('alice', password='x')
        self.bob = User.objects.create_user('bob', password='x')

        self.org = Organization.objects.create(name='Acme', created_by=self.alice)
        # The shared demo workspace.
        self.demo_ws = Workspace.objects.create(
            name='Demo', organization=self.org, created_by=self.alice, is_demo=True)

        # One canonical template (sandbox_owner=None) + a private clone per user,
        # all under the SAME demo workspace — the exact shape the demo seeder
        # produces via _clone_discovery_ideas_for_user.
        _make_idea(self.org, self.demo_ws, 'Template idea', None)
        _make_idea(self.org, self.demo_ws, "Alice's idea", self.alice)
        _make_idea(self.org, self.demo_ws, "Bob's idea", self.bob)

    def test_summary_demo_scoped_to_caller(self):
        data = fetch_discovery_summary(self.demo_ws, self.alice, is_demo_mode=True)
        # Alice sees ONLY her own clone — not bob's, not the template.
        self.assertEqual(data['total'], 1)

    def test_detail_demo_scoped_to_caller(self):
        data = fetch_discovery_detail(self.demo_ws, self.bob, is_demo_mode=True)
        titles = [r['title'] for r in data['recent']]
        self.assertEqual(titles, ["Bob's idea"])
        self.assertNotIn("Alice's idea", titles)
        self.assertNotIn('Template idea', titles)

    def test_no_cross_user_bleed(self):
        alice = fetch_discovery_summary(self.demo_ws, self.alice, is_demo_mode=True)
        bob = fetch_discovery_summary(self.demo_ws, self.bob, is_demo_mode=True)
        # Each demo user sees exactly one idea (their own), never 3.
        self.assertEqual(alice['total'], 1)
        self.assertEqual(bob['total'], 1)


class DiscoveryRealScopeTests(TestCase):
    def setUp(self):
        celery_patcher = patch('celery.app.task.Task.apply_async', return_value=None)
        celery_patcher.start()
        self.addCleanup(celery_patcher.stop)

        self.alice = User.objects.create_user('alice', password='x')
        self.org = Organization.objects.create(name='Acme', created_by=self.alice)
        self.ws = Workspace.objects.create(
            name='Real', organization=self.org, created_by=self.alice, is_demo=False)
        UserProfile.objects.get_or_create(user=self.alice)

        # A real idea (no sandbox owner) + a stray sandbox copy that must NOT
        # appear in a real-workspace answer.
        _make_idea(self.org, self.ws, 'Real idea', None)
        _make_idea(self.org, self.ws, 'Stray sandbox copy', self.alice)

    def test_real_mode_excludes_sandbox_copies(self):
        data = fetch_discovery_detail(self.ws, self.alice, is_demo_mode=False)
        titles = [r['title'] for r in data['recent']]
        self.assertIn('Real idea', titles)
        self.assertNotIn('Stray sandbox copy', titles)
        self.assertEqual(data['total'], 1)
