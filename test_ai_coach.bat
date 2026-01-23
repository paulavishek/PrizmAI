@echo off
echo ============================================================
echo AI Coach Enhancement Test
echo ============================================================
echo.

REM Activate virtual environment if it exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo Warning: Virtual environment not found
)

echo Running AI enhancement test...
echo.

python manage.py shell --command="from kanban.utils.ai_coach_service import AICoachService; coach = AICoachService(); print('Gemini Available:', coach.gemini_available); print('AI Enhancement:', 'ENABLED' if coach.gemini_available else 'DISABLED')"

echo.
echo ============================================================
echo Test complete!
echo ============================================================
pause
