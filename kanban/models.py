from datetime import date, timedelta
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.db.models import Q, Sum, Avg, Count
from colorfield.fields import ColorField
from accounts.models import Organization
from django.core.validators import MinValueValidator, MaxValueValidator

# Import coach models
from kanban.coach_models import CoachingSuggestion, CoachingFeedback, PMMetrics, CoachingInsight

# Import resource leveling models
from kanban.resource_leveling_models import (
    UserPerformanceProfile,
    TaskAssignmentHistory,
    ResourceLevelingSuggestion
)

# Import conflict detection models
from kanban.conflict_models import (
    ConflictDetection,
    ConflictResolution,
    ResolutionPattern,
    ConflictNotification
)

# Import automation models
from kanban.automation_models import BoardAutomation, ScheduledAutomation

# Import onboarding models
from kanban.onboarding_models import OnboardingWorkspacePreview

# Import Living Commitment Protocol models
from kanban.commitment_models import (
    CommitmentProtocol,
    ConfidenceSignal,
    CommitmentBet,
    NegotiationSession,
    UserCredibilityScore,
)

# Import Workspace Preset models
from kanban.preset_models import WorkspacePreset, BoardPreset, build_feature_flags


# ---------------------------------------------------------------------------
# WORKSPACE — the isolation boundary for multi-workspace support.
# Each workspace contains its own Goal → Mission → Strategy → Board → Task
# hierarchy.  Users switch between workspaces via a context switcher.
# The demo sandbox is modelled as a special workspace with is_demo=True.
# ---------------------------------------------------------------------------
class Workspace(models.Model):
    name = models.CharField(
        max_length=200,
        help_text="Display name of this workspace (e.g., 'Acme Corp Launch').",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='workspaces',
        help_text="The organization this workspace belongs to.",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_workspaces',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_demo = models.BooleanField(
        default=False,
        help_text="True for the demo/sandbox workspace. Only one per organization.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Soft-delete flag. Inactive workspaces are hidden from the switcher.",
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Workspace'
        verbose_name_plural = 'Workspaces'

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# ORGANIZATION GOAL — apex strategic layer
# Sits above Mission.  Owned by an Organization.  One Goal → many Missions.
# No access restrictions: all authenticated users can view and create these.
# ---------------------------------------------------------------------------
class OrganizationGoal(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('pending', 'Pending'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('archived', 'Archived'),
    ]

    name = models.CharField(
        max_length=200,
        help_text="The high-level organizational goal (e.g., 'Increase Market Share in Asia by 15%').",
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Context, motivation and success criteria for this goal.",
    )
    target_metric = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Measurable target (e.g., '15% market share increase', '$5M revenue').",
    )
    target_date = models.DateField(
        blank=True,
        null=True,
        help_text="Target completion / measurement date.",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        related_name='organization_goals',
        null=True,
        blank=True,
        help_text="Owning organization (optional — matches MVP open-access model).",
    )
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='created_organization_goals'
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='owned_goals',
        null=True,
        blank=True,
        help_text="Accountable owner of this goal (defaults to creator).",
    )
    version = models.IntegerField(
        default=1,
        help_text="Current version number — incremented on each edit.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Demo support
    is_demo = models.BooleanField(default=False)
    is_seed_demo_data = models.BooleanField(default=False)

    # Workspace isolation
    workspace = models.ForeignKey(
        'Workspace',
        on_delete=models.CASCADE,
        related_name='goals',
        null=True,
        blank=True,
        help_text="The workspace this goal belongs to.",
    )

    # AI Summary (bubble-up from Mission summaries)
    ai_summary = models.TextField(
        blank=True,
        null=True,
        help_text="AI-generated summary synthesised from all linked Mission summaries.",
    )
    ai_summary_generated_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the AI summary was last generated.",
    )

    # Portfolio Narrative (Goal-Aware Analytics — data storytelling)
    portfolio_narrative = models.TextField(
        null=True, blank=True,
        help_text="Gemini-generated narrative summarising health of all linked boards in Goal context."
    )
    portfolio_narrative_generated_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the portfolio narrative was last generated."
    )
    portfolio_narrative_metric_snapshot = models.JSONField(
        null=True, blank=True,
        help_text="Metric snapshot at time of portfolio narrative generation."
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Organization Goal'
        verbose_name_plural = 'Organization Goals'

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('goal_detail', kwargs={'goal_id': self.pk})


# ---------------------------------------------------------------------------
# MISSION — top-level strategic layer (the "problem / challenge" statement)
# No access restrictions: all authenticated users can view and create these.
# ---------------------------------------------------------------------------
class Mission(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('pending', 'Pending'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('archived', 'Archived'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Describe the problem or challenge this Mission addresses.",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='created_missions'
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='owned_missions',
        null=True,
        blank=True,
        help_text="Accountable owner of this mission.",
    )
    due_date = models.DateField(
        blank=True,
        null=True,
        help_text="Target completion date for this mission.",
    )
    version = models.IntegerField(
        default=1,
        help_text="Current version number — incremented on each edit.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Parent goal — one OrganizationGoal supports many Missions (nullable FK)
    organization_goal = models.ForeignKey(
        'OrganizationGoal',
        on_delete=models.SET_NULL,
        related_name='missions',
        null=True,
        blank=True,
        help_text="The Organization Goal this Mission contributes to.",
    )

    # Demo support
    is_demo = models.BooleanField(default=False)
    is_seed_demo_data = models.BooleanField(default=False)

    # AI Summary (bubble-up from strategies)
    ai_summary = models.TextField(
        blank=True,
        null=True,
        help_text="AI-generated summary synthesised from all strategy summaries."
    )
    ai_summary_generated_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the AI summary was last generated."
    )

    # Portfolio Narrative (Goal-Aware Analytics — data storytelling)
    portfolio_narrative = models.TextField(
        null=True, blank=True,
        help_text="Gemini-generated narrative summarising health of all linked boards in Mission context."
    )
    portfolio_narrative_generated_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the portfolio narrative was last generated."
    )
    portfolio_narrative_metric_snapshot = models.JSONField(
        null=True, blank=True,
        help_text="Metric snapshot at time of portfolio narrative generation."
    )

    # Workspace FK stub — reserved for future Workspace layer (currently unused)
    # workspace = models.ForeignKey('Workspace', null=True, blank=True, ...)
    workspace = models.ForeignKey(
        'Workspace',
        on_delete=models.CASCADE,
        related_name='missions',
        null=True,
        blank=True,
        help_text="The workspace this mission belongs to.",
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('mission_detail', kwargs={'mission_id': self.pk})


# ---------------------------------------------------------------------------
# STRATEGY — second-level layer (the "solution / response" statement)
# Sits between Mission and Board.
# No access restrictions: all authenticated users can view and create these.
# ---------------------------------------------------------------------------
class Strategy(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('pending', 'Pending'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('archived', 'Archived'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Describe the solution or approach this Strategy proposes.",
    )
    mission = models.ForeignKey(
        Mission, on_delete=models.CASCADE, related_name='strategies'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='created_strategies'
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='owned_strategies',
        null=True,
        blank=True,
        help_text="Accountable owner of this strategy.",
    )
    due_date = models.DateField(
        blank=True,
        null=True,
        help_text="Target completion date for this strategy.",
    )
    version = models.IntegerField(
        default=1,
        help_text="Current version number — incremented on each edit.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Demo support
    is_seed_demo_data = models.BooleanField(default=False)

    # Workspace isolation
    workspace = models.ForeignKey(
        'Workspace',
        on_delete=models.CASCADE,
        related_name='strategies',
        null=True,
        blank=True,
        help_text="The workspace this strategy belongs to.",
    )

    # AI Summary (bubble-up from boards)
    ai_summary = models.TextField(
        blank=True,
        null=True,
        help_text="AI-generated summary synthesised from all board summaries under this strategy."
    )
    ai_summary_generated_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the AI summary was last generated."
    )

    # Portfolio Narrative (Goal-Aware Analytics — data storytelling)
    portfolio_narrative = models.TextField(
        null=True, blank=True,
        help_text="Gemini-generated narrative summarising health of all linked boards in Strategy context."
    )
    portfolio_narrative_generated_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the portfolio narrative was last generated."
    )
    portfolio_narrative_metric_snapshot = models.JSONField(
        null=True, blank=True,
        help_text="Metric snapshot at time of portfolio narrative generation."
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Strategies'

    def __str__(self):
        return f"{self.mission.name} — {self.name}"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse(
            'strategy_detail',
            kwargs={'mission_id': self.mission_id, 'strategy_id': self.pk},
        )


# ---------------------------------------------------------------------------
# VERSION HISTORY MODELS — immutable snapshots created on each edit
# ---------------------------------------------------------------------------
class GoalVersion(models.Model):
    CHANGE_REASON_CHOICES = [
        ('minor_tweak', 'Minor tweak'),
        ('scope_change', 'Scope change'),
        ('strategic_pivot', 'Strategic pivot'),
    ]

    goal = models.ForeignKey(
        OrganizationGoal, on_delete=models.CASCADE, related_name='versions'
    )
    version_number = models.IntegerField()
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    target_date = models.DateField(null=True, blank=True)
    owner = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name='+'
    )
    changed_by = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name='+'
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    change_reason = models.CharField(max_length=20, choices=CHANGE_REASON_CHOICES)
    change_notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-version_number']
        unique_together = [('goal', 'version_number')]

    def __str__(self):
        return f"{self.goal.name} v{self.version_number}"


class MissionVersion(models.Model):
    CHANGE_REASON_CHOICES = GoalVersion.CHANGE_REASON_CHOICES

    mission = models.ForeignKey(
        Mission, on_delete=models.CASCADE, related_name='versions'
    )
    version_number = models.IntegerField()
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    due_date = models.DateField(null=True, blank=True)
    owner = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name='+'
    )
    changed_by = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name='+'
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    change_reason = models.CharField(max_length=20, choices=CHANGE_REASON_CHOICES)
    change_notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-version_number']
        unique_together = [('mission', 'version_number')]

    def __str__(self):
        return f"{self.mission.name} v{self.version_number}"


class StrategyVersion(models.Model):
    CHANGE_REASON_CHOICES = GoalVersion.CHANGE_REASON_CHOICES

    strategy = models.ForeignKey(
        Strategy, on_delete=models.CASCADE, related_name='versions'
    )
    version_number = models.IntegerField()
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    due_date = models.DateField(null=True, blank=True)
    owner = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name='+'
    )
    changed_by = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name='+'
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    change_reason = models.CharField(max_length=20, choices=CHANGE_REASON_CHOICES)
    change_notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-version_number']
        unique_together = [('strategy', 'version_number')]

    def __str__(self):
        return f"{self.strategy.name} v{self.version_number}"


# ---------------------------------------------------------------------------
# GOAL PROXY METRICS — outcome indicators suggested by Spectra
# Proxy Metrics measure real-world outcomes (not task outputs) to track
# whether a Goal is actually being achieved.
# ---------------------------------------------------------------------------
class GoalProxyMetric(models.Model):
    goal = models.ForeignKey(
        OrganizationGoal,
        on_delete=models.CASCADE,
        related_name='proxy_metrics',
    )
    name = models.CharField(max_length=200)
    why_it_matters = models.TextField()
    how_to_measure = models.TextField()
    current_value = models.CharField(max_length=200, null=True, blank=True)
    previous_value = models.CharField(max_length=200, null=True, blank=True)
    last_updated = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['display_order']

    def __str__(self):
        return f"{self.name} — {self.goal.name}"


# ---------------------------------------------------------------------------
# STRATEGIC UPDATES — structured status check-ins at Goal / Mission / Strategy
# Uses Django's ContentType framework for polymorphism.
# ---------------------------------------------------------------------------
class StrategicUpdate(models.Model):
    STATUS_CHOICES = [
        ('on_track', 'On track'),
        ('at_risk', 'At risk'),
        ('off_track', 'Off track'),
        ('blocked', 'Blocked'),
    ]

    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE
    )
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    message = models.TextField(
        max_length=500,
        help_text="Structured status check-in (max 500 characters).",
    )
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='strategic_updates')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        return f"{self.author} — {self.get_status_display()} ({self.created_at:%d %b %Y})"


