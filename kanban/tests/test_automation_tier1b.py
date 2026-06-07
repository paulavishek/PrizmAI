"""
Tier 1b Condition Battery — Risk/AI prediction + Hierarchy/Dependency (matrix).

Covers Battery 2 (8) + Battery 3 (9) = 17 condition attributes via the registry
entry point ``automation_conditions.evaluate(...)`` against real DB fixtures.

Battery 2: risk_level, risk_score, predicted_completion, prediction_confidence,
           complexity_score, schedule_status, lss_classification, ai_risk_score
Battery 3: parent_status, subtask_count, subtask_completion_pct, has_dependencies,
           has_blocked_tasks, dependency_status, item_type, phase, is_root_task

Run under pytest (``kanban_board.test_settings``):

    python -m pytest kanban/tests/test_automation_tier1b.py -v
"""

from datetime import timedelta

from django.utils import timezone

from kanban.tests.test_automation_tier1a import _ConditionTestBase


class Tier1bRiskAiConditionsTest(_ConditionTestBase):
    """Battery 2 — risk & AI-prediction conditions."""

    def test_risk_level(self):
        t = self._task(risk_level='high')
        self._assert('risk_level', 'is', 'high', t, True)
        self._assert('risk_level', 'is', 'High', t, True)            # case-insensitive
        self._assert('risk_level', 'is', 'low', t, False)
        self._assert('risk_level', 'is_not', 'low', t, True)
        self._assert('risk_level', 'is_at_least', 'medium', t, True)  # high >= medium
        self._assert('risk_level', 'is_at_least', 'critical', t, False)
        self._assert('risk_level', 'is_at_least', 'high', t, True)

    def test_risk_score(self):
        t = self._task(risk_score=6)
        self._assert('risk_score', 'gte', '6', t, True)
        self._assert('risk_score', 'gte', '7', t, False)
        self._assert('risk_score', 'lte', '6', t, True)
        self._assert('risk_score', 'lte', '5', t, False)
        self._assert('risk_score', 'equals', '6', t, True)
        self._assert('risk_score', 'equals', '5', t, False)

    def test_predicted_completion(self):
        due = timezone.now() + timedelta(days=10)
        early = self._task(due_date=due,
                           predicted_completion_date=due - timedelta(days=3))
        late = self._task(due_date=due,
                          predicted_completion_date=due + timedelta(days=3))
        self._assert('predicted_completion', 'before_due', None, early, True)
        self._assert('predicted_completion', 'before_due', None, late, False)
        self._assert('predicted_completion', 'after_due', None, late, True)
        self._assert('predicted_completion', 'after_due', None, early, False)
        self._assert('predicted_completion', 'within_days_of_due', '5', late, True)
        self._assert('predicted_completion', 'within_days_of_due', '2', late, False)

    def test_prediction_confidence(self):
        t = self._task(prediction_confidence=0.8)
        self._assert('prediction_confidence', 'gte', '0.5', t, True)
        self._assert('prediction_confidence', 'gte', '0.9', t, False)
        self._assert('prediction_confidence', 'lte', '0.9', t, True)
        self._assert('prediction_confidence', 'lte', '0.5', t, False)
        # Percentage form (50) is normalised to the 0–1 scale.
        self._assert('prediction_confidence', 'gte', '50', t, True)
        self._assert('prediction_confidence', 'lte', '50', t, False)

    def test_complexity_score(self):
        t = self._task(complexity_score=8)
        self._assert('complexity_score', 'gte', '8', t, True)
        self._assert('complexity_score', 'gte', '9', t, False)
        self._assert('complexity_score', 'lte', '8', t, True)
        self._assert('complexity_score', 'lte', '7', t, False)
        self._assert('complexity_score', 'equals', '8', t, True)
        self._assert('complexity_score', 'equals', '7', t, False)

    def test_schedule_status(self):
        # progress_status is computed: past-due & <100% → 'late'; 100% → 'on_track'.
        late = self._task(progress=40, due_date=timezone.now() - timedelta(days=2))
        self._assert('schedule_status', 'is', 'late', late, True)
        self._assert('schedule_status', 'is', 'on_track', late, False)
        on_track = self._task(progress=100, due_date=timezone.now() + timedelta(days=5))
        self._assert('schedule_status', 'is', 'on_track', on_track, True)
        self._assert('schedule_status', 'is', 'late', on_track, False)

    def test_lss_classification(self):
        t = self._task(lss_classification='value_added')
        self._assert('lss_classification', 'is', 'value_added', t, True)
        self._assert('lss_classification', 'is', 'waste', t, False)
        self._assert('lss_classification', 'is_not', 'waste', t, True)
        self._assert('lss_classification', 'is_not', 'value_added', t, False)

    def test_ai_risk_score(self):
        t = self._task(ai_risk_score=80)
        self._assert('ai_risk_score', 'gte', '80', t, True)
        self._assert('ai_risk_score', 'gte', '81', t, False)
        self._assert('ai_risk_score', 'lte', '80', t, True)
        self._assert('ai_risk_score', 'lte', '79', t, False)


