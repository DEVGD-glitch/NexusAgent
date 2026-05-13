@echo off
chcp 65001 >nul
title NEXUS Verification

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║     NEXUS — Verification de l'installation                  ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

set PASS=0
set FAIL=0
call "%CD%\venv\Scripts\activate.bat" 2>nul

echo [1/6] Python...
python --version 2>nul && (echo     OK & set /a PASS+=1) || (echo     FAIL: Python introuvable & set /a FAIL+=1)

echo [2/6] Environnement virtuel...
if exist "%CD%\venv\Scripts\activate.bat" (echo     OK & set /a PASS+=1) else (echo     FAIL: venv non trouve & set /a FAIL+=1)

echo [3/6] Module NEXUS...
python -c "import nexus; print('     OK v' + nexus.__version__)" 2>nul && set /a PASS+=1 || (echo     FAIL: nexus import echoue & set /a FAIL+=1)

echo [4/6] FastAPI...
python -c "import fastapi; print('     OK')" 2>nul && set /a PASS+=1 || (echo     FAIL: FastAPI manquant & set /a FAIL+=1)

echo [5/6] Configuration (.env)...
if exist "%CD%\.env" (echo     OK & set /a PASS+=1) else (echo     ATTENTION: .env manquant. Copiez .env.example & set /a PASS+=1)

echo [6/6] Frontend (nexus-web)...
if exist "%CD%\nexus-web\node_modules" (echo     OK & set /a PASS+=1) else (echo     ATTENTION: npm pas installe. Lancez install.bat & set /a PASS+=1)

echo.
echo ═══════════════════════════════════════════════════════════════
echo   Resultats : %PASS% sur 6
echo.
echo   Pour lancer : start_web.bat
echo   Pour configurer : editez .env
echo ═══════════════════════════════════════════════════════════════
echo.
pause
