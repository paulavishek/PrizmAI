# Real-Time Communication - Quick Start

## 30-Second Setup

### 1. Install Packages (Already Done)
```bash
pip install -r requirements.txt
```

### 2. Start Redis
- **Windows**: Run `redis-server.exe` from Redis directory
- **macOS/Linux**: Run `redis-server`

### 3. Run Daphne Server (Instead of `runserver`)
```bash
daphne -b 0.0.0.0 -p 8000 kanban_board.asgi:application
```

### 4. Access the Application
```
http://localhost:8000
```

## Key URLs

- **Chat Rooms**: `/messaging/board/<board_id>/rooms/`
- **Create Chat**: `/messaging/board/<board_id>/rooms/create/`
- **Task Comments**: `/messaging/task/<task_id>/comments/`
- **Notifications**: `/messaging/notifications/`

## Core Features

### 1. Board-Level Chat Rooms
- Navigate to a board
- Click "Chat Rooms"
- Create a new room
- Invite team members
- Send messages in real-time

**Benefits:**
- Quick team synchronization
- No email overhead
- @mention support for urgency
- Typing indicators

### 2. Task-Level Comments
- Open any task
- Click "Comments" tab
- Add comments with @mentions
- Real-time updates for all board members

**Benefits:**
- Context-specific discussions
- Task-specific notifications
- @mentions alert assignees

### 3. @Mentions
- Type `@username` in any message/comment
- Mentioned users get instant notifications
- Works with autocomplete suggestions

## Architecture Overview

```
┌─────────────────────────────────────────┐
│         PrizmAI Dashboard              │
│  ┌─────────────────────────────────┐   │
│  │  Chat Rooms | Task Comments     │   │
│  └─────────────────────────────────┘   │
└──────────────┬──────────────────────────┘
               │ WebSocket
               ▼
┌─────────────────────────────────────────┐
│      Daphne ASGI Server (Port 8000)     │
│  ┌──────────────────────────────────┐   │
│  │  ChatRoomConsumer                │   │
│  │  TaskCommentConsumer             │   │
│  └──────────────────────────────────┘   │
└──────────────┬──────────────────────────┘
               │ Messages
               ▼
┌─────────────────────────────────────────┐
│    Django Channels + Redis              │
│    (Message Broker & Storage)           │
└──────────────┬──────────────────────────┘
               │ Data
               ▼
┌─────────────────────────────────────────┐
│  PostgreSQL/SQLite Database             │
│  ┌──────────────────────────────────┐   │
│  │  ChatMessage | ChatRoom          │   │
│  │  TaskThreadComment | Notification│   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

## Development Tips

### Enable Django Debug Mode
Add to `.env`:
```
DEBUG=True
```

### View Logs
- Daphne logs appear in console
- Check `/logs/` directory for application logs

### Database Queries
- Use Django admin: `/admin/messaging/`
- View all chat rooms, messages, notifications
- Manage members and permissions

### Real-time Testing
1. Open chat room in 2 browser tabs (same user)
2. Send message from Tab 1
3. Watch it appear instantly in Tab 2
4. No page refresh needed!

## Integration with Existing Features

### Task Board Integration
- Access comments directly from task card hover
- Quick comment icon on task details
- Notification badge for new mentions

### Member Management
- Chat room members = Board members
- Add/remove members through board settings
- Automatic notification for new members

### Permission Model
- Create ChatRoom: Board members
- Send Message: Chat room members only
- Add Comment: Board members only
- Delete/Edit: Message author only (future)

## Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| WebSocket hangs | Daphne not running | `daphne -b 0.0.0.0 -p 8000 kanban_board.asgi:application` |
| No real-time updates | Redis offline | Start Redis server |
| 404 for chat rooms | URL wrong | Use `/messaging/board/<id>/rooms/` |
| Mentions don't work | User not in members | Add user to board/room |
| Blank chat history | Page not loaded | Refresh page or use history API |

## Files Modified/Created

### New Files
- `messaging/models.py` - Data models
- `messaging/views.py` - HTTP views
- `messaging/consumers.py` - WebSocket handlers
- `messaging/forms.py` - Django forms
- `messaging/urls.py` - URL routing
- `messaging/routing.py` - WebSocket routing
- `messaging/admin.py` - Django admin

### Modified Files
- `kanban_board/settings.py` - Added channels config
- `kanban_board/asgi.py` - WebSocket setup
- `kanban_board/urls.py` - Added messaging URLs
- `requirements.txt` - Added dependencies

### To Create (Templates)
- `templates/messaging/chat_room_list.html`
- `templates/messaging/chat_room_detail.html`
- `templates/messaging/create_chat_room.html`
- `templates/messaging/task_thread_comments.html`
- `templates/messaging/notifications.html`

## Next Steps

1. **Create HTML Templates** - See `REALTIME_COMMUNICATION_GUIDE.md` for examples
2. **Add JavaScript** - Implement WebSocket client code
3. **Test Features** - Create chat rooms and test @mentions
4. **Deploy** - Use Daphne + Gunicorn in production
5. **Monitor** - Set up Redis monitoring and Celery task tracking

## Production Deployment

### Using Systemd (Linux)
Create `/etc/systemd/system/PrizmAI-daphne.service`:
```ini
[Unit]
Description=PrizmAI Daphne Server
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/PrizmAI
ExecStart=/usr/bin/daphne -b 0.0.0.0 -p 8000 kanban_board.asgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

### Using Docker
```dockerfile
FROM python:3.11
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "kanban_board.asgi:application"]
```

### Nginx Reverse Proxy
```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header X-Real-IP $remote_addr;
}

location ~ ^/ws/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 86400;
}
```

## Support & Resources

- **Django Channels**: https://channels.readthedocs.io/
- **Redis**: https://redis.io/docs/
- **Daphne**: https://github.com/django/daphne
- **WebSocket API**: https://developer.mozilla.org/en-US/docs/Web/API/WebSocket

---

**Status**: ✅ Backend Complete | ⏳ Frontend Templates Pending | 🧪 Ready for Testing

