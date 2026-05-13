@echo off
chcp 65001 >nul
title NEXUS Build

echo.
echo  ╔══════════════════════════════════════════════════════════════╗
echo  ║     NEXUS — Build Frontend                                  ║
echo  ╚══════════════════════════════════════════════════════════════╝
echo.

set NEXUS_DIR=%~dp0

if not exist "%NEXUS_DIR%nexus-web\node_modules" (
    echo  [!] node_modules non trouve. Lancez d'abord install.bat
    pause
    exit /b 1
)

echo  [1/2] Build du frontend Next.js...
cd /d "%NEXUS_DIR%nexus-web"
call npm run build
if errorlevel 1 (
    echo  [ECHEC] Build frontend echoue.
    pause
    exit /b 1
)
echo  OK Frontend build termine
echo.

echo  [2/2] Build termine.
echo.
echo  Les fichiers sont dans nexus-web/.next/
echo  Lancez start_web.bat pour demarrer.
echo.

pause
