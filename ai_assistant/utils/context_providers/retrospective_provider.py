"""
Retrospective Context Provider — retrospectives, lessons learned, action items.
"""

import logging
from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class RetrospectiveContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Retrospectives'
    FEATURE_TAGS = [
        'retrospective', 'retro', 'lesson', 'lessons learned',
        'improvement', 'what went well', 'what went wrong',
        'action item', 'retrospective action', 'sprint review',
        'post mortem', 'scope autopsy',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        try:
            from kanban.retrospective_models import ProjectRetrospective
        except ImportError:
            return ''

        if board:
            retros = ProjectRetrospective.objects.filter(board=board)
        else:
            accessible = self._get_accessible_boards(user, is_demo_mode)
            retros = ProjectRetrospective.objects.filter(board__in=accessible)

        count = retros.count()
        if count == 0:
            return '🔄 **Retrospectives:** None recorded.\n'

        latest = retros.order_by('-created_at').first()
        latest_str = ''
        if latest:
            latest_str = f' Latest: "{latest.title}" ({latest.status})'

        return f'🔄 **Retrospectives:** {count} recorded.{latest_str}\n'

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        try:
            from kanban.retrospective_models import (
                ProjectRetrospective,
                RetrospectiveActionItem,
                LessonLearned,
            )
        except ImportError:
            return ''

        if board:
            retros = ProjectRetrospective.objects.filter(board=board)
        else:
            accessible = self._get_accessible_boards(user, is_demo_mode)
            retros = ProjectRetrospective.objects.filter(board__in=accessible)

        if not retros.exists():
            return '**🔄 Retrospectives:** None recorded.\n'

        ctx = f'**🔄 Retrospectives ({retros.count()}):**\n'

        for retro in retros.order_by('-created_at')[:5]:
            ctx += f'\n  **{retro.title}** ({retro.retrospective_type}, {retro.status})\n'
            if retro.period_start and retro.period_end:
                ctx += f'  Period: {retro.period_start} — {retro.period_end}\n'

            if retro.what_went_well:
                ctx += f'  ✅ What went well: {retro.what_went_well[:200]}\n'
            if retro.what_needs_improvement:
                ctx += f'  ⚠️ Needs improvement: {retro.what_needs_improvement[:200]}\n'
            if retro.lessons_learned:
                ctx += f'  📝 Lessons: {retro.lessons_learned[:200]}\n'

            # Action items
            try:
                actions = RetrospectiveActionItem.objects.filter(retrospective=retro)[:5]
                if actions:
                    ctx += '  Action Items:\n'
                    for a in actions:
                        status_icon = '✅' if a.status == 'completed' else '⏳'
                        ctx += f'    {status_icon} {a.title}'
                        if hasattr(a, 'assigned_to') and a.assigned_to:
                            name = a.assigned_to.get_full_name() or a.assigned_to.username
                            ctx += f' → {name}'
                        ctx += '\n'
            except Exception:
                pass

        # Lessons learned
        try:
            if board:
                lessons = LessonLearned.objects.filter(retrospective__board=board)
            else:
                lessons = LessonLearned.objects.filter(
                    retrospective__board__in=self._get_accessible_boards(user, is_demo_mode)
                )
            if lessons.exists():
                ctx += f'\n**📝 Lessons Learned ({lessons.count()}):**\n'
                for l in lessons.order_by('-created_at')[:10]:
                    ctx += f'  • {l.title}: {l.description[:100]}\n'
        except Exception:
            pass

        return ctx


registry.register(RetrospectiveContextProvider())
