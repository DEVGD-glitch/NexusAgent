#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Deploy NEXUS — Push to GitHub
.DESCRIPTION
    Automates git add/commit/push
#>

$ErrorActionPreference = "Stop"
param([string]$Message = "")

$NEXUS_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $NEXUS_DIR

$status = git status --porcelain
if (-not $status) {
    Write-Host "Rien a commit — depot propre." -ForegroundColor Green
    exit 0
}

if (-not $Message) {
    $count = ($status | Measure-Object -Line).Lines
    $Message = "chore: update ($count files)"
}

git add -A
git commit -m $Message
git push

Write-Host "Pushed: $Message" -ForegroundColor Green
