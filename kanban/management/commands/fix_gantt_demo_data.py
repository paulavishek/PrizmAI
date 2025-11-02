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
        
        # Define a realistic project timeline - ALWAYS relative to current date
        # This ensures demo data is always relevant regardless of when it's run
        base_date = timezone.now().date()
        
        # Define task sequences with realistic durations and dependencies
        # Offsets are RELATIVE to current date (base_date = today)
        # Negative offset = days in the past, Positive offset = days in the future
        # Format: (task_title_pattern, start_offset_days, duration_days)
        task_schedule = {
            'Done': [
                # Completed tasks (in the past)
                ('Setup project repository', -20, 3),      # Started 20 days ago, took 3 days
                ('Create UI mockups', -25, 5),             # Started 25 days ago, took 5 days
                ('Remove legacy code', -15, 2),            # Started 15 days ago, took 2 days
            ],
            'Review': [
                # In review - almost done (very recent)
                ('Review homepage design', -3, 4),         # Started 3 days ago, 4 day duration
            ],
            'In Progress': [
                # Currently being worked on (started recently)
                ('Implement dashboard layout', -5, 8),     # Started 5 days ago, 8 day duration
                ('Setup authentication middleware', -7, 10), # Started 7 days ago, 10 day duration
            ],
            'To Do': [
                # Ready to start (near future)
                ('Create component library', 2, 6),        # Starts in 2 days, 6 day duration
                ('Write documentation for API endpoints', 5, 5), # Starts in 5 days
            ],
            'Backlog': [
                # Tasks in backlog - planned for later
                ('Design database schema', 12, 5),         # Starts in 12 days
                ('Implement user authentication', 18, 7),   # Starts in 18 days
                ('Setup CI/CD pipeline', 25, 4),           # Starts in 25 days
            ],
        }
        
        # Map tasks to schedule
        all_tasks_dict = {}
        for col_name, task_list in columns_tasks.items():
            for task in task_list:
                all_tasks_dict[task.title] = task
        
        # Track which tasks were scheduled
        scheduled_tasks = set()
        
        # Apply dates to tasks in the schedule
        for col_name, schedule_items in task_schedule.items():
            for title_pattern, start_offset, duration in schedule_items:
                # Find matching task
                task = None
                for task_title, task_obj in all_tasks_dict.items():
                    if title_pattern.lower() in task_title.lower() and task_obj not in scheduled_tasks:
                        task = task_obj
                        break
                
                if task:
                    start_date = base_date + timedelta(days=start_offset)
                    end_date = start_date + timedelta(days=duration)
                    
                    task.start_date = start_date
                    task.due_date = datetime.combine(end_date, datetime.max.time())
                    task.due_date = timezone.make_aware(task.due_date) if timezone.is_naive(task.due_date) else task.due_date
                    task.save()
                    
                    scheduled_tasks.add(task)
                    self.stdout.write(f'    ✓ {task.title[:50]}: {start_date} → {end_date}')
        
        # Handle any remaining unscheduled tasks based on their column
        for task in all_tasks_dict.values():
            if task not in scheduled_tasks:
                col_name = task.column.name
                
                # Assign default dates based on column
                if col_name.lower() in ['done', 'closed', 'completed']:
                    start_offset = -22
                    duration = 4
                elif col_name.lower() in ['review', 'testing']:
                    start_offset = -4
                    duration = 4
                elif col_name.lower() in ['in progress', 'investigating']:
                    start_offset = -6
                    duration = 7
                elif col_name.lower() in ['to do', 'new']:
                    start_offset = 3
                    duration = 5
                else:  # Backlog or other
                    start_offset = 20
                    duration = 5
                
                start_date = base_date + timedelta(days=start_offset)
                end_date = start_date + timedelta(days=duration)
                
                task.start_date = start_date
                task.due_date = datetime.combine(end_date, datetime.max.time())
                task.due_date = timezone.make_aware(task.due_date) if timezone.is_naive(task.due_date) else task.due_date
                task.save()
                
                self.stdout.write(f'    ✓ {task.title[:50]} (auto): {start_date} → {end_date}')
        
        # Create finish-to-start dependencies for a realistic project flow
        # Project flow: Setup (Done) → Design (Backlog) → Backend (In Progress/To Do) → Frontend (To Do) → Review
        
        dependency_chains = [
            # Phase 1: Foundation (already done)
            ('Setup authentication middleware', ['Setup project repository']),
            
            # Phase 2: Core Implementation (in progress)
            ('Implement dashboard layout', ['Setup authentication middleware']),
            
            # Phase 3: Review current work
            ('Review homepage design', ['Implement dashboard layout']),
            
            # Phase 4: Future work (to do)
            ('Create component library', ['Review homepage design']),
            ('Design database schema', ['Setup project repository']),
            
            # Phase 5: Advanced features (backlog)
            ('Implement user authentication', ['Design database schema']),
            ('Setup CI/CD pipeline', ['Design database schema']),
            ('Write documentation for API endpoints', ['Create component library', 'Implement user authentication']),
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
        
        # Base date is always current date - keeps demo data fresh
        base_date = timezone.now().date()
        
        # Define bug fix timeline - RELATIVE to current date
        # Negative offset = days in the past, Positive offset = days in the future
        # Format: (task_title_pattern, start_offset_days, duration_days)
        task_schedule = {
            'Closed': [
                # Fixed bugs (completed in the past)
                ('Error 500 when uploading large files', -12, 3),  # Fixed 12 days ago
                ('Typo on welcome screen', -8, 1),                 # Fixed 8 days ago
            ],
            'Testing': [
                # In testing phase (recent)
                ('Fixed pagination on user list', -4, 3),          # Started testing 4 days ago
            ],
            'In Progress': [
                # Currently being fixed
                ('Button alignment issue on mobile', -2, 4),       # Started fixing 2 days ago
            ],
            'Investigating': [
                # Under investigation
                ('Inconsistent data in reports', -1, 5),           # Started investigating yesterday
            ],
            'New': [
                # Recently reported (today/tomorrow)
                ('Login page not working on Safari', 0, 3),        # Reported today
                ('Slow response time on search feature', 1, 4),    # Will be reported tomorrow
            ],
        }
        
        # Map tasks to schedule
        all_tasks_dict = {}
        for col_name, task_list in columns_tasks.items():
            for task in task_list:
                all_tasks_dict[task.title] = task
        
        # Track which tasks were scheduled
        scheduled_tasks = set()
        
        # Apply dates to tasks in the schedule
        for col_name, schedule_items in task_schedule.items():
            for title_pattern, start_offset, duration in schedule_items:
                # Find matching task
                task = None
                for task_title, task_obj in all_tasks_dict.items():
                    if title_pattern.lower() in task_title.lower() and task_obj not in scheduled_tasks:
                        task = task_obj
                        break
                
                if task:
                    start_date = base_date + timedelta(days=start_offset)
                    end_date = start_date + timedelta(days=duration)
                    
                    task.start_date = start_date
                    task.due_date = datetime.combine(end_date, datetime.max.time())
                    task.due_date = timezone.make_aware(task.due_date) if timezone.is_naive(task.due_date) else task.due_date
                    task.save()
                    
                    scheduled_tasks.add(task)
                    self.stdout.write(f'    ✓ {task.title[:50]}: {start_date} → {end_date}')
        
        # Handle any remaining unscheduled tasks based on their column
        for task in all_tasks_dict.values():
            if task not in scheduled_tasks:
                col_name = task.column.name
                
                # Assign default dates based on column
                if col_name.lower() in ['done', 'closed', 'completed']:
                    start_offset = -10
                    duration = 2
                elif col_name.lower() in ['review', 'testing']:
                    start_offset = -5
                    duration = 3
                elif col_name.lower() in ['in progress', 'investigating']:
                    start_offset = -3
                    duration = 4
                elif col_name.lower() in ['to do', 'new']:
                    start_offset = 0
                    duration = 3
                else:  # Other
                    start_offset = 2
                    duration = 3
                
                start_date = base_date + timedelta(days=start_offset)
                end_date = start_date + timedelta(days=duration)
                
                task.start_date = start_date
                task.due_date = datetime.combine(end_date, datetime.max.time())
                task.due_date = timezone.make_aware(task.due_date) if timezone.is_naive(task.due_date) else task.due_date
                task.save()
                
                self.stdout.write(f'    ✓ {task.title[:50]} (auto): {start_date} → {end_date}')
        
        # Create finish-to-start dependencies for bug tracking
        # Bugs flow: Identify → Fix → Test → Close
        # Some bugs are related (backend data issues affect other features)
        
        dependency_chains = [
            # Backend data investigation must complete before pagination fix can be tested
            ('Fixed pagination on user list', ['Inconsistent data in reports']),
            # Performance issues often stem from data problems
            ('Slow response time on search feature', ['Inconsistent data in reports']),
            # Login bug is critical - no dependencies, needs immediate attention
            # UI bugs are independent - can be fixed in parallel
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
