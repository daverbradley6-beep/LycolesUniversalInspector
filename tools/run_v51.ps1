# v51: automatic generation from observed local-player state
param([string]$ReceiverBundle="examples/muscle-legends-receiver-v15-sanitized.json",[string]$Build="build",[string]$Receipt="")
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$v49Args=@("-ExecutionPolicy","Bypass","-File",".\tools\run_v49.ps1","-ReceiverBundle",$ReceiverBundle,"-Build",$Build)
if (-not [string]::IsNullOrWhiteSpace($Receipt)) { $v49Args+=@("-Receipt",$Receipt) }
& powershell @v49Args
if ($LASTEXITCODE -ne 0) { throw "v49 pipeline failed" }
& py -m unittest discover -s tests -p "test_v51*.py"
if ($LASTEXITCODE -ne 0) { throw "v51 tests failed" }
$report=Join-Path $Build "state-changes-v48.json"
if (-not [string]::IsNullOrWhiteSpace($Receipt) -and (Test-Path $report)) {
 & py tools/auto_actions_v51.py (Join-Path $Build "generation-manifest-v42.json") $report --output $Build
 if ($LASTEXITCODE -ne 0) { throw "v51 generation failed" }
} else { Write-Host "v51: supply -Receipt with a v48 receipt to generate verified-path read-only controls." }
