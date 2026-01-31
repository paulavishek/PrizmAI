"""
Demo Mode Views
Provides a consistent demo environment for all users

SIMPLIFIED MODE (January 2026):
- Single authenticated environment
- All users get full access to demo boards
- No Solo/Team mode selection required
- Pre-populated demo data for immediate exploration

LEGACY ARCHITECTURE (disabled when SIMPLIFIED_MODE=True):
- SOLO MODE: Users are logged in as a virtual admin user (demo_admin_solo)
- TEAM MODE: Users stay as themselves, RBAC applies via DemoPermissions
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from datetime import timedelta
from decimal import Decimal
import random
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

# Import settings from centralized config
from kanban.utils.demo_settings import SIMPLIFIED_MODE


def _auto_grant_demo_access(request):
    """
    Automatically grant the authenticated user access to demo boards.
    
    In simplified mode, users automatically become members of demo boards
    so they can explore the pre-populated data immediately.
    """
    if not request.user.is_authenticated:
        return
    
    try:
        # Get all official demo boards
        demo_boards = Board.objects.filter(
            is_official_demo_board=True
        )
        
        if not demo_boards.exists():
            logger.warning("No demo boards found for auto-grant")
            return
        
        for board in demo_boards:
            # Add user to board members (simple M2M relationship)
            if request.user not in board.members.all():
                board.members.add(request.user)
                logger.info(f"Auto-granted {request.user.username} access to demo board: {board.name}")
            
            # Add user to chat rooms for this board
            chat_rooms = ChatRoom.objects.filter(board=board)
            for room in chat_rooms:
                if request.user not in room.members.all():
                    room.members.add(request.user)
        
        # Also set up time tracking demo data for this user
        _setup_user_time_tracking_demo(request.user, demo_boards)
        
    except Exception as e:
        logger.error(f"Error auto-granting demo access: {e}")


def _setup_user_time_tracking_demo(user, demo_boards):
    """
    Set up time tracking demo data for a new user accessing the demo.
    
    This function:
    1. Assigns some tasks to the user (so they appear in My Timesheet)
    2. Creates time entries for those tasks (so the dashboard shows data)
    
    Only runs once per user (checks if user already has time entries).
    """
    from kanban.budget_models import TimeEntry
    
    # Skip if user is a demo user (they already have data)
    if '_demo' in user.username:
        return
    
    # Skip if user already has time entries in demo boards
    existing_entries = TimeEntry.objects.filter(
        user=user,
        task__column__board__in=demo_boards
    ).exists()
    
    if existing_entries:
        return  # User already has time tracking data
    
    try:
        now = timezone.now().date()
        
        # Time entry descriptions for variety
        descriptions = [
            "Reviewed requirements and planning",
            "Implementation work",
            "Testing and validation",
            "Code review participation",
            "Documentation updates",
            "Bug investigation",
            "Feature development",
            "Team collaboration session",
        ]
        
        entries_created = 0
        tasks_assigned = 0
        
        for board in demo_boards:
            # Get some tasks that are in progress but not yet assigned to this user
            # Prioritize tasks that already have some progress
            available_tasks = Task.objects.filter(
                column__board=board,
                progress__gt=0,
                progress__lt=100
            ).exclude(
                assigned_to=user
            ).order_by('?')[:3]  # Random 3 tasks per board
            
            for task in available_tasks:
                # Assign the task to this user (in addition to existing assignee)
                # We don't change the existing assigned_to field, we just create time entries
                tasks_assigned += 1
                
                # Create 1-3 time entries per task
                num_entries = random.randint(1, 3)
                for i in range(num_entries):
                    hours = Decimal(str(round(random.uniform(0.5, 3.0), 2)))
                    
                    # Spread entries over the last 14 days
                    days_ago = random.randint(0, 13)
                    entry_date = now - timedelta(days=days_ago)
                    
                    # Avoid weekends
                    while entry_date.weekday() >= 5:
                        days_ago += 1
                        entry_date = now - timedelta(days=days_ago)
                    
                    description = random.choice(descriptions)
                    
                    TimeEntry.objects.create(
                        task=task,
                        user=user,
                        hours_spent=hours,
                        description=f"{description} - {task.title[:30]}",
                        work_date=entry_date,
                    )
                    entries_created += 1
        
        if entries_created > 0:
            logger.info(f"Created {entries_created} time entries for user {user.username}")
    
    except Exception as e:
        logger.error(f"Error setting up time tracking demo for {user.username}: {e}")
        
    except Exception as e:
        logger.error(f"Error auto-granting demo access: {e}")


def demo_mode_selection(request):
    """
    Demo mode selection screen - entry point for demo experience
    
    SIMPLIFIED MODE (January 2026):
    - No Solo/Team selection required
    - All authenticated users get full access
    - Pre-populated demo data available immediately
    - Automatically redirects to dashboard if already authenticated
    - NO demo session variables set (just regular dashboard)
    
    LEGACY MODE:
    - Choose between Solo or Team mode
    - SOLO MODE: User is logged in as virtual admin
    - TEAM MODE: User experiences RBAC via session role
    """
    # SIMPLIFIED MODE: Skip mode selection entirely
    # Redirect directly to regular dashboard without setting demo session
    if SIMPLIFIED_MODE:
        if request.user.is_authenticated:
            # In simplified mode, just grant access to demo boards and redirect to regular dashboard
            # DO NOT set is_demo_mode - we want demo boards to appear as regular boards
            _auto_grant_demo_access(request)
            
            return redirect('dashboard')
        else:
            # Not authenticated - redirect to login with message
            from django.contrib import messages
            messages.info(request, 'Please sign in or create a free account to explore the demo.')
            return redirect('account_login')
    
    # LEGACY MODE: Original Solo/Team selection flow
    if request.method == 'POST':
        mode = request.POST.get('mode', 'solo')  # 'solo' or 'team'
        selection_method = request.POST.get('selection_method', 'selected')  # 'selected' or 'skipped'
        
        # Check abuse prevention BEFORE allowing demo access
        try:
            from kanban.utils.demo_abuse_prevention import can_create_demo_session
            can_create, abuse_message = can_create_demo_session(request)
            if not can_create:
                logger.warning(f"Demo access denied due to abuse prevention: {abuse_message}")
                return render(request, 'demo/mode_selection.html', {
                    'error': abuse_message,
                    'abuse_blocked': True,
                })
        except Exception as e:
            logger.warning(f"Could not check abuse prevention: {e}")
        
        # Track if user was authenticated before starting demo
        was_authenticated = request.user.is_authenticated
        original_user_id = request.user.id if was_authenticated else None
        
        # Check if user is a REAL authenticated user (not a demo admin)
        # Real authenticated users should NOT be switched to demo_admin
        is_real_authenticated_user = False
        if was_authenticated and hasattr(request.user, 'email') and request.user.email:
            email = request.user.email.lower()
            # Check if this is NOT a demo admin account
            if not ('demo_admin' in email or email.startswith('virtual_demo')):
                is_real_authenticated_user = True
                logger.info(f"Real authenticated user '{request.user.username}' entering demo mode - keeping their session")
        
        # For SOLO mode: Log in as virtual demo admin for full access
        # BUT ONLY for anonymous users - real authenticated users keep their own session
        if mode == 'solo' and not is_real_authenticated_user:
            success = login_as_demo_admin(request)
            if success:
                logger.info(f"Solo demo: Anonymous user logged in as virtual admin")
            else:
                logger.warning(f"Solo demo: Failed to login as virtual admin, continuing with session-based access")
        
        # Ensure session exists and force cycle to generate new session key
        if not request.session.session_key:
            request.session.cycle_key()
        
        # Generate browser fingerprint for persistent tracking across sessions
        import hashlib
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        ip_address = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0] or request.META.get('REMOTE_ADDR', '')
        fingerprint_string = f"{user_agent}_{ip_address}"
        browser_fingerprint = hashlib.sha256(fingerprint_string.encode()).hexdigest()[:64]
        
        # Initialize demo session
        request.session['is_demo_mode'] = True
        request.session['demo_mode'] = mode
        request.session['demo_mode_selected'] = True
        request.session['demo_role'] = 'admin'  # Start as admin in both modes
        request.session['demo_session_id'] = request.session.session_key
        # Real authenticated users are NOT anonymous demo users
        request.session['is_anonymous_demo'] = not is_real_authenticated_user
        # Store original user info for authenticated users exploring demo
        if is_real_authenticated_user:
            request.session['original_user_id'] = original_user_id
            request.session['original_username'] = request.user.username
        request.session['browser_fingerprint'] = browser_fingerprint
        
        # Check if this browser has an existing demo session
        existing_demo_start = None
        recent_session = None
        try:
            from analytics.models import DemoSession
            # Look for sessions started within 48h
            recent_session = DemoSession.objects.filter(
                browser_fingerprint=browser_fingerprint,
                first_demo_start__gte=timezone.now() - timedelta(hours=48)
            ).order_by('-first_demo_start').first()
            
            if recent_session and recent_session.first_demo_start:
                existing_demo_start = recent_session.first_demo_start
                logger.info(f"Found existing demo session for browser, started at {existing_demo_start}")
        except Exception as e:
            logger.warning(f"Could not check for existing demo session: {e}")
        
        # Set demo start time (use existing if found, otherwise now)
        demo_started_at = existing_demo_start or timezone.now()
        
        request.session['demo_started_at'] = demo_started_at.isoformat()
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
            
            # CRITICAL FIX: Check if we found an existing session by browser fingerprint
            # If so, update that session's session_id instead of creating a new record
            # This ensures session data persists across login/logout
            if recent_session:
                # Update the existing session with the new session_id
                demo_session = recent_session
                demo_session.session_id = request.session.session_key
                demo_session.demo_mode = mode
                demo_session.selection_method = selection_method
                demo_session.user = request.user if request.user.is_authenticated else None
                demo_session.current_role = 'admin'
                demo_session.is_active = True
                demo_session.save()
                created = False
                logger.info(f"Updated existing demo session with new session_id: {request.session.session_key}")
            else:
                # No existing session found, create a new one
                demo_session, created = DemoSession.objects.get_or_create(
                    session_id=request.session.session_key,
                    defaults={
                        'user': request.user if request.user.is_authenticated else None,
                        'demo_mode': mode,
                        'current_role': 'admin',
                        'browser_fingerprint': browser_fingerprint,
                        'first_demo_start': demo_started_at,
                        'selection_method': selection_method,
                        'device_type': device_type,
                        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                        'ip_address': ip_address,
                    }
                )
                
                if not created:
                    # Session_id already exists, just update it
                    demo_session.demo_mode = mode
                    demo_session.selection_method = selection_method
                    demo_session.user = request.user if request.user.is_authenticated else None
                    demo_session.save()
            
            # Register new session for abuse prevention tracking if it's truly new
            if created:
                try:
                    from kanban.utils.demo_abuse_prevention import register_new_session
                    register_new_session(request, request.session.session_key)
                except Exception as e:
                    logger.warning(f"Could not register session for abuse prevention: {e}")
            
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
        'admin': 'Demo Admin (Solo)',
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
    
    SIMPLIFIED MODE (January 2026):
    - Redirect to regular dashboard (demo boards shown there)
    - No separate demo dashboard needed
    
    LEGACY MODE:
    - ANONYMOUS ACCESS: No login required for demo mode
    - Note: Anonymous users won't have board membership, but can view demo data
    """
    # SIMPLIFIED MODE: Redirect to regular dashboard
    if SIMPLIFIED_MODE:
        if request.user.is_authenticated:
            _auto_grant_demo_access(request)
        return redirect('dashboard')
    
    # LEGACY MODE: Check if demo mode has been selected
    if not request.session.get('demo_mode_selected'):
        return redirect('demo_mode_selection')
    
    # Get the demo organization - using constants
    demo_orgs = Organization.objects.filter(name__in=DEMO_ORG_NAMES)
    logger.info(f"demo_dashboard: DEMO_ORG_NAMES={DEMO_ORG_NAMES}, found {demo_orgs.count()} orgs")
    
    if not demo_orgs.exists():
        # No demo data available
        logger.warning("demo_dashboard: No demo orgs found!")
        context = {
            'demo_available': False,
            'demo_boards': [],
            'message': 'Demo data has not been set up yet. Please contact your administrator.'
        }
        return render(request, 'kanban/demo_dashboard.html', context)
    
    # Get demo boards - these are visible to ALL users (using constants)
    # Also include boards created by this demo session (using browser fingerprint)
    browser_fingerprint = request.session.get('browser_fingerprint')
    
    # Start with official demo boards
    demo_boards = Board.objects.filter(
        organization__in=demo_orgs,
        name__in=DEMO_BOARD_NAMES
    ).prefetch_related('members')
    logger.info(f"demo_dashboard: DEMO_BOARD_NAMES={DEMO_BOARD_NAMES}, found {demo_boards.count()} boards")
    
    # Also include boards created by this user during demo mode
    user_created_boards = Board.objects.none()
    if browser_fingerprint:
        user_created_boards = Board.objects.filter(
            created_by_session=browser_fingerprint
        ).prefetch_related('members')
        if user_created_boards.exists():
            logger.info(f"demo_dashboard: Found {user_created_boards.count()} user-created boards for this session")
            # Combine official demo boards with user-created boards
            demo_boards = (demo_boards | user_created_boards).distinct()
    
    if not demo_boards.exists():
        logger.warning("demo_dashboard: No demo boards found!")
        context = {
            'demo_available': False,
            'demo_boards': [],
            'message': 'Demo boards not found. Please run: python manage.py populate_test_data'
        }
        return render(request, 'kanban/demo_dashboard.html', context)
    
    # Auto-grant access for authenticated users only
    # Anonymous users can view demo boards without membership
    if request.user.is_authenticated:
        # Check if user is already a member of any demo boards
        user_demo_orgs = Organization.objects.filter(
            name__in=DEMO_ORG_NAMES,
            boards__members=request.user
        ).distinct()
        
        if not user_demo_orgs.exists():
            # User doesn't have access yet - grant it automatically
            from kanban.permission_models import BoardMembership, Role
            
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
        
        # IMPORTANT: Don't filter boards in demo mode - all demo boards should be visible
        # The membership grants above ensure proper RBAC, but visibility should be unrestricted
        # This prevents the bug where filtering by user_demo_orgs returns empty results
        # due to queryset caching/evaluation timing issues
        # demo_boards queryset already contains all demo boards, no need to filter further
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
    
    # Get UNREAD message count (matching the navigation bar badge)
    # Count messages the current user hasn't read (excluding their own messages)
    if request.user.is_authenticated:
        # Get chat rooms from demo boards where user is a member
        user_chat_rooms = ChatRoom.objects.filter(
            board__in=demo_boards,
            members=request.user
        )
        
        # Count unread messages across all these rooms
        message_count = 0
        for room in user_chat_rooms:
            room_unread = room.messages.exclude(read_by=request.user).exclude(author=request.user).count()
            message_count += room_unread
    else:
        # For anonymous demo users, show total message count as fallback
        message_count = ChatMessage.objects.filter(
            chat_room__board__in=demo_boards
        ).count()
    
    # Get conflict count (matching the navigation bar badge)
    # Only count active conflicts from boards the user has access to
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
    
    logger.info(f"demo_dashboard: boards_with_stats has {len(boards_with_stats)} boards")
    for bws in boards_with_stats:
        logger.info(f"  - {bws['board'].name}: {bws['task_count']} tasks")
    
    context = {
        'demo_available': True,
        'demo_mode': True,
        'demo_mode_type': request.session.get('demo_mode', 'solo'),
        'current_demo_role': request.session.get('demo_role', 'admin'),
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
    
    SIMPLIFIED MODE (January 2026):
    - Redirect to regular board detail view
    - Demo boards treated as regular boards
    
    LEGACY MODE:
    - ANONYMOUS ACCESS: No login required for demo mode
    - Authenticated users get automatic board membership
    """
    # SIMPLIFIED MODE: Redirect to regular board detail
    if SIMPLIFIED_MODE:
        if request.user.is_authenticated:
            _auto_grant_demo_access(request)
        return redirect('board_detail', board_id=board_id)
    
    # LEGACY MODE: Get the demo organization - using constants
    demo_orgs = Organization.objects.filter(name__in=DEMO_ORG_NAMES)
    browser_fingerprint = request.session.get('browser_fingerprint')
    
    # Get the board - must be a demo board OR a board created by this demo session
    # First try to get it as a demo board
    board = Board.objects.filter(
        id=board_id,
        organization__in=demo_orgs
    ).first()
    
    # If not found in demo orgs, check if it's a user-created board from this session
    if not board and browser_fingerprint:
        board = Board.objects.filter(
            id=board_id,
            created_by_session=browser_fingerprint
        ).first()
    
    if not board:
        from django.http import Http404
        raise Http404("Board not found or not accessible in demo mode")
    
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
    # All restrictions removed - users have full access
    from kanban.permission_utils import (
        get_user_board_membership, 
        get_column_permissions_for_user,
        user_has_board_permission
    )
    
    demo_mode_type = request.session.get('demo_mode', 'solo')
    user_membership = None
    user_role_name = 'Admin'  # Default - all users have full access
    column_permissions = {}
    can_manage_members = True
    can_edit_board = True
    can_create_tasks = True
    
    # All restrictions removed - all users have full admin access
    
    # Get board members - show all board members
    from accounts.models import UserProfile
    board_member_ids = board.members.values_list('id', flat=True)
    board_member_profiles = UserProfile.objects.filter(user_id__in=board_member_ids)
    
    # For adding new members: show all users who aren't on the board yet
    available_org_members = UserProfile.objects.exclude(
        user_id__in=board_member_ids
    ).select_related('user')
    
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
    
    # Ensure Solo mode never shows permission restrictions
    # (column_permissions should already be empty from the RBAC section above,
    # but we double-check here for safety)
    if demo_mode_type != 'team':
        column_permissions = {}  # Force empty for Solo mode
    
    context = {
        'demo_mode': True,
        'demo_mode_type': request.session.get('demo_mode', 'solo'),
        'current_demo_role': request.session.get('demo_role', 'admin'),
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
        'column_permissions': column_permissions,  # Empty for Solo mode, RBAC for Team mode
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
    Reset demo data to original state.
    Available to all authenticated users.
    Supports both AJAX (POST with JSON response) and regular form requests.
    """
    from django.contrib import messages
    
    # Only authenticated users can reset demo data
    if not request.user.is_authenticated:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'error',
                'message': 'You must be logged in to reset demo data.'
            }, status=403)
        messages.error(request, 'You must be logged in to reset demo data.')
        return redirect('demo_dashboard')
    
    if request.method == 'POST':
        try:
            from django.core.management import call_command
            from io import StringIO
            
            # Capture output for logging
            out = StringIO()
            
            # ============================================================
            # STEP 1: Get demo boards
            # ============================================================
            
            # Get all official demo boards (no organization filter needed)
            demo_boards = Board.objects.filter(is_official_demo_board=True)
            
            # ============================================================
            # STEP 2: Clean up user-created data
            # ============================================================
            
            # Delete session-created content (if any)
            session_id = request.session.get('demo_session_id')
            browser_fingerprint = request.session.get('browser_fingerprint')
            
            identifiers_to_clean = []
            if session_id:
                identifiers_to_clean.append(session_id)
            if browser_fingerprint:
                identifiers_to_clean.append(browser_fingerprint)
            
            if identifiers_to_clean:
                # Delete tasks created by session on any board
                Task.objects.filter(
                    created_by_session__in=identifiers_to_clean
                ).delete()
                
                # Delete boards created by session (non-demo boards only)
                Board.objects.filter(
                    created_by_session__in=identifiers_to_clean,
                    is_official_demo_board=False
                ).delete()
            
            # Delete ALL user-created boards (non-demo boards)
            if request.user.is_authenticated:
                Board.objects.filter(
                    created_by=request.user,
                    is_official_demo_board=False
                ).delete()
            
            # Delete user-created tasks on demo boards
            Task.objects.filter(
                column__board__in=demo_boards,
                is_seed_demo_data=False
            ).delete()
            
            # ============================================================
            # STEP 3: Populate all demo data
            # ============================================================
            # The --reset flag ensures it clears and recreates everything
            call_command('populate_all_demo_data', '--reset', stdout=out, stderr=out)
            
            # Refresh all dates to current (burndown, retrospectives, etc.)
            try:
                call_command('refresh_demo_dates', '--force', stdout=out, stderr=out)
            except Exception:
                pass  # Date refresh is optional
            
            # Detect conflicts for fresh data
            try:
                call_command('detect_conflicts', '--clear', stdout=out, stderr=out)
            except Exception:
                pass  # Conflicts detection is optional
            
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
                    event_data={'success': True, 'full_repopulation': True}
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
    demo_boards = Board.objects.filter(is_official_demo_board=True)
    
    task_count = Task.objects.filter(column__board__in=demo_boards).count() if demo_boards.exists() else 0
    user_count = demo_boards.values('members').distinct().count() if demo_boards.exists() else 0
    
    context = {
        'demo_boards': demo_boards,
        'task_count': task_count,
        'user_count': user_count,
    }
    
    return render(request, 'kanban/reset_demo_confirm.html', context)


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


