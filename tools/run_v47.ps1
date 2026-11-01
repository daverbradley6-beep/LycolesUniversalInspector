# v47: full regression and generated game-specific diagnostics
param([string]$ReceiverBundle="examples/muscle-legends-receiver-v15-sanitized.json",[string]$Build="build",[string]$Console="")
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$v46Args=@("-ExecutionPolicy","Bypass","-File",".\tools\run_v46.ps1","-ReceiverBundle",$ReceiverBundle,"-Build",$Build)
if (-not [string]::IsNullOrWhiteSpace($Console)) { $v46Args+=@("-Console",$Console) }
& powershell @v46Args
if ($LASTEXITCODE -ne 0) { throw "v46 pipeline failed" }
& py -m unittest discover -s tests -p "test_v47*.py"
if ($LASTEXITCODE -ne 0) { throw "v47 regression failed" }
& py tools/feature_dashboard_v47.py (Join-Path $Build "generation-manifest-v42.json") --output (Join-Path $Build "feature-dashboard-v47.luau")
if ($LASTEXITCODE -ne 0) { throw "v47 dashboard generation failed" }
Write-Host "v47 ready: build/feature-dashboard-v47.luau and build/auto-probe-v46.luau"
