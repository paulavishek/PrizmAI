"""
Custom Fields for PrizmAI — v1 (Tasks only, workspace-scoped).

Three models:
  - CustomFieldDefinition: the schema (one row per field per workspace).
  - CustomFieldOption: allowed values for list-type fields.
  - TaskCustomFieldValue: typed value rows linking a Task to a field.

Forward-compat hooks:
  - applies_to_tasks / applies_to_boards on the definition. v1 only renders
    applies_to_tasks=True; boards UI lands in v1.1 without schema churn.

AI privacy:
  - exclude_from_ai flag on each field; serializers honor it.
"""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q, UniqueConstraint


FIELD_TYPE_TEXT = 'text'
FIELD_TYPE_LONG_TEXT = 'long_text'
FIELD_TYPE_NUMBER = 'number'
FIELD_TYPE_INTEGER = 'integer'
FIELD_TYPE_DATE = 'date'
FIELD_TYPE_BOOLEAN = 'boolean'
FIELD_TYPE_LIST = 'list'

FIELD_TYPE_CHOICES = [
    (FIELD_TYPE_TEXT, 'Text'),
    (FIELD_TYPE_LONG_TEXT, 'Long Text'),
    (FIELD_TYPE_NUMBER, 'Number'),
    (FIELD_TYPE_INTEGER, 'Integer'),
    (FIELD_TYPE_DATE, 'Date'),
    (FIELD_TYPE_BOOLEAN, 'Boolean'),
    (FIELD_TYPE_LIST, 'List'),
]


