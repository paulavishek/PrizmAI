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
        boards = Board.objects.filter(name__in=['Software Project', 'Bug Tracking', 'Marketing Campaign'])
        
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
        elif board.name == 'Marketing Campaign':
            self.fix_marketing_campaign_board(board, columns_tasks)
        
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
                    
                    if dep_task and dep_task.start_date and dep_task.due_date and task.start_date:
                        # Ensure dependency task ends BEFORE dependent task starts
                        if dep_task.due_date.date() <= task.start_date:
                            task.dependencies.add(dep_task)
                            self.stdout.write(f'    → "{task.title[:40]}" depends on "{dep_task.title[:40]}"')
                        else:
                            # Auto-adjust task dates to start after dependency
                            task.start_date = dep_task.due_date.date() + timedelta(days=1)
                            original_duration = (task.due_date.date() - base_date).days if task.due_date else 7
                            duration = max(3, min(original_duration, 10))  # Keep reasonable duration
                            task.due_date = datetime.combine(task.start_date + timedelta(days=duration), datetime.max.time())
                            task.due_date = timezone.make_aware(task.due_date) if timezone.is_naive(task.due_date) else task.due_date
                            task.save()
                            task.dependencies.add(dep_task)
                            self.stdout.write(f'    → "{task.title[:40]}" depends on "{dep_task.title[:40]}" (dates auto-adjusted)')

    def fix_bug_tracking_board(self, board, columns_tasks):
        """Fix Bug Tracking board with bug resolution workflow"""
        self.stdout.write('  Setting up Bug Tracking workflow...')
        
        # Base date is always current date - keeps demo data fresh
        base_date = timezone.now().date()
        
        # Define bug fix timeline - RELATIVE to current date
        # Format: (task_title_pattern, start_offset_days, duration_days)
        # We'll create a clear workflow: Bug1 -> Bug2 -> Bug3 in sequence
        task_schedule = {
            'Closed': [
                # Fixed bugs (completed in the past) - sequential
                ('Error 500 when uploading large files', -30, 5),  # First bug fixed
                ('Typo on welcome screen', -23, 3),                 # Fixed after first bug
            ],
            'Testing': [
                # In testing phase (recent)
                ('Fixed pagination on user list', -10, 6),          # In testing
            ],
            'In Progress': [
                # Currently being fixed - depends on testing results
                ('Button alignment issue on mobile', -4, 8),       # Currently fixing
            ],
            'Investigating': [
                # Under investigation - depends on in-progress bug
                ('Inconsistent data in reports', 2, 6),           # Will start investigating
            ],
            'New': [
                # Recently reported (future) - will start after investigation
                ('Login page not working on Safari', 10, 5),        # Future bug 1
                ('Slow response time on search feature', 17, 6),    # Future bug 2
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
        offset_counter = 25  # Start future tasks
        for task in all_tasks_dict.values():
            if task not in scheduled_tasks:
                col_name = task.column.name
                
                # Assign default dates based on column
                if col_name.lower() in ['done', 'closed', 'completed']:
                    start_offset = -35 - (offset_counter % 5)
                    duration = 3
                elif col_name.lower() in ['review', 'testing']:
                    start_offset = -12
                    duration = 4
                elif col_name.lower() in ['in progress', 'investigating']:
                    start_offset = -2
                    duration = 6
                elif col_name.lower() in ['to do', 'new']:
                    start_offset = offset_counter
                    duration = 4
                    offset_counter += 8  # Space out new bugs
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
        # Clear dependency chain: Each bug depends on the previous one being resolved
        
        dependency_chains = [
            # Sequential workflow: Fix bugs in priority order
            ('Typo on welcome screen', ['Error 500 when uploading large files']),
            ('Fixed pagination on user list', ['Typo on welcome screen']),
            ('Button alignment issue on mobile', ['Fixed pagination on user list']),
            ('Inconsistent data in reports', ['Button alignment issue on mobile']),
            ('Login page not working on Safari', ['Inconsistent data in reports']),
            ('Slow response time on search feature', ['Login page not working on Safari']),
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
                    
                    if dep_task and dep_task.start_date and dep_task.due_date and task.start_date:
                        # Ensure dependency task ends BEFORE dependent task starts
                        if dep_task.due_date.date() <= task.start_date:
                            task.dependencies.add(dep_task)
                            self.stdout.write(f'    → "{task.title[:40]}" depends on "{dep_task.title[:40]}"')
                        else:
                            # Adjust task start date to be after dependency ends
                            task.start_date = dep_task.due_date.date() + timedelta(days=1)
                            task.due_date = datetime.combine(task.start_date + timedelta(days=5), datetime.max.time())
                            task.due_date = timezone.make_aware(task.due_date) if timezone.is_naive(task.due_date) else task.due_date
                            task.save()
                            task.dependencies.add(dep_task)
                            self.stdout.write(f'    → "{task.title[:40]}" depends on "{dep_task.title[:40]}" (dates adjusted)')

    def fix_marketing_campaign_board(self, board, columns_tasks):
        """Fix Marketing Campaign board with marketing workflow"""
        self.stdout.write('  Setting up Marketing Campaign workflow...')
        
        # Base date is always current date - keeps demo data fresh
        base_date = timezone.now().date()
        
        # Define marketing campaign timeline - RELATIVE to current date
        # Negative offset = days in the past, Positive offset = days in the future
        # Format: (task_title_pattern, start_offset_days, duration_days)
        task_schedule = {
            'Completed': [
                # Completed campaigns (in the past) - sequential completion
                ('Summer campaign graphics', -30, 10),           # Completed 30 days ago
                ('Competitor analysis report', -18, 6),          # Completed 18 days ago
                ('Remove outdated content', -10, 3),             # Completed 10 days ago
            ],
            'Review': [
                # In review phase (recent)
                ('New product announcement email', -5, 7),       # Started review 5 days ago
            ],
            'In Progress': [
                # Currently being worked on
                ('Website redesign for Q4 launch', -12, 20),     # Started 12 days ago, ongoing
                ('Monthly performance report', -4, 8),           # Started 4 days ago
            ],
            'Planning': [
                # Planning phase (near future)
                ('Q3 Email newsletter schedule', 2, 6),          # Will start planning in 2 days
            ],
            'Ideas': [
                # Ideas/Backlog (future)
                ('Holiday social campaign concept', 10, 8),      # Will start in 10 days
                ('Video content strategy', 20, 10),              # Will start in 20 days
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
        offset_counter = 30  # Start future tasks
        for task in all_tasks_dict.values():
            if task not in scheduled_tasks:
                col_name = task.column.name
                
                # Assign default dates based on column
                if col_name.lower() in ['done', 'closed', 'completed']:
                    start_offset = -35 - (offset_counter % 10)
                    duration = 7
                elif col_name.lower() in ['review', 'testing']:
                    start_offset = -8
                    duration = 5
                elif col_name.lower() in ['in progress', 'working']:
                    start_offset = -10
                    duration = 12
                elif col_name.lower() in ['planning', 'to do']:
                    start_offset = 3
                    duration = 6
                else:  # Ideas or Backlog
                    start_offset = offset_counter
                    duration = 8
                    offset_counter += 12  # Space out ideas
                
                start_date = base_date + timedelta(days=start_offset)
                end_date = start_date + timedelta(days=duration)
                
                task.start_date = start_date
                task.due_date = datetime.combine(end_date, datetime.max.time())
                task.due_date = timezone.make_aware(task.due_date) if timezone.is_naive(task.due_date) else task.due_date
                task.save()
                
                self.stdout.write(f'    ✓ {task.title[:50]} (auto): {start_date} → {end_date}')
        
        # Create finish-to-start dependencies for marketing campaign
        # Marketing flow: Research → Planning → Execution → Review → Complete
        
        dependency_chains = [
            # Phase 1: Analysis drives planning
            ('Q3 Email newsletter schedule', ['Competitor analysis report']),
            ('Holiday social campaign concept', ['Competitor analysis report']),
            
            # Phase 2: Planning leads to execution
            ('Website redesign for Q4 launch', ['Q3 Email newsletter schedule']),
            ('Monthly performance report', ['Summer campaign graphics']),
            
            # Phase 3: Review depends on execution
            ('New product announcement email', ['Website redesign for Q4 launch']),
            
            # Phase 4: Future campaigns build on current work
            ('Video content strategy', ['New product announcement email', 'Monthly performance report']),
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
