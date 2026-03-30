"""Tests for Exit Protocol app."""

from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import Organization, UserProfile
from kanban.models import Board, BoardMembership, Column, Task


class ExitProtocolTestBase(TestCase):
    """Shared setUp for Exit Protocol tests."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='epowner', email='ep@example.com', password='testpass123'
        )
        self.org = Organization.objects.create(
            name='EP Test Org', domain='ep-test.com', created_by=self.user
        )
        UserProfile.objects.create(user=self.user, organization=self.org)

        self.board = Board.objects.create(
            name='Project Omega',
            description='A test project for exit protocol',
            organization=self.org,
            created_by=self.user,
        )
        BoardMembership.objects.get_or_create(board=self.board, user=self.user, defaults={'role': 'member'})

        # Backdate creation for the 7-day minimum
        self.board.created_at = timezone.now() - timedelta(days=30)
        self.board.save(update_fields=['created_at'])

        # Create columns and tasks
        self.col_todo = Column.objects.create(board=self.board, name='To Do', position=0)
        self.col_done = Column.objects.create(board=self.board, name='Done', position=1)

        for i in range(10):
            t = Task.objects.create(column=self.col_todo, title=f'Task {i}', created_by=self.user)
            if i < 3:
                t.column = self.col_done
                t.completed_at = timezone.now()
                t.save()

        self.client = Client()
        self.client.force_login(self.user)


class ModelTests(ExitProtocolTestBase):
    """Test model creation and constraints."""

    def test_create_health_signal(self):
        from .models import ProjectHealthSignal
        signal = ProjectHealthSignal.objects.create(
            board=self.board,
            hospice_risk_score=0.42,
            dimensions_available=3,
            score_is_valid=True,
        )
        self.assertEqual(signal.board, self.board)
        self.assertAlmostEqual(signal.hospice_risk_score, 0.42)
        self.assertEqual(str(signal), f"{self.board.name} — 0.42 @ {signal.recorded_at}")

    def test_create_hospice_session(self):
        from .models import HospiceSession
        session = HospiceSession.objects.create(
            board=self.board,
            initiated_by=self.user,
            trigger_type='manager_initiated',
            status='assessment',
        )
        self.assertEqual(session.board, self.board)
        self.assertEqual(session.status, 'assessment')

    def test_create_cemetery_entry(self):
        from .models import CemeteryEntry, HospiceSession
        session = HospiceSession.objects.create(
            board=self.board,
            initiated_by=self.user,
            trigger_type='manager_initiated',
        )
        entry = CemeteryEntry.objects.create(
            board=self.board,
            hospice_session=session,
            project_name='Project Omega',
            board_id_snapshot=self.board.id,
            team_size=5,
            total_tasks=10,
            completed_tasks=3,
            cause_of_death='zombie_death',
            autopsy_report={'test': True},
            autopsy_summary='Test autopsy',
        )
        self.assertEqual(entry.project_name, 'Project Omega')
        self.assertFalse(entry.is_resurrected)

    def test_create_project_organ(self):
        from .models import ProjectOrgan, HospiceSession
        session = HospiceSession.objects.create(
            board=self.board, initiated_by=self.user,
            trigger_type='auto_detected',
        )
        organ = ProjectOrgan.objects.create(
            source_board=self.board,
            hospice_session=session,
            organ_type='task_template',
            name='Sprint Planning Template',
            description='Reusable task template',
            payload={'title': 'Sprint Planning', 'subtasks': []},
        )
        self.assertEqual(organ.status, 'available')
        self.assertEqual(organ.reusability_score, 0)

    def test_hospice_dismissal_unique(self):
        from .models import HospiceDismissal
        from django.db import IntegrityError

        HospiceDismissal.objects.create(
            board=self.board, user=self.user,
            expires_at=timezone.now() + timedelta(days=7),
        )
        with self.assertRaises(IntegrityError):
            HospiceDismissal.objects.create(
                board=self.board, user=self.user,
                expires_at=timezone.now() + timedelta(days=7),
            )


class HealthScoringTests(ExitProtocolTestBase):
    """Test health scoring logic."""

    @patch('exit_protocol.tasks.trigger_hospice_notification.delay')
    def test_healthy_board_scores_low(self, mock_notify):
        from .tasks import compute_board_health_score
        compute_board_health_score(self.board.id)

        from .models import ProjectHealthSignal
        signal = ProjectHealthSignal.objects.filter(board=self.board).first()
        # With only activity dimension available (+ possibly deadline),
        # a recently active board should score low
        if signal and signal.score_is_valid:
            self.assertLess(signal.hospice_risk_score, 0.75)
        mock_notify.assert_not_called()

    @patch('exit_protocol.tasks.trigger_hospice_notification.delay')
    def test_inactive_board_scores_high(self, mock_notify):
        """A board with no activity for 30 days should score high on activity."""
        # Make all tasks old
        Task.objects.filter(column__board=self.board).update(
            updated_at=timezone.now() - timedelta(days=35)
        )
        # Add overdue tasks
        for i in range(10):
            Task.objects.create(
                column=self.col_todo,
                title=f'Overdue {i}',
                due_date=timezone.now() - timedelta(days=10),
                created_by=self.user,
            )

        from .tasks import compute_board_health_score
        compute_board_health_score(self.board.id)

        from .models import ProjectHealthSignal
        signal = ProjectHealthSignal.objects.filter(board=self.board).order_by('-recorded_at').first()
        self.assertIsNotNone(signal)
        if signal.score_is_valid:
            self.assertGreater(signal.hospice_risk_score, 0.3)

    def test_new_board_skipped(self):
        """Boards < 7 days old should not get a score."""
        new_board = Board.objects.create(
            name='Brand New', organization=self.org, created_by=self.user,
        )
        # created_at defaults to now, which is < 7 days

        from .tasks import compute_board_health_score
        compute_board_health_score(new_board.id)

        from .models import ProjectHealthSignal
        self.assertFalse(
            ProjectHealthSignal.objects.filter(board=new_board).exists()
        )


class ViewTests(ExitProtocolTestBase):
    """Test view access and basic responses."""

    def test_cemetery_get(self):
        resp = self.client.get(reverse('exit_protocol:cemetery'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Project Cemetery')

    def test_dashboard_get(self):
        resp = self.client.get(
            reverse('exit_protocol:dashboard', args=[self.board.id])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Exit Protocol')

    def test_initiate_hospice(self):
        with patch('exit_protocol.tasks.generate_hospice_assessment.delay'):
            with patch('exit_protocol.tasks.generate_knowledge_checklist.delay'):
                with patch('exit_protocol.tasks.generate_team_transition_memos.delay'):
                    with patch('exit_protocol.tasks.scan_and_extract_organs.delay'):
                        resp = self.client.post(
                            reverse('exit_protocol:initiate', args=[self.board.id])
                        )
        self.assertEqual(resp.status_code, 302)
        from .models import HospiceSession
        self.assertTrue(HospiceSession.objects.filter(board=self.board).exists())

    def test_initiate_hospice_duplicate(self):
        from .models import HospiceSession
        HospiceSession.objects.create(
            board=self.board, initiated_by=self.user,
            trigger_type='manager_initiated',
        )
        resp = self.client.post(
            reverse('exit_protocol:initiate', args=[self.board.id])
        )
        self.assertEqual(resp.status_code, 400)

    def test_bury_requires_confirmation(self):
        from .models import HospiceSession
        HospiceSession.objects.create(
            board=self.board, initiated_by=self.user,
            trigger_type='manager_initiated', status='burial_pending',
        )
        # Wrong confirmation text
        resp = self.client.post(
            reverse('exit_protocol:bury', args=[self.board.id]),
            {'confirmation': 'wrong text'},
        )
        self.assertEqual(resp.status_code, 400)

    @patch('exit_protocol.tasks.perform_burial.delay')
    def test_bury_with_correct_confirmation(self, mock_burial):
        from .models import HospiceSession
        HospiceSession.objects.create(
            board=self.board, initiated_by=self.user,
            trigger_type='manager_initiated', status='burial_pending',
        )
        resp = self.client.post(
            reverse('exit_protocol:bury', args=[self.board.id]),
            {'confirmation': 'I confirm I want to archive this project'},
        )
        self.assertEqual(resp.status_code, 302)
        mock_burial.assert_called_once()

    def test_dismiss_banner(self):
        resp = self.client.post(
            reverse('exit_protocol:dismiss_banner', args=[self.board.id])
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['dismissed'])

        from .models import HospiceDismissal
        self.assertTrue(
            HospiceDismissal.objects.filter(
                board=self.board, user=self.user
            ).exists()
        )

    def test_organ_bank_get(self):
        resp = self.client.get(
            reverse('exit_protocol:organ_bank', args=[self.board.id])
        )
        self.assertEqual(resp.status_code, 200)

    def test_organ_library_get(self):
        resp = self.client.get(reverse('exit_protocol:organ_library'))
        self.assertEqual(resp.status_code, 200)

    def test_reject_organ(self):
        from .models import ProjectOrgan, HospiceSession
        session = HospiceSession.objects.create(
            board=self.board, initiated_by=self.user,
            trigger_type='manager_initiated',
        )
        organ = ProjectOrgan.objects.create(
            source_board=self.board, hospice_session=session,
            organ_type='knowledge_entry', name='Test Organ',
            description='Test', payload={},
        )
        resp = self.client.post(
            reverse('exit_protocol:reject_organ', args=[organ.id])
        )
        self.assertEqual(resp.status_code, 200)
        organ.refresh_from_db()
        self.assertEqual(organ.status, 'rejected')

    def test_autopsy_report_404(self):
        resp = self.client.get(
            reverse('exit_protocol:autopsy_report', args=[99999])
        )
        self.assertEqual(resp.status_code, 404)

    def test_resurrect_project(self):
        from .models import CemeteryEntry, HospiceSession
        session = HospiceSession.objects.create(
            board=self.board, initiated_by=self.user,
            trigger_type='manager_initiated',
        )
        entry = CemeteryEntry.objects.create(
            board=self.board, hospice_session=session,
            project_name='Project Omega', board_id_snapshot=self.board.id,
            team_size=5, total_tasks=10, completed_tasks=3,
            cause_of_death='budget_bleed',
            autopsy_report={}, autopsy_summary='Test',
        )
        resp = self.client.post(
            reverse('exit_protocol:resurrect', args=[entry.id])
        )
        self.assertEqual(resp.status_code, 302)
        entry.refresh_from_db()
        self.assertTrue(entry.is_resurrected)
        self.assertIsNotNone(entry.resurrected_as)

    def test_resurrect_already_resurrected(self):
        from .models import CemeteryEntry, HospiceSession
        session = HospiceSession.objects.create(
            board=self.board, initiated_by=self.user,
            trigger_type='manager_initiated',
        )
        entry = CemeteryEntry.objects.create(
            board=self.board, hospice_session=session,
            project_name='Project Omega', board_id_snapshot=self.board.id,
            team_size=5, total_tasks=10, completed_tasks=3,
            cause_of_death='scope_cancer', is_resurrected=True,
            autopsy_report={}, autopsy_summary='Test',
        )
        resp = self.client.post(
            reverse('exit_protocol:resurrect', args=[entry.id])
        )
        self.assertEqual(resp.status_code, 400)

    def test_unauthenticated_redirect(self):
        anon_client = Client()
        resp = anon_client.get(reverse('exit_protocol:cemetery'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('login', resp.url)


class BurialTaskTests(ExitProtocolTestBase):
    """Test the perform_burial task."""

    @patch('exit_protocol.ai_utils.classify_cause_of_death')
    @patch('exit_protocol.ai_utils.extract_lessons')
    @patch('exit_protocol.ai_utils.generate_tags')
    def test_perform_burial_creates_entry(self, mock_tags, mock_lessons, mock_classify):
        mock_classify.return_value = {
            'cause': 'velocity_collapse',
            'primary_rationale': 'Team velocity dropped significantly',
            'contributing_factors': ['budget overrun', 'team turnover'],
        }
        mock_lessons.return_value = {
            'lessons_to_repeat': [{'lesson': 'Good CI/CD pipeline'}],
            'lessons_to_avoid': [{'lesson': 'No sprint planning'}],
            'open_questions': [{'question': 'Was the scope realistic?'}],
        }
        mock_tags.return_value = ['velocity', 'budget', 'planning']

        from .models import HospiceSession, CemeteryEntry
        session = HospiceSession.objects.create(
            board=self.board, initiated_by=self.user,
            trigger_type='manager_initiated', status='burial_pending',
        )

        from .tasks import perform_burial
        perform_burial(session.id)

        # Verify cemetery entry created
        entry = CemeteryEntry.objects.filter(hospice_session=session).first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.project_name, 'Project Omega')
        self.assertEqual(entry.cause_of_death, 'velocity_collapse')
        self.assertEqual(entry.total_tasks, 13)  # 10 + 3 completed

        # Verify board archived
        self.board.refresh_from_db()
        self.assertTrue(self.board.is_archived)

        # Verify session status
        session.refresh_from_db()
        self.assertEqual(session.status, 'buried')

    @patch('exit_protocol.ai_utils.classify_cause_of_death')
    @patch('exit_protocol.ai_utils.extract_lessons')
    @patch('exit_protocol.ai_utils.generate_tags')
    def test_perform_burial_idempotent(self, mock_tags, mock_lessons, mock_classify):
        """Running burial twice should not create duplicate entries."""
        mock_classify.return_value = {'cause': 'zombie_death', 'primary_rationale': '', 'contributing_factors': []}
        mock_lessons.return_value = {'lessons_to_repeat': [], 'lessons_to_avoid': [], 'open_questions': []}
        mock_tags.return_value = []

        from .models import HospiceSession, CemeteryEntry
        session = HospiceSession.objects.create(
            board=self.board, initiated_by=self.user,
            trigger_type='manager_initiated', status='burial_pending',
        )

        from .tasks import perform_burial
        perform_burial(session.id)
        perform_burial(session.id)  # Second call should be idempotent

        self.assertEqual(
            CemeteryEntry.objects.filter(hospice_session=session).count(), 1
        )
