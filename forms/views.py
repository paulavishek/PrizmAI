"""
Forms — AI-assisted intake engine.

v1 scope: logged-in, non-viewer workspace members only (no public/anonymous
submission — see the plan this was built from for the deferred phases).

Gating mirrors kanban.discovery_views's RBAC shape (features.show_forms on
Professional+, non-viewer WorkspaceMembership) and reuses its _is_viewer/
_demo_owner_filter helpers. It deliberately does NOT reuse discovery_views's
_get_features/_require_discovery, which resolve the active workspace from
``user.profile.active_workspace`` directly: accounts.middleware.WorkspaceMiddleware's
ownership guard resets that field to None on every request for a workspace
member who isn't the workspace's creator (see WorkspaceMiddleware's
docstring — "Workspaces are private to their owner"), while still correctly
setting ``request.workspace`` via the org-wide fallback lookup. Since Forms
is explicitly meant for teammates beyond just the workspace creator, it
reads ``request.workspace`` (what the middleware intends views to use)
instead.
"""
import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from kanban.discovery_views import _is_viewer, _demo_owner_filter
from kanban.preset_models import build_feature_flags
from .models import (
    Form, FormField, FormSubmission, FormAnswer,
    TARGET_DESTINATION_CHOICES, FIELD_TYPE_CHOICES, MAPPED_PROPERTY_CHOICES,
)

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_features_for_request(request):
    """Feature flags for request.workspace's preset (see module docstring
    for why this reads request.workspace rather than profile.active_workspace)."""
    ws = getattr(request, 'workspace', None)
    if ws is None:
        return build_feature_flags('lean')
    try:
        return build_feature_flags(ws.workspace_preset.global_preset)
    except Exception:
        return build_feature_flags('lean')


def _require_forms(request):
    """
    Return (org, workspace, features, None) if Forms is enabled and the user
    has an active workspace. Return (None, None, None, HttpResponse) if
    access is blocked (redirect).
    """
    active_ws = getattr(request, 'workspace', None)
    profile = getattr(request.user, 'profile', None)
    org = getattr(active_ws, 'organization', None) or getattr(profile, 'organization', None)
    features = _get_features_for_request(request)

    if not features.get('show_forms'):
        messages.warning(
            request,
            'Forms is available on Professional and Enterprise plans. '
            'Upgrade your workspace in Settings to unlock it.',
        )
        return None, None, None, redirect('dashboard')

    if org is None or active_ws is None:
        messages.warning(request, 'You need a workspace to use Forms.')
        return None, None, None, redirect('dashboard')

    return org, active_ws, features, None


def _form_scope(request):
    """ORM filter kwargs scoping Form queries to the active workspace
    (mirrors kanban.discovery_views._idea_scope, but via request.workspace —
    see module docstring)."""
    ws = getattr(request, 'workspace', None)
    profile = getattr(request.user, 'profile', None)
    scope = {'workspace': ws}
    if getattr(ws, 'is_demo', False) or getattr(profile, 'is_viewing_demo', False):
        scope['sandbox_owner'] = request.user
    return scope


def _user_boards_for_picker(request):
    """Boards the user can pick as a Kanban-Task form's target (mirrors the
    board list built for the Discovery promote form in idea_detail)."""
    from kanban.models import Board
    demo_mode = getattr(getattr(request.user, 'profile', None), 'is_viewing_demo', False)
    if demo_mode:
        return Board.objects.filter(
            owner=request.user, is_sandbox_copy=True, is_archived=False
        ).order_by('name')
    from kanban.utils.demo_protection import get_user_boards
    return get_user_boards(request.user).filter(is_archived=False).order_by('name')


def _fields_json(intake_form):
    """JSON-serialize a Form's fields for the builder template's JS to
    pre-populate rows on the edit page."""
    payload = json.dumps([
        {
            'id': f.pk,
            'label': f.label,
            'help_text': f.help_text,
            'field_type': f.field_type,
            'mapped_property': f.mapped_property,
            'is_required': f.is_required,
            'choices': f.choices,
        }
        for f in intake_form.fields.order_by('order', 'id')
    ])
    # Guard against a field label containing "</script>" prematurely closing
    # the template's inline <script> block.
    return payload.replace('</', '<\\/')


