"""
AI Coach Views and API Endpoints

Provides views and API endpoints for the AI coaching system
"""

import logging
import json
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q, Case, When, IntegerField
from django.core.paginator import Paginator

from kanban.models import Board, Task
from kanban.coach_models import (
    CoachingSuggestion,
    CoachingFeedback,
    PMMetrics,
    CoachingInsight
)
from kanban.utils.coaching_rules import CoachingRuleEngine
from kanban.utils.ai_coach_service import AICoachService
from kanban.utils.feedback_learning import FeedbackLearningSystem

logger = logging.getLogger(__name__)


@login_required
def coach_dashboard(request, board_id):
    """
    Main coaching dashboard showing suggestions and insights
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Get active suggestions — ordered by semantic severity (critical→high→medium→low→info)
    severity_order = Case(
        When(severity='critical', then=0),
        When(severity='high', then=1),
        When(severity='medium', then=2),
        When(severity='low', then=3),
        When(severity='info', then=4),
        default=5,
        output_field=IntegerField()
    )
    active_suggestions = CoachingSuggestion.objects.filter(
        board=board,
        status__in=['active', 'acknowledged']
    ).annotate(severity_rank=severity_order).order_by('severity_rank', '-created_at')
    
    # Get recent resolved suggestions
    recent_resolved = CoachingSuggestion.objects.filter(
        board=board,
        status='resolved',
        resolved_at__gte=timezone.now() - timedelta(days=30)
    ).order_by('-resolved_at')[:10]
    
    # Calculate coaching effectiveness
    learning_system = FeedbackLearningSystem()
    effectiveness = learning_system.calculate_pm_coaching_effectiveness(
        board, request.user, days=30
    )
    
    # Get improvement recommendations
    recommendations = learning_system.get_improvement_recommendations(board, request.user)
    
    # Group suggestions by severity
    critical = active_suggestions.filter(severity='critical')
    high = active_suggestions.filter(severity='high')
    medium = active_suggestions.filter(severity='medium')
    low = active_suggestions.filter(severity='low')
    info = active_suggestions.filter(severity='info')
    
    context = {
        'board': board,
        'critical_suggestions': critical,
        'high_suggestions': high,
        'medium_suggestions': medium,
        'low_suggestions': low,
        'info_suggestions': info,
        'recent_resolved': recent_resolved,
        'effectiveness': effectiveness,
        'recommendations': recommendations,
        'total_active': active_suggestions.count(),
    }
    
    return render(request, 'kanban/coach_dashboard.html', context)


@login_required
def suggestion_detail(request, suggestion_id):
    """
    Detailed view of a coaching suggestion
    """
    suggestion = get_object_or_404(CoachingSuggestion, id=suggestion_id)
    board = suggestion.board
    
    # Get related feedback
    feedback_entries = suggestion.feedback_entries.all()
    
    context = {
        'suggestion': suggestion,
        'board': board,
        'feedback_entries': feedback_entries,
    }
    
    return render(request, 'kanban/coach_suggestion_detail.html', context)


@login_required
@require_POST
def generate_suggestions(request, board_id):
    """
    Generate new coaching suggestions for a board
    """
    from api.ai_usage_utils import check_ai_quota
    
    board = get_object_or_404(Board, id=board_id)
    
    # Check if user can use AI features
    can_use_ai = True
    has_quota, _, _ = check_ai_quota(request.user)
    if not has_quota:
        can_use_ai = False
    
    try:
        # Run rule engine
        rule_engine = CoachingRuleEngine(board)
        suggestions_data = rule_engine.analyze_and_generate_suggestions()
        
        # Create board context for AI enhancement
        context = {
            'board_name': board.name,
            'team_size': board.members.count(),
            'active_tasks': Task.objects.filter(column__board=board, progress__isnull=False, progress__lt=100).count(),
            'project_phase': 'active',  # Could be enhanced
        }
        
        # Initialize AI coach service
        ai_coach = AICoachService()
        learning_system = FeedbackLearningSystem()
        
        # Log AI availability status
        if ai_coach.gemini_available:
            logger.info(f"AI enhancement enabled for board {board.name}")
        else:
            logger.warning(f"AI enhancement not available - suggestions will be basic format only")
        
        created_count = 0
        skipped_count = 0
        enhanced_count = 0
        
        for suggestion_data in suggestions_data:
            # Check if we should generate this based on learning
            should_generate = learning_system.should_generate_suggestion(
                suggestion_data['suggestion_type'],
                board,
                float(suggestion_data['confidence_score'])
            )
            
            if not should_generate:
                skipped_count += 1
                continue
            
            # Adjust confidence based on learning
            adjusted_confidence = learning_system.get_adjusted_confidence(
                suggestion_data['suggestion_type'],
                float(suggestion_data['confidence_score']),
                board
            )
            suggestion_data['confidence_score'] = adjusted_confidence
            
            # Only attempt AI enhancement if user has AI quota remaining
            if can_use_ai:
                try:
                    original_method = suggestion_data.get('generation_method', 'rule')
                    suggestion_data = ai_coach.enhance_suggestion_with_ai(
                        suggestion_data, context
                    )
                    # Track if enhancement was successful
                    if suggestion_data.get('generation_method') == 'hybrid':
                        enhanced_count += 1
                        logger.debug(f"Successfully enhanced: {suggestion_data['title']}")
                except Exception as enhance_error:
                    logger.error(f"AI enhancement failed for '{suggestion_data['title']}': {enhance_error}")
            
            # Check if similar suggestion already exists
            # Block if recent suggestion exists in these statuses:
            # - active: already showing
            # - acknowledged: user is aware, don't nag (3 days)
            # - in_progress: user is working on it (7 days)
            # - resolved: user fixed it, don't show again (30 days)
            from django.db.models import Q
            
            existing = CoachingSuggestion.objects.filter(
                board=board,
                suggestion_type=suggestion_data['suggestion_type']
            ).filter(
                Q(status='active', created_at__gte=timezone.now() - timedelta(days=3)) |
                Q(status='acknowledged', created_at__gte=timezone.now() - timedelta(days=3)) |
                Q(status='in_progress', created_at__gte=timezone.now() - timedelta(days=7)) |
                Q(status='resolved', created_at__gte=timezone.now() - timedelta(days=30))
            ).exists()
            
            if existing:
                skipped_count += 1
                continue
            
            # Create suggestion
            CoachingSuggestion.objects.create(**suggestion_data)
            created_count += 1
        
        logger.info(
            f"Generated {created_count} suggestions for board {board.name}, "
            f"enhanced {enhanced_count} with AI, skipped {skipped_count}"
        )
        
        # Create user-friendly message
        if created_count == 0:
            message = "No new suggestions at this time"
        elif created_count == 1:
            message = f"✅ Generated 1 new suggestion"
        else:
            message = f"✅ Generated {created_count} new suggestions"
        
        return JsonResponse({
            'success': True,
            'created': created_count,
            'enhanced': enhanced_count,
            'skipped': skipped_count,
            'ai_available': ai_coach.gemini_available,
            'message': message
        })
        
    except Exception as e:
        import traceback
        logger.error(f"Error generating suggestions: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def acknowledge_suggestion(request, suggestion_id):
    """
    Mark a suggestion as acknowledged
    """
    suggestion = get_object_or_404(CoachingSuggestion, id=suggestion_id)
    
    try:
        suggestion.acknowledge(request.user)
        
        return JsonResponse({
            'success': True,
            'message': 'Suggestion acknowledged'
        })
        
    except Exception as e:
        logger.error(f"Error acknowledging suggestion: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def dismiss_suggestion(request, suggestion_id):
    """
    Dismiss a suggestion
    """
    suggestion = get_object_or_404(CoachingSuggestion, id=suggestion_id)
    
    try:
        suggestion.dismiss()
        
        # Optionally record as feedback
        learning_system = FeedbackLearningSystem()
        learning_system.record_feedback(
            suggestion=suggestion,
            user=request.user,
            was_helpful=False,
            relevance_score=1,
            action_taken='ignored',
            feedback_text='Dismissed by user'
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Suggestion dismissed'
        })
        
    except Exception as e:
        logger.error(f"Error dismissing suggestion: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def submit_feedback(request, suggestion_id):
    """
    Submit detailed feedback on a suggestion
    """
    suggestion = get_object_or_404(CoachingSuggestion, id=suggestion_id)
    
    try:
        # Accept both form POST and JSON data
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            was_helpful = data.get('was_helpful', False)
            action_taken = data.get('action_taken', 'ignored')
            feedback_text = data.get('feedback_text', '')
            outcome_description = data.get('outcome_description', '')
            improved_situation = data.get('improved_situation')
            relevance_score = int(data.get('relevance_score', 3))
        else:
            # Form POST data
            was_helpful = request.POST.get('helpful', '').lower() == 'true'
            action_taken = request.POST.get('action_taken', '') or 'ignored'
            feedback_text = request.POST.get('comment', '')
            outcome_description = ''
            improved_situation = None
            relevance_score = 3
        
        # Record feedback
        learning_system = FeedbackLearningSystem()
        feedback = learning_system.record_feedback(
            suggestion=suggestion,
            user=request.user,
            was_helpful=was_helpful,
            relevance_score=relevance_score,
            action_taken=action_taken,
            feedback_text=feedback_text,
            outcome_description=outcome_description,
            improved_situation=improved_situation
        )
        
        # Return appropriate response based on request type
        if request.content_type == 'application/json':
            return JsonResponse({
                'success': True,
                'message': 'Thank you for your feedback!',
                'feedback_id': feedback.id
            })
        else:
            # Form submission - redirect back with success message
            messages.success(request, 'Thank you for your feedback! It helps us improve AI Coach.')
            return redirect('coach_suggestion_detail', suggestion_id=suggestion.id)
        
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        if request.content_type == 'application/json':
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
        else:
            messages.error(request, f'Error submitting feedback: {str(e)}')
            return redirect('coach_suggestion_detail', suggestion_id=suggestion.id)


@login_required
@require_http_methods(["GET", "POST"])
def ask_coach(request, board_id):
    """
    Ask the AI coach a question
    """
    from api.ai_usage_utils import check_ai_quota, track_ai_request, get_or_create_quota
    import time
    
    board = get_object_or_404(Board, id=board_id)
    
    if request.method == 'POST':
        # Check AI quota before processing
        has_quota, quota, remaining = check_ai_quota(request.user)
        
        if not has_quota:
            days_until_reset = quota.get_days_until_reset()
            return JsonResponse({
                'success': False,
                'error': 'AI usage quota exceeded',
                'quota_exceeded': True,
                'message': f'You have reached your monthly AI usage limit of {quota.monthly_quota} requests. '
                           f'Your quota will reset in {days_until_reset} days.'
            }, status=429)
        
        start_time = time.time()
        try:
            data = json.loads(request.body)
            question = data.get('question', '')
            
            if not question:
                return JsonResponse({
                    'success': False,
                    'error': 'Question is required'
                }, status=400)
            
            # Get AI coaching advice
            ai_coach = AICoachService()
            advice = ai_coach.generate_coaching_advice(board, request.user, question)
            
            # Track successful AI request
            response_time_ms = int((time.time() - start_time) * 1000)
            track_ai_request(
                user=request.user,
                feature='ai_coach',
                request_type='question',
                board_id=board_id,
                success=True,
                response_time_ms=response_time_ms
            )
            
            # Get updated remaining count
            _, _, remaining = check_ai_quota(request.user)
            
            return JsonResponse({
                'success': True,
                'advice': advice,
                'question': question,
                'ai_usage': {
                    'remaining': remaining,
                    'used': quota.requests_used + 1
                }
            })
            
        except Exception as e:
            logger.error(f"Error getting coaching advice: {e}")
            
            # Track failed request (doesn't count against quota)
            response_time_ms = int((time.time() - start_time) * 1000)
            track_ai_request(
                user=request.user,
                feature='ai_coach',
                request_type='question',
                board_id=board_id,
                success=False,
                error_message=str(e),
                response_time_ms=response_time_ms
            )
            
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    # GET request - show ask coach page with quota info
    quota = get_or_create_quota(request.user)
    
    ai_quota_info = {
        'used': quota.requests_used,
        'limit': quota.monthly_quota,
        'remaining': quota.get_remaining_requests(),
        'percentage': quota.get_usage_percent()
    }
    
    context = {
        'board': board,
        'ai_quota': ai_quota_info
    }
    
    return render(request, 'kanban/coach_ask.html', context)


@login_required
def coaching_analytics(request, board_id):
    """
    Analytics view for coaching effectiveness
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Get date range (default: last 30 days)
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)
    
    # Get suggestions
    suggestions = CoachingSuggestion.objects.filter(
        board=board,
        created_at__gte=start_date
    )
    
    # Calculate metrics
    total = suggestions.count()
    by_type = suggestions.values('suggestion_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    by_severity = suggestions.values('severity').annotate(
        count=Count('id')
    )
    
    by_status = suggestions.values('status').annotate(
        count=Count('id')
    )
    
    # Feedback analysis
    with_feedback = suggestions.filter(was_helpful__isnull=False)
    helpful_count = suggestions.filter(was_helpful=True).count()
    acted_on = suggestions.filter(
        action_taken__in=['accepted', 'partially', 'modified']
    ).count()
    
    # Calculate effectiveness
    learning_system = FeedbackLearningSystem()
    effectiveness = learning_system.calculate_pm_coaching_effectiveness(
        board, request.user, days
    )
    
    # Get insights
    insights = CoachingInsight.objects.filter(
        is_active=True
    ).order_by('-confidence_score')[:10]
    
    context = {
        'board': board,
        'days': days,
        'total_suggestions': total,
        'by_type': by_type,
        'by_severity': by_severity,
        'by_status': by_status,
        'helpful_count': helpful_count,
        'acted_on': acted_on,
        'effectiveness': effectiveness,
        'insights': insights,
    }
    
    return render(request, 'kanban/coach_analytics.html', context)