# ---------------------------------------------------------------------------
# MILESTONE — concrete checkpoints unique to the Strategy level
# ---------------------------------------------------------------------------
class Milestone(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('complete', 'Complete'),
        ('missed', 'Missed'),
    ]

    strategy = models.ForeignKey(
        Strategy, on_delete=models.CASCADE, related_name='milestones'
    )
    name = models.CharField(max_length=255)
    due_date = models.DateField()
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='pending'
    )

    class Meta:
        ordering = ['due_date']

    def __str__(self):
        return f"{self.name} ({self.get_status_display()}) — {self.due_date}"


# ---------------------------------------------------------------------------
# STRATEGIC FOLLOWER — polymorphic follower (Goal / Mission / Strategy)
# ---------------------------------------------------------------------------
class StrategicFollower(models.Model):
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE
    )
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='strategic_follows'
    )
    followed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('content_type', 'object_id', 'user')]
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        return f"{self.user} follows {self.content_type} #{self.object_id}"


# ---------------------------------------------------------------------------
# USER FAVORITE — polymorphic "My Favorites" sidebar pins
# ---------------------------------------------------------------------------
class UserFavorite(models.Model):
    FAVORITE_TYPES = [
        ('board', 'Board'),
        ('goal', 'Goal'),
        ('mission', 'Mission'),
        ('wiki_page', 'Wiki Page'),
        ('task', 'Task'),
        ('retrospective', 'Retrospective'),
        ('chat_room', 'Chat Room'),
        ('conflict', 'Conflict'),
        ('shadow_branch', 'Shadow Branch'),
        ('automation', 'Automation Rule'),
    ]

    ICON_MAP = {
        'board': 'fas fa-columns',
        'goal': 'fas fa-trophy',
        'mission': 'fas fa-bullseye',
        'wiki_page': 'fas fa-book-open',
        'task': 'fas fa-check-square',
        'retrospective': 'fas fa-history',
        'chat_room': 'fas fa-comments',
        'conflict': 'fas fa-exclamation-triangle',
        'shadow_branch': 'fas fa-code-branch',
        'automation': 'fas fa-cogs',
    }

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='favorites'
    )
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE
    )
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    favorite_type = models.CharField(max_length=20, choices=FAVORITE_TYPES)
    display_name = models.CharField(
        max_length=200,
        help_text="Cached name for sidebar rendering without extra queries"
    )
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('user', 'content_type', 'object_id')]
        ordering = ['position', '-created_at']
        indexes = [
            models.Index(fields=['user', 'position']),
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        return f"{self.user} ♥ {self.display_name}"

    def get_icon_class(self):
        return self.ICON_MAP.get(self.favorite_type, 'fas fa-star')

    def get_absolute_url(self):
        """Resolve the detail URL for the favorited object."""
        from django.urls import reverse
        try:
            obj = self.content_object
            if obj is None:
                return '#'
            if self.favorite_type == 'board':
                return reverse('board_detail', args=[obj.pk])
            elif self.favorite_type == 'goal':
                return reverse('goal_detail', args=[obj.pk])
            elif self.favorite_type == 'mission':
                return reverse('mission_detail', args=[obj.pk])
            elif self.favorite_type == 'wiki_page':
                return reverse('wiki:wiki_page_detail', args=[obj.pk])
            elif self.favorite_type == 'task':
                return reverse('board_detail', args=[obj.column.board.pk])
            elif self.favorite_type == 'retrospective':
                return reverse('retrospective_detail', args=[obj.board.pk, obj.pk])
            elif self.favorite_type == 'chat_room':
                return reverse('messaging:chat_room_detail', args=[obj.pk])
            elif self.favorite_type == 'conflict':
                return reverse('conflict_detail', args=[obj.pk])
            elif self.favorite_type == 'shadow_branch':
                return reverse('shadow_board_detail', args=[obj.board.pk, obj.pk])
            elif self.favorite_type == 'automation':
                return reverse('automation_rule_detail', args=[obj.board.pk, obj.pk])
        except Exception:
            return '#'
        return '#'


class Board(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    # Organization is now optional - MVP simplification
    organization = models.ForeignKey(
        Organization, 
        on_delete=models.SET_NULL, 
        related_name='boards',
        null=True,
        blank=True,
        help_text="Organization (optional - MVP mode does not require organization)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_boards')
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_boards',
        help_text="Board owner — full edit, delete, invite rights. Access flows down to all children."
    )
    
    # Scope baseline tracking
    baseline_task_count = models.IntegerField(null=True, blank=True, 
                                             help_text="Baseline task count for scope tracking")
    baseline_complexity_total = models.IntegerField(null=True, blank=True,
                                                    help_text="Baseline complexity total")
    baseline_set_date = models.DateTimeField(null=True, blank=True,
                                            help_text="When the baseline was established")
    baseline_set_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='baseline_boards',
                                       help_text="User who set the baseline")

    # Workspace isolation (denormalized from strategy→mission→goal for query efficiency)
    workspace = models.ForeignKey(
        'Workspace',
        on_delete=models.CASCADE,
        related_name='boards',
        null=True,
        blank=True,
        help_text="The workspace this board belongs to.",
    )
    
    # Demo Mode Support
    is_official_demo_board = models.BooleanField(
        default=False,
        help_text="Official demo boards cannot be deleted by demo users"
    )
    created_by_session = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Session ID if created in demo mode (for cleanup)"
    )
    is_seed_demo_data = models.BooleanField(
        default=False,
        help_text="True if this is original seed demo data (not user-created)."
    )
    is_sandbox_copy = models.BooleanField(
        default=False,
        help_text="True if this board was created by sandbox provisioning (personal demo copy)."
    )
    is_imported = models.BooleanField(
        default=False,
        help_text="True if this board was created via file import (Jira, Monday.com, Trello, etc.)."
    )
    cloned_from = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='sandbox_clones',
        help_text="Template board this sandbox copy was cloned from."
    )

    # Phase Configuration for Gantt Chart
    num_phases = models.PositiveIntegerField(
        default=0,
        help_text="Number of phases for this board (0 means phases are disabled). Users set this during board creation."
    )

    # Triple Constraint – project deadline (Time constraint)
    project_deadline = models.DateField(
        null=True,
        blank=True,
        help_text="Target completion date for the project (Time constraint). Set from the Triple Constraint dashboard."
    )

    # Hierarchy: Mission → Strategy → Board
    strategy = models.ForeignKey(
        'Strategy',
        on_delete=models.SET_NULL,
        related_name='boards',
        null=True,
        blank=True,
        help_text="The Strategy this board belongs to (optional — existing boards unaffected).",
    )

    # AI Summary (bubble-up from tasks)
    ai_summary = models.TextField(
        blank=True,
        null=True,
        help_text="AI-generated summary synthesised from all task summaries on this board."
    )
    ai_summary_generated_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the AI summary was last generated."
    )
    ai_summary_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Explainability metadata for the AI summary (confidence, data completeness, key drivers)."
    )

    # Archival status
    is_archived = models.BooleanField(
        default=False,
        help_text="Whether this board has been archived/completed."
    )
    archived_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the board was archived."
    )

    # Gantt Task ID Prefix (e.g. 'PRZ', 'SD')
    task_prefix = models.CharField(
        max_length=10,
        blank=True,
        default='',
        help_text="Short prefix for task IDs in Gantt chart (e.g. 'PRZ'). Auto-derived from board name if left blank."
    )

    # --------------- Goal-Aware Analytics (project type classification) ---------------
    PROJECT_TYPE_CHOICES = [
        ('product_tech', 'Product / Tech'),
        ('marketing_campaign', 'Marketing / Campaign'),
        ('operations', 'Operations'),
    ]
    project_type = models.CharField(
        max_length=30,
        choices=PROJECT_TYPE_CHOICES,
        null=True,
        blank=True,
        help_text="Gemini-classified project type. Controls which analytics are promoted."
    )
    project_type_confirmed = models.BooleanField(
        default=False,
        help_text="True once user has confirmed or manually set the project type."
    )
    project_type_confidence = models.FloatField(
        null=True,
        blank=True,
        help_text="Gemini confidence score at time of classification (0.0 to 1.0)."
    )

    # AI Narrative Summary (Goal-Aware Analytics — data storytelling)
    analytics_narrative = models.TextField(
        null=True, blank=True,
        help_text="Gemini-generated 2-sentence narrative explaining what board metrics mean for the linked Goal."
    )
    analytics_narrative_generated_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the analytics narrative was last generated."
    )
    analytics_narrative_metric_snapshot = models.JSONField(
        null=True, blank=True,
        help_text="Metric values at time of narrative generation — used for staleness detection."
    )

    def __str__(self):
        return self.name

    def get_default_prefix(self):
        """Derive a default prefix from the board name initials, uppercased, max 5 chars."""
        words = self.name.split()
        if len(words) >= 2:
            return ''.join(w[0] for w in words if w)[:5].upper()
        return self.name[:3].upper()

    def get_task_prefix(self):
        """Return the task prefix, auto-generating from name if not set."""
        return self.task_prefix or self.get_default_prefix()

    @property
    def completed_task_count(self):
        """Return count of tasks with progress == 100 on this board."""
        return Task.objects.filter(column__board=self, item_type='task', progress=100).count()

    def create_scope_snapshot(self, user=None, snapshot_type='manual', is_baseline=False, notes=None):
        """
        Create a scope snapshot for this board
        Returns the created ScopeChangeSnapshot instance
        """
        from django.db.models import Q, Sum, Avg, Count
        
        tasks = Task.objects.filter(column__board=self, item_type='task')
        
        # Calculate metrics
        total_tasks = tasks.count()
        complexity_sum = tasks.aggregate(Sum('complexity_score'))['complexity_score__sum'] or 0
        complexity_avg = tasks.aggregate(Avg('complexity_score'))['complexity_score__avg'] or 0.0
        
        high_priority = tasks.filter(priority='high').count()
        urgent_priority = tasks.filter(priority='urgent').count()
        
        # Task status breakdown (approximate based on column names)
        todo_tasks = tasks.filter(column__name__icontains='to do').count() + \
                    tasks.filter(column__name__icontains='backlog').count()
        in_progress_tasks = tasks.filter(
            Q(column__name__icontains='in progress') | 
            Q(column__name__icontains='doing')
        ).count()
        completed_tasks = tasks.filter(
            Q(column__name__icontains='done') | 
            Q(column__name__icontains='complete')
        ).count()
        
        # Get baseline for comparison
        baseline = None
        if is_baseline:
            # This is the new baseline
            baseline = None
        else:
            # Find the most recent baseline
            baseline = self.scope_snapshots.filter(is_baseline=True).order_by('-snapshot_date').first()
        
        # Create snapshot
        snapshot = ScopeChangeSnapshot.objects.create(
            board=self,
            total_tasks=total_tasks,
            total_complexity_points=complexity_sum,
            avg_complexity=round(complexity_avg, 2),
            high_priority_tasks=high_priority,
            urgent_priority_tasks=urgent_priority,
            todo_tasks=todo_tasks,
            in_progress_tasks=in_progress_tasks,
            completed_tasks=completed_tasks,
            is_baseline=is_baseline,
            baseline_snapshot=baseline,
            created_by=user,
            snapshot_type=snapshot_type,
            notes=notes
        )
        
        # Calculate changes if there's a baseline
        if baseline:
            snapshot.calculate_changes_from_baseline()
            snapshot.save()
        
        # Update board baseline fields if this is a baseline
        if is_baseline:
            self.baseline_task_count = total_tasks
            self.baseline_complexity_total = complexity_sum
            self.baseline_set_date = timezone.now()
            self.baseline_set_by = user
            self.save()
        
        return snapshot
    
    def get_current_scope_status(self):
        """
        Get current scope status compared to baseline
        Returns dict with scope metrics or None if no baseline
        """
        if not self.baseline_task_count:
            return None
        
        tasks = Task.objects.filter(column__board=self, item_type='task')
        current_count = tasks.count()
        current_complexity = tasks.aggregate(Sum('complexity_score'))['complexity_score__sum'] or 0
        
        if self.baseline_task_count > 0:
            scope_change = ((current_count - self.baseline_task_count) / self.baseline_task_count) * 100
        else:
            scope_change = 0
        
        if self.baseline_complexity_total and self.baseline_complexity_total > 0:
            complexity_change = ((current_complexity - self.baseline_complexity_total) / 
                               self.baseline_complexity_total) * 100
        else:
            complexity_change = 0
        
        return {
            'baseline_tasks': self.baseline_task_count,
            'current_tasks': current_count,
            'tasks_added': current_count - self.baseline_task_count,
            'scope_change_percentage': round(scope_change, 2),
            'baseline_complexity': self.baseline_complexity_total,
            'current_complexity': current_complexity,
            'complexity_change_percentage': round(complexity_change, 2),
            'baseline_date': self.baseline_set_date,
        }
    
    def check_scope_creep_threshold(self, warning_threshold=15, critical_threshold=30):
        """
        Check if scope has exceeded warning or critical thresholds
        Returns tuple: (has_alert, severity, scope_change_pct)
        """
        status = self.get_current_scope_status()
        if not status:
            return (False, None, 0)
        
        scope_change = abs(status['scope_change_percentage'])
        
        if scope_change >= critical_threshold:
            return (True, 'critical', status['scope_change_percentage'])
        elif scope_change >= warning_threshold:
            return (True, 'warning', status['scope_change_percentage'])
        elif scope_change >= 5:
            return (True, 'info', status['scope_change_percentage'])
        
        return (False, None, status['scope_change_percentage'])

