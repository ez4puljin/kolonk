@echo off
REM Kolonk - deploy to production (see deploy.ps1).
REM ASCII only: PowerShell 5.1 misreads Cyrillic in .bat files.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy.ps1" %*
