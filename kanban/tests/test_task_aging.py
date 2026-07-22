"""
Task Aging / Stalling Detection tests.

Covers:
  * Column.effective_aging() resolution: inherit / custom / disabled, board disabled,
    and the DERIVED grey "show" threshold (ceil(warning/2), min 1).
  * BoardForm validation: critical must exceed warning.
  * create_column auto-disables aging for Done/Backlog-style names.
  * column_update_aging endpoint: happy paths, validation, RBAC (non-member 403).
"""

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse

from datetime import timedelta
from django.utils import timezone

from accounts.models import Organization, UserProfile
from kanban.models import (
    Board, Column, Task,
    column_name_disables_aging,
)
from kanban.forms import BoardForm


def _make_tenant(slug, *, warning=7, critical=14, aging_enabled=True):
    user = User.objects.create_user(username=f'{slug}_user', password='pw',
                                    email=f'{slug}@example.com')
    org = Organization.objects.create(name=f'{slug} Org', created_by=user)
    from kanban.models import Workspace
    ws = Workspace.objects.create(name=f"{slug} WS", organization=org,
                                  created_by=user, is_demo=False)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.organization = org
    profile.active_workspace = ws
    profile.is_viewing_demo = False
    profile.save()
    board = Board.objects.create(
        name=f'{slug} Board', created_by=user, owner=user,
        organization=org, workspace=ws,
        aging_enabled=aging_enabled, aging_warning_days=warning, aging_critical_days=critical,
    )
    col = Column.objects.create(board=board, name='In Progress', position=0)
    return {'user': user, 'org': org, 'ws': ws, 'board': board, 'col': col}


class EffectiveAgingTest(TestCase):
    def test_inherit_uses_board_defaults_and_derives_show(self):
        t = _make_tenant('alpha', warning=7, critical=14)
        eff = t['col'].effective_aging()
        self.assertTrue(eff['enabled'])
        self.assertEqual(eff['warning'], 7)
        self.assertEqual(eff['critical'], 14)
        self.assertEqual(eff['show'], 4)  # ceil(7/2)

    def test_show_threshold_minimum_one(self):
        t = _make_tenant('beta', warning=1, critical=3)
        self.assertEqual(t['col'].effective_aging()['show'], 1)

    def test_custom_overrides_board(self):
        t = _make_tenant('gamma', warning=7, critical=14)
        col = t['col']
        col.aging_mode = 'custom'
        col.aging_warning_days = 2
        col.aging_critical_days = 5
        col.save()
        eff = col.effective_aging()
        self.assertEqual((eff['warning'], eff['critical'], eff['show']), (2, 5, 1))

    def test_disabled_column(self):
        t = _make_tenant('delta')
        t['col'].aging_mode = 'disabled'
        t['col'].save()
        self.assertFalse(t['col'].effective_aging()['enabled'])

    def test_board_disabled_overrides_inherit(self):
        t = _make_tenant('epsilon', aging_enabled=False)
        self.assertFalse(t['col'].effective_aging()['enabled'])

    def test_custom_with_missing_values_falls_back_to_board(self):
        t = _make_tenant('zeta', warning=9, critical=20)
        col = t['col']
        col.aging_mode = 'custom'  # but no custom values set
        col.save()
        eff = col.effective_aging()
        self.assertEqual((eff['warning'], eff['critical']), (9, 20))


class DoneBacklogHelperTest(TestCase):
    def test_keywords_match(self):
        for name in ['Done', 'COMPLETED', 'Closed', 'Backlog', 'Archive',
                     'Shipped', 'Deployed', 'Released', 'Cancelled', 'Canceled']:
            self.assertTrue(column_name_disables_aging(name), name)

    def test_normal_names_do_not_match(self):
        for name in ['In Progress', 'To Do', 'Review', 'QA']:
            self.assertFalse(column_name_disables_aging(name), name)