class Column(models.Model):
    COLOR_CHOICES = [
        ('green', 'Green'),
        ('blue', 'Blue'),
        ('purple', 'Purple'),
        ('orange', 'Orange'),
        ('red', 'Red'),
        ('yellow', 'Yellow'),
        ('teal', 'Teal'),
        ('gray', 'Gray'),
    ]

    name = models.CharField(max_length=100)
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='columns')
    position = models.IntegerField(default=0)
    color = models.CharField(max_length=20, choices=COLOR_CHOICES, default='blue')
    wip_limit = models.PositiveIntegerField(null=True, blank=True, default=None,
                                            help_text="Maximum number of tasks allowed in this column. Leave blank for no limit.")
    
    class Meta:
        ordering = ['position']
    
    def __str__(self):
        return f"{self.name} - {self.board.name}"
    
    def is_wip_exceeded(self, task_count=None):
        """Return True if the column has exceeded its WIP limit."""
        if self.wip_limit is None:
            return False
        if task_count is None:
            task_count = self.task_set.filter(item_type='task').count()
        return task_count > self.wip_limit

class TaskLabel(models.Model):
    CATEGORY_CHOICES = [
        ('regular', 'Regular'),
        ('lean', 'Lean Six Sigma'),
    ]
    
    name = models.CharField(max_length=50)
    color = ColorField(default='#FF5733')
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='labels')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='regular')
    
    def __str__(self):
        return self.name

