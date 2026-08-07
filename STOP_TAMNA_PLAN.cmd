@echo off
chcp 65001 >nul
taskkill /FI "WINDOWTITLE eq Tamna Plan Django*" /T /F >nul 2>nul
taskkill /FI "WINDOWTITLE eq Tamna Plan Frontend*" /T /F >nul 2>nul
echo Tamna Plan development servers stopped.
pause
