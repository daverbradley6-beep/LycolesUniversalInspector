# Lycoles v32 Windows offline analysis and regression entrypoint.
# Run from repository root: powershell -ExecutionPolicy Bypass -File .\tools\run_v32.ps1
param(
    [string]$Examples = "examples",
    [string]$Build = "build",
    [switch]$SkipTests
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$python = Get-Command py -ErrorAction SilentlyContinue
if (-not $python) { throw "Python launcher (py) not found. Install Python 3.13 and reopen PowerShell." }
if (-not $SkipTests) {
    & py -m unittest discover -s tests -p "test_v3*.py"
    if ($LASTEXITCODE -ne 0) { throw "Regression tests failed. Pipeline stopped." }
}
if (-not (Test-Path $Examples -PathType Container)) {
    New-Item -ItemType Directory -Path $Examples -Force | Out-Null
    Write-Host "Created empty $Examples directory. Add readable .lua/.luau/.txt scripts and rerun."
    exit 0
}
New-Item -ItemType Directory -Path $Build -Force | Out-Null
& py tools/analyze_script_corpus.py $Examples --output (Join-Path $Build "script-corpus.json")
if ($LASTEXITCODE -ne 0) { throw "Corpus analysis failed" }
& py tools/synthesize_workflow_specs.py (Join-Path $Build "script-corpus.json") --output (Join-Path $Build "workflow-specs.json")
if ($LASTEXITCODE -ne 0) { throw "Workflow synthesis failed" }
& py tools/feature_intelligence.py $Examples --output (Join-Path $Build "feature-intelligence.json")
if ($LASTEXITCODE -ne 0) { throw "Feature intelligence failed" }
Write-Host "Finished. Review build/script-corpus.json, build/workflow-specs.json, build/feature-intelligence.json"
Write-Host "These are static findings, not runtime-tested gameplay scripts."