class CustomFieldDefinition(models.Model):
    """A user-defined task attribute, scoped to one Workspace."""

    workspace = models.ForeignKey(
        'kanban.Workspace',
        on_delete=models.CASCADE,
        related_name='custom_fields',
    )
    name = models.CharField(max_length=100)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES)

    is_required = models.BooleanField(default=False)
    # List-type only: when True the field stores multiple selected options.
    is_multi_select = models.BooleanField(default=False)

    # Typed defaults (only the one matching field_type is consulted).
    default_text = models.TextField(blank=True, default='')
    default_number = models.DecimalField(
        max_digits=20, decimal_places=4, null=True, blank=True,
    )
    default_date = models.DateField(null=True, blank=True)
    default_boolean = models.BooleanField(null=True, blank=True)

    # v1 only renders applies_to_tasks. applies_to_boards is reserved for v1.1.
    applies_to_tasks = models.BooleanField(default=True)
    applies_to_boards = models.BooleanField(default=False)

    # When False, this field is hidden on Epic detail pages. Defaults to True so
    # existing fields keep showing on Epics; uncheck for task-only metadata like
    # Story Points or Sprint that doesn't make sense on an Epic container.
    applies_to_epics = models.BooleanField(
        default=True,
        help_text=(
            "When unchecked, this field is hidden on Epics. Use for task-level "
            "metadata (e.g. Story Points, Sprint) that doesn't apply to an Epic."
        ),
    )

    exclude_from_ai = models.BooleanField(
        default=False,
        help_text=(
            "When checked, Spectra and other AI features will not see this "
            "field's values. Use for sensitive data like client budgets or PII."
        ),
    )

    is_active = models.BooleanField(default=True)  # soft-delete
    position = models.PositiveIntegerField(default=0)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='custom_fields_created',
    )
    # Demo per-user isolation. The demo workspace is shared by every demo user,
    # so a workspace-scoped field would otherwise bleed across all of them (one
    # user's field edits/deletes hitting everyone). Mirror the Wiki/Discovery
    # sandbox_owner pattern: template rows have sandbox_owner=NULL and each demo
    # user gets private clones (sandbox_owner=user) via
    # _clone_custom_fields_for_user. Real workspaces always keep NULL. Scope all
    # reads through kanban.custom_field_scoping.custom_field_scope_q.
    sandbox_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='sandbox_custom_fields',
        help_text='Demo-only: the sandbox user this cloned field belongs to. '
                  'NULL on real-workspace fields and on shared demo templates.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position', 'name']
        constraints = [
            # Two partial constraints instead of one on (workspace,
            # sandbox_owner, name): SQLite/Postgres treat NULL as DISTINCT in a
            # unique index, so a single constraint spanning the nullable
            # sandbox_owner would let two real-workspace rows (both NULL) share a
            # name — silently weakening real uniqueness. Split it:
            #   • real rows (sandbox_owner IS NULL): unique on (workspace, name)
            #   • demo clones (sandbox_owner NOT NULL): unique per owner too
            UniqueConstraint(
                fields=['workspace', 'name'],
                condition=Q(is_active=True, sandbox_owner__isnull=True),
                name='uniq_active_field_name_per_workspace',
            ),
            UniqueConstraint(
                fields=['workspace', 'sandbox_owner', 'name'],
                condition=Q(is_active=True, sandbox_owner__isnull=False),
                name='uniq_active_field_name_per_sandbox_owner',
            ),
        ]
        indexes = [
            models.Index(fields=['workspace', 'is_active', 'position']),
            models.Index(fields=['sandbox_owner', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_field_type_display()})"

    @property
    def supports_options(self):
        return self.field_type == FIELD_TYPE_LIST

    def resolved_default(self):
        """Return the typed default for this field, or None."""
        ft = self.field_type
        if ft in (FIELD_TYPE_TEXT, FIELD_TYPE_LONG_TEXT):
            return self.default_text or None
        if ft == FIELD_TYPE_NUMBER:
            return self.default_number
        if ft == FIELD_TYPE_INTEGER:
            return int(self.default_number) if self.default_number is not None else None
        if ft == FIELD_TYPE_DATE:
            return self.default_date
        if ft == FIELD_TYPE_BOOLEAN:
            return self.default_boolean
        if ft == FIELD_TYPE_LIST:
            defaults = list(self.options.filter(is_default=True).values_list('value', flat=True))
            if not defaults:
                return None
            return defaults if self.is_multi_select else defaults[0]
        return None


class CustomFieldOption(models.Model):
    """An allowed value for a list-type CustomFieldDefinition."""

    field = models.ForeignKey(
        CustomFieldDefinition,
        on_delete=models.CASCADE,
        related_name='options',
    )
    value = models.CharField(max_length=200)
    is_default = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['position', 'id']
        constraints = [
            UniqueConstraint(
                fields=['field', 'value'],
                name='uniq_option_value_per_field',
            ),
        ]

    def __str__(self):
        return self.value


class TaskCustomFieldValue(models.Model):
    """
    Typed value for one Task × one CustomFieldDefinition.

    Only the column matching field.field_type is populated. The other typed
    columns stay null/empty so we can keep clean Django filter ergonomics
    (e.g. value_number__gte=1000) without JSON casting.
    """

    task = models.ForeignKey(
        'kanban.Task',
        on_delete=models.CASCADE,
        related_name='custom_field_values',
    )
    field = models.ForeignKey(
        CustomFieldDefinition,
        on_delete=models.CASCADE,
        related_name='values',
    )

    value_text = models.TextField(blank=True, default='')
    value_number = models.DecimalField(
        max_digits=20, decimal_places=4, null=True, blank=True,
    )
    value_date = models.DateField(null=True, blank=True)
    value_boolean = models.BooleanField(null=True, blank=True)
    selected_options = models.ManyToManyField(
        CustomFieldOption, blank=True, related_name='value_rows',
    )

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='custom_field_values_updated',
    )

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['task', 'field'],
                name='uniq_value_per_task_field',
            ),
        ]
        indexes = [
            models.Index(fields=['field', 'value_text']),
            models.Index(fields=['field', 'value_number']),
            models.Index(fields=['field', 'value_date']),
            models.Index(fields=['field', 'value_boolean']),
        ]

    def __str__(self):
        return f"{self.task_id} · {self.field.name}"

    def resolved_value(self):
        """Return the typed Python value for this row, per the field type."""
        ft = self.field.field_type
        if ft in (FIELD_TYPE_TEXT, FIELD_TYPE_LONG_TEXT):
            return self.value_text or None
        if ft == FIELD_TYPE_NUMBER:
            return self.value_number
        if ft == FIELD_TYPE_INTEGER:
            return int(self.value_number) if self.value_number is not None else None
        if ft == FIELD_TYPE_DATE:
            return self.value_date
        if ft == FIELD_TYPE_BOOLEAN:
            return self.value_boolean
        if ft == FIELD_TYPE_LIST:
            values = [opt.value for opt in self.selected_options.all()]
            if not values:
                return None
            return values if self.field.is_multi_select else values[0]
        return None

    def display_value(self):
        """Human-friendly string for templates and filter chips."""
        v = self.resolved_value()
        if v is None:
            return ''
        if isinstance(v, list):
            return ', '.join(str(x) for x in v)
        if isinstance(v, bool):
            return 'Yes' if v else 'No'
        if isinstance(v, int):
            # Integer type — no decimal places.
            return str(v)
        if isinstance(v, Decimal):
            # Strip trailing zeros (e.g. 987654.0000 → 987654, 3.50 → 3.5).
            normalized = v.normalize()
            return format(normalized, 'f') if normalized == normalized.to_integral_value() else str(normalized)
        return str(v)
