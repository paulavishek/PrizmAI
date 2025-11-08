# REST API & Integration Framework - Implementation Starter Guide

**Quick Start**: Build your first API endpoint and Slack connector in 2 hours.

---

## Part 1: Core API Authentication (30 minutes)

### Step 1: Create API Token Model

**File**: `accounts/models.py` (add to existing file)

```python
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import secrets

class APIToken(models.Model):
    """API token for external applications"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='api_token')
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    scopes = models.JSONField(default=list)  # ['tasks.read', 'tasks.write', 'boards.read']
    
    def save(self, *args, **kwargs):
        if not self.token:
            self.token = self._generate_token()
        super().save(*args, **kwargs)
    
    @staticmethod
    def _generate_token():
        """Generate secure random token"""
        return 'prizmaiapi_' + secrets.token_urlsafe(32)
    
    def use(self):
        """Record token usage"""
        self.last_used = timezone.now()
        self.save(update_fields=['last_used'])
    
    class Meta:
        verbose_name = "API Token"
        verbose_name_plural = "API Tokens"
    
    def __str__(self):
        return f"{self.user.username}'s API Token"
```

### Step 2: Create Custom Authentication Backend

**File**: `api/authentication.py` (NEW FILE)

```python
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed
from accounts.models import APIToken

class APITokenAuthentication(TokenAuthentication):
    """Custom token authentication for API"""
    keyword = 'Bearer'
    
    def get_model(self):
        return APIToken
    
    def authenticate_credentials(self, key):
        """Authenticate token and record usage"""
        try:
            token = APIToken.objects.get(token=key, is_active=True)
        except APIToken.DoesNotExist:
            raise AuthenticationFailed('Invalid or inactive API token.')
        
        if not token.user.is_active:
            raise AuthenticationFailed('User inactive or deleted.')
        
        # Record token usage
        token.use()
        
        return (token.user, token)
```

### Step 3: Run Migration

```bash
python manage.py makemigrations accounts
python manage.py migrate
```

---

## Part 2: Basic RESTful Endpoints (45 minutes)

### Step 1: Create Serializers

**File**: `api/serializers.py` (NEW FILE)

```python
from rest_framework import serializers
from kanban.models import Task, Board, Column
from django.contrib.auth.models import User

class BoardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Board
        fields = ['id', 'name', 'description', 'created_at', 'created_by']
        read_only_fields = ['id', 'created_at', 'created_by']

class TaskSerializer(serializers.ModelSerializer):
    board_id = serializers.SerializerMethodField()
    assigned_to_username = serializers.CharField(source='assigned_to.username', read_only=True)
    
    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'priority', 'progress',
            'due_date', 'board_id', 'assigned_to', 'assigned_to_username',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_board_id(self, obj):
        return obj.column.board.id if obj.column else None

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
```

### Step 2: Create API Views

**File**: `api/views.py` (NEW FILE)

```python
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from kanban.models import Task, Board
from .authentication import APITokenAuthentication
from .serializers import TaskSerializer, BoardSerializer

class TaskViewSet(viewsets.ModelViewSet):
    """API endpoint for tasks"""
    serializer_class = TaskSerializer
    authentication_classes = [APITokenAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return tasks from user's boards"""
        user = self.request.user
        return Task.objects.filter(
            column__board__members=user
        ) | Task.objects.filter(
            column__board__created_by=user
        )
    
    def perform_create(self, serializer):
        """Auto-assign creator"""
        serializer.save(created_by=self.request.user)

class BoardViewSet(viewsets.ModelViewSet):
    """API endpoint for boards"""
    serializer_class = BoardSerializer
    authentication_classes = [APITokenAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return user's boards only"""
        user = self.request.user
        return Board.objects.filter(
            members=user
        ) | Board.objects.filter(
            created_by=user
        )

@api_view(['GET'])
@authentication_classes([APITokenAuthentication])
@permission_classes([IsAuthenticated])
def api_status(request):
    """Check API status"""
    return Response({
        'status': 'ok',
        'user': request.user.username,
        'message': 'API is running'
    })
```

### Step 3: Create URL Routes

