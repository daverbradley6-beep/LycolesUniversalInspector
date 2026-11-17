param(
    [string]$ContainerName = "openhands-app",
    [int]$BackendPort = 8787,
    [string]$ProxyContainerName = "lycoles-backend-proxy",
    [switch]$EnableSharedToken,
    [string]$SharedToken = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[lycoles-bridge] $Message" -ForegroundColor Cyan
}

function Require-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker CLI not found. Install Docker Desktop and retry."
    }
}

function Invoke-Docker {
    param([Parameter(ValueFromRemainingArguments = $true)] [string[]]$Args)
    $output = & docker @Args 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "docker $($Args -join ' ') failed: $output"
    }
    return $output
}

function Resolve-ManagerScriptPath {
    param([string]$Container)

    $path = Invoke-Docker exec $Container sh -lc "find /home/openhands/workspace/project -maxdepth 5 -name lycoles_backend_manager.py -print -quit"
    $trimmed = "$path".Trim()
    if ([string]::IsNullOrWhiteSpace($trimmed)) {
        throw "Could not locate lycoles_backend_manager.py in container workspace."
    }
    return $trimmed
}

function Resolve-ContainerNetwork {
    param([string]$Container)

    $network = Invoke-Docker inspect -f "{{range `$k,`$v := .NetworkSettings.Networks}}{{printf `%s`n `$k}}{{end}}" $Container
    $trimmed = "$network".Trim()
    if ([string]::IsNullOrWhiteSpace($trimmed)) {
        throw "Could not resolve docker network for $Container"
    }
    return ($trimmed -split "`n")[0].Trim()
}

function New-SharedToken {
    $bytes = New-Object byte[] 24
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return ([Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_'))
}

Require-Docker

Write-Step "Checking OpenHands container runtime state."
$running = Invoke-Docker inspect -f "{{.State.Running}}" $ContainerName
if ("$running".Trim().ToLowerInvariant() -ne "true") {
    throw "Container '$ContainerName' is not running. Start Agent Canvas first."
}

$managerScript = Resolve-ManagerScriptPath -Container $ContainerName
Write-Step "Resolved backend manager path: $managerScript"

$effectiveToken = ""
if ($EnableSharedToken.IsPresent) {
    $effectiveToken = if ([string]::IsNullOrWhiteSpace($SharedToken)) { New-SharedToken } else { $SharedToken.Trim() }
    if ([string]::IsNullOrWhiteSpace($effectiveToken)) {
        throw "Shared token generation failed."
    }
    Write-Step "Shared token auth enabled for backend API."
}

Write-Step "Ensuring Lycoles backend service is running inside container."
$execArgs = @("exec")
if (-not [string]::IsNullOrWhiteSpace($effectiveToken)) {
    $execArgs += @("-e", "LYCOLES_BACKEND_SHARED_TOKEN=$effectiveToken")
}
$execArgs += @(
    $ContainerName,
    "python3",
    $managerScript,
    "ensure",
    "--host", "0.0.0.0",
    "--port", "$BackendPort"
)
Invoke-Docker @execArgs | Out-Host

$networkName = Resolve-ContainerNetwork -Container $ContainerName
Write-Step "Using docker network: $networkName"

$existingProxy = & docker ps -a --filter "name=^/$ProxyContainerName$" --format "{{.ID}}" 2>$null
if ($LASTEXITCODE -ne 0) { $existingProxy = "" }
if (-not [string]::IsNullOrWhiteSpace("$existingProxy".Trim())) {
    Write-Step "Removing existing proxy container '$ProxyContainerName'."
    Invoke-Docker rm -f $ProxyContainerName | Out-Null
}

Write-Step "Starting backend proxy sidecar on 127.0.0.1:$BackendPort."
Invoke-Docker run -d `
    --name $ProxyContainerName `
    --restart unless-stopped `
    --network $networkName `
    -p "127.0.0.1:$BackendPort`:$BackendPort" `
    alpine/socat `
    "TCP-LISTEN:$BackendPort,fork,reuseaddr" `
    "TCP:$ContainerName:$BackendPort" | Out-Host

$headers = @{}
if (-not [string]::IsNullOrWhiteSpace($effectiveToken)) {
    $headers["X-Lycoles-Backend-Token"] = $effectiveToken
}

$healthUrl = "http://127.0.0.1:$BackendPort/v1/generation/health"
Write-Step "Waiting for backend health endpoint: $healthUrl"
$healthy = $false
for ($i = 0; $i -lt 25; $i++) {
    try {
        $response = Invoke-RestMethod -Uri $healthUrl -Method GET -Headers $headers -TimeoutSec 3
        if ($response -and $response.status -eq "ok") {
            $healthy = $true
            break
        }
    } catch {
        Start-Sleep -Milliseconds 400
    }
}

if (-not $healthy) {
    throw "Bridge started but health probe failed. Check logs: docker logs $ProxyContainerName"
}

Write-Step "Bridge is healthy."
Write-Host ""
Write-Host "Use this Roblox backend config:" -ForegroundColor Green
if (-not [string]::IsNullOrWhiteSpace($effectiveToken)) {
    Write-Host "_G.LycolesGenerationBackendConfig = { enabled = true, baseUrls = { \"http://127.0.0.1:$BackendPort\" }, sharedToken = \"$effectiveToken\", maxAttempts = 3, timeoutSeconds = 15, pollTimeoutSeconds = 90 }"
} else {
    Write-Host "_G.LycolesGenerationBackendConfig = { enabled = true, baseUrls = { \"http://127.0.0.1:$BackendPort\" }, maxAttempts = 3, timeoutSeconds = 15, pollTimeoutSeconds = 90 }"
}
Write-Host ""
Write-Host "Cleanup command: docker rm -f $ProxyContainerName" -ForegroundColor DarkGray
