#requires -Version 5.1
<#
.SYNOPSIS
    Verifies port availability for the local Docker deploy of MT Pricing.

.DESCRIPTION
    Reads .env.deploy (or uses defaults) and tests if Caddy + Redis ports are
    free. The DB lives in Supabase cloud — no local Postgres port required.
    If any port is taken, suggests alternative free ports.

.EXAMPLE
    .\infra\scripts\check-ports.ps1
#>

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$envFile = Join-Path $repoRoot '.env.deploy'

# Defaults aligned with docker-compose.dev.yml fallbacks.
$envVars = @{
    CADDY_HTTP_PORT  = '8080'
    CADDY_HTTPS_PORT = '8443'
    REDIS_HOST_PORT  = '6379'
}

if (Test-Path $envFile) {
    Write-Host "[i] Usando configuracion de: $envFile" -ForegroundColor Blue
    Get-Content $envFile | ForEach-Object {
        if ($_ -notmatch '^\s*#' -and $_ -match '^\s*([A-Z_]+)\s*=\s*(.+?)\s*$') {
            $envVars[$Matches[1]] = $Matches[2].Trim()
        }
    }
}
else {
    Write-Host "[!] No existe .env.deploy - usando defaults del docker-compose" -ForegroundColor Yellow
}

function Test-PortInUse {
    param([int]$Port)
    try {
        $tcp = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        return ($null -ne $tcp)
    }
    catch {
        try {
            $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
            $listener.Start()
            $listener.Stop()
            return $false
        }
        catch {
            return $true
        }
    }
}

function Find-FreePort {
    param([int]$Start)
    for ($i = 1; $i -le 20; $i++) {
        $candidate = $Start + $i
        if (-not (Test-PortInUse -Port $candidate)) {
            return $candidate
        }
    }
    return 0
}

function Test-PortAvailability {
    param(
        [string]$Name,
        [int]$Port,
        [string]$VarName
    )
    if (Test-PortInUse -Port $Port) {
        $suggested = Find-FreePort -Start $Port
        Write-Host "[X] $Name - puerto $Port OCUPADO" -ForegroundColor Red
        if ($suggested -ne 0) {
            Write-Host "    -> Sugerencia: cambiar $VarName=$suggested en .env.deploy" -ForegroundColor Yellow
        }
        return $false
    }
    Write-Host "[OK] $Name - puerto $Port disponible" -ForegroundColor Green
    return $true
}

Write-Host ''
Write-Host '================================================================'
Write-Host ' Verificacion de puertos - MT Pricing local Docker deploy'
Write-Host '================================================================'
Write-Host ''

$caddyHttpOk = Test-PortAvailability -Name 'Caddy HTTP ' -Port ([int]$envVars.CADDY_HTTP_PORT)  -VarName 'CADDY_HTTP_PORT'
$caddyHttpsOk = Test-PortAvailability -Name 'Caddy HTTPS' -Port ([int]$envVars.CADDY_HTTPS_PORT) -VarName 'CADDY_HTTPS_PORT'
$redisOk = Test-PortAvailability -Name 'Redis      ' -Port ([int]$envVars.REDIS_HOST_PORT)  -VarName 'REDIS_HOST_PORT'

$allOk = $caddyHttpOk -and $caddyHttpsOk -and $redisOk

Write-Host ''
if ($allOk) {
    Write-Host '[OK] Todos los puertos disponibles. Listo para arrancar:' -ForegroundColor Green
    Write-Host ''
    Write-Host '    docker compose -f docker-compose.dev.yml --env-file .env.deploy up'
    Write-Host ''
    Write-Host '    BD: Supabase real (https://vayatmweveoaskyejzba.supabase.co)'
    Write-Host ''
    exit 0
}

Write-Host '[X] Hay puertos ocupados. Edita .env.deploy con las sugerencias arriba.' -ForegroundColor Red
Write-Host ''
Write-Host '    Si no existe .env.deploy todavia:'
Write-Host '      Copy-Item .env.deploy.example .env.deploy'
Write-Host '      notepad .env.deploy'
Write-Host ''
exit 1
