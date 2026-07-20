"""HTTP-level tests for the Forms views: RBAC gating and the builder/fill flows."""
from unittest.mock import patch

from django.test import Client
from django.urls import reverse

from forms.models import Form, FormField
from kanban.discovery_models import DiscoveryIdea
from kanban.models import Task

FAKE_SCORE = {
    'impact': 80, 'effort': 20, 'confidence': 70,
    'recommendation': 'Ship it.', 'reasoning': 'High value, low effort.', 'success': True,
}


def _client_for(user):
    c = Client()
    c.force_login(user)
    return c


def test_viewer_cannot_create_form(workspace_setup):
    ws = workspace_setup
    client = _client_for(ws.viewer)

    resp = client.get(reverse('form_create'))
    assert resp.status_code == 302
    assert resp.url == reverse('form_list')
    assert Form.objects.count() == 0


def test_member_can_build_a_discovery_form_with_fields(workspace_setup):
    ws = workspace_setup
    client = _client_for(ws.member)

    resp = client.post(reverse('form_create'), {
        'title': 'Feature Request Intake',
        'description': 'Tell us what you need.',
        'target_destination': 'DISCOVERY',
        'submit_button_text': 'Send',
        'confirmation_message': 'Thanks!',
        'field_id[]': ['', ''],
        'field_label[]': ['Title', 'Description'],
        'field_help_text[]': ['', ''],
        'field_type[]': ['SHORT_TEXT', 'LONG_TEXT'],
        'field_mapped_property[]': ['title', 'description'],
        'field_choices[]': ['', ''],
        'field_is_required_0': 'on',
    })

    assert Form.objects.count() == 1
    new_form = Form.objects.get()
    assert resp.status_code == 302
    assert resp.url == reverse('form_detail', kwargs={'form_id': new_form.pk})
    assert new_form.workspace_id == ws.ws.pk
    assert list(new_form.fields.order_by('order').values_list('label', 'mapped_property', 'is_required')) == [
        ('Title', 'title', True),
        ('Description', 'description', False),
    ]


def test_kanban_task_form_requires_a_target_board(workspace_setup):
    ws = workspace_setup
    client = _client_for(ws.member)

    resp = client.post(reverse('form_create'), {
        'title': 'Bug Report Intake',
        'description': '',
        'target_destination': 'KANBAN_TASK',
        # no target_board supplied
        'submit_button_text': 'Send',
        'confirmation_message': 'Thanks!',
        'field_id[]': [''],
        'field_label[]': ['Title'],
        'field_help_text[]': [''],
        'field_type[]': ['SHORT_TEXT'],
        'field_mapped_property[]': ['title'],
        'field_choices[]': [''],
    })

    assert resp.status_code == 200  # re-rendered with an error, not saved
    assert Form.objects.count() == 0


def test_only_owner_can_edit_a_form(workspace_setup):
    ws = workspace_setup
    intake_form = Form.objects.create(workspace=ws.ws, created_by=ws.owner, title='Owner-only form')

    other_member = ws.member
    client = _client_for(other_member)
    resp = client.get(reverse('form_edit', kwargs={'form_id': intake_form.pk}))

    assert resp.status_code == 302
    assert resp.url == reverse('form_list')


def test_form_fill_creates_submission_and_scored_idea(workspace_setup, django_capture_on_commit_callbacks):
    ws = workspace_setup
    intake_form = Form.objects.create(
        workspace=ws.ws, created_by=ws.owner, title='Feature Request Intake',
        target_destination='DISCOVERY',
    )
    title_field = FormField.objects.create(
        form=intake_form, label='Title', field_type='SHORT_TEXT',
        mapped_property='title', is_required=True, order=0,
    )
    desc_field = FormField.objects.create(
        form=intake_form, label='Description', field_type='LONG_TEXT',
        mapped_property='description', order=1,
    )

    client = _client_for(ws.member)
    with patch('kanban.discovery_ai.DiscoveryAIScorer.score_idea', return_value=FAKE_SCORE):
        with django_capture_on_commit_callbacks(execute=True):
            resp = client.post(reverse('form_fill', kwargs={'form_id': intake_form.pk}), {
                f'answer_{title_field.pk}': 'Bulk CSV export',
                f'answer_{desc_field.pk}': 'Users want to export their tasks.',
            })

    assert resp.status_code == 302
    assert resp.url == reverse('form_detail', kwargs={'form_id': intake_form.pk})

    idea = DiscoveryIdea.objects.get(title='Bulk CSV export')
    assert idea.workspace_id == ws.ws.pk
    assert idea.submitted_by_id == ws.member.pk
    assert idea.is_scored
    assert idea.ai_score_impact == 80


def test_form_fill_required_field_missing_shows_error_and_creates_nothing(workspace_setup):
    ws = workspace_setup
    intake_form = Form.objects.create(
        workspace=ws.ws, created_by=ws.owner, title='Feature Request Intake',
        target_destination='DISCOVERY',
    )
    FormField.objects.create(
        form=intake_form, label='Title', field_type='SHORT_TEXT',
        mapped_property='title', is_required=True, order=0,
    )

    client = _client_for(ws.member)
    resp = client.post(reverse('form_fill', kwargs={'form_id': intake_form.pk}), {})

    assert resp.status_code == 200
    assert DiscoveryIdea.objects.count() == 0
    assert intake_form.submissions.count() == 0


def test_form_fill_kanban_task_target(workspace_setup):
    ws = workspace_setup
    intake_form = Form.objects.create(
        workspace=ws.ws, created_by=ws.owner, title='Bug Report Intake',
        target_destination='KANBAN_TASK', target_board=ws.board,
    )
    title_field = FormField.objects.create(
        form=intake_form, label='Title', field_type='SHORT_TEXT',
        mapped_property='title', is_required=True, order=0,
    )

    client = _client_for(ws.member)
    resp = client.post(reverse('form_fill', kwargs={'form_id': intake_form.pk}), {
        f'answer_{title_field.pk}': 'Login button is broken',
    })

    assert resp.status_code == 302
    task = Task.objects.get(title='Login button is broken')
    assert task.column_id == ws.backlog.pk
