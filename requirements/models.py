import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Max
from django.urls import reverse

logger = logging.getLogger(__name__)


class RequirementCategory(models.Model):
    """Per-board requirement categories (Functional, Non-functional, etc.)."""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    board = models.ForeignKey(
        'kanban.Board',
        on_delete=models.CASCADE,
        related_name='requirement_categories',
    )

    class Meta:
        verbose_name_plural = 'Requirement Categories'
        unique_together = ('board', 'name')
        ordering = ['name']

    def __str__(self):
        return self.name


class ProjectObjective(models.Model):
    """Board-level objectives that requirements trace to."""
    board = models.ForeignKey(
        'kanban.Board',
        on_delete=models.CASCADE,
        related_name='project_objectives',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_objectives',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return self.title


class Requirement(models.Model):
    """Core requirement model, scoped to a Board."""

    PRIORITY_CHOICES = [
        ('critical', 'Critical'),
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('in_review', 'In Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('implemented', 'Implemented'),
        ('verified', 'Verified'),
    ]
    TYPE_CHOICES = [
        ('functional', 'Functional'),
        ('non_functional', 'Non-Functional'),
        ('business', 'Business'),
        ('user', 'User'),
        ('technical', 'Technical'),
    ]

    # Auto-generated identifier per board (e.g. REQ-001)
    identifier = models.CharField(max_length=50, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    acceptance_criteria = models.TextField(blank=True)

    # Board scope
    board = models.ForeignKey(
        'kanban.Board',
        on_delete=models.CASCADE,
        related_name='requirements',
    )

    # Classification
    category = models.ForeignKey(
        RequirementCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requirements',
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='functional')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # Traceability — upward
    objectives = models.ManyToManyField(
        ProjectObjective,
        blank=True,
        related_name='requirements',
    )
    linked_strategies = models.ManyToManyField(
        'kanban.Strategy',
        blank=True,
        related_name='linked_requirements',
    )

    # Traceability — downward
    linked_tasks = models.ManyToManyField(
        'kanban.Task',
        blank=True,
        related_name='linked_requirements',
    )

    # Requirement hierarchy
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
    )
    related_requirements = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=False,
        related_name='related_to',
    )

    # Metadata
    created_by = models.ForeignKey(
        User,
        related_name='requirements_created',
        on_delete=models.SET_NULL,
        null=True,
    )
    updated_by = models.ForeignKey(
        User,
        related_name='requirements_updated',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    assigned_reviewer = models.ForeignKey(
        User,
        related_name='requirements_to_review',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('board', 'identifier')
        ordering = ['identifier']

    def __str__(self):
        return f"{self.identifier} — {self.title}"

    def get_absolute_url(self):
        return reverse('requirements:requirement_detail', kwargs={
            'board_id': self.board_id,
            'pk': self.pk,
        })

    def save(self, *args, **kwargs):
        user = kwargs.pop('user', None)

        if len(self.title) > 200:
            self.title = self.title[:200]

        # Auto-generate identifier
        if not self.identifier:
            last = (
                Requirement.objects
                .filter(board=self.board)
                .aggregate(max_num=Max('id'))
            )
            next_num = (last['max_num'] or 0) + 1
            self.identifier = f"REQ-{next_num:03d}"

        # Track old status for history
        old_status = None
        if self.pk:
            try:
                old_status = Requirement.objects.get(pk=self.pk).status
            except Requirement.DoesNotExist:
                pass

        super().save(*args, **kwargs)

        # Create history entry on status change
        if old_status and old_status != self.status:
            RequirementHistory.objects.create(
                requirement=self,
                old_status=old_status,
                new_status=self.status,
                changed_by=user or self.updated_by,
                notes=f"Status changed from {old_status} to {self.status}",
            )


class RequirementHistory(models.Model):
    """Audit trail for requirement status changes."""
    requirement = models.ForeignKey(
        Requirement,
        on_delete=models.CASCADE,
        related_name='history',
    )
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'Requirement Histories'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.requirement.identifier} — {self.old_status}→{self.new_status} — {self.timestamp}"


class RequirementComment(models.Model):
    """Threaded comments on requirements."""
    requirement = models.ForeignKey(
        Requirement,
        on_delete=models.CASCADE,
        related_name='comments',
    )
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.author} on {self.requirement.identifier}"
