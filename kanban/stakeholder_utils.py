# kanban/stakeholder_utils.py
"""
Utility functions for stakeholder engagement tracking and metrics calculation
"""

from django.utils import timezone
from django.db.models import Count, Avg, Q
from datetime import timedelta
from .stakeholder_models import (
    ProjectStakeholder, StakeholderTaskInvolvement, 
    StakeholderEngagementRecord, EngagementMetrics
)


def calculate_engagement_metrics(board):
    """
    Calculate engagement metrics for all stakeholders in a board
    """
    stakeholders = ProjectStakeholder.objects.filter(board=board)
    
    for stakeholder in stakeholders:
        # Get date range (last 30 days)
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        # Get engagement records for period
        records = stakeholder.engagement_records.filter(
            date__gte=start_date,
            date__lte=end_date
        )
        
        # Calculate metrics
        total_count = records.count()
        
        # Communication channels
        channel_breakdown = records.values('communication_channel').annotate(
            count=Count('id')
        )
        channels_used = [
            {
                'channel': ch['communication_channel'],
                'count': ch['count']
            }
            for ch in channel_breakdown
        ]
        primary_channel = max(
            channels_used, 
            key=lambda x: x['count']
        )['channel'] if channels_used else ''
        
        # Satisfaction metrics
        satisfaction_records = records.filter(satisfaction_rating__isnull=False)
        avg_satisfaction = satisfaction_records.aggregate(
            avg=Avg('satisfaction_rating')
        )['avg'] or 0
        
        positive_count = records.filter(engagement_sentiment='positive').count()
        negative_count = records.filter(engagement_sentiment='negative').count()
        
        # Last engagement
        last_record = stakeholder.engagement_records.first()
        days_since = 0
        if last_record:
            days_since = (end_date - last_record.date).days
        
        # Follow-ups
        pending_followups = records.filter(
            follow_up_required=True,
            follow_up_completed=False
        ).count()
        
        # Calculate engagement gap
        engagement_gap = stakeholder.get_engagement_gap()
        
        # Get or create metrics
        metrics, created = EngagementMetrics.objects.get_or_create(
            board=board,
            stakeholder=stakeholder,
            defaults={
                'period_start': start_date,
                'period_end': end_date,
            }
        )
        
        # Update metrics
        metrics.total_engagements = stakeholder.engagement_records.count()
        metrics.engagements_this_month = total_count
        metrics.average_engagements_per_month = total_count / 1  # Simple calculation for now
        metrics.primary_channel = primary_channel
        metrics.channels_used = channels_used
        metrics.average_satisfaction = float(avg_satisfaction)
        metrics.positive_engagements_count = positive_count
        metrics.negative_engagements_count = negative_count
        metrics.days_since_last_engagement = days_since
        metrics.pending_follow_ups = pending_followups
        metrics.engagement_gap = engagement_gap
        metrics.period_start = start_date
        metrics.period_end = end_date
        metrics.save()
    
    return True


def recalculate_stakeholder_metrics(stakeholder):
    """
    Recalculate engagement metrics for a single stakeholder
    """
    board = stakeholder.board
    
    # Get date range (last 30 days)
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    # Get engagement records for period
    records = stakeholder.engagement_records.filter(
        date__gte=start_date,
        date__lte=end_date
    )
    
    # Calculate metrics
    total_count = records.count()
    
    # Communication channels
    channel_breakdown = records.values('communication_channel').annotate(
        count=Count('id')
    )
    channels_used = [
        {
            'channel': ch['communication_channel'],
            'count': ch['count']
        }
        for ch in channel_breakdown
    ]
    primary_channel = max(
        channels_used, 
        key=lambda x: x['count']
    )['channel'] if channels_used else ''
    
    # Satisfaction metrics
    satisfaction_records = records.filter(satisfaction_rating__isnull=False)
    avg_satisfaction = satisfaction_records.aggregate(
        avg=Avg('satisfaction_rating')
    )['avg'] or 0
    
    positive_count = records.filter(engagement_sentiment='positive').count()
    negative_count = records.filter(engagement_sentiment='negative').count()
    
    # Last engagement
    last_record = stakeholder.engagement_records.first()
    days_since = 0
    if last_record:
        days_since = (end_date - last_record.date).days
    
    # Follow-ups
    pending_followups = records.filter(
        follow_up_required=True,
        follow_up_completed=False
    ).count()
    
    # Calculate engagement gap
    engagement_gap = stakeholder.get_engagement_gap()
    
    # Get or create metrics
    metrics, created = EngagementMetrics.objects.get_or_create(
        board=board,
        stakeholder=stakeholder,
        defaults={
            'period_start': start_date,
            'period_end': end_date,
        }
    )
    
    # Update metrics
    metrics.total_engagements = stakeholder.engagement_records.count()
    metrics.engagements_this_month = total_count
    metrics.average_engagements_per_month = total_count / 1  # Simple calculation for now
    metrics.primary_channel = primary_channel
    metrics.channels_used = channels_used
    metrics.average_satisfaction = float(avg_satisfaction)
    metrics.positive_engagements_count = positive_count
    metrics.negative_engagements_count = negative_count
    metrics.days_since_last_engagement = days_since
    metrics.pending_follow_ups = pending_followups
    metrics.engagement_gap = engagement_gap
    metrics.period_start = start_date
    metrics.period_end = end_date
    metrics.save()
    
    return metrics


