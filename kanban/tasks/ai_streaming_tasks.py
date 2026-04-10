"""
Celery tasks for AI features with real-time WebSocket progress streaming.

Each task:
  1. Streams status updates via Django Channels (channel_layer.group_send)
  2. Calls the same AI utility functions used by the synchronous views
  3. Sends the final result (or error) over the WebSocket
  4. Tracks AI usage via track_ai_request()

Usage from a Django view:
  result = run_premortem_task.delay(board_id, user_id)
  return JsonResponse({'task_id': result.id, 'status': 'queued'})
"""
import json
import time
import logging

from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


def _send_status(task_id, message, progress=0):
    """Send a progress update to the AI task WebSocket group."""
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'ai_task_{task_id}',
            {
                'type': 'ai_status_update',
                'message': message,
                'progress': progress,
            },
        )
    except Exception as exc:
        logger.warning('Failed to send AI status update for task %s: %s', task_id, exc)


def _send_result(task_id, data):
    """Send the final result to the AI task WebSocket group."""
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'ai_task_{task_id}',
            {
                'type': 'ai_result',
                'data': data,
            },
        )
    except Exception as exc:
        logger.warning('Failed to send AI result for task %s: %s', task_id, exc)


def _send_error(task_id, message):
    """Send an error message to the AI task WebSocket group."""
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'ai_task_{task_id}',
            {
                'type': 'ai_error',
                'message': message,
            },
        )
    except Exception as exc:
        logger.warning('Failed to send AI error for task %s: %s', task_id, exc)


# ---------------------------------------------------------------------------
# 1. Pre-Mortem Analysis
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name='kanban.ai_streaming.run_premortem',
    queue='ai_tasks',
    time_limit=120,
    soft_time_limit=90,
)
def run_premortem_task(self, board_id, user_id):
    """Run Pre-Mortem AI analysis with streamed status updates."""
    task_id = self.request.id
    start_time = time.time()

    try:
        from kanban.models import Board
        from kanban.premortem_models import PreMortemAnalysis
        from kanban.premortem_views import (
            _collect_board_snapshot,
            _build_gemini_prompt,
            _call_gemini,
        )
        from api.ai_usage_utils import track_ai_request
        from django.contrib.auth.models import User
        from ai_assistant.utils.rbac_utils import can_spectra_read_board

        user = User.objects.get(id=user_id)
        board = Board.objects.get(id=board_id)

        # Re-validate board access at execution time (TOCTOU protection)
        if not can_spectra_read_board(user, board):
            _send_error(task_id, 'You no longer have access to this board.')
            return {'error': 'Access denied'}

        _send_status(task_id, 'Collecting board snapshot…', 10)
        snapshot = _collect_board_snapshot(board)

        _send_status(task_id, 'Building risk analysis prompt…', 25)
        system_prompt, user_prompt = _build_gemini_prompt(snapshot)

        _send_status(task_id, 'Simulating failure scenarios with AI…', 40)
        analysis_data = _call_gemini(system_prompt, user_prompt)

        _send_status(task_id, 'Processing results…', 80)

        overall_risk = analysis_data.get('overall_risk_level', 'medium').lower()
        if overall_risk not in ('high', 'medium', 'low'):
            overall_risk = 'medium'

        analysis = PreMortemAnalysis.objects.create(
            board=board,
            created_by=user,
            overall_risk_level=overall_risk,
            analysis_json=analysis_data,
            board_snapshot=snapshot,
        )

        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=user,
            feature='premortem',
            request_type='pre_mortem_analysis',
            board_id=board.id,
            success=True,
            response_time_ms=response_time_ms,
        )

        result = {
            'success': True,
            'analysis': {
                'id': analysis.id,
                'overall_risk_level': analysis.overall_risk_level,
                'created_at': analysis.created_at.isoformat(),
                'created_by': user.get_full_name() or user.username,
                'failure_scenarios': analysis_data.get('failure_scenarios', []),
                'confidence_note': analysis_data.get('confidence_note', ''),
            },
        }

        _send_status(task_id, 'Analysis complete!', 100)
        _send_result(task_id, result)
        return result

    except Exception as exc:
        logger.error('Pre-Mortem streaming task failed for board %s: %s', board_id, exc)
        response_time_ms = int((time.time() - start_time) * 1000)
        try:
            from api.ai_usage_utils import track_ai_request
            from django.contrib.auth.models import User
            user = User.objects.get(id=user_id)
            track_ai_request(
                user=user,
                feature='premortem',
                request_type='pre_mortem_analysis',
                board_id=board_id,
                success=False,
                error_message=str(exc)[:500],
                response_time_ms=response_time_ms,
            )
        except Exception:
            pass
        _send_error(task_id, 'AI analysis failed. Please try again in a moment.')
        return {'success': False, 'error': str(exc)}


