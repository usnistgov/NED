@echo off
title NED Web App
cd /d "%~dp0"

if not exist venv\Scripts\python.exe (
    echo The project environment was not found.
    echo Please run setup_workshop_windows.bat first.
    pause
    exit /b 1
)

if not exist db.sqlite3 (
    echo The NED database was not found.
    echo Please run setup_workshop_windows.bat first to build it.
    pause
    exit /b 1
)

cd ui
set "DB_PATH=../db.sqlite3"
set "AUTH_ENABLED=false"
set "STREAMLIT_BROWSER_GATHER_USAGE_STATS=false"

echo Starting the NED web app... a browser tab should open shortly.
echo.
echo Keep this window open while using the app.
echo Press Ctrl+C here (or close this window) to stop the app.
echo.
..\venv\Scripts\python.exe -m streamlit run app.py
pause
