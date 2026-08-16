@echo off
REM ===========================================================
REM  Kolonk - Docker gorimoor asaah wrapper.
REM
REM  Shine PC deer PowerShell-iin ExecutionPolicy .ps1 faylyg
REM  huriglodog ("running scripts is disabled..." aldaa) tul
REM  ene wrapper Bypass-aar start-docker.ps1-iig ajilluulna.
REM
REM  Hereglee (argument-uud shuud damjina):
REM    start-docker.bat            (dev: API 8000)
REM    start-docker.bat -Prod      (buten sistem, http://localhost)
REM    start-docker.bat -Down      (zogsooh)
REM    start-docker.bat -Reset     (DB volume ustgaj tsever ehleh)
REM
REM  Control flow-d zovhon ASCII ashiglana: cmd.exe kirill
REM  useg aguulsan .bat faylyg codepage-ees hamaaran buruu
REM  unshdag. Kirill medeelliig PowerShell skript haruulna.
REM ===========================================================
chcp 65001 >nul 2>&1
title Kolonk Docker
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-docker.ps1" %*

if errorlevel 1 (
    echo.
    echo [!] Aldaa garlaa. Deerh medeelliig unshina uu.
    echo.
    pause
    exit /b 1
)

REM Amjilttai: tsonh 5 sekundiin daraa aani haagdana.
ping -n 6 127.0.0.1 >nul 2>&1
exit /b 0
