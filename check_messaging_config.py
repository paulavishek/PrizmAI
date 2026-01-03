"""
Diagnostic script for PrizmAI Messaging Feature
Checks WebSocket, Redis, Channels configuration
"""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')

import django
django.setup()

from django.conf import settings
import socket
import subprocess

print("=" * 80)
print("PRIZMAI MESSAGING DIAGNOSTIC")
print("=" * 80)

# 1. Check Django Channels Installation
print("\n1️⃣  DJANGO CHANNELS CONFIGURATION")
print("-" * 40)

try:
    import channels
    print(f"   ✅ Django Channels installed: v{channels.__version__}")
except ImportError:
    print("   ❌ Django Channels NOT installed!")

try:
    import channels_redis
    print(f"   ✅ channels-redis installed: v{channels_redis.__version__}")
except ImportError:
    print("   ❌ channels-redis NOT installed!")

# Check ASGI_APPLICATION
asgi_app = getattr(settings, 'ASGI_APPLICATION', None)
if asgi_app:
    print(f"   ✅ ASGI_APPLICATION: {asgi_app}")
else:
    print("   ❌ ASGI_APPLICATION not configured!")

# Check CHANNEL_LAYERS
channel_layers = getattr(settings, 'CHANNEL_LAYERS', None)
if channel_layers:
    backend = channel_layers.get('default', {}).get('BACKEND', 'Unknown')
    config = channel_layers.get('default', {}).get('CONFIG', {})
    print(f"   ✅ CHANNEL_LAYERS backend: {backend}")
    print(f"      Config: {config}")
else:
    print("   ❌ CHANNEL_LAYERS not configured!")


# 2. Check Redis Connection
print("\n2️⃣  REDIS CONNECTION")
print("-" * 40)

redis_host = '127.0.0.1'
redis_port = 6379

# Check if Redis port is open
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    result = sock.connect_ex((redis_host, redis_port))
    sock.close()
    
    if result == 0:
        print(f"   ✅ Redis port {redis_port} is OPEN")
    else:
        print(f"   ❌ Redis port {redis_port} is CLOSED")
        print("      Make sure Redis server is running!")
except Exception as e:
    print(f"   ❌ Error checking Redis port: {e}")

# Try actual Redis connection
try:
    import redis
    r = redis.Redis(host=redis_host, port=redis_port, db=0)
    r.ping()
    print(f"   ✅ Redis PING successful!")
    info = r.info('server')
    print(f"      Redis version: {info.get('redis_version', 'Unknown')}")
except ImportError:
    print("   ⚠️  redis-py not installed (optional for this check)")
except Exception as e:
    print(f"   ❌ Redis connection failed: {e}")
    print("      Make sure Redis is running: redis-server.exe")


# 3. Check Daphne Installation
print("\n3️⃣  DAPHNE (ASGI SERVER)")
print("-" * 40)

try:
    import daphne
    print(f"   ✅ Daphne installed: v{daphne.__version__}")
except ImportError:
    print("   ❌ Daphne NOT installed!")
    print("      Install with: pip install daphne")


# 4. Check WebSocket Routing
print("\n4️⃣  WEBSOCKET ROUTING")
print("-" * 40)

try:
    from messaging.routing import websocket_urlpatterns
    print(f"   ✅ WebSocket URL patterns: {len(websocket_urlpatterns)} routes")
    for pattern in websocket_urlpatterns:
        print(f"      - {pattern.pattern}")
except Exception as e:
    print(f"   ❌ Error loading WebSocket routes: {e}")


# 5. Check Consumer
print("\n5️⃣  WEBSOCKET CONSUMERS")
print("-" * 40)

try:
    from messaging.consumers import ChatRoomConsumer, TaskCommentConsumer
    print("   ✅ ChatRoomConsumer loaded")
    print("   ✅ TaskCommentConsumer loaded")
except Exception as e:
    print(f"   ❌ Error loading consumers: {e}")


# 6. Check ASGI Application
print("\n6️⃣  ASGI APPLICATION")
print("-" * 40)

try:
    from kanban_board.asgi import application
    print(f"   ✅ ASGI application loaded: {type(application).__name__}")
except Exception as e:
    print(f"   ❌ Error loading ASGI application: {e}")


# 7. Check for potential issues
print("\n7️⃣  POTENTIAL ISSUES CHECK")
print("-" * 40)

issues = []

# Check if running with runserver (not Daphne)
if 'runserver' in sys.argv:
    issues.append("Running with 'runserver' instead of 'daphne' - WebSockets may not work!")

# Check Redis hosts config
if channel_layers:
    hosts = channel_layers.get('default', {}).get('CONFIG', {}).get('hosts', [])
    if hosts:
        host_tuple = hosts[0]
        if isinstance(host_tuple, tuple):
            h, p = host_tuple
            if h != '127.0.0.1' and h != 'localhost':
                issues.append(f"Redis host is {h} - make sure it's reachable")

# Check for InMemoryChannelLayer (bad for production)
if channel_layers:
    backend = channel_layers.get('default', {}).get('BACKEND', '')
    if 'InMemory' in backend:
        issues.append("Using InMemoryChannelLayer - messages won't be shared across workers!")

if issues:
    for issue in issues:
        print(f"   ⚠️  {issue}")
else:
    print("   ✅ No obvious configuration issues found")


# 8. WebSocket Connection Test Info
print("\n8️⃣  WEBSOCKET TEST INFO")
print("-" * 40)
print("""
   To test WebSocket connectivity:
   
   1. Make sure you're running Daphne (not Django runserver):
      daphne -b 0.0.0.0 -p 8000 kanban_board.asgi:application
   
   2. Open browser console and run:
      let ws = new WebSocket('ws://localhost:8000/ws/chat-room/1/');
      ws.onopen = () => console.log('Connected!');
      ws.onmessage = (e) => console.log('Received:', e.data);
      ws.onerror = (e) => console.log('Error:', e);
   
   3. Check browser Network tab > WS filter for WebSocket frames
""")


# 9. Recommendations
print("\n9️⃣  RECOMMENDATIONS")
print("-" * 40)
print("""
   For reliable real-time messaging:
   
   1. ✓ Always use Daphne (your start_prizmAI.bat does this correctly)
   2. ✓ Make sure Redis is running BEFORE Daphne
   3. ✓ Check browser console for WebSocket errors
   4. ⚡ Consider adding WebSocket reconnection logic
   5. ⚡ Add heartbeat/ping-pong to keep connections alive
""")

print("\n" + "=" * 80)
print("DIAGNOSTIC COMPLETE")
print("=" * 80)
