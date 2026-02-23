import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse, FileResponse
from django.contrib import messages
from django.db.models import Count, Q, Case, When, IntegerField, Max, Sum
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from datetime import timedelta
import json
import csv
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

# Configure logger
logger = logging.getLogger(__name__)

from .models import Board, Column, Task, TaskLabel, Comment, TaskActivity, TaskFile
from .forms import BoardForm, ColumnForm, TaskForm, TaskLabelForm, CommentForm, TaskMoveForm, TaskSearchForm, TaskFileForm
from accounts.models import UserProfile, Organization
from .stakeholder_models import StakeholderTaskInvolvement, ProjectStakeholder

@login_required
def dashboard(request):
    # Ensure user has a profile (MVP mode: auto-create without organization)
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(
            user=request.user,
            organization=None,
            is_admin=False,
            completed_wizard=True
        )
    
    # MVP Mode: Organization is optional (can be None)
    organization = profile.organization
    
    # Mark wizard as completed for new users (we skip the wizard now)
    if not profile.completed_wizard:
        profile.completed_wizard = True
        profile.save()
    
    # Track if this is first visit for welcome modal
    show_welcome_modal = not profile.has_seen_welcome
    if show_welcome_modal:
        profile.has_seen_welcome = True
        profile.save()
    
    # Import simplified mode setting
    from kanban.utils.demo_settings import SIMPLIFIED_MODE
    
    # MVP Mode: Get all boards the user has access to
    # Include: 1) Official demo boards, 2) Boards user created, 3) Boards user is member of
    demo_boards = Board.objects.filter(is_official_demo_board=True)
    user_boards = Board.objects.filter(
        Q(created_by=request.user) | Q(members=request.user)
    )
    
    # Combine and deduplicate
    boards = (demo_boards | user_boards).distinct()
    
    # Get analytics data — exclude milestones (item_type='task' only)
    task_count = Task.objects.filter(column__board__in=boards, item_type='task').count()
    completed_count = Task.objects.filter(
        column__board__in=boards,
        item_type='task',
        progress=100
    ).count()
    
    # Get completion rate
    completion_rate = 0
    if task_count > 0:
        completion_rate = (completed_count / task_count) * 100
      # Get tasks due soon (next 3 days) — exclude milestones
    due_soon = Task.objects.filter(
        column__board__in=boards,
        item_type='task',
        due_date__range=[timezone.now(), timezone.now() + timedelta(days=3)]
    ).exclude(
        progress=100
    ).count()
      # Get overdue tasks (due date in the past and not completed) — exclude milestones
    overdue_count = Task.objects.filter(
        column__board__in=boards,
        item_type='task',
        due_date__lt=timezone.now()
    ).exclude(
        progress=100
    ).count()
    
    # Get detailed task data for modals with pagination
    # Items per page
    items_per_page = 10
    
    # All Tasks (exclude milestones)
    all_tasks_list = Task.objects.filter(column__board__in=boards, item_type='task').select_related('column', 'assigned_to', 'column__board').order_by('-created_at')
    all_tasks_page = request.GET.get('all_tasks_page', 1)
    all_tasks_paginator = Paginator(all_tasks_list, items_per_page)
    try:
        all_tasks = all_tasks_paginator.page(all_tasks_page)
    except PageNotAnInteger:
        all_tasks = all_tasks_paginator.page(1)
    except EmptyPage:
        all_tasks = all_tasks_paginator.page(all_tasks_paginator.num_pages)
    
    # Completed Tasks (exclude milestones)
    completed_tasks_list = Task.objects.filter(
        column__board__in=boards,
        item_type='task',
        progress=100
    ).select_related('column', 'assigned_to', 'column__board').order_by('-updated_at')
    completed_tasks_page = request.GET.get('completed_tasks_page', 1)
    completed_tasks_paginator = Paginator(completed_tasks_list, items_per_page)
    try:
        completed_tasks = completed_tasks_paginator.page(completed_tasks_page)
    except PageNotAnInteger:
        completed_tasks = completed_tasks_paginator.page(1)
    except EmptyPage:
        completed_tasks = completed_tasks_paginator.page(completed_tasks_paginator.num_pages)
    
    # Overdue Tasks
    overdue_tasks_list = Task.objects.filter(
        column__board__in=boards,
        due_date__lt=timezone.now()
    ).exclude(
        progress=100
    ).select_related('column', 'assigned_to', 'column__board').order_by('due_date')
    overdue_tasks_page = request.GET.get('overdue_tasks_page', 1)
    overdue_tasks_paginator = Paginator(overdue_tasks_list, items_per_page)
    try:
        overdue_tasks = overdue_tasks_paginator.page(overdue_tasks_page)
    except PageNotAnInteger:
        overdue_tasks = overdue_tasks_paginator.page(1)
    except EmptyPage:
        overdue_tasks = overdue_tasks_paginator.page(overdue_tasks_paginator.num_pages)
    
    # Due Soon Tasks
    due_soon_tasks_list = Task.objects.filter(
        column__board__in=boards,
        due_date__range=[timezone.now(), timezone.now() + timedelta(days=3)]
    ).exclude(
        progress=100
    ).select_related('column', 'assigned_to', 'column__board').order_by('due_date')
    due_soon_tasks_page = request.GET.get('due_soon_tasks_page', 1)
    due_soon_tasks_paginator = Paginator(due_soon_tasks_list, items_per_page)
    try:
        due_soon_tasks = due_soon_tasks_paginator.page(due_soon_tasks_page)
    except PageNotAnInteger:
        due_soon_tasks = due_soon_tasks_paginator.page(1)
    except EmptyPage:
        due_soon_tasks = due_soon_tasks_paginator.page(due_soon_tasks_paginator.num_pages)
    
    # Get sort preference from request (default to 'urgency')
    sort_by = request.GET.get('sort_tasks', 'urgency')
    
    # Base query for My Tasks - exclude only completed tasks (progress=100)
    my_tasks_query = Task.objects.filter(
        column__board__in=boards,
        assigned_to=request.user
    ).exclude(
        progress=100
    ).select_related('column', 'column__board', 'assigned_to')
    
    # Apply sorting based on user preference
    if sort_by == 'due_date':
        # Sort by: 1) Due date (soonest first), 2) Priority, 3) Creation date
        my_tasks = my_tasks_query.extra(
            select={
                'priority_order': """
                    CASE priority 
                        WHEN 'urgent' THEN 1 
                        WHEN 'high' THEN 2 
                        WHEN 'medium' THEN 3 
                        WHEN 'low' THEN 4 
                        ELSE 5 
                    END
                """,
                'due_date_order': "CASE WHEN due_date IS NULL THEN 1 ELSE 0 END"
            }
        ).order_by('due_date_order', 'due_date', 'priority_order', 'created_at')[:8]
    elif sort_by == 'priority':
        # Sort by: 1) Priority level, 2) Due date, 3) Creation date
        my_tasks = my_tasks_query.extra(
            select={
                'priority_order': """
                    CASE priority 
                        WHEN 'urgent' THEN 1 
                        WHEN 'high' THEN 2 
                        WHEN 'medium' THEN 3 
                        WHEN 'low' THEN 4 
                        ELSE 5 
                    END
                """,
                'due_date_order': "CASE WHEN due_date IS NULL THEN 1 ELSE 0 END"
            }
        ).order_by('priority_order', 'due_date_order', 'due_date', 'created_at')[:8]
    elif sort_by == 'recent':
        # Sort by: 1) Most recently created/updated, 2) Priority
        my_tasks = my_tasks_query.extra(
            select={
                'priority_order': """
                    CASE priority 
                        WHEN 'urgent' THEN 1 
                        WHEN 'high' THEN 2 
                        WHEN 'medium' THEN 3 
                        WHEN 'low' THEN 4 
                        ELSE 5 
                    END
                """
            }
        ).order_by('-updated_at', '-created_at', 'priority_order')[:8]
    else:  # Default: 'urgency'
        # Sort by: 1) Overdue tasks first, 2) Priority level, 3) Due date, 4) Creation date
        my_tasks = my_tasks_query.extra(
            select={
                'is_overdue': "CASE WHEN due_date < datetime('now') THEN 1 ELSE 0 END",
                'priority_order': """
                    CASE priority 
                        WHEN 'urgent' THEN 1 
                        WHEN 'high' THEN 2 
                        WHEN 'medium' THEN 3 
                        WHEN 'low' THEN 4 
                        ELSE 5 
                    END
                """
            }
        ).order_by('-is_overdue', 'priority_order', 'due_date', 'created_at')[:8]
    
    # Count of my tasks (for stats) — exclude milestones
    my_tasks_count = Task.objects.filter(
        column__board__in=boards,
        assigned_to=request.user,
        item_type='task'
    ).exclude(
        Q(column__name__icontains='done') |
        Q(column__name__icontains='closed') |
        Q(column__name__icontains='completed') |
        Q(progress=100)
    ).count()        
    return render(request, 'kanban/dashboard.html', {
        'boards': boards,
        'task_count': task_count,
        'completed_count': completed_count,
        'completion_rate': round(completion_rate, 1),
        'due_soon': due_soon,
        'overdue_count': overdue_count,
        'all_tasks': all_tasks,
        'completed_tasks': completed_tasks,
        'overdue_tasks': overdue_tasks,
        'due_soon_tasks': due_soon_tasks,
            'remaining_tasks': task_count - completed_count,
            'my_tasks': my_tasks,
            'my_tasks_count': my_tasks_count,
            'my_tasks_sort_by': sort_by,  # Current sort preference
            'now': timezone.now(),  # For comparing dates in the template
            'show_welcome_modal': show_welcome_modal,  # Show welcome modal for first-time users
        })

@login_required
def board_list(request):
    # Ensure user has a profile (MVP mode: auto-create without organization)
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(
            user=request.user,
            organization=None,
            is_admin=False,
            completed_wizard=True
        )
    
    # MVP Mode: Get all boards the user has access to
    # Include: 1) Official demo boards, 2) Boards user created, 3) Boards user is member of
    demo_boards = Board.objects.filter(is_official_demo_board=True)
    user_boards = Board.objects.filter(
        Q(created_by=request.user) | Q(members=request.user)
    )
    
    # Combine and deduplicate
    boards = (demo_boards | user_boards).distinct()
    
    # For board_list, we only display boards, creation is handled by create_board view
    form = BoardForm()
    
    return render(request, 'kanban/board_list.html', {
        'boards': boards,
        'form': form
    })

@login_required
def create_board(request):
    from kanban.audit_utils import log_model_change
    from kanban.permission_utils import assign_default_role_to_user
    from kanban.models import Strategy as KanbanStrategy

    # Ensure user has a profile (MVP mode: auto-create without organization)
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(
            user=request.user,
            organization=None,
            is_admin=False,
            completed_wizard=True
        )
    
    # MVP Mode: Organization is optional (can be None)
    organization = profile.organization

    # Optional: link new board directly to a Strategy when coming from strategy_detail
    strategy_id = request.GET.get('strategy_id') or request.POST.get('strategy_id')
    selected_strategy = None
    if strategy_id:
        try:
            selected_strategy = KanbanStrategy.objects.get(id=strategy_id)
        except KanbanStrategy.DoesNotExist:
            selected_strategy = None

    if request.method == 'POST':
        form = BoardForm(request.POST)
        if form.is_valid():
            board = form.save(commit=False)
            # MVP Mode: organization can be None
            board.organization = organization
            board.created_by = request.user

            # Auto-link to strategy if one was passed
            if selected_strategy:
                board.strategy = selected_strategy

            board.save()
            board.members.add(request.user)
            
            # Assign creator as Admin in RBAC system (if organization exists)
            if organization:
                try:
                    from kanban.permission_models import Role, BoardMembership
                    admin_role = Role.objects.filter(
                        organization=organization,
                        name='Admin'
                    ).first()
                    if admin_role:
                        BoardMembership.objects.create(
                            board=board,
                            user=request.user,
                            role=admin_role,
                            added_by=request.user
                        )
                except Exception as e:
                    # Continue even if RBAC setup fails
                    pass
            
            # Log board creation
            log_model_change('board.created', board, request.user, request)
              # Check if there are recommended columns to create
            recommended_columns_json = request.POST.get('recommended_columns')
            if recommended_columns_json:
                try:
                    recommended_columns = json.loads(recommended_columns_json)
                    
                    # Safety check: Ensure first column is "To Do" (required for Add Task button)
                    if recommended_columns and recommended_columns[0]['name'] != 'To Do':
                        # Prepend "To Do" if it's missing
                        has_todo = any(col['name'].lower() in ['to do', 'todo'] for col in recommended_columns)
                        if not has_todo:
                            recommended_columns.insert(0, {
                                'name': 'To Do',
                                'description': 'Tasks to be started',
                                'position': 0
                            })
                            # Adjust positions for other columns
                            for i, col in enumerate(recommended_columns[1:], start=1):
                                col['position'] = i
                    
                    # Create the recommended columns
                    for i, column_data in enumerate(recommended_columns):
                        Column.objects.create(
                            name=column_data['name'],
                            board=board,
                            position=i
                        )
                    
                    messages.success(request, f'Board "{board.name}" created successfully with {len(recommended_columns)} AI-recommended columns!')
                except (json.JSONDecodeError, KeyError) as e:
                    # Fallback to default columns if there's an error with recommended columns
                    default_columns = ['To Do', 'In Progress', 'Done']
                    for i, name in enumerate(default_columns):
                        Column.objects.create(name=name, board=board, position=i)
                    messages.success(request, f'Board "{board.name}" created successfully with default columns!')
            else:
                # No recommended columns, create default ones
                default_columns = ['To Do', 'In Progress', 'Done']
                for i, name in enumerate(default_columns):
                    Column.objects.create(name=name, board=board, position=i)
                messages.success(request, f'Board "{board.name}" created successfully!')

            # Redirect back to strategy if we came from one
            if selected_strategy:
                return redirect('strategy_detail',
                                mission_id=selected_strategy.mission_id,
                                strategy_id=selected_strategy.id)
            return redirect('board_detail', board_id=board.id)
    else:
        form = BoardForm()
    
    return render(request, 'kanban/create_board.html', {
        'form': form,
        'selected_strategy': selected_strategy,
    })

