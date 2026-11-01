# v45 evidence compiler
param([string]$ReceiverBundle="examples/muscle-legends-receiver-v15-sanitized.json",[string]$Build="build",[string]$Receipt="")
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
& powershell -ExecutionPolicy Bypass -File .\tools\run_v44.ps1 -ReceiverBundle $ReceiverBundle -Build $Build -Receipt $Receipt
if ($LASTEXITCODE -ne 0) { throw "v44 pipeline failed" }
& py -m unittest discover -s tests -p "test_v45*.py"
if ($LASTEXITCODE -ne 0) { throw "v45 tests failed" }
$report=Join-Path $Build "adaptive-report-v44.json"
if ($Receipt -and (Test-Path $report)) {
 & py tools/evidence_compiler_v45.py (Join-Path $Build "generation-manifest-v42.json") $report --output (Join-Path $Build "evidence-contracts-v45.json")
 if ($LASTEXITCODE -ne 0) { throw "v45 compilation failed" }
} else {
 Write-Host "v45: provide -Receipt with a v44 receipt to compile contracts."
}
