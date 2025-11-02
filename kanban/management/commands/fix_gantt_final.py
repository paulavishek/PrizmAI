"""
Final fix for Gantt chart: Remove duplicates and adjust dates for proper dependency flow
"""

from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from kanban.models import Board, Task


class Command(BaseCommand):
    help = 'Remove duplicate tasks and adjust dates for perfect Gantt chart display'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('='*70))
        self.stdout.write(self.style.NOTICE('Final Gantt Chart Fix - Removing Duplicates & Adjusting Dates'))
        self.stdout.write(self.style.NOTICE('='*70))
        
        try:
            board = Board.objects.get(name='Software Project')
            self.fix_final_gantt_issues(board)
        except Board.DoesNotExist:
            self.stdout.write(self.style.ERROR('Software Project board not found.'))
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('✅ Final Gantt Chart Fix Complete!'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))

    def fix_final_gantt_issues(self, board):
        """Remove duplicates and adjust dates"""
        
        # Find and handle duplicate "Design database schema" tasks
        db_tasks = Task.objects.filter(
            column__board=board,
            title__icontains='design database'
        ).order_by('start_date')
        
        if db_tasks.count() > 1:
            self.stdout.write(f'\n  Found {db_tasks.count()} "Design database schema" tasks')
            # Keep the earlier one, remove the later duplicate
            for task in db_tasks[1:]:
                self.stdout.write(f'  🗑️  Removing duplicate: {task.title} (ID: {task.id})')
                task.delete()
        
        # Get all remaining tasks
        tasks = Task.objects.filter(
            column__board=board,
            start_date__isnull=False,
            due_date__isnull=False
        ).order_by('start_date')
        
        self.stdout.write(f'\n  Total tasks after cleanup: {tasks.count()}')
        
        # Adjust dates to fix conflicts
        base_date = timezone.now().date()
        
        # Define the perfect timeline
        task_schedule = {
            # PAST - Completed
            'setup project repository': (-35, 3),
            'create ui mockups': (-28, 5),
            'remove legacy code': (-20, 2),
            
            # PAST/RECENT - In Progress
            'setup authentication middleware': (-15, 12),  # Extended duration
            'implement dashboard layout': (-10, 10),
            
            # RECENT - Review
            'review homepage design': (-3, 4),
            'project planning': (-2, 6),
            
            # NEAR FUTURE - To Do
            'create component library': (2, 8),
            'write documentation': (11, 7),
            
            # FUTURE - Backlog Phase 1
            'design database': (20, 6),
            'implement user authentication': (27, 9),
            'setup ci/cd pipeline': (37, 5),
            
            # FUTURE - Backlog Phase 2
            'implement backend api': (43, 7),
            'create frontend ui': (51, 8),
            
            # FUTURE - Final Phase
            'testing and qa': (60, 7),
            'deployment': (68, 5),
        }
        
        self.stdout.write('\n  Adjusting task dates for perfect dependency flow...\n')
        
        for task in tasks:
            task_key = task.title.lower()[:20]  # Use first 20 chars for matching
            
            # Find matching schedule
            schedule_found = False
            for pattern, (start_offset, duration) in task_schedule.items():
                if pattern in task_key:
                    start_date = base_date + timedelta(days=start_offset)
                    end_date = start_date + timedelta(days=duration)
                    
                    # Only update if dates are different
                    if task.start_date != start_date or task.due_date.date() != end_date:
                        task.start_date = start_date
                        task.due_date = datetime.combine(end_date, datetime.max.time())
                        task.due_date = timezone.make_aware(task.due_date) if timezone.is_naive(task.due_date) else task.due_date
                        task.save()
                        self.stdout.write(f'  ✓ {task.title[:40]:40} | {start_date} → {end_date}')
                    schedule_found = True
                    break
            
            if not schedule_found:
                self.stdout.write(f'  ℹ️  Kept existing dates: {task.title[:40]}')
        
        # Now rebuild dependencies with corrected dates
        self.stdout.write('\n  Rebuilding dependencies with corrected dates...\n')
        
        # Clear all dependencies
        for task in tasks:
            task.dependencies.clear()
        
        # Refresh tasks
        tasks = Task.objects.filter(
            column__board=board,
            start_date__isnull=False,
            due_date__isnull=False
        ).order_by('start_date')
        
        # Helper function
        def find_task(pattern):
            pattern = pattern.lower()
            for task in tasks:
                if pattern in task.title.lower():
                    return task
            return None
        
        def add_dep(task_pattern, dep_patterns):
            task = find_task(task_pattern)
            if not task:
                return
            
            for dep_pattern in (dep_patterns if isinstance(dep_patterns, list) else [dep_patterns]):
                dep_task = find_task(dep_pattern)
                if dep_task and dep_task.due_date.date() <= task.start_date:
                    task.dependencies.add(dep_task)
                    self.stdout.write(f'  → {task.title[:30]:30} depends on {dep_task.title[:30]}')
        
        # Perfect dependency chain
        add_dep('ui mockup', 'setup project')
        add_dep('authentication middleware', 'setup project')
        add_dep('remove legacy', 'setup project')
        add_dep('dashboard layout', ['ui mockup', 'authentication middleware'])
        add_dep('homepage design', 'dashboard layout')
        add_dep('project planning', 'ui mockup')
        add_dep('component library', 'homepage design')
        add_dep('design database', 'setup project')
        add_dep('user authentication', ['design database', 'authentication middleware'])
        add_dep('ci/cd pipeline', 'user authentication')
        add_dep('backend api', 'user authentication')
        add_dep('frontend ui', ['component library', 'backend api'])
        add_dep('documentation', ['component library', 'user authentication'])
        add_dep('testing', ['frontend ui', 'backend api'])
        add_dep('deployment', ['testing', 'ci/cd', 'documentation'])
        
        # Final summary
        total_deps = sum(task.dependencies.count() for task in tasks)
        self.stdout.write(self.style.SUCCESS(f'\n  ✅ Total: {tasks.count()} tasks, {total_deps} dependencies'))
