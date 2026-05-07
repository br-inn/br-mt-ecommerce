# =============================================================================
# validate-e2e.ps1 — Orquestador E2E Sprint 1+2 (Windows / pwsh)
# =============================================================================
# Levanta la stack local (Docker + Supabase + Next.js dev), espera health,
# corre Playwright, y opcionalmente teardown.
#
# Uso:
#   .\scripts\validate-e2e.ps1                       # full run (boot + tests + teardown frontend/backend)
#   .\scripts\validate-e2e.ps1 -SkipBoot             # asume stack ya corriendo
#   .\scripts\validate-e2e.ps1 -NoTeardown           # deja jobs vivos
#   .\scripts\validate-e2e.ps1 -Headed               # Playwright con browser visible
#   .\scripts\validate-e2e.ps1 -OnlyHealth           # smoke run: solo healthchecks
#
# Exit codes:
#   0 → todo OK
#   1 → tests fallaron
#   2 → stack no booted (preflight/health timeout)
# =============================================================================
[CmdletBinding()]
param(
  [switch]$SkipBoot,
  [switch]$NoTeardown,
  [switch]$Headed,
  [switch]$OnlyHealth,
  [int]$BootTimeoutSec = 60
)

$ErrorActionPreference = "Stop"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..")
$frontend = Join-Path $repo "mt-pricing-frontend"
$backend = Join-Path $repo "mt-pricing-backend"
$supabaseDir = Join-Path $repo "supabase"
$composeRoot = Join-Path $repo "docker-compose.dev.yml"
$composeOverlay = Join-Path $repo "infra/docker-compose.dev.yml"

# Variables de jobs (para teardown)
$script:backendJob = $null
$script:frontendJob = $null

function Section($msg) {
  Write-Host ""
  Write-Host "=== $msg ===" -ForegroundColor Cyan
}

function Need($cmd, $hint) {
  $exists = Get-Command $cmd -ErrorAction SilentlyContinue
  if (-not $exists) {
    Write-Error "Comando requerido no encontrado: $cmd. $hint"
    exit 2
  }
  $version = & $cmd --version 2>$null | Select-Object -First 1
  Write-Host "  - $cmd  $version"
}

function Wait-ForUrl([string]$Url, [int]$TimeoutSec, [string]$Label) {
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $deadline) {
    try {
      $r = Invoke-WebRequest -Uri $Url -Method GET -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
      if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 600) {
        Write-Host "  OK  $Label → HTTP $($r.StatusCode)" -ForegroundColor Green
        return $true
      }
    } catch {
      Start-Sleep -Milliseconds 1500
    }
  }
  Write-Host "  FAIL  $Label no responde tras ${TimeoutSec}s" -ForegroundColor Red
  return $false
}

function Stop-DevJobs {
  if ($script:frontendJob) {
    Write-Host "  Stopping frontend job (id=$($script:frontendJob.Id))..."
    Stop-Job $script:frontendJob -ErrorAction SilentlyContinue
    Remove-Job $script:frontendJob -Force -ErrorAction SilentlyContinue
  }
  if ($script:backendJob) {
    Write-Host "  Stopping backend job (id=$($script:backendJob.Id))..."
    Stop-Job $script:backendJob -ErrorAction SilentlyContinue
    Remove-Job $script:backendJob -Force -ErrorAction SilentlyContinue
  }
}

# -----------------------------------------------------------------------------
# 1. PRE-FLIGHT
# -----------------------------------------------------------------------------
Section "Pre-flight checks"
Need "docker" "Instala Docker Desktop."
Need "pnpm" "Instala pnpm: npm i -g pnpm"
Need "node" "Instala Node.js 20+."
# uv y supabase CLI son opcionales — solo si vamos a bootear desde cero
if (-not $SkipBoot) {
  Need "python" "Instala Python 3.11+."
  $hasUv = Get-Command "uv" -ErrorAction SilentlyContinue
  if (-not $hasUv) {
    Write-Warning "  uv no encontrado — backend asumirá venv preexistente."
  } else {
    Write-Host "  - uv $((& uv --version) 2>$null)"
  }
}

