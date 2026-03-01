"""
Tests for Onboarding v2 â€” AI-powered workspace setup
=====================================================

Coverage:
- Models: OnboardingWorkspacePreview lifecycle
- Views: all 9 onboarding views + toggle_demo_mode
- Backward compatibility: v1 users are never affected
- Edge cases: missing preview, already committed, Celery fallback
- Commit logic: JSON â†’ real DB objects
"""

from unittest.mock import patch, MagicMock
import json

from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse

from accounts.models import Organization, UserProfile
from kanban.onboarding_models import OnboardingWorkspacePreview
from kanban.models import OrganizationGoal, Mission, Strategy, Board, Column, Task


# ---------------------------------------------------------------------------
# Sample generated data fixture
# ---------------------------------------------------------------------------
SAMPLE_WORKSPACE = {
    "goal": {
        "name": "Launch an AI-powered customer support platform",
        "description": "Build and ship a real-time AI chat support system.",
        "target_metric": "50% ticket deflection within 6 months",
        "target_date": "2026-09-01",
    },
    "missions": [
        {
            "name": "Build Core Chat Engine",
            "description": "Develop the real-time messaging infrastructure.",
            "strategies": [
                {
                    "name": "Real-time messaging infrastructure",
                    "description": "WebSocket-based messaging pipeline.",
                    "boards": [
                        {
                            "name": "Chat Backend",
                            "description": "Backend implementation for chat.",
                            "columns": ["Backlog", "In Progress", "Review", "Done"],
                            "tasks": [
                                {
                                    "title": "Set up WebSocket server",
                                    "description": "Implement WS endpoint for real-time messaging",
                                    "priority": "high",
                                    "item_type": "task",
                                },
                                {
                                    "title": "Design message schema",
                                    "description": "Define JSON schema for chat messages",
                                    "priority": "medium",
                                    "item_type": "task",
                                },
                            ],
                        }
                    ],
                }
            ],
        },
        {
            "name": "AI Integration Layer",
            "description": "Add NLP and AI to support flow.",
            "strategies": [
                {
                    "name": "NLP pipeline for ticket classification",
                    "description": "Classify incoming support tickets.",
                    "boards": [
                        {
                            "name": "AI Pipeline",
                            "description": "AI model training and deployment.",
                            "columns": ["To Do", "Doing", "Done"],
                            "tasks": [
                                {
                                    "title": "Train intent classifier",
                                    "description": "Fine-tune model on support ticket data",
                                    "priority": "high",
                                    "item_type": "task",
                                },
                            ],
                        }
                    ],
                }
            ],
        },
    ],
}


def _make_v2_user(username="v2user", status="pending"):
    """Helper: create a user with v2 onboarding profile."""
    user = User.objects.create_user(username=username, password="pass1234")
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={
            "onboarding_version": 2,
            "onboarding_status": status,
            "has_seen_welcome": True,
            "completed_wizard": True,
        },
    )
    if profile.onboarding_version != 2:
        profile.onboarding_version = 2
        profile.onboarding_status = status
        profile.save()
    return user, profile


def _make_v1_user(username="v1user"):
    """Helper: create a user with v1 (legacy) profile."""
    user = User.objects.create_user(username=username, password="pass1234")
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={
            "onboarding_version": 1,
            "onboarding_status": "completed",
            "has_seen_welcome": True,
            "completed_wizard": True,
        },
    )
    return user, profile


# ===================================================================
# Model tests
# ===================================================================

class OnboardingWorkspacePreviewModelTests(TestCase):
    """Test the OnboardingWorkspacePreview model."""

    def test_create_preview(self):
        user, _ = _make_v2_user()
        preview = OnboardingWorkspacePreview.objects.create(
            user=user,
            goal_text="Build AI support platform",
            generated_data=SAMPLE_WORKSPACE,
            status="ready",
        )
        self.assertEqual(preview.status, "ready")
        self.assertEqual(preview.generated_data["goal"], SAMPLE_WORKSPACE["goal"])
        self.assertIsNone(preview.edited_data)

    def test_one_preview_per_user(self):
        user, _ = _make_v2_user()
        OnboardingWorkspacePreview.objects.create(
            user=user, goal_text="First", generated_data={}, status="ready"
        )
        with self.assertRaises(Exception):
            OnboardingWorkspacePreview.objects.create(
                user=user, goal_text="Second", generated_data={}, status="ready"
            )


# ===================================================================
# View tests â€” Welcome
# ===================================================================

class OnboardingWelcomeViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_welcome_page_renders_for_v2_pending(self):
        user, _ = _make_v2_user(status="pending")
        self.client.force_login(user)
        resp = self.client.get(reverse("onboarding_welcome"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Set up my workspace")

    def test_welcome_redirects_anon(self):
        resp = self.client.get(reverse("onboarding_welcome"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)


# ===================================================================
# View tests â€” Goal Input
# ===================================================================

class OnboardingGoalInputViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user, self.profile = _make_v2_user(status="pending")
        self.client.force_login(self.user)

    def test_get_goal_page(self):
        resp = self.client.get(reverse("onboarding_goal"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "organization")  # contains goal input form

    def test_post_too_short_goal(self):
        resp = self.client.post(
            reverse("onboarding_goal"),
            {"goal_text": "Short"},
        )
        self.assertEqual(resp.status_code, 200)  # re-renders form
        self.assertContains(resp, "Please enter at least 30 characters")

    @patch("kanban.tasks.onboarding_tasks.generate_workspace_from_goal_task")
    def test_post_valid_goal_dispatches_task(self, mock_task):
        mock_task.delay.return_value = MagicMock(id="fake-celery-id")
        goal = "Launch an AI-powered customer support platform with real-time chat"
        resp = self.client.post(reverse("onboarding_goal"), {"goal_text": goal})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("generating", resp.url)
        # Profile should be updated
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.onboarding_status, "goal_submitted")
        self.assertEqual(self.profile.onboarding_goal_text, goal)

    def test_v1_user_redirected(self):
        v1_user, _ = _make_v1_user(username="legacy")
        self.client.force_login(v1_user)
        resp = self.client.post(
            reverse("onboarding_goal"),
            {"goal_text": "This is long enough to be thirty characters at least yeah"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn("dashboard", resp.url)


# ===================================================================
# View tests â€” Status polling
# ===================================================================

class OnboardingStatusViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user, _ = _make_v2_user(status="goal_submitted")
        self.client.force_login(self.user)

    def test_status_no_preview(self):
        resp = self.client.get(reverse("onboarding_status"))
        data = json.loads(resp.content)
        self.assertEqual(data["status"], "failed")

    def test_status_generating(self):
        OnboardingWorkspacePreview.objects.create(
            user=self.user, goal_text="Test", generated_data={}, status="generating"
        )
        resp = self.client.get(reverse("onboarding_status"))
        data = json.loads(resp.content)
        self.assertEqual(data["status"], "generating")

    def test_status_ready(self):
        OnboardingWorkspacePreview.objects.create(
            user=self.user,
            goal_text="Test",
            generated_data=SAMPLE_WORKSPACE,
            status="ready",
        )
        resp = self.client.get(reverse("onboarding_status"))
        data = json.loads(resp.content)
        self.assertEqual(data["status"], "ready")


# ===================================================================
# View tests â€” Review
# ===================================================================

class OnboardingReviewViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user, self.profile = _make_v2_user(status="workspace_generated")
        self.client.force_login(self.user)

    def test_review_shows_data(self):
        OnboardingWorkspacePreview.objects.create(
            user=self.user,
            goal_text="AI platform",
            generated_data=SAMPLE_WORKSPACE,
            status="ready",
        )
        resp = self.client.get(reverse("onboarding_review"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Build Core Chat Engine")

    def test_review_missing_preview_redirects(self):
        resp = self.client.get(reverse("onboarding_review"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("goal", resp.url)

    def test_review_generating_redirects(self):
        OnboardingWorkspacePreview.objects.create(
            user=self.user,
            goal_text="AI platform",
            generated_data={},
            status="generating",
        )
        resp = self.client.get(reverse("onboarding_review"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("generating", resp.url)


# ===================================================================
# View tests â€” Commit
# ===================================================================

class OnboardingCommitViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user, self.profile = _make_v2_user(status="workspace_generated")
        self.client.force_login(self.user)
        self.preview = OnboardingWorkspacePreview.objects.create(
            user=self.user,
            goal_text="AI platform",
            generated_data=SAMPLE_WORKSPACE,
            status="ready",
        )

    def test_commit_creates_objects(self):
        resp = self.client.post(reverse("onboarding_commit"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("dashboard", resp.url)

        # Verify DB objects created
        self.assertEqual(OrganizationGoal.objects.filter(created_by=self.user).count(), 1)
        goal = OrganizationGoal.objects.get(created_by=self.user)
        self.assertEqual(goal.name, SAMPLE_WORKSPACE["goal"]["name"])

        self.assertEqual(Mission.objects.filter(created_by=self.user).count(), 2)
        self.assertEqual(Strategy.objects.filter(created_by=self.user).count(), 2)
        self.assertEqual(Board.objects.filter(created_by=self.user).count(), 2)
        self.assertEqual(Task.objects.filter(created_by=self.user).count(), 3)

        # Verify profile updated
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.onboarding_status, "completed")

        # Verify preview marked committed
        self.preview.refresh_from_db()
        self.assertEqual(self.preview.status, "committed")

    def test_commit_with_edits(self):
        edited = json.loads(json.dumps(SAMPLE_WORKSPACE))
        edited["goal"]["name"] = "EDITED GOAL TEXT"
        resp = self.client.post(
            reverse("onboarding_commit"),
            {"edited_data": json.dumps(edited)},
        )
        self.assertEqual(resp.status_code, 302)
        goal = OrganizationGoal.objects.get(created_by=self.user)
        self.assertEqual(goal.name, "EDITED GOAL TEXT")

    def test_commit_already_committed_redirects(self):
        self.preview.status = "committed"
        self.preview.save()
        resp = self.client.post(reverse("onboarding_commit"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("dashboard", resp.url)

    def test_commit_get_not_allowed(self):
        resp = self.client.get(reverse("onboarding_commit"))
        self.assertEqual(resp.status_code, 405)


# ===================================================================
# View tests â€” Skip
# ===================================================================

class OnboardingSkipViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user, self.profile = _make_v2_user(status="pending")
        self.client.force_login(self.user)

    def test_skip_sets_status(self):
        resp = self.client.post(reverse("onboarding_skip"))
        self.assertEqual(resp.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.onboarding_status, "skipped")

    def test_skip_v1_redirects(self):
        v1_user, _ = _make_v1_user(username="legacy2")
        self.client.force_login(v1_user)
        resp = self.client.post(reverse("onboarding_skip"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("dashboard", resp.url)


# ===================================================================
# View tests â€” Explore Demo
# ===================================================================

class OnboardingExploreDemoViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user, self.profile = _make_v2_user(status="pending")
        self.client.force_login(self.user)

    def test_explore_demo_sets_flags(self):
        resp = self.client.post(reverse("onboarding_explore_demo"))
        self.assertEqual(resp.status_code, 302)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_viewing_demo)
        self.assertEqual(self.profile.onboarding_status, "demo_exploring")


# ===================================================================
# View tests â€” Start Over
# ===================================================================

class OnboardingStartOverViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user, self.profile = _make_v2_user(status="workspace_generated")
        self.client.force_login(self.user)
        OnboardingWorkspacePreview.objects.create(
            user=self.user,
            goal_text="Previous goal text",
            generated_data=SAMPLE_WORKSPACE,
            status="ready",
        )

    def test_start_over_deletes_preview(self):
        resp = self.client.post(reverse("onboarding_start_over"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("goal", resp.url)
        self.assertEqual(
            OnboardingWorkspacePreview.objects.filter(user=self.user).count(), 0
        )


# ===================================================================
# View tests â€” Toggle Demo Mode
# ===================================================================

class ToggleDemoModeViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user, self.profile = _make_v2_user(status="completed")
        self.client.force_login(self.user)

    def test_toggle_on(self):
        self.assertFalse(self.profile.is_viewing_demo)
        resp = self.client.post(reverse("toggle_demo_mode"))
        self.assertEqual(resp.status_code, 302)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_viewing_demo)

    def test_toggle_off(self):
        self.profile.is_viewing_demo = True
        self.profile.save()
        resp = self.client.post(reverse("toggle_demo_mode"))
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.is_viewing_demo)


# ===================================================================
# Dashboard redirect guard tests
# ===================================================================

class DashboardOnboardingGuardTests(TestCase):
    """Verify the dashboard redirects v2 users who haven't finished onboarding."""

    def setUp(self):
        self.client = Client()

    def test_v2_pending_redirects_to_welcome(self):
        user, _ = _make_v2_user(status="pending")
        self.client.force_login(user)
        resp = self.client.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("onboarding", resp.url)

    def test_v2_goal_submitted_redirects_to_generating(self):
        user, _ = _make_v2_user(username="gs", status="goal_submitted")
        self.client.force_login(user)
        resp = self.client.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("generating", resp.url)

    def test_v2_workspace_generated_redirects_to_review(self):
        user, _ = _make_v2_user(username="wg", status="workspace_generated")
        self.client.force_login(user)
        resp = self.client.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("review", resp.url)

    def test_v2_completed_shows_dashboard(self):
        user, _ = _make_v2_user(username="done", status="completed")
        self.client.force_login(user)
        resp = self.client.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 200)

    def test_v2_skipped_shows_dashboard(self):
        user, _ = _make_v2_user(username="skip", status="skipped")
        self.client.force_login(user)
        resp = self.client.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 200)

    def test_v2_demo_exploring_shows_dashboard(self):
        user, profile = _make_v2_user(username="demo", status="demo_exploring")
        profile.is_viewing_demo = True
        profile.save()
        self.client.force_login(user)
        resp = self.client.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 200)

    def test_v1_user_never_redirected(self):
        user, _ = _make_v1_user()
        self.client.force_login(user)
        resp = self.client.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 200)


# ===================================================================
# Commit utility tests
# ===================================================================

class CommitOnboardingWorkspaceTests(TestCase):
    """Test the commit_onboarding_workspace function directly."""

    def test_priority_mapping(self):
        """'critical' in AI output maps to 'urgent' in the DB."""
        from kanban.onboarding_utils import commit_onboarding_workspace

        user, profile = _make_v2_user(username="prio", status="workspace_generated")
        data = {
            "goal": {"name": "Priority test", "description": "Test", "target_metric": "", "target_date": ""},
            "missions": [
                {
                    "name": "M1",
                    "strategies": [
                        {
                            "name": "S1",
                            "boards": [
                                {
                                    "name": "B1",
                                    "columns": ["To Do", "Done"],
                                    "tasks": [
                                        {
                                            "title": "Critical task",
                                            "description": "Desc",
                                            "priority": "critical",
                                            "item_type": "bug",
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        preview = OnboardingWorkspacePreview.objects.create(
            user=user, goal_text="Priority test", generated_data=data, status="ready"
        )
        commit_onboarding_workspace(user, preview)
        task = Task.objects.get(created_by=user)
        self.assertEqual(task.priority, "urgent")
        self.assertEqual(task.item_type, "task")  # bug â†’ task

    def test_columns_created_in_order(self):
        from kanban.onboarding_utils import commit_onboarding_workspace

        user, _ = _make_v2_user(username="cols", status="workspace_generated")
        data = {
            "goal": {"name": "Column order test", "description": "Test", "target_metric": "", "target_date": ""},
            "missions": [
                {
                    "name": "M1",
                    "strategies": [
                        {
                            "name": "S1",
                            "boards": [
                                {
                                    "name": "B1",
                                    "columns": ["Backlog", "In Progress", "Review", "Done"],
                                    "tasks": [],
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        preview = OnboardingWorkspacePreview.objects.create(
            user=user, goal_text="Test", generated_data=data, status="ready"
        )
        commit_onboarding_workspace(user, preview)
        board = Board.objects.get(created_by=user)
        cols = list(board.columns.order_by("position").values_list("name", flat=True))
        # "To Do" is prepended when not already the first column
        self.assertEqual(cols, ["To Do", "Backlog", "In Progress", "Review", "Done"])


# ===================================================================
# AI generation tests (mocked)
# ===================================================================

class AIWorkspaceGenerationTests(TestCase):
    """Test generate_workspace_from_goal with mocked Gemini."""

    @patch("kanban.utils.ai_utils.generate_ai_content")
    def test_valid_json_response(self, mock_ai):
        from kanban.utils.ai_utils import generate_workspace_from_goal

        mock_ai.return_value = json.dumps(SAMPLE_WORKSPACE)
        result = generate_workspace_from_goal("Build AI support platform")
        self.assertIn("goal", result)
        self.assertIn("missions", result)
        self.assertEqual(len(result["missions"]), 2)

    @patch("kanban.utils.ai_utils.generate_ai_content")
    def test_fallback_on_bad_json(self, mock_ai):
        from kanban.utils.ai_utils import generate_workspace_from_goal

        mock_ai.return_value = "THIS IS NOT JSON AT ALL"
        result = generate_workspace_from_goal("Build AI support platform")
        # generate_workspace_from_goal returns None on failure
        # (the Celery task is responsible for calling get_fallback_workspace)
        self.assertIsNone(result)

    def test_get_fallback_workspace(self):
        from kanban.utils.ai_utils import get_fallback_workspace

        result = get_fallback_workspace("My org goal text here")
        self.assertEqual(result["goal"]["name"], "My org goal text here")
        self.assertTrue(len(result["missions"]) >= 2)
        for mission in result["missions"]:
            self.assertIn("strategies", mission)
            for strat in mission["strategies"]:
                self.assertIn("boards", strat)
                for board in strat["boards"]:
                    self.assertIn("columns", board)
                    self.assertIn("tasks", board)