def _save_fields_from_post(form, request):
    """
    Replace `form`'s FormFields with the rows submitted by the builder UI.

    Existing rows (identified by field_id[]) are updated in place; rows
    without a field_id are created; any existing field not present in this
    submission is deleted (cascades its historical FormAnswers — acceptable
    for a v1 builder with no drag-drop/versioning).
    """
    ids = request.POST.getlist('field_id[]')
    labels = request.POST.getlist('field_label[]')
    help_texts = request.POST.getlist('field_help_text[]')
    field_types = request.POST.getlist('field_type[]')
    mapped_props = request.POST.getlist('field_mapped_property[]')
    choices_raw = request.POST.getlist('field_choices[]')

    valid_types = {c[0] for c in FIELD_TYPE_CHOICES}
    valid_props = {c[0] for c in MAPPED_PROPERTY_CHOICES}

    kept_ids = set()
    order = 0
    for i, label in enumerate(labels):
        label = label.strip()
        if not label:
            continue

        field_type = field_types[i] if i < len(field_types) else 'SHORT_TEXT'
        if field_type not in valid_types:
            field_type = 'SHORT_TEXT'
        mapped_property = mapped_props[i] if i < len(mapped_props) else 'none'
        if mapped_property not in valid_props:
            mapped_property = 'none'
        help_text = help_texts[i].strip() if i < len(help_texts) else ''
        choices_list = [
            c.strip() for c in (choices_raw[i] if i < len(choices_raw) else '').split(',') if c.strip()
        ]
        # Checkboxes only appear in POST when checked, so each row's box is
        # given a unique indexed name rather than a shared field_is_required[]
        # list — otherwise an unchecked box in the middle would misalign
        # every array above it.
        is_required = f'field_is_required_{i}' in request.POST

        defaults = dict(
            label=label, help_text=help_text, field_type=field_type,
            mapped_property=mapped_property, is_required=is_required,
            choices=choices_list, order=order,
        )
        field_id = ids[i] if i < len(ids) else ''
        if field_id:
            FormField.objects.filter(pk=field_id, form=form).update(**defaults)
            kept_ids.add(int(field_id))
        else:
            new_field = FormField.objects.create(form=form, **defaults)
            kept_ids.add(new_field.pk)
        order += 1

    form.fields.exclude(pk__in=kept_ids).delete()


# ── Builder / management views ──────────────────────────────────────────────

@login_required
def form_list(request):
    """PM's forms for the active workspace."""
    org, workspace, features, blocked = _require_forms(request)
    if blocked:
        return blocked

    forms_qs = Form.objects.filter(**_form_scope(request)).select_related('created_by', 'target_board')

    return render(request, 'forms/form_list.html', {
        'forms': forms_qs,
        'features': features,
        'is_viewer': _is_viewer(request.user, org),
    })


