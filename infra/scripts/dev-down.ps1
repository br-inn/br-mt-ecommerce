#requires -Version 5.1
<#
.SYNOPSIS
    Stops the local Docker stack.

.PARAMETER Volumes
    Also remove named volumes (deletes Postgres + Redis data).

.EXAMPLE
    .\infra\scripts\dev-down.ps1
    .\infra\scripts\dev-down.ps1 -Volumes
#>

[CmdletBinding()]
param(
    [switch]$Volumes
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repoRoot

if (-not (Test-Path '.env.deploy')) {
    Write-Warning '.env.deploy no existe - usando defaults.'
}

$composeArgs = @('compose', '-f', 'docker-compose.dev.yml', '--env-file', '.env.deploy', 'down')
if ($Volumes) { $composeArgs += '-v' }

Write-Host '[i] Parando docker compose...' -ForegroundColor Blue
& docker @composeArgs

if ($Volumes) {
    Write-Host '[!] Volumenes BORRADOS - datos Postgres + Redis perdidos.' -ForegroundColor Yellow
}