@login_required
def board_detail(request, board_id):
    from kanban.audit_utils import log_audit
    from kanban.utils.demo_settings import SIMPLIFIED_MODE
    
    board = get_object_or_404(Board, id=board_id)
    
    # Check if this is a demo board
    is_demo_board = board.is_official_demo_board if hasattr(board, 'is_official_demo_board') else False
    
    # Auto-add user to demo boards - ensures they appear in AI Resource Optimization
    if is_demo_board and request.user not in board.members.all():
        board.members.add(request.user)
    
    # Log board view
    log_audit('board.viewed', user=request.user, request=request,
              object_type='board', object_id=board.id, object_repr=board.name,
              board_id=board.id)
    
    columns = Column.objects.filter(board=board).order_by('position')
    
    # Create default columns if none exist
    if not columns.exists():
        default_columns = ['To Do', 'In Progress', 'Done']
        for i, name in enumerate(default_columns):
            Column.objects.create(name=name, board=board, position=i)
        columns = Column.objects.filter(board=board).order_by('position')
    
    # Initialize the search form
    search_form = TaskSearchForm(request.GET or None, board=board)
    
    # Get all tasks for this board (with filtering if search is active)
    # Exclude milestones (item_type='milestone') — they are Gantt-only items
    tasks = Task.objects.filter(column__board=board, item_type='task')
    
    # Apply search filters if the form is valid
    any_filter_active = False
    if search_form.is_valid() and any(search_form.cleaned_data.values()):
        any_filter_active = True
        # Filter by column
        if search_form.cleaned_data.get('column'):
            tasks = tasks.filter(column=search_form.cleaned_data['column'])
        
        # Filter by priority
        if search_form.cleaned_data.get('priority'):
            tasks = tasks.filter(priority=search_form.cleaned_data['priority'])
        
        # Filter by label category (Lean Six Sigma)
        if search_form.cleaned_data.get('label_category'):
            category = search_form.cleaned_data['label_category']
            if category == 'lean':
                # All Lean Six Sigma labels
                tasks = tasks.filter(labels__category='lean')
            elif category == 'regular':
                # Only regular labels
                tasks = tasks.filter(labels__category='regular')
            elif category == 'lean_va':
                # Value-Added tasks
                tasks = tasks.filter(labels__name='Value-Added', labels__category='lean')
            elif category == 'lean_nva':
                # Necessary Non-Value-Added tasks
                tasks = tasks.filter(labels__name='Necessary NVA', labels__category='lean')
            elif category == 'lean_waste':
                # Waste/Eliminate tasks
                tasks = tasks.filter(labels__name='Waste/Eliminate', labels__category='lean')
        
        # Filter by assignee
        if search_form.cleaned_data.get('assignee'):
            tasks = tasks.filter(assigned_to=search_form.cleaned_data['assignee'])
        
        # Filter by search term (in title or description)
        if search_form.cleaned_data.get('search_term'):
            search_term = search_form.cleaned_data['search_term']
            tasks = tasks.filter(
                Q(title__icontains=search_term) | 
                Q(description__icontains=search_term)
            )
    
    # Get all labels for this board
    labels = TaskLabel.objects.filter(board=board)
    
    # Get board members - all members of this board
    board_member_ids = board.members.values_list('id', flat=True)
    board_member_profiles = UserProfile.objects.filter(user_id__in=board_member_ids)
    
    # For adding new members: show all non-demo users who aren't on the board yet
    available_org_members = UserProfile.objects.exclude(
        user_id__in=board_member_ids
    ).exclude(
        user__username__icontains='_demo'
    ).exclude(
        organization__is_demo=True
    ).select_related('user')
    
    # Get linked wiki pages for this board
    from wiki.models import WikiLink
    wiki_links = WikiLink.objects.filter(board=board).select_related('wiki_page')
    
    # Get scope creep data
    from kanban.models import ScopeCreepAlert
    from kanban.utils.scope_analysis import refresh_active_alerts
    scope_status = board.get_current_scope_status()
    # Refresh any stale alert metrics so the banner always matches live scope
    refresh_active_alerts(board, scope_status)
    active_scope_alerts = ScopeCreepAlert.objects.filter(
        board=board,
        status__in=['active', 'acknowledged']
    ).order_by('-detected_at')[:3]  # Show top 3 active alerts
    
    # Get permission information for UI feedback
    from kanban.permission_utils import (
        get_user_board_membership, 
        get_column_permissions_for_user
    )
    
    user_membership = get_user_board_membership(request.user, board)
    user_role_name = user_membership.role.name if user_membership else 'Viewer'
    
    # Get column permissions for visual feedback
    column_permissions = {}
    for column in columns:
        perms = get_column_permissions_for_user(request.user, column)
        if perms:
            column_permissions[column.id] = perms
    
    # All restrictions removed - all authenticated users have full access
    can_manage_members = True
    can_edit_board = True
    can_create_tasks = True

    # Invitation permission: board creator or site admin
    can_manage_invites = (
        board.created_by == request.user or
        getattr(getattr(request.user, 'profile', None), 'is_admin', False)
    )

    return render(request, 'kanban/board_detail.html', {
        'board': board,
        'columns': columns,
        'tasks': tasks,
        'labels': labels,
        'board_member_profiles': board_member_profiles,
        'available_org_members': available_org_members,
        'now': timezone.now(),  # Used for due date comparison
        'search_form': search_form,  # Add the search form to the context
        'any_filter_active': any_filter_active,  # Add the flag for active filters
        'wiki_links': wiki_links,  # Add linked wiki pages
        'scope_status': scope_status,  # Add scope tracking data
        'active_scope_alerts': active_scope_alerts,  # Add active alerts
        'is_demo_board': is_demo_board,  # Flag to show demo mode banner
        'user_role_name': user_role_name,  # User's role on this board
        'column_permissions': column_permissions,  # Column-level restrictions
        'can_manage_members': can_manage_members,  # Permission flags for UI
        'can_edit_board': can_edit_board,
        'can_create_tasks': can_create_tasks,
        'can_manage_invites': can_manage_invites,  # For invite button visibility
    })

def task_detail(request, task_id):
    from django.db.models import Prefetch
    from kanban.audit_utils import log_model_change, AuditLogContext
    from kanban.utils.demo_settings import SIMPLIFIED_MODE
    
    # Optimize query with select_related and prefetch_related to avoid N+1 queries
    task = get_object_or_404(
        Task.objects.select_related(
            'column',
            'column__board',
            'column__board__organization',
            'assigned_to',
            'assigned_to__profile',
            'created_by',
            'created_by__profile',
            'parent_task'
        ).prefetch_related(
            'labels',
            'subtasks',
            'related_tasks',
            'dependencies',
            Prefetch('file_attachments', queryset=TaskFile.objects.filter(deleted_at__isnull=True).select_related('uploaded_by'))
        ),
        id=task_id
    )
    board = task.column.board

    # Milestones have their own dedicated detail page
    if task.item_type == 'milestone':
        next_url = request.GET.get('next', '')
        qs = f'?next={next_url}' if next_url else ''
        return redirect(f'/milestones/{task.id}/{qs}')

    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task, board=board)
        if form.is_valid():
            # Track changes automatically
            with AuditLogContext(task, request.user, request, 'task.updated'):
                task = form.save(commit=False)
                # Store who made the change for signal handler
                task._changed_by_user = request.user
                task.save()
                # Save many-to-many relationships (dependencies, labels, related_tasks)
                form.save_m2m()
            
            # Record activity
            TaskActivity.objects.create(
                task=task,
                user=request.user,
                activity_type='updated',
                description=f"Updated task details for '{task.title}'"
            )
            
            messages.success(request, 'Task updated successfully!')
            
            # Redirect to the referring page if provided, otherwise back to task detail
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('task_detail', task_id=task.id)
    else:
        form = TaskForm(instance=task, board=board)
    
    # Handle comments
    if request.method == 'POST' and 'content' in request.POST:
        # All restrictions removed - all authenticated users can add comments
        
        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.task = task
            # For demo mode, use a demo user or allow anonymous
            if request.user.is_authenticated:
                comment.user = request.user
            else:
                # For demo sessions, assign to the demo admin user
                from django.contrib.auth.models import User
                comment.user = User.objects.filter(username='demo_admin').first()
            comment.save()
            
            # Log comment creation (only for authenticated users)
            if request.user.is_authenticated:
                log_model_change('comment.created', comment, request.user, request)
                
                # Record activity
                TaskActivity.objects.create(
                    task=task,
                    user=request.user,
                    activity_type='commented',
                    description=f"Commented on '{task.title}'"
                )
            
            messages.success(request, 'Comment added successfully!')
            return redirect('task_detail', task_id=task.id)
    else:
        comment_form = CommentForm()
    
    # Get all comments for this task with optimized queries
    comments = Comment.objects.filter(task=task).select_related('user', 'user__profile').order_by('-created_at')
    
    # Get all activities for this task with optimized queries
    activities = TaskActivity.objects.filter(task=task).select_related('user', 'user__profile').order_by('-created_at')
    
    # Get stakeholders involved in this task with optimized queries
    stakeholders = StakeholderTaskInvolvement.objects.filter(task=task).select_related(
        'stakeholder'
    ).order_by('stakeholder__name')
    
    # Get board stakeholders for AI recommendations (when no task stakeholders assigned)
    board_stakeholders = ProjectStakeholder.objects.filter(board=board).order_by('name')
    
    # Get linked wiki pages for this task
    from wiki.models import WikiLink
    wiki_links = WikiLink.objects.filter(task=task).select_related('wiki_page')
    
    # Get task completion prediction if available
    prediction_data = None
    if task.progress < 100:
        from kanban.utils.task_prediction import predict_task_completion_date
        from kanban.utils.task_prediction import update_task_prediction
        
        # Auto-generate prediction if task has start date but no prediction yet
        if task.start_date and not task.predicted_completion_date:
            try:
                prediction = update_task_prediction(task)
                if prediction:
                    # Format the prediction for template use
                    is_likely_late = False
                    if task.due_date:
                        is_likely_late = prediction['predicted_date'] > task.due_date
                    
                    prediction_data = {
                        'predicted_date': prediction['predicted_date'],
                        'confidence': prediction['confidence'],
                        'confidence_percentage': int(prediction['confidence'] * 100),
                        'confidence_interval_days': prediction['confidence_interval_days'],
                        'based_on_tasks': prediction['based_on_tasks'],
                        'similar_tasks': prediction.get('similar_tasks', []),
                        'factors': prediction['factors'],
                        'early_date': prediction['early_date'],
                        'late_date': prediction['late_date'],
                        'prediction_method': prediction['prediction_method'],
                        'is_likely_late': is_likely_late
                    }
            except Exception as e:
                logger.warning(f"Failed to generate initial prediction for task {task.id}: {e}")
        
        # Check if prediction is stale (older than 24 hours) and update if needed
        elif task.predicted_completion_date and (
            not task.last_prediction_update or 
            (timezone.now() - task.last_prediction_update > timedelta(hours=24))
        ):
            try:
                prediction = update_task_prediction(task)
                if prediction:
                    # Format the prediction for template use
                    is_likely_late = False
                    if task.due_date:
                        is_likely_late = prediction['predicted_date'] > task.due_date
                    
                    prediction_data = {
                        'predicted_date': prediction['predicted_date'],
                        'confidence': prediction['confidence'],
                        'confidence_percentage': int(prediction['confidence'] * 100),
                        'confidence_interval_days': prediction['confidence_interval_days'],
                        'based_on_tasks': prediction['based_on_tasks'],
                        'similar_tasks': prediction.get('similar_tasks', []),
                        'factors': prediction['factors'],
                        'early_date': prediction['early_date'],
                        'late_date': prediction['late_date'],
                        'prediction_method': prediction['prediction_method'],
                        'is_likely_late': is_likely_late
                    }
            except Exception as e:
                logger.warning(f"Failed to update prediction for task {task.id}: {e}")
        
        # Use existing prediction
        if not prediction_data and task.predicted_completion_date:
            is_likely_late = False
            if task.due_date:
                is_likely_late = task.predicted_completion_date > task.due_date
            
            prediction_data = {
                'predicted_date': task.predicted_completion_date,
                'confidence': task.prediction_confidence,
                'confidence_percentage': int(task.prediction_confidence * 100),
                'confidence_interval_days': task.prediction_metadata.get('confidence_interval_days', 0),
                'based_on_tasks': task.prediction_metadata.get('based_on_tasks', 0),
                'similar_tasks': task.prediction_metadata.get('similar_tasks', []),
                'factors': task.prediction_metadata.get('factors', {}),
                'early_date': task.prediction_metadata.get('early_date'),
                'late_date': task.prediction_metadata.get('late_date'),
                'prediction_method': task.prediction_metadata.get('prediction_method', 'unknown'),
                'is_likely_late': is_likely_late
            }
    
    # Get total time logged on this task
    from kanban.budget_models import TimeEntry
    total_time_logged = TimeEntry.objects.filter(task=task).aggregate(
        total=Sum('hours_spent')
    )['total'] or 0
    
    return render(request, 'kanban/task_detail.html', {
        'task': task,
        'board': board,
        'form': form,
        'comment_form': comment_form,
        'comments': comments,
        'activities': activities,
        'stakeholders': stakeholders,
        'board_stakeholders': board_stakeholders,
        'wiki_links': wiki_links,
        'prediction': prediction_data,
        'total_time_logged': total_time_logged,
        'is_demo_mode': False,
        'is_demo_board': False,
    })

