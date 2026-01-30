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
from .stakeholder_models import StakeholderTaskInvolvement

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
    
    # Get analytics data
    task_count = Task.objects.filter(column__board__in=boards).count()
    completed_count = Task.objects.filter(
        column__board__in=boards,
        progress=100
    ).count()
    
    # Get completion rate
    completion_rate = 0
    if task_count > 0:
        completion_rate = (completed_count / task_count) * 100
      # Get tasks due soon (next 3 days)
    due_soon = Task.objects.filter(
        column__board__in=boards,
        due_date__range=[timezone.now(), timezone.now() + timedelta(days=3)]
    ).count()
      # Get overdue tasks (due date in the past and not completed)
    overdue_count = Task.objects.filter(
        column__board__in=boards,
        due_date__lt=timezone.now()
    ).exclude(
        progress=100
    ).count()
    
    # Get detailed task data for modals with pagination
    # Items per page
    items_per_page = 10
    
    # All Tasks
    all_tasks_list = Task.objects.filter(column__board__in=boards).select_related('column', 'assigned_to', 'column__board').order_by('-created_at')
    all_tasks_page = request.GET.get('all_tasks_page', 1)
    all_tasks_paginator = Paginator(all_tasks_list, items_per_page)
    try:
        all_tasks = all_tasks_paginator.page(all_tasks_page)
    except PageNotAnInteger:
        all_tasks = all_tasks_paginator.page(1)
    except EmptyPage:
        all_tasks = all_tasks_paginator.page(all_tasks_paginator.num_pages)
    
    # Completed Tasks
    completed_tasks_list = Task.objects.filter(
        column__board__in=boards,
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
    
    # Count of my tasks (for stats)
    my_tasks_count = Task.objects.filter(
        column__board__in=boards,
        assigned_to=request.user
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
    from kanban.utils.demo_limits import check_project_limit, increment_project_count, record_limitation_hit
    
    # Check demo mode project limits
    project_limit_status = check_project_limit(request)
    if project_limit_status['is_demo'] and not project_limit_status['can_create']:
        # Record limitation hit for analytics
        record_limitation_hit(request, 'project_limit')
        messages.warning(request, project_limit_status['message'])
        return render(request, 'kanban/create_board.html', {
            'form': BoardForm(),
            'demo_limit_reached': True,
            'demo_limit_message': project_limit_status['message'],
            'demo_projects_created': project_limit_status['current_count'],
            'demo_projects_max': project_limit_status['max_allowed'],
        })
    
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
    
    if request.method == 'POST':
        # Re-check limit before processing (in case of race condition)
        project_limit_status = check_project_limit(request)
        if project_limit_status['is_demo'] and not project_limit_status['can_create']:
            record_limitation_hit(request, 'project_limit')
            messages.warning(request, project_limit_status['message'])
            return redirect('board_list')
        
        form = BoardForm(request.POST)
        if form.is_valid():
            board = form.save(commit=False)
            # MVP Mode: organization can be None
            board.organization = organization
            board.created_by = request.user
            
            # If in demo mode, track this board as created by this demo session
            is_demo_mode = request.session.get('is_demo_mode', False)
            if is_demo_mode:
                # Use browser_fingerprint for persistent tracking across session changes
                browser_fingerprint = request.session.get('browser_fingerprint')
                if browser_fingerprint:
                    board.created_by_session = browser_fingerprint
                else:
                    # Fallback to session key if fingerprint not available
                    board.created_by_session = request.session.session_key
            
            board.save()
            board.members.add(request.user)
            
            # Increment demo project count if in demo mode
            increment_project_count(request)
            
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
            
            return redirect('board_detail', board_id=board.id)
    else:
        form = BoardForm()
    
    # Pass demo status to template
    demo_context = {}
    if project_limit_status['is_demo']:
        demo_context = {
            'demo_projects_created': project_limit_status['current_count'],
            'demo_projects_max': project_limit_status['max_allowed'],
            'demo_projects_remaining': project_limit_status['max_allowed'] - project_limit_status['current_count'],
        }
    
    return render(request, 'kanban/create_board.html', {
        'form': form,
        **demo_context
    })

@login_required
def board_detail(request, board_id):
    from kanban.permission_utils import user_has_board_permission
    from kanban.audit_utils import log_audit
    from kanban.utils.demo_settings import SIMPLIFIED_MODE
    
    board = get_object_or_404(Board, id=board_id)
    
    # Check if this is a demo board (MVP mode: organization can be null)
    is_demo_board = board.is_official_demo_board or (
        board.organization and board.organization.is_demo
    )
    
    # In simplified mode: treat demo boards as regular boards, no redirect
    # In legacy mode: redirect to demo board view if in demo mode
    is_demo_mode = request.session.get('is_demo_mode', False)
    if not SIMPLIFIED_MODE and is_demo_board and is_demo_mode:
        return redirect('demo_board_detail', board_id=board_id)
    
    # Check permission using RBAC (includes organization-level access for demo boards)
    if not user_has_board_permission(request.user, board, 'board.view'):
        if is_demo_board:
            messages.error(request, "You don't have access to this demo board. Click 'Load Demo Data' to get started.")
            return redirect('demo_dashboard')
        return HttpResponseForbidden("You don't have permission to view this board.")
    
    # Log board view
    log_audit('board.viewed', user=request.user, request=request,
              object_type='board', object_id=board.id, object_repr=board.name,
              board_id=board.id)
    
    columns = Column.objects.filter(board=board).order_by('position')
    
    # Create default columns if none exist (only for boards created without AI recommendations)
    if not columns.exists():
        default_columns = ['To Do', 'In Progress', 'Done']
        for i, name in enumerate(default_columns):
            Column.objects.create(name=name, board=board, position=i)
        columns = Column.objects.filter(board=board).order_by('position')
    else:
        # Ensure "To Do" column exists - recreate if missing (for compatibility)
        has_todo = columns.filter(name__iregex=r'^(to do|todo)$').exists()
        if not has_todo:
            # Get the highest position and add "To Do" at the beginning
            max_position = columns.aggregate(max_pos=Max('position'))['max_pos'] or -1
            
            # Shift all existing columns one position to the right
            for column in columns.order_by('-position'):
                column.position += 1
                column.save()
                
            # Create "To Do" column at position 0
            Column.objects.create(name='To Do', board=board, position=0)
            columns = Column.objects.filter(board=board).order_by('position')  # Refresh queryset
    
    # Initialize the search form
    search_form = TaskSearchForm(request.GET or None, board=board)
    
    # Get all tasks for this board (with filtering if search is active)
    tasks = Task.objects.filter(column__board=board)
    
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
          # Filter by label
        if search_form.cleaned_data.get('label'):
            tasks = tasks.filter(labels=search_form.cleaned_data['label'])
        
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
    
    # Get board members - for demo boards, show only users from viewer's real organization
    if is_demo_board:
        try:
            # For demo boards: show only users from the viewer's REAL organization
            # This ensures invitation-based visibility even in demo mode
            user_org = request.user.profile.organization
            # Get users from viewer's real org who are also members of this demo board
            board_member_profiles = UserProfile.objects.filter(
                organization=user_org,
                user__in=board.members.all()
            )
            # For adding new members: show other users from viewer's real organization
            board_member_ids = board_member_profiles.values_list('user_id', flat=True)
            available_org_members = UserProfile.objects.filter(
                organization=user_org
            ).exclude(user_id__in=board_member_ids)
        except UserProfile.DoesNotExist:
            board_member_profiles = UserProfile.objects.none()
            available_org_members = []
    else:
        # For regular boards: show all board members
        board_member_ids = board.members.values_list('id', flat=True)
        board_member_profiles = UserProfile.objects.filter(user_id__in=board_member_ids)
        
        # For adding new members: get org members who aren't on the board yet
        try:
            organization = request.user.profile.organization
            available_org_members = UserProfile.objects.filter(
                organization=organization
            ).exclude(user_id__in=board_member_ids)
        except UserProfile.DoesNotExist:
            available_org_members = []
    
    # Get linked wiki pages for this board
    from wiki.models import WikiLink
    wiki_links = WikiLink.objects.filter(board=board).select_related('wiki_page')
    
    # Get scope creep data
    from kanban.models import ScopeCreepAlert
    scope_status = board.get_current_scope_status()
    active_scope_alerts = ScopeCreepAlert.objects.filter(
        board=board,
        status__in=['active', 'acknowledged']
    ).order_by('-detected_at')[:3]  # Show top 3 active alerts
    
    # Get permission information for UI feedback
    from kanban.permission_utils import (
        get_user_board_membership, 
        get_column_permissions_for_user,
        user_has_board_permission
    )
    
    user_membership = get_user_board_membership(request.user, board)
    user_role_name = user_membership.role.name if user_membership else 'Viewer'
    
    # Get column permissions for visual feedback
    column_permissions = {}
    for column in columns:
        perms = get_column_permissions_for_user(request.user, column)
        if perms:
            column_permissions[column.id] = perms
    
    # Check key permissions for UI elements
    can_manage_members = user_has_board_permission(request.user, board, 'board.manage_members')
    can_edit_board = user_has_board_permission(request.user, board, 'board.edit')
    can_create_tasks = user_has_board_permission(request.user, board, 'task.create')
    
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
    })

