"""
test_connectors.py — Live-migration connector framework + SourceConnection model.

All HTTP is mocked — no network calls. Verifies that:
  * SourceConnection encrypts/decrypts its token and never leaks it in repr.
  * JiraConnector authenticates, lists projects, paginates issues, flattens ADF
    descriptions, and normalises epics.
  * The connector's fetch_project output is directly consumable by the existing
    JiraAdapter (the whole point: reuse translation, don't rewrite it).
  * ConnectorFactory resolves/refuses providers.

Run with:
    pytest tests/test_connectors.py
"""

import json
from unittest.mock import patch, MagicMock

import pytest
from cryptography.fernet import Fernet
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings

from kanban.utils.connectors import ConnectorFactory, ConnectorError
from kanban.utils.connectors.jira_connector import JiraConnector
from kanban.utils.import_adapters import AdapterFactory


_TEST_FERNET_KEY = Fernet.generate_key().decode()


def _resp(status_code=200, json_body=None):
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = json_body if json_body is not None else {}
    return m


class _FakeConnection:
    """Minimal stand-in for integrations.SourceConnection (no DB needed)."""

    def __init__(self, base_url, email, token):
        self.base_url = base_url
        self.account_email = email
        self._token = token

    def get_token(self):
        return self._token


# ===========================================================================
# JiraConnector (mocked HTTP)
# ===========================================================================

class TestJiraConnector(SimpleTestCase):

    def setUp(self):
        self.conn = _FakeConnection("https://acme.atlassian.net/", "me@acme.com", "tok-123")
        self.connector = JiraConnector(self.conn)

    @patch("kanban.utils.connectors.jira_connector.requests.request")
    def test_test_connection_success(self, mock_req):
        mock_req.return_value = _resp(200, {"emailAddress": "me@acme.com", "accountId": "a1"})
        info = self.connector.test_connection()
        self.assertEqual(info["account"], "me@acme.com")

    @patch("kanban.utils.connectors.jira_connector.requests.request")
    def test_bad_credentials_raise(self, mock_req):
        mock_req.return_value = _resp(401, {})
        with self.assertRaises(ConnectorError) as ctx:
            self.connector.test_connection()
        self.assertEqual(ctx.exception.status_code, 401)

    @patch("kanban.utils.connectors.jira_connector.requests.request")
    def test_list_projects(self, mock_req):
        mock_req.return_value = _resp(200, {
            "isLast": True,
            "values": [
                {"key": "KAN", "name": "Kanban"},
                {"key": "MOB", "name": "Mobile"},
            ],
        })
        projects = self.connector.list_projects()
        self.assertEqual(projects, [
            {"id": "KAN", "name": "Kanban"},
            {"id": "MOB", "name": "Mobile"},
        ])

    @patch("kanban.utils.connectors.jira_connector.requests.request")
    def test_fetch_project_paginates(self, mock_req):
        page1 = _resp(200, {
            "issues": [{"key": "KAN-1", "fields": {"summary": "One"}}],
            "nextPageToken": "tok2",
            "isLast": False,
        })
        page2 = _resp(200, {
            "issues": [{"key": "KAN-2", "fields": {"summary": "Two"}}],
            "isLast": True,
        })
        mock_req.side_effect = [page1, page2]
        data = self.connector.fetch_project("KAN")
        keys = [i["key"] for i in data["issues"]]
        self.assertEqual(keys, ["KAN-1", "KAN-2"])

    def test_adf_to_text_flattens(self):
        adf = {
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [
                    {"type": "text", "text": "Hello "},
                    {"type": "text", "text": "world"},
                ]},
            ],
        }
        self.assertEqual(JiraConnector._adf_to_text(adf), "Hello world")
        self.assertEqual(JiraConnector._adf_to_text("plain"), "plain")
        self.assertEqual(JiraConnector._adf_to_text(None), "")

    def test_normalise_issue_sets_epic_from_parent(self):
        issue = {
            "key": "KAN-5",
            "fields": {
                "summary": "Child",
                "parent": {
                    "key": "KAN-1",
                    "fields": {"summary": "Login Epic", "issuetype": {"name": "Epic"}},
                },
            },
        }
        out = self.connector._normalise_issue(issue)
        self.assertEqual(out["fields"]["epic"], {"key": "KAN-1", "name": "Login Epic"})

    @patch("kanban.utils.connectors.jira_connector.requests.request")
    def test_output_is_consumable_by_jira_adapter(self, mock_req):
        """The core contract: connector output flows straight into JiraAdapter."""
        mock_req.return_value = _resp(200, {
            "isLast": True,
            "issues": [
                {"key": "KAN-1", "fields": {
                    "summary": "Build login",
                    "status": {"name": "In Progress"},
                    "priority": {"name": "High"},
                    "issuetype": {"name": "Story"},
                    "labels": ["backend"],
                    "description": {"type": "doc", "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": "Do it"}]}]},
                }},
            ],
        })
        raw = self.connector.fetch_project("KAN")
        # Hand the raw dict (as JSON) to the existing adapter, unchanged.
        result = AdapterFactory().import_with_adapter("jira", json.dumps(raw), "jira.json")
        self.assertTrue(result.success)
        self.assertEqual(len(result.tasks_data), 1)
        self.assertEqual(result.tasks_data[0]["title"], "Build login")
        self.assertEqual(result.tasks_data[0]["priority"], "high")
        self.assertEqual(result.tasks_data[0]["description"], "Do it")