@login_required
def create_task(request, board_id, column_id=None):
    from kanban.audit_utils import log_model_change

    board = get_object_or_404(Board, id=board_id)

    # Demo mode flags — always False for authenticated users on this view
    is_demo_mode = False
    is_demo_board = getattr(board, 'is_demo', False)
    
    if column_id:
        column = get_object_or_404(Column, id=column_id, board=board)
    else:
        # Try to get "To Do" column first, otherwise get the first available column
        column = Column.objects.filter(
            board=board, 
            name__iregex=r'^(to do|todo)$'
        ).first()
        
        if not column:
            # If no "To Do" column exists, get the first column
            column = Column.objects.filter(board=board).order_by('position').first()
        
        # If still no column exists, this is an error state
        if not column:
            messages.error(request, 'No columns exist on this board. Please create a column first.')
            return redirect('board_detail', board_id=board.id)
    
    if request.method == 'POST':
        form = TaskForm(request.POST, board=board)
        
        # Check if this is a confirmed duplicate submission
        confirm_duplicate = request.POST.get('confirm_duplicate', 'false') == 'true'
        
        if form.is_valid() or (not form.is_valid() and confirm_duplicate and hasattr(form, '_duplicate_tasks')):
            # If there are duplicate warnings but user confirmed, clear non-field errors
            if confirm_duplicate and hasattr(form, '_duplicate_tasks'):
                # Remove duplicate warning errors
                if hasattr(form, '_errors') and None in form._errors:
                    form._errors[None] = [err for err in form._errors[None] if err.code != 'duplicate_warning']
                    if not form._errors[None]:
                        del form._errors[None]
                # Re-validate without duplicate check
                if form.is_valid():
                    pass  # Continue to save
                else:
                    # Still has other errors, show form again
                    pass
            
            if form.is_valid():
                task = form.save(commit=False)

                # Set the column for the task
                if column:
                    task.column = column
                else:
                    # If no column specified, use the first column of the board
                    task.column = board.columns.first()

                # For demo mode, use demo_admin if user is anonymous
                if request.user.is_authenticated:
                    task.created_by = request.user
                else:
                    # For demo sessions, assign to the demo admin user
                    from django.contrib.auth.models import User
                    task.created_by = User.objects.filter(username='demo_admin').first()
                # Set position to be at the end of the column
                last_position = Task.objects.filter(column=column).order_by('-position').first()
                task.position = (last_position.position + 1) if last_position else 0
                
                # If in demo mode (via session OR demo board), track this task as user-created
                # This ensures proper cleanup after 48 hours
                effective_demo_mode = is_demo_mode or is_demo_board
                if effective_demo_mode:
                    browser_fingerprint = request.session.get('browser_fingerprint')
                    if browser_fingerprint:
                        task.created_by_session = browser_fingerprint
                    elif request.session.session_key:
                        task.created_by_session = request.session.session_key
                    else:
                        # Fallback: generate a unique identifier if session tracking failed
                        import uuid
                        task.created_by_session = f"demo-task-{uuid.uuid4().hex[:16]}"
                    # Explicitly mark as NOT seed data
                    task.is_seed_demo_data = False
                
                # Store who created the task for signal handler
                task._changed_by_user = task.created_by
                task.save()
                # Save many-to-many relationships
                form.save_m2m()
                
                # Record activity (only for authenticated users)
                if request.user.is_authenticated:
                    TaskActivity.objects.create(
                        task=task,
                        user=request.user,
                        activity_type='created',
                        description=f"Created task '{task.title}'"
                    )
                
                # Log to audit trail (only for authenticated users)
                if request.user.is_authenticated:
                    log_model_change('task.created', task, request.user, request)
                
                messages.success(request, 'Task created successfully!')
                return redirect('board_detail', board_id=board.id)
        
        # If form has duplicate tasks, add them to context for display
        duplicate_tasks = getattr(form, '_duplicate_tasks', None)
    else:
        form = TaskForm(board=board)
        duplicate_tasks = None
    
    return render(request, 'kanban/create_task.html', {
        'form': form,
        'board': board,
        'column': column,
        'duplicate_tasks': duplicate_tasks
    })

def delete_task(request, task_id):
    from kanban.audit_utils import log_audit
    
    task = get_object_or_404(Task, id=task_id)
    board = task.column.board
    
    # Require authentication
    if not request.user.is_authenticated:
        from django.contrib.auth.views import redirect_to_login
        return redirect_to_login(request.get_full_path())
    
    # All restrictions removed - all authenticated users can delete tasks
    
    if request.method == 'POST':
        board_id = task.column.board.id
        task_title = task.title
        task_id = task.id
        
        # Log before deletion
        log_audit('task.deleted', user=request.user, request=request,
                  object_type='task', object_id=task_id, object_repr=task_title,
                  board_id=board_id)
        
        task.delete()
        messages.success(request, 'Task deleted successfully!')
        return redirect('board_detail', board_id=board_id)
    
    return render(request, 'kanban/delete_task.html', {'task': task})

def create_column(request, board_id):
    from kanban.audit_utils import log_model_change
    
    board = get_object_or_404(Board, id=board_id)
    
    # Require authentication
    if not request.user.is_authenticated:
        from django.contrib.auth.views import redirect_to_login
        return redirect_to_login(request.get_full_path())
    
    # All restrictions removed - all authenticated users can create columns
    
    if request.method == 'POST':
        form = ColumnForm(request.POST)
        if form.is_valid():
            column = form.save(commit=False)
            column.board = board
            # Set position to be at the end
            last_position = Column.objects.filter(board=board).order_by('-position').first()
            column.position = (last_position.position + 1) if last_position else 0
            column.save()
            
            # Log to audit trail
            log_model_change('column.created', column, request.user, request)
            
            messages.success(request, 'Column created successfully!')
            return redirect('board_detail', board_id=board.id)
    else:
        form = ColumnForm()
    
    return render(request, 'kanban/create_column.html', {
        'form': form,
        'board': board
    })

def update_column(request, column_id):
    """Update/rename a column"""
    from kanban.audit_utils import log_model_change
    
    column = get_object_or_404(Column, id=column_id)
    board = column.board
    
    # Require authentication
    if not request.user.is_authenticated:
        from django.contrib.auth.views import redirect_to_login
        return redirect_to_login(request.get_full_path())
    
    # All restrictions removed - all authenticated users can edit columns
    
    if request.method == 'POST':
        new_name = request.POST.get('name', '').strip()
        if new_name:
            old_name = column.name
            column.name = new_name
            column.save()
            
            # Log to audit trail
            log_model_change('column.updated', column, request.user if request.user.is_authenticated else None, request)
            
            messages.success(request, f'Column renamed from "{old_name}" to "{new_name}"!')
        else:
            messages.error(request, 'Column name cannot be empty.')
        
        return redirect('board_detail', board_id=board.id)
    
    # For GET requests, return JSON data
    return JsonResponse({
        'id': column.id,
        'name': column.name
    })

@login_required
def create_label(request, board_id):
    board = get_object_or_404(Board, id=board_id)
    
    # Check if user has access to this board
    # Access restriction removed - all authenticated users can access

    pass  # Original: board membership check removed
    
    if request.method == 'POST':
        form = TaskLabelForm(request.POST)
        if form.is_valid():
            label = form.save(commit=False)
            label.board = board
            label.save()
            messages.success(request, 'Label created successfully!')
            return redirect('board_detail', board_id=board.id)
    else:
        form = TaskLabelForm()    
        return render(request, 'kanban/create_label.html', {
        'form': form,
        'board': board,
        'has_lean_labels': board.labels.filter(category='lean').exists(),
        'has_regular_labels': board.labels.filter(category='regular').exists()
    })

@login_required
def delete_label(request, label_id):
    label = get_object_or_404(TaskLabel, id=label_id)
    board = label.board
    
    # Check if user has access to this board
    # Access restriction removed - all authenticated users can access

    pass  # Original: board membership check removed
    
    # Delete the label
    label_name = label.name
    label.delete()
    messages.success(request, f'Label "{label_name}" has been deleted.')
    
    return redirect('create_label', board_id=board.id)

