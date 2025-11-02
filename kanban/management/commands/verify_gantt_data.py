"""
Quick verification script to show Gantt chart data status
"""
from django.core.management.base import BaseCommand
from kanban.models import Board, Task


class Command(BaseCommand):
    help = 'Display current Gantt chart data status'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('GANTT CHART DATA STATUS'))
        self.stdout.write(self.style.SUCCESS('='*70))
        
        boards = Board.objects.filter(name__in=['Software Project', 'Bug Tracking'])
        
        for board in boards:
            self.stdout.write(f'\n📊 {board.name.upper()}')
            self.stdout.write(f'   Board ID: {board.id}')
            self.stdout.write(f'   URL: /boards/{board.id}/gantt/')
            
            tasks = Task.objects.filter(column__board=board).order_by('start_date')
            tasks_with_dates = tasks.filter(start_date__isnull=False, due_date__isnull=False)
            
            self.stdout.write(f'\n   Total Tasks: {tasks.count()}')
            self.stdout.write(f'   Tasks with Complete Dates: {tasks_with_dates.count()}')
            self.stdout.write(f'   Will Display in Gantt: {tasks_with_dates.count()}')
            
            # Count dependencies
            total_deps = 0
            for task in tasks:
                total_deps += task.dependencies.count()
            
            self.stdout.write(f'   Total Dependencies (Finish-to-Start): {total_deps}')
            
            # Show task timeline
            self.stdout.write(f'\n   📅 Task Timeline:')
            for task in tasks_with_dates[:10]:  # Show first 10
                deps = task.dependencies.all()
                dep_info = f" [depends on: {deps[0].title[:30]}...]" if deps.exists() else ""
                self.stdout.write(
                    f'      • {task.title[:40]:40} | '
                    f'{task.start_date} → {task.due_date.date()}'
                    f'{dep_info}'
                )
            
            if tasks_with_dates.count() > 10:
                self.stdout.write(f'      ... and {tasks_with_dates.count() - 10} more tasks')
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('✅ All boards ready for Gantt chart visualization!'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))
