# PrizmAI Startup Scripts - Quick Guide

## Overview

Two batch files make it easy to start and stop all PrizmAI components with a single command:

- **`start_PrizmAI.bat`** - Starts all required services
- **`stop_PrizmAI.bat`** - Stops all running services

## Requirements

Before using these scripts, ensure you have:

1. **Redis Server** installed at: `C:\redis\Redis-x64-5.0.14.1\`
   - Download from: https://github.com/tporadowski/redis/releases
   - Extract to the path above (update in `start_PrizmAI.bat` if different)

2. **Python Virtual Environment** activated
   - Located at: `C:\Users\Avishek Paul\PrizmAI\venv\`
   - Created with: `python -m venv venv`

3. **Dependencies installed**
   - Run: `pip install -r requirements.txt`

## Starting PrizmAI

### Option 1: Double-Click (Easiest)
1. Navigate to `C:\Users\Avishek Paul\PrizmAI\`
2. Double-click `start_PrizmAI.bat`
3. Wait for all 4 components to start (about 5 seconds)

### Option 2: Command Line
```bash
cd "C:\Users\Avishek Paul\PrizmAI"
start_PrizmAI.bat
```

### What Gets Started

When you run `start_PrizmAI.bat`, it automatically starts:

| Component | Port | Purpose | Window Title |
|-----------|------|---------|--------------|
| **Redis Server** | 6379 | Message broker & cache | Redis Server |
| **Celery Worker** | N/A | Background tasks | Celery Worker |
| **Celery Beat** | N/A | Scheduled tasks | Celery Beat |
| **Daphne Server** | 8000 | WebSocket & HTTP | Daphne Server |

Each component runs in its own command window for easy monitoring.

## Accessing PrizmAI

Once all components have started, access the application:

| Feature | URL |
|---------|-----|
| Main Application | http://localhost:8000/ |
| Admin Dashboard | http://localhost:8000/admin/ |
| Messaging Module | http://localhost:8000/messaging/ |
| Django Shell | `python manage.py shell` |

## Stopping PrizmAI

### Option 1: Double-Click (Easiest)
1. Navigate to `C:\Users\Avishek Paul\PrizmAI\`
2. Double-click `stop_PrizmAI.bat`
3. All components will be stopped gracefully

### Option 2: Command Line
```bash
cd "C:\Users\Avishek Paul\PrizmAI"
stop_PrizmAI.bat
```

### Option 3: Manually Close Windows
- Close each command window individually (Redis Server, Celery Worker, Celery Beat, Daphne Server)
- Or press `Ctrl+C` in each window

## Troubleshooting

### Redis Server Won't Start
**Problem**: "Connection refused" or Redis port in use
```
Solution:
1. Check if Redis is already running: tasklist | find "redis-server.exe"
2. Kill existing Redis: taskkill /F /IM redis-server.exe
3. Verify Redis path in start_PrizmAI.bat is correct
```

### Daphne Server Won't Start
**Problem**: "Port 8000 already in use"
```
Solution 1 - Kill existing process:
  taskkill /F /IM python.exe /FI "COMMANDLINE eq *daphne*"

Solution 2 - Use different port:
  Edit start_PrizmAI.bat, change:
    daphne -b 0.0.0.0 -p 8000 ...
  To:
    daphne -b 0.0.0.0 -p 8001 ...
```

### Celery Worker/Beat Won't Start
**Problem**: "Virtual environment not activated"
```
Solution:
1. Verify venv folder exists at: C:\Users\Avishek Paul\PrizmAI\venv\
2. Run pip install from workspace: pip install -r requirements.txt
3. Check Windows PATH includes Python
```

### Components Start Then Immediately Close
**Problem**: Missing dependencies or configuration error
```
Solution:
1. Open Command Prompt
2. Navigate to: cd "C:\Users\Avishek Paul\PrizmAI"
3. Activate venv: venv\Scripts\activate
4. Check for errors: python manage.py check
5. Run specific component manually to see error:
   - daphne -b 0.0.0.0 -p 8000 kanban_board.asgi:application
```

## Customizing the Scripts

### Change Redis Path
Edit `start_PrizmAI.bat`, line 6:
```bat
:: Default:
cd /d C:\redis\Redis-x64-5.0.14.1