def board_analytics(request, board_id):
    """
    Board analytics dashboard
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Require authentication
    if not request.user.is_authenticated:
        from django.contrib.auth.views import redirect_to_login
        return redirect_to_login(request.get_full_path())
    
    # All restrictions removed - all authenticated users can view analytics
    # Demo mode removed - always False
    is_demo_mode = False
    is_demo_board = board.is_official_demo_board if hasattr(board, 'is_official_demo_board') else False
    
    # Get columns for this board
    columns = Column.objects.filter(board=board)
    
    # Get tasks by column (exclude milestones)
    tasks_by_column = []
    for column in columns:
        count = Task.objects.filter(column=column, item_type='task').count()
        tasks_by_column.append({
            'name': column.name,
            'count': count
        })
    
    # Get tasks by priority - convert QuerySet to list of dictionaries
    priority_queryset = Task.objects.filter(column__board=board, item_type='task').values('priority').annotate(
        count=Count('id')
    ).order_by('priority')
    
    tasks_by_priority = []
    for item in priority_queryset:
        # Convert priority codes to readable names
        priority_name = dict(Task.PRIORITY_CHOICES).get(item['priority'], item['priority'])
        tasks_by_priority.append({
            'priority': priority_name,
            'count': item['count']
        })
    
    # Get tasks by assigned user - convert QuerySet to list of dictionaries (exclude milestones)
    user_queryset = Task.objects.filter(column__board=board, item_type='task').values(
        'assigned_to__username'
    ).annotate(
        count=Count('id')
    ).order_by('-count')
    
    tasks_by_user = []
    for item in user_queryset:
        username = item['assigned_to__username'] or 'Unassigned'
        # Count completed tasks for this user based on progress = 100%
        completed_user_tasks = Task.objects.filter(
            column__board=board,
            item_type='task',
            assigned_to__username=item['assigned_to__username'],
            progress=100
        ).count()
        
        # Calculate completion percentage
        user_completion_rate = 0
        if item['count'] > 0:
            user_completion_rate = (completed_user_tasks / item['count']) * 100
            
        tasks_by_user.append({
            'username': username,
            'count': item['count'],
            'completed': completed_user_tasks,
            'completion_rate': int(user_completion_rate)
        })
    
    # Get completion rate over time (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    completed_tasks_queryset = TaskActivity.objects.filter(
        task__column__board=board,
        activity_type='moved',
        description__contains='Done',
        created_at__gte=thirty_days_ago
    ).values('created_at__date').annotate(
        count=Count('id')
    ).order_by('created_at__date')
    
    completed_tasks = []
    for item in completed_tasks_queryset:
        completed_tasks.append({
            'date': item['created_at__date'].strftime('%Y-%m-%d'),
            'count': item['count']
        })
    
    # Calculate productivity based on task progress (exclude milestones)
    total_tasks = Task.objects.filter(column__board=board, item_type='task').count()
    
    # Get all tasks and their progress values (exclude milestones)
    all_tasks = Task.objects.filter(column__board=board, item_type='task')
    
    # Count completed tasks based on progress percentage (100%) instead of column name
    completed_count = Task.objects.filter(
        column__board=board,
        item_type='task',
        progress=100
    ).count()
    
    # Calculate overall productivity based on completion rate (completed tasks / total tasks)
    productivity = 0
    if total_tasks > 0:
        productivity = (completed_count / total_tasks) * 100
    
    # Get tasks due soon (next 7 days) — exclude milestones
    today = timezone.now().date()
    upcoming_tasks = Task.objects.filter(
        column__board=board,
        item_type='task',
        due_date__isnull=False,
        due_date__date__gte=today,
        due_date__date__lte=today + timedelta(days=7)
    ).exclude(
        progress=100
    ).order_by('due_date')
    
    # Get overdue tasks (due date in the past and not completed) — exclude milestones
    overdue_tasks = Task.objects.filter(
        column__board=board,
        item_type='task',
        due_date__isnull=False,
        due_date__date__lt=today
    ).exclude(
        progress=100
    ).order_by('due_date')
    
    # Get count of overdue tasks
    overdue_count = overdue_tasks.count()
    
    # Lean Six Sigma Metrics (exclude milestones)
    # Get tasks by value added category
    value_added_count = Task.objects.filter(
        column__board=board,
        item_type='task',
        labels__name='Value-Added', 
        labels__category='lean'
    ).count()
    
    necessary_nva_count = Task.objects.filter(
        column__board=board,
        item_type='task',
        labels__name='Necessary NVA', 
        labels__category='lean'
    ).count()
    
    waste_count = Task.objects.filter(
        column__board=board,
        item_type='task',
        labels__name='Waste/Eliminate', 
        labels__category='lean'
    ).count()
    
    # Calculate value-added percentage
    total_categorized = value_added_count + necessary_nva_count + waste_count
    value_added_percentage = 0
    if total_categorized > 0:
        value_added_percentage = (value_added_count / total_categorized) * 100
      # Tasks by Lean Six Sigma category
    tasks_by_lean_category = [
        {'name': 'Value-Added', 'count': value_added_count, 'color': '#28a745'},
        {'name': 'Necessary NVA', 'count': necessary_nva_count, 'color': '#ffc107'},
        {'name': 'Waste/Eliminate', 'count': waste_count, 'color': '#dc3545'}
    ]
    
    # Calculate remaining tasks
    remaining_tasks = total_tasks - completed_count
    
    response = render(request, 'kanban/board_analytics.html', {
        'board': board,
        'columns': columns,
        'tasks': all_tasks,  # Add all tasks to the template context
        'tasks_by_column': tasks_by_column,  # Raw data for JSON encoding in template
        'tasks_by_priority': tasks_by_priority,  # Raw data for JSON encoding in template
        'tasks_by_user': tasks_by_user,  # Raw data for JSON encoding in template
        'completed_tasks': completed_tasks,  # Raw data for JSON encoding in template
        'tasks_by_lean_category': tasks_by_lean_category, # Raw data for JSON encoding in template
        'productivity': round(productivity, 1),
        'upcoming_tasks': upcoming_tasks,
        'overdue_tasks': overdue_tasks,  # Add overdue tasks
        'overdue_count': overdue_count,  # Add overdue count
        'total_tasks': total_tasks,
        'completed_count': completed_count,
        'remaining_tasks': remaining_tasks,  # Add remaining tasks count
        'now': timezone.now(),  # For comparing dates in the template
        # Lean Six Sigma metrics
        'value_added_percentage': round(value_added_percentage, 1),
        'total_categorized': total_categorized,
        'is_demo_mode': is_demo_mode,
        'is_demo_board': is_demo_board,
    })
    
    # Prevent caching of analytics data
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    
    return response

def gantt_chart(request, board_id):
    """Display Gantt chart view for a board"""
    from kanban.utils.demo_settings import SIMPLIFIED_MODE
    
    board = get_object_or_404(Board, id=board_id)
    
    # Require authentication
    if not request.user.is_authenticated:
        from django.contrib.auth.views import redirect_to_login
        return redirect_to_login(request.get_full_path())
    
    # All restrictions removed - all authenticated users can view Gantt chart
    # Demo mode removed - always False
    is_demo_mode = False
    is_demo_board = board.is_official_demo_board if hasattr(board, 'is_official_demo_board') else False
    
    # Get tasks for this board with dependencies prefetched for Gantt chart
    # Order by phase and id to maintain consistent task order regardless of date changes
    # This ensures tasks stay in their original position even after editing dates
    # Exclude milestones from the regular tasks queryset (milestones fetched separately)
    tasks = Task.objects.filter(column__board=board, item_type='task').select_related('column', 'assigned_to').prefetch_related('dependencies').order_by('phase', 'id')

    # Always load milestones separately so filters don't affect them
    milestones = Task.objects.filter(column__board=board, item_type='milestone').select_related('column').order_by('phase', 'id')

    # Process Gantt chart filters
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')
    assignee_filter = request.GET.get('assignee', '')
    
    # Apply search filter (search in title and description)
    if search_query:
        tasks = tasks.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )
    
    # Apply status filter (based on column name patterns)
    if status_filter:
        if status_filter == 'todo':
            # Tasks not in progress or done columns
            tasks = tasks.exclude(
                Q(column__name__icontains='progress') | 
                Q(column__name__icontains='done') | 
                Q(column__name__icontains='complete')
            )
        elif status_filter == 'in_progress':
            tasks = tasks.filter(column__name__icontains='progress')
        elif status_filter == 'done':
            tasks = tasks.filter(
                Q(column__name__icontains='done') | Q(column__name__icontains='complete')
            )
        elif status_filter == 'active':
            # Active = To Do + In Progress (exclude completed)
            tasks = tasks.exclude(
                Q(column__name__icontains='done') | Q(column__name__icontains='complete')
            )
    
    # Apply priority filter
    if priority_filter:
        tasks = tasks.filter(priority=priority_filter)
    
    # Apply assignee filter
    if assignee_filter:
        if assignee_filter == 'unassigned':
            tasks = tasks.filter(assigned_to__isnull=True)
        else:
            tasks = tasks.filter(assigned_to_id=assignee_filter)
    
    # Get unique assignees for filter dropdown
    assignees = User.objects.filter(
        assigned_tasks__column__board=board
    ).distinct().order_by('username')

    # Calculate phase timelines for phase-based Gantt chart view
    phases_data = {}
    has_phases = board.num_phases > 0 if hasattr(board, 'num_phases') else False

    if has_phases:
        import json
        from datetime import date

        for i in range(1, board.num_phases + 1):
            phase_name = f'Phase {i}'
            phase_tasks = tasks.filter(phase=phase_name)

            if phase_tasks.exists():
                # Get earliest start_date
                task_start_dates = list(phase_tasks.filter(
                    start_date__isnull=False
                ).values_list('start_date', flat=True))

                # Get latest due_date (from both tasks and milestones)
                task_due_dates = list(phase_tasks.filter(
                    due_date__isnull=False
                ).values_list('due_date', flat=True))

                # Convert datetime to date for comparison
                due_dates_as_date = [d.date() if hasattr(d, 'date') else d for d in task_due_dates]

                phases_data[phase_name] = {
                    'start': min(task_start_dates).isoformat() if task_start_dates else None,
                    'end': max(due_dates_as_date).isoformat() if due_dates_as_date else None,
                    'task_count': phase_tasks.count(),
                }
            else:
                phases_data[phase_name] = {
                    'start': None,
                    'end': None,
                    'task_count': 0,
                }

        # Convert to JSON for JavaScript consumption
        phases_data_json = json.dumps(phases_data)
    else:
        phases_data_json = '{}'

    # When any filter is active, the phases view should default to 'all tasks'
    # so individual matched task bars are visible (not hidden inside collapsed phase bars)
    any_filters_active = bool(search_query or status_filter or priority_filter or assignee_filter)

    context = {
        'board': board,
        'tasks': tasks,
        'milestones': milestones,
        'is_demo_board': is_demo_board,
        'is_demo_mode': is_demo_mode,
        'has_phases': has_phases,
        'phases_data_json': phases_data_json,
        'num_phases': board.num_phases if has_phases else 0,
        # Gantt filter context
        'search_query': search_query,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'assignee_filter': assignee_filter,
        'assignees': assignees,
        'priority_choices': Task.PRIORITY_CHOICES,
        'any_filters_active': any_filters_active,
    }

    return render(request, 'kanban/gantt_chart.html', context)


@login_required
def board_calendar(request, board_id):
    """
    Calendar view: shows all tasks with due dates laid out by month/week.
    Tasks with no due date are listed in a separate 'unscheduled' section.
    """
    board = get_object_or_404(Board, id=board_id)

    # Fetch all tasks that have a due date, ordered by due date
    tasks_with_dates = (
        Task.objects
        .filter(column__board=board, item_type='task', due_date__isnull=False)
        .select_related('column', 'assigned_to')
        .order_by('due_date')
    )

    tasks_without_dates = (
        Task.objects
        .filter(column__board=board, item_type='task', due_date__isnull=True)
        .select_related('column', 'assigned_to')
        .order_by('column__position', 'position')
    )

    # Build a simple serialisable list of events for FullCalendar (JS)
    import json as _json
    events = []
    for t in tasks_with_dates:
        color = {
            'urgent': '#dc3545',
            'high':   '#fd7e14',
            'medium': '#0d6efd',
            'low':    '#198754',
        }.get(t.priority, '#6c757d')

        due = t.due_date
        if hasattr(due, 'date'):
            due_str = due.date().isoformat()
        else:
            due_str = due.isoformat()

        events.append({
            'id': t.id,
            'title': t.title,
            'start': due_str,
            'url': f'/tasks/{t.id}/',
            'color': color,
            'extendedProps': {
                'column': t.column.name,
                'priority': t.get_priority_display(),
                'progress': t.progress,
                'assignee': t.assigned_to.get_full_name() or t.assigned_to.username if t.assigned_to else None,
            }
        })

    context = {
        'board': board,
        'tasks_without_dates': tasks_without_dates,
        'events_json': _json.dumps(events),
        'total_tasks': tasks_with_dates.count() + tasks_without_dates.count(),
        'scheduled_count': tasks_with_dates.count(),
        'unscheduled_count': tasks_without_dates.count(),
    }
    return render(request, 'kanban/calendar_view.html', context)


def add_gantt_milestone(request, board_id):
    """Create a new milestone (stored as a Task with item_type='milestone') from the Gantt chart."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    board = get_object_or_404(Board, id=board_id)

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    import json as _json
    from datetime import datetime, date as _date, time as _time

    try:
        data = _json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    phase = data.get('phase', '').strip()
    due_date_str = data.get('due_date', '').strip()
    status = data.get('status', 'upcoming').strip()
    position_after_task_id = data.get('position_after_task_id', None)

    if not name:
        return JsonResponse({'error': 'Milestone name is required'}, status=400)
    if not due_date_str:
        return JsonResponse({'error': 'Due date is required'}, status=400)

    try:
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)

    if status not in ('upcoming', 'completed'):
        status = 'upcoming'

    # Resolve position_after_task FK (must be a real task on this board)
    position_after_task = None
    if position_after_task_id:
        try:
            position_after_task = Task.objects.get(
                id=int(position_after_task_id), item_type='task', column__board=board
            )
        except (Task.DoesNotExist, ValueError):
            pass  # silently ignore invalid FK

    # Find a column to attach the milestone to (prefer Backlog, then first column)
    column = (
        Column.objects.filter(board=board, name__icontains='backlog').first()
        or Column.objects.filter(board=board).order_by('position').first()
    )
    if not column:
        return JsonResponse({'error': 'Board has no columns'}, status=400)

    # Milestones are single-day bar items on the Gantt chart (start=end)
    milestone = Task.objects.create(
        title=name,
        description=description,
        column=column,
        created_by=request.user,
        start_date=due_date,
        due_date=datetime.combine(due_date, _time.min),  # DateTimeField expects datetime
        phase=phase if phase else None,
        priority='medium',
        progress=100 if status == 'completed' else 0,
        item_type='milestone',
        milestone_status=status,
        position_after_task=position_after_task,
    )

    return JsonResponse({
        'success': True,
        'milestone': {
            'id': milestone.id,
            'name': milestone.title,
            'due_date': due_date_str,
            'phase': milestone.phase or '',
            'status': milestone.milestone_status,
            'position_after_task_id': milestone.position_after_task_id or '',
        }
    })


