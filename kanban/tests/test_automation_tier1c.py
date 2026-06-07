"""
Tier 1c Condition Battery — Resource/Cost/Workload + Board-scoped (matrix).

Covers Battery 4 (9) + Battery 5 (5) = 14 condition attributes via the registry
entry point ``automation_conditions.evaluate(...)`` against real DB fixtures.

Battery 4: workload_impact, skill_match_score, required_skills,
           collaboration_required, estimated_cost, estimated_hours, hours_logged,
           cost_variance_pct, assignee_workload
Battery 5 (board-scoped, requires='board'): board_has_active_conflicts,
           board_immunity_score, board_scope_creep_pct, board_velocity_trend,
           board_predicted_overrun_days

Run under pytest (``kanban_board.test_settings``):

    python -m pytest kanban/tests/test_automation_tier1c.py -v
"""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from kanban.tests.test_automation_tier1a import _ConditionTestBase


class Tier1cResourceConditionsTest(_ConditionTestBase):
    """Battery 4 — resource, cost & workload conditions."""

    def test_workload_impact(self):
        t = self._task(workload_impact='high')
        self._assert('workload_impact', 'is', 'high', t, True)
        self._assert('workload_impact', 'is', 'low', t, False)
        self._assert('workload_impact', 'is_at_least', 'medium', t, True)
        self._assert('workload_impact', 'is_at_least', 'critical', t, False)
        self._assert('workload_impact', 'is_at_least', 'high', t, True)

    def test_skill_match_score(self):
        t = self._task(skill_match_score=70)
        self._assert('skill_match_score', 'gte', '70', t, True)
        self._assert('skill_match_score', 'gte', '71', t, False)
        self._assert('skill_match_score', 'lte', '70', t, True)
        self._assert('skill_match_score', 'lte', '69', t, False)

    def test_required_skills(self):
        t = self._task(required_skills=[{'name': 'Python', 'level': 'Intermediate'},
                                        {'name': 'Django', 'level': 'Advanced'}])
        self._assert('required_skills', 'is_not_empty', None, t, True)
        self._assert('required_skills', 'contains', 'python', t, True)
        self._assert('required_skills', 'contains', 'rust', t, False)
        self._assert('required_skills', 'count_gte', '2', t, True)
        self._assert('required_skills', 'count_gte', '3', t, False)
        empty = self._task(required_skills=[])
        self._assert('required_skills', 'is_empty', None, empty, True)
        self._assert('required_skills', 'is_not_empty', None, empty, False)

    def test_collaboration_required(self):
        yes = self._task(collaboration_required=True)
        no = self._task(collaboration_required=False)
        self._assert('collaboration_required', 'is_true', None, yes, True)
        self._assert('collaboration_required', 'is_false', None, yes, False)
        self._assert('collaboration_required', 'is_true', None, no, False)
        self._assert('collaboration_required', 'is_false', None, no, True)

    def test_estimated_cost(self):
        from kanban.budget_models import TaskCost
        t = self._task()
        TaskCost.objects.create(task=t, estimated_cost=Decimal('5000.00'))
        self._assert('estimated_cost', 'gte', '5000', t, True)
        self._assert('estimated_cost', 'gte', '5001', t, False)
        self._assert('estimated_cost', 'lte', '5000', t, True)
        self._assert('estimated_cost', 'lte', '4999', t, False)
        # No TaskCost row → handler degrades to 0.0.
        nocost = self._task()
        self._assert('estimated_cost', 'lte', '0', nocost, True)
        self._assert('estimated_cost', 'gte', '1', nocost, False)

    def test_estimated_hours(self):
        from kanban.budget_models import TaskCost
        t = self._task()
        TaskCost.objects.create(task=t, estimated_hours=Decimal('12.00'))
        self._assert('estimated_hours', 'gte', '12', t, True)
        self._assert('estimated_hours', 'gte', '13', t, False)
        self._assert('estimated_hours', 'lte', '12', t, True)
        self._assert('estimated_hours', 'lte', '11', t, False)

    def test_hours_logged(self):
        from kanban.budget_models import TimeEntry
        t = self._task()
        today = timezone.now().date()
        TimeEntry.objects.create(task=t, user=self.tester,
                                 hours_spent=Decimal('3.00'), work_date=today)
        TimeEntry.objects.create(task=t, user=self.tester,
                                 hours_spent=Decimal('2.50'), work_date=today)
        # Sum = 5.5
        self._assert('hours_logged', 'gte', '5', t, True)
        self._assert('hours_logged', 'gte', '6', t, False)
        self._assert('hours_logged', 'lte', '6', t, True)
        self._assert('hours_logged', 'lte', '5', t, False)

    def test_cost_variance_pct(self):
        from kanban.budget_models import TaskCost
        t = self._task()
        # est 1000, actual 1200 → +20% variance
        TaskCost.objects.create(task=t, estimated_cost=Decimal('1000.00'),
                                actual_cost=Decimal('1200.00'))
        self._assert('cost_variance_pct', 'gte', '20', t, True)
        self._assert('cost_variance_pct', 'gte', '21', t, False)
        self._assert('cost_variance_pct', 'lte', '20', t, True)
        self._assert('cost_variance_pct', 'lte', '19', t, False)
        # No estimate → division guard returns False.
        noest = self._task()
        TaskCost.objects.create(task=noest, estimated_cost=Decimal('0.00'),
                                actual_cost=Decimal('500.00'))
        self._assert('cost_variance_pct', 'gte', '1', noest, False)

    def test_assignee_workload(self):
        # Three open tasks + one done for priya → workload = 3.
        for i in range(3):
            self._task(title=f'open{i}', assigned_to=self.priya, progress=10)
        self._task(title='done', assigned_to=self.priya, progress=100)
        probe = self._task(title='probe', assigned_to=self.priya, progress=10)
        # probe itself is open too → 4 open assigned to priya.
        self._assert('assignee_workload', 'gte', '4', probe, True)
        self._assert('assignee_workload', 'gte', '5', probe, False)
        self._assert('assignee_workload', 'lte', '4', probe, True)
        self._assert('assignee_workload', 'lte', '3', probe, False)
        # Unassigned task → handler returns False.
        un = self._task(title='un', assigned_to=None)
        self._assert('assignee_workload', 'gte', '0', un, False)


