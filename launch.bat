@echo off
title Learn Python App
echo Starting Learn Python App...
echo.

REM Kill any old instance that might be running
wsl.exe -d Ubuntu-24.04 bash -c "pkill -f 'python3 app.py' 2>/dev/null; sleep 1"

REM Start a fresh Flask server
start "Learn Python Server" wsl.exe -d Ubuntu-24.04 bash -c "cd /mnt/c/Users/progm/python-learning-app && python3 app.py"

REM Wait for Flask to start
timeout /t 5 /nobreak > nul

REM Open the browser
start "" "http://localhost:5000"

echo App is running! You can close this window.
timeout /t 3 /nobreak > nul
