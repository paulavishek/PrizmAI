"""
Regression tests for AI Resource Optimization overload guards.

These lock in the fix for the "assign a brand-new task to the MOST overloaded
member" bug observed on the demo board: the unassigned-task path gated on the
*projected* utilization, which an earlier same-run suggestion can artificially
lower (by moving a task off the overloaded member), letting that member slip
past the <=90% gate while the card still displays their real 105%.

The fix gates on ACTUAL utilization, so an overloaded member is never offered
new work even when their projected utilization has been pulled down within a
generation run.
"""

from django.contrib.auth.models import User
from django.test import TestCase

from kanban.models import Board, Column, Task, Workspace, BoardMembership
from kanban.resource_leveling import ResourceLevelingService
from kanban.resource_leveling_models import UserPerformanceProfile, ResourceLevelingSuggestion


def _board_with_member():
    """A board with one member ('ov') who will be made overloaded."""
    from accounts.models import Organization
    owner = User.objects.create_user(username='ov', password='pw')
    org = Organization.objects.create(name='Org', created_by=owner)
    ws = Workspace.objects.create(name='WS', organization=org, created_by=owner, is_demo=False)
    board = Board.objects.create(name='Board', created_by=owner, owner=owner, workspace=ws)
    BoardMembership.objects.create(board=board, user=owner, role='owner')
    col = Column.objects.create(board=board, name='Backlog', position=0)
    return owner, board, col


def _make_overloaded(user, board, col, total_complexity=42, n=6):
    """Assign `n` active tasks to `user` summing to `total_complexity` complexity
    points → utilization = total/40 * 100 (42 → 105%)."""
    per = total_complexity // n
    rem = total_complexity - per * n
    for i in range(n):
        c = per + (1 if i < rem else 0)
        Task.objects.create(column=col, title=f'load {i}', complexity_score=c,
                            assigned_to=user, created_by=board.created_by)
    # Refresh the profile so utilization reflects the new active tasks.
    return ResourceLevelingService().get_or_create_profile(user, board=board)


class UnassignedTaskOverloadGuardTest(TestCase):
    def test_overloaded_member_not_offered_new_task_despite_projected_drop(self):
        owner, board, col = _board_with_member()
        profile = _make_overloaded(owner, board, col)
        self.assertGreaterEqual(profile.utilization_percentage, 100,
                                'fixture should make the member overloaded')

        unassigned = Task.objects.create(
            column=col, title='Brand New Task', complexity_score=5,
            assigned_to=None, created_by=board.created_by,
        )

        svc = ResourceLevelingService()
        # Simulate the cascade: an earlier suggestion moved a task OFF the
        # overloaded member, dropping their PROJECTED utilization by ~15 pts.
        result = svc.analyze_task_assignment(
            unassigned, temp_workload_adjustments={owner.id: -1},
        )

        # Even though projected utilization is now ~90, actual is 105% — the
        # engine must NOT recommend handing this person a brand-new task.
        self.assertFalse(
            result.get('should_reassign'),
            'overloaded member (105% actual) must not be offered an unassigned task',
        )

    def test_non_overloaded_member_is_offered_the_task(self):
        """Positive control: a member with capacity still gets the assignment,
        so the guard is specific to overload and not a blanket block."""
        owner, board, col = _board_with_member()
        # Light load: 2 complexity points → ~5% utilization.
        Task.objects.create(column=col, title='light', complexity_score=2,
                            assigned_to=owner, created_by=board.created_by)
        profile = ResourceLevelingService().get_or_create_profile(owner, board=board)
        self.assertLess(profile.utilization_percentage, 90)

        unassigned = Task.objects.create(
            column=col, title='Brand New Task', complexity_score=5,
            assigned_to=None, created_by=board.created_by,
        )
        result = ResourceLevelingService().analyze_task_assignment(unassigned)
        self.assertTrue(result.get('should_reassign'))
        self.assertEqual(result['top_recommendation']['user_id'], owner.id)


