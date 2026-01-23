"""
AI Usage Tracking Utilities

Helper functions to track and manage AI feature usage
"""

import time
import logging
from django.utils import timezone
from functools import wraps

logger = logging.getLogger(__name__)


def get_or_create_quota(user):
    """
    Get or create AI usage quota for a user
    """
    from api.ai_usage_models import AIUsageQuota
    
    quota, created = AIUsageQuota.objects.get_or_create(
        user=user,
        defaults={
            'monthly_quota': 50,  # Cost control: 50/month for free users
            'daily_limit': 10,    # Cost control: 10/day for free users
            'requests_used': 0,
            'daily_requests_used': 0,
            'period_start': timezone.now(),
            'last_daily_reset': timezone.now().date(),
        }
    )
    
    # Check if period needs reset
    quota.check_and_reset_if_needed()
    
    return quota


def check_ai_quota(user):
    """
    Check if user has remaining AI quota
    Returns: (has_quota: bool, quota_obj: AIUsageQuota, remaining: int)
    """
    quota = get_or_create_quota(user)
    has_quota = quota.has_quota_remaining()
    remaining = quota.get_remaining_requests()
    
    return has_quota, quota, remaining


def track_ai_request(user, feature, request_type='', board_id=None, ai_model='gemini', 
                     success=True, error_message='', tokens_used=0, response_time_ms=0):
    """
    Track an AI request and increment user's quota
    
    Args:
        user: User object
        feature: AI feature name (ai_coach, ai_assistant, etc.)
        request_type: Type of request (question, suggestion, etc.)
        board_id: Board ID if relevant
        ai_model: AI model used
        success: Whether request succeeded
        error_message: Error message if failed
        tokens_used: Approximate tokens used
        response_time_ms: Response time in milliseconds
    
    Returns:
        AIRequestLog object
    """
    from api.ai_usage_models import AIRequestLog, AIUsageQuota
    
    # Get or create quota
    quota = get_or_create_quota(user)
    
    # Increment usage (only if successful)
    if success:
        quota.increment_usage()
    
    # Sanitize board_id - convert empty strings to None
    if board_id is not None:
        if isinstance(board_id, str):
            board_id = int(board_id) if board_id.strip() else None
        elif not isinstance(board_id, int):
            board_id = None
    
    # Log the request
    log = AIRequestLog.objects.create(
        user=user,
        feature=feature,
        request_type=request_type,
        ai_model=ai_model,
        tokens_used=tokens_used,
        success=success,
        error_message=error_message[:500] if error_message else '',
        response_time_ms=response_time_ms,
        board_id=board_id
    )
    
    return log


def require_ai_quota(feature_name, request_type=''):
    """
    Decorator to check and track AI quota for views
    
    Usage:
        @require_ai_quota('ai_coach', 'question')
        def ask_coach(request, board_id):
            # ... your view code
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            from django.http import JsonResponse
            
            # Check if user is authenticated
            if not request.user.is_authenticated:
                return JsonResponse({
                    'success': False,
                    'error': 'Authentication required'
                }, status=401)
            
            # Check quota (both monthly and daily)
            has_quota, quota, remaining = check_ai_quota(request.user)
            
            if not has_quota:
                days_until_reset = quota.get_days_until_reset()
                daily_remaining = quota.get_remaining_daily_requests()
                
                # Determine if it's a daily or monthly limit
                if daily_remaining <= 0:
                    return JsonResponse({
                        'success': False,
                        'error': 'Daily AI usage limit exceeded',
                        'quota_exceeded': True,
                        'daily_limit_exceeded': True,
                        'quota_info': {
                            'daily_used': quota.daily_requests_used,
                            'daily_limit': quota.daily_limit,
                            'monthly_used': quota.requests_used,
                            'monthly_limit': quota.monthly_quota,
                        },
                        'message': f'You have reached your daily limit of {quota.daily_limit} AI requests. '
                                   f'Your daily limit resets at midnight.'
                    }, status=429)
                else:
                    return JsonResponse({
                        'success': False,
                        'error': 'Monthly AI usage quota exceeded',
                        'quota_exceeded': True,
                        'monthly_limit_exceeded': True,
                        'quota_info': {
                            'used': quota.requests_used,
                            'limit': quota.monthly_quota,
                            'days_until_reset': days_until_reset
                        },
                        'message': f'You have reached your monthly limit of {quota.monthly_quota} AI requests. '
                                   f'Your quota will reset in {days_until_reset} days.'
                    }, status=429)
            
            # Add quota info to request for easy access
            request.ai_quota = quota
            request.ai_remaining = remaining
            
            # Call the view
            start_time = time.time()
            try:
                response = view_func(request, *args, **kwargs)
                response_time_ms = int((time.time() - start_time) * 1000)
                
                # Track successful request
                board_id = kwargs.get('board_id')
                track_ai_request(
                    user=request.user,
                    feature=feature_name,
                    request_type=request_type,
                    board_id=board_id,
                    success=True,
                    response_time_ms=response_time_ms
                )
                
                return response
                
            except Exception as e:
                response_time_ms = int((time.time() - start_time) * 1000)
                
                # Track failed request (don't increment quota for failures)
                board_id = kwargs.get('board_id')
                track_ai_request(
                    user=request.user,
                    feature=feature_name,
                    request_type=request_type,
                    board_id=board_id,
                    success=False,
                    error_message=str(e),
                    response_time_ms=response_time_ms
                )
                
                raise  # Re-raise the exception
        
        return wrapper
    return decorator


def get_usage_stats(user, days=30):
    """
    Get AI usage statistics for a user
    
    Returns dict with usage analytics
    """
    from api.ai_usage_models import AIRequestLog
    from datetime import timedelta
    from django.db.models import Count, Avg
    
    quota = get_or_create_quota(user)
    
    # Get logs from last N days
    since = timezone.now() - timedelta(days=days)
    logs = AIRequestLog.objects.filter(user=user, timestamp__gte=since)
    
    # Aggregate by feature
    by_feature = logs.values('feature').annotate(
        count=Count('id'),
        avg_response_time=Avg('response_time_ms')
    ).order_by('-count')
    
    # Success rate
    total_requests = logs.count()
    successful_requests = logs.filter(success=True).count()
    success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 100
    
    return {
        'quota': {
            'used': quota.requests_used,
            'limit': quota.monthly_quota,
            'remaining': quota.get_remaining_requests(),
            'percentage': quota.get_usage_percent(),
            'days_until_reset': quota.get_days_until_reset(),
            'period_start': quota.period_start,
            'period_end': quota.period_end,
        },
        'lifetime': {
            'total_requests': quota.total_requests_all_time,
            'last_request': quota.last_request_at,
        },
        'recent': {
            'total_requests': total_requests,
            'successful_requests': successful_requests,
            'failed_requests': total_requests - successful_requests,
            'success_rate': round(success_rate, 1),
            'by_feature': list(by_feature),
        }
    }
