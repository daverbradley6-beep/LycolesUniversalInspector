# v54 full offline build, test, and optional live receipt analysis
param([string]$ReceiverBundle="examples/muscle-legends-receiver-v15-sanitized.json",[string]$Build="build",[string]$Receipt="",[string]$DiscoveryReceipt="")
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$previous=@("-ExecutionPolicy","Bypass","-File",".\tools\run_v53.ps1","-ReceiverBundle",$ReceiverBundle,"-Build",$Build)
if (-not [string]::IsNullOrWhiteSpace($Receipt)) { $previous+=@("-Receipt",$Receipt) }
& powershell @previous
if ($LASTEXITCODE -ne 0) { throw "v53 failed" }
& py -m unittest discover -s tests -p test_v54_balanced.py
if ($LASTEXITCODE -ne 0) { throw "v54 regression failed" }
$manifest=Get-Content (Join-Path $Build "generation-manifest-v42.json") -Raw | ConvertFrom-Json
$placeId=[int64]$manifest.placeId
$args54=@("tools/balanced_discovery_v54.py","--place-id","$placeId","--output",(Join-Path $Build "release-v54"))
if (-not [string]::IsNullOrWhiteSpace($DiscoveryReceipt)) { $args54+=@("--receipt",$DiscoveryReceipt) }
& py @args54
if ($LASTEXITCODE -ne 0) { throw "v54 generation failed" }
Write-Host "v54 release ready in build/release-v54"
Write-Host "Final Roblox test: execute balanced-discovery-v54.luau in the matching place."
