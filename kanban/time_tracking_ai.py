"""
AI-Powered Time Tracking Service
Provides anomaly detection, smart task suggestions, and missing time alerts
"""
import logging
from decimal import Decimal
from typing import Dict, List, Optional
from datetime import timedelta, date
from django.utils import timezone
from django.db.models import Sum, Avg, Count, Q
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


class TimeTrackingAIService:
    """
    AI-powered time tracking analysis and recommendations
    """
    
    # Thresholds for anomaly detection
    HIGH_HOURS_THRESHOLD = Decimal('12.00')  # Warning threshold per day
    CRITICAL_HOURS_THRESHOLD = Decimal('16.00')  # Critical threshold per entry
    MISSING_TIME_THRESHOLD_DAYS = 3  # Days without logging before alert
    
    def __init__(self, user: User, board=None):
        """
        Initialize with user and optional board
        
        Args:
            user: User instance to analyze
            board: Optional Board instance to filter by
        """
        self.user = user
        self.board = board
    
    def detect_anomalies(self, days_back: int = 14) -> List[Dict]:
        """
        Detect unusual time entry patterns
        
        Returns:
            List of anomaly alerts with severity and details
        """
        from kanban.budget_models import TimeEntry
        
        alerts = []
        today = timezone.now().date()
        start_date = today - timedelta(days=days_back)
        
        # Get entries for the period
        entries_qs = TimeEntry.objects.filter(
            user=self.user,
            work_date__gte=start_date,
            work_date__lte=today
        )
        
        if self.board:
            entries_qs = entries_qs.filter(task__column__board=self.board)
        
        # Check for high-hour days
        daily_totals = entries_qs.values('work_date').annotate(
            total_hours=Sum('hours_spent')
        ).order_by('-total_hours')
        
        for day_data in daily_totals:
            total = day_data['total_hours']
            work_date = day_data['work_date']
            
            if total >= self.CRITICAL_HOURS_THRESHOLD:
                alerts.append({
                    'type': 'high_hours_critical',
                    'severity': 'critical',
                    'date': work_date,
                    'hours': float(total),
                    'message': f'Logged {total}h on {work_date.strftime("%b %d")} - this exceeds sustainable work limits.',
                    'suggestion': 'Consider splitting time entries across multiple days if this was not continuous work.'
                })
            elif total >= self.HIGH_HOURS_THRESHOLD:
                alerts.append({
                    'type': 'high_hours_warning',
                    'severity': 'warning',
                    'date': work_date,
                    'hours': float(total),
                    'message': f'Logged {total}h on {work_date.strftime("%b %d")} - longer than a typical workday.',
                    'suggestion': 'Monitor workload to prevent burnout.'
                })
        
        # Check for missing time entries during weekdays
        missing_days = self._find_missing_time_days(start_date, today, entries_qs)
        if len(missing_days) >= self.MISSING_TIME_THRESHOLD_DAYS:
            alerts.append({
                'type': 'missing_time',
                'severity': 'info',
                'days_count': len(missing_days),
                'recent_missing': [d.strftime('%b %d') for d in missing_days[:5]],
                'message': f'{len(missing_days)} weekdays without logged time in the last {days_back} days.',
                'suggestion': 'Remember to log time daily for accurate tracking.'
            })
        
        # Check for large single entries
        large_entries = entries_qs.filter(
            hours_spent__gte=self.HIGH_HOURS_THRESHOLD
        ).select_related('task')
        
        for entry in large_entries:
            alerts.append({
                'type': 'large_entry',
                'severity': 'warning',
                'entry_id': entry.id,
                'task_title': entry.task.title,
                'hours': float(entry.hours_spent),
                'date': entry.work_date,
                'message': f'Single entry of {entry.hours_spent}h for "{entry.task.title[:30]}".',
                'suggestion': 'Consider breaking this into multiple smaller entries with descriptions.'
            })
        
        return sorted(alerts, key=lambda x: {'critical': 0, 'warning': 1, 'info': 2}[x['severity']])
    
    def _find_missing_time_days(self, start_date: date, end_date: date, entries_qs) -> List[date]:
        """
        Find weekdays without any logged time
        """
        # Get all dates with entries
        logged_dates = set(entries_qs.values_list('work_date', flat=True))
        
        # Check each weekday
        missing = []
        current = start_date
        while current <= end_date:
            # Skip weekends (0=Monday, 6=Sunday)
            if current.weekday() < 5 and current not in logged_dates:
                missing.append(current)
            current += timedelta(days=1)
        
        return missing
    
    def suggest_tasks(self, limit: int = 5) -> List[Dict]:
        """
        Get smart task suggestions for time logging based on user activity
        
        Returns:
            List of suggested tasks with reasons
        """
        from kanban.models import Task
        from kanban.budget_models import TimeEntry
        
        suggestions = []
        today = timezone.now().date()
        
        # Build base task queryset
        task_qs = Task.objects.filter(assigned_to=self.user)
        if self.board:
            task_qs = task_qs.filter(column__board=self.board)
        
        task_qs = task_qs.select_related('column', 'column__board')
        
        # 1. Last logged task (most likely to continue working on)
        last_entry = TimeEntry.objects.filter(
            user=self.user
        ).select_related('task').order_by('-created_at').first()
        
        if last_entry and last_entry.task.progress < 100:
            suggestions.append({
                'task': last_entry.task,
                'reason': 'last_logged',
                'reason_text': 'You recently logged time for this task',
                'priority': 1
            })
        
        # 2. In-progress tasks (status in "Doing" or similar columns)
        in_progress_tasks = task_qs.filter(
            Q(column__name__icontains='doing') |
            Q(column__name__icontains='progress') |
            Q(column__name__icontains='working') |
            Q(progress__gt=0, progress__lt=100)
        ).exclude(
            id__in=[s['task'].id for s in suggestions]
        )[:3]
        
        for task in in_progress_tasks:
            suggestions.append({
                'task': task,
                'reason': 'in_progress',
                'reason_text': f'Currently in progress ({task.progress}% complete)',
                'priority': 2
            })
        
        # 3. Tasks with upcoming deadlines
        week_from_now = today + timedelta(days=7)
        deadline_tasks = task_qs.filter(
            due_date__isnull=False,
            due_date__lte=week_from_now,
            progress__lt=100
        ).exclude(
            id__in=[s['task'].id for s in suggestions]
        ).order_by('due_date')[:2]
        
        for task in deadline_tasks:
            days_left = (task.due_date - today).days
            suggestions.append({
                'task': task,
                'reason': 'deadline',
                'reason_text': f'Due in {days_left} day{"s" if days_left != 1 else ""}',
                'priority': 3
            })
        
        # 4. Tasks with most recent time entries (frequently worked on)
        frequent_task_ids = TimeEntry.objects.filter(
            user=self.user,
            work_date__gte=today - timedelta(days=7)
        ).values('task_id').annotate(
            entry_count=Count('id')
        ).order_by('-entry_count').values_list('task_id', flat=True)[:3]
        
        frequent_tasks = task_qs.filter(
            id__in=frequent_task_ids,
            progress__lt=100
        ).exclude(
            id__in=[s['task'].id for s in suggestions]
        )
        
        for task in frequent_tasks:
            suggestions.append({
                'task': task,
                'reason': 'frequent',
                'reason_text': 'Frequently worked on this week',
                'priority': 4
            })
        
        # Sort by priority and limit
        suggestions.sort(key=lambda x: x['priority'])
        return suggestions[:limit]
    
    def get_missing_time_alerts(self) -> Optional[Dict]:
        """
        Check if user should be reminded to log time
        
        Returns:
            Alert dict if reminder needed, None otherwise
        """
        from kanban.budget_models import TimeEntry
        
        today = timezone.now().date()
        now = timezone.now()
        
        # Skip weekends
        if today.weekday() >= 5:
            return None
        
        # Check if user has logged any time today
        today_hours = TimeEntry.objects.filter(
            user=self.user,
            work_date=today
        ).aggregate(total=Sum('hours_spent'))['total'] or Decimal('0.00')
        
        # If it's afternoon and no time logged, suggest reminder
        if now.hour >= 14 and today_hours == 0:
            # Get expected daily hours based on user's average
            week_start = today - timedelta(days=today.weekday())
            avg_daily = TimeEntry.objects.filter(
                user=self.user,
                work_date__gte=week_start - timedelta(days=14),
                work_date__lt=today
            ).values('work_date').annotate(
                total=Sum('hours_spent')
            ).aggregate(avg=Avg('total'))['avg'] or Decimal('6.00')
            
            return {
                'type': 'missing_today',
                'message': f"You haven't logged time today yet.",
                'suggestion': f'Based on your average ({round(avg_daily, 1)}h/day), consider tracking your work.',
                'expected_hours': float(round(avg_daily, 1))
            }
        
        return None
    
    def get_time_insights(self) -> Dict:
        """
        Get comprehensive time tracking insights for the user
        
        Returns:
            Dictionary with insights and statistics
        """
        from kanban.budget_models import TimeEntry
        
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        
        entries_qs = TimeEntry.objects.filter(user=self.user)
        if self.board:
            entries_qs = entries_qs.filter(task__column__board=self.board)
        
        # Weekly statistics
        week_entries = entries_qs.filter(work_date__gte=week_start, work_date__lte=today)
        week_total = week_entries.aggregate(total=Sum('hours_spent'))['total'] or Decimal('0.00')
        
        # Daily average this week
        days_so_far = (today - week_start).days + 1
        week_avg = week_total / days_so_far if days_so_far > 0 else Decimal('0.00')
        
        # Month statistics
        month_entries = entries_qs.filter(work_date__gte=month_start, work_date__lte=today)
        month_total = month_entries.aggregate(total=Sum('hours_spent'))['total'] or Decimal('0.00')
        
        # Productivity trend (compare this week to last week)
        last_week_start = week_start - timedelta(days=7)
        last_week_end = week_start - timedelta(days=1)
        last_week_total = entries_qs.filter(
            work_date__gte=last_week_start,
            work_date__lte=last_week_end
        ).aggregate(total=Sum('hours_spent'))['total'] or Decimal('0.00')
        
        if last_week_total > 0:
            trend_percent = ((week_total - last_week_total) / last_week_total * 100)
        else:
            trend_percent = Decimal('0.00')
        
        return {
            'week_total': float(round(week_total, 2)),
            'week_average': float(round(week_avg, 2)),
            'month_total': float(round(month_total, 2)),
            'last_week_total': float(round(last_week_total, 2)),
            'trend_percent': float(round(trend_percent, 1)),
            'trend_direction': 'up' if trend_percent > 0 else 'down' if trend_percent < 0 else 'stable'
        }
