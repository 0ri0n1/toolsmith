# build_model.ps1 — Build an Ollama model from a Modelfile
# Usage: .\scripts\build_model.ps1 [-ModelName toolsmith] [-ModelFile ollama/Modelfile]

param(
    [string]$ModelName = "toolsmith",
    [string]$ModelFile = "ollama/Modelfile"
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

Write-Host "=== Model Forge: Build ===" -ForegroundColor Cyan
Write-Host "Model:     $ModelName"
Write-Host "Modelfile: $ModelFile"
Write-Host ""

# Resolve path
$mfPath = if ([System.IO.Path]::IsPathRooted($ModelFile)) { $ModelFile } else { Join-Path $root $ModelFile }

if (-not (Test-Path $mfPath)) {
    Write-Host "ERROR: Modelfile not found at $mfPath" -ForegroundColor Red
    exit 1
}

# Check Ollama is running
try {
    $version = Invoke-RestMethod -Uri "http://localhost:11434/api/version" -Method Get
    Write-Host "Ollama version: $($version.version)" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Ollama is not running. Start it first." -ForegroundColor Red
    exit 1
}

# Check if model already exists
$existing = & ollama list 2>&1
if ($existing -match $ModelName) {
    Write-Host "Model '$ModelName' already exists. Rebuilding..." -ForegroundColor Yellow
}

# Build — copy to temp dir to avoid Windows colon-in-path issue with FROM tags
Write-Host "`nBuilding model..." -ForegroundColor Yellow
$tempMf = Join-Path $env:TEMP "modelforge_Modelfile"
Copy-Item $mfPath $tempMf -Force
& ollama create $ModelName -f $tempMf
$buildResult = $LASTEXITCODE
Remove-Item $tempMf -ErrorAction SilentlyContinue
if ($buildResult -ne 0) {
    Write-Host "ERROR: Model build failed." -ForegroundColor Red
    exit 1
}

# Verify
Write-Host "`nVerifying..." -ForegroundColor Yellow
& ollama show $ModelName --modelfile | Select-Object -First 5
Write-Host ""

# Quick test
Write-Host "Running quick generation test..." -ForegroundColor Yellow
$body = @{
    model = $ModelName
    prompt = "Say 'hello' and nothing else."
    stream = $false
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri "http://localhost:11434/api/generate" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 120
    Write-Host "Response: $($response.response.Substring(0, [Math]::Min(200, $response.response.Length)))" -ForegroundColor Green
} catch {
    Write-Host "WARNING: Generation test failed: $_" -ForegroundColor Yellow
    Write-Host "The model was created but may need a moment to initialize." -ForegroundColor Yellow
}

Write-Host "`n=== Build complete: $ModelName ===" -ForegroundColor Cyan
