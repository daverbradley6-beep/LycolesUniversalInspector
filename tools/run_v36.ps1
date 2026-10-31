# Lycoles v36 validated multipart-to-feature pipeline
param([Parameter(Mandatory=$true)][string]$ScanParts,[string]$Examples="examples",[string]$Build="build")
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
& py -m unittest discover -s tests -p "test_v3*.py"
if ($LASTEXITCODE -ne 0) { throw "Tests failed" }
New-Item -ItemType Directory -Force -Path $Build | Out-Null
& py tools/feature_intelligence.py $Examples --output (Join-Path $Build "feature-intelligence.json")
if ($LASTEXITCODE -ne 0) { throw "Feature analysis failed" }
& py tools/luau_evidence_v34.py $Examples --output (Join-Path $Build "luau-evidence-v34.json")
if ($LASTEXITCODE -ne 0) { throw "Lexical analysis failed" }
& py tools/audit_feature_evidence_v34.py (Join-Path $Build "feature-intelligence.json") (Join-Path $Build "luau-evidence-v34.json") --output (Join-Path $Build "evidence-audit-v34.json")
if ($LASTEXITCODE -ne 0) { throw "Evidence audit failed" }
& py tools/scan_adapter_v36.py $ScanParts --output (Join-Path $Build "scan-objects-v36.json")
if ($LASTEXITCODE -ne 0) { throw "Multipart integrity validation failed" }
& py tools/match_scan_features_v36.py (Join-Path $Build "feature-intelligence.json") (Join-Path $Build "scan-objects-v36.json") --audit (Join-Path $Build "evidence-audit-v34.json") --output (Join-Path $Build "feature-match-v36.json")
if ($LASTEXITCODE -ne 0) { throw "Feature matching failed" }
Write-Host "v36 reports generated. All evidence remains unverified in-game."
