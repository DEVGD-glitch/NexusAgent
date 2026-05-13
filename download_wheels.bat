@echo off
chcp 65001 >nul
title NEXUS Download Wheels

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║     NEXUS — Telechargement hors-ligne                       ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python introuvable. Installez Python 3.11+.
    pause
    exit /b 1
)

if not exist venv (
    python -m venv venv
)
call venv\Scripts\activate.bat
python -m pip install --upgrade pip wheel --quiet

if not exist wheels mkdir wheels

echo Telechargement des dependances pour installation hors-ligne...
echo.

pip download -r requirements.txt -d wheels --platform win_amd64 --python-version 312 --only-binary=:all: 2>nul
pip download -r requirements.txt -d wheels --platform win_amd64 --python-version 311 --only-binary=:all: 2>nul
pip download -r requirements.txt -d wheels 2>nul

echo.
echo Wheels telecharges dans wheels/
echo Utilisez : install_build.bat (detecte automatiquement wheels/)
echo.
pause
