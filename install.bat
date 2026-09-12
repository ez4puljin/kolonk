@echo off
REM ===========================================================
REM  Kolonk - shine PC deer suulgah NEGDSEN wrapper.
REM
REM  Ehend "Docker ashiglah uu?" gej asuuna. "Ugui" gevel Docker-toi
REM  holbootoi yuu ch hiihgui (Python, Node, PostgreSQL shuud suuna).
REM  "Tiim" gevel Python/Node/PostgreSQL yuu ch suulgahgui (bugd
REM  konteinert).
REM
REM  Hereglee (argument-uud shuud damjina):
REM    install.bat              (asuuna)
REM    install.bat -DryRun      (zovhon shalgana, yuu ch oorchlohgui)
REM    install.bat -Docker      (asuulgui Docker gorim)
REM    install.bat -NoDocker    (asuulgui Docker-gui gorim)
REM    install.bat -SkipStart   (tugsguld sistemiig asaahgui)
REM
REM  Shine PC deer PowerShell-iin ExecutionPolicy .ps1 faylyg
REM  huriglodog ("running scripts is disabled...") tul ene wrapper
REM  Bypass-aar install.ps1-iig ajilluulna.
REM
REM  Control flow-d zovhon ASCII ashiglana: cmd.exe kirill
REM  useg aguulsan .bat faylyg codepage-ees hamaaran buruu
REM  unshdag. Kirill medeelliig PowerShell skript haruulna.
REM ===========================================================
chcp 65001 >nul 2>&1
title Kolonk POS - install
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*

if errorlevel 1 (
    echo.
    echo [!] Aldaa garlaa. Deerh medeelliig unshina uu.
    echo.
    pause
    exit /b 1
)
exit /b 0
