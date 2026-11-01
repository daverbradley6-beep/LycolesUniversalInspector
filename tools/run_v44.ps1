# Lycoles v44: full regression and adaptive snapshot pipeline
param([string]$ReceiverBundle="examples/muscle-legends-receiver-v15-sanitized.json",[string]$Build="build",[string]$Receipt="")
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
& powershell -ExecutionPolicy Bypass -File .\tools\run_v43.ps1 -ReceiverBundle $ReceiverBundle -Build $Build
if ($LASTEXITCODE -ne 0) { throw "v43 pipeline failed" }
& py -m unittest discover -s tests -p "test_v44*.py"
if ($LASTEXITCODE -ne 0) { throw "v44 tests failed" }
$manifest=Join-Path $Build "generation-manifest-v42.json"
$script=Join-Path $Build "adaptive-probe-v44.luau"
if ($Receipt) {
 & py tools/adaptive_probe_v44.py $manifest --luau $script --receipt $Receipt --report (Join-Path $Build "adaptive-report-v44.json")
} else {
 & py tools/adaptive_probe_v44.py $manifest --luau $script
}
if ($LASTEXITCODE -ne 0) { throw "v44 probe generation or analysis failed" }
Write-Host "v44 ready: run build/adaptive-probe-v44.luau inside the matching Roblox place."