def task_detail(request, task_id):
    from django.db.models import Prefetch
    from kanban.permission_utils import user_has_task_permission, user_can_edit_task_in_column
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
    
    # Check if this is a demo board
    is_demo_board = board.is_official_demo_board if hasattr(board, 'is_official_demo_board') else False
    is_demo_mode = request.session.get('is_demo_mode', False)
    demo_mode_type = request.session.get('demo_mode', 'solo')  # 'solo' or 'team'
    
    # SIMPLIFIED MODE: Don't re-establish demo mode, require authentication for all boards
    # LEGACY MODE: Re-establish demo mode for anonymous users accessing demo boards
    if not SIMPLIFIED_MODE:
        # If accessing an official demo board without demo mode active, re-establish demo mode
        # This handles cases where demo session expired but user is still browsing demo content
        if is_demo_board and not is_demo_mode and not request.user.is_authenticated:
            request.session['is_demo_mode'] = True
            request.session['demo_mode'] = 'solo'
            is_demo_mode = True
            demo_mode_type = 'solo'
    
    # For non-demo boards, require authentication
    # In simplified mode, ALL boards require authentication
    if SIMPLIFIED_MODE or not (is_demo_board and is_demo_mode):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        
        # Check permission using RBAC
        if not user_has_task_permission(request.user, task, 'task.view'):
            return HttpResponseForbidden("You don't have permission to view this task.")
    
    # For demo boards in team mode, check role-based permissions
    elif demo_mode_type == 'team':
        from kanban.utils.demo_permissions import DemoPermissions
        if not DemoPermissions.can_perform_action(request, 'can_view_board'):
            return HttpResponseForbidden("You don't have permission to view this task in your current demo role.")
    
    if request.method == 'POST':
        # Check edit permission
        if not (is_demo_board and is_demo_mode):
            # Non-demo boards: use RBAC
            can_edit, error_msg = user_can_edit_task_in_column(request.user, task)
            if not can_edit:
                messages.error(request, error_msg)
                return redirect('task_detail', task_id=task.id)
        elif demo_mode_type == 'team':
            # Demo team mode: check role-based permissions
            from kanban.utils.demo_permissions import DemoPermissions
            if not DemoPermissions.can_perform_action(request, 'can_edit_tasks'):
                messages.error(request, "You don't have permission to edit tasks in your current demo role.")
                return redirect('task_detail', task_id=task.id)
        # Solo demo mode: no restrictions, allow all edits
        
        form = TaskForm(request.POST, instance=task, board=board)
        if form.is_valid():
            # Track changes automatically (only for authenticated users)
            if request.user.is_authenticated:
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
            else:
                # Demo mode - save and mark as user-modified to prevent date refresh overwriting
                task = form.save(commit=False)
                # Mark this task as user-modified so the demo date refresh won't overwrite it
                # Set created_by_session to the user's session ID
                session_id = request.session.get('browser_fingerprint') or request.session.session_key
                if session_id and not task.created_by_session:
                    task.created_by_session = session_id
                # Also mark it as not seed data so the date refresh skips it
                task.is_seed_demo_data = False
                task.save()
                form.save_m2m()
            
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
        # Check comment permission
        if not (is_demo_board and is_demo_mode):
            # Non-demo boards: use RBAC
            if not user_has_task_permission(request.user, task, 'comment.create'):
                return HttpResponseForbidden("You don't have permission to add comments.")
        elif demo_mode_type == 'team':
            # Demo team mode: check role-based permissions
            from kanban.utils.demo_permissions import DemoPermissions
            if not DemoPermissions.can_perform_action(request, 'can_add_comments'):
                messages.error(request, "You don't have permission to add comments in your current demo role.")
                return redirect('task_detail', task_id=task.id)
        # Solo demo mode: no restrictions, allow all comments
        
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
        'wiki_links': wiki_links,
        'prediction': prediction_data,
        'total_time_logged': total_time_logged,
        'is_demo_mode': is_demo_mode,
        'is_demo_board': is_demo_board,
    })

