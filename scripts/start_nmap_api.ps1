# start_nmap_api.ps1 - Start the nmap tool API for Open WebUI
# Usage: .\scripts\start_nmap_api.ps1

$root = Split-Path $PSScriptRoot -Parent

Write-Host "=== Starting Nmap Tool API ===" -ForegroundColor Cyan

# Check Docker
try {
    docker exec kali-mcp-pentest nmap --version 2>&1 | Select-Object -First 1
} catch {
    Write-Host "ERROR: Kali container not running" -ForegroundColor Red
    exit 1
}

# Check if port 8801 is already in use
$existing = Get-NetTCPConnection -LocalPort 8801 -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Port 8801 already in use. API may already be running." -ForegroundColor Yellow
    Write-Host "Health: $(Invoke-RestMethod http://localhost:8801/health)" -ForegroundColor Green
    exit 0
}

# Start the API
Write-Host "Starting on http://localhost:8801 ..." -ForegroundColor Yellow
Write-Host "OpenAPI spec: http://localhost:8801/openapi.json"
Write-Host "Swagger UI:   http://localhost:8801/docs"
Write-Host ""
Write-Host "Register in Open WebUI:" -ForegroundColor Cyan
Write-Host "  1. Go to http://localhost:3010"
Write-Host "  2. Admin Panel > Settings > Tools"
Write-Host "  3. Add Connection > URL: http://host.docker.internal:8801"
Write-Host "  4. Select kali-nmap model in chat"
Write-Host "  5. Click the + next to the message box > enable nmap_scan tool"
Write-Host ""

Start-Process -NoNewWindow python -ArgumentList "$root\tool-transport\nmap-api.py"
