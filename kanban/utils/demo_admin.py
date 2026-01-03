"""
Virtual Demo Admin User Management

This module provides utilities for creating and managing a virtual admin user
for Solo demo mode. When users enter Solo mode, they are logged in as this
virtual admin user, which gives them full access to all demo features without
needing to check permissions in every view.

SOLO MODE: User is logged in as demo_admin → full admin access everywhere
TEAM MODE: User uses their session role → RBAC applies via DemoPermissions
"""

from django.contrib.auth.models import User
from django.contrib.auth import login, logout
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

# Constants for the demo admin user
DEMO_ADMIN_USERNAME = 'demo_admin_solo'
DEMO_ADMIN_EMAIL = 'demo_admin@prizmaidemo.internal'
DEMO_ADMIN_FIRST_NAME = 'Demo'
DEMO_ADMIN_LAST_NAME = 'Admin'


def get_or_create_demo_admin():
    """
    Get or create the virtual demo admin user.
    
    This user is used for Solo demo mode to provide full admin access
    without requiring authentication checks in every view.
    
    Returns:
        User: The demo admin user instance
    """
    try:
        with transaction.atomic():
            demo_admin, created = User.objects.get_or_create(
                username=DEMO_ADMIN_USERNAME,
                defaults={
                    'email': DEMO_ADMIN_EMAIL,
                    'first_name': DEMO_ADMIN_FIRST_NAME,
                    'last_name': DEMO_ADMIN_LAST_NAME,
                    'is_active': True,
                    'is_staff': False,  # Not actual staff, just demo
                }
            )
            
            if created:
                # Set simple demo password for easy testing
                demo_admin.set_password('demo123')
                demo_admin.save()
                logger.info(f"Created virtual demo admin user: {DEMO_ADMIN_USERNAME} with password 'demo123'")
                
                # Create profile and assign to demo organization
                _setup_demo_admin_profile(demo_admin)
            else:
                # Update existing user password
                demo_admin.set_password('demo123')
                demo_admin.save()
            
            return demo_admin
            
    except Exception as e:
        logger.error(f"Error creating demo admin user: {e}")
        raise


def _setup_demo_admin_profile(demo_admin):
    """
    Set up the demo admin's profile with demo organization membership.
    
    Args:
        demo_admin: The demo admin User instance
    """
    from accounts.models import Organization, UserProfile
    from kanban.models import Board
    from kanban.permission_models import BoardMembership, Role
    
    try:
        # Get or create demo organization
        demo_org = Organization.objects.filter(
            name__in=['Demo - Acme Corporation', 'Demo Organization']
        ).first()
        
        if not demo_org:
            logger.warning("Demo organization not found. Profile setup incomplete.")
            return
        
        # Create or update profile
        profile, _ = UserProfile.objects.get_or_create(
            user=demo_admin,
            defaults={
                'organization': demo_org,
                'is_admin': True,
            }
        )
        
        if profile.organization != demo_org:
            profile.organization = demo_org
            profile.is_admin = True
            profile.save()
        
        # Add demo admin to all demo boards with Admin role
        _add_demo_admin_to_boards(demo_admin, demo_org)
        
        logger.info(f"Demo admin profile setup complete for org: {demo_org.name}")
        
    except Exception as e:
        logger.error(f"Error setting up demo admin profile: {e}")


def _add_demo_admin_to_boards(demo_admin, demo_org):
    """
    Add the demo admin to all demo boards with Admin role.
    
    Args:
        demo_admin: The demo admin User instance
        demo_org: The demo Organization instance
    """
    from kanban.models import Board
    from kanban.permission_models import BoardMembership, Role
    
    try:
        # Get admin role for this organization
        admin_role = Role.objects.filter(
            name='Admin',
            organization=demo_org
        ).first()
        
        if not admin_role:
            # Try to find any Admin role in the demo org or create one
            admin_role, _ = Role.objects.get_or_create(
                name='Admin',
                organization=demo_org,
                defaults={
                    'description': 'Full access to all features',
                    'is_system_role': True,
                    'permissions': [
                        # Board permissions
                        'board.view', 'board.create', 'board.edit', 'board.delete',
                        'board.manage_members', 'board.export',
                        # Column permissions
                        'column.create', 'column.edit', 'column.delete', 'column.reorder',
                        # Task permissions
                        'task.view', 'task.create', 'task.edit', 'task.delete',
                        'task.assign', 'task.move',
                        # Comment permissions
                        'comment.view', 'comment.create', 'comment.edit', 'comment.delete',
                        # Label permissions
                        'label.view', 'label.create', 'label.edit', 'label.delete', 'label.assign',
                        # File permissions
                        'file.view', 'file.upload', 'file.download', 'file.delete',
                        # Sprint permissions
                        'sprint.view', 'sprint.create', 'sprint.edit', 'sprint.delete', 'sprint.manage_tasks',
                        # Analytics
                        'analytics.view', 'analytics.export',
                    ]
                }
            )
        
        # Get all demo boards
        demo_boards = Board.objects.filter(organization=demo_org)
        
        for board in demo_boards:
            # Add as board member
            if demo_admin not in board.members.all():
                board.members.add(demo_admin)
            
            # Create BoardMembership with Admin role
            BoardMembership.objects.get_or_create(
                user=demo_admin,
                board=board,
                defaults={'role': admin_role}
            )
        
        # Add demo admin to chat rooms for demo boards
        _add_demo_admin_to_chat_rooms(demo_admin, demo_boards)
        
        logger.info(f"Demo admin added to {demo_boards.count()} demo boards")
        
    except Exception as e:
        logger.error(f"Error adding demo admin to boards: {e}")


