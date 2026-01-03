# PrizmAI Messaging Troubleshooting Guide

## Overview

The PrizmAI messaging feature uses **Django Channels** with **WebSockets** for real-time communication. This requires:
1. **Redis** - Message broker for channel layers
2. **Daphne** - ASGI server (instead of Django's runserver)
3. **Proper startup order** - Redis must start BEFORE Daphne

## Quick Diagnosis

Run the diagnostic script:
```bash
python check_messaging_config.py
```

## Common Issues and Solutions

### Issue 1: Messages Not Delivered in Real-Time

**Symptoms:**
- Messages only appear after page refresh
- Delays of several minutes before messages appear

**Causes & Solutions:**

1. **Redis not running**
   ```bash
   # Check if Redis is running
   redis-cli ping
   # Should return: PONG
   
   # If not running, start Redis:
   cd C:\redis\Redis-x64-5.0.14.1
   redis-server.exe
   ```

2. **Using Django runserver instead of Daphne**
   ```bash
   # WRONG - runserver doesn't support WebSockets
   python manage.py runserver
   
   # CORRECT - use Daphne
   daphne -b 0.0.0.0 -p 8000 kanban_board.asgi:application
   ```

3. **Startup order wrong**
   - Redis MUST be running before Daphne starts
   - Use `start_prizmAI.bat` which handles the correct order

### Issue 2: WebSocket Connection Drops

**Symptoms:**
- "Disconnected" status in chat header
- Connection errors in browser console

**Solutions:**
- The WebSocket now has automatic reconnection (up to 10 attempts)
- Check if Redis is still running
- Check if Daphne is still running
- Network issues (firewall, proxy, VPN)

### Issue 3: WebSocket Connection Refused

**Symptoms:**
- Immediate "Connection Error" status
- Console shows `WebSocket connection failed`

**Causes:**
- Daphne not running on port 8000
- Firewall blocking WebSocket connections
- Wrong WebSocket URL (check browser console)

### Issue 4: Messages Sent But Not Received by Others

**Symptoms:**
- Sender sees their message
- Other users don't see the message in real-time

**Cause:**
This is almost always a **Redis issue**. Without Redis, the channel layer can't relay messages between different WebSocket connections.

**Solution:**
```bash
# Restart Redis
redis-cli shutdown
redis-server.exe

# Then restart Daphne
```

## Correct Startup Procedure

### Option 1: Use the Batch File (Recommended)
```bash
start_prizmAI.bat
```

This starts (in order):
1. Redis Server
2. Celery Worker
3. Celery Beat
4. Daphne Server

### Option 2: Manual Startup
```bash
# Terminal 1: Start Redis
cd C:\redis\Redis-x64-5.0.14.1
redis-server.exe

# Terminal 2: Start Celery Worker
cd C:\Users\Avishek Paul\PrizmAI
venv\Scripts\activate
celery -A kanban_board worker --pool=solo -l info

# Terminal 3: Start Celery Beat
cd C:\Users\Avishek Paul\PrizmAI
venv\Scripts\activate
celery -A kanban_board beat -l info

# Terminal 4: Start Daphne
cd C:\Users\Avishek Paul\PrizmAI
venv\Scripts\activate
daphne -b 0.0.0.0 -p 8000 kanban_board.asgi:application
```

## Testing WebSocket Connection

### Browser Console Test
Open browser developer tools (F12) and run in Console:
```javascript
let ws = new WebSocket('ws://localhost:8000/ws/chat-room/1/');
ws.onopen = () => console.log('✅ Connected!');
ws.onmessage = (e) => console.log('📨 Message:', e.data);
ws.onerror = (e) => console.error('❌ Error:', e);
ws.onclose = (e) => console.log('🔌 Closed:', e.code);
```

### Network Tab Check
1. Open DevTools → Network tab
2. Filter by "WS" (WebSocket)
3. You should see the WebSocket connection
4. Click on it to see frames (sent/received messages)

## Configuration Reference

### settings.py
```python
# ASGI Application
ASGI_APPLICATION = 'kanban_board.asgi.application'

# Channel Layers (Redis)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('127.0.0.1', 6379)],
        },
    },
}
```

### asgi.py
```python
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from messaging.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
```

### routing.py
```python
websocket_urlpatterns = [
    path('ws/chat-room/<int:room_id>/', ChatRoomConsumer.as_asgi()),
    path('ws/task-comments/<int:task_id>/', TaskCommentConsumer.as_asgi()),
]
```

## New Features (v2.0)

### Auto-Reconnection
- WebSocket automatically reconnects if connection drops
- Up to 10 reconnection attempts with exponential backoff
- Visual status indicator in chat header

### Heartbeat/Keep-Alive
- Client sends ping every 25 seconds
- Server responds with pong
- Detects stale connections and triggers reconnect

### Connection Status Indicator
- 🟢 Connected (green)
- 🟡 Connecting/Reconnecting (yellow)
- 🔴 Disconnected/Error (red)

## Log Locations

- **Daphne logs**: Terminal window running Daphne
- **Redis logs**: Terminal window running Redis
- **Browser logs**: Developer Tools → Console

## Need More Help?

1. Run `python check_messaging_config.py` for diagnostics
2. Check browser console for JavaScript errors
3. Check Daphne terminal for Python errors
4. Check Redis is running: `redis-cli ping`
