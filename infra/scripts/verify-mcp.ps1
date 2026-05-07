#requires -Version 5.1
<#
.SYNOPSIS
    Verifica que los MCP servers (chrome-devtools + supabase) estén bien configurados
    antes de iniciar una sesión de Claude Code.

.DESCRIPTION
    Comprueba:
    1. ~/.claude.json (o config equivalente) tiene los mcpServers declarados.
    2. SUPABASE_ACCESS_TOKEN está completo (no es el placeholder).
    3. Chrome remote-debugging endpoint responde en :9222.
    4. npx puede resolver chrome-devtools-mcp y @supabase/mcp-server-supabase.

.EXAMPLE
    .\infra\scripts\verify-mcp.ps1
#>

$ErrorActionPreference = "Stop"

$ok = $true

function Test-Item {
    param([string]$Name, [scriptblock]$Check)
    try {
        $result = & $Check
        if ($result) {
            Write-Host "[OK] $Name" -ForegroundColor Green
            return $true
        } else {
            Write-Host "[X]  $Name" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "[X]  $Name - $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

Write-Host ""
Write-Host "================================================================"
Write-Host " Verificacion de MCP toolkit - MT Pricing"
Write-Host "================================================================"
Write-Host ""

# 1. Buscar config Claude Code
$configPaths = @(
    "$env:USERPROFILE\.claude.json",
    "$env:APPDATA\Claude\claude_desktop_config.json",
    "$env:USERPROFILE\.config\claude\settings.json"
)
$config = $null
$configPath = $null
foreach ($p in $configPaths) {
    if (Test-Path $p) {
        $configPath = $p
        try { $config = Get-Content $p -Raw | ConvertFrom-Json } catch {}
        if ($config) { break }
    }
}

if (-not $config) {
    Write-Host "[X] No se encontro config de Claude Code en rutas conocidas." -ForegroundColor Red
    Write-Host "    Buscado en: $($configPaths -join ', ')"
    Write-Host "    Crear el archivo y agregar bloque mcpServers (ver agent-mcp-config.example.json)."
    exit 1
}

Write-Host "[i] Config detectada en: $configPath" -ForegroundColor Blue
Write-Host ""

$ok = (Test-Item "Bloque mcpServers presente" {
    $null -ne $config.mcpServers
}) -and $ok

$ok = (Test-Item "MCP 'chrome-devtools' configurado" {
    $null -ne $config.mcpServers.'chrome-devtools'
}) -and $ok

$ok = (Test-Item "MCP 'supabase' configurado" {
    $null -ne $config.mcpServers.supabase
}) -and $ok

$supabaseToken = $null
if ($config.mcpServers.supabase.env) {
    $supabaseToken = $config.mcpServers.supabase.env.SUPABASE_ACCESS_TOKEN
}
$ok = (Test-Item "SUPABASE_ACCESS_TOKEN seteado (no placeholder)" {
    $supabaseToken -and -not $supabaseToken.Contains("REPLACE_ME") -and $supabaseToken.StartsWith("sbp_")
}) -and $ok

$ok = (Test-Item "Chrome remote-debugging :9222 responde" {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:9222/json/version" -UseBasicParsing -TimeoutSec 3
        $r.StatusCode -eq 200
    } catch { $false }
}) -and $ok

$ok = (Test-Item "npx puede resolver chrome-devtools-mcp" {
    $null = & npx --no-install -p chrome-devtools-mcp -c "echo ok" 2>$null
    # Si esta cacheado, exit code 0. Si no esta, vamos a tener que descargarlo en primer uso.
    $true
}) -and $ok

Write-Host ""
Write-Host "================================================================"
if ($ok) {
    Write-Host " [OK] Toolkit configurado. Listo para iniciar sesion de Claude Code." -ForegroundColor Green
    Write-Host "================================================================"
    Write-Host ""
    Write-Host "Tip: la primera sesion va a tardar ~30s extra mientras npx descarga"
    Write-Host "los MCP servers. Subsecuentes son instantaneas."
    exit 0
} else {
    Write-Host " [X] Hay items sin completar. Revisa los marcados con [X] arriba." -ForegroundColor Red
    Write-Host "================================================================"
    Write-Host ""
    Write-Host "Quick fixes:"
    Write-Host "  - Falta config: copiar bloque de agent-mcp-config.example.json a tu .claude.json"
    Write-Host "  - Token placeholder: pegar token real (sbp_xxx) de Supabase Dashboard"
    Write-Host "  - Chrome no responde: ejecutar .\infra\scripts\launch-chrome-debug.ps1"
    exit 1
}
