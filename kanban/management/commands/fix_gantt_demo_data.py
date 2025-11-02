"""
Management command to fix demo data for Gantt chart visualization.
This script:
1. Adds start_date to all tasks that have a due_date
2. Establishes Finish-to-Start dependencies between tasks in each board
3. Ensures tasks are ordered logically for Gantt chart display
"""

from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from kanban.models import Board, Task


class Command(BaseCommand):
    help = 'Fix demo data to properly display Gantt charts with task dependencies'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('='*70))
        self.stdout.write(self.style.NOTICE('Fixing Gantt Chart Demo Data'))
        self.stdout.write(self.style.NOTICE('='*70))
        
        # Process each board
        boards = Board.objects.filter(name__in=['Software Project', 'Bug Tracking'])
        
        if not boards.exists():
            self.stdout.write(self.style.ERROR('No demo boards found. Please run populate_test_data first.'))
            return
        
        for board in boards:
            self.stdout.write(self.style.SUCCESS(f'\n📊 Processing Board: {board.name}'))
            self.fix_board_gantt_data(board)
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('✅ Gantt Chart Demo Data Fixed Successfully!'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('\nYou can now view complete Gantt charts at:'))
        for board in boards:
            self.stdout.write(self.style.SUCCESS(f'  📈 /boards/{board.id}/gantt/ - {board.name}'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))

    def fix_board_gantt_data(self, board):
        """Fix Gantt data for a specific board"""
        # Get all tasks for this board, ordered by column position and task position
        tasks = Task.objects.filter(
            column__board=board
        ).select_related('column').order_by('column__position', 'position')
        
        if not tasks.exists():
            self.stdout.write(self.style.WARNING(f'  No tasks found for board: {board.name}'))
            return
        
        self.stdout.write(f'  Found {tasks.count()} tasks')
        
        # Clear existing dependencies to start fresh
        self.stdout.write('  Clearing existing dependencies...')
        for task in tasks:
            task.dependencies.clear()
        
        # Group tasks by column for logical dependency creation
        columns_tasks = {}
        for task in tasks:
            col_name = task.column.name
            if col_name not in columns_tasks:
                columns_tasks[col_name] = []
            columns_tasks[col_name].append(task)
        
        # Fix dates and create dependencies based on board type
        if board.name == 'Software Project':
            self.fix_software_project_board(board, columns_tasks)
        elif board.name == 'Bug Tracking':
            self.fix_bug_tracking_board(board, columns_tasks)
        
        # Verify all tasks have proper dates
        tasks_without_dates = tasks.filter(start_date__isnull=True) | tasks.filter(due_date__isnull=True)
        if tasks_without_dates.exists():
            self.stdout.write(self.style.WARNING(f'  ⚠️  {tasks_without_dates.count()} tasks still missing dates'))
        else:
            self.stdout.write(self.style.SUCCESS(f'  ✅ All {tasks.count()} tasks have start and due dates'))
        
        # Count dependencies
        total_deps = sum(task.dependencies.count() for task in tasks)
        self.stdout.write(self.style.SUCCESS(f'  ✅ Created {total_deps} task dependencies (Finish-to-Start)'))

    def fix_software_project_board(self, board, columns_tasks):
        """Fix Software Project board with realistic project workflow"""
        self.stdout.write('  Setting up Software Development workflow...')
        
        # Define a realistic project timeline
        # Start date: today
        base_date = timezone.now().date()
        
        # Define task sequences with realistic durations and dependencies
        # Each entry: (column_name, task_index, start_offset_days, duration_days)
        task_schedule = {
            'Backlog': [
                # Tasks in backlog - planned but not started yet
                ('Implement user authentication', 30, 7),
                ('Design database schema', 28, 5),
                ('Setup CI/CD pipeline', 35, 4),
            ],
            'To Do': [
                # Ready to start
                ('Create component library', 15, 6),
                ('Write documentation for API endpoints', 20, 5),
            ],
            'In Progress': [
                # Currently being worked on
                ('Implement dashboard layout', -3, 6),  # Started 3 days ago
                ('Setup authentication middleware', -2, 5),  # Started 2 days ago
            ],
            'Review': [
                # In review - almost done
                ('Review homepage design', -1, 3),  # Started yesterday
            ],
            'Done': [
                # Completed tasks
                ('Setup project repository', -10, 3),
                ('Create UI mockups', -13, 5),
                ('Remove legacy code', -7, 2),
            ],
        }
        
        # Map tasks to schedule
        all_tasks_dict = {}
        for col_name, task_list in columns_tasks.items():
            for task in task_list:
                all_tasks_dict[task.title] = task
        
        # Apply dates to tasks
        for col_name, schedule_items in task_schedule.items():
            for title_pattern, start_offset, duration in schedule_items:
                # Find matching task
                task = None
                for task_title, task_obj in all_tasks_dict.items():
                    if title_pattern.lower() in task_title.lower():
                        task = task_obj
                        break
                
                if task:
                    start_date = base_date + timedelta(days=start_offset)
                    end_date = start_date + timedelta(days=duration)
                    
                    task.start_date = start_date
                    task.due_date = datetime.combine(end_date, datetime.max.time())
                    task.due_date = timezone.make_aware(task.due_date) if timezone.is_naive(task.due_date) else task.due_date
                    task.save()
                    
                    self.stdout.write(f'    ✓ {task.title[:50]}: {start_date} → {end_date}')
        
        # Create finish-to-start dependencies for a realistic project flow
        # Project flow: Setup → Design → Backend → Frontend → Testing/Docs
        
        dependency_chains = [
            # Database design depends on project setup
            ('Design database schema', ['Setup project repository']),
            # Authentication depends on database design
            ('Implement user authentication', ['Design database schema']),
            ('Setup authentication middleware', ['Design database schema']),
            # Frontend depends on backend/auth
            ('Implement dashboard layout', ['Setup authentication middleware']),
            ('Create component library', ['Implement dashboard layout']),
            # Review depends on implementation
            ('Review homepage design', ['Implement dashboard layout']),
            # CI/CD can run parallel but should have some deps
            ('Setup CI/CD pipeline', ['Setup project repository']),
            # Documentation depends on implementation
            ('Write documentation for API endpoints', ['Setup authentication middleware', 'Implement user authentication']),
        ]
        
        for task_title, dep_titles in dependency_chains:
            task = all_tasks_dict.get(task_title)
            if not task:
                # Try partial match
                for title, obj in all_tasks_dict.items():
                    if task_title.lower() in title.lower():
                        task = obj
                        break
            
            if task:
                for dep_title in dep_titles:
                    dep_task = all_tasks_dict.get(dep_title)
                    if not dep_task:
                        # Try partial match
                        for title, obj in all_tasks_dict.items():
                            if dep_title.lower() in title.lower():
                                dep_task = obj
                                break
                    
                    if dep_task:
                        task.dependencies.add(dep_task)
                        self.stdout.write(f'    → "{task.title[:40]}" depends on "{dep_task.title[:40]}"')

    def fix_bug_tracking_board(self, board, columns_tasks):
        """Fix Bug Tracking board with bug resolution workflow"""
        self.stdout.write('  Setting up Bug Tracking workflow...')
        
        base_date = timezone.now().date()
        
        # Define bug fix timeline
        # Each entry: (task_title_pattern, start_offset_days, duration_days)
        task_schedule = {
            'New': [
                ('Login page not working on Safari', 1, 3),
                ('Slow response time on search feature', 2, 4),
            ],
            'Investigating': [
                ('Inconsistent data in reports', -1, 4),
            ],
            'In Progress': [
                ('Button alignment issue on mobile', -2, 3),
            ],
            'Testing': [
                ('Fixed pagination on user list', -3, 2),
            ],
            'Closed': [
                ('Error 500 when uploading large files', -8, 3),
                ('Typo on welcome screen', -6, 1),
            ],
        }
        
        # Map tasks to schedule
        all_tasks_dict = {}
        for col_name, task_list in columns_tasks.items():
            for task in task_list:
                all_tasks_dict[task.title] = task
        
        # Apply dates to tasks
        for col_name, schedule_items in task_schedule.items():
            for title_pattern, start_offset, duration in schedule_items:
                # Find matching task
                task = None
                for task_title, task_obj in all_tasks_dict.items():
                    if title_pattern.lower() in task_title.lower():
                        task = task_obj
                        break
                
                if task:
                    start_date = base_date + timedelta(days=start_offset)
                    end_date = start_date + timedelta(days=duration)
                    
                    task.start_date = start_date
                    task.due_date = datetime.combine(end_date, datetime.max.time())
                    task.due_date = timezone.make_aware(task.due_date) if timezone.is_naive(task.due_date) else task.due_date
                    task.save()
                    
                    self.stdout.write(f'    ✓ {task.title[:50]}: {start_date} → {end_date}')
        
        # Create finish-to-start dependencies for bug tracking
        # Some bugs might be related or depend on others being fixed first
        
        dependency_chains = [
            # Data issues might need to be fixed before pagination works
            ('Fixed pagination on user list', ['Inconsistent data in reports']),
            # Performance issue might be related to data issues
            ('Slow response time on search feature', ['Inconsistent data in reports']),
            # UI issues don't necessarily depend on backend fixes
            # Login bug is critical and should be independent
        ]
        
        for task_title, dep_titles in dependency_chains:
            task = None
            for title, obj in all_tasks_dict.items():
                if task_title.lower() in title.lower():
                    task = obj
                    break
            
            if task:
                for dep_title in dep_titles:
                    dep_task = None
                    for title, obj in all_tasks_dict.items():
                        if dep_title.lower() in title.lower():
                            dep_task = obj
                            break
                    
                    if dep_task:
                        task.dependencies.add(dep_task)
                        self.stdout.write(f'    → "{task.title[:40]}" depends on "{dep_task.title[:40]}"')
