@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0\..\.."
set "ROOT=%CD%"
set "PYTHON_EXE=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
  echo [ERROR] Virtual environment Python was not found:
  echo %PYTHON_EXE%
  echo Run START_TAMNA_PLAN.cmd again from the project root.
  pause
  exit /b 1
)

echo [Tamna Plan] Starting feature/backend RAG evaluation API at http://localhost:8001
echo Swagger docs: http://localhost:8001/docs
"%PYTHON_EXE%" -m uvicorn backend.evaluation_app:app --host localhost --port 8001 --reload
set "EXIT_CODE=%ERRORLEVEL%"
echo.
echo [Tamna Plan] RAG evaluation API stopped with exit code %EXIT_CODE%.
pause
exit /b %EXIT_CODE%
