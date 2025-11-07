# Real-Time Communication Integration for PrizmAI

## Overview

This integration adds real-time communication capabilities to PrizmAI, enabling teams to collaborate effectively on tasks and boards. It includes:

1. **Task-Level Comments** - Add @mentions and real-time comments to individual tasks
2. **Board-Level Chat Rooms** - Create quick discussion channels for board-wide coordination
3. **Mention Notifications** - Automatic notifications when users are mentioned
4. **WebSocket Support** - Real-time message delivery using Django Channels

## Architecture

### Components

#### Models
- **TaskThreadComment** - Real-time comments on tasks with @mention support
- **ChatRoom** - Board-level discussion channels
- **ChatMessage** - Messages within chat rooms
- **Notification** - User notifications for mentions and activities
- **UserTypingStatus** - Tracks typing indicators in chat rooms

#### WebSocket Consumers
- **ChatRoomConsumer** - Handles real-time messaging in chat rooms
  - Manages user connections and disconnections
  - Broadcasts messages to room members
  - Tracks typing status indicators
  
- **TaskCommentConsumer** - Handles real-time comments on tasks
  - Broadcasts new comments to task subscribers
  - Processes @mentions and creates notifications

#### Views
- `chat_room_list` - List all chat rooms for a board
- `chat_room_detail` - Display and interact in a chat room
- `create_chat_room` - Create new chat rooms
- `send_chat_message` - Send messages (HTTP fallback)
- `task_thread_comments` - View and add comments on tasks
- `get_mentions` - Autocomplete for @mentions
- `notifications` - View all notifications
- `mark_notification_read` - Mark notifications as read

## Setup Instructions

### 1. Install Dependencies

All required packages are already in `requirements.txt`:
```bash
pip install -r requirements.txt
```

Key packages:
- `channels==4.0.0` - WebSocket support
- `channels-redis==4.1.0` - Message broker
- `daphne==4.0.0` - ASGI server
- `redis==5.0.1` - Redis client
- `celery==5.3.4` - Async task processing

### 2. Redis Setup

You need Redis running for WebSockets and Channels to work.

**Windows:**
1. Download Redis from: https://github.com/tporadowski/redis/releases
2. Extract to a location (e.g., `C:\redis`)
3. Run `redis-server.exe`

**macOS:**
```bash
brew install redis
redis-server
```

**Linux:**
```bash
sudo apt-get install redis-server
redis-server
```

### 3. Running the Development Server

You need to run two processes:

**Process 1 - Daphne ASGI Server (replaces runserver):**
```bash
daphne -b 0.0.0.0 -p 8000 kanban_board.asgi:application
```

**Process 2 - Optional: Celery Worker (for notifications):**
```bash
celery -A kanban_board worker -l info
```

