# Lycoles v41 offline evidence-gated feature builder
param([string]$ReceiverBundle="examples/muscle-legends-receiver-v15-sanitized.json",[string]$Build="build")
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
& py -m unittest discover -s tests -p "test_v3*.py"
if ($LASTEXITCODE -ne 0) { throw "v3x regression tests failed" }
& py -m unittest discover -s tests -p "test_v40*.py"
if ($LASTEXITCODE -ne 0) { throw "v40 tests failed" }
& py -m unittest discover -s tests -p "test_v41*.py"
if ($LASTEXITCODE -ne 0) { throw "v41 tests failed" }
if (-not (Test-Path $ReceiverBundle)) { throw "Receiver bundle missing: $ReceiverBundle" }
New-Item -ItemType Directory -Force -Path $Build | Out-Null
& py tools/receiver_pipeline_v38.py validate $ReceiverBundle --output (Join-Path $Build "receiver-summary-v38.json")
if ($LASTEXITCODE -ne 0) { throw "Receiver validation failed" }
& py tools/game_first_v39.py $ReceiverBundle --report (Join-Path $Build "game-discovery-v39.json") --luau (Join-Path $Build "diagnostic-v39-legacy.luau")
if ($LASTEXITCODE -ne 0) { throw "Discovery failed" }
& py tools/feature_spec_v41.py (Join-Path $Build "game-discovery-v39.json") --spec (Join-Path $Build "feature-spec-v41.json") --luau (Join-Path $Build "feature-inspector-v41.luau")
if ($LASTEXITCODE -ne 0) { throw "Feature specification failed" }
Write-Host "v41 feature specifications and read-only diagnostic GUI generated."
