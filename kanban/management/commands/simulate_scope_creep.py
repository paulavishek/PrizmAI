"""
Management command to simulate scope creep on demo boards
This helps demonstrate the scope tracking and alert features
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User
from kanban.models import Board, Column, Task, TaskLabel
from kanban.utils.scope_analysis import create_scope_alert_if_needed
from datetime import timedelta
import random


class Command(BaseCommand):
    help = 'Simulate scope creep on demo boards to test scope tracking features'

    def add_arguments(self, parser):
        parser.add_argument(
            '--board',
            type=str,
            help='Board name to simulate scope creep on (default: all demo boards)',
        )
        parser.add_argument(
            '--intensity',
            type=str,
            choices=['low', 'medium', 'high'],
            default='medium',
            help='Intensity of scope creep (low=5-8 tasks, medium=10-15 tasks, high=20-30 tasks)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('='*70))
        self.stdout.write(self.style.NOTICE('Simulating Scope Creep on Demo Boards'))
        self.stdout.write(self.style.NOTICE('='*70))
        
        # Get target boards
        board_name = options.get('board')
        if board_name:
            boards = Board.objects.filter(name=board_name)
            if not boards.exists():
                self.stdout.write(self.style.ERROR(f'Board "{board_name}" not found'))
                return
        else:
            # Target demo boards
            boards = Board.objects.filter(name__in=['Software Project', 'Marketing Campaign', 'Bug Tracking'])
        
        if not boards.exists():
            self.stdout.write(self.style.ERROR('No demo boards found. Run populate_test_data first.'))
            return
        
        intensity = options.get('intensity', 'medium')
        
        for board in boards:
            self.stdout.write(self.style.SUCCESS(f'\n📊 Processing Board: {board.name}'))
            self.simulate_board_scope_creep(board, intensity)
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('✅ Scope Creep Simulation Complete!'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.NOTICE('\nYou can now:'))
        self.stdout.write(self.style.NOTICE('1. View scope alerts in the board analytics'))
        self.stdout.write(self.style.NOTICE('2. Check scope change snapshots'))
        self.stdout.write(self.style.NOTICE('3. Review AI-generated recommendations'))

    def simulate_board_scope_creep(self, board, intensity):
        """Simulate scope creep on a specific board"""
        
        # Get admin user for task creation
        admin_user = User.objects.filter(username='admin').first()
        if not admin_user:
            admin_user = User.objects.first()
        
        # Get board columns
        columns = board.columns.all()
        if not columns.exists():
            self.stdout.write(self.style.WARNING(f'  No columns found for {board.name}'))
            return
        
        # Determine number of tasks to add based on intensity
        intensity_map = {
            'low': (5, 8),
            'medium': (10, 15),
            'high': (20, 30)
        }
        min_tasks, max_tasks = intensity_map[intensity]
        num_tasks = random.randint(min_tasks, max_tasks)
        
        self.stdout.write(f'  Adding {num_tasks} new tasks ({intensity} intensity)...')
        
        # Create a snapshot before changes (if baseline exists)
        if board.baseline_task_count:
            before_snapshot = board.create_scope_snapshot(
                user=admin_user,
                snapshot_type='scheduled',
                notes='Before scope creep simulation'
            )
            self.stdout.write(f'  📸 Created "before" snapshot (ID: {before_snapshot.id})')
        
        # Add new tasks to simulate scope creep
        tasks_added = self.add_scope_creep_tasks(board, columns, admin_user, num_tasks)
        
        # Inflate complexity on some existing tasks
        complexity_increased = self.inflate_task_complexity(board, count=random.randint(3, 7))
        
        # Create snapshot after changes
        after_snapshot = board.create_scope_snapshot(
            user=admin_user,
            snapshot_type='scheduled',
            notes=f'After scope creep simulation: {tasks_added} tasks added, {complexity_increased} tasks complexity increased'
        )
        
        self.stdout.write(f'  📸 Created "after" snapshot (ID: {after_snapshot.id})')
        
        # Check for alerts
        if after_snapshot.scope_change_percentage:
            self.stdout.write(f'  📈 Scope change: {after_snapshot.scope_change_percentage:+.1f}%')
            
            # Create alert if needed
            alert = create_scope_alert_if_needed(after_snapshot)
            if alert:
                self.stdout.write(self.style.WARNING(
                    f'  ⚠️  ALERT CREATED: {alert.get_severity_display()} - '
                    f'Scope increased {alert.scope_increase_percentage:.1f}%'
                ))
                self.stdout.write(f'      Predicted delay: {alert.predicted_delay_days} days')
            else:
                self.stdout.write(self.style.SUCCESS('  ✓ Scope change within acceptable limits'))
        
        self.stdout.write(self.style.SUCCESS(f'  ✅ Completed: {tasks_added} tasks added, {complexity_increased} complexities increased'))

    def add_scope_creep_tasks(self, board, columns, user, count):
        """Add new tasks to simulate scope creep"""
        
        # Task templates for different board types
        task_templates = {
            'Software Project': [
                ('Add user profile avatar upload', 'Allow users to upload custom avatars', 'medium', 6),
                ('Implement password reset email', 'Send password reset emails with tokens', 'high', 5),
                ('Add activity feed to dashboard', 'Show recent activities on user dashboard', 'medium', 7),
                ('Create admin panel for user management', 'Admin interface to manage users', 'high', 9),
                ('Implement search functionality', 'Global search across all content', 'high', 8),
                ('Add email notification settings', 'Let users customize email preferences', 'low', 4),
                ('Create mobile-responsive navbar', 'Improve navbar for mobile devices', 'medium', 5),
                ('Add two-factor authentication', 'Security feature for user accounts', 'high', 8),
                ('Implement data export feature', 'Allow users to export their data', 'medium', 6),
                ('Create onboarding tutorial', 'Guide new users through features', 'medium', 7),
                ('Add dark mode toggle', 'Theme switching functionality', 'low', 5),
                ('Implement rate limiting on API', 'Prevent API abuse', 'high', 6),
                ('Add file preview functionality', 'Preview uploaded files before download', 'medium', 7),
                ('Create automated backup system', 'Daily backups of database', 'high', 8),
                ('Add social media login', 'Login with Google, GitHub, etc.', 'medium', 7),
                ('Implement real-time notifications', 'WebSocket-based notifications', 'high', 9),
                ('Add data visualization charts', 'Charts and graphs for analytics', 'medium', 8),
                ('Create audit log viewer', 'UI to view system audit logs', 'low', 5),
                ('Implement keyboard shortcuts', 'Power user keyboard navigation', 'low', 4),
                ('Add bulk operations', 'Bulk edit/delete functionality', 'medium', 6),
            ],
            'Marketing Campaign': [
                ('Design social media graphics pack', 'Create branded graphics for social posts', 'high', 6),
                ('Write blog post series', 'SEO-optimized blog content', 'medium', 7),
                ('Create email drip campaign', 'Automated email sequence for leads', 'high', 8),
                ('Design landing page mockups', 'Convert-optimized landing pages', 'high', 7),
                ('Develop influencer outreach list', 'Research and compile influencer contacts', 'medium', 5),
                ('Create video marketing content', 'Short-form videos for social media', 'high', 9),
                ('Design infographic for whitepaper', 'Visual summary of key findings', 'medium', 6),
                ('Set up Google Ads campaign', 'PPC campaign with ad groups', 'high', 7),
                ('Create press release', 'Announce new product launch', 'medium', 4),
                ('Design promotional banners', 'Website and social media banners', 'low', 5),
                ('Develop content calendar', 'Q1 content planning and scheduling', 'medium', 6),
                ('Create customer testimonial videos', 'Record and edit testimonials', 'high', 8),
                ('Design email newsletter templates', 'Branded email templates', 'medium', 5),
                ('Set up marketing automation', 'Configure automation workflows', 'high', 7),
                ('Create competitor analysis report', 'Research and analyze competitors', 'medium', 6),
            ],
            'Bug Tracking': [
                ('Fix memory leak in background process', 'Investigation and resolution', 'urgent', 8),
                ('Resolve API timeout issues', 'Optimize slow API endpoints', 'high', 7),
                ('Fix broken image uploads', 'Images not uploading correctly', 'high', 6),
                ('Resolve mobile layout issues', 'Fix responsive design bugs', 'medium', 5),
                ('Fix email delivery failures', 'Some emails not being sent', 'high', 6),
                ('Resolve database connection pool exhaustion', 'Connection pool management', 'urgent', 9),
                ('Fix broken export functionality', 'CSV export throwing errors', 'high', 5),
                ('Resolve caching inconsistencies', 'Cache invalidation issues', 'medium', 6),
                ('Fix authentication token expiry bug', 'Users logged out prematurely', 'high', 7),
                ('Resolve cross-browser compatibility', 'Fix issues in Safari and Firefox', 'medium', 6),
                ('Fix data validation errors', 'Form validation not working', 'medium', 5),
                ('Resolve timezone conversion bugs', 'Incorrect time displays', 'high', 6),
                ('Fix pagination on search results', 'Pagination broken after query', 'medium', 4),
                ('Resolve file upload size limit', 'Large files failing to upload', 'high', 5),
                ('Fix notification badge count', 'Incorrect unread count', 'low', 3),
            ]
        }
        
        # Get appropriate templates or use generic
        templates = task_templates.get(board.name, task_templates['Software Project'])
        
        # Select random tasks from templates
        selected_tasks = random.sample(templates, min(count, len(templates)))
        
        # Get labels if available
        labels = list(board.labels.all()[:3])
        
        # Determine target column (prefer To Do or Backlog)
        target_column = None
        for col in columns:
            if 'to do' in col.name.lower() or 'backlog' in col.name.lower():
                target_column = col
                break
        if not target_column:
            target_column = columns.first()
        
        tasks_created = 0
        for title, description, priority, complexity in selected_tasks:
            task = Task.objects.create(
                title=title,
                description=description,
                column=target_column,
                priority=priority,
                complexity_score=complexity,
                created_by=user,
                assigned_to=random.choice([user, None]),
                due_date=timezone.now() + timedelta(days=random.randint(7, 30)),
                position=tasks_created
            )
            
            # Add random labels
            if labels:
                task.labels.set(random.sample(labels, min(2, len(labels))))
            
            tasks_created += 1
        
        return tasks_created

    def inflate_task_complexity(self, board, count=5):
        """Increase complexity scores on existing tasks"""
        
        # Get tasks with lower complexity that can be increased
        tasks = Task.objects.filter(
            column__board=board,
            complexity_score__lt=8
        ).order_by('?')[:count]
        
        increased = 0
        for task in tasks:
            old_complexity = task.complexity_score
            task.complexity_score = min(10, task.complexity_score + random.randint(2, 4))
            task.save()
            increased += 1
            self.stdout.write(
                f'      Increased "{task.title}" complexity: {old_complexity} → {task.complexity_score}'
            )
        
        return increased
