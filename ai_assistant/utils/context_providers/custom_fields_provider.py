"""
Custom Fields Context Provider — workspace-scoped task attributes.

CustomFieldDefinition is workspace-scoped (one row per workspace). This
provider exposes the schema (field names, types, required flags) plus a
preview of values across the active board. The `exclude_from_ai` flag is
honored — fields marked AI-exempt are never surfaced.
"""

import logging

from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class CustomFieldsContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Custom Fields'
    FEATURE_TAGS = [
        'custom field', 'custom fields', 'field', 'fields', 'attribute',
        'attributes', 'property', 'properties', 'metadata',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        if not board:
            return ''

        from ai_assistant.utils.spectra_data_fetchers import fetch_custom_fields_summary

        data = fetch_custom_fields_summary(board)
        if data is None:
            return ''
        total = data['total']
        if total == 0:
            return ''  # don't add noise if there are no custom fields

        names = ', '.join(data['names'][:6])
        more = '' if total <= 6 else f' (+{total - 6} more)'
        lines = [f'🧩 **Custom Fields:** {total} defined — {names}{more}']
        if data['excluded_from_ai']:
            lines.append(
                f'  ({data["excluded_from_ai"]} field(s) hidden from AI by configuration)'
            )
        return '\n'.join(lines) + '\n'

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        if not board:
            return None

        from ai_assistant.utils.spectra_data_fetchers import fetch_custom_fields_detail

        data = fetch_custom_fields_detail(board)
        if data is None or data['total'] == 0:
            return None

        ctx = f'**🧩 Custom Fields — workspace of {board.name}** ({data["total"]} fields)\n'
        if data['excluded_from_ai']:
            ctx += (
                f'_{data["excluded_from_ai"]} field(s) excluded from AI per workspace settings._\n'
            )

        ctx += '\n**Schema:**\n'
        for f in data['fields']:
            required = ' (required)' if f['is_required'] else ''
            options = ''
            if f['options']:
                options = f' — options: {", ".join(f["options"][:6])}'
                if len(f['options']) > 6:
                    options += f' (+{len(f["options"]) - 6} more)'
            ctx += f'  - {f["name"]} [{f["field_type"]}]{required}{options}\n'

        if data['value_samples']:
            ctx += '\n**Recent values on this board:**\n'
            for sample in data['value_samples'][:15]:
                ctx += (
                    f'  - "{sample["task_title"]}" → '
                    f'{sample["field_name"]}: {sample["display_value"]}\n'
                )

        return ctx


registry.register(CustomFieldsContextProvider())
