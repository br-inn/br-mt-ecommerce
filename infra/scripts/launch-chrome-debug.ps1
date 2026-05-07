#requires -Version 5.1
<#
.SYNOPSIS
    Abre Chrome con remote-debugging-port habilitado para conectar
    chrome-devtools-mcp.

.DESCRIPTION
    1. Cierra cualquier instancia de Chrome para no compartir profile con el normal.
    2. Levanta Chrome con --remote-debugging-port=9222 + profile aislado.
    3. Abre la URL local de la app por default.

.PARAMETER Url
    URL inicial a abrir. Default: http://localhost:8081/login.

.PARAMETER Port
    Puerto de remote debugging. Default: 9222.

.EXAMPLE
    .\infra\scripts\launch-chrome-debug.ps1
    .\infra\scripts\launch-chrome-debug.ps1 -Url "http://localhost:8081/dashboard"
    .\infra\scripts\launch-chrome-debug.ps1 -Port 9223
#>

[CmdletBinding()]
param(
    [string]$Url = "http://localhost:8081/login",
    [int]$Port = 9222
)

$ErrorActionPreference = "Stop"

# Localizar chrome.exe
$chromePaths = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "$env:ProgramFiles(x86)\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)
$chrome = $chromePaths | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chrome) {
    Write-Error "No se encontro chrome.exe en rutas conocidas. Verifica instalacion de Google Chrome."
    exit 1
}

# Cerrar instancias previas
Write-Host "[i] Cerrando instancias previas de Chrome (si las hay)..." -ForegroundColor Blue
Get-Process -Name "chrome" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

# Profile aislado en TEMP — no toca tu profile principal
$profileDir = Join-Path $env:TEMP "chrome-debug-mt"
New-Item -ItemType Directory -Force -Path $profileDir | Out-Null

Write-Host "[i] Lanzando Chrome con remote-debugging..." -ForegroundColor Blue
Write-Host "    Binary:    $chrome"
Write-Host "    Port:      $Port"
Write-Host "    Profile:   $profileDir"
Write-Host "    URL:       $Url"
Write-Host ""

$args = @(
    "--remote-debugging-port=$Port",
    "--user-data-dir=$profileDir",
    "--no-default-browser-check",
    "--no-first-run",
    "--disable-background-networking",
    $Url
)

Start-Process -FilePath $chrome -ArgumentList $args

Start-Sleep -Seconds 3

# Verificar que el debug endpoint responde
Write-Host "[i] Verificando endpoint de debug..." -ForegroundColor Blue
try {
    $r = Invoke-WebRequest -Uri "http://localhost:$Port/json/version" -UseBasicParsing -TimeoutSec 5
    $info = $r.Content | ConvertFrom-Json
    Write-Host "[OK] Chrome remote debugging activo:" -ForegroundColor Green
    Write-Host "      Browser:           $($info.Browser)"
    Write-Host "      WebSocketDebugger: $($info.webSocketDebuggerUrl)"
    Write-Host ""
    Write-Host "Listo. Iniciá una sesion de Claude Code AHORA — chrome-devtools-mcp"
    Write-Host "se conectara automaticamente."
} catch {
    Write-Warning "El endpoint :$Port/json/version no respondio. Chrome puede haber tardado en arrancar."
    Write-Warning "Esperá 5-10 segundos mas y reintentá. Si persiste, revisar logs de Chrome."
}