def delete_gantt_milestone(request, board_id, task_id):
    """Delete a milestone from the Gantt chart."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    task = get_object_or_404(Task, id=task_id, item_type='milestone', column__board_id=board_id)
    task.delete()

    # AJAX callers (Gantt JS) expect JSON; regular form submissions get a redirect
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
              'application/json' in request.headers.get('Accept', '')
    if is_ajax:
        return JsonResponse({'success': True})

    # Regular form delete (from milestone_detail page)
    next_url = request.POST.get('next', '')
    messages.success(request, 'Milestone deleted.')
    if next_url:
        return redirect(next_url)
    return redirect('gantt_chart', board_id=board_id)


def milestone_detail(request, milestone_id):
    """Simple view for Gantt chart milestones (item_type='milestone').
    Shows only: name, description, phase, due date, status, and who created it.
    """
    milestone = get_object_or_404(
        Task.objects.select_related('column__board', 'created_by'),
        id=milestone_id,
        item_type='milestone'
    )
    board = milestone.column.board
    next_url = request.GET.get('next', '')

    if request.method == 'POST':
        from datetime import datetime as _dt
        import json as _json

        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        phase = request.POST.get('phase', '').strip()
        due_date_str = request.POST.get('due_date', '').strip()
        status = request.POST.get('status', 'upcoming').strip()
        position_after_id = request.POST.get('position_after_task', '').strip()
        next_url_post = request.POST.get('next', next_url)

        errors = []
        if not name:
            errors.append('Name is required.')
        if not due_date_str:
            errors.append('Due date is required.')

        due_date = None
        if due_date_str:
            try:
                due_date = _dt.strptime(due_date_str, '%Y-%m-%d').date()
            except ValueError:
                errors.append('Invalid date format.')

        if status not in ('upcoming', 'completed'):
            status = 'upcoming'

        if not errors and due_date:
            from datetime import time as _time_cls, datetime as _dt2
            # Resolve position_after FK
            position_after_task = None
            if position_after_id:
                try:
                    position_after_task = Task.objects.get(
                        id=int(position_after_id), item_type='task', column__board=board
                    )
                except (Task.DoesNotExist, ValueError):
                    pass
            milestone.title = name
            milestone.description = description
            milestone.phase = phase if phase else None
            milestone.start_date = due_date
            milestone.due_date = _dt2.combine(due_date, _time_cls.min)
            milestone.milestone_status = status
            milestone.progress = 100 if status == 'completed' else 0
            milestone.position_after_task = position_after_task
            milestone.save()
            messages.success(request, 'Milestone updated successfully!')
            if next_url_post:
                return redirect(next_url_post)
            return redirect('milestone_detail', milestone_id=milestone.id)
        else:
            for err in errors:
                messages.error(request, err)

    # Build phase choices and board tasks for dropdowns
    phase_choices = []
    if hasattr(board, 'num_phases') and board.num_phases > 0:
        phase_choices = [f'Phase {i}' for i in range(1, board.num_phases + 1)]

    board_tasks = Task.objects.filter(
        column__board=board, item_type='task'
    ).select_related('column').order_by('phase', 'id')

    context = {
        'milestone': milestone,
        'board': board,
        'next_url': next_url,
        'phase_choices': phase_choices,
        'board_tasks': board_tasks,
    }
    return render(request, 'kanban/milestone_detail.html', context)


def move_task(request):
    """
    Move a task to a different column via drag-and-drop.
    Supports both authenticated users and demo mode (including anonymous users).
    """
    from kanban.audit_utils import log_audit
    
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        data = json.loads(request.body)
        task_id = data.get('taskId')
        column_id = data.get('columnId')
        position = data.get('position', 0)
        
        task = get_object_or_404(Task, id=task_id)
        new_column = get_object_or_404(Column, id=column_id)
        board = new_column.board
        
        # Require authentication
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        # All restrictions removed - all authenticated users can move tasks
        
        old_column = task.column
        task.column = new_column
        task.position = position
        
        # Auto-update progress to 100% when moved to a "Done" or "Complete" column
        column_name_lower = new_column.name.lower()
        if 'done' in column_name_lower or 'complete' in column_name_lower:
            task.progress = 100
        
        task.save()
        
        # Record activity (only for authenticated users)
        if request.user.is_authenticated:
            TaskActivity.objects.create(
                task=task,
                user=request.user,
                activity_type='moved',
                description=f"Moved task '{task.title}' from '{old_column.name}' to '{new_column.name}'"
            )
            
            # Log to audit trail
            log_audit('task.moved', user=request.user, request=request,
                      object_type='task', object_id=task.id, object_repr=task.title,
                      board_id=new_column.board.id,
                      changes={'column': {'old': old_column.name, 'new': new_column.name}})
            
            # If progress was set to 100% automatically, record that too
            column_name_lower = new_column.name.lower()
            if ('done' in column_name_lower or 'complete' in column_name_lower) and task.progress == 100:
                TaskActivity.objects.create(
                    task=task,
                    user=request.user,
                    activity_type='updated',
                    description=f"Automatically updated progress for '{task.title}' to 100% ({new_column.name})"
                )
        
        # Reorder tasks in the column
        tasks_to_reorder = Task.objects.filter(column=new_column).exclude(id=task_id)
        for i, t in enumerate(tasks_to_reorder):
            new_position = i
            if i >= position:
                new_position = i + 1
            t.position = new_position
            t.save()
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def add_board_member(request, board_id):
    board = get_object_or_404(Board, id=board_id)
    
    # All restrictions removed - all authenticated users can add members
    
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                # Check if user is in the same organization (if both have orgs)
                user_has_same_org = True
                if hasattr(user, 'profile') and hasattr(request.user, 'profile'):
                    if user.profile.organization and request.user.profile.organization:
                        user_has_same_org = user.profile.organization == request.user.profile.organization
                
                if user_has_same_org:
                    # Check if this is a demo board
                    demo_org_names = ['Demo - Acme Corporation']
                    is_demo_board = board.organization and board.organization.name in demo_org_names
                    
                    if is_demo_board:
                        # For demo boards: add user to ALL boards in this demo organization
                        # This maintains organization-level access consistency
                        demo_boards = Board.objects.filter(organization=board.organization)
                        added_count = 0
                        for demo_board in demo_boards:
                            if user not in demo_board.members.all():
                                demo_board.members.add(user)
                                added_count += 1
                        
                        if added_count > 0:
                            messages.success(request, f'{user.username} added to {added_count} demo board(s) successfully!')
                        else:
                            messages.info(request, f'{user.username} is already a member of all demo boards.')
                    else:
                        # For regular boards: add user to this board only
                        if user not in board.members.all():
                            board.members.add(user)
                            messages.success(request, f'{user.username} added to the board successfully!')
                        else:
                            messages.info(request, f'{user.username} is already a member of this board.')
                else:
                    messages.error(request, 'You can only add members from your organization.')
            except User.DoesNotExist:
                messages.error(request, 'User not found.')
            except UserProfile.DoesNotExist:
                messages.error(request, 'User does not have a profile.')
        else:
            messages.error(request, 'No user selected.')
    
    return redirect('board_detail', board_id=board.id)

@login_required
def remove_board_member(request, board_id, user_id):
    board = get_object_or_404(Board, id=board_id)
    user_to_remove = get_object_or_404(User, id=user_id)
    
    # Check if user has permission to remove members
    # Only board creator, org admins, and org creator can remove members
    user_profile = getattr(request.user, 'profile', None)
    has_permission = (
        board.created_by == request.user or  # Board creator
        (user_profile and user_profile.is_admin) or  # Organization admin
        (user_profile and board.organization and request.user == board.organization.created_by)  # Organization creator
    )
    
    # Get the redirect destination (manage_board_members if came from there, else board_detail)
    referer = request.META.get('HTTP_REFERER', '')
    redirect_to_manage = 'manage' in referer
    
    if not has_permission:
        messages.error(request, "You don't have permission to remove members from this board.")
        if redirect_to_manage:
            return redirect('manage_board_members', board_id=board.id)
        return redirect('board_detail', board_id=board.id)
    
    # Don't allow removing the board creator
    if user_to_remove == board.created_by:
        messages.error(request, "You cannot remove the board creator.")
        if redirect_to_manage:
            return redirect('manage_board_members', board_id=board.id)
        return redirect('board_detail', board_id=board.id)
    
    # Check if user is actually a member of the board
    if user_to_remove not in board.members.all():
        messages.error(request, "This user is not a member of the board.")
        if redirect_to_manage:
            return redirect('manage_board_members', board_id=board.id)
        return redirect('board_detail', board_id=board.id)
    
    # Remove the member
    board.members.remove(user_to_remove)
    messages.success(request, f'{user_to_remove.username} has been removed from the board.')
    
    if redirect_to_manage:
        return redirect('manage_board_members', board_id=board.id)
    return redirect('board_detail', board_id=board.id)

@login_required
def delete_board(request, board_id):
    board = get_object_or_404(Board, id=board_id)
    
    # Delete the board
    if request.method == 'POST':
        board_name = board.name
        board.delete()
        messages.success(request, f'Board "{board_name}" has been deleted.')
        return redirect('board_list')
    
    return redirect('board_detail', board_id=board_id)

@login_required
def organization_boards(request):
    try:
        profile = request.user.profile
        organization = profile.organization
        
        # Get all boards for this organization, even if user is not a member
        # EXCLUDE demo boards - demo environment is isolated
        demo_org_names = ['Demo - Acme Corporation']
        all_org_boards = Board.objects.filter(
            organization=organization
        ).exclude(
            organization__name__in=demo_org_names
        )
        
        # Determine which boards the user is a member of
        user_boards = Board.objects.filter(
            Q(organization=organization) & 
            (Q(created_by=request.user) | Q(members=request.user))
        ).exclude(
            organization__name__in=demo_org_names
        ).distinct()
        
        # Create a list to track which boards the user is a member of
        user_board_ids = user_boards.values_list('id', flat=True)
        
        return render(request, 'kanban/organization_boards.html', {
            'all_org_boards': all_org_boards,
            'user_board_ids': user_board_ids,
            'organization': organization
        })
    except UserProfile.DoesNotExist:
        return redirect('organization_choice')

@login_required
def join_board(request, board_id):
    """Allow users to join boards they have access to"""
    board = get_object_or_404(Board, id=board_id)
    
    # MVP Mode: Users can join any board they can access
    # Access restriction removed - no organization check needed
    
    # Check if user is already a member
    if request.user in board.members.all() or board.created_by == request.user:
        messages.info(request, f"You are already a member of the board '{board.name}'.")
    else:
        # Add user to board members
        board.members.add(request.user)
        messages.success(request, f"You've successfully joined the board '{board.name}'!")
    
    return redirect('board_detail', board_id=board.id)

@login_required
def move_column(request, column_id, direction):
    """
    Move a column left or right in the board sequence based on its position
    """
    column = get_object_or_404(Column, id=column_id)
    board = column.board
    
    # Check if user has access to this board
    # Access restriction removed - all authenticated users can access

    pass  # Original: board membership check removed
    
    # Get all columns in order of position
    columns = list(Column.objects.filter(board=board).order_by('position'))
    current_index = next((i for i, col in enumerate(columns) if col.id == column.id), -1)
    
    if current_index == -1:
        messages.error(request, "Could not find the column position.")
        return redirect('board_detail', board_id=board.id)
    
    # Determine target position based on direction
    if direction == 'left' and current_index > 0:
        # Move column to the left
        target_index = current_index - 1
    elif direction == 'right' and current_index < len(columns) - 1:
        # Move column to the right
        target_index = current_index + 1
    else:
        # Can't move further in that direction
        messages.info(request, f"Cannot move column {direction}.")
        return redirect('board_detail', board_id=board.id)
    
    # Instead of just swapping positions, we'll reorder all columns properly
    if target_index != current_index:
        # Remove column from current position
        moved_column = columns.pop(current_index)
        # Insert column at new position
        columns.insert(target_index, moved_column)
        
        # Update all column positions
        for i, col in enumerate(columns):
            if col.position != i:
                col.position = i
                col.save()
        
        messages.success(request, f"Column '{column.name}' moved {direction}.")
    
    return redirect('board_detail', board_id=board.id)

@login_required
def reorder_columns(request):
    """
    Handle AJAX request to reorder columns via drag and drop.
    """
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        data = json.loads(request.body)
        column_id = data.get('columnId')
        new_position = data.get('position', 0)
        board_id = data.get('boardId')
        
        column = get_object_or_404(Column, id=column_id)
        board = get_object_or_404(Board, id=board_id)
        
        # Get all columns in order
        columns = list(Column.objects.filter(board=board).order_by('position'))
        
        # Find the column in the list
        current_index = next((i for i, col in enumerate(columns) if col.id == column.id), -1)
        
        if current_index == -1:
            return JsonResponse({'error': 'Column not found'}, status=400)
        
        # Remove column from current position and insert at new position
        moved_column = columns.pop(current_index)
        columns.insert(new_position, moved_column)
        
        # Update all column positions
        for i, col in enumerate(columns):
            if col.position != i:
                col.position = i
                col.save()
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

def reorder_multiple_columns(request):
    """
    Handle AJAX request to reorder multiple columns at once via the index-based approach.
    Supports both authenticated users and demo mode (including anonymous users).
    """
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            data = json.loads(request.body)
            columns_data = data.get('columns', [])
            board_id = data.get('boardId')
            
            # Log for debugging
            print(f"[reorder_multiple_columns] Received board_id: {board_id}")
            print(f"[reorder_multiple_columns] Columns data: {columns_data}")
            
            if not board_id:
                print("[reorder_multiple_columns] ERROR: Board ID is missing")
                return JsonResponse({'error': 'Board ID is required'}, status=400)
            
            board = get_object_or_404(Board, id=board_id)
            
            # Simple authentication check only - no board-level access restrictions
            if not request.user.is_authenticated:
                print("[reorder_multiple_columns] ERROR: User not authenticated")
                return JsonResponse({'error': 'Authentication required'}, status=401)
            
            # Create a dictionary to map column_id to position
            # Handle both string and int column IDs
            position_map = {}
            for item in columns_data:
                col_id = str(item.get('columnId', ''))
                position = item.get('position', 0)
                position_map[col_id] = position
            
            # Get all columns for this board
            db_columns = list(Column.objects.filter(board=board))
            
            # Update positions based on the map
            for column in db_columns:
                col_id_str = str(column.id)
                if col_id_str in position_map:
                    column.position = position_map[col_id_str]
            
            # Sort by the new positions and reassign sequentially to ensure no gaps
            sorted_columns = sorted(db_columns, key=lambda col: col.position)
            for index, column in enumerate(sorted_columns):
                column.position = index
                column.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Columns rearranged successfully'
            })
            
        except json.JSONDecodeError as e:
            print(f"[reorder_multiple_columns] JSON Decode Error: {str(e)}")
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            print(f"[reorder_multiple_columns] Exception: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def delete_column(request, column_id):
    """Delete a column and all of its tasks"""
    column = get_object_or_404(Column, id=column_id)
    board = column.board
    
    # Check if user has access to this board
    # Access restriction removed - all authenticated users can access

    pass  # Original: board membership check removed
    
    # Prevent deletion of "To Do" column as it's required for task creation
    if column.name.lower() in ['to do', 'todo']:
        messages.error(request, 'Cannot delete the "To Do" column as it is required for creating new tasks.')
        return redirect('board_detail', board_id=board.id)
    
    if request.method == 'POST':
        # Store column name for success message
        column_name = column.name
        
        # Delete the column (will cascade delete all tasks in this column)
        column.delete()
        
        # Reorder remaining columns to ensure sequential positions
        remaining_columns = Column.objects.filter(board=board).order_by('position')
        for index, col in enumerate(remaining_columns):
            if col.position != index:
                col.position = index
                col.save()
                
        messages.success(request, f'Column "{column_name}" and its tasks have been deleted.')
        return redirect('board_detail', board_id=board.id)
    
    return render(request, 'kanban/delete_column.html', {
        'column': column,
        'board': board
    })

@login_required
def update_task_progress(request, task_id):
    """
    Update the progress percentage of a task through an AJAX request.
    Expects 'direction' parameter: 'increase' or 'decrease'.
    Increases or decreases by 10% increments.
    """
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            task = get_object_or_404(Task, id=task_id)
            board = task.column.board
            
            data = json.loads(request.body)
            direction = data.get('direction')
            
            # Update progress based on direction
            if direction == 'increase':
                # Ensure we don't go above 100%
                task.progress = min(100, task.progress + 10)
            elif direction == 'decrease':
                # Ensure we don't go below 0%
                task.progress = max(0, task.progress - 10)
            else:
                return JsonResponse({'error': 'Invalid direction parameter'}, status=400)
            
            # Save the updated task
            task.save()
            
            # Record activity
            TaskActivity.objects.create(
                task=task,
                user=request.user,
                activity_type='updated',
                description=f"Updated progress for '{task.title}' to {task.progress}%"
            )
            
            # Return the updated progress
            return JsonResponse({
                'success': True,
                'progress': task.progress,
                'colorClass': get_progress_color_class(task.progress)
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

def get_progress_color_class(progress):
    """Helper function to determine the progress bar color class based on percentage"""
    if progress < 30:
        return 'bg-danger'
    elif progress < 70:
        return 'bg-warning'
    else:
        return 'bg-success'

@login_required
def export_board(request, board_id):
    """Export a board's data to JSON or CSV format"""
    board = get_object_or_404(Board, id=board_id)
    
    export_format = request.GET.get('format', 'json')
    
    # Get all columns for this board
    columns = Column.objects.filter(board=board).order_by('position')
    
    # Build the board data structure
    board_data = {
        'board': {
            'name': board.name,
            'description': board.description,
            'created_at': board.created_at.isoformat(),
        },
        'columns': []
    }
    
    # Add columns and tasks
    for column in columns:
        column_data = {
            'name': column.name,
            'position': column.position,
            'tasks': []
        }
        
        tasks = Task.objects.filter(column=column, item_type='task').order_by('position')
        
        for task in tasks:
            # Get task labels
            labels = list(task.labels.values_list('name', flat=True))
            
            task_data = {
                'title': task.title,
                'description': task.description,
                'position': task.position,
                'created_at': task.created_at.isoformat(),
                'updated_at': task.updated_at.isoformat(),
                'due_date': task.due_date.isoformat() if task.due_date else None,
                'assigned_to': task.assigned_to.username if task.assigned_to else None,
                'created_by': task.created_by.username,
                'labels': labels,
                'priority': task.priority,
                'progress': task.progress,
            }
            column_data['tasks'].append(task_data)
        
        board_data['columns'].append(column_data)
    
    if export_format == 'json':
        response = HttpResponse(json.dumps(board_data, indent=2), content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="{board.name}_export.json"'
        return response
    elif export_format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{board.name}_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Column', 'Task Title', 'Description', 'Position', 'Created At', 'Updated At', 
                         'Due Date', 'Assigned To', 'Created By', 'Labels', 'Priority', 'Progress'])
        
        for column in columns:
            tasks = Task.objects.filter(column=column, item_type='task').order_by('position')
            for task in tasks:
                labels = ", ".join(list(task.labels.values_list('name', flat=True)))
                writer.writerow([
                    column.name,
                    task.title,
                    task.description,
                    task.position,
                    task.created_at,
                    task.updated_at,
                    task.due_date if task.due_date else '',
                    task.assigned_to.username if task.assigned_to else '',
                    task.created_by.username,
                    labels,
                    task.priority,
                    task.progress
                ])
        
        return response
    else:
        messages.error(request, "Unsupported export format specified")
        return redirect('board_detail', board_id=board.id)

