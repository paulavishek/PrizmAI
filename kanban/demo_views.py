"""
Demo Mode Views
Provides a consistent demo environment for all users without RBAC restrictions

ARCHITECTURE:
- SOLO MODE: Users are logged in as a virtual admin user (demo_admin_solo)
             This gives them full access everywhere without view-level checks
- TEAM MODE: Users stay as themselves or anonymous, RBAC applies via DemoPermissions
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from datetime import timedelta
from kanban.models import Board, Task, Column, Organization, TaskLabel
from messaging.models import ChatRoom, ChatMessage
from kanban.conflict_models import ConflictDetection
from wiki.models import WikiPage
from kanban.utils.demo_permissions import DemoPermissions
from kanban.utils.demo_admin import login_as_demo_admin, logout_demo_admin, is_demo_admin_user
import logging

logger = logging.getLogger(__name__)


# Demo configuration constants - update these to match your database
DEMO_ORG_NAMES = ['Demo - Acme Corporation']
DEMO_BOARD_NAMES = ['Software Development', 'Bug Tracking', 'Marketing Campaign']


def demo_mode_selection(request):
    """
    Demo mode selection screen - choose between Solo or Team mode
    This is the entry point for the new demo experience
    ANONYMOUS ACCESS: No login required for demo mode
    
    SOLO MODE: User is logged in as virtual admin → full access everywhere
    TEAM MODE: User stays as themselves → RBAC applies via session role
    """
    if request.method == 'POST':
        mode = request.POST.get('mode', 'solo')  # 'solo' or 'team'
        selection_method = request.POST.get('selection_method', 'selected')  # 'selected' or 'skipped'
        
        # Track if user was authenticated before starting demo
        was_authenticated = request.user.is_authenticated
        original_user_id = request.user.id if was_authenticated else None
        
        # For SOLO mode: Log in as virtual demo admin for full access
        if mode == 'solo':
            success = login_as_demo_admin(request)
            if success:
                logger.info(f"Solo demo: User logged in as virtual admin")
            else:
                logger.warning(f"Solo demo: Failed to login as virtual admin, continuing with session-based access")
        
        # Ensure session exists and force cycle to generate new session key
        if not request.session.session_key:
            request.session.cycle_key()
        
        # Initialize demo session
        request.session['is_demo_mode'] = True
        request.session['demo_mode'] = mode
        request.session['demo_mode_selected'] = True
        request.session['demo_role'] = 'admin'  # Start as admin in both modes
        request.session['demo_session_id'] = request.session.session_key
        request.session['is_anonymous_demo'] = not was_authenticated
        request.session['demo_started_at'] = timezone.now().isoformat()
        request.session['demo_expires_at'] = (timezone.now() + timedelta(hours=48)).isoformat()
        request.session['features_explored'] = []
        request.session['aha_moments'] = []
        request.session['nudges_shown'] = []
        
        # Store original user info for restoration on exit
        if was_authenticated and original_user_id:
            request.session['original_user_id'] = original_user_id
            request.session['was_authenticated_before_demo'] = True
        
        # Mark if this is a solo demo with virtual admin login
        if mode == 'solo':
            request.session['demo_admin_logged_in'] = True
        
        # Mark session as modified to ensure it's saved
        request.session.modified = True
        
        # Debug logging
        logger.info(f"demo_mode_selection POST: mode={mode}, session_key={request.session.session_key}, is_demo_mode={request.session.get('is_demo_mode')}, demo_admin_logged_in={request.session.get('demo_admin_logged_in', False)}")
        
        # Create DemoSession record (if models exist)
        try:
            from analytics.models import DemoSession, DemoAnalytics
            
            # Detect device type
            user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
            if 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent:
                device_type = 'mobile'
            elif 'tablet' in user_agent or 'ipad' in user_agent:
                device_type = 'tablet'
            else:
                device_type = 'desktop'
            
            # Get IP address
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0]
            else:
                ip_address = request.META.get('REMOTE_ADDR')
            
            # Create or update demo session
            demo_session, created = DemoSession.objects.get_or_create(
                session_id=request.session.session_key,
                defaults={
                    'user': request.user if request.user.is_authenticated else None,
                    'demo_mode': mode,
                    'current_role': 'admin',
                    'expires_at': timezone.now() + timedelta(hours=48),
                    'selection_method': selection_method,
                    'device_type': device_type,
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                    'ip_address': ip_address,
                }
            )
            
            if not created:
                # Update existing session
                demo_session.demo_mode = mode
                demo_session.selection_method = selection_method
                demo_session.user = request.user if request.user.is_authenticated else None
                demo_session.save()
            
            # Track selection event with anonymous flag
            DemoAnalytics.objects.create(
                session_id=request.session.session_key,
                demo_session=demo_session,
                event_type='demo_mode_selected',
                event_data={
                    'mode': mode,
                    'selection_method': selection_method,
                    'is_anonymous': not request.user.is_authenticated,
                    'user_id': request.user.id if request.user.is_authenticated else None,
                },
                device_type=device_type,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )
        except Exception as e:
            # Analytics models may not exist yet - that's OK
            pass
        
        # Explicitly save session to ensure it persists
        request.session.save()
        
        return redirect('demo_dashboard')
    
    # GET request - show selection screen
    return render(request, 'demo/mode_selection.html')


@require_POST
def switch_demo_role(request):
    """
    Switch between demo roles (Admin/Member/Viewer) in Team mode
    ANONYMOUS ACCESS: Works for both logged-in and anonymous users
    """
    # Check if in demo mode
    if not request.session.get('is_demo_mode'):
        return JsonResponse({
            'status': 'error',
            'message': 'Not in demo mode'
        }, status=403)
    
    # Check if in team mode
    if request.session.get('demo_mode') != 'team':
        return JsonResponse({
            'status': 'error',
            'message': 'Role switching only available in Team mode'
        }, status=403)
    
    # Get new role
    new_role = request.POST.get('role', '').lower()
    valid_roles = ['admin', 'member', 'viewer']
    
    if new_role not in valid_roles:
        return JsonResponse({
            'status': 'error',
            'message': f'Invalid role. Must be one of: {", ".join(valid_roles)}'
        }, status=400)
    
    # Update session
    old_role = request.session.get('demo_role', 'admin')
    request.session['demo_role'] = new_role
    request.session.modified = True
    
    # Track role switch (if analytics models exist)
    try:
        from analytics.models import DemoSession, DemoAnalytics
        
        # Update DemoSession
        demo_session = DemoSession.objects.filter(
            session_id=request.session.session_key
        ).first()
        
        if demo_session:
            demo_session.current_role = new_role
            demo_session.role_switches = (demo_session.role_switches or 0) + 1
            demo_session.save()
        
        # Track role switch event
        DemoAnalytics.objects.create(
            session_id=request.session.session_key,
            event_type='role_switched',
            event_data={
                'from_role': old_role,
                'to_role': new_role
            }
        )
    except Exception as e:
        # Analytics tracking failed - that's OK
        pass
    
    # Get role display name
    role_names = {
        'admin': 'Alex Chen (Admin)',
        'member': 'Sam Rivera (Member)',
        'viewer': 'Jordan Taylor (Viewer)'
    }
    
    return JsonResponse({
        'status': 'success',
        'message': f'Switched to {role_names.get(new_role, new_role)}',
        'new_role': new_role,
        'role_display_name': role_names.get(new_role, new_role)
    })


def exit_demo(request):
    """
    Exit demo mode and clean up session.
    
    For SOLO mode: Logs out the virtual admin and restores original user if any
    For TEAM mode: Just clears session variables
    
    ANONYMOUS ACCESS: Works for both logged-in and anonymous users
    """
    # Check if in demo mode
    if not request.session.get('is_demo_mode'):
        # Not in demo mode, just redirect to welcome
        return redirect('welcome')
    
    demo_mode = request.session.get('demo_mode', 'solo')
    demo_admin_logged_in = request.session.get('demo_admin_logged_in', False)
    
    # Track demo exit (if analytics models exist)
    try:
        from analytics.models import DemoSession, DemoAnalytics
        
        demo_session = DemoSession.objects.filter(
            session_id=request.session.session_key
        ).first()
        
        if demo_session:
            demo_session.is_active = False
            demo_session.save()
        
        DemoAnalytics.objects.create(
            session_id=request.session.session_key,
            event_type='demo_exited',
            event_data={
                'mode': demo_mode,
                'was_virtual_admin': demo_admin_logged_in
            }
        )
    except Exception as e:
        logger.debug(f"Analytics tracking on exit failed: {e}")
    
    # For SOLO mode with virtual admin login: logout and restore original user
    if demo_mode == 'solo' and demo_admin_logged_in:
        logout_demo_admin(request)
    else:
        # For TEAM mode: just clear the demo session variables
        demo_keys = [
            'is_demo_mode',
            'demo_mode',
            'demo_mode_selected',
            'demo_role',
            'demo_session_id',
            'is_anonymous_demo',
            'demo_started_at',
            'demo_expires_at',
            'features_explored',
            'aha_moments',
            'nudges_shown',
            'demo_admin_logged_in',
        ]
        
        for key in demo_keys:
            if key in request.session:
                del request.session[key]
        
        request.session.modified = True
    
    logger.info(f"User exited demo mode: {demo_mode}")
    
    return redirect('welcome')


def _ensure_user_in_demo_boards(user, demo_boards):
    """
    Helper function to automatically add user as member to demo boards
    This ensures they appear in resource lists and have proper access
    
    Args:
        user: User object
        demo_boards: QuerySet or list of Board objects
    """
    from kanban.permission_models import BoardMembership, Role
    
    for board in demo_boards:
        # Skip if user is already a member
        if user in board.members.all():
            continue
        
        # Add user to board members
        board.members.add(user)
        
        # Create BoardMembership with Editor role for proper RBAC
        editor_role = Role.objects.filter(
            organization=board.organization,
            name='Editor'
        ).first()
        
        if editor_role:
            BoardMembership.objects.get_or_create(
                board=board,
                user=user,
                defaults={'role': editor_role}
            )
        
        # Add user to all chat rooms for this board
        chat_rooms = ChatRoom.objects.filter(board=board)
        for room in chat_rooms:
            if user not in room.members.all():
                room.members.add(user)


def demo_dashboard(request):
    """
    Demo dashboard - shows demo boards to ALL users (including anonymous)
    This bypasses RBAC and provides a consistent tutorial environment
    
    ANONYMOUS ACCESS: No login required for demo mode
    Note: Anonymous users won't have board membership, but can view demo data
    """
    # Check if demo mode has been selected
    if not request.session.get('demo_mode_selected'):
        return redirect('demo_mode_selection')
    
    # Get the demo organization - using constants
    demo_orgs = Organization.objects.filter(name__in=DEMO_ORG_NAMES)
    
    if not demo_orgs.exists():
        # No demo data available
        context = {
            'demo_available': False,
            'demo_boards': [],
            'message': 'Demo data has not been set up yet. Please contact your administrator.'
        }
        return render(request, 'kanban/demo_dashboard.html', context)
    
    # Get demo boards - these are visible to ALL users (using constants)
    demo_boards = Board.objects.filter(
        organization__in=demo_orgs,
        name__in=DEMO_BOARD_NAMES
    ).prefetch_related('members')
    
    if not demo_boards.exists():
        context = {
            'demo_available': False,
            'demo_boards': [],
            'message': 'Demo boards not found. Please run: python manage.py populate_test_data'
        }
        return render(request, 'kanban/demo_dashboard.html', context)
    
    # Auto-grant access for authenticated users only
    # Anonymous users can view demo boards without membership
    if request.user.is_authenticated:
        user_demo_orgs = Organization.objects.filter(
            name__in=DEMO_ORG_NAMES,
            boards__members=request.user
        ).distinct()
        
        if not user_demo_orgs.exists():
            # User doesn't have access yet - grant it automatically
            from kanban.permission_models import BoardMembership, Role
            from messaging.models import ChatRoom
            
            for demo_board in demo_boards:
                # Add user to board members
                demo_board.members.add(request.user)
                
                # Create BoardMembership with Editor role
                editor_role = Role.objects.filter(
                    organization=demo_board.organization,
                    name='Editor'
                ).first()
                
                if editor_role:
                    BoardMembership.objects.get_or_create(
                        board=demo_board,
                        user=request.user,
                        defaults={'role': editor_role}
                    )
                
                # Add user to all chat rooms for this board
                chat_rooms = ChatRoom.objects.filter(board=demo_board)
                for room in chat_rooms:
                    if request.user not in room.members.all():
                        room.members.add(request.user)
            
            # Refresh the query to include newly added organizations
            user_demo_orgs = Organization.objects.filter(
                name__in=DEMO_ORG_NAMES,
                boards__members=request.user
            ).distinct()
        
        # Filter to show boards only from organizations user has access to
        demo_boards = demo_boards.filter(organization__in=user_demo_orgs)
    # else: Anonymous users see all demo boards without membership
    
    # Calculate analytics for demo boards
    task_count = Task.objects.filter(column__board__in=demo_boards).count()
    completed_count = Task.objects.filter(
        column__board__in=demo_boards,
        progress=100
    ).count()
    
    completion_rate = 0
    if task_count > 0:
        completion_rate = round((completed_count / task_count) * 100, 1)
    
    # Get overdue tasks (exclude completed tasks with progress=100)
    overdue_count = Task.objects.filter(
        column__board__in=demo_boards,
        due_date__lt=timezone.now()
    ).exclude(
        progress=100
    ).count()
    
    # Get tasks due soon
    due_soon = Task.objects.filter(
        column__board__in=demo_boards,
        due_date__range=[timezone.now(), timezone.now() + timedelta(days=3)]
    ).count()
    
    # Get demo tasks sorted by urgency (for display) - exclude completed tasks
    demo_tasks = Task.objects.filter(
        column__board__in=demo_boards
    ).exclude(
        progress=100
    ).select_related('column', 'column__board', 'assigned_to').extra(
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
    ).order_by('due_date_order', 'due_date', 'priority_order')[:8]
    
    # Get message count
    message_count = ChatMessage.objects.filter(
        chat_room__board__in=demo_boards
    ).count()
    
    # Get conflict count
    conflict_count = ConflictDetection.objects.filter(
        board__in=demo_boards,
        status='active'
    ).count()
    
    # Get wiki pages count
    wiki_count = WikiPage.objects.filter(
        organization__in=demo_orgs
    ).count()
    
    # Get board stats
    boards_with_stats = []
    for board in demo_boards:
        board_task_count = Task.objects.filter(column__board=board).count()
        board_completed = Task.objects.filter(
            column__board=board,
            progress=100
        ).count()
        board_completion_rate = 0
        if board_task_count > 0:
            board_completion_rate = round((board_completed / board_task_count) * 100, 1)
        
        boards_with_stats.append({
            'board': board,
            'task_count': board_task_count,
            'completed_count': board_completed,
            'completion_rate': board_completion_rate
        })
    
    context = {
        'demo_available': True,
        'demo_mode': True,
        'demo_mode_type': request.session.get('demo_mode', 'solo'),
        'current_demo_role': request.session.get('demo_role', 'admin'),
        'demo_expires_at': request.session.get('demo_expires_at'),
        'demo_boards': boards_with_stats,
        'task_count': task_count,
        'completed_count': completed_count,
        'completion_rate': completion_rate,
        'overdue_count': overdue_count,
        'due_soon': due_soon,
        'demo_tasks': demo_tasks,
        'message_count': message_count,
        'conflict_count': conflict_count,
        'wiki_count': wiki_count,
        # Add permission context for role-based feature visibility
        'permissions': DemoPermissions.get_permission_context(request),
        'role_info': DemoPermissions.get_role_description(request.session.get('demo_role', 'admin')),
    }
    
    return render(request, 'kanban/demo_dashboard.html', context)


def demo_board_detail(request, board_id):
    """
    Demo board detail - shows a demo board to ALL users (including anonymous)
    This bypasses RBAC checks completely
    
    ANONYMOUS ACCESS: No login required for demo mode
    Authenticated users get automatic board membership
    """
    # Get the demo organization - using constants
    demo_orgs = Organization.objects.filter(name__in=DEMO_ORG_NAMES)
    
    # Get the board - must be a demo board
    board = get_object_or_404(
        Board,
        id=board_id,
        organization__in=demo_orgs
    )
    
    # Auto-grant access for authenticated users only
    if request.user.is_authenticated:
        # Organization-level access check: user must have access to at least one board in this org
        user_has_org_access = Board.objects.filter(
            organization=board.organization,
            members=request.user
        ).exists()
        
        if not user_has_org_access:
            # Auto-grant access when user clicks on a demo board
            from kanban.permission_models import BoardMembership, Role
            
            # Add user to this board
            board.members.add(request.user)
            
            # Create BoardMembership with Editor role
            editor_role = Role.objects.filter(
                organization=board.organization,
                name='Editor'
            ).first()
            
            if editor_role:
                BoardMembership.objects.get_or_create(
                    board=board,
                    user=request.user,
                    defaults={'role': editor_role}
                )
            
            # Add user to all chat rooms for this board
            chat_rooms = ChatRoom.objects.filter(board=board)
            for room in chat_rooms:
                if request.user not in room.members.all():
                    room.members.add(request.user)
    # else: Anonymous users can view demo board without membership
    
    # Get columns and tasks
    columns = Column.objects.filter(board=board).order_by('position')
    
    # Get all tasks with related data (same as real board_detail view)
    tasks = Task.objects.filter(column__board=board).select_related(
        'assigned_to', 'assigned_to__profile', 'created_by', 'column'
    ).prefetch_related('labels', 'dependencies', 'dependent_tasks').order_by('position')
    
    # Also keep tasks_by_column for compatibility with other parts
    tasks_by_column = {}
    for column in columns:
        column_tasks = Task.objects.filter(column=column).select_related(
            'assigned_to', 'created_by'
        ).prefetch_related('labels', 'dependencies', 'dependent_tasks')
        tasks_by_column[column.id] = column_tasks
    
    # Get board statistics
    total_tasks = Task.objects.filter(column__board=board).count()
    completed_tasks = Task.objects.filter(
        column__board=board,
        progress=100
    ).count()
    
    # Get chat rooms
    chat_rooms = ChatRoom.objects.filter(board=board).annotate(
        message_count=Count('messages')
    )
    
    # Get conflicts
    conflicts = ConflictDetection.objects.filter(
        board=board,
        status='active'
    ).prefetch_related('tasks', 'affected_users')
    
    # Get wiki pages
    wiki_pages = WikiPage.objects.filter(
        organization=board.organization
    )[:5]  # Show first 5
    
    # Get permission information for UI feedback (same as real board)
    # BUT only apply RBAC restrictions in TEAM mode, not SOLO mode
    from kanban.permission_utils import (
        get_user_board_membership, 
        get_column_permissions_for_user,
        user_has_board_permission
    )
    
    demo_mode_type = request.session.get('demo_mode', 'solo')
    user_membership = None
    user_role_name = 'Admin'  # Default for demo mode
    column_permissions = {}
    can_manage_members = True
    can_edit_board = True
    can_create_tasks = True
    
    # Only apply RBAC restrictions in TEAM mode
    if demo_mode_type == 'team' and request.user.is_authenticated:
        user_membership = get_user_board_membership(request.user, board)
        user_role_name = user_membership.role.name if user_membership else 'Admin'
        
        # Get column permissions for visual feedback
        for column in columns:
            perms = get_column_permissions_for_user(request.user, column)
            if perms:
                column_permissions[column.id] = perms
        
        # Check key permissions for UI elements
        can_manage_members = user_has_board_permission(request.user, board, 'board.manage_members')
        can_edit_board = user_has_board_permission(request.user, board, 'board.edit')
        can_create_tasks = user_has_board_permission(request.user, board, 'task.create')
    # Solo mode: Full admin access, no restrictions
    
    # Get board members - same logic as real board
    if request.user.is_authenticated:
        try:
            # For demo boards: show only users from the viewer's REAL organization
            user_org = request.user.profile.organization
            # Get users from viewer's real org who are also members of this demo board
            from accounts.models import UserProfile
            board_member_profiles = UserProfile.objects.filter(
                organization=user_org,
                user__in=board.members.all()
            )
            # For adding new members: show other users from viewer's real organization
            board_member_ids = board_member_profiles.values_list('user_id', flat=True)
            available_org_members = UserProfile.objects.filter(
                organization=user_org
            ).exclude(user_id__in=board_member_ids)
        except:
            board_member_profiles = []
            available_org_members = []
    else:
        board_member_profiles = []
        available_org_members = []
    
    # Get linked wiki pages for this board
    from wiki.models import WikiLink
    wiki_links = WikiLink.objects.filter(board=board).select_related('wiki_page')
    
    # Get scope creep data (same as real board)
    # Show scope tracking in both modes (educational value)
    from kanban.models import ScopeCreepAlert
    scope_status = board.get_current_scope_status()
    active_scope_alerts = ScopeCreepAlert.objects.filter(
        board=board,
        status__in=['active', 'acknowledged']
    ).order_by('-detected_at')[:3]  # Show top 3 active alerts
    
    # Get all labels for this board (for filtering/display)
    labels = TaskLabel.objects.filter(board=board)
    
    context = {
        'demo_mode': True,
        'demo_mode_type': request.session.get('demo_mode', 'solo'),
        'current_demo_role': request.session.get('demo_role', 'admin'),
        'demo_expires_at': request.session.get('demo_expires_at'),
        'board': board,
        'columns': columns,
        'tasks': tasks,  # Add this for the new template structure
        'tasks_by_column': tasks_by_column,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'chat_rooms': chat_rooms,
        'conflicts': conflicts,
        'wiki_pages': wiki_pages,
        'now': timezone.now(),  # Add this for date comparisons
        'can_edit': False,  # Demo mode is read-only for safety
        # Add permission context for role-based feature visibility
        'permissions': DemoPermissions.get_permission_context(request),
        'role_info': DemoPermissions.get_role_description(request.session.get('demo_role', 'admin')),
        # NEW: Add context variables to match real board_detail view
        'user_role_name': user_role_name,
        'column_permissions': column_permissions,
        'can_manage_members': can_manage_members,
        'can_edit_board': can_edit_board,
        'can_create_tasks': can_create_tasks,
        'board_member_profiles': board_member_profiles,
        'available_org_members': available_org_members,
        'wiki_links': wiki_links,
        'scope_status': scope_status,
        'active_scope_alerts': active_scope_alerts,
        'labels': labels,
        'is_demo_board': True,  # Flag to indicate demo board
    }
    
    return render(request, 'kanban/demo_board_detail.html', context)


def reset_demo_data(request):
    """
    Reset demo data to original state
    Supports both AJAX (POST with JSON response) and regular form requests
    ANONYMOUS ACCESS: Works for both logged-in and anonymous users
    """
    from django.contrib import messages
    
    # Check if user is in demo mode (for session-based reset)
    is_demo_user = request.session.get('is_demo_mode', False)
    
    # Superusers can reset anytime, demo users (including anonymous) can reset their session
    is_superuser = request.user.is_authenticated and request.user.is_superuser
    if not (is_superuser or is_demo_user):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'error',
                'message': 'Only demo users or administrators can reset demo data.'
            }, status=403)
        messages.error(request, 'Only administrators can reset demo data.')
        return redirect('demo_dashboard')
    
    if request.method == 'POST':
        try:
            # Get demo boards
            demo_org = Organization.objects.filter(is_demo=True).first()
            if not demo_org:
                raise Exception('Demo organization not found')
            
            demo_boards = Board.objects.filter(
                organization=demo_org,
                is_official_demo_board=True
            )
            
            # Delete session-created content (if any)
            session_id = request.session.get('demo_session_id')
            if session_id:
                # Delete tasks created by this session
                Task.objects.filter(
                    created_by_session=session_id,
                    column__board__organization=demo_org
                ).delete()
                
                # Delete boards created by this session
                Board.objects.filter(
                    created_by_session=session_id,
                    organization=demo_org,
                    is_official_demo_board=False
                ).delete()
            
            # OPTIMIZATION: Reset by clearing user modifications, not full repopulation
            # Use bulk_update for performance
            for board in demo_boards:
                tasks = list(Task.objects.filter(column__board=board))
                # Reset task progress and assignments in batch
                for task in tasks:
                    # Reset progress based on column type
                    if task.column.name in ['Done', 'Closed', 'Published']:
                        task.progress = 100  # Keep completed tasks done
                    else:
                        task.progress = 0  # Reset others to 0
                    task.assigned_to = None  # Clear assignments
                
                # Bulk update for performance
                if tasks:
                    Task.objects.bulk_update(tasks, ['progress', 'assigned_to'], batch_size=100)
            
            # Track reset event
            try:
                from analytics.models import DemoSession, DemoAnalytics
                
                demo_session = DemoSession.objects.filter(
                    session_id=request.session.session_key
                ).first()
                
                if demo_session:
                    demo_session.reset_count = (demo_session.reset_count or 0) + 1
                    demo_session.save()
                
                DemoAnalytics.objects.create(
                    session_id=request.session.session_key,
                    event_type='demo_reset',
                    event_data={'success': True}
                )
            except:
                pass
            
            # Return JSON for AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'message': 'Demo reset successfully!'
                })
            
            # Regular request
            messages.success(request, 'Demo data has been successfully reset to its original state!')
            messages.info(request, 'All user-created changes have been removed. Demo boards are now fresh.')
            return redirect('demo_dashboard')
            
        except Exception as e:
            error_msg = f'Error resetting demo data: {str(e)}'
            
            # Return JSON for AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'message': error_msg
                }, status=500)
            
            messages.error(request, error_msg)
            return redirect('demo_dashboard')
    
    # GET request - show confirmation page
    demo_org = Organization.objects.filter(is_demo=True).first()
    demo_boards = Board.objects.filter(organization=demo_org, is_official_demo_board=True) if demo_org else []
    
    task_count = Task.objects.filter(column__board__in=demo_boards).count() if demo_boards else 0
    user_count = demo_boards.values('members').distinct().count() if demo_boards else 0
    
    context = {
        'demo_boards': demo_boards,
        'task_count': task_count,
        'user_count': user_count,
        'demo_org': demo_org,
    }
    
    return render(request, 'kanban/reset_demo_confirm.html', context)


@require_POST
def extend_demo_session(request):
    """
    Extend demo session by 1 hour (max 3 extensions)
    """
    # Check if in demo mode
    if not request.session.get('is_demo_mode'):
        return JsonResponse({
            'status': 'error',
            'message': 'Not in demo mode'
        }, status=403)
    
    try:
        from analytics.models import DemoSession, DemoAnalytics
        
        # Get session
        session_id = request.session.session_key
        demo_session = DemoSession.objects.filter(session_id=session_id).first()
        
        if not demo_session:
            return JsonResponse({
                'status': 'error',
                'message': 'Demo session not found'
            }, status=404)
        
        # Check extension count
        if demo_session.extensions_count >= 3:
            return JsonResponse({
                'status': 'error',
                'message': 'Maximum extensions reached. Please create an account to continue.'
            }, status=403)
        
        # Extend session
        demo_session.expires_at = timezone.now() + timedelta(hours=1)
        demo_session.extensions_count += 1
        demo_session.save()
        
        # Update session variable
        request.session['demo_expires_at'] = demo_session.expires_at.isoformat()
        
        # Track extension
        DemoAnalytics.objects.create(
            session_id=session_id,
            event_type='session_extended',
            event_data={
                'extensions_count': demo_session.extensions_count,
                'new_expiry': demo_session.expires_at.isoformat()
            }
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Session extended by 1 hour',
            'new_expiry_time': demo_session.expires_at.isoformat(),
            'extensions_remaining': 3 - demo_session.extensions_count
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error extending session: {str(e)}'
        }, status=500)


@require_POST
def track_demo_event(request):
    """
    Track custom demo events (aha moments, feature exploration, etc.)
    """
    import json
    
    # Check if in demo mode
    if not request.session.get('is_demo_mode'):
        return JsonResponse({
            'status': 'error',
            'message': 'Not in demo mode'
        }, status=403)
    
    try:
        from analytics.models import DemoAnalytics
        
        # Parse request body
        data = json.loads(request.body)
        event_type = data.get('event_type')
        event_data = data.get('event_data', {})
        
        if not event_type:
            return JsonResponse({
                'status': 'error',
                'message': 'event_type is required'
            }, status=400)
        
        # Create analytics event
        DemoAnalytics.objects.create(
            session_id=request.session.session_key,
            event_type=event_type,
            event_data=event_data
        )
        
        # Update session tracking for specific events
        if event_type == 'aha_moment':
            aha_moments = request.session.get('aha_moments', [])
            if event_data.get('moment_type') not in aha_moments:
                aha_moments.append(event_data.get('moment_type'))
                request.session['aha_moments'] = aha_moments
        
        elif event_type == 'feature_explored':
            features = request.session.get('features_explored', [])
            if event_data.get('feature') not in features:
                features.append(event_data.get('feature'))
                request.session['features_explored'] = features
        
        return JsonResponse({
            'status': 'success',
            'message': 'Event tracked'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error tracking event: {str(e)}'
        }, status=500)


def trigger_aha_moment_server_side(request, moment_type, event_data=None):
    """
    Helper function to trigger aha moments from server-side code
    Call this when detecting aha moments in view logic
    
    Args:
        request: Django request object
        moment_type: String identifier for aha moment type
        event_data: Optional dict of additional data to track
    
    Returns:
        bool: True if aha moment was recorded, False if already triggered
    """
    if not request.session.get('is_demo_mode'):
        return False
    
    # Get aha moments list from session
    aha_moments = request.session.get('aha_moments', [])
    
    # Check if already triggered
    if moment_type in aha_moments:
        return False
    
    # Add to session
    aha_moments.append(moment_type)
    request.session['aha_moments'] = aha_moments
    request.session.modified = True
    
    # Track in analytics
    try:
        from analytics.models import DemoAnalytics, DemoSession
        
        # Create analytics event
        DemoAnalytics.objects.create(
            session_id=request.session.session_key,
            event_type='aha_moment',
            event_data={
                'moment_type': moment_type,
                'timestamp': timezone.now().isoformat(),
                **(event_data or {})
            }
        )
        
        # Update DemoSession
        session_id = request.session.session_key
        demo_session = DemoSession.objects.filter(session_id=session_id).first()
        if demo_session:
            demo_session.aha_moments += 1
            if moment_type not in demo_session.aha_moments_list:
                demo_session.aha_moments_list.append(moment_type)
            demo_session.save(update_fields=['aha_moments', 'aha_moments_list'])
    
    except Exception as e:
        # Fail silently - analytics shouldn't break functionality
        pass
    
    return True


def check_aha_moment_triggers(request):
    """
    Check for aha moment triggers based on user activity
    Called periodically from views to detect server-side aha moments
    
    Returns:
        list: List of newly triggered aha moment types
    """
    if not request.session.get('is_demo_mode'):
        return []
    
    triggered_moments = []
    
    # Check time in demo (for engagement-based moments)
    try:
        from analytics.models import DemoSession
        session_id = request.session.session_key
        demo_session = DemoSession.objects.filter(session_id=session_id).first()
        
        if demo_session:
            # Check if user has been active for 5+ minutes
            time_in_demo = demo_session.time_in_demo or 0
            if time_in_demo >= 300:  # 5 minutes
                # Check features explored
                features_explored = len(demo_session.features_list)
                
                # Trigger "power user" moment if explored 5+ features
                if features_explored >= 5:
                    if trigger_aha_moment_server_side(request, 'power_user_exploration', {
                        'features_count': features_explored,
                        'time_in_demo': time_in_demo
                    }):
                        triggered_moments.append('power_user_exploration')
    
    except Exception as e:
        pass
    
    return triggered_moments


def check_nudge(request):
    """
    Check if a nudge should be shown based on current session state
    Called periodically by client-side JavaScript
    
    ANONYMOUS ACCESS: Works for both logged-in and anonymous users
    Returns JSON with nudge_type and context if nudge should show
    """
    from kanban.utils.nudge_timing import NudgeTiming, NudgeType
    
    # Check if in demo mode
    if not request.session.get('is_demo_mode'):
        return JsonResponse({
            'show_nudge': False,
            'reason': 'Not in demo mode'
        })
    
    # Check for specific nudge type (for exit intent)
    nudge_type = request.GET.get('type')
    
    if nudge_type == 'exit_intent':
        should_show = NudgeTiming.should_show_exit_intent_nudge(request.session)
        if should_show:
            context = NudgeTiming.get_nudge_context(request.session)
            return JsonResponse({
                'show_nudge': True,
                'nudge_type': NudgeType.EXIT_INTENT,
                'context': context
            })
        else:
            return JsonResponse({
                'show_nudge': False,
                'reason': 'Exit intent conditions not met'
            })
    
    # Get next nudge to show
    next_nudge = NudgeTiming.get_next_nudge(request.session)
    
    if next_nudge:
        context = NudgeTiming.get_nudge_context(request.session)
        return JsonResponse({
            'show_nudge': True,
            'nudge_type': next_nudge,
            'context': context
        })
    else:
        return JsonResponse({
            'show_nudge': False,
            'reason': 'No nudge conditions met yet'
        })


@require_POST
def track_nudge(request):
    """
    Track nudge events (shown, clicked, dismissed)
    ANONYMOUS ACCESS: Works for both logged-in and anonymous users
    """
    import json
    from kanban.utils.nudge_timing import NudgeTiming
    
    # Check if in demo mode
    if not request.session.get('is_demo_mode'):
        return JsonResponse({
            'status': 'error',
            'message': 'Not in demo mode'
        }, status=403)
    
    try:
        # Parse request body
        data = json.loads(request.body)
        event_type = data.get('event_type')  # 'shown', 'clicked', 'dismissed'
        nudge_type = data.get('nudge_type')
        
        if not event_type or not nudge_type:
            return JsonResponse({
                'status': 'error',
                'message': 'event_type and nudge_type are required'
            }, status=400)
        
        # Track in analytics
        try:
            from analytics.models import DemoAnalytics, DemoSession
            
            # Create analytics event
            DemoAnalytics.objects.create(
                session_id=request.session.session_key,
                event_type=f'nudge_{event_type}',
                event_data={
                    'nudge_type': nudge_type,
                    'timestamp': data.get('timestamp', timezone.now().isoformat())
                }
            )
            
            # Update DemoSession nudge counts
            session_id = request.session.session_key
            demo_session = DemoSession.objects.filter(session_id=session_id).first()
            
            if demo_session:
                if event_type == 'shown':
                    demo_session.nudges_shown += 1
                    # Update session variable
                    NudgeTiming.mark_nudge_shown(request.session, nudge_type)
                    
                elif event_type == 'clicked':
                    demo_session.nudges_clicked += 1
                    
                elif event_type == 'dismissed':
                    demo_session.nudges_dismissed += 1
                    # Update session variable
                    NudgeTiming.mark_nudge_dismissed(request.session, nudge_type)
                
                demo_session.save()
        
        except ImportError:
            # Analytics models don't exist - that's OK
            pass
        
        return JsonResponse({
            'status': 'success',
            'message': f'Nudge {event_type} tracked'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error tracking nudge: {str(e)}'
        }, status=500)
