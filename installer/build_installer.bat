@echo off
REM ═══════════════════════════════════════════════════════════════
REM NEXUS — Build Windows Installer
REM Creates a professional .exe installer using NSIS
REM Prerequisites: NSIS (https://nsis.sourceforge.io/Download)
REM ═══════════════════════════════════════════════════════════════

echo.
echo Building NEXUS installer...
echo.

set NEXUS_DIR=%~dp0..
set INSTALLER_DIR=%~dp0

makensis /VERSION >nul 2>&1
if errorlevel 1 (
    echo [ERROR] NSIS is not installed.
    echo Download from: https://nsis.sourceforge.io/Download
    pause
    exit /b 1
)

makensis /DVERSION=1.0.0 "%INSTALLER_DIR%setup.nsi"

echo.
echo [OK] Installer created: %INSTALLER_DIR%NEXUS-Setup-1.0.0.exe
echo.
pause
