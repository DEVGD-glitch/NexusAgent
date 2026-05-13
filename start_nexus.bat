@echo off
chcp 65001 >nul 2>&1
title NEXUS v3 — Backend

echo.
echo  ╔══════════════════════════════════════════════════════════════════╗
echo  ║     NEXUS v3 — Agent IA Souverain                                ║
echo  ║     Mode Backend uniquement (API)                                ║
echo  ╚══════════════════════════════════════════════════════════════════╝
echo.

set NEXUS_DIR=%~dp0
cd /d "%NEXUS_DIR%"

if not exist "%NEXUS_DIR%venv\Scripts\python.exe" (
    echo [INFO] Environnement virtuel introuvable.
    echo [INFO] Lancement de l'installation...
    call "%NEXUS_DIR%install_build.bat" --no-build
    if errorlevel 1 (
        echo [ECHEC] L'installation a echoue.
        pause
        exit /b 1
    )
)

echo [INFO] Demarrage de l'API NEXUS sur http://localhost:8081
echo [INFO] Documentation : http://localhost:8081/docs
echo.
echo [INFO] Pour le frontend web, utilisez start_web.bat
echo [INFO] Pour le desktop, utilisez : cd nexus-desktop ^&^& npm run tauri dev
echo.

call "%NEXUS_DIR%venv\Scripts\activate.bat"
python -m nexus serve --port 8081

if errorlevel 1 (
    echo [ECHEC] Le backend s'est arrete avec une erreur.
    pause
)
