@echo off
setlocal
cd /d "%~dp0\..\.."
"%CD%\.venv\Scripts\python.exe" backend\manage.py runserver localhost:8000