# -----------------------------------------------------------------------------
# 2. BOOT STACK (idempotente)
# -----------------------------------------------------------------------------
if (-not $SkipBoot) {
  Section "Boot stack (Docker)"

  # Compose root: redis + caddy + backend + frontend (modo container)
  if (Test-Path $composeRoot) {
    Write-Host "  Iniciando docker-compose root (redis + caddy + backend + frontend)..."
    docker compose -f $composeRoot up -d 2>&1 | Out-String | Write-Host
  } else {
    Write-Warning "  $composeRoot no existe — saltando docker compose root"
  }

  # Overlay opcional: worker-images + flower
  if (Test-Path $composeOverlay) {
    Write-Host "  Iniciando overlay (worker-images + flower)..."
    docker compose -f $composeOverlay up -d 2>&1 | Out-String | Write-Host
  }

  # Supabase local: solo si el dev lo usa (evitamos romper si no está instalado)
  $hasSupabase = Get-Command "supabase" -ErrorAction SilentlyContinue
  $supabaseRunning = $false
  if ($hasSupabase -and (Test-Path $supabaseDir)) {
    Write-Host "  Verificando supabase status..."
    Push-Location $supabaseDir
    try {
      $statusOutput = supabase status 2>&1 | Out-String
      if ($statusOutput -match "API URL") {
        Write-Host "  Supabase ya está activo." -ForegroundColor Green
        $supabaseRunning = $true
      } else {
        Write-Host "  Iniciando supabase local..."
        supabase start 2>&1 | Out-String | Write-Host
        $supabaseRunning = $true
      }
    } finally {
      Pop-Location
    }
  } else {
    Write-Warning "  supabase CLI no encontrado o supabase/ ausente — asumimos Supabase remoto / Docker."
  }
}

# -----------------------------------------------------------------------------
# 3. WAIT-FOR-READY
# -----------------------------------------------------------------------------
Section "Wait-for-ready"
$baseUrl = if ($env:E2E_BASE_URL) { $env:E2E_BASE_URL } else { "http://localhost:8080" }
$backendUrl = if ($env:E2E_BACKEND_URL) { $env:E2E_BACKEND_URL } else { $baseUrl }

$backendOk = Wait-ForUrl "$backendUrl/health/live" $BootTimeoutSec "backend (/health/live)"
$frontendOk = Wait-ForUrl "$baseUrl/" $BootTimeoutSec "frontend (/)"

if (-not ($backendOk -and $frontendOk)) {
  Write-Host ""
  Write-Host "Stack no respondió en ${BootTimeoutSec}s. Diagnóstico:" -ForegroundColor Red
  Write-Host "  - docker compose -f $composeRoot ps"
  Write-Host "  - docker compose -f $composeRoot logs backend --tail=80"
  Write-Host "  - docker compose -f $composeRoot logs frontend --tail=80"
  if (-not $NoTeardown) { Stop-DevJobs }
  exit 2
}

# -----------------------------------------------------------------------------
# 4. INSTALL PLAYWRIGHT BROWSERS (idempotente)
# -----------------------------------------------------------------------------
Section "Playwright browsers"
Push-Location $frontend
try {
  $browsersDir = Join-Path $env:USERPROFILE "AppData\Local\ms-playwright"
  $hasChromium = Test-Path (Join-Path $browsersDir "chromium-*")
  if (-not $hasChromium) {
    Write-Host "  Instalando chromium..."
    pnpm exec playwright install chromium 2>&1 | Out-String | Write-Host
  } else {
    Write-Host "  Chromium ya instalado, skip." -ForegroundColor Green
  }

  # -----------------------------------------------------------------------------
  # 5. RUN PLAYWRIGHT
  # -----------------------------------------------------------------------------
  Section "Run Playwright"
  $env:E2E_BASE_URL = $baseUrl
  $env:E2E_BACKEND_URL = $backendUrl

  $args = @("exec", "playwright", "test", "--config=tests/e2e/playwright.config.ts", "--reporter=list,html")
  if ($Headed) { $args += "--headed" }
  if ($OnlyHealth) { $args += "tests/e2e/01-healthchecks.spec.ts" }

  Write-Host "  pnpm $($args -join ' ')" -ForegroundColor Yellow
  & pnpm @args
  $testsExitCode = $LASTEXITCODE

  Section "Resultado"
  if ($testsExitCode -eq 0) {
    Write-Host "  Todos los tests OK." -ForegroundColor Green
  } else {
    Write-Host "  Hay tests fallando (exit=$testsExitCode)." -ForegroundColor Red
    $reportPath = Join-Path $frontend "playwright-report\index.html"
    if (Test-Path $reportPath) {
      Write-Host "  Abriendo report HTML: $reportPath"
      Start-Process $reportPath
    }
  }
} finally {
  Pop-Location
}

# -----------------------------------------------------------------------------
# 6. TEARDOWN
# -----------------------------------------------------------------------------
if (-not $NoTeardown) {
  Section "Teardown"
  Write-Host "  -NoTeardown no activo — bajamos jobs frontend/backend (NO supabase, NO docker)."
  Stop-DevJobs
} else {
  Write-Host ""
  Write-Host "  -NoTeardown activo — stack queda arriba para reuso." -ForegroundColor Yellow
}

exit $testsExitCode