class Task(models.Model):
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    column = models.ForeignKey(Column, on_delete=models.CASCADE, related_name='tasks')
    position = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    start_date = models.DateField(blank=True, null=True, help_text="Task start date for Gantt chart")
    due_date = models.DateTimeField(blank=True, null=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='assigned_tasks', blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_tasks')
    labels = models.ManyToManyField(TaskLabel, related_name='tasks', blank=True)

    # Phase Assignment (for Gantt chart phase-based grouping)
    phase = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Phase this task belongs to (e.g., 'Phase 1', 'Phase 2'). Set via dropdown based on board's num_phases."
    )

    # Lean Six Sigma Classification (Single-select, mutually exclusive)
    LSS_CLASSIFICATION_CHOICES = [
        ('value_added', 'Value-Added'),
        ('necessary_nva', 'Necessary NVA'),
        ('waste', 'Waste/Eliminate'),
    ]
    lss_classification = models.CharField(
        max_length=20,
        choices=LSS_CLASSIFICATION_CHOICES,
        blank=True,
        null=True,
        help_text="Lean Six Sigma classification - mutually exclusive category"
    )
    lss_classification_confidence = models.FloatField(
        blank=True,
        null=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="AI confidence score for LSS classification (0.0-1.0)"
    )
    lss_classification_reasoning = models.JSONField(
        default=dict,
        blank=True,
        help_text="AI reasoning for LSS classification"
    )
    
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    progress = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
      # AI Analysis Results
    ai_risk_score = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)],
                                      help_text="AI-calculated risk score (0-100)")
    ai_recommendations = models.TextField(blank=True, null=True, help_text="AI-generated recommendations for this task")
    last_ai_analysis = models.DateTimeField(blank=True, null=True, help_text="When AI last analyzed this task")

    # AI Summary (persisted plain-text executive summary for dashboard bubble-up)
    ai_summary = models.TextField(
        blank=True,
        null=True,
        help_text="Persisted AI-generated executive summary for this task."
    )
    ai_summary_generated_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the AI task summary was last generated."
    )
    ai_summary_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Rich explainability data from the AI task summary (confidence, health, risks, etc.)."
    )
    
    # Smart Resource Analysis Fields
    required_skills = models.JSONField(
        default=list,
        blank=True,
        help_text="Required skills for this task (e.g., [{'name': 'Python', 'level': 'Intermediate'}])"
    )
    skill_match_score = models.IntegerField(
        blank=True, 
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="AI-calculated skill match score for assigned user (0-100)"
    )
    optimal_assignee_suggestions = models.JSONField(
        default=list,
        blank=True,
        help_text="AI-suggested optimal assignees with match scores"
    )
    workload_impact = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low Impact'),
            ('medium', 'Medium Impact'),
            ('high', 'High Impact'),
            ('critical', 'Critical Impact'),
        ],
        default='medium',
        blank=True,
        null=True,
        help_text="Impact on assignee's workload"
    )
    resource_conflicts = models.JSONField(
        default=list,
        blank=True,
        help_text="Identified resource conflicts and scheduling issues"
    )
    
    # Enhanced Resource Tracking    
    complexity_score = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Task complexity score (1-10)"  
    )
    collaboration_required = models.BooleanField(
        default=False,
        help_text="Does this task require collaboration with others?"
    )
    suggested_team_members = models.JSONField(
        default=list,
        blank=True,
        help_text="AI-suggested team members for collaborative tasks"
    )
    
    # Risk Management Fields
    risk_likelihood = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(3)],
        choices=[(1, 'Low'), (2, 'Medium'), (3, 'High')],
        help_text="Risk likelihood score (1=Low, 2=Medium, 3=High)"
    )
    risk_impact = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(3)],
        choices=[(1, 'Low'), (2, 'Medium'), (3, 'High')],
        help_text="Risk impact score (1=Low, 2=Medium, 3=High)"
    )
    risk_score = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(9)],
        help_text="AI-calculated risk score (Likelihood × Impact, range 1-9)"
    )
    risk_level = models.CharField(
        max_length=10,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical'),
        ],
        blank=True,
        null=True,
        help_text="AI-determined risk level classification"
    )
    risk_indicators = models.JSONField(
        default=list,
        blank=True,
        help_text="Key indicators to monitor for this risk (from AI analysis)"
    )
    mitigation_suggestions = models.JSONField(
        default=list,
        blank=True,
        help_text="AI-generated mitigation strategies and action plans"
    )
    risk_analysis = models.JSONField(
        default=dict,
        blank=True,
        help_text="Complete AI risk analysis including reasoning and factors"
    )
    last_risk_assessment = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When AI last performed risk assessment for this task"
    )
    
    # Task Dependency Management (adapted from ReqManager)
    parent_task = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subtasks',
        help_text="Parent task for this subtask"
    )
    related_tasks = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=False,
        related_name='related_to',
        help_text="Tasks that are related but not parent-child"
    )
    # Gantt Chart Dependencies (blocking tasks)
    dependencies = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=False,
        related_name='dependent_tasks',
        help_text="Tasks that must be completed before this task can start"
    )
    dependency_chain = models.JSONField(
        default=list,
        blank=True,
        help_text="Ordered list of task IDs showing complete dependency chain"
    )
    
    # AI-Generated Dependency Suggestions
    suggested_dependencies = models.JSONField(
        default=list,
        blank=True,
        help_text="AI-suggested task dependencies based on description analysis"
    )
    last_dependency_analysis = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When AI last analyzed this task for dependency suggestions"
    )
    
    # Predictive Task Completion Fields
    completed_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Actual completion timestamp (when progress reached 100%)"
    )
    actual_duration_days = models.FloatField(
        blank=True,
        null=True,
        help_text="Actual days taken to complete (start_date to completed_at)"
    )
    predicted_completion_date = models.DateTimeField(
        blank=True,
        null=True,
        help_text="AI-predicted completion date based on historical data"
    )
    prediction_confidence = models.FloatField(
        blank=True,
        null=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence score for prediction (0.0-1.0)"
    )
    prediction_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Prediction details: confidence_interval, based_on_tasks, factors"
    )
    last_prediction_update = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When prediction was last calculated"
    )
    
    # Demo Mode Support
    created_by_session = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Session ID if created in demo mode (for cleanup)"
    )
    is_seed_demo_data = models.BooleanField(
        default=False,
        help_text="True if this is original seed demo data (not user-created)."
    )

    # WIP Age Tracking
    column_entered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the task last entered its current column (used for WIP age calculation)"
    )

    # Item Type (task vs milestone vs epic)
    ITEM_TYPE_CHOICES = [
        ('task', 'Task'),
        ('milestone', 'Milestone'),
        ('epic', 'Epic'),
    ]
    item_type = models.CharField(
        max_length=20,
        choices=ITEM_TYPE_CHOICES,
        default='task',
        help_text="Whether this item is a regular task, a milestone marker, or an epic container"
    )

    MILESTONE_STATUS_CHOICES = [
        ('upcoming', 'Upcoming'),
        ('completed', 'Completed'),
    ]
    milestone_status = models.CharField(
        max_length=20,
        choices=MILESTONE_STATUS_CHOICES,
        blank=True,
        null=True,
        help_text="Status of the milestone (only used when item_type='milestone')"
    )
    position_after_task = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='preceded_milestones',
        help_text="For milestones: which task this milestone appears after in the Gantt chart rows"
    )

    class Meta:
        ordering = ['position']
        indexes = [
            models.Index(fields=['column', 'position']),
            models.Index(fields=['assigned_to']),
            models.Index(fields=['created_by']),
            models.Index(fields=['due_date']),
            models.Index(fields=['progress']),
            models.Index(fields=['priority']),
        ]
    
    def __str__(self):
        return self.title

    @property
    def is_epic(self):
        """Convenience check for epic item type."""
        return self.item_type == 'epic'

    @property
    def checklist_progress(self):
        """Return checklist completion dict {completed, total} or None if no items."""
        items = self.checklist_items.all()
        total = items.count()
        if total == 0:
            return None
        completed = items.filter(is_completed=True).count()
        return {'completed': completed, 'total': total}

    @property
    def checklist_percentage(self):
        """Return checklist completion percentage (0-100) or None if no items."""
        progress = self.checklist_progress
        if progress is None:
            return None
        if progress['total'] == 0:
            return 0
        return int((progress['completed'] / progress['total']) * 100)

    @property
    def progress_status(self):
        """
        Computed schedule status badge for the task.

        Returns one of:
          'late'      — due date has passed and task is not complete
          'at_risk'   — task is falling behind its expected pace
          'on_track'  — task is progressing as expected
          None        — no due date set, cannot determine status

        Logic
        -----
        1. If no due_date → None
        2. If due_date is in the past and progress < 100 → 'late'
        3. If start_date is available:
             expected_pct = elapsed / total_duration * 100
             if (expected_pct - progress) > 15 → 'at_risk'
        4. If no start_date but due in ≤ 3 days and progress < 80 → 'at_risk'
        5. Otherwise → 'on_track'
        """
        if not self.due_date:
            return None
        if self.progress >= 100:
            return 'on_track'

        now = timezone.now()
        # Normalise due_date to an aware datetime
        due = self.due_date
        if timezone.is_naive(due):
            due = timezone.make_aware(due)

        if due < now:
            return 'late'

        # At-risk calculation
        if self.start_date:
            # Convert start_date (date) to aware datetime at midnight
            import datetime as _dt
            start_dt = timezone.make_aware(
                _dt.datetime.combine(self.start_date, _dt.time(12, 0))
            )
            total_seconds = (due - start_dt).total_seconds()
            if total_seconds > 0:
                elapsed_seconds = (now - start_dt).total_seconds()
                if elapsed_seconds > 0:
                    expected_pct = min((elapsed_seconds / total_seconds) * 100, 100)
                    if (expected_pct - self.progress) > 15:
                        return 'at_risk'
        else:
            # Fallback: warn if due within 3 days and progress is below 80 %
            days_remaining = (due - now).total_seconds() / 86400
            if days_remaining <= 3 and self.progress < 80:
                return 'at_risk'

        return 'on_track'

    def duration_days(self):
        """Calculate task duration in days"""
        if self.start_date and self.due_date:
            # Convert due_date to date if it's datetime
            due = self.due_date.date() if hasattr(self.due_date, 'date') else self.due_date
            return (due - self.start_date).days
        return 0
    
    def get_all_subtasks(self):
        """Get all subtasks recursively"""
        subtasks = list(self.subtasks.all())
        for subtask in subtasks:
            subtasks.extend(subtask.get_all_subtasks())
        return subtasks
    
    def get_all_parent_tasks(self):
        """Get all parent tasks up the hierarchy"""
        parents = []
        current = self.parent_task
        while current:
            parents.append(current)
            current = current.parent_task
        return parents
    
    def get_dependency_level(self):
        """Get the nesting level of this task in the hierarchy"""
        level = 0
        current = self.parent_task
        while current:
            level += 1
            current = current.parent_task
        return level
    
    def has_circular_dependency(self, potential_parent):
        """Check if setting a parent would create a circular dependency"""
        if potential_parent is None:
            return False
        if potential_parent == self:
            return True
        return self in potential_parent.get_all_parent_tasks() or potential_parent in self.get_all_subtasks()
    
    def update_dependency_chain(self):
        """Update the dependency chain based on parent relationships"""
        chain = []
        current = self
        while current:
            chain.insert(0, current.id)
            current = current.parent_task
        self.dependency_chain = chain
        self.save()
    
    def save(self, *args, **kwargs):
        """Override save to track completion and update predictions"""
        # Track completion timestamp
        if self.progress == 100 and not self.completed_at:
            self.completed_at = timezone.now()
            
            # Calculate actual duration if start_date exists
            if self.start_date:
                # start_date is a DateField (datetime.date), completed_at is DateTimeField
                # Convert to dates before subtraction
                completion_date = self.completed_at.date() if hasattr(self.completed_at, 'date') else self.completed_at
                start_date_val = self.start_date if isinstance(self.start_date, date) else self.start_date.date()
                duration = (completion_date - start_date_val).days
                self.actual_duration_days = max(0.5, duration)  # Minimum 0.5 days
        
        # Reset completion if progress drops below 100
        elif self.progress < 100 and self.completed_at:
            self.completed_at = None
            self.actual_duration_days = None
        
        super().save(*args, **kwargs)
    
    def get_velocity_factor(self):
        """Calculate team member's velocity factor based on historical data"""
        if not self.assigned_to:
            return 1.0
        
        from django.db.models import Avg
        
        # Get completed tasks by this user with similar complexity
        completed_tasks = Task.objects.filter(
            assigned_to=self.assigned_to,
            progress=100,
            actual_duration_days__isnull=False,
            complexity_score__range=(max(1, self.complexity_score - 2), 
                                    min(10, self.complexity_score + 2))
        ).exclude(id=self.id)
        
        avg_duration = completed_tasks.aggregate(
            avg=Avg('actual_duration_days')
        )['avg']
        
        if avg_duration and avg_duration > 0:
            # Calculate velocity relative to baseline
            baseline = self.complexity_score * 1.5  # Baseline: 1.5 days per complexity point
            return avg_duration / baseline
        
        return 1.0

