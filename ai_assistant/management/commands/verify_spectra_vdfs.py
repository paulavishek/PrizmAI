"""
Management command to verify Spectra VDF (Verified Data Fetcher) output
against the database for a specific board.

Usage:
    python manage.py verify_spectra_vdfs --board-id=78
    python manage.py verify_spectra_vdfs --board-id=78 --section milestones
    python manage.py verify_spectra_vdfs --board-id=78 --section dependencies
"""

from django.core.management.base import BaseCommand

from ai_assistant.utils.spectra_data_fetchers import (
    fetch_assignee_workload,
    fetch_board_tasks,
    fetch_column_distribution,
    fetch_dependency_graph,
    fetch_milestones,
)


class Command(BaseCommand):
    help = 'Verify Spectra VDF output for a specific board'

    def add_arguments(self, parser):
        parser.add_argument('--board-id', type=int, required=True,
                            help='Board ID to verify')
        parser.add_argument('--section', type=str, default='all',
                            choices=['all', 'tasks', 'milestones', 'columns',
                                     'dependencies', 'workload'],
                            help='Which section to display (default: all)')

    def handle(self, *args, **options):
        from kanban.models import Board

        board_id = options['board_id']
        section = options['section']

        try:
            board = Board.objects.get(id=board_id)
        except Board.DoesNotExist:
            self.stderr.write(self.style.ERROR(f'Board {board_id} not found'))
            return

        self.stdout.write(self.style.SUCCESS(
            f'\n=== VDF Verification for Board: "{board.name}" (id={board.id}) ===\n'
        ))

        if section in ('all', 'columns'):
            self._print_columns(board)
        if section in ('all', 'tasks'):
            self._print_tasks(board)
        if section in ('all', 'milestones'):
            self._print_milestones(board)
        if section in ('all', 'dependencies'):
            self._print_dependencies(board)
        if section in ('all', 'workload'):
            self._print_workload(board)

    def _print_columns(self, board):
        self.stdout.write(self.style.MIGRATE_HEADING('\n--- Column Distribution ---'))
        dist = fetch_column_distribution(board)
        total = sum(count for _, count in dist)
        for col_name, count in dist:
            self.stdout.write(f'  {col_name}: {count}')
        self.stdout.write(f'  TOTAL: {total}')

    def _print_tasks(self, board):
        self.stdout.write(self.style.MIGRATE_HEADING('\n--- All Tasks ---'))
        tasks = fetch_board_tasks(board, filters={'item_type': 'task'})
        for t in tasks:
            overdue = ' [OVERDUE]' if t['is_overdue'] else ''
            done = ' [DONE]' if t['is_complete'] else ''
            self.stdout.write(
                f"  [{t['column_name']}] {t['title']}"
                f" | Priority: {t['priority_label']}"
                f" | Assigned: {t['assigned_to_display']}"
                f" | Progress: {t['progress']}%"
                f"{overdue}{done}"
            )
        self.stdout.write(f'  TOTAL: {len(tasks)} tasks')

    def _print_milestones(self, board):
        self.stdout.write(self.style.MIGRATE_HEADING('\n--- Milestones ---'))
        milestones = fetch_milestones(board)
        if not milestones:
            self.stdout.write('  (none)')
            return
        for m in milestones:
            status = '[DONE]' if m['is_complete'] else m['column_name']
            overdue = ' [OVERDUE]' if m['is_overdue'] else ''
            due_str = str(m['due_date_date']) if m['due_date_date'] else 'No date'
            ms_status = m['milestone_status'] or 'n/a'
            self.stdout.write(
                f"  - {m['title']} [{status}] Due: {due_str}{overdue}"
                f"  (column={m['column_name']}, milestone_status={ms_status})"
            )

    def _print_dependencies(self, board):
        self.stdout.write(self.style.MIGRATE_HEADING('\n--- Dependency Graph ---'))
        graph = fetch_dependency_graph(board)
        # Sort by blocking_count descending
        sorted_nodes = sorted(graph.values(), key=lambda n: -n['blocking_count'])
        for node in sorted_nodes:
            if node['blocking_count'] > 0 or node['blocked_by']:
                blocked_titles = [b['title'] for b in node['blocking']]
                depends_titles = [b['title'] for b in node['blocked_by']]
                self.stdout.write(
                    f"  {node['title']} [{node['column_name']}]"
                    f"  BLOCKS {node['blocking_count']}: {blocked_titles}"
                    f"  DEPENDS ON: {depends_titles}"
                )

    def _print_workload(self, board):
        self.stdout.write(self.style.MIGRATE_HEADING('\n--- Assignee Workload ---'))
        workload = fetch_assignee_workload(board)
        for name, data in workload.items():
            overdue_str = f' ({data["overdue_count"]} overdue)' if data['overdue_count'] else ''
            self.stdout.write(
                f'  {name} (@{data["username"]}): {data["count"]} tasks{overdue_str}'
            )
            for col, count in data['column_breakdown'].items():
                self.stdout.write(f'      {col}: {count}')
            for task in data['tasks']:
                flag = ' [OVERDUE]' if task['is_overdue'] else ''
                self.stdout.write(
                    f"      - [{task['column_name']}] {task['title']}"
                    f" ({task['priority_label']}){flag}"
                )
