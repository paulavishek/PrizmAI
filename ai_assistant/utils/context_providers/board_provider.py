"""
Board Context Provider — tasks, columns, team members, labels.

Replaces the old get_taskflow_context() monolith with a structured,
RBAC-aware provider that fixes the 50-task display limit.
"""

import logging
from datetime import date

from django.db.models import Q
from django.utils import timezone

from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class BoardContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Board Tasks'
    FEATURE_TAGS = [
        'task', 'tasks', 'assigned', 'column', 'status', 'priority',
        'team', 'member', 'members', 'label', 'labels', 'board',
        'sprint', 'wip', 'kanban', 'unassigned', 'progress',
        'how many tasks', 'task count', 'who is assigned',
        'assignee', 'to do', 'in progress', 'done', 'backlog',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        if not board:
            return self._get_multi_board_summary(user, is_demo_mode)

        from ai_assistant.utils.spectra_data_fetchers import (
            fetch_column_distribution,
            fetch_milestones,
        )

        col_dist = fetch_column_distribution(board)
        total = sum(c for _, c in col_dist)
        milestones = fetch_milestones(board)

        if total == 0 and not milestones:
            return f'📋 **{board.name}**: 0 tasks.\n'

        # Overdue + unassigned counts
        from ai_assistant.utils.spectra_data_fetchers import fetch_board_tasks
        incomplete = fetch_board_tasks(board, filters={'item_type': 'task', 'is_complete': False})
        overdue = sum(1 for t in incomplete if t['is_overdue'])
        unassigned = sum(1 for t in incomplete if not t['assigned_to_username'])

        lines = [f'📋 **{board.name}** — {total} tasks']
        if milestones:
            lines[0] += f', {len(milestones)} milestones'
        col_parts = [f'{name}: {cnt}' for name, cnt in col_dist]
        lines.append(f'  Columns: {" | ".join(col_parts)}')
        if overdue:
            lines.append(f'  ⚠️ Overdue: {overdue}')
        if unassigned:
            lines.append(f'  📋 Unassigned: {unassigned}')
        return '\n'.join(lines) + '\n'

    def _get_multi_board_summary(self, user, is_demo_mode):
        boards = self._get_accessible_boards(user, is_demo_mode)[:10]
        if not boards.exists():
            return '📋 No boards available.\n'
        from kanban.models import Task
        lines = [f'📋 **Your Boards ({boards.count()}):**']
        for b in boards:
            cnt = Task.objects.filter(column__board=b, item_type='task').count()
            lines.append(f'  • {b.name} ({cnt} tasks)')
        return '\n'.join(lines) + '\n'

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        if not board:
            return None

        from ai_assistant.utils.spectra_data_fetchers import (
            fetch_board_tasks,
            fetch_column_distribution,
            fetch_milestones,
        )

        tasks = fetch_board_tasks(board, filters={'item_type': 'task'})
        col_dist = fetch_column_distribution(board)
        milestones = fetch_milestones(board)
        total = len(tasks)

        ctx = f'**📋 Board: {board.name}**\n'
        created = getattr(board, 'created_at', None)
        if created:
            ctx += f'Created: {created.strftime("%Y-%m-%d")}\n'
        if board.description:
            ctx += f'Description: {board.description[:200]}\n'

        # Column distribution
        ctx += f'\n**Tasks Summary ({total} total):**\n'
        for col_name, count in col_dist:
            ctx += f'  - {col_name}: {count}\n'

        # ── Smart task display (fixes 50-task limit) ────────────────────
        # Always show ALL task titles in compact format.
        # Expand full details only for query-matched tasks OR first 30.
        query_lower = query.lower()
        ctx += f'\n**All Tasks ({total}):**\n'

        expanded = 0
        for t in tasks:
            # Decide if this task gets full detail
            is_relevant = (
                expanded < 30
                or (query_lower and (
                    query_lower in t['title'].lower()
                    or query_lower in (t['assigned_to_display'] or '').lower()
                    or query_lower in t['column_name'].lower()
                ))
            )

            if is_relevant and expanded < 80:
                ctx += f'- [{t["column_name"]}] {t["title"]}\n'
                ctx += f'  • Priority: {t["priority_label"]}, Assigned: {t["assigned_to_display"]}, Progress: {t["progress"]}%\n'
                if t['description']:
                    ctx += f'  • Description: {t["description"][:150]}\n'
                if t['due_date_date']:
                    due_str = str(t['due_date_date'])
                    if t['is_overdue']:
                        due_str += f' ⚠️ OVERDUE by {t["overdue_days"]} days'
                    ctx += f'  • Due: {due_str}\n'
                if t['risk_level']:
                    # ai_risk_score can be present-but-None; show N/A, not "None".
                    score = t['ai_risk_score'] if t.get('ai_risk_score') is not None else 'N/A'
                    ctx += f'  • Risk: {t["risk_level"]} (Score: {score})\n'
                if t['dependency_titles']:
                    ctx += f'  • Dependencies: {", ".join(t["dependency_titles"][:5])}\n'
                if t['subtask_count']:
                    ctx += f'  • Has {t["subtask_count"]} subtask(s)\n'
                if t['comment_count']:
                    ctx += f'  • Comments: {t["comment_count"]}\n'
                # User-defined custom fields. Already serialized in the task dict
                # via serialize_for_ai (honors exclude_from_ai + skips empties),
                # and prefetched in fetch_board_tasks — no extra query here. This
                # is the per-task source of truth; without it Spectra fell back to
                # the board-wide recency sample (or invented values from the title).
                if t.get('custom_fields'):
                    cf = ', '.join(
                        f'{k}: {", ".join(map(str, v)) if isinstance(v, list) else v}'
                        for k, v in t['custom_fields'].items()
                    )
                    ctx += f'  • Custom fields: {cf}\n'
                # Checklist items — without these Spectra wrongly reports "no
                # checklist exists" for tasks that have one.
                if t.get('checklist'):
                    done = sum(1 for c in t['checklist'] if c['is_completed'])
                    ctx += f'  • Checklist ({done}/{len(t["checklist"])} done): '
                    ctx += '; '.join(
                        f'{"[x]" if c["is_completed"] else "[ ]"} {c["title"]}'
                        for c in t['checklist']
                    ) + '\n'
                expanded += 1
            else:
                # Compact single-line for remaining tasks
                assignee = t['assigned_to_display']
                overdue_flag = ' ⚠️' if t['is_overdue'] else ''
                ctx += f'- [{t["column_name"]}] {t["title"]} → {assignee}{overdue_flag}\n'

        # Pre-filtered "due in the next 7 days" subsection so the LLM doesn't
        # have to filter All Tasks mentally — that was producing answers with
        # tasks months out when the user asked about the next week.
        from datetime import timedelta
        from django.utils import timezone as _tz
        today = _tz.now().date()
        next_week = today + timedelta(days=7)
        due_soon = [
            t for t in tasks
            if t.get('due_date_date') and today <= t['due_date_date'] <= next_week
            and not t.get('is_complete')
        ]
        ctx += f'\n**Due in next 7 days ({len(due_soon)}):**\n'
        if not due_soon:
            ctx += '  (none)\n'
        else:
            for t in sorted(due_soon, key=lambda x: x['due_date_date']):
                ctx += f'  • {t["title"]} — due {t["due_date_date"]} — {t["assigned_to_display"]}\n'

        # Task dependencies / blocking relationships. Stated explicitly (even
        # when empty) so "which tasks are blocking?" never falls back to a
        # canned refusal for lack of context.
        blocking = [t for t in tasks if t.get('dependency_titles')]
        ctx += '\n**Task Dependencies / Blocking:**\n'
        if not blocking:
            ctx += '  No task dependencies are defined on this board (no tasks are blocking others).\n'
        else:
            for t in blocking:
                ctx += f'  • "{t["title"]}" depends on: {", ".join(t["dependency_titles"][:5])}\n'

        # Milestones
        if milestones:
            ctx += f'\n**🏁 Milestones ({len(milestones)}):**\n'
            for m in milestones:
                ms_status = '✅ Done' if m['is_complete'] else m['column_name']
                ms_due = ''
                if m['due_date_date']:
                    ms_due = f' — Due: {m["due_date_date"]}'
                    if m['is_overdue']:
                        ms_due += ' ⚠️ OVERDUE'
                ctx += f'  • {m["title"]} [{ms_status}]{ms_due}\n'

        # Team members
        from kanban.models import BoardMembership
        memberships = BoardMembership.objects.filter(
            board=board
        ).select_related('user')[:20]
        if memberships:
            ctx += f'\n**Team Members ({memberships.count()}):**\n'
            for m in memberships:
                name = m.user.get_full_name() or m.user.username
                role = m.role
                ctx += f'  - {name} ({role})\n'

        # Workflow columns
        from kanban.models import Column
        columns = Column.objects.filter(board=board).order_by('position')
        if columns.exists():
            col_names = [c.name for c in columns]
            ctx += f'\n**Workflow Columns:** {" → ".join(col_names)}\n'

        # Labels — include usage counts so the LLM can answer
        # "which label is used most" and surface duplicate labels that
        # exist at the seeded level but are not actually applied.
        from kanban.models import TaskLabel, Task
        from django.db.models import Count
        labels = (
            TaskLabel.objects.filter(board=board)
            .annotate(usage=Count('tasks', filter=Q(tasks__column__board=board)))
            .order_by('-usage', 'name')
        )
        if labels.exists():
            ctx += f'\n**Labels ({labels.count()}, sorted by usage):**\n'
            for l in labels[:25]:
                cat = f' [{l.category}]' if l.category else ''
                ctx += f'  • {l.name}{cat} — used by {l.usage} task(s)\n'

        return ctx


registry.register(BoardContextProvider())