class SuggestionListInvariantsTest(TestCase):
    def test_no_board_suggestion_targets_an_overloaded_member(self):
        owner, board, col = _board_with_member()
        _make_overloaded(owner, board, col)
        # A second, lighter member so there is a valid reassignment target.
        light = User.objects.create_user(username='light', password='pw')
        BoardMembership.objects.create(board=board, user=light, role='member')
        Task.objects.create(column=col, title='light task', complexity_score=4,
                            assigned_to=light, created_by=board.created_by)
        Task.objects.create(column=col, title='Unassigned APAC', complexity_score=5,
                            assigned_to=None, created_by=board.created_by)

        svc = ResourceLevelingService()
        suggestions = svc.get_board_optimization_suggestions(board, limit=20)

        for s in suggestions:
            prof = UserPerformanceProfile.objects.filter(user=s.suggested_assignee).first()
            util = prof.utilization_percentage if prof else 0
            self.assertLess(
                util, 100,
                f'suggestion targets {s.suggested_assignee.username} at {util:.0f}% (overloaded)',
            )
            # Confidence floor: weak guesses should not be surfaced.
            self.assertGreaterEqual(s.confidence_score, svc.MIN_DISPLAY_CONFIDENCE)

    def test_batch_has_no_contradictory_moves(self):
        """A generation run must be direction-coherent: no user may be both a giver
        (current_assignee) and a receiver (suggested_assignee). Otherwise "Accept All"
        churns tasks back and forth (e.g. Marcus->testuser1 AND testuser1->Marcus) and
        can leave the team MORE imbalanced than before."""
        from accounts.models import Organization
        creator = User.objects.create_user(username='creator', password='pw')
        org = Organization.objects.create(name='Org', created_by=creator)
        ws = Workspace.objects.create(name='WS', organization=org, created_by=creator, is_demo=False)
        board = Board.objects.create(name='B', created_by=creator, owner=creator, workspace=ws)
        col = Column.objects.create(board=board, name='Backlog', position=0)

        # Two heavily loaded members and two light members, all qualified (active tasks).
        members = {}
        for name, n, cx in [('heavy1', 6, 8), ('heavy2', 6, 7), ('mid', 4, 6), ('light', 1, 4)]:
            u = User.objects.create_user(username=name, password='pw')
            BoardMembership.objects.create(board=board, user=u, role='member')
            for i in range(n):
                Task.objects.create(column=col, title=f'{name}-{i}', complexity_score=cx,
                                    assigned_to=u, created_by=creator)
            members[name] = u

        svc = ResourceLevelingService()
        suggestions = svc.get_board_optimization_suggestions(board, limit=20)

        sources = {s.current_assignee_id for s in suggestions if s.current_assignee_id}
        targets = {s.suggested_assignee_id for s in suggestions}
        self.assertEqual(
            sources & targets, set(),
            'a user is both giving and receiving in the same batch (contradictory churn)',
        )

    def test_displayed_suggestions_match_pending_rows(self):
        """"Accept All" acts on every pending suggestion row for the board, so the
        set of pending rows must exactly equal what get_board_optimization_suggestions
        returns — otherwise a confidence-floored / over-limit suggestion the user
        never saw would still be applied (the "phantom 3rd reassignment" bug)."""
        owner, board, col = _board_with_member()
        _make_overloaded(owner, board, col)
        light = User.objects.create_user(username='light', password='pw')
        BoardMembership.objects.create(board=board, user=light, role='member')
        Task.objects.create(column=col, title='light task', complexity_score=4,
                            assigned_to=light, created_by=board.created_by)
        # An unassigned task tends to generate a low-confidence (floored) row.
        Task.objects.create(column=col, title='Unassigned APAC', complexity_score=5,
                            assigned_to=None, created_by=board.created_by)

        svc = ResourceLevelingService()
        returned = svc.get_board_optimization_suggestions(board, limit=20)
        returned_ids = {s.id for s in returned}

        pending_ids = set(
            ResourceLevelingSuggestion.objects.filter(
                task__column__board=board, status='pending',
            ).values_list('id', flat=True)
        )
        self.assertEqual(
            pending_ids, returned_ids,
            'pending rows (what Accept All applies) must equal the displayed set',
        )
