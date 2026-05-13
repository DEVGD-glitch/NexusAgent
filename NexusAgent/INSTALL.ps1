#!/usr/bin/env pwsh
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$NEXUS_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "╔══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     NEXUS — One-Click Installer      ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── Python ──
try {
    $pyVersion = python --version 2>&1
    Write-Host "Python : $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "Python introuvable. Telechargement..." -ForegroundColor Yellow
    winget install Python.Python.3.12 2>$null
    refreshenv
}

# ── Node.js ──
try {
    $nodeVersion = node --version
    Write-Host "Node.js : $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "Node.js introuvable. Telechargement..." -ForegroundColor Yellow
    winget install OpenJS.NodeJS.LTS 2>$null
    refreshenv
}

# ── Venv + deps ──
Write-Host "`nInstallation des dependances Python..." -ForegroundColor Cyan
if (-not (Test-Path "$NEXUS_DIR\venv")) {
    python -m venv "$NEXUS_DIR\venv"
}
& "$NEXUS_DIR\venv\Scripts\pip" install -q -r "$NEXUS_DIR\requirements.txt" 2>&1 | Out-Null
& "$NEXUS_DIR\venv\Scripts\pip" install -q -e "$NEXUS_DIR" 2>&1 | Out-Null

# ── Frontend ──
Write-Host "Installation du frontend..." -ForegroundColor Cyan
Set-Location "$NEXUS_DIR\nexus-web"
npm install --no-fund --no-audit --silent 2>&1 | Out-Null
Set-Location $NEXUS_DIR

# ── .env ──
if (-not (Test-Path "$NEXUS_DIR\.env")) {
    Copy-Item "$NEXUS_DIR\.env.example" "$NEXUS_DIR\.env"
    Write-Host ".env cree. Configure tes cles API." -ForegroundColor Green
}

Write-Host ""
Write-Host "╔══════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║   NEXUS pret !                       ║" -ForegroundColor Green
Write-Host "║                                      ║" -ForegroundColor Green
Write-Host "║   Lance start_web.bat pour demarrer  ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Green
