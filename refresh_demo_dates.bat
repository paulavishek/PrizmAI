@echo off
REM Refresh PrizmAI Demo Data Dates
REM This script refreshes all demo data dates to be relative to the current date
REM Run this periodically to keep your demo data fresh and prevent overdue tasks

echo ========================================================================
echo Refreshing PrizmAI Demo Data Dates
echo ========================================================================
echo.
echo This will update all task, milestone, and time entry dates
echo to be relative to the current date, maintaining realistic
echo date distributions based on task status.
echo.

python manage.py refresh_demo_dates

if %ERRORLEVEL% == 0 (
    echo.
    echo ========================================================================
    echo Demo data dates refreshed successfully!
    echo ========================================================================
    echo.
    echo Your demo data is now up-to-date with current dates.
    echo Tasks are distributed appropriately across past, present, and future.
    echo.
) else (
    echo.
    echo ========================================================================
    echo Error refreshing demo data dates!
    echo ========================================================================
    echo.
    echo Please check the error messages above and try again.
    echo.
)

pause
