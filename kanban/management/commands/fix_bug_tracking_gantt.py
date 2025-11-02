"""
Management command to fix Bug Tracking board Gantt chart with realistic bug workflow
"""

from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from kanban.models import Board, Task


class Command(BaseCommand):
    help = 'Fix Bug Tracking board Gantt chart with comprehensive dependencies and realistic timeline'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('='*70))
        self.stdout.write(self.style.NOTICE('Fixing Bug Tracking Board Gantt Chart'))
        self.stdout.write(self.style.NOTICE('='*70))
        
        try:
            board = Board.objects.get(name='Bug Tracking')
            self.fix_bug_tracking_board(board)
        except Board.DoesNotExist:
            self.stdout.write(self.style.ERROR('Bug Tracking board not found.'))
            return
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('✅ Bug Tracking Gantt Chart Fixed!'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))

    def fix_bug_tracking_board(self, board):
        """Fix Bug Tracking board with realistic bug resolution workflow"""
        
        self.stdout.write(f'\n📊 Processing: {board.name}')
        
        # Get all tasks
        tasks = Task.objects.filter(
            column__board=board,
            start_date__isnull=False,
            due_date__isnull=False
        ).order_by('start_date')
        
        if not tasks.exists():
            self.stdout.write(self.style.WARNING('  No tasks found'))
            return
        
        self.stdout.write(f'  Found {tasks.count()} tasks')
        
        # Clear existing dependencies
        self.stdout.write('  Clearing existing dependencies...')
        for task in tasks:
            task.dependencies.clear()
        
        # Define realistic bug tracking timeline
        # Base date is current date
        base_date = timezone.now().date()
        
        # Define comprehensive bug workflow with better spacing
        # Format: (task_title_pattern, start_offset_days, duration_days)
        task_schedule = {
            # PAST - Critical bugs fixed first
            'error 500': (-30, 5),          # Critical bug - fixed 30 days ago, took 5 days
            'typo': (-22, 2),                # Minor bug - fixed 22 days ago, quick fix
            
            # RECENT PAST - Investigation started
            'inconsistent data': (-18, 10),  # Major bug - under investigation, finished 8 days ago
            
            # CURRENT - Active work (depends on investigation)
            'pagination': (-6, 8),           # Testing phase - started 6 days ago
            'button alignment': (-4, 7),     # Being fixed - started 4 days ago
            
            # NEAR FUTURE - Newly reported (depends on current work)
            'login page': (4, 6),            # Will be reported in 4 days, 6 days to fix
            'slow response': (11, 7),        # Will be reported in 11 days, 7 days to fix
        }
        
        # Apply dates
        self.stdout.write('\n  Adjusting task dates for realistic bug workflow...\n')
        
        task_objects = {}
        for task in tasks:
            task_key = task.title.lower()
            
            # Find matching schedule
            for pattern, (start_offset, duration) in task_schedule.items():
                if pattern in task_key:
                    start_date = base_date + timedelta(days=start_offset)
                    end_date = start_date + timedelta(days=duration)
                    
                    task.start_date = start_date
                    task.due_date = datetime.combine(end_date, datetime.max.time())
                    task.due_date = timezone.make_aware(task.due_date) if timezone.is_naive(task.due_date) else task.due_date
                    task.save()
                    
                    task_objects[pattern] = task
                    self.stdout.write(f'  ✓ {task.title[:45]:45} | {start_date} → {end_date}')
                    break
        
        # Refresh tasks
        tasks = Task.objects.filter(
            column__board=board,
            start_date__isnull=False,
            due_date__isnull=False
        ).order_by('start_date')
        
        # Helper function to find task
        def find_task(pattern):
            pattern = pattern.lower()
            for task in tasks:
                if pattern in task.title.lower():
                    return task
            return None
        
        # Helper function to add dependency
        def add_dep(task_pattern, dep_patterns):
            task = find_task(task_pattern)
            if not task:
                self.stdout.write(self.style.WARNING(f'  ⚠ Task not found: {task_pattern}'))
                return
            
            for dep_pattern in (dep_patterns if isinstance(dep_patterns, list) else [dep_patterns]):
                dep_task = find_task(dep_pattern)
                if dep_task and dep_task.due_date.date() <= task.start_date:
                    task.dependencies.add(dep_task)
                    self.stdout.write(f'  → {task.title[:35]:35} depends on {dep_task.title[:35]}')
                elif dep_task:
                    self.stdout.write(self.style.WARNING(
                        f'  ⚠ Date conflict: {task.title[:25]} -> {dep_task.title[:25]}'
                    ))
        
        # Create realistic bug tracking dependencies
        self.stdout.write('\n  Creating bug workflow dependencies...\n')
        
        # Bug Resolution Flow:
        # 1. Critical bugs get fixed first and may enable other work
        # 2. Data issues must be investigated before related bugs can be fixed
        # 3. Backend fixes enable frontend fixes
        # 4. Testing follows fixes
        
        # Critical bug fixes enable investigation
        # After fixing critical upload bug, can investigate data issues
        add_dep('inconsistent data', 'error 500')
        
        # Typo fix shows system is stable for further investigation
        add_dep('inconsistent data', 'typo')
        
        # Data investigation is foundational for other bugs
        # Pagination bug testing depends on data investigation being complete
        add_dep('pagination', 'inconsistent data')
        
        # Button alignment can start after critical bugs are fixed
        add_dep('button alignment', 'typo')
        
        # Performance issue (slow response) likely stems from data problems
        add_dep('slow response', 'inconsistent data')
        
        # Login bug depends on data issues being resolved
        add_dep('login page', 'inconsistent data')
        
        # Frontend bugs (button, login) have relationship
        add_dep('login page', 'button alignment')
        
        # Performance testing should come after pagination testing
        add_dep('slow response', 'pagination')
        
        # Login issue should wait for pagination fix verification
        add_dep('login page', 'pagination')
        
        # Final summary
        total_deps = sum(task.dependencies.count() for task in tasks)
        self.stdout.write(self.style.SUCCESS(f'\n  ✅ Total: {tasks.count()} tasks, {total_deps} dependencies'))
        
        # Show tasks without dependencies (starting points)
        tasks_without_deps = [t for t in tasks if t.dependencies.count() == 0]
        if tasks_without_deps:
            self.stdout.write(f'\n  Starting points (no dependencies):')
            for task in tasks_without_deps:
                self.stdout.write(f'    • {task.title} ({task.column.name})')