@login_required
def import_board(request):
    """
    Import a board from external PM tools (Trello, Jira, Asana) or CSV/JSON files.
    
    Supports multiple formats with automatic detection:
    - PrizmAI native JSON
    - Trello JSON export
    - Jira CSV/JSON export
    - Asana CSV/JSON export
    - Generic CSV with field mapping
    """
    if request.method != 'POST':
        return redirect('board_list')
    
    # Check if user has a profile and organization
    try:
        profile = request.user.profile
        organization = profile.organization
    except UserProfile.DoesNotExist:
        messages.error(request, "You must be part of an organization to import a board.")
        return redirect('create_organization')
    
    # Check if file was uploaded
    if 'import_file' not in request.FILES:
        messages.error(request, "No file was uploaded")
        return redirect('board_list')
        
    import_file = request.FILES['import_file']
    filename = import_file.name
    
    # Check file extension - now supports JSON and CSV
    valid_extensions = ['.json', '.csv', '.tsv']
    if not any(filename.lower().endswith(ext) for ext in valid_extensions):
        messages.error(request, "Supported file formats: JSON, CSV, TSV")
        return redirect('board_list')
    
    try:
        # Read file content
        file_content = import_file.read()
        
        # Try to decode as text
        try:
            file_data = file_content.decode('utf-8')
        except UnicodeDecodeError:
            try:
                file_data = file_content.decode('utf-8-sig')
            except UnicodeDecodeError:
                file_data = file_content.decode('latin-1')
        
        # Import using the adapter system
        from kanban.utils.import_adapters import AdapterFactory, UserMatcher
        
        # Create user matcher for this organization
        user_matcher = UserMatcher(organization=organization)
        
        # Check if a specific adapter was requested
        adapter_name = request.POST.get('adapter')
        
        # Create factory and import
        factory = AdapterFactory(user_matcher=user_matcher)
        
        if adapter_name:
            result = factory.import_with_adapter(adapter_name, file_data, filename)
        else:
            result = factory.detect_and_import(file_data, filename)
        
        if not result.success:
            error_msg = '; '.join(result.errors) if result.errors else 'Unknown import error'
            messages.error(request, f"Import failed: {error_msg}")
            return redirect('board_list')
        
        # Create the board and its contents from the import result
        new_board = _create_board_from_import_result(
            result, 
            request.user, 
            organization, 
            request.session
        )
        
        # Build success message with statistics
        stats_parts = []
        if result.stats.get('columns_imported'):
            stats_parts.append(f"{result.stats['columns_imported']} columns")
        if result.stats.get('tasks_imported'):
            stats_parts.append(f"{result.stats['tasks_imported']} tasks")
        if result.stats.get('labels_imported'):
            stats_parts.append(f"{result.stats['labels_imported']} labels")
        
        stats_msg = ', '.join(stats_parts) if stats_parts else 'data'
        source_msg = f" from {result.source_tool}" if result.source_tool else ""
        
        messages.success(request, f"Board '{new_board.name}' imported successfully{source_msg} ({stats_msg})!")
        
        # Add warnings if any
        if result.warnings:
            for warning in result.warnings[:3]:  # Show first 3 warnings
                messages.warning(request, warning)
        
        return redirect('board_detail', board_id=new_board.id)
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception(f"Error importing board: {e}")
        messages.error(request, f"Error importing board: {str(e)}")
        return redirect('board_list')


