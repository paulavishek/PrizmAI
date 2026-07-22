"""
Knowledge Base Context Provider — always-on inventory of ProjectKnowledgeBase.

This provider does NOT replace the keyword-search retrieval in
``chatbot_service.get_knowledge_base_context`` — that path still injects the
top-N matching excerpts on demand. This provider's job is to keep Spectra
aware that a KB exists at all, so it never says "I don't have any
documentation" when there are 47 indexed pages on the board.
"""

import logging

from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class KnowledgeBaseContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Knowledge Base Inventory'
    # Intentionally narrow — detailed retrieval is handled by the keyword
    # search in chatbot_service.get_knowledge_base_context. These tags only
    # exist so the router can ask for a full breakdown of what's indexed.
    FEATURE_TAGS = [
        'knowledge base', 'knowledge-base', 'kb', 'indexed', 'index',
        'what docs', 'available docs',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        from ai_assistant.models import ProjectKnowledgeBase
        from django.db.models import Count

        qs = ProjectKnowledgeBase.objects.filter(is_active=True)
        if board:
            qs = qs.filter(board=board)
        else:
            # Cross-board mode — restrict to KB entries on accessible boards.
            accessible = self._get_accessible_boards(user, is_demo_mode)
            qs = qs.filter(board__in=accessible)

        total = qs.count()
        if total == 0:
            return ''

        breakdown = list(
            qs.values('content_type').annotate(c=Count('id')).order_by('-c')
        )
        type_label_map = dict(ProjectKnowledgeBase.CONTENT_TYPE_CHOICES)
        parts = ', '.join(
            f'{row["c"]} {type_label_map.get(row["content_type"], row["content_type"])}'
            for row in breakdown
        )
        scope = 'across your boards' if not board else ''
        prefix = f'📚 **Knowledge Base{(" " + scope) if scope else ""}:**'
        return f'{prefix} {total} entries — {parts}.\n'

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        from ai_assistant.models import ProjectKnowledgeBase

        qs = ProjectKnowledgeBase.objects.filter(is_active=True)
        if board:
            qs = qs.filter(board=board)
        else:
            accessible = self._get_accessible_boards(user, is_demo_mode)
            qs = qs.filter(board__in=accessible)

        qs = qs.only('title', 'content_type', 'updated_at', 'board_id').order_by('-updated_at')
        total = qs.count()
        if total == 0:
            return None

        title_scope = board.name if board else 'all your boards'
        ctx = f'**📚 Knowledge Base — {title_scope}** ({total} entries)\n'
        ctx += '_Spectra retrieves specific excerpts from these entries via keyword search; this list is just the inventory._\n\n'

        type_label_map = dict(ProjectKnowledgeBase.CONTENT_TYPE_CHOICES)
        by_type = {}
        for entry in qs:
            by_type.setdefault(
                type_label_map.get(entry.content_type, entry.content_type), []
            ).append(entry)

        for type_label, entries in by_type.items():
            ctx += f'**{type_label} ({len(entries)}):**\n'
            for e in entries[:8]:
                ctx += f'  - {e.title} (updated {e.updated_at:%Y-%m-%d})\n'
            if len(entries) > 8:
                ctx += f'  …and {len(entries) - 8} more\n'

        return ctx


registry.register(KnowledgeBaseContextProvider())
