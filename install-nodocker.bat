@echo off
REM ===========================================================
REM  Kolonk - huuchin ner. install.bat -NoDocker ruu damjuulna.
REM
REM  Suulgalt negdsen install.bat-d negdsen: ene fayl zovhon huuchin
REM  holboos, dadal zurshliig hadgalahyn tuld uldsen.
REM  Control flow-d zovhon ASCII ashiglana.
REM ===========================================================
cd /d "%~dp0"
call "%~dp0install.bat" -NoDocker %*
exit /b %errorlevel%