def demo_feature_counts_api(request):
    """
    API endpoint to get real-time counts for demo dashboard banner.
    Returns: unread messages, active conflicts, and wiki pages count.
    """
    try:
        # Get demo organizations and boards
        demo_orgs = Organization.objects.filter(name__in=DEMO_ORG_NAMES)
        demo_boards = Board.objects.filter(
            organization__in=demo_orgs,
            is_official_demo_board=True
        )
        
        # Get UNREAD message count (same logic as demo_dashboard)
        if request.user.is_authenticated:
            # Get chat rooms from demo boards where user is a member
            user_chat_rooms = ChatRoom.objects.filter(
                board__in=demo_boards,
                members=request.user
            )
            
            # Count unread messages across all these rooms
            message_count = 0
            for room in user_chat_rooms:
                room_unread = room.messages.exclude(read_by=request.user).exclude(author=request.user).count()
                message_count += room_unread
        else:
            # For anonymous demo users, show total message count as fallback
            message_count = ChatMessage.objects.filter(
                chat_room__board__in=demo_boards
            ).count()
        
        # Get active conflict count
        conflict_count = ConflictDetection.objects.filter(
            board__in=demo_boards,
            status='active'
        ).count()
        
        # Get wiki pages count
        wiki_count = WikiPage.objects.filter(
            organization__in=demo_orgs
        ).count()
        
        return JsonResponse({
            'message_count': message_count,
            'conflict_count': conflict_count,
            'wiki_count': wiki_count
        })
        
    except Exception as e:
        logger.error(f"Error getting demo feature counts: {e}")
        return JsonResponse({
            'error': str(e)
        }, status=500)


