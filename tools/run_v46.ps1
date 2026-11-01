# v46 automatic sampling pipeline
param([string]$ReceiverBundle="examples/muscle-legends-receiver-v15-sanitized.json",[string]$Build="build",[string]$Console="")
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
& powershell -ExecutionPolicy Bypass -File .\tools\run_v45.ps1 -ReceiverBundle $ReceiverBundle -Build $Build
if ($LASTEXITCODE -ne 0) { throw "v45 pipeline failed" }
& py -m unittest discover -s tests -p "test_v46*.py"
if ($LASTEXITCODE -ne 0) { throw "v46 tests failed" }
$args46 = @("tools/auto_pipeline_v46.py", (Join-Path $Build "generation-manifest-v42.json"), "--output", $Build)
if (-not [string]::IsNullOrWhiteSpace($Console)) { $args46 += @("--console", $Console) }
& py @args46
if ($LASTEXITCODE -ne 0) { throw "v46 processing failed" }
Write-Host "v46 ready: build/auto-probe-v46.luau. Sampling starts automatically."
