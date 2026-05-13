@echo off
chcp 65001 >nul 2>&1
title NEXUS v3 — Desktop

echo.
echo  ╔══════════════════════════════════════════════════════════════════╗
echo  ║     NEXUS v3 — Agent IA Souverain                                ║
echo  ║     Lancement App Desktop (Tauri)                                ║
echo  ╚══════════════════════════════════════════════════════════════════╝
echo.

set NEXUS_DIR=%~dp0
cd /d "%NEXUS_DIR%"

REM ── Verifier Rust ──
where rustc >nul 2>&1
if errorlevel 1 (
    echo [ATTENTION] Rust n'est pas installe.
    echo Le desktop Tauri necessite Rust.
    echo.
    echo Pour installer Rust : https://rustup.rs
    echo Ou utilisez start_web.bat pour l'app web.
    echo.
    pause
    exit /b 1
)

REM ── Verifier backend ──
echo [INFO] Verification du backend...
python -c "import httpx; r=httpx.get('http://127.0.0.1:8081/health', timeout=2); exit(0)" 2>nul
if errorlevel 1 (
    echo [INFO] Backend non detecte sur :8081.
    echo.
    echo Options :
    echo   1. Lancer le backend dans un autre terminal :
    echo      python -m nexus serve --port 8081
    echo.
    echo   2. Lancer le frontend web seulement :
    echo      cd nexus-web ^&^& npm run dev
    echo      puis ouvrir http://localhost:3000
    echo.
    echo Appui sur une touche pour lancer le desktop quand meme...
    pause >nul
)

REM ── Lancer Tauri ──
echo [INFO] Demarrage de NEXUS Desktop...
echo.
cd /d "%NEXUS_DIR%nexus-desktop"
npm run tauri dev

echo.
echo [INFO] NEXUS Desktop arrete.
pause