def demo_board_tasks_list(request, board_id):
    """
    Display all tasks for a demo board in a filterable table view
    Provides better UX than navigating through columns
    """
    # Get the demo organization
    demo_orgs = Organization.objects.filter(name__in=DEMO_ORG_NAMES)
    browser_fingerprint = request.session.get('browser_fingerprint')
    
    # Get the board
    board = Board.objects.filter(
        id=board_id,
        organization__in=demo_orgs
    ).first()
    
    # If not found in demo orgs, check if it's a user-created board from this session
    if not board and browser_fingerprint:
        board = Board.objects.filter(
            id=board_id,
            created_by_session=browser_fingerprint
        ).first()
    
    if not board:
        from django.http import Http404
        raise Http404("Board not found or not accessible in demo mode")
    
    # Get filter parameter from URL
    status_filter = request.GET.get('status', 'all')
    
    # Get all tasks with related data
    tasks_queryset = Task.objects.filter(
        column__board=board
    ).select_related(
        'assigned_to', 'assigned_to__profile', 'created_by', 'column'
    ).prefetch_related('labels', 'dependencies').order_by('-created_at')
    
    # Apply filters
    if status_filter == 'completed':
        tasks_queryset = tasks_queryset.filter(progress=100)
    elif status_filter == 'in_progress':
        tasks_queryset = tasks_queryset.filter(progress__gt=0, progress__lt=100)
    elif status_filter == 'not_started':
        tasks_queryset = tasks_queryset.filter(progress=0)
    elif status_filter == 'high_priority':
        tasks_queryset = tasks_queryset.filter(priority__in=['high', 'urgent'])
    
    # Pagination
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(tasks_queryset, 25)  # Show 25 tasks per page
    page_number = request.GET.get('page', 1)
    
    try:
        tasks = paginator.page(page_number)
    except PageNotAnInteger:
        tasks = paginator.page(1)
    except EmptyPage:
        tasks = paginator.page(paginator.num_pages)
    
    # Get statistics
    total_tasks = Task.objects.filter(column__board=board).count()
    completed_count = Task.objects.filter(column__board=board, progress=100).count()
    in_progress_count = Task.objects.filter(column__board=board, progress__gt=0, progress__lt=100).count()
    not_started_count = Task.objects.filter(column__board=board, progress=0).count()
    high_priority_count = Task.objects.filter(column__board=board, priority__in=['high', 'urgent']).count()
    
    # Completion rate
    completion_rate = round((completed_count / total_tasks * 100) if total_tasks > 0 else 0, 1)
    
    context = {
        'board': board,
        'tasks': tasks,
        'status_filter': status_filter,
        'total_tasks': total_tasks,
        'completed_count': completed_count,
        'in_progress_count': in_progress_count,
        'not_started_count': not_started_count,
        'high_priority_count': high_priority_count,
        'completion_rate': completion_rate,
        'demo_mode': request.session.get('demo_mode', 'solo'),
    }
    
    return render(request, 'kanban/demo_board_tasks_list.html', context)


