# Lycoles v35 offline evidence pipeline
param([string]$Inspection="",[string]$Build="build")
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
& py -m unittest discover -s tests -p "test_v3*.py"
if ($LASTEXITCODE -ne 0) { throw "Regression tests failed" }
& py tools/feature_intelligence.py examples --output (Join-Path $Build "feature-intelligence.json")
if ($LASTEXITCODE -ne 0) { throw "Feature analysis failed" }
& py tools/luau_evidence_v34.py examples --output (Join-Path $Build "luau-evidence-v34.json")
if ($LASTEXITCODE -ne 0) { throw "Lexical analysis failed" }
& py tools/audit_feature_evidence_v34.py (Join-Path $Build "feature-intelligence.json") (Join-Path $Build "luau-evidence-v34.json") --output (Join-Path $Build "evidence-audit-v34.json")
if ($LASTEXITCODE -ne 0) { throw "Audit failed" }
if ($Inspection -ne "") {
    & py tools/inspection_bridge_v35.py (Join-Path $Build "feature-intelligence.json") $Inspection --audit (Join-Path $Build "evidence-audit-v34.json")
    if ($LASTEXITCODE -ne 0) { throw "Scan matching failed" }
}
Write-Host "Static analysis complete. Live gameplay not tested."
