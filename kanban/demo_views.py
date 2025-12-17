"""
Demo Mode Views
Provides a consistent demo environment for all users without RBAC restrictions
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta
from kanban.models import Board, Task, Column, Organization
from messaging.models import ChatRoom, ChatMessage
from kanban.conflict_models import ConflictDetection
from wiki.models import WikiPage


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
    
    # Get overdue tasks
    overdue_count = Task.objects.filter(
        column__board__in=demo_boards,
        due_date__lt=timezone.now()
    ).exclude(
        column__name__icontains='done'
    ).count()
    
    # Get tasks due soon
    due_soon = Task.objects.filter(
        column__board__in=demo_boards,
        due_date__range=[timezone.now(), timezone.now() + timedelta(days=3)]
    ).count()
    
    # Get demo tasks sorted by urgency (for display)
    demo_tasks = Task.objects.filter(
        column__board__in=demo_boards
    ).exclude(
        Q(column__name__icontains='done') |
        Q(column__name__icontains='closed') |
        Q(column__name__icontains='completed') |
        Q(progress=100)
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
