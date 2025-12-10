from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages as django_messages
from django.http import JsonResponse, FileResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.contrib.auth.models import User
from django.core.files.storage import default_storage
from django.utils import timezone
import os

from kanban.models import Board, Task
from .models import ChatRoom, ChatMessage, TaskThreadComment, Notification, FileAttachment
from .forms import ChatRoomForm, ChatMessageForm, TaskThreadCommentForm, MentionForm, ChatRoomFileForm


@login_required
def messaging_hub(request):
    """Main messaging hub showing all boards and recent notifications"""
    try:
        profile = request.user.profile
        organization = profile.organization
        
        # Filter boards by organization and membership, consistent with board_list view
        user_boards = Board.objects.filter(
            Q(organization=organization) & 
            (Q(created_by=request.user) | Q(members=request.user))
        ).distinct()
    except:
        # If user has no profile/organization, show no boards
        user_boards = Board.objects.none()
    
    # Calculate unread messages per board
    boards_with_unread = []
    for board in user_boards:
        board_rooms = board.chat_rooms.filter(members=request.user)
        unread_count = 0
        for room in board_rooms:
            unread_count += room.messages.exclude(read_by=request.user).exclude(author=request.user).count()
        boards_with_unread.append({
            'board': board,
            'unread_count': unread_count
        })
    
    unread_notifications = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).order_by('-created_at')[:10]
    
    context = {
        'boards_with_unread': boards_with_unread,
        'unread_notifications': unread_notifications,
    }
    return render(request, 'messaging/messaging_hub.html', context)


@login_required
def chat_room_list(request, board_id):
    """List all chat rooms for a board"""
    board = get_object_or_404(Board, id=board_id)
    
    # Check if user is board member
    if request.user not in board.members.all():
        django_messages.error(request, 'You do not have access to this board.')
        return redirect('board_list')
    
    chat_rooms = board.chat_rooms.all()
    
    # Add unread count for each chat room
    chat_rooms_with_unread = []
    total_unread_in_board = 0
    for room in chat_rooms:
        unread_count = room.messages.exclude(read_by=request.user).exclude(author=request.user).count()
        chat_rooms_with_unread.append({
            'room': room,
            'unread_count': unread_count
        })
        total_unread_in_board += unread_count
    
    context = {
        'board': board,
        'chat_rooms_with_unread': chat_rooms_with_unread,
        'total_unread_in_board': total_unread_in_board,
    }
    return render(request, 'messaging/chat_room_list.html', context)


@login_required
def chat_room_detail(request, room_id):
    """Display a specific chat room"""
    chat_room = get_object_or_404(ChatRoom, id=room_id)
    
    # Check if user is member
    if request.user not in chat_room.members.all():
        django_messages.error(request, 'You do not have access to this room.')
        return redirect('board_list')
    
    # Mark all notifications related to this chat room as read
    Notification.objects.filter(
        recipient=request.user,
        chat_message__chat_room=chat_room,
        is_read=False
    ).update(is_read=True)
    
    # Get recent messages (last 50)
    chat_messages = chat_room.messages.all().order_by('-created_at')[:50]
    chat_messages = reversed(list(chat_messages))
    
    form = ChatMessageForm()
    
    # Get list of message IDs that current user has read
    # Include messages from the current user (they don't need to be marked as read)
    read_message_ids = set(chat_room.messages.filter(
        Q(read_by=request.user) | Q(author=request.user)
    ).values_list('id', flat=True))
    
    context = {
        'chat_room': chat_room,
        'chat_messages': chat_messages,
        'form': form,
        'read_message_ids': read_message_ids,
    }
    return render(request, 'messaging/chat_room_detail.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def create_chat_room(request, board_id):
    """Create a new chat room for a board"""
    board = get_object_or_404(Board, id=board_id)
    
    # Check if user is board admin/creator
    if request.user != board.created_by and request.user not in board.members.all():
        django_messages.error(request, 'You do not have permission to create rooms.')
        return redirect('chat_room_list', board_id=board_id)
    
    if request.method == 'POST':
        form = ChatRoomForm(request.POST, board=board)
        if form.is_valid():
            chat_room = form.save(commit=False)
            chat_room.board = board
            chat_room.created_by = request.user
            chat_room.save()
            
            # Add members
            form.save_m2m()
            
            # Always add creator as member
            chat_room.members.add(request.user)
            
            django_messages.success(request, f'Chat room "{chat_room.name}" created successfully!')
            return redirect('chat_room_detail', room_id=chat_room.id)
    else:
        form = ChatRoomForm(board=board)
    
    context = {
        'form': form,
        'board': board,
    }
    return render(request, 'messaging/create_chat_room.html', context)


@login_required
@require_http_methods(["POST"])
def send_chat_message(request, room_id):
    """Send a message to a chat room (for non-WebSocket clients)"""
    chat_room = get_object_or_404(ChatRoom, id=room_id)
    
    if request.user not in chat_room.members.all():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    form = ChatMessageForm(request.POST)
    if form.is_valid():
        message = form.save(commit=False)
        message.chat_room = chat_room
        message.author = request.user
        message.save()
        
        # Process mentions
        message.notify_mentioned_users()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'id': message.id,
                'username': message.author.username,
                'message': message.content,
                'timestamp': message.created_at.isoformat(),
            })
        else:
            return redirect('chat_room_detail', room_id=room_id)
    
    return JsonResponse({'error': 'Invalid message'}, status=400)


