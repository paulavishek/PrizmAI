"""
Tests for WebSocket Consumers
===============================

Tests coverage:
- Chat room consumers
- Real-time messaging
- Typing indicators
- Connection/disconnection handling
- Message broadcasting
- User presence
"""

from django.test import TestCase
from django.contrib.auth.models import User
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
import json

from accounts.models import Organization, UserProfile
from kanban.models import Board
from messaging.models import ChatRoom, ChatMessage
from messaging.consumers import ChatConsumer


class ChatConsumerTests(TestCase):
    """Test ChatConsumer WebSocket functionality"""
    
    async def asyncSetUp(self):
        """Set up test data asynchronously"""
        self.user = await database_sync_to_async(User.objects.create_user)(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.org = await database_sync_to_async(Organization.objects.create)(
            name='Test Org',
            domain='test.org',
            created_by=self.user
        )
        await database_sync_to_async(UserProfile.objects.create)(
            user=self.user,
            organization=self.org
        )
        self.board = await database_sync_to_async(Board.objects.create)(
            name='Test Board',
            organization=self.org,
            created_by=self.user
        )
        self.room = await database_sync_to_async(ChatRoom.objects.create)(
            board=self.board,
            name='General',
            created_by=self.user
        )
        await database_sync_to_async(self.room.members.add)(self.user)
    
    async def test_websocket_connection(self):
        """Test WebSocket connection to chat room"""
        await self.asyncSetUp()
        
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.room.id}/"
        )
        communicator.scope['user'] = self.user
        
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        
        await communicator.disconnect()
    
    async def test_websocket_connection_requires_auth(self):
        """Test WebSocket connection requires authentication"""
        await self.asyncSetUp()
        
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.room.id}/"
        )
        # No user in scope (unauthenticated)
        
        connected, _ = await communicator.connect()
        self.assertFalse(connected)
    
    async def test_send_message_to_chat(self):
        """Test sending message through WebSocket"""
        await self.asyncSetUp()
        
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.room.id}/"
        )
        communicator.scope['user'] = self.user
        
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        
        # Send message
        await communicator.send_json_to({
            'type': 'chat_message',
            'message': 'Hello, World!'
        })
        
        # Receive message
        response = await communicator.receive_json_from()
        
        self.assertEqual(response['type'], 'chat_message')
        self.assertEqual(response['message'], 'Hello, World!')
        self.assertEqual(response['username'], 'testuser')
        
        await communicator.disconnect()
    
    async def test_message_persisted_to_database(self):
        """Test messages are saved to database"""
        await self.asyncSetUp()
        
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.room.id}/"
        )
        communicator.scope['user'] = self.user
        
        await communicator.connect()
        
        await communicator.send_json_to({
            'type': 'chat_message',
            'message': 'Persistent message'
        })
        
        await communicator.receive_json_from()
        await communicator.disconnect()
        
        # Check database
        message_exists = await database_sync_to_async(
            ChatMessage.objects.filter(
                chat_room=self.room,
                content='Persistent message'
            ).exists
        )()
        self.assertTrue(message_exists)
    
    async def test_typing_indicator(self):
        """Test typing indicator functionality"""
        await self.asyncSetUp()
        
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.room.id}/"
        )
        communicator.scope['user'] = self.user
        
        await communicator.connect()
        
        # Send typing indicator
        await communicator.send_json_to({
            'type': 'typing',
            'is_typing': True
        })
        
        response = await communicator.receive_json_from()
        
        self.assertEqual(response['type'], 'typing')
        self.assertEqual(response['username'], 'testuser')
        self.assertTrue(response['is_typing'])
        
        await communicator.disconnect()
    
    async def test_user_join_notification(self):
        """Test user join notification"""
        await self.asyncSetUp()
        
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.room.id}/"
        )
        communicator.scope['user'] = self.user
        
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        
        # Should receive join notification
        response = await communicator.receive_json_from()
        
        self.assertEqual(response['type'], 'user_join')
        self.assertEqual(response['username'], 'testuser')
        
        await communicator.disconnect()
    
    async def test_user_leave_notification(self):
        """Test user leave notification"""
        await self.asyncSetUp()
        
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.room.id}/"
        )
        communicator.scope['user'] = self.user
        
        await communicator.connect()
        
        # Disconnect
        await communicator.disconnect()
        
        # Other users should receive leave notification
        # (Would need second communicator to test fully)
    
    async def test_message_mention_notification(self):
        """Test @mention creates notification"""
        await self.asyncSetUp()
        
        user2 = await database_sync_to_async(User.objects.create_user)(
            username='user2',
            email='user2@example.com',
            password='testpass123'
        )
        await database_sync_to_async(self.room.members.add)(user2)
        
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.room.id}/"
        )
        communicator.scope['user'] = self.user
        
        await communicator.connect()
        
        # Send message with mention
        await communicator.send_json_to({
            'type': 'chat_message',
            'message': '@user2 check this out'
        })
        
        await communicator.receive_json_from()
        await communicator.disconnect()
        
        # Notification should be created
        from messaging.models import Notification
        notif_exists = await database_sync_to_async(
            Notification.objects.filter(
                recipient=user2,
                notification_type='MENTION'
            ).exists
        )()
        self.assertTrue(notif_exists)
    
    async def test_multiple_concurrent_connections(self):
        """Test multiple users can connect simultaneously"""
        await self.asyncSetUp()
        
        user2 = await database_sync_to_async(User.objects.create_user)(
            username='user2',
            email='user2@example.com',
            password='testpass123'
        )
        await database_sync_to_async(self.room.members.add)(user2)
        
        # First user connection
        comm1 = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.room.id}/"
        )
        comm1.scope['user'] = self.user
        
        # Second user connection
        comm2 = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.room.id}/"
        )
        comm2.scope['user'] = user2
        
        connected1, _ = await comm1.connect()
        connected2, _ = await comm2.connect()
        
        self.assertTrue(connected1)
        self.assertTrue(connected2)
        
        # User1 sends message
        await comm1.send_json_to({
            'type': 'chat_message',
            'message': 'Broadcast test'
        })
        
        # Both users should receive it
        response1 = await comm1.receive_json_from()
        response2 = await comm2.receive_json_from()
        
        self.assertEqual(response1['message'], 'Broadcast test')
        self.assertEqual(response2['message'], 'Broadcast test')
        
        await comm1.disconnect()
        await comm2.disconnect()


