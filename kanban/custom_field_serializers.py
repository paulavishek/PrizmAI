"""
Custom-field serializers.

Two surfaces:
  - serialize_task_custom_fields(task): for the UI / templates / forms.
  - serialize_for_ai(task): for LLM prompts. Honors `exclude_from_ai`.

IMPORTANT — N+1 PREVENTION:
    Both functions iterate `task.custom_field_values.all()` and read
    `value_row.field` and `value_row.selected_options.all()`. Every queryset
    that feeds a task into these serializers MUST use:

        prefetch_related(
            'custom_field_values__field',
            'custom_field_values__selected_options',
        )

    Without that prefetch, a board with N tasks triggers up to 3N extra
    queries (one per task for values, plus one each for field and options).
    On a 100-task board that's hundreds of unnecessary DB hits.

    The board view, task_detail view, and fetch_task_dict (Spectra) callers
    have been updated to include this prefetch. New callers must do the same.
"""

from __future__ import annotations


def serialize_task_custom_fields(task):
    """
    Return a list of dicts describing every custom-field value on `task`,
    including fields the user hasn't set yet (those come back with value=None
    so templates can render the input with the field's default).

    Output shape:
        [
          {
            'field_id': 12,
            'name': 'Regulatory Phase',
            'field_type': 'list',
            'is_required': True,
            'is_multi_select': False,
            'exclude_from_ai': False,
            'value': 'Phase 2',           # resolved typed value, or None
            'display': 'Phase 2',          # string for templates
            'options': [{'id': 5, 'value': 'Phase 1'}, ...]  # only for list
          },
          ...
        ]
    """
    from .custom_field_models import CustomFieldDefinition, FIELD_TYPE_LIST

    workspace_id = _resolve_workspace_id(task)
    if workspace_id is None:
        return []

    fields = (
        CustomFieldDefinition.objects
        .filter(workspace_id=workspace_id, is_active=True, applies_to_tasks=True)
        .prefetch_related('options')
        .order_by('position', 'name')
    )

    # Build a lookup of existing values for this task.
    values_by_field = {v.field_id: v for v in task.custom_field_values.all()}

    out = []
    for fdef in fields:
        v_row = values_by_field.get(fdef.id)
        resolved = v_row.resolved_value() if v_row else fdef.resolved_default()
        display = v_row.display_value() if v_row else _format_default_display(fdef)
        entry = {
            'field_id': fdef.id,
            'name': fdef.name,
            'field_type': fdef.field_type,
            'is_required': fdef.is_required,
            'is_multi_select': fdef.is_multi_select,
            'exclude_from_ai': fdef.exclude_from_ai,
            'value': resolved,
            'display': display,
        }
        if fdef.field_type == FIELD_TYPE_LIST:
            entry['options'] = [
                {'id': opt.id, 'value': opt.value, 'is_default': opt.is_default}
                for opt in fdef.options.all()
            ]
            entry['selected_option_ids'] = (
                [opt.id for opt in v_row.selected_options.all()] if v_row else
                [opt.id for opt in fdef.options.all() if opt.is_default]
            )
        out.append(entry)
    return out


def serialize_for_ai(task):
    """
    Return a `{field_name: value}` dict suitable for LLM prompts.

    - Skips fields where `exclude_from_ai=True` (user opt-out).
    - Skips fields with no set value AND no resolved default — keeps the
      prompt tight; the LLM should not see empty fields as meaningful.
    - Returns {} when the task has no custom fields, so non-customizing
      workspaces pay near-zero cost.

    The caller MUST prefetch `custom_field_values__field` and
    `custom_field_values__selected_options` (see module docstring).
    """
    from .custom_field_models import FIELD_TYPE_LIST

    values_by_field = {v.field_id: v for v in task.custom_field_values.all()}
    if not values_by_field:
        return {}

    out = {}
    for v_row in values_by_field.values():
        fdef = v_row.field
        if fdef.exclude_from_ai or not fdef.is_active:
            continue
        resolved = v_row.resolved_value()
        if resolved is None or resolved == '' or resolved == []:
            continue
        # Normalize for JSON-friendly output (used by AI prompts).
        if fdef.field_type == FIELD_TYPE_LIST:
            out[fdef.name] = resolved if isinstance(resolved, list) else [resolved]
        else:
            from decimal import Decimal
            from datetime import date
            if isinstance(resolved, Decimal):
                # Convert Decimal → float for JSON serialization.
                out[fdef.name] = float(resolved)
            elif isinstance(resolved, date):
                out[fdef.name] = resolved.isoformat()
            else:
                out[fdef.name] = resolved
    return out


