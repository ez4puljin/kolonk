@echo off
REM ===========================================================
REM  Kolonk - Shatahuun tugeeh stantsyn POS sistem
REM  Ene faylyg 2 udaa darahad butne sistem asna.
REM
REM  Control flow-d zovhon ASCII ashiglana: cmd.exe kirill
REM  useg aguulsan .bat faylyg codepage-ees hamaaran buruu
REM  unshdag. Kirill medeelliig PowerShell skript haruulna.
REM ===========================================================
chcp 65001 >nul 2>&1
title Kolonk POS
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-dev.ps1" -Seed -Open -Quiet

if errorlevel 1 (
    echo.
    echo [!] Aldaa garlaa. Deerh medeelliig unshina uu.
    echo     Log: "%~dp0logs"
    echo.
    pause
    exit /b 1
)

REM Amjilttai: tsonh 5 sekundiin daraa aani haagdana.
ping -n 6 127.0.0.1 >nul 2>&1
exit /b 0