# ===========================================================================
# AsanaConnector (mocked HTTP)
# ===========================================================================

class TestAsanaConnector(SimpleTestCase):

    def setUp(self):
        from kanban.utils.connectors.asana_connector import AsanaConnector
        self.connector = AsanaConnector(_FakeConnection("", "", "pat-123"))

    @patch("kanban.utils.connectors.asana_connector.requests.get")
    def test_connection_and_projects(self, mock_get):
        mock_get.side_effect = [
            _resp(200, {"data": {"email": "me@acme.com", "name": "Me"}}),   # /users/me
            _resp(200, {"data": [{"gid": "ws1", "name": "Acme"}]}),          # /workspaces
            _resp(200, {"data": [{"gid": "p1", "name": "Launch", "archived": False},
                                 {"gid": "p2", "name": "Old", "archived": True}]}),  # /projects
        ]
        self.assertEqual(self.connector.test_connection()["account"], "me@acme.com")
        projects = self.connector.list_projects()
        self.assertEqual(projects, [{"id": "p1", "name": "Acme / Launch"}])  # archived excluded

    @patch("kanban.utils.connectors.asana_connector.requests.get")
    def test_fetch_paginates_and_feeds_adapter(self, mock_get):
        mock_get.side_effect = [
            _resp(200, {"data": [{"gid": "1", "name": "Design", "completed": False,
                                  "memberships": [{"section": {"name": "To Do"}}]}],
                        "next_page": {"offset": "off2"}}),
            _resp(200, {"data": [{"gid": "2", "name": "Build", "completed": True,
                                  "memberships": [{"section": {"name": "Done"}}]}],
                        "next_page": None}),
        ]
        raw = self.connector.fetch_project("p1")
        self.assertEqual([t["gid"] for t in raw["data"]], ["1", "2"])
        result = AdapterFactory().import_with_adapter("asana", json.dumps(raw), "asana.json")
        self.assertTrue(result.success)
        self.assertEqual(len(result.tasks_data), 2)

    @patch("kanban.utils.connectors.asana_connector.requests.get")
    def test_bad_token_raises(self, mock_get):
        mock_get.return_value = _resp(401, {})
        with self.assertRaises(ConnectorError):
            self.connector.test_connection()


# ===========================================================================
# MondayConnector (mocked GraphQL)
# ===========================================================================

class TestMondayConnector(SimpleTestCase):

    def setUp(self):
        from kanban.utils.connectors.monday_connector import MondayConnector
        self.connector = MondayConnector(_FakeConnection("", "", "tok"))

    @patch("kanban.utils.connectors.monday_connector.requests.post")
    def test_connection_and_boards(self, mock_post):
        mock_post.side_effect = [
            _resp(200, {"data": {"me": {"email": "me@acme.com"}}}),
            _resp(200, {"data": {"boards": [{"id": 10, "name": "Sprint"}]}}),
        ]
        self.assertEqual(self.connector.test_connection()["account"], "me@acme.com")
        self.assertEqual(self.connector.list_projects(), [{"id": "10", "name": "Sprint"}])

    @patch("kanban.utils.connectors.monday_connector.requests.post")
    def test_graphql_error_raises(self, mock_post):
        mock_post.return_value = _resp(200, {"errors": [{"message": "Invalid token"}]})
        with self.assertRaises(ConnectorError):
            self.connector.test_connection()

    @patch("kanban.utils.connectors.monday_connector.requests.post")
    def test_fetch_feeds_monday_api_adapter(self, mock_post):
        mock_post.return_value = _resp(200, {"data": {"boards": [{
            "id": 10, "name": "Sprint",
            "groups": [{"id": "g1", "title": "To Do"}],
            "items_page": {"cursor": None, "items": [
                {"id": "i1", "name": "Ship it", "group": {"id": "g1", "title": "To Do"},
                 "column_values": [{"text": "Working on it", "column": {"title": "Status"}}]},
            ]},
        }]}})
        raw = self.connector.fetch_project("10")
        self.assertEqual(raw["boards"][0]["name"], "Sprint")
        result = AdapterFactory().import_with_adapter("monday_api", json.dumps(raw), "monday.json")
        self.assertTrue(result.success)
        self.assertEqual(len(result.tasks_data), 1)
        self.assertEqual(result.tasks_data[0]["progress"], 50)  # "Working on it"