def demo_all_tasks_list(request):
    """
    Display all tasks across all demo boards in a filterable table view
    Provides a unified view of tasks across the entire demo environment
    """
    # Get the demo organization(s)
    demo_orgs = Organization.objects.filter(name__in=DEMO_ORG_NAMES)
    browser_fingerprint = request.session.get('browser_fingerprint')
    
    # Get all demo boards
    demo_boards = Board.objects.filter(organization__in=demo_orgs)
    
    # Also include user-created boards from this session
    if browser_fingerprint:
        user_boards = Board.objects.filter(created_by_session=browser_fingerprint)
        demo_boards = demo_boards | user_boards
    
    # Get filter parameter from URL
    status_filter = request.GET.get('status', 'all')
    
    # Get all tasks with related data
    tasks_queryset = Task.objects.filter(
        column__board__in=demo_boards
    ).select_related(
        'assigned_to', 'assigned_to__profile', 'created_by', 'column', 'column__board'
    ).prefetch_related('labels', 'dependencies').order_by('-created_at')
    
    # Apply filters
    if status_filter == 'completed':
        tasks_queryset = tasks_queryset.filter(progress=100)
    elif status_filter == 'in_progress':
        tasks_queryset = tasks_queryset.filter(progress__gt=0, progress__lt=100)
    elif status_filter == 'not_started':
        tasks_queryset = tasks_queryset.filter(progress=0)
    elif status_filter == 'overdue':
        tasks_queryset = tasks_queryset.filter(
            due_date__lt=timezone.now().date(),
            progress__lt=100
        )
    elif status_filter == 'high_priority':
        tasks_queryset = tasks_queryset.filter(priority__in=['high', 'urgent'])
    
    # Pagination
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(tasks_queryset, 25)  # Show 25 tasks per page
    page_number = request.GET.get('page', 1)
    
    try:
        tasks = paginator.page(page_number)
    except PageNotAnInteger:
        tasks = paginator.page(1)
    except EmptyPage:
        tasks = paginator.page(paginator.num_pages)
    
    # Get statistics
    total_tasks = Task.objects.filter(column__board__in=demo_boards).count()
    completed_count = Task.objects.filter(column__board__in=demo_boards, progress=100).count()
    in_progress_count = Task.objects.filter(column__board__in=demo_boards, progress__gt=0, progress__lt=100).count()
    not_started_count = Task.objects.filter(column__board__in=demo_boards, progress=0).count()
    overdue_count = Task.objects.filter(
        column__board__in=demo_boards,
        due_date__lt=timezone.now().date(),
        progress__lt=100
    ).count()
    high_priority_count = Task.objects.filter(column__board__in=demo_boards, priority__in=['high', 'urgent']).count()
    
    # Completion rate
    completion_rate = round((completed_count / total_tasks * 100) if total_tasks > 0 else 0, 1)
    
    context = {
        'tasks': tasks,
        'status_filter': status_filter,
        'total_tasks': total_tasks,
        'completed_count': completed_count,
        'in_progress_count': in_progress_count,
        'not_started_count': not_started_count,
        'overdue_count': overdue_count,
        'high_priority_count': high_priority_count,
        'completion_rate': completion_rate,
        'demo_mode': request.session.get('demo_mode', 'solo'),
        'all_boards_view': True,
    }
    
    return render(request, 'kanban/demo_all_tasks_list.html', context)


