# v59: run full offline regression suite and generate evidence-gated gameplay plan
param([string]$ReceiverBundle="examples/muscle-legends-receiver-v15-sanitized.json",[string]$Build="build",[string]$Receipt="",[string]$DiscoveryReceipt="",[string]$ActionSpec="")
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$previous=@("-ExecutionPolicy","Bypass","-File",".\tools\run_v58.ps1","-ReceiverBundle",$ReceiverBundle,"-Build",$Build)
if (-not [string]::IsNullOrWhiteSpace($Receipt)) { $previous+=@("-Receipt",$Receipt) }
if (-not [string]::IsNullOrWhiteSpace($DiscoveryReceipt)) { $previous+=@("-DiscoveryReceipt",$DiscoveryReceipt) }
& powershell @previous
if ($LASTEXITCODE -ne 0) { throw "v58 pipeline failed" }
& py -m unittest discover -s tests -p test_v59_planner.py
if ($LASTEXITCODE -ne 0) { throw "v59 tests failed" }
if (-not [string]::IsNullOrWhiteSpace($DiscoveryReceipt)) {
 $manifest=Get-Content (Join-Path $Build "generation-manifest-v42.json") -Raw | ConvertFrom-Json
 $placeId=[int64]$manifest.placeId
 $args59=@("tools/gameplay_planner_v59.py","--receipt",$DiscoveryReceipt,"--place-id","$placeId","--output",(Join-Path $Build "release-v59"))
 if (-not [string]::IsNullOrWhiteSpace($ActionSpec)) { $args59+=@("--contract",$ActionSpec) }
 & py @args59
 if ($LASTEXITCODE -ne 0) { throw "v59 compilation failed" }
 Write-Host "v59 evidence-gated release ready in build/release-v59"
} else {
 Write-Host "v59 tests finished. A v54 discovery receipt is required for game-specific planning."
}
