"""
Integrations models — inbound receiver integrations + outbound source connections.

Currently supports:
  - GitHubIntegration: connect a GitHub repo to a PrizmAI board so that
    PR events automatically update task statuses.
  - SourceConnection: an authenticated live connection to an external PM tool
    (Jira, Trello, Asana, Monday, ClickUp, Notion) used to migrate projects
    into PrizmAI. The API token is stored encrypted at rest.

Future: GitLab, Bitbucket, Salesforce, Figma follow the same pattern.
"""
import secrets

from django.db import models
from django.contrib.auth.models import User

from kanban.models import Board, Column, Workspace


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


class SourceConnection(models.Model):
    """
    An authenticated live connection to an external project-management tool,
    used to migrate the user's projects into PrizmAI.

    The API token is NEVER stored in plaintext: it is Fernet-encrypted via
    ``kanban_board.encryption`` before it touches the database, decrypted only
    in memory immediately before an API call, and wiped when the connection is
    deleted (row hard-delete). ``token_last_four`` is kept only for display.

    Tenancy: scoped by ``workspace`` (the tenant boundary), never Organization.
    """

    PROVIDER_JIRA = "jira"
    PROVIDER_TRELLO = "trello"
    PROVIDER_ASANA = "asana"
    PROVIDER_MONDAY = "monday"
    PROVIDER_CLICKUP = "clickup"
    PROVIDER_NOTION = "notion"
    PROVIDER_CHOICES = [
        (PROVIDER_JIRA, "Jira"),
        (PROVIDER_TRELLO, "Trello"),
        (PROVIDER_ASANA, "Asana"),
        (PROVIDER_MONDAY, "Monday.com"),
        (PROVIDER_CLICKUP, "ClickUp"),
        (PROVIDER_NOTION, "Notion"),
    ]

    STATUS_CONNECTED = "connected"
    STATUS_ERROR = "error"
    STATUS_SYNCING = "syncing"
    STATUS_CHOICES = [
        (STATUS_CONNECTED, "Connected"),
        (STATUS_ERROR, "Error"),
        (STATUS_SYNCING, "Syncing"),
    ]

    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="source_connections",
        help_text="The workspace (tenant) this connection belongs to.",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="source_connections_created",
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    base_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Provider site/base URL, e.g. 'https://acme.atlassian.net' for Jira Cloud.",
    )
    account_email = models.EmailField(
        blank=True,
        help_text="Account email used with the API token (Basic auth for Jira Cloud).",
    )
    encrypted_api_token = models.TextField(
        help_text="Fernet-encrypted API token. Never store or log the raw token.",
    )
    token_last_four = models.CharField(
        max_length=8,
        blank=True,
        help_text="Last 4 chars of the token, for display only.",
    )
    is_active = models.BooleanField(default=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_CONNECTED
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Source Connection"
        verbose_name_plural = "Source Connections"
        ordering = ["-created_at"]

    def set_token(self, raw_token: str):
        """
        Encrypt and store a raw API token. Also records the last 4 chars for
        display. Does NOT persist — caller must save(). The raw token is never
        held on the instance.
        """
        from kanban_board.encryption import encrypt_secret

        raw_token = (raw_token or "").strip()
        self.encrypted_api_token = encrypt_secret(raw_token)
        self.token_last_four = raw_token[-4:] if len(raw_token) >= 4 else ""

    def get_token(self) -> str:
        """
        Decrypt and return the raw API token, in memory only. Never log or
        persist the result.
        """
        from kanban_board.encryption import decrypt_secret

        return decrypt_secret(self.encrypted_api_token)

    def __str__(self):
        return f"{self.get_provider_display()} → {self.workspace.name}"

    def __repr__(self):
        # Deliberately excludes the token/ciphertext so it can never leak to logs.
        return (
            f"<SourceConnection id={self.pk} provider={self.provider} "
            f"workspace_id={self.workspace_id} status={self.status}>"
        )
