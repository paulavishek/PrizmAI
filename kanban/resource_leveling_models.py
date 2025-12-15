"""
Resource Leveling Models
Track user performance, task history, and workload for AI-powered resource optimization
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Avg, Count, Q, F
from datetime import timedelta
from accounts.models import Organization


class UserPerformanceProfile(models.Model):
    """
    Tracks historical performance metrics for each user
    Used for predicting task completion times and skill matching
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='performance_profiles')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='performance_profiles_org')
    
    # Performance metrics
    total_tasks_completed = models.IntegerField(default=0)
    avg_completion_time_hours = models.FloatField(default=0.0, help_text="Average hours to complete a task")
    velocity_score = models.FloatField(default=1.0, help_text="Normalized velocity (tasks/week)")
    
    # Reliability metrics
    on_time_completion_rate = models.FloatField(default=0.0, help_text="Percentage of tasks completed on time")
    quality_score = models.FloatField(default=3.0, help_text="Average quality rating (1-5)")
    
    # Skill profile (JSON field for flexibility)
    skill_keywords = models.JSONField(default=dict, blank=True, 
                                     help_text="Keywords extracted from completed tasks with frequency counts")
    
    # Current workload
    current_active_tasks = models.IntegerField(default=0)
    current_workload_hours = models.FloatField(default=0.0, help_text="Estimated hours of current work")
    utilization_percentage = models.FloatField(default=0.0, help_text="Current capacity utilization")
    
    # Capacity settings
    weekly_capacity_hours = models.FloatField(default=40.0, help_text="Available hours per week")
    
    # Timestamps
    last_updated = models.DateTimeField(auto_now=True)
    last_task_completed = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = [['user', 'organization']]
        ordering = ['-velocity_score']
    
    def __str__(self):
        return f"{self.user.username} - Performance Profile"
    
    def update_metrics(self):
        """Recalculate all performance metrics from historical data"""
        from kanban.models import Task
        
        # Get completed tasks in last 90 days
        ninety_days_ago = timezone.now() - timedelta(days=90)
        completed_tasks = Task.objects.filter(
            assigned_to=self.user,
            completed_at__isnull=False,
            completed_at__gte=ninety_days_ago,
            column__board__organization=self.organization
        )
        
        task_count = completed_tasks.count()
        if task_count == 0:
            return
        
        # Calculate average completion time
        completion_times = []
        on_time_count = 0
        
        for task in completed_tasks:
            if task.created_at and task.completed_at:
                hours = (task.completed_at - task.created_at).total_seconds() / 3600
                completion_times.append(hours)
                
                # Check if completed on time
                if task.due_date and task.completed_at <= task.due_date:
                    on_time_count += 1
        
        if completion_times:
            self.avg_completion_time_hours = sum(completion_times) / len(completion_times)
        
        # Calculate velocity (tasks per week)
        days_active = (timezone.now() - ninety_days_ago).days
        weeks_active = max(days_active / 7, 1)
        self.velocity_score = task_count / weeks_active
        
        # On-time completion rate
        tasks_with_due_date = completed_tasks.filter(due_date__isnull=False).count()
        if tasks_with_due_date > 0:
            self.on_time_completion_rate = (on_time_count / tasks_with_due_date) * 100
        
        # Update skill keywords from task descriptions
        self.update_skill_profile(completed_tasks)
        
        # Update current workload
        self.update_current_workload()
        
        self.total_tasks_completed = task_count
        self.last_task_completed = completed_tasks.latest('completed_at').completed_at
        self.save()
    
    def update_skill_profile(self, tasks):
        """Extract and count keywords from task descriptions"""
        import re
        from collections import Counter
        
        # Common stop words to ignore
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been'}
        
        all_words = []
        for task in tasks:
            # Extract words from title and description
            text = f"{task.title} {task.description or ''}".lower()
            words = re.findall(r'\b[a-z]{3,}\b', text)  # Words with 3+ letters
            all_words.extend([w for w in words if w not in stop_words])
        
        # Count frequency
        word_counts = Counter(all_words)
        
        # Store top 50 keywords
        self.skill_keywords = dict(word_counts.most_common(50))
    
    def update_current_workload(self):
        """Calculate current workload from active tasks"""
        from kanban.models import Task
        
        active_tasks = Task.objects.filter(
            assigned_to=self.user,
            completed_at__isnull=True,
            column__board__organization=self.organization
        ).exclude(column__name__icontains='done')
        
        self.current_active_tasks = active_tasks.count()
        
        # Estimate workload hours (use complexity or average completion time)
        estimated_hours = 0
        for task in active_tasks:
            if task.complexity_score:
                # Assume complexity maps roughly to hours (you can adjust this)
                estimated_hours += task.complexity_score
            else:
                # Use average completion time as estimate
                estimated_hours += self.avg_completion_time_hours or 8  # Default 8 hours
        
        self.current_workload_hours = estimated_hours
        
        # Calculate utilization
        if self.weekly_capacity_hours > 0:
            self.utilization_percentage = min((estimated_hours / self.weekly_capacity_hours) * 100, 100)
    
    def calculate_skill_match(self, task_text):
        """
        Calculate skill match score (0-100) for a given task
        Based on keyword overlap with user's skill profile
        """
        import re
        from collections import Counter
        
        if not self.skill_keywords:
            return 50.0  # Neutral score if no skill data
        
        # Extract words from task text
        words = re.findall(r'\b[a-z]{3,}\b', task_text.lower())
        task_word_counts = Counter(words)
        
        # Calculate overlap
        total_score = 0
        max_possible = 0
        
        for word, count in task_word_counts.items():
            skill_freq = self.skill_keywords.get(word, 0)
            if skill_freq > 0:
                # Weight by frequency in user's profile
                total_score += min(skill_freq, 10)  # Cap at 10 to avoid over-weighting
            max_possible += 10
        
        if max_possible == 0 or total_score == 0:
            # No keywords to match, or no overlap found
            # Return neutral score (50) instead of 0 to avoid penalizing unrelated tasks
            return 50.0
        
        # Convert to 0-100 scale
        match_percentage = (total_score / max_possible) * 100
        return min(match_percentage, 100.0)
    
    def predict_completion_time(self, task):
        """
        Predict how long this user will take to complete the task (in hours)
        Based on complexity and historical performance
        """
        base_time = self.avg_completion_time_hours or 8.0
        
        # Adjust for complexity
        if task.complexity_score:
            complexity_multiplier = task.complexity_score / 5  # Normalize to ~1.0
            estimated_time = base_time * complexity_multiplier
        else:
            estimated_time = base_time
        
        # Adjust for current workload (overloaded users take longer)
        if self.utilization_percentage > 80:
            workload_penalty = 1 + ((self.utilization_percentage - 80) / 100)  # Up to 20% slower
            estimated_time *= workload_penalty
        
        return estimated_time
    
    def get_availability_score(self):
        """
        Calculate availability score (0-100)
        Higher score = more available
        """
        # Invert utilization percentage
        return max(100 - self.utilization_percentage, 0)