class ChecklistItem(models.Model):
    """Individual checklist item within a task — used for AI-generated sub-task breakdowns."""
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    SOURCE_CHOICES = [
        ('manual', 'Manual'),
        ('ai_generated', 'AI Generated'),
    ]

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='checklist_items')
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True, null=True)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(blank=True, null=True)
    completed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, blank=True, null=True, related_name='completed_checklist_items'
    )
    position = models.IntegerField(default=0)
    estimated_effort = models.CharField(max_length=50, blank=True, help_text="e.g. '2.5 hrs', '1 day'")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='manual')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position', 'created_at']
        indexes = [
            models.Index(fields=['task', 'position']),
        ]

    def __str__(self):
        status = '✓' if self.is_completed else '○'
        return f"[{status}] {self.title}"


class Comment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['task', '-created_at']),
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        return f"Comment by {self.user.username} on {self.task.title}"

class TaskActivity(models.Model):
    ACTIVITY_CHOICES = [
        ('created', 'Created'),
        ('moved', 'Moved'),
        ('assigned', 'Assigned'),
        ('updated', 'Updated'),
        ('commented', 'Commented'),
        ('label_added', 'Label Added'),
        ('label_removed', 'Label Removed'),
    ]
    
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='activities')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_CHOICES)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Task Activities'
        indexes = [
            models.Index(fields=['task', '-created_at']),
            models.Index(fields=['user']),
            models.Index(fields=['activity_type']),
        ]
    
    def __str__(self):
        return f"{self.activity_type} by {self.user.username} on {self.task.title}"

class MeetingTranscript(models.Model):
    MEETING_TYPE_CHOICES = [
        ('standup', 'Daily Standup'),
        ('planning', 'Sprint Planning'),
        ('review', 'Review Meeting'),
        ('retrospective', 'Retrospective'),
        ('general', 'General Meeting'),
    ]
    
    PROCESSING_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    title = models.CharField(max_length=200, help_text="Meeting title or topic")
    meeting_type = models.CharField(max_length=20, choices=MEETING_TYPE_CHOICES, default='general')
    meeting_date = models.DateField(help_text="Date when the meeting occurred")
    transcript_text = models.TextField(help_text="Raw meeting transcript")
    transcript_file = models.FileField(upload_to='meeting_transcripts/', blank=True, null=True, 
                                     help_text="Uploaded transcript file")
    
    # Processing information
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='meeting_transcripts')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='meeting_transcripts')
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    processing_status = models.CharField(max_length=20, choices=PROCESSING_STATUS_CHOICES, default='pending')
    
    # AI extraction results
    extraction_results = models.JSONField(default=dict, blank=True, 
                                        help_text="AI extraction results including tasks and metadata")
    tasks_extracted_count = models.IntegerField(default=0)
    tasks_created_count = models.IntegerField(default=0)
    
    # Meeting context
    participants = models.JSONField(default=list, blank=True, 
                                  help_text="List of meeting participants")
    meeting_context = models.JSONField(default=dict, blank=True,
                                     help_text="Additional meeting context and metadata")
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.title} - {self.meeting_date}"


class ResourceDemandForecast(models.Model):
    """
    Store predictive analytics for team member demand and workload
    Adapted from ResourcePro for PrizmAI's kanban board
    """
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='forecasts')
    forecast_date = models.DateField(auto_now_add=True, help_text="Date when forecast was generated")
    period_start = models.DateField(help_text="Start date of forecast period")
    period_end = models.DateField(help_text="End date of forecast period")
    
    # Resource info
    resource_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='demand_forecasts', 
                                     null=True, blank=True)
    resource_role = models.CharField(max_length=100, help_text="Role/Title of the resource")
    
    # Forecast data
    predicted_workload_hours = models.DecimalField(max_digits=8, decimal_places=2, 
                                                   help_text="Predicted hours of work needed")
    available_capacity_hours = models.DecimalField(max_digits=8, decimal_places=2,
                                                  help_text="Available hours in period")
    confidence_score = models.DecimalField(max_digits=3, decimal_places=2, default=0.5,
                                         help_text="Confidence score (0.00-1.00)")
    forecast_explainability = models.JSONField(
        default=dict,
        blank=True,
        help_text="Explainability data: confidence breakdown, assumptions, calculation details."
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-forecast_date', 'resource_user']
        verbose_name = 'Resource Demand Forecast'
        verbose_name_plural = 'Resource Demand Forecasts'
    
    def __str__(self):
        resource_name = self.resource_user.username if self.resource_user else self.resource_role
        return f"Forecast for {resource_name} - {self.period_start} to {self.period_end}"
    
    @property
    def is_overloaded(self):
        """Check if workload exceeds capacity"""
        return self.predicted_workload_hours > self.available_capacity_hours
    
    @property
    def utilization_percentage(self):
        """Calculate utilization percentage"""
        if self.available_capacity_hours > 0:
            return (self.predicted_workload_hours / self.available_capacity_hours) * 100
        return 0


class TeamCapacityAlert(models.Model):
    """
    Track alerts when team members or team is overloaded
    """
    ALERT_LEVEL_CHOICES = [
        ('warning', 'Warning - 80-100% capacity'),
        ('critical', 'Critical - Over 100% capacity'),
        ('resolved', 'Resolved'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
    ]
    
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='capacity_alerts')
    forecast = models.ForeignKey(ResourceDemandForecast, on_delete=models.CASCADE, 
                                related_name='alerts', null=True, blank=True)
    
    # Alert info
    alert_type = models.CharField(max_length=20, choices=[
        ('individual', 'Individual Overload'),
        ('team', 'Team Overload'),
    ], default='individual')
    alert_level = models.CharField(max_length=20, choices=ALERT_LEVEL_CHOICES, default='warning')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Context
    resource_user = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='capacity_alerts',
                                     null=True, blank=True, help_text="User who is overloaded")
    message = models.TextField(help_text="Alert message with details")
    workload_percentage = models.IntegerField(default=0, help_text="Current utilization percentage")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(blank=True, null=True)
    acknowledged_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='acknowledged_alerts',
                                       null=True, blank=True)
    resolved_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        resource_name = self.resource_user.username if self.resource_user else 'Team'
        return f"{self.get_alert_type_display()} Alert for {resource_name} - {self.get_alert_level_display()}"