class BoardFormValidationTest(TestCase):
    def _data(self, warning, critical, enabled=True):
        return {
            'name': 'B', 'description': '', 'num_phases': 0,
            'aging_enabled': enabled,
            'aging_warning_days': warning, 'aging_critical_days': critical,
        }

    def test_critical_must_exceed_warning(self):
        self.assertFalse(BoardForm(data=self._data(10, 10)).is_valid())
        self.assertFalse(BoardForm(data=self._data(10, 5)).is_valid())

    def test_valid_thresholds(self):
        self.assertTrue(BoardForm(data=self._data(7, 14)).is_valid())

    def test_disabled_skips_threshold_validation(self):
        # When disabled, an inverted pair shouldn't block saving.
        self.assertTrue(BoardForm(data=self._data(10, 5, enabled=False)).is_valid())


class CreateColumnDefaultDisableTest(TestCase):
    def test_done_column_created_disabled(self):
        t = _make_tenant('eta')
        client = Client()
        client.force_login(t['user'])
        resp = client.post(reverse('create_column', args=[t['board'].id]), {'name': 'Done'})
        self.assertin_status(resp)
        col = Column.objects.get(board=t['board'], name='Done')
        self.assertEqual(col.aging_mode, 'disabled')

    def test_normal_column_inherits(self):
        t = _make_tenant('theta')
        client = Client()
        client.force_login(t['user'])
        client.post(reverse('create_column', args=[t['board'].id]), {'name': 'Review'})
        col = Column.objects.get(board=t['board'], name='Review')
        self.assertEqual(col.aging_mode, 'inherit')

    def assertin_status(self, resp):
        self.assertIn(resp.status_code, (200, 302))


class ColumnUpdateAgingEndpointTest(TestCase):
    def _post(self, client, col, **data):
        return client.post(reverse('column_update_aging', args=[col.id]), data)

    def test_set_custom(self):
        t = _make_tenant('iota')
        client = Client()
        client.force_login(t['user'])
        resp = self._post(client, t['col'], aging_mode='custom',
                          aging_warning_days=3, aging_critical_days=6)
        self.assertEqual(resp.status_code, 200)
        t['col'].refresh_from_db()
        self.assertEqual(t['col'].aging_mode, 'custom')
        self.assertEqual(t['col'].aging_warning_days, 3)

    def test_custom_rejects_inverted_thresholds(self):
        t = _make_tenant('kappa')
        client = Client()
        client.force_login(t['user'])
        resp = self._post(client, t['col'], aging_mode='custom',
                          aging_warning_days=6, aging_critical_days=3)
        self.assertEqual(resp.status_code, 400)
        t['col'].refresh_from_db()
        self.assertEqual(t['col'].aging_mode, 'inherit')  # unchanged

    def test_disabled_clears_custom_values(self):
        t = _make_tenant('lam')
        col = t['col']
        col.aging_mode = 'custom'
        col.aging_warning_days = 3
        col.aging_critical_days = 6
        col.save()
        client = Client()
        client.force_login(t['user'])
        self._post(client, col, aging_mode='disabled')
        col.refresh_from_db()
        self.assertEqual(col.aging_mode, 'disabled')
        self.assertIsNone(col.aging_warning_days)

    def test_non_member_forbidden(self):
        owner = _make_tenant('mu')
        attacker = _make_tenant('nu')
        client = Client()
        client.force_login(attacker['user'])
        resp = self._post(client, owner['col'], aging_mode='disabled')
        self.assertEqual(resp.status_code, 403)
        owner['col'].refresh_from_db()
        self.assertEqual(owner['col'].aging_mode, 'inherit')


def _make_task(col, *, days_ago=None, progress=0, item_type='task',
               milestone_status=None, title='T'):
    """Create a task whose column_entered_at is `days_ago` in the past.

    column_entered_at is passed at create time so the track_column_entry_time
    pre_save signal preserves it (it only stamps now() when the field is unset).
    """
    entered = None if days_ago is None else timezone.now() - timedelta(days=days_ago)
    task = Task.objects.create(
        column=col, title=title, progress=progress, item_type=item_type,
        milestone_status=milestone_status, column_entered_at=entered,
        created_by=col.board.created_by,
    )
    if entered is None:
        # The track_column_entry_time pre_save signal stamps now() on create when
        # the field is unset; force a true NULL (as legacy pre-migration tasks have)
        # via an UPDATE that bypasses the signal.
        Task.objects.filter(pk=task.pk).update(column_entered_at=None)
        task.refresh_from_db()
    return task