def _create_board_from_import_result(result, user, organization, session):
    """
    Create a Board and its contents from an ImportResult object.
    
    Args:
        result: ImportResult from adapter
        user: User creating the board
        organization: Organization for the board
        session: Request session for demo mode tracking
    
    Returns:
        Created Board instance
    """
    # Create the board
    board_data = result.board_data
    new_board = Board.objects.create(
        name=board_data.get('name', 'Imported Board'),
        description=board_data.get('description', ''),
        organization=organization,
        created_by=user,
        num_phases=board_data.get('num_phases', 0)
    )
    new_board.members.add(user)
    
    # Create labels first (so we can reference them from tasks)
    labels_map = {}  # label_name -> TaskLabel instance
    for label_data in result.labels_data:
        label, created = TaskLabel.objects.get_or_create(
            name=label_data.get('name'),
            board=new_board,
            defaults={'color': label_data.get('color', '#FF5733')}
        )
        labels_map[label_data.get('name')] = label
    
    # Create columns and build mapping
    columns_map = {}  # temp_id -> Column instance
    for col_data in result.columns_data:
        column = Column.objects.create(
            name=col_data.get('name', 'Column'),
            board=new_board,
            position=col_data.get('position', 0)
        )
        columns_map[col_data.get('temp_id')] = column
    
    # If no columns were created, create a default one
    if not columns_map:
        default_column = Column.objects.create(
            name='To Do',
            board=new_board,
            position=0
        )
        columns_map['default'] = default_column
    
    # Create tasks
    is_demo_mode = session.get('is_demo_mode', False)
    created_by_session = None
    if is_demo_mode:
        created_by_session = session.get('browser_fingerprint') or session.session_key
    
    for task_data in result.tasks_data:
        # Get the column for this task
        column_temp_id = task_data.get('column_temp_id')
        column = columns_map.get(column_temp_id)
        
        # Fall back to first column if column not found
        if not column:
            column = list(columns_map.values())[0]
        
        # Create the task
        new_task = Task.objects.create(
            title=task_data.get('title', 'Untitled Task')[:200],
            description=task_data.get('description', '') or '',
            column=column,
            position=task_data.get('position', 0),
            created_by=user,
            priority=task_data.get('priority', 'medium'),
            progress=task_data.get('progress', 0),
            complexity_score=task_data.get('complexity_score', 5),
            phase=task_data.get('phase'),
            created_by_session=created_by_session
        )
        
        # Handle dates
        if task_data.get('start_date'):
            new_task.start_date = task_data['start_date']
        if task_data.get('due_date'):
            new_task.due_date = task_data['due_date']
        
        # Handle assigned user
        assigned_username = task_data.get('assigned_to_username')
        if assigned_username:
            try:
                # Try exact username match first
                assigned_user = User.objects.filter(username__iexact=assigned_username).first()
                
                # Try email match
                if not assigned_user and '@' in assigned_username:
                    assigned_user = User.objects.filter(email__iexact=assigned_username).first()
                
                # Verify user is in the same organization
                if assigned_user:
                    if hasattr(assigned_user, 'profile') and assigned_user.profile.organization == organization:
                        new_task.assigned_to = assigned_user
            except Exception:
                pass  # Skip if user lookup fails
        
        new_task.save()
        
        # Handle labels
        for label_name in task_data.get('label_names', []):
            if label_name in labels_map:
                new_task.labels.add(labels_map[label_name])
            else:
                # Create new label if not exists
                label, _ = TaskLabel.objects.get_or_create(
                    name=label_name,
                    board=new_board,
                    defaults={'color': '#FF5733'}
                )
                new_task.labels.add(label)
    
    return new_board

@login_required
def add_lean_labels(request, board_id):
    board = get_object_or_404(Board, id=board_id)
    
    # Check if user has access to this board
    # Access restriction removed - all authenticated users can access

    pass  # Original: board membership check removed
    
    if request.method == 'POST':
        # Call the management command to add the labels
        call_command('add_lean_labels', board_id=board_id)
        messages.success(request, 'Lean Six Sigma labels added successfully!')
    
    return redirect('create_label', board_id=board.id)

def welcome(request):
    """
    Welcome page view that will be shown to users who are not logged in.
    Logged in users will be redirected to the dashboard.
    """
    # Clear demo session if user is exiting demo mode
    if request.session.get('is_demo_mode'):
        request.session.pop('is_demo_mode', None)
        request.session.pop('demo_mode', None)
        request.session.pop('demo_role', None)
        request.session.pop('demo_session_id', None)
        request.session.pop('demo_started_at', None)
        request.session.pop('demo_expires_at', None)
        request.session.pop('features_explored', None)
        request.session.pop('aha_moments', None)
        request.session.pop('nudges_shown', None)
        request.session.pop('is_anonymous_demo', None)
        request.session.modified = True
    
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    # Add cache busting timestamp
    import time
    cache_buster = str(int(time.time()))
    
    return render(request, 'kanban/welcome.html', {
        'cache_buster': cache_buster
    })

@login_required
def test_ai_features(request):
    """Test page for AI features debugging"""
    return render(request, 'kanban/test_ai_features.html')

@login_required
def edit_board(request, board_id):
    board = get_object_or_404(Board, id=board_id)
      # Check if user is the board creator or a member
    # Access restriction removed - all authenticated users can access

    pass  # Original: board membership check removed
    
    if request.method == 'POST':
        form = BoardForm(request.POST, instance=board)
        if form.is_valid():
            form.save()
            messages.success(request, f'Board "{board.name}" updated successfully!')
            return redirect('board_detail', board_id=board.id)
    else:
        form = BoardForm(instance=board)
    
    return render(request, 'kanban/edit_board.html', {
        'form': form,
        'board': board
    })

@login_required
@login_required
def getting_started_wizard(request):
    """
    Getting Started Wizard for new users
    """
    try:
        profile = request.user.profile
        organization = profile.organization
        
        # Get user's basic info for personalization
        context = {
            'user': request.user,
            'organization': organization,
            'profile': profile,
            'is_repeat_visitor': profile.completed_wizard,  # Show different messaging for repeat visitors
        }
        
        return render(request, 'kanban/getting_started_wizard.html', context)
        
    except UserProfile.DoesNotExist:
        return redirect('organization_choice')

@login_required
@login_required
def complete_wizard(request):
    """
    Mark the wizard as completed for the user
    """
    if request.method == 'POST':
        try:
            profile = request.user.profile
            profile.completed_wizard = True
            profile.wizard_completed_at = timezone.now()
            profile.save()
            
            messages.success(request, 'Welcome to TaskFlow! You\'re all set to start managing your projects.')
            return redirect('dashboard')
            
        except UserProfile.DoesNotExist:
            return redirect('organization_choice')
    
    return redirect('getting_started_wizard')

@login_required
def wizard_create_board(request):
    """
    Create a board during the getting started wizard
    """
    if request.method == 'POST':
        try:
            profile = request.user.profile
            organization = profile.organization
            
            # Get board data from the request
            board_name = request.POST.get('board_name', '').strip()
            board_description = request.POST.get('board_description', '').strip()
            use_ai_columns = request.POST.get('use_ai_columns') == 'true'
            
            if not board_name:
                return JsonResponse({'error': 'Board name is required'}, status=400)
            
            # Create the board
            board = Board.objects.create(
                name=board_name,
                description=board_description,
                organization=organization,
                created_by=request.user
            )
            board.members.add(request.user)
            
            # If AI columns are requested, get AI recommendations
            if use_ai_columns:
                from .utils.ai_utils import recommend_board_columns
                
                board_data = {
                    'name': board_name,
                    'description': board_description,
                    'team_size': 1,
                    'project_type': 'general',
                    'organization_type': 'general',
                    'existing_columns': []
                }
                
                recommendation = recommend_board_columns(board_data)
                
                if recommendation and recommendation.get('recommended_columns'):
                    # Create AI-recommended columns
                    for i, column_data in enumerate(recommendation['recommended_columns']):
                        Column.objects.create(
                            name=column_data['name'],
                            board=board,
                            position=i
                        )
                else:
                    # Fallback to default columns
                    default_columns = ['To Do', 'In Progress', 'Done']
                    for i, name in enumerate(default_columns):
                        Column.objects.create(name=name, board=board, position=i)
            else:
                # Create default columns
                default_columns = ['To Do', 'In Progress', 'Done']
                for i, name in enumerate(default_columns):
                    Column.objects.create(name=name, board=board, position=i)
            
            return JsonResponse({
                'success': True,
                'board_id': board.id,
                'board_name': board.name,
                'message': 'Board created successfully!'
            })
            
        except UserProfile.DoesNotExist:
            return JsonResponse({'error': 'User profile not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@login_required
def wizard_create_task(request):
    """
    Create a task during the getting started wizard
    """
    if request.method == 'POST':
        try:
            profile = request.user.profile
            
            # Get task data from the request
            board_id = request.POST.get('board_id')
            task_title = request.POST.get('task_title', '').strip()
            task_description = request.POST.get('task_description', '').strip()
            use_ai_description = request.POST.get('use_ai_description') == 'true'
            
            if not board_id or not task_title:
                return JsonResponse({'error': 'Board ID and task title are required'}, status=400)
            
            # Get the board and verify access
            board = get_object_or_404(Board, id=board_id)
            # Access restriction removed - all authenticated users can access

            pass  # Original: board membership check removed
            
            # Get the first column (To Do column)
            first_column = board.columns.first()
            if not first_column:
                return JsonResponse({'error': 'No columns found in board'}, status=404)
            
            # If AI description is requested, enhance the description
            if use_ai_description and not task_description:
                from .utils.ai_utils import enhance_task_description
                
                task_data = {
                    'title': task_title,
                    'description': task_description,
                    'board_context': board.name,
                    'column_context': first_column.name
                }
                
                enhanced = enhance_task_description(task_data)
                if enhanced and enhanced.get('enhanced_description'):
                    task_description = enhanced['enhanced_description']
            
            task = Task.objects.create(
                title=task_title,
                description=task_description,
                column=first_column,
                created_by=request.user,
                assigned_to=request.user,
                priority='medium',
                is_seed_demo_data=False
            )
            
            return JsonResponse({
                'success': True,
                'task_id': task.id,
                'task_title': task.title,
                'task_description': task.description,
                'board_id': board.id,
                'message': 'Task created successfully!'
            })
            
        except UserProfile.DoesNotExist:
            return JsonResponse({'error': 'User profile not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@login_required
def reset_wizard(request):
    """
    Reset the wizard for a user (admin feature or for testing)
    """
    if request.method == 'POST':
        try:
            profile = request.user.profile
            profile.completed_wizard = False
            profile.wizard_completed_at = None
            profile.save()
            
            messages.success(request, 'Getting Started Wizard has been reset. You will see it on your next dashboard visit.')
            return redirect('dashboard')
            
        except UserProfile.DoesNotExist:
            return redirect('organization_choice')
    
    return redirect('dashboard')


# ============================================================================
# Task Dependency Management Views
# ============================================================================

@login_required
def view_dependency_tree(request, task_id):
    """
    Display the dependency tree for a task
    """
    try:
        task = get_object_or_404(Task, id=task_id)
        
        # Access restriction removed - all authenticated users can access
        
        # Get all relationships
        parent_task = task.parent_task
        subtasks = task.subtasks.all()
        related_tasks = task.related_tasks.all()
        dependency_level = task.get_dependency_level()
        
        context = {
            'task': task,
            'parent_task': parent_task,
            'subtasks': subtasks,
            'related_tasks': related_tasks,
            'dependency_level': dependency_level,
            'board': task.column.board,
        }
        
        return render(request, 'kanban/dependency_tree.html', context)
        
    except Task.DoesNotExist:
        messages.error(request, 'Task not found')
        return redirect('dashboard')


@login_required
def board_dependency_graph(request, board_id):
    """
    Display the full dependency graph for a board
    """
    try:
        board = get_object_or_404(Board, id=board_id)
        
        # Access restriction removed - all authenticated users can access
        
        # Get all tasks with dependencies
        tasks = Task.objects.filter(column__board=board).prefetch_related(
            'parent_task', 'subtasks', 'related_tasks'
        )
        
        # Count dependencies
        parent_count = tasks.filter(parent_task__isnull=False).count()
        related_count = 0
        for task in tasks:
            related_count += task.related_tasks.count()
        
        context = {
            'board': board,
            'tasks': tasks,
            'parent_count': parent_count,
            'related_count': related_count,
            'total_tasks': tasks.count(),
        }
        
        return render(request, 'kanban/board_dependency_graph.html', context)
        
    except Board.DoesNotExist:
        messages.error(request, 'Board not found')
        return redirect('dashboard')


# ===== FILE MANAGEMENT VIEWS FOR TASKS =====

@login_required
@require_http_methods(["POST"])
def upload_task_file(request, task_id):
    """Upload a file to a task"""
    task = get_object_or_404(Task, id=task_id)
    board = task.column.board
    
    # Check if user is board member
    # Access restriction removed - all authenticated users can access

    pass  # Original: board membership check removed
    
    if request.method == 'POST':
        form = TaskFileForm(request.POST, request.FILES)
        if form.is_valid():
            file_obj = form.save(commit=False)
            file_obj.task = task
            file_obj.uploaded_by = request.user
            # Filename, size, and type are now set by form.save() with proper sanitization
            file_obj.save()
            
            messages.success(request, f'File "{file_obj.filename}" uploaded successfully!')
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'id': file_obj.id,
                    'filename': file_obj.filename,
                    'file_type': file_obj.file_type,
                    'file_size': file_obj.file_size,
                    'uploaded_by': file_obj.uploaded_by.username,
                    'uploaded_at': file_obj.uploaded_at.isoformat(),
                })
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                }, status=400)
    
    return redirect('task_detail', task_id=task_id)


