@echo off
chcp 65001 >nul
title NEXUS Installer

echo ╔══════════════════════════════════════╗
echo ║     NEXUS — One-Click Installer      ║
echo ╚══════════════════════════════════════╝
echo.

REM ── Check Python ──
python --version >nul 2>&1
if errorlevel 1 (
    echo Python introuvable. Telechargement...
    start https://www.python.org/downloads/
    echo Installez Python 3.11+ avec "Add Python to PATH" coche.
    pause
    exit /b 1
)
echo Python OK

REM ── Venv + deps ──
if not exist "venv" python -m venv venv
call venv\Scripts\activate.bat
python -m pip install -q -r requirements.txt
python -m pip install -q -e .
echo Dependances Python OK

REM ── Frontend ──
cd nexus-web
call npm install --no-fund --no-audit --silent
cd ..
echo Frontend OK

REM ── .env ──
if not exist ".env" (
    copy .env.example .env >nul
    echo .env cree. Configure tes cles API.
)

REM ── Shortcut ──
powershell -Command "$WS=New-Object -ComObject WScript.Shell; $SC=$WS.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\NEXUS.lnk'); $SC.TargetPath='%~dp0start_web.bat'; $SC.Save()" >nul 2>&1

echo.
echo ╔══════════════════════════════════════╗
echo ║   NEXUS pret !                       ║
echo ║                                      ║
echo ║   Lance start_web.bat pour demarrer  ║
echo ╚══════════════════════════════════════╝
echo.
pause
