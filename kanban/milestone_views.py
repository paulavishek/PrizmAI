"""
Views for Milestone Management
Handles CRUD operations for project milestones
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from datetime import datetime

from kanban.models import Board, Milestone, Task


@login_required
@require_http_methods(["POST"])
def create_milestone(request, board_id):
    """
    Create a new milestone for a board
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Check access
    if not (board.created_by == request.user or request.user in board.members.all()):
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    try:
        # Get form data
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        target_date = request.POST.get('target_date')
        milestone_type = request.POST.get('milestone_type', 'custom')
        color = request.POST.get('color', '#FFD700')
        
        # Validate required fields
        if not title or not target_date:
            return JsonResponse({
                'success': False,
                'error': 'Title and target date are required'
            }, status=400)
        
        # Parse target date
        try:
            target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid date format'
            }, status=400)
        
        # Create milestone
        milestone = Milestone.objects.create(
            board=board,
            title=title,
            description=description,
            target_date=target_date,
            milestone_type=milestone_type,
            color=color,
            created_by=request.user
        )
        
        # Handle related tasks if provided
        task_ids = request.POST.getlist('related_tasks')
        if task_ids:
            tasks = Task.objects.filter(id__in=task_ids, column__board=board)
            milestone.related_tasks.set(tasks)
        
        return JsonResponse({
            'success': True,
            'message': 'Milestone created successfully',
            'milestone': {
                'id': milestone.id,
                'title': milestone.title,
                'target_date': milestone.target_date.isoformat(),
                'status': milestone.status,
                'completion_percentage': milestone.completion_percentage,
            }
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@require_http_methods(["POST"])
def update_milestone(request, board_id, milestone_id):
    """
    Update an existing milestone
    """
    board = get_object_or_404(Board, id=board_id)
    milestone = get_object_or_404(Milestone, id=milestone_id, board=board)
    
    # Check access
    if not (board.created_by == request.user or request.user in board.members.all()):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
        messages.error(request, "You don't have access to this board.")
        return redirect('dashboard')
    
    try:
        # Update fields
        if 'title' in request.POST:
            milestone.title = request.POST.get('title')
        if 'description' in request.POST:
            milestone.description = request.POST.get('description', '')
        if 'target_date' in request.POST:
            target_date_str = request.POST.get('target_date')
            milestone.target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        if 'milestone_type' in request.POST:
            milestone.milestone_type = request.POST.get('milestone_type')
        if 'color' in request.POST:
            milestone.color = request.POST.get('color')
        
        milestone.save()
        
        # Update related tasks if provided
        if 'related_tasks' in request.POST:
            task_ids = request.POST.getlist('related_tasks')
            tasks = Task.objects.filter(id__in=task_ids, column__board=board)
            milestone.related_tasks.set(tasks)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Milestone updated successfully',
                'milestone': {
                    'id': milestone.id,
                    'title': milestone.title,
                    'target_date': milestone.target_date.isoformat(),
                    'status': milestone.status,
                    'completion_percentage': milestone.completion_percentage,
                }
            })
        else:
            messages.success(request, 'Milestone updated successfully')
            return redirect('manage_milestones', board_id=board_id)
    
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
        messages.error(request, f'Error updating milestone: {str(e)}')
        return redirect('manage_milestones', board_id=board_id)


@login_required
@require_http_methods(["POST"])
def delete_milestone(request, board_id, milestone_id):
    """
    Delete a milestone
    """
    board = get_object_or_404(Board, id=board_id)
    milestone = get_object_or_404(Milestone, id=milestone_id, board=board)
    
    # Check access - only board creator can delete
    if board.created_by != request.user:
        return JsonResponse({'success': False, 'error': 'Only board creator can delete milestones'}, status=403)
    
    try:
        milestone_title = milestone.title
        milestone.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Milestone "{milestone_title}" deleted successfully'
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@require_http_methods(["POST"])
def toggle_milestone_completion(request, board_id, milestone_id):
    """
    Toggle milestone completion status
    """
    board = get_object_or_404(Board, id=board_id)
    milestone = get_object_or_404(Milestone, id=milestone_id, board=board)
    
    # Check access
    if not (board.created_by == request.user or request.user in board.members.all()):
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    try:
        if milestone.is_completed:
            milestone.mark_incomplete()
            message = f'Milestone "{milestone.title}" marked as incomplete'
        else:
            milestone.mark_complete(request.user)
            message = f'Milestone "{milestone.title}" marked as complete'
        
        return JsonResponse({
            'success': True,
            'message': message,
            'milestone': {
                'id': milestone.id,
                'is_completed': milestone.is_completed,
                'completed_date': milestone.completed_date.isoformat() if milestone.completed_date else None,
                'status': milestone.status,
            }
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
def get_milestone_details(request, board_id, milestone_id):
    """
    Get detailed information about a milestone
    """
    board = get_object_or_404(Board, id=board_id)
    milestone = get_object_or_404(Milestone, id=milestone_id, board=board)
    
    # Check access
    if not (board.created_by == request.user or request.user in board.members.all()):
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    # Get related tasks
    related_tasks = milestone.related_tasks.all()
    
    return JsonResponse({
        'success': True,
        'milestone': {
            'id': milestone.id,
            'title': milestone.title,
            'description': milestone.description,
            'target_date': milestone.target_date.isoformat(),
            'milestone_type': milestone.milestone_type,
            'milestone_type_display': milestone.get_milestone_type_display(),
            'is_completed': milestone.is_completed,
            'completed_date': milestone.completed_date.isoformat() if milestone.completed_date else None,
            'is_overdue': milestone.is_overdue,
            'status': milestone.status,
            'completion_percentage': milestone.completion_percentage,
            'color': milestone.color,
            'created_by': milestone.created_by.username,
            'created_at': milestone.created_at.isoformat(),
            'related_tasks': [
                {
                    'id': task.id,
                    'title': task.title,
                    'progress': task.progress,
                    'is_completed': task.progress == 100,
                }
                for task in related_tasks
            ],
            'related_tasks_count': related_tasks.count(),
            'completed_tasks_count': related_tasks.filter(progress=100).count(),
        }
    })


@login_required
def list_board_milestones(request, board_id):
    """
    Get all milestones for a board (API endpoint)
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Check access
    if not (board.created_by == request.user or request.user in board.members.all()):
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')  # all, completed, upcoming, overdue
    
    milestones = Milestone.objects.filter(board=board).order_by('target_date')
    
    # Apply filters
    if status_filter == 'completed':
        milestones = milestones.filter(is_completed=True)
    elif status_filter == 'upcoming':
        milestones = milestones.filter(is_completed=False, target_date__gte=timezone.now().date())
    elif status_filter == 'overdue':
        milestones = milestones.filter(is_completed=False, target_date__lt=timezone.now().date())
    
    return JsonResponse({
        'success': True,
        'milestones': [
            {
                'id': m.id,
                'title': m.title,
                'description': m.description,
                'target_date': m.target_date.isoformat(),
                'milestone_type': m.milestone_type,
                'is_completed': m.is_completed,
                'is_overdue': m.is_overdue,
                'status': m.status,
                'completion_percentage': m.completion_percentage,
                'color': m.color,
                'related_tasks_count': m.related_tasks.count(),
            }
            for m in milestones
        ],
        'total_count': milestones.count(),
    })
