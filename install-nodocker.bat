@echo off
REM ===========================================================
REM  Kolonk - Docker demjdegggui PC deer suulgah
REM  Ene faylyg 2 udaa darahad shaardlagatai buh program suugaad
REM  computer asah bolgond sistem ooroo asdag bolno.
REM
REM  Control flow-d zovhon ASCII ashiglana: cmd.exe kirill
REM  useg aguulsan .bat faylyg codepage-ees hamaaran buruu
REM  unshdag. Kirill medeelliig PowerShell skript haruulna.
REM ===========================================================
chcp 65001 >nul 2>&1
title Kolonk POS - install (no docker)
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-nodocker.ps1"

exit /b %errorlevel%
