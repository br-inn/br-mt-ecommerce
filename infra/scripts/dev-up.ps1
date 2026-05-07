#requires -Version 5.1
<#
.SYNOPSIS
    Starts the local Docker stack with Caddy as single HTTP entry point.

.DESCRIPTION
    1. Ensures .env.deploy exists (copies from .env.deploy.example if missing).
    2. Ensures backend/.env and frontend/.env.local exist.
    3. Verifies port availability via check-ports.ps1.
    4. Runs docker compose with --env-file .env.deploy.

.PARAMETER Detach
    Run in background (-d / --detach).

.PARAMETER Build
    Force rebuild before starting.

.EXAMPLE
    .\infra\scripts\dev-up.ps1
    .\infra\scripts\dev-up.ps1 -Detach
    .\infra\scripts\dev-up.ps1 -Build
#>

[CmdletBinding()]
param(
    [switch]$Detach,
    [switch]$Build
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repoRoot

# 1. .env.deploy
if (-not (Test-Path '.env.deploy')) {
    Write-Host '[!] .env.deploy no existe - creandolo desde template' -ForegroundColor Yellow
    Copy-Item '.env.deploy.example' '.env.deploy'
}

# 2. backend/.env
if (-not (Test-Path 'mt-pricing-backend\.env')) {
    Write-Host '[!] mt-pricing-backend/.env no existe - creandolo desde template' -ForegroundColor Yellow
    Copy-Item 'mt-pricing-backend\.env.example' 'mt-pricing-backend\.env'
}

# 3. frontend/.env.local
if (-not (Test-Path 'mt-pricing-frontend\.env.local')) {
    Write-Host '[!] mt-pricing-frontend/.env.local no existe - creandolo desde template' -ForegroundColor Yellow
    Copy-Item 'mt-pricing-frontend\.env.example' 'mt-pricing-frontend\.env.local'
}

# 4. Verificar puertos
Write-Host '[i] Verificando puertos disponibles...' -ForegroundColor Blue
& "$repoRoot\infra\scripts\check-ports.ps1"
if ($LASTEXITCODE -ne 0) {
    Write-Host '[!] Hay puertos ocupados - edita .env.deploy con las sugerencias arriba y reintenta.' -ForegroundColor Yellow
    exit 1
}

# 5. Build args
$composeArgs = @('compose', '-f', 'docker-compose.dev.yml', '--env-file', '.env.deploy', 'up')
if ($Build)  { $composeArgs += '--build' }
if ($Detach) { $composeArgs += '-d' }

Write-Host '[i] Arrancando docker compose...' -ForegroundColor Blue
& docker @composeArgs

if ($Detach -and $LASTEXITCODE -eq 0) {
    # Cargar .env.deploy para mostrar URLs
    $envVars = @{}
    Get-Content '.env.deploy' | ForEach-Object {
        if ($_ -notmatch '^\s*#' -and $_ -match '^\s*([A-Z_]+)\s*=\s*(.+?)\s*$') {
            $envVars[$Matches[1]] = $Matches[2].Trim()
        }
    }
    $caddyPort = if ($envVars.CADDY_HTTP_PORT) { $envVars.CADDY_HTTP_PORT } else { '8080' }
    $redisPort = if ($envVars.REDIS_HOST_PORT) { $envVars.REDIS_HOST_PORT } else { '6379' }

    Write-Host ''
    Write-Host '[OK] Stack arrancado en modo detach.' -ForegroundColor Green
    Write-Host ''
    Write-Host "  App:         http://localhost:$caddyPort"
    Write-Host "  API docs:    http://localhost:$caddyPort/docs"
    Write-Host "  Healthcheck: http://localhost:$caddyPort/health/live"
    Write-Host "  Redis:       localhost:$redisPort"
    Write-Host '  BD:          Supabase real (https://vayatmweveoaskyejzba.supabase.co)'
    Write-Host ''
    Write-Host 'Logs:    docker compose -f docker-compose.dev.yml --env-file .env.deploy logs -f'
    Write-Host 'Parar:   .\infra\scripts\dev-down.ps1'
    Write-Host ''
}
