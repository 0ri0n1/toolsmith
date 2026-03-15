# test_stack.ps1 — Run smoke tests and evals
# Usage: .\scripts\test_stack.ps1 [-ModelName toolsmith] [-SkipEvals]

param(
    [string]$ModelName = "toolsmith",
    [switch]$SkipEvals
)

$ErrorActionPreference = "Continue"
$root = Split-Path $PSScriptRoot -Parent

Write-Host "=== Model Forge: Test Stack ===" -ForegroundColor Cyan
Write-Host "Model: $ModelName`n"

# Run Python smoke tests
Write-Host "--- Smoke Tests ---" -ForegroundColor Yellow
$testScript = Join-Path $root "tests" "tool_smoke_test.py"
if (Test-Path $testScript) {
    & python $testScript --model $ModelName
    $smokeResult = $LASTEXITCODE
    if ($smokeResult -eq 0) {
        Write-Host "`nSmoke tests: PASSED" -ForegroundColor Green
    } else {
        Write-Host "`nSmoke tests: FAILED (exit code $smokeResult)" -ForegroundColor Red
    }
} else {
    Write-Host "ERROR: Smoke test script not found at $testScript" -ForegroundColor Red
    $smokeResult = 1
}

# Run evals
if (-not $SkipEvals) {
    Write-Host "`n--- Eval Cases ---" -ForegroundColor Yellow
    $evalScript = Join-Path $root "tests" "run_evals.py"
    if (Test-Path $evalScript) {
        & python $evalScript --model $ModelName
        $evalResult = $LASTEXITCODE
        if ($evalResult -eq 0) {
            Write-Host "`nEvals: PASSED" -ForegroundColor Green
        } else {
            Write-Host "`nEvals: SOME FAILURES (exit code $evalResult)" -ForegroundColor Red
        }
    } else {
        Write-Host "Eval runner not found. Run smoke tests only." -ForegroundColor Yellow
        $evalResult = 0
    }
} else {
    Write-Host "`nEvals: SKIPPED" -ForegroundColor Yellow
    $evalResult = 0
}

# Run stack verification
Write-Host "`n--- Stack Verification ---" -ForegroundColor Yellow
& powershell -File "$PSScriptRoot\verify_stack.ps1" -ModelName $ModelName
$verifyResult = $LASTEXITCODE

# Summary
Write-Host "`n=== Test Summary ===" -ForegroundColor Cyan
$overall = 0
if ($smokeResult -eq 0) { Write-Host "  Smoke Tests:    PASS" -ForegroundColor Green } else { Write-Host "  Smoke Tests:    FAIL" -ForegroundColor Red; $overall = 1 }
if ($evalResult -eq 0) { Write-Host "  Evals:          PASS" -ForegroundColor Green } else { Write-Host "  Evals:          FAIL" -ForegroundColor Red; $overall = 1 }
if ($verifyResult -eq 0) { Write-Host "  Verification:   PASS" -ForegroundColor Green } else { Write-Host "  Verification:   FAIL" -ForegroundColor Red; $overall = 1 }

exit $overall