class Tier1bHierarchyConditionsTest(_ConditionTestBase):
    """Battery 3 — hierarchy & dependency conditions."""

    def test_parent_status(self):
        parent = self._task(title='parent', column=self.cols['In Review'])
        child = self._task(title='child', parent_task=parent)
        self._assert('parent_status', 'is', 'In Review', child, True)
        self._assert('parent_status', 'is', 'To Do', child, False)
        self._assert('parent_status', 'is_not', 'To Do', child, True)
        self._assert('parent_status', 'is_not', 'In Review', child, False)
        # No parent → handler returns False for any operator.
        root = self._task(title='root')
        self._assert('parent_status', 'is', 'In Review', root, False)

    def test_subtask_count(self):
        parent = self._task(title='p')
        self._task(title='s1', parent_task=parent)
        self._task(title='s2', parent_task=parent)
        self._assert('subtask_count', 'equals', '2', parent, True)
        self._assert('subtask_count', 'equals', '3', parent, False)
        self._assert('subtask_count', 'gte', '2', parent, True)
        self._assert('subtask_count', 'gte', '3', parent, False)
        self._assert('subtask_count', 'lte', '2', parent, True)
        self._assert('subtask_count', 'lte', '1', parent, False)

    def test_subtask_completion_pct(self):
        parent = self._task(title='p')
        self._task(title='s1', parent_task=parent, progress=100)
        self._task(title='s2', parent_task=parent, progress=100)
        self._task(title='s3', parent_task=parent, progress=0)
        self._task(title='s4', parent_task=parent, progress=0)
        # 2/4 done → 50%
        self._assert('subtask_completion_pct', 'gte', '50', parent, True)
        self._assert('subtask_completion_pct', 'gte', '51', parent, False)
        self._assert('subtask_completion_pct', 'lte', '50', parent, True)
        self._assert('subtask_completion_pct', 'lte', '49', parent, False)

    def test_has_dependencies(self):
        a = self._task(title='a')
        b = self._task(title='b')
        b.dependencies.add(a)
        self._assert('has_dependencies', 'is_true', None, b, True)
        self._assert('has_dependencies', 'is_false', None, b, False)
        self._assert('has_dependencies', 'is_true', None, a, False)
        self._assert('has_dependencies', 'is_false', None, a, True)

    def test_has_blocked_tasks(self):
        a = self._task(title='a')
        b = self._task(title='b')
        b.dependencies.add(a)            # a blocks b
        self._assert('has_blocked_tasks', 'is_true', None, a, True)
        self._assert('has_blocked_tasks', 'is_false', None, a, False)
        self._assert('has_blocked_tasks', 'is_true', None, b, False)
        self._assert('has_blocked_tasks', 'is_false', None, b, True)

    def test_dependency_status(self):
        host = self._task(title='host')
        done = self._task(title='done', progress=100)
        host.dependencies.add(done)
        self._assert('dependency_status', 'all_complete', None, host, True)

        host2 = self._task(title='host2')
        overdue = self._task(title='overdue', progress=20,
                             due_date=timezone.now() - timedelta(days=2))
        host2.dependencies.add(overdue)
        self._assert('dependency_status', 'all_complete', None, host2, False)
        self._assert('dependency_status', 'any_overdue', None, host2, True)
        self._assert('dependency_status', 'any_overdue', None, host, False)

        # any_blocked: a dependency that itself has an incomplete dependency.
        host3 = self._task(title='host3')
        mid = self._task(title='mid')
        leaf = self._task(title='leaf', progress=10)
        mid.dependencies.add(leaf)
        host3.dependencies.add(mid)
        self._assert('dependency_status', 'any_blocked', None, host3, True)
        # No dependencies at all → False for every operator.
        self._assert('dependency_status', 'all_complete', None, leaf, False)

    def test_item_type(self):
        m = self._task(title='m', item_type='milestone')
        self._assert('item_type', 'is', 'milestone', m, True)
        self._assert('item_type', 'is', 'task', m, False)

    def test_phase(self):
        t = self._task(phase='Phase 1')
        self._assert('phase', 'is', 'Phase 1', t, True)
        self._assert('phase', 'is', 'phase 1', t, True)              # case-insensitive
        self._assert('phase', 'is', 'Phase 2', t, False)
        self._assert('phase', 'is_not', 'Phase 2', t, True)
        self._assert('phase', 'is_not', 'Phase 1', t, False)

    def test_is_root_task(self):
        root = self._task(title='root')
        child = self._task(title='child', parent_task=root)
        self._assert('is_root_task', 'is_true', None, root, True)
        self._assert('is_root_task', 'is_false', None, root, False)
        self._assert('is_root_task', 'is_true', None, child, False)
        self._assert('is_root_task', 'is_false', None, child, True)
