from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Sum, Q, Avg
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
import json
from datetime import timedelta

from kanban.models import Board, Task
from .models import (
    AIAssistantSession,
    AIAssistantMessage,
    ProjectKnowledgeBase,
    AIAssistantAnalytics,
    AITaskRecommendation,
    UserPreference,
)
from .forms import AISessionForm, UserPreferenceForm
from .utils.chatbot_service import TaskFlowChatbotService


@login_required(login_url='accounts:login')
@ensure_csrf_cookie
def assistant_welcome(request):
    """Welcome page for AI Project Assistant"""
    user_sessions = AIAssistantSession.objects.filter(user=request.user).order_by('-updated_at')[:5]
    
    # Get or create user preferences
    user_pref, created = UserPreference.objects.get_or_create(user=request.user)
    
    context = {
        'recent_sessions': user_sessions,
        'total_sessions': AIAssistantSession.objects.filter(user=request.user).count(),
        'user_preferences': user_pref,
    }
    return render(request, 'ai_assistant/welcome.html', context)


@login_required(login_url='accounts:login')
@ensure_csrf_cookie
def chat_interface(request, session_id=None):
    """Main chat interface for AI Assistant"""
    
    # Get or create user preferences
    user_pref, created = UserPreference.objects.get_or_create(user=request.user)
    
    # Check for session in query parameter first
    session_param = request.GET.get('session')
    if session_param:
        try:
            session_id = int(session_param)
        except (ValueError, TypeError):
            session_id = None
    
    # Get session or create new one
    if session_id:
        session = get_object_or_404(AIAssistantSession, id=session_id, user=request.user)
    else:
        # Get active session or create new one
        session = AIAssistantSession.objects.filter(user=request.user, is_active=True).first()
        if not session:
            session = AIAssistantSession.objects.create(
                user=request.user,
                title=f"Chat Session {timezone.now().strftime('%Y-%m-%d %H:%M')}"
            )
    
    # Get user's organization
    user_org = request.user.profile.organization if hasattr(request.user, 'profile') else None
    
    # Get user's boards for context selection - filtered by organization
    if user_org:
        user_boards = Board.objects.filter(
            organization=user_org,
        ).filter(
            Q(created_by=request.user) | Q(members=request.user)
        ).distinct()
    else:
        user_boards = Board.objects.none()
    
    # Count active boards for welcome message
    active_boards_count = user_boards.count()
    
    # Get initial query from URL parameter (e.g., from wiki quick queries)
    initial_query = request.GET.get('q', '')
    
    context = {
        'session': session,
        'boards': user_boards,
        'user_preferences': user_pref,
        'initial_query': initial_query,
        'active_boards_count': active_boards_count,
    }
    return render(request, 'ai_assistant/chat.html', context)


