# v37 receiver-indexed scan workflow
param([Parameter(Mandatory=$true)][string]$ReceiverBundle,[string]$Examples="examples",[string]$Build="build")
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
& py -m unittest discover -s tests -p "test_v3*.py"
if ($LASTEXITCODE -ne 0) { throw "Regression tests failed" }
New-Item -ItemType Directory -Force -Path $Build | Out-Null
& py tools/feature_intelligence.py $Examples --output (Join-Path $Build "feature-intelligence.json")
if ($LASTEXITCODE -ne 0) { throw "Source analysis failed" }
& py tools/receiver_adapter_v37.py $ReceiverBundle --output (Join-Path $Build "receiver-objects-v37.json")
if ($LASTEXITCODE -ne 0) { throw "Receiver import failed" }
& py tools/match_receiver_features_v37.py (Join-Path $Build "feature-intelligence.json") (Join-Path $Build "receiver-objects-v37.json") --output (Join-Path $Build "receiver-feature-match-v37.json")
if ($LASTEXITCODE -ne 0) { throw "Feature matching failed" }
Write-Host "v37 receiver analysis complete. No gameplay automation or server outcomes verified."