Alternatively, use a simple approach with `runserver` for basic HTTP (WebSockets won't work):
```bash
python manage.py runserver
```

## Usage Guide

### 1. Creating a Chat Room

1. Go to a board
2. Click "Chat Rooms" or "Create Chat Room"
3. Fill in room details:
   - Name: Room identifier (e.g., "#frontend-discussion")
   - Description: Optional description
   - Add members to the room
4. Click Create

### 2. Sending Messages in Chat Rooms

Messages appear in real-time to all members in the room.

**Features:**
- Use `@username` to mention specific users
- Mentioned users get notifications immediately
- WebSocket provides instant delivery (no page refresh needed)
- Typing indicators show when others are typing

**URL Structure:**
```
/messaging/room/<room_id>/
```

### 3. Adding Comments to Tasks

1. Open a task detail page
2. Click "Add Comment" or scroll to the comments section
3. Type your comment
4. Use `@username` to mention team members
5. Press Enter or click Send

**Features:**
- Real-time comment updates
- @mentions trigger notifications
- Comments maintain chronological order
- All comments visible to board members

**URL Structure:**
```
/messaging/task/<task_id>/comments/
```

### 4. Notifications

Users receive notifications for:
- Being mentioned in chat messages
- Being mentioned in task comments
- New messages in their chat rooms (future enhancement)

**Views Unread Notifications:**
```
/messaging/notifications/
```

**Mark as Read:**
- Click notification link (automatically marked as read)
- Or use the mark-as-read button

**API Endpoint for Count:**
```
GET /messaging/notifications/count/
```

## API Endpoints

### Chat Messages
```
GET/POST  /messaging/room/<room_id>/send/       - Send a message
GET       /messaging/room/<room_id>/history/    - Get message history (pagination)
```

### Task Comments
```
GET/POST  /messaging/task/<task_id>/comments/   - View/add comments
GET       /messaging/task/<task_id>/comments/history/ - Get comment history
```

### Mentions
```
GET       /messaging/mentions/                   - Autocomplete mention suggestions
```

### Notifications
```
GET       /messaging/notifications/              - View all notifications
POST      /messaging/notifications/<id>/read/    - Mark as read
GET       /messaging/notifications/count/        - Get unread count
```

## WebSocket Endpoints

### Chat Room WebSocket
```
ws://localhost:8000/ws/chat-room/<room_id>/
```

**Message Format (Client → Server):**
```json
{
  "type": "chat_message",
  "message": "Hello team!"
}
```

Or for typing indicators:
```json
{
  "type": "typing"
}
```

```json
{
  "type": "stop_typing"
}
```

**Message Format (Server → Client):**
```json
{
  "type": "chat_message",
  "message_id": 123,
  "username": "john_doe",
  "user_id": 5,
  "message": "Hello team!",
  "timestamp": "2025-10-30T14:30:00Z",
  "mentioned_users": ["jane_smith"]
}
```

### Task Comments WebSocket
```
ws://localhost:8000/ws/task-comments/<task_id>/
```

**Message Format (Client → Server):**
```json
{
  "type": "comment",
  "comment": "Great progress @jane_smith!"
}
```

**Message Format (Server → Client):**
```json
{
  "type": "new_comment",
  "comment_id": 45,
  "username": "john_doe",
  "user_id": 5,
  "comment": "Great progress @jane_smith!",
  "timestamp": "2025-10-30T14:31:00Z",
  "mentioned_users": ["jane_smith"]
}
```

## @Mentions Feature

### How It Works
1. User types `@` in the message/comment box
2. JavaScript autocomplete suggests matching usernames
3. Mention is formatted as `@username` in the message
4. On save, regex extracts all mentions from the message
5. Mentioned users are linked to the message in the database
6. Notifications are created for each mentioned user

### Autocomplete API
```
GET /messaging/mentions/?q=john
```

**Response:**
```json
{
  "results": [
    {
      "id": 5,
      "text": "john_doe",
      "display": "john_doe (John Doe)"
    }
  ]
}
```

## Security Considerations

### Access Control
- Users can only send messages to chat rooms they are members of
- Users can only comment on tasks in boards they have access to
- WebSocket connections authenticate via Django session
- All views check membership before allowing access

### Data Privacy
- Messages are stored in the database with sender information
- Notifications only created for actual users
- Invalid mentions are silently ignored
- Message history respects board membership

## Database Schema

### TaskThreadComment
```python
- id: AutoField
- task: ForeignKey(Task)
- author: ForeignKey(User)
- content: TextField
- created_at: DateTimeField
- updated_at: DateTimeField
- mentioned_users: ManyToManyField(User)
```

### ChatRoom
```python
- id: AutoField
- board: ForeignKey(Board)
- name: CharField (100)
- description: TextField
- created_by: ForeignKey(User)
- created_at: DateTimeField
- members: ManyToManyField(User)
- unique_together: (board, name)
```

### ChatMessage
```python
- id: AutoField
- chat_room: ForeignKey(ChatRoom)
- author: ForeignKey(User)
- content: TextField
- created_at: DateTimeField
- mentioned_users: ManyToManyField(User)
```

### Notification
```python
- id: AutoField
- recipient: ForeignKey(User)
- sender: ForeignKey(User)
- notification_type: CharField (MENTION, COMMENT, CHAT_MESSAGE, ACTIVITY)
- text: TextField
- task_thread_comment: ForeignKey(TaskThreadComment, nullable)
- chat_message: ForeignKey(ChatMessage, nullable)
- created_at: DateTimeField
- is_read: BooleanField
```

## Frontend Integration Example

### HTML Template for Chat Room
```html
<div class="chat-container">
  <div id="messages"></div>
  <form id="message-form">
    <textarea id="message-input" placeholder="Type a message..."></textarea>
    <button type="submit">Send</button>
  </form>
</div>

<script>
  const roomId = {{ room_id }};
  const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
  const chatSocket = new WebSocket(
    protocol + window.location.host + '/ws/chat-room/' + roomId + '/'
  );
  
  chatSocket.onmessage = function(e) {
    const data = JSON.parse(e.data);
    if (data.type === 'chat_message') {
      // Display message in chat
      const msg = document.createElement('div');
      msg.textContent = data.username + ': ' + data.message;
      document.getElementById('messages').appendChild(msg);
    }
  };
  
  document.getElementById('message-form').onsubmit = function(e) {
    e.preventDefault();
    const input = document.getElementById('message-input');
    chatSocket.send(JSON.stringify({
      'type': 'chat_message',
      'message': input.value
    }));
    input.value = '';
  };
</script>
```

### HTML Template for Task Comments
```html
<div id="comments"></div>
<form id="comment-form">
  <textarea id="comment-input" placeholder="Add a comment..."></textarea>
  <button type="submit">Comment</button>
</form>

<script>
  const taskId = {{ task_id }};
  const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
  const commentSocket = new WebSocket(
    protocol + window.location.host + '/ws/task-comments/' + taskId + '/'
  );
  
  commentSocket.onmessage = function(e) {
    const data = JSON.parse(e.data);
    if (data.type === 'new_comment') {
      // Display comment
      const comment = document.createElement('div');
      comment.innerHTML = '<strong>' + data.username + ':</strong> ' + data.comment;
      document.getElementById('comments').appendChild(comment);
    }
  };
</script>
```

## Troubleshooting

### WebSocket Connection Fails
- **Cause**: Daphne not running or not listening on the correct port
- **Fix**: Ensure Daphne is started with: `daphne -b 0.0.0.0 -p 8000 kanban_board.asgi:application`

### Messages Not Appearing in Real-Time
- **Cause**: Redis not running or not accessible
- **Fix**: Start Redis and verify it's running on port 6379

### Notifications Not Sent
- **Cause**: Celery worker not running
- **Fix**: Optional - start with `celery -A kanban_board worker -l info`

### @Mentions Not Working
- **Cause**: JavaScript not initialized or username doesn't exist
- **Fix**: Ensure JavaScript is loaded and username matches exactly

### Chat Room Not Found
- **Cause**: User is not a member of the chat room
- **Fix**: Add user to the chat room members list

## Performance Tips

1. **Pagination**: Use message/comment history endpoints to load older messages on demand
2. **Typing Indicators**: Remove typing status after 10 seconds of inactivity
3. **Database Indexes**: Queries for messages/comments are indexed on (chat_room/task, created_at)
4. **Connection Pooling**: Redis channel layer handles multiple WebSocket connections efficiently

## Future Enhancements

1. Message editing and deletion
2. Message reactions (emoji reactions)
3. File sharing in chat rooms
4. Message threading/replies
5. Read receipts
6. Message search
7. Chat room archiving
8. Scheduled messages
9. Polls in chat
10. Integration with task status changes

## Admin Interface

The Django admin includes management interfaces for:
- TaskThreadComment
- ChatRoom
- ChatMessage
- Notification
- UserTypingStatus

Access at: `/admin/messaging/`

