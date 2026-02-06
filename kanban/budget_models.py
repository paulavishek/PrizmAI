"""
Budget & ROI Tracking Models
Tracks project budgets, task costs, time spent, and ROI metrics with AI optimization
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from kanban.models import Task, Board, Column


class ProjectBudget(models.Model):
    """
    Project budget tracking for boards
    """
    CURRENCY_CHOICES = [
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
        ('INR', 'Indian Rupee'),
        ('JPY', 'Japanese Yen'),
    ]
    
    board = models.OneToOneField(
        Board,
        on_delete=models.CASCADE,
        related_name='budget',
        help_text="Board this budget is for"
    )
    
    # Budget allocation
    allocated_budget = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Total allocated budget for the project"
    )
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default='USD',
        help_text="Currency for budget tracking"
    )
    
    # Time budget
    allocated_hours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Total allocated hours for the project"
    )
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_budgets'
    )
    
    # Alert thresholds
    warning_threshold = models.IntegerField(
        default=80,
        validators=[MinValueValidator(1)],
        help_text="Warning threshold percentage (e.g., 80 for 80%)"
    )
    critical_threshold = models.IntegerField(
        default=95,
        validators=[MinValueValidator(1)],
        help_text="Critical threshold percentage (e.g., 95 for 95%)"
    )
    
    # AI learning
    ai_optimization_enabled = models.BooleanField(
        default=True,
        help_text="Enable AI-powered budget optimization"
    )
    last_ai_analysis = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time AI analyzed this budget"
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Project Budget'
        verbose_name_plural = 'Project Budgets'
    
    def __str__(self):
        return f"{self.board.name} - Budget: {self.currency} {self.allocated_budget}"
    
    def get_spent_amount(self):
        """Calculate total spent amount from task costs"""
        from django.db.models import Sum
        total = TaskCost.objects.filter(
            task__column__board=self.board
        ).aggregate(total=Sum('actual_cost'))['total'] or Decimal('0.00')
        return total
    
    def get_spent_hours(self):
        """Calculate total spent hours from time entries"""
        from django.db.models import Sum
        total = TimeEntry.objects.filter(
            task__column__board=self.board
        ).aggregate(total=Sum('hours_spent'))['total'] or Decimal('0.00')
        return total
    
    def get_budget_utilization_percent(self):
        """Calculate budget utilization percentage"""
        if self.allocated_budget <= 0:
            return 0
        spent = self.get_spent_amount()
        return float((spent / self.allocated_budget) * 100)
    
    def get_time_utilization_percent(self):
        """Calculate time utilization percentage"""
        if not self.allocated_hours or self.allocated_hours <= 0:
            return 0
        spent = self.get_spent_hours()
        return float((spent / self.allocated_hours) * 100)
    
    def get_remaining_budget(self):
        """Calculate remaining budget"""
        return self.allocated_budget - self.get_spent_amount()
    
    def get_status(self):
        """Get budget status: ok, warning, critical, over"""
        utilization = self.get_budget_utilization_percent()
        if utilization >= 100:
            return 'over'
        elif utilization >= self.critical_threshold:
            return 'critical'
        elif utilization >= self.warning_threshold:
            return 'warning'
        return 'ok'


class TaskCost(models.Model):
    """
    Cost tracking for individual tasks
    """
    task = models.OneToOneField(
        Task,
        on_delete=models.CASCADE,
        related_name='cost',
        help_text="Task this cost is for"
    )
    
    # Estimated costs
    estimated_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Estimated cost for this task"
    )
    estimated_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Estimated hours for this task"
    )
    
    # Actual costs
    actual_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Actual cost incurred"
    )
    
    # Labor costs (calculated from time entries)
    hourly_rate = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Hourly rate for labor cost calculation"
    )
    
    # Resource costs
    resource_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Cost of resources/materials"
    )
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Task Cost'
        verbose_name_plural = 'Task Costs'
    
    def __str__(self):
        return f"{self.task.title} - Cost: {self.actual_cost}"
    
    def get_total_actual_cost(self):
        """Calculate total actual cost including labor"""
        labor_cost = self.get_labor_cost()
        return self.actual_cost + labor_cost + self.resource_cost
    
    def get_labor_cost(self):
        """Calculate labor cost from time entries"""
        if not self.hourly_rate:
            return Decimal('0.00')
        total_hours = TimeEntry.objects.filter(task=self.task).aggregate(
            total=models.Sum('hours_spent')
        )['total'] or Decimal('0.00')
        return total_hours * self.hourly_rate
    
    def get_cost_variance(self):
        """Calculate variance between estimated and actual"""
        return self.get_total_actual_cost() - self.estimated_cost
    
    def get_cost_variance_percent(self):
        """Calculate variance percentage"""
        if self.estimated_cost <= 0:
            return 0
        variance = self.get_cost_variance()
        return float((variance / self.estimated_cost) * 100)
    
    def is_over_budget(self):
        """Check if task is over budget"""
        return self.get_total_actual_cost() > self.estimated_cost


class TimeEntry(models.Model):
    """
    Time tracking entries for tasks
    """
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='time_entries',
        help_text="Task this time entry is for"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='time_entries',
        help_text="User who logged this time"
    )
    
    # Time tracking
    hours_spent = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('0.01')),
            MaxValueValidator(Decimal('16.00'))
        ],
        help_text="Hours spent on this task (max 16 hours per entry)"
    )
    work_date = models.DateField(
        help_text="Date when work was performed"
    )
    
    # Description
    description = models.TextField(
        blank=True,
        help_text="Description of work performed"
    )
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-work_date', '-created_at']
        verbose_name = 'Time Entry'
        verbose_name_plural = 'Time Entries'
        indexes = [
            models.Index(fields=['task', 'work_date']),
            models.Index(fields=['user', 'work_date']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.hours_spent}h on {self.task.title}"


class ProjectROI(models.Model):
    """
    ROI tracking and analysis for projects
    """
    board = models.ForeignKey(
        Board,
        on_delete=models.CASCADE,
        related_name='roi_analyses',
        help_text="Board this ROI analysis is for"
    )
    
    # Value metrics
    expected_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Expected value/revenue from project"
    )
    realized_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Actual realized value"
    )
    
    # Snapshot date
    snapshot_date = models.DateTimeField(
        default=timezone.now,
        help_text="When this ROI snapshot was taken"
    )
    
    # Calculated metrics (stored for historical tracking)
    total_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Total cost at snapshot time"
    )
    roi_percentage = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="ROI percentage: (Value - Cost) / Cost * 100"
    )
    
    # Task metrics at snapshot
    completed_tasks = models.IntegerField(
        default=0,
        help_text="Number of completed tasks"
    )
    total_tasks = models.IntegerField(
        default=0,
        help_text="Total number of tasks"
    )
    
    # AI analysis
    ai_insights = models.JSONField(
        null=True,
        blank=True,
        help_text="AI-generated insights and recommendations"
    )
    ai_risk_score = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="AI-calculated risk score (0-100)"
    )
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='roi_analyses'
    )
    
    class Meta:
        ordering = ['-snapshot_date']
        verbose_name = 'Project ROI'
        verbose_name_plural = 'Project ROI Analyses'
        indexes = [
            models.Index(fields=['board', '-snapshot_date']),
        ]
    
    def __str__(self):
        return f"{self.board.name} - ROI Analysis {self.snapshot_date.strftime('%Y-%m-%d')}"
    
    def calculate_roi(self):
        """Calculate ROI percentage"""
        if self.total_cost <= 0:
            return None
        if not self.realized_value and not self.expected_value:
            return None
        value = self.realized_value or self.expected_value or Decimal('0.00')
        roi = ((value - self.total_cost) / self.total_cost) * 100
        return roi
    
    def get_cost_per_task(self):
        """Calculate cost per completed task"""
        if self.completed_tasks <= 0:
            return Decimal('0.00')
        return self.total_cost / self.completed_tasks


class BudgetRecommendation(models.Model):
    """
    AI-generated budget recommendations and optimization suggestions
    """
    RECOMMENDATION_TYPE_CHOICES = [
        ('reallocation', 'Budget Reallocation'),
        ('scope_cut', 'Scope Reduction'),
        ('timeline_change', 'Timeline Adjustment'),
        ('resource_optimization', 'Resource Optimization'),
        ('risk_mitigation', 'Risk Mitigation'),
        ('efficiency_improvement', 'Efficiency Improvement'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('implemented', 'Implemented'),
    ]
    
    board = models.ForeignKey(
        Board,
        on_delete=models.CASCADE,
        related_name='budget_recommendations',
        help_text="Board this recommendation is for"
    )
    
    # Recommendation details
    recommendation_type = models.CharField(
        max_length=30,
        choices=RECOMMENDATION_TYPE_CHOICES,
        help_text="Type of recommendation"
    )
    title = models.CharField(
        max_length=200,
        help_text="Recommendation title"
    )
    description = models.TextField(
        help_text="Detailed recommendation description"
    )
    
    # Impact analysis
    estimated_savings = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Estimated cost savings"
    )
    confidence_score = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="AI confidence score (0-100)"
    )
    
    # Priority
    priority = models.CharField(
        max_length=10,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('urgent', 'Urgent'),
        ],
        default='medium'
    )
    
    # Status tracking
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # AI context
    ai_reasoning = models.TextField(
        help_text="AI reasoning for this recommendation"
    )
    based_on_patterns = models.JSONField(
        null=True,
        blank=True,
        help_text="Historical patterns that informed this recommendation"
    )
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_recommendations'
    )
    implemented_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the recommendation was implemented"
    )
    implementation_summary = models.TextField(
        blank=True,
        default='',
        help_text="Summary of changes made when implementing this recommendation"
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Budget Recommendation'
        verbose_name_plural = 'Budget Recommendations'
        indexes = [
            models.Index(fields=['board', 'status']),
            models.Index(fields=['recommendation_type', 'status']),
        ]
    
    def __str__(self):
        return f"{self.get_recommendation_type_display()} - {self.title}"
    
    def get_implementation_logs(self):
        """Get all implementation logs for this recommendation"""
        return self.implementation_logs.all()
    
    def get_total_savings_realized(self):
        """Calculate actual savings from implementation logs"""
        logs = self.implementation_logs.filter(is_rolled_back=False)
        total_change = sum(log.get_change_amount() for log in logs)
        return abs(total_change) if total_change < 0 else Decimal('0.00')


class CostPattern(models.Model):
    """
    Historical cost patterns learned by AI for better predictions
    """
    board = models.ForeignKey(
        Board,
        on_delete=models.CASCADE,
        related_name='cost_patterns',
        help_text="Board this pattern was learned from"
    )
    
    # Pattern identification
    pattern_name = models.CharField(
        max_length=100,
        help_text="Name/identifier for this pattern"
    )
    pattern_type = models.CharField(
        max_length=50,
        help_text="Type of pattern (e.g., 'task_overrun', 'resource_spike')"
    )
    
    # Pattern data
    pattern_data = models.JSONField(
        help_text="Structured pattern data for ML analysis"
    )
    confidence = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Pattern confidence score (0-100)"
    )
    
    # Occurrences
    occurrence_count = models.IntegerField(
        default=1,
        help_text="Number of times this pattern has been observed"
    )
    last_occurred = models.DateTimeField(
        default=timezone.now,
        help_text="Last time this pattern was observed"
    )
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-last_occurred']
        verbose_name = 'Cost Pattern'
        verbose_name_plural = 'Cost Patterns'
        unique_together = ['board', 'pattern_name']
    
    def __str__(self):
        return f"{self.board.name} - {self.pattern_name} (Confidence: {self.confidence}%)"


class BudgetImplementationLog(models.Model):
    """
    Audit log for tracking budget changes when recommendations are implemented.
    Records what was changed, by whom, and allows for potential rollback.
    """
    CHANGE_TYPE_CHOICES = [
        ('budget_reallocation', 'Budget Reallocation'),
        ('task_estimate_update', 'Task Estimate Update'),
        ('hourly_rate_change', 'Hourly Rate Change'),
        ('scope_reduction', 'Scope Reduction'),
        ('resource_reassignment', 'Resource Reassignment'),
        ('timeline_adjustment', 'Timeline Adjustment'),
    ]
    
    recommendation = models.ForeignKey(
        BudgetRecommendation,
        on_delete=models.CASCADE,
        related_name='implementation_logs',
        help_text="Recommendation that triggered this change"
    )
    
    # Change details
    change_type = models.CharField(
        max_length=30,
        choices=CHANGE_TYPE_CHOICES,
        help_text="Type of change made"
    )
    
    # What was changed
    affected_task = models.ForeignKey(
        Task,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='budget_change_logs',
        help_text="Task affected by this change (if applicable)"
    )
    
    # Before/After values
    field_changed = models.CharField(
        max_length=100,
        help_text="Name of the field that was changed"
    )
    old_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Previous value"
    )
    new_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="New value after change"
    )
    
    # For complex changes
    change_details = models.JSONField(
        null=True,
        blank=True,
        help_text="Additional details about the change"
    )
    
    # Tracking
    implemented_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='budget_implementations'
    )
    implemented_at = models.DateTimeField(auto_now_add=True)
    
    # Rollback support
    is_rolled_back = models.BooleanField(
        default=False,
        help_text="Whether this change has been rolled back"
    )
    rolled_back_at = models.DateTimeField(
        null=True,
        blank=True
    )
    rolled_back_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='budget_rollbacks'
    )
    
    class Meta:
        ordering = ['-implemented_at']
        verbose_name = 'Budget Implementation Log'
        verbose_name_plural = 'Budget Implementation Logs'
    
    def __str__(self):
        task_name = self.affected_task.title if self.affected_task else "N/A"
        return f"{self.get_change_type_display()} - {task_name} ({self.field_changed}: {self.old_value} → {self.new_value})"
    
    def get_change_amount(self):
        """Calculate the net change amount"""
        if self.old_value is not None and self.new_value is not None:
            return self.new_value - self.old_value
        return Decimal('0.00')
