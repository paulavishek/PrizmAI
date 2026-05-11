from django.contrib import admin
from .models import TaskThreadComment, ChatRoom, ChatMessage, Notification, UserTypingStatus, ChatRoomInvitation


@admin.register(ChatRoomInvitation)
class ChatRoomInvitationAdmin(admin.ModelAdmin):
    list_display = ['id', 'invited_user', 'chat_room', 'invited_by', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['invited_user__username', 'chat_room__name']
    readonly_fields = ['created_at', 'responded_at']


@admin.register(TaskThreadComment)
class TaskThreadCommentAdmin(admin.ModelAdmin):
    list_display = ['id', 'author', 'task', 'created_at']
    list_filter = ['created_at', 'author']
    search_fields = ['content', 'author__username', 'task__title']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['mentioned_users']


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'board', 'created_by', 'created_at']
    list_filter = ['board', 'created_at']
    search_fields = ['name', 'description']
    filter_horizontal = ['members']


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'author', 'chat_room', 'created_at']
    list_filter = ['chat_room', 'created_at', 'author']
    search_fields = ['content', 'author__username']
    readonly_fields = ['created_at']
    filter_horizontal = ['mentioned_users']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'recipient', 'sender', 'notification_type', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['recipient__username', 'sender__username', 'text']
    readonly_fields = ['created_at']


@admin.register(UserTypingStatus)
class UserTypingStatusAdmin(admin.ModelAdmin):
    list_display = ['user', 'chat_room', 'last_update']
    list_filter = ['chat_room', 'last_update']
    search_fields = ['user__username']

