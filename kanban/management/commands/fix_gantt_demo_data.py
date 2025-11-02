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
                # Completed tasks (in the past) - sequential completion
                ('Setup project repository', -35, 3),      # Started 35 days ago, took 3 days
                ('Create UI mockups', -28, 5),             # Started 28 days ago (after repo setup), took 5 days
                ('Remove legacy code', -20, 2),            # Started 20 days ago, took 2 days
            ],
            'Review': [
                # In review - almost done (very recent)
                ('Review homepage design', -5, 4),         # Started 5 days ago, 4 day duration
            ],
            'In Progress': [
                # Currently being worked on (started recently)
                ('Implement dashboard layout', -8, 10),     # Started 8 days ago, 10 day duration (in progress)
                ('Setup authentication middleware', -12, 14), # Started 12 days ago, 14 day duration (in progress)
            ],
            'To Do': [
                # Ready to start (near future) - will start after current work
                ('Create component library', 3, 8),        # Starts in 3 days, 8 day duration
                ('Write documentation for API endpoints', 12, 7), # Starts in 12 days
            ],
            'Backlog': [
                # Tasks in backlog - planned for later with proper spacing
                ('Design database schema', 20, 6),         # Starts in 20 days
                ('Implement user authentication', 28, 9),   # Starts in 28 days
                ('Setup CI/CD pipeline', 38, 5),           # Starts in 38 days
            ],
        }
        
        # Map tasks to schedule
        all_tasks_dict = {}
        for col_name, task_list in columns_tasks.items():
            for task in task_list:
                all_tasks_dict[task.title] = task
        
        # Track which tasks were scheduled
        scheduled_tasks = set()
        task_objects = {}  # Map title pattern to task object
        
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
                    task_objects[title_pattern] = task
                    self.stdout.write(f'    ✓ {task.title[:50]}: {start_date} → {end_date}')
        
        # Handle any remaining unscheduled tasks based on their column
        offset_counter = 45  # Start future tasks far out
        for task in all_tasks_dict.values():
            if task not in scheduled_tasks:
                col_name = task.column.name
                
                # Assign default dates based on column
                if col_name.lower() in ['done', 'closed', 'completed']:
                    start_offset = -40 - (offset_counter % 10)
                    duration = 4
                elif col_name.lower() in ['review', 'testing']:
                    start_offset = -10
                    duration = 4
                elif col_name.lower() in ['in progress', 'investigating']:
                    start_offset = -15
                    duration = 8
                elif col_name.lower() in ['to do', 'new']:
                    start_offset = 5
                    duration = 6
                else:  # Backlog or other
                    start_offset = offset_counter
                    duration = 5
                    offset_counter += 8  # Space out backlog tasks
                
                start_date = base_date + timedelta(days=start_offset)
                end_date = start_date + timedelta(days=duration)
                
                task.start_date = start_date
                task.due_date = datetime.combine(end_date, datetime.max.time())
                task.due_date = timezone.make_aware(task.due_date) if timezone.is_naive(task.due_date) else task.due_date
                task.save()
                
                self.stdout.write(f'    ✓ {task.title[:50]} (auto): {start_date} → {end_date}')
        
        # Create finish-to-start dependencies for a realistic project flow
        # Project flow: Setup (Done) → Design (Done/Backlog) → Backend (In Progress/To Do) → Frontend (To Do/Review) → Pipeline
        
        dependency_chains = [
            # Phase 1: Foundation → Current Work
            ('Create UI mockups', ['Setup project repository']),
            ('Setup authentication middleware', ['Setup project repository']),
            
            # Phase 2: Current work dependencies
            ('Implement dashboard layout', ['Create UI mockups', 'Setup authentication middleware']),
            
            # Phase 3: Review depends on implementation
            ('Review homepage design', ['Implement dashboard layout']),
            
            # Phase 4: Future work depends on reviews
            ('Create component library', ['Review homepage design']),
            
            # Phase 5: Database and backend work
            ('Design database schema', ['Setup project repository']),
            ('Implement user authentication', ['Design database schema', 'Setup authentication middleware']),
            
            # Phase 6: Documentation and CI/CD come last
            ('Write documentation for API endpoints', ['Create component library', 'Implement user authentication']),
            ('Setup CI/CD pipeline', ['Implement user authentication']),
        ]
        
        for task_title, dep_titles in dependency_chains:
            task = task_objects.get(task_title)
            if not task:
                # Try partial match
                for title, obj in all_tasks_dict.items():
                    if task_title.lower() in title.lower():
                        task = obj
                        break
            
            if task:
                for dep_title in dep_titles:
                    dep_task = task_objects.get(dep_title)
                    if not dep_task:
                        # Try partial match
                        for title, obj in all_tasks_dict.items():
                            if dep_title.lower() in title.lower():
                                dep_task = obj
                                break
                    
                    if dep_task and dep_task.start_date and dep_task.due_date:
                        # Ensure dependency task ends before dependent task starts
                        if dep_task.due_date.date() <= task.start_date:
                            task.dependencies.add(dep_task)
                            self.stdout.write(f'    → "{task.title[:40]}" depends on "{dep_task.title[:40]}"')
                        else:
                            self.stdout.write(f'    ⚠ Skipped invalid dependency: "{task.title[:40]}" -> "{dep_task.title[:40]}" (dates conflict)')

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
                # Fixed bugs (completed in the past) - sequential
                ('Error 500 when uploading large files', -20, 4),  # Fixed 20 days ago
                ('Typo on welcome screen', -14, 2),                 # Fixed 14 days ago
            ],
            'Testing': [
                # In testing phase (recent)
                ('Fixed pagination on user list', -6, 5),          # Started testing 6 days ago
            ],
            'In Progress': [
                # Currently being fixed
                ('Button alignment issue on mobile', -4, 6),       # Started fixing 4 days ago
            ],
            'Investigating': [
                # Under investigation
                ('Inconsistent data in reports', -2, 7),           # Started investigating 2 days ago
            ],
            'New': [
                # Recently reported (near future)
                ('Login page not working on Safari', 1, 4),        # Will be reported tomorrow
                ('Slow response time on search feature', 6, 5),    # Will be reported in 6 days
            ],
        }
        
        # Map tasks to schedule
        all_tasks_dict = {}
        for col_name, task_list in columns_tasks.items():
            for task in task_list:
                all_tasks_dict[task.title] = task
        
        # Track which tasks were scheduled
        scheduled_tasks = set()
        task_objects = {}  # Map title pattern to task object
        
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
                    task_objects[title_pattern] = task
                    self.stdout.write(f'    ✓ {task.title[:50]}: {start_date} → {end_date}')
        
        # Handle any remaining unscheduled tasks based on their column
        offset_counter = 12  # Start future tasks
        for task in all_tasks_dict.values():
            if task not in scheduled_tasks:
                col_name = task.column.name
                
                # Assign default dates based on column
                if col_name.lower() in ['done', 'closed', 'completed']:
                    start_offset = -25 - (offset_counter % 5)
                    duration = 3
                elif col_name.lower() in ['review', 'testing']:
                    start_offset = -8
                    duration = 4
                elif col_name.lower() in ['in progress', 'investigating']:
                    start_offset = -5
                    duration = 6
                elif col_name.lower() in ['to do', 'new']:
                    start_offset = offset_counter
                    duration = 4
                    offset_counter += 6  # Space out new bugs
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
            task = task_objects.get(task_title)
            if not task:
                for title, obj in all_tasks_dict.items():
                    if task_title.lower() in title.lower():
                        task = obj
                        break
            
            if task:
                for dep_title in dep_titles:
                    dep_task = task_objects.get(dep_title)
                    if not dep_task:
                        for title, obj in all_tasks_dict.items():
                            if dep_title.lower() in title.lower():
                                dep_task = obj
                                break
                    
                    if dep_task and dep_task.start_date and dep_task.due_date:
                        # Ensure dependency task ends before dependent task starts
                        if dep_task.due_date.date() <= task.start_date:
                            task.dependencies.add(dep_task)
                            self.stdout.write(f'    → "{task.title[:40]}" depends on "{dep_task.title[:40]}"')
                        else:
                            self.stdout.write(f'    ⚠ Skipped invalid dependency: "{task.title[:40]}" -> "{dep_task.title[:40]}" (dates conflict)')
