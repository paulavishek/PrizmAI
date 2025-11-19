"""
API views for Wiki Meeting Assistant - AI-Powered Meeting Analysis
Handles AI-powered analysis of wiki pages containing meeting notes
"""

import json
import logging
import hashlib
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from django.db import models

from kanban.models import Board, Task, Column
from .models import WikiPage, WikiMeetingAnalysis, WikiMeetingTask
from .ai_utils import analyze_meeting_notes_from_wiki, parse_due_date

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["POST"])
def analyze_wiki_meeting_page(request, wiki_page_id):
    """
    API endpoint to analyze a wiki page as meeting notes using AI
    Extracts action items, decisions, blockers, risks, etc.
    """
    try:
        # Get organization
        if not hasattr(request.user, 'profile') or not request.user.profile.organization:
            return JsonResponse({'error': 'No organization found'}, status=400)
        
        org = request.user.profile.organization
        
        # Get the wiki page
        wiki_page = get_object_or_404(WikiPage, id=wiki_page_id, organization=org)
        
        # Check if user has access (must be in the organization)
        if not (hasattr(request.user, 'profile') and request.user.profile.organization == org):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Check if there's already a recent analysis for this content
        content_hash = hashlib.sha256(wiki_page.content.encode()).hexdigest()
        existing_analysis = WikiMeetingAnalysis.objects.filter(
            wiki_page=wiki_page,
            content_hash=content_hash,
            processing_status='completed'
        ).first()
        
        if existing_analysis:
            # Return existing analysis
            return JsonResponse({
                'success': True,
                'is_cached': True,
                'analysis_id': existing_analysis.id,
                'analysis_results': existing_analysis.analysis_results,
                'processed_at': existing_analysis.processed_at.isoformat()
            })
        
        # Create new analysis record
        analysis = WikiMeetingAnalysis.objects.create(
            wiki_page=wiki_page,
            organization=org,
            processed_by=request.user,
            processing_status='processing',
            content_hash=content_hash
        )
        
        try:
            # Get available boards for context
            available_boards = Board.objects.filter(organization=org)
            
            # Prepare wiki page context
            wiki_context = {
                'title': wiki_page.title,
                'created_at': wiki_page.created_at.isoformat(),
                'created_by': wiki_page.created_by.username,
                'tags': wiki_page.tags if wiki_page.tags else []
            }
            
            # Run AI analysis
            analysis_results = analyze_meeting_notes_from_wiki(
                wiki_content=wiki_page.content,
                wiki_page_context=wiki_context,
                organization=org,
                available_boards=available_boards
            )
            
            if not analysis_results:
                analysis.processing_status = 'failed'
                analysis.processing_error = 'AI analysis returned no results'
                analysis.save()
                return JsonResponse({'error': 'Failed to analyze meeting notes'}, status=500)
            
            # Store results
            analysis.analysis_results = analysis_results
            analysis.processing_status = 'completed'
            analysis.update_counts()  # Update denormalized counts
            analysis.save()
            
            return JsonResponse({
                'success': True,
                'is_cached': False,
                'analysis_id': analysis.id,
                'analysis_results': analysis_results,
                'processed_at': analysis.processed_at.isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error during AI analysis: {str(e)}")
            analysis.processing_status = 'failed'
            analysis.processing_error = str(e)
            analysis.save()
            return JsonResponse({'error': f'Analysis failed: {str(e)}'}, status=500)
        
    except Exception as e:
        logger.error(f"Error in analyze_wiki_meeting_page: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def create_tasks_from_meeting_analysis(request, analysis_id):
    """
    API endpoint to create tasks from wiki meeting analysis
    Allows user to select which action items to convert to tasks
    """
    try:
        if not hasattr(request.user, 'profile') or not request.user.profile.organization:
            return JsonResponse({'error': 'No organization found'}, status=400)
        
        org = request.user.profile.organization
        data = json.loads(request.body)
        
        board_id = data.get('board_id')
        selected_indices = data.get('selected_action_items', [])
        column_id = data.get('column_id')  # Optional: specific column
        
        if not board_id:
            return JsonResponse({'error': 'board_id is required'}, status=400)
        
        # Get analysis and board
        analysis = get_object_or_404(WikiMeetingAnalysis, id=analysis_id, organization=org)
        board = get_object_or_404(Board, id=board_id, organization=org)
        
        # Check board access
        if board.created_by != request.user and request.user not in board.members.all():
            return JsonResponse({'error': 'Access denied to board'}, status=403)
        
        # Get target column
        if column_id:
            target_column = get_object_or_404(Column, id=column_id, board=board)
        else:
            # Get default column (usually "To Do" or first column)
            target_column = board.columns.filter(name__icontains='todo').first() or board.columns.first()
        
        if not target_column:
            return JsonResponse({'error': 'No columns found in board'}, status=400)
        
        action_items = analysis.get_action_items()
        created_tasks = []
        failed_items = []
        
        with transaction.atomic():
            for idx in selected_indices:
                try:
                    if idx >= len(action_items):
                        failed_items.append({'index': idx, 'error': 'Index out of range'})
                        continue
                    
                    action_item = action_items[idx]
                    
                    # Map priority
                    priority_map = {
                        'urgent': 'urgent',
                        'high': 'high',
                        'medium': 'medium',
                        'low': 'low'
                    }
                    priority = priority_map.get(action_item.get('priority', 'medium'), 'medium')
                    
                    # Create task
                    task = Task.objects.create(
                        title=action_item['title'][:200],  # Limit title length
                        description=action_item.get('description', ''),
                        column=target_column,
                        priority=priority,
                        created_by=request.user
                    )
                    
                    # Try to assign if suggested
                    assignee_username = action_item.get('suggested_assignee')
                    if assignee_username:
                        try:
                            # Try to find user by username
                            assignee = User.objects.filter(username=assignee_username).first()
                            if assignee and assignee.profile.organization == org:
                                task.assigned_to = assignee
                            else:
                                # Try partial match if exact match fails
                                assignee = User.objects.filter(
                                    username__icontains=assignee_username,
                                    profile__organization=org
                                ).first()
                                if assignee:
                                    task.assigned_to = assignee
                        except Exception as e:
                            logger.warning(f"Could not assign task to {assignee_username}: {str(e)}")
                    
                    # Set due date if suggested
                    due_date_str = action_item.get('due_date_suggestion')
                    if due_date_str:
                        due_date = parse_due_date(due_date_str)
                        if due_date:
                            task.due_date = due_date
                    
                    # Add tags from action item
                    if action_item.get('tags'):
                        task.tags = action_item['tags']
                    
                    task.save()
                    
                    # Create WikiMeetingTask link
                    WikiMeetingTask.objects.create(
                        meeting_analysis=analysis,
                        task=task,
                        action_item_index=idx,
                        action_item_data=action_item,
                        created_by=request.user
                    )
                    
                    created_tasks.append({
                        'id': task.id,
                        'title': task.title,
                        'priority': task.priority,
                        'assigned_to': task.assigned_to.username if task.assigned_to else None,
                        'due_date': task.due_date.isoformat() if task.due_date else None,
                        'url': f'/tasks/{task.id}/'
                    })
                    
                except Exception as e:
                    logger.error(f"Error creating task from action item {idx}: {str(e)}")
                    failed_items.append({'index': idx, 'error': str(e)})
            
            # Update analysis with task count
            analysis.tasks_created_count = len(created_tasks)
            analysis.save(update_fields=['tasks_created_count'])
        
        return JsonResponse({
            'success': True,
            'created_tasks': created_tasks,
            'failed_items': failed_items,
            'total_created': len(created_tasks),
            'total_failed': len(failed_items)
        })
        
    except Exception as e:
        logger.error(f"Error in create_tasks_from_meeting_analysis: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_meeting_analysis_details(request, analysis_id):
    """
    API endpoint to get detailed meeting analysis information
    """
    try:
        if not hasattr(request.user, 'profile') or not request.user.profile.organization:
            return JsonResponse({'error': 'No organization found'}, status=400)
        
        org = request.user.profile.organization
        analysis = get_object_or_404(WikiMeetingAnalysis, id=analysis_id, organization=org)
        
        # Get created tasks
        created_tasks = []
        for meeting_task in analysis.created_tasks.select_related('task').all():
            task = meeting_task.task
            created_tasks.append({
                'id': task.id,
                'title': task.title,
                'status': task.column.name if task.column else 'Unknown',
                'priority': task.priority,
                'assigned_to': task.assigned_to.username if task.assigned_to else None,
                'created_at': meeting_task.created_at.isoformat()
            })
        
        return JsonResponse({
            'id': analysis.id,
            'wiki_page': {
                'id': analysis.wiki_page.id,
                'title': analysis.wiki_page.title,
                'slug': analysis.wiki_page.slug
            },
            'processing_status': analysis.processing_status,
            'processed_at': analysis.processed_at.isoformat(),
            'processed_by': analysis.processed_by.username,
            'analysis_results': analysis.analysis_results,
            'action_items_count': analysis.action_items_count,
            'decisions_count': analysis.decisions_count,
            'blockers_count': analysis.blockers_count,
            'risks_count': analysis.risks_count,
            'tasks_created_count': analysis.tasks_created_count,
            'created_tasks': created_tasks,
            'confidence_score': analysis.confidence_score,
            'user_reviewed': analysis.user_reviewed
        })
        
    except Exception as e:
        logger.error(f"Error in get_meeting_analysis_details: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def mark_analysis_reviewed(request, analysis_id):
    """
    Mark an analysis as reviewed by user, optionally with notes
    """
    try:
        if not hasattr(request.user, 'profile') or not request.user.profile.organization:
            return JsonResponse({'error': 'No organization found'}, status=400)
        
        org = request.user.profile.organization
        analysis = get_object_or_404(WikiMeetingAnalysis, id=analysis_id, organization=org)
        
        data = json.loads(request.body)
        user_notes = data.get('user_notes', '')
        
        analysis.user_reviewed = True
        if user_notes:
            analysis.user_notes = user_notes
        analysis.save()
        
        return JsonResponse({
            'success': True,
            'analysis_id': analysis.id,
            'user_reviewed': analysis.user_reviewed
        })
        
    except Exception as e:
        logger.error(f"Error in mark_analysis_reviewed: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_boards_for_organization(request):
    """
    Get all boards available in the user's organization
    Used for board selection when creating tasks
    """
    try:
        if not hasattr(request.user, 'profile') or not request.user.profile.organization:
            return JsonResponse({'error': 'No organization found'}, status=400)
        
        org = request.user.profile.organization
        
        # Get boards user has access to
        boards = Board.objects.filter(organization=org).filter(
            models.Q(created_by=request.user) | models.Q(members=request.user)
        ).distinct()
        
        boards_data = []
        for board in boards:
            columns = []
            for column in board.columns.all():
                columns.append({
                    'id': column.id,
                    'name': column.name,
                    'position': column.position
                })
            
            boards_data.append({
                'id': board.id,
                'name': board.name,
                'description': board.description,
                'columns': columns
            })
        
        return JsonResponse({
            'success': True,
            'boards': boards_data
        })
        
    except Exception as e:
        logger.error(f"Error in get_boards_for_organization: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
