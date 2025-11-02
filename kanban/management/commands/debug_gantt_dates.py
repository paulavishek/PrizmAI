"""
Debug script to show all tasks and their dates
"""
from django.core.management.base import BaseCommand
from kanban.models import Board, Task


class Command(BaseCommand):
    help = 'Show all tasks with their exact dates for debugging'

    def handle(self, *args, **options):
        board = Board.objects.get(name='Software Project')
        tasks = Task.objects.filter(column__board=board).order_by('start_date')
        
        self.stdout.write(f'\nAll tasks in {board.name}:')
        self.stdout.write('='*80)
        
        for task in tasks:
            deps = list(task.dependencies.all())
            dep_str = f" → depends on: {deps[0].title}" if deps else ""
            
            # Check for date issues
            if task.start_date and task.due_date:
                if task.start_date > task.due_date.date():
                    status = self.style.ERROR('❌ DATE ERROR!')
                else:
                    status = self.style.SUCCESS('✓')
            else:
                status = self.style.WARNING('⚠️  Missing dates')
            
            self.stdout.write(
                f'{status} {task.title[:45]:45} | '
                f'Start: {task.start_date} | Due: {task.due_date.date() if task.due_date else "None":10} | '
                f'Column: {task.column.name:15}{dep_str}'
            )
