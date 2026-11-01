# v56 consolidated offline release
param([string]$ReceiverBundle="examples/muscle-legends-receiver-v15-sanitized.json",[string]$Build="build",[string]$Receipt="",[string]$DiscoveryReceipt="")
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$previous=@("-ExecutionPolicy","Bypass","-File",".\tools\run_v55.ps1","-ReceiverBundle",$ReceiverBundle,"-Build",$Build)
if (-not [string]::IsNullOrWhiteSpace($Receipt)) { $previous+=@("-Receipt",$Receipt) }
if (-not [string]::IsNullOrWhiteSpace($DiscoveryReceipt)) { $previous+=@("-DiscoveryReceipt",$DiscoveryReceipt) }
& powershell @previous
if ($LASTEXITCODE -ne 0) { throw "v55 failed" }
& py -m unittest discover -s tests -p test_v56_compiler.py
if ($LASTEXITCODE -ne 0) { throw "v56 tests failed" }
if (-not [string]::IsNullOrWhiteSpace($DiscoveryReceipt)) {
 $manifest=Get-Content (Join-Path $Build "generation-manifest-v42.json") -Raw | ConvertFrom-Json
 $placeId=[int64]$manifest.placeId
 & py tools/universal_compiler_v56.py --receipt $DiscoveryReceipt --place-id $placeId --output (Join-Path $Build "release-v56")
 if ($LASTEXITCODE -ne 0) { throw "v56 release failed" }
 Write-Host "v56 compiled release ready in build/release-v56"
} else {
 Write-Host "v56 tests completed. A v54 live receipt is required for the evidence-based GUI."
}
