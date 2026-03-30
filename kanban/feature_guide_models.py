"""
Feature Guide Models
Stores contextual help content for AI features, displayed as
click-to-open popovers and detail modals on each feature page.
"""
from django.db import models


class FeatureGuide(models.Model):
    """
    Admin-editable help content for AI feature pages.
    Each entry powers a 'What is this?' badge on the feature's heading.
    """
    feature_key = models.SlugField(
        max_length=80, unique=True,
        help_text="Lookup key used in the template tag, e.g. 'shadow_board'."
    )
    feature_name = models.CharField(
        max_length=120,
        help_text="Display name shown in the modal title."
    )
    brief_description = models.CharField(
        max_length=400,
        help_text="Short description shown in the popover (max 400 chars)."
    )
    detailed_description = models.TextField(
        help_text="Full HTML description shown in the modal body. Supports headings, lists, bold, etc."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Uncheck to hide the help badge without deleting content."
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text="Ordering in admin list view."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'feature_name']
        verbose_name = 'Feature Guide'
        verbose_name_plural = 'Feature Guides'

    def __str__(self):
        return self.feature_name
