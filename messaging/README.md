# Messaging Module - Real-Time Communication for PrizmAI

## Overview

The `messaging` Django app provides real-time communication capabilities for PrizmAI, enabling teams to collaborate efficiently through task-level comments and board-level chat rooms.

## Features

### 1. Task Thread Comments
- Add real-time comments directly on tasks
- @mention specific team members
- Automatic notifications for mentioned users
- Full conversation history with timestamps
- WebSocket support for instant updates

### 2. Board Chat Rooms
- Create discussion channels for quick team sync
- Lightweight, Slack-like interface
- Member management per room
- Real-time message broadcasting
- Typing indicators for awareness

### 3. @Mention System
- Type `@username` to mention team members
- Autocomplete suggestions as you type
- Invalid mentions silently ignored
- Mentioned users get instant notifications
- Works in both comments and messages

### 4. Notification System
- Track mentions across tasks and chats
- Click-to-view notifications
- Mark as read functionality
- Unread notification counter
- Integration with WebSocket for real-time alerts

## Models

### TaskThreadComment
Real-time comments on individual tasks with mention tracking.

```python
class TaskThreadComment(models.Model):
    task = ForeignKey(Task)          # The task being commented on
    author = ForeignKey(User)        # Who wrote the comment
    content = TextField()            # Comment text
    created_at = DateTimeField()     # Creation timestamp
    updated_at = DateTimeField()     # Last edit timestamp
    mentioned_users = M2MField()     # Tagged users
```

### ChatRoom
Board-level discussion channels for team communication.

```python
class ChatRoom(models.Model):
    board = ForeignKey(Board)        # Associated board
    name = CharField()               # Unique room name
    description = TextField()        # Room purpose
    created_by = ForeignKey(User)   # Creator
    created_at = DateTimeField()     # When created
    members = M2MField()             # Room members
```

### ChatMessage
Individual messages within a chat room.

```python
class ChatMessage(models.Model):
    chat_room = ForeignKey(ChatRoom)  # Room it belongs to
    author = ForeignKey(User)         # Who sent it
    content = TextField()             # Message text
    created_at = DateTimeField()      # When sent
    mentioned_users = M2MField()      # Tagged users
```

### Notification
User notifications for mentions and activities.

```python
class Notification(models.Model):
    recipient = ForeignKey(User)     # Who gets notified
    sender = ForeignKey(User)        # Who caused it
    notification_type = CharField()  # Type of notification
    text = TextField()               # Notification message
    task_thread_comment = ForeignKey() # Optional: related comment
    chat_message = ForeignKey()      # Optional: related message
    created_at = DateTimeField()     # When created
    is_read = BooleanField()         # Read status
```

### UserTypingStatus
Real-time tracking of who's typing in a room.

```python
class UserTypingStatus(models.Model):
    chat_room = ForeignKey(ChatRoom)
    user = ForeignKey(User)
    last_update = DateTimeField()    # When they last typed
```

## Views

### HTTP Views

#### Chat Rooms
- `chat_room_list(request, board_id)` - List all rooms for a board
- `chat_room_detail(request, room_id)` - View a specific room
- `create_chat_room(request, board_id)` - Create a new room
- `send_chat_message(request, room_id)` - Send a message (HTTP fallback)

#### Task Comments
- `task_thread_comments(request, task_id)` - View/add comments on a task
- `task_comment_history(request, task_id)` - Get paginated comment history

#### Notifications
- `notifications(request)` - View all notifications
- `mark_notification_read(request, notification_id)` - Mark as read

#### API Endpoints
- `get_mentions(request)` - Autocomplete for @mentions
- `message_history(request, room_id)` - Paginated message history
- `get_unread_notification_count(request)` - Get unread count

### WebSocket Consumers

#### ChatRoomConsumer
Handles real-time messaging in chat rooms.

