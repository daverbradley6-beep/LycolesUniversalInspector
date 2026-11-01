# v60 offline regression, synthetic replay and optional owner-authorized build
param([string]$ReceiverBundle="examples/muscle-legends-receiver-v15-sanitized.json",[string]$Build="build",[string]$Receipt="",[string]$DiscoveryReceipt="",[string]$ActionSpec="",[string]$ActionTrace="")
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$previous=@("-ExecutionPolicy","Bypass","-File",".\tools\run_v59.ps1","-ReceiverBundle",$ReceiverBundle,"-Build",$Build)
if (-not [string]::IsNullOrWhiteSpace($Receipt)) { $previous+=@("-Receipt",$Receipt) }
if (-not [string]::IsNullOrWhiteSpace($DiscoveryReceipt)) { $previous+=@("-DiscoveryReceipt",$DiscoveryReceipt) }
& powershell @previous
if ($LASTEXITCODE -ne 0) { throw "v59 pipeline failed" }
& py -m unittest discover -s tests -p test_v60_verification.py
if ($LASTEXITCODE -ne 0) { throw "v60 tests failed" }
& py tools/verification_replay_v60.py --receipt examples/v60-synthetic-receipt.json --contract examples/v60-synthetic-contract.json --trace examples/v60-synthetic-trace.json --output (Join-Path $Build "v60-synthetic-smoke")
if ($LASTEXITCODE -ne 0) { throw "v60 synthetic smoke failed" }
if (-not [string]::IsNullOrWhiteSpace($DiscoveryReceipt) -and -not [string]::IsNullOrWhiteSpace($ActionSpec) -and -not [string]::IsNullOrWhiteSpace($ActionTrace)) {
 & py tools/verification_replay_v60.py --receipt $DiscoveryReceipt --contract $ActionSpec --trace $ActionTrace --output (Join-Path $Build "release-v60")
 if ($LASTEXITCODE -ne 0) { throw "v60 release failed" }
 Write-Host "v60 observationally gated release generated in build/release-v60"
} else {
 Write-Host "v60 offline tests and synthetic replay completed. Real gameplay verification requires an authorized trace."
}