class NotificationConsumerTests(TestCase):
    """Test notification WebSocket consumer"""
    
    async def asyncSetUp(self):
        """Set up test data"""
        self.user = await database_sync_to_async(User.objects.create_user)(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    async def test_notification_websocket_connection(self):
        """Test connecting to notification WebSocket"""
        await self.asyncSetUp()
        
        from messaging.consumers import NotificationConsumer
        
        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(),
            "/ws/notifications/"
        )
        communicator.scope['user'] = self.user
        
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        
        await communicator.disconnect()
    
    async def test_receive_real_time_notification(self):
        """Test receiving notifications in real-time"""
        await self.asyncSetUp()
        
        from messaging.consumers import NotificationConsumer
        from messaging.models import Notification
        
        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(),
            "/ws/notifications/"
        )
        communicator.scope['user'] = self.user
        
        await communicator.connect()
        
        # Create notification
        await database_sync_to_async(Notification.objects.create)(
            recipient=self.user,
            notification_type='MENTION',
            text='You were mentioned'
        )
        
        # Should receive notification through WebSocket
        response = await communicator.receive_json_from(timeout=2)
        
        self.assertEqual(response['type'], 'notification')
        self.assertIn('mentioned', response['text'].lower())
        
        await communicator.disconnect()


class PresenceTests(TestCase):
    """Test user presence tracking"""
    
    async def asyncSetUp(self):
        """Set up test data"""
        self.user = await database_sync_to_async(User.objects.create_user)(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.org = await database_sync_to_async(Organization.objects.create)(
            name='Test Org',
            domain='test.org',
            created_by=self.user
        )
        await database_sync_to_async(UserProfile.objects.create)(
            user=self.user,
            organization=self.org
        )
        self.board = await database_sync_to_async(Board.objects.create)(
            name='Test Board',
            organization=self.org,
            created_by=self.user
        )
        self.room = await database_sync_to_async(ChatRoom.objects.create)(
            board=self.board,
            name='General',
            created_by=self.user
        )
        await database_sync_to_async(self.room.members.add)(self.user)
    
    async def test_user_presence_on_connect(self):
        """Test user presence is tracked on connection"""
        await self.asyncSetUp()
        
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.room.id}/"
        )
        communicator.scope['user'] = self.user
        
        await communicator.connect()
        
        # Check presence is tracked
        # (Implementation depends on your presence tracking system)
        
        await communicator.disconnect()
    
    async def test_online_users_list(self):
        """Test getting list of online users"""
        await self.asyncSetUp()
        
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.room.id}/"
        )
        communicator.scope['user'] = self.user
        
        await communicator.connect()
        
        # Request online users
        await communicator.send_json_to({
            'type': 'get_online_users'
        })
        
        response = await communicator.receive_json_from()
        
        self.assertEqual(response['type'], 'online_users')
        self.assertIn(self.user.username, response['users'])
        
        await communicator.disconnect()
