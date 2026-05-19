"""
Summarize custom-field state for the AI Coach prompt.

We deliberately do not dump every task's value here — that would blow up
the prompt for large boards. Instead we produce a small overview the LLM
can use to (a) reference fields by name and (b) ask Spectra for details
when relevant.

Output shape (list of dicts):
    [
      {
        'name': 'Externally Blocked',
        'type': 'boolean',
        'tasks_set': 12,           # number of tasks where this is set
        'top_values': ['Yes (8)', 'No (4)'],  # only for boolean/list types
      },
      ...
    ]

Honors `exclude_from_ai`: those fields are silently omitted.
"""

from __future__ import annotations

from collections import Counter

from kanban.custom_field_models import (
    CustomFieldDefinition,
    FIELD_TYPE_BOOLEAN,
    FIELD_TYPE_LIST,
    TaskCustomFieldValue,
)


def summarize_custom_fields_for_board(board, top_n=4):
    workspace_id = getattr(board, 'workspace_id', None)
    if not workspace_id:
        return []

    fields = (
        CustomFieldDefinition.objects
        .filter(
            workspace_id=workspace_id,
            is_active=True,
            applies_to_tasks=True,
            exclude_from_ai=False,
        )
        .order_by('position', 'name')
    )

    out = []
    for fdef in fields:
        values_qs = (
            TaskCustomFieldValue.objects
            .filter(field=fdef, task__column__board_id=board.id)
            .prefetch_related('selected_options')
        )
        values = list(values_qs)

        entry = {
            'name': fdef.name,
            'type': fdef.field_type,
            'tasks_set': len(values),
        }

        if fdef.field_type == FIELD_TYPE_BOOLEAN:
            counter = Counter('Yes' if v.value_boolean else 'No' for v in values)
            entry['top_values'] = [f"{label} ({count})" for label, count in counter.most_common()]
        elif fdef.field_type == FIELD_TYPE_LIST:
            counter = Counter()
            for v in values:
                for opt in v.selected_options.all():
                    counter[opt.value] += 1
            entry['top_values'] = [f"{label} ({count})" for label, count in counter.most_common(top_n)]

        out.append(entry)
    return out
