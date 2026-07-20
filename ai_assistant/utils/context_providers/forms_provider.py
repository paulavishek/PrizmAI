"""
Forms Context Provider — AI-assisted intake forms (workspace-scoped).

Form is workspace-scoped, not board-scoped (like DiscoveryIdea), so this
provider works at the user's active workspace level. It surfaces how many
intake forms exist, how many are active, and what each one produces
(Discovery ideas or Kanban tasks) — the destination Forms feeds into.
"""

import logging

from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class FormsContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Forms'
    FEATURE_TAGS = [
        'form', 'forms', 'intake', 'intake form', 'submission', 'submissions',
        'request form', 'form builder', 'form response', 'form responses',
        'submit a form', 'fill out',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        from ai_assistant.utils.spectra_data_fetchers import fetch_forms_summary

        ws = self._get_user_workspace(user)
        if not ws:
            return ''
        data = fetch_forms_summary(ws, user, is_demo_mode)
        if data is None or data['total'] == 0:
            return ''

        return (
            f'📝 **Forms:** {data["total"]} total ({data["active"]} active) — '
            f'{data["total_submissions"]} submission(s) received\n'
        )

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        from ai_assistant.utils.spectra_data_fetchers import fetch_forms_detail

        ws = self._get_user_workspace(user)
        if not ws:
            return None
        data = fetch_forms_detail(ws, user, is_demo_mode)
        if data is None or data['total'] == 0:
            return None

        ctx = f'**📝 Intake Forms — {ws.name}** ({data["total"]} total)\n'
        for form_row in data['forms']:
            status = 'active' if form_row['is_active'] else 'inactive'
            ctx += f'  - "{form_row["title"]}" ({status}) → {form_row["target_destination"]}'
            if form_row['target_board']:
                ctx += f' [{form_row["target_board"]}]'
            ctx += (
                f' — {form_row["field_count"]} field(s), '
                f'{form_row["submission_count"]} submission(s)'
            )
            if form_row['scored_idea_count']:
                ctx += f', {form_row["scored_idea_count"]} scored idea(s)'
            if form_row['task_count']:
                ctx += f', {form_row["task_count"]} task(s) created'
            ctx += '\n'

        return ctx


registry.register(FormsContextProvider())
