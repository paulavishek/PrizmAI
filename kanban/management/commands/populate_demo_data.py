"""
Management command to populate demo boards with realistic tasks
Creates ~120 tasks across 3 demo boards with proper assignments, dates, dependencies, and skills
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta
from kanban.models import Board, Column, Task, TaskLabel, Organization
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'Populate demo boards with realistic tasks for demonstration purposes'

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
                'assigned_to': None,  # Unassigned for AI suggestion demo
            },
            {
                'title': 'Implement file upload functionality',
                'description': 'Support for multiple file types with virus scanning and storage optimization',
                'priority': 'low',
                'complexity': 7,
                'assigned_to': None,
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
                'assigned_to': None,
            },
            {
                'title': 'Create data export feature (CSV/Excel)',
                'description': 'Export any dataset to CSV or Excel with custom column selection',
                'priority': 'low',
                'complexity': 4,
                'assigned_to': None,
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
                'assigned_to': None,
            },
            {
                'title': 'Build admin dashboard for system monitoring',
                'description': 'Real-time metrics, logs, and system health indicators',
                'priority': 'medium',
                'complexity': 6,
                'assigned_to': None,
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
                'assigned_to': None,
            },
            {
                'title': 'Add dark mode theme support',
                'description': 'User-selectable dark theme with smooth transitions',
                'priority': 'low',
                'complexity': 4,
                'assigned_to': None,
            },
            {
                'title': 'Build automated backup system',
                'description': 'Daily database backups with retention policy and restore testing',
                'priority': 'high',
                'complexity': 5,
                'assigned_to': None,
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
                'assigned_to': None,
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
                'assigned_to': None,
            },
            {
                'title': 'Social media contest',
                'description': 'Run a giveaway to boost engagement',
                'priority': 'low',
                'complexity': 4,
                'assigned_to': None,
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
                'assigned_to': None,
            },
            {
                'title': 'Redesign landing pages',
                'description': 'Optimize conversion rates on key pages',
                'priority': 'high',
                'complexity': 6,
                'assigned_to': None,
            },
            {
                'title': 'Launch referral program',
                'description': 'Incentivize customers to refer friends',
                'priority': 'medium',
                'complexity': 5,
                'assigned_to': None,
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
                'assigned_to': None,
            },
            {
                'title': 'Customer testimonial videos',
                'description': 'Film satisfied customers sharing their experience',
                'priority': 'medium',
                'complexity': 6,
                'assigned_to': None,
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
                'assigned_to': None,
            },
            {
                'title': 'Memory leak in dashboard view',
                'description': 'Dashboard page memory usage grows continuously',
                'priority': 'high',
                'complexity': 7,
                'assigned_to': None,
            },
            {
                'title': 'Email notifications not sent for comments',
                'description': 'Users not receiving email when mentioned in comments',
                'priority': 'high',
                'complexity': 6,
                'assigned_to': None,
            },
            {
                'title': 'Date picker shows wrong timezone',
                'description': 'Date picker not respecting user timezone settings',
                'priority': 'medium',
                'complexity': 5,
                'assigned_to': None,
            },
            {
                'title': 'Export to CSV includes deleted items',
                'description': 'CSV export showing soft-deleted records',
                'priority': 'low',
                'complexity': 3,
                'assigned_to': None,
            },
            {
                'title': 'Search results missing recent items',
                'description': 'Items created in last hour not appearing in search',
                'priority': 'medium',
                'complexity': 6,
                'assigned_to': None,
            },
            {
                'title': 'Profile image upload fails for large files',
                'description': 'Files over 5MB fail silently without error message',
                'priority': 'medium',
                'complexity': 4,
                'assigned_to': None,
            },
            {
                'title': 'Dark mode colors inconsistent',
                'description': 'Some UI elements not properly themed in dark mode',
                'priority': 'low',
                'complexity': 3,
                'assigned_to': None,
            },
            {
                'title': 'API returns 500 error for invalid date format',
                'description': 'Should return 400 bad request instead',
                'priority': 'medium',
                'complexity': 2,
                'assigned_to': None,
            },
            {
                'title': 'Drag and drop broken in Firefox',
                'description': 'Cannot reorder items in Firefox browser',
                'priority': 'high',
                'complexity': 6,
                'assigned_to': None,
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
