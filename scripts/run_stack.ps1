# run_stack.ps1 — Start the Model Forge stack
# Usage: .\scripts\run_stack.ps1 [-ModelName toolsmith]

param(
    [string]$ModelName = "toolsmith"
)

$ErrorActionPreference = "Continue"
$root = Split-Path $PSScriptRoot -Parent

Write-Host "=== Model Forge: Run Stack ===" -ForegroundColor Cyan
Write-Host ""

# 1. Check Ollama
Write-Host "1. Checking Ollama..." -ForegroundColor Yellow
try {
    $version = Invoke-RestMethod -Uri "http://localhost:11434/api/version" -Method Get
    Write-Host "   Ollama v$($version.version) running" -ForegroundColor Green
} catch {
    Write-Host "   Ollama not running. Starting..." -ForegroundColor Yellow
    Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3
    try {
        $version = Invoke-RestMethod -Uri "http://localhost:11434/api/version" -Method Get
        Write-Host "   Ollama v$($version.version) started" -ForegroundColor Green
    } catch {
        Write-Host "   ERROR: Could not start Ollama" -ForegroundColor Red
        exit 1
    }
}

# 2. Check model exists
Write-Host "`n2. Checking model '$ModelName'..." -ForegroundColor Yellow
$models = & ollama list 2>&1
if ($models -match $ModelName) {
    Write-Host "   Model found" -ForegroundColor Green
} else {
    Write-Host "   Model not found. Building..." -ForegroundColor Yellow
    & powershell -File "$PSScriptRoot\build_model.ps1" -ModelName $ModelName
}

# 3. Preload model
Write-Host "`n3. Preloading model..." -ForegroundColor Yellow
$body = @{ model = $ModelName } | ConvertTo-Json
try {
    Invoke-RestMethod -Uri "http://localhost:11434/api/generate" -Method Post -Body (@{ model = $ModelName; prompt = ""; keep_alive = "10m" } | ConvertTo-Json) -ContentType "application/json" -TimeoutSec 120 | Out-Null
    Write-Host "   Model loaded into memory" -ForegroundColor Green
} catch {
    Write-Host "   WARNING: Preload may have timed out, model will load on first use" -ForegroundColor Yellow
}

# 4. Check Open WebUI
Write-Host "`n4. Checking Open WebUI..." -ForegroundColor Yellow
try {
    $owui = Invoke-WebRequest -Uri "http://localhost:3010/" -Method Get -MaximumRedirection 0 -ErrorAction SilentlyContinue
    Write-Host "   Open WebUI available at http://localhost:3010" -ForegroundColor Green
} catch {
    if ($_.Exception.Response.StatusCode -eq 307 -or $_.Exception.Response.StatusCode -eq 302) {
        Write-Host "   Open WebUI available at http://localhost:3010 (redirects to login)" -ForegroundColor Green
    } else {
        Write-Host "   Open WebUI not reachable at http://localhost:3010" -ForegroundColor Yellow
    }
}

# 5. Check MCPO
Write-Host "`n5. Checking MCPO bridge..." -ForegroundColor Yellow
try {
    $mcpo = Invoke-RestMethod -Uri "http://localhost:8800/openapi.json" -Method Get
    $paths = ($mcpo.paths | Get-Member -MemberType NoteProperty).Count
    Write-Host "   MCPO running at http://localhost:8800 ($paths endpoints)" -ForegroundColor Green
} catch {
    Write-Host "   MCPO not reachable at http://localhost:8800" -ForegroundColor Yellow
    Write-Host "   Tools will not be available until MCPO is configured and started" -ForegroundColor Yellow
}

# Summary
Write-Host "`n=== Stack Status ===" -ForegroundColor Cyan
Write-Host "Ollama API:   http://localhost:11434"
Write-Host "Model:        $ModelName"
Write-Host "Open WebUI:   http://localhost:3010"
Write-Host "MCPO Bridge:  http://localhost:8800"
Write-Host ""
Write-Host "To use: Open http://localhost:3010 and select '$ModelName' from the model dropdown."
Write-Host "To test: .\scripts\test_stack.ps1 -ModelName $ModelName"
