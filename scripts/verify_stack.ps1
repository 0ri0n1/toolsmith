# verify_stack.ps1 - Model Forge Stack Verification
# Run this before declaring any build complete.
# Exit code 0 = all checks pass. Non-zero = incomplete.

param(
    [string]$ModelName = "toolsmith",
    [switch]$Verbose
)

$ErrorActionPreference = "Continue"
$failures = @()
$passes = @()
$root = Join-Path $PSScriptRoot ".."

function Resolve($relative) {
    return Join-Path $root $relative
}

function Check($name, $condition, $detail) {
    if ($condition) {
        $script:passes += "$name"
        if ($Verbose) { Write-Host "  PASS: $name" -ForegroundColor Green }
    } else {
        $script:failures += ("$name -- $detail")
        Write-Host ("  FAIL: $name -- $detail") -ForegroundColor Red
    }
}

Write-Host "`n=== Model Forge Stack Verification ===" -ForegroundColor Cyan
Write-Host "Model: $ModelName`n"

# 1. Required files exist
Write-Host "Checking required files..." -ForegroundColor Yellow
$requiredFiles = @(
    ".claude/agents/model-forge.md",
    ".claude/settings.json",
    "ollama/Modelfile",
    "scripts/build_model.ps1",
    "scripts/run_stack.ps1",
    "scripts/test_stack.ps1",
    "scripts/verify_stack.ps1",
    "tests/tool_smoke_test.py",
    "evals/tool_use_cases.json",
    "docs/architecture.md",
    "docs/runtime_notes.md",
    "docs/how_to_use_model_forge.md"
)
foreach ($f in $requiredFiles) {
    $path = Resolve $f
    Check "File: $f" (Test-Path $path) "File not found"
}

# 2. Modelfile coherence
Write-Host "`nChecking Modelfile..." -ForegroundColor Yellow
$modelfilePath = Resolve "ollama\Modelfile"
if (Test-Path $modelfilePath) {
    $content = Get-Content $modelfilePath -Raw
    Check "Modelfile has FROM" ($content -match "(?m)^FROM\s") "Missing FROM directive"
    Check "Modelfile has SYSTEM" ($content -match "SYSTEM") "Missing SYSTEM prompt"
    Check "Modelfile has TEMPLATE" ($content -match "TEMPLATE") "Missing TEMPLATE"
    Check "Modelfile has stop tokens" ($content -match "PARAMETER stop") "Missing stop tokens"
    Check "Modelfile has num_ctx" ($content -match "num_ctx") "Missing num_ctx parameter"
} else {
    $failures += "Modelfile -- File missing entirely"
}

# 3. Tool transport config exists
Write-Host "`nChecking tool transport..." -ForegroundColor Yellow
$mcpoConfig = Resolve "tool-transport\mcpo-config.json"
Check "MCPO config exists" (Test-Path $mcpoConfig) "tool-transport/mcpo-config.json not found"

# 4. Scripts are non-empty
Write-Host "`nChecking scripts..." -ForegroundColor Yellow
foreach ($s in @("build_model.ps1", "run_stack.ps1", "test_stack.ps1")) {
    $spath = Join-Path $PSScriptRoot $s
    if (Test-Path $spath) {
        $size = (Get-Item $spath).Length
        Check "Script $s" ($size -gt 100) ("Script is empty or too small (" + $size + " bytes)")
    } else {
        $failures += ("Script $s -- not found")
    }
}

# 5. Smoke tests exist and are runnable
Write-Host "`nChecking tests..." -ForegroundColor Yellow
$testFile = Resolve "tests\tool_smoke_test.py"
if (Test-Path $testFile) {
    $tc = Get-Content $testFile -Raw
    Check "Smoke test has test functions" ($tc -match "def test_") "No test functions found"
    Check "Smoke test checks model" ($tc -match "model") "No model reference found"
} else {
    $failures += "Smoke test -- file not found"
}

# 6. Eval cases exist
Write-Host "`nChecking evals..." -ForegroundColor Yellow
$evalFile = Resolve "evals\tool_use_cases.json"
if (Test-Path $evalFile) {
    try {
        $evalData = Get-Content $evalFile -Raw | ConvertFrom-Json
        $count = if ($evalData.test_cases) { $evalData.test_cases.Count } else { 0 }
        Check "Eval cases exist" ($count -gt 0) "No test cases in file"
        Check "Eval cases >= 5" ($count -ge 5) ("Only " + $count + " cases (need at least 5)")
    } catch {
        $failures += ("Eval cases -- Invalid JSON: " + $_)
    }
} else {
    $failures += "Eval cases -- file not found"
}

# 7. Check if model exists in Ollama
Write-Host "`nChecking Ollama..." -ForegroundColor Yellow
$ollamaList = & ollama list 2>&1
Check "Ollama is running" ($LASTEXITCODE -eq 0) "Cannot reach Ollama"
if ($ollamaList -is [string]) {
    Check "Model '$ModelName' exists" ($ollamaList -match $ModelName) "Model not found in ollama list"
} else {
    $joined = $ollamaList -join "`n"
    Check "Model '$ModelName' exists" ($joined -match $ModelName) "Model not found in ollama list"
}

# Summary
Write-Host "`n=== Summary ===" -ForegroundColor Cyan
Write-Host "Passed: $($passes.Count)" -ForegroundColor Green
Write-Host "Failed: $($failures.Count)" -ForegroundColor $(if ($failures.Count -gt 0) { "Red" } else { "Green" })

if ($failures.Count -gt 0) {
    Write-Host "`nFailures:" -ForegroundColor Red
    foreach ($f in $failures) {
        Write-Host "  - $f" -ForegroundColor Red
    }
    Write-Host "`nStack verification INCOMPLETE. Fix failures before declaring success." -ForegroundColor Red
    exit 1
} else {
    Write-Host "`nStack verification PASSED." -ForegroundColor Green
    exit 0
}
