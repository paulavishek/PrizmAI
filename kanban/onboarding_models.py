from django.db import models
from django.contrib.auth.models import User


class OnboardingWorkspacePreview(models.Model):
    """
    Stores the AI-generated workspace hierarchy (Goal → Missions → Strategies
    → Boards → Tasks) while the user reviews it before committing.

    OneToOneField on User ensures only one preview exists per user at a time.
    Creating a new preview replaces the previous one.
    """

    STATUS_CHOICES = [
        ('generating', 'Generating'),
        ('ready', 'Ready for Review'),
        ('committed', 'Committed'),
        ('failed', 'Failed'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='onboarding_preview',
    )
    goal_text = models.TextField(
        help_text="The raw organization goal text the user entered.",
    )
    generated_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Full AI-generated workspace hierarchy as JSON.",
    )
    edited_data = models.JSONField(
        null=True,
        blank=True,
        help_text="User's edits from the review step (overrides generated_data on commit).",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='generating',
    )
    celery_task_id = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="Celery AsyncResult ID for polling task status.",
    )
    error_message = models.TextField(
        blank=True,
        null=True,
        help_text="Error details if generation failed.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Onboarding Workspace Preview"
        verbose_name_plural = "Onboarding Workspace Previews"

    def __str__(self):
        return f"Preview for {self.user.username} ({self.status})"
