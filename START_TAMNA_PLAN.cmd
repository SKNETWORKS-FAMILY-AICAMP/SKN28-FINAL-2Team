@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "ROOT=%CD%"
set "PY=%ROOT%\.venv\Scripts\python.exe"

echo ==============================================
echo   Tamna Plan - feature/backend runnable launcher
echo ==============================================

if not exist "%PY%" (
  echo [1/6] Creating .venv...
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3.14 -m venv .venv 2>nul || py -3.13 -m venv .venv 2>nul || py -3.12 -m venv .venv 2>nul || python -m venv .venv
  ) else (
    python -m venv .venv
  )
) else (
  echo [1/6] .venv found.
)
if not exist "%PY%" goto :venv_error

echo [2/6] Checking Python dependencies...
"%PY%" -c "import django, MySQLdb, chromadb, mysql.connector, google.auth" >nul 2>nul
if errorlevel 1 (
  echo Installing requirements...
  "%PY%" -m pip install --upgrade pip
  if errorlevel 1 goto :dependency_error
  "%PY%" -m pip install -r requirements.txt
  if errorlevel 1 goto :dependency_error
)

echo [3/6] Checking local environment...
if not exist ".env" (copy /Y ".env.example" ".env" >nul & echo [ERROR] Created .env. Fill your MySQL/OpenAI/OAuth values and run again. & pause & exit /b 1)
if not exist "frontend\.env" (copy /Y "frontend\.env.example" "frontend\.env" >nul & echo [ERROR] Created frontend/.env. Fill Google/Kakao values and run again. & pause & exit /b 1)
"%PY%" scripts\windows\tamna_preflight.py
if errorlevel 1 (pause & exit /b 1)

echo [4/6] Checking Django and migrations...
"%PY%" backend\manage.py check
if errorlevel 1 goto :django_error
"%PY%" backend\manage.py migrate --noinput
if errorlevel 1 goto :django_error

echo [5/6] Checking frontend dependencies...
if not exist "frontend\node_modules" (
  pushd frontend
  call npm install
  if errorlevel 1 (popd & goto :npm_error)
  popd
)

echo [6/6] Starting Django + Vite...
start "Tamna Plan Django" "%ComSpec%" /k call "%ROOT%\scripts\windows\run_django_backend.cmd"
start "Tamna Plan Frontend" "%ComSpec%" /k call "%ROOT%\scripts\windows\run_frontend.cmd"
timeout /t 3 /nobreak >nul
start "" "http://localhost:5173/"
echo Started. Close with STOP_TAMNA_PLAN.cmd
exit /b 0

:venv_error
echo [ERROR] Failed to create .venv. Install Python 3.12+ and retry.
pause
exit /b 1
:dependency_error
echo [ERROR] Python dependency installation failed.
pause
exit /b 1
:django_error
echo [ERROR] Django check/migrate failed. Verify MySQL is running and .env DB permissions are correct.
pause
exit /b 1
:npm_error
echo [ERROR] npm install failed. Verify Node.js/npm and network access.
pause
exit /b 1
