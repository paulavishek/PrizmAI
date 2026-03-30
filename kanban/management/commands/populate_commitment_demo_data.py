"""
Populate demo data for Living Commitment Protocols
===================================================
Creates 2 commitment protocols with realistic confidence signals,
prediction market bets, and user credibility scores for the
Software Development demo board.

Usage:
    python manage.py populate_commitment_demo_data
    python manage.py populate_commitment_demo_data --reset

Standalone or called automatically from populate_all_demo_data.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from datetime import timedelta, date, time, datetime
import json

from accounts.models import Organization
from kanban.models import Board, Task
from kanban.commitment_models import (
    CommitmentProtocol,
    ConfidenceSignal,
    CommitmentBet,
    UserCredibilityScore,
)


class Command(BaseCommand):
    help = 'Populate demo Commitment Protocols with signals, bets, and credibility scores'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing commitment demo data before creating new data',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('\n📋 Populating Commitment Protocol Demo Data...'))

        # --- Get demo organization ---
        try:
            demo_org = Organization.objects.get(is_demo=True, name='Demo - Acme Corporation')
        except Organization.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                '❌ Demo organization not found. Run create_demo_organization first.'
            ))
            return

        # --- Get demo board ---
        board = Board.objects.filter(
            organization=demo_org,
            is_official_demo_board=True,
            name__icontains='software',
        ).first()
        if not board:
            self.stdout.write(self.style.ERROR(
                '❌ Software Development demo board not found.'
            ))
            return

        # --- Get demo users ---
        alex = User.objects.filter(username='alex_chen_demo').first()
        sam = User.objects.filter(username='sam_rivera_demo').first()
        jordan = User.objects.filter(username='jordan_taylor_demo').first()
        if not all([alex, sam, jordan]):
            self.stdout.write(self.style.ERROR(
                '❌ Demo users not found. Run create_demo_organization first.'
            ))
            return

        # --- Reset if requested ---
        if options['reset']:
            deleted = CommitmentProtocol.objects.filter(board=board).delete()
            # Also clear credibility scores for demo users
            UserCredibilityScore.objects.filter(
                user__in=[alex, sam, jordan]
            ).delete()
            self.stdout.write(f'   ✓ Cleared commitment data ({deleted[0]} objects)')

        # --- Idempotency: skip if protocols already exist ---
        if CommitmentProtocol.objects.filter(board=board).exists():
            self.stdout.write(self.style.SUCCESS(
                '   ✅ Commitment protocols already exist — skipping'
            ))
            return

        now = timezone.now()
        today = now.date()

        with transaction.atomic():
            stats = {'protocols': 0, 'signals': 0, 'bets': 0, 'credibility': 0}

            # =================================================================
            # CREDIBILITY SCORES (needed before bets)
            # =================================================================
            for user in [alex, sam, jordan]:
                _, created = UserCredibilityScore.objects.get_or_create(
                    user=user,
                    defaults={
                        'score': 50.0,
                        'total_bets': 0,
                        'correct_bets': 0,
                        'tokens_remaining': 100,
                    },
                )
                if created:
                    stats['credibility'] += 1

            # =================================================================
            # PROTOCOL 1: "Ship MVP Platform v1.0" — At Risk showcase
            # =================================================================
            protocol1 = CommitmentProtocol.objects.create(
                board=board,
                title='Ship MVP Platform v1.0',
                description=(
                    'Deliver the complete MVP platform including authentication, '
                    'dashboard, file management, and core API integrations to '
                    'production by target date.'
                ),
                target_date=today + timedelta(days=30),
                initial_confidence=0.80,
                current_confidence=0.52,
                confidence_halflife_days=14,
                decay_model='exponential',
                status='at_risk',
                created_by=alex,
                negotiation_threshold=0.40,
                last_signal_date=now - timedelta(days=2),
                ai_reasoning=(
                    '**Confidence Analysis — Ship MVP Platform v1.0**\n\n'
                    'Current confidence has declined from 80% to 52% over the past '
                    '16 days, placing this commitment in "At Risk" territory.\n\n'
                    '**Key factors driving the decline:**\n'
                    '1. **Third-party dependency block** (Search & Indexing Engine): '
                    'The vendor API migration pushed the integration timeline back by '
                    '2 weeks. This is the single largest confidence impact (-21 pts).\n'
                    '2. **Scope creep**: Three GDPR compliance tasks were added mid-sprint '
                    'after a legal review, increasing total scope by ~15%.\n\n'
                    '**Positive signals:**\n'
                    '- Dashboard UI completed ahead of schedule (+3 pts)\n'
                    '- File Upload System passed security review and pen testing (+6 pts)\n\n'
                    '**Recommendation:** If the search API dependency is not resolved '
                    'within 5 business days, consider triggering scope renegotiation. '
                    'The team velocity on non-blocked tasks remains strong, suggesting '
                    'a partial scope reduction could restore confidence above 70%.'
                ),
                baseline_snapshot={
                    'total_tasks': 30,
                    'completed_tasks': 11,
                    'in_progress_tasks': 7,
                    'blocked_tasks': 1,
                    'team_size': 3,
                    'budget_utilization_pct': 45,
                },
            )
            # Override created_at to 16 days ago
            CommitmentProtocol.objects.filter(pk=protocol1.pk).update(
                created_at=now - timedelta(days=16)
            )
            stats['protocols'] += 1

            # --- Link tasks to Protocol 1 ---
            p1_task_names = [
                'Dashboard UI Development',
                'File Upload System',
                'Notification Service',
                'User Management API',
                'Search & Indexing Engine',
                'Real-time Collaboration',
            ]
            p1_tasks = Task.objects.filter(
                column__board=board,
                title__in=p1_task_names,
            )
            protocol1.linked_tasks.set(p1_tasks)

            # --- Stakeholders ---
            protocol1.stakeholders.set([alex, sam, jordan])

            # --- Signals for Protocol 1 ---
            # Pre-calculated using the apply_signal formula:
            # Positive: new = before + (1 - before) * value * 0.5
            # Negative: new = before + before * value * 0.5
            p1_signals_data = [
                {
                    'signal_type': 'milestone_hit',
                    'signal_value': 0.30,
                    'description': (
                        'Dashboard UI core components completed ahead of schedule — '
                        'all 8 wireframes implemented and passing visual regression tests.'
                    ),
                    'confidence_before': 0.80,
                    'confidence_after': 0.83,
                    'recorded_by': sam,
                    'related_task_title': 'Dashboard UI Development',
                    'day_offset': -14,
                },
                {
                    'signal_type': 'dependency_blocked',
                    'signal_value': -0.50,
                    'description': (
                        'Third-party search API vendor pushed back integration timeline '
                        'by 2 weeks due to API v3 migration — Search & Indexing Engine blocked.'
                    ),
                    'confidence_before': 0.83,
                    'confidence_after': 0.62,
                    'recorded_by': sam,
                    'related_task_title': 'Search & Indexing Engine',
                    'day_offset': -10,
                },
                {
                    'signal_type': 'task_added',
                    'signal_value': -0.30,
                    'description': (
                        'Three new GDPR compliance tasks added to scope mid-sprint '
                        'after legal review — increases total task count by 15%.'
                    ),
                    'confidence_before': 0.62,
                    'confidence_after': 0.53,
                    'recorded_by': alex,
                    'related_task_title': None,
                    'day_offset': -6,
                },
                {
                    'signal_type': 'task_completed',
                    'signal_value': 0.25,
                    'description': (
                        'File Upload System completed security review and '
                        'penetration testing — all critical paths verified.'
                    ),
                    'confidence_before': 0.53,
                    'confidence_after': 0.59,
                    'recorded_by': jordan,
                    'related_task_title': 'File Upload System',
                    'day_offset': -2,
                },
            ]

            for sig_data in p1_signals_data:
                related_task = None
                if sig_data['related_task_title']:
                    related_task = Task.objects.filter(
                        column__board=board,
                        title=sig_data['related_task_title'],
                    ).first()

                signal = ConfidenceSignal.objects.create(
                    protocol=protocol1,
                    signal_type=sig_data['signal_type'],
                    signal_value=sig_data['signal_value'],
                    description=sig_data['description'],
                    confidence_before=sig_data['confidence_before'],
                    confidence_after=sig_data['confidence_after'],
                    ai_generated=False,
                    recorded_by=sig_data['recorded_by'],
                    related_task=related_task,
                )
                # Override auto_now_add timestamp
                ConfidenceSignal.objects.filter(pk=signal.pk).update(
                    timestamp=now + timedelta(days=sig_data['day_offset'])
                )
                stats['signals'] += 1

            # --- Bets for Protocol 1 ---
            bet1 = CommitmentBet.objects.create(
                protocol=protocol1,
                bettor=sam,
                tokens_wagered=35,
                confidence_estimate=0.45,
                reasoning=(
                    'The search API blocker will take at least another sprint to '
                    'resolve. Third-party dependency patterns like this always '
                    'underestimate resolution time. I\'d reduce scope before '
                    'extending the deadline.'
                ),
                is_anonymous=True,
            )
            CommitmentBet.objects.filter(pk=bet1.pk).update(
                placed_at=now - timedelta(days=8)
            )
            # Deduct tokens
            UserCredibilityScore.objects.filter(user=sam).update(
                tokens_remaining=65,  # 100 - 35
                total_bets=1,
            )
            stats['bets'] += 1

            bet2 = CommitmentBet.objects.create(
                protocol=protocol1,
                bettor=jordan,
                tokens_wagered=50,
                confidence_estimate=0.62,
                reasoning=(
                    'Team velocity on core features is strong — Dashboard and '
                    'File Upload were both ahead of schedule. If the search '
                    'dependency unblocks this week, we have enough runway. '
                    'The scope additions are manageable.'
                ),
                is_anonymous=True,
            )
            CommitmentBet.objects.filter(pk=bet2.pk).update(
                placed_at=now - timedelta(days=5)
            )
            UserCredibilityScore.objects.filter(user=jordan).update(
                tokens_remaining=50,  # 100 - 50
                total_bets=1,
            )
            stats['bets'] += 1

            # =================================================================
            # PROTOCOL 2: "Complete Security Audit & Compliance" — Active/healthy
            # =================================================================
            protocol2 = CommitmentProtocol.objects.create(
                board=board,
                title='Complete Security Audit & Compliance',
                description=(
                    'Pass full security audit covering authentication, data handling, '
                    'API endpoints, and achieve SOC 2 readiness before launch.'
                ),
                target_date=today + timedelta(days=21),
                initial_confidence=0.90,
                current_confidence=0.78,
                confidence_halflife_days=14,
                decay_model='exponential',
                status='active',
                created_by=jordan,
                negotiation_threshold=0.40,
                last_signal_date=now - timedelta(days=3),
                ai_reasoning=(
                    '**Confidence Analysis — Security Audit & Compliance**\n\n'
                    'Confidence is at 78%, down from 90% initial. The protocol '
                    'remains in "Active" status with a healthy margin above '
                    'the 40% negotiation threshold.\n\n'
                    '**Positive:** Authentication system passed OWASP Top 10 '
                    'compliance review, demonstrating strong security fundamentals.\n\n'
                    '**Risk factor:** A new PCI-DSS requirement revision was '
                    'announced, requiring validation of payment data handling '
                    'compliance. Impact is moderate — the team has experience '
                    'with PCI-DSS and the revision is incremental.\n\n'
                    '**Outlook:** On track if the PCI-DSS validation completes '
                    'within the next sprint. No renegotiation expected.'
                ),
                baseline_snapshot={
                    'total_tasks': 30,
                    'completed_tasks': 11,
                    'security_tasks': 5,
                    'team_size': 3,
                },
            )
            CommitmentProtocol.objects.filter(pk=protocol2.pk).update(
                created_at=now - timedelta(days=10)
            )
            stats['protocols'] += 1

            # --- Link tasks to Protocol 2 ---
            p2_task_names = [
                'Authentication System',
                'Authentication Testing Suite',
                'Security Audit & Fixes',
            ]
            p2_tasks = Task.objects.filter(
                column__board=board,
                title__in=p2_task_names,
            )
            protocol2.linked_tasks.set(p2_tasks)
            protocol2.stakeholders.set([jordan, alex])

            # --- Signals for Protocol 2 ---
            p2_signals_data = [
                {
                    'signal_type': 'task_completed',
                    'signal_value': 0.25,
                    'description': (
                        'Authentication System passed code review — '
                        'OWASP Top 10 compliance verified across all endpoints.'
                    ),
                    'confidence_before': 0.90,
                    'confidence_after': 0.91,
                    'recorded_by': sam,
                    'related_task_title': 'Authentication System',
                    'day_offset': -7,
                },
                {
                    'signal_type': 'external_risk',
                    'signal_value': -0.30,
                    'description': (
                        'New PCI-DSS requirement revision announced — '
                        'need to validate payment data handling compliance. '
                        'Impact assessment in progress.'
                    ),
                    'confidence_before': 0.91,
                    'confidence_after': 0.77,
                    'recorded_by': jordan,
                    'related_task_title': None,
                    'day_offset': -3,
                },
            ]

            for sig_data in p2_signals_data:
                related_task = None
                if sig_data['related_task_title']:
                    related_task = Task.objects.filter(
                        column__board=board,
                        title=sig_data['related_task_title'],
                    ).first()

                signal = ConfidenceSignal.objects.create(
                    protocol=protocol2,
                    signal_type=sig_data['signal_type'],
                    signal_value=sig_data['signal_value'],
                    description=sig_data['description'],
                    confidence_before=sig_data['confidence_before'],
                    confidence_after=sig_data['confidence_after'],
                    ai_generated=False,
                    recorded_by=sig_data['recorded_by'],
                    related_task=related_task,
                )
                ConfidenceSignal.objects.filter(pk=signal.pk).update(
                    timestamp=now + timedelta(days=sig_data['day_offset'])
                )
                stats['signals'] += 1

            # --- Bet for Protocol 2 ---
            bet3 = CommitmentBet.objects.create(
                protocol=protocol2,
                bettor=alex,
                tokens_wagered=40,
                confidence_estimate=0.75,
                reasoning=(
                    'Jordan\'s track record on security tasks is excellent. '
                    'The PCI-DSS revision is a standard incremental update, '
                    'shouldn\'t significantly impact the timeline.'
                ),
                is_anonymous=True,
            )
            CommitmentBet.objects.filter(pk=bet3.pk).update(
                placed_at=now - timedelta(days=4)
            )
            UserCredibilityScore.objects.filter(user=alex).update(
                tokens_remaining=60,  # 100 - 40
                total_bets=1,
            )
            stats['bets'] += 1

        self.stdout.write(self.style.SUCCESS(
            f'   ✅ Commitments: {stats["protocols"]} protocols, '
            f'{stats["signals"]} signals, {stats["bets"]} bets, '
            f'{stats["credibility"]} credibility scores'
        ))