class TaskAssignmentHistory(models.Model):
    """
    Tracks assignment changes for learning and optimization
    """
    task = models.ForeignKey('kanban.Task', on_delete=models.CASCADE, related_name='assignment_history')
    
    # Assignment details
    previous_assignee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                         related_name='previous_assignments')
    new_assignee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='new_assignments')
    
    # Context
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assignment_changes')
    changed_at = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=50, choices=[
        ('manual', 'Manual Reassignment'),
        ('ai_suggestion', 'AI Suggestion Accepted'),
        ('workload_balancing', 'Workload Balancing'),
        ('skill_match', 'Better Skill Match'),
        ('other', 'Other')
    ], default='manual')
    
    # Predictions at time of assignment
    predicted_completion_hours = models.FloatField(null=True, blank=True)
    predicted_due_date = models.DateTimeField(null=True, blank=True)
    
    # Actual outcomes (filled when task completes)
    actual_completion_hours = models.FloatField(null=True, blank=True)
    actual_completion_date = models.DateTimeField(null=True, blank=True)
    prediction_accuracy = models.FloatField(null=True, blank=True, help_text="How accurate was prediction (0-100)")
    
    # AI suggestion details (if this was an AI suggestion)
    was_ai_suggested = models.BooleanField(default=False)
    ai_confidence_score = models.FloatField(null=True, blank=True, help_text="AI confidence in suggestion (0-100)")
    ai_reasoning = models.TextField(blank=True, help_text="Why AI suggested this assignment")
    
    class Meta:
        ordering = ['-changed_at']
        verbose_name_plural = "Task Assignment Histories"
    
    def __str__(self):
        return f"{self.task.title} - {self.previous_assignee} → {self.new_assignee}"
    
    def calculate_actual_metrics(self):
        """Calculate actual completion metrics when task is done"""
        if not self.task.completed_at or not self.task.created_at:
            return
        
        # Calculate actual hours
        actual_hours = (self.task.completed_at - self.changed_at).total_seconds() / 3600
        self.actual_completion_hours = actual_hours
        self.actual_completion_date = self.task.completed_at
        
        # Calculate prediction accuracy
        if self.predicted_completion_hours and actual_hours > 0:
            error_percentage = abs(self.predicted_completion_hours - actual_hours) / actual_hours * 100
            self.prediction_accuracy = max(100 - error_percentage, 0)
        
        self.save()


