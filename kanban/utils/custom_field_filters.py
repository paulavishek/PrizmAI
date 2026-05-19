"""
Filter a Task queryset by custom-field values.

Used by the board filter bar. Filters are passed in a flat dict (typically
the request.GET QueryDict) keyed by `cf_<field_id>` and `cf_<field_id>_op`.

Supported operators per type (defaults in parens):
  text / long_text → exact, icontains (icontains)
  number           → exact, gte, lte                  (exact)
  date             → exact, before, after             (exact)
  boolean          → exact                             (exact)
  list             → in (multi-select)                 (in)

Example:
    qs = apply_custom_field_filters(
        Task.objects.filter(column__board=board),
        {'cf_12': 'High', 'cf_12_op': 'exact', 'cf_8': '1000', 'cf_8_op': 'gte'},
    )
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from datetime import date

from django.db.models import Q

from kanban.custom_field_models import (
    CustomFieldDefinition,
    FIELD_TYPE_BOOLEAN,
    FIELD_TYPE_DATE,
    FIELD_TYPE_LIST,
    FIELD_TYPE_LONG_TEXT,
    FIELD_TYPE_NUMBER,
    FIELD_TYPE_TEXT,
)


def apply_custom_field_filters(queryset, filter_params, workspace_id=None):
    """
    Apply `cf_<id>` filters from `filter_params` to `queryset`.

    `queryset` must be a Task queryset. `filter_params` is a dict (or
    QueryDict). `workspace_id` is optional but recommended — without it the
    function can't validate that the referenced fields belong to the right
    workspace and will trust the IDs.
    """
    if not filter_params:
        return queryset

    field_ids = _extract_filter_field_ids(filter_params)
    if not field_ids:
        return queryset

    fields_qs = CustomFieldDefinition.objects.filter(id__in=field_ids, is_active=True)
    if workspace_id is not None:
        fields_qs = fields_qs.filter(workspace_id=workspace_id)
    fields_by_id = {f.id: f for f in fields_qs}

    for field_id in field_ids:
        fdef = fields_by_id.get(field_id)
        if fdef is None:
            continue
        raw_value = filter_params.get(f'cf_{field_id}')
        op = filter_params.get(f'cf_{field_id}_op')
        if raw_value in (None, ''):
            continue
        queryset = _apply_one_filter(queryset, fdef, raw_value, op, filter_params)

    return queryset.distinct()


def _extract_filter_field_ids(params):
    out = []
    for key in params.keys():
        if not key.startswith('cf_') or key.endswith('_op'):
            continue
        suffix = key[3:]
        if not suffix.isdigit():
            continue
        out.append(int(suffix))
    return out


def _apply_one_filter(qs, fdef, raw_value, op, params):
    ft = fdef.field_type
    value_path = f'custom_field_values__field_id'

    if ft in (FIELD_TYPE_TEXT, FIELD_TYPE_LONG_TEXT):
        text_op = op if op in ('exact', 'icontains') else 'icontains'
        return qs.filter(**{
            value_path: fdef.id,
            f'custom_field_values__value_text__{text_op}': raw_value,
        })

    if ft == FIELD_TYPE_NUMBER:
        try:
            value = Decimal(str(raw_value))
        except (InvalidOperation, ValueError):
            return qs
        num_op = op if op in ('exact', 'gte', 'lte') else 'exact'
        return qs.filter(**{
            value_path: fdef.id,
            f'custom_field_values__value_number__{num_op}': value,
        })

    if ft == FIELD_TYPE_DATE:
        parsed = _parse_iso_date(raw_value)
        if parsed is None:
            return qs
        if op == 'before':
            return qs.filter(**{
                value_path: fdef.id,
                'custom_field_values__value_date__lt': parsed,
            })
        if op == 'after':
            return qs.filter(**{
                value_path: fdef.id,
                'custom_field_values__value_date__gt': parsed,
            })
        return qs.filter(**{
            value_path: fdef.id,
            'custom_field_values__value_date': parsed,
        })

    if ft == FIELD_TYPE_BOOLEAN:
        truthy = str(raw_value).lower() in ('1', 'true', 'yes', 'on')
        return qs.filter(**{
            value_path: fdef.id,
            'custom_field_values__value_boolean': truthy,
        })

    if ft == FIELD_TYPE_LIST:
        # Multi-select: `params.getlist` if available; otherwise comma-split.
        if hasattr(params, 'getlist'):
            values = params.getlist(f'cf_{fdef.id}')
        else:
            values = [v.strip() for v in str(raw_value).split(',') if v.strip()]
        values = [v for v in values if v]
        if not values:
            return qs
        return qs.filter(
            custom_field_values__field_id=fdef.id,
            custom_field_values__selected_options__value__in=values,
        )

    return qs


def _parse_iso_date(raw):
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw))
    except (ValueError, TypeError):
        return None
