# kanban/management/commands/analyze_task_dependencies.py
"""
Management command to analyze tasks for suggested dependencies
"""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from kanban.models import Task, Board
from kanban.utils.dependency_suggestions import analyze_and_suggest_dependencies


class Command(BaseCommand):
    help = 'Analyze tasks for suggested dependencies using AI'

    def add_arguments(self, parser):
        parser.add_argument(
            '--board-id',
            type=int,
            help='Analyze only tasks in a specific board'
        )
        parser.add_argument(
            '--task-id',
            type=int,
            help='Analyze a specific task'
        )
        parser.add_argument(
            '--auto-link',
            action='store_true',
            help='Automatically create links to top suggestions'
        )

    def handle(self, *args, **options):
        board_id = options.get('board_id')
        task_id = options.get('task_id')
        auto_link = options.get('auto_link', False)

        # Get tasks to analyze
        if task_id:
            try:
                tasks = Task.objects.filter(id=task_id)
                if not tasks.exists():
                    raise CommandError(f"Task with ID {task_id} not found")
            except Task.DoesNotExist:
                raise CommandError(f"Task with ID {task_id} not found")
        elif board_id:
            try:
                board = Board.objects.get(id=board_id)
                tasks = Task.objects.filter(column__board=board)
                self.stdout.write(f"Analyzing {tasks.count()} tasks in board: {board.name}")
            except Board.DoesNotExist:
                raise CommandError(f"Board with ID {board_id} not found")
        else:
            tasks = Task.objects.all()
            self.stdout.write(f"Analyzing all {tasks.count()} tasks")

        # Analyze each task
        analyzed_count = 0
        for task in tasks:
            try:
                board = task.column.board if task.column else None
                result = analyze_and_suggest_dependencies(task, board, auto_link)
                
                parent_suggestions = len(result.get('parent_suggestions', []))
                related_suggestions = len(result.get('related_suggestions', []))
                confidence = result.get('confidence', 0)
                
                self.stdout.write(
                    f"[OK] Task '{task.title}': "
                    f"Found {parent_suggestions} parent suggestions, "
                    f"{related_suggestions} related tasks (confidence: {confidence})"
                )
                
                analyzed_count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"[FAIL] Error analyzing task '{task.title}': {str(e)}")
                )

        self.stdout.write(
            self.style.SUCCESS(f"\nSuccessfully analyzed {analyzed_count} tasks")
        )