@login_required(login_url='accounts:login')
@require_http_methods(["POST"])
def create_session(request):
    """Create a new AI Assistant session"""
    try:
        data = json.loads(request.body)
        
        form = AISessionForm(data)
        if form.is_valid():
            session = form.save(commit=False)
            session.user = request.user
            session.save()
            
            return JsonResponse({
                'status': 'success',
                'session_id': session.id,
                'title': session.title,
            })
        else:
            return JsonResponse({
                'status': 'error',
                'errors': form.errors
            }, status=400)
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='accounts:login')
@require_POST
def send_message(request):
    """Send message to AI Assistant and get response"""
    from api.ai_usage_utils import check_ai_quota, track_ai_request
    from kanban.utils.demo_limits import (
        is_demo_mode, check_ai_generation_limit,
        increment_ai_generation_count, record_limitation_hit
    )
    import time
    
    # Check demo AI limit first (if in demo mode)
    if is_demo_mode(request):
        demo_ai_status = check_ai_generation_limit(request)
        if not demo_ai_status['can_generate']:
            record_limitation_hit(request, 'ai_limit')
            return JsonResponse({
                'error': 'Demo AI limit reached',
                'quota_exceeded': True,
                'message': demo_ai_status['message'],
                'demo_limit': True
            }, status=429)
    
    # Check AI quota before processing (for non-demo authenticated users)
    if not is_demo_mode(request):
        has_quota, quota, remaining = check_ai_quota(request.user)
        
        if not has_quota:
            days_until_reset = quota.get_days_until_reset()
            return JsonResponse({
                'error': 'AI usage quota exceeded',
                'quota_exceeded': True,
                'message': f'You have reached your monthly AI usage limit of {quota.monthly_quota} requests. '
                           f'Your quota will reset in {days_until_reset} days.'
            }, status=429)
    else:
        quota = None
        remaining = float('inf')
    
    start_time = time.time()
    
    try:
        data = json.loads(request.body)
        
        message_text = data.get('message', '').strip()
        session_id = data.get('session_id')
        board_id = data.get('board_id')
        # Sanitize board_id - convert empty string to None
        if board_id is not None and (board_id == '' or board_id == 'null'):
            board_id = None
        elif board_id:
            try:
                board_id = int(board_id)
            except (ValueError, TypeError):
                board_id = None
        refresh_data = data.get('refresh_data', False)
        # Note: history is no longer used - each AI request is stateless to prevent token accumulation
        
        if not message_text:
            return JsonResponse({'error': 'Message cannot be empty'}, status=400)
        
        # Get session
        try:
            session = AIAssistantSession.objects.get(id=session_id, user=request.user)
        except AIAssistantSession.DoesNotExist:
            return JsonResponse({'error': 'Session not found'}, status=404)
        
        # Get board context if specified
        board = None
        if board_id:
            board = get_object_or_404(Board, id=board_id)
            session.board = board
            session.save()
        
        # Save user message
        user_message = AIAssistantMessage.objects.create(
            session=session,
            role='user',
            content=message_text
        )
        
        # Get response from chatbot service
        # Note: Using stateless mode - no history passed to prevent session persistence
        chatbot = TaskFlowChatbotService(user=request.user, board=board)
        response = chatbot.get_response(
            message_text,
            use_cache=not refresh_data
        )
        
        # Save assistant message
        assistant_message = AIAssistantMessage.objects.create(
            session=session,
            role='assistant',
            content=response['response'],
            model=response.get('source', 'gemini'),
            tokens_used=response.get('tokens', 0),
            used_web_search=response.get('used_web_search', False),
            search_sources=response.get('search_sources', []),
            context_data=response.get('context', {})
        )
        
        # Update session message count
        session.message_count = AIAssistantMessage.objects.filter(session=session).count()
        session.total_tokens_used += response.get('tokens', 0)
        session.save()
        
        # Update analytics
        try:
            today = timezone.now().date()
            analytics, created = AIAssistantAnalytics.objects.get_or_create(
                user=request.user,
                board=board,
                date=today,
                defaults={
                    'sessions_created': 0,
                    'messages_sent': 0,
                    'gemini_requests': 0,
                    'web_searches_performed': 0,
                    'total_tokens_used': 0,
                }
            )
            
            analytics.messages_sent += 1
            if response.get('source') == 'gemini':
                analytics.gemini_requests += 1
            
            if response.get('used_web_search'):
                analytics.web_searches_performed += 1
            
            analytics.total_tokens_used += response.get('tokens', 0)
            analytics.save()
        except Exception as e:
            print(f"Error updating analytics: {e}")
        
        # Track AI usage (wrap in try-except to not fail the response if tracking fails)
        try:
            response_time_ms = int((time.time() - start_time) * 1000)
            track_ai_request(
                user=request.user,
                feature='ai_assistant',
                request_type='message',
                board_id=board_id,
                success=True,
                tokens_used=response.get('tokens', 0),
                response_time_ms=response_time_ms
            )
        except Exception as e:
            print(f"Error tracking AI request: {e}")
        
        # Track demo AI usage (for demo limitation banner)
        if is_demo_mode(request):
            increment_ai_generation_count(request)
        
        # Get updated remaining count
        if not is_demo_mode(request):
            _, _, remaining = check_ai_quota(request.user)
        
        # For demo mode, get demo AI usage stats
        demo_ai_info = None
        if is_demo_mode(request):
            demo_ai_status = check_ai_generation_limit(request)
            demo_ai_info = {
                'used': demo_ai_status['current_count'],
                'max': demo_ai_status['max_allowed'],
                'remaining': demo_ai_status['max_allowed'] - demo_ai_status['current_count']
            }
        
        return JsonResponse({
            'status': 'success',
            'message_id': assistant_message.id,
            'response': response['response'],
            'source': response.get('source', 'gemini'),
            'used_web_search': response.get('used_web_search', False),
            'search_sources': response.get('search_sources', []),
            'ai_usage': demo_ai_info if demo_ai_info else {
                'remaining': remaining,
                'used': quota.requests_used + 1 if quota else 0
            }
        })
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        # Track failed request (doesn't count against quota)
        try:
            response_time_ms = int((time.time() - start_time) * 1000)
            board_id_val = board_id if 'board_id' in locals() else None
            # Ensure board_id_val is properly sanitized
            if board_id_val is not None and board_id_val == '':
                board_id_val = None
            track_ai_request(
                user=request.user,
                feature='ai_assistant',
                request_type='message',
                board_id=board_id_val,
                success=False,
                error_message=str(e),
                response_time_ms=response_time_ms
            )
        except Exception as track_error:
            print(f"Error tracking failed AI request: {track_error}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='accounts:login')
def get_sessions(request):
    """Get user's chat sessions"""
    sessions = AIAssistantSession.objects.filter(user=request.user).order_by('-updated_at')
    
    data = {
        'sessions': [
            {
                'id': s.id,
                'title': s.title,
                'description': s.description,
                'message_count': s.message_count,
                'is_active': s.is_active,
                'updated_at': s.updated_at.isoformat(),
            }
            for s in sessions
        ]
    }
    return JsonResponse(data)


@login_required(login_url='accounts:login')
def get_session_messages(request, session_id):
    """Get messages for a specific session"""
    try:
        session = get_object_or_404(AIAssistantSession, id=session_id, user=request.user)
        
        # Get user preferences for messages per page
        user_pref, _ = UserPreference.objects.get_or_create(user=request.user)
        
        # Get pagination parameters
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', user_pref.messages_per_page))
        
        messages_qs = AIAssistantMessage.objects.filter(session=session).order_by('created_at', 'id')
        
        # Calculate pagination
        total = messages_qs.count()
        start = (page - 1) * per_page
        end = start + per_page
        messages = messages_qs[start:end]
        
        data = {
            'session_id': session.id,
            'total': total,
            'page': page,
            'per_page': per_page,
            'messages': [
                {
                    'id': m.id,
                    'role': m.role,
                    'content': m.content,
                    'model': m.model,
                    'is_starred': m.is_starred,
                    'used_web_search': m.used_web_search,
                    'created_at': m.created_at.isoformat(),
                }
                for m in messages
            ]
        }
        return JsonResponse(data)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='accounts:login')