class AgingStateTest(TestCase):
    """Task.aging_state() — the single source of truth shared by Spectra,
    Focus Today and the Decision Center. Mirrors kanban_aging.js badge tiers."""

    def test_tiers_by_days(self):
        t = _make_tenant('as_alpha', warning=7, critical=14)  # show=4
        col = t['col']
        self.assertEqual(_make_task(col, days_ago=2).aging_state()['tier'], 'fresh')
        self.assertEqual(_make_task(col, days_ago=5).aging_state()['tier'], 'show')
        self.assertEqual(_make_task(col, days_ago=9).aging_state()['tier'], 'warning')
        st = _make_task(col, days_ago=20).aging_state()
        self.assertEqual(st['tier'], 'critical')
        self.assertEqual(st['days'], 20)
        self.assertEqual((st['warning'], st['critical']), (7, 14))

    def test_disabled_column_is_not_enabled(self):
        t = _make_tenant('as_beta')
        t['col'].aging_mode = 'disabled'
        t['col'].save()
        st = _make_task(t['col'], days_ago=30).aging_state()
        self.assertFalse(st['enabled'])
        self.assertEqual(st['tier'], 'fresh')

    def test_null_column_entered_at(self):
        t = _make_tenant('as_gamma')
        st = _make_task(t['col'], days_ago=None).aging_state()
        self.assertFalse(st['enabled'])
        self.assertIsNone(st['days'])

    def test_completed_task_not_stalled(self):
        t = _make_tenant('as_delta')
        st = _make_task(t['col'], days_ago=30, progress=100).aging_state()
        self.assertFalse(st['enabled'])

    def test_completed_milestone_not_stalled(self):
        t = _make_tenant('as_eps')
        st = _make_task(t['col'], days_ago=30, item_type='milestone',
                        milestone_status='completed').aging_state()
        self.assertFalse(st['enabled'])


class StalledForBoardsTest(TestCase):
    def test_warning_tier_floor_and_ordering(self):
        t = _make_tenant('sf_alpha', warning=7, critical=14)
        col = t['col']
        _make_task(col, days_ago=2, title='fresh')       # below show — excluded
        _make_task(col, days_ago=5, title='show')         # show tier — excluded at warning floor
        warn = _make_task(col, days_ago=9, title='warn')
        crit = _make_task(col, days_ago=20, title='crit')
        result = Task.stalled_for_boards([t['board'].id], tier='warning')
        self.assertEqual([x.title for x in result], ['crit', 'warn'])  # oldest first
        self.assertEqual(result[0].days_in_column, 20)
        self.assertEqual(crit.id, result[0].id)
        self.assertEqual(warn.id, result[1].id)

    def test_critical_tier_floor(self):
        t = _make_tenant('sf_beta', warning=7, critical=14)
        col = t['col']
        _make_task(col, days_ago=9, title='warn')   # excluded at critical floor
        _make_task(col, days_ago=20, title='crit')
        result = Task.stalled_for_boards([t['board'].id], tier='critical')
        self.assertEqual([x.title for x in result], ['crit'])

    def test_completed_excluded(self):
        t = _make_tenant('sf_gamma', warning=7, critical=14)
        _make_task(t['col'], days_ago=20, progress=100, title='done')
        self.assertEqual(Task.stalled_for_boards([t['board'].id]), [])


class StalledBriefingPlanTest(TestCase):
    """Focus Today rule-based action plan for the 'stalled' action type speaks to
    column dwell, not deadlines (kanban/ai_briefing.py)."""

    def test_rule_based_plan_uses_column_dwell_wording(self):
        # Test the rule-based functions directly so no live Gemini call is made.
        from kanban.ai_briefing import _rule_based_action_plan, _rule_based_summary
        t = _make_tenant('br_alpha', warning=7, critical=14)
        task = _make_task(t['col'], days_ago=12, progress=30, title='Migrate API')
        task.days_in_column = 12  # set by the view from aging_state()

        plan = _rule_based_action_plan([task], 'stalled', 0, timezone.now())
        self.assertEqual(len(plan), 1)
        why = plan[0]['why'].lower()
        self.assertIn('12 days', why)
        self.assertIn('in progress', why)  # the column name
        self.assertNotIn('overdue', why)   # not framed around deadlines

        summary = _rule_based_summary(plan, 'stalled', 0, '')
        self.assertIn('stopped moving', summary.lower())