**File**: `api/urls.py` (NEW FILE)

```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'tasks', views.TaskViewSet, basename='task')
router.register(r'boards', views.BoardViewSet, basename='board')

urlpatterns = [
    path('', include(router.urls)),
    path('status/', views.api_status, name='api_status'),
]
```

### Step 4: Register in Main URLs

**File**: `kanban_board/urls.py` (modify existing)

```python
# Add this import
from django.urls import path, include

# Add this line to urlpatterns
path('api/v1/', include('api.urls')),
```

### Test Your API

```bash
# 1. Generate API token in Django shell
python manage.py shell
>>> from accounts.models import APIToken
>>> from django.contrib.auth.models import User
>>> user = User.objects.first()
>>> token, created = APIToken.objects.get_or_create(user=user)
>>> print(token.token)

# 2. Test endpoint
curl -H "Authorization: Bearer prizmaiapi_XXXXX" http://localhost:8000/api/v1/status/
```

---

## Part 3: Webhook System (45 minutes)

### Step 1: Create Webhook Models

**File**: `kanban/models.py` (add to existing models)

```python
from django.db import models
from django.contrib.auth.models import User

class Webhook(models.Model):
    """Store webhook subscriptions"""
    EVENTS = [
        ('task.created', 'Task Created'),
        ('task.updated', 'Task Updated'),
        ('task.completed', 'Task Completed'),
        ('task.deleted', 'Task Deleted'),
        ('board.created', 'Board Created'),
        ('comment.added', 'Comment Added'),
    ]
    
    board = models.ForeignKey('Board', on_delete=models.CASCADE, related_name='webhooks')
    url = models.URLField()
    events = models.JSONField(default=list)  # ['task.created', 'task.updated']
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    class Meta:
        verbose_name = "Webhook"
        verbose_name_plural = "Webhooks"
    
    def __str__(self):
        return f"{self.url} for {self.board.name}"

class WebhookDelivery(models.Model):
    """Track webhook deliveries"""
    webhook = models.ForeignKey(Webhook, on_delete=models.CASCADE, related_name='deliveries')
    event = models.CharField(max_length=50)
    payload = models.JSONField()
    response_status = models.IntegerField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Webhook Delivery"
        verbose_name_plural = "Webhook Deliveries"
    
    def __str__(self):
        return f"{self.event} to {self.webhook.url}"
```

### Step 2: Create Webhook Trigger System

**File**: `kanban/webhook_handlers.py` (NEW FILE)

```python
import json
import requests
from django.utils import timezone
from .models import Webhook, WebhookDelivery
import logging

logger = logging.getLogger(__name__)

def trigger_webhook(event_type, task, board=None):
    """Trigger webhooks for an event"""
    if not board and task.column:
        board = task.column.board
    
    if not board:
        return
    
    # Find matching webhooks
    webhooks = Webhook.objects.filter(
        board=board,
        is_active=True,
        events__contains=event_type
    )
    
    for webhook in webhooks:
        payload = {
            'event': event_type,
            'timestamp': timezone.now().isoformat(),
            'data': {
                'task_id': task.id,
                'task_title': task.title,
                'task_priority': task.priority,
                'task_status': task.column.name if task.column else 'Unknown',
                'assigned_to': task.assigned_to.username if task.assigned_to else None,
            }
        }
        
        # Send webhook asynchronously
        send_webhook_async.delay(webhook.id, event_type, payload)

def send_webhook_sync(webhook_id, event_type, payload):
    """Send webhook synchronously"""
    try:
        webhook = Webhook.objects.get(id=webhook_id)
        
        response = requests.post(
            webhook.url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=5
        )
        
        # Record delivery
        WebhookDelivery.objects.create(
            webhook=webhook,
            event=event_type,
            payload=payload,
            response_status=response.status_code,
            delivered_at=timezone.now()
        )
        
        return response.status_code == 200
        
    except Exception as e:
        logger.error(f"Webhook delivery failed: {str(e)}")
        WebhookDelivery.objects.create(
            webhook=webhook,
            event=event_type,
            payload=payload,
            error=str(e)
        )
        return False

# For async delivery with Celery (optional)
try:
    from celery import shared_task
    
    @shared_task
    def send_webhook_async(webhook_id, event_type, payload):
        """Send webhook asynchronously"""
        return send_webhook_sync(webhook_id, event_type, payload)
        
except ImportError:
    # Celery not available, use sync version
    send_webhook_async = type('obj', (object,), {'delay': send_webhook_sync})()
```