def save_custom_field_values_from_post(task, post_data, user, files=None):
    """
    Upsert TaskCustomFieldValue rows from a POST payload.

    Convention: form inputs are named  custom_field_<field_id>  (lists may
    arrive as custom_field_<id> or custom_field_<id>[] — getlist() handles
    both). The current user is stamped onto `updated_by` so the scope-autopsy
    signal records a real event (vs. silent bulk/system writes).

    Raises ValidationError if a required field is left blank.
    """
    from django.core.exceptions import ValidationError
    from .custom_field_models import (
        CustomFieldDefinition,
        CustomFieldOption,
        TaskCustomFieldValue,
        FIELD_TYPE_BOOLEAN,
        FIELD_TYPE_DATE,
        FIELD_TYPE_INTEGER,
        FIELD_TYPE_LIST,
        FIELD_TYPE_LONG_TEXT,
        FIELD_TYPE_NUMBER,
        FIELD_TYPE_TEXT,
    )
    from datetime import date
    from decimal import Decimal, InvalidOperation

    workspace_id = _resolve_workspace_id(task)
    if workspace_id is None:
        return

    fields = list(
        CustomFieldDefinition.objects
        .filter(workspace_id=workspace_id, is_active=True, applies_to_tasks=True)
    )

    errors = {}
    for fdef in fields:
        post_key = f'custom_field_{fdef.id}'
        list_key = f'{post_key}[]'

        raw_values = None
        if hasattr(post_data, 'getlist'):
            raw_values = post_data.getlist(list_key) or post_data.getlist(post_key)
        else:
            single = post_data.get(post_key)
            raw_values = [single] if single is not None else []

        # Compress: filter out empty/None entries; preserve order.
        raw_values = [v for v in raw_values if v not in (None, '')]
        is_blank = (len(raw_values) == 0)

        if fdef.field_type == FIELD_TYPE_BOOLEAN:
            # Unchecked boxes don't post a value — that's not "blank", it's False.
            is_blank = False
            bool_val = bool(raw_values)
            _upsert_value(task, fdef, user, value_boolean=bool_val)
            continue

        if is_blank:
            if fdef.is_required:
                errors[fdef.name] = "is required"
                continue
            # Clear any existing value.
            TaskCustomFieldValue.objects.filter(task=task, field=fdef).delete()
            continue

        if fdef.field_type in (FIELD_TYPE_TEXT, FIELD_TYPE_LONG_TEXT):
            _upsert_value(task, fdef, user, value_text=str(raw_values[0]).strip())

        elif fdef.field_type == FIELD_TYPE_NUMBER:
            try:
                num = Decimal(str(raw_values[0]))
            except (InvalidOperation, ValueError):
                errors[fdef.name] = "must be a number"
                continue
            _upsert_value(task, fdef, user, value_number=num)

        elif fdef.field_type == FIELD_TYPE_INTEGER:
            try:
                int_val = int(str(raw_values[0]).strip())
            except (ValueError, TypeError):
                errors[fdef.name] = "must be a whole number"
                continue
            _upsert_value(task, fdef, user, value_number=Decimal(int_val))

        elif fdef.field_type == FIELD_TYPE_DATE:
            try:
                parsed = date.fromisoformat(str(raw_values[0]))
            except (ValueError, TypeError):
                errors[fdef.name] = "must be a valid date (YYYY-MM-DD)"
                continue
            _upsert_value(task, fdef, user, value_date=parsed)

        elif fdef.field_type == FIELD_TYPE_LIST:
            # Values are option IDs (rendered as <option value="{{ opt.id }}">).
            try:
                option_ids = [int(v) for v in raw_values]
            except (ValueError, TypeError):
                errors[fdef.name] = "invalid option selection"
                continue
            valid_options = list(
                CustomFieldOption.objects.filter(field=fdef, id__in=option_ids)
            )
            if not valid_options:
                errors[fdef.name] = "invalid option selection"
                continue
            if not fdef.is_multi_select:
                valid_options = valid_options[:1]
            row = _upsert_value(task, fdef, user)
            row.selected_options.set(valid_options)
            # Trigger a save so the signal sees updated_by — set/clear M2M
            # alone doesn't call post_save on the parent row.
            row.save()

    if errors:
        raise ValidationError({k: [v] for k, v in errors.items()})


def _upsert_value(task, fdef, user, **typed_fields):
    """
    Get-or-create a TaskCustomFieldValue, stamping `updated_by` so the
    autopsy signal recognises it as a real-user change.
    """
    from .custom_field_models import TaskCustomFieldValue

    row, _ = TaskCustomFieldValue.objects.get_or_create(task=task, field=fdef)
    for attr, val in typed_fields.items():
        setattr(row, attr, val)
    row.updated_by = user
    row.save()
    return row


def serialize_field_definitions_for_workspace(workspace_id):
    """
    Return a list of field-definition dicts for a workspace (used by the
    filter bar and admin UI). Includes options for list fields.
    """
    from .custom_field_models import CustomFieldDefinition, FIELD_TYPE_LIST

    fields = (
        CustomFieldDefinition.objects
        .filter(workspace_id=workspace_id, is_active=True, applies_to_tasks=True)
        .prefetch_related('options')
        .order_by('position', 'name')
    )
    out = []
    for f in fields:
        entry = {
            'id': f.id,
            'name': f.name,
            'field_type': f.field_type,
            'is_required': f.is_required,
            'is_multi_select': f.is_multi_select,
            'exclude_from_ai': f.exclude_from_ai,
        }
        if f.field_type == FIELD_TYPE_LIST:
            entry['options'] = [
                {'id': opt.id, 'value': opt.value} for opt in f.options.all()
            ]
        out.append(entry)
    return out


# ── Internal helpers ────────────────────────────────────────────────────────


def _resolve_workspace_id(task):
    """Walk task → column → board → workspace_id without extra queries
    (assumes the caller select_related('column__board'))."""
    column = getattr(task, 'column', None)
    if column is None:
        return None
    board = getattr(column, 'board', None)
    if board is None:
        return None
    return getattr(board, 'workspace_id', None)


def _format_default_display(fdef):
    """String form of a field's default for template rendering."""
    from decimal import Decimal
    default = fdef.resolved_default()
    if default is None:
        return ''
    if isinstance(default, list):
        return ', '.join(str(x) for x in default)
    if isinstance(default, bool):
        return 'Yes' if default else 'No'
    if isinstance(default, int):
        return str(default)
    if isinstance(default, Decimal):
        normalized = default.normalize()
        return format(normalized, 'f') if normalized == normalized.to_integral_value() else str(normalized)
    return str(default)
