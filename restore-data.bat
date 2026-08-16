@echo off
REM ===========================================================
REM  Kolonk - zeeverlesen ugugdliig shine PC deer sergeeh wrapper.
REM  PowerShell-iin ExecutionPolicy haalttai PC deer ch ajillana.
REM  Argument-uud shuud damjina.
REM ===========================================================
chcp 65001 >nul 2>&1
title Kolonk restore
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0restore-data.ps1" %*
set "RC=%errorlevel%"

echo.
if %RC% neq 0 (
    echo [!] Aldaa garlaa. Deerh medeelliig unshina uu.
) else (
    echo [OK] Duuslaa.
)
pause
exit /b %RC%
