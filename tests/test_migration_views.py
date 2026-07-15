"""
test_migration_views.py — HTTP flow for the live-migration onboarding wizard.

Connector HTTP and the Celery enqueue are mocked; this verifies the view layer:
credential save + encryption, project listing, task enqueue, progress polling,
and cross-user ownership scoping.

Run with:
    pytest tests/test_migration_views.py
"""

from unittest.mock import MagicMock, patch

from cryptography.fernet import Fernet
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

_TEST_FERNET_KEY = Fernet.generate_key().decode()


@override_settings(AI_KEY_ENCRYPTION_KEY=_TEST_FERNET_KEY)
class TestMigrationViews(TestCase):

    def setUp(self):
        from accounts.models import Organization, UserProfile
        from kanban.models import Workspace
        self.user = User.objects.create_user("owner", "owner@acme.com", "pw")
        self.org = Organization.objects.create(name="Acme", created_by=self.user)
        self.ws = Workspace.objects.create(name="Acme WS", organization=self.org, created_by=self.user)
        p, _ = UserProfile.objects.get_or_create(user=self.user)
        p.organization = self.org
        p.active_workspace = self.ws
        p.save()
        self.client.force_login(self.user)

    def test_start_page_renders(self):
        resp = self.client.get(reverse("integrations:migrate_start"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Migrate a project into PrizmAI")

    @patch("kanban.utils.connectors.ConnectorFactory.get_connector")
    def test_connect_saves_encrypted_and_lists_projects(self, mock_get):
        from integrations.models import SourceConnection

        fake = MagicMock()
        fake.test_connection.return_value = {"account": "owner@acme.com"}
        fake.list_projects.return_value = [{"id": "KAN", "name": "Kanban"}]
        mock_get.return_value = fake

        resp = self.client.post(reverse("integrations:migrate_connect"), {
            "provider": "jira",
            "base_url": "https://acme.atlassian.net",
            "account_email": "owner@acme.com",
            "api_token": "secret-token-1234",
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["projects"], [{"id": "KAN", "name": "Kanban"}])

        conn = SourceConnection.objects.get(id=data["connection_id"])
        self.assertEqual(conn.workspace_id, self.ws.id)
        self.assertEqual(conn.created_by_id, self.user.id)
        # Token stored encrypted, retrievable, last-4 recorded.
        self.assertNotIn("secret-token-1234", conn.encrypted_api_token)
        self.assertEqual(conn.get_token(), "secret-token-1234")
        self.assertEqual(conn.token_last_four, "1234")

    def test_connect_rejects_unsupported_provider(self):
        resp = self.client.post(reverse("integrations:migrate_connect"), {
            "provider": "trello", "api_token": "x",
        })
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["ok"])

    @patch("kanban.utils.connectors.ConnectorFactory.get_connector")
    def test_connect_reports_bad_credentials(self, mock_get):
        from kanban.utils.connectors import ConnectorError
        fake = MagicMock()
        fake.test_connection.side_effect = ConnectorError("Jira rejected the credentials.", status_code=401)
        mock_get.return_value = fake

        resp = self.client.post(reverse("integrations:migrate_connect"), {
            "provider": "jira", "base_url": "https://acme.atlassian.net",
            "account_email": "owner@acme.com", "api_token": "bad",
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("rejected", resp.json()["error"])

    @patch("kanban.tasks.migration_tasks.run_source_migration.delay")
    def test_run_enqueues_task(self, mock_delay):
        from integrations.models import SourceConnection
        mock_delay.return_value = MagicMock(id="task-abc-123")
        conn = SourceConnection(
            workspace=self.ws, created_by=self.user, provider="jira",
            base_url="https://acme.atlassian.net", account_email="owner@acme.com",
        )
        conn.set_token("t")
        conn.save()

        resp = self.client.post(reverse("integrations:migrate_run"), {
            "connection_id": conn.id, "project_id": "KAN", "project_name": "Kanban",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["task_id"], "task-abc-123")
        mock_delay.assert_called_once_with(conn.id, "KAN", "Kanban")

    def test_run_blocks_other_users_connection(self):
        from integrations.models import SourceConnection
        other = User.objects.create_user("intruder", "x@x.com", "pw")
        conn = SourceConnection(
            workspace=self.ws, created_by=other, provider="jira",
            base_url="https://acme.atlassian.net", account_email="x@x.com",
        )
        conn.set_token("t")
        conn.save()

        resp = self.client.post(reverse("integrations:migrate_run"), {
            "connection_id": conn.id, "project_id": "KAN", "project_name": "Kanban",
        })
        self.assertEqual(resp.status_code, 404)

    def test_status_returns_progress(self):
        from kanban.utils.connectors.migration_progress import set_progress
        set_progress("task-xyz", 42, "Halfway there")
        resp = self.client.get(reverse("integrations:migrate_status", args=["task-xyz"]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["percent"], 42)
        self.assertEqual(data["message"], "Halfway there")