def update_stakeholder_engagement(stakeholder, task=None):
    """
    Update stakeholder engagement status based on recent activity
    """
    # Get engagement records from last 7 days
    recent_date = timezone.now().date() - timedelta(days=7)
    recent_records = stakeholder.engagement_records.filter(date__gte=recent_date)
    
    if recent_records.exists():
        # Update last engagement timestamp for all task involvements
        stakeholder.task_involvements.all().update(
            last_engagement=timezone.now(),
            engagement_count=Count('engagement_count') + 1
        )
        
        # Update engagement status based on last interaction
        last_record = recent_records.last()
        
        # Determine engagement status based on interaction
        if last_record:
            # Determine status from communication channel and sentiment
            if last_record.engagement_sentiment == 'positive':
                status = 'satisfied'
            elif last_record.communication_channel in ['meeting', 'video', 'phone']:
                status = 'collaborated'
            elif last_record.communication_channel in ['presentation', 'survey']:
                status = 'involved'
            else:
                status = 'informed'
            
            # Update all task involvements
            stakeholder.task_involvements.all().update(
                engagement_status=status
            )


def get_stakeholder_summary(board):
    """
    Get summary statistics for all stakeholders in a board
    """
    stakeholders = ProjectStakeholder.objects.filter(board=board)
    
    total = stakeholders.count()
    total_engagements = StakeholderEngagementRecord.objects.filter(
        stakeholder__board=board
    ).count()
    
    # Quadrant distribution
    quadrants = {
        'Manage Closely': 0,
        'Keep Satisfied': 0,
        'Keep Informed': 0,
        'Monitor': 0,
    }
    
    for stakeholder in stakeholders:
        q = stakeholder.get_quadrant()
        quadrants[q] += 1
    
    # Engagement distribution
    engagements = {
        'inform': stakeholders.filter(current_engagement='inform').count(),
        'consult': stakeholders.filter(current_engagement='consult').count(),
        'involve': stakeholders.filter(current_engagement='involve').count(),
        'collaborate': stakeholders.filter(current_engagement='collaborate').count(),
        'empower': stakeholders.filter(current_engagement='empower').count(),
    }
    
    # Average satisfaction
    avg_satisfaction = StakeholderEngagementRecord.objects.filter(
        stakeholder__board=board,
        satisfaction_rating__isnull=False
    ).aggregate(avg=Avg('satisfaction_rating'))['avg'] or 0
    
    return {
        'total_stakeholders': total,
        'total_engagements': total_engagements,
        'quadrant_distribution': quadrants,
        'engagement_distribution': engagements,
        'average_satisfaction': round(avg_satisfaction, 2),
    }


def identify_at_risk_stakeholders(board, days=30):
    """
    Identify stakeholders who haven't been engaged recently
    """
    threshold_date = timezone.now().date() - timedelta(days=days)
    
    stakeholders = ProjectStakeholder.objects.filter(board=board)
    at_risk = []
    
    for stakeholder in stakeholders:
        last_engagement = stakeholder.engagement_records.first()
        
        if not last_engagement or last_engagement.date < threshold_date:
            # Stakeholder hasn't been engaged recently
            at_risk.append({
                'stakeholder': stakeholder,
                'days_since_engagement': (timezone.now().date() - (last_engagement.date if last_engagement else stakeholder.created_at.date())).days,
                'quadrant': stakeholder.get_quadrant(),
                'engagement_gap': stakeholder.get_engagement_gap(),
            })
    
    return at_risk


def get_engagement_recommendations(stakeholder):
    """
    Get recommendations for engaging a specific stakeholder
    """
    recommendations = []
    
    # Engagement gap recommendations
    gap = stakeholder.get_engagement_gap()
    if gap > 0:
        recommendations.append({
            'type': 'engagement_gap',
            'message': f'Increase engagement from {stakeholder.current_engagement.title()} to {stakeholder.desired_engagement.title()}',
            'priority': 'high' if gap > 2 else 'medium',
        })
    
    # Quadrant-based recommendations
    quadrant = stakeholder.get_quadrant()
    if quadrant == 'Manage Closely':
        recommendations.append({
            'type': 'frequent_engagement',
            'message': 'Regular engagement required for high influence/interest stakeholder',
            'priority': 'high',
        })
    elif quadrant == 'Keep Satisfied':
        recommendations.append({
            'type': 'maintain_satisfaction',
            'message': 'Keep stakeholder satisfied with periodic updates',
            'priority': 'medium',
        })
    elif quadrant == 'Keep Informed':
        recommendations.append({
            'type': 'keep_informed',
            'message': 'Provide regular information updates to maintain interest',
            'priority': 'medium',
        })
    
    # Recent engagement tracking
    recent_engagement = stakeholder.engagement_records.filter(
        date__gte=timezone.now().date() - timedelta(days=7)
    ).exists()
    
    if not recent_engagement:
        recommendations.append({
            'type': 'overdue_engagement',
            'message': 'No recent engagement recorded - schedule an engagement activity',
            'priority': 'high',
        })
    
    return recommendations


def batch_calculate_metrics(board):
    """
    Batch calculate metrics for all stakeholders in a board
    Useful for scheduled tasks
    """
    try:
        calculate_engagement_metrics(board)
        return True, "Metrics calculated successfully"
    except Exception as e:
        return False, f"Error calculating metrics: {str(e)}"