@login_required
@require_http_methods(["GET"])
def download_task_file(request, file_id):
    """Download a file from a task"""
    file_obj = get_object_or_404(TaskFile, id=file_id)
    board = file_obj.task.column.board
    
    # Check if user is board member
    # Access restriction removed - all authenticated users can access

    pass  # Original: board membership check removed
    
    # Serve the file
    if file_obj.file:
        response = FileResponse(file_obj.file.open('rb'), as_attachment=True)
        response['Content-Disposition'] = f'attachment; filename="{file_obj.filename}"'
        return response
    
    messages.error(request, 'File not found.')
    return redirect('task_detail', task_id=file_obj.task.id)


@login_required
@require_http_methods(["POST"])
def delete_task_file(request, file_id):
    """Delete (soft delete) a file from a task"""
    file_obj = get_object_or_404(TaskFile, id=file_id)
    task = file_obj.task
    board = task.column.board
    
    # Check permissions - only uploader or staff can delete
    if request.user != file_obj.uploaded_by and not request.user.is_staff:
        messages.error(request, 'You do not have permission to delete this file.')
        return redirect('task_detail', task_id=task.id)
    
    # Soft delete
    file_obj.deleted_at = timezone.now()
    file_obj.save()
    
    messages.success(request, f'File "{file_obj.filename}" deleted.')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    return redirect('task_detail', task_id=task.id)


@login_required
@require_http_methods(["GET"])
def list_task_files(request, task_id):
    """Get a list of files in a task (JSON API)"""
    task = get_object_or_404(Task, id=task_id)
    board = task.column.board
    
    # Check if user is board member
    # Access restriction removed - all authenticated users can access

    pass  # Original: board membership check removed
    
    # Get non-deleted files
    files = task.file_attachments.filter(deleted_at__isnull=True).values(
        'id', 'filename', 'file_type', 'file_size', 'uploaded_by__username', 'uploaded_at', 'description'
    )
    
    return JsonResponse({
        'success': True,
        'files': list(files)
    })


@login_required
def skill_gap_dashboard(request, board_id):
    """
    Skill Gap Analysis Dashboard
    Shows team skill inventory, identified gaps, and development plans
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Get skill gaps and development plans
    from .models import SkillGap, SkillDevelopmentPlan, TeamSkillProfile
    
    # Try to get team skill profile
    try:
        team_profile = TeamSkillProfile.objects.get(board=board)
        # Normalize skill_inventory to ensure all required keys exist
        if team_profile and team_profile.skill_inventory:
            for skill_name, skill_data in team_profile.skill_inventory.items():
                # Ensure all proficiency levels exist
                if isinstance(skill_data, dict):
                    for level in ['expert', 'advanced', 'intermediate', 'beginner']:
                        if level not in skill_data:
                            skill_data[level] = 0
                    # Ensure members list exists
                    if 'members' not in skill_data:
                        skill_data['members'] = []
    except TeamSkillProfile.DoesNotExist:
        team_profile = None
    
    # Get active skill gaps
    skill_gaps = SkillGap.objects.filter(
        board=board,
        status__in=['identified', 'acknowledged', 'in_progress']
    ).prefetch_related('affected_tasks').annotate(
        severity_rank=Case(
            When(severity='critical', then=0),
            When(severity='high', then=1),
            When(severity='medium', then=2),
            When(severity='low', then=3),
            default=4,
            output_field=IntegerField()
        )
    ).order_by('severity_rank', '-gap_count')
    
    # Get development plans
    development_plans = SkillDevelopmentPlan.objects.filter(
        board=board
    ).select_related('skill_gap', 'created_by').prefetch_related('target_users').order_by('-created_at')
    
    # Count gaps by severity
    critical_gaps = skill_gaps.filter(severity='critical').count()
    high_gaps = skill_gaps.filter(severity='high').count()
    medium_gaps = skill_gaps.filter(severity='medium').count()
    low_gaps = skill_gaps.filter(severity='low').count()
    
    # Count plans by status
    active_plans = development_plans.filter(status__in=['approved', 'in_progress']).count()
    proposed_plans = development_plans.filter(status='proposed').count()
    completed_plans = development_plans.filter(status='completed').count()
    
    context = {
        'board': board,
        'team_profile': team_profile,
        'skill_gaps': skill_gaps,
        'development_plans': development_plans,
        'critical_gaps': critical_gaps,
        'high_gaps': high_gaps,
        'medium_gaps': medium_gaps,
        'low_gaps': low_gaps,
        'active_plans': active_plans,
        'proposed_plans': proposed_plans,
        'completed_plans': completed_plans,
        'is_demo_mode': False,
        'is_demo_board': False,
    }
    
    return render(request, 'kanban/skill_gap_dashboard.html', context)


@login_required
def scope_tracking_dashboard(request, board_id):
    """
    Scope Tracking Dashboard - Redirects to comprehensive scope dashboard
    Kept for backward compatibility with existing links
    """
    from django.shortcuts import redirect
    return redirect('scope_dashboard', board_id=board_id)


@login_required
def load_demo_data(request):
    """
    Add user as member to existing demo boards so they can explore all features
    Accessible to all authenticated users (not just admins)
    """
    if request.method == 'POST':
        try:
            profile = request.user.profile
            user_org = profile.organization
            
            # Find the demo organizations
            demo_org_names = ['Demo - Acme Corporation']
            demo_orgs = Organization.objects.filter(name__in=demo_org_names)
            
            if not demo_orgs.exists():
                messages.error(request, 'Demo data not found. Please contact administrator to load the initial demo data using: python manage.py populate_test_data')
                return redirect('dashboard')
            
            # Get the demo boards
            demo_board_names = ['Software Project', 'Bug Tracking', 'Marketing Campaign']
            demo_boards = Board.objects.filter(
                organization__in=demo_orgs,
                name__in=demo_board_names
            )
            
            if not demo_boards.exists():
                messages.error(request, 'Demo boards not found. Please contact administrator to load the initial demo data.')
                return redirect('dashboard')
            
            # Check if user has duplicate boards in their own organization
            duplicate_boards = Board.objects.filter(
                organization=user_org,
                name__in=demo_board_names
            )
            
            if duplicate_boards.exists():
                duplicate_names = ', '.join([board.name for board in duplicate_boards])
                duplicate_count = duplicate_boards.count()
                
                # Count tasks in user's duplicate boards vs official demo boards
                user_duplicate_tasks = sum(board.tasks.count() for board in duplicate_boards)
                official_demo_tasks = sum(board.tasks.count() for board in demo_boards)
                
                messages.warning(request, 
                    f'⚠️ You have {duplicate_count} duplicate demo board(s) in your organization: {duplicate_names}. '
                    f'Your duplicates have {user_duplicate_tasks} tasks vs {official_demo_tasks} tasks in the full demo. '
                    f'Please delete your duplicate boards first to access the complete demo with 1000+ tasks. '
                    f'Admin can run: python manage.py cleanup_duplicate_demo_boards --auto-fix')
                return redirect('board_list')
            
            # Check if user is already a member of any demo boards
            already_member_boards = demo_boards.filter(members=request.user)
            
            if already_member_boards.count() >= demo_boards.count():
                # Mark wizard as completed even if they already have access
                profile = request.user.profile
                if not profile.completed_wizard:
                    profile.completed_wizard = True
                    profile.save()
                messages.info(request, 'You already have access to all demo boards!')
                return redirect('dashboard')
            
            # Add user as member to all demo boards with proper roles
            # NOTE: This grants organization-level access - once added to one board in a demo org,
            # user can access all boards in that organization
            from kanban.permission_models import BoardMembership, Role
            from messaging.models import ChatRoom
            
            added_count = 0
            for demo_board in demo_boards:
                # Add to members list if not already
                # This gives them the "key" to access all boards in this demo organization
                if request.user not in demo_board.members.all():
                    demo_board.members.add(request.user)
                    added_count += 1
                
                # Create BoardMembership with Editor role (allows full access)
                membership_exists = BoardMembership.objects.filter(
                    board=demo_board,
                    user=request.user
                ).exists()
                
                if not membership_exists:
                    # Get the Editor role for the board's organization
                    editor_role = Role.objects.filter(
                        organization=demo_board.organization,
                        name='Editor'
                    ).first()
                    
                    if editor_role:
                        BoardMembership.objects.create(
                            board=demo_board,
                            user=request.user,
                            role=editor_role
                        )
                
                # Add user to all chat rooms for this board
                chat_rooms = ChatRoom.objects.filter(board=demo_board)
                for room in chat_rooms:
                    if request.user not in room.members.all():
                        room.members.add(request.user)
            
            if added_count > 0:
                messages.success(request, 
                    f'✅ Successfully added you to {added_count} demo board(s)! '
                    f'You now have access to 1000+ tasks with all advanced features including risk management, '
                    f'budget tracking, milestones, messages, conflicts, wiki, and more. Check your dashboard!')
            else:
                messages.info(request, 'You already have access to all demo boards.')
            
            # Mark wizard as completed since user now has access to boards
            profile = request.user.profile
            if not profile.completed_wizard:
                profile.completed_wizard = True
                profile.save()
            
            # If came from wizard, go to dashboard, otherwise go back
            if request.GET.get('from_wizard') == 'true':
                return redirect('dashboard')
            else:
                return redirect('dashboard')
                
        except Exception as e:
            messages.error(request, f'Error accessing demo data: {str(e)}')
            return redirect('dashboard')
    
    # GET request - show confirmation page
    # Check if demo boards exist in system
    from django.contrib.auth.models import User
    demo_org_names = ['Demo - Acme Corporation']
    demo_orgs = Organization.objects.filter(name__in=demo_org_names)
    demo_available = demo_orgs.exists() and Board.objects.filter(organization__in=demo_orgs).exists()
    
    context = {
        'user': request.user,
        'from_wizard': request.GET.get('from_wizard', 'false'),
        'demo_available': demo_available
    }
    return render(request, 'kanban/load_demo_data.html', context)


@login_required
def board_status_report(request, board_id):
    """
    AI-generated stakeholder status report for a board.
    Gathers key metrics and calls Gemini to produce a concise weekly update.
    """
    from api.ai_usage_utils import check_ai_quota, track_ai_request
    from kanban.utils.ai_utils import generate_status_report
    import time as _time

    board = get_object_or_404(Board, id=board_id)

    # Only generate on POST so users explicitly trigger the AI call
    report_text = None
    error = None

    if request.method == 'POST':
        start = _time.time()

        # Quota guard
        has_quota, quota, remaining = check_ai_quota(request.user)
        if not has_quota:
            error = 'AI usage quota exceeded. Please wait for your quota to reset.'
        else:
            # Gather metrics
            all_tasks = Task.objects.filter(column__board=board, item_type='task')
            total_tasks = all_tasks.count()
            completed = all_tasks.filter(progress=100).count()
            in_progress = all_tasks.filter(progress__gt=0, progress__lt=100).count()
            completion_pct = round((completed / total_tasks * 100), 1) if total_tasks else 0

            today = timezone.now().date()
            overdue = all_tasks.filter(due_date__date__lt=today).exclude(progress=100).count()

            # Velocity: tasks completed in last 7 days
            week_ago = timezone.now() - timedelta(days=7)
            velocity = all_tasks.filter(completed_at__gte=week_ago, progress=100).count()

            # High-risk tasks
            high_risk = all_tasks.filter(risk_level__in=['high', 'critical']).count()

            # Budget status (optional)
            try:
                from kanban.budget_models import ProjectBudget
                budget = ProjectBudget.objects.filter(board=board).order_by('-created_at').first()
                budget_status = budget.status.title() if budget else 'Not tracked'
            except Exception:
                budget_status = 'Not tracked'

            # Column breakdown
            columns = Column.objects.filter(board=board)
            tasks_by_column = [
                {'name': col.name, 'count': all_tasks.filter(column=col).count()}
                for col in columns
            ]

            report_data = {
                'board_name': board.name,
                'total_tasks': total_tasks,
                'completed_count': completed,
                'in_progress_count': in_progress,
                'completion_pct': completion_pct,
                'overdue_count': overdue,
                'velocity': velocity,
                'high_risk_count': high_risk,
                'budget_status': budget_status,
                'tasks_by_column': tasks_by_column,
                'report_date': today.strftime('%B %d, %Y'),
            }

            report_text = generate_status_report(report_data)

            elapsed_ms = int((_time.time() - start) * 1000)
            track_ai_request(
                user=request.user,
                feature='status_report',
                request_type='generate',
                board_id=board.id,
                success=bool(report_text),
                response_time_ms=elapsed_ms,
            )

            if not report_text:
                error = 'AI could not generate the report at this time. Please try again shortly.'

    context = {
        'board': board,
        'report_text': report_text,
        'error': error,
    }
    return render(request, 'kanban/status_report.html', context)