:: Change to your Redis path:
cd /d "C:\path\to\your\redis"
```

### Change Project Path
Edit both batch files, update all instances of:
```bat
cd /d "C:\Users\Avishek Paul\PrizmAI"
```

### Change Port Number
Edit `start_PrizmAI.bat`, line 22:
```bat
:: Default (port 8000):
daphne -b 0.0.0.0 -p 8000 kanban_board.asgi:application

:: Use different port (e.g., 8001):
daphne -b 0.0.0.0 -p 8001 kanban_board.asgi:application
```

### Change Celery Log Level
Edit `start_PrizmAI.bat`:
- Line 12: `celery -A kanban_board worker --pool=solo -l info`
- Line 16: `celery -A kanban_board beat -l info`

Log levels: `debug`, `info`, `warning`, `error`, `critical`

## Environment Variables

To set environment variables before starting, add to `start_PrizmAI.bat`:

```bat
:: Add after @echo off, before first start command:
set DEBUG=True
set PYTHONUNBUFFERED=1
set DJANGO_SETTINGS_MODULE=kanban_board.settings
```

## Performance Tips

1. **Close Unnecessary Applications**: Frees up RAM for PrizmAI
2. **Monitor Resource Usage**: Open Windows Task Manager to watch CPU/Memory
3. **Check Redis Memory**: `redis-cli info memory` in Redis window
4. **Increase Virtual Memory**: If RAM is limited, increase page file size

## Testing the Setup

After starting with `start_PrizmAI.bat`:

1. **Test Redis**:
   ```bash
   redis-cli ping
   # Should respond: PONG
   ```

2. **Test Django**:
   ```bash
   python manage.py check
   # Should show: System check identified no issues
   ```

3. **Test WebSocket**:
   - Open browser DevTools (F12)
   - Go to Console tab
   - Try to connect to any messaging page
   - Check for WebSocket connection in Network tab

4. **View Logs**:
   - Check each command window for errors
   - Django/Daphne logs appear in their window
   - Celery logs appear in their windows

## Advanced Usage

### Run with Custom Configuration
```bash
:: Terminal 1
redis-server.exe

:: Terminal 2
cd "C:\Users\Avishek Paul\PrizmAI"
venv\Scripts\activate
daphne -b 0.0.0.0 -p 8000 -v 2 kanban_board.asgi:application

:: Terminal 3
celery -A kanban_board worker --pool=solo -l debug

:: Terminal 4
celery -A kanban_board beat -l debug
```

### Monitor Resource Usage
While PrizmAI is running:
```bash
:: Check Redis memory
redis-cli info memory

:: Check Python processes
tasklist /FI "IMAGENAME eq python.exe" /V

:: Check overall system
tasklist /V
```

## Uninstall/Reset

To completely reset PrizmAI:

```bash
:: 1. Stop all components
stop_PrizmAI.bat

:: 2. Delete database (optional)
del db.sqlite3

:: 3. Delete cache and temp files
rmdir /S /Q __pycache__
rmdir /S /Q .pytest_cache

:: 4. Reinstall dependencies
pip install -r requirements.txt --force-reinstall

:: 5. Create fresh database
python manage.py migrate
python manage.py createsuperuser
```

## Quick Reference Commands

```bash
:: Check if Redis is running
redis-cli ping

:: Check Django status
python manage.py check

:: Create new admin user
python manage.py createsuperuser

:: View running processes
tasklist

:: Kill specific process
taskkill /F /PID <process_id>

:: Get help for daphne
daphne --help

:: Get help for celery
celery --help
```

## Support

If you encounter issues:

1. Check that **all 4 component windows** have started (may require scrolling)
2. Look for **error messages** in the command windows
3. Verify **Redis is installed** at the correct path
4. Ensure **all packages are installed**: `pip install -r requirements.txt`
5. Check **port 8000** is not in use by another application
6. Review **REALTIME_COMMUNICATION_QUICKSTART.md** for additional troubleshooting

## Next Steps

After successfully starting PrizmAI:

1. ✅ **Verify Setup** - Open http://localhost:8000/ in browser
2. 📝 **Create Admin User** - If not already created
3. 🗂️ **Create First Board** - To start using features
4. 💬 **Test Messaging** - Try creating a chat room
5. 📚 **Read Documentation** - See REALTIME_COMMUNICATION_GUIDE.md

---

**Status**: ✅ Production Ready | 🚀 One-Click Startup | 📊 Multi-Process Architecture

**Last Updated**: October 30, 2025
**Compatibility**: Windows (7, 10, 11, Server)
**Tested With**: Python 3.13, Django 5.2.3, Redis 5.0+
