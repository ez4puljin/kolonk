@echo off
REM ===========================================================
REM  Kolonk - ugugdul zeeverleh bagts uusgeh wrapper.
REM  PowerShell-iin ExecutionPolicy haalttai PC deer ch ajillana.
REM  Argument-uud shuud damjina (jishee: backup-data.bat -Local).
REM ===========================================================
chcp 65001 >nul 2>&1
title Kolonk backup
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0backup-data.ps1" %*
set "RC=%errorlevel%"

echo.
if %RC% neq 0 (
    echo [!] Aldaa garlaa. Deerh medeelliig unshina uu.
) else (
    echo [OK] Duuslaa.
)
pause
exit /b %RC%
