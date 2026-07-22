"""
Tests for forms/services.py — mapping FormAnswers onto a DiscoveryIdea/Task,
and the async auto-scoring handoff.
"""
from unittest.mock import patch

from forms.models import Form, FormField, FormSubmission, FormAnswer
from forms.services import build_property_values, process_submission
from kanban.discovery_models import DiscoveryIdea
from kanban.models import Task


def _make_discovery_form(ws, extra_fields=True):
    intake_form = Form.objects.create(
        workspace=ws.ws, created_by=ws.member,
        title='Feature Request Intake', target_destination='DISCOVERY',
    )
    title_field = FormField.objects.create(
        form=intake_form, label='Title', field_type='SHORT_TEXT',
        mapped_property='title', is_required=True, order=0,
    )
    desc_field = FormField.objects.create(
        form=intake_form, label='Description', field_type='LONG_TEXT',
        mapped_property='description', order=1,
    )
    fields = {'title': title_field, 'description': desc_field}
    if extra_fields:
        fields['target_user'] = FormField.objects.create(
            form=intake_form, label='Target User', field_type='SHORT_TEXT',
            mapped_property='none', order=2,
        )
        fields['source'] = FormField.objects.create(
            form=intake_form, label='Source', field_type='SINGLE_SELECT',
            mapped_property='source', choices=['sales_team', 'customer_feedback'], order=3,
        )
    return intake_form, fields


def test_build_property_values_maps_fields_and_folds_context_into_description(workspace_setup):
    ws = workspace_setup
    intake_form, fields = _make_discovery_form(ws)
    submission = FormSubmission.objects.create(form=intake_form, submitter_user=ws.member)
    FormAnswer.objects.create(submission=submission, field=fields['title'], value='Bulk CSV export')
    FormAnswer.objects.create(submission=submission, field=fields['description'], value='Users want to export tasks.')
    FormAnswer.objects.create(submission=submission, field=fields['target_user'], value='Enterprise admins')
    FormAnswer.objects.create(submission=submission, field=fields['source'], value='sales_team')

    title, description, source = build_property_values(submission)

    assert title == 'Bulk CSV export'
    assert 'Users want to export tasks.' in description
    # Context-only ('none'-mapped) fields are folded into the description as
    # "Label: value" so Spectra still sees them when scoring.
    assert 'Target User: Enterprise admins' in description
    assert source == 'sales_team'


def test_build_property_values_ignores_static_content_and_blank_answers(workspace_setup):
    ws = workspace_setup
    intake_form, fields = _make_discovery_form(ws, extra_fields=False)
    static_field = FormField.objects.create(
        form=intake_form, label='Instructions', field_type='STATIC_CONTENT', order=5,
    )
    submission = FormSubmission.objects.create(form=intake_form, submitter_user=ws.member)
    FormAnswer.objects.create(submission=submission, field=fields['title'], value='Idea title')
    FormAnswer.objects.create(submission=submission, field=fields['description'], value='')  # blank, ignored
    FormAnswer.objects.create(submission=submission, field=static_field, value='ignored — no answer expected')

    title, description, source = build_property_values(submission)

    assert title == 'Idea title'
    assert description == ''
    assert source == 'other'


def test_process_submission_discovery_creates_idea_and_queues_scoring(
    workspace_setup, django_capture_on_commit_callbacks,
):
    ws = workspace_setup
    intake_form, fields = _make_discovery_form(ws)
    submission = FormSubmission.objects.create(form=intake_form, submitter_user=ws.member)
    FormAnswer.objects.create(submission=submission, field=fields['title'], value='Bulk CSV export')
    FormAnswer.objects.create(submission=submission, field=fields['description'], value='Users want exports.')

    fake_score = {
        'impact': 80, 'effort': 20, 'confidence': 70,
        'recommendation': 'Ship it.', 'reasoning': 'High value, low effort.', 'success': True,
    }
    with patch('kanban.discovery_ai.DiscoveryAIScorer.score_idea', return_value=fake_score):
        with django_capture_on_commit_callbacks(execute=True):
            idea = process_submission(submission, ws.member)

    assert isinstance(idea, DiscoveryIdea)
    assert idea.title == 'Bulk CSV export'
    assert idea.workspace_id == ws.ws.pk
    assert idea.submitted_by_id == ws.member.pk
    assert idea.stage == 'new'

    submission.refresh_from_db()
    assert submission.created_idea_id == idea.pk

    # The on_commit-deferred Celery task (forms.tasks.score_form_idea) ran
    # synchronously under CELERY_TASK_ALWAYS_EAGER and saved the score.
    idea.refresh_from_db()
    assert idea.is_scored
    assert idea.ai_score_impact == 80
    assert idea.quadrant == 'quick_win'


def test_process_submission_falls_back_to_form_title_when_no_title_field_answered(workspace_setup, django_capture_on_commit_callbacks):
    ws = workspace_setup
    intake_form, fields = _make_discovery_form(ws)
    submission = FormSubmission.objects.create(form=intake_form, submitter_user=ws.member)
    FormAnswer.objects.create(submission=submission, field=fields['description'], value='No title given.')

    fake_score = {'impact': 50, 'effort': 50, 'confidence': 30, 'recommendation': '', 'reasoning': '', 'success': False}
    with patch('kanban.discovery_ai.DiscoveryAIScorer.score_idea', return_value=fake_score):
        with django_capture_on_commit_callbacks(execute=True):
            idea = process_submission(submission, ws.member)

    assert idea.title == intake_form.title


def test_process_submission_kanban_task_creates_task_on_target_board(workspace_setup):
    ws = workspace_setup
    intake_form = Form.objects.create(
        workspace=ws.ws, created_by=ws.member, title='Bug Report Intake',
        target_destination='KANBAN_TASK', target_board=ws.board,
    )
    title_field = FormField.objects.create(
        form=intake_form, label='Title', field_type='SHORT_TEXT',
        mapped_property='title', order=0,
    )
    submission = FormSubmission.objects.create(form=intake_form, submitter_user=ws.member)
    FormAnswer.objects.create(submission=submission, field=title_field, value='Login button is broken')

    task = process_submission(submission, ws.member)

    assert isinstance(task, Task)
    assert task.title == 'Login button is broken'
    # Auto-detected intake column: 'Backlog' matches the intake-name regex,
    # 'Done' does not — mirrors kanban.discovery_utils.pick_intake_column.
    assert task.column_id == ws.backlog.pk

    submission.refresh_from_db()
    assert submission.created_task_id == task.pk
