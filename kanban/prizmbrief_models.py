"""
SavedBrief — persists PrizmBrief AI-generated presentation content.
Capped at 10 saved briefs per user per board.
"""

from django.db import models
from django.contrib.auth.models import User


class SavedBrief(models.Model):
    """A user-saved PrizmBrief result."""

    MAX_PER_USER_BOARD = 10

    board = models.ForeignKey(
        'kanban.Board', on_delete=models.CASCADE, related_name='saved_briefs',
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='saved_briefs',
    )
    name = models.CharField(max_length=120)

    # Generation parameters
    audience = models.CharField(max_length=30)
    purpose = models.CharField(max_length=30)
    mode = models.CharField(max_length=30)

    # Display labels for audience/purpose/mode
    audience_label = models.CharField(max_length=80, blank=True, default='')
    purpose_label = models.CharField(max_length=80, blank=True, default='')
    mode_label = models.CharField(max_length=80, blank=True, default='')

    # Content
    slides_json = models.JSONField(
        help_text="List of slide dicts: [{number, title, body, body_html}, ...]",
    )
    full_text = models.TextField(
        help_text="Plain-text version used for Copy All / Download.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.board.name})"
