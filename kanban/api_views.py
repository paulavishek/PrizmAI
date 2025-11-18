"""
API Views for AI-powered features in TaskFlow

This module contains API view functions that handle requests from 
the front-end for AI-powered features.
"""
import json
import logging
from datetime import timedelta
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.utils import timezone

# Setup logging
logger = logging.getLogger(__name__)

from kanban.models import Task, Comment, Board, Column, TaskActivity
from accounts.models import UserProfile
from django.contrib.auth.models import User
from kanban.utils.ai_utils import (
    generate_task_description, 
    summarize_comments,
    suggest_lean_classification,
    summarize_board_analytics,
    suggest_task_priority,
    predict_realistic_deadline,
    recommend_board_columns,
    suggest_task_breakdown,
    analyze_workflow_optimization,
    summarize_task_details,
    analyze_critical_path,
    predict_task_completion,
    generate_project_timeline,
    calculate_task_risk_score,
    generate_risk_mitigation_suggestions,
    assess_task_dependencies_and_risks
)

@login_required
@require_http_methods(["POST"])
def generate_task_description_api(request):
    """
    API endpoint to generate a task description using AI
    """
    try:
        data = json.loads(request.body)
        title = data.get('title', '')
        
        if not title:
            return JsonResponse({'error': 'Title is required'}, status=400)
            
        # Call AI util function to generate description
        description = generate_task_description(title)
        
        if not description:
            return JsonResponse({'error': 'Failed to generate description'}, status=500)
            
        return JsonResponse({'description': description})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["GET"])
def summarize_comments_api(request, task_id):
    """
    API endpoint to summarize task comments using AI
    """
    try:
        # Get the task and verify user access
        task = get_object_or_404(Task, id=task_id)
        board = task.column.board
        
        # Check if user has access to this board/task
        if not (board.created_by == request.user or request.user in board.members.all()):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Format comments for AI
        comments_data = []
        for comment in task.comments.all().order_by('created_at'):
            comments_data.append({
                'user': comment.user.username,
                'content': comment.content,
                'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M')
            })
            
        if not comments_data:
            return JsonResponse({'summary': 'No comments to summarize.'})
            
        # Generate summary
        summary = summarize_comments(comments_data)
        
        if not summary:
            return JsonResponse({'error': 'Failed to generate summary'}, status=500)
        return JsonResponse({'summary': summary})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["POST"])
def suggest_lss_classification_api(request):
    """
    API endpoint to suggest Lean Six Sigma classification for a task
    """
    try:
        data = json.loads(request.body)
        title = data.get('title', '')
        description = data.get('description', '')
        
        if not title:
            return JsonResponse({'error': 'Title is required'}, status=400)
            
        # Call AI util function to suggest classification
        suggestion = suggest_lean_classification(title, description)
        
        if not suggestion:
            return JsonResponse({'error': 'Failed to suggest classification'}, status=500)
            
        return JsonResponse(suggestion)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["GET"])
def summarize_board_analytics_api(request, board_id):
    """
    API endpoint to summarize board analytics using AI
    """
    try:
        # Get the board and verify user access
        board = get_object_or_404(Board, id=board_id)
        
        # Check if user has access to this board
        if not (board.created_by == request.user or request.user in board.members.all()):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Gather analytics data (same as in board_analytics view)
        from django.db.models import Count, Q
        from django.utils import timezone
        from datetime import timedelta
        
        # Get all tasks for this board
        all_tasks = Task.objects.filter(column__board=board)
        total_tasks = all_tasks.count()
        
        # Completed tasks
        completed_count = Task.objects.filter(
            column__board=board, 
            column__name__icontains='done'
        ).count()
        
        # Calculate productivity
        total_progress_percentage = 0
        for task in all_tasks:
            if task.column.name.lower().find('done') >= 0:
                progress = 100
            else:
                progress = task.progress
            total_progress_percentage += progress
        
        productivity = 0
        if total_tasks > 0:
            productivity = (total_progress_percentage / (total_tasks * 100)) * 100
        
        # Overdue and upcoming tasks
        today = timezone.now().date()
        overdue_tasks = Task.objects.filter(
            column__board=board,
            due_date__date__lt=today
        ).exclude(column__name__icontains='done')
        
        upcoming_tasks = Task.objects.filter(
            column__board=board,
            due_date__date__gte=today,
            due_date__date__lte=today + timedelta(days=7)
        )
        
        # Lean Six Sigma metrics
        value_added_count = Task.objects.filter(
            column__board=board, 
            labels__name='Value-Added', 
            labels__category='lean'
        ).count()
        
        necessary_nva_count = Task.objects.filter(
            column__board=board, 
            labels__name='Necessary NVA', 
            labels__category='lean'
        ).count()
        
        waste_count = Task.objects.filter(
            column__board=board, 
            labels__name='Waste/Eliminate', 
            labels__category='lean'
        ).count()
        
        total_categorized = value_added_count + necessary_nva_count + waste_count
        value_added_percentage = 0
        if total_categorized > 0:
            value_added_percentage = (value_added_count / total_categorized) * 100
        
        # Task distribution by column
        columns = Column.objects.filter(board=board)
        tasks_by_column = []
        for column in columns:
            count = Task.objects.filter(column=column).count()
            tasks_by_column.append({'name': column.name, 'count': count})
        
        # Task distribution by priority
        priority_queryset = Task.objects.filter(column__board=board).values('priority').annotate(
            count=Count('id')
        ).order_by('priority')
        
        tasks_by_priority = []
        for item in priority_queryset:
            priority_name = dict(Task.PRIORITY_CHOICES).get(item['priority'], item['priority'])
            tasks_by_priority.append({'priority': priority_name, 'count': item['count']})
        
        # Task distribution by user
        user_queryset = Task.objects.filter(column__board=board).values(
            'assigned_to__username'
        ).annotate(count=Count('id')).order_by('-count')
        
        tasks_by_user = []
        for item in user_queryset:
            username = item['assigned_to__username'] or 'Unassigned'
            completed_user_tasks = Task.objects.filter(
                column__board=board,
                assigned_to__username=item['assigned_to__username'],
                column__name__icontains='done'
            ).count()
            
            user_completion_rate = 0
            if item['count'] > 0:
                user_completion_rate = (completed_user_tasks / item['count']) * 100
                
            tasks_by_user.append({
                'username': username,
                'count': item['count'],
                'completion_rate': int(user_completion_rate)
            })
        
        # Prepare analytics data for AI
        analytics_data = {
            'total_tasks': total_tasks,
            'completed_count': completed_count,
            'productivity': round(productivity, 1),
            'overdue_count': overdue_tasks.count(),
            'upcoming_count': upcoming_tasks.count(),
            'value_added_percentage': round(value_added_percentage, 1),
            'total_categorized': total_categorized,
            'tasks_by_lean_category': [
                {'name': 'Value-Added', 'count': value_added_count},
                {'name': 'Necessary NVA', 'count': necessary_nva_count},
                {'name': 'Waste/Eliminate', 'count': waste_count}
            ],
            'tasks_by_column': tasks_by_column,
            'tasks_by_priority': tasks_by_priority,
            'tasks_by_user': tasks_by_user
        }
        
        # Generate analytics summary
        summary = summarize_board_analytics(analytics_data)
        
        if not summary:
            return JsonResponse({'error': 'Failed to generate analytics summary'}, status=500)
            
        return JsonResponse({'summary': summary})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["POST"])
