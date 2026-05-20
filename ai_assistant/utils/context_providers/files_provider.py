"""
Task Files Context Provider — TaskFile attachments and chat FileAttachments.

Surfaces filename + size + uploader so Spectra can answer "what files are
attached to task X?" without making up document names. Never exposes raw
file URLs (those bypass auth) — only metadata.
"""

import logging

from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class FilesContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Files & Attachments'
    FEATURE_TAGS = [
        'file', 'files', 'attachment', 'attachments', 'attached',
        'document', 'documents', 'upload', 'uploaded', 'image',
        'doc', 'docx', 'pdf', 'spreadsheet', 'attach',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        from ai_assistant.utils.spectra_data_fetchers import fetch_files_summary
        accessible = self._get_accessible_boards(user, is_demo_mode) if not board else None
        data = fetch_files_summary(board, accessible)
        if data is None or data['total'] == 0:
            return ''
        size_mb = data['total_size_bytes'] / (1024 * 1024)
        return (
            f'📎 **Files:** {data["total"]} attachments '
            f'({data["task_files"]} on tasks, {data["chat_files"]} in chat), '
            f'{size_mb:.1f} MB total.\n'
        )

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        from ai_assistant.utils.spectra_data_fetchers import fetch_files_detail
        accessible = self._get_accessible_boards(user, is_demo_mode) if not board else None
        data = fetch_files_detail(board, accessible)
        if data is None or not data['files']:
            return None

        scope = board.name if board else 'all your boards'
        ctx = f'**📎 File Attachments — {scope}**\n\n'

        by_type = data.get('by_type', {})
        if by_type:
            ctx += '**By type:** ' + ', '.join(
                f'{c} {t}' for t, c in by_type.items()
            ) + '\n\n'

        ctx += '**Recent uploads:**\n'
        for f in data['files'][:15]:
            size_kb = f['size'] / 1024
            ctx += (
                f'- `{f["filename"]}` ({f["type"]}, {size_kb:.0f} KB) '
                f'uploaded by **{f["uploaded_by"]}** on {f["when"]}'
            )
            if f.get('attached_to'):
                ctx += f' → {f["attached_to"]}'
            ctx += '\n'
            if f.get('ai_summary'):
                ctx += f'    AI: {f["ai_summary"][:160]}\n'
        return ctx


registry.register(FilesContextProvider())