```python
class ChatRoomConsumer(AsyncWebsocketConsumer):
    # Handles: chat_message, typing, stop_typing events
    # Broadcasts: user_join, user_leave, chat_message_send
```

#### TaskCommentConsumer
Handles real-time comments on tasks.

```python
class TaskCommentConsumer(AsyncWebsocketConsumer):
    # Handles: comment events
    # Broadcasts: comment_send events
```

## URL Patterns

### Chat Rooms
```
GET/POST  /messaging/board/<board_id>/rooms/              List/filter
POST      /messaging/board/<board_id>/rooms/create/       Create room
GET       /messaging/room/<room_id>/                       View room
POST      /messaging/room/<room_id>/send/                  Send message
GET       /messaging/room/<room_id>/history/              Message history
```

### Task Comments
```
GET/POST  /messaging/task/<task_id>/comments/             View/add comments
GET       /messaging/task/<task_id>/comments/history/     Comment history
```

### Notifications
```
GET       /messaging/notifications/                       View all
POST      /messaging/notifications/<id>/read/             Mark read
GET       /messaging/notifications/count/                 Get count
```

### API
```
GET       /messaging/mentions/?q=<query>                  Autocomplete
```

## WebSocket Protocols

### Chat Room WebSocket
```
Endpoint: ws://host/ws/chat-room/<room_id>/

Client → Server:
{
  "type": "chat_message",
  "message": "Hello team!"
}

Server → Client:
{
  "type": "chat_message",
  "message_id": 123,
  "username": "john_doe",
  "message": "Hello team!",
  "timestamp": "2025-10-30T14:30:00Z",
  "mentioned_users": ["jane_smith"]
}
```

### Task Comments WebSocket
```
Endpoint: ws://host/ws/task-comments/<task_id>/

Client → Server:
{
  "type": "comment",
  "comment": "Great work @jane_smith!"
}

Server → Client:
{
  "type": "new_comment",
  "comment_id": 45,
  "username": "john_doe",
  "comment": "Great work @jane_smith!",
  "timestamp": "2025-10-30T14:31:00Z",
  "mentioned_users": ["jane_smith"]
}
```

## Forms

### TaskThreadCommentForm
- Field: `content` (Textarea)
- Placeholder suggests @mention syntax

### ChatRoomForm
- Fields: `name`, `description`, `members` (checkboxes)
- Filters members to board members only

### ChatMessageForm
- Field: `content` (TextInput)
- Placeholder suggests @mention syntax

### MentionForm
- Field: `search` (TextInput for autocomplete)

## Admin Interface

Access Django admin at `/admin/messaging/`:

- **TaskThreadComment** - View/edit/delete task comments
- **ChatRoom** - Manage rooms and members
- **ChatMessage** - View/moderate messages
- **Notification** - Track notifications
- **UserTypingStatus** - Monitor active typers

## Security

### Access Control
- ✅ Chat rooms: Only members can send messages
- ✅ Task comments: Only board members can comment
- ✅ Notifications: Only recipient can view
- ✅ WebSocket: Session authentication required
- ✅ Admin: Django staff only

### Data Protection
- ✅ CSRF tokens on all forms
- ✅ Django template auto-escaping
- ✅ Input validation on all endpoints
- ✅ Database indexes for query performance
- ✅ Invalid mentions silently ignored

## Performance

### Database Optimization
- Indexes on `(chat_room, created_at)`
- Indexes on `(task, created_at)`
- Indexes on `(recipient, is_read, created_at)`
- Efficient M2M queries with `select_related()`

### WebSocket Efficiency
- Redis channel layer for broadcasting
- Async consumers for non-blocking I/O
- Automatic typing status expiration
- Message pagination for history

### Caching
- Channel layer handles message buffering
- Redis stores channel state
- Browser caching for static assets

## Usage Examples

### Creating a Chat Room (Python)
```python
from messaging.models import ChatRoom
from kanban.models import Board

board = Board.objects.get(id=1)
room = ChatRoom.objects.create(
    board=board,
    name="Frontend Team",
    description="Frontend development discussion",
    created_by=request.user
)
room.members.add(user1, user2, user3)
```

