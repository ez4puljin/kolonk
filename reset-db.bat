@echo off
REM ===========================================================
REM  Kolonk - database-iig tsewerlej shineer seed hiih wrapper.
REM  PowerShell-iin ExecutionPolicy haalttai PC deer ch ajillana.
REM  Argument-uud shuud damjina: reset-db.bat -Demo  /  -Force
REM ===========================================================
chcp 65001 >nul 2>&1
title Kolonk reset-db
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0reset-db.ps1" %*
set "RC=%errorlevel%"

echo.
if %RC% neq 0 (
    echo [!] Aldaa garlaa. Deerh medeelliig unshina uu.
) else (
    echo [OK] Duuslaa.
)
pause
exit /b %RC%
