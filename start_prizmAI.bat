@echo off
echo Starting PrizmAI Components...
echo.

:: Start Redis Server
echo [1/4] Starting Redis Server...
start cmd /k "title Redis Server && cd /d C:\redis\Redis-x64-5.0.14.1 && redis-server.exe"
echo Redis server started.
timeout /t 3 > nul

:: Start Celery Worker
echo [2/4] Starting Celery Worker...
start cmd /k "title Celery Worker && cd /d "C:\Users\Avishek Paul\PrizmAI" && venv\Scripts\activate && celery -A kanban_board worker --pool=solo -l info -Q celery,summaries"
echo Celery worker started.

:: Start Celery Beat
echo [3/4] Starting Celery Beat...
start cmd /k "title Celery Beat && cd /d "C:\Users\Avishek Paul\PrizmAI" && venv\Scripts\activate && celery -A kanban_board beat -l info"
echo Celery beat started.

:: Start Daphne Server (for websockets and HTTP)
echo [4/4] Starting Daphne Server...
start cmd /k "title Daphne Server && cd /d "C:\Users\Avishek Paul\PrizmAI" && venv\Scripts\activate && daphne -b 0.0.0.0 -p 8000 kanban_board.asgi:application"
echo Daphne server started.

echo.
echo ============================================
echo All PrizmAI components started successfully!
echo ============================================
echo.
echo Access your application at:
echo   http://localhost:8000/
echo.
echo Admin Dashboard at:
echo   http://localhost:8000/admin/
echo.
echo Real-time Messaging at:
echo   http://localhost:8000/messaging/
echo.
echo To stop all services, run:
echo   stop_prizmAI.bat
echo.
pause
