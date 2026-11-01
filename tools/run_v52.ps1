# v52: unified build and offline end-to-end smoke test
param([string]$ReceiverBundle="examples/muscle-legends-receiver-v15-sanitized.json",[string]$Build="build",[string]$Receipt="")
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
& powershell -ExecutionPolicy Bypass -File .\tools\run_v51.ps1 -ReceiverBundle $ReceiverBundle -Build $Build
if ($LASTEXITCODE -ne 0) { throw "Prior pipeline failed" }
$manifest=Join-Path $Build "generation-manifest-v42.json"
& py tools/release_builder_v52.py --manifest $manifest --output (Join-Path $Build "release-v52") --self-test --test-suite
if ($LASTEXITCODE -ne 0) { throw "v52 smoke/regression failed" }
if (-not [string]::IsNullOrWhiteSpace($Receipt)) {
 & py tools/release_builder_v52.py --manifest $manifest --receipt $Receipt --output (Join-Path $Build "release-v52-live")
 if ($LASTEXITCODE -ne 0) { throw "v52 live receipt analysis failed" }
}
Write-Host "v52 offline release generated in build/release-v52"
Write-Host "Synthetic smoke data is not proof of live Roblox mechanics."