class WorkloadDistributionRecommendation(models.Model):
    """
    AI-generated recommendations for optimal workload distribution
    """
    RECOMMENDATION_TYPE_CHOICES = [
        ('reassign', 'Task Reassignment'),
        ('defer', 'Defer/Postpone'),
        ('distribute', 'Distribute to Multiple'),
        ('hire', 'Hire/Allocate Resource'),
        ('optimize', 'Optimize Timeline'),
    ]
    
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='distribution_recommendations')
    forecast = models.ForeignKey(ResourceDemandForecast, on_delete=models.CASCADE,
                                related_name='recommendations', null=True, blank=True)
    
    recommendation_type = models.CharField(max_length=20, choices=RECOMMENDATION_TYPE_CHOICES)
    priority = models.IntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(10)],
                                  help_text="Priority (1=low, 10=high)")
    
    # Recommendation details
    title = models.CharField(max_length=200, help_text="Short title of recommendation")
    description = models.TextField(help_text="Detailed recommendation description")
    affected_tasks = models.ManyToManyField(Task, related_name='distribution_recommendations', blank=True)
    affected_users = models.ManyToManyField(User, related_name='distribution_recommendations', blank=True)
    
    # Impact metrics
    expected_capacity_savings_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0,
                                                         help_text="Hours this recommendation could save")
    confidence_score = models.DecimalField(max_digits=3, decimal_places=2, default=0.75,
                                         help_text="Confidence in recommendation (0-1)")
    
    # Status
    status = models.CharField(max_length=20, default='pending', choices=[
        ('pending', 'Pending Review'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('implemented', 'Implemented'),
    ])
    
    created_at = models.DateTimeField(auto_now_add=True)
    implemented_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ['-priority', '-created_at']
    
    def __str__(self):
        return f"{self.get_recommendation_type_display()}: {self.title}"


class TaskFile(models.Model):
    """File attachments for tasks"""
    ALLOWED_FILE_TYPES = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'jpg', 'jpeg', 'png']
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='file_attachments')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='task_file_uploads')
    file = models.FileField(upload_to='tasks/%Y/%m/%d/')
    filename = models.CharField(max_length=255)
    file_size = models.BigIntegerField(help_text="File size in bytes")
    file_type = models.CharField(max_length=10, help_text="File extension")
    description = models.TextField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(blank=True, null=True)  # Soft delete

    # AI analysis fields
    ai_summary = models.TextField(blank=True, default='', help_text="AI-generated summary of file contents")
    ai_tasks_suggested = models.JSONField(default=list, blank=True, help_text="AI-suggested tasks extracted from file")
    ai_analyzed_at = models.DateTimeField(null=True, blank=True, help_text="When AI last analyzed this file")
    
    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['task', 'uploaded_at']),
            models.Index(fields=['uploaded_by', 'uploaded_at']),
        ]
    
    def __str__(self):
        return f"{self.filename} for {self.task.title}"
    
    def is_deleted(self):
        """Check if file is soft-deleted"""
        return self.deleted_at is not None
    
    def get_file_icon(self):
        """Get Bootstrap icon class based on file type"""
        icon_map = {
            'pdf': 'fa-file-pdf',
            'doc': 'fa-file-word',
            'docx': 'fa-file-word',
            'xls': 'fa-file-excel',
            'xlsx': 'fa-file-excel',
            'ppt': 'fa-file-powerpoint',
            'pptx': 'fa-file-powerpoint',
            'jpg': 'fa-file-image',
            'jpeg': 'fa-file-image',
            'png': 'fa-file-image',
        }
        return icon_map.get(self.file_type.lower(), 'fa-file')
    
    @staticmethod
    def is_valid_file_type(filename):
        """Validate file type"""
        ext = filename.split('.')[-1].lower()
        return ext in TaskFile.ALLOWED_FILE_TYPES


class TeamSkillProfile(models.Model):
    """
    Aggregated skill inventory for a team/board
    Provides high-level view of available skills and capacity
    """
    board = models.OneToOneField(Board, on_delete=models.CASCADE, related_name='skill_profile')
    
    # Aggregate skill data
    skill_inventory = models.JSONField(
        default=dict,
        help_text="Dictionary of available skills: {'Python': {'expert': 2, 'intermediate': 3, 'beginner': 1}}"
    )
    total_capacity_hours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Total team capacity in hours per week"
    )
    utilized_capacity_hours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Currently utilized hours"
    )
    
    # Metadata
    last_updated = models.DateTimeField(auto_now=True)
    last_analysis = models.DateTimeField(blank=True, null=True, help_text="Last AI skill analysis timestamp")
    
    class Meta:
        verbose_name = 'Team Skill Profile'
        verbose_name_plural = 'Team Skill Profiles'
    
    def __str__(self):
        return f"Skill Profile for {self.board.name}"
    
    @property
    def utilization_percentage(self):
        """Calculate team utilization"""
        if self.total_capacity_hours == 0:
            return 0
        return min(100, (self.utilized_capacity_hours / self.total_capacity_hours) * 100)
    
    @property
    def available_skills(self):
        """Get list of all available skill names"""
        return list(self.skill_inventory.keys())


class SkillGap(models.Model):
    """
    Identified skill gaps between required and available skills
    AI-calculated with recommendations for remediation
    """
    GAP_SEVERITY_CHOICES = [
        ('low', 'Low - Can work around'),
        ('medium', 'Medium - May cause delays'),
        ('high', 'High - Blocking work'),
        ('critical', 'Critical - Cannot proceed'),
    ]
    
    GAP_STATUS_CHOICES = [
        ('identified', 'Identified'),
        ('acknowledged', 'Acknowledged'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('accepted', 'Accepted Risk'),
    ]
    
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='skill_gaps')
    
    # Gap details
    skill_name = models.CharField(max_length=100, help_text="Name of the missing/insufficient skill")
    proficiency_level = models.CharField(
        max_length=20,
        choices=[
            ('beginner', 'Beginner'),
            ('intermediate', 'Intermediate'),
            ('advanced', 'Advanced'),
            ('expert', 'Expert'),
        ],
        help_text="Required proficiency level"
    )
    required_count = models.IntegerField(default=1, help_text="Number of team members needed with this skill")
    available_count = models.IntegerField(default=0, help_text="Number of team members currently with this skill")
    gap_count = models.IntegerField(help_text="Difference between required and available (auto-calculated)")
    
    # Context
    severity = models.CharField(max_length=20, choices=GAP_SEVERITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=GAP_STATUS_CHOICES, default='identified')
    
    # Associated data
    affected_tasks = models.ManyToManyField(Task, related_name='skill_gaps', blank=True,
                                           help_text="Tasks that require this skill")
    sprint_period_start = models.DateField(blank=True, null=True, help_text="Sprint/period when gap was identified")
    sprint_period_end = models.DateField(blank=True, null=True)
    
    # AI Analysis
    ai_recommendations = models.JSONField(
        default=list,
        help_text="AI-generated recommendations: [{'type': 'hire', 'details': '...', 'priority': 1}]"
    )
    estimated_impact_hours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Estimated hours of delay/impact if not addressed"
    )
    confidence_score = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.75,
        help_text="AI confidence in this gap analysis (0-1)"
    )
    
    # Tracking
    identified_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(blank=True, null=True)
    acknowledged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='acknowledged_skill_gaps')
    
    class Meta:
        ordering = ['-severity', '-identified_at']
        verbose_name = 'Skill Gap'
        verbose_name_plural = 'Skill Gaps'
        indexes = [
            models.Index(fields=['board', 'status']),
            models.Index(fields=['skill_name', 'proficiency_level']),
        ]
    
    def __str__(self):
        return f"{self.skill_name} ({self.proficiency_level}) - Gap: {self.gap_count} - {self.board.name}"
    
    def save(self, *args, **kwargs):
        """Auto-calculate gap_count on save"""
        self.gap_count = max(0, self.required_count - self.available_count)
        super().save(*args, **kwargs)
    
    @property
    def is_critical(self):
        """Check if this is a critical gap"""
        return self.severity in ['high', 'critical'] or self.gap_count >= 2
    
    @property
    def gap_percentage(self):
        """Calculate gap as percentage of requirement"""
        if self.required_count == 0:
            return 0
        return (self.gap_count / self.required_count) * 100


