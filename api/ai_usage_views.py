"""
AI Usage Dashboard Views

Dashboard for monitoring AI feature consumption and quotas
"""

import json
import logging
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Avg
from django.db.models.functions import TruncDate, TruncHour

from api.ai_usage_models import AIUsageQuota, AIRequestLog
from api.ai_usage_utils import get_or_create_quota, get_usage_stats

logger = logging.getLogger(__name__)


@login_required
def ai_usage_dashboard(request):
    """
    Main AI usage dashboard showing consumption and quota information
    """
    # Check if user is a demo account - redirect them since AI features are not available
    if hasattr(request.user, 'email') and request.user.email:
        if '@demo.prizmai.local' in request.user.email.lower():
            from django.contrib import messages
            messages.info(request, 'AI features are not available for demo accounts. Please create a free account to access AI-powered features.')
            from django.shortcuts import redirect
            return redirect('dashboard')
    
    # Get or create quota for user
    quota = get_or_create_quota(request.user)
    
    # Get usage stats
    stats = get_usage_stats(request.user, days=30)
    
    # Get recent requests (last 24 hours)
    last_24h = timezone.now() - timedelta(hours=24)
    recent_logs = AIRequestLog.objects.filter(
        user=request.user,
        timestamp__gte=last_24h
    )
    
    # Requests per hour (last 24 hours)
    hourly_requests = recent_logs.annotate(
        hour=TruncHour('timestamp')
    ).values('hour').annotate(
        count=Count('id')
    ).order_by('hour')
    
    # Feature breakdown
    by_feature = AIRequestLog.objects.filter(
        user=request.user,
        timestamp__gte=timezone.now() - timedelta(days=30)
    ).values('feature').annotate(
        count=Count('id'),
        avg_response_time=Avg('response_time_ms')
    ).order_by('-count')
    
    # Daily usage (last 30 days)
    daily_usage = AIRequestLog.objects.filter(
        user=request.user,
        timestamp__gte=timezone.now() - timedelta(days=30)
    ).annotate(
        date=TruncDate('timestamp')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    # Convert dates to ISO format strings for JavaScript
    daily_usage_list = [
        {
            'date': item['date'].isoformat() if item['date'] else None,
            'count': item['count']
        }
        for item in daily_usage
    ]
    
    context = {
        'quota': quota,
        'stats': stats,
        'recent_requests_24h': recent_logs.count(),
        'hourly_requests': list(hourly_requests),
        'by_feature': list(by_feature),
        'daily_usage': daily_usage_list,
        'daily_usage_json': json.dumps(daily_usage_list),
    }
    
    return render(request, 'api/ai_usage_dashboard.html', context)


@login_required
def ai_usage_stats_api(request):
    """
    AJAX endpoint for real-time AI usage statistics
    """
    quota = get_or_create_quota(request.user)
    stats = get_usage_stats(request.user, days=30)
    
    # Get recent activity
    last_hour = timezone.now() - timedelta(hours=1)
    requests_last_hour = AIRequestLog.objects.filter(
        user=request.user,
        timestamp__gte=last_hour
    ).count()
    
    return JsonResponse({
        'success': True,
        'quota': {
            'used': quota.requests_used,
            'limit': quota.monthly_quota,
            'remaining': quota.get_remaining_requests(),
            'percentage': quota.get_usage_percent(),
            'days_until_reset': quota.get_days_until_reset(),
            'period_end': quota.period_end.isoformat(),
        },
        'recent': {
            'requests_last_hour': requests_last_hour,
            'last_request': quota.last_request_at.isoformat() if quota.last_request_at else None,
        },
        'lifetime': {
            'total_requests': quota.total_requests_all_time,
        }
    })
