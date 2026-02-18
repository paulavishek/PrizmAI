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
            self.stdout.write(self.style.SUCCESS(f'✅ Found organization: {self.demo_org.name}'))
        except Organization.DoesNotExist:
            self.stdout.write(self.style.ERROR('❌ Demo - Acme Corporation not found!'))
            self.stdout.write('   Please run: python manage.py create_demo_organization')
            return

        # Get demo boards
        self.demo_boards = Board.objects.filter(organization=self.demo_org)
        self.stdout.write(f'   Found {self.demo_boards.count()} demo boards')

        # Get demo users
        self.demo_admin = User.objects.filter(username='demo_admin_solo').first()
        self.alex = User.objects.filter(username='alex_chen_demo').first()
        self.sam = User.objects.filter(username='sam_rivera_demo').first()
        self.jordan = User.objects.filter(username='jordan_taylor_demo').first()

        self.demo_users = [u for u in [self.demo_admin, self.alex, self.sam, self.jordan] if u]
        self.stdout.write(f'   Found {len(self.demo_users)} demo users')

        if not self.demo_admin:
            self.stdout.write(self.style.ERROR('❌ demo_admin_solo user not found!'))
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
        self.stdout.write(self.style.WARNING('\n🗑️  Clearing existing conflict demo data...'))
        
        # Delete in correct order for foreign key constraints
        ConflictNotification.objects.filter(conflict__board__in=self.demo_boards).delete()
        ConflictResolution.objects.filter(conflict__board__in=self.demo_boards).delete()
        ConflictDetection.objects.filter(board__in=self.demo_boards).delete()
        ResolutionPattern.objects.filter(board__in=self.demo_boards).delete()
        
        self.stdout.write(self.style.SUCCESS('   ✅ Cleared existing data'))

    def get_conflict_configs(self):
        """Return conflict configurations for each board"""
        now = timezone.now()
        
        return {
            'Software Development': [
                {
                    'conflict_type': 'resource',
                    'severity': 'high',
                    'title': 'Sam Rivera has excessive workload',
                    'description': 'Sam has 8 tasks assigned with overlapping deadlines in the next 2 weeks. This exceeds the recommended workload of 5 tasks per developer and may cause delays or quality issues.',
                    'conflict_data': {
                        'affected_user': 'sam_rivera_demo',
                        'current_tasks': 8,
                        'recommended_max': 5,
                        'overdue_risk': 3,
                        'affected_task_titles': [
                            'Build dashboard UI',
                            'Implement file upload system',
                            'Create notification system',
                            'Build user management API',
                            'Implement search functionality'
                        ]
                    },
                    'ai_confidence_score': 92,
                    'suggested_resolutions': [
                        {
                            'type': 'reassign',
                            'title': 'Reassign 2 tasks to Jordan',
                            'confidence': 85,
                            'impact': 'Reduces Sam\'s workload by 25%'
                        },
                        {
                            'type': 'reschedule',
                            'title': 'Extend deadlines for lower priority tasks',
                            'confidence': 75,
                            'impact': 'Spreads workload over 3 weeks'
                        }
                    ],
                    'status': 'active'
                },
                {
                    'conflict_type': 'dependency',
                    'severity': 'medium',
                    'title': 'API integration blocked by incomplete authentication',
                    'description': 'The "Implement file upload system" task depends on "Build user management API" which is still in progress. Current progress on the blocking task is only 40%.',
                    'conflict_data': {
                        'blocked_task': 'Implement file upload system',
                        'blocking_task': 'Build user management API',
                        'blocking_progress': 40,
                        'days_blocked': 3,
                        'estimated_delay': 2
                    },
                    'ai_confidence_score': 88,
                    'suggested_resolutions': [
                        {
                            'type': 'modify_dependency',
                            'title': 'Use mock API for initial development',
                            'confidence': 80,
                            'impact': 'Allows parallel progress on both tasks'
                        },
                        {
                            'type': 'add_resources',
                            'title': 'Pair programming to accelerate blocking task',
                            'confidence': 70,
                            'impact': 'Could reduce blocking time by 50%'
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
                        'task_1': 'Performance optimization',
                        'task_2': 'Security audit fixes',
                        'overlap_days': 5,
                        'shared_resource': 'Sam Rivera'
                    },
                    'ai_confidence_score': 72,
                    'suggested_resolutions': [
                        {
                            'type': 'reschedule',
                            'title': 'Stagger tasks by 1 week',
                            'confidence': 85,
                            'impact': 'Better focus on each task'
                        }
                    ],
                    'status': 'resolved'
                }
            ],
        }

    def create_conflicts(self):
        """Create conflict detection records and resolutions"""
        self.stdout.write(self.style.NOTICE('\n⚠️  Creating Conflicts and Resolutions...'))
        
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

                # Add affected users
                affected_users = random.sample(self.demo_users, min(2, len(self.demo_users)))
                conflict.affected_users.set(affected_users)

                conflicts_created += 1
                self.stdout.write(f'   ✅ Created: {board_name} → {config["title"][:50]}...')

                # Create resolutions for this conflict
                for i, res_data in enumerate(config['suggested_resolutions']):
                    resolution = ConflictResolution.objects.create(
                        conflict=conflict,
                        resolution_type=res_data['type'],
                        title=res_data['title'],
                        description=f"Suggested resolution: {res_data['title']}",
                        ai_confidence=res_data['confidence'],
                        ai_reasoning=f"Based on analysis, this resolution has a {res_data['confidence']}% confidence of success. Expected impact: {res_data['impact']}",
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

    def create_resolution_patterns(self):
        """Create resolution patterns for learning"""
        self.stdout.write(self.style.NOTICE('\n📊 Creating Resolution Patterns...'))
        
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
        self.stdout.write(self.style.NOTICE('\n🔔 Creating Conflict Notifications...'))
        
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
📊 Total Conflict Demo Data:
   • Total Conflicts: {total_conflicts}
     - Active: {active_conflicts}
     - Resolved: {resolved_conflicts}
   • Resolution Options: {total_resolutions}
   • Learning Patterns: {total_patterns}
   • Notifications: {total_notifications}

🎉 Conflict detection demo is now populated!
''')