@login_required
def get_suggestions_api(request, board_id):
    """
    API endpoint to get coaching suggestions
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Get filter parameters
    status = request.GET.get('status', 'active')
    severity = request.GET.get('severity')
    suggestion_type = request.GET.get('type')
    limit = int(request.GET.get('limit', 20))
    
    # Build query
    query = Q(board=board)
    
    if status:
        if status == 'active':
            query &= Q(status__in=['active', 'acknowledged'])
        else:
            query &= Q(status=status)
    
    if severity:
        query &= Q(severity=severity)
    
    if suggestion_type:
        query &= Q(suggestion_type=suggestion_type)
    
    # Get suggestions
    suggestions = CoachingSuggestion.objects.filter(query).order_by(
        '-severity', '-created_at'
    )[:limit]
    
    # Serialize
    data = [
        {
            'id': s.id,
            'type': s.suggestion_type,
            'severity': s.severity,
            'status': s.status,
            'title': s.title,
            'message': s.message,
            'reasoning': s.reasoning,
            'recommended_actions': s.recommended_actions,
            'expected_impact': s.expected_impact,
            'confidence_score': float(s.confidence_score),
            'created_at': s.created_at.isoformat(),
            'days_active': s.days_active,
            'is_expired': s.is_expired,
        }
        for s in suggestions
    ]
    
    return JsonResponse({
        'success': True,
        'suggestions': data,
        'count': len(data)
    })