@require_POST
def rename_session(request, session_id):
    """Rename a chat session"""
    try:
        session = get_object_or_404(AIAssistantSession, id=session_id, user=request.user)
        
        data = json.loads(request.body)
        new_title = data.get('title', '').strip()
        
        if not new_title:
            return JsonResponse({'error': 'Title cannot be empty'}, status=400)
        
        session.title = new_title
        session.save()
        
        return JsonResponse({'status': 'success', 'title': session.title})
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='accounts:login')
@require_POST
def delete_session(request, session_id):
    """Delete a chat session"""
    try:
        session = get_object_or_404(AIAssistantSession, id=session_id, user=request.user)
        session.delete()
        
        return JsonResponse({'status': 'success'})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='accounts:login')
@require_POST
def clear_session(request, session_id):
    """Clear all messages in a chat session"""
    try:
        session = get_object_or_404(AIAssistantSession, id=session_id, user=request.user)
        
        # Delete all messages in the session
        AIAssistantMessage.objects.filter(session=session).delete()
        
        # Reset session counters
        session.message_count = 0
        session.total_tokens_used = 0
        session.save()
        
        return JsonResponse({
            'status': 'success',
            'message': f'All messages cleared from session "{session.title}"'
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='accounts:login')
def export_session(request, session_id):
    """Export chat session as JSON or Markdown"""
    try:
        session = get_object_or_404(AIAssistantSession, id=session_id, user=request.user)
        export_format = request.GET.get('format', 'json')  # 'json' or 'markdown'
        
        messages = AIAssistantMessage.objects.filter(session=session).order_by('created_at')
        
        if export_format == 'markdown':
            # Export as Markdown
            from django.http import HttpResponse
            
            content = f"# {session.title}\n\n"
            content += f"**Created:** {session.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            content += f"**Last Updated:** {session.updated_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            content += f"**Total Messages:** {session.message_count}\n"
            if session.board:
                content += f"**Board Context:** {session.board.name}\n"
            content += f"\n---\n\n"
            
            for msg in messages:
                role_icon = "👤" if msg.role == 'user' else "🤖"
                content += f"## {role_icon} {msg.role.capitalize()}\n"
                content += f"*{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
                content += f"{msg.content}\n\n"
                
                if msg.used_web_search:
                    content += f"*🔍 Web search was used for this response*\n\n"
                
                content += "---\n\n"
            
            # Create response
            response = HttpResponse(content, content_type='text/markdown')
            response['Content-Disposition'] = f'attachment; filename="chat_session_{session.id}_{session.created_at.strftime("%Y%m%d")}.md"'
            return response
        
        else:
            # Export as JSON
            from django.http import JsonResponse
            
            data = {
                'session': {
                    'id': session.id,
                    'title': session.title,
                    'description': session.description,
                    'created_at': session.created_at.isoformat(),
                    'updated_at': session.updated_at.isoformat(),
                    'message_count': session.message_count,
                    'total_tokens_used': session.total_tokens_used,
                    'board': session.board.name if session.board else None,
                },
                'messages': [
                    {
                        'id': msg.id,
                        'role': msg.role,
                        'content': msg.content,
                        'model': msg.model,
                        'tokens_used': msg.tokens_used,
                        'created_at': msg.created_at.isoformat(),
                        'is_starred': msg.is_starred,
                        'is_helpful': msg.is_helpful,
                        'feedback': msg.feedback,
                        'used_web_search': msg.used_web_search,
                        'search_sources': msg.search_sources,
                    }
                    for msg in messages
                ],
                'export_date': timezone.now().isoformat(),
            }
            
            # Create downloadable JSON response
            from django.http import HttpResponse
            import json
            
            response = HttpResponse(
                json.dumps(data, indent=2),
                content_type='application/json'
            )
            response['Content-Disposition'] = f'attachment; filename="chat_session_{session.id}_{session.created_at.strftime("%Y%m%d")}.json"'
            return response
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='accounts:login')
@require_POST
def toggle_star_message(request, message_id):
    """Toggle star on a message"""
    try:
        message = get_object_or_404(AIAssistantMessage, id=message_id, session__user=request.user)
        message.is_starred = not message.is_starred
        message.save()
        
        return JsonResponse({'status': 'success', 'is_starred': message.is_starred})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='accounts:login')