@login_required
def form_create(request):
    """Build a new intake form. Viewers cannot access this view."""
    org, workspace, features, blocked = _require_forms(request)
    if blocked:
        return blocked

    if _is_viewer(request.user, org):
        messages.error(request, 'Viewers cannot create forms.')
        return redirect('form_list')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        target_destination = request.POST.get('target_destination', 'DISCOVERY')
        target_board_id = request.POST.get('target_board') or None
        submit_button_text = request.POST.get('submit_button_text', '').strip() or 'Submit Request'
        confirmation_message = request.POST.get('confirmation_message', '').strip() or \
            'Thanks — your submission has been received.'

        valid_targets = {c[0] for c in TARGET_DESTINATION_CHOICES}
        if target_destination not in valid_targets:
            target_destination = 'DISCOVERY'

        target_board = None
        if target_destination == 'KANBAN_TASK':
            if target_board_id:
                target_board = _user_boards_for_picker(request).filter(pk=target_board_id).first()
            if target_board is None:
                messages.error(request, 'Choose a target board for a Kanban Task form.')
                return render(request, 'forms/form_builder.html', {
                    'action': 'create', 'features': features,
                    'target_destination_choices': TARGET_DESTINATION_CHOICES,
                    'field_type_choices': FIELD_TYPE_CHOICES,
                    'mapped_property_choices': MAPPED_PROPERTY_CHOICES,
                    'boards': _user_boards_for_picker(request),
                })

        if not title:
            messages.error(request, 'Title is required.')
            return render(request, 'forms/form_builder.html', {
                'action': 'create', 'features': features,
                'target_destination_choices': TARGET_DESTINATION_CHOICES,
                'field_type_choices': FIELD_TYPE_CHOICES,
                'mapped_property_choices': MAPPED_PROPERTY_CHOICES,
                'boards': _user_boards_for_picker(request),
            })

        new_form = Form.objects.create(
            workspace=workspace,
            created_by=request.user,
            title=title,
            description=description,
            target_destination=target_destination,
            target_board=target_board,
            submit_button_text=submit_button_text,
            confirmation_message=confirmation_message,
            **_demo_owner_filter(org, request.user),
        )
        _save_fields_from_post(new_form, request)
        messages.success(request, f'Form "{new_form.title}" created.')
        return redirect('form_detail', form_id=new_form.pk)

    return render(request, 'forms/form_builder.html', {
        'action': 'create',
        'features': features,
        'target_destination_choices': TARGET_DESTINATION_CHOICES,
        'field_type_choices': FIELD_TYPE_CHOICES,
        'mapped_property_choices': MAPPED_PROPERTY_CHOICES,
        'boards': _user_boards_for_picker(request),
    })


@login_required
def form_edit(request, form_id):
    """Edit an existing form's settings and fields."""
    org, workspace, features, blocked = _require_forms(request)
    if blocked:
        return blocked

    intake_form = get_object_or_404(Form, pk=form_id, **_form_scope(request))
    is_owner = intake_form.created_by_id == request.user.id

    if _is_viewer(request.user, org) or not is_owner:
        messages.error(request, 'You do not have permission to edit this form.')
        return redirect('form_list')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        target_destination = request.POST.get('target_destination', intake_form.target_destination)
        target_board_id = request.POST.get('target_board') or None
        submit_button_text = request.POST.get('submit_button_text', '').strip() or 'Submit Request'
        confirmation_message = request.POST.get('confirmation_message', '').strip() or \
            'Thanks — your submission has been received.'

        valid_targets = {c[0] for c in TARGET_DESTINATION_CHOICES}
        if target_destination not in valid_targets:
            target_destination = intake_form.target_destination

        target_board = None
        if target_destination == 'KANBAN_TASK':
            if target_board_id:
                target_board = _user_boards_for_picker(request).filter(pk=target_board_id).first()
            if target_board is None:
                messages.error(request, 'Choose a target board for a Kanban Task form.')
                return render(request, 'forms/form_builder.html', {
                    'action': 'edit', 'form_obj': intake_form, 'features': features,
                    'target_destination_choices': TARGET_DESTINATION_CHOICES,
                    'field_type_choices': FIELD_TYPE_CHOICES,
                    'mapped_property_choices': MAPPED_PROPERTY_CHOICES,
                    'boards': _user_boards_for_picker(request),
                    'existing_fields_json': _fields_json(intake_form),
                })

        if not title:
            messages.error(request, 'Title is required.')
        else:
            intake_form.title = title
            intake_form.description = description
            intake_form.target_destination = target_destination
            intake_form.target_board = target_board
            intake_form.submit_button_text = submit_button_text
            intake_form.confirmation_message = confirmation_message
            intake_form.save(update_fields=[
                'title', 'description', 'target_destination', 'target_board',
                'submit_button_text', 'confirmation_message', 'updated_at',
            ])
            _save_fields_from_post(intake_form, request)
            messages.success(request, 'Form updated.')
            return redirect('form_detail', form_id=intake_form.pk)

    return render(request, 'forms/form_builder.html', {
        'action': 'edit',
        'form_obj': intake_form,
        'features': features,
        'target_destination_choices': TARGET_DESTINATION_CHOICES,
        'field_type_choices': FIELD_TYPE_CHOICES,
        'mapped_property_choices': MAPPED_PROPERTY_CHOICES,
        'boards': _user_boards_for_picker(request),
        'existing_fields_json': _fields_json(intake_form),
    })


