# v48: full pipeline plus passive state-change observation
param([string]$ReceiverBundle="examples/muscle-legends-receiver-v15-sanitized.json",[string]$Build="build",[string]$Receipt="")
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
& powershell -ExecutionPolicy Bypass -File .\tools\run_v47.ps1 -ReceiverBundle $ReceiverBundle -Build $Build
if ($LASTEXITCODE -ne 0) { throw "v47 pipeline failed" }
& py -m unittest discover -s tests -p "test_v48*.py"
if ($LASTEXITCODE -ne 0) { throw "v48 tests failed" }
$args48=@("tools/passive_observer_v48.py",(Join-Path $Build "generation-manifest-v42.json"),"--output",$Build)
if (-not [string]::IsNullOrWhiteSpace($Receipt)) { $args48+=@("--receipt",$Receipt) }
& py @args48
if ($LASTEXITCODE -ne 0) { throw "v48 observation processing failed" }
Write-Host "v48 ready: build/passive-observer-v48.luau"