@require_POST
def receive_client_fingerprint(request):
    """
    Receive and store the client-side JavaScript fingerprint.
    This endpoint is called by fingerprint.js after generating a robust fingerprint
    using canvas, WebGL, audio context, and other browser attributes.
    
    This provides stronger abuse prevention than server-side fingerprinting alone.
    """
    import json
    
    if not request.session.get('is_demo_mode'):
        return JsonResponse({
            'status': 'error',
            'message': 'Not in demo mode'
        }, status=403)
    
    try:
        data = json.loads(request.body)
        client_fingerprint = data.get('fingerprint')
        canvas_hash = data.get('canvas')
        webgl_hash = data.get('webgl')
        audio_hash = data.get('audio')
        local_usage = data.get('localUsage', {})
        
        if not client_fingerprint:
            return JsonResponse({
                'status': 'error',
                'message': 'No fingerprint provided'
            }, status=400)
        
        # Update the current DemoSession with client fingerprint
        try:
            from analytics.models import DemoSession, DemoAbusePrevention
            session_id = request.session.session_key
            
            if session_id:
                demo_session = DemoSession.objects.filter(session_id=session_id).first()
                if demo_session:
                    demo_session.client_fingerprint = client_fingerprint
                    demo_session.save(update_fields=['client_fingerprint'])
                    logger.info(f"Updated DemoSession with client fingerprint: {client_fingerprint[:16]}...")
            
            # Also update/create the abuse prevention record with client fingerprint
            # This allows cross-session tracking even when cookies are cleared
            from kanban.utils.demo_abuse_prevention import get_client_ip, get_or_create_abuse_record
            
            ip_address = get_client_ip(request)
            
            # Try to find existing record by client fingerprint (more robust matching)
            existing_by_client_fp = DemoAbusePrevention.objects.filter(
                client_fingerprint=client_fingerprint
            ).first()
            
            if existing_by_client_fp:
                # Update existing record - user returned with cleared cookies
                existing_by_client_fp.last_seen = timezone.now()
                if not existing_by_client_fp.browser_fingerprint:
                    existing_by_client_fp.browser_fingerprint = request.session.get('browser_fingerprint')
                existing_by_client_fp.save()
                logger.info(f"Found existing abuse record by client fingerprint, IP history: {existing_by_client_fp.ip_address}")
            else:
                # Update current record with client fingerprint
                record = get_or_create_abuse_record(request)
                if record and not record.client_fingerprint:
                    record.client_fingerprint = client_fingerprint
                    record.save(update_fields=['client_fingerprint', 'last_seen'])
                    logger.info(f"Added client fingerprint to abuse record: {client_fingerprint[:16]}...")
            
        except Exception as e:
            logger.warning(f"Could not update fingerprint records: {e}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Fingerprint received',
            'fingerprint_stored': True,
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Error receiving client fingerprint: {e}")
        return JsonResponse({
            'status': 'error',
            'message': 'Server error'
        }, status=500)
