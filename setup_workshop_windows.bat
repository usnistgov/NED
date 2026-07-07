@echo off
setlocal
title NED Workshop Setup
cd /d "%~dp0"
chcp 65001 >nul

echo ============================================================
echo  NED - Nonstructural Element Database - Workshop Setup
echo ============================================================
echo.
echo This script will:
echo   1. Install the "uv" Python manager (if not already installed)
echo   2. Create a private Python 3.12 environment in ".\venv"
echo   3. Install all required packages
echo   4. Build the NED database from the source JSON data
echo.
echo No admin rights are needed. Nothing is installed outside your
echo user folder and this project folder. Safe to re-run anytime.
echo.

set "PYTHONUTF8=1"

rem ---- Step 1: find or install uv ---------------------------------
set "UV=uv"
where uv >nul 2>&1
if %errorlevel%==0 (
    echo [1/4] uv is already installed.
    goto uv_ready
)
if exist "%USERPROFILE%\.local\bin\uv.exe" (
    set "UV=%USERPROFILE%\.local\bin\uv.exe"
    echo [1/4] uv is already installed.
    goto uv_ready
)
echo [1/4] Installing uv (this does not require admin rights^)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
if errorlevel 1 goto fail
set "UV=%USERPROFILE%\.local\bin\uv.exe"
if not exist "%UV%" (
    echo Could not find uv at "%UV%" after installation.
    goto fail
)

:uv_ready

rem ---- Step 2: create the Python environment ----------------------
echo.
echo [2/4] Setting up a Python 3.12 environment in ".\venv"...
if exist venv\Scripts\python.exe (
    echo        Found an existing environment - reusing it.
    goto venv_ready
)
"%UV%" venv venv --python 3.12
if errorlevel 1 goto fail

:venv_ready

rem ---- Step 3: install packages -----------------------------------
echo.
echo [3/4] Installing required packages...
"%UV%" pip install --python venv\Scripts\python.exe -r requirements-workshop.txt
if errorlevel 1 goto fail

rem ---- Step 4: build the database ---------------------------------
echo.
echo [4/4] Building the NED database (migrate + ingest^)...
venv\Scripts\python.exe manage.py migrate
if errorlevel 1 goto fail
venv\Scripts\python.exe manage.py ingest
if errorlevel 1 goto fail

echo.
echo ============================================================
echo  Setup complete!
echo ============================================================
echo.
echo This window is now a ready-to-use NED terminal. The "(venv)"
echo prefix on the prompt means the project environment is active.
echo.
echo Next steps:
echo   * To open the NED web app: double-click start_app_windows.bat
echo   * To run project commands, type them right here, e.g.:
echo       python manage.py import_model --model Experiment --input_file my_data.csv
echo       python manage.py ingest
echo.
echo Need this terminal again later? Double-click this file again.
echo Re-running is safe and only takes a few seconds.
echo.
call venv\Scripts\activate.bat
cmd /k
exit /b 0

:fail
echo.
echo ------------------------------------------------------------
echo  Setup did NOT complete. Please review the message above,
echo  or ask a workshop host for help.
echo ------------------------------------------------------------
pause
exit /b 1