# ---------------------------------------------------------------------------
# 2. Board Analytics Summary
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name='kanban.ai_streaming.summarize_board_analytics',
    queue='ai_tasks',
    time_limit=120,
    soft_time_limit=90,
)
def summarize_board_analytics_task(self, board_id, user_id):
    """Summarize board analytics with AI, streaming progress updates."""
    task_id = self.request.id
    start_time = time.time()

    try:
        from kanban.models import Board, Task, Column
        from kanban.utils.ai_utils import summarize_board_analytics
        from api.ai_usage_utils import track_ai_request
        from django.contrib.auth.models import User
        from django.db.models import Count
        from django.utils import timezone
        from datetime import timedelta
        from ai_assistant.utils.rbac_utils import can_spectra_read_board

        user = User.objects.get(id=user_id)
        board = Board.objects.get(id=board_id)

        # Re-validate board access at execution time (TOCTOU protection)
        if not can_spectra_read_board(user, board):
            _send_error(task_id, 'You no longer have access to this board.')
            return {'error': 'Access denied'}

        _send_status(task_id, 'Gathering board metrics…', 10)

        all_tasks = Task.objects.filter(column__board=board, item_type='task')
        total_tasks = all_tasks.count()
        completed_count = all_tasks.filter(progress=100).count()
        productivity = (completed_count / total_tasks * 100) if total_tasks > 0 else 0

        today = timezone.now().date()
        overdue_count = Task.objects.filter(
            column__board=board, due_date__date__lt=today
        ).exclude(progress=100).count()
        upcoming_count = Task.objects.filter(
            column__board=board, due_date__date__gte=today,
            due_date__date__lte=today + timedelta(days=7)
        ).exclude(progress=100).count()

        _send_status(task_id, 'Analyzing velocity trends…', 30)

        # Lean Six Sigma metrics
        value_added_count = Task.objects.filter(
            column__board=board, labels__name='Value-Added', labels__category='lean'
        ).count()
        necessary_nva_count = Task.objects.filter(
            column__board=board, labels__name='Necessary NVA', labels__category='lean'
        ).count()
        waste_count = Task.objects.filter(
            column__board=board, labels__name='Waste/Eliminate', labels__category='lean'
        ).count()
        total_categorized = value_added_count + necessary_nva_count + waste_count
        value_added_percentage = (value_added_count / total_categorized * 100) if total_categorized > 0 else 0

        columns = Column.objects.filter(board=board)
        tasks_by_column = [{'name': c.name, 'count': Task.objects.filter(column=c, item_type='task').count()} for c in columns]

        priority_qs = all_tasks.values('priority').annotate(count=Count('id')).order_by('priority')
        tasks_by_priority = [
            {'priority': dict(Task.PRIORITY_CHOICES).get(i['priority'], i['priority']), 'count': i['count']}
            for i in priority_qs
        ]

        user_qs = all_tasks.values('assigned_to__username').annotate(count=Count('id')).order_by('-count')
        tasks_by_user = []
        for item in user_qs:
            username = item['assigned_to__username'] or 'Unassigned'
            completed_user = all_tasks.filter(assigned_to__username=item['assigned_to__username'], progress=100).count()
            rate = int(completed_user / item['count'] * 100) if item['count'] > 0 else 0
            tasks_by_user.append({'username': username, 'count': item['count'], 'completion_rate': rate})

        analytics_data = {
            'total_tasks': total_tasks,
            'completed_count': completed_count,
            'productivity': round(productivity, 1),
            'overdue_count': overdue_count,
            'upcoming_count': upcoming_count,
            'value_added_percentage': round(value_added_percentage, 1),
            'total_categorized': total_categorized,
            'tasks_by_lean_category': [
                {'name': 'Value-Added', 'count': value_added_count},
                {'name': 'Necessary NVA', 'count': necessary_nva_count},
                {'name': 'Waste/Eliminate', 'count': waste_count},
            ],
            'tasks_by_column': tasks_by_column,
            'tasks_by_priority': tasks_by_priority,
            'tasks_by_user': tasks_by_user,
        }

        _send_status(task_id, 'Generating AI insights…', 60)
        summary = summarize_board_analytics(analytics_data)

        if not summary:
            response_time_ms = int((time.time() - start_time) * 1000)
            track_ai_request(user=user, feature='board_analytics', request_type='summarize',
                             board_id=board.id, success=False,
                             error_message='Failed to generate analytics summary',
                             response_time_ms=response_time_ms)
            _send_error(task_id, 'Failed to generate AI summary. Please try again.')
            return {'error': 'Failed to generate analytics summary'}

        _send_status(task_id, 'Summary complete!', 100)

        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(user=user, feature='board_analytics', request_type='summarize',
                         board_id=board.id, success=True, response_time_ms=response_time_ms)

        result = {'summary': summary}
        _send_result(task_id, result)
        return result

    except Exception as exc:
        logger.error('Board analytics streaming task failed for board %s: %s', board_id, exc)
        _send_error(task_id, 'An unexpected error occurred while generating the summary.')
        return {'error': str(exc)}


