# Lycoles v34: one-command offline test and evidence pipeline
param([string]$Examples="examples",[string]$Build="build")
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw "Python launcher py is required" }
& py -m unittest discover -s tests -p "test_v3*.py"
if ($LASTEXITCODE -ne 0) { throw "Regression suite failed; pipeline stopped" }
if (-not (Test-Path $Examples -PathType Container)) { throw "Missing examples folder; add readable Lua/Luau scripts" }
New-Item -ItemType Directory -Force -Path $Build | Out-Null
& py tools/analyze_script_corpus.py $Examples --output (Join-Path $Build "script-corpus.json")
if ($LASTEXITCODE -ne 0) { throw "v31 corpus failed" }
& py tools/synthesize_workflow_specs.py (Join-Path $Build "script-corpus.json") --output (Join-Path $Build "workflow-specs.json")
if ($LASTEXITCODE -ne 0) { throw "v31 workflows failed" }
& py tools/feature_intelligence.py $Examples --output (Join-Path $Build "feature-intelligence.json")
if ($LASTEXITCODE -ne 0) { throw "v32 feature analysis failed" }
& py tools/luau_evidence_v34.py $Examples --output (Join-Path $Build "luau-evidence-v34.json")
if ($LASTEXITCODE -ne 0) { throw "v34 lexical evidence failed" }
& py tools/audit_feature_evidence_v34.py (Join-Path $Build "feature-intelligence.json") (Join-Path $Build "luau-evidence-v34.json") --output (Join-Path $Build "evidence-audit-v34.json")
if ($LASTEXITCODE -ne 0) { throw "v34 cross-check failed" }
Write-Host "Lycoles offline evidence pipeline complete. No live gameplay was tested."
