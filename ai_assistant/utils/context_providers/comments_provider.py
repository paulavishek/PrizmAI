"""
Comments Context Provider — task comment threads (Comment + TaskThreadComment).

Lets Spectra answer "what did people say about task X?" / "what was discussed
in the thread?" without inventing quotes.
"""

import logging

from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class CommentsContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Comments'
    FEATURE_TAGS = [
        'comment', 'comments', 'discussion', 'said', 'thread', 'reply',
        'mentioned', 'conversation', 'chatter', 'task comment', 'discussed',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        from ai_assistant.utils.spectra_data_fetchers import fetch_comments_summary
        accessible = self._get_accessible_boards(user, is_demo_mode) if not board else None
        data = fetch_comments_summary(board, accessible)
        if data is None or data['total'] == 0:
            return ''
        return (
            f'💬 **Comments:** {data["total"]} total '
            f'({data["thread_count"]} thread comments, '
            f'{data["classic_count"]} classic). '
            f'Last 7 days: {data["recent_7d"]}.\n'
        )

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        from ai_assistant.utils.spectra_data_fetchers import fetch_comments_detail
        accessible = self._get_accessible_boards(user, is_demo_mode) if not board else None
        data = fetch_comments_detail(board, accessible)
        if data is None or not data['comments']:
            return None

        scope = board.name if board else 'all your boards'
        ctx = f'**💬 Recent Comments — {scope}**\n\n'
        for c in data['comments'][:15]:
            kind = '@-thread' if c['kind'] == 'thread' else 'classic'
            ctx += (
                f'- **{c["author"]}** on `{c["task_title"]}` '
                f'({kind}, {c["when"]}):\n'
            )
            ctx += f'    {c["content_excerpt"]}\n'
        return ctx


registry.register(CommentsContextProvider())
