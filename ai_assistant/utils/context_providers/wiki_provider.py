"""
Wiki Context Provider — wiki pages, knowledge base.
"""

import logging
from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class WikiContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Wiki'
    FEATURE_TAGS = [
        'wiki', 'documentation', 'docs', 'guide', 'knowledge base',
        'article', 'page', 'how to', 'instructions', 'reference',
        'knowledge', 'kb', 'meeting notes', 'meeting',
    ]

    def _wiki_pages_for(self, user, is_demo_mode):
        """Published wiki pages scoped like the app's wiki_scope_q.

        WikiPage is workspace-scoped (the tenant boundary), but the shared demo
        workspace isolates per user via sandbox_owner (each demo user gets their
        own wiki clones). Scope to the user's own clones in demo so Spectra never
        surfaces another demo user's — or the shared template's — wiki content.
        """
        from wiki.models import WikiPage
        if is_demo_mode:
            return WikiPage.objects.filter(sandbox_owner=user, is_published=True)
        ws = self._get_user_workspace(user)
        if ws is not None:
            return WikiPage.objects.filter(
                workspace=ws, sandbox_owner__isnull=True, is_published=True,
            )
        return WikiPage.objects.none()

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        try:
            pages = self._wiki_pages_for(user, is_demo_mode)
        except ImportError:
            return ''

        count = pages.count()
        if count == 0:
            return '📚 **Wiki:** No published pages.\n'

        categories = pages.values_list('category__name', flat=True).distinct()
        cat_list = [c for c in categories if c][:5]
        cat_str = f' Categories: {", ".join(cat_list)}' if cat_list else ''

        return f'📚 **Wiki:** {count} published page(s).{cat_str}\n'

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        try:
            pages = self._wiki_pages_for(user, is_demo_mode)
        except ImportError:
            return ''

        if not pages.exists():
            return '**📚 Wiki:** No published pages.\n'

        # If user has a specific query, search for relevant pages
        query_lower = query.lower()
        if query_lower:
            relevant = pages.filter(
                title__icontains=query_lower
            ) | pages.filter(
                content__icontains=query_lower
            )
            if relevant.exists():
                pages = relevant

        ctx = f'**📚 Wiki Pages ({pages.count()}):**\n'
        for page in pages.order_by('-updated_at')[:15]:
            ctx += f'  • **{page.title}**'
            if page.category:
                ctx += f' [{page.category}]'
            ctx += '\n'
            if page.content:
                # Include content excerpt for relevant pages
                content_preview = page.content[:200].replace('\n', ' ')
                ctx += f'    {content_preview}\n'

        # Knowledge base entries
        try:
            from ai_assistant.models import ProjectKnowledgeBase
            if board:
                kb = ProjectKnowledgeBase.objects.filter(board=board, is_active=True)
            else:
                kb = ProjectKnowledgeBase.objects.filter(
                    board__in=self._get_accessible_boards(user, is_demo_mode),
                    is_active=True,
                )
            if kb.exists():
                ctx += f'\n**Knowledge Base ({kb.count()} entries):**\n'
                for entry in kb[:10]:
                    ctx += f'  • {entry.topic}: {entry.content[:100]}\n'
        except (ImportError, Exception):
            pass

        return ctx


registry.register(WikiContextProvider())