class SkillDevelopmentPlan(models.Model):
    """
    Track training and skill development initiatives to address gaps
    Includes hiring, training, and work redistribution plans
    """
    PLAN_TYPE_CHOICES = [
        ('training', 'Training/Upskilling'),
        ('hiring', 'Hire New Resource'),
        ('contractor', 'Contract Resource'),
        ('redistribute', 'Redistribute Work'),
        ('mentorship', 'Mentorship Program'),
        ('cross_training', 'Cross Training'),
    ]
    
    PLAN_STATUS_CHOICES = [
        ('proposed', 'Proposed'),
        ('approved', 'Approved'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    skill_gap = models.ForeignKey(SkillGap, on_delete=models.CASCADE, related_name='development_plans')
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='skill_development_plans')
    
    # Plan details
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPE_CHOICES)
    title = models.CharField(max_length=200, help_text="Brief title of the development plan")
    description = models.TextField(help_text="Detailed plan description and action steps")
    
    # Targets
    target_users = models.ManyToManyField(User, related_name='skill_development_plans', blank=True,
                                         help_text="Team members involved in this plan")
    target_skill = models.CharField(max_length=100, help_text="Skill being developed")
    target_proficiency = models.CharField(
        max_length=20,
        choices=[
            ('beginner', 'Beginner'),
            ('intermediate', 'Intermediate'),
            ('advanced', 'Advanced'),
            ('expert', 'Expert'),
        ]
    )
    
    # Timeline and budget
    start_date = models.DateField(blank=True, null=True)
    target_completion_date = models.DateField(blank=True, null=True)
    actual_completion_date = models.DateField(blank=True, null=True)
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True,
                                        help_text="Estimated cost (training fees, hiring budget, etc.)")
    estimated_hours = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True,
                                         help_text="Estimated hours investment")
    
    # Status and progress
    status = models.CharField(max_length=20, choices=PLAN_STATUS_CHOICES, default='proposed')
    progress_percentage = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Impact tracking
    expected_impact = models.TextField(blank=True, help_text="Expected impact on team capability")
    actual_impact = models.TextField(blank=True, help_text="Measured impact after completion")
    success_metrics = models.JSONField(
        default=list,
        blank=True,
        help_text="Metrics to track success: [{'metric': 'Tasks completed', 'target': 5, 'actual': 3}]"
    )
    
    # Ownership
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_development_plans')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='owned_development_plans',
                                   help_text="Person responsible for executing this plan")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # AI-generated recommendations
    ai_suggested = models.BooleanField(default=False, help_text="Was this plan AI-generated?")
    ai_confidence = models.DecimalField(max_digits=3, decimal_places=2, blank=True, null=True,
                                       help_text="AI confidence in this recommendation (0-1)")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Skill Development Plan'
        verbose_name_plural = 'Skill Development Plans'
        indexes = [
            models.Index(fields=['board', 'status']),
            models.Index(fields=['skill_gap']),
        ]
    
    def __str__(self):
        return f"{self.get_plan_type_display()}: {self.title}"
    
    @property
    def is_overdue(self):
        """Check if plan is overdue"""
        if self.target_completion_date and self.status not in ['completed', 'cancelled']:
            from django.utils import timezone
            return timezone.now().date() > self.target_completion_date
        return False
    
    @property
    def days_until_target(self):
        """Calculate days until target completion"""
        if self.target_completion_date:
            from django.utils import timezone
            delta = self.target_completion_date - timezone.now().date()
            return delta.days
        return None


class ScopeChangeSnapshot(models.Model):
    """
    Captures board scope metrics at a point in time to track scope creep
    Used for historical comparison and trend analysis
    """
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='scope_snapshots')
    snapshot_date = models.DateTimeField(auto_now_add=True)
    
    # Scope metrics
    total_tasks = models.IntegerField(help_text="Total number of tasks")
    total_complexity_points = models.IntegerField(default=0, help_text="Sum of all task complexity scores")
    avg_complexity = models.FloatField(default=0.0, help_text="Average complexity per task")
    high_priority_tasks = models.IntegerField(default=0, help_text="Count of high/urgent priority tasks")
    urgent_priority_tasks = models.IntegerField(default=0, help_text="Count of urgent priority tasks")
    
    # Task status breakdown
    todo_tasks = models.IntegerField(default=0, help_text="Tasks in To Do columns")
    in_progress_tasks = models.IntegerField(default=0, help_text="Tasks in In Progress columns")
    completed_tasks = models.IntegerField(default=0, help_text="Tasks in Done columns")
    
    # Baseline tracking
    is_baseline = models.BooleanField(default=False, help_text="Is this the baseline snapshot?")
    baseline_snapshot = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='comparison_snapshots',
                                         help_text="Reference to baseline snapshot for comparison")
    
    # AI analysis results
    scope_change_percentage = models.FloatField(null=True, blank=True, 
                                               help_text="Percentage change from baseline")
    complexity_change_percentage = models.FloatField(null=True, blank=True,
                                                     help_text="Percentage change in complexity")
    ai_analysis = models.JSONField(null=True, blank=True,
                                   help_text="AI-generated analysis of scope changes")
    predicted_delay_days = models.IntegerField(null=True, blank=True,
                                              help_text="AI-predicted delay in days")
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='created_snapshots')
    snapshot_type = models.CharField(max_length=20, 
                                     choices=[
                                         ('manual', 'Manual'),
                                         ('scheduled', 'Scheduled'),
                                         ('milestone', 'Milestone'),
                                     ],
                                     default='scheduled')
    notes = models.TextField(blank=True, null=True, help_text="Optional notes about this snapshot")
    
    class Meta:
        ordering = ['-snapshot_date']
        verbose_name = 'Scope Change Snapshot'
        verbose_name_plural = 'Scope Change Snapshots'
        indexes = [
            models.Index(fields=['board', '-snapshot_date']),
            models.Index(fields=['board', 'is_baseline']),
        ]
    
    def __str__(self):
        baseline_str = " (Baseline)" if self.is_baseline else ""
        return f"{self.board.name} - {self.snapshot_date.strftime('%Y-%m-%d')}{baseline_str}"
    
    def calculate_changes_from_baseline(self):
        """Calculate percentage changes from baseline snapshot"""
        if not self.baseline_snapshot:
            return None
        
        baseline = self.baseline_snapshot
        
        # Calculate scope change
        if baseline.total_tasks > 0:
            self.scope_change_percentage = round(
                ((self.total_tasks - baseline.total_tasks) / baseline.total_tasks) * 100, 2
            )
        
        # Calculate complexity change
        if baseline.total_complexity_points > 0:
            self.complexity_change_percentage = round(
                ((self.total_complexity_points - baseline.total_complexity_points) / 
                 baseline.total_complexity_points) * 100, 2
            )
        
        return {
            'scope_change': self.scope_change_percentage,
            'complexity_change': self.complexity_change_percentage,
            'tasks_added': self.total_tasks - baseline.total_tasks,
            'complexity_added': self.total_complexity_points - baseline.total_complexity_points,
        }


class ScopeCreepAlert(models.Model):
    """
    Alerts when scope increases beyond acceptable thresholds
    Helps prevent project timeline slippage due to uncontrolled scope changes
    """
    SEVERITY_CHOICES = [
        ('info', 'Info - Minor increase (<15%)'),
        ('warning', 'Warning - Moderate increase (15-30%)'),
        ('critical', 'Critical - Major increase (>30%)'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ]
    
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='scope_creep_alerts')
    snapshot = models.ForeignKey(ScopeChangeSnapshot, on_delete=models.CASCADE, 
                                related_name='generated_alerts')
    
    # Alert details
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Scope change metrics
    scope_increase_percentage = models.FloatField(help_text="Percentage increase in task count")
    complexity_increase_percentage = models.FloatField(default=0.0, 
                                                       help_text="Percentage increase in complexity")
    tasks_added = models.IntegerField(default=0, help_text="Number of tasks added")
    
    # Impact analysis
    predicted_delay_days = models.IntegerField(null=True, blank=True,
                                              help_text="Estimated project delay in days")
    timeline_at_risk = models.BooleanField(default=False, 
                                          help_text="Is the project timeline at risk?")
    
    # AI recommendations
    recommendations = models.JSONField(default=list, help_text="AI-generated recommendations")
    ai_summary = models.TextField(blank=True, null=True, 
                                 help_text="AI-generated summary of scope changes")
    
    # Alert lifecycle
    detected_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='acknowledged_scope_alerts')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='resolved_scope_alerts')
    resolution_notes = models.TextField(blank=True, null=True,
                                       help_text="Notes on how the alert was resolved")
    
    class Meta:
        ordering = ['-detected_at']
        verbose_name = 'Scope Creep Alert'
        verbose_name_plural = 'Scope Creep Alerts'
        indexes = [
            models.Index(fields=['board', 'status', '-detected_at']),
            models.Index(fields=['severity', 'status']),
        ]
    
    def __str__(self):
        return f"{self.get_severity_display()} - {self.board.name} (+{self.scope_increase_percentage}%)"
    
    def acknowledge(self, user):
        """Mark alert as acknowledged by user"""
        self.status = 'acknowledged'
        self.acknowledged_at = timezone.now()
        self.acknowledged_by = user
        self.save()
    
    def resolve(self, user, notes=None):
        """Mark alert as resolved"""
        self.status = 'resolved'
        self.resolved_at = timezone.now()
        self.resolved_by = user
        if notes:
            self.resolution_notes = notes
        self.save()
    
    @property
    def days_since_detected(self):
        """Calculate days since alert was detected"""
        delta = timezone.now() - self.detected_at
        return delta.days
    
    @property
    def is_unresolved(self):
        """Check if alert is still active or acknowledged but not resolved"""
        return self.status in ['active', 'acknowledged']