def suggest_task_priority_api(request):
    """
    API endpoint to suggest optimal priority for a task using AI
    """
    try:
        data = json.loads(request.body)
        task_id = data.get('task_id')
        title = data.get('title', '')
        description = data.get('description', '')
        due_date = data.get('due_date', '')
        
        if not title:
            return JsonResponse({'error': 'Title is required'}, status=400)
        
        # If task_id is provided, get board context
        board_context = {}
        if task_id:
            task = get_object_or_404(Task, id=task_id)
            board = task.column.board
            
            # Check access
            if not (board.created_by == request.user or request.user in board.members.all()):
                return JsonResponse({'error': 'Access denied'}, status=403)
        else:
            # For new tasks, try to get board from request
            board_id = data.get('board_id')
            if board_id:
                board = get_object_or_404(Board, id=board_id)
                if not (board.created_by == request.user or request.user in board.members.all()):
                    return JsonResponse({'error': 'Access denied'}, status=403)
            else:
                return JsonResponse({'error': 'Board ID or Task ID is required'}, status=400)
        
        # Gather board context for priority suggestion
        from django.db.models import Count
        all_tasks = Task.objects.filter(column__board=board)
        
        board_context = {
            'total_tasks': all_tasks.count(),
            'high_priority_count': all_tasks.filter(priority='high').count(),
            'urgent_count': all_tasks.filter(priority='urgent').count(),
            'overdue_count': all_tasks.filter(due_date__lt=timezone.now()).exclude(column__name__icontains='done').count(),
            'upcoming_deadlines': all_tasks.filter(
                due_date__gte=timezone.now(),
                due_date__lte=timezone.now() + timedelta(days=7)
            ).count()
        }
        
        task_data = {
            'title': title,
            'description': description,
            'due_date': due_date,
            'current_priority': data.get('current_priority', 'medium')
        }
        
        # Call AI function
        suggestion = suggest_task_priority(task_data, board_context)
        
        if not suggestion:
            return JsonResponse({'error': 'Failed to suggest priority'}, status=500)
            
        return JsonResponse(suggestion)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["POST"])
