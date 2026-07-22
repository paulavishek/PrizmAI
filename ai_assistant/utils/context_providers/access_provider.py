"""
Access Context Provider — pending access requests for the active board.

Surfaces AccessRequest rows so Spectra can answer "who is waiting for
access?" and "is there a pending request I should approve?" honestly.
The user only sees requests they sent OR requests they are the owner of.
"""

import logging

from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class AccessRequestsContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Access Requests'
    FEATURE_TAGS = [
        'access request', 'access requests', 'permission request', 'pending request',
        'invite', 'invitation', 'access', 'requested access', 'request access',
        'approve access', 'deny access',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        from ai_assistant.utils.spectra_data_fetchers import fetch_access_requests_summary

        data = fetch_access_requests_summary(board, user)
        if data is None or data['total_pending'] == 0:
            return ''

        parts = []
        if data['pending_as_owner']:
            parts.append(f'{data["pending_as_owner"]} awaiting your approval')
        if data['pending_by_user']:
            parts.append(f'{data["pending_by_user"]} you requested')
        return '🔐 **Access Requests:** ' + ', '.join(parts) + '.\n'

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        from ai_assistant.utils.spectra_data_fetchers import fetch_access_requests_detail

        data = fetch_access_requests_detail(board, user)
        if data is None:
            return None
        if not data['as_owner'] and not data['as_requester']:
            return None

        ctx = '**🔐 Access Requests**\n'

        if data['as_owner']:
            ctx += f'\n**Awaiting your approval ({len(data["as_owner"])}):**\n'
            for r in data['as_owner']:
                ctx += (
                    f'  - {r["requester_name"]} → board "{r["board_name"]}" '
                    f'(role: {r["requested_role"]}, trigger: {r["trigger"]}, '
                    f'{r["created_at"]})\n'
                )
                if r['message']:
                    ctx += f'    Message: {r["message"][:200]}\n'

        if data['as_requester']:
            ctx += f'\n**Your pending requests ({len(data["as_requester"])}):**\n'
            for r in data['as_requester']:
                ctx += (
                    f'  - "{r["board_name"]}" (role: {r["requested_role"]}, '
                    f'owner: {r["owner_name"]}, {r["created_at"]})\n'
                )

        return ctx


registry.register(AccessRequestsContextProvider())