@login_required
@require_http_methods(["GET", "POST"])
def task_thread_comments(request, task_id):
    """View and manage real-time task thread comments"""
    task = get_object_or_404(Task, id=task_id)
    
    # Check if user has access to this task
    board = task.column.board
    if request.user not in board.members.all():
        django_messages.error(request, 'You do not have access to this task.')
        return redirect('board_list')
    
    if request.method == 'POST':
        form = TaskThreadCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.task = task
            comment.author = request.user
            comment.save()
            
            # Process mentions
            comment.notify_mentioned_users()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'id': comment.id,
                    'username': comment.author.username,
                    'content': comment.content,
                    'timestamp': comment.created_at.isoformat(),
                }, status=201)
            else:
                django_messages.success(request, 'Comment added successfully!')
                return redirect('task_thread_comments', task_id=task_id)
    else:
        form = TaskThreadCommentForm()
    
    # Mark all notifications related to this task as read
    Notification.objects.filter(
        recipient=request.user,
        task_thread_comment__task=task,
        is_read=False
    ).update(is_read=True)
    
    comments = task.thread_comments.all().order_by('-created_at')
    
    context = {
        'task': task,
        'comments': comments,
        'form': form,
    }
    return render(request, 'messaging/task_thread_comments.html', context)


@login_required
@require_http_methods(["GET"])
def get_mentions(request):
    """API endpoint for mention autocomplete"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 1:
        return JsonResponse({'results': []})
    
    # Find users matching the query
    users = User.objects.filter(
        Q(username__istartswith=query) | Q(first_name__istartswith=query)
    ).values('id', 'username', 'first_name')[:10]
    
    results = [
        {
            'id': user['id'],
            'text': user['username'],
            'display': f"{user['username']}" + (f" ({user['first_name']})" if user['first_name'] else "")
        }
        for user in users
    ]
    
    return JsonResponse({'results': results})


@login_required
def notifications(request):
    """View all notifications for the user"""
    user_notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    
    # Mark as read if requested
    if request.GET.get('mark_read'):
        user_notifications.filter(is_read=False).update(is_read=True)
        django_messages.success(request, 'All notifications marked as read.')
        return redirect('messaging:notifications')
    
    context = {
        'notifications': user_notifications,
    }
    return render(request, 'messaging/notifications.html', context)


@login_required
@require_http_methods(["POST"])
def mark_notification_read(request, notification_id):
    """Mark a notification as read"""
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notification.mark_as_read()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    return redirect('notifications')


@login_required
@require_http_methods(["GET"])
def get_unread_notification_count(request):
    """API endpoint to get unread notification count"""
    count = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()
    
    return JsonResponse({'count': count})


@login_required
@require_http_methods(["GET"])
def message_history(request, room_id):
    """Get message history for a chat room (pagination)"""
    chat_room = get_object_or_404(ChatRoom, id=room_id)
    
    if request.user not in chat_room.members.all():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    offset = int(request.GET.get('offset', 0))
    limit = 20
    
    messages = chat_room.messages.all().order_by('-created_at')[offset:offset + limit]
    messages = reversed(list(messages))
    
    messages_data = [
        {
            'id': msg.id,
            'username': msg.author.username,
            'content': msg.content,
            'timestamp': msg.created_at.isoformat(),
            'mentioned_users': [u.username for u in msg.mentioned_users.all()]
        }
        for msg in messages
    ]
    
    return JsonResponse({'messages': messages_data})


@login_required
@require_http_methods(["GET"])
def task_comment_history(request, task_id):
    """Get comment history for a task (pagination)"""
    task = get_object_or_404(Task, id=task_id)
    board = task.column.board
    
    if request.user not in board.members.all():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    offset = int(request.GET.get('offset', 0))
    limit = 20
    
    comments = task.comments.all().order_by('-created_at')[offset:offset + limit]
    comments = reversed(list(comments))
    
    comments_data = [
        {
            'id': comment.id,
            'username': comment.author.username,
            'content': comment.content,
            'timestamp': comment.created_at.isoformat(),
            'mentioned_users': [u.username for u in comment.mentioned_users.all()]
        }
        for comment in comments
    ]
    
    return JsonResponse({'comments': comments_data})


@login_required
@require_http_methods(["GET"])
def get_unread_message_count(request):
    """API endpoint to get unread message count for the current user
    
    Counts messages that the user hasn't marked as read yet.
    Optional query parameter:
    - board_id: If provided, only count messages from chat rooms in this board
    """
    board_id = request.GET.get('board_id')
    
    # Get all chat rooms the user is a member of
    user_chat_rooms = ChatRoom.objects.filter(members=request.user)
    
    # If board_id is provided, filter to only that board
    if board_id:
        try:
            board_id = int(board_id)
            user_chat_rooms = user_chat_rooms.filter(board_id=board_id)
        except (ValueError, TypeError):
            pass  # Invalid board_id, ignore the filter
    
    # Count total unread messages
    # Messages are unread if: the user hasn't marked them as read AND they're not from the user
    unread_count = 0
    for room in user_chat_rooms:
        # Count messages from this room that the current user hasn't read
        room_unread = room.messages.exclude(read_by=request.user).exclude(author=request.user).count()
        unread_count += room_unread
    
    return JsonResponse({'unread_count': unread_count})


@login_required
@require_http_methods(["POST"])
def mark_chat_message_read(request, message_id):
    """Mark a specific chat message as read by the current user"""
    message = get_object_or_404(ChatMessage, id=message_id)
    
    # Check if user is member of the room
    if request.user not in message.chat_room.members.all():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    # Mark message as read by this user
    message.read_by.add(request.user)
    
    # Check if all members have read it
    chat_room = message.chat_room
    total_members = chat_room.members.count()
    read_count = message.read_by.count()
    
    all_read = read_count >= total_members
    
    if all_read:
        message.is_read = True
        message.read_at = timezone.now()
        message.save()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message_id': message_id,
            'read_count': read_count,
            'total_members': total_members,
            'all_read': all_read
        })
    
    return redirect('messaging:chat_room_detail', room_id=message.chat_room.id)


@login_required
@require_http_methods(["GET"])
def get_unread_message_count_v2(request):
    """API endpoint to get count of unread messages for the current user
    
    This counts messages that haven't been marked as read by the user.
    Optional query parameter:
    - board_id: If provided, only count messages from chat rooms in this board
    """
    board_id = request.GET.get('board_id')
    
    # Get all chat rooms the user is a member of
    user_chat_rooms = ChatRoom.objects.filter(members=request.user)
    
    # If board_id is provided, filter to only that board
    if board_id:
        try:
            board_id = int(board_id)
            user_chat_rooms = user_chat_rooms.filter(board_id=board_id)
        except (ValueError, TypeError):
            pass
    
    # Count messages the user hasn't marked as read
    unread_count = 0
    for room in user_chat_rooms:
        # Count messages that the current user hasn't read
        unread_msgs = room.messages.exclude(read_by=request.user).exclude(author=request.user).count()
        unread_count += unread_msgs
    
    return JsonResponse({'unread_count': unread_count})


@login_required
@require_http_methods(["POST"])
def mark_room_messages_read(request, room_id):
    """Mark all messages in a chat room as read by the current user"""
    chat_room = get_object_or_404(ChatRoom, id=room_id)
    
    if request.user not in chat_room.members.all():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    # Get all messages the user hasn't read
    messages_to_mark = chat_room.messages.exclude(read_by=request.user)
    
    count = 0
    for message in messages_to_mark:
        message.read_by.add(request.user)
        count += 1
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'room_id': room_id,
            'messages_marked_read': count
        })
    
    return redirect('messaging:chat_room_detail', room_id=room_id)


@login_required
@require_http_methods(["DELETE"])
def delete_chat_message(request, message_id):
    """Delete a specific chat message"""
    message = get_object_or_404(ChatMessage, id=message_id)
    
    # Check if user is the author or a room creator
    chat_room = message.chat_room
    is_creator = request.user == chat_room.created_by
    is_author = request.user == message.author
    
    if not (is_author or is_creator or request.user.is_staff):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    message_id = message.id
    message.delete()
    
    return JsonResponse({
        'success': True,
        'message': f'Message deleted successfully',
        'message_id': message_id
    })


@login_required
@require_http_methods(["POST"])
def clear_chat_room_messages(request, room_id):
    """Delete all messages in a chat room"""
    chat_room = get_object_or_404(ChatRoom, id=room_id)
    
    # Check if user is room creator or staff
    if request.user != chat_room.created_by and not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized - only room creator can clear all messages'}, status=403)
    
    # Get count before deletion
    count = chat_room.messages.count()
    
    # Delete all messages
    chat_room.messages.all().delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': f'{count} messages deleted successfully',
            'count': count
        })
    else:
        django_messages.success(request, f'All {count} messages have been deleted from the room.')
        return redirect('messaging:chat_room_detail', room_id=room_id)


@login_required
def go_to_first_unread_room(request):
    """Redirect user to the first chat room with unread messages, or to messaging hub if none"""
    from django.utils import timezone
    from datetime import timedelta
    
    # Get all chat rooms the user is a member of
    user_chat_rooms = ChatRoom.objects.filter(members=request.user).order_by('-created_at')
    
    # Get board_id from query params if available
    board_id = request.GET.get('board_id')
    if board_id:
        try:
            board_id = int(board_id)
            user_chat_rooms = user_chat_rooms.filter(board_id=board_id)
        except (ValueError, TypeError):
            pass
    
    # Find first room with unread messages
    recent_cutoff = timezone.now() - timedelta(hours=24)
    
    for room in user_chat_rooms:
        unread_count = room.messages.filter(
            created_at__gte=recent_cutoff
        ).exclude(author=request.user).count()
        
        if unread_count > 0:
            return redirect('messaging:chat_room_detail', room_id=room.id)
    
    # No unread messages found, go to messaging hub
    return redirect('messaging:hub')


# ===== FILE MANAGEMENT VIEWS FOR CHAT ROOMS =====

@login_required
@require_http_methods(["POST"])
def upload_chat_room_file(request, room_id):
    """Upload a file to a chat room"""
    chat_room = get_object_or_404(ChatRoom, id=room_id)
    
    # Check if user is member
    if request.user not in chat_room.members.all():
        django_messages.error(request, 'You do not have access to this room.')
        return redirect('messaging:chat_room_list', board_id=chat_room.board.id)
    
    if request.method == 'POST':
        form = ChatRoomFileForm(request.POST, request.FILES)
        if form.is_valid():
            file_obj = form.save(commit=False)
            file_obj.chat_room = chat_room
            file_obj.uploaded_by = request.user
            # Filename, size, and type are now set by form.save() with proper sanitization
            file_obj.save()
            
            # Create a system message to notify about file upload
            # Use emoji icons instead of HTML for plain text storage
            file_icon_map = {
                'pdf': '📄',
                'doc': '📝',
                'docx': '📝',
                'xls': '📊',
                'xlsx': '📊',
                'ppt': '🎯',
                'pptx': '🎯',
                'jpg': '🖼️',
                'jpeg': '🖼️',
                'png': '🖼️',
            }
            file_icon = file_icon_map.get(file_obj.file_type.lower(), '📎')
            system_message_text = f'📎 {request.user.username} uploaded {file_icon} {file_obj.filename}'
            system_message = ChatMessage.objects.create(
                chat_room=chat_room,
                author=request.user,
                content=system_message_text
            )
            
            # Create notifications for other room members
            for member in chat_room.members.all():
                if member != request.user:  # Don't notify the uploader
                    Notification.objects.create(
                        recipient=member,
                        sender=request.user,
                        notification_type='CHAT_MESSAGE',
                        chat_message=system_message,
                        text=f'{request.user.username} uploaded {file_obj.filename} in {chat_room.name}'
                    )
            
            # Broadcast file upload to all room members via WebSocket
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            
            channel_layer = get_channel_layer()
            room_group_name = f'chat_room_{chat_room.id}'
            
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    room_group_name,
                    {
                        'type': 'file_uploaded',
                        'file_id': file_obj.id,
                        'filename': file_obj.filename,
                        'file_type': file_obj.file_type,
                        'file_size': file_obj.file_size,
                        'uploaded_by': request.user.username,
                        'uploaded_at': file_obj.uploaded_at.isoformat(),
                        'description': file_obj.description or '',
                        'uploader_id': request.user.id
                    }
                )
                
                # Also trigger notification count update
                async_to_sync(channel_layer.group_send)(
                    room_group_name,
                    {
                        'type': 'notification_count_update',
                        'trigger': 'file_upload'
                    }
                )
            
            django_messages.success(request, f'File "{file_obj.filename}" uploaded successfully!')
            
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
    
    return redirect('messaging:chat_room_detail', room_id=room_id)


@login_required
@require_http_methods(["GET"])
def download_chat_room_file(request, file_id):
    """Download a file from a chat room"""
    file_obj = get_object_or_404(FileAttachment, id=file_id)
    
    # Check if user is member of the room
    if request.user not in file_obj.chat_room.members.all():
        django_messages.error(request, 'You do not have access to this file.')
        return redirect('messaging:hub')
    
    # Serve the file
    if file_obj.file:
        response = FileResponse(file_obj.file.open('rb'), as_attachment=True)
        response['Content-Disposition'] = f'attachment; filename="{file_obj.filename}"'
        return response
    
    django_messages.error(request, 'File not found.')
    return redirect('messaging:chat_room_detail', room_id=file_obj.chat_room.id)


@login_required
@require_http_methods(["POST"])
def delete_chat_room_file(request, file_id):
    """Delete (soft delete) a file from a chat room"""
    file_obj = get_object_or_404(FileAttachment, id=file_id)
    chat_room = file_obj.chat_room
    
    # Check permissions - only uploader, room creator, or staff can delete
    if request.user not in [file_obj.uploaded_by, chat_room.created_by] and not request.user.is_staff:
        django_messages.error(request, 'You do not have permission to delete this file.')
        return redirect('messaging:chat_room_detail', room_id=chat_room.id)
    
    # Soft delete
    file_obj.deleted_at = timezone.now()
    file_obj.save()
    
    django_messages.success(request, f'File "{file_obj.filename}" deleted.')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    return redirect('messaging:chat_room_detail', room_id=chat_room.id)


@login_required
@require_http_methods(["GET"])
def list_chat_room_files(request, room_id):
    """Get a list of files in a chat room (JSON API)"""
    chat_room = get_object_or_404(ChatRoom, id=room_id)
    
    # Check if user is member
    if request.user not in chat_room.members.all():
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    # Get non-deleted files
    files = chat_room.file_attachments.filter(deleted_at__isnull=True).values(
        'id', 'filename', 'file_type', 'file_size', 'uploaded_by__username', 'uploaded_at', 'description'
    )
    
    return JsonResponse({
        'success': True,
        'files': list(files)
    })
