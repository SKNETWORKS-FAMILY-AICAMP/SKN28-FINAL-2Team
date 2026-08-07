@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PY=%CD%\.venv\Scripts\python.exe"

echo ==============================================
echo   Tamna Plan - MySQL bootstrap
echo ==============================================

if not exist ".env" (
  copy /Y ".env.example" ".env" >nul
  echo [ERROR] .env was created. Fill MYSQL_ADMIN_USER and MYSQL_ADMIN_PASSWORD, then run this file again.
  pause
  exit /b 1
)

if not exist "%PY%" (
  echo Creating .venv...
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3.14 -m venv .venv 2>nul || py -3.13 -m venv .venv 2>nul || py -3.12 -m venv .venv 2>nul || python -m venv .venv
  ) else (
    python -m venv .venv
  )
)
if not exist "%PY%" (
  echo [ERROR] Failed to create .venv.
  pause
  exit /b 1
)

"%PY%" -c "import mysql.connector, dotenv" >nul 2>nul
if errorlevel 1 (
  echo Installing bootstrap dependencies...
  "%PY%" -m pip install "mysql-connector-python>=9.6.0,<10.0" "python-dotenv==1.2.2"
  if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
  )
)

"%PY%" scripts\bootstrap_mysql.py --env-file .env
if errorlevel 1 (
  echo.
  echo [ERROR] Bootstrap failed. Check MYSQL_ADMIN_USER / MYSQL_ADMIN_PASSWORD and whether MySQL is running.
  pause
  exit /b 1
)

echo.
echo MySQL databases and tour_app permissions are ready.
pause
