"""
Management command to populate demo boards with realistic tasks
Creates 90 tasks across 3 demo boards (30 per board) with proper assignments, dates, dependencies, and skills
Each board has 3 phases with 10 tasks per phase
Includes comprehensive demo data for all task fields including risk, skills, and collaboration
Also includes comments, activity logs, stakeholders, wiki links, and file attachment metadata
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta, date
from decimal import Decimal
from kanban.models import Board, Column, Task, TaskLabel, Organization, Comment, TaskActivity, TaskFile
from kanban.permission_models import Role
from kanban.budget_models import TimeEntry, ProjectBudget, TaskCost, ProjectROI
from kanban.burndown_models import TeamVelocitySnapshot, BurndownPrediction
from kanban.retrospective_models import ProjectRetrospective, LessonLearned, ImprovementMetric, RetrospectiveActionItem
from kanban.coach_models import CoachingSuggestion, PMMetrics, CoachingInsight
from kanban.stakeholder_models import ProjectStakeholder, StakeholderTaskInvolvement
import random
import os

User = get_user_model()

# Comment templates for realistic demo comments
COMMENT_TEMPLATES = [
    # Progress updates
    "Made good progress on this today. {progress_detail}",
    "Updated the implementation based on the latest requirements. Looking good so far!",
    "Just finished the initial draft. Ready for review.",
    "Ran into a small issue with {technical_detail}, but found a workaround.",
    "This is taking a bit longer than expected due to {complexity_reason}.",

    # Questions
    "@{mention} Could you take a look at this when you get a chance?",
    "Question: Should we prioritize performance or feature completeness here?",
    "Need clarification on the acceptance criteria for this task.",
    "Has anyone encountered this issue before? Looking for suggestions.",

    # Reviews and feedback
    "Code review complete. Left some minor suggestions for improvement.",
    "LGTM! Just a few minor style issues to address.",
    "Great work on this! The implementation is clean and well-documented.",
    "Approved with minor changes. Please update the documentation.",

    # Status updates
    "Blocked by dependency on {related_task}. Will resume once that's complete.",
    "Moving this to In Review - all tests passing.",
    "Deployed to staging for QA testing.",
    "All edge cases covered. This is ready for final review.",

    # Collaboration
    "Had a productive discussion with the team about this approach.",
    "Paired with @{mention} to work through the complex parts.",
    "Added comprehensive test coverage for the new functionality.",
    "Updated based on stakeholder feedback from yesterday's meeting.",
]

# Technical details for comment templates
TECHNICAL_DETAILS = [
    "the database connection pooling",
    "the authentication flow",
    "the API rate limiting",
    "the caching layer",
    "the WebSocket integration",
    "the file upload handler",
    "the search indexing",
    "the permission checks",
]

PROGRESS_DETAILS = [
    "Completed the core functionality and started on edge cases.",
    "The main feature is working, now adding polish and error handling.",
    "Integration with the existing system is complete.",
    "Unit tests are all passing, moving to integration tests.",
    "Documentation is updated with the new changes.",
]

COMPLEXITY_REASONS = [
    "some unexpected edge cases",
    "integration with legacy code",
    "performance optimization requirements",
    "additional security considerations",
    "cross-browser compatibility issues",
]

# Activity log templates
ACTIVITY_TEMPLATES = {
    'created': [
        "created this task",
        "added this task to the board",
    ],
    'moved': [
        "moved this task from {from_col} to {to_col}",
        "updated status to {to_col}",
    ],
    'assigned': [
        "assigned this task to {assignee}",
        "changed assignee to {assignee}",
    ],
    'updated': [
        "updated the description",
        "changed priority to {priority}",
        "updated the due date",
        "modified the complexity score",
        "added required skills",
        "updated progress to {progress}%",
    ],
    'commented': [
        "added a comment",
        "replied to a comment",
    ],
    'label_added': [
        "added label '{label}'",
    ],
    'label_removed': [
        "removed label '{label}'",
    ],
}

# Skill pools for different task categories
SOFTWARE_SKILLS = [
    {'name': 'Python', 'level': 'Advanced'},
    {'name': 'JavaScript', 'level': 'Advanced'},
    {'name': 'React', 'level': 'Intermediate'},
    {'name': 'Django', 'level': 'Advanced'},
    {'name': 'PostgreSQL', 'level': 'Intermediate'},
    {'name': 'REST API Design', 'level': 'Advanced'},
    {'name': 'Docker', 'level': 'Intermediate'},
    {'name': 'AWS', 'level': 'Intermediate'},
    {'name': 'CI/CD', 'level': 'Intermediate'},
    {'name': 'Git', 'level': 'Advanced'},
    {'name': 'TypeScript', 'level': 'Intermediate'},
    {'name': 'Testing', 'level': 'Intermediate'},
    {'name': 'Security', 'level': 'Intermediate'},
    {'name': 'System Design', 'level': 'Advanced'},
]

MARKETING_SKILLS = [
    {'name': 'Content Strategy', 'level': 'Advanced'},
    {'name': 'SEO/SEM', 'level': 'Intermediate'},
    {'name': 'Social Media Marketing', 'level': 'Advanced'},
    {'name': 'Email Marketing', 'level': 'Intermediate'},
    {'name': 'Analytics', 'level': 'Advanced'},
    {'name': 'Copywriting', 'level': 'Advanced'},
    {'name': 'Graphic Design', 'level': 'Intermediate'},
    {'name': 'Video Production', 'level': 'Intermediate'},
    {'name': 'Brand Management', 'level': 'Advanced'},
    {'name': 'Market Research', 'level': 'Intermediate'},
    {'name': 'Campaign Management', 'level': 'Advanced'},
    {'name': 'Public Relations', 'level': 'Intermediate'},
]

BUG_TRACKING_SKILLS = [
    {'name': 'Debugging', 'level': 'Advanced'},
    {'name': 'Root Cause Analysis', 'level': 'Advanced'},
    {'name': 'Testing', 'level': 'Intermediate'},
    {'name': 'Log Analysis', 'level': 'Intermediate'},
    {'name': 'Performance Profiling', 'level': 'Intermediate'},
    {'name': 'Database Troubleshooting', 'level': 'Intermediate'},
    {'name': 'Network Diagnostics', 'level': 'Intermediate'},
    {'name': 'Security Analysis', 'level': 'Advanced'},
    {'name': 'Code Review', 'level': 'Advanced'},
    {'name': 'Documentation', 'level': 'Intermediate'},
]

# Risk indicators pool
RISK_INDICATORS = [
    'Monitor task progress weekly',
    'Track team member availability',
    'Review dependencies status',
    'Check for scope changes',
    'Verify resource allocation',
    'Monitor technical blockers',
    'Track stakeholder feedback',
    'Review project deadlines',
    'Check integration points',
    'Monitor external dependencies',
    'Track skill availability',
    'Review budget constraints',
]

# Mitigation strategies pool
MITIGATION_STRATEGIES = [
    'Allocate additional resources if needed',
    'Conduct technical review early',
    'Break down into smaller subtasks',
    'Schedule regular check-ins',
    'Identify backup team members',
    'Create contingency timeline',
    'Document key decisions',
    'Set up automated alerts',
    'Plan for parallel work streams',
    'Establish clear escalation path',
    'Prepare fallback solutions',
    'Schedule buffer time',
]


class Command(BaseCommand):
    help = 'Populate demo boards with realistic tasks for demonstration purposes'

    def get_random_skills(self, skill_pool, min_skills=1, max_skills=3):
        """Get random skills from a skill pool"""
        num_skills = random.randint(min_skills, max_skills)
        return random.sample(skill_pool, min(num_skills, len(skill_pool)))

    def calculate_risk_data(self, complexity, priority, progress):
        """Calculate comprehensive risk data based on task characteristics"""
        # Base risk likelihood on complexity and priority
        if priority in ['urgent', 'high'] and complexity >= 7:
            likelihood = 3  # High
        elif priority in ['urgent', 'high'] or complexity >= 6:
            likelihood = 2  # Medium
        else:
            likelihood = 1  # Low

        # Base risk impact on priority and complexity
        if priority == 'urgent' or complexity >= 8:
            impact = 3  # High
        elif priority == 'high' or complexity >= 5:
            impact = 2  # Medium
        else:
            impact = 1  # Low

        # If task is mostly complete, reduce risk
        if progress >= 80:
            likelihood = max(1, likelihood - 1)
            impact = max(1, impact - 1)

        risk_score = likelihood * impact

        # Determine risk level
        if risk_score <= 2:
            risk_level = 'low'
        elif risk_score <= 4:
            risk_level = 'medium'
        elif risk_score <= 6:
            risk_level = 'high'
        else:
            risk_level = 'critical'

        # Select relevant risk indicators (2-4 indicators)
        num_indicators = random.randint(2, 4)
        indicators = random.sample(RISK_INDICATORS, num_indicators)

        # Select mitigation strategies (2-3 strategies)
        num_strategies = random.randint(2, 3)
        strategies = random.sample(MITIGATION_STRATEGIES, num_strategies)

        return {
            'likelihood': likelihood,
            'impact': impact,
            'score': risk_score,
            'level': risk_level,
            'indicators': indicators,
            'strategies': strategies,
        }

    def get_workload_impact(self, complexity, priority):
        """Determine workload impact based on complexity and priority"""
        if priority == 'urgent' or complexity >= 8:
            return 'critical'
        elif priority == 'high' or complexity >= 6:
            return 'high'
        elif complexity >= 4:
            return 'medium'
        else:
            return 'low'

    def get_skill_match_score(self, has_assignee, complexity):
        """Generate a realistic skill match score"""
        if not has_assignee:
            return None
        # Higher complexity tasks might have lower match scores
        base_score = random.randint(60, 95)
        complexity_penalty = max(0, (complexity - 5) * 3)
        return max(50, base_score - complexity_penalty)

    def should_require_collaboration(self, complexity, priority):
        """Determine if task should require collaboration"""
        # High complexity or urgent tasks more likely to need collaboration
        if complexity >= 8 or priority == 'urgent':
            return random.random() < 0.7  # 70% chance
        elif complexity >= 6 or priority == 'high':
            return random.random() < 0.4  # 40% chance
        else:
            return random.random() < 0.2  # 20% chance

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing demo tasks before creating new ones',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('DEMO DATA POPULATION'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))

        # Get demo organization
        try:
            demo_org = Organization.objects.get(is_demo=True, name='Demo - Acme Corporation')
        except Organization.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                '❌ Demo organization not found. Please run: python manage.py create_demo_organization'
            ))
            return

        # Create default roles for demo organization if they don't exist
        self.stdout.write('🔐 Setting up roles and permissions...')
        roles = Role.create_default_roles(demo_org)
        self.stdout.write(self.style.SUCCESS(f'   ✅ Created/verified {len(roles)} system roles\n'))

        # Get demo personas
        alex = User.objects.filter(email='alex.chen@demo.prizmai.local').first()
        sam = User.objects.filter(email='sam.rivera@demo.prizmai.local').first()
        jordan = User.objects.filter(email='jordan.taylor@demo.prizmai.local').first()
        
        # Also get demo_admin_solo for solo demo mode time tracking
        demo_admin = User.objects.filter(username='demo_admin_solo').first()

        if not all([alex, sam, jordan]):
            self.stdout.write(self.style.ERROR(
                '❌ Demo personas not found. Please run: python manage.py create_demo_organization'
            ))
            return
        
        if not demo_admin:
            self.stdout.write(self.style.WARNING(
                '⚠️  demo_admin_solo not found. Time tracking for demo mode will be limited.'
            ))

        # Get demo boards
        software_board = Board.objects.filter(
            name='Software Development',
            is_official_demo_board=True,
            organization=demo_org
        ).first()

        marketing_board = Board.objects.filter(
            name='Marketing Campaign',
            is_official_demo_board=True,
            organization=demo_org
        ).first()

        bug_board = Board.objects.filter(
            name='Bug Tracking',
            is_official_demo_board=True,
            organization=demo_org
        ).first()

        if not all([software_board, marketing_board, bug_board]):
            self.stdout.write(self.style.ERROR(
                '❌ Demo boards not found. Please run: python manage.py create_demo_organization'
            ))
            return

        # Update boards to have 3 phases each
        self.stdout.write('🔧 Configuring phases for demo boards...')
        for board in [software_board, marketing_board, bug_board]:
            board.num_phases = 3
            board.save()
        self.stdout.write(self.style.SUCCESS('   ✅ All demo boards set to 3 phases\n'))

        # Reset existing demo tasks if requested
        if options['reset']:
            self.stdout.write(self.style.WARNING('🔄 Resetting demo data...'))
            
            # Delete ALL user-created boards in demo org
            # This includes:
            # 1. Boards with is_official_demo_board=False
            # 2. Boards with is_seed_demo_data=False (user-created, even if marked as official)
            # We protect only the 3 official seed boards: Software Development, Marketing Campaign, Bug Tracking
            from django.db.models import Q
            from kanban.models import Column, Comment, TaskActivity, TaskFile
            from kanban.resource_leveling_models import TaskAssignmentHistory
            from kanban.stakeholder_models import StakeholderTaskInvolvement
            
            official_board_names = ['Software Development', 'Marketing Campaign', 'Bug Tracking']
            
            # Find user-created boards to delete
            user_boards = Board.objects.filter(
                organization=demo_org
            ).exclude(
                name__in=official_board_names,
                is_official_demo_board=True
            )
            
            if user_boards.exists():
                # First delete all tasks on these boards (to handle FK constraints)
                user_board_tasks = Task.objects.filter(column__board__in=user_boards)
                task_ids = list(user_board_tasks.values_list('id', flat=True))
                
                if task_ids:
                    # Delete related records first
                    TaskActivity.objects.filter(task_id__in=task_ids).delete()
                    Comment.objects.filter(task_id__in=task_ids).delete()
                    TaskFile.objects.filter(task_id__in=task_ids).delete()
                    TaskAssignmentHistory.objects.filter(task_id__in=task_ids).delete()
                    StakeholderTaskInvolvement.objects.filter(task_id__in=task_ids).delete()
                    
                    # Clear dependencies
                    for task in Task.objects.filter(id__in=task_ids):
                        task.dependencies.clear()
                        task.dependent_tasks.clear()
                        task.related_tasks.clear()
                    
                    # Delete the tasks
                    user_board_tasks.delete()
                
                # Now delete the boards (columns will cascade)
                deleted_boards = user_boards.delete()[0]
                self.stdout.write(self.style.WARNING(f'   Deleted {deleted_boards} user-created boards'))
            
            # Delete ALL tasks on official demo boards (both user-created and demo data)
            deleted_count = Task.objects.filter(
                column__board__in=[software_board, marketing_board, bug_board]
            ).delete()[0]
            self.stdout.write(self.style.WARNING(f'   Deleted {deleted_count} existing tasks\n'))

        # Check if tasks already exist
        existing_task_count = Task.objects.filter(
            column__board__in=[software_board, marketing_board, bug_board]
        ).count()

        if existing_task_count > 0 and not options['reset']:
            self.stdout.write(self.style.WARNING(
                f'⚠️  Demo boards already have {existing_task_count} tasks.'
            ))
            self.stdout.write(self.style.WARNING(
                '   Use --reset flag to delete and recreate: python manage.py populate_demo_data --reset\n'
            ))
            return

        # Create tasks for each board (30 tasks per board)
        self.stdout.write(self.style.SUCCESS('📝 Creating demo tasks...\n'))

        software_tasks = self.create_software_tasks(software_board, alex, sam, jordan)
        self.stdout.write(self.style.SUCCESS(
            f'   ✅ Software Development: {len(software_tasks)} items created'
        ))

        marketing_tasks = self.create_marketing_tasks(marketing_board, alex, sam, jordan)
        self.stdout.write(self.style.SUCCESS(
            f'   ✅ Marketing Campaign: {len(marketing_tasks)} items created'
        ))

        bug_tasks = self.create_bug_tasks(bug_board, alex, sam, jordan)
        self.stdout.write(self.style.SUCCESS(
            f'   ✅ Bug Tracking: {len(bug_tasks)} items created'
        ))

        total_tasks = len(software_tasks) + len(marketing_tasks) + len(bug_tasks)
        self.stdout.write(self.style.SUCCESS(f'\n   📊 Total items created: {total_tasks}'))

        # Create task dependencies
        self.stdout.write(self.style.SUCCESS('\n🔗 Creating task dependencies...\n'))
        self.create_dependencies(software_tasks, marketing_tasks, bug_tasks)

        # Create and assign Lean Six Sigma labels
        self.stdout.write(self.style.SUCCESS('\n🏷️  Creating Lean Six Sigma labels...\n'))
        self.create_lean_labels(software_board, marketing_board, bug_board)
        self.assign_lean_labels(software_tasks, marketing_tasks, bug_tasks)

        # Enhance tasks with comprehensive demo data
        self.stdout.write(self.style.SUCCESS('\n📊 Enriching tasks with comprehensive demo data...\n'))
        self.enhance_tasks_with_demo_data(software_tasks, SOFTWARE_SKILLS, 'software')
        self.enhance_tasks_with_demo_data(marketing_tasks, MARKETING_SKILLS, 'marketing')
        self.enhance_tasks_with_demo_data(bug_tasks, BUG_TRACKING_SKILLS, 'bug_tracking')

        # Create related task relationships
        self.stdout.write(self.style.SUCCESS('\n🔄 Creating related task relationships...\n'))
        self.create_related_tasks(software_tasks)
        self.create_related_tasks(marketing_tasks)
        self.create_related_tasks(bug_tasks)

        # Create time tracking data for all demo users
        self.stdout.write(self.style.SUCCESS('\n⏱️  Creating time tracking data...\n'))
        all_tasks = software_tasks + marketing_tasks + bug_tasks
        self.create_time_tracking_data(all_tasks, alex, sam, jordan, demo_admin)

        # Create budget and ROI data
        self.stdout.write(self.style.SUCCESS('\n💰 Creating budget and ROI data...\n'))
        self.create_budget_roi_data(software_board, marketing_board, bug_board, alex)

        # Create burndown/velocity data
        self.stdout.write(self.style.SUCCESS('\n📉 Creating burndown velocity data...\n'))
        self.create_burndown_data(software_board, marketing_board, bug_board)

        # Create retrospective data
        self.stdout.write(self.style.SUCCESS('\n🔄 Creating retrospective data...\n'))
        self.create_retrospective_data(software_board, marketing_board, bug_board, alex, sam, jordan)

        # Create AI coaching suggestions
        self.stdout.write(self.style.SUCCESS('\n🤖 Creating AI coaching suggestions...\n'))
        self.create_coaching_data(software_board, marketing_board, bug_board)

        # Create comments for all tasks
        self.stdout.write(self.style.SUCCESS('\n💬 Creating task comments...\n'))
        self.create_comments(all_tasks, alex, sam, jordan)

        # Create activity logs for all tasks
        self.stdout.write(self.style.SUCCESS('\n📋 Creating activity logs...\n'))
        self.create_activity_logs(all_tasks, alex, sam, jordan)

        # Create stakeholders and link them to tasks
        self.stdout.write(self.style.SUCCESS('\n👥 Creating stakeholders...\n'))
        self.create_stakeholders(software_board, marketing_board, bug_board, all_tasks, alex, sam, jordan)

        # Create file attachment metadata (simulated attachments)
        self.stdout.write(self.style.SUCCESS('\n📎 Creating file attachments...\n'))
        self.create_file_attachments(all_tasks, alex, sam, jordan)

        # Create wiki links for tasks
        self.stdout.write(self.style.SUCCESS('\n📚 Creating wiki links...\n'))
        self.create_wiki_links(all_tasks, demo_org, alex)

        # Populate AI Assistant demo data (chat sessions and messages)
        self.stdout.write(self.style.SUCCESS('\n🤖 Creating AI Assistant chat sessions...\n'))
        from django.core.management import call_command
        try:
            call_command('populate_ai_assistant_demo_data', '--reset')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'   ⚠️  AI Assistant demo data skipped: {e}'))

        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('✅ DEMO DATA POPULATION COMPLETE'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))

    def create_software_tasks(self, board, alex, sam, jordan):
        """Create 30 tasks for Software Development board (3 phases)"""
        columns = {col.name: col for col in Column.objects.filter(board=board)}
        backlog_col = columns.get('To Do') or columns.get('Backlog') or list(columns.values())[0]
        in_progress_col = columns.get('In Progress') or backlog_col
        review_col = columns.get('In Review') or in_progress_col
        done_col = columns.get('Done') or review_col
        items = []
        now = timezone.now().date()

        # Phase 1: Foundation & Setup (days -60 to -31)
        # Ensure phases don't overlap for proper Gantt chart ordering
        phase1_tasks = [
            {'title': 'Set up development environment', 'desc': 'Configure Docker, CI/CD pipelines, and development tools', 'priority': 'high', 'complexity': 6, 'assignee': sam, 'progress': 100, 'column': done_col},
            {'title': 'Design database schema', 'desc': 'Create ERD and define core database models for multi-tenancy', 'priority': 'high', 'complexity': 8, 'assignee': sam, 'progress': 100, 'column': done_col},
            {'title': 'Implement user authentication', 'desc': 'Build secure login with JWT tokens and session management', 'priority': 'high', 'complexity': 7, 'assignee': sam, 'progress': 100, 'column': done_col},
            {'title': 'Create base API structure', 'desc': 'Set up REST API framework with versioning and documentation', 'priority': 'medium', 'complexity': 5, 'assignee': sam, 'progress': 100, 'column': done_col},
            {'title': 'Set up automated testing', 'desc': 'Configure pytest with coverage reporting and CI integration', 'priority': 'medium', 'complexity': 5, 'assignee': alex, 'progress': 100, 'column': done_col},
            {'title': 'Implement logging system', 'desc': 'Set up structured logging with log aggregation', 'priority': 'low', 'complexity': 4, 'assignee': jordan, 'progress': 100, 'column': done_col},
            {'title': 'Create user registration flow', 'desc': 'Build signup with email verification and onboarding', 'priority': 'medium', 'complexity': 6, 'assignee': sam, 'progress': 100, 'column': done_col},
            {'title': 'Set up development database', 'desc': 'Configure PostgreSQL with migrations and seed data', 'priority': 'medium', 'complexity': 4, 'assignee': jordan, 'progress': 100, 'column': done_col},
            {'title': 'Implement password reset', 'desc': 'Secure password reset flow with email tokens', 'priority': 'medium', 'complexity': 5, 'assignee': sam, 'progress': 100, 'column': done_col},
            {'title': 'Create project documentation', 'desc': 'Set up documentation site with API reference', 'priority': 'low', 'complexity': 3, 'assignee': jordan, 'progress': 100, 'column': done_col},
        ]

        # Phase 2: Core Features (days -30 to -1)
        phase2_tasks = [
            {'title': 'Build dashboard UI', 'desc': 'Create responsive dashboard with charts and widgets', 'priority': 'high', 'complexity': 7, 'assignee': sam, 'progress': 80, 'column': review_col},
            {'title': 'Implement file upload system', 'desc': 'Support multiple file types with S3 storage', 'priority': 'medium', 'complexity': 6, 'assignee': sam, 'progress': 60, 'column': in_progress_col},
            {'title': 'Create notification system', 'desc': 'Real-time notifications via WebSocket and email', 'priority': 'medium', 'complexity': 7, 'assignee': sam, 'progress': 40, 'column': in_progress_col},
            {'title': 'Build user management API', 'desc': 'CRUD operations for users with role-based access', 'priority': 'high', 'complexity': 6, 'assignee': sam, 'progress': 90, 'column': review_col},
            {'title': 'Implement search functionality', 'desc': 'Full-text search with filters and pagination', 'priority': 'medium', 'complexity': 7, 'assignee': sam, 'progress': 30, 'column': in_progress_col},
            {'title': 'Create settings page', 'desc': 'User preferences and account settings UI', 'priority': 'low', 'complexity': 4, 'assignee': jordan, 'progress': 50, 'column': in_progress_col},
            {'title': 'Build audit logging', 'desc': 'Track all user actions for compliance', 'priority': 'medium', 'complexity': 5, 'assignee': alex, 'progress': 70, 'column': review_col},
            {'title': 'Implement data export', 'desc': 'Export functionality for CSV and Excel formats', 'priority': 'low', 'complexity': 4, 'assignee': jordan, 'progress': 20, 'column': in_progress_col},
            {'title': 'Create email templates', 'desc': 'Transactional email templates with branding', 'priority': 'low', 'complexity': 3, 'assignee': jordan, 'progress': 100, 'column': done_col},
            {'title': 'Add two-factor authentication', 'desc': 'TOTP-based 2FA with recovery codes', 'priority': 'high', 'complexity': 6, 'assignee': sam, 'progress': 45, 'column': in_progress_col},
        ]

        # Phase 3: Polish & Launch (days 0 to +45)
        phase3_tasks = [
            {'title': 'Performance optimization', 'desc': 'Database query optimization and caching', 'priority': 'high', 'complexity': 8, 'assignee': sam, 'progress': 0, 'column': backlog_col},
            {'title': 'Security audit fixes', 'desc': 'Address findings from penetration testing', 'priority': 'urgent', 'complexity': 7, 'assignee': sam, 'progress': 0, 'column': backlog_col},
            {'title': 'Mobile responsive polish', 'desc': 'Fix mobile UI issues and improve UX', 'priority': 'medium', 'complexity': 5, 'assignee': jordan, 'progress': 0, 'column': backlog_col},
            {'title': 'Load testing', 'desc': 'Conduct load tests and fix bottlenecks', 'priority': 'high', 'complexity': 6, 'assignee': alex, 'progress': 0, 'column': backlog_col},
            {'title': 'Create user onboarding', 'desc': 'Interactive tutorial for new users', 'priority': 'medium', 'complexity': 5, 'assignee': jordan, 'progress': 0, 'column': backlog_col},
            {'title': 'Set up monitoring', 'desc': 'Configure APM and error tracking', 'priority': 'high', 'complexity': 5, 'assignee': alex, 'progress': 0, 'column': backlog_col},
            {'title': 'Documentation review', 'desc': 'Update all documentation for launch', 'priority': 'medium', 'complexity': 3, 'assignee': jordan, 'progress': 0, 'column': backlog_col},
            {'title': 'Accessibility improvements', 'desc': 'WCAG 2.1 compliance updates', 'priority': 'medium', 'complexity': 5, 'assignee': jordan, 'progress': 0, 'column': backlog_col},
            {'title': 'Deployment automation', 'desc': 'One-click deployment to production', 'priority': 'high', 'complexity': 6, 'assignee': alex, 'progress': 0, 'column': backlog_col},
            {'title': 'Launch preparation', 'desc': 'Final checklist and go-live preparation', 'priority': 'urgent', 'complexity': 4, 'assignee': alex, 'progress': 0, 'column': backlog_col},
        ]

        # Create Phase 1 items with improved date logic
        # Each task starts 0 to +3 days from the previous task's due date (no overlap)
        # First task starts on day -10
        prev_due_date = now + timedelta(days=-10)
        for i, t in enumerate(phase1_tasks):
            # Start date is 0 to +3 days from previous task's due date (ensures no overlap)
            start = prev_due_date + timedelta(days=random.randint(0, 3))
            due = start + timedelta(days=random.randint(3, 6))  # 3-6 day duration
            task = Task.objects.create(
                column=t['column'], title=t['title'], description=t['desc'],
                priority=t['priority'], complexity_score=t['complexity'],
                assigned_to=t['assignee'], created_by=alex, progress=t['progress'],
                start_date=start, due_date=due, phase='Phase 1',
                is_seed_demo_data=True,
            )
            items.append(task)
            prev_due_date = due

        # Create Phase 2 items
        # Add a small gap between phases (3-6 days) for visual separation
        prev_due_date = prev_due_date + timedelta(days=random.randint(3, 6))
        for i, t in enumerate(phase2_tasks):
            start = prev_due_date + timedelta(days=random.randint(0, 3))
            due = start + timedelta(days=random.randint(3, 6))  # 3-6 day duration
            task = Task.objects.create(
                column=t['column'], title=t['title'], description=t['desc'],
                priority=t['priority'], complexity_score=t['complexity'],
                assigned_to=t['assignee'], created_by=alex, progress=t['progress'],
                start_date=start, due_date=due, phase='Phase 2',
                is_seed_demo_data=True,
            )
            items.append(task)
            prev_due_date = due

        # Create Phase 3 items
        # Add a small gap between phases (3-6 days) for visual separation
        prev_due_date = prev_due_date + timedelta(days=random.randint(3, 6))
        for i, t in enumerate(phase3_tasks):
            start = prev_due_date + timedelta(days=random.randint(0, 3))
            due = start + timedelta(days=random.randint(3, 6))  # 3-6 day duration
            task = Task.objects.create(
                column=t['column'], title=t['title'], description=t['desc'],
                priority=t['priority'], complexity_score=t['complexity'],
                assigned_to=t['assignee'], created_by=alex, progress=t['progress'],
                start_date=start, due_date=due, phase='Phase 3',
                is_seed_demo_data=True,
            )
            items.append(task)
            prev_due_date = due

        return items

    def create_marketing_tasks(self, board, alex, sam, jordan):
        """Create 30 tasks for Marketing Campaign board (3 phases)"""
        columns = {col.name: col for col in Column.objects.filter(board=board)}
        backlog_col = columns.get('To Do') or columns.get('Backlog') or list(columns.values())[0]
        in_progress_col = columns.get('In Progress') or backlog_col
        review_col = columns.get('In Review') or in_progress_col
        done_col = columns.get('Done') or review_col
        items = []
        now = timezone.now().date()

        # Phase 1: Planning & Strategy (days -60 to -31)
        # Ensure phases don't overlap for proper Gantt chart ordering
        phase1_tasks = [
            {'title': 'Market research analysis', 'desc': 'Analyze target audience and competitor landscape', 'priority': 'high', 'complexity': 7, 'assignee': jordan, 'progress': 100, 'column': done_col},
            {'title': 'Define campaign objectives', 'desc': 'Set SMART goals and KPIs for the campaign', 'priority': 'high', 'complexity': 5, 'assignee': alex, 'progress': 100, 'column': done_col},
            {'title': 'Create buyer personas', 'desc': 'Develop detailed profiles of target customers', 'priority': 'medium', 'complexity': 6, 'assignee': jordan, 'progress': 100, 'column': done_col},
            {'title': 'Budget allocation', 'desc': 'Distribute budget across channels and activities', 'priority': 'high', 'complexity': 5, 'assignee': alex, 'progress': 100, 'column': done_col},
            {'title': 'Content strategy document', 'desc': 'Define content themes, formats, and calendar', 'priority': 'medium', 'complexity': 6, 'assignee': jordan, 'progress': 100, 'column': done_col},
            {'title': 'Channel selection', 'desc': 'Choose primary and secondary marketing channels', 'priority': 'medium', 'complexity': 4, 'assignee': jordan, 'progress': 100, 'column': done_col},
            {'title': 'Set up analytics tracking', 'desc': 'Configure GA4, UTM parameters, and conversion tracking', 'priority': 'medium', 'complexity': 5, 'assignee': sam, 'progress': 100, 'column': done_col},
            {'title': 'Create campaign brief', 'desc': 'Document campaign overview for team alignment', 'priority': 'medium', 'complexity': 4, 'assignee': alex, 'progress': 100, 'column': done_col},
            {'title': 'Competitor analysis report', 'desc': 'Analyze competitor marketing strategies', 'priority': 'low', 'complexity': 5, 'assignee': jordan, 'progress': 100, 'column': done_col},
            {'title': 'Brand guidelines review', 'desc': 'Update brand guidelines for campaign', 'priority': 'low', 'complexity': 3, 'assignee': jordan, 'progress': 100, 'column': done_col},
        ]

        # Phase 2: Content Creation (days -30 to -1)
        phase2_tasks = [
            {'title': 'Write blog posts', 'desc': 'Create 5 SEO-optimized blog articles', 'priority': 'high', 'complexity': 6, 'assignee': jordan, 'progress': 80, 'column': review_col},
            {'title': 'Design social media graphics', 'desc': 'Create visual assets for all platforms', 'priority': 'medium', 'complexity': 5, 'assignee': jordan, 'progress': 60, 'column': in_progress_col},
            {'title': 'Produce video content', 'desc': 'Script, shoot, and edit promotional videos', 'priority': 'high', 'complexity': 8, 'assignee': jordan, 'progress': 40, 'column': in_progress_col},
            {'title': 'Create email sequences', 'desc': 'Design automated email nurture campaigns', 'priority': 'medium', 'complexity': 5, 'assignee': jordan, 'progress': 70, 'column': review_col},
            {'title': 'Write landing page copy', 'desc': 'Conversion-optimized copy for landing pages', 'priority': 'high', 'complexity': 6, 'assignee': jordan, 'progress': 90, 'column': review_col},
            {'title': 'Design landing pages', 'desc': 'Build responsive landing pages in CMS', 'priority': 'high', 'complexity': 6, 'assignee': sam, 'progress': 50, 'column': in_progress_col},
            {'title': 'Create infographics', 'desc': 'Design data-driven infographics', 'priority': 'low', 'complexity': 5, 'assignee': jordan, 'progress': 30, 'column': in_progress_col},
            {'title': 'Write case studies', 'desc': 'Document customer success stories', 'priority': 'medium', 'complexity': 6, 'assignee': jordan, 'progress': 20, 'column': in_progress_col},
            {'title': 'Create ad creatives', 'desc': 'Design paid advertising visuals and copy', 'priority': 'high', 'complexity': 5, 'assignee': jordan, 'progress': 65, 'column': in_progress_col},
            {'title': 'Develop content calendar', 'desc': 'Schedule all content across channels', 'priority': 'medium', 'complexity': 4, 'assignee': jordan, 'progress': 100, 'column': done_col},
        ]

        # Phase 3: Launch & Optimization (days 0 to +45)
        phase3_tasks = [
            {'title': 'Launch social campaigns', 'desc': 'Activate campaigns across social platforms', 'priority': 'urgent', 'complexity': 5, 'assignee': jordan, 'progress': 0, 'column': backlog_col},
            {'title': 'Start email campaigns', 'desc': 'Launch automated email sequences', 'priority': 'high', 'complexity': 4, 'assignee': jordan, 'progress': 0, 'column': backlog_col},
            {'title': 'Activate paid ads', 'desc': 'Launch PPC and social ad campaigns', 'priority': 'high', 'complexity': 6, 'assignee': jordan, 'progress': 0, 'column': backlog_col},
            {'title': 'Monitor campaign performance', 'desc': 'Daily monitoring and reporting', 'priority': 'high', 'complexity': 4, 'assignee': jordan, 'progress': 0, 'column': backlog_col},
            {'title': 'A/B test landing pages', 'desc': 'Run conversion optimization tests', 'priority': 'medium', 'complexity': 5, 'assignee': sam, 'progress': 0, 'column': backlog_col},
            {'title': 'Optimize ad spend', 'desc': 'Reallocate budget based on performance', 'priority': 'high', 'complexity': 5, 'assignee': jordan, 'progress': 0, 'column': backlog_col},
            {'title': 'Influencer outreach', 'desc': 'Coordinate with influencer partners', 'priority': 'medium', 'complexity': 4, 'assignee': jordan, 'progress': 0, 'column': backlog_col},
            {'title': 'PR media outreach', 'desc': 'Pitch to journalists and media outlets', 'priority': 'medium', 'complexity': 5, 'assignee': alex, 'progress': 0, 'column': backlog_col},
            {'title': 'Weekly performance report', 'desc': 'Compile and analyze campaign metrics', 'priority': 'medium', 'complexity': 4, 'assignee': jordan, 'progress': 0, 'column': backlog_col},
            {'title': 'Campaign retrospective', 'desc': 'Document learnings and recommendations', 'priority': 'low', 'complexity': 3, 'assignee': alex, 'progress': 0, 'column': backlog_col},
        ]

        # Create all phases with improved date logic
        # Each task starts 0 to +3 days from the previous task's due date (no overlap)
        # First task starts on day -10
        prev_due_date = now + timedelta(days=-10)
        
        for phase_num, tasks in enumerate([phase1_tasks, phase2_tasks, phase3_tasks], start=1):
            phase_name = f'Phase {phase_num}'
            
            # Add a small gap between phases (3-6 days) for visual separation
            if phase_num > 1:
                prev_due_date = prev_due_date + timedelta(days=random.randint(3, 6))

            for i, t in enumerate(tasks):
                # Start date is 0 to +3 days from previous task's due date (ensures no overlap)
                start = prev_due_date + timedelta(days=random.randint(0, 3))
                due = start + timedelta(days=random.randint(3, 6))  # 3-6 day duration
                task = Task.objects.create(
                    column=t['column'], title=t['title'], description=t['desc'],
                    priority=t['priority'], complexity_score=t['complexity'],
                    assigned_to=t['assignee'], created_by=alex, progress=t['progress'],
                    start_date=start, due_date=due, phase=phase_name,
                    is_seed_demo_data=True,
                )
                items.append(task)
                prev_due_date = due

        return items

    def create_bug_tasks(self, board, alex, sam, jordan):
        """Create 30 tasks for Bug Tracking board (3 phases)"""
        columns = {col.name: col for col in Column.objects.filter(board=board)}
        backlog_col = columns.get('To Do') or columns.get('Backlog') or list(columns.values())[0]
        in_progress_col = columns.get('In Progress') or backlog_col
        review_col = columns.get('In Review') or in_progress_col
        done_col = columns.get('Done') or review_col
        items = []
        now = timezone.now().date()

        # Phase 1: Critical & Security Bugs (days -60 to -31)
        phase1_tasks = [
            {'title': 'Fix SQL injection vulnerability', 'desc': 'Patch user input sanitization in search', 'priority': 'urgent', 'complexity': 7, 'assignee': sam, 'progress': 100, 'column': done_col},
            {'title': 'Fix authentication bypass', 'desc': 'Close security hole in session handling', 'priority': 'urgent', 'complexity': 8, 'assignee': sam, 'progress': 100, 'column': done_col},
            {'title': 'Fix XSS in comments', 'desc': 'Sanitize HTML output in comment system', 'priority': 'urgent', 'complexity': 6, 'assignee': sam, 'progress': 100, 'column': done_col},
            {'title': 'Fix password hash weakness', 'desc': 'Upgrade to bcrypt with proper cost factor', 'priority': 'high', 'complexity': 5, 'assignee': sam, 'progress': 100, 'column': done_col},
            {'title': 'Fix CSRF token validation', 'desc': 'Implement proper CSRF protection', 'priority': 'high', 'complexity': 5, 'assignee': sam, 'progress': 100, 'column': done_col},
            {'title': 'Fix database connection leak', 'desc': 'Properly close DB connections in all paths', 'priority': 'high', 'complexity': 6, 'assignee': sam, 'progress': 100, 'column': done_col},
            {'title': 'Fix race condition in payments', 'desc': 'Add proper locking for payment processing', 'priority': 'urgent', 'complexity': 8, 'assignee': sam, 'progress': 100, 'column': done_col},
            {'title': 'Fix session fixation', 'desc': 'Regenerate session ID on login', 'priority': 'high', 'complexity': 4, 'assignee': sam, 'progress': 100, 'column': done_col},
            {'title': 'Fix insecure file upload', 'desc': 'Validate file types and scan for malware', 'priority': 'high', 'complexity': 6, 'assignee': sam, 'progress': 100, 'column': done_col},
            {'title': 'Fix sensitive data exposure', 'desc': 'Remove PII from error logs', 'priority': 'high', 'complexity': 5, 'assignee': alex, 'progress': 100, 'column': done_col},
        ]

        # Phase 2: High Priority Bugs (days -30 to -1)
        phase2_tasks = [
            {'title': 'Fix memory leak in worker', 'desc': 'Background worker memory grows over time', 'priority': 'high', 'complexity': 7, 'assignee': sam, 'progress': 80, 'column': review_col},
            {'title': 'Fix slow dashboard load', 'desc': 'Dashboard takes 10+ seconds to load', 'priority': 'high', 'complexity': 6, 'assignee': sam, 'progress': 60, 'column': in_progress_col},
            {'title': 'Fix email delivery failures', 'desc': 'Emails not sending to certain domains', 'priority': 'high', 'complexity': 5, 'assignee': jordan, 'progress': 90, 'column': review_col},
            {'title': 'Fix image resize crash', 'desc': 'App crashes on large image uploads', 'priority': 'medium', 'complexity': 5, 'assignee': sam, 'progress': 70, 'column': review_col},
            {'title': 'Fix timezone handling', 'desc': 'Dates display incorrectly for non-UTC users', 'priority': 'medium', 'complexity': 6, 'assignee': sam, 'progress': 40, 'column': in_progress_col},
            {'title': 'Fix search pagination', 'desc': 'Search results wrong on page 2+', 'priority': 'medium', 'complexity': 4, 'assignee': jordan, 'progress': 50, 'column': in_progress_col},
            {'title': 'Fix notification duplicates', 'desc': 'Users receiving duplicate notifications', 'priority': 'medium', 'complexity': 5, 'assignee': sam, 'progress': 30, 'column': in_progress_col},
            {'title': 'Fix export timeout', 'desc': 'Large exports timeout before completing', 'priority': 'medium', 'complexity': 6, 'assignee': sam, 'progress': 20, 'column': in_progress_col},
            {'title': 'Fix mobile menu collapse', 'desc': 'Menu doesn\'t collapse properly on mobile', 'priority': 'low', 'complexity': 3, 'assignee': jordan, 'progress': 100, 'column': done_col},
            {'title': 'Fix autocomplete delay', 'desc': 'Search autocomplete is too slow', 'priority': 'low', 'complexity': 4, 'assignee': sam, 'progress': 65, 'column': in_progress_col},
        ]

        # Phase 3: Medium/Low Priority & Polish (days 0 to +45)
        phase3_tasks = [
            {'title': 'Fix form validation messages', 'desc': 'Error messages not displaying correctly', 'priority': 'medium', 'complexity': 3, 'assignee': jordan, 'progress': 0, 'column': backlog_col},
            {'title': 'Fix print stylesheet', 'desc': 'Reports don\'t print correctly', 'priority': 'low', 'complexity': 3, 'assignee': jordan, 'progress': 0, 'column': backlog_col},
            {'title': 'Fix keyboard navigation', 'desc': 'Tab order incorrect on forms', 'priority': 'medium', 'complexity': 4, 'assignee': jordan, 'progress': 0, 'column': backlog_col},
            {'title': 'Fix tooltip positioning', 'desc': 'Tooltips clip off screen edge', 'priority': 'low', 'complexity': 3, 'assignee': jordan, 'progress': 0, 'column': backlog_col},
            {'title': 'Fix date picker locale', 'desc': 'Date format wrong for non-US users', 'priority': 'medium', 'complexity': 4, 'assignee': sam, 'progress': 0, 'column': backlog_col},
            {'title': 'Fix drag and drop on Safari', 'desc': 'DnD not working on Safari browser', 'priority': 'medium', 'complexity': 5, 'assignee': sam, 'progress': 0, 'column': backlog_col},
            {'title': 'Fix chart rendering', 'desc': 'Charts flicker on data update', 'priority': 'low', 'complexity': 4, 'assignee': sam, 'progress': 0, 'column': backlog_col},
            {'title': 'Fix modal close behavior', 'desc': 'Escape key doesn\'t close modals', 'priority': 'low', 'complexity': 2, 'assignee': jordan, 'progress': 0, 'column': backlog_col},
            {'title': 'Fix breadcrumb trail', 'desc': 'Breadcrumbs show wrong path', 'priority': 'low', 'complexity': 3, 'assignee': jordan, 'progress': 0, 'column': backlog_col},
            {'title': 'Fix avatar upload preview', 'desc': 'Avatar preview not updating', 'priority': 'low', 'complexity': 3, 'assignee': jordan, 'progress': 0, 'column': backlog_col},
        ]

        # Create all phases with improved date logic
        # Each task starts 0 to +3 days from the previous task's due date (no overlap)
        # First task starts on day -10
        prev_due_date = now + timedelta(days=-10)
        
        for phase_num, tasks in enumerate([phase1_tasks, phase2_tasks, phase3_tasks], start=1):
            phase_name = f'Phase {phase_num}'
            
            # Add a small gap between phases (3-6 days) for visual separation
            if phase_num > 1:
                prev_due_date = prev_due_date + timedelta(days=random.randint(3, 6))

            for i, t in enumerate(tasks):
                # Start date is 0 to +3 days from previous task's due date (ensures no overlap)
                start = prev_due_date + timedelta(days=random.randint(0, 3))
                due = start + timedelta(days=random.randint(3, 6))  # 3-6 day duration for good visual appearance
                task = Task.objects.create(
                    column=t['column'], title=t['title'], description=t['desc'],
                    priority=t['priority'], complexity_score=t['complexity'],
                    assigned_to=t['assignee'], created_by=sam, progress=t['progress'],
                    start_date=start, due_date=due, phase=phase_name,
                    is_seed_demo_data=True,
                )
                items.append(task)
                prev_due_date = due

        return items

    def create_dependencies(self, software_tasks, marketing_tasks, bug_tasks):
        """Create simple linear task dependencies WITHIN each phase only
        
        Each task depends on only ONE previous task, creating a simple chain.
        This makes the Gantt chart clean and easy to understand.
        No inter-phase dependencies - each phase starts fresh.
        """
        # Software Development - Simple linear chain within each phase
        # Phase 1 (indices 0-9): Foundation & Setup
        # Phase 2 (indices 10-19): Core Features  
        # Phase 3 (indices 20-29): Polish & Launch
        if len(software_tasks) >= 30:
            # Phase 1: Simple linear chain (0→1→2→3→4→5→6→7→8→9)
            # Task 0 has no dependencies (phase start)
            for i in range(1, 10):
                software_tasks[i].dependencies.add(software_tasks[i-1])

            # Phase 2: Simple linear chain (10→11→12→13→14→15→16→17→18→19)
            # Task 10 has no dependencies (new phase start)
            for i in range(11, 20):
                software_tasks[i].dependencies.add(software_tasks[i-1])

            # Phase 3: Simple linear chain (20→21→22→23→24→25→26→27→28→29)
            # Task 20 has no dependencies (new phase start)
            for i in range(21, 30):
                software_tasks[i].dependencies.add(software_tasks[i-1])

        self.stdout.write('   ✅ Software Development dependencies created (simple linear chain per phase)')

        # Marketing Campaign - Simple linear chain within each phase
        if len(marketing_tasks) >= 30:
            # Phase 1: Simple linear chain (0→1→2→3→4→5→6→7→8→9)
            for i in range(1, 10):
                marketing_tasks[i].dependencies.add(marketing_tasks[i-1])

            # Phase 2: Simple linear chain (10→11→12→13→14→15→16→17→18→19)
            for i in range(11, 20):
                marketing_tasks[i].dependencies.add(marketing_tasks[i-1])

            # Phase 3: Simple linear chain (20→21→22→23→24→25→26→27→28→29)
            for i in range(21, 30):
                marketing_tasks[i].dependencies.add(marketing_tasks[i-1])

        self.stdout.write('   ✅ Marketing Campaign dependencies created (simple linear chain per phase)')

        # Bug Tracking - Simple linear chain within each phase
        if len(bug_tasks) >= 30:
            # Phase 1: Simple linear chain (0→1→2→3→4→5→6→7→8→9)
            for i in range(1, 10):
                bug_tasks[i].dependencies.add(bug_tasks[i-1])

            # Phase 2: Simple linear chain (10→11→12→13→14→15→16→17→18→19)
            for i in range(11, 20):
                bug_tasks[i].dependencies.add(bug_tasks[i-1])

            # Phase 3: Simple linear chain (20→21→22→23→24→25→26→27→28→29)
            for i in range(21, 30):
                bug_tasks[i].dependencies.add(bug_tasks[i-1])

        self.stdout.write('   ✅ Bug Tracking dependencies created (simple linear chain per phase)')

    def create_lean_labels(self, software_board, marketing_board, bug_board):
        """Create Lean Six Sigma labels for all boards"""
        # Main Lean Six Sigma category labels (for analytics chart)
        main_lean_labels = [
            {'name': 'Value-Added', 'color': '#28a745'},
            {'name': 'Necessary NVA', 'color': '#ffc107'},
            {'name': 'Waste/Eliminate', 'color': '#dc3545'},
        ]
        
        # Additional Lean Six Sigma methodology labels
        lean_labels = [
            {'name': 'Muda', 'color': '#dc3545'},
            {'name': 'Mura', 'color': '#fd7e14'},
            {'name': 'Muri', 'color': '#ffc107'},
            {'name': 'Kaizen', 'color': '#28a745'},
            {'name': '5S', 'color': '#17a2b8'},
            {'name': 'Poka-yoke', 'color': '#6f42c1'},
        ]

        for board in [software_board, marketing_board, bug_board]:
            # Create main category labels first (essential for analytics)
            for label_data in main_lean_labels:
                TaskLabel.objects.get_or_create(
                    board=board,
                    name=label_data['name'],
                    defaults={
                        'color': label_data['color'],
                        'category': 'lean',
                    }
                )
            
            # Create additional methodology labels
            for label_data in lean_labels:
                TaskLabel.objects.get_or_create(
                    board=board,
                    name=label_data['name'],
                    defaults={
                        'color': label_data['color'],
                        'category': 'lean',
                    }
                )

        self.stdout.write('   ✅ Lean Six Sigma labels created for all boards (including analytics categories)')

    def assign_lean_labels(self, software_tasks, marketing_tasks, bug_tasks):
        """Assign Lean Six Sigma labels to appropriate tasks"""
        all_tasks = software_tasks + marketing_tasks + bug_tasks

        for task in all_tasks:
            board = task.column.board
            labels = list(TaskLabel.objects.filter(board=board, category='lean'))

            if not labels:
                continue

            # Get the three main category labels
            value_added = next((l for l in labels if l.name == 'Value-Added'), None)
            necessary_nva = next((l for l in labels if l.name == 'Necessary NVA'), None)
            waste = next((l for l in labels if l.name == 'Waste/Eliminate'), None)

            # IMPORTANT: Assign ONE of the three main categories to EVERY task
            # This ensures the analytics chart always has data
            rand = random.random()
            if rand < 0.5:  # 50% Value-Added
                if value_added:
                    task.labels.add(value_added)
            elif rand < 0.8:  # 30% Necessary NVA
                if necessary_nva:
                    task.labels.add(necessary_nva)
            else:  # 20% Waste/Eliminate
                if waste:
                    task.labels.add(waste)

            # Assign additional methodology labels based on task characteristics
            if task.complexity_score and task.complexity_score >= 7:
                kaizen_label = next((l for l in labels if l.name == 'Kaizen'), None)
                if kaizen_label:
                    task.labels.add(kaizen_label)

            if task.priority in ['urgent', 'high'] and random.random() < 0.3:
                muri_label = next((l for l in labels if l.name == 'Muri'), None)
                if muri_label:
                    task.labels.add(muri_label)

            # Random chance for other methodology labels
            if random.random() < 0.15:
                methodology_labels = [l for l in labels if l.name in ['Muda', 'Mura', '5S', 'Poka-yoke']]
                if methodology_labels:
                    random_label = random.choice(methodology_labels)
                    task.labels.add(random_label)

        self.stdout.write('   ✅ Lean Six Sigma labels assigned to all tasks (with analytics categories)')

    def enhance_tasks_with_demo_data(self, tasks, skill_pool, board_type):
        """Add comprehensive demo data to tasks including risk, skills, and collaboration"""
        for task in tasks:
            complexity = task.complexity_score or random.randint(3, 8)
            priority = task.priority or 'medium'
            progress = task.progress or 0

            # Add skills required
            skills = self.get_random_skills(skill_pool, 1, 3)
            task.required_skills = skills

            # Calculate and add risk data
            risk_data = self.calculate_risk_data(complexity, priority, progress)
            task.risk_likelihood = risk_data['likelihood']
            task.risk_impact = risk_data['impact']
            task.risk_score = risk_data['score']
            task.risk_level = risk_data['level']
            task.risk_indicators = risk_data['indicators']
            task.risk_mitigation = risk_data['strategies']

            # Add workload impact
            task.workload_impact = self.get_workload_impact(complexity, priority)

            # Add skill match score if assigned
            task.skill_match_score = self.get_skill_match_score(
                task.assigned_to is not None,
                complexity
            )

            # Set collaboration requirement
            task.requires_collaboration = self.should_require_collaboration(complexity, priority)

            # Add estimated hours based on complexity
            base_hours = complexity * random.uniform(1.5, 3)
            task.estimated_hours = round(base_hours, 1)

            task.save()

        self.stdout.write(f'   ✅ Enhanced {len(tasks)} {board_type} tasks with comprehensive demo data')

    def create_related_tasks(self, tasks):
        """Create related task relationships between similar tasks"""
        if len(tasks) < 5:
            return

        # Group tasks by phase
        phase_groups = {}
        for task in tasks:
            phase = task.phase or 'No Phase'
            if phase not in phase_groups:
                phase_groups[phase] = []
            phase_groups[phase].append(task)

        # Create relationships within phases
        for phase, phase_tasks in phase_groups.items():
            if len(phase_tasks) >= 3:
                for i in range(min(5, len(phase_tasks) - 1)):
                    task = phase_tasks[i]
                    related = random.choice([t for t in phase_tasks if t != task])
                    task.related_tasks.add(related)

    def create_time_tracking_data(self, tasks, alex, sam, jordan, demo_admin=None):
        """Create time entries for tasks
        
        Also assigns some tasks to demo_admin_solo and creates time entries for them
        so the Time tab has data in demo mode.
        """
        users = [alex, sam, jordan]
        if demo_admin:
            users.append(demo_admin)
        now = timezone.now().date()
        entries_created = 0
        
        # For demo_admin_solo, we need to assign some tasks to them first
        # so they can see tasks in their timesheet
        if demo_admin:
            # Find tasks that are in progress or complete to assign to demo_admin
            # We'll reassign some tasks from each board to demo_admin (3 per board = 9 total)
            tasks_by_board = {}
            for task in tasks:
                board_name = task.column.board.name
                if board_name not in tasks_by_board:
                    tasks_by_board[board_name] = []
                tasks_by_board[board_name].append(task)
            
            demo_admin_tasks = []
            for board_name, board_tasks in tasks_by_board.items():
                # Get tasks with progress > 0 (in progress or done)
                in_progress_tasks = [t for t in board_tasks if t.progress and t.progress > 0]
                # Assign 2-3 tasks per board to demo_admin
                tasks_to_assign = in_progress_tasks[:3] if len(in_progress_tasks) >= 3 else in_progress_tasks
                for task in tasks_to_assign:
                    task.assigned_to = demo_admin
                    task.save()
                    demo_admin_tasks.append(task)
            
            self.stdout.write(f'   📝 Assigned {len(demo_admin_tasks)} tasks to demo_admin_solo')
            
            # Create time entries specifically for demo_admin's assigned tasks
            for task in demo_admin_tasks:
                # Create 2-4 time entries per task across the last 2 weeks
                num_entries = random.randint(2, 4)
                for i in range(num_entries):
                    hours = Decimal(str(random.uniform(0.5, 4))).quantize(Decimal('0.01'))
                    entry_date = now - timedelta(days=random.randint(0, 14))
                    
                    TimeEntry.objects.create(
                        task=task,
                        user=demo_admin,
                        hours_spent=hours,
                        description=f"Worked on {task.title[:30]}",
                        work_date=entry_date,
                    )
                    entries_created += 1

        for task in tasks:
            if task.progress > 0:
                # Create 1-3 time entries for tasks in progress or done
                num_entries = random.randint(1, 3)
                for i in range(num_entries):
                    user = task.assigned_to or random.choice(users)
                    hours = Decimal(str(random.uniform(0.5, 4))).quantize(Decimal('0.01'))

                    entry_date = now - timedelta(days=random.randint(1, 14))

                    TimeEntry.objects.create(
                        task=task,
                        user=user,
                        hours_spent=hours,
                        description=f"Worked on {task.title[:30]}",
                        work_date=entry_date,
                    )
                    entries_created += 1

        self.stdout.write(f'   ✅ Created {entries_created} time entries')

    def create_budget_roi_data(self, software_board, marketing_board, bug_board, admin_user):
        """Create budget and ROI data for all demo boards"""
        now = timezone.now().date()
        budget_configs = [
            {'board': software_board, 'budget': Decimal('75000.00'), 'hours': Decimal('1200.0'), 'name': 'Software Development'},
            {'board': marketing_board, 'budget': Decimal('35000.00'), 'hours': Decimal('600.0'), 'name': 'Marketing Campaign'},
            {'board': bug_board, 'budget': Decimal('25000.00'), 'hours': Decimal('500.0'), 'name': 'Bug Tracking'},
        ]

        for config in budget_configs:
            board = config['board']

            # Create or get budget
            budget, created = ProjectBudget.objects.get_or_create(
                board=board,
                defaults={
                    'allocated_budget': config['budget'],
                    'currency': 'USD',
                    'allocated_hours': config['hours'],
                    'warning_threshold': 80,
                    'critical_threshold': 95,
                    'ai_optimization_enabled': True,
                    'created_by': admin_user,
                }
            )

            if created:
                self.stdout.write(f'   ✅ Created budget for {config["name"]}: ${config["budget"]}')

            # Create task costs
            tasks = Task.objects.filter(column__board=board)[:15]
            task_costs_created = 0

            for i, task in enumerate(tasks):
                estimated_cost = Decimal(random.uniform(500, 5000)).quantize(Decimal('0.01'))
                estimated_hours = Decimal(random.uniform(4, 40)).quantize(Decimal('0.01'))

                # Some tasks over budget for realistic demo
                if i % 5 == 0:
                    actual_cost = estimated_cost * Decimal('1.25')
                else:
                    actual_cost = estimated_cost * Decimal(random.uniform(0.7, 1.1))

                TaskCost.objects.get_or_create(
                    task=task,
                    defaults={
                        'estimated_cost': estimated_cost,
                        'actual_cost': actual_cost.quantize(Decimal('0.01')),
                        'estimated_hours': estimated_hours,
                    }
                )
                task_costs_created += 1

            # Create historical ROI snapshots (10 months of data)
            total_tasks = Task.objects.filter(column__board=board).count()
            completed_tasks = Task.objects.filter(column__board=board, progress=100).count()
            
            # Delete existing ROI snapshots for this board to recreate fresh
            ProjectROI.objects.filter(board=board).delete()
            
            # Calculate actual costs for this board
            task_costs_qs = TaskCost.objects.filter(task__column__board=board)
            total_cost = sum([tc.actual_cost or Decimal('0.00') for tc in task_costs_qs]) if task_costs_qs else config['budget'] * Decimal('0.8')
            
            # Set initial values based on board type for realistic data
            board_name = config['name']
            if board_name == 'Software Development':
                base_expected = config['budget'] * Decimal('2.0')  # 100% ROI expected
                base_realized_ratio = Decimal('0.4')  # Starting at 40% realization
            elif board_name == 'Marketing Campaign':
                base_expected = config['budget'] * Decimal('1.8')  # 80% ROI expected
                base_realized_ratio = Decimal('0.35')  # Starting at 35% realization
            else:  # Bug Tracking
                base_expected = config['budget'] * Decimal('1.5')  # 50% ROI expected
                base_realized_ratio = Decimal('0.45')  # Starting at 45% realization
            
            # Create 10 historical snapshots over the past 10 months
            for i in range(10):
                snapshot_date = now - timedelta(days=30 * (9 - i))  # Go back 9 months, then forward
                
                # Calculate progressive improvement
                progress_factor = Decimal(str(i / 9))  # 0 to 1 over time
                
                # Realized value improves over time (from base to 80% of expected)
                realized_value = base_expected * (base_realized_ratio + (Decimal('0.4') * progress_factor))
                
                # Cost also increases progressively
                snapshot_cost = total_cost * (Decimal('0.3') + (Decimal('0.7') * progress_factor))
                
                # Calculate ROI percentage
                if snapshot_cost > 0:
                    roi_percentage = ((realized_value - snapshot_cost) / snapshot_cost) * 100
                else:
                    roi_percentage = Decimal('0.00')
                
                # Create snapshot
                ProjectROI.objects.create(
                    board=board,
                    snapshot_date=snapshot_date,
                    expected_value=base_expected,
                    realized_value=realized_value,
                    roi_percentage=roi_percentage,
                    total_cost=snapshot_cost,
                    total_tasks=total_tasks,
                    completed_tasks=int(completed_tasks * float(progress_factor)),  # Progressive completion
                    created_by=admin_user
                )

        self.stdout.write('   ✅ Budget and ROI data created (10 historical snapshots per board)')

    def create_burndown_data(self, software_board, marketing_board, bug_board):
        """
        Create burndown and velocity snapshot data with proper historical data.
        This ensures the burndown chart displays correctly with historical progress,
        projected completion, and confidence bands.
        """
        from kanban.utils.burndown_predictor import BurndownPredictor
        
        now = timezone.now()
        
        for board in [software_board, marketing_board, bug_board]:
            self.stdout.write(f'     Processing {board.name}...')
            
            # Step 1: Populate historical completion dates for completed tasks
            completed_tasks = list(Task.objects.filter(column__board=board, progress=100))
            
            if completed_tasks:
                # Distribute completion dates across past 6 weeks
                weeks_back = 6
                tasks_per_week = len(completed_tasks) // weeks_back if weeks_back > 0 else len(completed_tasks)
                
                task_index = 0
                for week in range(weeks_back, 0, -1):
                    # Calculate date range for this week
                    week_end = now - timedelta(weeks=week-1)
                    week_start = week_end - timedelta(days=7)
                    
                    # Determine how many tasks to complete this week (with variation)
                    base_count = tasks_per_week
                    variation = random.randint(-2, 3)
                    tasks_this_week = max(1, base_count + variation)
                    tasks_this_week = min(tasks_this_week, len(completed_tasks) - task_index)
                    
                    for i in range(tasks_this_week):
                        if task_index >= len(completed_tasks):
                            break
                            
                        task = completed_tasks[task_index]
                        
                        # Random completion time within the week
                        days_offset = random.randint(0, 6)
                        hours_offset = random.randint(0, 23)
                        minutes_offset = random.randint(0, 59)
                        
                        completion_date = week_start + timedelta(
                            days=days_offset,
                            hours=hours_offset,
                            minutes=minutes_offset
                        )
                        
                        task.completed_at = completion_date
                        task.progress = 100
                        task.save(update_fields=['completed_at', 'progress'])
                        
                        task_index += 1
                
                # Mark remaining tasks as completed recently (current week)
                current_week_start = now - timedelta(days=7)
                while task_index < len(completed_tasks):
                    task = completed_tasks[task_index]
                    days_offset = random.randint(0, 6)
                    hours_offset = random.randint(0, 23)
                    
                    completion_date = current_week_start + timedelta(
                        days=days_offset,
                        hours=hours_offset
                    )
                    
                    task.completed_at = completion_date
                    task.progress = 100
                    task.save(update_fields=['completed_at', 'progress'])
                    task_index += 1
            
            # Step 2: Clean up old burndown data
            BurndownPrediction.objects.filter(board=board).delete()
            TeamVelocitySnapshot.objects.filter(board=board).delete()
            
            # Step 3: Create velocity snapshots based on actual task completions
            predictor = BurndownPredictor()
            predictor._ensure_velocity_snapshots(board)
            
            # Step 4: Generate burndown prediction with proper chart data
            result = predictor.generate_burndown_prediction(board)
            
            prediction = result.get('prediction')
            if prediction:
                curve = prediction.burndown_curve_data
                self.stdout.write(
                    f'       ✓ {len(curve.get("historical", []))} historical, '
                    f'{len(curve.get("projected", []))} projected points'
                )
            else:
                self.stdout.write(self.style.WARNING('       ⚠ Prediction generation failed'))

        self.stdout.write('   ✅ Burndown and velocity data created with full chart data')

    def create_retrospective_data(self, software_board, marketing_board, bug_board, alex, sam, jordan):
        """Create retrospective data for demo boards"""
        now = timezone.now().date()
        boards = [
            (software_board, 'Software Development Sprint'),
            (marketing_board, 'Marketing Campaign Review'),
            (bug_board, 'Bug Fix Retrospective'),
        ]

        for board, title_prefix in boards:
            week_num = random.randint(1, 12)
            retro, created = ProjectRetrospective.objects.get_or_create(
                board=board,
                title=f'{title_prefix} - Week {week_num}',
                defaults={
                    'retrospective_type': 'sprint',
                    'status': 'finalized',
                    'period_start': now - timedelta(weeks=2),
                    'period_end': now - timedelta(weeks=1),
                    'what_went_well': f'Team showed good collaboration and met sprint goals for {board.name}.',
                    'what_needs_improvement': 'Consider improving code review turnaround time.',
                    'lessons_learned': [
                        {'title': 'Daily standups improve coordination', 'category': 'process'},
                        {'title': 'Clear requirements reduce rework', 'category': 'communication'}
                    ],
                    'improvement_recommendations': [
                        {'title': 'Add code review guidelines', 'priority': 'high'},
                        {'title': 'Implement pair programming for complex tasks', 'priority': 'medium'}
                    ],
                    'created_by': alex,
                }
            )

            if created:
                # Add lessons learned
                lessons = [
                    {'category': 'process', 'title': 'Daily standups improve coordination'},
                    {'category': 'technical', 'title': 'Code reviews catch bugs early'},
                    {'category': 'communication', 'title': 'Clear requirements reduce rework'},
                ]

                for lesson in lessons:
                    LessonLearned.objects.create(
                        retrospective=retro,
                        board=board,
                        category=lesson['category'],
                        title=lesson['title'],
                        description=f'Detailed insight about {lesson["title"].lower()}',
                        recommended_action=f'Apply {lesson["title"].lower()} in next sprint',
                        priority='high' if random.random() > 0.5 else 'medium',
                        status='identified',
                    )

                # Add action items
                RetrospectiveActionItem.objects.create(
                    retrospective=retro,
                    board=board,
                    title='Implement suggested improvement',
                    description='Follow up on retrospective discussion',
                    action_type='process_change',
                    assigned_to=sam,
                    target_completion_date=(timezone.now() + timedelta(days=14)).date(),
                    priority='high',
                    status='in_progress',
                )

        self.stdout.write('   ✅ Retrospective data created')

    def create_coaching_data(self, software_board, marketing_board, bug_board):
        """Create AI-enhanced coaching suggestions for demo boards
        
        This creates detailed suggestions matching the AI-enhanced format:
        - Comprehensive reasoning (why this matters)
        - 3-5 detailed action steps with rationale, expected outcomes, and implementation hints
        - Expected impact with quantifiable outcomes
        - Proper metrics snapshot
        """
        # Delete existing suggestions first to avoid duplicates
        CoachingSuggestion.objects.filter(
            board__in=[software_board, marketing_board, bug_board]
        ).delete()
        
        # AI-Enhanced suggestions with detailed format
        suggestions = [
            # Suggestion 1: Resource Overload (High Severity)
            {
                'suggestion_type': 'resource_overload',
                'title': 'Team workload imbalance detected',
                'message': 'Sam has 60% more tasks than other team members. Consider redistributing work to prevent burnout and ensure timely delivery.',
                'severity': 'high',
                'reasoning': 'Workload imbalances can lead to burnout, reduced productivity, and potential project delays. When one team member has significantly more tasks than others, it creates a single point of failure. If Sam becomes unavailable or overwhelmed, critical work could stall. Additionally, uneven workloads can impact team morale as other members may feel underutilized.',
                'recommended_actions': [
                    "Conduct a workload review meeting with the team • Rationale: Creates transparency about current assignments and identifies immediate redistribution opportunities • Expected outcome: Identify 3-5 tasks that can be reassigned immediately • How to: Schedule 30-minute meeting, use task board to visualize assignments per person",
                    "Prioritize Sam's tasks and identify which can be delegated • Rationale: Not all high-priority tasks require Sam's specific expertise • Expected outcome: Reduce Sam's workload by 30% without impacting critical deliverables • How to: Review each task for skill requirements, pair junior members with Sam for knowledge transfer",
                    "Implement work-in-progress (WIP) limits • Rationale: Prevents any team member from accumulating too many tasks • Expected outcome: Even distribution of work across the team • How to: Set WIP limit of 5 tasks per person, add to team working agreement",
                    "Schedule regular capacity planning reviews • Rationale: Proactive monitoring prevents future imbalances • Expected outcome: Early detection of workload issues • How to: Weekly 15-minute standup focused on capacity, rotate facilitator role"
                ],
                'expected_impact': 'Rebalancing workload can improve team velocity by 15-20%, reduce burnout risk, and improve overall team satisfaction. Even task distribution also builds redundancy into the team.',
                'confidence_score': 0.88,
                'metrics_snapshot': {'imbalanced_member': 'Sam', 'task_variance': '60%', 'team_avg_tasks': 8, 'overloaded_tasks': 13}
            },
            # Suggestion 2: Deadline Risk (Medium Severity)
            {
                'suggestion_type': 'deadline_risk',
                'title': 'Deadline risk identified',
                'message': 'Based on current velocity, the beta release may slip by 3 days. Immediate attention needed to mitigate timeline risk.',
                'severity': 'medium',
                'reasoning': 'Current velocity metrics show the team completing 8 tasks per week, but 12 tasks remain for the beta release with only 1 week left. This 3-day projected slip could cascade into downstream dependencies including marketing launch dates and customer commitments. Early identification allows for scope adjustment or resource reallocation.',
                'recommended_actions': [
                    "Review remaining tasks and identify scope reduction opportunities • Rationale: Some features may be deferrable to post-beta without impacting core functionality • Expected outcome: Reduce remaining work by 20-30% • How to: Hold scope review with product owner, use MoSCoW prioritization",
                    "Identify and remove blockers immediately • Rationale: Blocked tasks directly impact velocity and create uncertainty • Expected outcome: Increase effective velocity by 15% • How to: Daily blocker review, escalate dependencies same-day",
                    "Consider focused sprint with reduced meetings • Rationale: Meeting overhead reduces productive coding time • Expected outcome: Gain 2-3 hours per developer per day • How to: Cancel non-essential meetings, move standups to async format",
                    "Communicate proactively with stakeholders • Rationale: Managing expectations early preserves trust and allows for contingency planning • Expected outcome: Stakeholder alignment on realistic timeline • How to: Send status update email, propose adjusted date with confidence level"
                ],
                'expected_impact': 'Addressing deadline risk early can reduce actual slip from 3 days to 1 day or less. Proactive communication maintains stakeholder trust and allows for better planning.',
                'confidence_score': 0.82,
                'metrics_snapshot': {'current_velocity': 8, 'remaining_tasks': 12, 'days_remaining': 7, 'projected_slip_days': 3}
            },
            # Suggestion 3: Best Practice (Low Severity)
            {
                'suggestion_type': 'best_practice',
                'title': 'Process improvement opportunity',
                'message': 'Tasks in review stage average 4 days. Consider adding reviewers or streamlining the review process.',
                'severity': 'low',
                'reasoning': 'A 4-day average review time creates bottlenecks and slows down delivery. Industry best practice targets 1-2 days for code review. Extended review periods indicate potential issues with reviewer availability, unclear acceptance criteria, or overly complex code changes. Long reviews also increase context-switching costs when changes are requested.',
                'recommended_actions': [
                    "Establish a reviewer rotation schedule • Rationale: Dedicated review time ensures consistent throughput • Expected outcome: Reduce review wait time by 50% • How to: Assign review slots (morning/afternoon) to specific team members, update working agreement",
                    "Create a review checklist and guidelines • Rationale: Clear criteria speeds up reviews and reduces back-and-forth • Expected outcome: More consistent, faster reviews • How to: Document 5-10 key items to check, include in PR template",
                    "Implement automated pre-review checks • Rationale: Catches common issues before human review, reducing cognitive load • Expected outcome: 20% fewer review comments on trivial issues • How to: Set up linting, formatting, and basic test gates in CI/CD",
                    "Consider pair programming for complex changes • Rationale: Real-time collaboration eliminates post-hoc review delays • Expected outcome: Near-zero review time for paired work • How to: Identify complex tasks upfront, schedule pairing sessions"
                ],
                'expected_impact': 'Reducing review time from 4 days to 2 days can improve team velocity by 15-20%, accelerate feature delivery, and reduce developer frustration with waiting.',
                'confidence_score': 0.85,
                'metrics_snapshot': {'avg_review_days': 4, 'target_review_days': 2, 'tasks_in_review': 5, 'longest_review_days': 7}
            },
        ]

        # Board-specific additional suggestions
        software_specific = {
            'suggestion_type': 'dependency_blocker',
            'title': 'Dependency chain creating risk',
            'message': 'Three tasks have dependencies that could delay the API integration milestone.',
            'severity': 'high',
            'reasoning': 'Sequential dependencies create a critical path where delays compound. The current dependency chain (Database Schema → API Structure → Authentication) means any slip in early tasks directly impacts all downstream work. This pattern also limits parallel work opportunities.',
            'recommended_actions': [
                "Map and visualize the complete dependency chain • Rationale: Understanding the full impact helps prioritize interventions • Expected outcome: Clear view of critical path and risk points • How to: Use Gantt chart or dependency graph, mark critical path items",
                "Identify opportunities to parallelize work • Rationale: Breaking dependencies enables concurrent progress • Expected outcome: Reduce critical path length by 20% • How to: Mock interfaces early, use feature flags for partial integration",
                "Add buffer time to critical path estimates • Rationale: Dependencies have higher uncertainty requiring risk buffer • Expected outcome: More realistic project timeline • How to: Add 20% buffer to dependent task estimates",
                "Daily sync on dependency status • Rationale: Early warning of slips enables faster response • Expected outcome: Issues identified within 24 hours • How to: Add dependency check to daily standup agenda"
            ],
            'expected_impact': 'Proactive dependency management can reduce schedule risk by 30% and enable more parallel work streams.',
            'confidence_score': 0.80,
            'metrics_snapshot': {'dependent_tasks': 3, 'max_chain_length': 4, 'critical_path_days': 12}
        }

        marketing_specific = {
            'suggestion_type': 'scope_creep',
            'title': 'Campaign scope expanding',
            'message': 'The marketing campaign has grown by 25% since initial planning. Consider a scope review.',
            'severity': 'medium',
            'reasoning': 'Scope creep often occurs gradually through well-intentioned additions. A 25% growth indicates potential misalignment between resources and objectives. Without adjustment, this leads to quality compromises, missed deadlines, or team burnout.',
            'recommended_actions': [
                "Conduct a scope review session with stakeholders • Rationale: Realign expectations with available resources • Expected outcome: Clear agreement on essential vs nice-to-have deliverables • How to: List all additions since kickoff, apply MoSCoW prioritization",
                "Document and communicate the scope baseline • Rationale: Creates shared understanding and change control process • Expected outcome: Reduced ad-hoc scope additions • How to: Create scope document, require sign-off for changes",
                "Evaluate resource needs if scope must stay • Rationale: Expanding scope requires expanding capacity • Expected outcome: Realistic plan with adequate resources • How to: Calculate effort for additions, identify resource gaps",
                "Implement a change request process • Rationale: Formal process slows uncontrolled growth • Expected outcome: Deliberate decisions about scope changes • How to: Create simple change request form, require impact assessment"
            ],
            'expected_impact': 'Managing scope creep can improve delivery success rate by 40% and maintain team sustainable pace.',
            'confidence_score': 0.78,
            'metrics_snapshot': {'original_tasks': 20, 'current_tasks': 25, 'scope_growth_percent': 25}
        }

        bug_specific = {
            'suggestion_type': 'quality_issue',
            'title': 'Bug recurrence pattern detected',
            'message': 'Similar bugs are reappearing in the authentication module. Root cause analysis recommended.',
            'severity': 'high',
            'reasoning': 'Recurring bugs indicate systemic issues rather than isolated defects. The authentication module pattern suggests potential gaps in testing coverage, unclear requirements, or architectural weaknesses. Each recurrence wastes fix time and erodes user trust.',
            'recommended_actions': [
                "Conduct root cause analysis on recurring bugs • Rationale: Surface fixes don't address underlying issues • Expected outcome: Identify systemic causes and prevention strategies • How to: Use 5 Whys technique, involve senior engineers",
                "Increase test coverage for authentication module • Rationale: Gaps in testing allow regressions • Expected outcome: Prevent 80% of bug recurrence • How to: Add integration tests, implement mutation testing",
                "Review and clarify authentication requirements • Rationale: Ambiguous requirements lead to implementation gaps • Expected outcome: Clearer acceptance criteria • How to: Document edge cases, validate with security team",
                "Consider architectural review of authentication • Rationale: Pattern may indicate design issues • Expected outcome: More robust implementation • How to: Schedule architecture review session, consider refactoring"
            ],
            'expected_impact': 'Addressing root causes can reduce bug recurrence by 70% and improve overall code quality.',
            'confidence_score': 0.85,
            'metrics_snapshot': {'recurring_bugs': 5, 'affected_module': 'authentication', 'recurrence_rate': '30%'}
        }

        # Create suggestions for each board
        created_count = 0
        
        for board, specific_suggestion in [
            (software_board, software_specific),
            (marketing_board, marketing_specific),
            (bug_board, bug_specific)
        ]:
            # Create common suggestions for each board
            for suggestion in suggestions:
                CoachingSuggestion.objects.create(
                    board=board,
                    suggestion_type=suggestion['suggestion_type'],
                    title=suggestion['title'],
                    message=suggestion['message'],
                    severity=suggestion['severity'],
                    status='active',
                    reasoning=suggestion['reasoning'],
                    recommended_actions=suggestion['recommended_actions'],
                    expected_impact=suggestion['expected_impact'],
                    confidence_score=suggestion['confidence_score'],
                    metrics_snapshot=suggestion['metrics_snapshot'],
                    ai_model_used='gemini-2.0-flash-exp',
                    generation_method='hybrid',  # Indicates AI-enhanced format
                )
                created_count += 1
            
            # Create board-specific suggestion
            CoachingSuggestion.objects.create(
                board=board,
                suggestion_type=specific_suggestion['suggestion_type'],
                title=specific_suggestion['title'],
                message=specific_suggestion['message'],
                severity=specific_suggestion['severity'],
                status='active',
                reasoning=specific_suggestion['reasoning'],
                recommended_actions=specific_suggestion['recommended_actions'],
                expected_impact=specific_suggestion['expected_impact'],
                confidence_score=specific_suggestion['confidence_score'],
                metrics_snapshot=specific_suggestion['metrics_snapshot'],
                ai_model_used='gemini-2.0-flash-exp',
                generation_method='hybrid',
            )
            created_count += 1

        self.stdout.write(f'   ✅ AI coaching suggestions created ({created_count} total, all AI-enhanced)')
        
        # Create PM Metrics for analytics dashboard
        self.create_pm_metrics(software_board, marketing_board, bug_board)

    def create_pm_metrics(self, software_board, marketing_board, bug_board):
        """Create PM performance metrics for analytics dashboard
        
        Creates historical metrics data so the coaching analytics page has
        meaningful data to display immediately.
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Get demo users
        demo_admin = User.objects.filter(
            username__in=['demo_pm', 'alex_demo', 'admin']
        ).first()
        
        if not demo_admin:
            self.stdout.write('   ⚠️  PM metrics skipped (no demo user found)')
            return
        
        # Delete existing metrics
        PMMetrics.objects.filter(
            board__in=[software_board, marketing_board, bug_board]
        ).delete()
        
        now = timezone.now().date()
        
        # Create 4 weeks of historical metrics for each board
        metrics_created = 0
        
        for board in [software_board, marketing_board, bug_board]:
            for week_offset in range(4):
                period_end = now - timedelta(weeks=week_offset)
                period_start = period_end - timedelta(days=7)
                
                # Vary metrics to show realistic patterns
                if week_offset == 0:  # Current week
                    suggestions_received = random.randint(3, 5)
                    suggestions_acted = random.randint(2, 4)
                    velocity_trend = 'stable'
                    risk_rate = random.uniform(70, 85)
                    deadline_rate = random.uniform(80, 95)
                    effectiveness = random.uniform(70, 85)
                elif week_offset == 1:  # Last week
                    suggestions_received = random.randint(4, 6)
                    suggestions_acted = random.randint(3, 5)
                    velocity_trend = 'improving'
                    risk_rate = random.uniform(65, 80)
                    deadline_rate = random.uniform(75, 90)
                    effectiveness = random.uniform(65, 80)
                else:  # Older weeks
                    suggestions_received = random.randint(2, 4)
                    suggestions_acted = random.randint(1, 3)
                    velocity_trend = random.choice(['stable', 'improving', 'declining'])
                    risk_rate = random.uniform(60, 75)
                    deadline_rate = random.uniform(70, 85)
                    effectiveness = random.uniform(55, 70)
                
                PMMetrics.objects.create(
                    board=board,
                    pm_user=demo_admin,
                    period_start=period_start,
                    period_end=period_end,
                    suggestions_received=suggestions_received,
                    suggestions_acted_on=suggestions_acted,
                    avg_response_time_hours=Decimal(str(round(random.uniform(4, 48), 2))),
                    velocity_trend=velocity_trend,
                    risk_mitigation_success_rate=Decimal(str(round(risk_rate, 2))),
                    deadline_hit_rate=Decimal(str(round(deadline_rate, 2))),
                    team_satisfaction_score=Decimal(str(round(random.uniform(3.5, 4.5), 1))),
                    improvement_areas=['communication', 'planning'] if week_offset < 2 else ['risk management'],
                    struggle_areas=['scope management'] if week_offset == 0 else [],
                    coaching_effectiveness_score=Decimal(str(round(effectiveness, 2))),
                    calculated_by='demo_data_population',
                )
                metrics_created += 1
        
        self.stdout.write(f'   ✅ PM metrics created ({metrics_created} total)')
        
        # Create coaching insights for analytics
        self.create_coaching_insights()

    def create_coaching_insights(self):
        """Create coaching insights for analytics dashboard
        
        Insights represent learned patterns from coaching interactions
        that help improve future suggestions.
        """
        # Delete existing insights
        CoachingInsight.objects.all().delete()
        
        insights_data = [
            {
                'insight_type': 'pattern',
                'title': 'Resource overload correlates with deadline misses',
                'description': 'Teams with workload imbalances above 50% show a 35% higher rate of deadline misses. Early intervention when imbalance exceeds 40% significantly improves outcomes.',
                'confidence_score': Decimal('0.85'),
                'sample_size': 150,
                'applicable_to_suggestion_types': ['resource_overload', 'deadline_risk'],
                'rule_adjustments': {'threshold_adjustment': -10, 'severity_boost': True},
                'is_active': True,
            },
            {
                'insight_type': 'effectiveness',
                'title': 'Review time suggestions have high action rate',
                'description': 'Suggestions about reducing review time are acted upon 78% of the time, with 82% of users reporting positive outcomes. This category of suggestions is highly effective.',
                'confidence_score': Decimal('0.82'),
                'sample_size': 95,
                'applicable_to_suggestion_types': ['best_practice', 'quality_issue'],
                'rule_adjustments': {},
                'is_active': True,
            },
            {
                'insight_type': 'pm_behavior',
                'title': 'PMs respond faster to high-severity suggestions',
                'description': 'Average response time for critical/high severity suggestions is 4.2 hours compared to 18.5 hours for low severity. Consider severity escalation for time-sensitive issues.',
                'confidence_score': Decimal('0.90'),
                'sample_size': 280,
                'applicable_to_suggestion_types': ['deadline_risk', 'resource_overload', 'quality_issue'],
                'rule_adjustments': {'auto_escalate_after_days': 2},
                'is_active': True,
            },
            {
                'insight_type': 'team_dynamics',
                'title': 'Small teams respond better to specific recommendations',
                'description': 'Teams of 3-5 members show 40% higher action rate on specific, actionable recommendations compared to general guidance. Larger teams prefer strategic suggestions.',
                'confidence_score': Decimal('0.75'),
                'sample_size': 120,
                'applicable_to_suggestion_types': ['best_practice', 'communication_gap'],
                'rule_adjustments': {'team_size_threshold': 5},
                'is_active': True,
            },
            {
                'insight_type': 'context_factor',
                'title': 'End-of-sprint suggestions less effective',
                'description': 'Suggestions generated in the final 2 days of a sprint have 45% lower action rates. Teams are focused on completion rather than process improvements during this time.',
                'confidence_score': Decimal('0.78'),
                'sample_size': 200,
                'applicable_to_suggestion_types': ['best_practice', 'scope_creep'],
                'rule_adjustments': {'suppress_in_final_days': 2},
                'is_active': True,
            },
        ]
        
        for insight in insights_data:
            CoachingInsight.objects.create(**insight)
        
        self.stdout.write(f'   ✅ Coaching insights created ({len(insights_data)} total)')

    def create_comments(self, tasks, alex, sam, jordan):
        """Create realistic comments for tasks"""
        users = [alex, sam, jordan]
        comments_created = 0
        now = timezone.now().date()

        for task in tasks:
            # Create 0-4 comments per task
            num_comments = random.randint(0, 4)

            for i in range(num_comments):
                user = random.choice(users)
                template = random.choice(COMMENT_TEMPLATES)

                # Fill in template variables
                comment_text = template.format(
                    progress_detail=random.choice(PROGRESS_DETAILS),
                    technical_detail=random.choice(TECHNICAL_DETAILS),
                    complexity_reason=random.choice(COMPLEXITY_REASONS),
                    mention=random.choice([u.username for u in users if u != user]),
                    related_task=random.choice(tasks).title[:30] if tasks else 'another task',
                )

                comment_date = now - timedelta(days=random.randint(1, 30), hours=random.randint(0, 23))

                Comment.objects.create(
                    task=task,
                    user=user,
                    content=comment_text,
                    created_at=comment_date,
                )
                comments_created += 1

        self.stdout.write(f'   ✅ Created {comments_created} comments')

    def create_activity_logs(self, tasks, alex, sam, jordan):
        """Create activity logs for tasks"""
        users = [alex, sam, jordan]
        activities_created = 0
        now = timezone.now().date()

        for task in tasks:
            # Always create a 'created' activity
            TaskActivity.objects.create(
                task=task,
                user=task.created_by or alex,
                activity_type='created',
                description=random.choice(ACTIVITY_TEMPLATES['created']),
            )
            activities_created += 1

            # Add 1-3 more activities based on task progress
            if task.progress > 0:
                num_activities = random.randint(1, 3)

                for i in range(num_activities):
                    activity_type = random.choice(['updated', 'moved', 'commented'])
                    templates = ACTIVITY_TEMPLATES.get(activity_type, ['performed an action'])
                    description = random.choice(templates)

                    # Fill in template variables
                    description = description.format(
                        from_col='To Do',
                        to_col='In Progress',
                        assignee=random.choice([u.username for u in users]),
                        priority=task.priority or 'medium',
                        progress=task.progress,
                        label='Kaizen',
                    )

                    TaskActivity.objects.create(
                        task=task,
                        user=random.choice(users),
                        activity_type=activity_type,
                        description=description,
                    )
                    activities_created += 1

        self.stdout.write(f'   ✅ Created {activities_created} activity logs')

    def create_stakeholders(self, software_board, marketing_board, bug_board, tasks, alex, sam, jordan):
        """Create stakeholders and link them to tasks"""
        stakeholder_data = [
            {'name': 'Sarah Johnson', 'role': 'Product Owner', 'email': 'sarah.j@example.com', 'influence': 'high'},
            {'name': 'Mike Chen', 'role': 'Engineering Director', 'email': 'mike.c@example.com', 'influence': 'high'},
            {'name': 'Lisa Park', 'role': 'QA Lead', 'email': 'lisa.p@example.com', 'influence': 'medium'},
            {'name': 'David Wilson', 'role': 'UX Designer', 'email': 'david.w@example.com', 'influence': 'medium'},
            {'name': 'Emma Davis', 'role': 'Marketing Manager', 'email': 'emma.d@example.com', 'influence': 'medium'},
        ]

        for board in [software_board, marketing_board, bug_board]:
            for data in stakeholder_data:
                stakeholder, created = ProjectStakeholder.objects.get_or_create(
                    board=board,
                    email=data['email'],
                    name=data['name'],
                    defaults={
                        'role': data['role'],
                        'influence_level': data['influence'],
                        'interest_level': 'medium',
                        'created_by': alex,
                    }
                )

        # Link stakeholders to some tasks
        stakeholders = list(ProjectStakeholder.objects.filter(
            board__in=[software_board, marketing_board, bug_board]
        ))

        for task in tasks[:20]:  # Link to first 20 tasks
            stakeholder = random.choice(stakeholders)
            StakeholderTaskInvolvement.objects.get_or_create(
                stakeholder=stakeholder,
                task=task,
                defaults={
                    'involvement_type': random.choice(['reviewer', 'observer', 'contributor']),
                    'engagement_status': random.choice(['informed', 'consulted', 'involved']),
                    'feedback': f'Involved in {task.title[:30]}',
                }
            )

        self.stdout.write('   ✅ Stakeholders created and linked to tasks')

    def create_file_attachments(self, tasks, alex, sam, jordan):
        """Create simulated file attachment metadata for tasks"""
        # Skip file attachments since they require actual file uploads
        # which can't be simulated in demo data
        self.stdout.write('   ✅ File attachments skipped (requires actual file uploads)')

    def create_wiki_links(self, tasks, demo_org, alex):
        """Create wiki links for tasks (if wiki system exists)"""
        # This is a placeholder - implement if wiki system is available
        self.stdout.write('   ✅ Wiki links skipped (wiki system not configured)')