# ===========================================================================
# ConnectorFactory
# ===========================================================================

class TestConnectorFactory(SimpleTestCase):

    def test_jira_supported(self):
        self.assertTrue(ConnectorFactory.is_supported("jira"))
        conn = _FakeConnection("https://x.atlassian.net", "a@b.com", "t")
        self.assertIsInstance(ConnectorFactory.get_connector("jira", conn), JiraConnector)

    def test_unsupported_provider_raises(self):
        with self.assertRaises(ConnectorError):
            ConnectorFactory.get_connector("trello", _FakeConnection("u", "e", "t"))


# ===========================================================================
# SourceConnection model (DB + encryption)
# ===========================================================================

@override_settings(AI_KEY_ENCRYPTION_KEY=_TEST_FERNET_KEY)
class TestSourceConnectionModel(TestCase):

    def _make_workspace(self):
        from accounts.models import Organization
        from kanban.models import Workspace
        user = User.objects.create_user("owner", "owner@acme.com", "pw")
        org = Organization.objects.create(name="Acme", created_by=user)
        ws = Workspace.objects.create(name="Acme WS", organization=org, created_by=user)
        return user, ws

    def test_token_encrypted_and_round_trips(self):
        from integrations.models import SourceConnection
        user, ws = self._make_workspace()
        conn = SourceConnection(
            workspace=ws, created_by=user, provider="jira",
            base_url="https://acme.atlassian.net", account_email="me@acme.com",
        )
        conn.set_token("super-secret-token-9999")
        conn.save()

        # Ciphertext in the column, never the raw token.
        self.assertNotIn("super-secret-token-9999", conn.encrypted_api_token)
        self.assertEqual(conn.token_last_four, "9999")
        # Decrypt round-trips.
        self.assertEqual(conn.get_token(), "super-secret-token-9999")

    def test_repr_never_leaks_token(self):
        from integrations.models import SourceConnection
        user, ws = self._make_workspace()
        conn = SourceConnection(
            workspace=ws, created_by=user, provider="jira",
            base_url="https://acme.atlassian.net", account_email="me@acme.com",
        )
        conn.set_token("leaky-token-abcd")
        conn.save()
        text = repr(conn)
        self.assertNotIn("leaky-token-abcd", text)
        self.assertNotIn(conn.encrypted_api_token, text)


# ===========================================================================
# Migration orchestrator (Project -> Strategy, Epic -> Board, Issue -> Task)
# ===========================================================================

def _issue(key, summary, status="To Do", epic=None, issue_type="Story"):
    fields = {"summary": summary, "status": {"name": status}, "issuetype": {"name": issue_type}}
    if epic:
        fields["epic"] = epic
    return {"key": key, "fields": fields}


