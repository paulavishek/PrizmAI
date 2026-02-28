from django.urls import path
from . import views
from . import ai_views

app_name = 'messaging'

urlpatterns = [
    # Messaging Hub
    path('', views.messaging_hub, name='hub'),
    
    # Chat Rooms
    path('board/<int:board_id>/rooms/', views.chat_room_list, name='chat_room_list'),
    path('board/<int:board_id>/rooms/create/', views.create_chat_room, name='create_chat_room'),
    path('room/<int:room_id>/', views.chat_room_detail, name='chat_room_detail'),
    
    # Messages
    path('room/<int:room_id>/send/', views.send_chat_message, name='send_chat_message'),
    path('room/<int:room_id>/history/', views.message_history, name='message_history'),
    
    # Task Thread Comments
    path('task/<int:task_id>/comments/', views.task_thread_comments, name='task_thread_comments'),
    path('task/<int:task_id>/comments/history/', views.task_comment_history, name='task_comment_history'),
    
    # Mentions
    path('mentions/', views.get_mentions, name='get_mentions'),
    
    # Notifications
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/count/', views.get_unread_notification_count, name='get_unread_notification_count'),
    
    # Unread Messages
    path('messages/unread-count/', views.get_unread_message_count, name='get_unread_message_count'),
    path('messages/go-to-unread/', views.go_to_first_unread_room, name='go_to_first_unread_room'),
    
    # Mark Messages as Read
    path('message/<int:message_id>/read/', views.mark_chat_message_read, name='mark_chat_message_read'),
    path('room/<int:room_id>/mark-read/', views.mark_room_messages_read, name='mark_room_messages_read'),
    
    # Delete Messages
    path('message/<int:message_id>/delete/', views.delete_chat_message, name='delete_chat_message'),
    path('room/<int:room_id>/clear/', views.clear_chat_room_messages, name='clear_chat_room_messages'),
    
    # File Management for Chat Rooms
    path('room/<int:room_id>/files/upload/', views.upload_chat_room_file, name='upload_chat_room_file'),
    path('room/<int:room_id>/files/list/', views.list_chat_room_files, name='list_chat_room_files'),
    path('file/<int:file_id>/download/', views.download_chat_room_file, name='download_chat_room_file'),
    path('file/<int:file_id>/delete/', views.delete_chat_room_file, name='delete_chat_room_file'),
    path('file/<int:file_id>/ai-analyze/', ai_views.analyze_chat_attachment, name='ai_analyze_chat_file'),
    path('file/<int:file_id>/ai-create-tasks/', ai_views.create_tasks_from_chat_attachment, name='ai_create_tasks_chat_file'),

    # AI Features (Thread Summary & Task Extraction)
    path('room/<int:room_id>/ai/summarize/', ai_views.summarize_thread, name='ai_summarize_thread'),
    path('room/<int:room_id>/ai/extract-tasks/', ai_views.extract_tasks_from_thread, name='ai_extract_tasks_thread'),
    path('message/<int:message_id>/ai/extract-tasks/', ai_views.extract_tasks_from_message, name='ai_extract_tasks_message'),
    path('room/<int:room_id>/ai/confirm-tasks/', ai_views.confirm_create_tasks, name='ai_confirm_tasks'),
]
