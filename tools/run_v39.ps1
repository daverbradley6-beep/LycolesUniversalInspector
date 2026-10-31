# v39 game-first offline analysis
param([string]$ReceiverBundle="examples/muscle-legends-receiver-v15-sanitized.json",[string]$Build="build")
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
& py -m unittest discover -s tests -p "test_v3*.py"
if ($LASTEXITCODE -ne 0) { throw "Regression tests failed" }
if (-not (Test-Path $ReceiverBundle)) { throw "Receiver bundle not found: $ReceiverBundle" }
New-Item -ItemType Directory -Force -Path $Build | Out-Null
& py tools/receiver_pipeline_v38.py validate $ReceiverBundle --output (Join-Path $Build "receiver-summary-v38.json")
if ($LASTEXITCODE -ne 0) { throw "Receiver validation failed" }
& py tools/game_first_v39.py $ReceiverBundle --report (Join-Path $Build "game-discovery-v39.json") --luau (Join-Path $Build "diagnostic-v39.luau")
if ($LASTEXITCODE -ne 0) { throw "Game-first discovery failed" }
Write-Host "v39 game-first evidence reports and read-only Luau diagnostic generated."
