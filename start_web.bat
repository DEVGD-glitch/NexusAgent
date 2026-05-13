@echo off
chcp 65001 >nul 2>&1
title NEXUS v3 — App Web

echo.
echo  ╔══════════════════════════════════════════════════════════════════╗
echo  ║     NEXUS v3 — Agent IA Souverain                                ║
echo  ║     Agent Command Center + Code Workspace + Avatar VRM          ║
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

where node >nul 2>&1
if errorlevel 1 (
    echo [ECHEC] Node.js n'est pas installe.
    pause
    exit /b 1
)
for /f "tokens=2 delims=v." %%v in ('node --version') do set NODE_MAJOR=%%v
echo [OK] Node.js v%NODE_MAJOR%

if not exist "%NEXUS_DIR%nexus-web\node_modules" (
    echo [INFO] Installation des dependances npm...
    cd /d "%NEXUS_DIR%nexus-web"
    npm install
    if errorlevel 1 (
        echo [ECHEC] npm install a echoue.
        pause
        exit /b 1
    )
    cd /d "%NEXUS_DIR%"
)

echo [INFO] Lancement du backend (port 8081)...
start "NEXUS-Backend" cmd /k "cd /d "%NEXUS_DIR%" && call venv\Scripts\activate.bat && python -m nexus serve --port 8081"

timeout /t 4 /nobreak >nul

echo [INFO] Lancement du frontend (port 3000)...
start "NEXUS-Frontend" cmd /k "cd /d "%NEXUS_DIR%nexus-web" && npm run dev"

timeout /t 5 /nobreak >nul

echo [INFO] Ouverture du navigateur...
start http://localhost:3000

echo.
echo  ╔══════════════════════════════════════════════════════════════════╗
echo  ║  NEXUS v3 est en cours d'execution !                             ║
echo  ║                                                                  ║
echo  ║  Frontend : http://localhost:3000                                  ║
echo  ║  Backend  : http://localhost:8081/docs                             ║
echo  ║                                                                  ║
echo  ║  Fermez les deux terminaux pour arreter.                          ║
echo  ╚══════════════════════════════════════════════════════════════════╝
echo.
pause >nul
