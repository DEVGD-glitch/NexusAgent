@echo off
chcp 65001 >nul
title NEXUS Installation

echo.
echo  ╔══════════════════════════════════════════════════════════════════╗
echo  ║     NEXUS v3 — Agent IA Souverain                                ║
echo  ║     Installation                                                ║
echo  ╚══════════════════════════════════════════════════════════════════╝
echo.

set NEXUS_DIR=%~dp0
set ERROR_COUNT=0

REM ── Options ──
set BUILD_FRONTEND=1
if "%1"=="--no-build" set BUILD_FRONTEND=0
if "%1"=="--skip-build" set BUILD_FRONTEND=0

REM ═══════════════════════════════════════════════════════════════════
REM ÉTAPE 1 : Vérifier Python 3.11+
REM ═══════════════════════════════════════════════════════════════════
echo  [1/6] Verification de Python 3.11+...

python --version >nul 2>&1
if errorlevel 1 (
    echo     X Python n'est PAS installe !
    echo     Telechargez Python 3.11+ depuis : https://www.python.org/downloads/
    echo     Pendant l'installation, COCHEZ "Add Python to PATH"
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo     Python %PYVER% detecte

python -c "import sys; v=sys.version_info; exit(0 if v >= (3,11) else 1)" 2>nul
if errorlevel 1 (
    echo     X Python 3.11+ requis. Vous avez %PYVER%
    pause
    exit /b 1
)
echo     OK
echo.

REM ═══════════════════════════════════════════════════════════════════
REM ÉTAPE 2 : Environnement virtuel
REM ═══════════════════════════════════════════════════════════════════
echo  [2/6] Creation de l'environnement virtuel...

if exist "%NEXUS_DIR%venv\Scripts\activate.bat" (
    echo     Environnement existant, reutilisation...
) else (
    python -m venv "%NEXUS_DIR%venv"
    if errorlevel 1 (
        echo     X Impossible de creer l'environnement virtuel
        pause
        exit /b 1
    )
    echo     OK Environnement cree dans venv\
)
call "%NEXUS_DIR%venv\Scripts\activate.bat"
echo.

REM ═══════════════════════════════════════════════════════════════════
REM ÉTAPE 3 : Mise à jour pip
REM ═══════════════════════════════════════════════════════════════════
echo  [3/6] Mise a jour de pip...
python -m pip install --upgrade pip wheel setuptools --quiet 2>nul
echo     OK
echo.

REM ═══════════════════════════════════════════════════════════════════
REM ÉTAPE 4 : Installation des dépendances Python
REM ═══════════════════════════════════════════════════════════════════
echo  [4/6] Installation des dependances Python...
echo     Cela peut prendre 2-5 minutes...

pip install -r "%NEXUS_DIR%requirements.txt"
if errorlevel 1 (
    echo     X Certaines dependances ont echoue.
    set /a ERROR_COUNT+=1
) else (
    echo     OK Toutes les dependances installees
)
pip install -e "%NEXUS_DIR%." --quiet 2>nul
echo.

REM ═══════════════════════════════════════════════════════════════════
REM ÉTAPE 5 : Configuration .env
REM ═══════════════════════════════════════════════════════════════════
echo  [5/6] Configuration...

if not exist "%NEXUS_DIR%.env" (
    copy "%NEXUS_DIR%.env.example" "%NEXUS_DIR%.env" >nul
    echo     Fichier .env cree.
    echo.
    echo     *** IMPORTANT ***
    echo     Ouvrez .env avec le Bloc-notes et ajoutez votre cle API :
    echo     Exemple : GOOGLE_API_KEY=votre_cle_ici
    echo.
    echo     Pas de cle ? Installez Ollama (gratuit) :
    echo     https://ollama.com/download
    echo.
) else (
    echo     .env deja existant, parametres conserves.
)
echo.

REM ═══════════════════════════════════════════════════════════════════
REM ÉTAPE 6 : Frontend Node.js
REM ═══════════════════════════════════════════════════════════════════
if "%BUILD_FRONTEND%"=="1" (
    echo  [6/6] Installation du frontend web...

    cd /d "%NEXUS_DIR%nexus-web"
    if not exist "node_modules" (
        call npm install --no-fund --no-audit
        if errorlevel 1 (
            echo     X npm install a echoue
            set /a ERROR_COUNT+=1
        ) else (
            echo     OK Dependances npm installees
        )
    ) else (
        echo     node_modules existant, ok.
    )
    cd /d "%NEXUS_DIR%"
) else (
    echo  [6/6] Frontend ignore (--no-build)
)
echo.

REM ═══════════════════════════════════════════════════════════════════
REM RÉSUMÉ
REM ═══════════════════════════════════════════════════════════════════
echo.
echo  ═══════════════════════════════════════════════════════════════
echo.
echo   NEXUS v3 est installe et pret !
echo.
if "%BUILD_FRONTEND%"=="1" (
    echo   Pour lancer l'app web (recommande) :
    echo     start_web.bat
    echo.
    echo   Pour lancer l'app desktop (Tauri) :
    echo     start_desktop.bat
    echo.
    echo   Pour lancer l'API seulement :
    echo     start_nexus.bat
    echo.
)
echo   Pour configurer vos cles API :
echo     Ouvrez .env avec le Bloc-notes
echo.

if %ERROR_COUNT% gtr 0 (
    echo  [!] %ERROR_COUNT% avertissement(s) - certaines fonctionnalites
    echo      peuvent etre limitees.
    echo.
)

pause
