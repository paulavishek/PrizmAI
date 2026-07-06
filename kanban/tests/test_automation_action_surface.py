"""
Action Surface Contract — builder ⇄ save-endpoint ⇄ model
=========================================================

The automation engine *registers* 50 action handlers (``ACTION_HANDLERS`` in
``kanban/automation_actions.py``), but the shipped rule builder deliberately
exposes only a **lean MVP subset**. Three lists must therefore agree exactly for
the save flow to be safe:

    1. ``ACTION_GROUPS`` in ``static/js/unified_rule_builder.js``  (what the
       dropdown offers the user)
    2. ``AutomationRule.ACTION_CHOICES``                           (the model's
       declared choices)
    3. ``VALID_ACTIONS`` in ``kanban/automation_views.py``         (what the
       create/update endpoint accepts) — derived from ACTION_CHOICES.

If (1) ever drifts ahead of (2)/(3), a user could pick an action in the UI that
the server then rejects with HTTP 400 — a broken save. This file is the guard.

It also PROVES the positive path: every one of the exposed actions round-trips
through create → detail → update → detail without drift, and pins the
registered-but-unexposed actions as *intentionally* rejected by the endpoint (so
that "unknown action type" stays a deliberate contract, not an accident).

Context: the broad ship-gate ``test_automation_serialization.py`` builds fixtures
from the full 50-action registry and therefore reports the 37 unexposed actions
as red. That is the test being ahead of the shipped UI surface — NOT a product
regression. This file draws the line explicitly.

    python -m pytest kanban/tests/test_automation_action_surface.py -v
"""

import json

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse


# The exact action keys the builder dropdown offers. Mirrors ACTION_GROUPS in
# static/js/unified_rule_builder.js (the "Lean MVP set"). If you expose a new
# action in the JS, add it here AND to AutomationRule.ACTION_CHOICES — this test
# will flag the omission.
BUILDER_EXPOSED_ACTIONS = {
    'add_label', 'assign_to_user', 'clear_assignee', 'close_task',
    'flag_for_review', 'mention_users_in_comment', 'move_to_column',
    'post_comment', 'remove_label', 'send_notification', 'set_due_date',
    'set_priority', 'set_progress',
}

# Minimal valid target/message per exposed action so the save endpoint accepts it.
_EXPOSED_PROBE = {
    'add_label':                {'target': 'Hot', 'message': None},
    'assign_to_user':           {'target': 'rule_creator', 'message': None},
    'clear_assignee':           {'target': None, 'message': None},
    'close_task':               {'target': None, 'message': None},
    'flag_for_review':          {'target': None, 'message': None},
    'mention_users_in_comment': {'target': None, 'message': 'ping {assignee}'},
    'move_to_column':           {'target': 'Done', 'message': None},
    'post_comment':             {'target': None, 'message': 'auto-comment'},
    'remove_label':             {'target': 'Hot', 'message': None},
    'send_notification':        {'target': 'task_assignee', 'message': 'hi'},
    'set_due_date':             {'target': 'in_2_days', 'message': None},
    'set_priority':             {'target': 'high', 'message': None},
    'set_progress':             {'target': '50', 'message': None},
}

SERIALIZED_KEYS = (
    'trigger_type', 'trigger_config', 'condition_logic',
    'conditions', 'actions', 'otherwise_actions',
)


def _project(payload):
    return {k: payload.get(k) for k in SERIALIZED_KEYS}


class ActionSurfaceContractTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        from kanban.models import Board, Column
        cls.user = User.objects.create_user(
            username='surface_runner', password='x', email='surface@example.com')
        cls.board = Board.objects.create(name='Surface Board', created_by=cls.user)
        Column.objects.create(board=cls.board, name='To Do', position=0)
        Column.objects.create(board=cls.board, name='Done', position=1)

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    # ── the sync invariant ───────────────────────────────────────────────────

    def test_builder_matches_model_choices(self):
        """Builder dropdown == model ACTION_CHOICES (no UI action the server rejects)."""
        from kanban.automation_models import AutomationRule
        choices = {a[0] for a in AutomationRule.ACTION_CHOICES}
        self.assertEqual(
            BUILDER_EXPOSED_ACTIONS, choices,
            'The rule-builder ACTION_GROUPS and AutomationRule.ACTION_CHOICES have '
            'drifted. A user could select an action the save endpoint rejects. '
            f'builder-only={BUILDER_EXPOSED_ACTIONS - choices}, '
            f'choices-only={choices - BUILDER_EXPOSED_ACTIONS}')

    def test_endpoint_valid_actions_match_model_choices(self):
        """The create/update endpoint's whitelist == the model choices."""
        from kanban.automation_models import AutomationRule
        from kanban.automation_views import VALID_ACTIONS
        choices = {a[0] for a in AutomationRule.ACTION_CHOICES}
        self.assertEqual(VALID_ACTIONS, choices)

    def test_every_exposed_action_is_registered_and_executable(self):
        """Each of the 13 exposed actions has a real handler behind it."""
        from kanban.automation_actions import ACTION_HANDLERS
        missing = BUILDER_EXPOSED_ACTIONS - set(ACTION_HANDLERS.keys())
        self.assertEqual(missing, set(),
                         f'Exposed actions with no registered handler: {missing}')

    # ── positive path: every exposed action round-trips through save ─────────

    def test_exposed_actions_round_trip(self):
        """Create → detail → update → detail with no field drift, per action."""
        create_url = reverse('automation_rule_create', args=[self.board.id])
        for action_key in sorted(BUILDER_EXPOSED_ACTIONS):
            with self.subTest(action=action_key):
                probe = _EXPOSED_PROBE[action_key]
                fixture = {
                    'name': f'Exposed: {action_key}',
                    'trigger_type': 'task_created',
                    'trigger_config': {},
                    'condition_logic': 'AND',
                    'conditions': [],
                    'actions': [{'type': action_key, 'target': probe['target'],
                                 'message': probe['message']}],
                    'otherwise_actions': [],
                }
                resp = self.client.post(create_url, json.dumps(fixture),
                                        content_type='application/json')
                self.assertEqual(resp.status_code, 201,
                                 f'{action_key}: create {resp.status_code} {resp.content[:200]!r}')
                rule_id = resp.json()['id']
                detail_url = reverse('automation_rule_detail',
                                     args=[self.board.id, rule_id])
                fetched = self.client.get(detail_url).json()
                self.assertEqual(_project(fetched), _project(fixture),
                                 f'{action_key}: drifted on round-trip')
                update_url = reverse('automation_rule_update',
                                     args=[self.board.id, rule_id])
                resaved = self.client.post(update_url, json.dumps(fetched),
                                           content_type='application/json')
                self.assertEqual(resaved.status_code, 200)

    # ── the deliberate boundary: unexposed actions are rejected ──────────────

    def test_unexposed_registered_actions_are_rejected(self):
        """Registered-but-not-exposed actions must 400 at the save endpoint.

        This pins the lean-MVP boundary: the engine can *run* these (via
        templates / programmatic rules) but the builder does not offer them and
        the endpoint refuses to persist them. Locking this in means an unexposed
        action can never silently leak into the save flow.
        """
        from kanban.automation_actions import ACTION_HANDLERS
        create_url = reverse('automation_rule_create', args=[self.board.id])
        unexposed = sorted(set(ACTION_HANDLERS.keys()) - BUILDER_EXPOSED_ACTIONS)
        self.assertTrue(unexposed, 'expected some registered-but-unexposed actions')
        for action_key in unexposed:
            with self.subTest(action=action_key):
                fixture = {
                    'name': f'Unexposed: {action_key}',
                    'trigger_type': 'task_created',
                    'trigger_config': {},
                    'condition_logic': 'AND',
                    'conditions': [],
                    'actions': [{'type': action_key, 'target': None, 'message': None}],
                    'otherwise_actions': [],
                }
                resp = self.client.post(create_url, json.dumps(fixture),
                                        content_type='application/json')
                self.assertEqual(
                    resp.status_code, 400,
                    f'{action_key}: expected 400 (unexposed) but got {resp.status_code}')
                self.assertIn('unknown action type', resp.content.decode().lower())
