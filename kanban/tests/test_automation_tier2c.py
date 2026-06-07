"""
Tier 2c Action Battery — engine-level regression suite.

Covers the 12 actions in two automation builder groups:
  - AI & Risk (5): set_risk_level, request_ai_analysis, flag_for_review,
    add_risk_indicator, add_mitigation_strategy
  - AI Tools & Platform (7): acknowledge_coach_suggestion, resolve_conflict,
    promote_discovery_idea, apply_stress_test_vaccine, create_memory_node,
    generate_status_report, add_stakeholder_engagement

None of these call the LLM synchronously (see test_automation_no_sync_ai.py);
they are field writes, comments, ORM status updates and record creation, so the
suite needs no AI mocking. Most fire via task_assigned; promote_discovery_idea
fires via its native discovery_idea_submitted trigger (task_assigned would
_ActionSkip).

Hermetic: each test builds its own org/board/scaffolding in a rolled-back
transaction. Run under pytest (kanban_board.test_settings):

    python -m pytest kanban/tests/test_automation_tier2c.py -v
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone


class Tier2cAiRiskPlatformActionsTest(TestCase):
    """C-01 … C-12 — AI & Risk + AI Tools & Platform."""

    def setUp(self):
        from accounts.models import Organization
        from kanban.automation_models import AutomationRule
        from kanban.models import Board, Column

        self.AutomationRule = AutomationRule

        self.tester = User.objects.create_user(
            username='t2c_tester', password='x', email='t2c_tester@example.com')
        self.alice = User.objects.create_user(
            username='t2c_alice', password='x', email='t2c_alice@example.com')

        self.org = Organization.objects.create(name='Tier2c Org', created_by=self.tester)
        self.board = Board.objects.create(
            name='Tier2c Board', organization=self.org, created_by=self.tester)
        self.cols = {}
        for pos, name in enumerate(['To Do', 'In Progress', 'Done']):
            self.cols[name] = Column.objects.create(board=self.board, name=name, position=pos)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _make_rule(self, name, actions, trigger_type='task_assigned'):
        return self.AutomationRule.objects.create(
            board=self.board, created_by=self.tester, name=name,
            trigger_type=trigger_type, trigger_config={},
            conditions=[], condition_logic='AND',
            actions=actions, otherwise_actions=[], is_active=True,
        )

    def _task(self, **kw):
        from kanban.models import Task
        kw.setdefault('column', self.cols['To Do'])
        kw.setdefault('created_by', self.tester)
        kw.setdefault('assigned_to', self.tester)
        kw.setdefault('title', 'TIER2C-TASK')
        return Task.objects.create(**kw)

    def _fire(self, task, new_assignee):
        from kanban.models import Task
        fresh = Task.objects.get(pk=task.pk)
        fresh.assigned_to = new_assignee
        fresh.save()

    def _assert_log(self, rule, task=None, outcome='success'):
        from kanban.automation_models import AutomationLog
        qs = AutomationLog.objects.filter(rule=rule)
        if task is not None:
            qs = qs.filter(task_affected=task)
        self.assertEqual(qs.count(), 1,
                         f'expected 1 log, got {list(qs.values_list("outcome", flat=True))}')
        self.assertEqual(qs.first().outcome, outcome)

    def _reload(self, obj):
        return type(obj).objects.get(pk=obj.pk)

    # ───────────────────────────── AI & Risk ────────────────────────────────

    def test_c01_set_risk_level(self):
        task = self._task()
        rule = self._make_rule('TIER2C-C01: Set risk level',
                               [{'type': 'set_risk_level', 'target': 'high'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task)
        self.assertEqual(self._reload(task).risk_level, 'high')

    def test_c02_request_ai_analysis(self):
        from kanban.models import Task
        task = self._task()
        Task.objects.filter(pk=task.pk).update(last_ai_analysis=timezone.now())  # seed non-null
        rule = self._make_rule('TIER2C-C02: Request AI analysis',
                               [{'type': 'request_ai_analysis'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task)
        self.assertIsNone(self._reload(task).last_ai_analysis)

    def test_c03_flag_for_review(self):
        from kanban.models import Comment
        task = self._task()
        rule = self._make_rule('TIER2C-C03: Flag for review',
                               [{'type': 'flag_for_review', 'message': 'Please review'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task)
        self.assertIn('Needs Review', self._reload(task).labels.values_list('name', flat=True))
        self.assertTrue(Comment.objects.filter(task=task).exists())

    def test_c04_add_risk_indicator(self):
        task = self._task()
        rule = self._make_rule('TIER2C-C04: Add risk indicator',
                               [{'type': 'add_risk_indicator', 'target': 'Single point of failure'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task)
        self.assertIn('Single point of failure', self._reload(task).risk_indicators)

    def test_c05_add_mitigation_strategy(self):
        from kanban.models import Comment
        task = self._task()
        rule = self._make_rule('TIER2C-C05: Add mitigation strategy',
                               [{'type': 'add_mitigation_strategy', 'target': 'Add a standby replica'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task)
        self.assertTrue(
            Comment.objects.filter(task=task, content__startswith='mitigation: ').exists())

    # ───────────────────────── AI Tools & Platform ──────────────────────────

    def test_c06_acknowledge_coach_suggestion(self):
        from kanban.coach_models import CoachingSuggestion
        s1 = CoachingSuggestion.objects.create(
            board=self.board, suggestion_type='velocity_drop',
            title='Velocity dropping', message='Down 20%', status='active')
        s2 = CoachingSuggestion.objects.create(
            board=self.board, suggestion_type='deadline_risk',
            title='Deadline at risk', message='Slipping', status='active')
        task = self._task()
        rule = self._make_rule('TIER2C-C06: Acknowledge coach suggestion',
                               [{'type': 'acknowledge_coach_suggestion'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task)
        self.assertEqual(self._reload(s1).status, 'acknowledged')
        self.assertEqual(self._reload(s2).status, 'acknowledged')

    def test_c06b_acknowledge_no_active_skips(self):
        task = self._task()
        rule = self._make_rule('TIER2C-C06b: Acknowledge (none active)',
                               [{'type': 'acknowledge_coach_suggestion'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task, outcome='skipped')

    def test_c07_resolve_conflict(self):
        from kanban.conflict_models import ConflictDetection
        conflict = ConflictDetection.objects.create(
            board=self.board, conflict_type='schedule',
            title='Schedule overlap', description='Two tasks overlap', status='active')
        task = self._task()
        rule = self._make_rule('TIER2C-C07: Resolve conflict',
                               [{'type': 'resolve_conflict', 'message': 'Handled'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task)
        self.assertEqual(self._reload(conflict).status, 'resolved')

    def test_c08_promote_discovery_idea(self):
        from kanban.discovery_models import DiscoveryIdea
        rule = self._make_rule('TIER2C-C08: Promote discovery idea',
                               [{'type': 'promote_discovery_idea'}],
                               trigger_type='discovery_idea_submitted')
        idea = DiscoveryIdea.objects.create(
            organization=self.org, title='Add dark mode', submitted_by=self.tester)
        self.assertEqual(self._reload(idea).stage, 'approved')
        self._assert_log(rule)  # source-triggered: no task_affected

    def test_c09_apply_stress_test_vaccine(self):
        from kanban.stress_test_models import StressTestSession, Vaccine
        session = StressTestSession.objects.create(board=self.board, run_by=self.tester)
        vaccine = Vaccine.objects.create(
            session=session, board=self.board, vaccine_number=1,
            targets_scenario_number=1, name='Add buffer',
            description='Increase capacity', effort_level='MEDIUM', is_applied=False)
        task = self._task()
        rule = self._make_rule('TIER2C-C09: Apply stress-test vaccine',
                               [{'type': 'apply_stress_test_vaccine'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task)
        self.assertTrue(self._reload(vaccine).is_applied)

    def test_c09b_apply_vaccine_none_skips(self):
        task = self._task()
        rule = self._make_rule('TIER2C-C09b: Apply vaccine (none)',
                               [{'type': 'apply_stress_test_vaccine'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task, outcome='skipped')

    def test_c10_create_memory_node(self):
        from knowledge_graph.models import MemoryNode
        task = self._task()
        rule = self._make_rule('TIER2C-C10: Create memory node',
                               [{'type': 'create_memory_node', 'target': 'decision',
                                 'message': 'Chose option A'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task)
        self.assertTrue(MemoryNode.objects.filter(
            node_type='decision', is_auto_captured=True,
            title__startswith='Auto-captured: TIER2C-C10').exists())

    def test_c11_generate_status_report(self):
        from kanban.prizmbrief_models import SavedBrief
        task = self._task()
        rule = self._make_rule('TIER2C-C11: Generate status report',
                               [{'type': 'generate_status_report', 'target': 'team'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task)
        self.assertTrue(SavedBrief.objects.filter(board=self.board, user=self.tester).exists())

    def test_c12_add_stakeholder_engagement(self):
        from kanban.stakeholder_models import ProjectStakeholder, StakeholderEngagementRecord
        sh = ProjectStakeholder.objects.create(
            board=self.board, name='Jane Doe', role='Sponsor',
            created_by=self.tester, is_active=True)
        task = self._task()
        rule = self._make_rule('TIER2C-C12: Add stakeholder engagement',
                               [{'type': 'add_stakeholder_engagement', 'message': 'Milestone reached'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task)
        self.assertTrue(StakeholderEngagementRecord.objects.filter(stakeholder=sh).exists())
