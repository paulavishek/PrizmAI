from django.urls import path
from messaging import consumers
from kanban.consumers import AITaskConsumer, SandboxProvisionConsumer

websocket_urlpatterns = [
    path('ws/chat-room/<int:room_id>/', consumers.ChatRoomConsumer.as_asgi()),
    path('ws/task-comments/<int:task_id>/', consumers.TaskCommentConsumer.as_asgi()),
    path('ws/ai-task/<str:task_id>/', AITaskConsumer.as_asgi()),
    path('ws/sandbox-provision/', SandboxProvisionConsumer.as_asgi()),
]