@require_POST
def submit_feedback(request, message_id):
    """Submit feedback on a message"""
    try:
        message = get_object_or_404(AIAssistantMessage, id=message_id, session__user=request.user)
        
        data = json.loads(request.body)
        is_helpful = data.get('is_helpful', None)
        feedback_text = data.get('feedback', '')
        
        message.is_helpful = is_helpful
        message.feedback = feedback_text
        message.save()
        
        return JsonResponse({'status': 'success'})
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='accounts:login')
def analytics_dashboard(request):
    """View analytics dashboard"""
    board_id = request.GET.get('board_id')
    
    # Get user preferences
    user_pref, _ = UserPreference.objects.get_or_create(user=request.user)
    
    # Get date range (last 30 days)
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    # Get analytics
    analytics_qs = AIAssistantAnalytics.objects.filter(
        user=request.user,
        date__gte=start_date,
        date__lte=end_date
    )
    
    if board_id:
        analytics_qs = analytics_qs.filter(board_id=board_id)
    
    # Aggregate metrics
    total_messages = analytics_qs.aggregate(Sum('messages_sent'))['messages_sent__sum'] or 0
    total_tokens = analytics_qs.aggregate(Sum('total_tokens_used'))['total_tokens_used__sum'] or 0
    web_searches = analytics_qs.aggregate(Sum('web_searches_performed'))['web_searches_performed__sum'] or 0
    kb_queries = analytics_qs.aggregate(Sum('knowledge_base_queries'))['knowledge_base_queries__sum'] or 0
    gemini_requests = analytics_qs.aggregate(Sum('gemini_requests'))['gemini_requests__sum'] or 0
    
    # Calculate RAG usage rate (KB queries / total requests)
    rag_usage_rate = round((kb_queries / gemini_requests * 100), 1) if gemini_requests > 0 else 0
    
    # Calculate context-aware response rate (KB or Web Search used)
    context_aware_requests = kb_queries + web_searches
    context_aware_rate = round((context_aware_requests / gemini_requests * 100), 1) if gemini_requests > 0 else 0
    
    # Get active sessions count and multi-turn conversations
    active_sessions = AIAssistantSession.objects.filter(
        user=request.user,
        updated_at__gte=timezone.now() - timedelta(days=30)
    ).count()
    
    # Count multi-turn conversations (sessions with 3+ messages)
    multi_turn_sessions = AIAssistantSession.objects.filter(
        user=request.user,
        updated_at__gte=timezone.now() - timedelta(days=30),
        message_count__gte=3
    ).count()
    
    # Calculate average response time
    avg_response_time = analytics_qs.aggregate(Avg('avg_response_time_ms'))['avg_response_time_ms__avg'] or 0
    
    # Calculate average tokens per message (efficiency metric)
    avg_tokens_per_message = round(total_tokens / total_messages, 1) if total_messages > 0 else 0
    
    context = {
        'total_messages': total_messages,
        'total_tokens': total_tokens,
        'web_searches': web_searches,
        'kb_queries': kb_queries,
        'gemini_requests': gemini_requests,
        'rag_usage_rate': rag_usage_rate,
        'context_aware_rate': context_aware_rate,
        'active_sessions': active_sessions,
        'multi_turn_sessions': multi_turn_sessions,
        'avg_response_time': round(avg_response_time / 1000, 2) if avg_response_time else 0,  # Convert to seconds
        'avg_tokens_per_message': avg_tokens_per_message,
        'user_preferences': user_pref,
    }
    return render(request, 'ai_assistant/analytics.html', context)


