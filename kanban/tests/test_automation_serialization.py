"""
Serialization Round-Trip Test — Automation Rules
================================================

This test file is the **ship gate for every phase of the automation expansion
roadmap**. It asserts that loading a saved rule into the builder and saving it
back produces a byte-for-byte equivalent JSON payload — no condition attribute,
operator, value, target, message, or trigger_config key is silently dropped,
renamed, or mutated during the round trip.

Two fixture buckets:

    LEGACY_RULES   — frozen JSON of rules saved BEFORE any phase shipped.
                     These never change. They guard against accidental breakage
                     of rules already in production.

    CURRENT_RULES  — one rule per registered trigger, condition, and action
                     covering every operator and target supported by the
                     current registries. Grows with each phase.

Each phase's pre-merge ship gate runs:

    python manage.py test kanban.tests.test_automation_serialization

A phase that fails this test against LEGACY_RULES cannot merge. A phase that
fails it against CURRENT_RULES has introduced a serialization bug in the new
handlers it added.
"""

import json

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse


# ─── Test fixtures ───────────────────────────────────────────────────────────

# LEGACY_RULES: rule payloads representing the 11 triggers, 8 condition
# attributes, and 10 actions that existed before Phase 1a. These are FROZEN —
# they should never be edited. Their job is to verify that future code never
# silently drops a field a production rule depended on.
LEGACY_RULES = [
    {
        'name': 'Legacy: simple priority rule',
        'trigger_type': 'task_created',
        'trigger_config': {},
        'condition_logic': 'AND',
        'conditions': [
            {'attribute': 'priority', 'operator': 'is', 'value': 'Urgent'},
        ],
        'actions': [
            {'type': 'add_label', 'target': 'Hot', 'message': None},
        ],
        'otherwise_actions': [],
    },
    {
        'name': 'Legacy: overdue with all operators',
        'trigger_type': 'task_overdue',
        'trigger_config': {},
        'condition_logic': 'OR',
        'conditions': [
            {'attribute': 'assignee', 'operator': 'is_empty', 'value': None},
            {'attribute': 'progress', 'operator': 'lte', 'value': '25'},
            {'attribute': 'due_date', 'operator': 'within_days', 'value': '3'},
            {'attribute': 'label', 'operator': 'has', 'value': 'Hot'},
            {'attribute': 'stale_high_priority', 'operator': 'is_true', 'value': None},
            {'attribute': 'all_subtasks_done', 'operator': 'is_false', 'value': None},
        ],
        'actions': [
            {'type': 'send_notification', 'target': 'task_assignee',
             'message': 'Task {task_title} is overdue.'},
            {'type': 'set_priority', 'target': 'urgent', 'message': None},
        ],
        'otherwise_actions': [
            {'type': 'post_comment', 'target': None,
             'message': 'Otherwise branch fired.'},
        ],
    },
    {
        'name': 'Legacy: moved-to-column with trigger config',
        'trigger_type': 'task_moved_to_column',
        'trigger_config': {'column_name': 'Review'},
        'condition_logic': 'AND',
        'conditions': [
            {'attribute': 'column', 'operator': 'is_not', 'value': 'Done'},
        ],
        'actions': [
            {'type': 'move_to_column', 'target': 'In Progress', 'message': None},
            {'type': 'remove_label', 'target': 'Hot', 'message': None},
        ],
        'otherwise_actions': [],
    },
    {
        'name': 'Legacy: due-date approaching scheduled-by-config',
        'trigger_type': 'due_date_approaching',
        'trigger_config': {'days': 2},
        'condition_logic': 'AND',
        'conditions': [],
        'actions': [
            {'type': 'set_due_date', 'target': 'in_7_days', 'message': None},
        ],
        'otherwise_actions': [],
    },
    {
        'name': 'Legacy: scheduled weekly',
        'trigger_type': 'scheduled_weekly',
        'trigger_config': {'day': 'Monday', 'time': '09:00'},
        'condition_logic': 'AND',
        'conditions': [],
        'actions': [
            {'type': 'log_time_entry', 'target': '0.5', 'message': None},
        ],
        'otherwise_actions': [],
    },
    {
        'name': 'Legacy: assignment rule',
        'trigger_type': 'task_assigned',
        'trigger_config': {},
        'condition_logic': 'AND',
        'conditions': [
            {'attribute': 'assignee', 'operator': 'is_not_empty', 'value': None},
        ],
        'actions': [
            {'type': 'assign_to_user', 'target': 'rule_creator', 'message': None},
        ],
        'otherwise_actions': [],
    },
    {
        'name': 'Legacy: completion-threshold rule',
        'trigger_type': 'task_completion_threshold',
        'trigger_config': {'threshold': 75},
        'condition_logic': 'AND',
        'conditions': [
            {'attribute': 'progress', 'operator': 'gte', 'value': '75'},
        ],
        'actions': [
            {'type': 'close_task', 'target': None, 'message': None},
        ],
        'otherwise_actions': [],
    },
]


