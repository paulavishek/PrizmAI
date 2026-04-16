"""
Analytics Context Provider — burndown, velocity, status distribution.
"""

import logging
from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class AnalyticsContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Analytics'
    FEATURE_TAGS = [
        'analytics', 'burndown', 'velocity', 'chart', 'metrics',
        'performance', 'throughput', 'cycle time', 'lead time',
        'completion rate', 'trend', 'status report', 'skill gap',
        'resource optimization', 'workload', 'utilization',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        if not board:
            return ''
        from ai_assistant.utils.spectra_data_fetchers import (
            fetch_board_tasks,
            fetch_column_distribution,
            fetch_assignee_workload,
        )

        tasks = fetch_board_tasks(board, filters={'item_type': 'task'})
        total = len(tasks)
        if total == 0:
            return '📈 **Analytics:** No tasks to analyze.\n'

        done = sum(1 for t in tasks if t['is_complete'])
        overdue = sum(1 for t in tasks if t['is_overdue'])
        pct = round(done / total * 100, 1) if total else 0

        workload = fetch_assignee_workload(board)
        busiest = max(workload.items(), key=lambda x: x[1]['count']) if workload else None
        busiest_str = f' Busiest: {busiest[0]} ({busiest[1]["count"]} tasks)' if busiest else ''

        return (
            f'📈 **Analytics:** {pct}% complete ({done}/{total}), '
            f'{overdue} overdue.{busiest_str}\n'
        )

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        if not board:
            return None

        from ai_assistant.utils.spectra_data_fetchers import (
            fetch_board_tasks,
            fetch_column_distribution,
            fetch_assignee_workload,
        )

        tasks = fetch_board_tasks(board, filters={'item_type': 'task'})
        total = len(tasks)
        done = sum(1 for t in tasks if t['is_complete'])
        overdue = sum(1 for t in tasks if t['is_overdue'])
        high_risk = sum(1 for t in tasks if t.get('risk_level') in ('high', 'critical'))
        col_dist = fetch_column_distribution(board)
        workload = fetch_assignee_workload(board)

        ctx = f'**📈 Analytics — {board.name}:**\n'
        ctx += f'  Total tasks: {total}\n'
        ctx += f'  Completed: {done} ({round(done/total*100, 1) if total else 0}%)\n'
        ctx += f'  Overdue: {overdue}\n'
        ctx += f'  High Risk: {high_risk}\n'

        # Column distribution
        ctx += '\n**Status Distribution:**\n'
        for col, cnt in col_dist:
            bar = '█' * min(cnt, 20)
            ctx += f'  {col}: {cnt} {bar}\n'

        # Workload distribution
        if workload:
            ctx += '\n**Workload by Team Member:**\n'
            for name, data in sorted(
                workload.items(), key=lambda x: x[1]['count'], reverse=True
            ):
                od = data.get('overdue_count', 0)
                od_flag = f' (⚠️ {od} overdue)' if od else ''
                ctx += f'  {name}: {data["count"]} tasks{od_flag}\n'
                if data.get('column_breakdown'):
                    parts = [f'{c}: {n}' for c, n in data['column_breakdown'].items()]
                    ctx += f'    {" | ".join(parts)}\n'

        # Priority breakdown
        pri_counts = {}
        for t in tasks:
            p = t['priority_label']
            pri_counts[p] = pri_counts.get(p, 0) + 1
        if pri_counts:
            ctx += '\n**Priority Breakdown:**\n'
            for p, c in sorted(pri_counts.items()):
                ctx += f'  {p}: {c}\n'

        return ctx


registry.register(AnalyticsContextProvider())
