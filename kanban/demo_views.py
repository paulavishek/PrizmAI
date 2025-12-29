"""
Demo Mode Views
Provides a consistent demo environment for all users without RBAC restrictions
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from datetime import timedelta
from kanban.models import Board, Task, Column, Organization
from messaging.models import ChatRoom, ChatMessage
from kanban.conflict_models import ConflictDetection
from wiki.models import WikiPage


@login_required
def demo_mode_selection(request):
    """
    Demo mode selection screen - choose between Solo or Team mode
    This is the entry point for the new demo experience
    """
    if request.method == 'POST':
        mode = request.POST.get('mode', 'solo')  # 'solo' or 'team'
        selection_method = request.POST.get('selection_method', 'selected')  # 'selected' or 'skipped'
        
        # Initialize demo session
        request.session['is_demo_mode'] = True
        request.session['demo_mode'] = mode
        request.session['demo_mode_selected'] = True
        request.session['demo_role'] = 'admin'  # Start as admin in both modes
        request.session['demo_session_id'] = request.session.session_key
        request.session['demo_started_at'] = timezone.now().isoformat()
        request.session['demo_expires_at'] = (timezone.now() + timedelta(hours=48)).isoformat()
        request.session['features_explored'] = []
        request.session['aha_moments'] = []
        request.session['nudges_shown'] = []
        
        # Create DemoSession record (if models exist)
        try:
            from analytics.models import DemoSession, DemoAnalytics
            
            # Create or update demo session
            demo_session, created = DemoSession.objects.get_or_create(
                session_id=request.session.session_key,
                defaults={
                    'demo_mode': mode,
                    'current_role': 'admin',
                    'expires_at': timezone.now() + timedelta(hours=48),
                    'selection_method': selection_method,
                }
            )
            
            if not created:
                # Update existing session
                demo_session.demo_mode = mode
                demo_session.selection_method = selection_method
                demo_session.save()
            
            # Track selection event
            DemoAnalytics.objects.create(
                session_id=request.session.session_key,
                event_type='demo_mode_selected',
                event_data={
                    'mode': mode,
                    'selection_method': selection_method
                }
            )
        except Exception as e:
            # Analytics models may not exist yet - that's OK
            pass
        
        return redirect('demo_dashboard')
    
    # GET request - show selection screen
    return render(request, 'demo/mode_selection.html')


@login_required
@require_POST
def switch_demo_role(request):
    """
    Switch between demo roles (Admin/Member/Viewer) in Team mode
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


@login_required
def demo_dashboard(request):
    """
    Demo dashboard - shows demo boards to ALL authenticated users
    This bypasses RBAC and provides a consistent tutorial environment
    
    IMPORTANT: Automatically adds users as members when they access demo mode
    """
    # Check if demo mode has been selected
    if not request.session.get('demo_mode_selected'):
        return redirect('demo_mode_selection')
    
    # Get the demo organizations
    demo_org_names = ['Dev Team', 'Marketing Team']
    demo_orgs = Organization.objects.filter(name__in=demo_org_names)
    
    if not demo_orgs.exists():
        # No demo data available
        context = {
            'demo_available': False,
            'demo_boards': [],
            'message': 'Demo data has not been set up yet. Please contact your administrator.'
        }
        return render(request, 'kanban/demo_dashboard.html', context)
    
    # Get demo boards - these are visible to ALL users
    demo_board_names = ['Software Project', 'Bug Tracking', 'Marketing Campaign']
    demo_boards = Board.objects.filter(
        organization__in=demo_orgs,
        name__in=demo_board_names
    ).prefetch_related('members')
    
    if not demo_boards.exists():
        context = {
            'demo_available': False,
            'demo_boards': [],
            'message': 'Demo boards not found. Please run: python manage.py populate_test_data'
        }
        return render(request, 'kanban/demo_dashboard.html', context)
    
    # Auto-grant access: First time user visits demo, automatically add them to demo boards
    # This provides seamless access to demo data without explicit "Load Demo Data" button
    user_demo_orgs = Organization.objects.filter(
        name__in=demo_org_names,
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
            name__in=demo_org_names,
            boards__members=request.user
        ).distinct()
    
    # Filter to show boards only from organizations user has access to
    demo_boards = demo_boards.filter(organization__in=user_demo_orgs)
    
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
    }
    
    return render(request, 'kanban/demo_dashboard.html', context)


@login_required
def demo_board_detail(request, board_id):
    """
    Demo board detail - shows a demo board to ALL authenticated users
    This bypasses RBAC checks completely
    
    IMPORTANT: Automatically adds users as members when they access demo boards
    """
    # Get the demo organizations
    demo_org_names = ['Dev Team', 'Marketing Team']
    demo_orgs = Organization.objects.filter(name__in=demo_org_names)
    
    # Get the board - must be a demo board
    board = get_object_or_404(
        Board,
        id=board_id,
        organization__in=demo_orgs
    )
    
    # Organization-level access check: user must have access to at least one board in this org
    user_has_org_access = Board.objects.filter(
        organization=board.organization,
        members=request.user
    ).exists()
    
    if not user_has_org_access:
        # Auto-grant access when user clicks on a demo board
        from kanban.permission_models import BoardMembership, Role
        from messaging.models import ChatRoom
        
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
    
    # Get columns and tasks
    columns = Column.objects.filter(board=board).order_by('position')
    
    # Get all tasks with related data
    tasks_by_column = {}
    for column in columns:
        tasks = Task.objects.filter(column=column).select_related(
            'assigned_to', 'created_by'
        ).prefetch_related('labels', 'dependencies', 'dependents')
        tasks_by_column[column.id] = tasks
    
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
    ).select_related('task1', 'task2')
    
    # Get wiki pages
    wiki_pages = WikiPage.objects.filter(
        organization=board.organization
    )[:5]  # Show first 5
    
    context = {
        'demo_mode': True,
        'demo_mode_type': request.session.get('demo_mode', 'solo'),
        'current_demo_role': request.session.get('demo_role', 'admin'),
        'demo_expires_at': request.session.get('demo_expires_at'),
        'board': board,
        'columns': columns,
        'tasks_by_column': tasks_by_column,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'chat_rooms': chat_rooms,
        'conflicts': conflicts,
        'wiki_pages': wiki_pages,
        'can_edit': False,  # Demo mode is read-only for safety
    }
    
    return render(request, 'kanban/demo_board_detail.html', context)


@login_required
def reset_demo_data(request):
    """
    Reset demo data to original state
    Supports both AJAX (POST with JSON response) and regular form requests
    """
    from django.contrib import messages
    
    # Check if user is in demo mode (for session-based reset)
    is_demo_user = request.session.get('is_demo_mode', False)
    
    # Superusers can reset anytime, demo users can reset their session
    if not (request.user.is_superuser or is_demo_user):
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
            
            # Reset official demo boards' tasks to default state
            # For now, we'll just clear and repopulate
            # In production, you might want to restore from a baseline
            for board in demo_boards:
                # Clear existing tasks
                Task.objects.filter(column__board=board).delete()
            
            # Repopulate demo data
            from django.core.management import call_command
            from io import StringIO
            output = StringIO()
            call_command('populate_demo_data', '--reset', stdout=output, stderr=output)
            
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
