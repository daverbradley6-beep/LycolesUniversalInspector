# v50 offline contract generator and full regression
param([string]$ReceiverBundle="examples/muscle-legends-receiver-v15-sanitized.json",[string]$Build="build",[string]$Contract="examples/authorized-local-actions-v50.json")
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
& powershell -ExecutionPolicy Bypass -File .\tools\run_v49.ps1 -ReceiverBundle $ReceiverBundle -Build $Build
if ($LASTEXITCODE -ne 0) { throw "v49 pipeline failed" }
& py -m unittest discover -s tests -p "test_v50*.py"
if ($LASTEXITCODE -ne 0) { throw "v50 tests failed" }
& py tools/action_contract_v50.py $Contract --output (Join-Path $Build "authorized-actions-v50.luau")
if ($LASTEXITCODE -ne 0) { throw "v50 contract generation failed" }
Write-Host "v50 ready: build/authorized-actions-v50.luau (paths in example contract must be verified in-game)"