### Step 3: Update Task Model to Trigger Webhooks

**File**: `kanban/models.py` (modify Task model save method)

```python
def save(self, *args, **kwargs):
    # Your existing save logic...
    is_new = not self.pk
    super().save(*args, **kwargs)
    
    # Trigger webhooks
    from .webhook_handlers import trigger_webhook
    if is_new:
        trigger_webhook('task.created', self)
    else:
        trigger_webhook('task.updated', self)
```

### Step 4: Create Webhook Management API

**File**: `api/views.py` (add these endpoints)

```python
from .models import Webhook, WebhookDelivery
from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(['POST'])
@authentication_classes([APITokenAuthentication])
@permission_classes([IsAuthenticated])
def register_webhook(request):
    """Register a new webhook"""
    url = request.data.get('url')
    board_id = request.data.get('board_id')
    events = request.data.get('events', [])
    
    board = Board.objects.get(id=board_id)
    
    # Verify user has permission to this board
    if not (request.user == board.created_by or request.user in board.members.all()):
        return Response({'error': 'Permission denied'}, status=403)
    
    webhook = Webhook.objects.create(
        board=board,
        url=url,
        events=events,
        created_by=request.user
    )
    
    return Response({
        'id': webhook.id,
        'url': webhook.url,
        'events': webhook.events,
        'created_at': webhook.created_at
    })

@api_view(['GET'])
@authentication_classes([APITokenAuthentication])
@permission_classes([IsAuthenticated])
def list_webhooks(request, board_id):
    """List webhooks for a board"""
    board = Board.objects.get(id=board_id)
    
    webhooks = board.webhooks.all().values('id', 'url', 'events', 'is_active', 'created_at')
    return Response(list(webhooks))
```

---

## Part 4: Slack Connector (30 minutes)

### Step 1: Create Base Connector Class

**File**: `integrations/base.py` (NEW FILE)

```python
from abc import ABC, abstractmethod

class BaseIntegrationConnector(ABC):
    """Base class for all integration connectors"""
    
    def __init__(self, connection):
        self.connection = connection
        self.service = connection.service
    
    @abstractmethod
    def handle_task_created(self, task):
        """Handle task creation"""
        pass
    
    @abstractmethod
    def handle_task_updated(self, task):
        """Handle task update"""
        pass
    
    @abstractmethod
    def handle_task_completed(self, task):
        """Handle task completion"""
        pass
    
    def format_task_message(self, task):
        """Format task data for display"""
        return {
            'id': task.id,
            'title': task.title,
            'priority': task.priority,
            'status': task.column.name if task.column else 'Unknown',
            'assigned_to': task.assigned_to.username if task.assigned_to else 'Unassigned',
            'due_date': task.due_date.strftime('%Y-%m-%d') if task.due_date else None,
        }
```

### Step 2: Create Slack Connector

**File**: `integrations/slack.py` (NEW FILE)

```python
import requests
import json
from .base import BaseIntegrationConnector

class SlackConnector(BaseIntegrationConnector):
    """Slack integration connector"""
    
    def handle_task_created(self, task):
        """Post new task to Slack"""
        webhook_url = self.connection.metadata.get('webhook_url')
        if not webhook_url:
            return
        
        message = {
            "text": f"New task created",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"📋 New Task"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Title:*\n{task.title}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Priority:*\n{task.priority}"
                        }
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Assigned to:*\n{task.assigned_to.username if task.assigned_to else 'Unassigned'}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Due:*\n{task.due_date.strftime('%Y-%m-%d') if task.due_date else 'N/A'}"
                        }
                    ]
                }
            ]
        }
        
        try:
            requests.post(webhook_url, json=message)
        except Exception as e:
            print(f"Failed to post to Slack: {str(e)}")
    
    def handle_task_updated(self, task):
        """Post updated task to Slack"""
        # Similar to handle_task_created but with "Updated" header
        pass
    
    def handle_task_completed(self, task):
        """Post completed task to Slack"""
        webhook_url = self.connection.metadata.get('webhook_url')
        if not webhook_url:
            return
        
        message = {
            "text": f"✅ Task completed: {task.title}",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"✅ *Task Completed*\n{task.title}"
                    }
                }
            ]
        }
        
        try:
            requests.post(webhook_url, json=message)
        except Exception as e:
            print(f"Failed to post to Slack: {str(e)}")
```

