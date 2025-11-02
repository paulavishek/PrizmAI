"""
Management command to fix ALL Gantt chart dependencies for complete project flow.
This ensures every task has proper dependencies for a realistic project timeline.
"""

from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from kanban.models import Board, Task


class Command(BaseCommand):
    help = 'Fix ALL Gantt chart dependencies to show complete project flow with dependency arrows'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('='*70))
        self.stdout.write(self.style.NOTICE('Fixing ALL Gantt Chart Dependencies'))
        self.stdout.write(self.style.NOTICE('='*70))
        
        # Process Software Project board
        try:
            board = Board.objects.get(name='Software Project')
            self.stdout.write(self.style.SUCCESS(f'\n📊 Processing Board: {board.name}'))
            self.fix_software_project_complete(board)
        except Board.DoesNotExist:
            self.stdout.write(self.style.ERROR('Software Project board not found.'))
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('✅ All Dependencies Fixed!'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))

    def fix_software_project_complete(self, board):
        """Fix Software Project board with complete dependency chain"""
        
        # Get all tasks ordered by start date
        tasks = Task.objects.filter(
            column__board=board,
            start_date__isnull=False,
            due_date__isnull=False
        ).order_by('start_date')
        
        if not tasks.exists():
            self.stdout.write(self.style.WARNING('  No tasks found'))
            return
        
        self.stdout.write(f'  Found {tasks.count()} tasks')
        
        # Clear all existing dependencies
        self.stdout.write('  Clearing existing dependencies...')
        for task in tasks:
            task.dependencies.clear()
        
        # Create a mapping of task titles to objects (case-insensitive partial matching)
        task_map = {}
        for task in tasks:
            task_map[task.title.lower()] = task
        
        def find_task(pattern):
            """Find task by partial match"""
            pattern = pattern.lower()
            for title, task in task_map.items():
                if pattern in title:
                    return task
            return None
        
        def add_dependency(task_pattern, dep_patterns):
            """Add dependencies with validation"""
            task = find_task(task_pattern)
            if not task:
                self.stdout.write(self.style.WARNING(f'  ⚠ Task not found: {task_pattern}'))
                return
            
            for dep_pattern in dep_patterns if isinstance(dep_patterns, list) else [dep_patterns]:
                dep_task = find_task(dep_pattern)
                if not dep_task:
                    self.stdout.write(self.style.WARNING(f'  ⚠ Dependency not found: {dep_pattern}'))
                    continue
                
                # Validate dates (predecessor must end before successor starts)
                if dep_task.due_date.date() <= task.start_date:
                    task.dependencies.add(dep_task)
                    self.stdout.write(f'  ✓ {task.title[:35]:35} ← {dep_task.title[:35]}')
                else:
                    self.stdout.write(self.style.WARNING(
                        f'  ⚠ Date conflict: {task.title[:30]} cannot depend on {dep_task.title[:30]}'
                    ))
        
        # Define complete project dependency flow
        self.stdout.write('\n  Creating comprehensive dependency chain...\n')
        
        # Phase 1: Project Setup (Foundation)
        self.stdout.write(self.style.NOTICE('  Phase 1: Project Foundation'))
        add_dependency('ui mockup', 'setup project repository')
        add_dependency('authentication middleware', 'setup project repository')
        add_dependency('remove legacy', 'setup project repository')
        
        # Phase 2: Core Development
        self.stdout.write(self.style.NOTICE('\n  Phase 2: Core Development'))
        add_dependency('dashboard layout', ['ui mockup', 'authentication middleware'])
        add_dependency('homepage design', 'dashboard layout')
        
        # Phase 3: Component Development
        self.stdout.write(self.style.NOTICE('\n  Phase 3: Component Development'))
        add_dependency('component library', 'homepage design')
        add_dependency('project planning', 'ui mockup')
        
        # Phase 4: Backend Development
        self.stdout.write(self.style.NOTICE('\n  Phase 4: Backend Development'))
        add_dependency('database schema', 'setup project repository')
        add_dependency('user authentication', ['database schema', 'authentication middleware'])
        add_dependency('backend api', 'user authentication')
        
        # Phase 5: Advanced Features
        self.stdout.write(self.style.NOTICE('\n  Phase 5: Advanced Features'))
        add_dependency('frontend ui', ['component library', 'backend api'])
        add_dependency('ci/cd pipeline', 'user authentication')
        
        # Phase 6: Documentation & Testing
        self.stdout.write(self.style.NOTICE('\n  Phase 6: Documentation & Testing'))
        add_dependency('documentation', ['component library', 'backend api'])
        add_dependency('testing', ['frontend ui', 'backend api'])
        
        # Phase 7: Deployment
        self.stdout.write(self.style.NOTICE('\n  Phase 7: Deployment'))
        add_dependency('deployment', ['testing', 'ci/cd pipeline', 'documentation'])
        
        # Count total dependencies
        total_deps = sum(task.dependencies.count() for task in tasks)
        self.stdout.write(self.style.SUCCESS(f'\n  ✅ Created {total_deps} dependencies across {tasks.count()} tasks'))
        
        # Show tasks without dependencies (should only be the first task)
        tasks_without_deps = [t for t in tasks if t.dependencies.count() == 0]
        if tasks_without_deps:
            self.stdout.write(f'\n  Tasks without dependencies (starting points):')
            for task in tasks_without_deps:
                self.stdout.write(f'    • {task.title}')
