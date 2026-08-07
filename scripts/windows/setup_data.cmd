@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0\..\.."
set "PY=%CD%\.venv\Scripts\python.exe"
if not exist "%PY%" (echo [ERROR] Run START_TAMNA_PLAN.cmd once to create .venv. & pause & exit /b 1)
echo This loads TourAPI + AIHub + curated 30 packages into MYSQL_DATABASE.
echo Existing travel data can be replaced. Press Ctrl+C to cancel.
pause
"%PY%" -m scripts.storage.manage_tourapi_storage --env-file .env mysql-load --recreate-database || goto :err
"%PY%" -m scripts.storage.load_aihub_to_mysql --replace || goto :err
"%PY%" scripts\load_final_packages.py --env-file .env || goto :err
echo Data setup completed.
pause
exit /b 0
:err
echo [ERROR] Data setup failed.
pause
exit /b 1
