"""
WebSocket consumer for AI task progress streaming.

Provides real-time status updates and result delivery for long-running
AI tasks offloaded to Celery (Pre-Mortem, Board Analytics, Deadline
Prediction, Workflow Optimization, AI Chat).

Protocol:
  Client connects to ws://.../ws/ai-task/<task_id>/
  Server sends: {type: "ai_status_update", message: "...", progress: 0-100}
  Server sends: {type: "ai_result", data: {...}}
  Server sends: {type: "ai_error", message: "..."}
"""
import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class AITaskConsumer(AsyncWebsocketConsumer):
    """Stream AI task progress and results to the client via WebSocket."""

    async def connect(self):
        self.task_id = self.scope['url_route']['kwargs']['task_id']
        self.group_name = f'ai_task_{self.task_id}'

        # Require authenticated user
        user = self.scope.get('user')
        if not user or user.is_anonymous:
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # ------------------------------------------------------------------
    # Handlers for messages sent via channel_layer.group_send()
    # ------------------------------------------------------------------

    async def ai_status_update(self, event):
        """Forward a progress update to the client."""
        await self.send(text_data=json.dumps({
            'type': 'ai_status_update',
            'message': event.get('message', ''),
            'progress': event.get('progress', 0),
        }))

    async def ai_result(self, event):
        """Forward the final AI result and close the connection."""
        await self.send(text_data=json.dumps({
            'type': 'ai_result',
            'data': event.get('data', {}),
        }))

    async def ai_error(self, event):
        """Forward an error and close the connection."""
        await self.send(text_data=json.dumps({
            'type': 'ai_error',
            'message': event.get('message', 'An unexpected error occurred.'),
        }))


class SandboxProvisionConsumer(AsyncWebsocketConsumer):
    """Stream sandbox provisioning progress to the client via WebSocket."""

    async def connect(self):
        user = self.scope.get('user')
        if not user or user.is_anonymous:
            await self.close()
            return

        self.group_name = f'sandbox_provision_{user.id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def provision_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'provision_status',
            'message': event.get('message', ''),
            'progress': event.get('progress', 0),
        }))

    async def provision_result(self, event):
        await self.send(text_data=json.dumps({
            'type': 'provision_result',
            'data': event.get('data', {}),
        }))

    async def provision_error(self, event):
        await self.send(text_data=json.dumps({
            'type': 'provision_error',
            'message': event.get('message', 'Provisioning failed.'),
        }))
