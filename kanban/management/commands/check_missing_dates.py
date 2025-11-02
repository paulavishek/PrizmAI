"""
Management command to check and fix any tasks still missing dates
"""
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from kanban.models import Board, Task


class Command(BaseCommand):
    help = 'Check and fix tasks missing start_date or due_date'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Checking for tasks missing dates...'))
        
        # Check both boards
        boards = Board.objects.filter(name__in=['Software Project', 'Bug Tracking'])
        
        for board in boards:
            self.stdout.write(f'\n📊 Board: {board.name}')
            
            # Find tasks without start_date or due_date
            all_tasks = Task.objects.filter(column__board=board)
            tasks_missing_start = all_tasks.filter(start_date__isnull=True)
            tasks_missing_due = all_tasks.filter(due_date__isnull=True)
            
            self.stdout.write(f'  Total tasks: {all_tasks.count()}')
            self.stdout.write(f'  Tasks missing start_date: {tasks_missing_start.count()}')
            self.stdout.write(f'  Tasks missing due_date: {tasks_missing_due.count()}')
            
            # Fix missing dates
            tasks_to_fix = tasks_missing_start | tasks_missing_due
            
            for task in tasks_to_fix:
                self.stdout.write(f'\n  ⚠️  Task: {task.title}')
                self.stdout.write(f'     Column: {task.column.name}')
                self.stdout.write(f'     Current - Start: {task.start_date}, Due: {task.due_date}')
                
                # Set a reasonable start date based on column if missing
                if not task.start_date:
                    if task.column.name.lower() in ['done', 'closed', 'completed']:
                        task.start_date = (timezone.now() - timedelta(days=14)).date()
                    elif task.column.name.lower() in ['review', 'testing']:
                        task.start_date = (timezone.now() - timedelta(days=2)).date()
                    elif task.column.name.lower() in ['in progress', 'investigating']:
                        task.start_date = (timezone.now() - timedelta(days=3)).date()
                    elif task.column.name.lower() in ['to do', 'new']:
                        task.start_date = (timezone.now() + timedelta(days=1)).date()
                    else:  # Backlog or other
                        task.start_date = (timezone.now() + timedelta(days=7)).date()
                
                # Set due date 5 days after start if missing
                if not task.due_date:
                    end_date = task.start_date + timedelta(days=5)
                    task.due_date = datetime.combine(end_date, datetime.max.time())
                    task.due_date = timezone.make_aware(task.due_date) if timezone.is_naive(task.due_date) else task.due_date
                
                task.save()
                self.stdout.write(self.style.SUCCESS(f'     ✅ Fixed - Start: {task.start_date}, Due: {task.due_date.date()}'))
            
            # Final verification
            tasks_complete = all_tasks.filter(start_date__isnull=False, due_date__isnull=False)
            self.stdout.write(self.style.SUCCESS(f'\n  ✅ Tasks with complete dates: {tasks_complete.count()}/{all_tasks.count()}'))
        
        self.stdout.write(self.style.SUCCESS('\n✅ All tasks checked and fixed!'))
