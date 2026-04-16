"""
Populate Missing Demo Data for Spectra Context Providers
=========================================================
Seeds demo data for features that have 0 records on the official demo board:
  - CalendarEvent (meetings, team events, OOO, busy blocks)
  - CommitmentProtocol + ConfidenceSignal (living commitments with decay)
  - BoardAutomation (trigger/action rules)
  - DecisionItem (decision center items)
  - ProjectStakeholder (stakeholder map)

Usage:
    python manage.py populate_missing_demo_data
    python manage.py populate_missing_demo_data --reset
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from datetime import timedelta, datetime, time
from decimal import Decimal
import json


class Command(BaseCommand):
    help = 'Populate demo data for features missing from the official demo board'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing data for these features before creating new data',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))
        self.stdout.write(self.style.SUCCESS('  Populating Missing Demo Data for Spectra'))
        self.stdout.write(self.style.SUCCESS('=' * 70))

        from accounts.models import Organization
        from kanban.models import Board

        # Find demo org by is_demo flag (not by name, since it may have been renamed)
        demo_org = Organization.objects.filter(is_demo=True).first()
        if not demo_org:
            self.stdout.write(self.style.ERROR('❌ No demo organization found (is_demo=True).'))
            return

        # Find official demo board
        board = Board.objects.filter(
            organization=demo_org,
            is_official_demo_board=True,
        ).first()
        if not board:
            self.stdout.write(self.style.ERROR('❌ No official demo board found.'))
            return

        self.stdout.write(f'  Org: {demo_org.name} (id={demo_org.id})')
        self.stdout.write(f'  Board: {board.name} (id={board.id})')

        # Get demo users
        alex = User.objects.filter(username='alex_chen_demo').first()
        sam = User.objects.filter(username='sam_rivera_demo').first()
        jordan = User.objects.filter(username='jordan_taylor_demo').first()

        if not all([alex, sam, jordan]):
            self.stdout.write(self.style.ERROR('❌ Demo users not found.'))
            return

        self.board = board
        self.alex = alex
        self.sam = sam
        self.jordan = jordan
        self.now = timezone.now()
        self.today = self.now.date()

        with transaction.atomic():
            if options['reset']:
                self._reset_data()

            stats = {}
            stats['calendar'] = self._create_calendar_events()
            stats['commitments'] = self._create_commitment_protocols()
            stats['automations'] = self._create_board_automations()
            stats['decisions'] = self._create_decision_items()
            stats['stakeholders'] = self._create_stakeholders()

        self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))
        self.stdout.write(self.style.SUCCESS('  Summary'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        for feature, count in stats.items():
            self.stdout.write(f'  ✅ {feature}: {count} records created')
        self.stdout.write('')

    def _reset_data(self):
        """Delete existing data for these features on the demo board."""
        from kanban.models import CalendarEvent
        from kanban.commitment_models import CommitmentProtocol
        from kanban.automation_models import BoardAutomation
        from decision_center.models import DecisionItem
        from kanban.stakeholder_models import ProjectStakeholder

        CalendarEvent.objects.filter(board=self.board).delete()
        CommitmentProtocol.objects.filter(board=self.board).delete()
        BoardAutomation.objects.filter(board=self.board).delete()
        DecisionItem.objects.filter(board=self.board).delete()
        ProjectStakeholder.objects.filter(board=self.board).delete()
        self.stdout.write('   ✓ Cleared existing data for all 5 features')

    # -----------------------------------------------------------------
    #  1. CALENDAR EVENTS
    # -----------------------------------------------------------------
    def _create_calendar_events(self):
        from kanban.models import CalendarEvent, Task

        self.stdout.write(self.style.NOTICE('\n📅 Creating Calendar Events...'))

        if CalendarEvent.objects.filter(board=self.board).exists():
            self.stdout.write('   ⏭️  Calendar events already exist, skipping')
            return 0

        tasks = list(Task.objects.filter(column__board=self.board).order_by('id')[:6])
        count = 0

        events = [
            # Recurring standup — today
            {
                'title': 'Daily Standup',
                'description': 'Team sync: blockers, progress, and priorities for the day.',
                'event_type': 'meeting',
                'visibility': 'team',
                'start_datetime': timezone.make_aware(datetime.combine(self.today, time(9, 0))),
                'end_datetime': timezone.make_aware(datetime.combine(self.today, time(9, 15))),
                'location': 'Zoom — #standup',
                'created_by': self.alex,
                'participants': [self.alex, self.sam, self.jordan],
            },
            # Sprint planning — 2 days from now
            {
                'title': 'Sprint 3 Planning',
                'description': 'Plan Sprint 3 scope. Review backlog priorities, estimate new tasks, and agree on capacity.',
                'event_type': 'meeting',
                'visibility': 'team',
                'start_datetime': timezone.make_aware(datetime.combine(self.today + timedelta(days=2), time(10, 0))),
                'end_datetime': timezone.make_aware(datetime.combine(self.today + timedelta(days=2), time(11, 30))),
                'location': 'Conference Room B',
                'created_by': self.alex,
                'participants': [self.alex, self.sam, self.jordan],
                'linked_task': tasks[0] if tasks else None,
            },
            # Architecture review — 4 days from now
            {
                'title': 'Architecture Review: Search Engine',
                'description': 'Deep-dive on Search & Indexing Engine design. Review Elasticsearch vs Meilisearch trade-offs.',
                'event_type': 'meeting',
                'visibility': 'team',
                'start_datetime': timezone.make_aware(datetime.combine(self.today + timedelta(days=4), time(14, 0))),
                'end_datetime': timezone.make_aware(datetime.combine(self.today + timedelta(days=4), time(15, 0))),
                'location': 'Zoom — #architecture',
                'created_by': self.sam,
                'participants': [self.sam, self.jordan],
                'linked_task': tasks[5] if len(tasks) > 5 else None,
            },
            # Sprint retrospective — past (3 days ago)
            {
                'title': 'Sprint 2 Retrospective',
                'description': 'Reflect on Sprint 2 outcomes. Discuss what went well, what needs improvement, and action items.',
                'event_type': 'meeting',
                'visibility': 'team',
                'start_datetime': timezone.make_aware(datetime.combine(self.today - timedelta(days=3), time(15, 0))),
                'end_datetime': timezone.make_aware(datetime.combine(self.today - timedelta(days=3), time(16, 0))),
                'location': 'Conference Room A',
                'created_by': self.alex,
                'participants': [self.alex, self.sam, self.jordan],
            },
            # Team event — 7 days out
            {
                'title': 'Team Lunch — Sprint 2 Celebration',
                'description': 'Celebrating successful Sprint 2 delivery! Dashboard UI and Authentication shipped on time.',
                'event_type': 'team_event',
                'visibility': 'team',
                'start_datetime': timezone.make_aware(datetime.combine(self.today + timedelta(days=7), time(12, 0))),
                'end_datetime': timezone.make_aware(datetime.combine(self.today + timedelta(days=7), time(13, 30))),
                'location': 'Downtown Bistro',
                'created_by': self.alex,
                'participants': [self.alex, self.sam, self.jordan],
            },
            # Out of office — Sam
            {
                'title': 'Sam Rivera — PTO',
                'description': 'Out of office for personal day. Jordan covering API reviews.',
                'event_type': 'out_of_office',
                'visibility': 'team',
                'start_datetime': timezone.make_aware(datetime.combine(self.today + timedelta(days=5), time(0, 0))),
                'end_datetime': timezone.make_aware(datetime.combine(self.today + timedelta(days=5), time(23, 59))),
                'is_all_day': True,
                'created_by': self.sam,
                'participants': [self.sam],
            },
            # Code review block — Jordan
            {
                'title': 'Focus Block: Code Review',
                'description': 'Reserved time for reviewing Authentication System and File Upload PRs.',
                'event_type': 'busy_block',
                'visibility': 'private',
                'start_datetime': timezone.make_aware(datetime.combine(self.today + timedelta(days=1), time(13, 0))),
                'end_datetime': timezone.make_aware(datetime.combine(self.today + timedelta(days=1), time(15, 0))),
                'created_by': self.jordan,
                'participants': [self.jordan],
                'linked_task': tasks[1] if len(tasks) > 1 else None,
            },
            # Stakeholder demo — 6 days out
            {
                'title': 'Stakeholder Demo — Core Features',
                'description': 'Demo Authentication, Dashboard, and File Upload features to VP of Engineering and Product Lead.',
                'event_type': 'meeting',
                'visibility': 'team',
                'start_datetime': timezone.make_aware(datetime.combine(self.today + timedelta(days=6), time(11, 0))),
                'end_datetime': timezone.make_aware(datetime.combine(self.today + timedelta(days=6), time(12, 0))),
                'location': 'Main Conference Room',
                'created_by': self.alex,
                'participants': [self.alex, self.sam, self.jordan],
            },
        ]

        for ev_data in events:
            participants = ev_data.pop('participants', [])
            linked_task = ev_data.pop('linked_task', None)
            ev = CalendarEvent.objects.create(
                board=self.board,
                linked_task=linked_task,
                **ev_data,
            )
            if participants:
                ev.participants.set(participants)
            count += 1

        self.stdout.write(f'   ✅ Created {count} calendar events')
        return count

    # -----------------------------------------------------------------
    #  2. COMMITMENT PROTOCOLS + CONFIDENCE SIGNALS
    # -----------------------------------------------------------------
    def _create_commitment_protocols(self):
        from kanban.commitment_models import CommitmentProtocol, ConfidenceSignal
        from kanban.models import Task

        self.stdout.write(self.style.NOTICE('\n📋 Creating Commitment Protocols...'))

        if CommitmentProtocol.objects.filter(board=self.board).exists():
            self.stdout.write('   ⏭️  Commitment protocols already exist, skipping')
            return 0

        tasks = list(Task.objects.filter(column__board=self.board).order_by('id'))
        count = 0

        # Protocol 1: Sprint 3 delivery commitment
        p1 = CommitmentProtocol.objects.create(
            board=self.board,
            title='Sprint 3 Core Delivery',
            description=(
                'Team commits to completing Search & Indexing Engine, Notification Service, '
                'and User Management API by end of Sprint 3. These are the critical path items '
                'needed before the Beta Release Checkpoint.'
            ),
            target_date=self.today + timedelta(days=14),
            initial_confidence=0.85,
            current_confidence=0.72,
            confidence_halflife_days=14,
            decay_model='exponential',
            status='active',
            created_by=self.alex,
            baseline_snapshot={
                'total_tasks': 30,
                'completed': 7,
                'in_progress': 6,
                'velocity': 4.2,
                'team_size': 3,
            },
            ai_reasoning=(
                'Confidence has decayed from 0.85 to 0.72 due to the Database Schema task '
                'remaining unassigned and the User Registration Flow running 2 days overdue. '
                'The team velocity of 4.2 tasks/week is sufficient if blockers are resolved.'
            ),
            negotiation_threshold=0.40,
            token_pool_per_member=100,
        )
        # Link some tasks
        sprint3_tasks = [t for t in tasks if t.title in [
            'Search & Indexing Engine', 'Notification Service', 'User Management API',
            'Real-time Collaboration', 'Data Caching Layer',
        ]]
        if sprint3_tasks:
            p1.linked_tasks.set(sprint3_tasks)
        p1.stakeholders.set([self.alex, self.sam, self.jordan])

        # Signals for protocol 1
        signals_p1 = [
            {'days_ago': 10, 'signal_type': 'task_completed', 'signal_value': 0.3,
             'description': 'Dashboard UI Development completed ahead of schedule.',
             'confidence_before': 0.85, 'confidence_after': 0.88, 'recorded_by': self.alex},
            {'days_ago': 7, 'signal_type': 'dependency_blocked', 'signal_value': -0.4,
             'description': 'Database Schema task unassigned — blocks User Management API.',
             'confidence_before': 0.88, 'confidence_after': 0.80, 'recorded_by': self.sam},
            {'days_ago': 5, 'signal_type': 'decay', 'signal_value': -0.05,
             'description': 'Automated confidence decay — no new positive signals.',
             'confidence_before': 0.80, 'confidence_after': 0.76, 'ai_generated': True},
            {'days_ago': 3, 'signal_type': 'milestone_missed', 'signal_value': -0.3,
             'description': 'User Registration Flow missed its target completion date.',
             'confidence_before': 0.76, 'confidence_after': 0.72, 'recorded_by': self.jordan},
        ]
        for sig_data in signals_p1:
            days_ago = sig_data.pop('days_ago')
            ai_gen = sig_data.pop('ai_generated', False)
            related_task = None
            sig = ConfidenceSignal.objects.create(
                protocol=p1,
                ai_generated=ai_gen,
                related_task=related_task,
                **sig_data,
            )
            ConfidenceSignal.objects.filter(pk=sig.pk).update(
                timestamp=self.now - timedelta(days=days_ago)
            )
        count += 1

        # Protocol 2: Security milestone
        p2 = CommitmentProtocol.objects.create(
            board=self.board,
            title='Security Audit Readiness',
            description=(
                'Commitment to have Authentication System, Security Audit & Fixes, and '
                'API Rate Limiting completed and code-reviewed before the external security '
                'audit scheduled for the end of the month.'
            ),
            target_date=self.today + timedelta(days=21),
            initial_confidence=0.90,
            current_confidence=0.82,
            confidence_halflife_days=10,
            decay_model='linear',
            status='active',
            created_by=self.sam,
            baseline_snapshot={
                'security_tasks': 3,
                'completed': 0,
                'in_review': 1,
                'audit_date': (self.today + timedelta(days=21)).isoformat(),
            },
            ai_reasoning=(
                'Authentication System is in review which is positive. However, Security Audit '
                'and API Rate Limiting have not started. Linear decay model chosen because '
                'security tasks have clear pass/fail criteria — partial progress matters less.'
            ),
            negotiation_threshold=0.50,
            token_pool_per_member=100,
        )
        security_tasks = [t for t in tasks if t.title in [
            'Authentication System', 'Security Audit & Fixes', 'API Rate Limiting',
        ]]
        if security_tasks:
            p2.linked_tasks.set(security_tasks)
        p2.stakeholders.set([self.sam, self.alex])

        signals_p2 = [
            {'days_ago': 8, 'signal_type': 'task_completed', 'signal_value': 0.2,
             'description': 'Security Architecture Patterns completed — foundation in place.',
             'confidence_before': 0.90, 'confidence_after': 0.90, 'recorded_by': self.sam},
            {'days_ago': 4, 'signal_type': 'manual_positive', 'signal_value': 0.15,
             'description': 'Authentication System moved to In Review — on track.',
             'confidence_before': 0.90, 'confidence_after': 0.88, 'recorded_by': self.sam},
            {'days_ago': 2, 'signal_type': 'external_risk', 'signal_value': -0.3,
             'description': 'External audit firm moved date up by 5 days — tighter window.',
             'confidence_before': 0.88, 'confidence_after': 0.82, 'recorded_by': self.alex},
        ]
        for sig_data in signals_p2:
            days_ago = sig_data.pop('days_ago')
            sig = ConfidenceSignal.objects.create(
                protocol=p2,
                ai_generated=False,
                **sig_data,
            )
            ConfidenceSignal.objects.filter(pk=sig.pk).update(
                timestamp=self.now - timedelta(days=days_ago)
            )
        count += 1

        # Protocol 3: At-risk protocol
        p3 = CommitmentProtocol.objects.create(
            board=self.board,
            title='Beta Release by End of Month',
            description=(
                'Commitment to reach Beta Release Checkpoint by end of month. Requires '
                'completing all Phase 2 tasks plus Integration Testing Suite.'
            ),
            target_date=self.today + timedelta(days=28),
            initial_confidence=0.80,
            current_confidence=0.48,
            confidence_halflife_days=12,
            decay_model='stepped',
            status='at_risk',
            created_by=self.alex,
            baseline_snapshot={
                'total_phase2_tasks': 12,
                'completed': 2,
                'blocked': 1,
                'velocity_needed': 5.5,
                'current_velocity': 4.2,
            },
            ai_reasoning=(
                'This commitment is AT RISK. Current velocity of 4.2 tasks/week is below '
                'the 5.5 needed to hit the target. The Database Schema task is unassigned '
                'and blocks multiple downstream items. Recommend renegotiation: either '
                'reduce scope or extend deadline by 1 week.'
            ),
            negotiation_threshold=0.40,
            token_pool_per_member=100,
        )
        p3.stakeholders.set([self.alex, self.sam, self.jordan])

        signals_p3 = [
            {'days_ago': 12, 'signal_type': 'task_completed', 'signal_value': 0.2,
             'description': 'Base API Structure completed.',
             'confidence_before': 0.80, 'confidence_after': 0.82, 'recorded_by': self.sam},
            {'days_ago': 8, 'signal_type': 'dependency_blocked', 'signal_value': -0.5,
             'description': 'Database Schema unassigned — blocks 3 downstream tasks.',
             'confidence_before': 0.82, 'confidence_after': 0.68, 'recorded_by': self.alex},
            {'days_ago': 5, 'signal_type': 'decay', 'signal_value': -0.1,
             'description': 'Stepped decay triggered — crossed 7-day inactivity threshold.',
             'confidence_before': 0.68, 'confidence_after': 0.58, 'ai_generated': True},
            {'days_ago': 2, 'signal_type': 'milestone_missed', 'signal_value': -0.4,
             'description': 'Mid-sprint checkpoint missed — only 2 of 5 planned tasks done.',
             'confidence_before': 0.58, 'confidence_after': 0.48, 'recorded_by': self.jordan},
        ]
        for sig_data in signals_p3:
            days_ago = sig_data.pop('days_ago')
            ai_gen = sig_data.pop('ai_generated', False)
            sig = ConfidenceSignal.objects.create(
                protocol=p3,
                ai_generated=ai_gen,
                **sig_data,
            )
            ConfidenceSignal.objects.filter(pk=sig.pk).update(
                timestamp=self.now - timedelta(days=days_ago)
            )
        count += 1

        total_signals = ConfidenceSignal.objects.filter(protocol__board=self.board).count()
        self.stdout.write(f'   ✅ Created {count} commitment protocols, {total_signals} confidence signals')
        return count

    # -----------------------------------------------------------------
    #  3. BOARD AUTOMATIONS
    # -----------------------------------------------------------------
    def _create_board_automations(self):
        from kanban.automation_models import BoardAutomation

        self.stdout.write(self.style.NOTICE('\n⚡ Creating Board Automations...'))

        if BoardAutomation.objects.filter(board=self.board).exists():
            self.stdout.write('   ⏭️  Board automations already exist, skipping')
            return 0

        count = 0
        automations = [
            {
                'name': 'Auto-escalate overdue tasks',
                'trigger_type': 'task_overdue',
                'trigger_value': '2',  # 2 days overdue
                'action_type': 'set_priority',
                'action_value': 'urgent',
                'is_active': True,
                'created_by': self.alex,
                'run_count': 3,
            },
            {
                'name': 'Notify on task completion',
                'trigger_type': 'task_completed',
                'trigger_value': '',
                'action_type': 'send_notification',
                'action_value': 'Task completed: {task_title}',
                'is_active': True,
                'created_by': self.alex,
                'run_count': 7,
            },
            {
                'name': 'Label high-priority new tasks',
                'trigger_type': 'task_created',
                'trigger_value': 'priority:high',
                'action_type': 'add_label',
                'action_value': 'needs-review',
                'is_active': True,
                'created_by': self.sam,
                'run_count': 5,
            },
            {
                'name': 'Move reviewed tasks to Done',
                'trigger_type': 'moved_to_column',
                'trigger_value': 'In Review',
                'action_type': 'send_notification',
                'action_value': 'Task ready for final review: {task_title}',
                'is_active': True,
                'created_by': self.jordan,
                'run_count': 4,
            },
            {
                'name': 'Due date reminder (3 days)',
                'trigger_type': 'due_date_approaching',
                'trigger_value': '3',  # 3 days before due
                'action_type': 'send_notification',
                'action_value': 'Due in 3 days: {task_title}',
                'is_active': True,
                'created_by': self.alex,
                'run_count': 12,
            },
            {
                'name': 'Auto-assign priority on column move',
                'trigger_type': 'moved_to_column',
                'trigger_value': 'In Progress',
                'action_type': 'set_priority',
                'action_value': 'medium',
                'is_active': False,  # Disabled — was too aggressive
                'created_by': self.sam,
                'run_count': 8,
            },
        ]

        for auto_data in automations:
            run_count = auto_data.pop('run_count', 0)
            auto = BoardAutomation.objects.create(board=self.board, **auto_data)
            if run_count > 0:
                BoardAutomation.objects.filter(pk=auto.pk).update(
                    run_count=run_count,
                    last_run_at=self.now - timedelta(days=1),
                )
            count += 1

        self.stdout.write(f'   ✅ Created {count} board automations')
        return count

    # -----------------------------------------------------------------
    #  4. DECISION ITEMS
    # -----------------------------------------------------------------
    def _create_decision_items(self):
        from decision_center.models import DecisionItem

        self.stdout.write(self.style.NOTICE('\n🎯 Creating Decision Items...'))

        if DecisionItem.objects.filter(board=self.board).exists():
            self.stdout.write('   ⏭️  Decision items already exist, skipping')
            return 0

        count = 0
        items = [
            {
                'created_for': self.alex,
                'item_type': 'overdue_task',
                'priority_level': 'action_required',
                'title': 'User Registration Flow is 9 days overdue',
                'description': 'The User Registration Flow task (assigned to Alex Chen) is 9 days past its due date with 80% progress. Consider reallocating resources or adjusting the deadline.',
                'suggested_action': 'Schedule a focused pairing session with Sam to resolve remaining 20%. Alternatively, split the remaining work into a separate task.',
                'context_data': {'task_id': 8263, 'days_overdue': 9, 'progress': 80, 'assigned_to': 'Alex Chen'},
                'status': 'pending',
                'estimated_minutes': 5,
            },
            {
                'created_for': self.alex,
                'item_type': 'unassigned_task',
                'priority_level': 'action_required',
                'title': 'Database Schema & Migrations has no assignee',
                'description': 'Database Schema & Migrations is In Progress but unassigned. This task blocks User Management API and is on the critical path.',
                'suggested_action': 'Assign to Sam Rivera who has database expertise, or redistribute current workload to free up capacity.',
                'context_data': {'task_id': 8264, 'column': 'In Progress', 'blocks': ['User Management API']},
                'status': 'pending',
                'estimated_minutes': 2,
            },
            {
                'created_for': self.sam,
                'item_type': 'overallocated',
                'priority_level': 'awareness',
                'title': 'Sam Rivera has 10 tasks — above team average',
                'description': 'Sam Rivera is assigned to 10 tasks (team avg: 8.7). Three tasks are in high-priority status. Consider load balancing.',
                'suggested_action': 'Review Sam\'s task list and consider moving API Rate Limiting or Performance Optimization to Jordan.',
                'context_data': {'user': 'Sam Rivera', 'task_count': 10, 'high_priority': 3, 'team_avg': 8.7},
                'status': 'pending',
                'estimated_minutes': 3,
            },
            {
                'created_for': self.alex,
                'item_type': 'deadline_approaching',
                'priority_level': 'awareness',
                'title': 'Authentication System review needs completion',
                'description': 'Authentication System has been in "In Review" for 4 days. The Security Audit Readiness commitment depends on this completing soon.',
                'suggested_action': 'Expedite the code review. Tag Jordan for a second pair of eyes.',
                'context_data': {'task_id': 8262, 'days_in_review': 4, 'related_commitment': 'Security Audit Readiness'},
                'status': 'pending',
                'estimated_minutes': 3,
            },
            {
                'created_for': self.jordan,
                'item_type': 'scope_change',
                'priority_level': 'awareness',
                'title': 'Accessibility Compliance may require external audit',
                'description': 'The Accessibility Compliance task may need an external WCAG 2.1 audit based on client requirements. This could add 5-7 days and $3,000-5,000 to the budget.',
                'suggested_action': 'Discuss with Alex whether to include WCAG audit in current sprint or defer to post-launch.',
                'context_data': {'task_id': 8283, 'potential_delay_days': 7, 'potential_cost': 5000},
                'status': 'snoozed',
                'estimated_minutes': 10,
            },
            {
                'created_for': self.alex,
                'item_type': 'budget_threshold',
                'priority_level': 'quick_win',
                'title': 'Budget at 24.6% — on track for current sprint',
                'description': 'Project has spent $18,466 of $75,000 (24.6%). At current velocity, the project is on budget. However, if the scope change for accessibility audit is approved, budget utilization could reach 31%.',
                'suggested_action': 'No immediate action needed. Monitor if accessibility audit is approved.',
                'context_data': {'budget_total': 75000, 'budget_spent': 18466, 'pct': 24.6},
                'status': 'resolved',
                'estimated_minutes': 1,
            },
            {
                'created_for': self.alex,
                'item_type': 'ai_recommendation',
                'priority_level': 'quick_win',
                'title': 'Consider parallel-tracking Search & Notification tasks',
                'description': 'AI analysis shows Search & Indexing Engine and Notification Service have no dependency between them. Running them in parallel could save 3-4 days on the critical path.',
                'suggested_action': 'Assign Notification Service to Jordan and keep Search with Sam. Both can proceed independently.',
                'context_data': {'tasks': ['Search & Indexing Engine', 'Notification Service'], 'potential_savings_days': 4},
                'status': 'resolved',
                'estimated_minutes': 2,
            },
        ]

        for item_data in items:
            status = item_data.pop('status')
            di = DecisionItem.objects.create(board=self.board, status=status, **item_data)

            # Set resolved_at for resolved items
            if status == 'resolved':
                DecisionItem.objects.filter(pk=di.pk).update(
                    resolved_at=self.now - timedelta(days=1),
                    resolved_by=self.alex,
                )
            elif status == 'snoozed':
                DecisionItem.objects.filter(pk=di.pk).update(
                    snoozed_until=self.now + timedelta(days=3),
                )
            count += 1

        self.stdout.write(f'   ✅ Created {count} decision items')
        return count

    # -----------------------------------------------------------------
    #  5. PROJECT STAKEHOLDERS
    # -----------------------------------------------------------------
    def _create_stakeholders(self):
        from kanban.stakeholder_models import ProjectStakeholder

        self.stdout.write(self.style.NOTICE('\n👥 Creating Project Stakeholders...'))

        if ProjectStakeholder.objects.filter(board=self.board).exists():
            self.stdout.write('   ⏭️  Stakeholders already exist, skipping')
            return 0

        count = 0
        stakeholders = [
            {
                'name': 'Dr. Priya Sharma',
                'role': 'VP of Engineering',
                'organization': 'Acme Corporation',
                'email': 'priya.sharma@acme.example.com',
                'influence_level': 'high',
                'interest_level': 'high',
                'current_engagement': 'collaborate',
                'desired_engagement': 'collaborate',
                'notes': 'Primary executive sponsor. Reviews progress weekly. Approves budget changes >$5K.',
                'created_by': self.alex,
            },
            {
                'name': 'Marcus Johnson',
                'role': 'Product Lead',
                'organization': 'Acme Corporation',
                'email': 'marcus.johnson@acme.example.com',
                'influence_level': 'high',
                'interest_level': 'high',
                'current_engagement': 'collaborate',
                'desired_engagement': 'empower',
                'notes': 'Owns the product roadmap. Provides acceptance criteria for all user-facing features. Wants more direct involvement in sprint planning.',
                'created_by': self.alex,
            },
            {
                'name': 'Lisa Chen',
                'role': 'Security Officer',
                'organization': 'Acme Corporation',
                'email': 'lisa.chen@acme.example.com',
                'influence_level': 'medium',
                'interest_level': 'high',
                'current_engagement': 'consult',
                'desired_engagement': 'involve',
                'notes': 'Responsible for security compliance. Will conduct the external security audit. Needs to review Authentication System and API Rate Limiting before go-live.',
                'created_by': self.sam,
            },
            {
                'name': 'David Park',
                'role': 'UX Designer',
                'organization': 'Acme Corporation',
                'email': 'david.park@acme.example.com',
                'influence_level': 'medium',
                'interest_level': 'medium',
                'current_engagement': 'involve',
                'desired_engagement': 'involve',
                'notes': 'Designed the dashboard wireframes. Available for UI/UX Polish and Accessibility Compliance tasks. Meets with Jordan weekly.',
                'created_by': self.jordan,
            },
            {
                'name': 'Rachel Torres',
                'role': 'Client Success Manager',
                'organization': 'Acme Corporation',
                'email': 'rachel.torres@acme.example.com',
                'influence_level': 'low',
                'interest_level': 'medium',
                'current_engagement': 'inform',
                'desired_engagement': 'consult',
                'notes': 'Represents customer voice. Will manage beta users and collect feedback post-launch. Wants earlier access to feature previews.',
                'created_by': self.alex,
            },
            {
                'name': 'James Wilson',
                'role': 'DevOps Lead',
                'organization': 'Acme Corporation',
                'email': 'james.wilson@acme.example.com',
                'influence_level': 'medium',
                'interest_level': 'low',
                'current_engagement': 'inform',
                'desired_engagement': 'consult',
                'notes': 'Manages CI/CD pipeline and deployment infrastructure. Needs 2 weeks notice before go-live for production environment prep.',
                'created_by': self.alex,
            },
        ]

        for sh_data in stakeholders:
            ProjectStakeholder.objects.create(
                board=self.board,
                is_active=True,
                **sh_data,
            )
            count += 1

        self.stdout.write(f'   ✅ Created {count} project stakeholders')
        return count