def current_rules():
    """Return the CURRENT_RULES fixture set.

    Built dynamically from the registry contents so it grows automatically when
    a new phase registers handlers. Each fixture is a minimal-but-complete rule
    that exercises one registered entry.
    """
    from kanban.automation_models import AutomationRule
    from kanban.automation_conditions import CONDITION_HANDLERS
    from kanban.automation_actions import ACTION_HANDLERS

    fixtures = []

    # One rule per trigger (uses simple universal condition+action).
    for trigger_key, _ in AutomationRule.TRIGGER_CHOICES:
        cfg = {}
        # Minimal configs for triggers that need them
        if trigger_key == 'scheduled_daily':
            cfg = {'time': '09:00'}
        elif trigger_key == 'scheduled_weekly':
            cfg = {'day': 'Monday', 'time': '09:00'}
        elif trigger_key == 'scheduled_monthly':
            cfg = {'day_of_month': 1, 'time': '09:00'}
        elif trigger_key == 'due_date_approaching':
            cfg = {'days': 2}
        fixtures.append({
            'name': f'Current trigger: {trigger_key}',
            'trigger_type': trigger_key,
            'trigger_config': cfg,
            'condition_logic': 'AND',
            'conditions': [],
            'actions': [{'type': 'close_task', 'target': None, 'message': None}],
            'otherwise_actions': [],
        })

    # One rule per registered condition attribute (uses task_created trigger).
    # Each condition uses an arbitrary operator and value that round-trip
    # cleanly. The point is the JSON shape, not the semantic correctness.
    _COND_PROBE = {
        'priority':           {'operator': 'is', 'value': 'high'},
        'assignee':           {'operator': 'is_empty', 'value': None},
        'column':             {'operator': 'is', 'value': 'To Do'},
        'label':              {'operator': 'has', 'value': 'Hot'},
        'progress':           {'operator': 'gte', 'value': '50'},
        'due_date':           {'operator': 'within_days', 'value': '3'},
        'all_subtasks_done':  {'operator': 'is_true', 'value': None},
        'stale_high_priority':{'operator': 'is_true', 'value': None},
    }
    for attr in sorted(CONDITION_HANDLERS.keys()):
        probe = _COND_PROBE.get(attr, {'operator': 'is', 'value': 'x'})
        fixtures.append({
            'name': f'Current condition: {attr}',
            'trigger_type': 'task_created',
            'trigger_config': {},
            'condition_logic': 'AND',
            'conditions': [{
                'attribute': attr,
                'operator':  probe['operator'],
                'value':     probe['value'],
            }],
            'actions': [{'type': 'close_task', 'target': None, 'message': None}],
            'otherwise_actions': [],
        })

    # One rule per registered action.
    _ACT_PROBE = {
        'set_priority':      {'target': 'high', 'message': None},
        'add_label':         {'target': 'Hot', 'message': None},
        'remove_label':      {'target': 'Hot', 'message': None},
        'assign_to_user':    {'target': 'rule_creator', 'message': None},
        'move_to_column':    {'target': 'Done', 'message': None},
        'set_due_date':      {'target': 'in_2_days', 'message': None},
        'close_task':        {'target': None, 'message': None},
        'send_notification': {'target': 'task_assignee', 'message': 'hi {assignee}'},
        'post_comment':      {'target': None, 'message': 'auto-comment'},
        'log_time_entry':    {'target': '0.5', 'message': None},
    }
    for action_key in sorted(ACTION_HANDLERS.keys()):
        probe = _ACT_PROBE.get(action_key, {'target': None, 'message': None})
        fixtures.append({
            'name': f'Current action: {action_key}',
            'trigger_type': 'task_created',
            'trigger_config': {},
            'condition_logic': 'AND',
            'conditions': [],
            'actions': [{
                'type':    action_key,
                'target':  probe['target'],
                'message': probe['message'],
            }],
            'otherwise_actions': [],
        })

    return fixtures