# ---------------------------------------------------------------------------
# 3. Deadline Prediction
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name='kanban.ai_streaming.predict_deadline',
    queue='ai_tasks',
    time_limit=120,
    soft_time_limit=90,
)
def predict_deadline_task(self, task_data, team_context, board_id, user_id):
    """Predict realistic deadline with AI, streaming progress updates."""
    task_id = self.request.id
    start_time = time.time()

    try:
        from kanban.utils.ai_utils import predict_realistic_deadline
        from api.ai_usage_utils import track_ai_request
        from django.contrib.auth.models import User
        from kanban.models import Board, Task
        from ai_assistant.utils.rbac_utils import can_spectra_read_board

        user = User.objects.get(id=user_id)
        board = Board.objects.get(id=board_id)

        # Re-validate board access at execution time (TOCTOU protection)
        if not can_spectra_read_board(user, board):
            _send_error(task_id, 'You no longer have access to this board.')
            return {'error': 'Access denied'}

        _send_status(task_id, 'Analyzing assignee velocity…', 20)

        # Build team_context if it was not provided (async path passes {})
        if not team_context:
            from django.db.models import Avg
            assigned_to = task_data.get('assigned_to', 'Unassigned')

            completed_tasks = Task.objects.filter(column__board=board, progress=100)
            team_avg_completion = 5
            team_completed_count = 0
            assignee_avg_completion = 5
            assignee_velocity_hours = 8
            assignee_current_tasks = 0
            assignee_completed_count = 0

            if completed_tasks.exists():
                total_days = 0
                count = 0
                for t in completed_tasks:
                    if t.updated_at and t.created_at:
                        days = (t.updated_at - t.created_at).days
                        if days > 0:
                            total_days += days
                            count += 1
                if count > 0:
                    team_avg_completion = total_days / count
                    team_completed_count = count

            if assigned_to and assigned_to != 'Unassigned':
                try:
                    assignee_user = User.objects.get(username=assigned_to)
                    assignee_current_tasks = Task.objects.filter(
                        column__board=board, assigned_to=assignee_user
                    ).exclude(progress=100).count()

                    assignee_completed_tasks = Task.objects.filter(
                        column__board=board, assigned_to=assignee_user, progress=100
                    )
                    if assignee_completed_tasks.exists():
                        a_total = 0
                        a_count = 0
                        for t in assignee_completed_tasks:
                            if t.updated_at and t.created_at:
                                days = (t.updated_at - t.created_at).days
                                if days > 0:
                                    a_total += days
                                    a_count += 1
                        if a_count > 0:
                            assignee_avg_completion = a_total / a_count
                            assignee_completed_count = a_count
                            if assignee_avg_completion < team_avg_completion:
                                velocity_boost = team_avg_completion / assignee_avg_completion
                                assignee_velocity_hours = min(10, 8 * velocity_boost)
                            else:
                                velocity_reduction = assignee_avg_completion / team_avg_completion
                                assignee_velocity_hours = max(4, 8 / velocity_reduction)
                except User.DoesNotExist:
                    pass

            team_context = {
                'assignee_avg_completion_days': round(assignee_avg_completion, 1),
                'team_avg_completion_days': round(team_avg_completion, 1),
                'team_completed_tasks_count': team_completed_count,
                'assignee_current_tasks': assignee_current_tasks,
                'assignee_completed_tasks_count': assignee_completed_count,
                'assignee_velocity_hours_per_day': round(assignee_velocity_hours, 1),
                'similar_tasks_avg_days': round(team_avg_completion, 1),
                'upcoming_holidays': [],
            }

        _send_status(task_id, 'Calculating team metrics…', 40)
        _send_status(task_id, 'Generating AI prediction…', 60)

        prediction = predict_realistic_deadline(task_data, team_context)

        if not prediction:
            response_time_ms = int((time.time() - start_time) * 1000)
            track_ai_request(user=user, feature='deadline_prediction', request_type='predict',
                             board_id=board_id, success=False,
                             error_message='Failed to predict deadline',
                             response_time_ms=response_time_ms)
            _send_error(task_id, 'Failed to predict deadline.')
            return {'error': 'Failed to predict deadline'}

        _send_status(task_id, 'Prediction complete!', 100)

        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(user=user, feature='deadline_prediction', request_type='predict',
                         board_id=board_id, success=True, response_time_ms=response_time_ms)

        _send_result(task_id, prediction)
        return prediction

    except Exception as exc:
        logger.error('Deadline prediction streaming task failed: %s', exc)
        _send_error(task_id, 'An error occurred while predicting the deadline.')
        return {'error': str(exc)}


