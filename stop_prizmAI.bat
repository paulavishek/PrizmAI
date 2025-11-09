@echo off
echo Stopping PrizmAI Components...
echo.

:: Try to stop by window title first (cleaner approach)
echo Stopping components by window title...
taskkill /FI "WINDOWTITLE eq Redis Server" /T /F 2>nul
taskkill /FI "WINDOWTITLE eq Celery Worker" /T /F 2>nul
taskkill /FI "WINDOWTITLE eq Celery Beat" /T /F 2>nul
taskkill /FI "WINDOWTITLE eq Daphne Server" /T /F 2>nul

:: More reliable method to stop Redis server
echo Ensuring Redis server is stopped...
taskkill /F /FI "IMAGENAME eq redis-server.exe" 2>nul

:: More reliable method to stop Daphne and Celery processes
echo Ensuring Python processes (Daphne and Celery) are stopped...
taskkill /F /FI "IMAGENAME eq python.exe" /FI "COMMANDLINE eq *daphne*" 2>nul
taskkill /F /FI "IMAGENAME eq python.exe" /FI "COMMANDLINE eq *celery worker*" 2>nul
taskkill /F /FI "IMAGENAME eq python.exe" /FI "COMMANDLINE eq *celery beat*" 2>nul

:: Final check - stop any remaining processes related to our application
FOR /F "tokens=2" %%i IN ('tasklist /FI "IMAGENAME eq python.exe" /FO TABLE /NH 2^>nul') DO (
    tasklist /FI "PID eq %%i" /V /FO CSV | findstr /I "celery\|daphne" > nul
    IF NOT ERRORLEVEL 1 (
        echo Stopping Python process %%i (Celery/Daphne)
        taskkill /F /PID %%i 2>nul
    )
)

echo.
echo ============================================
echo All PrizmAI components stopped!
echo ============================================
echo.
pause
