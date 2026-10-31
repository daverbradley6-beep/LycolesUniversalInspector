# v40 game-first discovery + valid Luau diagnostic
param([string]$ReceiverBundle="examples/muscle-legends-receiver-v15-sanitized.json",[string]$Build="build")
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
& py -m unittest discover -s tests -p "test_v3*.py"
if ($LASTEXITCODE -ne 0) { throw "v3x regression tests failed" }
& py -m unittest discover -s tests -p "test_v40*.py"
if ($LASTEXITCODE -ne 0) { throw "v40 regression tests failed" }
if (-not (Test-Path $ReceiverBundle)) { throw "Receiver bundle not found: $ReceiverBundle" }
New-Item -ItemType Directory -Force -Path $Build | Out-Null
& py tools/receiver_pipeline_v38.py validate $ReceiverBundle --output (Join-Path $Build "receiver-summary-v38.json")
if ($LASTEXITCODE -ne 0) { throw "Receiver validation failed" }
& py tools/game_first_v39.py $ReceiverBundle --report (Join-Path $Build "game-discovery-v39.json") --luau (Join-Path $Build "diagnostic-v39-legacy.luau")
if ($LASTEXITCODE -ne 0) { throw "Discovery failed" }
& py tools/diagnostic_generator_v40.py (Join-Path $Build "game-discovery-v39.json") --output (Join-Path $Build "diagnostic-v40.luau")
if ($LASTEXITCODE -ne 0) { throw "Luau generation failed" }
Write-Host "v40 report and valid Luau diagnostic generated. Gameplay remains unverified."
