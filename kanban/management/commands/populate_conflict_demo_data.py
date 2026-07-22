"""
Management Command: Populate Conflict Demo Data
================================================
Creates realistic conflict detection scenarios for demo boards to showcase
the conflict detection and resolution features.

Usage:
    python manage.py populate_conflict_demo_data
    python manage.py populate_conflict_demo_data --reset  # Clear and recreate

This creates:
- Resource conflicts (team members overloaded)
- Schedule conflicts (overlapping deadlines)
- Dependency conflicts (blocked tasks)
- Resolution suggestions with AI confidence scores
- Resolution patterns for learning
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import random

from kanban.models import Board, Task
from kanban.conflict_models import (
    ConflictDetection, ConflictResolution, ResolutionPattern, ConflictNotification
)
from accounts.models import Organization
from accounts.demo_personas import DEMO_PERSONAS


class Command(BaseCommand):
    help = 'Populate demo boards with conflict detection demo data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Clear existing conflict demo data before creating new data',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('=' * 80))
        self.stdout.write(self.style.NOTICE('POPULATING CONFLICT DEMO DATA'))
        self.stdout.write(self.style.NOTICE('=' * 80))

        # Get demo organization
        try:
            self.demo_org = Organization.objects.get(name='Demo - Acme Corporation')
            self.stdout.write(self.style.SUCCESS(f'[OK] Found organization: {self.demo_org.name}'))
        except Organization.DoesNotExist:
            self.stdout.write(self.style.ERROR('[FAIL] Demo - Acme Corporation not found!'))
            self.stdout.write('   Please run: python manage.py create_demo_organization')
            return

        # Get demo boards
        self.demo_boards = Board.objects.filter(organization=self.demo_org)
        self.stdout.write(f'   Found {self.demo_boards.count()} demo boards')

        # Get demo users - try canonical names first, then fall back to any board member
        self.demo_admin = User.objects.filter(username='demo_admin_solo').first()
        self.alex = User.objects.filter(username=DEMO_PERSONAS['lead']['username']).first()
        self.sam = User.objects.filter(username=DEMO_PERSONAS['frontend']['username']).first()
        self.jordan = User.objects.filter(username=DEMO_PERSONAS['devops']['username']).first()

        self.demo_users = [u for u in [self.demo_admin, self.alex, self.sam, self.jordan] if u]

        # Fallback: if demo_admin_solo doesn't exist, use any board member as admin
        if not self.demo_admin:
            self.demo_admin = (
                self.alex or self.sam or self.jordan
                or User.objects.filter(board_memberships__board__in=self.demo_boards).first()
            )
            if self.demo_admin:
                self.stdout.write(self.style.WARNING(
                    f'   [WARN]  demo_admin_solo not found - using "{self.demo_admin.username}" as admin'
                ))

        self.demo_users = [u for u in [self.demo_admin, self.alex, self.sam, self.jordan] if u]
        # Deduplicate while preserving order
        seen = set()
        self.demo_users = [u for u in self.demo_users if not (u.id in seen or seen.add(u.id))]
        self.stdout.write(f'   Found {len(self.demo_users)} demo users')

        if not self.demo_admin:
            self.stdout.write(self.style.ERROR('[FAIL] No demo users found! Run create_demo_organization first.'))
            return

        # Clear existing data if requested
        if options['reset']:
            self.clear_conflict_data()

        # Create demo data
        self.create_conflicts()
        self.create_resolution_patterns()
        self.create_notifications()

        # Summary
        self.print_summary()

    def clear_conflict_data(self):
        """Clear existing conflict demo data"""
        self.stdout.write(self.style.WARNING('\n  Clearing existing conflict demo data...'))
        
        # Delete in correct order for foreign key constraints
        ConflictNotification.objects.filter(conflict__board__in=self.demo_boards).delete()
        ConflictResolution.objects.filter(conflict__board__in=self.demo_boards).delete()
        ConflictDetection.objects.filter(board__in=self.demo_boards).delete()
        ResolutionPattern.objects.filter(board__in=self.demo_boards).delete()
        
        self.stdout.write(self.style.SUCCESS('   [OK] Cleared existing data'))

    def get_conflict_configs(self):
        """Return conflict configurations for each board"""
        now = timezone.now()
        
        return {
            'Software Development': [
                {
                    'conflict_type': 'resource',
                    'severity': 'high',
                    'title': 'Marcus Chen has excessive workload',
                    'description': 'Marcus has 11 tasks assigned with overlapping deadlines in the next 2 weeks. This exceeds the recommended workload of 8 tasks per developer and may cause delays or quality issues.',
                    'conflict_data': {
                        'affected_user': 'marcus.chen',
                        'current_tasks': 11,
                        'recommended_max': 8,
                        'overdue_risk': 3,
                        'affected_task_titles': [
                            'Dashboard UI Development',
                            'User Management API',
                            'Search & Indexing Engine',
                            'API Rate Limiting',
                            'Performance Optimization'
                        ]
                    },
                    'ai_confidence_score': 92,
                    'suggested_resolutions': [
                        {
                            'type': 'reassign',
                            'title': 'Reassign 2 tasks to Jordan',
                            'confidence': 85,
                            'impact': 'Reduces Sam\'s workload by 25%',
                            'reasoning': (
                                "Reassigning tasks to a team member with available capacity directly removes the "
                                "overallocation at its source, giving each task a dedicated owner with realistic "
                                "bandwidth to meet its deadline without quality trade-offs from split focus. "
                                "The expected outcome is that Sam's remaining tasks proceed at full pace while "
                                "Jordan takes ownership of the reassigned work with a clear scope. "
                                "A brief handover session is recommended so Jordan has enough context to avoid "
                                "ramp-up delays. "
                                "Based on 15 past resolutions of this type on your projects, this approach has "
                                "an 80% success rate (+15% confidence adjustment)."
                            )
                        },
                        {
                            'type': 'reschedule',
                            'title': 'Extend deadlines for lower priority tasks',
                            'confidence': 75,
                            'impact': 'Spreads workload over 3 weeks',
                            'reasoning': (
                                "Spreading deadlines over a longer window reduces the simultaneous demand on Sam, "
                                "eliminating the bottleneck without changing task ownership. "
                                "Sam can then give focused attention to each task in sequence, reducing the risk "
                                "of delays or errors that arise from context-switching between 11 concurrent items. "
                                "This approach requires downstream dependencies and stakeholder expectations to "
                                "tolerate the adjusted timeline before committing. "
                                "Based on 10 past resolutions of this type on your projects, this approach has "
                                "a 70% success rate (+8% confidence adjustment)."
                            )
                        }
                    ],
                    'status': 'active'
                },
                {
                    'conflict_type': 'dependency',
                    'severity': 'medium',
                    'title': 'API integration blocked by incomplete authentication',
                    'description': 'The "File Upload System" task depends on "User Management API" which is still in progress. Current progress on the blocking task is only 60%.',
                    'conflict_data': {
                        'blocked_task': 'File Upload System',
                        'blocking_task': 'User Management API',
                        'blocking_progress': 60,
                        'days_blocked': 3,
                        'estimated_delay': 2
                    },
                    'ai_confidence_score': 88,
                    'suggested_resolutions': [
                        {
                            'type': 'modify_dependency',
                            'title': 'Use mock API for initial development',
                            'confidence': 80,
                            'impact': 'Allows parallel progress on both tasks',
                            'reasoning': (
                                "Using a mock API decouples the File Upload System from its dependency on the "
                                "User Management API, allowing both workstreams to advance in parallel rather "
                                "than sequentially. "
                                "Once the real API is ready, integration can be completed with minimal rework "
                                "since both sides will have been developed against an agreed interface contract. "
                                "This requires both teams to define the API contract before work proceeds and "
                                "to maintain discipline to swap out the mock cleanly on completion. "
                                "Based on 8 past resolutions of this type on your projects, this approach has "
                                "a 75% success rate (+12% confidence adjustment)."
                            )
                        },
                        {
                            'type': 'add_resources',
                            'title': 'Pair programming to accelerate blocking task',
                            'confidence': 70,
                            'impact': 'Could reduce blocking time by 50%',
                            'reasoning': (
                                "Pairing a second developer on the blocking User Management API task directly "
                                "accelerates its completion, shortening the window during which the File Upload "
                                "System is held up. "
                                "Pair programming on this type of integration work typically reduces elapsed time "
                                "by 30-50% while also improving code quality through real-time review. "
                                "This works best when both contributors have enough codebase context to pair "
                                "effectively without a lengthy ramp-up period."
                            )
                        }
                    ],
                    'status': 'active'
                },
                {
                    'conflict_type': 'schedule',
                    'severity': 'low',
                    'title': 'Performance optimization overlaps with security audit',
                    'description': 'Both tasks are scheduled for the same sprint and require focused attention. Running them simultaneously may reduce effectiveness.',
                    'conflict_data': {
                        'task_1': 'Performance Optimization',
                        'task_2': 'Security Audit & Fixes',
                        'overlap_days': 5,
                        'shared_resource': 'Marcus Chen'
                    },
                    'ai_confidence_score': 72,
                    'suggested_resolutions': [
                        {
                            'type': 'reschedule',
                            'title': 'Stagger tasks by 1 week',
                            'confidence': 85,
                            'impact': 'Better focus on each task',
                            'reasoning': (
                                "Staggering the Performance Optimization and Security Audit tasks creates "
                                "dedicated focus windows for each, preventing the context-switching overhead "
                                "that reduces Sam's effectiveness when both are active in the same sprint. "
                                "The expected outcome is higher-quality output on both tasks and a lower risk "
                                "of one slipping because of pressure from the other. "
                                "This requires confirming with stakeholders that the later task's revised "
                                "timeline is acceptable before committing to the change. "
                                "Based on 20 past resolutions of this type on your projects, this approach has "
                                "an 85% success rate (+18% confidence adjustment)."
                            )
                        }
                    ],
                    'status': 'resolved'
                }
            ],
        }

    def create_conflicts(self):
        """Create conflict detection records and resolutions"""
        self.stdout.write(self.style.NOTICE('\n[WARN]  Creating Conflicts and Resolutions...'))
        
        conflicts_created = 0
        resolutions_created = 0
        now = timezone.now()
        conflict_configs = self.get_conflict_configs()

        for board in self.demo_boards:
            board_name = board.name
            if board_name not in conflict_configs:
                continue

            board_tasks = list(Task.objects.filter(column__board=board))

            for config in conflict_configs[board_name]:
                # Create conflict detection
                detected_at = now - timedelta(hours=random.randint(2, 72))
                resolved_at = detected_at + timedelta(hours=random.randint(4, 24)) if config['status'] == 'resolved' else None

                conflict = ConflictDetection.objects.create(
                    conflict_type=config['conflict_type'],
                    severity=config['severity'],
                    status=config['status'],
                    title=config['title'],
                    description=config['description'],
                    board=board,
                    conflict_data=config['conflict_data'],
                    ai_confidence_score=config['ai_confidence_score'],
                    suggested_resolutions=config['suggested_resolutions'],
                    auto_detection=True,
                    detection_run_id=f'demo_detection_{now.strftime("%Y%m%d")}',
                )
                
                # Update timestamps
                ConflictDetection.objects.filter(pk=conflict.pk).update(
                    detected_at=detected_at,
                    resolved_at=resolved_at
                )
                conflict.refresh_from_db()

                # Add affected tasks
                if board_tasks:
                    affected_tasks = random.sample(board_tasks, min(3, len(board_tasks)))
                    conflict.tasks.set(affected_tasks)

                # Add affected users — prefer the person actually named in the
                # conflict so THEY receive the notification (mirrors real
                # detection). Only fall back to a random demo user when no named
                # subject can be resolved from the conflict data.
                named_user = self._resolve_named_user(config)
                if named_user:
                    conflict.affected_users.add(named_user)
                else:
                    affected_users = random.sample(self.demo_users, min(2, len(self.demo_users)))
                    conflict.affected_users.set(affected_users)

                conflicts_created += 1
                self.stdout.write(f'   [OK] Created: {board_name} -> {config["title"][:50]}...')

                # Create resolutions for this conflict
                for i, res_data in enumerate(config['suggested_resolutions']):
                    resolution = ConflictResolution.objects.create(
                        conflict=conflict,
                        resolution_type=res_data['type'],
                        title=res_data['title'],
                        description=f"Suggested resolution: {res_data['title']}",
                        ai_confidence=res_data['confidence'],
                        ai_reasoning=res_data.get('reasoning', ''),
                        estimated_impact=res_data['impact'],
                        action_steps=[
                            f"Review current situation",
                            f"Implement {res_data['title'].lower()}",
                            f"Verify resolution effectiveness"
                        ],
                        auto_applicable=res_data['type'] in ['reassign', 'reschedule', 'adjust_dates'],
                        times_suggested=random.randint(1, 5),
                        times_accepted=random.randint(0, 3)
                    )
                    resolutions_created += 1

                    # If resolved, mark one resolution as chosen
                    if config['status'] == 'resolved' and i == 0:
                        conflict.chosen_resolution = resolution
                        conflict.resolution_effectiveness = random.randint(3, 5)
                        conflict.resolution_feedback = "Resolution applied successfully."
                        conflict.save()
                        
                        resolution.applied_at = resolved_at
                        resolution.applied_by = self.demo_admin
                        resolution.save()

        self.stdout.write(self.style.SUCCESS(f'   Created {conflicts_created} conflicts, {resolutions_created} resolutions'))

    def _resolve_named_user(self, config):
        """Resolve the User named in a conflict config's data, if any.

        Conflict configs reference their subject as ``affected_user`` (a
        username-like value, e.g. 'marcus.chen') or ``shared_resource`` (a
        display name, e.g. 'Marcus Chen'). Returns the matching User or None.
        """
        data = config.get('conflict_data', {}) or {}
        for cand in (data.get('affected_user'), data.get('shared_resource')):
            if not cand:
                continue
            user = User.objects.filter(username=cand).first()
            if user:
                return user
            for u in self.demo_users:
                display = (u.get_full_name() or u.username)
                if display.lower() == str(cand).lower():
                    return u
        return None

    def create_resolution_patterns(self):
        """Create resolution patterns for learning"""
        self.stdout.write(self.style.NOTICE('\n Creating Resolution Patterns...'))
        
        patterns_created = 0
        
        # Global patterns (applicable across boards)
        patterns = [
            {
                'conflict_type': 'resource',
                'resolution_type': 'reassign',
                'times_used': 15,
                'times_successful': 12,
                'success_rate': 0.80,
                'avg_effectiveness_rating': 4.2,
                'confidence_boost': 15.0
            },
            {
                'conflict_type': 'resource',
                'resolution_type': 'reschedule',
                'times_used': 10,
                'times_successful': 7,
                'success_rate': 0.70,
                'avg_effectiveness_rating': 3.8,
                'confidence_boost': 8.0
            },
            {
                'conflict_type': 'dependency',
                'resolution_type': 'modify_dependency',
                'times_used': 8,
                'times_successful': 6,
                'success_rate': 0.75,
                'avg_effectiveness_rating': 4.0,
                'confidence_boost': 12.0
            },
            {
                'conflict_type': 'schedule',
                'resolution_type': 'reschedule',
                'times_used': 20,
                'times_successful': 17,
                'success_rate': 0.85,
                'avg_effectiveness_rating': 4.3,
                'confidence_boost': 18.0
            },
            {
                'conflict_type': 'schedule',
                'resolution_type': 'reduce_scope',
                'times_used': 5,
                'times_successful': 3,
                'success_rate': 0.60,
                'avg_effectiveness_rating': 3.5,
                'confidence_boost': 5.0
            }
        ]

        for pattern_data in patterns:
            pattern, created = ResolutionPattern.objects.update_or_create(
                conflict_type=pattern_data['conflict_type'],
                resolution_type=pattern_data['resolution_type'],
                board=None,  # Global pattern
                defaults={
                    'times_used': pattern_data['times_used'],
                    'times_successful': pattern_data['times_successful'],
                    'success_rate': pattern_data['success_rate'],
                    'avg_effectiveness_rating': pattern_data['avg_effectiveness_rating'],
                    'confidence_boost': pattern_data['confidence_boost'],
                    'last_used_at': timezone.now() - timedelta(days=random.randint(1, 14))
                }
            )
            if created:
                patterns_created += 1

        self.stdout.write(self.style.SUCCESS(f'   Created {patterns_created} resolution patterns'))

    def create_notifications(self):
        """Create notifications for active conflicts"""
        self.stdout.write(self.style.NOTICE('\n Creating Conflict Notifications...'))
        
        notifications_created = 0
        
        active_conflicts = ConflictDetection.objects.filter(
            board__in=self.demo_boards,
            status='active'
        )

        for conflict in active_conflicts:
            # Use the model's ensure_notifications method
            created = conflict.ensure_notifications()
            notifications_created += created

        self.stdout.write(self.style.SUCCESS(f'   Created {notifications_created} notifications'))

    def print_summary(self):
        """Print summary of created data"""
        total_conflicts = ConflictDetection.objects.filter(board__in=self.demo_boards).count()
        active_conflicts = ConflictDetection.objects.filter(board__in=self.demo_boards, status='active').count()
        resolved_conflicts = ConflictDetection.objects.filter(board__in=self.demo_boards, status='resolved').count()
        total_resolutions = ConflictResolution.objects.filter(conflict__board__in=self.demo_boards).count()
        total_patterns = ResolutionPattern.objects.count()
        total_notifications = ConflictNotification.objects.filter(conflict__board__in=self.demo_boards).count()

        self.stdout.write(self.style.SUCCESS('\n' + '=' * 80))
        self.stdout.write(self.style.SUCCESS('CONFLICT DEMO DATA SUMMARY'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(f'''
 Total Conflict Demo Data:
   - Total Conflicts: {total_conflicts}
     - Active: {active_conflicts}
     - Resolved: {resolved_conflicts}
   - Resolution Options: {total_resolutions}
   - Learning Patterns: {total_patterns}
   - Notifications: {total_notifications}

 Conflict detection demo is now populated!
''')