@override_settings(AI_KEY_ENCRYPTION_KEY=_TEST_FERNET_KEY)
class TestMigrationOrchestrator(TestCase):

    def _setup_user(self):
        from accounts.models import Organization, UserProfile
        from kanban.models import Workspace
        user = User.objects.create_user("mig", "mig@acme.com", "pw")
        org = Organization.objects.create(name="Acme", created_by=user)
        ws = Workspace.objects.create(name="Acme WS", organization=org, created_by=user)
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.organization = org
        profile.active_workspace = ws
        profile.save()
        return user, org, ws

    def test_epics_become_boards_under_one_strategy(self):
        from kanban.utils.connectors.migration_orchestrator import run_migration

        user, org, ws = self._setup_user()
        login_epic = {"key": "KAN-100", "name": "Login"}
        pay_epic = {"key": "KAN-200", "name": "Payments"}
        raw = {"issues": [
            _issue("KAN-1", "Build login form", "In Progress", epic=login_epic),
            _issue("KAN-2", "Login API", "To Do", epic=login_epic),
            _issue("KAN-3", "Stripe webhook", "Done", epic=pay_epic),
            _issue("KAN-4", "Housekeeping", "To Do", epic=None),
        ]}

        res = run_migration(
            provider="jira", raw=raw, adapter_name="jira",
            project_name="Kanban", user=user, organization=org, session={},
        )

        self.assertIsNotNone(res.strategy)
        self.assertIsNotNone(res.mission)
        self.assertEqual(res.strategy.name, "Kanban")
        # 3 buckets: Login, Payments, General
        self.assertEqual(res.stats.get("boards_created"), 3)
        self.assertEqual(res.stats.get("tasks_imported"), 4)

        board_names = sorted(b.name for b in res.boards)
        self.assertEqual(board_names, ["General", "Login", "Payments"])
        # Every board is wired into the Strategy and its workspace.
        for board in res.boards:
            self.assertEqual(board.strategy_id, res.strategy.id)
            self.assertEqual(board.workspace_id, ws.id)

    def test_epic_issue_is_not_imported_as_a_task(self):
        """The Epic card itself must become a Board, not also a task in General."""
        from kanban.utils.connectors.migration_orchestrator import run_migration

        user, org, ws = self._setup_user()
        epic_ref = {"key": "KAN-6", "name": "Just a Test"}
        raw = {"issues": [
            _issue("KAN-1", "Start here", "Idea"),                       # no epic -> General
            _issue("KAN-2", "Connect tools", "Idea"),                    # no epic -> General
            _issue("KAN-3", "test 1", "Idea", epic=epic_ref),            # -> epic board
            _issue("KAN-4", "test 2", "To Do", epic=epic_ref),           # -> epic board
            _issue("KAN-5", "test 3", "In Progress"),                    # no epic -> General
            _issue("KAN-6", "Just a Test", "To Do", issue_type="Epic"),  # the Epic itself
        ]}
        res = run_migration(
            provider="jira", raw=raw, adapter_name="jira",
            project_name="Kanban", user=user, organization=org, session={},
        )
        # Epic excluded from tasks: 3 in General + 2 in epic board = 5 (not 6).
        self.assertEqual(res.stats.get("tasks_imported"), 5)
        by_name = {b.name: b for b in res.boards}
        self.assertIn("General", by_name)
        self.assertIn("Just a Test", by_name)
        from kanban.models import Task
        general_task_count = Task.objects.filter(
            column__board=by_name["General"]).count()
        self.assertEqual(general_task_count, 3)

    def test_project_without_epics_makes_single_board(self):
        from kanban.utils.connectors.migration_orchestrator import run_migration

        user, org, ws = self._setup_user()
        raw = {"issues": [
            _issue("KAN-1", "Task one"),
            _issue("KAN-2", "Task two"),
        ]}
        res = run_migration(
            provider="jira", raw=raw, adapter_name="jira",
            project_name="Solo Project", user=user, organization=org, session={},
        )
        self.assertEqual(res.stats.get("boards_created"), 1)
        # No epics -> the single "General" bucket is renamed to the project.
        self.assertEqual(res.boards[0].name, "Solo Project")
        self.assertEqual(res.boards[0].strategy_id, res.strategy.id)

    @patch("ai_assistant.utils.ai_router.AIRouter.complete")
    def test_audit_collects_signals_and_persists_summary(self, mock_complete):
        from kanban.utils.connectors.migration_orchestrator import run_migration
        from kanban.utils.connectors.migration_audit import (
            collect_signals, generate_migration_audit,
        )

        mock_complete.return_value = {"text": "Healthy start. Watch the backlog."}
        user, org, ws = self._setup_user()
        raw = {"issues": [
            _issue("KAN-1", "Open no due date", "To Do"),
            _issue("KAN-2", "Also open", "In Progress"),
            _issue("KAN-3", "Finished", "Done"),
        ]}
        res = run_migration(
            provider="jira", raw=raw, adapter_name="jira",
            project_name="Audit Project", user=user, organization=org, session={},
        )

        signals = collect_signals(res.strategy)
        self.assertEqual(signals["total_tasks"], 3)
        self.assertEqual(signals["done_tasks"], 1)
        self.assertEqual(signals["open_tasks"], 2)
        self.assertEqual(signals["missing_due_dates"], 2)

        out = generate_migration_audit(res.strategy, user)
        self.assertEqual(out["summary"], "Healthy start. Watch the backlog.")
        res.strategy.refresh_from_db()
        self.assertEqual(res.strategy.ai_summary, "Healthy start. Watch the backlog.")
        self.assertIsNotNone(res.strategy.ai_summary_generated_at)

    @patch("ai_assistant.utils.ai_router.AIRouter.complete")
    def test_audit_falls_back_when_ai_fails(self, mock_complete):
        from ai_assistant.utils.ai_router import AIProviderError
        from kanban.utils.connectors.migration_orchestrator import run_migration
        from kanban.utils.connectors.migration_audit import generate_migration_audit

        mock_complete.side_effect = AIProviderError("gemini", Exception("boom"))
        user, org, ws = self._setup_user()
        raw = {"issues": [_issue("KAN-1", "Task")]}
        res = run_migration(
            provider="jira", raw=raw, adapter_name="jira",
            project_name="Fallback Project", user=user, organization=org, session={},
        )
        out = generate_migration_audit(res.strategy, user)
        # Deterministic fallback still produces a non-empty, persisted summary.
        self.assertIn("Migrated", out["summary"])
        res.strategy.refresh_from_db()
        self.assertTrue(res.strategy.ai_summary)
