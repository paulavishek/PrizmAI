"""Model-level tests for the Forms app."""
from forms.models import Form, FormField, FormSubmission, FormAnswer


def test_form_field_submission_answer_creation(workspace_setup):
    ws = workspace_setup

    intake_form = Form.objects.create(
        workspace=ws.ws, created_by=ws.member,
        title='Feature Request Intake', target_destination='DISCOVERY',
    )
    field = FormField.objects.create(
        form=intake_form, label='What problem does this solve?',
        field_type='LONG_TEXT', mapped_property='description', order=0,
    )
    assert str(intake_form) == 'Feature Request Intake'
    assert intake_form.fields.count() == 1
    assert field.form_id == intake_form.pk

    submission = FormSubmission.objects.create(form=intake_form, submitter_user=ws.member)
    answer = FormAnswer.objects.create(submission=submission, field=field, value='Onboarding is too slow.')
    assert submission.answers.count() == 1
    assert answer.value == 'Onboarding is too slow.'


def test_form_field_default_ordering(workspace_setup):
    ws = workspace_setup
    intake_form = Form.objects.create(workspace=ws.ws, created_by=ws.member, title='Bug Report')
    second = FormField.objects.create(form=intake_form, label='Second', order=1)
    first = FormField.objects.create(form=intake_form, label='First', order=0)

    assert list(intake_form.fields.all()) == [first, second]


def test_multi_select_answer_stores_a_list(workspace_setup):
    ws = workspace_setup
    intake_form = Form.objects.create(workspace=ws.ws, created_by=ws.member, title='Survey')
    field = FormField.objects.create(
        form=intake_form, label='Which areas?', field_type='MULTI_SELECT',
        choices=['Billing', 'Support', 'Onboarding'],
    )
    submission = FormSubmission.objects.create(form=intake_form, submitter_user=ws.member)
    answer = FormAnswer.objects.create(submission=submission, field=field, value=['Billing', 'Support'])

    assert answer.value == ['Billing', 'Support']