class Tier1cBoardConditionsTest(_ConditionTestBase):
    """Battery 5 — board-scoped conditions (requires='board')."""

    def _board_target(self, task=None):
        from kanban.automation_conditions import TriggerTarget
        return TriggerTarget(target_board=self.board, target_task=task,
                             source=task or self.board,
                             source_type='task' if task else 'board')

    def _bassert(self, attr, operator, value, expected, task=None):
        from kanban.automation_conditions import evaluate
        got = evaluate(attr, operator, value, self._board_target(task))
        self.assertEqual(
            got, expected,
            f'{attr} {operator} {value!r}: expected {expected}, got {got}')

    def test_board_has_active_conflicts(self):
        from kanban.conflict_models import ConflictDetection
        # No conflicts yet.
        self._bassert('board_has_active_conflicts', 'is_false', None, True)
        self._bassert('board_has_active_conflicts', 'is_true', None, False)
        ConflictDetection.objects.create(
            board=self.board, conflict_type='resource', status='active',
            title='c1', description='d')
        ConflictDetection.objects.create(
            board=self.board, conflict_type='schedule', status='resolved',
            title='c2', description='d')
        # Only the active one counts.
        self._bassert('board_has_active_conflicts', 'is_true', None, True)
        self._bassert('board_has_active_conflicts', 'count_gte', '1', True)
        self._bassert('board_has_active_conflicts', 'count_gte', '2', False)

    def test_board_immunity_score(self):
        from kanban.stress_test_models import StressTestSession, ImmunityScore
        # No score → False.
        self._bassert('board_immunity_score', 'gte', '50', False)
        session = StressTestSession.objects.create(board=self.board, run_by=self.tester)
        ImmunityScore.objects.create(
            session=session, overall=85, schedule=80, budget=80,
            team=80, dependencies=80, scope_stability=80)
        self._bassert('board_immunity_score', 'gte', '80', True)
        self._bassert('board_immunity_score', 'gte', '90', False)
        self._bassert('board_immunity_score', 'lte', '90', True)
        self._bassert('board_immunity_score', 'lte', '80', False)

    def test_board_scope_creep_pct(self):
        from kanban.models import Task
        # Baseline of 2 tasks; create 3 → +50% scope change.
        self.board.baseline_task_count = 2
        self.board.save(update_fields=['baseline_task_count'])
        for i in range(3):
            self._task(title=f'scope{i}', item_type='task')
        self._bassert('board_scope_creep_pct', 'gte', '50', True)
        self._bassert('board_scope_creep_pct', 'gte', '51', False)
        self._bassert('board_scope_creep_pct', 'lte', '50', True)

    def test_board_velocity_trend(self):
        from kanban.burndown_models import TeamVelocitySnapshot
        today = timezone.now().date()

        def snap(end_offset, points):
            return TeamVelocitySnapshot.objects.create(
                board=self.board,
                period_start=today - timedelta(days=end_offset + 7),
                period_end=today - timedelta(days=end_offset),
                story_points_completed=Decimal(str(points)))

        # Oldest = 10 pts, newest = 20 pts → latest > prior*1.10 → 'improving'.
        snap(14, 10)
        snap(7, 15)
        snap(0, 20)
        self._bassert('board_velocity_trend', 'is', 'improving', True)
        self._bassert('board_velocity_trend', 'is', 'declining', False)

    def test_board_predicted_overrun_days(self):
        from kanban.burndown_models import BurndownPrediction
        today = timezone.now().date()
        self.board.project_deadline = today
        self.board.save(update_fields=['project_deadline'])
        pred = today + timedelta(days=10)
        BurndownPrediction.objects.create(
            board=self.board,
            predicted_completion_date=pred,
            completion_date_lower_bound=pred - timedelta(days=2),
            completion_date_upper_bound=pred + timedelta(days=2))
        # Predicted 10 days past deadline.
        self._bassert('board_predicted_overrun_days', 'gte', '10', True)
        self._bassert('board_predicted_overrun_days', 'gte', '11', False)
