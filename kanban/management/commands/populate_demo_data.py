"""
Management command to populate demo boards with realistic tasks
Creates ~120 tasks across 3 demo boards with proper assignments, dates, dependencies, and skills
Includes comprehensive demo data for all task fields including risk, skills, and collaboration
Also includes comments, activity logs, stakeholders, wiki links, and file attachment metadata
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta, date
from decimal import Decimal
from kanban.models import Board, Column, Task, TaskLabel, Organization, Milestone, Comment, TaskActivity, TaskFile
from kanban.permission_models import Role
from kanban.budget_models import TimeEntry, ProjectBudget, TaskCost, ProjectROI
from kanban.burndown_models import TeamVelocitySnapshot, BurndownPrediction
from kanban.retrospective_models import ProjectRetrospective, LessonLearned, ImprovementMetric, RetrospectiveActionItem
from kanban.coach_models import CoachingSuggestion, PMMetrics
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
    'Review milestone deadlines',
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

        if not all([alex, sam, jordan]):
            self.stdout.write(self.style.ERROR(
                '❌ Demo personas not found. Please run: python manage.py create_demo_organization'
            ))
            return

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

        # Reset existing demo tasks if requested
        if options['reset']:
            self.stdout.write(self.style.WARNING('🔄 Resetting existing demo tasks...'))
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

        # Create tasks for each board
        self.stdout.write(self.style.SUCCESS('📝 Creating demo tasks...\n'))

        software_tasks = self.create_software_tasks(software_board, alex, sam, jordan)
        self.stdout.write(self.style.SUCCESS(
            f'   ✅ Software Development: {len(software_tasks)} tasks created'
        ))

        marketing_tasks = self.create_marketing_tasks(marketing_board, alex, sam, jordan)
        self.stdout.write(self.style.SUCCESS(
            f'   ✅ Marketing Campaign: {len(marketing_tasks)} tasks created'
        ))

        bug_tasks = self.create_bug_tasks(bug_board, alex, sam, jordan)
        self.stdout.write(self.style.SUCCESS(
            f'   ✅ Bug Tracking: {len(bug_tasks)} tasks created'
        ))

        total_tasks = len(software_tasks) + len(marketing_tasks) + len(bug_tasks)
        self.stdout.write(self.style.SUCCESS(f'\n   📊 Total tasks created: {total_tasks}'))

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
        self.create_time_tracking_data(all_tasks, alex, sam, jordan)

        # Create milestones for Gantt chart
        self.stdout.write(self.style.SUCCESS('\n📌 Creating milestones...\n'))
        self.create_milestones(software_board, marketing_board, bug_board, alex, sam, jordan)

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

        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('✅ DEMO DATA POPULATION COMPLETE'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))

    def create_software_tasks(self, board, alex, sam, jordan):
        """Create 50 tasks for Software Development board"""
        columns = {col.name: col for col in Column.objects.filter(board=board)}
        tasks = []
        now = timezone.now()

        # To Do tasks (15)
        backlog_tasks = [
            {
                'title': 'Implement user authentication system',
                'description': 'Build secure login/logout with JWT tokens and refresh token rotation',
                'priority': 'high',
                'complexity': 8,
                'assigned_to': sam,
            },
            {
                'title': 'Design database schema for multi-tenancy',
                'description': 'Create scalable database architecture supporting multiple organizations',
                'priority': 'high',
                'complexity': 9,
                'assigned_to': sam,
            },
            {
                'title': 'Build REST API endpoints for user management',
                'description': 'CRUD operations for users with proper validation and error handling',
                'priority': 'medium',
                'complexity': 6,
                'assigned_to': sam,
            },
            {
                'title': 'Create responsive dashboard layout',
                'description': 'Mobile-first dashboard with Bootstrap 5 and custom CSS',
                'priority': 'medium',
                'complexity': 5,
                'assigned_to': sam,
            },
            {
                'title': 'Implement file upload functionality',
                'description': 'Support for multiple file types with virus scanning and storage optimization',
                'priority': 'low',
                'complexity': 7,
                'assigned_to': sam,
            },
            {
                'title': 'Add email notification system',
                'description': 'Async email sending with templates and delivery tracking',
                'priority': 'medium',
                'complexity': 6,
                'assigned_to': sam,
            },
            {
                'title': 'Build search functionality with Elasticsearch',
                'description': 'Full-text search across all entities with faceted filtering',
                'priority': 'low',
                'complexity': 8,
                'assigned_to': sam,
            },
            {
                'title': 'Create data export feature (CSV/Excel)',
                'description': 'Export any dataset to CSV or Excel with custom column selection',
                'priority': 'low',
                'complexity': 4,
                'assigned_to': jordan,
            },
            {
                'title': 'Implement API rate limiting',
                'description': 'Protect API endpoints from abuse with configurable rate limits',
                'priority': 'medium',
                'complexity': 5,
                'assigned_to': sam,
            },
            {
                'title': 'Add webhook support for integrations',
                'description': 'Allow external systems to receive real-time event notifications',
                'priority': 'low',
                'complexity': 7,
                'assigned_to': sam,
            },
            {
                'title': 'Build admin dashboard for system monitoring',
                'description': 'Real-time metrics, logs, and system health indicators',
                'priority': 'medium',
                'complexity': 6,
                'assigned_to': alex,
            },
            {
                'title': 'Implement two-factor authentication',
                'description': 'TOTP-based 2FA with recovery codes and backup options',
                'priority': 'high',
                'complexity': 7,
                'assigned_to': sam,
            },
            {
                'title': 'Create mobile PWA manifest and service worker',
                'description': 'Enable install-to-home-screen and offline capabilities',
                'priority': 'medium',
                'complexity': 6,
                'assigned_to': sam,
            },
            {
                'title': 'Add dark mode theme support',
                'description': 'User-selectable dark theme with smooth transitions',
                'priority': 'low',
                'complexity': 4,
                'assigned_to': sam,
            },
            {
                'title': 'Build automated backup system',
                'description': 'Daily database backups with retention policy and restore testing',
                'priority': 'high',
                'complexity': 5,
                'assigned_to': alex,
            },
        ]

        for i, task_data in enumerate(backlog_tasks):
            task = Task.objects.create(
                column=columns['To Do'],
                title=task_data['title'],
                description=task_data['description'],
                priority=task_data['priority'],
                complexity_score=task_data['complexity'],
                assigned_to=task_data['assigned_to'],
                created_by=alex,
                progress=0,
                due_date=now + timedelta(days=random.randint(20, 45)),
                is_seed_demo_data=True,
            )
            tasks.append(task)

        # In Progress tasks (20)
        in_progress_tasks = [
            {
                'title': 'Refactor authentication middleware',
                'description': 'Improve performance and add better error handling',
                'priority': 'high',
                'complexity': 7,
                'assigned_to': sam,
                'progress': 60,
            },
            {
                'title': 'Optimize database queries in dashboard',
                'description': 'Reduce N+1 queries and add proper indexes',
                'priority': 'high',
                'complexity': 6,
                'assigned_to': sam,
                'progress': 45,
            },
            {
                'title': 'Implement real-time notifications with WebSockets',
                'description': 'Add Django Channels for live updates',
                'priority': 'medium',
                'complexity': 8,
                'assigned_to': sam,
                'progress': 30,
            },
            {
                'title': 'Create user onboarding flow',
                'description': 'Step-by-step wizard for new users',
                'priority': 'medium',
                'complexity': 5,
                'assigned_to': sam,
                'progress': 70,
            },
            {
                'title': 'Add integration with Slack',
                'description': 'Post notifications to Slack channels',
                'priority': 'low',
                'complexity': 6,
                'assigned_to': sam,
                'progress': 20,
            },
            {
                'title': 'Build analytics dashboard with charts',
                'description': 'Interactive charts using Chart.js',
                'priority': 'medium',
                'complexity': 7,
                'assigned_to': sam,
                'progress': 50,
            },
            {
                'title': 'Implement activity feed/timeline',
                'description': 'Show recent actions across the platform',
                'priority': 'low',
                'complexity': 5,
                'assigned_to': sam,
                'progress': 40,
            },
            {
                'title': 'Add bulk actions for task management',
                'description': 'Select and modify multiple items at once',
                'priority': 'medium',
                'complexity': 5,
                'assigned_to': sam,
                'progress': 55,
            },
            {
                'title': 'Create custom field system',
                'description': 'Allow users to define custom attributes',
                'priority': 'low',
                'complexity': 8,
                'assigned_to': sam,
                'progress': 25,
            },
            {
                'title': 'Implement advanced filtering UI',
                'description': 'Multi-criteria filters with save/load functionality',
                'priority': 'medium',
                'complexity': 6,
                'assigned_to': sam,
                'progress': 65,
            },
            {
                'title': 'Add calendar view for tasks',
                'description': 'Monthly/weekly calendar with drag-and-drop',
                'priority': 'low',
                'complexity': 7,
                'assigned_to': sam,
                'progress': 35,
            },
            {
                'title': 'Build comment system with mentions',
                'description': '@mention users to notify them in comments',
                'priority': 'medium',
                'complexity': 6,
                'assigned_to': sam,
                'progress': 50,
            },
            {
                'title': 'Create audit log for compliance',
                'description': 'Track all changes for security auditing',
                'priority': 'high',
                'complexity': 7,
                'assigned_to': sam,
                'progress': 40,
            },
            {
                'title': 'Implement role-based access control',
                'description': 'Granular permissions system with roles',
                'priority': 'high',
                'complexity': 9,
                'assigned_to': sam,
                'progress': 75,
            },
            {
                'title': 'Add keyboard shortcuts for power users',
                'description': 'Vim-style shortcuts for common actions',
                'priority': 'low',
                'complexity': 4,
                'assigned_to': sam,
                'progress': 60,
            },
            {
                'title': 'Build template system for recurring tasks',
                'description': 'Save and reuse task templates',
                'priority': 'medium',
                'complexity': 6,
                'assigned_to': sam,
                'progress': 45,
            },
            {
                'title': 'Create API documentation with Swagger',
                'description': 'Interactive API docs for developers',
                'priority': 'medium',
                'complexity': 5,
                'assigned_to': sam,
                'progress': 80,
            },
            {
                'title': 'Implement time tracking functionality',
                'description': 'Track time spent on tasks with reports',
                'priority': 'medium',
                'complexity': 7,
                'assigned_to': sam,
                'progress': 55,
            },
            {
                'title': 'Add team workload visualization',
                'description': 'Visual representation of team capacity',
                'priority': 'high',
                'complexity': 6,
                'assigned_to': sam,
                'progress': 40,
            },
            {
                'title': 'Build dependency management system',
                'description': 'Define and visualize task dependencies',
                'priority': 'high',
                'complexity': 8,
                'assigned_to': sam,
                'progress': 70,
            },
        ]

        for task_data in in_progress_tasks:
            task = Task.objects.create(
                column=columns['In Progress'],
                title=task_data['title'],
                description=task_data['description'],
                priority=task_data['priority'],
                complexity_score=task_data['complexity'],
                assigned_to=task_data['assigned_to'],
                created_by=alex,
                progress=task_data['progress'],
                due_date=now + timedelta(days=random.randint(5, 15)),
                is_seed_demo_data=True,
            )
            tasks.append(task)

        # In Review tasks (10)
        in_review_tasks = [
            {
                'title': 'Code review: API endpoint refactoring',
                'description': 'Review REST API improvements and breaking changes',
                'priority': 'high',
                'complexity': 5,
                'assigned_to': sam,
                'progress': 90,
            },
            {
                'title': 'UI/UX review: New dashboard layout',
                'description': 'Get feedback on redesigned dashboard',
                'priority': 'medium',
                'complexity': 4,
                'assigned_to': sam,
                'progress': 85,
            },
            {
                'title': 'Security review: Authentication system',
                'description': 'Audit new auth implementation for vulnerabilities',
                'priority': 'urgent',
                'complexity': 7,
                'assigned_to': alex,
                'progress': 95,
            },
            {
                'title': 'Performance testing: Database optimization',
                'description': 'Load test new query optimizations',
                'priority': 'high',
                'complexity': 6,
                'assigned_to': sam,
                'progress': 88,
            },
            {
                'title': 'Documentation review: API guides',
                'description': 'Proofread and verify API documentation',
                'priority': 'medium',
                'complexity': 3,
                'assigned_to': jordan,
                'progress': 92,
            },
            {
                'title': 'QA testing: Notification system',
                'description': 'Test all notification scenarios',
                'priority': 'high',
                'complexity': 5,
                'assigned_to': sam,
                'progress': 80,
            },
            {
                'title': 'Accessibility audit: Forms and inputs',
                'description': 'Ensure WCAG 2.1 AA compliance',
                'priority': 'medium',
                'complexity': 4,
                'assigned_to': sam,
                'progress': 87,
            },
            {
                'title': 'Browser compatibility testing',
                'description': 'Test on Chrome, Firefox, Safari, Edge',
                'priority': 'high',
                'complexity': 3,
                'assigned_to': sam,
                'progress': 75,
            },
            {
                'title': 'Mobile responsiveness review',
                'description': 'Test all pages on mobile devices',
                'priority': 'high',
                'complexity': 4,
                'assigned_to': sam,
                'progress': 90,
            },
            {
                'title': 'Integration testing: Third-party APIs',
                'description': 'Verify all external API integrations',
                'priority': 'medium',
                'complexity': 6,
                'assigned_to': sam,
                'progress': 85,
            },
        ]

        for task_data in in_review_tasks:
            task = Task.objects.create(
                column=columns['In Progress'],
                title=task_data['title'],
                description=task_data['description'],
                priority=task_data['priority'],
                complexity_score=task_data['complexity'],
                assigned_to=task_data['assigned_to'],
                created_by=alex,
                progress=task_data['progress'],
                due_date=now + timedelta(days=random.randint(1, 5)),
                is_seed_demo_data=True,
            )
            tasks.append(task)

        # Done tasks (5)
        done_tasks = [
            {
                'title': 'Set up CI/CD pipeline',
                'description': 'GitHub Actions for automated testing and deployment',
                'priority': 'high',
                'complexity': 7,
                'assigned_to': sam,
                'progress': 100,
            },
            {
                'title': 'Configure production server',
                'description': 'Set up AWS infrastructure with load balancing',
                'priority': 'urgent',
                'complexity': 8,
                'assigned_to': alex,
                'progress': 100,
            },
            {
                'title': 'Implement error tracking with Sentry',
                'description': 'Capture and monitor application errors',
                'priority': 'high',
                'complexity': 4,
                'assigned_to': sam,
                'progress': 100,
            },
            {
                'title': 'Create project documentation',
                'description': 'Setup guide and architecture overview',
                'priority': 'medium',
                'complexity': 5,
                'assigned_to': jordan,
                'progress': 100,
            },
            {
                'title': 'Set up monitoring and alerts',
                'description': 'Configure Datadog for system monitoring',
                'priority': 'high',
                'complexity': 6,
                'assigned_to': sam,
                'progress': 100,
            },
        ]

        for task_data in done_tasks:
            task = Task.objects.create(
                column=columns['Done'],
                title=task_data['title'],
                description=task_data['description'],
                priority=task_data['priority'],
                complexity_score=task_data['complexity'],
                assigned_to=task_data['assigned_to'],
                created_by=alex,
                progress=task_data['progress'],
                due_date=now - timedelta(days=random.randint(1, 10)),
                is_seed_demo_data=True,
            )
            tasks.append(task)

        return tasks

    def create_marketing_tasks(self, board, alex, sam, jordan):
        """Create 40 tasks for Marketing Campaign board"""
        columns = {col.name: col for col in Column.objects.filter(board=board)}
        tasks = []
        now = timezone.now()

        # To Do tasks (12)
        ideas_tasks = [
            {
                'title': 'Launch product video campaign',
                'description': 'Create engaging product demo videos for social media',
                'priority': 'high',
                'complexity': 7,
                'assigned_to': jordan,
            },
            {
                'title': 'Blog post series on industry trends',
                'description': 'Weekly blog posts establishing thought leadership',
                'priority': 'medium',
                'complexity': 5,
                'assigned_to': jordan,
            },
            {
                'title': 'Email newsletter automation',
                'description': 'Set up automated email nurture campaigns',
                'priority': 'high',
                'complexity': 6,
                'assigned_to': sam,
            },
            {
                'title': 'Social media contest',
                'description': 'Run a giveaway to boost engagement',
                'priority': 'low',
                'complexity': 4,
                'assigned_to': jordan,
            },
            {
                'title': 'Partner with industry influencers',
                'description': 'Identify and reach out to relevant influencers',
                'priority': 'medium',
                'complexity': 6,
                'assigned_to': jordan,
            },
            {
                'title': 'Create case studies',
                'description': 'Document customer success stories',
                'priority': 'high',
                'complexity': 5,
                'assigned_to': jordan,
            },
            {
                'title': 'Webinar series planning',
                'description': 'Plan monthly educational webinars',
                'priority': 'medium',
                'complexity': 7,
                'assigned_to': alex,
            },
            {
                'title': 'Redesign landing pages',
                'description': 'Optimize conversion rates on key pages',
                'priority': 'high',
                'complexity': 6,
                'assigned_to': sam,
            },
            {
                'title': 'Launch referral program',
                'description': 'Incentivize customers to refer friends',
                'priority': 'medium',
                'complexity': 5,
                'assigned_to': alex,
            },
            {
                'title': 'Create product comparison guides',
                'description': 'Help prospects make informed decisions',
                'priority': 'low',
                'complexity': 4,
                'assigned_to': jordan,
            },
            {
                'title': 'SEO optimization initiative',
                'description': 'Improve organic search rankings',
                'priority': 'high',
                'complexity': 7,
                'assigned_to': sam,
            },
            {
                'title': 'Customer testimonial videos',
                'description': 'Film satisfied customers sharing their experience',
                'priority': 'medium',
                'complexity': 6,
                'assigned_to': jordan,
            },
        ]

        for task_data in ideas_tasks:
            task = Task.objects.create(
                column=columns['To Do'],
                title=task_data['title'],
                description=task_data['description'],
                priority=task_data['priority'],
                complexity_score=task_data['complexity'],
                assigned_to=task_data['assigned_to'],
                created_by=alex,
                progress=0,
                due_date=now + timedelta(days=random.randint(30, 60)),
                is_seed_demo_data=True,
            )
            tasks.append(task)

        # In Progress tasks (15)
        planning_tasks = [
            {
                'title': 'Q2 content calendar planning',
                'description': 'Plan all content for next quarter',
                'priority': 'high',
                'complexity': 6,
                'assigned_to': jordan,
                'progress': 35,
            },
            {
                'title': 'Competitor analysis update',
                'description': 'Analyze competitor marketing strategies',
                'priority': 'medium',
                'complexity': 5,
                'assigned_to': jordan,
                'progress': 50,
            },
            {
                'title': 'Target audience persona refresh',
                'description': 'Update buyer personas with new data',
                'priority': 'high',
                'complexity': 6,
                'assigned_to': jordan,
                'progress': 60,
            },
            {
                'title': 'Marketing budget allocation',
                'description': 'Plan budget across channels for Q2',
                'priority': 'urgent',
                'complexity': 5,
                'assigned_to': alex,
                'progress': 70,
            },
            {
                'title': 'Brand guidelines update',
                'description': 'Refresh visual and voice guidelines',
                'priority': 'medium',
                'complexity': 5,
                'assigned_to': jordan,
                'progress': 40,
            },
            {
                'title': 'Marketing automation workflow design',
                'description': 'Map out lead nurture workflows',
                'priority': 'high',
                'complexity': 7,
                'assigned_to': jordan,
                'progress': 45,
            },
            {
                'title': 'Trade show booth planning',
                'description': 'Design and logistics for industry conference',
                'priority': 'medium',
                'complexity': 6,
                'assigned_to': jordan,
                'progress': 30,
            },
            {
                'title': 'Partnership agreement drafting',
                'description': 'Legal agreements for co-marketing partners',
                'priority': 'high',
                'complexity': 4,
                'assigned_to': alex,
                'progress': 55,
            },
            {
                'title': 'Customer survey design',
                'description': 'Create survey to gather feedback',
                'priority': 'medium',
                'complexity': 4,
                'assigned_to': jordan,
                'progress': 65,
            },
            {
                'title': 'Press release strategy',
                'description': 'Plan announcements for product launch',
                'priority': 'high',
                'complexity': 5,
                'assigned_to': jordan,
                'progress': 50,
            },
            {
                'title': 'Video production storyboarding',
                'description': 'Create storyboards for explainer videos',
                'priority': 'medium',
                'complexity': 6,
                'assigned_to': jordan,
                'progress': 40,
            },
            {
                'title': 'Email campaign segmentation',
                'description': 'Define audience segments for targeting',
                'priority': 'high',
                'complexity': 5,
                'assigned_to': jordan,
                'progress': 60,
            },
            {
                'title': 'Social media ad creative planning',
                'description': 'Plan ad visuals and copy for campaigns',
                'priority': 'medium',
                'complexity': 5,
                'assigned_to': jordan,
                'progress': 35,
            },
            {
                'title': 'Influencer outreach list',
                'description': 'Compile list of influencers to contact',
                'priority': 'low',
                'complexity': 3,
                'assigned_to': jordan,
                'progress': 75,
            },
            {
                'title': 'Landing page wireframes',
                'description': 'Design wireframes for new landing pages',
                'priority': 'high',
                'complexity': 6,
                'assigned_to': jordan,
                'progress': 55,
            },
        ]

        for task_data in planning_tasks:
            task = Task.objects.create(
                column=columns['In Progress'],
                title=task_data['title'],
                description=task_data['description'],
                priority=task_data['priority'],
                complexity_score=task_data['complexity'],
                assigned_to=task_data['assigned_to'],
                created_by=alex,
                progress=task_data['progress'],
                due_date=now + timedelta(days=random.randint(10, 25)),
                is_seed_demo_data=True,
            )
            tasks.append(task)

        # In Progress tasks (8)
        in_progress_tasks = [
            {
                'title': 'Write product launch announcement',
                'description': 'Craft compelling announcement copy',
                'priority': 'urgent',
                'complexity': 5,
                'assigned_to': jordan,
                'progress': 60,
            },
            {
                'title': 'Design social media graphics',
                'description': 'Create visuals for upcoming campaign',
                'priority': 'high',
                'complexity': 5,
                'assigned_to': jordan,
                'progress': 45,
            },
            {
                'title': 'Film customer testimonial video',
                'description': 'Record interview with happy customer',
                'priority': 'high',
                'complexity': 6,
                'assigned_to': jordan,
                'progress': 70,
            },
            {
                'title': 'Set up Google Ads campaign',
                'description': 'Configure PPC ads for product launch',
                'priority': 'high',
                'complexity': 6,
                'assigned_to': jordan,
                'progress': 55,
            },
            {
                'title': 'Update website homepage',
                'description': 'Refresh homepage with new messaging',
                'priority': 'medium',
                'complexity': 5,
                'assigned_to': jordan,
                'progress': 40,
            },
            {
                'title': 'Create email nurture sequence',
                'description': 'Write 5-email onboarding series',
                'priority': 'high',
                'complexity': 6,
                'assigned_to': jordan,
                'progress': 50,
            },
            {
                'title': 'Optimize SEO meta tags',
                'description': 'Update meta descriptions for key pages',
                'priority': 'medium',
                'complexity': 4,
                'assigned_to': jordan,
                'progress': 65,
            },
            {
                'title': 'Build landing page for webinar',
                'description': 'Create registration page with form',
                'priority': 'high',
                'complexity': 5,
                'assigned_to': jordan,
                'progress': 75,
            },
        ]

        for task_data in in_progress_tasks:
            task = Task.objects.create(
                column=columns['In Progress'],
                title=task_data['title'],
                description=task_data['description'],
                priority=task_data['priority'],
                complexity_score=task_data['complexity'],
                assigned_to=task_data['assigned_to'],
                created_by=alex,
                progress=task_data['progress'],
                due_date=now + timedelta(days=random.randint(3, 10)),
                is_seed_demo_data=True,
            )
            tasks.append(task)

        # Published tasks (5)
        published_tasks = [
            {
                'title': 'Launch holiday promotion campaign',
                'description': 'Seasonal discount campaign across all channels',
                'priority': 'high',
                'complexity': 7,
                'assigned_to': jordan,
                'progress': 100,
            },
            {
                'title': 'Publish Q1 success metrics blog post',
                'description': 'Share quarterly results with community',
                'priority': 'medium',
                'complexity': 4,
                'assigned_to': jordan,
                'progress': 100,
            },
            {
                'title': 'Release customer case study video',
                'description': 'Published enterprise customer success story',
                'priority': 'high',
                'complexity': 6,
                'assigned_to': jordan,
                'progress': 100,
            },
            {
                'title': 'Launch LinkedIn thought leadership series',
                'description': 'Weekly posts from CEO on industry topics',
                'priority': 'medium',
                'complexity': 5,
                'assigned_to': jordan,
                'progress': 100,
            },
            {
                'title': 'Deploy new brand identity',
                'description': 'Rolled out refreshed logo and colors',
                'priority': 'high',
                'complexity': 8,
                'assigned_to': alex,
                'progress': 100,
            },
        ]

        for task_data in published_tasks:
            task = Task.objects.create(
                column=columns['Done'],
                title=task_data['title'],
                description=task_data['description'],
                priority=task_data['priority'],
                complexity_score=task_data['complexity'],
                assigned_to=task_data['assigned_to'],
                created_by=alex,
                progress=task_data['progress'],
                due_date=now - timedelta(days=random.randint(1, 15)),
                is_seed_demo_data=True,
            )
            tasks.append(task)

        return tasks

    def create_bug_tasks(self, board, alex, sam, jordan):
        """Create 30 tasks for Bug Tracking board"""
        columns = {col.name: col for col in Column.objects.filter(board=board)}
        tasks = []
        now = timezone.now()

        # To Do tasks (10)
        new_tasks = [
            {
                'title': 'Login button not working on mobile Safari',
                'description': 'Users report login button click not responding on iOS Safari browser',
                'priority': 'urgent',
                'complexity': 5,
                'assigned_to': alex,
            },
            {
                'title': 'Memory leak in dashboard view',
                'description': 'Dashboard page memory usage grows continuously',
                'priority': 'high',
                'complexity': 7,
                'assigned_to': sam,
            },
            {
                'title': 'Email notifications not sent for comments',
                'description': 'Users not receiving email when mentioned in comments',
                'priority': 'high',
                'complexity': 6,
                'assigned_to': jordan,
            },
            {
                'title': 'Date picker shows wrong timezone',
                'description': 'Date picker not respecting user timezone settings',
                'priority': 'medium',
                'complexity': 5,
                'assigned_to': alex,
            },
            {
                'title': 'Export to CSV includes deleted items',
                'description': 'CSV export showing soft-deleted records',
                'priority': 'low',
                'complexity': 3,
                'assigned_to': sam,
            },
            {
                'title': 'Search results missing recent items',
                'description': 'Items created in last hour not appearing in search',
                'priority': 'medium',
                'complexity': 6,
                'assigned_to': jordan,
            },
            {
                'title': 'Profile image upload fails for large files',
                'description': 'Files over 5MB fail silently without error message',
                'priority': 'medium',
                'complexity': 4,
                'assigned_to': alex,
            },
            {
                'title': 'Dark mode colors inconsistent',
                'description': 'Some UI elements not properly themed in dark mode',
                'priority': 'low',
                'complexity': 3,
                'assigned_to': sam,
            },
            {
                'title': 'API returns 500 error for invalid date format',
                'description': 'Should return 400 bad request instead',
                'priority': 'medium',
                'complexity': 2,
                'assigned_to': jordan,
            },
            {
                'title': 'Drag and drop broken in Firefox',
                'description': 'Cannot reorder items in Firefox browser',
                'priority': 'high',
                'complexity': 6,
                'assigned_to': alex,
            },
        ]

        for task_data in new_tasks:
            task = Task.objects.create(
                column=columns['To Do'],
                title=task_data['title'],
                description=task_data['description'],
                priority=task_data['priority'],
                complexity_score=task_data['complexity'],
                assigned_to=task_data['assigned_to'],
                created_by=alex,
                progress=0,
                due_date=now + timedelta(days=random.randint(1, 7)),
                is_seed_demo_data=True,
            )
            tasks.append(task)

        # In Progress tasks (12)
        investigating_tasks = [
            {
                'title': 'Intermittent 504 timeout errors',
                'description': 'Random Gateway Timeout errors under load',
                'priority': 'urgent',
                'complexity': 8,
                'assigned_to': sam,
                'progress': 30,
            },
            {
                'title': 'Database deadlock on task updates',
                'description': 'Concurrent task updates causing deadlocks',
                'priority': 'high',
                'complexity': 7,
                'assigned_to': sam,
                'progress': 45,
            },
            {
                'title': 'Charts not rendering in IE11',
                'description': 'JavaScript errors in Internet Explorer',
                'priority': 'low',
                'complexity': 5,
                'assigned_to': sam,
                'progress': 20,
            },
            {
                'title': 'Pagination broken on large datasets',
                'description': 'Next page button not working for >1000 items',
                'priority': 'medium',
                'complexity': 5,
                'assigned_to': sam,
                'progress': 50,
            },
            {
                'title': 'Mobile menu not closing after navigation',
                'description': 'Hamburger menu stays open after clicking link',
                'priority': 'medium',
                'complexity': 3,
                'assigned_to': sam,
                'progress': 60,
            },
            {
                'title': 'Notification badge count incorrect',
                'description': 'Badge shows wrong number of unread notifications',
                'priority': 'low',
                'complexity': 4,
                'assigned_to': sam,
                'progress': 35,
            },
            {
                'title': 'File download corrupted for PDFs',
                'description': 'Downloaded PDFs cannot be opened',
                'priority': 'high',
                'complexity': 6,
                'assigned_to': sam,
                'progress': 40,
            },
            {
                'title': 'Auto-save not working consistently',
                'description': 'Form data sometimes lost on navigation',
                'priority': 'high',
                'complexity': 7,
                'assigned_to': sam,
                'progress': 55,
            },
            {
                'title': 'Avatar images not loading over HTTPS',
                'description': 'Mixed content warning blocking avatar display',
                'priority': 'medium',
                'complexity': 3,
                'assigned_to': sam,
                'progress': 70,
            },
            {
                'title': 'Calendar events off by one day',
                'description': 'All-day events showing on wrong date',
                'priority': 'medium',
                'complexity': 5,
                'assigned_to': sam,
                'progress': 45,
            },
            {
                'title': 'Filter dropdown cut off in modal',
                'description': 'Dropdown menu clipped by modal boundaries',
                'priority': 'low',
                'complexity': 3,
                'assigned_to': sam,
                'progress': 65,
            },
            {
                'title': 'Real-time updates delayed',
                'description': 'WebSocket messages taking 30+ seconds',
                'priority': 'high',
                'complexity': 7,
                'assigned_to': sam,
                'progress': 40,
            },
        ]

        for task_data in investigating_tasks:
            task = Task.objects.create(
                column=columns['In Progress'],
                title=task_data['title'],
                description=task_data['description'],
                priority=task_data['priority'],
                complexity_score=task_data['complexity'],
                assigned_to=task_data['assigned_to'],
                created_by=alex,
                progress=task_data['progress'],
                due_date=now + timedelta(days=random.randint(3, 10)),
                is_seed_demo_data=True,
            )
            tasks.append(task)

        # In Progress tasks (5)
        in_progress_tasks = [
            {
                'title': 'Fix SQL injection vulnerability in search',
                'description': 'Sanitize user input in search queries',
                'priority': 'urgent',
                'complexity': 6,
                'assigned_to': sam,
                'progress': 75,
            },
            {
                'title': 'Resolve XSS vulnerability in comments',
                'description': 'Properly escape HTML in user-generated content',
                'priority': 'urgent',
                'complexity': 5,
                'assigned_to': sam,
                'progress': 85,
            },
            {
                'title': 'Fix broken image links after migration',
                'description': 'Update image paths to new CDN',
                'priority': 'high',
                'complexity': 4,
                'assigned_to': sam,
                'progress': 60,
            },
            {
                'title': 'Correct timezone conversion in reports',
                'description': 'Reports showing UTC instead of user timezone',
                'priority': 'medium',
                'complexity': 5,
                'assigned_to': sam,
                'progress': 70,
            },
            {
                'title': 'Optimize slow dashboard query',
                'description': 'Add indexes and refactor query logic',
                'priority': 'high',
                'complexity': 7,
                'assigned_to': sam,
                'progress': 55,
            },
        ]

        for task_data in in_progress_tasks:
            task = Task.objects.create(
                column=columns['In Progress'],
                title=task_data['title'],
                description=task_data['description'],
                priority=task_data['priority'],
                complexity_score=task_data['complexity'],
                assigned_to=task_data['assigned_to'],
                created_by=alex,
                progress=task_data['progress'],
                due_date=now + timedelta(days=random.randint(1, 5)),
                is_seed_demo_data=True,
            )
            tasks.append(task)

        # Closed tasks (3)
        closed_tasks = [
            {
                'title': 'Fixed password reset email not delivered',
                'description': 'Updated email provider settings',
                'priority': 'urgent',
                'complexity': 4,
                'assigned_to': sam,
                'progress': 100,
            },
            {
                'title': 'Resolved dashboard loading forever',
                'description': 'Fixed infinite loop in data fetching',
                'priority': 'urgent',
                'complexity': 6,
                'assigned_to': sam,
                'progress': 100,
            },
            {
                'title': 'Corrected calculation error in reports',
                'description': 'Fixed rounding logic in percentage calculations',
                'priority': 'high',
                'complexity': 3,
                'assigned_to': sam,
                'progress': 100,
            },
        ]

        for task_data in closed_tasks:
            task = Task.objects.create(
                column=columns['Done'],
                title=task_data['title'],
                description=task_data['description'],
                priority=task_data['priority'],
                complexity_score=task_data['complexity'],
                assigned_to=task_data['assigned_to'],
                created_by=alex,
                progress=task_data['progress'],
                due_date=now - timedelta(days=random.randint(1, 10)),
                is_seed_demo_data=True,
            )
            tasks.append(task)

        return tasks

    def create_dependencies(self, software_tasks, marketing_tasks, bug_tasks):
        """Create logical task dependencies"""
        # Software Development dependencies
        if len(software_tasks) >= 5:
            # Auth system must be complete before API endpoints
            software_tasks[0].dependencies.add(software_tasks[4])  # API depends on Auth
            software_tasks[2].dependencies.add(software_tasks[0])  # User API depends on Auth
            self.stdout.write('   ✅ Created 2 dependencies in Software Development')

        # Marketing dependencies
        if len(marketing_tasks) >= 5:
            # Can't film testimonial until customer agrees (planning before execution)
            marketing_tasks[20].dependencies.add(marketing_tasks[15])  # Video depends on planning
            marketing_tasks[21].dependencies.add(marketing_tasks[10])  # Landing page depends on wireframes
            self.stdout.write('   ✅ Created 2 dependencies in Marketing Campaign')

        # Bug dependencies
        if len(bug_tasks) >= 3:
            # Must investigate before fixing
            bug_tasks[20].dependencies.add(bug_tasks[10])  # Fix depends on investigation
            self.stdout.write('   ✅ Created 1 dependency in Bug Tracking')

    def create_lean_labels(self, *boards):
        """Create Lean Six Sigma labels for demo boards"""
        lean_labels = [
            {'name': 'Value-Added', 'color': '#28a745', 'category': 'lean'},  # Green
            {'name': 'Necessary NVA', 'color': '#ffc107', 'category': 'lean'},  # Yellow
            {'name': 'Waste/Eliminate', 'color': '#dc3545', 'category': 'lean'}  # Red
        ]
        
        labels_created = 0
        for board in boards:
            for label_data in lean_labels:
                # Check if label already exists
                if not TaskLabel.objects.filter(
                    name=label_data['name'],
                    board=board,
                    category='lean'
                ).exists():
                    TaskLabel.objects.create(
                        name=label_data['name'],
                        color=label_data['color'],
                        category='lean',
                        board=board
                    )
                    labels_created += 1
        
        self.stdout.write(f'   ✅ Created {labels_created} Lean Six Sigma labels')

    def assign_lean_labels(self, software_tasks, marketing_tasks, bug_tasks):
        """Assign Lean Six Sigma labels to tasks based on their characteristics"""
        all_tasks = software_tasks + marketing_tasks + bug_tasks
        
        # Get labels from the first task's board (they should all exist now)
        if not all_tasks:
            return
        
        sample_board = all_tasks[0].column.board
        value_added_label = TaskLabel.objects.filter(
            name='Value-Added',
            board=sample_board,
            category='lean'
        ).first()
        
        necessary_nva_label = TaskLabel.objects.filter(
            name='Necessary NVA',
            board=sample_board,
            category='lean'
        ).first()
        
        waste_label = TaskLabel.objects.filter(
            name='Waste/Eliminate',
            board=sample_board,
            category='lean'
        ).first()
        
        # Categorize tasks intelligently based on keywords and priority
        value_added_count = 0
        necessary_count = 0
        waste_count = 0
        
        for task in all_tasks:
            # Value-Added: Core features, user-facing functionality, high-priority items
            value_keywords = ['implement', 'build', 'create', 'develop', 'design', 'api', 'authentication', 
                            'feature', 'landing page', 'campaign', 'video', 'content']
            
            # Necessary NVA: Testing, documentation, reviews, planning, meetings
            necessary_keywords = ['test', 'review', 'document', 'plan', 'meeting', 'research', 
                                'analyze', 'investigate', 'fix bug', 'setup', 'configure']
            
            # Waste: Rework, redundant work, low priority items
            waste_keywords = ['rework', 'redo', 'duplicate', 'unnecessary', 'redundant', 
                            'refactor old', 'update deprecated']
            
            title_lower = task.title.lower()
            desc_lower = (task.description or '').lower()
            
            # Get labels for this task's board
            board = task.column.board
            board_value_label = TaskLabel.objects.filter(
                name='Value-Added', board=board, category='lean'
            ).first()
            board_necessary_label = TaskLabel.objects.filter(
                name='Necessary NVA', board=board, category='lean'
            ).first()
            board_waste_label = TaskLabel.objects.filter(
                name='Waste/Eliminate', board=board, category='lean'
            ).first()
            
            # Categorize based on keywords (check waste first, then necessary, then value-added as default)
            if any(keyword in title_lower or keyword in desc_lower for keyword in waste_keywords):
                if board_waste_label:
                    task.labels.add(board_waste_label)
                    waste_count += 1
            elif any(keyword in title_lower or keyword in desc_lower for keyword in necessary_keywords):
                if board_necessary_label:
                    task.labels.add(board_necessary_label)
                    necessary_count += 1
            elif any(keyword in title_lower or keyword in desc_lower for keyword in value_keywords):
                if board_value_label:
                    task.labels.add(board_value_label)
                    value_added_count += 1
            else:
                # Default: High/Urgent priority = Value-Added, Low = Necessary NVA
                if task.priority in ['high', 'urgent']:
                    if board_value_label:
                        task.labels.add(board_value_label)
                        value_added_count += 1
                else:
                    if board_necessary_label:
                        task.labels.add(board_necessary_label)
                        necessary_count += 1
        
        self.stdout.write(f'   ✅ Assigned labels to {len(all_tasks)} tasks:')
        self.stdout.write(f'      • Value-Added: {value_added_count}')
        self.stdout.write(f'      • Necessary NVA: {necessary_count}')
        self.stdout.write(f'      • Waste/Eliminate: {waste_count}')

    def enhance_tasks_with_demo_data(self, tasks, skill_pool, task_type):
        """
        Enhance tasks with comprehensive demo data including:
        - start_date (always before due_date)
        - required_skills
        - skill_match_score
        - collaboration_required
        - workload_impact
        - risk_likelihood, risk_impact, risk_score, risk_level
        - risk_indicators
        - mitigation_suggestions
        """
        now = timezone.now()
        enhanced_count = 0

        for task in tasks:
            # Calculate start_date based on due_date and complexity
            # CRITICAL: Ensure start_date is ALWAYS before due_date
            if task.due_date:
                # Duration in days based on complexity (complexity * 2-3 days)
                duration_days = task.complexity_score * random.randint(2, 3)
                
                # Get due_date as date object
                due_date = task.due_date.date() if hasattr(task.due_date, 'date') else task.due_date
                
                # Calculate start_date (must be before due_date)
                task.start_date = due_date - timedelta(days=duration_days)
                
                # For completed tasks, ensure dates make sense historically
                if task.progress == 100:
                    # Task is complete, so start_date should be in the past
                    # and completed_at should be set
                    if not task.completed_at:
                        # Set completed_at to a day or two before due_date
                        days_before_due = random.randint(1, 3)
                        task.completed_at = task.due_date - timedelta(days=days_before_due)
                    # Calculate actual duration
                    if task.start_date:
                        actual_days = (task.completed_at.date() - task.start_date).days
                        task.actual_duration_days = max(0.5, actual_days)
                else:
                    # For incomplete tasks, start_date should be recent if task has started
                    if task.progress > 0:
                        # Task has started - start_date should be in the recent past
                        max_days_ago = min(duration_days, 14)  # Started within last 2 weeks
                        task.start_date = (now - timedelta(days=random.randint(3, max_days_ago))).date()
                    else:
                        # Task hasn't started yet - start_date should be today or in future
                        if task.start_date < now.date():
                            task.start_date = now.date()
                
                # FINAL CHECK: Ensure start_date is always before due_date
                if task.start_date >= due_date:
                    task.start_date = due_date - timedelta(days=max(1, duration_days))

            # Add required skills (1-3 skills based on complexity)
            min_skills = 1 if task.complexity_score < 5 else 2
            max_skills = 2 if task.complexity_score < 7 else 3
            task.required_skills = self.get_random_skills(skill_pool, min_skills, max_skills)

            # Add skill match score for assigned tasks
            task.skill_match_score = self.get_skill_match_score(
                task.assigned_to is not None,
                task.complexity_score
            )

            # Add collaboration required flag
            task.collaboration_required = self.should_require_collaboration(
                task.complexity_score,
                task.priority
            )

            # Add workload impact
            task.workload_impact = self.get_workload_impact(
                task.complexity_score,
                task.priority
            )

            # Calculate and add risk data
            risk_data = self.calculate_risk_data(
                task.complexity_score,
                task.priority,
                task.progress
            )
            task.risk_likelihood = risk_data['likelihood']
            task.risk_impact = risk_data['impact']
            task.risk_score = risk_data['score']
            task.risk_level = risk_data['level']
            task.risk_indicators = risk_data['indicators']
            task.mitigation_suggestions = [
                {
                    'strategy': strategy,
                    'priority': random.choice(['high', 'medium', 'low']),
                    'estimated_effort': random.choice(['1 day', '2-3 days', '1 week'])
                }
                for strategy in risk_data['strategies']
            ]

            # Add risk analysis details
            task.risk_analysis = {
                'factors': self._get_risk_factors(task, task_type),
                'assessment': self._get_risk_assessment(risk_data['level'], task.title),
                'last_updated': now.isoformat(),
                'analyzed_by': 'AI Risk Engine'
            }
            task.last_risk_assessment = now

            task.save()
            
            # CRITICAL: Fix created_at to be before start_date
            # created_at has auto_now_add=True, so we must use update() to bypass it
            if task.start_date:
                # created_at should be 1-7 days before start_date (when task was planned)
                days_before_start = random.randint(1, 7)
                # Convert start_date to datetime if needed
                if hasattr(task.start_date, 'date'):
                    created_date = task.start_date - timedelta(days=days_before_start)
                else:
                    created_date = timezone.make_aware(
                        timezone.datetime.combine(task.start_date, timezone.datetime.min.time())
                    ) - timedelta(days=days_before_start)
                
                # Update created_at using update() to bypass auto_now_add
                Task.objects.filter(pk=task.pk).update(created_at=created_date)
            
            enhanced_count += 1

        self.stdout.write(f'   ✅ Enhanced {enhanced_count} {task_type.replace("_", " ")} tasks')

    def _get_risk_factors(self, task, task_type):
        """Get relevant risk factors based on task type"""
        common_factors = ['Timeline pressure', 'Resource availability', 'Dependencies']
        
        type_specific_factors = {
            'software': ['Technical complexity', 'Integration risks', 'Code quality'],
            'marketing': ['Market conditions', 'Brand consistency', 'Stakeholder alignment'],
            'bug_tracking': ['Root cause identification', 'Regression risk', 'User impact']
        }
        
        factors = common_factors + type_specific_factors.get(task_type, [])
        return random.sample(factors, min(4, len(factors)))

    def _get_risk_assessment(self, risk_level, task_title):
        """Generate a human-readable risk assessment"""
        assessments = {
            'low': f'Task "{task_title[:30]}..." has minimal risk factors and is on track.',
            'medium': f'Task "{task_title[:30]}..." has moderate risk. Regular monitoring recommended.',
            'high': f'Task "{task_title[:30]}..." requires close attention due to elevated risk factors.',
            'critical': f'Task "{task_title[:30]}..." has critical risk level. Immediate action may be required.'
        }
        return assessments.get(risk_level, 'Risk assessment pending.')

    def create_related_tasks(self, tasks):
        """Create related task relationships within a board"""
        if len(tasks) < 3:
            return

        related_count = 0
        
        # Create logical relationships based on task content
        for i, task in enumerate(tasks):
            # Each task gets 1-3 related tasks
            num_related = random.randint(1, 3)
            
            # Get potential related tasks (exclude self)
            potential_related = [t for t in tasks if t.id != task.id]
            
            if potential_related:
                # Select random related tasks
                related_tasks = random.sample(
                    potential_related,
                    min(num_related, len(potential_related))
                )
                
                for related in related_tasks:
                    # Only add if not already related
                    if not task.related_tasks.filter(id=related.id).exists():
                        task.related_tasks.add(related)
                        related_count += 1

        self.stdout.write(f'   ✅ Created {related_count} related task connections')

    def create_time_tracking_data(self, all_tasks, alex, sam, jordan):
        """Create realistic time tracking entries for all demo users"""
        
        # Get demo_admin_solo user for additional entries
        demo_admin = User.objects.filter(username='demo_admin_solo').first()
        
        # All users who can log time
        time_loggers = [u for u in [alex, sam, jordan, demo_admin] if u is not None]
        
        if not time_loggers:
            self.stdout.write(self.style.WARNING('   ⚠️ No users found for time tracking data'))
            return
        
        # Sample descriptions for time entries
        work_descriptions = [
            'Implemented core functionality',
            'Code review and testing',
            'Fixed bugs and edge cases',
            'Updated documentation',
            'Refactored for better performance',
            'Integration testing with external APIs',
            'UI/UX improvements and polish',
            'Database query optimization',
            'Security enhancements and audit',
            'REST API development',
            'Unit test creation and coverage',
            'Performance tuning and profiling',
            'Debugging production issues',
            'Requirements analysis and planning',
            'Design mockups and prototyping',
            'Client meeting and feedback session',
            'Code deployment and release',
            'Pair programming session',
            'Research and spike work',
            'Technical documentation update',
            'Sprint planning and estimation',
            'Backlog grooming session',
        ]
        
        today = timezone.now().date()
        time_entries_created = 0
        
        # Create time entries for tasks that have progress > 0
        tasks_with_progress = [t for t in all_tasks if t.progress > 0]
        
        for task in tasks_with_progress:
            # Get the assigned user or a random user
            if task.assigned_to and task.assigned_to in time_loggers:
                primary_user = task.assigned_to
            else:
                primary_user = random.choice(time_loggers)
            
            # Number of time entries based on progress
            if task.progress >= 80:
                num_entries = random.randint(3, 6)
            elif task.progress >= 50:
                num_entries = random.randint(2, 4)
            else:
                num_entries = random.randint(1, 3)
            
            for i in range(num_entries):
                # Random date within last 30 days (weighted towards recent)
                if random.random() < 0.5:
                    days_ago = random.randint(0, 7)  # 50% in last week
                else:
                    days_ago = random.randint(8, 30)  # 50% in last 3 weeks
                
                work_date = today - timedelta(days=days_ago)
                
                # Random hours between 0.5 and 6 hours
                hours_values = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]
                hours_spent = Decimal(str(random.choice(hours_values)))
                
                description = random.choice(work_descriptions)
                
                # Use primary user for most entries, occasionally use other users
                if random.random() < 0.8:
                    entry_user = primary_user
                else:
                    entry_user = random.choice(time_loggers)
                
                # Check if entry already exists for this exact task/date/user
                if not TimeEntry.objects.filter(
                    task=task, 
                    user=entry_user, 
                    work_date=work_date
                ).exists():
                    TimeEntry.objects.create(
                        task=task,
                        user=entry_user,
                        hours_spent=hours_spent,
                        work_date=work_date,
                        description=description
                    )
                    time_entries_created += 1
        
        self.stdout.write(f'   ✅ Created {time_entries_created} time entries across {len(tasks_with_progress)} tasks')
        
        # Calculate and display totals
        from django.db.models import Sum
        total_hours = TimeEntry.objects.filter(
            task__is_seed_demo_data=True
        ).aggregate(total=Sum('hours_spent'))['total'] or Decimal('0.00')
        
        self.stdout.write(f'   📊 Total logged hours across all users: {total_hours}h')

    def create_milestones(self, software_board, marketing_board, bug_board, alex, sam, jordan):
        """Create milestones for each demo board"""
        now = timezone.now()
        
        # Software Development Milestones
        software_tasks = list(Task.objects.filter(column__board=software_board))
        software_milestones = [
            {
                'title': 'Project Kickoff',
                'description': 'Official start of the Software Development project',
                'target_date': (now - timedelta(days=45)).date(),
                'milestone_type': 'project_start',
                'is_completed': True,
                'completed_date': (now - timedelta(days=45)).date(),
                'color': '#28a745',
                'created_by': alex,
            },
            {
                'title': 'Authentication Module Complete',
                'description': 'User authentication with JWT tokens and 2FA implemented',
                'target_date': (now - timedelta(days=20)).date(),
                'milestone_type': 'phase_completion',
                'is_completed': True,
                'completed_date': (now - timedelta(days=18)).date(),
                'color': '#28a745',
                'created_by': sam,
            },
            {
                'title': 'API MVP Ready',
                'description': 'Core REST API endpoints ready for testing',
                'target_date': (now + timedelta(days=7)).date(),
                'milestone_type': 'deliverable',
                'is_completed': False,
                'completed_date': None,
                'color': '#ffc107',
                'created_by': sam,
            },
            {
                'title': 'Beta Release',
                'description': 'First beta release to selected users',
                'target_date': (now + timedelta(days=30)).date(),
                'milestone_type': 'deliverable',
                'is_completed': False,
                'completed_date': None,
                'color': '#fd7e14',
                'created_by': alex,
            },
            {
                'title': 'Production Launch',
                'description': 'Final deployment to production',
                'target_date': (now + timedelta(days=60)).date(),
                'milestone_type': 'project_end',
                'is_completed': False,
                'completed_date': None,
                'color': '#dc3545',
                'created_by': alex,
            },
        ]
        
        for m_data in software_milestones:
            milestone, created = Milestone.objects.get_or_create(
                board=software_board,
                title=m_data['title'],
                defaults=m_data
            )
            if created and software_tasks:
                milestone.related_tasks.set(random.sample(software_tasks, min(3, len(software_tasks))))
        
        self.stdout.write(f'   ✅ Created {len(software_milestones)} milestones for Software Development')
        
        # Marketing Campaign Milestones
        marketing_tasks = list(Task.objects.filter(column__board=marketing_board))
        marketing_milestones = [
            {
                'title': 'Campaign Planning Complete',
                'description': 'All campaign strategies and content calendar finalized',
                'target_date': (now - timedelta(days=30)).date(),
                'milestone_type': 'phase_completion',
                'is_completed': True,
                'completed_date': (now - timedelta(days=28)).date(),
                'color': '#28a745',
                'created_by': jordan,
            },
            {
                'title': 'Content Creation Phase',
                'description': 'All marketing content created and reviewed',
                'target_date': (now + timedelta(days=14)).date(),
                'milestone_type': 'deliverable',
                'is_completed': False,
                'completed_date': None,
                'color': '#17a2b8',
                'created_by': jordan,
            },
            {
                'title': 'Campaign Launch',
                'description': 'Official marketing campaign launch across all channels',
                'target_date': (now + timedelta(days=21)).date(),
                'milestone_type': 'project_end',
                'is_completed': False,
                'completed_date': None,
                'color': '#fd7e14',
                'created_by': alex,
            },
        ]
        
        for m_data in marketing_milestones:
            milestone, created = Milestone.objects.get_or_create(
                board=marketing_board,
                title=m_data['title'],
                defaults=m_data
            )
            if created and marketing_tasks:
                milestone.related_tasks.set(random.sample(marketing_tasks, min(3, len(marketing_tasks))))
        
        self.stdout.write(f'   ✅ Created {len(marketing_milestones)} milestones for Marketing Campaign')
        
        # Bug Tracking Milestones
        bug_tasks = list(Task.objects.filter(column__board=bug_board))
        bug_milestones = [
            {
                'title': 'Critical Bugs Fixed',
                'description': 'All critical/urgent bugs resolved',
                'target_date': (now + timedelta(days=5)).date(),
                'milestone_type': 'deliverable',
                'is_completed': False,
                'completed_date': None,
                'color': '#dc3545',
                'created_by': sam,
            },
            {
                'title': 'Security Audit Complete',
                'description': 'All security vulnerabilities addressed',
                'target_date': (now + timedelta(days=10)).date(),
                'milestone_type': 'review',
                'is_completed': False,
                'completed_date': None,
                'color': '#6f42c1',
                'created_by': alex,
            },
            {
                'title': 'Bug-Free Release',
                'description': 'Zero known bugs release candidate',
                'target_date': (now + timedelta(days=20)).date(),
                'milestone_type': 'project_end',
                'is_completed': False,
                'completed_date': None,
                'color': '#28a745',
                'created_by': alex,
            },
        ]
        
        for m_data in bug_milestones:
            milestone, created = Milestone.objects.get_or_create(
                board=bug_board,
                title=m_data['title'],
                defaults=m_data
            )
            if created and bug_tasks:
                milestone.related_tasks.set(random.sample(bug_tasks, min(3, len(bug_tasks))))
        
        self.stdout.write(f'   ✅ Created {len(bug_milestones)} milestones for Bug Tracking')

    def create_budget_roi_data(self, software_board, marketing_board, bug_board, admin_user):
        """Create budget and ROI data for all demo boards"""
        
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
            tasks = Task.objects.filter(column__board=board)[:20]
            task_costs_created = 0
            
            for i, task in enumerate(tasks):
                estimated_cost = Decimal(random.uniform(500, 5000)).quantize(Decimal('0.01'))
                estimated_hours = Decimal(random.uniform(4, 40)).quantize(Decimal('0.01'))
                
                # Some tasks over budget for realistic demo
                is_over = i % 5 == 0
                variance = Decimal(random.uniform(1.1, 1.3)) if is_over else Decimal(random.uniform(0.7, 1.0))
                actual_cost = (estimated_cost * variance).quantize(Decimal('0.01'))
                
                task_cost, created = TaskCost.objects.get_or_create(
                    task=task,
                    defaults={
                        'estimated_cost': estimated_cost,
                        'estimated_hours': estimated_hours,
                        'actual_cost': actual_cost,
                        'hourly_rate': Decimal(random.choice(['75.00', '100.00', '125.00'])),
                        'resource_cost': Decimal(random.uniform(0, 200)).quantize(Decimal('0.01')) if i % 4 == 0 else Decimal('0.00'),
                    }
                )
                if created:
                    task_costs_created += 1
            
            self.stdout.write(f'   ✅ Created {task_costs_created} task costs for {config["name"]}')
            
            # Create ROI snapshot
            completed_tasks = Task.objects.filter(column__board=board, progress=100).count()
            total_tasks = Task.objects.filter(column__board=board).count()
            
            total_cost = sum([tc.get_total_actual_cost() for tc in TaskCost.objects.filter(task__column__board=board)])
            if not total_cost:
                total_cost = config['budget'] * Decimal('0.5')
            expected_value = config['budget'] * Decimal('1.6')
            realized_value = (expected_value * Decimal(random.uniform(0.85, 1.15))).quantize(Decimal('0.01'))
            
            roi_percentage = None
            if total_cost > 0:
                roi_percentage = ((realized_value - total_cost) / total_cost * 100).quantize(Decimal('0.01'))
            
            roi, created = ProjectROI.objects.get_or_create(
                board=board,
                snapshot_date__date=timezone.now().date(),
                defaults={
                    'expected_value': expected_value,
                    'realized_value': realized_value,
                    'roi_percentage': roi_percentage or Decimal('0'),
                    'total_cost': total_cost,
                    'total_tasks': total_tasks,
                    'completed_tasks': completed_tasks,
                    'ai_insights': {'note': f'Automated ROI tracking for {config["name"]}'},
                }
            )
            if created:
                self.stdout.write(f'   ✅ Created ROI snapshot for {config["name"]}: {roi_percentage}%')

    def create_burndown_data(self, software_board, marketing_board, bug_board):
        """Create velocity and burndown data for all demo boards"""
        now = timezone.now()
        
        boards = [
            {'board': software_board, 'name': 'Software Development', 'base_velocity': 45},
            {'board': marketing_board, 'name': 'Marketing Campaign', 'base_velocity': 35},
            {'board': bug_board, 'name': 'Bug Tracking', 'base_velocity': 40},
        ]
        
        for config in boards:
            board = config['board']
            
            # Create weekly velocity snapshots for last 8 weeks
            snapshots_created = 0
            for week in range(8, 0, -1):
                period_end = now.date() - timedelta(days=week * 7)
                period_start = period_end - timedelta(days=7)
                
                # Vary velocity realistically
                velocity_variation = random.uniform(0.8, 1.2)
                tasks_completed = int(config['base_velocity'] * velocity_variation / 5)
                story_points = Decimal(config['base_velocity'] * velocity_variation).quantize(Decimal('0.01'))
                hours = Decimal(tasks_completed * random.uniform(3, 6)).quantize(Decimal('0.01'))
                
                snapshot, created = TeamVelocitySnapshot.objects.get_or_create(
                    board=board,
                    period_start=period_start,
                    period_end=period_end,
                    defaults={
                        'period_type': 'weekly',
                        'tasks_completed': tasks_completed,
                        'story_points_completed': story_points,
                        'hours_completed': hours,
                        'active_team_members': 3,
                        'tasks_reopened': 0,
                        'quality_score': Decimal('95.00'),
                    }
                )
                if created:
                    snapshots_created += 1
            
            self.stdout.write(f'   ✅ Created {snapshots_created} velocity snapshots for {config["name"]}')
            
            # Create burndown prediction
            total_tasks = Task.objects.filter(column__board=board).count()
            completed_tasks = Task.objects.filter(column__board=board, progress=100).count()
            total_remaining = total_tasks - completed_tasks
            avg_velocity = Decimal(config['base_velocity'] / 7).quantize(Decimal('0.01'))  # Daily velocity
            
            if avg_velocity > 0:
                days_to_complete = int(total_remaining / float(avg_velocity))
                predicted_date = now + timedelta(days=days_to_complete)
                lower_bound = (predicted_date - timedelta(days=int(days_to_complete * 0.2))).date()
                upper_bound = (predicted_date + timedelta(days=int(days_to_complete * 0.3))).date()
                
                # Use objects.create since prediction_date is auto_now_add
                prediction = BurndownPrediction.objects.create(
                    board=board,
                    prediction_type='burndown',
                    total_tasks=total_tasks,
                    completed_tasks=completed_tasks,
                    remaining_tasks=total_remaining,
                    current_velocity=avg_velocity,
                    average_velocity=avg_velocity,
                    velocity_std_dev=Decimal('2.5'),
                    velocity_trend='stable',
                    predicted_completion_date=predicted_date.date(),
                    completion_date_lower_bound=lower_bound,
                    completion_date_upper_bound=upper_bound,
                    days_until_completion_estimate=days_to_complete,
                    days_margin_of_error=int(days_to_complete * 0.25),
                    confidence_percentage=85,
                    prediction_confidence_score=Decimal('0.85'),
                )
                if created:
                    self.stdout.write(f'   ✅ Created burndown prediction for {config["name"]}')

    def create_retrospective_data(self, software_board, marketing_board, bug_board, alex, sam, jordan):
        """Create retrospective data for all demo boards"""
        now = timezone.now()
        
        boards_data = [
            {'board': software_board, 'name': 'Software Development', 'lead': sam},
            {'board': marketing_board, 'name': 'Marketing Campaign', 'lead': jordan},
            {'board': bug_board, 'name': 'Bug Tracking', 'lead': sam},
        ]
        
        for config in boards_data:
            board = config['board']
            
            # Create 2 retrospectives per board
            for i in range(2):
                days_ago = 30 * (i + 1)
                
                retro, created = ProjectRetrospective.objects.get_or_create(
                    board=board,
                    title=f'Sprint {3-i} Retrospective - {config["name"]}',
                    defaults={
                        'retrospective_type': 'sprint',
                        'status': 'finalized' if i == 1 else 'in_progress',
                        'period_start': (now - timedelta(days=days_ago + 14)).date(),
                        'period_end': (now - timedelta(days=days_ago)).date(),
                        'metrics_snapshot': {
                            'tasks_completed': random.randint(15, 25),
                            'tasks_planned': random.randint(18, 28),
                            'velocity': random.randint(35, 50),
                            'completion_rate': random.randint(75, 95),
                        },
                        'what_went_well': 'Team collaboration was excellent. Daily standups kept everyone aligned. Code reviews were thorough and helpful.',
                        'what_needs_improvement': 'Some tasks had unclear requirements. Testing environment had stability issues.',
                        'lessons_learned': [
                            {'lesson': 'Early testing catches issues faster', 'priority': 'high'},
                            {'lesson': 'Clear requirements reduce rework', 'priority': 'high'},
                        ],
                        'key_achievements': [
                            'All sprint goals met',
                            'Zero critical bugs in production',
                            'Improved code coverage',
                        ],
                        'overall_sentiment_score': Decimal(random.uniform(0.7, 0.9)).quantize(Decimal('0.01')),
                        'team_morale_indicator': random.choice(['high', 'medium']),
                        'performance_trend': 'improving',
                        'created_by': config['lead'],
                        'finalized_by': alex if i == 1 else None,
                        'finalized_at': now - timedelta(days=days_ago) if i == 1 else None,
                    }
                )
                
                if created:
                    # Add lessons learned
                    LessonLearned.objects.create(
                        retrospective=retro,
                        board=board,
                        title='Early Testing Prevents Issues',
                        description='Running tests early in development catches bugs before they become blockers.',
                        category='quality',
                        priority='high',
                        status='implemented' if i == 1 else 'in_progress',
                        expected_benefit='Reduce debugging time by 40%',
                        recommended_action='Implement test-driven development practices and code review before merging',
                        action_owner=config['lead'],
                    )
                    
                    # Add action items
                    RetrospectiveActionItem.objects.create(
                        retrospective=retro,
                        board=board,
                        title='Implement test automation',
                        description='Set up automated testing pipeline for all new features',
                        action_type='technical_improvement',
                        priority='high',
                        status='completed' if i == 1 else 'in_progress',
                        assigned_to=config['lead'],
                        target_completion_date=(now + timedelta(days=14)).date(),
                    )
                    
                    # Add improvement metrics
                    ImprovementMetric.objects.create(
                        retrospective=retro,
                        board=board,
                        metric_type='velocity',
                        metric_name='Team Velocity',
                        metric_value=Decimal(random.randint(40, 50)),
                        previous_value=Decimal(random.randint(35, 45)),
                        target_value=Decimal('55'),
                        trend='improving',
                        unit_of_measure='story points',
                        measured_at=(now - timedelta(days=days_ago)).date(),
                    )
            
            self.stdout.write(f'   ✅ Created 2 retrospectives for {config["name"]}')

    def create_coaching_data(self, software_board, marketing_board, bug_board):
        """Create AI coaching suggestions and PM metrics for all demo boards"""
        now = timezone.now()
        
        boards = [
            {'board': software_board, 'name': 'Software Development'},
            {'board': marketing_board, 'name': 'Marketing Campaign'},
            {'board': bug_board, 'name': 'Bug Tracking'},
        ]
        
        suggestion_templates = [
            {
                'suggestion_type': 'resource_overload',
                'title': 'Workload Imbalance Detected',
                'message': 'Some team members have significantly more tasks. Consider redistributing work for better balance.',
                'severity': 'high',
            },
            {
                'suggestion_type': 'deadline_risk',
                'title': 'Upcoming Deadline Risk',
                'message': 'Several high-priority tasks are approaching their due dates. Consider prioritizing or adjusting scope.',
                'severity': 'high',
            },
            {
                'suggestion_type': 'best_practice',
                'title': 'Velocity Improvement Opportunity',
                'message': 'Breaking down complex tasks into smaller units could improve team velocity by 15-20%.',
                'severity': 'medium',
            },
            {
                'suggestion_type': 'quality_issue',
                'title': 'Quality Enhancement Suggestion',
                'message': 'Adding code review checkpoints for complex tasks can reduce bugs by up to 30%.',
                'severity': 'medium',
            },
            {
                'suggestion_type': 'skill_opportunity',
                'title': 'Collaboration Opportunity',
                'message': 'Tasks with overlapping skills could benefit from pair programming or knowledge sharing sessions.',
                'severity': 'low',
            },
        ]
        
        for config in boards:
            board = config['board']
            suggestions_created = 0
            
            for template in suggestion_templates:
                suggestion, created = CoachingSuggestion.objects.get_or_create(
                    board=board,
                    title=template['title'],
                    defaults={
                        'suggestion_type': template['suggestion_type'],
                        'message': template['message'],
                        'severity': template['severity'],
                        'status': 'active',
                        'confidence_score': Decimal(random.uniform(0.75, 0.95)).quantize(Decimal('0.01')),
                        'metrics_snapshot': {
                            'analysis_date': now.isoformat(),
                            'tasks_analyzed': Task.objects.filter(column__board=board).count(),
                        },
                    }
                )
                if created:
                    suggestions_created += 1
            
            self.stdout.write(f'   ✅ Created {suggestions_created} coaching suggestions for {config["name"]}')
            
            # Get a demo user for PM metrics
            from django.contrib.auth import get_user_model
            User = get_user_model()
            demo_pm = User.objects.filter(email='alex.chen@demo.prizmai.local').first()
            if not demo_pm:
                demo_pm = User.objects.first()
            
            # Create PM metrics
            metrics, created = PMMetrics.objects.get_or_create(
                board=board,
                pm_user=demo_pm,
                period_start=(now - timedelta(days=30)).date(),
                period_end=now.date(),
                defaults={
                    'suggestions_received': random.randint(5, 15),
                    'suggestions_acted_on': random.randint(3, 10),
                    'avg_response_time_hours': Decimal(random.uniform(2, 24)).quantize(Decimal('0.01')),
                    'velocity_trend': random.choice(['improving', 'stable']),
                    'risk_mitigation_success_rate': Decimal(random.uniform(70, 95)).quantize(Decimal('0.01')),
                    'deadline_hit_rate': Decimal(random.uniform(75, 95)).quantize(Decimal('0.01')),
                    'team_satisfaction_score': Decimal(random.uniform(3.5, 4.8)).quantize(Decimal('0.1')),
                    'coaching_effectiveness_score': Decimal(random.uniform(70, 90)).quantize(Decimal('0.01')),
                }
            )
            if created:
                self.stdout.write(f'   ✅ Created PM metrics for {config["name"]}')

    def create_comments(self, all_tasks, alex, sam, jordan):
        """Create realistic comments for all demo tasks"""
        users = [alex, sam, jordan]
        user_names = ['alex.chen', 'sam.rivera', 'jordan.taylor']
        comments_created = 0
        now = timezone.now()

        for task in all_tasks:
            # Number of comments based on task progress and complexity
            if task.progress >= 80:
                num_comments = random.randint(3, 6)
            elif task.progress >= 40:
                num_comments = random.randint(2, 4)
            elif task.progress > 0:
                num_comments = random.randint(1, 3)
            else:
                num_comments = random.randint(0, 2)

            # Create comments at different times
            for i in range(num_comments):
                # Select a random comment template and user
                template = random.choice(COMMENT_TEMPLATES)
                user = random.choice(users)
                mention = random.choice(user_names)
                
                # Fill in template variables
                comment_text = template.format(
                    mention=mention,
                    progress_detail=random.choice(PROGRESS_DETAILS),
                    technical_detail=random.choice(TECHNICAL_DETAILS),
                    complexity_reason=random.choice(COMPLEXITY_REASONS),
                    related_task=random.choice(all_tasks).title[:30] if all_tasks else 'related task'
                )

                # Create comment at a random time in the past
                days_ago = random.randint(0, 30)
                hours_ago = random.randint(0, 23)
                comment_time = now - timedelta(days=days_ago, hours=hours_ago)

                # Create comment and update created_at (auto_now_add prevents direct setting)
                comment = Comment.objects.create(
                    task=task,
                    user=user,
                    content=comment_text,
                )
                # Update the created_at using raw SQL or update() to bypass auto_now_add
                Comment.objects.filter(pk=comment.pk).update(created_at=comment_time)
                comments_created += 1

        self.stdout.write(f'   ✅ Created {comments_created} comments across all tasks')

    def create_activity_logs(self, all_tasks, alex, sam, jordan):
        """Create activity logs for all demo tasks"""
        users = [alex, sam, jordan]
        activities_created = 0
        now = timezone.now()
        columns = ['To Do', 'In Progress', 'In Review', 'Done']
        priorities = ['low', 'medium', 'high', 'urgent']

        for task in all_tasks:
            # Always create a 'created' activity
            days_ago = random.randint(15, 45)
            created_time = now - timedelta(days=days_ago)
            
            activity = TaskActivity.objects.create(
                task=task,
                user=task.created_by,
                activity_type='created',
                description=random.choice(ACTIVITY_TEMPLATES['created']),
            )
            # Update the created_at using update() to bypass auto_now_add
            TaskActivity.objects.filter(pk=activity.pk).update(created_at=created_time)
            activities_created += 1

            # Add assignment activity if assigned
            if task.assigned_to:
                assign_time = created_time + timedelta(hours=random.randint(1, 48))
                description = random.choice(ACTIVITY_TEMPLATES['assigned']).format(
                    assignee=task.assigned_to.get_full_name() or task.assigned_to.username
                )
                activity = TaskActivity.objects.create(
                    task=task,
                    user=random.choice(users),
                    activity_type='assigned',
                    description=description,
                )
                TaskActivity.objects.filter(pk=activity.pk).update(created_at=assign_time)
                activities_created += 1

            # Add movement activities based on progress
            if task.progress > 0:
                # Moved from To Do to In Progress
                move_time = created_time + timedelta(days=random.randint(1, 5))
                description = random.choice(ACTIVITY_TEMPLATES['moved']).format(
                    from_col='To Do',
                    to_col='In Progress'
                )
                activity = TaskActivity.objects.create(
                    task=task,
                    user=random.choice(users),
                    activity_type='moved',
                    description=description,
                )
                TaskActivity.objects.filter(pk=activity.pk).update(created_at=move_time)
                activities_created += 1

            # Add update activities
            num_updates = random.randint(1, 4)
            for i in range(num_updates):
                update_time = created_time + timedelta(days=random.randint(2, 14), hours=random.randint(0, 23))
                template = random.choice(ACTIVITY_TEMPLATES['updated'])
                description = template.format(
                    priority=random.choice(priorities),
                    progress=task.progress
                )
                activity = TaskActivity.objects.create(
                    task=task,
                    user=random.choice(users),
                    activity_type='updated',
                    description=description,
                )
                TaskActivity.objects.filter(pk=activity.pk).update(created_at=update_time)
                activities_created += 1

            # Add label activities for some tasks
            if random.random() < 0.5:
                label_time = created_time + timedelta(days=random.randint(1, 7))
                labels = task.labels.all()
                if labels.exists():
                    label = labels.first()
                    description = random.choice(ACTIVITY_TEMPLATES['label_added']).format(label=label.name)
                    activity = TaskActivity.objects.create(
                        task=task,
                        user=random.choice(users),
                        activity_type='label_added',
                        description=description,
                    )
                    TaskActivity.objects.filter(pk=activity.pk).update(created_at=label_time)
                    activities_created += 1

        self.stdout.write(f'   ✅ Created {activities_created} activity log entries')

    def create_stakeholders(self, software_board, marketing_board, bug_board, all_tasks, alex, sam, jordan):
        """Create project stakeholders and link them to tasks"""
        now = timezone.now()
        stakeholders_created = 0
        involvements_created = 0

        # Stakeholder data for each board
        stakeholder_configs = [
            {
                'board': software_board,
                'stakeholders': [
                    {'name': 'Michael Chen', 'role': 'CTO', 'influence': 'high', 'interest': 'high', 'email': 'michael.chen@acme.demo'},
                    {'name': 'Sarah Williams', 'role': 'Product Owner', 'influence': 'high', 'interest': 'high', 'email': 'sarah.williams@acme.demo'},
                    {'name': 'David Brown', 'role': 'Security Lead', 'influence': 'medium', 'interest': 'high', 'email': 'david.brown@acme.demo'},
                    {'name': 'Emily Davis', 'role': 'QA Manager', 'influence': 'medium', 'interest': 'medium', 'email': 'emily.davis@acme.demo'},
                    {'name': 'Robert Johnson', 'role': 'DevOps Lead', 'influence': 'medium', 'interest': 'medium', 'email': 'robert.johnson@acme.demo'},
                ]
            },
            {
                'board': marketing_board,
                'stakeholders': [
                    {'name': 'Jennifer Smith', 'role': 'CMO', 'influence': 'high', 'interest': 'high', 'email': 'jennifer.smith@acme.demo'},
                    {'name': 'Amanda Wilson', 'role': 'Brand Manager', 'influence': 'high', 'interest': 'high', 'email': 'amanda.wilson@acme.demo'},
                    {'name': 'Kevin Lee', 'role': 'Content Director', 'influence': 'medium', 'interest': 'high', 'email': 'kevin.lee@acme.demo'},
                    {'name': 'Lisa Anderson', 'role': 'Social Media Lead', 'influence': 'low', 'interest': 'high', 'email': 'lisa.anderson@acme.demo'},
                ]
            },
            {
                'board': bug_board,
                'stakeholders': [
                    {'name': 'Michael Chen', 'role': 'CTO', 'influence': 'high', 'interest': 'medium', 'email': 'michael.chen@acme.demo'},
                    {'name': 'Thomas Miller', 'role': 'Support Manager', 'influence': 'medium', 'interest': 'high', 'email': 'thomas.miller@acme.demo'},
                    {'name': 'Nancy Clark', 'role': 'Customer Success', 'influence': 'medium', 'interest': 'high', 'email': 'nancy.clark@acme.demo'},
                ]
            },
        ]

        for config in stakeholder_configs:
            board = config['board']
            board_tasks = [t for t in all_tasks if t.column.board == board]

            for stakeholder_data in config['stakeholders']:
                # Create stakeholder
                stakeholder, created = ProjectStakeholder.objects.get_or_create(
                    board=board,
                    email=stakeholder_data['email'],
                    defaults={
                        'name': stakeholder_data['name'],
                        'role': stakeholder_data['role'],
                        'organization': 'Acme Corporation',
                        'influence_level': stakeholder_data['influence'],
                        'interest_level': stakeholder_data['interest'],
                        'current_engagement': random.choice(['inform', 'consult', 'involve', 'collaborate']),
                        'desired_engagement': random.choice(['involve', 'collaborate', 'empower']),
                        'notes': f'{stakeholder_data["role"]} stakeholder for {board.name} project',
                        'is_active': True,
                        'created_by': alex,
                    }
                )
                if created:
                    stakeholders_created += 1

                # Link stakeholder to random tasks (30-60% of board tasks)
                num_tasks_to_link = max(2, int(len(board_tasks) * random.uniform(0.3, 0.6)))
                tasks_to_link = random.sample(board_tasks, min(num_tasks_to_link, len(board_tasks)))

                for task in tasks_to_link:
                    # Create involvement record
                    involvement_type = random.choice(['reviewer', 'approver', 'observer', 'beneficiary', 'impacted'])
                    engagement_status = random.choice(['informed', 'consulted', 'involved', 'satisfied'])
                    
                    involvement, inv_created = StakeholderTaskInvolvement.objects.get_or_create(
                        stakeholder=stakeholder,
                        task=task,
                        defaults={
                            'involvement_type': involvement_type,
                            'engagement_status': engagement_status,
                            'engagement_count': random.randint(1, 10),
                            'last_engagement': now - timedelta(days=random.randint(0, 14)),
                            'satisfaction_rating': random.choice([3, 4, 4, 5, 5]) if task.progress > 50 else None,
                            'feedback': 'Good progress on this task.' if random.random() < 0.3 else '',
                        }
                    )
                    if inv_created:
                        involvements_created += 1

        self.stdout.write(f'   ✅ Created {stakeholders_created} stakeholders')
        self.stdout.write(f'   ✅ Created {involvements_created} stakeholder-task involvements')

    def create_file_attachments(self, all_tasks, alex, sam, jordan):
        """Create simulated file attachment metadata for demo tasks"""
        users = [alex, sam, jordan]
        attachments_created = 0
        now = timezone.now()

        # Sample file metadata (we create the records but not actual files)
        file_templates = [
            {'name': 'requirements.pdf', 'type': 'pdf', 'size': 245760, 'desc': 'Requirements document'},
            {'name': 'design-mockup.png', 'type': 'png', 'size': 1048576, 'desc': 'UI design mockup'},
            {'name': 'technical-spec.docx', 'type': 'docx', 'size': 524288, 'desc': 'Technical specification'},
            {'name': 'test-plan.xlsx', 'type': 'xlsx', 'size': 102400, 'desc': 'Test plan spreadsheet'},
            {'name': 'architecture-diagram.png', 'type': 'png', 'size': 819200, 'desc': 'Architecture diagram'},
            {'name': 'api-docs.pdf', 'type': 'pdf', 'size': 368640, 'desc': 'API documentation'},
            {'name': 'meeting-notes.docx', 'type': 'docx', 'size': 81920, 'desc': 'Meeting notes'},
            {'name': 'wireframes.pdf', 'type': 'pdf', 'size': 1536000, 'desc': 'UI wireframes'},
            {'name': 'data-model.xlsx', 'type': 'xlsx', 'size': 153600, 'desc': 'Data model diagram'},
            {'name': 'user-flow.png', 'type': 'png', 'size': 614400, 'desc': 'User flow diagram'},
            {'name': 'code-review.pdf', 'type': 'pdf', 'size': 204800, 'desc': 'Code review notes'},
            {'name': 'deployment-guide.docx', 'type': 'docx', 'size': 163840, 'desc': 'Deployment guide'},
        ]

        # Add attachments to 40-50% of tasks
        tasks_with_attachments = random.sample(all_tasks, int(len(all_tasks) * 0.45))

        for task in tasks_with_attachments:
            # 1-3 attachments per task
            num_attachments = random.randint(1, 3)
            selected_files = random.sample(file_templates, min(num_attachments, len(file_templates)))

            for file_data in selected_files:
                uploader = random.choice(users)
                upload_date = now - timedelta(days=random.randint(1, 30))

                # Create attachment record (without actual file - just metadata for demo)
                # Note: We set the file field to a placeholder path for demo purposes
                try:
                    attachment = TaskFile.objects.create(
                        task=task,
                        uploaded_by=uploader,
                        file=f'demo_files/{task.id}/{file_data["name"]}',  # Placeholder path
                        filename=file_data['name'],
                        file_size=file_data['size'],
                        file_type=file_data['type'],
                        description=file_data['desc'],
                    )
                    attachments_created += 1
                except Exception as e:
                    # Skip if there's an issue creating the attachment
                    pass

        self.stdout.write(f'   ✅ Created {attachments_created} file attachment records')

    def create_wiki_links(self, all_tasks, demo_org, admin_user):
        """Create wiki links for demo tasks"""
        links_created = 0

        try:
            from wiki.models import WikiPage, WikiLink
        except ImportError:
            self.stdout.write(self.style.WARNING('   ⚠️ Wiki module not available, skipping wiki links'))
            return

        # Check if wiki pages exist
        wiki_pages = list(WikiPage.objects.filter(organization=demo_org))
        if not wiki_pages:
            self.stdout.write(self.style.WARNING('   ⚠️ No wiki pages found. Run populate_wiki_demo_data first.'))
            return

        # Link tasks to wiki pages based on keywords
        # Using actual page slugs from the wiki demo data
        keyword_mappings = [
            {'keywords': ['api', 'endpoint', 'rest', 'swagger'], 'page_slug': 'api-documentation'},
            {'keywords': ['code', 'review', 'refactor', 'pull request', 'pr'], 'page_slug': 'code-review-guidelines'},
            {'keywords': ['standard', 'style', 'lint', 'format'], 'page_slug': 'coding-standards'},
            {'keywords': ['design', 'architecture', 'infrastructure', 'system'], 'page_slug': 'system-architecture'},
            {'keywords': ['database', 'schema', 'migration', 'model', 'query'], 'page_slug': 'database-schema'},
            {'keywords': ['sprint', 'planning', 'backlog', 'story'], 'page_slug': 'sprint-45-planning'},
            {'keywords': ['standup', 'daily', 'scrum', 'meeting'], 'page_slug': 'standup-week-1'},
            {'keywords': ['retro', 'retrospective', 'improvement'], 'page_slug': 'sprint-44-retro'},
            {'keywords': ['feature', 'dashboard', 'analytics', 'ai', 'machine learning'], 'page_slug': 'feature-req-ai-dashboard'},
            {'keywords': ['release', 'deploy', 'production', 'version', 'launch'], 'page_slug': 'release-notes-v25'},
            {'keywords': ['incident', 'bug', 'fix', 'error', 'crash', 'issue'], 'page_slug': 'incident-response'},
            {'keywords': ['onboard', 'setup', 'install', 'environment', 'guide', 'tutorial'], 'page_slug': 'team-setup-guide'},
            {'keywords': ['roadmap', 'milestone', 'q1', 'q2', 'quarter', 'goal'], 'page_slug': 'q1-2026-roadmap'},
            {'keywords': ['workflow', 'process', 'agile', 'kanban'], 'page_slug': 'sprint-workflow'},
            {'keywords': ['welcome', 'intro', 'start', 'new'], 'page_slug': 'welcome-to-acme'},
            {'keywords': ['checklist', 'employee', 'hr', 'training'], 'page_slug': 'onboarding-checklist'},
        ]

        for task in all_tasks:
            title_lower = task.title.lower()
            desc_lower = (task.description or '').lower()
            combined_text = title_lower + ' ' + desc_lower

            # Try to match multiple pages (up to 2 per task)
            matched_pages = 0
            for mapping in keyword_mappings:
                if matched_pages >= 2:
                    break
                    
                # Check if any keyword matches
                if any(kw in combined_text for kw in mapping['keywords']):
                    # Find the wiki page
                    wiki_page = WikiPage.objects.filter(
                        organization=demo_org,
                        slug=mapping['page_slug']
                    ).first()

                    if wiki_page:
                        # Create link if it doesn't exist
                        link, created = WikiLink.objects.get_or_create(
                            wiki_page=wiki_page,
                            link_type='task',
                            task=task,
                            defaults={
                                'created_by': admin_user,
                                'description': f'Related documentation for {task.title[:50]}'
                            }
                        )
                        if created:
                            links_created += 1
                            matched_pages += 1

        self.stdout.write(f'   ✅ Created {links_created} wiki links for tasks')

