# v61: full offline suite, collector build, and optional v60 replay
param([string]$ReceiverBundle="examples/muscle-legends-receiver-v15-sanitized.json",[string]$Build="build",[string]$Receipt="",[string]$DiscoveryReceipt="",[string]$ActionSpec="",[string]$ActionTrace="")
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$previous=@("-ExecutionPolicy","Bypass","-File",".\tools\run_v60.ps1","-ReceiverBundle",$ReceiverBundle,"-Build",$Build)
if (-not [string]::IsNullOrWhiteSpace($Receipt)) { $previous+=@("-Receipt",$Receipt) }
if (-not [string]::IsNullOrWhiteSpace($DiscoveryReceipt)) { $previous+=@("-DiscoveryReceipt",$DiscoveryReceipt) }
if (-not [string]::IsNullOrWhiteSpace($ActionSpec)) { $previous+=@("-ActionSpec",$ActionSpec) }
if (-not [string]::IsNullOrWhiteSpace($ActionTrace)) { $previous+=@("-ActionTrace",$ActionTrace) }
& powershell @previous
if ($LASTEXITCODE -ne 0) { throw "v60 pipeline failed" }
& py -m unittest discover -s tests -p test_v61_collector.py
if ($LASTEXITCODE -ne 0) { throw "v61 tests failed" }
if (-not [string]::IsNullOrWhiteSpace($ActionSpec)) {
 & py tools/live_trace_collector_v61.py --contract $ActionSpec --output (Join-Path $Build "release-v61")
 if ($LASTEXITCODE -ne 0) { throw "v61 collector build failed" }
 Write-Host "v61 collector ready at build/release-v61/live-trace-collector-v61.luau"
} else {
 Write-Host "v61 offline tests complete. Supply -ActionSpec to generate an authorized collector."
}
