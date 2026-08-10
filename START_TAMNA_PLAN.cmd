@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "ROOT=%CD%"
set "PY=%ROOT%\.venv\Scripts\python.exe"

echo ==============================================
echo   Tamna Plan - feature/backend + RAG evaluation
echo ==============================================

if not exist "%PY%" (
  echo [1/7] Creating .venv...
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3.14 -m venv .venv 2>nul || py -3.13 -m venv .venv 2>nul || py -3.12 -m venv .venv 2>nul || python -m venv .venv
  ) else (
    python -m venv .venv
  )
) else (
  echo [1/7] .venv found.
)
if not exist "%PY%" goto :venv_error

echo [2/7] Checking Python dependencies...
"%PY%" -c "import django, MySQLdb, chromadb, mysql.connector, google.auth, fastapi, uvicorn" >nul 2>nul
if errorlevel 1 (
  echo Installing requirements...
  "%PY%" -m pip install --upgrade pip
  if errorlevel 1 goto :dependency_error
  "%PY%" -m pip install -r requirements.txt
  if errorlevel 1 goto :dependency_error
)

echo [3/7] Checking local environment...
if not exist ".env" (copy /Y ".env.example" ".env" >nul & echo [ERROR] Created .env. Fill your MySQL/OpenAI/OAuth values and run again. & pause & exit /b 1)
if not exist "frontend\.env" (copy /Y "frontend\.env.example" "frontend\.env" >nul & echo [ERROR] Created frontend/.env. Fill Google/Kakao values and run again. & pause & exit /b 1)
"%PY%" scripts\windows\tamna_preflight.py
if errorlevel 1 (pause & exit /b 1)

echo [4/7] Checking evaluation integration...
"%PY%" VERIFY_FEATURE_BACKEND_EVALUATION.py
if errorlevel 1 goto :evaluation_error

echo [5/7] Checking Django and migrations...
"%PY%" backend\manage.py check
if errorlevel 1 goto :django_error
"%PY%" backend\manage.py migrate --noinput
if errorlevel 1 goto :django_error

echo [6/7] Checking frontend dependencies...
where npm >nul 2>nul
if errorlevel 1 goto :npm_missing
if not exist "frontend\node_modules" (
  pushd frontend
  call npm install
  if errorlevel 1 (popd & goto :npm_error)
  popd
)

echo [7/7] Starting Django + RAG Evaluation + Vite...
start "Tamna Plan Django" /D "%ROOT%" "%ComSpec%" /k call scripts\windows\run_django_backend.cmd
start "Tamna Plan RAG Evaluation" /D "%ROOT%" "%ComSpec%" /k call scripts\windows\run_rag_backend.cmd
start "Tamna Plan Frontend" /D "%ROOT%" "%ComSpec%" /k call scripts\windows\run_frontend.cmd

timeout /t 3 /nobreak >nul
start "" "http://localhost:5173/"
echo.
echo Frontend:       http://localhost:5173/
echo Django Swagger: http://localhost:8000/swagger/
echo Evaluation API: http://localhost:8001/docs
echo Evaluation UI:  http://localhost:5173/evaluation
echo.
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
:evaluation_error
echo [ERROR] feature/backend evaluation integration verification failed.
pause
exit /b 1
:django_error
echo [ERROR] Django check/migrate failed. Verify MySQL is running and .env DB permissions are correct.
pause
exit /b 1
:npm_missing
echo [ERROR] Node.js/npm is not installed.
pause
exit /b 1
:npm_error
echo [ERROR] npm install failed. Verify Node.js/npm and network access.
pause
exit /b 1