def create_task(request, board_id, column_id=None):
    from kanban.permission_utils import user_has_board_permission, user_can_create_task_in_column
    from kanban.audit_utils import log_model_change
    
    board = get_object_or_404(Board, id=board_id)
    
    # Check if this is a demo board
    is_demo_board = board.is_official_demo_board if hasattr(board, 'is_official_demo_board') else False
    is_demo_mode = request.session.get('is_demo_mode', False)
    demo_mode_type = request.session.get('demo_mode', 'solo')  # 'solo' or 'team'
    
    # For non-demo boards, require authentication
    if not (is_demo_board and is_demo_mode):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        
        # Check basic permission using RBAC
        if not user_has_board_permission(request.user, board, 'task.create'):
            return HttpResponseForbidden("You don't have permission to create tasks on this board.")
    
    # For demo boards in team mode, check role-based permissions
    elif demo_mode_type == 'team':
        from kanban.utils.demo_permissions import DemoPermissions
        if not DemoPermissions.can_perform_action(request, 'can_create_tasks'):
            return HttpResponseForbidden("You don't have permission to create tasks in your current demo role.")
    # Solo demo mode: no restrictions, allow all task creation
    
    if column_id:
        column = get_object_or_404(Column, id=column_id, board=board)
        # Check column-level permission (skip for demo boards)
        if not (is_demo_board and is_demo_mode):
            can_create, error_msg = user_can_create_task_in_column(request.user, column)
            if not can_create:
                messages.error(request, error_msg)
                return redirect('board_detail', board_id=board.id)
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
    from kanban.permission_utils import user_has_task_permission
    from kanban.audit_utils import log_audit
    
    task = get_object_or_404(Task, id=task_id)
    board = task.column.board
    
    # Check if this is a demo board
    is_demo_board = board.is_official_demo_board if hasattr(board, 'is_official_demo_board') else False
    is_demo_mode = request.session.get('is_demo_mode', False)
    demo_mode_type = request.session.get('demo_mode', 'solo')  # 'solo' or 'team'
    
    # For non-demo boards, require authentication
    if not (is_demo_board and is_demo_mode):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        
        # Check permission using RBAC
        if not user_has_task_permission(request.user, task, 'task.delete'):
            return HttpResponseForbidden("You don't have permission to delete this task.")
    
    # For demo boards in team mode, check role-based permissions
    elif demo_mode_type == 'team':
        from kanban.utils.demo_permissions import DemoPermissions
        if not DemoPermissions.can_perform_action(request, 'can_delete_tasks'):
            return HttpResponseForbidden("You don't have permission to delete tasks in your current demo role.")
    # Solo demo mode: no restrictions, allow all deletes
    
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
    from kanban.permission_utils import user_has_board_permission
    from kanban.audit_utils import log_model_change
    
    board = get_object_or_404(Board, id=board_id)
    
    # Check if this is a demo board
    is_demo_board = board.is_official_demo_board if hasattr(board, 'is_official_demo_board') else False
    is_demo_mode = request.session.get('is_demo_mode', False)
    demo_mode_type = request.session.get('demo_mode', 'solo')  # 'solo' or 'team'
    
    # For non-demo boards, require authentication
    if not (is_demo_board and is_demo_mode):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        
        # Check permission using RBAC
        if not user_has_board_permission(request.user, board, 'column.create'):
            return HttpResponseForbidden("You don't have permission to create columns on this board.")
    
    # For demo boards in team mode, check role-based permissions
    elif demo_mode_type == 'team':
        from kanban.utils.demo_permissions import DemoPermissions
        if not DemoPermissions.can_perform_action(request, 'can_create_columns'):
            return HttpResponseForbidden("You don't have permission to create columns in your current demo role.")
    # Solo demo mode: no restrictions, allow all column creation
    
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
    from kanban.permission_utils import user_has_board_permission
    from kanban.audit_utils import log_model_change
    
    column = get_object_or_404(Column, id=column_id)
    board = column.board
    
    # Check if this is a demo board
    is_demo_board = board.is_official_demo_board if hasattr(board, 'is_official_demo_board') else False
    is_demo_mode = request.session.get('is_demo_mode', False)
    demo_mode_type = request.session.get('demo_mode', 'solo')  # 'solo' or 'team'
    
    # For non-demo boards, require authentication
    if not (is_demo_board and is_demo_mode):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        
        # Check permission using RBAC
        if not user_has_board_permission(request.user, board, 'column.edit'):
            return HttpResponseForbidden("You don't have permission to edit columns on this board.")
    
    # For demo boards in team mode, check role-based permissions
    elif demo_mode_type == 'team':
        from kanban.utils.demo_permissions import DemoPermissions
        if not DemoPermissions.can_perform_action(request, 'can_edit_columns'):
            return HttpResponseForbidden("You don't have permission to edit columns in your current demo role.")
    # Solo demo mode: no restrictions, allow all column edits
    
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
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Check if this is a demo board (for display purposes only)
    demo_org_names = ['Demo - Acme Corporation']
    is_demo_board = board.organization.name in demo_org_names
    is_demo_mode = request.session.get('is_demo_mode', False)
    demo_mode_type = request.session.get('demo_mode', 'solo')  # 'solo' or 'team'
    
    # Debug logging
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"board_analytics: board={board.id}, org={board.organization.name}, is_demo_board={is_demo_board}, is_demo_mode={is_demo_mode}, session_key={request.session.session_key}, has_session_cookie={request.COOKIES.get('sessionid', 'NO COOKIE')}")
    
    # For non-demo boards, require authentication
    if not (is_demo_board and is_demo_mode):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        
        # Check if user has access to this board - all boards require membership
        # Access restriction removed - all authenticated users can access

        pass  # Original: board membership check removed
    
    # For demo boards in team mode, check role-based permissions
    elif demo_mode_type == 'team':
        from kanban.utils.demo_permissions import DemoPermissions
        if not DemoPermissions.can_perform_action(request, 'can_view_analytics'):
            return HttpResponseForbidden("You don't have permission to view analytics in your current demo role.")
    # Solo demo mode: full access, no restrictions
    
    # Get columns for this board
    columns = Column.objects.filter(board=board)
    
    # Get tasks by column
    tasks_by_column = []
    for column in columns:
        count = Task.objects.filter(column=column).count()
        tasks_by_column.append({
            'name': column.name,
            'count': count
        })
    
    # Get tasks by priority - convert QuerySet to list of dictionaries
    priority_queryset = Task.objects.filter(column__board=board).values('priority').annotate(
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
    
    # Get tasks by assigned user - convert QuerySet to list of dictionaries
    user_queryset = Task.objects.filter(column__board=board).values(
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
    
    # Calculate productivity based on task progress
    total_tasks = Task.objects.filter(column__board=board).count()
    
    # Get all tasks and their progress values
    all_tasks = Task.objects.filter(column__board=board)
    
    # Count completed tasks based on progress percentage (100%) instead of column name
    completed_count = Task.objects.filter(
        column__board=board,
        progress=100
    ).count()
    
    # Calculate overall productivity based on completion rate (completed tasks / total tasks)
    productivity = 0
    if total_tasks > 0:
        productivity = (completed_count / total_tasks) * 100
    
    # Get tasks due soon (next 7 days)
    today = timezone.now().date()
    upcoming_tasks = Task.objects.filter(
        column__board=board,
        due_date__isnull=False,
        due_date__date__gte=today,
        due_date__date__lte=today + timedelta(days=7)
    ).order_by('due_date')
    
    # Get overdue tasks (due date in the past and not completed)
    overdue_tasks = Task.objects.filter(
        column__board=board,
        due_date__isnull=False,
        due_date__date__lt=today
    ).exclude(
        progress=100
    ).order_by('due_date')
    
    # Get count of overdue tasks
    overdue_count = overdue_tasks.count()
    
    # Lean Six Sigma Metrics
    # Get tasks by value added category
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
    """Display Gantt chart view for a board
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team) - LEGACY MODE ONLY
    SIMPLIFIED MODE: Requires authentication for all boards
    """
    from kanban.permission_utils import user_has_board_permission
    from kanban.utils.demo_settings import SIMPLIFIED_MODE
    
    board = get_object_or_404(Board, id=board_id)
    
    # Check if this is a demo board (prefer is_official_demo_board flag)
    is_demo_board = board.is_official_demo_board if hasattr(board, 'is_official_demo_board') else False
    is_demo_mode = request.session.get('is_demo_mode', False)
    demo_mode_type = request.session.get('demo_mode', 'solo')  # 'solo' or 'team'
    
    # SIMPLIFIED MODE: Don't re-establish demo mode, require authentication for all boards
    # LEGACY MODE: Re-establish demo mode for anonymous users accessing demo boards
    if not SIMPLIFIED_MODE:
        # If accessing an official demo board without demo mode active, re-establish demo mode
        # This handles cases where demo session expired but user is still browsing demo content
        if is_demo_board and not is_demo_mode and not request.user.is_authenticated:
            request.session['is_demo_mode'] = True
            request.session['demo_mode'] = 'solo'
            is_demo_mode = True
            demo_mode_type = 'solo'
    
    # For non-demo boards, require authentication
    # In simplified mode, ALL boards require authentication
    if SIMPLIFIED_MODE or not (is_demo_board and is_demo_mode):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        
        # Check permission using RBAC
        if not user_has_board_permission(request.user, board, 'board.view'):
            return HttpResponseForbidden("You don't have permission to view this board.")
    
    # For demo boards in team mode, check role-based permissions
    elif demo_mode_type == 'team':
        from kanban.utils.demo_permissions import DemoPermissions
        if not DemoPermissions.can_perform_action(request, 'can_view_board'):
            return HttpResponseForbidden("You don't have permission to view Gantt chart in your current demo role.")
    # Solo demo mode: full access, no restrictions
    
    # Get tasks for this board with dependencies prefetched for Gantt chart
    # Order by phase and id to maintain consistent task order regardless of date changes
    # This ensures tasks stay in their original position even after editing dates
    tasks = Task.objects.filter(column__board=board).select_related('column', 'assigned_to').prefetch_related('dependencies').order_by('phase', 'id')
    
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

    context = {
        'board': board,
        'tasks': tasks,
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
    }

    return render(request, 'kanban/gantt_chart.html', context)

def move_task(request):
    """
    Move a task to a different column via drag-and-drop.
    Supports both authenticated users and demo mode (including anonymous users).
    """
    from kanban.permission_utils import user_has_task_permission, user_can_move_task_to_column
    from kanban.audit_utils import log_audit
    
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        data = json.loads(request.body)
        task_id = data.get('taskId')
        column_id = data.get('columnId')
        position = data.get('position', 0)
        
        task = get_object_or_404(Task, id=task_id)
        new_column = get_object_or_404(Column, id=column_id)
        board = new_column.board
        
        # Check if this is a demo board
        is_demo_board = board.is_official_demo_board if hasattr(board, 'is_official_demo_board') else False
        is_demo_mode = request.session.get('is_demo_mode', False)
        demo_mode_type = request.session.get('demo_mode', 'solo')  # 'solo' or 'team'
        
        # For non-demo boards, require authentication
        if not (is_demo_board and is_demo_mode):
            if not request.user.is_authenticated:
                return JsonResponse({'error': 'Authentication required'}, status=401)
            
            # Check permission using RBAC with column-level restrictions
            can_move, error_msg = user_can_move_task_to_column(request.user, task, new_column)
            if not can_move:
                return JsonResponse({'error': error_msg}, status=403)
        
        # For demo boards in team mode, check role-based permissions
        elif demo_mode_type == 'team':
            from kanban.utils.demo_permissions import DemoPermissions
            if not DemoPermissions.can_perform_action(request, 'can_move_tasks'):
                return JsonResponse({'error': "You don't have permission to move tasks in your current demo role."}, status=403)
        # Solo demo mode: no restrictions, allow all moves
        
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

def add_board_member(request, board_id):
    board = get_object_or_404(Board, id=board_id)
    
    # Check if this is a demo board
    is_demo_board = board.is_official_demo_board if hasattr(board, 'is_official_demo_board') else False
    is_demo_mode = request.session.get('is_demo_mode', False)
    demo_mode_type = request.session.get('demo_mode', 'solo')  # 'solo' or 'team'
    
    # For non-demo boards, require authentication
    if not (is_demo_board and is_demo_mode):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        
        # Check if user is the board creator, superuser, or has access to the board
        if not (board.created_by == request.user or 
                request.user.is_superuser or 
                request.user in board.members.all()):
            return HttpResponseForbidden("You don't have permission to add members to this board.")
    
    # For demo boards in team mode, check role-based permissions
    elif demo_mode_type == 'team':
        from kanban.utils.demo_permissions import DemoPermissions
        if not DemoPermissions.can_perform_action(request, 'can_add_board_members'):
            return HttpResponseForbidden("You don't have permission to add members in your current demo role.")
    # Solo demo mode: no restrictions, allow adding members
    
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                # Check if user is in the same organization
                if user.profile.organization == request.user.profile.organization:
                    # Check if this is a demo board
                    demo_org_names = ['Demo - Acme Corporation']
                    is_demo_board = board.organization.name in demo_org_names
                    
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
        (user_profile and request.user == board.organization.created_by)  # Organization creator
    )
    
    if not has_permission:
        messages.error(request, "You don't have permission to remove members from this board.")
        return redirect('board_detail', board_id=board.id)
    
    # Don't allow removing the board creator
    if user_to_remove == board.created_by:
        messages.error(request, "You cannot remove the board creator.")
        return redirect('board_detail', board_id=board.id)
    
    # Check if user is actually a member of the board
    if user_to_remove not in board.members.all():
        messages.error(request, "This user is not a member of the board.")
        return redirect('board_detail', board_id=board.id)
    
    # Remove the member
    board.members.remove(user_to_remove)
    messages.success(request, f'{user_to_remove.username} has been removed from the board.')
    
    return redirect('board_detail', board_id=board.id)

def delete_board(request, board_id):
    board = get_object_or_404(Board, id=board_id)
    
    # Check if this is a demo board
    is_demo_board = board.is_official_demo_board if hasattr(board, 'is_official_demo_board') else False
    is_demo_mode = request.session.get('is_demo_mode', False)
    demo_mode_type = request.session.get('demo_mode', 'solo')  # 'solo' or 'team'
    
    # For non-demo boards, require authentication
    if not (is_demo_board and is_demo_mode):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        
        # Check if user has permission to delete this board
        # Allow deletion if user is:
        # 1. Board creator
        # 2. Organization admin (if they have access to the board)
        # 3. Organization creator
        user_profile = getattr(request.user, 'profile', None)
        has_permission = (
            board.created_by == request.user or  # Board creator
            (user_profile and user_profile.is_admin and 
             (request.user in board.members.all() or board.created_by == request.user)) or  # Organization admin with board access
            (user_profile and request.user == board.organization.created_by)  # Organization creator
        )
        
        if not has_permission:
            return HttpResponseForbidden("You don't have permission to delete this board.")
    
    # For demo boards in team mode, check role-based permissions
    elif demo_mode_type == 'team':
        from kanban.utils.demo_permissions import DemoPermissions
        if not DemoPermissions.can_perform_action(request, 'can_delete_board'):
            return HttpResponseForbidden("You don't have permission to delete boards in your current demo role.")
    # Solo demo mode: no restrictions, allow board deletion
    
    # Delete the board
    if request.method == 'POST':
        board_name = board.name
        
        # Track demo board deletion for analytics (workaround detection)
        if is_demo_mode:
            try:
                from kanban.utils.demo_limits import get_demo_session
                from analytics.models import DemoAnalytics
                
                demo_session = get_demo_session(request)
                if demo_session:
                    # Check if user has hit project limit (potential workaround attempt)
                    at_limit = demo_session.projects_created_in_demo >= 2
                    
                    DemoAnalytics.objects.create(
                        session_id=request.session.session_key,
                        demo_session=demo_session,
                        event_type='board_deleted_in_demo',
                        event_data={
                            'board_name': board_name,
                            'total_created': demo_session.projects_created_in_demo,
                            'at_project_limit': at_limit,
                            'potential_workaround': at_limit,  # If at limit, might be trying workaround
                        }
                    )
            except Exception as e:
                pass  # Analytics should not block deletion
        
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
    """Allow users to join boards in their organization that they aren't already members of"""
    board = get_object_or_404(Board, id=board_id)
    
    # Check if user is in the same organization as the board
    try:
        user_profile = request.user.profile
        if user_profile.organization != board.organization:
            messages.error(request, "You cannot join boards outside your organization.")
            return redirect('organization_boards')
    except UserProfile.DoesNotExist:
        messages.error(request, "You need to set up a profile first.")
        return redirect('organization_choice')
    
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

def reorder_columns(request):
    """
    Handle AJAX request to reorder columns via drag and drop.
    Supports both authenticated users and demo mode (including anonymous users).
    """
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        data = json.loads(request.body)
        column_id = data.get('columnId')
        new_position = data.get('position', 0)
        board_id = data.get('boardId')
        
        column = get_object_or_404(Column, id=column_id)
        board = get_object_or_404(Board, id=board_id)
        
        # Check if this is a demo board - demo boards allow all changes
        is_demo_board = board.is_official_demo_board if hasattr(board, 'is_official_demo_board') else False
        is_demo_mode = request.session.get('is_demo_mode', False)
        
        # For non-demo boards, require authentication
        if not (is_demo_board and is_demo_mode):
            if not request.user.is_authenticated:
                return JsonResponse({'error': 'Authentication required'}, status=401)
            
            # Access restriction removed - all authenticated users can access
        
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

def update_task_progress(request, task_id):
    """
    Update the progress percentage of a task through an AJAX request.
    Expects 'direction' parameter: 'increase' or 'decrease'.
    Increases or decreases by 10% increments.
    Supports both authenticated users and demo mode.
    """
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            task = get_object_or_404(Task, id=task_id)
            board = task.column.board
            
            # Check if this is a demo board - demo boards allow all changes
            is_demo_board = board.is_official_demo_board if hasattr(board, 'is_official_demo_board') else False
            is_demo_mode = request.session.get('is_demo_mode', False)
            
            # For non-demo boards, require authentication
            if not (is_demo_board and is_demo_mode):
                if not request.user.is_authenticated:
                    return JsonResponse({'error': 'Authentication required'}, status=401)
                
                # Access restriction removed - all authenticated users can access
            
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
            
            # Record activity (only for authenticated users)
            if request.user.is_authenticated:
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
    from kanban.utils.demo_limits import check_export_allowed, record_export_attempt, record_limitation_hit
    
    # Check if export is allowed (blocked in demo mode)
    export_status = check_export_allowed(request)
    if export_status['is_demo'] and not export_status['allowed']:
        record_export_attempt(request)
        record_limitation_hit(request, 'export_blocked')
        messages.warning(request, export_status['message'])
        # Return JSON response for AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': 'demo_export_blocked',
                'message': export_status['message'],
                'upgrade_url': '/accounts/signup/'
            }, status=403)
        return redirect('board_detail', board_id=board_id)
    
    board = get_object_or_404(Board, id=board_id)
    
    # Check if user has access to this board
    # Access restriction removed - all authenticated users can access

    pass  # Original: board membership check removed
    
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
        
        tasks = Task.objects.filter(column=column).order_by('position')
        
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
            tasks = Task.objects.filter(column=column).order_by('position')
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
    """Import a board from a JSON file"""
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
    
    # Check file extension
    if not import_file.name.endswith('.json'):
        messages.error(request, "Only JSON files are supported for import")
        return redirect('board_list')
    
    # Try to parse the JSON file
    try:
        imported_data = json.load(import_file)
        
        # Basic validation of imported data structure
        if 'board' not in imported_data or 'columns' not in imported_data:
            messages.error(request, "Invalid board data format")
            return redirect('board_list')
            
        # Create the new board
        board_data = imported_data['board']
        new_board = Board.objects.create(
            name=board_data.get('name', 'Imported Board'),
            description=board_data.get('description', ''),
            organization=organization,
            created_by=request.user
        )
        new_board.members.add(request.user)
        
        # Create columns
        for col_index, column_data in enumerate(imported_data['columns']):
            column = Column.objects.create(
                name=column_data.get('name', f'Column {col_index+1}'),
                board=new_board,
                position=column_data.get('position', col_index)
            )
            
            # Create tasks for this column
            is_demo_mode = request.session.get('is_demo_mode', False)
            for task_index, task_data in enumerate(column_data.get('tasks', [])):
                # Create the task - mark as user-created in demo mode
                created_by_session = None
                if is_demo_mode:
                    created_by_session = request.session.get('browser_fingerprint') or request.session.session_key
                
                new_task = Task.objects.create(
                    title=task_data.get('title', f'Task {task_index+1}'),
                    description=task_data.get('description', ''),
                    column=column,
                    position=task_data.get('position', task_index),
                    created_by=request.user,
                    priority=task_data.get('priority', 'medium'),
                    progress=task_data.get('progress', 0),
                    created_by_session=created_by_session
                )
                
                # Handle assigned_to if provided
                assigned_username = task_data.get('assigned_to')
                if assigned_username:
                    try:
                        assigned_user = User.objects.get(username=assigned_username)
                        # Only set if user is in the same organization
                        if hasattr(assigned_user, 'profile') and assigned_user.profile.organization == organization:
                            new_task.assigned_to = assigned_user
                            new_task.save()
                    except User.DoesNotExist:
                        pass  # Skip if user doesn't exist
                
                # Handle labels if provided
                label_names = task_data.get('labels', [])
                for label_name in label_names:
                    # Try to find an existing label with this name, or create a new one
                    label, created = TaskLabel.objects.get_or_create(
                        name=label_name,
                        board=new_board,
                        defaults={'color': '#FF5733'}  # Default color for new labels
                    )
                    new_task.labels.add(label)
        
        messages.success(request, f"Board '{new_board.name}' imported successfully!")
        return redirect('board_detail', board_id=new_board.id)
        
    except json.JSONDecodeError:
        messages.error(request, "Invalid JSON file")
        return redirect('board_list')
    except Exception as e:
        messages.error(request, f"Error importing board: {str(e)}")
        return redirect('board_list')

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
            
            # Create the task with demo mode tracking
            # Check if demo mode via session OR board
            is_demo_board = board.is_official_demo_board or (hasattr(board.organization, 'is_demo') and board.organization.is_demo)
            is_demo_mode = request.session.get('is_demo_mode', False) or is_demo_board
            
            created_by_session = None
            if is_demo_mode:
                created_by_session = request.session.get('browser_fingerprint') or request.session.session_key
                if not created_by_session:
                    import uuid
                    created_by_session = f"demo-wizard-{uuid.uuid4().hex[:16]}"
            
            task = Task.objects.create(
                title=task_title,
                description=task_description,
                column=first_column,
                created_by=request.user,
                assigned_to=request.user,
                priority='medium',
                created_by_session=created_by_session,
                is_seed_demo_data=False if is_demo_mode else False  # Never seed data when user-created
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


def skill_gap_dashboard(request, board_id):
    """
    Skill Gap Analysis Dashboard
    Shows team skill inventory, identified gaps, and development plans
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Check if this is a demo board (for display purposes only)
    demo_org_names = ['Demo - Acme Corporation']
    is_demo_board = board.organization.name in demo_org_names
    is_demo_mode = request.session.get('is_demo_mode', False)
    demo_mode_type = request.session.get('demo_mode', 'solo')  # 'solo' or 'team'
    
    # For non-demo boards, require authentication
    if not (is_demo_board and is_demo_mode):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        
        # Check access - all boards require membership
        # Access restriction removed - all authenticated users can access

        pass  # Original: board membership check removed
    
    # For demo boards in team mode, check role-based permissions
    elif demo_mode_type == 'team':
        from kanban.utils.demo_permissions import DemoPermissions
        if not DemoPermissions.can_perform_action(request, 'can_use_ai_features'):
            return HttpResponseForbidden("You don't have permission to view skill gaps in your current demo role.")
    # Solo demo mode: full access, no restrictions
    
    # Get skill gaps and development plans
    from .models import SkillGap, SkillDevelopmentPlan, TeamSkillProfile
    
    # Try to get team skill profile
    try:
        team_profile = TeamSkillProfile.objects.get(board=board)
    except TeamSkillProfile.DoesNotExist:
        team_profile = None
    
    # Get active skill gaps
    skill_gaps = SkillGap.objects.filter(
        board=board,
        status__in=['identified', 'acknowledged', 'in_progress']
    ).prefetch_related('affected_tasks').order_by('-severity', '-gap_count')
    
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
        'is_demo_mode': is_demo_mode,
        'is_demo_board': is_demo_board,
    }
    
    return render(request, 'kanban/skill_gap_dashboard.html', context)


@login_required
def scope_tracking_dashboard(request, board_id):
    """
    Scope Tracking Dashboard
    Shows baseline, current scope, alerts, snapshots, and AI recommendations
    """
    from kanban.models import ScopeChangeSnapshot, ScopeCreepAlert
    from kanban.utils.scope_analysis import get_scope_trend_data, calculate_scope_velocity
    
    board = get_object_or_404(Board, id=board_id)
    
    # Check if this is a demo board
    demo_org_names = ['Demo - Acme Corporation']
    is_demo_board = board.organization.name in demo_org_names
    is_demo_mode = request.session.get('is_demo_mode', False)
    
    # Access restriction removed - all authenticated users can access
    
    # Get current scope status
    scope_status = board.get_current_scope_status()
    
    # Get all alerts
    all_alerts = ScopeCreepAlert.objects.filter(board=board).order_by('-detected_at')
    active_alerts = all_alerts.filter(status__in=['active', 'acknowledged'])
    resolved_alerts = all_alerts.filter(status='resolved')
    
    # Get snapshots
    snapshots_queryset = ScopeChangeSnapshot.objects.filter(board=board).order_by('-snapshot_date')
    baseline_snapshot = snapshots_queryset.filter(is_baseline=True).first()
    latest_snapshot = snapshots_queryset.filter(ai_analysis__isnull=False).first()
    snapshots = snapshots_queryset[:20]  # Limit to 20 for display
    
    # Get trend data (last 30 days)
    trend_data = get_scope_trend_data(board, days=30)
    
    # Calculate velocity
    velocity = calculate_scope_velocity(board, weeks=4)
    
    # Count alerts by severity
    critical_count = all_alerts.filter(severity='critical').count()
    warning_count = all_alerts.filter(severity='warning').count()
    info_count = all_alerts.filter(severity='info').count()
    
    context = {
        'board': board,
        'scope_status': scope_status,
        'all_alerts': all_alerts[:10],  # Show last 10
        'active_alerts': active_alerts,
        'resolved_alerts': resolved_alerts[:5],
        'snapshots': snapshots,
        'baseline_snapshot': baseline_snapshot,
        'trend_data': trend_data,
        'velocity': velocity,
        'critical_count': critical_count,
        'warning_count': warning_count,
        'info_count': info_count,
        'latest_snapshot': latest_snapshot,
        'is_demo_mode': is_demo_mode,
        'is_demo_board': is_demo_board,
    }
    
    return render(request, 'kanban/scope_tracking_dashboard.html', context)


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

