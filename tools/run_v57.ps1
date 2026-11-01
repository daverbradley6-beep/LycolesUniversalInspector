# v57 complete offline regression and optional authorized gameplay-contract compilation
param([string]$ReceiverBundle="examples/muscle-legends-receiver-v15-sanitized.json",[string]$Build="build",[string]$Receipt="",[string]$DiscoveryReceipt="",[string]$ActionSpec="")
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$previous=@("-ExecutionPolicy","Bypass","-File",".\tools\run_v56.ps1","-ReceiverBundle",$ReceiverBundle,"-Build",$Build)
if (-not [string]::IsNullOrWhiteSpace($Receipt)) { $previous+=@("-Receipt",$Receipt) }
if (-not [string]::IsNullOrWhiteSpace($DiscoveryReceipt)) { $previous+=@("-DiscoveryReceipt",$DiscoveryReceipt) }
& powershell @previous
if ($LASTEXITCODE -ne 0) { throw "v56 pipeline failed" }
& py -m unittest discover -s tests -p test_v57_gameplay.py
if ($LASTEXITCODE -ne 0) { throw "v57 tests failed" }
if (-not [string]::IsNullOrWhiteSpace($DiscoveryReceipt)) {
 $manifest=Get-Content (Join-Path $Build "generation-manifest-v42.json") -Raw | ConvertFrom-Json
 $placeId=[int64]$manifest.placeId
 & py tools/action_proposals_v57.py --receipt $DiscoveryReceipt --place-id $placeId --output (Join-Path $Build "release-v57")
 if ($LASTEXITCODE -ne 0) { throw "v57 proposals failed" }
}
if (-not [string]::IsNullOrWhiteSpace($ActionSpec)) {
 & py tools/gameplay_contracts_v57.py --spec $ActionSpec --output (Join-Path $Build "release-v57")
 if ($LASTEXITCODE -ne 0) { throw "v57 action contract build failed" }
 Write-Host "v57 authorized action runner ready in build/release-v57"
} else {
 Write-Host "v57 offline tests passed. To compile actions, provide a game-owner-approved -ActionSpec."
}