# Import scope autopsy models
from .scope_autopsy_models import ScopeAutopsyReport, ScopeTimelineEvent

# Import security and permission models to register them with Django
from .audit_models import SystemAuditLog, SecurityEvent, DataAccessLog

# Legacy permission_models.py deleted in RBAC Phase 1.
# PermissionAuditLog and ColumnPermission deferred to Phase 3.


class BoardMembership(models.Model):
    """
    RBAC board membership — replaces the legacy Board.members M2M and the
    deleted legacy Role-FK-based BoardMembership from permission_models.py.
    Role is a simple CharField (owner / member / viewer).
    """
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('member', 'Member'),
        ('viewer', 'Viewer'),
    ]

    board = models.ForeignKey(
        Board, on_delete=models.CASCADE, related_name='memberships'
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='board_memberships'
    )
    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default='member',
        help_text="Owner: full control. Member: create/edit tasks. Viewer: read-only."
    )
    added_at = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='added_board_members'
    )

    class Meta:
        unique_together = ('board', 'user')
        ordering = ['board', '-added_at']
        indexes = [
            models.Index(fields=['board', 'user']),
            models.Index(fields=['user', 'role']),
        ]

    def __str__(self):
        return f"{self.user.username} — {self.board.name} ({self.get_role_display()})"


class StrategicMembership(models.Model):
    """
    Generic-FK membership for Goal / Mission / Strategy level access.
    One model covers all three strategic levels.
    """
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('member', 'Member'),
        ('viewer', 'Viewer'),
    ]

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='strategic_memberships'
    )
    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default='member',
        help_text="Owner: full control + invite. Member: contribute. Viewer: read-only."
    )

    class Meta:
        unique_together = ('content_type', 'object_id', 'user')
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['user', 'role']),
        ]

    def __str__(self):
        return f"{self.user.username} — {self.content_type.model} #{self.object_id} ({self.get_role_display()})"


class DemoSandbox(models.Model):
    """
    Personal demo sandbox — private copy of all demo template boards for a user.
    OneToOneField enforces one sandbox per user at the DB level.

    Persistent model: the sandbox lives as long as the user's account.
    Users switch between Demo Workspace and My Workspace freely.
    The only control is a Reset button to wipe back to template state.
    """
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='demo_sandbox'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_reset_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the user last reset their demo. NULL on first provision."
    )
    reassigned_tasks = models.JSONField(
        default=dict, blank=True,
        help_text=(
            "Maps task IDs (str) to original assignee user IDs. "
            "Used to restore assignments when user leaves demo mode."
        ),
    )

    def __str__(self):
        return f"Sandbox for {self.user.username} (created {self.created_at})"


class BoardInvitation(models.Model):
    """Email-based invitation to join a specific board."""

    STATUS_PENDING = 'pending'
    STATUS_ACCEPTED = 'accepted'
    STATUS_EXPIRED = 'expired'
    STATUS_REVOKED = 'revoked'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_EXPIRED, 'Expired'),
        (STATUS_REVOKED, 'Revoked'),
    ]

    board = models.ForeignKey(
        Board, on_delete=models.CASCADE, related_name='invitations'
    )
    invited_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='sent_invitations'
    )
    email = models.EmailField()
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='accepted_invitations'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Invite to {self.board.name} for {self.email} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=48)
        super().save(*args, **kwargs)

    def is_valid(self):
        """Return True if the invitation is still usable."""
        if self.status != self.STATUS_PENDING:
            return False
        if timezone.now() > self.expires_at:
            # Auto-mark as expired
            self.status = self.STATUS_EXPIRED
            self.save(update_fields=['status'])
            return False
        return True

    def mark_accepted(self, user):
        self.status = self.STATUS_ACCEPTED
        self.accepted_at = timezone.now()
        self.accepted_by = user
        self.save()


# ---------------------------------------------------------------------------
# WORKSPACE MEMBERSHIP — Workspace-level member management with RBAC
# ---------------------------------------------------------------------------

class WorkspaceMembership(models.Model):
    """
    Workspace-level membership with a single RBAC role that propagates
    to all boards within the workspace (current and future).
    """
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('member', 'Member'),
        ('viewer', 'Viewer'),
    ]

    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name='memberships'
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='workspace_memberships'
    )
    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default='member',
        help_text="Owner: full control. Member: create/edit tasks. Viewer: read-only.",
    )
    added_at = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='added_workspace_members',
    )

    class Meta:
        unique_together = ('workspace', 'user')
        ordering = ['workspace', '-added_at']
        indexes = [
            models.Index(fields=['workspace', 'user']),
            models.Index(fields=['user', 'role']),
        ]

    def __str__(self):
        return f"{self.user.username} — {self.workspace.name} ({self.get_role_display()})"


class WorkspaceInvitation(models.Model):
    """Email-based invitation to join a workspace with a specific role."""

    STATUS_PENDING = 'pending'
    STATUS_ACCEPTED = 'accepted'
    STATUS_EXPIRED = 'expired'
    STATUS_REVOKED = 'revoked'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_EXPIRED, 'Expired'),
        (STATUS_REVOKED, 'Revoked'),
    ]

    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name='invitations',
    )
    invited_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='sent_workspace_invitations',
    )
    email = models.EmailField()
    role = models.CharField(
        max_length=10,
        choices=WorkspaceMembership.ROLE_CHOICES,
        default='member',
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='accepted_workspace_invitations',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Workspace invite to {self.workspace.name} for {self.email} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=48)
        super().save(*args, **kwargs)

    def is_valid(self):
        if self.status != self.STATUS_PENDING:
            return False
        if timezone.now() > self.expires_at:
            self.status = self.STATUS_EXPIRED
            self.save(update_fields=['status'])
            return False
        return True

    def mark_accepted(self, user):
        self.status = self.STATUS_ACCEPTED
        self.accepted_at = timezone.now()
        self.accepted_by = user
        self.save()


# ---------------------------------------------------------------------------
# SHADOW BOARD MODELS — Parallel Universe Simulator
# ---------------------------------------------------------------------------
# Import at the end to ensure all dependencies are loaded
from .shadow_models import ShadowBranch, BranchSnapshot, BranchDivergenceLog  # noqa: E402
from .access_request_models import AccessRequest  # noqa: E402


class CalendarEvent(models.Model):
    """
    Internal calendar events (meetings, OOO, busy blocks, team events).

    event_type controls how the event is interpreted and shown to others:
      meeting      — formal meeting; participants are invited
      out_of_office — holiday / sick day; shows as "unavailable" to teammates
      busy_block   — ad-hoc busy period (working on something, not available)
      team_event   — training, all-hands; visible to all board members

    visibility controls who sees the event on the calendar:
      team    (default) — teammates see you're blocked (but not the private reason)
      private           — only you see it; completely hidden from others
    """
    EVENT_TYPE_CHOICES = [
        ('meeting',       'Meeting'),
        ('out_of_office', 'Out of Office'),
        ('busy_block',    'Busy Block'),
        ('team_event',    'Team Event'),
    ]

    VISIBILITY_CHOICES = [
        ('team',    "Team can see I'm busy"),
        ('private', 'Private (only me)'),
    ]

    # Types that don't involve inviting other participants
    SOLO_TYPES = ('out_of_office', 'busy_block')

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES, default='meeting')
    visibility = models.CharField(
        max_length=10,
        choices=VISIBILITY_CHOICES,
        default='team',
        help_text="Controls whether teammates can see you're busy on this day",
    )

    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    is_all_day = models.BooleanField(default=False)

    location = models.CharField(max_length=255, blank=True, null=True,
                                help_text="Optional physical or virtual meeting location")

    # Optional board association
    board = models.ForeignKey(
        Board,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='calendar_events',
    )

    # Optional task link — lets a busy block say "I'm working on X today"
    linked_task = models.ForeignKey(
        'Task',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='calendar_events',
        help_text="Link to a task to give teammates context (e.g. 'busy on Auth System')",
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_calendar_events',
    )
    participants = models.ManyToManyField(
        User,
        blank=True,
        related_name='calendar_events',
        help_text="Users invited to this event (for Meetings and Team Events only)",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_datetime']
        indexes = [
            models.Index(fields=['start_datetime', 'end_datetime']),
            models.Index(fields=['created_by']),
        ]

    def __str__(self):
        return f"{self.title} ({self.start_datetime.date()})"

    def get_event_type_color(self):
        """Return a hex colour for FullCalendar based on event type.
        Colours are intentionally distinct from task priority colours
        (urgent=#dc3545 red, high=#fd7e14 orange, medium=#0d6efd blue, low=#198754 green)
        and assignee palette colours.
        """
        return {
            'meeting':       '#6f42c1',  # purple
            'out_of_office': '#f59e0b',  # amber  — vacation/holiday feel
            'busy_block':    '#64748b',  # slate  — "I'm blocked/working"
            'team_event':    '#0284c7',  # sky blue — company-wide
        }.get(self.event_type, '#6c757d')

    @property
    def is_solo_type(self):
        """True for event types that don't make sense to invite participants to."""
        return self.event_type in self.SOLO_TYPES
