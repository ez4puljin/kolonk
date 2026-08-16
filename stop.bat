@echo off
REM ===========================================================
REM  Kolonk - sistemiig zogsooh (API, worker, frontend, DB)
REM ===========================================================
chcp 65001 >nul 2>&1
title Kolonk POS - stop
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-dev.ps1" -Stop

ping -n 4 127.0.0.1 >nul 2>&1
exit /b 0
