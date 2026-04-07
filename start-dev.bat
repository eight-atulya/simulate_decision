@echo off
echo Starting SimulateDecision Backend Server...
start "SimulateDecision Server" cmd /k ".venv\Scripts\activate && uv run simulate-decision-server"

timeout /t 3 /nobreak >nul

echo Starting SimulateDecision UI...
start "SimulateDecision UI" cmd /k ".venv\Scripts\activate && uv run simulate-decision-ui"

echo.
echo Both servers starting!
echo - Backend API: http://localhost:8000
echo - UI Dashboard: http://localhost:8501
echo.
echo Press any key to exit this window...
pause >nul