# ---------------------------------------------------------------------------
# 4. Workflow Optimization
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name='kanban.ai_streaming.analyze_workflow',
    queue='ai_tasks',
    time_limit=120,
    soft_time_limit=90,
)
def analyze_workflow_task(self, board_id, user_id):
    """Analyze workflow optimization with AI, streaming progress updates."""
    task_id = self.request.id
    start_time = time.time()

    try:
        from kanban.models import Board, Task, Column
        from kanban.utils.ai_utils import analyze_workflow_optimization
        from api.ai_usage_utils import track_ai_request
        from django.contrib.auth.models import User
        from django.db.models import Count
        from django.utils import timezone
        from ai_assistant.utils.rbac_utils import can_spectra_read_board

        user = User.objects.get(id=user_id)
        board = Board.objects.get(id=board_id)

        # Re-validate board access at execution time (TOCTOU protection)
        if not can_spectra_read_board(user, board):
            _send_error(task_id, 'You no longer have access to this board.')
            return {'error': 'Access denied'}

        _send_status(task_id, 'Collecting workflow data…', 10)

        all_tasks = Task.objects.filter(column__board=board)
        total_tasks = all_tasks.count()
        completed_tasks = all_tasks.filter(progress=100)

        avg_completion_time = 5
        if completed_tasks.exists():
            total_days = 0
            count = 0
            for task in completed_tasks:
                if task.updated_at and task.created_at:
                    days = (task.updated_at - task.created_at).days
                    if days > 0:
                        total_days += days
                        count += 1
            if count > 0:
                avg_completion_time = total_days / count

        _send_status(task_id, 'Analyzing bottlenecks…', 30)

        columns = Column.objects.filter(board=board)
        tasks_by_column = [{'name': c.name, 'count': Task.objects.filter(column=c).count()} for c in columns]

        priority_qs = all_tasks.values('priority').annotate(count=Count('id'))
        tasks_by_priority = [
            {'priority': dict(Task.PRIORITY_CHOICES).get(i['priority'], i['priority']), 'count': i['count']}
            for i in priority_qs
        ]

        user_qs = all_tasks.values(
            'assigned_to__username', 'assigned_to__first_name', 'assigned_to__last_name'
        ).annotate(count=Count('id'))
        tasks_by_user = []
        for item in user_qs:
            full_name = f"{item.get('assigned_to__first_name', '')} {item.get('assigned_to__last_name', '')}".strip()
            display = full_name or item['assigned_to__username'] or 'Unassigned'
            completed_u = completed_tasks.filter(assigned_to__username=item['assigned_to__username']).count()
            rate = int(completed_u / item['count'] * 100) if item['count'] > 0 else 0
            tasks_by_user.append({'username': display, 'count': item['count'], 'completion_rate': rate})

        total_progress = sum(t.progress or 0 for t in all_tasks)
        productivity = total_progress / total_tasks if total_tasks > 0 else 0
        overdue_count = all_tasks.filter(due_date__lt=timezone.now()).exclude(progress=100).count()

        board_analytics = {
            'total_tasks': total_tasks,
            'tasks_by_column': tasks_by_column,
            'tasks_by_priority': tasks_by_priority,
            'tasks_by_user': tasks_by_user,
            'avg_completion_time_days': avg_completion_time,
            'overdue_count': overdue_count,
            'productivity': productivity,
            'weekly_velocity': [],
        }

        _send_status(task_id, 'Generating optimization suggestions…', 60)
        optimization = analyze_workflow_optimization(board_analytics)

        if not optimization:
            response_time_ms = int((time.time() - start_time) * 1000)
            track_ai_request(user=user, feature='workflow_optimization', request_type='analyze',
                             board_id=board.id, success=False,
                             error_message='Failed to analyze workflow',
                             response_time_ms=response_time_ms)
            _send_error(task_id, 'Failed to analyze workflow.')
            return {'error': 'Failed to analyze workflow'}

        _send_status(task_id, 'Optimization analysis complete!', 100)

        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(user=user, feature='workflow_optimization', request_type='analyze',
                         board_id=board.id, success=True, response_time_ms=response_time_ms)

        _send_result(task_id, optimization)
        return optimization

    except Exception as exc:
        logger.error('Workflow optimization streaming task failed for board %s: %s', board_id, exc)
        _send_error(task_id, 'An error occurred while analyzing the workflow.')
        return {'error': str(exc)}


