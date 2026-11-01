# v53: offline regression, live receipt analysis, and bounded discovery build
param([string]$ReceiverBundle="examples/muscle-legends-receiver-v15-sanitized.json",[string]$Build="build",[string]$Receipt="",[string]$DiscoveryReceipt="")
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$v52Args=@("-ExecutionPolicy","Bypass","-File",".\tools\run_v52.ps1","-ReceiverBundle",$ReceiverBundle,"-Build",$Build)
if (-not [string]::IsNullOrWhiteSpace($Receipt)) { $v52Args+=@("-Receipt",$Receipt) }
& powershell @v52Args
if ($LASTEXITCODE -ne 0) { throw "v52 failed" }
& py -m unittest discover -s tests -p test_v53_discovery.py
if ($LASTEXITCODE -ne 0) { throw "v53 tests failed" }
$manifest=Get-Content (Join-Path $Build "generation-manifest-v42.json") -Raw | ConvertFrom-Json
$placeId=[int64]$manifest.placeId
$args53=@("tools/live_discovery_v53.py","--place-id","$placeId","--output",(Join-Path $Build "release-v53"))
if (-not [string]::IsNullOrWhiteSpace($DiscoveryReceipt)) { $args53+=@("--receipt",$DiscoveryReceipt) }
& py @args53
if ($LASTEXITCODE -ne 0) { throw "v53 generation failed" }
Write-Host "v53 release ready in build/release-v53"
Write-Host "Execute live-discovery-v53.luau in the matching place and save the receipt."