def predict_deadline_api(request):
    """
    API endpoint to predict realistic deadline for a task using AI
    """
    try:
        data = json.loads(request.body)
        task_id = data.get('task_id')
        title = data.get('title', '')
        description = data.get('description', '')
        priority = data.get('priority', 'medium')
        assigned_to = data.get('assigned_to', 'Unassigned')
        
        if not title:
            return JsonResponse({'error': 'Title is required'}, status=400)
        
        # Get board context for deadline prediction
        board_id = data.get('board_id')
        if task_id:
            task = get_object_or_404(Task, id=task_id)
            board = task.column.board
        elif board_id:
            board = get_object_or_404(Board, id=board_id)
        else:
            return JsonResponse({'error': 'Board ID or Task ID is required'}, status=400)
        
        # Check access
        if not (board.created_by == request.user or request.user in board.members.all()):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Gather team context for deadline prediction
        from django.db.models import Avg
        from django.utils import timezone
        
        # Calculate average completion times (simplified calculation)
        completed_tasks = Task.objects.filter(
            column__board=board, 
            column__name__icontains='done'
        )
        
        team_avg_completion = 5  # Default fallback
        assignee_avg_completion = 5  # Default fallback
        
        if completed_tasks.exists():
            # Simple calculation based on created_at to completion
            total_days = 0
            count = 0
            for task in completed_tasks:
                if task.updated_at and task.created_at:
                    days_to_complete = (task.updated_at - task.created_at).days
                    if days_to_complete > 0:  # Avoid zero or negative days
                        total_days += days_to_complete
                        count += 1
            
            if count > 0:
                team_avg_completion = total_days / count
        
        # Get assignee's current workload
        assignee_current_tasks = 0
        if assigned_to and assigned_to != 'Unassigned':
            from django.contrib.auth.models import User
            try:
                assignee_user = User.objects.get(username=assigned_to)
                assignee_current_tasks = Task.objects.filter(
                    column__board=board,
                    assigned_to=assignee_user
                ).exclude(column__name__icontains='done').count()
            except User.DoesNotExist:
                pass
        
        team_context = {
            'assignee_avg_completion_days': assignee_avg_completion,
            'team_avg_completion_days': team_avg_completion,
            'assignee_current_tasks': assignee_current_tasks,
            'similar_tasks_avg_days': team_avg_completion,  # Simplified
            'upcoming_holidays': []  # Could be enhanced to include actual holidays
        }
        
        task_data = {
            'title': title,
            'description': description,
            'priority': priority,
            'assigned_to': assigned_to
        }
        
        # Call AI function
        prediction = predict_realistic_deadline(task_data, team_context)
        
        if not prediction:
            return JsonResponse({'error': 'Failed to predict deadline'}, status=500)
            
        return JsonResponse(prediction)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["POST"])
def recommend_columns_api(request):
    """
    API endpoint to recommend optimal column structure for a board using AI
    """
    try:
        data = json.loads(request.body)
        board_id = data.get('board_id')
        
        if board_id:
            # Existing board - get current structure
            board = get_object_or_404(Board, id=board_id)
            
            # Check access
            if not (board.created_by == request.user or request.user in board.members.all()):
                return JsonResponse({'error': 'Access denied'}, status=403)
            
            existing_columns = [col.name for col in board.columns.all()]
            board_name = board.name
            board_description = board.description
            team_size = board.members.count() + 1  # +1 for creator
        else:
            # New board recommendations
            board_name = data.get('name', '')
            board_description = data.get('description', '')
            team_size = data.get('team_size', 1)
            existing_columns = []
        
        if not board_name:
            return JsonResponse({'error': 'Board name is required'}, status=400)
        
        board_data = {
            'name': board_name,
            'description': board_description,
            'team_size': team_size,
            'project_type': data.get('project_type', 'general'),
            'organization_type': data.get('organization_type', 'general'),
            'existing_columns': existing_columns
        }
        
        # Call AI function
        recommendation = recommend_board_columns(board_data)
        
        if not recommendation:
            return JsonResponse({'error': 'Failed to recommend columns'}, status=500)
            
        return JsonResponse(recommendation)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["POST"])
def suggest_task_breakdown_api(request):
    """
    API endpoint to suggest automated breakdown of complex tasks using AI
    """
    try:
        data = json.loads(request.body)
        task_id = data.get('task_id')
        title = data.get('title', '')
        description = data.get('description', '')
        
        if not title:
            return JsonResponse({'error': 'Title is required'}, status=400)
        
        # If task_id provided, verify access
        if task_id:
            task = get_object_or_404(Task, id=task_id)
            board = task.column.board
            
            # Check access
            if not (board.created_by == request.user or request.user in board.members.all()):
                return JsonResponse({'error': 'Access denied'}, status=403)
        
        task_data = {
            'title': title,
            'description': description,
            'priority': data.get('priority', 'medium'),
            'due_date': data.get('due_date', ''),
            'estimated_effort': data.get('estimated_effort', '')
        }
        
        # Call AI function
        breakdown = suggest_task_breakdown(task_data)
        
        if not breakdown:
            return JsonResponse({'error': 'Failed to suggest task breakdown'}, status=500)
            
        return JsonResponse(breakdown)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["POST"])
def analyze_workflow_optimization_api(request):
    """
    API endpoint to analyze workflow and suggest optimizations using AI
    """
    try:
        data = json.loads(request.body)
        board_id = data.get('board_id')
        
        if not board_id:
            return JsonResponse({'error': 'Board ID is required'}, status=400)
        
        board = get_object_or_404(Board, id=board_id)
        
        # Check access
        if not (board.created_by == request.user or request.user in board.members.all()):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Gather comprehensive board analytics (similar to existing analytics)
        from django.db.models import Count, Avg
        from django.utils import timezone
        from datetime import timedelta
        
        all_tasks = Task.objects.filter(column__board=board)
        total_tasks = all_tasks.count()
        
        # Calculate average completion time
        completed_tasks = all_tasks.filter(column__name__icontains='done')
        avg_completion_time = 5  # Default
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
        
        # Task distribution by column
        columns = Column.objects.filter(board=board)
        tasks_by_column = []
        for column in columns:
            count = Task.objects.filter(column=column).count()
            tasks_by_column.append({'name': column.name, 'count': count})
        
        # Task distribution by priority
        priority_queryset = all_tasks.values('priority').annotate(count=Count('id'))
        tasks_by_priority = []
        for item in priority_queryset:
            priority_name = dict(Task.PRIORITY_CHOICES).get(item['priority'], item['priority'])
            tasks_by_priority.append({'priority': priority_name, 'count': item['count']})
        
        # Task distribution by user
        user_queryset = all_tasks.values('assigned_to__username').annotate(count=Count('id'))
        tasks_by_user = []
        for item in user_queryset:
            username = item['assigned_to__username'] or 'Unassigned'
            completed_user_tasks = completed_tasks.filter(
                assigned_to__username=item['assigned_to__username']
            ).count()
            
            completion_rate = 0
            if item['count'] > 0:
                completion_rate = (completed_user_tasks / item['count']) * 100
                
            tasks_by_user.append({
                'username': username,
                'count': item['count'],
                'completion_rate': int(completion_rate)
            })
        
        # Calculate productivity
        total_progress = sum(task.progress for task in all_tasks)
        productivity = 0
        if total_tasks > 0:
            productivity = total_progress / total_tasks
        
        # Overdue count
        overdue_count = all_tasks.filter(
            due_date__lt=timezone.now()
        ).exclude(column__name__icontains='done').count()
        
        board_analytics = {
            'total_tasks': total_tasks,
            'tasks_by_column': tasks_by_column,
            'tasks_by_priority': tasks_by_priority,
            'tasks_by_user': tasks_by_user,
            'avg_completion_time_days': avg_completion_time,
            'overdue_count': overdue_count,
            'productivity': productivity,
            'weekly_velocity': []  # Could be enhanced with historical data
        }
        
        # Call AI function
        optimization = analyze_workflow_optimization(board_analytics)
        
        if not optimization:
            return JsonResponse({'error': 'Failed to analyze workflow'}, status=500)
            
        return JsonResponse(optimization)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["POST"])
