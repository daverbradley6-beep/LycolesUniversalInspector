# v49: candidate synthesis from observed client-state changes
param([string]$ReceiverBundle="examples/muscle-legends-receiver-v15-sanitized.json",[string]$Build="build",[string]$Receipt="")
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$v48Args=@("-ExecutionPolicy","Bypass","-File",".\tools\run_v48.ps1","-ReceiverBundle",$ReceiverBundle,"-Build",$Build)
if (-not [string]::IsNullOrWhiteSpace($Receipt)) { $v48Args+=@("-Receipt",$Receipt) }
& powershell @v48Args
if ($LASTEXITCODE -ne 0) { throw "v48 pipeline failed" }
& py -m unittest discover -s tests -p "test_v49*.py"
if ($LASTEXITCODE -ne 0) { throw "v49 tests failed" }
$report=Join-Path $Build "state-changes-v48.json"
if (-not [string]::IsNullOrWhiteSpace($Receipt) -and (Test-Path $report)) {
 & py tools/feature_synthesizer_v49.py (Join-Path $Build "generation-manifest-v42.json") $report --output (Join-Path $Build "feature-candidates-v49.json")
 if ($LASTEXITCODE -ne 0) { throw "v49 candidate synthesis failed" }
} else { Write-Host "v49: supply -Receipt with a v48 receipt to synthesize candidates." }