### Sending a Message (HTTP)
```python
# In view or template
form = ChatMessageForm(data={'content': '@john Great progress!'})
if form.is_valid():
    message = form.save(commit=False)
    message.chat_room = chat_room
    message.author = request.user
    message.save()
    message.notify_mentioned_users()
```

### Getting Notifications (JavaScript)
```javascript
// Fetch unread count
fetch('/messaging/notifications/count/')
    .then(r => r.json())
    .then(data => {
        console.log('Unread:', data.count);
    });

// View all notifications
window.location = '/messaging/notifications/';
```

### WebSocket Message (JavaScript)
```javascript
const socket = new WebSocket(
    'ws://' + window.location.host + '/ws/chat-room/1/'
);

socket.onmessage = function(e) {
    const data = JSON.parse(e.data);
    console.log(data.username + ': ' + data.message);
};

socket.send(JSON.stringify({
    'type': 'chat_message',
    'message': 'Hello @jane_smith!'
}));
```

## Integration Points

### With Kanban App
- Comments linked to Task model
- Chat rooms linked to Board model
- Notifications created when tasks are mentioned

### With Accounts App
- User authentication via Django auth
- Permissions based on board membership
- User profiles in notifications

## Troubleshooting

### WebSocket Not Connecting
- Check Redis is running: `redis-cli ping`
- Verify Daphne is running: `daphne -b 0.0.0.0 -p 8000 kanban_board.asgi:application`
- Check browser console for errors

### Messages Not Real-Time
- Redis may be offline
- WebSocket may not be configured
- Check CHANNEL_LAYERS in settings.py

### Mentions Not Working
- Verify username is exact
- User must exist in system
- User must be in board/room

### Notifications Not Appearing
- Check database has notification records
- Verify recipient user is correct
- Clear browser cache

## Future Enhancements

- [ ] Message editing
- [ ] Message deletion
- [ ] Message reactions (emoji)
- [ ] Message threading/replies
- [ ] Read receipts
- [ ] Message search
- [ ] Chat room archiving
- [ ] Scheduled messages
- [ ] File sharing
- [ ] Voice/video calling
- [ ] Message translations
- [ ] Message pinning
- [ ] Custom emojis
- [ ] Chat bot integration

## Testing

### Unit Tests
```bash
python manage.py test messaging.tests
```

### Manual Testing
1. Create board with members
2. Create chat room
3. Send messages from different users
4. Test @mentions
5. Check notifications
6. Verify real-time updates

### WebSocket Testing
```bash
# Use wscat or similar
wscat -c "ws://localhost:8000/ws/chat-room/1/"
{"type": "chat_message", "message": "test"}
```

## Deployment

### Development
```bash
# Terminal 1
redis-server

# Terminal 2
daphne -b 0.0.0.0 -p 8000 kanban_board.asgi:application
```

### Production
- Use Systemd service for Daphne
- Configure Nginx for WebSocket upgrade
- Set up Redis persistence
- Use PostgreSQL instead of SQLite
- Enable SSL/TLS
- Configure logging and monitoring

## Configuration

### settings.py
```python
# ASGI Application
ASGI_APPLICATION = 'kanban_board.asgi.application'

# Channel Layers
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('127.0.0.1', 6379)],
        },
    },
}
```

### requirements.txt
```
channels==4.0.0
channels-redis==4.1.0
daphne==4.0.0
redis==5.0.1
celery==5.3.4
```

## License

Same as PrizmAI project

## Support

- Check REALTIME_COMMUNICATION_GUIDE.md for detailed documentation
- Django Channels: https://channels.readthedocs.io/
- Redis: https://redis.io/docs/

---

**Module Status**: ✅ Production Ready
**Last Updated**: October 30, 2025
**Maintainer**: PrizmAI Team
