"""
Conflicts Context Provider — surfaces resource, schedule, and dependency
conflicts that the Conflicts tab tracks in ``kanban.conflict_models.ConflictDetection``.

Previously Spectra had no provider for this feature, so when the user asked
"are there any resource or schedule conflicts?" Spectra answered "no" even
though the Conflicts tab in the UI showed active conflicts. This provider
closes that gap.
"""

import logging

from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class ConflictsContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Conflicts'
    FEATURE_TAGS = [
        'conflict', 'conflicts', 'resource conflict', 'schedule conflict',
        'dependency conflict', 'overlap', 'double booked', 'double-booked',
        'overlap detected', 'resolution', 'collision', 'clash',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        if not board:
            return ''

        try:
            from kanban.conflict_models import ConflictDetection
        except ImportError:
            return ''

        active = ConflictDetection.objects.filter(board=board, status='active')
        total = active.count()
        if total == 0:
            return '⚖️ **Conflicts:** none active.\n'

        # By type
        by_type = {}
        for ctype, _ in ConflictDetection.CONFLICT_TYPES:
            by_type[ctype] = active.filter(conflict_type=ctype).count()
        # By severity
        critical = active.filter(severity__in=['high', 'critical']).count()

        parts = [
            f'{cnt} {ctype}' for ctype, cnt in by_type.items() if cnt
        ]
        line = f'⚖️ **Conflicts:** {total} active ({", ".join(parts)})'
        if critical:
            line += f' — {critical} high/critical'
        return line + '\n'

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        if not board:
            return None

        try:
            from kanban.conflict_models import ConflictDetection
        except ImportError:
            return None

        active = (
            ConflictDetection.objects
            .filter(board=board, status='active')
            .prefetch_related('tasks', 'affected_users')
            .order_by('-severity', '-detected_at')
        )
        if not active.exists():
            return f'**⚖️ Conflicts — {board.name}:** none active.\n'

        # Group by conflict_type so the LLM never confuses resource vs schedule.
        ctx = f'**⚖️ Conflicts — {board.name}** ({active.count()} active)\n'
        for ctype, ctype_label in ConflictDetection.CONFLICT_TYPES:
            bucket = active.filter(conflict_type=ctype)
            if not bucket.exists():
                continue
            ctx += f'\n**{ctype_label} ({bucket.count()}):**\n'
            for c in bucket[:10]:
                tasks = list(c.tasks.all()[:3])
                task_titles = ', '.join(t.title for t in tasks) or 'no tasks listed'
                if c.tasks.count() > 3:
                    task_titles += f' (+{c.tasks.count() - 3} more)'
                ctx += (
                    f'  • [{c.severity.upper()}] {c.title}\n'
                    f'    Tasks: {task_titles}\n'
                )
                if c.description:
                    ctx += f'    {c.description[:160]}\n'

        # Resolved-recent footer for context (helps when user asks "what was resolved?")
        recent_resolved = ConflictDetection.objects.filter(
            board=board, status='resolved'
        ).order_by('-resolved_at')[:3]
        if recent_resolved.exists():
            ctx += f'\n**Recently resolved (last 3):**\n'
            for c in recent_resolved:
                resolved_at = c.resolved_at.strftime('%b %d') if c.resolved_at else 'unknown'
                ctx += f'  • {c.title} [{c.get_conflict_type_display()}] — resolved {resolved_at}\n'

        return ctx


registry.register(ConflictsContextProvider())
