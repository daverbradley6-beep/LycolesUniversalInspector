# Lycoles v42 full offline evidence compilation
param([string]$ReceiverBundle="examples/muscle-legends-receiver-v15-sanitized.json",[string]$Build="build")
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
foreach ($pattern in @("test_v3*.py","test_v40*.py","test_v41*.py","test_v42*.py")) {
    & py -m unittest discover -s tests -p $pattern
    if ($LASTEXITCODE -ne 0) { throw "Tests failed: $pattern" }
}
if (-not (Test-Path $ReceiverBundle)) { throw "Missing receiver bundle: $ReceiverBundle" }
New-Item -ItemType Directory -Force -Path $Build | Out-Null
& py tools/receiver_pipeline_v38.py validate $ReceiverBundle --output (Join-Path $Build "receiver-summary-v38.json")
if ($LASTEXITCODE -ne 0) { throw "Receiver validation failed" }
& py tools/game_first_v39.py $ReceiverBundle --report (Join-Path $Build "game-discovery-v39.json") --luau (Join-Path $Build "diagnostic-v39-legacy.luau")
if ($LASTEXITCODE -ne 0) { throw "Discovery failed" }
& py tools/feature_spec_v41.py (Join-Path $Build "game-discovery-v39.json") --spec (Join-Path $Build "feature-spec-v41.json") --luau (Join-Path $Build "feature-inspector-v41.luau")
if ($LASTEXITCODE -ne 0) { throw "Feature spec generation failed" }
& py tools/generation_manifest_v42.py (Join-Path $Build "feature-spec-v41.json") (Join-Path $Build "game-discovery-v39.json") --output (Join-Path $Build "generation-manifest-v42.json")
if ($LASTEXITCODE -ne 0) { throw "Manifest compilation failed" }
Write-Host "v42 provenance-checked generation manifest created. Runtime behavior remains unverified."
