"""
Forms — AI-assisted intake engine.

A Form is a small, ordered set of fields a workspace member fills out. On
submission the answers are mapped onto a new DiscoveryIdea (auto-scored by
Spectra) or a Kanban Task, via forms/services.py::process_submission.

v1 scope: logged-in workspace members only (no public/anonymous submission).
"""
import uuid

from django.contrib.auth.models import User
from django.db import models


TARGET_DESTINATION_CHOICES = [
    ('DISCOVERY', 'PrizmDiscovery Idea'),
    ('KANBAN_TASK', 'Kanban Task'),
]

FIELD_TYPE_CHOICES = [
    ('SHORT_TEXT', 'Short Text'),
    ('LONG_TEXT', 'Long Text'),
    ('SINGLE_SELECT', 'Single Select'),
    ('MULTI_SELECT', 'Multi Select'),
    ('STATIC_CONTENT', 'Static Content (instructions only)'),
]

# What a field's answer maps onto on the created DiscoveryIdea/Task.
# 'none' fields are context-only — their answers get folded into the
# description so Spectra still sees them, per the "structured intake ->
# higher-quality scoring" goal.
MAPPED_PROPERTY_CHOICES = [
    ('title', 'Title'),
    ('description', 'Description'),
    ('source', 'Source (Discovery only)'),
    ('none', 'Context only (included in description)'),
]


class Form(models.Model):
    """A reusable intake form owned by a workspace."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        'kanban.Workspace',
        on_delete=models.CASCADE,
        related_name='forms',
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_forms',
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    target_destination = models.CharField(
        max_length=20,
        choices=TARGET_DESTINATION_CHOICES,
        default='DISCOVERY',
    )
    # Required only when target_destination == 'KANBAN_TASK'.
    target_board = models.ForeignKey(
        'kanban.Board',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='intake_forms',
    )
    is_active = models.BooleanField(default=True)
    submit_button_text = models.CharField(max_length=60, default='Submit Request')
    confirmation_message = models.TextField(
        blank=True,
        default='Thanks — your submission has been received.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Sandbox isolation — mirrors DiscoveryIdea.sandbox_owner. None for real
    # workspaces/templates; set to the owning demo user for cloned copies.
    sandbox_owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True, blank=True,
        db_index=True,
        related_name='sandbox_forms',
        help_text="Owning demo user for sandbox-isolated copies; None for template/real forms.",
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Form'
        verbose_name_plural = 'Forms'

    def __str__(self):
        return self.title


class FormField(models.Model):
    """A single question/block on a Form, in display order."""
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name='fields')
    label = models.CharField(max_length=255)
    help_text = models.CharField(max_length=255, blank=True, default='')
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES, default='SHORT_TEXT')
    mapped_property = models.CharField(max_length=20, choices=MAPPED_PROPERTY_CHOICES, default='none')
    is_required = models.BooleanField(default=False)
    # Option labels for SINGLE_SELECT / MULTI_SELECT, e.g. ["Bug", "Feature"].
    choices = models.JSONField(blank=True, default=list)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'Form Field'
        verbose_name_plural = 'Form Fields'

    def __str__(self):
        return f"{self.form.title} — {self.label}"


class FormSubmission(models.Model):
    """One fill-out of a Form by a logged-in member."""
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name='submissions')
    submitter_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='form_submissions',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    created_idea = models.ForeignKey(
        'kanban.DiscoveryIdea',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='form_submission',
    )
    created_task = models.ForeignKey(
        'kanban.Task',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='form_submission',
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Form Submission'
        verbose_name_plural = 'Form Submissions'

    def __str__(self):
        return f"Submission of '{self.form.title}' by {self.submitter_user}"


class FormAnswer(models.Model):
    """One field's answer within a FormSubmission."""
    submission = models.ForeignKey(FormSubmission, on_delete=models.CASCADE, related_name='answers')
    field = models.ForeignKey(FormField, on_delete=models.CASCADE, related_name='answers')
    # Stores the raw answer regardless of field type: string for text fields,
    # list of strings for MULTI_SELECT.
    value = models.JSONField(blank=True, default=str)

    class Meta:
        verbose_name = 'Form Answer'
        verbose_name_plural = 'Form Answers'

    def __str__(self):
        return f"{self.field.label}: {self.value!r}"
