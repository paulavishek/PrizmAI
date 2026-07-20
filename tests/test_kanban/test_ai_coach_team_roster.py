"""
AI Coach team-roster context tests
===================================

The AI Coach's enhancement prompt used to name specific teammates for
reassignment ("give this to Marcus") without ever looking at their actual
workload or skills — the LLM was inventing plausible-sounding names purely
from the suggestion's message text. This let it contradict AI Resource
Optimization (e.g. recommending work go TO the person already most
overloaded on the board).

These tests verify AICoachService._build_team_roster_block() grounds the
prompt in the same UserPerformanceProfile data Resource Optimization uses.
"""

from django.test import TestCase
from django.contrib.auth.models import User

from accounts.models import Organization, UserProfile
from kanban.models import Board, BoardMembership, Column, Task, Workspace
from kanban.resource_leveling_models import UserPerformanceProfile
from kanban.utils.ai_coach_service import AICoachService


class AICoachTeamRosterTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('owner', password='x')
        cls.org = Organization.objects.create(name='Org', created_by=cls.owner)
        cls.ws = Workspace.objects.create(
            name='WS', organization=cls.org, is_active=True, created_by=cls.owner,
        )
        cls.board = Board.objects.create(
            name='Board', organization=cls.org, workspace=cls.ws, created_by=cls.owner,
        )
        cls.column = Column.objects.create(name='In Progress', board=cls.board, position=0)

        cls.overloaded = User.objects.create_user('elena', password='x')
        cls.available = User.objects.create_user('testuser1', password='x')

        for u, role in [(cls.owner, 'owner'), (cls.overloaded, 'member'), (cls.available, 'member')]:
            BoardMembership.objects.create(board=cls.board, user=u, role=role)

        # UserPerformanceProfile.current_active_tasks/utilization_percentage AND
        # weekly_capacity_hours are recomputed live on every get_or_create_profile()
        # call (update_current_workload from real Task rows; _sync_profile_capacity
        # from accounts.UserProfile.weekly_capacity_hours) — so the test must seed
        # actual tasks + declared capacity rather than set profile fields directly,
        # or they get overwritten back to derived/default values.
        UserProfile.objects.create(user=cls.overloaded, weekly_capacity_hours=20)
        UserPerformanceProfile.objects.create(
            user=cls.overloaded, workspace=cls.ws,
            skill_keywords={'backend': 10, 'database': 8},
        )
        # 3 tasks x complexity 7 = 21h workload against 20h capacity => 105%.
        for i in range(3):
            Task.objects.create(
                title=f'Elena task {i}', column=cls.column, assigned_to=cls.overloaded,
                item_type='task', complexity_score=7, created_by=cls.owner,
            )

        UserProfile.objects.create(user=cls.available, weekly_capacity_hours=6)
        UserPerformanceProfile.objects.create(
            user=cls.available, workspace=cls.ws,
            skill_keywords={'frontend': 6},
        )
        # 1 task x complexity 4 = 4h workload against 6h capacity => 67%.
        Task.objects.create(
            title='Available task', column=cls.column, assigned_to=cls.available,
            item_type='task', complexity_score=4, created_by=cls.owner,
        )

    def test_roster_includes_real_workload_and_skills(self):
        service = AICoachService()
        block = service._build_team_roster_block({'board_id': self.board.id})

        self.assertIn('elena', block)
        self.assertIn('105%', block)
        self.assertIn('backend', block)
        self.assertIn('testuser1', block)
        self.assertIn('67%', block)
        self.assertIn('frontend', block)

    def test_roster_instructs_against_overloaded_recommendation(self):
        service = AICoachService()
        block = service._build_team_roster_block({'board_id': self.board.id})

        self.assertIn('90%', block)
        self.assertIn('LOWER capacity utilization', block)

    def test_roster_empty_without_board_id(self):
        service = AICoachService()
        block = service._build_team_roster_block({})
        self.assertEqual(block, '')

    def test_enhancement_prompt_embeds_roster(self):
        service = AICoachService()
        suggestion = {
            'message': 'Elena is overloaded with 3 overdue tasks',
            'suggestion_type': 'resource_overload',
            'severity': 'critical',
            'metrics_snapshot': {},
        }
        context = {'board_id': self.board.id, 'board_name': self.board.name}
        prompt = service._build_enhancement_prompt(suggestion, context)

        self.assertIn('Team Workload & Skills', prompt)
        self.assertIn('testuser1', prompt)
