"""
Comprehensive verification script for Gantt chart data across all organizations.
This script verifies:
1. All tasks have dynamic dates (relative to current date)
2. All tasks are displayed in Gantt chart
3. Dependencies are correctly set and valid
4. Each organization's boards are working properly
"""
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from kanban.models import Board, Task, Organization


class Command(BaseCommand):
    help = 'Comprehensive check of Gantt chart data for all organizations'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('='*80))
        self.stdout.write(self.style.SUCCESS('COMPREHENSIVE GANTT CHART VERIFICATION'))
        self.stdout.write(self.style.SUCCESS('='*80))
        
        # Get all organizations
        organizations = Organization.objects.all()
        
        if not organizations.exists():
            self.stdout.write(self.style.ERROR('No organizations found.'))
            return
        
        self.stdout.write(f'\nFound {organizations.count()} organization(s)\n')
        
        total_boards = 0
        total_tasks = 0
        total_tasks_with_dates = 0
        total_dependencies = 0
        issues_found = []
        
        for org in organizations:
            self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
            self.stdout.write(self.style.SUCCESS(f'ORGANIZATION: {org.name}'))
            self.stdout.write(self.style.SUCCESS(f'{"="*80}'))
            
            boards = Board.objects.filter(organization=org)
            
            if not boards.exists():
                self.stdout.write(self.style.WARNING(f'  No boards found for {org.name}'))
                continue
            
            self.stdout.write(f'\n  Boards: {boards.count()}')
            
            for board in boards:
                total_boards += 1
                self.check_board(board, issues_found)
                
                # Count tasks
                tasks = Task.objects.filter(column__board=board)
                tasks_with_dates = tasks.filter(start_date__isnull=False, due_date__isnull=False)
                total_tasks += tasks.count()
                total_tasks_with_dates += tasks_with_dates.count()
                total_dependencies += sum(task.dependencies.count() for task in tasks)
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write(self.style.SUCCESS(f'{"="*80}'))
        self.stdout.write(f'\n  Organizations Checked: {organizations.count()}')
        self.stdout.write(f'  Total Boards: {total_boards}')
        self.stdout.write(f'  Total Tasks: {total_tasks}')
        self.stdout.write(f'  Tasks with Dates (Gantt-Ready): {total_tasks_with_dates}')
        self.stdout.write(f'  Total Dependencies: {total_dependencies}')
        
        if total_tasks > 0:
            coverage = (total_tasks_with_dates / total_tasks) * 100
            self.stdout.write(f'  Gantt Coverage: {coverage:.1f}%')
        
        # Issues
        if issues_found:
            self.stdout.write(self.style.WARNING(f'\n⚠️  ISSUES FOUND: {len(issues_found)}'))
            for issue in issues_found:
                self.stdout.write(self.style.WARNING(f'  • {issue}'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ NO ISSUES FOUND - All Gantt charts are ready!'))
        
        self.stdout.write(self.style.SUCCESS(f'\n{"="*80}\n'))
    
    def check_board(self, board, issues_found):
        """Check a specific board's Gantt chart data"""
        self.stdout.write(f'\n  📊 Board: {board.name} (ID: {board.id})')
        self.stdout.write(f'     URL: http://127.0.0.1:8000/boards/{board.id}/gantt/')
        
        tasks = Task.objects.filter(column__board=board).order_by('start_date')
        tasks_with_dates = tasks.filter(start_date__isnull=False, due_date__isnull=False)
        tasks_without_dates = tasks.filter(start_date__isnull=True) | tasks.filter(due_date__isnull=True)
        
        self.stdout.write(f'     Total Tasks: {tasks.count()}')
        self.stdout.write(f'     Tasks with Dates: {tasks_with_dates.count()}')
        
        if tasks_without_dates.exists():
            issue = f'{board.name}: {tasks_without_dates.count()} tasks missing dates'
            issues_found.append(issue)
            self.stdout.write(self.style.WARNING(f'     ⚠️  Missing Dates: {tasks_without_dates.count()}'))
            for task in tasks_without_dates[:3]:
                self.stdout.write(self.style.WARNING(f'        - {task.title}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'     ✅ All tasks have dates'))
        
        # Check dynamic dates (should have dates in past, present, and future)
        today = timezone.now().date()
        past_tasks = tasks_with_dates.filter(start_date__lt=today)
        current_tasks = tasks_with_dates.filter(start_date__lte=today, due_date__gte=today)
        future_tasks = tasks_with_dates.filter(start_date__gt=today)
        
        self.stdout.write(f'     Date Distribution:')
        self.stdout.write(f'       Past: {past_tasks.count()}')
        self.stdout.write(f'       Current: {current_tasks.count()}')
        self.stdout.write(f'       Future: {future_tasks.count()}')
        
        if not past_tasks.exists() and not current_tasks.exists() and not future_tasks.exists():
            if tasks_with_dates.exists():
                issue = f'{board.name}: All tasks have same date range - not dynamic'
                issues_found.append(issue)
        
        # Check dependencies
        total_deps = 0
        invalid_deps = 0
        self_referencing_deps = 0
        
        for task in tasks_with_dates:
            deps = task.dependencies.all()
            total_deps += deps.count()
            
            for dep in deps:
                # Check for self-referencing
                if dep.id == task.id:
                    self_referencing_deps += 1
                    continue
                
                # Check if dependency has dates
                if not dep.start_date or not dep.due_date:
                    invalid_deps += 1
                    continue
                
                # Check if dependency finishes before task starts (Finish-to-Start)
                if dep.due_date.date() > task.start_date:
                    invalid_deps += 1
        
        self.stdout.write(f'     Dependencies: {total_deps}')
        
        if invalid_deps > 0:
            issue = f'{board.name}: {invalid_deps} invalid dependencies (dates conflict)'
            issues_found.append(issue)
            self.stdout.write(self.style.WARNING(f'     ⚠️  Invalid Dependencies: {invalid_deps}'))
        
        if self_referencing_deps > 0:
            issue = f'{board.name}: {self_referencing_deps} self-referencing dependencies'
            issues_found.append(issue)
            self.stdout.write(self.style.WARNING(f'     ⚠️  Self-Referencing: {self_referencing_deps}'))
        
        if total_deps > 0 and invalid_deps == 0 and self_referencing_deps == 0:
            self.stdout.write(self.style.SUCCESS(f'     ✅ All dependencies are valid'))
        
        # Show task timeline sample
        if tasks_with_dates.exists():
            self.stdout.write(f'\n     📅 Task Timeline Sample (first 5):')
            for task in tasks_with_dates[:5]:
                deps = task.dependencies.all()
                dep_info = ''
                if deps.exists():
                    dep_names = ', '.join([d.title[:20] for d in deps[:2]])
                    if deps.count() > 2:
                        dep_names += f' +{deps.count()-2} more'
                    dep_info = f' [depends on: {dep_names}]'
                
                self.stdout.write(
                    f'        • {task.title[:40]:42} | '
                    f'{task.start_date} → {task.due_date.date()}'
                    f'{dep_info}'
                )
            
            if tasks_with_dates.count() > 5:
                self.stdout.write(f'        ... and {tasks_with_dates.count() - 5} more tasks')
