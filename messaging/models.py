from django.db import models
from django.contrib.auth.models import User
from kanban.models import Task, Board
from django.db.models import Q
from django.utils import timezone


class TaskThreadComment(models.Model):
    """Real-time comments on individual tasks with @mention support"""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='thread_comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='task_thread_comments')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # @mention support
    mentioned_users = models.ManyToManyField(User, related_name='mentioned_in_task_threads', blank=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['task', 'created_at']),
        ]
    
    def __str__(self):
        return f"Comment by {self.author.username} on Task {self.task.id}"
    
    def get_mentioned_usernames(self):
        """Extract @mentions from content (format: @username)"""
        import re
        mentions = re.findall(r'@(\w+)', self.content)
        return list(set(mentions))  # Remove duplicates
    
    def notify_mentioned_users(self):
        """Create notifications for mentioned users"""
        for mention in self.get_mentioned_usernames():
            try:
                user = User.objects.get(username=mention)
                if user != self.author:
                    Notification.objects.create(
                        recipient=user,
                        sender=self.author,
                        notification_type='MENTION',
                        task_comment=self,
                        text=f'{self.author.username} mentioned you in a comment on task "{self.task.title}"'
                    )
            except User.DoesNotExist:
                pass


class ChatRoom(models.Model):
    """Board-level chat rooms for team synchronization"""
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='chat_rooms')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_chat_rooms')
    created_at = models.DateTimeField(auto_now_add=True)
    members = models.ManyToManyField(User, related_name='chat_rooms', blank=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['board', 'name']
        indexes = [
            models.Index(fields=['board', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.board.name})"
    
    def get_room_group_name(self):
        """Get the channel group name for WebSocket"""
        return f'chat_room_{self.id}'


class ChatMessage(models.Model):
    """Messages in a chat room"""
    chat_room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_messages')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Message read status tracking
    is_read = models.BooleanField(default=False)
    read_by = models.ManyToManyField(User, related_name='read_messages', blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # @mention support
    mentioned_users = models.ManyToManyField(User, related_name='mentioned_in_chat', blank=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['chat_room', 'created_at']),
        ]
    
    def __str__(self):
        return f"Message by {self.author.username} in {self.chat_room.name}"
    
    def get_mentioned_usernames(self):
        """Extract @mentions from content (format: @username)"""
        import re
        mentions = re.findall(r'@(\w+)', self.content)
        return list(set(mentions))  # Remove duplicates
    
    def mark_as_read(self, user):
        """Mark message as read by a specific user"""
        self.read_by.add(user)
        if self.read_by.count() == self.chat_room.members.count():
            self.is_read = True
            self.read_at = timezone.now()
            self.save()
    
    def get_unread_count(self):
        """Get number of users who haven't read this message"""
        return self.chat_room.members.count() - self.read_by.count()
    
    def notify_mentioned_users(self):
        """Create notifications for mentioned users"""
        for mention in self.get_mentioned_usernames():
            try:
                user = User.objects.get(username=mention)
                if user != self.author:
                    Notification.objects.create(
                        recipient=user,
                        sender=self.author,
                        notification_type='MENTION',
                        chat_message=self,
                        text=f'{self.author.username} mentioned you in {self.chat_room.name}: "{self.content[:50]}"'
                    )
            except User.DoesNotExist:
                pass


class Notification(models.Model):
    """Notifications for mentions and activity"""
    NOTIFICATION_TYPES = [
        ('MENTION', 'Mention'),
        ('COMMENT', 'Comment Reply'),
        ('CHAT_MESSAGE', 'Chat Message'),
        ('ACTIVITY', 'Activity Update'),
    ]
    
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    text = models.TextField()
    
    # AI-generated summary for concise notification display
    ai_summary = models.CharField(max_length=200, blank=True, null=True, 
                                   help_text="AI-generated concise summary of the notification")
    
    # Links to related objects
    task_thread_comment = models.ForeignKey(TaskThreadComment, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    chat_message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.notification_type} notification for {self.recipient.username}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.save()
    
    def generate_ai_summary(self):
        """Generate AI summary for the notification using Gemini"""
        try:
            from kanban.utils.ai_utils import generate_ai_content
            
            prompt = f"""Summarize this notification for a busy project manager in ONE short sentence (max 100 chars):

Notification type: {self.get_notification_type_display()}
From: {self.sender.get_full_name() or self.sender.username}
Message: {self.text}

Requirements:
- Be actionable and direct
- Keep it under 100 characters
- Focus on what the PM needs to know/do
- Don't include quotes or special formatting

Example outputs:
- "Sarah mentioned you on API redesign task"
- "New comment on Sprint Planning - review needed"
- "John replied to your design feedback"
"""
            summary = generate_ai_content(prompt, task_type='simple')
            if summary:
                # Clean up and truncate if needed
                summary = summary.strip().strip('"').strip("'")
                if len(summary) > 200:
                    summary = summary[:197] + '...'
                self.ai_summary = summary
                self.save(update_fields=['ai_summary'])
                return summary
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to generate AI summary for notification {self.id}: {e}")
        return None
    
    def get_display_text(self):
        """Return AI summary if available, otherwise return the full text"""
        return self.ai_summary if self.ai_summary else self.text
    
    def save(self, *args, **kwargs):
        """Override save to generate AI summary for new notifications"""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Generate AI summary asynchronously for new notifications
        # Only if not already being saved with ai_summary
        if is_new and not self.ai_summary and 'update_fields' not in kwargs:
            # Use a simple async approach - generate summary in background
            try:
                from threading import Thread
                thread = Thread(target=self._generate_summary_background)
                thread.daemon = True
                thread.start()
            except Exception:
                pass  # Fail silently - AI summary is optional
    
    def _generate_summary_background(self):
        """Background task to generate AI summary"""
        import django
        django.db.connections.close_all()
        self.generate_ai_summary()


class UserTypingStatus(models.Model):
    """Track user typing status in chat rooms"""
    chat_room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='typing_users')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    last_update = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['chat_room', 'user']
    
    def is_typing(self, timeout_seconds=10):
        """Check if user is still typing (not older than timeout)"""
        elapsed = (timezone.now() - self.last_update).total_seconds()
        return elapsed < timeout_seconds
    
    def __str__(self):
        return f"{self.user.username} typing in {self.chat_room.name}"


class FileAttachment(models.Model):
    """File attachments for chat rooms"""
    ALLOWED_FILE_TYPES = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'jpg', 'jpeg', 'png']
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    chat_room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='file_attachments')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_file_uploads')
    file = models.FileField(upload_to='chat_rooms/%Y/%m/%d/')
    filename = models.CharField(max_length=255)
    file_size = models.BigIntegerField(help_text="File size in bytes")
    file_type = models.CharField(max_length=10, help_text="File extension")
    description = models.TextField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(blank=True, null=True)  # Soft delete
    
    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['chat_room', 'uploaded_at']),
            models.Index(fields=['uploaded_by', 'uploaded_at']),
        ]
    
    def __str__(self):
        return f"{self.filename} in {self.chat_room.name}"
    
    def is_deleted(self):
        """Check if file is soft-deleted"""
        return self.deleted_at is not None
    
    def get_file_icon(self):
        """Get Bootstrap icon class based on file type"""
        icon_map = {
            'pdf': 'fa-file-pdf',
            'doc': 'fa-file-word',
            'docx': 'fa-file-word',
            'xls': 'fa-file-excel',
            'xlsx': 'fa-file-excel',
            'ppt': 'fa-file-powerpoint',
            'pptx': 'fa-file-powerpoint',
            'jpg': 'fa-file-image',
            'jpeg': 'fa-file-image',
            'png': 'fa-file-image',
        }
        return icon_map.get(self.file_type.lower(), 'fa-file')
    
    @staticmethod
    def is_valid_file_type(filename):
        """Validate file type"""
        ext = filename.split('.')[-1].lower()
        return ext in FileAttachment.ALLOWED_FILE_TYPES
