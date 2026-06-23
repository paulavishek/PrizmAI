"""
Workspace-admin UI for managing CustomFieldDefinition rows.

RBAC: requires the workspace owner. Custom fields are workspace-scoped, so
the owner of the workspace (its creator) is the right tier.

Routes (registered in kanban/urls.py):
    GET  /workspace/<ws_id>/custom-fields/             list
    GET  /workspace/<ws_id>/custom-fields/new/         create form
    POST /workspace/<ws_id>/custom-fields/new/         create submit
    GET  /workspace/<ws_id>/custom-fields/<id>/        edit form
    POST /workspace/<ws_id>/custom-fields/<id>/        edit submit
    POST /workspace/<ws_id>/custom-fields/<id>/delete/ soft-delete
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .custom_field_forms import CustomFieldDefinitionForm
from .custom_field_models import (
    CustomFieldDefinition,
    CustomFieldOption,
    FIELD_TYPE_LIST,
)
from .models import Workspace
from .permissions import is_demo_context


def _require_workspace_admin(request, workspace):
    """Permission gate: must be the owner of the workspace.

    Demo workspaces bypass the owner check so that any authenticated user
    exploring the demo can freely manage custom fields.
    """
    if is_demo_context(request, workspace=workspace):
        return None
    if workspace.created_by_id != request.user.id:
        return HttpResponseForbidden(
            "Only the workspace owner can manage custom fields."
        )
    return None


@login_required
def custom_field_list(request, workspace_id):
    workspace = get_object_or_404(Workspace, id=workspace_id)
    denied = _require_workspace_admin(request, workspace)
    if denied:
        return denied

    fields = (
        CustomFieldDefinition.objects
        .filter(workspace=workspace, is_active=True)
        .prefetch_related('options')
        .order_by('position', 'name')
    )
    return render(request, 'kanban/custom_fields/list.html', {
        'workspace': workspace,
        'fields': fields,
    })


@login_required
def custom_field_create(request, workspace_id):
    workspace = get_object_or_404(Workspace, id=workspace_id)
    denied = _require_workspace_admin(request, workspace)
    if denied:
        return denied

    if request.method == 'POST':
        form = CustomFieldDefinitionForm(request.POST, workspace=workspace)
        if form.is_valid():
            with transaction.atomic():
                fdef = form.save(commit=False)
                fdef.workspace = workspace
                fdef.created_by = request.user
                # Position at the end of the list.
                from django.db.models import Max
                max_pos = (
                    CustomFieldDefinition.objects
                    .filter(workspace=workspace, is_active=True)
                    .aggregate(m=Max('position'))['m']
                ) or 0
                fdef.position = max_pos + 1
                fdef.save()

                if fdef.field_type == FIELD_TYPE_LIST:
                    _save_list_options(request, fdef)

            messages.success(request, f"Custom field '{fdef.name}' created.")
            return redirect('custom_field_list', workspace_id=workspace.id)
    else:
        form = CustomFieldDefinitionForm(workspace=workspace)

    return render(request, 'kanban/custom_fields/form.html', {
        'workspace': workspace,
        'form': form,
        'field': None,
        'options': [],
    })


@login_required
def custom_field_edit(request, workspace_id, field_id):
    workspace = get_object_or_404(Workspace, id=workspace_id)
    denied = _require_workspace_admin(request, workspace)
    if denied:
        return denied

    fdef = get_object_or_404(
        CustomFieldDefinition, id=field_id, workspace=workspace, is_active=True,
    )

    if request.method == 'POST':
        form = CustomFieldDefinitionForm(request.POST, instance=fdef, workspace=workspace)
        if form.is_valid():
            with transaction.atomic():
                fdef = form.save()
                if fdef.field_type == FIELD_TYPE_LIST:
                    _save_list_options(request, fdef)
                else:
                    # Clear any orphan options if type changed away from list.
                    fdef.options.all().delete()
            messages.success(request, f"Custom field '{fdef.name}' updated.")
            return redirect('custom_field_list', workspace_id=workspace.id)
    else:
        form = CustomFieldDefinitionForm(instance=fdef, workspace=workspace)

    return render(request, 'kanban/custom_fields/form.html', {
        'workspace': workspace,
        'form': form,
        'field': fdef,
        'options': list(fdef.options.order_by('position', 'id')),
    })


@login_required
@require_POST
def custom_field_delete(request, workspace_id, field_id):
    workspace = get_object_or_404(Workspace, id=workspace_id)
    denied = _require_workspace_admin(request, workspace)
    if denied:
        return denied

    fdef = get_object_or_404(
        CustomFieldDefinition, id=field_id, workspace=workspace, is_active=True,
    )
    fdef.is_active = False
    fdef.save(update_fields=['is_active', 'updated_at'])
    messages.success(request, f"Custom field '{fdef.name}' archived.")
    return redirect('custom_field_list', workspace_id=workspace.id)


# ── Internal helpers ────────────────────────────────────────────────────────


def _save_list_options(request, fdef):
    """
    Parse parallel arrays from POST and upsert option rows.

    Expected POST keys:
      option_values[]    — display value (string)
      option_ids[]       — existing option id or '' for new
      option_is_default[]— '1' if this option is a default, else '' / missing
      option_positions[] — integer sort order

    Empty `value` rows are ignored (lets users leave the last "Add" row blank).
    Options whose id is no longer in the submitted list are deleted.
    """
    values = request.POST.getlist('option_values[]')
    ids = request.POST.getlist('option_ids[]')
    defaults = request.POST.getlist('option_is_default[]')
    positions = request.POST.getlist('option_positions[]')

    # Pad shorter arrays so zip() works (HTML forms can omit empties).
    n = len(values)
    ids = (ids + [''] * n)[:n]
    positions = (positions + ['0'] * n)[:n]
    # `defaults` is the trickiest: HTML usually sends one entry per checked box,
    # not aligned to the row. We instead read `option_is_default_<idx>` keys
    # which we render row-by-row in the template.
    survivors = set()
    for idx, raw_value in enumerate(values):
        value = (raw_value or '').strip()
        if not value:
            continue
        opt_id = ids[idx] or None
        try:
            position = int(positions[idx])
        except (TypeError, ValueError):
            position = idx
        is_default = bool(request.POST.get(f'option_is_default_{idx}'))

        if opt_id:
            try:
                opt = CustomFieldOption.objects.get(id=int(opt_id), field=fdef)
                opt.value = value
                opt.position = position
                opt.is_default = is_default
                opt.save()
                survivors.add(opt.id)
            except (CustomFieldOption.DoesNotExist, ValueError):
                opt = CustomFieldOption.objects.create(
                    field=fdef, value=value, position=position, is_default=is_default,
                )
                survivors.add(opt.id)
        else:
            opt = CustomFieldOption.objects.create(
                field=fdef, value=value, position=position, is_default=is_default,
            )
            survivors.add(opt.id)

    # Delete options the user removed.
    fdef.options.exclude(id__in=survivors).delete()

    # Enforce single-default for single-select fields.
    if not fdef.is_multi_select:
        defaults_qs = fdef.options.filter(is_default=True).order_by('position', 'id')
        if defaults_qs.count() > 1:
            # Keep the first; clear the rest.
            keeper = defaults_qs.first()
            fdef.options.filter(is_default=True).exclude(pk=keeper.pk).update(is_default=False)
