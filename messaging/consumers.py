import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import ChatMessage, ChatRoom, TaskThreadComment, UserTypingStatus, Notification
from kanban.models import Task
from datetime import datetime


class ChatRoomConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time chat room messaging"""
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_room_{self.room_id}'
        self.user = self.scope['user']
        
        # Check if user is authorized
        if not self.user.is_authenticated:
            await self.close()
            return
        
        is_authorized = await self.is_user_authorized()
        if not is_authorized:
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Notify others that user joined
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_join',
                'username': self.user.username,
                'user_id': self.user.id
            }
        )
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        # Notify others that user left
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_leave',
                'username': self.user.username,
                'user_id': self.user.id
            }
        )
        
        # Remove typing status
        await self.remove_typing_status()
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'chat_message':
                await self.handle_message(data)
            elif message_type == 'typing':
                await self.handle_typing(data)
            elif message_type == 'stop_typing':
                await self.handle_stop_typing(data)
            elif message_type == 'message_read':
                await self.handle_message_read(data)
        
        except json.JSONDecodeError:
            pass
    
    async def handle_message(self, data):
        """Handle a chat message"""
        message_text = data.get('message', '').strip()
        
        if not message_text:
            return
        
        # Save message to database
        message_obj = await self.save_message(message_text)
        
        if message_obj['id'] is None:
            return
        
        # Get room creator info
        room_creator_id = await self.get_room_creator_id()
        
        # Broadcast message to ALL members in the room (regardless of mentions)
        # This ensures all chat room members see all messages
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message_send',
                'message_id': message_obj['id'],
                'username': self.user.username,
                'user_id': self.user.id,
                'message': message_text,
                'timestamp': message_obj['timestamp'],
                'mentioned_users': message_obj['mentioned_users'],
                'is_broadcast': True,  # Mark as broadcast to all members
                'room_creator_id': room_creator_id
            }
        )
        
        # If message has mentions, also notify those users
        if message_obj['mentioned_users']:
            await self.notify_mentioned_users_async(message_obj)
        
        # Broadcast notification count update to all members (new message creates notifications)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'notification_count_update',
                'trigger': 'new_message'
            }
        )
        
        # Remove typing status after sending
        await self.remove_typing_status()
    
    async def handle_typing(self, data):
        """Handle user typing notification"""
        await self.update_typing_status()
        
        # Broadcast typing indicator
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_typing',
                'username': self.user.username,
                'user_id': self.user.id
            }
        )
    
    async def handle_stop_typing(self, data):
        """Handle user stop typing notification"""
        await self.remove_typing_status()
        
        # Broadcast stop typing
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_stop_typing',
                'username': self.user.username,
                'user_id': self.user.id
            }
        )
    
    async def handle_message_read(self, data):
        """Handle message read notification"""
        message_id = data.get('message_id')
        if not message_id:
            return
        
        # Mark message as read in database
        result = await self.mark_message_as_read(message_id)
        
        if result:
            # Broadcast read status to all members
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_marked_read',
                    'message_id': message_id,
                    'username': self.user.username,
                    'user_id': self.user.id,
                    'read_count': result['read_count'],
                    'total_members': result['total_members'],
                    'all_read': result['all_read']
                }
            )
            
            # Broadcast notification count update to all members
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'notification_count_update',
                    'trigger': 'message_read'
                }
            )
    
    # Message handlers for group_send
    async def chat_message_send(self, event):
        """Send a chat message to WebSocket - delivered to ALL members"""
        # Check if current user is room creator (can delete any message)
        current_user_is_room_creator = event.get('room_creator_id') == self.user.id
        # Check if message sender is room creator
        sender_is_room_creator = event.get('room_creator_id') == event['user_id']
        
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'id': event['message_id'],
            'message_id': event['message_id'],
            'username': event['username'],
            'user_id': event['user_id'],
            'message': event['message'],
            'timestamp': event['timestamp'],
            'mentioned_users': event['mentioned_users'],
            'is_broadcast': event.get('is_broadcast', True),  # All messages are broadcast to room
            'is_own_message': event['user_id'] == self.user.id,
            'current_user_is_room_creator': current_user_is_room_creator,
            'sender_is_room_creator': sender_is_room_creator
        }))
    
    async def user_join(self, event):
        """Send user join notification"""
        await self.send(text_data=json.dumps({
            'type': 'user_join',
            'username': event['username'],
            'user_id': event['user_id']
        }))
    
    async def user_leave(self, event):
        """Send user leave notification"""
        await self.send(text_data=json.dumps({
            'type': 'user_leave',
            'username': event['username'],
            'user_id': event['user_id']
        }))
    
    async def user_typing(self, event):
        """Send typing indicator"""
        await self.send(text_data=json.dumps({
            'type': 'user_typing',
            'username': event['username'],
            'user_id': event['user_id']
        }))
    
    async def user_stop_typing(self, event):
        """Send stop typing notification"""
        await self.send(text_data=json.dumps({
            'type': 'user_stop_typing',
            'username': event['username'],
            'user_id': event['user_id']
        }))
    
    async def message_marked_read(self, event):
        """Send message read status update to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'message_marked_read',
            'message_id': event['message_id'],
            'username': event['username'],
            'user_id': event['user_id'],
            'read_count': event['read_count'],
            'total_members': event['total_members'],
            'all_read': event['all_read']
        }))
    
    async def notification_count_update(self, event):
        """Send notification to update the unread message count badge"""
        await self.send(text_data=json.dumps({
            'type': 'notification_count_update',
            'trigger': event.get('trigger', 'unknown')
        }))
    
    async def file_uploaded(self, event):
        """Send file upload notification to all room members"""
        await self.send(text_data=json.dumps({
            'type': 'file_uploaded',
            'file_id': event['file_id'],
            'filename': event['filename'],
            'file_type': event['file_type'],
            'file_size': event['file_size'],
            'uploaded_by': event['uploaded_by'],
            'uploaded_at': event['uploaded_at'],
            'description': event.get('description', ''),
            'uploader_id': event['uploader_id']
        }))
    
    async def notify_mentioned_users_async(self, message_obj):
        """Send notifications to mentioned users"""
        # This is called after message is saved
        # Mentioned users will see notification but message is already in chat
        pass
    
    # Database operations
    @database_sync_to_async
    def is_user_authorized(self):
        """Check if user is authorized to access this room"""
        try:
            chat_room = ChatRoom.objects.get(id=self.room_id)
            return chat_room.members.filter(id=self.user.id).exists()
        except ChatRoom.DoesNotExist:
            return False
    
    @database_sync_to_async
    def get_room_creator_id(self):
        """Get the room creator's user ID"""
        try:
            chat_room = ChatRoom.objects.get(id=self.room_id)
            return chat_room.created_by.id
        except ChatRoom.DoesNotExist:
            return None
    
    @database_sync_to_async
    def save_message(self, message_text):
        """Save message to database and extract mentions
        
        Messages are ALWAYS delivered to all chat room members.
        Mentions (@username) are optional and only trigger notifications
        for those specific users.
        """
        import re
        
        try:
            chat_room = ChatRoom.objects.get(id=self.room_id)
            message = ChatMessage.objects.create(
                chat_room=chat_room,
                author=self.user,
                content=message_text
            )
            
            # Auto-mark sender's message as read for themselves
            message.read_by.add(self.user)
            
            # Extract and add mentioned users
            # This is OPTIONAL - messages don't need mentions to be sent
            mentions = re.findall(r'@(\w+)', message_text)
            mentioned_users = []
            
            for mention in set(mentions):
                try:
                    mentioned_user = User.objects.get(username=mention)
                    message.mentioned_users.add(mentioned_user)
                    mentioned_users.append(mention)
                    
                    # Create notification for mentioned user (if different from author)
                    if mentioned_user != self.user:
                        Notification.objects.create(
                            recipient=mentioned_user,
                            sender=self.user,
                            notification_type='MENTION',
                            chat_message=message,
                            text=f'{self.user.username} mentioned you in {chat_room.name}'
                        )
                except User.DoesNotExist:
                    # Silently skip non-existent usernames in mentions
                    pass
            
            return {
                'id': message.id,
                'timestamp': message.created_at.isoformat(),
                'mentioned_users': mentioned_users,
                'chat_room_id': chat_room.id,
                'chat_room_name': chat_room.name
            }
        except ChatRoom.DoesNotExist:
            return {'id': None, 'timestamp': None, 'mentioned_users': [], 'chat_room_id': None, 'chat_room_name': None}
    
    @database_sync_to_async
    def update_typing_status(self):
        """Update user typing status"""
        try:
            chat_room = ChatRoom.objects.get(id=self.room_id)
            typing_status, created = UserTypingStatus.objects.get_or_create(
                chat_room=chat_room,
                user=self.user
            )
            return typing_status
        except ChatRoom.DoesNotExist:
            return None
    
    @database_sync_to_async
    def remove_typing_status(self):
        """Remove user typing status"""
        try:
            UserTypingStatus.objects.filter(
                chat_room_id=self.room_id,
                user=self.user
            ).delete()
        except:
            pass
    
    @database_sync_to_async
    def mark_message_as_read(self, message_id):
        """Mark a message as read by the current user"""
        try:
            message = ChatMessage.objects.get(id=message_id)
            message.read_by.add(self.user)
            
            total_members = message.chat_room.members.count()
            read_count = message.read_by.count()
            all_read = read_count >= total_members
            
            if all_read:
                message.is_read = True
                message.read_at = datetime.now()
                message.save()
            
            return {
                'read_count': read_count,
                'total_members': total_members,
                'all_read': all_read
            }
        except ChatMessage.DoesNotExist:
            return None


class TaskCommentConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time task thread comments"""
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.task_id = self.scope['url_route']['kwargs']['task_id']
        self.room_group_name = f'task_thread_comments_{self.task_id}'
        self.user = self.scope['user']
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        is_authorized = await self.is_user_authorized()
        if not is_authorized:
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'comment':
                await self.handle_comment(data)
        except json.JSONDecodeError:
            pass
    
    async def handle_comment(self, data):
        """Handle a new comment"""
        comment_text = data.get('comment', '').strip()
        
        if not comment_text:
            return
        
        # Save comment to database
        comment_obj = await self.save_comment(comment_text)
        
        # Broadcast comment to task subscribers
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'comment_send',
                'comment_id': comment_obj['id'],
                'username': self.user.username,
                'user_id': self.user.id,
                'comment': comment_text,
                'timestamp': comment_obj['timestamp'],
                'mentioned_users': comment_obj['mentioned_users']
            }
        )
    
    async def comment_send(self, event):
        """Send a comment to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'new_comment',
            'comment_id': event['comment_id'],
            'username': event['username'],
            'user_id': event['user_id'],
            'comment': event['comment'],
            'timestamp': event['timestamp'],
            'mentioned_users': event['mentioned_users']
        }))
    
    @database_sync_to_async
    def is_user_authorized(self):
        """Check if user is authorized to access this task"""
        try:
            task = Task.objects.get(id=self.task_id)
            # Check if user is assigned, created task, or board member
            board = task.column.board
            return (
                task.assigned_to == self.user or 
                task.created_by == self.user or 
                board.members.filter(id=self.user.id).exists()
            )
        except Task.DoesNotExist:
            return False
    
    @database_sync_to_async
    def save_comment(self, comment_text):
        """Save comment to database and extract mentions"""
        import re
        
        try:
            task = Task.objects.get(id=self.task_id)
            comment = TaskThreadComment.objects.create(
                task=task,
                author=self.user,
                content=comment_text
            )
            
            # Extract and add mentioned users
            mentions = re.findall(r'@(\w+)', comment_text)
            mentioned_users = []
            
            for mention in set(mentions):
                try:
                    mentioned_user = User.objects.get(username=mention)
                    comment.mentioned_users.add(mentioned_user)
                    mentioned_users.append(mention)
                    
                    # Create notification for mentioned user
                    if mentioned_user != self.user:
                        Notification.objects.create(
                            recipient=mentioned_user,
                            sender=self.user,
                            notification_type='MENTION',
                            task_thread_comment=comment,
                            text=f'{self.user.username} mentioned you in a comment on task "{task.title}"'
                        )
                except User.DoesNotExist:
                    pass
            
            return {
                'id': comment.id,
                'timestamp': comment.created_at.isoformat(),
                'mentioned_users': mentioned_users
            }
        except Task.DoesNotExist:
            return {'id': None, 'timestamp': None, 'mentioned_users': []}