@login_required(login_url='accounts:login')
def get_analytics_data(request):
    """Get analytics data for charts"""
    board_id = request.GET.get('board_id')
    
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    analytics_qs = AIAssistantAnalytics.objects.filter(
        user=request.user,
        date__gte=start_date,
        date__lte=end_date
    ).order_by('date')
    
    if board_id:
        analytics_qs = analytics_qs.filter(board_id=board_id)
    
    data = {
        'dates': [],
        'messages': [],
        'tokens': [],
        'web_searches': [],
        'kb_queries': [],
    }
    
    for analytics in analytics_qs:
        data['dates'].append(analytics.date.isoformat())
        data['messages'].append(analytics.messages_sent)
        data['tokens'].append(analytics.total_tokens_used)
        data['web_searches'].append(analytics.web_searches_performed)
        data['kb_queries'].append(analytics.knowledge_base_queries)
    
    return JsonResponse(data)


@login_required(login_url='accounts:login')
def view_recommendations(request):
    """View AI task recommendations"""
    board_id = request.GET.get('board_id')
    status = request.GET.get('status', 'pending')
    
    # Get recommendations
    recs_qs = AITaskRecommendation.objects.filter(
        board__in=Board.objects.filter(Q(created_by=request.user) | Q(members=request.user)).distinct()
    )
    
    if board_id:
        recs_qs = recs_qs.filter(board_id=board_id)
    
    if status:
        recs_qs = recs_qs.filter(status=status)
    
    recommendations = recs_qs.order_by('-created_at')
    
    context = {
        'recommendations': recommendations,
        'status_filter': status,
    }
    return render(request, 'ai_assistant/recommendations.html', context)


