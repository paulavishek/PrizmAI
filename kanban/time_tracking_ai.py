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
    
    # Thresholds for anomaly detection - aligned with labor law standards
    HIGH_HOURS_THRESHOLD = Decimal('10.00')  # Warning threshold per day (long day alert)
    CRITICAL_HOURS_THRESHOLD = Decimal('14.00')  # Critical threshold (exceeds safe limits)
    MISSING_TIME_THRESHOLD_DAYS = 3  # Days without logging before alert
    
    # Smart split thresholds
    RECOMMENDED_DAILY_MAX = Decimal('8.00')  # Recommended max hours per day
    SPLIT_TRIGGER_THRESHOLD = Decimal('10.00')  # Trigger split suggestion when this is exceeded
    
    def __init__(self, user: User, board=None):
        """
        Initialize with user and optional board
        
        Args:
            user: User instance to analyze
            board: Optional Board instance to filter by
        """
        self.user = user
        self.board = board
    
    def validate_time_entry(self, task, hours: Decimal, work_date: date) -> Dict:
        """
        Validate a proposed time entry and suggest splits if excessive.
        This is the PROACTIVE validation called before saving.
        
        Args:
            task: Task instance for the time entry
            hours: Proposed hours to log
            work_date: Date for the entry
            
        Returns:
            Dict with validation result and AI suggestions
        """
        from kanban.budget_models import TimeEntry
        from kanban.models import Task
        
        result = {
            'valid': True,
            'needs_attention': False,
            'severity': 'ok',
            'message': '',
            'suggestion': None,
            'split_entries': [],
            'task_suggestions': []
        }
        
        # Get existing hours for that day
        existing_hours = TimeEntry.objects.filter(
            user=self.user,
            work_date=work_date
        ).aggregate(total=Sum('hours_spent'))['total'] or Decimal('0.00')
        
        proposed_total = existing_hours + hours
        
        # Check if this would result in an excessive day
        if proposed_total > self.SPLIT_TRIGGER_THRESHOLD:
            result['needs_attention'] = True
            result['severity'] = 'warning' if proposed_total <= self.CRITICAL_HOURS_THRESHOLD else 'critical'
            
            # Generate AI split suggestion
            split_suggestion = self._generate_split_suggestion(
                task=task,
                hours=hours,
                work_date=work_date,
                existing_hours=existing_hours
            )
            
            result['message'] = (
                f"You're logging {hours}h which would bring your total for "
                f"{work_date.strftime('%b %d')} to {proposed_total}h. "
                f"That's {'extremely ' if result['severity'] == 'critical' else ''}high for a single day."
            )
            result['suggestion'] = split_suggestion
            result['split_entries'] = split_suggestion.get('entries', [])
            
            # Get task suggestions for splitting
            result['task_suggestions'] = self._get_split_task_suggestions(task, work_date, hours)
        
        elif proposed_total > self.HIGH_HOURS_THRESHOLD:
            # Soft warning - high but not excessive
            result['needs_attention'] = True
            result['severity'] = 'info'
            result['message'] = (
                f"After this entry, you'll have logged {proposed_total}h on "
                f"{work_date.strftime('%b %d')}. That's a long day - everything ok?"
            )
        
        return result
    
    def _generate_split_suggestion(self, task, hours: Decimal, work_date: date, 
                                   existing_hours: Decimal) -> Dict:
        """
        Generate AI-powered suggestion to split hours across multiple days.
        
        Returns:
            Dict with splitting strategy and entry suggestions
        """
        entries = []
        remaining_hours = hours
        current_date = work_date
        
        # Calculate how much capacity is left for the original day
        original_day_capacity = max(Decimal('0'), self.RECOMMENDED_DAILY_MAX - existing_hours)
        
        # First entry: fill up the original day to recommended max
        if original_day_capacity > Decimal('0'):
            first_entry_hours = min(remaining_hours, original_day_capacity)
            entries.append({
                'date': current_date.isoformat(),
                'date_display': current_date.strftime('%a, %b %d'),
                'hours': float(first_entry_hours),
                'task_id': task.id,
                'task_title': task.title[:50],
                'description': f"Work on {task.title[:30]}",
                'is_original_day': True
            })
            remaining_hours -= first_entry_hours
        
        # Distribute remaining hours across following days
        days_added = 0
        while remaining_hours > Decimal('0') and days_added < 7:
            days_added += 1
            current_date = work_date + timedelta(days=days_added)
            
            # Skip weekends
            while current_date.weekday() >= 5:
                days_added += 1
                current_date = work_date + timedelta(days=days_added)
            
            # Allocate hours for this day (max recommended daily hours)
            day_hours = min(remaining_hours, self.RECOMMENDED_DAILY_MAX)
            
            entries.append({
                'date': current_date.isoformat(),
                'date_display': current_date.strftime('%a, %b %d'),
                'hours': float(day_hours),
                'task_id': task.id,
                'task_title': task.title[:50],
                'description': f"Continued work on {task.title[:30]}",
                'is_original_day': False
            })
            
            remaining_hours -= day_hours
        
        total_days = len(entries)
        total_hours = float(hours)
        
        return {
            'strategy': 'balanced_split',
            'original_hours': float(hours),
            'original_date': work_date.isoformat(),
            'days_needed': total_days,
            'entries': entries,
            'summary': (
                f"Split {total_hours}h across {total_days} days "
                f"(~{round(total_hours/total_days, 1)}h per day average)"
            ),
            'rationale': (
                "This split keeps each day under 8 hours to maintain work-life balance "
                "and ensure accurate time tracking. Weekends are automatically skipped."
            )
        }
    
    def _get_split_task_suggestions(self, original_task, work_date: date, 
                                    total_hours: Decimal) -> List[Dict]:
        """
        Suggest related tasks that the user might want to split time across.
        
        Returns:
            List of task suggestions for time splitting
        """
        from kanban.models import Task
        
        suggestions = []
        
        # Get tasks in the same board
        board = original_task.column.board if original_task.column else None
        if not board:
            return suggestions
        
        # 1. Tasks with dependencies to/from the original task
        related_task_ids = list(original_task.dependencies.values_list('id', flat=True))
        if hasattr(original_task, 'dependent_tasks'):
            related_task_ids.extend(original_task.dependent_tasks.values_list('id', flat=True))
        
        related_tasks = Task.objects.filter(
            id__in=related_task_ids,
            progress__lt=100
        ).select_related('column')[:3]
        
        for task in related_tasks:
            suggestions.append({
                'task_id': task.id,
                'task_title': task.title,
                'reason': 'Related task (dependency)',
                'board_name': board.name,
                'progress': task.progress
            })
        
        # 2. Tasks in the same column (similar work)
        same_column_tasks = Task.objects.filter(
            column=original_task.column,
            progress__lt=100
        ).exclude(
            id__in=[original_task.id] + [s['task_id'] for s in suggestions]
        ).select_related('column')[:2]
        
        for task in same_column_tasks:
            suggestions.append({
                'task_id': task.id,
                'task_title': task.title,
                'reason': f'Same column ({original_task.column.name})',
                'board_name': board.name,
                'progress': task.progress
            })
        
        # 3. Other tasks assigned to user in this board
        user_tasks = Task.objects.filter(
            column__board=board,
            assigned_to=self.user,
            progress__lt=100
        ).exclude(
            id__in=[original_task.id] + [s['task_id'] for s in suggestions]
        ).select_related('column')[:3]
        
        for task in user_tasks:
            suggestions.append({
                'task_id': task.id,
                'task_title': task.title,
                'reason': 'Your assigned task',
                'board_name': board.name,
                'progress': task.progress
            })
        
        return suggestions[:5]  # Limit to 5 suggestions
    
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
            total_rounded = round(float(total), 2)
            work_date = day_data['work_date']
            
            if total >= self.CRITICAL_HOURS_THRESHOLD:
                alerts.append({
                    'type': 'high_hours_critical',
                    'severity': 'critical',
                    'date': work_date,
                    'date_str': work_date.isoformat(),
                    'hours': total_rounded,
                    'message': f'Logged {total_rounded}h on {work_date.strftime("%b %d")} - this exceeds safe work limits.',
                    'suggestion': 'Consider splitting time entries across multiple days if this was not continuous work.'
                })
            elif total >= self.HIGH_HOURS_THRESHOLD:
                alerts.append({
                    'type': 'high_hours_warning',
                    'severity': 'warning',
                    'date': work_date,
                    'date_str': work_date.isoformat(),
                    'hours': total_rounded,
                    'message': f'Logged {total_rounded}h on {work_date.strftime("%b %d")} - that\'s a long day! Everything OK?',
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
