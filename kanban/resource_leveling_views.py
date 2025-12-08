"""
Resource Leveling API Views
API endpoints for AI-powered resource optimization and workload balancing
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.contrib.auth.models import User

from kanban.models import Task, Board
from kanban.resource_leveling import ResourceLevelingService, WorkloadBalancer
from kanban.resource_leveling_models import (
    UserPerformanceProfile,
    ResourceLevelingSuggestion,
    TaskAssignmentHistory
)

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["POST"])
def analyze_task_assignment(request, task_id):
    """
    Analyze optimal assignment for a task
    
    POST /api/tasks/{task_id}/analyze-assignment/
    
    Returns:
        {
            "task_id": 123,
            "current_assignee": "bob",
            "top_recommendation": {...},
            "all_candidates": [...],
            "should_reassign": true,
            "reasoning": "Move to Jane: 70% faster, better skill match"
        }
    """
    try:
        task = get_object_or_404(Task, id=task_id)
        
        # Check permissions
        board = task.column.board if task.column else None
        if not board or request.user not in board.members.all():
            return JsonResponse({
                'error': 'You do not have permission to access this task'
            }, status=403)
        
        # Initialize service
        service = ResourceLevelingService(board.organization)
        
        # Analyze assignment
        analysis = service.analyze_task_assignment(task)
        
        return JsonResponse(analysis)
        
    except Task.DoesNotExist:
        return JsonResponse({'error': 'Task not found'}, status=404)
    except Exception as e:
        logger.error(f"Error analyzing task assignment: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def create_leveling_suggestion(request, task_id):
    """
    Create a resource leveling suggestion for a task
    
    POST /api/tasks/{task_id}/suggest-reassignment/
    
    Returns:
        {
            "suggestion_id": 456,
            "suggested_assignee": "jane",
            "time_savings": "70%",
            "confidence": 85,
            "reasoning": "...",
            "expires_at": "2025-12-10T12:00:00Z"
        }
    """
    try:
        task = get_object_or_404(Task, id=task_id)
        
        # Check permissions
        board = task.column.board if task.column else None
        if not board or request.user not in board.members.all():
            return JsonResponse({
                'error': 'You do not have permission to access this task'
            }, status=403)
        
        # Initialize service
        service = ResourceLevelingService(board.organization)
        
        # Create suggestion
        suggestion = service.create_suggestion(task)
        
        if not suggestion:
            return JsonResponse({
                'message': 'No beneficial reassignment found',
                'current_assignment_is_optimal': True
            })
        
        return JsonResponse({
            'suggestion_id': suggestion.id,
            'suggested_assignee': suggestion.suggested_assignee.username,
            'suggested_name': suggestion.suggested_assignee.get_full_name() or suggestion.suggested_assignee.username,
            'time_savings': f"{suggestion.time_savings_percentage:.0f}%",
            'time_savings_hours': suggestion.time_savings_hours,
            'confidence': suggestion.confidence_score,
            'skill_match': suggestion.skill_match_score,
            'reasoning': suggestion.reasoning,
            'projected_completion': suggestion.suggested_projected_date.isoformat() if suggestion.suggested_projected_date else None,
            'expires_at': suggestion.expires_at.isoformat()
        })
        
    except Task.DoesNotExist:
        return JsonResponse({'error': 'Task not found'}, status=404)
    except Exception as e:
        logger.error(f"Error creating leveling suggestion: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def accept_suggestion(request, suggestion_id):
    """
    Accept a resource leveling suggestion and reassign the task
    
    POST /api/suggestions/{suggestion_id}/accept/
    
    Returns:
        {
            "success": true,
            "task_id": 123,
            "new_assignee": "jane",
            "message": "Task reassigned successfully"
        }
    """
    try:
        suggestion = get_object_or_404(ResourceLevelingSuggestion, id=suggestion_id)
        
        # Check permissions
        board = suggestion.task.column.board if suggestion.task.column else None
        if not board or request.user not in board.members.all():
            return JsonResponse({
                'error': 'You do not have permission to accept this suggestion'
            }, status=403)
        
        # Accept suggestion
        success = suggestion.accept(request.user)
        
        if not success:
            return JsonResponse({
                'error': 'Suggestion has expired or is no longer valid'
            }, status=400)
        
        return JsonResponse({
            'success': True,
            'task_id': suggestion.task.id,
            'new_assignee': suggestion.suggested_assignee.username,
            'message': 'Task reassigned successfully'
        })
        
    except ResourceLevelingSuggestion.DoesNotExist:
        return JsonResponse({'error': 'Suggestion not found'}, status=404)
    except Exception as e:
        logger.error(f"Error accepting suggestion: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def reject_suggestion(request, suggestion_id):
    """
    Reject a resource leveling suggestion
    
    POST /api/suggestions/{suggestion_id}/reject/
    """
    try:
        suggestion = get_object_or_404(ResourceLevelingSuggestion, id=suggestion_id)
        
        # Check permissions
        board = suggestion.task.column.board if suggestion.task.column else None
        if not board or request.user not in board.members.all():
            return JsonResponse({
                'error': 'You do not have permission to reject this suggestion'
            }, status=403)
        
        suggestion.reject(request.user)
        
        return JsonResponse({
            'success': True,
            'message': 'Suggestion rejected'
        })
        
    except ResourceLevelingSuggestion.DoesNotExist:
        return JsonResponse({'error': 'Suggestion not found'}, status=404)
    except Exception as e:
        logger.error(f"Error rejecting suggestion: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_board_suggestions(request, board_id):
    """
    Get all active resource leveling suggestions for a board
    
    GET /api/boards/{board_id}/leveling-suggestions/
    
    Returns:
        {
            "suggestions": [
                {
                    "id": 456,
                    "task_title": "Fix login bug",
                    "current_assignee": "bob",
                    "suggested_assignee": "jane",
                    "time_savings": "70%",
                    "confidence": 85,
                    "reasoning": "...",
                    "expires_at": "..."
                },
                ...
            ],
            "total_potential_savings": 15.5
        }
    """
    try:
        board = get_object_or_404(Board, id=board_id)
        
        # Check permissions
        if request.user not in board.members.all():
            return JsonResponse({
                'error': 'You do not have permission to access this board'
            }, status=403)
        
        # Initialize service
        service = ResourceLevelingService(board.organization)
        
        # Get suggestions
        suggestions = service.get_board_optimization_suggestions(board, limit=20)
        
        # Format response
        suggestion_list = []
        total_savings = 0
        
        for s in suggestions:
            suggestion_list.append({
                'id': s.id,
                'task_id': s.task.id,
                'task_title': s.task.title,
                'current_assignee': s.current_assignee.username if s.current_assignee else 'unassigned',
                'suggested_assignee': s.suggested_assignee.username,
                'suggested_name': s.suggested_assignee.get_full_name() or s.suggested_assignee.username,
                'time_savings': f"{s.time_savings_percentage:.0f}%",
                'time_savings_hours': s.time_savings_hours,
                'confidence': s.confidence_score,
                'skill_match': s.skill_match_score,
                'workload_impact': s.get_workload_impact_display(),
                'reasoning': s.reasoning,
                'projected_completion': s.suggested_projected_date.isoformat() if s.suggested_projected_date else None,
                'expires_at': s.expires_at.isoformat(),
                'status': s.status
            })
            total_savings += s.time_savings_hours
        
        return JsonResponse({
            'suggestions': suggestion_list,
            'total_suggestions': len(suggestion_list),
            'total_potential_savings_hours': round(total_savings, 1)
        })
        
    except Board.DoesNotExist:
        return JsonResponse({'error': 'Board not found'}, status=404)
    except Exception as e:
        logger.error(f"Error getting board suggestions: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_team_workload_report(request, board_id):
    """
    Get team workload report for a board
    
    GET /api/boards/{board_id}/workload-report/
    
    Returns:
        {
            "board": "Q4 Product Launch",
            "team_size": 5,
            "members": [
                {
                    "username": "bob",
                    "name": "Bob Smith",
                    "active_tasks": 8,
                    "workload_hours": 45.5,
                    "utilization": 113.8,
                    "velocity": 2.5,
                    "on_time_rate": 85.0,
                    "status": "overloaded"
                },
                ...
            ],
            "bottlenecks": [...],
            "underutilized": [...]
        }
    """
    try:
        board = get_object_or_404(Board, id=board_id)
        
        # Check permissions
        if request.user not in board.members.all():
            return JsonResponse({
                'error': 'You do not have permission to access this board'
            }, status=403)
        
        # Initialize service
        service = ResourceLevelingService(board.organization)
        
        # Generate report
        report = service.get_team_workload_report(board)
        
        return JsonResponse(report)
        
    except Board.DoesNotExist:
        return JsonResponse({'error': 'Board not found'}, status=404)
    except Exception as e:
        logger.error(f"Error generating workload report: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def optimize_board_workload(request, board_id):
    """
    Perform comprehensive workload optimization for a board
    
    POST /api/boards/{board_id}/optimize-workload/
    
    Body (optional):
        {
            "auto_apply": false,  // If true, automatically apply suggestions (use with caution)
            "limit": 10           // Max suggestions to generate
        }
    
    Returns:
        {
            "total_suggestions": 8,
            "potential_time_savings": 25.5,
            "suggestions": [...],
            "applied": 0
        }
    """
    try:
        board = get_object_or_404(Board, id=board_id)
        
        # Check permissions
        if request.user not in board.members.all():
            return JsonResponse({
                'error': 'You do not have permission to access this board'
            }, status=403)
        
        # Parse body
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            data = {}
        
        auto_apply = data.get('auto_apply', False)
        
        # Initialize service
        service = ResourceLevelingService(board.organization)
        
        # Optimize
        result = service.optimize_board_workload(board, auto_apply=auto_apply)
        
        return JsonResponse(result)
        
    except Board.DoesNotExist:
        return JsonResponse({'error': 'Board not found'}, status=404)
    except Exception as e:
        logger.error(f"Error optimizing board workload: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def balance_workload(request, board_id):
    """
    Balance workload across team members
    
    POST /api/boards/{board_id}/balance-workload/
    
    Body (optional):
        {
            "target_utilization": 75.0  // Target utilization percentage
        }
    
    Returns:
        {
            "message": "Generated 5 balancing suggestions",
            "suggestions": [...]
        }
    """
    try:
        board = get_object_or_404(Board, id=board_id)
        
        # Check permissions
        if request.user not in board.members.all():
            return JsonResponse({
                'error': 'You do not have permission to access this board'
            }, status=403)
        
        # Parse body
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            data = {}
        
        target_utilization = data.get('target_utilization', 75.0)
        
        # Initialize balancer
        balancer = WorkloadBalancer(board.organization)
        
        # Balance workload
        result = balancer.balance_workload(board, target_utilization=target_utilization)
        
        return JsonResponse(result)
        
    except Board.DoesNotExist:
        return JsonResponse({'error': 'Board not found'}, status=404)
    except Exception as e:
        logger.error(f"Error balancing workload: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_user_performance_profile(request, user_id):
    """
    Get performance profile for a user
    
    GET /api/users/{user_id}/performance-profile/
    
    Returns:
        {
            "username": "bob",
            "total_tasks_completed": 45,
            "avg_completion_time_hours": 12.5,
            "velocity_score": 2.5,
            "on_time_rate": 85.0,
            "quality_score": 4.2,
            "current_tasks": 8,
            "workload_hours": 45.5,
            "utilization": 113.8,
            "top_skills": ["api", "backend", "django", ...]
        }
    """
    try:
        user = get_object_or_404(User, id=user_id)
        
        # Get organization from request user
        user_profile = request.user.userprofile
        organization = user_profile.organization
        
        # Get performance profile
        profile, created = UserPerformanceProfile.objects.get_or_create(
            user=user,
            organization=organization
        )
        
        if created or not profile.total_tasks_completed:
            profile.update_metrics()
        
        # Get top skills
        top_skills = list(profile.skill_keywords.keys())[:10] if profile.skill_keywords else []
        
        return JsonResponse({
            'username': user.username,
            'name': user.get_full_name() or user.username,
            'total_tasks_completed': profile.total_tasks_completed,
            'avg_completion_time_hours': round(profile.avg_completion_time_hours, 1),
            'velocity_score': round(profile.velocity_score, 2),
            'on_time_rate': round(profile.on_time_completion_rate, 1),
            'quality_score': round(profile.quality_score, 1),
            'current_tasks': profile.current_active_tasks,
            'workload_hours': round(profile.current_workload_hours, 1),
            'utilization': round(profile.utilization_percentage, 1),
            'weekly_capacity': profile.weekly_capacity_hours,
            'top_skills': top_skills,
            'last_updated': profile.last_updated.isoformat()
        })
        
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        logger.error(f"Error getting performance profile: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def update_performance_profiles(request, board_id):
    """
    Update performance profiles for all board members
    
    POST /api/boards/{board_id}/update-profiles/
    
    Returns:
        {
            "total_members": 5,
            "updated": 5
        }
    """
    try:
        board = get_object_or_404(Board, id=board_id)
        
        # Check permissions (only board admins)
        if request.user not in board.members.all():
            return JsonResponse({
                'error': 'You do not have permission to update profiles'
            }, status=403)
        
        # Initialize service
        service = ResourceLevelingService(board.organization)
        
        # Update all profiles
        result = service.update_all_profiles(board)
        
        return JsonResponse(result)
        
    except Board.DoesNotExist:
        return JsonResponse({'error': 'Board not found'}, status=404)
    except Exception as e:
        logger.error(f"Error updating profiles: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)
