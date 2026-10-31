# v38 offline receiver pipeline
param([Parameter(Mandatory=$true)][string]$ReceiverBundle,[string]$Examples="examples",[string]$Build="build")
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
& py -m unittest discover -s tests -p "test_v3*.py"
if ($LASTEXITCODE -ne 0) { throw "Regression tests failed" }
New-Item -ItemType Directory -Force -Path $Build | Out-Null
& py tools/feature_intelligence.py $Examples --output (Join-Path $Build "feature-intelligence.json")
if ($LASTEXITCODE -ne 0) { throw "Feature extraction failed" }
& py tools/receiver_pipeline_v38.py validate $ReceiverBundle --output (Join-Path $Build "receiver-summary-v38.json")
if ($LASTEXITCODE -ne 0) { throw "Receiver validation failed" }
& py tools/receiver_pipeline_v38.py plan (Join-Path $Build "feature-intelligence.json") $ReceiverBundle --output (Join-Path $Build "feature-plan-v38.json")
if ($LASTEXITCODE -ne 0) { throw "Diagnostic planning failed" }
Write-Host "v38 offline reports created; live gameplay remains unverified."