def _add_demo_admin_to_chat_rooms(demo_admin, demo_boards):
    """
    Add demo admin to chat rooms for the demo boards.
    
    Args:
        demo_admin: The demo admin User instance
        demo_boards: QuerySet of demo Board instances
    """
    try:
        from messaging.models import ChatRoom
        
        for board in demo_boards:
            # Find chat rooms associated with this board
            chat_rooms = ChatRoom.objects.filter(board=board)
            for room in chat_rooms:
                if demo_admin not in room.members.all():
                    room.members.add(demo_admin)
        
    except Exception as e:
        # Chat rooms might not exist or be configured differently
        logger.debug(f"Could not add demo admin to chat rooms: {e}")


def login_as_demo_admin(request):
    """
    Log in the current request as the demo admin user.
    
    This is called when a user enters Solo demo mode to give them
    full admin access throughout the demo experience.
    
    Args:
        request: The Django request object
        
    Returns:
        bool: True if login successful, False otherwise
    """
    try:
        # Store the original user info if they were logged in
        if request.user.is_authenticated:
            request.session['original_user_id'] = request.user.id
            request.session['was_authenticated_before_demo'] = True
        else:
            request.session['was_authenticated_before_demo'] = False
        
        # Get or create the demo admin
        demo_admin = get_or_create_demo_admin()
        
        # Ensure profile exists and is set up
        ensure_demo_admin_profile(demo_admin)
        
        # Log in as demo admin
        login(request, demo_admin, backend='django.contrib.auth.backends.ModelBackend')
        
        logger.info(f"User logged in as demo admin for Solo mode. Session: {request.session.session_key}")
        return True
        
    except Exception as e:
        logger.error(f"Error logging in as demo admin: {e}")
        return False


def ensure_demo_admin_profile(demo_admin):
    """
    Ensure the demo admin has a valid profile with demo org membership.
    Called before each login to make sure the profile is still valid.
    
    Args:
        demo_admin: The demo admin User instance
    """
    from accounts.models import Organization, UserProfile
    
    try:
        # Check if profile exists
        if not hasattr(demo_admin, 'profile'):
            _setup_demo_admin_profile(demo_admin)
            return
        
        # Check if organization is valid
        if not demo_admin.profile.organization:
            demo_org = Organization.objects.filter(
                name__in=['Demo - Acme Corporation', 'Demo Organization']
            ).first()
            if demo_org:
                demo_admin.profile.organization = demo_org
                demo_admin.profile.is_admin = True
                demo_admin.profile.save()
                _add_demo_admin_to_boards(demo_admin, demo_org)
                
    except Exception as e:
        logger.error(f"Error ensuring demo admin profile: {e}")
        # Try to set up profile from scratch
        _setup_demo_admin_profile(demo_admin)


def logout_demo_admin(request):
    """
    Log out the demo admin and restore the original user if they were logged in.
    
    This is called when exiting demo mode.
    
    Args:
        request: The Django request object
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        was_authenticated = request.session.get('was_authenticated_before_demo', False)
        original_user_id = request.session.get('original_user_id')
        
        # Log out the demo admin
        logout(request)
        
        # If the user was originally logged in, restore their session
        if was_authenticated and original_user_id:
            try:
                original_user = User.objects.get(id=original_user_id)
                login(request, original_user, backend='django.contrib.auth.backends.ModelBackend')
                logger.info(f"Restored original user: {original_user.username}")
            except User.DoesNotExist:
                logger.warning(f"Original user {original_user_id} not found")
        
        # Clean up demo session variables
        _cleanup_demo_session(request)
        
        return True
        
    except Exception as e:
        logger.error(f"Error logging out demo admin: {e}")
        return False


def _cleanup_demo_session(request):
    """
    Clean up all demo-related session variables.
    
    Args:
        request: The Django request object
    """
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
        'original_user_id',
        'was_authenticated_before_demo',
        'demo_admin_logged_in',
    ]
    
    for key in demo_keys:
        if key in request.session:
            del request.session[key]
    
    request.session.modified = True


def is_demo_admin_user(user):
    """
    Check if the given user is the virtual demo admin.
    
    Args:
        user: A User instance
        
    Returns:
        bool: True if user is the demo admin
    """
    if not user or not user.is_authenticated:
        return False
    return user.username == DEMO_ADMIN_USERNAME