@login_required
@require_POST
def form_toggle_active(request, form_id):
    org, workspace, features, blocked = _require_forms(request)
    if blocked:
        return blocked

    intake_form = get_object_or_404(Form, pk=form_id, **_form_scope(request))
    if _is_viewer(request.user, org) or intake_form.created_by_id != request.user.id:
        messages.error(request, 'You do not have permission to change this form.')
        return redirect('form_list')

    intake_form.is_active = not intake_form.is_active
    intake_form.save(update_fields=['is_active', 'updated_at'])
    messages.success(request, f'Form {"activated" if intake_form.is_active else "deactivated"}.')
    return redirect('form_list')


@login_required
@require_POST
def form_delete(request, form_id):
    org, workspace, features, blocked = _require_forms(request)
    if blocked:
        return blocked

    intake_form = get_object_or_404(Form, pk=form_id, **_form_scope(request))
    if _is_viewer(request.user, org) or intake_form.created_by_id != request.user.id:
        messages.error(request, 'You do not have permission to delete this form.')
        return redirect('form_list')

    intake_form.delete()
    messages.success(request, 'Form deleted.')
    return redirect('form_list')


@login_required
def form_detail(request, form_id):
    """Responses dashboard: submissions + the idea/task each one created."""
    org, workspace, features, blocked = _require_forms(request)
    if blocked:
        return blocked

    intake_form = get_object_or_404(Form, pk=form_id, **_form_scope(request))
    submissions = intake_form.submissions.select_related(
        'submitter_user', 'created_idea', 'created_task',
    )

    return render(request, 'forms/form_detail.html', {
        'form_obj': intake_form,
        'submissions': submissions,
        'features': features,
        'is_viewer': _is_viewer(request.user, org),
        'is_owner': intake_form.created_by_id == request.user.id,
    })


@login_required
def form_submission_status(request, submission_id):
    """
    GET JSON: has this submission's Discovery idea been scored yet?

    Auto-scoring runs on a Celery worker after the page has already
    rendered, so the responses dashboard polls this to flip "Scoring…" to
    the real quadrant/scores without a manual reload.
    """
    submission = get_object_or_404(
        FormSubmission, pk=submission_id, form__workspace=getattr(request, 'workspace', None),
    )
    idea = submission.created_idea
    if idea is None or not idea.is_scored:
        return JsonResponse({'scored': False})
    return JsonResponse({
        'scored': True,
        'quadrant_label': idea.quadrant_label,
        'impact': idea.ai_score_impact,
        'effort': idea.ai_score_effort,
    })


# ── Fill-out view ────────────────────────────────────────────────────────────

@login_required
def form_fill(request, form_id):
    """Fill out and submit a form. v1: logged-in workspace members only."""
    org, workspace, features, blocked = _require_forms(request)
    if blocked:
        return blocked

    intake_form = get_object_or_404(Form, pk=form_id, is_active=True, **_form_scope(request))
    fields = list(intake_form.fields.order_by('order', 'id'))

    if request.method == 'POST':
        errors = []
        answers_to_create = []
        for field in fields:
            if field.field_type == 'STATIC_CONTENT':
                continue
            if field.field_type == 'MULTI_SELECT':
                value = request.POST.getlist(f'answer_{field.pk}[]')
            else:
                value = request.POST.get(f'answer_{field.pk}', '').strip()

            if field.is_required and not value:
                errors.append(f'"{field.label}" is required.')
                continue
            if value:
                answers_to_create.append((field, value))

        if errors:
            for err in errors:
                messages.error(request, err)
        else:
            from .services import process_submission

            submission = FormSubmission.objects.create(
                form=intake_form,
                submitter_user=request.user,
            )
            FormAnswer.objects.bulk_create([
                FormAnswer(submission=submission, field=field, value=value)
                for field, value in answers_to_create
            ])
            process_submission(submission, request.user)
            messages.success(request, intake_form.confirmation_message)
            return redirect('form_detail', form_id=intake_form.pk)

    return render(request, 'forms/form_fill.html', {
        'form_obj': intake_form,
        'fields': fields,
        'features': features,
    })
