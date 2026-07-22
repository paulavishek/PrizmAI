"""
Task Aging Context Provider — how long tasks have sat untouched in their column.

Answers "which tasks are stalling?" / "what's been stuck the longest?" using the
SAME signal as the card aging badge: Task.aging_state() (column dwell time vs. the
per-column effective thresholds). Numbers here always match the badges on the board
because both go through Task.aging_state() — never re-derive from created/updated_at.
"""

import logging
from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class TaskAgingContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Task Aging'
    FEATURE_TAGS = [
        'aging', 'aging badge', 'stalled', 'stalling', 'stuck', 'idle',
        'how long', 'days in column', 'sitting', 'no movement', 'not moving',
        'oldest task', 'longest in column', 'wip age', 'dwell', 'gathering dust',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        if not board:
            return ''

        from kanban.models import Task

        # warning+ tier = amber or red badge on the board.
        stalled = Task.stalled_for_boards([board.id], tier='warning')
        if not stalled:
            return '🕐 **Task Aging:** No tasks past their aging threshold.\n'

        critical = sum(1 for t in stalled if t.aging_tier == 'critical')
        warning = len(stalled) - critical
        bits = []
        if critical:
            bits.append(f'{critical} critical (red)')
        if warning:
            bits.append(f'{warning} warning (amber)')
        oldest = stalled[0]
        return (
            f'🕐 **Task Aging:** {", ".join(bits)}. '
            f'Oldest: "{oldest.title}" — {oldest.days_in_column}d in {oldest.column.name}.\n'
        )

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        if not board:
            return None

        from kanban.models import Task

        stalled = Task.stalled_for_boards([board.id], tier='warning')
        if not stalled:
            # Distinguish "feature on, nothing stalled" from "feature off entirely".
            any_enabled = any(c.effective_aging()['enabled'] for c in board.columns.all())
            if not any_enabled:
                return None
            return (
                f'**🕐 Task Aging — {board.name}:** Aging alerts are on, but no task '
                f'has crossed its warning threshold. Nothing is stalling right now.\n'
            )

        critical = [t for t in stalled if t.aging_tier == 'critical']
        warning = [t for t in stalled if t.aging_tier == 'warning']

        ctx = f'**🕐 Task Aging Analysis — {board.name}:**\n'
        ctx += (
            'Badges count days a task has sat in its CURRENT column (the count resets '
            'when the task moves). Thresholds are per-column; below each task is its '
            'column-specific warning/critical day count.\n'
        )

        if critical:
            ctx += f'\n**🔴 Critical — past the red threshold ({len(critical)}):**\n'
            for t in critical[:15]:
                assignee = (t.assigned_to.get_full_name() or t.assigned_to.username) if t.assigned_to else 'Unassigned'
                state = t.aging_state()
                ctx += (
                    f'  • {t.title} — {t.days_in_column}d in {t.column.name} '
                    f'(critical at {state["critical"]}d) — {assignee}\n'
                )

        if warning:
            ctx += f'\n**🟠 Warning — past the amber threshold ({len(warning)}):**\n'
            for t in warning[:15]:
                assignee = (t.assigned_to.get_full_name() or t.assigned_to.username) if t.assigned_to else 'Unassigned'
                state = t.aging_state()
                ctx += (
                    f'  • {t.title} — {t.days_in_column}d in {t.column.name} '
                    f'(warning at {state["warning"]}d) — {assignee}\n'
                )

        return ctx


registry.register(TaskAgingContextProvider())
