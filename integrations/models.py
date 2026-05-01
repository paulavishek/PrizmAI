"""
Integrations models — inbound receiver integrations.

Currently supports:
  - GitHubIntegration: connect a GitHub repo to a PrizmAI board so that
    PR events automatically update task statuses.

Future: GitLab, Bitbucket, Salesforce, Figma follow the same pattern.
"""
import secrets

from django.db import models
from django.contrib.auth.models import User

from kanban.models import Board, Column


class GitHubIntegration(models.Model):
    """
    Links a GitHub repository to a PrizmAI board.

    When GitHub sends a pull_request webhook to PrizmAI, we:
      1. Verify the HMAC-SHA256 signature using webhook_secret.
      2. Extract task IDs (e.g. "SD-101") from the PR title/body.
      3. Move matching tasks to `in_review_column`.
    """

    board = models.OneToOneField(
        Board,
        on_delete=models.CASCADE,
        related_name="github_integration",
    )
    repo_full_name = models.CharField(
        max_length=255,
        help_text='GitHub repository in "owner/repo" format, e.g. "acme/backend"',
    )
    webhook_secret = models.CharField(
        max_length=64,
        help_text="Secret token shared with GitHub for HMAC-SHA256 signature verification.",
        default=secrets.token_hex,  # auto-generate on creation
    )
    in_review_column = models.ForeignKey(
        Column,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="github_review_integrations",
        help_text="Tasks matching a PR will be moved to this column (e.g. 'In Review').",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="github_integrations_created",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "GitHub Integration"
        verbose_name_plural = "GitHub Integrations"

    def __str__(self):
        return f"GitHub: {self.repo_full_name} → {self.board.name}"