@login_required(login_url='accounts:login')
@require_POST
def accept_recommendation(request, recommendation_id):
    """Accept a task recommendation"""
    try:
        rec = get_object_or_404(AITaskRecommendation, id=recommendation_id)
        rec.status = 'accepted'
        rec.save()
        
        messages.success(request, 'Recommendation accepted!')
        return JsonResponse({'status': 'success'})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='accounts:login')
@require_POST
def reject_recommendation(request, recommendation_id):
    """Reject a task recommendation"""
    try:
        rec = get_object_or_404(AITaskRecommendation, id=recommendation_id)
        rec.status = 'rejected'
        rec.save()
        
        messages.success(request, 'Recommendation rejected.')
        return JsonResponse({'status': 'success'})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='accounts:login')
def user_preferences(request):
    """Manage user preferences"""
    user_pref, created = UserPreference.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = UserPreferenceForm(request.POST, instance=user_pref)
        if form.is_valid():
            form.save()
            messages.success(request, 'Preferences updated successfully!')
            return redirect('ai_assistant:preferences')
    else:
        form = UserPreferenceForm(instance=user_pref)
    
    context = {'form': form, 'user_preferences': user_pref}
    return render(request, 'ai_assistant/preferences.html', context)


@login_required(login_url='accounts:login')
@require_POST
def save_preferences(request):
    """Save user preferences via AJAX"""
    try:
        user_pref, _ = UserPreference.objects.get_or_create(user=request.user)
        
        data = json.loads(request.body)
        
        # Update preferences
        if 'enable_web_search' in data:
            user_pref.enable_web_search = data['enable_web_search']
        if 'enable_task_insights' in data:
            user_pref.enable_task_insights = data['enable_task_insights']
        if 'enable_risk_alerts' in data:
            user_pref.enable_risk_alerts = data['enable_risk_alerts']
        
        user_pref.save()
        
        return JsonResponse({'status': 'success'})
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='accounts:login')
def knowledge_base_view(request):
    """View and manage project knowledge base"""
    board_id = request.GET.get('board_id')
    
    # Get knowledge base entries
    kb_qs = ProjectKnowledgeBase.objects.filter(is_active=True)
    
    if board_id:
        kb_qs = kb_qs.filter(board_id=board_id)
    
    entries = kb_qs.order_by('-updated_at')
    
    context = {
        'entries': entries,
        'board_id': board_id,
    }
    return render(request, 'ai_assistant/knowledge_base.html', context)


@login_required(login_url='accounts:login')
@require_POST
def refresh_knowledge_base(request):
    """Refresh knowledge base from project data"""
    try:
        board_id = request.GET.get('board_id')
        
        # This would trigger KB indexing/refresh logic
        # For now, just return success
        
        return JsonResponse({
            'status': 'success',
            'message': 'Knowledge base refreshed successfully'
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
