# v58 complete offline pipeline and optional explicit gameplay workflow build
param([string]$ReceiverBundle="examples/muscle-legends-receiver-v15-sanitized.json",[string]$Build="build",[string]$Receipt="",[string]$DiscoveryReceipt="",[string]$ActionSpec="")
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$previous=@("-ExecutionPolicy","Bypass","-File",".\tools\run_v57.ps1","-ReceiverBundle",$ReceiverBundle,"-Build",$Build)
if (-not [string]::IsNullOrWhiteSpace($Receipt)) { $previous+=@("-Receipt",$Receipt) }
if (-not [string]::IsNullOrWhiteSpace($DiscoveryReceipt)) { $previous+=@("-DiscoveryReceipt",$DiscoveryReceipt) }
& powershell @previous
if ($LASTEXITCODE -ne 0) { throw "v57 failed" }
& py -m unittest discover -s tests -p test_v58_workflows.py
if ($LASTEXITCODE -ne 0) { throw "v58 regression failed" }
if (-not [string]::IsNullOrWhiteSpace($ActionSpec)) {
 & py tools/gameplay_workflows_v58.py --spec $ActionSpec --output (Join-Path $Build "release-v58")
 if ($LASTEXITCODE -ne 0) { throw "v58 generation failed" }
 Write-Host "v58 gameplay runner ready in build/release-v58"
} else {
 Write-Host "v58 offline validation complete. Provide -ActionSpec for owner-authorized gameplay workflow generation."
}
