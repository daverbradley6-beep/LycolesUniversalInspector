# v55 release pipeline: prior regression suites, evidence contract and live GUI
param([string]$ReceiverBundle="examples/muscle-legends-receiver-v15-sanitized.json",[string]$Build="build",[string]$Receipt="",[string]$DiscoveryReceipt="")
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$previous=@("-ExecutionPolicy","Bypass","-File",".\tools\run_v54.ps1","-ReceiverBundle",$ReceiverBundle,"-Build",$Build)
if (-not [string]::IsNullOrWhiteSpace($Receipt)) { $previous+=@("-Receipt",$Receipt) }
if (-not [string]::IsNullOrWhiteSpace($DiscoveryReceipt)) { $previous+=@("-DiscoveryReceipt",$DiscoveryReceipt) }
& powershell @previous
if ($LASTEXITCODE -ne 0) { throw "v54 failed" }
& py -m unittest discover -s tests -p test_v55_explorer.py
if ($LASTEXITCODE -ne 0) { throw "v55 tests failed" }
if (-not [string]::IsNullOrWhiteSpace($DiscoveryReceipt)) {
 $manifest=Get-Content (Join-Path $Build "generation-manifest-v42.json") -Raw | ConvertFrom-Json
 $placeId=[int64]$manifest.placeId
 & py tools/evidence_explorer_v55.py --receipt $DiscoveryReceipt --place-id $placeId --output (Join-Path $Build "release-v55")
 if ($LASTEXITCODE -ne 0) { throw "v55 evidence compilation failed" }
 Write-Host "v55 evidence GUI ready: build/release-v55/evidence-explorer-v55.luau"
} else {
 Write-Host "v55 offline tests passed; evidence GUI requires -DiscoveryReceipt with a v54 receipt."
}