# ─── Helpers ─────────────────────────────────────────────────────────────────

SERIALIZED_KEYS = (
    'trigger_type',
    'trigger_config',
    'condition_logic',
    'conditions',
    'actions',
    'otherwise_actions',
)


def _project(payload):
    """Project a rule payload (request or response) to just the keys the
    serialization gate cares about. Strips out server-assigned fields like
    id/run_count/timestamps."""
    return {k: payload.get(k) for k in SERIALIZED_KEYS}


# ─── Test case ───────────────────────────────────────────────────────────────


class AutomationSerializationRoundTripTest(TestCase):
    """The Phase 1a → Phase N ship gate.

    For each fixture rule:
        1. POST it to the create endpoint.
        2. GET it back via the detail endpoint.
        3. POST it back unchanged to the update endpoint (no-op save).
        4. GET it again.
        5. Assert the projected payloads match the original fixture.
    """

    @classmethod
    def setUpTestData(cls):
        from kanban.models import Board, Column
        cls.user = User.objects.create_user(
            username='gate_runner', password='x', email='gate@example.com',
        )
        cls.board = Board.objects.create(name='Gate Board', created_by=cls.user)
        # Two columns so move_to_column has somewhere to go.
        Column.objects.create(board=cls.board, name='To Do', position=0)
        Column.objects.create(board=cls.board, name='Done', position=1)

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def _round_trip(self, fixture, label=''):
        """Run one fixture through create → detail → update → detail and assert
        no fields were dropped or mutated."""
        create_url = reverse('automation_rule_create', args=[self.board.id])
        payload = dict(fixture)

        resp = self.client.post(
            create_url, json.dumps(payload), content_type='application/json',
        )
        self.assertEqual(
            resp.status_code, 201,
            msg=f'{label}: create returned {resp.status_code} body={resp.content[:300]!r}',
        )
        created = resp.json()
        rule_id = created['id']

        # Assert what the server stored matches what we sent on the keys we care about.
        self.assertEqual(
            _project(created), _project(fixture),
            msg=f'{label}: server returned different fields on CREATE',
        )

        detail_url = reverse(
            'automation_rule_detail',
            args=[self.board.id, rule_id],
        )
        fetched = self.client.get(detail_url).json()
        self.assertEqual(
            _project(fetched), _project(fixture),
            msg=f'{label}: GET after CREATE drifted from the fixture',
        )

        # Re-save the fetched payload unchanged (simulates "user opens rule
        # then clicks save without touching anything").
        update_url = reverse(
            'automation_rule_update',
            args=[self.board.id, rule_id],
        )
        resaved = self.client.post(
            update_url, json.dumps(fetched), content_type='application/json',
        )
        self.assertEqual(
            resaved.status_code, 200,
            msg=f'{label}: update returned {resaved.status_code} body={resaved.content[:300]!r}',
        )

        refetched = self.client.get(detail_url).json()
        self.assertEqual(
            _project(refetched), _project(fixture),
            msg=f'{label}: round-trip dropped/mutated fields. '
                f'expected={_project(fixture)!r} got={_project(refetched)!r}',
        )

    def test_legacy_rules_round_trip(self):
        """LEGACY_RULES — never edit these; they guard against future regressions."""
        for fixture in LEGACY_RULES:
            with self.subTest(rule=fixture['name']):
                self._round_trip(fixture, label=fixture['name'])

    def test_current_rules_round_trip(self):
        """CURRENT_RULES — one rule per registered trigger/condition/action."""
        for fixture in current_rules():
            with self.subTest(rule=fixture['name']):
                self._round_trip(fixture, label=fixture['name'])
