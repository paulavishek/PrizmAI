@echo off
echo Starting PrizmAI Components...
echo.

:: Start Redis Server
echo [1/4] Starting Redis Server...
start cmd /k "title Redis Server && cd /d C:\redis\Redis-x64-5.0.14.1 && redis-server.exe"
echo Redis server started.
timeout /t 3 > nul

:: Start Celery Worker (background/scheduled tasks)
echo [2/5] Starting Celery Worker...
start cmd /k "title Celery Worker && cd /d "C:\Users\Avishek Paul\PrizmAI" && venv\Scripts\activate && celery -A kanban_board worker --pool=solo -l info -Q celery,summaries,ai_tasks"
echo Celery worker started.

:: Start dedicated Interactive Worker (user-triggered, fast-response tasks such
:: as Reset Demo / sandbox provisioning). Consuming ONLY the 'interactive' queue
:: keeps these off the main worker, which is serial (--pool=solo) and gets
:: flooded by Celery Beat's startup burst of heavy scheduled tasks.
echo [3/5] Starting Celery Interactive Worker...
start cmd /k "title Celery Worker (interactive) && cd /d "C:\Users\Avishek Paul\PrizmAI" && venv\Scripts\activate && celery -A kanban_board worker --pool=solo -l info -Q interactive -n worker-interactive@%%h"
echo Celery interactive worker started.

:: Start Daphne Server (for websockets and HTTP)
echo [4/5] Starting Daphne Server...
start cmd /k "title Daphne Server && cd /d "C:\Users\Avishek Paul\PrizmAI" && venv\Scripts\activate && daphne -b 0.0.0.0 -p 8000 kanban_board.asgi:application"
echo Daphne server started.

:: Start Celery Beat LAST, after a delay that outlasts a typical login+reset.
:: Two reasons for the delay:
::  1) Beat's DatabaseScheduler writes its schedule to SQLite on startup; starting
::     it into the workers+Daphne connection storm caused "database is locked" and a
::     full schedule re-fire.
::  2) More importantly, when Beat starts it dispatches any overdue hourly
::     maintenance/automation tasks (idle/due-date/digest sweeps) to the solo
::     default worker. On the local 100 MB+ SQLite DB those sweeps run for ~1-2 min
::     and hold SQLite's single write lock, starving a Reset Demo that the user
::     clicks right after login (the reset's own work is only ~10s, measured).
:: A 90s delay means Beat (and that one-time startup churn) begins AFTER a normal
:: "start servers -> log in -> Reset Demo" has already finished on a quiet DB.
:: NB: this sidesteps the collision for the common workflow; it is not a cure for
:: SQLite's single-writer limit. A reset clicked DURING the post-Beat churn, or on
:: Postgres-less heavy concurrency, can still contend.
echo [5/5] Starting Celery Beat (after a 90s delay so login+reset finishes first)...
start cmd /k "title Celery Beat && cd /d "C:\Users\Avishek Paul\PrizmAI" && venv\Scripts\activate && echo Waiting 90s for login+reset to finish before starting Beat... && timeout /t 90 > nul && celery -A kanban_board beat -l info"
echo Celery beat will start in ~90 seconds.

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