class ResourceLevelingSuggestion(models.Model):
    """
    Stores AI-generated resource leveling suggestions
    """
    task = models.ForeignKey('kanban.Task', on_delete=models.CASCADE, related_name='leveling_suggestions')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='leveling_suggestions')
    
    # Current state
    current_assignee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='current_task_assignments')
    
    # Suggestion
    suggested_assignee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='suggested_assignments')
    confidence_score = models.FloatField(help_text="AI confidence (0-100)")
    
    # Impact metrics
    time_savings_hours = models.FloatField(help_text="Expected time savings in hours")
    time_savings_percentage = models.FloatField(help_text="Percentage improvement")
    skill_match_score = models.FloatField(help_text="How well skills match (0-100)")
    workload_impact = models.CharField(max_length=50, choices=[
        ('reduces_bottleneck', 'Reduces Bottleneck'),
        ('balances_load', 'Balances Workload'),
        ('better_skills', 'Better Skill Match'),
        ('improves_timeline', 'Improves Timeline')
    ])
    
    # Projected dates
    current_projected_date = models.DateTimeField(null=True, blank=True)
    suggested_projected_date = models.DateTimeField(null=True, blank=True)
    
    # Reasoning
    reasoning = models.TextField(help_text="Human-readable explanation")
    
    # Status
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending Review'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired')
    ], default='pending')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(help_text="Suggestion expires after 48 hours")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='reviewed_suggestions')
    
    class Meta:
        ordering = ['-confidence_score', '-time_savings_percentage']
    
    def __str__(self):
        return f"{self.task.title}: {self.current_assignee} → {self.suggested_assignee} ({self.time_savings_percentage:.0f}% faster)"
    
    def is_expired(self):
        """Check if suggestion has expired"""
        return timezone.now() > self.expires_at
    
    def accept(self, user):
        """Accept the suggestion and reassign the task"""
        if self.is_expired():
            self.status = 'expired'
            self.save()
            return False
        
        # Update task assignment
        old_assignee = self.task.assigned_to
        self.task.assigned_to = self.suggested_assignee
        # Mark that this was accepted by AI to prevent duplicate history entries
        self.task._ai_suggestion_accepted = True
        self.task._changed_by_user = user
        self.task.save()
        
        # Create assignment history
        TaskAssignmentHistory.objects.create(
            task=self.task,
            previous_assignee=old_assignee,
            new_assignee=self.suggested_assignee,
            changed_by=user,
            reason='ai_suggestion',
            predicted_completion_hours=abs(self.time_savings_hours) if self.time_savings_hours else None,
            was_ai_suggested=True,
            ai_confidence_score=self.confidence_score,
            ai_reasoning=self.reasoning
        )
        
        # Update status
        self.status = 'accepted'
        self.reviewed_at = timezone.now()
        self.reviewed_by = user
        self.save()
        
        # Update performance profiles - this will now be handled by signals
        # But we'll keep this as a backup in case signals don't fire
        if old_assignee:
            profile = UserPerformanceProfile.objects.filter(user=old_assignee, organization=self.organization).first()
            if profile:
                profile.update_current_workload()
        
        profile = UserPerformanceProfile.objects.filter(user=self.suggested_assignee, organization=self.organization).first()
        if profile:
            profile.update_current_workload()
        
        return True
    
    def reject(self, user):
        """Reject the suggestion"""
        self.status = 'rejected'
        self.reviewed_at = timezone.now()
        self.reviewed_by = user
        self.save()