### Step 3: Integration Model

**File**: `accounts/models.py` (add)

```python
class IntegrationConnection(models.Model):
    """Store third-party integration connections"""
    SERVICE_CHOICES = [
        ('slack', 'Slack'),
        ('teams', 'MS Teams'),
        ('jira', 'Jira'),
        ('github', 'GitHub'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='integrations')
    service = models.CharField(max_length=20, choices=SERVICE_CHOICES)
    oauth_token = models.CharField(max_length=500, null=True, blank=True)
    webhook_url = models.URLField(null=True, blank=True)
    connected_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict)
    
    class Meta:
        unique_together = ['user', 'service']
    
    def __str__(self):
        return f"{self.user.username} - {self.service}"
```

### Step 4: Test Slack Webhook

```python
# In Django shell
from integrations.slack import SlackConnector
from accounts.models import IntegrationConnection

# Get or create connection with webhook URL
connection, _ = IntegrationConnection.objects.get_or_create(
    user=User.objects.first(),
    service='slack',
    defaults={
        'webhook_url': 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL',
        'metadata': {'webhook_url': 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'}
    }
)

# Create connector and test
connector = SlackConnector(connection)
task = Task.objects.first()
connector.handle_task_created(task)
```

---

## Part 5: Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py runserver
```

---

## Testing Everything

### 1. Test API Token

```bash
# Generate token
python manage.py shell
>>> from accounts.models import APIToken
>>> from django.contrib.auth.models import User
>>> user = User.objects.first()
>>> token = APIToken.objects.create(user=user)
>>> print(f"Token: {token.token}")

# Test API
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/status/
```

### 2. Test Webhooks

```bash
# Register webhook
curl -X POST http://localhost:8000/api/v1/webhooks/register/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://webhook.site/YOUR_URL",
    "board_id": 1,
    "events": ["task.created", "task.updated"]
  }'

# Create a task and check webhook.site
```

### 3. Test Slack Connector

```bash
# Get your Slack webhook URL and test
python manage.py shell
>>> from integrations.slack import SlackConnector
>>> from accounts.models import IntegrationConnection
>>> from kanban.models import Task

>>> connection = IntegrationConnection.objects.first()
>>> connector = SlackConnector(connection)
>>> task = Task.objects.first()
>>> connector.handle_task_created(task)
```

---

## What's Next

1. ✅ Complete Part 1-5 above
2. Add MS Teams connector (similar to Slack)
3. Add Jira bidirectional sync
4. Add GitHub issues sync
5. Create integration marketplace UI
6. Add rate limiting and monitoring

---

## API Documentation Example

Now you can document your API:

```markdown
# PrizmAI API v1

## Authentication
Use Bearer token in Authorization header:
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" https://api.prizmai.com/v1/tasks/
```

## Endpoints

### GET /api/v1/tasks/
List all tasks

**Parameters:**
- board_id (optional): Filter by board

**Response:**
```json
[
  {
    "id": 1,
    "title": "Build login screen",
    "priority": "high",
    "status": "In Progress",
    "assigned_to": "john",
    "due_date": "2025-11-15"
  }
]
```

### POST /api/v1/webhooks/register/
Register a webhook

**Body:**
```json
{
  "url": "https://your-server.com/webhook",
  "board_id": 1,
  "events": ["task.created", "task.updated"]
}
```

---

This starter guide gets you running in ~2 hours. Start here!