# ---------------------------------------------------------------------------
# 5. AI Chat (Send Message)
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name='kanban.ai_streaming.send_ai_message',
    queue='ai_tasks',
    time_limit=180,
    soft_time_limit=150,
)
def send_ai_message_task(self, message_text, session_id, user_id, board_id=None,
                          refresh_data=False, file_context=None):
    """Process AI assistant message with streamed progress updates."""
    task_id = self.request.id
    start_time = time.time()

    try:
        from django.contrib.auth.models import User
        from django.utils import timezone
        from kanban.models import Board
        from ai_assistant.models import (
            AIAssistantSession, AIAssistantMessage,
            AIAssistantAnalytics,
        )
        from ai_assistant.utils.chatbot_service import TaskFlowChatbotService
        from api.ai_usage_utils import track_ai_request, check_ai_quota
        from ai_assistant.utils.rbac_utils import can_spectra_read_board

        user = User.objects.get(id=user_id)
        session = AIAssistantSession.objects.get(id=session_id, user=user)

        board = None
        if board_id:
            board = Board.objects.get(id=board_id)
            # Re-validate board access at execution time (TOCTOU protection)
            if not can_spectra_read_board(user, board):
                _send_error(task_id, 'You no longer have access to this board.')
                return {'error': 'Access denied'}

        _send_status(task_id, 'Processing your question…', 20)

        is_demo_mode = False
        if hasattr(user, 'profile'):
            is_demo_mode = getattr(user.profile, 'is_viewing_demo', False)

        _send_status(task_id, 'Consulting AI…', 50)

        chatbot = TaskFlowChatbotService(
            user=user, board=board, session_id=session.id,
            is_demo_mode=is_demo_mode,
        )
        response = chatbot.get_response(
            message_text,
            use_cache=not refresh_data,
            file_context=file_context,
        )

        _send_status(task_id, 'Saving response…', 85)

        assistant_message = AIAssistantMessage.objects.create(
            session=session,
            role='assistant',
            content=response['response'],
            model=response.get('source', 'gemini'),
            tokens_used=response.get('tokens', 0),
            used_web_search=response.get('used_web_search', False),
            search_sources=response.get('search_sources', []),
            context_data=response.get('context', {}),
        )

        session.message_count = AIAssistantMessage.objects.filter(session=session).count()
        session.total_tokens_used += response.get('tokens', 0)
        session.save()

        # Track analytics/usage
        try:
            response_time_ms = int((time.time() - start_time) * 1000)
            track_ai_request(
                user=user, feature='ai_assistant', request_type='message',
                board_id=board_id, success=True,
                tokens_used=response.get('tokens', 0),
                response_time_ms=response_time_ms,
            )
        except Exception:
            pass

        _, _, remaining = check_ai_quota(user)

        result = {
            'status': 'success',
            'message_id': assistant_message.id,
            'response': response['response'],
            'source': response.get('source', 'gemini'),
            'used_web_search': response.get('used_web_search', False),
            'search_sources': response.get('search_sources', []),
            'ai_usage': {'remaining': remaining},
        }

        _send_status(task_id, 'Done!', 100)
        _send_result(task_id, result)
        return result

    except Exception as exc:
        logger.error('AI chat streaming task failed: %s', exc)
        _send_error(task_id, 'AI assistant encountered an error. Please try again.')
        return {'error': str(exc)}