def create_subtasks_api(request):
    """
    API endpoint to create multiple tasks from AI-generated subtask breakdown
    """
    try:
        data = json.loads(request.body)
        board_id = data.get('board_id')
        column_id = data.get('column_id')
        subtasks = data.get('subtasks', [])
        original_task_title = data.get('original_task_title', '')
        if not board_id or not subtasks:
            return JsonResponse({'error': 'Missing required fields (board_id, subtasks)'}, status=400)
              # Verify user has access to the board
        board = get_object_or_404(Board, id=board_id)
        if not (request.user in board.members.all() or request.user == board.created_by):
            return JsonResponse({'error': 'Access denied'}, status=403)
            
        # Get column - if not specified, use first column
        if column_id:
            column = get_object_or_404(Column, id=column_id, board=board)
        else:
            # Default to first column (usually "To Do")
            column = Column.objects.filter(board=board).order_by('position').first()
            if not column:
                return JsonResponse({'error': 'No columns found in board'}, status=400)
        
        created_tasks = []
        errors = []
        
        for i, subtask_data in enumerate(subtasks):
            try:
                # Extract subtask information
                title = subtask_data.get('title', '').strip()
                description = subtask_data.get('description', '').strip()
                estimated_effort = subtask_data.get('estimated_effort', '')
                priority = subtask_data.get('priority', 'medium').lower()
                
                # Validate data
                if not title:
                    errors.append(f"Subtask {i+1}: Title is required")
                    continue
                
                # Ensure priority is valid
                valid_priorities = ['low', 'medium', 'high', 'urgent']
                if priority not in valid_priorities:
                    priority = 'medium'
                
                # Parse estimated effort to get due date (if provided)
                due_date = None
                if estimated_effort and 'day' in estimated_effort.lower():
                    try:
                        # Extract number of days from strings like "2 days", "1 day"
                        import re
                        days_match = re.search(r'(\d+)', estimated_effort)
                        if days_match:
                            days = int(days_match.group(1))
                            due_date = timezone.now() + timedelta(days=days)
                    except:
                        pass  # If parsing fails, just leave due_date as None
                
                # Enhance description with effort information
                if estimated_effort:
                    if description:
                        description += f"\n\n**Estimated Effort:** {estimated_effort}"
                    else:
                        description = f"**Estimated Effort:** {estimated_effort}"
                
                # Add reference to original task
                if original_task_title:
                    description += f"\n\n*Subtask of: {original_task_title}*"
                
                # Create the task
                task = Task.objects.create(
                    title=title,
                    description=description,
                    column=column,
                    priority=priority,
                    due_date=due_date,
                    created_by=request.user,
                    position=Task.objects.filter(column=column).count()  # Add to end
                )
                
                created_tasks.append({
                    'id': task.id,
                    'title': task.title,
                    'priority': task.priority,
                    'due_date': task.due_date.isoformat() if task.due_date else None
                })
                
            except Exception as e:
                errors.append(f"Subtask {i+1}: {str(e)}")
          # Prepare response
        response_data = {
            'success': True,
            'created_count': len(created_tasks),
            'total_subtasks': len(subtasks),
            'created_tasks': created_tasks
        }
        
        if errors:
            response_data['errors'] = errors
            response_data['partial_success'] = True
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def calculate_task_risk_api(request):
    """
    API endpoint to calculate AI-powered risk score for a task
    """
    try:
        data = json.loads(request.body)
        task_id = data.get('task_id')
        title = data.get('title', '')
        description = data.get('description', '')
        priority = data.get('priority', 'medium')
        board_id = data.get('board_id')
        
        if not title:
            return JsonResponse({'error': 'Title is required'}, status=400)
        
        # If task_id provided, verify access
        if task_id:
            task = get_object_or_404(Task, id=task_id)
            board = task.column.board
        elif board_id:
            board = get_object_or_404(Board, id=board_id)
        else:
            return JsonResponse({'error': 'Board ID or Task ID is required'}, status=400)
        
        # Check access
        if not (board.created_by == request.user or request.user in board.members.all()):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Get board context
        board_context = f"Board: {board.name}. Description: {board.description or 'N/A'}"
        
        # Calculate risk score
        risk_analysis = calculate_task_risk_score(title, description, priority, board_context)
        
        if not risk_analysis:
            return JsonResponse({'error': 'Failed to calculate risk score'}, status=500)
        
        # If task_id provided, save the analysis to the task
        if task_id:
            task.risk_likelihood = risk_analysis.get('likelihood', {}).get('score')
            task.risk_impact = risk_analysis.get('impact', {}).get('score')
            task.risk_score = risk_analysis.get('risk_assessment', {}).get('risk_score')
            task.risk_level = risk_analysis.get('risk_assessment', {}).get('risk_level', 'low').lower()
            task.risk_indicators = risk_analysis.get('risk_indicators', [])
            task.mitigation_suggestions = risk_analysis.get('mitigation_suggestions', [])
            task.risk_analysis = risk_analysis
            task.last_risk_assessment = timezone.now()
            task.save()
        
        return JsonResponse({
            'success': True,
            'risk_analysis': risk_analysis,
            'saved': bool(task_id)
        })
    except Exception as e:
        logger.error(f"Error in calculate_task_risk_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def get_mitigation_suggestions_api(request):
    """
    API endpoint to get AI-generated mitigation suggestions for a high-risk task
    """
    try:
        data = json.loads(request.body)
        task_id = data.get('task_id')
        title = data.get('title', '')
        description = data.get('description', '')
        risk_likelihood = data.get('risk_likelihood', 2)
        risk_impact = data.get('risk_impact', 2)
        risk_indicators = data.get('risk_indicators', [])
        board_id = data.get('board_id')
        
        if not title:
            return JsonResponse({'error': 'Title is required'}, status=400)
        
        # If task_id provided, verify access
        if task_id:
            task = get_object_or_404(Task, id=task_id)
            board = task.column.board
        elif board_id:
            board = get_object_or_404(Board, id=board_id)
        else:
            return JsonResponse({'error': 'Board ID or Task ID is required'}, status=400)
        
        # Check access
        if not (board.created_by == request.user or request.user in board.members.all()):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Get mitigation suggestions
        mitigation_suggestions = generate_risk_mitigation_suggestions(
            title, 
            description,
            risk_likelihood,
            risk_impact,
            risk_indicators
        )
        
        if not mitigation_suggestions:
            return JsonResponse({'error': 'Failed to generate mitigation suggestions'}, status=500)
        
        # If task_id provided, update the task
        if task_id:
            task.mitigation_suggestions = mitigation_suggestions
            task.save()
        
        return JsonResponse({
            'success': True,
            'mitigation_suggestions': mitigation_suggestions,
            'count': len(mitigation_suggestions)
        })
    except Exception as e:
        logger.error(f"Error in get_mitigation_suggestions_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def assess_task_dependencies_api(request):
    """
    API endpoint to assess task dependencies and cascading risks
    """
    try:
        data = json.loads(request.body)
        task_id = data.get('task_id')
        board_id = data.get('board_id')
        
        if task_id:
            task = get_object_or_404(Task, id=task_id)
            board = task.column.board
            task_title = task.title
        elif board_id:
            board = get_object_or_404(Board, id=board_id)
            task_title = data.get('task_title', '')
        else:
            return JsonResponse({'error': 'Board ID or Task ID is required'}, status=400)
        
        # Check access
        if not (board.created_by == request.user or request.user in board.members.all()):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Get related tasks
        all_tasks = Task.objects.filter(column__board=board).values(
            'id', 'title', 'priority', 'column__name'
        )[:20]  # Limit to avoid token overflow
        
        tasks_data = [
            {
                'id': t['id'],
                'title': t['title'],
                'priority': t['priority'],
                'status': t['column__name']
            }
            for t in all_tasks
        ]
        
        # Assess dependencies
        dependency_analysis = assess_task_dependencies_and_risks(task_title, tasks_data)
        
        if not dependency_analysis:
            return JsonResponse({'error': 'Failed to assess task dependencies'}, status=500)
        
        return JsonResponse({
            'success': True,
            'dependency_analysis': dependency_analysis
        })
    except Exception as e:
        logger.error(f"Error in assess_task_dependencies_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

# Meeting Transcript Extraction API Endpoints










@login_required
@require_http_methods(["POST"])
def update_user_skills_api(request):
    """
    API endpoint to update user skills and capacity information
    """
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        
        # If no user_id provided, update current user
        if not user_id:
            target_user = request.user
        else:
            target_user = get_object_or_404(User, id=user_id)
            
            # Check if current user can update this profile
            if target_user != request.user:
                # Only organization admins can update other users' profiles
                if not hasattr(request.user, 'profile') or not request.user.profile.is_admin:
                    return JsonResponse({'error': 'Permission denied'}, status=403)
        
        # Get or create user profile
        profile, created = UserProfile.objects.get_or_create(
            user=target_user,
            defaults={'organization': request.user.profile.organization}
        )
        
        # Update skills
        if 'skills' in data:
            skills = data['skills']
            if isinstance(skills, list):
                profile.skills = skills
        
        # Update capacity
        if 'weekly_capacity_hours' in data:
            capacity = data['weekly_capacity_hours']
            if isinstance(capacity, int) and capacity > 0:
                profile.weekly_capacity_hours = capacity
        
        # Update availability schedule
        if 'availability_schedule' in data:
            schedule = data['availability_schedule']
            if isinstance(schedule, dict):
                profile.availability_schedule = schedule
        
        # Update preferred task types
        if 'preferred_task_types' in data:
            task_types = data['preferred_task_types']
            if isinstance(task_types, list):
                profile.preferred_task_types = task_types
        
        profile.save()
        
        return JsonResponse({
            'success': True,
            'message': 'User profile updated successfully',
            'utilization_percentage': profile.utilization_percentage,
            'available_hours': profile.available_hours
        })
        
    except Exception as e:
        logger.error(f"Error updating user skills API: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["POST"])

# ============================================================================
# Task Dependency Management API Endpoints
# ============================================================================

@login_required
@require_http_methods(["GET"])
def get_task_dependencies_api(request, task_id):
    """
    Get all dependencies for a task (parents, children, related tasks)
    """
    try:
        task = get_object_or_404(Task, id=task_id)
        
        # Verify user has access to this task's board
        if not request.user in task.column.board.members.all() and task.column.board.created_by != request.user:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        dependencies = {
            'task_id': task.id,
            'task_title': task.title,
            'parent_task': None,
            'subtasks': [],
            'related_tasks': [],
            'dependency_chain': task.dependency_chain,
            'dependency_level': task.get_dependency_level()
        }
        
        # Add parent task
        if task.parent_task:
            dependencies['parent_task'] = {
                'id': task.parent_task.id,
                'title': task.parent_task.title,
                'status': task.parent_task.column.name if task.parent_task.column else 'Unknown'
            }
        
        # Add subtasks
        for subtask in task.subtasks.all():
            dependencies['subtasks'].append({
                'id': subtask.id,
                'title': subtask.title,
                'status': subtask.column.name if subtask.column else 'Unknown',
                'assigned_to': subtask.assigned_to.username if subtask.assigned_to else 'Unassigned'
            })
        
        # Add related tasks
        for related in task.related_tasks.all():
            dependencies['related_tasks'].append({
                'id': related.id,
                'title': related.title,
                'status': related.column.name if related.column else 'Unknown'
            })
        
        return JsonResponse({
            'success': True,
            'dependencies': dependencies
        })
        
    except Task.DoesNotExist:
        return JsonResponse({'error': 'Task not found'}, status=404)
    except Exception as e:
        logger.error(f"Error in get_task_dependencies_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def set_parent_task_api(request, task_id):
    """
    Set a parent task for the given task
    """
    try:
        task = get_object_or_404(Task, id=task_id)
        
        # Verify user has access
        if not request.user in task.column.board.members.all() and task.column.board.created_by != request.user:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        data = json.loads(request.body)
        parent_id = data.get('parent_task_id')
        
        if parent_id is None:
            # Remove parent
            task.parent_task = None
        else:
            parent_task = get_object_or_404(Task, id=parent_id)
            
            # Check for circular dependency
            if task.has_circular_dependency(parent_task):
                return JsonResponse({
                    'error': 'This would create a circular dependency',
                    'success': False
                }, status=400)
            
            task.parent_task = parent_task
        
        task.update_dependency_chain()
        
        return JsonResponse({
            'success': True,
            'message': f'Parent task {'set to' if parent_id else 'removed from'} {task.title}',
            'dependency_chain': task.dependency_chain
        })
        
    except Task.DoesNotExist:
        return JsonResponse({'error': 'Task not found'}, status=404)
    except Exception as e:
        logger.error(f"Error in set_parent_task_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def add_related_task_api(request, task_id):
    """
    Add a related task (non-hierarchical relationship)
    """
    try:
        task = get_object_or_404(Task, id=task_id)
        
        # Verify user has access
        if not request.user in task.column.board.members.all() and task.column.board.created_by != request.user:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        data = json.loads(request.body)
        related_id = data.get('related_task_id')
        
        if not related_id:
            return JsonResponse({'error': 'No related task ID provided'}, status=400)
        
        related_task = get_object_or_404(Task, id=related_id)
        
        if task.id == related_task.id:
            return JsonResponse({'error': 'Cannot relate a task to itself'}, status=400)
        
        task.related_tasks.add(related_task)
        
        return JsonResponse({
            'success': True,
            'message': f'Related task added to {task.title}'
        })
        
    except Task.DoesNotExist:
        return JsonResponse({'error': 'Task not found'}, status=404)
    except Exception as e:
        logger.error(f"Error in add_related_task_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def analyze_task_dependencies_api(request, task_id):
    """
    Analyze a task and suggest dependencies
    """
    try:
        from kanban.utils.dependency_suggestions import analyze_and_suggest_dependencies
        
        task = get_object_or_404(Task, id=task_id)
        
        # Verify user has access
        if not request.user in task.column.board.members.all() and task.column.board.created_by != request.user:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        data = json.loads(request.body)
        auto_link = data.get('auto_link', False)
        
        board = task.column.board if task.column else None
        result = analyze_and_suggest_dependencies(task, board, auto_link)
        
        return JsonResponse({
            'success': True,
            'analysis': result,
            'message': result.get('analysis', 'Analysis completed')
        })
        
    except Task.DoesNotExist:
        return JsonResponse({'error': 'Task not found'}, status=404)
    except Exception as e:
        logger.error(f"Error in analyze_task_dependencies_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_dependency_tree_api(request, task_id):
    """
    Get a hierarchical dependency tree for visualization
    """
    try:
        from kanban.utils.dependency_suggestions import DependencyGraphGenerator
        
        task = get_object_or_404(Task, id=task_id)
        
        # Verify user has access
        if not request.user in task.column.board.members.all() and task.column.board.created_by != request.user:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        include_related = request.GET.get('include_related', 'false').lower() == 'true'
        tree = DependencyGraphGenerator.generate_dependency_tree(task, include_subtasks=True, include_related=include_related)
        
        return JsonResponse({
            'success': True,
            'tree': tree
        })
        
    except Task.DoesNotExist:
        return JsonResponse({'error': 'Task not found'}, status=404)
    except Exception as e:
        logger.error(f"Error in get_dependency_tree_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_board_dependency_graph_api(request, board_id):
    """
    Get a full dependency graph for a board
    """
    try:
        from kanban.utils.dependency_suggestions import DependencyGraphGenerator
        
        board = get_object_or_404(Board, id=board_id)
        
        # Verify user has access
        if not request.user in board.members.all() and board.created_by != request.user:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        root_task_id = request.GET.get('root_task_id')
        if root_task_id:
            root_task_id = int(root_task_id)
        
        graph = DependencyGraphGenerator.generate_dependency_graph(board, root_task_id)
        
        return JsonResponse({
            'success': True,
            'graph': graph
        })
        
    except Board.DoesNotExist:
        return JsonResponse({'error': 'Board not found'}, status=404)
    except Exception as e:
        logger.error(f"Error in get_board_dependency_graph_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def update_task_dates_api(request):
    """
    Update task start_date and due_date from Gantt chart
    """
    try:
        data = json.loads(request.body)
        task_id = data.get('task_id')
        start_date = data.get('start_date')
        due_date = data.get('due_date')
        
        if not task_id:
            return JsonResponse({'error': 'Task ID is required'}, status=400)
        
        task = get_object_or_404(Task, id=task_id)
        
        # Verify user has access
        board = task.column.board
        if not (request.user in board.members.all() or board.created_by == request.user):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Update dates
        if start_date:
            from datetime import datetime
            task.start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        if due_date:
            from datetime import datetime
            # Keep the time part if due_date is datetime, otherwise set to end of day
            if task.due_date:
                # Preserve time component
                new_date = datetime.strptime(due_date, '%Y-%m-%d').date()
                task.due_date = datetime.combine(new_date, task.due_date.time())
            else:
                # Set to end of day
                task.due_date = datetime.strptime(due_date + ' 23:59:59', '%Y-%m-%d %H:%M:%S')
        
        task.save()
        
        # Log activity
        TaskActivity.objects.create(
            task=task,
            user=request.user,
            activity_type='updated',
            description=f'Updated task dates: {start_date} to {due_date}'
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Task dates updated successfully'
        })
        
    except Task.DoesNotExist:
        return JsonResponse({'error': 'Task not found'}, status=404)
    except Exception as e:
        logger.error(f"Error in update_task_dates_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def summarize_task_details_api(request, task_id):
    """
    API endpoint to generate a comprehensive AI-powered summary of a task's details.
    
    This analyzes all aspects of the task including:
    - Risk management and mitigation strategies
    - Stakeholder involvement and feedback
    - Resource requirements and skill matching
    - Task dependencies and hierarchy
    - Complexity and effort estimates
    - Lean Six Sigma classification
    """
    try:
        # Get the task and verify user access
        task = get_object_or_404(Task, id=task_id)
        board = task.column.board
        
        # Check if user has access to this board
        if not (board.created_by == request.user or request.user in board.members.all()):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Import StakeholderTaskInvolvement here to avoid circular import
        from kanban.stakeholder_models import StakeholderTaskInvolvement
        
        # Gather comprehensive task data
        task_data = {
            'title': task.title,
            'description': task.description or 'No description provided',
            'status': task.column.name,
            'priority': task.get_priority_display(),
            'progress': task.progress if task.progress is not None else 0,
            'due_date': task.due_date.strftime('%B %d, %Y at %H:%M') if task.due_date else 'No due date set',
            'assigned_to': task.assigned_to.username if task.assigned_to else 'Unassigned',
            'created_by': task.created_by.username,
            'created_at': task.created_at.strftime('%B %d, %Y'),
            
            # Risk management
            'risk_level': task.risk_level,
            'risk_score': task.risk_score,
            'risk_likelihood': task.risk_likelihood,
            'risk_impact': task.risk_impact,
            'risk_indicators': task.risk_indicators if task.risk_indicators else [],
            'mitigation_suggestions': task.mitigation_suggestions if task.mitigation_suggestions else [],
            
            # Stakeholders
            'stakeholders': [
                {
                    'name': involvement.stakeholder.name,
                    'involvement_type': involvement.get_involvement_type_display(),
                    'engagement_status': involvement.get_engagement_status_display(),
                    'satisfaction_rating': involvement.satisfaction_rating,
                    'feedback': involvement.feedback
                }
                for involvement in StakeholderTaskInvolvement.objects.filter(task=task).select_related('stakeholder')
            ],
            
            # Resource management
            'required_skills': task.required_skills if task.required_skills else [],
            'skill_match_score': task.skill_match_score,
            'workload_impact': task.get_workload_impact_display() if task.workload_impact else None,
            'collaboration_required': task.collaboration_required,
            'complexity_score': task.complexity_score,
            
            # Dependencies and hierarchy
            'parent_task': task.parent_task.title if task.parent_task else None,
            'subtasks': [subtask.title for subtask in task.subtasks.all()],
            'dependencies': [
                f"{dep.title} ({dep.progress}% complete, Due: {dep.due_date.strftime('%Y-%m-%d') if dep.due_date else 'No date'})"
                for dep in task.dependencies.all()
            ],
            'dependent_tasks': [
                f"{blocked.title} (Waiting on this task)"
                for blocked in task.dependent_tasks.all()
            ],
            'related_tasks': [rel.title for rel in task.related_tasks.all()],
            
            # Labels
            'labels': [
                {
                    'name': label.name,
                    'category': label.category
                }
                for label in task.labels.all()
            ],
            
            # Additional context
            'comments_count': task.comments.count()
        }
        
        # Generate comprehensive summary
        summary = summarize_task_details(task_data)
        
        if not summary:
            return JsonResponse({'error': 'Failed to generate task summary'}, status=500)
            
        return JsonResponse({'summary': summary})
    except Exception as e:
        logger.error(f"Error in summarize_task_details_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET", "POST"])
def get_task_prediction_api(request, task_id):
    """
    API endpoint to get or update task completion prediction
    GET: Returns current prediction
    POST: Triggers new prediction calculation
    """
    try:
        task = get_object_or_404(Task, pk=task_id)
        
        # Check user has access to this task's board
        if request.user not in task.column.board.members.all():
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # For POST, force recalculation
        if request.method == 'POST':
            from kanban.utils.task_prediction import update_task_prediction
            prediction = update_task_prediction(task)
            
            if not prediction:
                return JsonResponse({
                    'message': 'Task is completed or cannot be predicted',
                    'has_prediction': False
                })
            
            # Format similar_tasks for JSON serialization
            similar_tasks_formatted = []
            if prediction.get('similar_tasks'):
                for task_data in prediction['similar_tasks']:
                    # completed_at is already a string (isoformat) from task_prediction.py
                    formatted_task = {
                        'id': task_data['id'],
                        'title': task_data['title'],
                        'actual_duration_days': task_data['actual_duration_days'],
                        'complexity_score': task_data['complexity_score'],
                        'priority': task_data['priority'],
                        'completed_at': task_data.get('completed_at')  # Already a string
                    }
                    similar_tasks_formatted.append(formatted_task)
            
            return JsonResponse({
                'success': True,
                'prediction': {
                    'predicted_date': prediction['predicted_date'].isoformat(),
                    'predicted_date_formatted': prediction['predicted_date'].strftime('%B %d, %Y'),
                    'confidence': prediction['confidence'],
                    'confidence_percentage': int(prediction['confidence'] * 100),
                    'confidence_interval_days': prediction['confidence_interval_days'],
                    'based_on_tasks': prediction['based_on_tasks'],
                    'similar_tasks': similar_tasks_formatted,
                    'early_date': prediction['early_date'].isoformat(),
                    'early_date_formatted': prediction['early_date'].strftime('%b %d'),
                    'late_date': prediction['late_date'].isoformat(),
                    'late_date_formatted': prediction['late_date'].strftime('%b %d'),
                    'prediction_method': prediction['prediction_method'],
                    'factors': prediction['factors'],
                    'is_likely_late': prediction['predicted_date'] > task.due_date if task.due_date else False
                },
                'has_prediction': True
            })
        
        # For GET, return existing prediction
        if task.predicted_completion_date and task.prediction_confidence:
            is_likely_late = False
            if task.due_date:
                is_likely_late = task.predicted_completion_date > task.due_date
            
            return JsonResponse({
                'has_prediction': True,
                'prediction': {
                    'predicted_date': task.predicted_completion_date.isoformat(),
                    'predicted_date_formatted': task.predicted_completion_date.strftime('%B %d, %Y'),
                    'confidence': task.prediction_confidence,
                    'confidence_percentage': int(task.prediction_confidence * 100),
                    'confidence_interval_days': task.prediction_metadata.get('confidence_interval_days', 0),
                    'based_on_tasks': task.prediction_metadata.get('based_on_tasks', 0),
                    'similar_tasks': task.prediction_metadata.get('similar_tasks', []),
                    'early_date': task.prediction_metadata.get('early_date', ''),
                    'late_date': task.prediction_metadata.get('late_date', ''),
                    'prediction_method': task.prediction_metadata.get('prediction_method', 'unknown'),
                    'factors': task.prediction_metadata.get('factors', {}),
                    'is_likely_late': is_likely_late,
                    'last_updated': task.last_prediction_update.isoformat() if task.last_prediction_update else None
                }
            })
        else:
            return JsonResponse({
                'has_prediction': False,
                'message': 'No prediction available. Task may need a start date or more historical data.'
            })
            
    except Exception as e:
        logger.error(f"Error in get_task_prediction_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def bulk_update_predictions_api(request, board_id):
    """
    API endpoint to update predictions for all tasks in a board
    """
    try:
        board = get_object_or_404(Board, pk=board_id)
        
        # Check user has access
        if request.user not in board.members.all():
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        from kanban.utils.task_prediction import bulk_update_predictions
        result = bulk_update_predictions(board=board)
        
        return JsonResponse({
            'success': True,
            'total_tasks': result['total_tasks'],
            'updated': result['updated'],
            'failed': result['failed'],
            'message': f"Updated {result['updated']} of {result['total_tasks']} task predictions"
        })
        
    except Exception as e:
        logger.error(f"Error in bulk_update_predictions_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
