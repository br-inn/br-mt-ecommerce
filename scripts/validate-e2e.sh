#!/usr/bin/env bash
# =============================================================================
# validate-e2e.sh — Orquestador E2E Sprint 1+2 (Linux / WSL / macOS)
# =============================================================================
# Equivalente a validate-e2e.ps1. Mantener paridad de flags.
#
# Uso:
#   ./scripts/validate-e2e.sh                       # full run
#   ./scripts/validate-e2e.sh --skip-boot           # asume stack ya corriendo
#   ./scripts/validate-e2e.sh --no-teardown         # deja stack viva
#   ./scripts/validate-e2e.sh --headed              # Playwright con browser
#   ./scripts/validate-e2e.sh --only-health         # smoke run
#
# Exit codes:
#   0 → tests OK
#   1 → tests fail
#   2 → stack no booted
# =============================================================================
set -euo pipefail

SKIP_BOOT=0
NO_TEARDOWN=0
HEADED=0
ONLY_HEALTH=0
BOOT_TIMEOUT=60

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-boot) SKIP_BOOT=1 ;;
    --no-teardown) NO_TEARDOWN=1 ;;
    --headed) HEADED=1 ;;
    --only-health) ONLY_HEALTH=1 ;;
    --boot-timeout) BOOT_TIMEOUT="$2"; shift ;;
    -h|--help)
      grep '^#' "$0" | head -30
      exit 0
      ;;
    *) echo "Flag desconocido: $1" >&2; exit 2 ;;
  esac
  shift
done

# Resolver paths absolutos
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND="$REPO/mt-pricing-frontend"
SUPABASE_DIR="$REPO/supabase"
COMPOSE_ROOT="$REPO/docker-compose.dev.yml"
COMPOSE_OVERLAY="$REPO/infra/docker-compose.dev.yml"

cyan() { printf "\033[36m%s\033[0m\n" "$*"; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
red() { printf "\033[31m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }

section() { echo; cyan "=== $* ==="; }

need() {
  local cmd="$1" hint="$2"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    red "Comando requerido no encontrado: $cmd. $hint"
    exit 2
  fi
  local v
  v="$("$cmd" --version 2>/dev/null | head -1)"
  echo "  - $cmd  $v"
}

wait_for_url() {
  local url="$1" timeout="$2" label="$3"
  local deadline=$(( $(date +%s) + timeout ))
  while [[ $(date +%s) -lt $deadline ]]; do
    local code
    code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 3 "$url" 2>/dev/null || echo 0)"
    if [[ "$code" =~ ^[2-5][0-9][0-9]$ ]]; then
      green "  OK  $label → HTTP $code"
      return 0
    fi
    sleep 1.5
  done
  red "  FAIL  $label no responde tras ${timeout}s"
  return 1
}

# -----------------------------------------------------------------------------
# 1. PRE-FLIGHT
# -----------------------------------------------------------------------------
section "Pre-flight checks"
need docker "Instala Docker."
need pnpm "Instala pnpm: npm i -g pnpm"
need node "Instala Node.js 20+."
need curl "Necesario para healthchecks."
if [[ $SKIP_BOOT -eq 0 ]]; then
  need python3 "Instala Python 3.11+."
  if ! command -v uv >/dev/null 2>&1; then
    yellow "  uv no encontrado — backend asumirá venv preexistente."
  fi
fi

# -----------------------------------------------------------------------------
# 2. BOOT STACK
# -----------------------------------------------------------------------------
if [[ $SKIP_BOOT -eq 0 ]]; then
  section "Boot stack (Docker)"
  if [[ -f "$COMPOSE_ROOT" ]]; then
    echo "  Iniciando docker-compose root..."
    docker compose -f "$COMPOSE_ROOT" up -d
  fi
  if [[ -f "$COMPOSE_OVERLAY" ]]; then
    echo "  Iniciando overlay (worker-images + flower)..."
    docker compose -f "$COMPOSE_OVERLAY" up -d || true
  fi

  if command -v supabase >/dev/null 2>&1 && [[ -d "$SUPABASE_DIR" ]]; then
    echo "  Verificando supabase status..."
    pushd "$SUPABASE_DIR" >/dev/null
    if supabase status 2>&1 | grep -q "API URL"; then
      green "  Supabase ya está activo."
    else
      echo "  Iniciando supabase local..."
      supabase start || true
    fi
    popd >/dev/null
  else
    yellow "  supabase CLI no disponible — asumimos Supabase remoto / Docker."
  fi
fi

# -----------------------------------------------------------------------------
# 3. WAIT-FOR-READY
# -----------------------------------------------------------------------------
section "Wait-for-ready"
BASE_URL="${E2E_BASE_URL:-http://localhost:8080}"
BACKEND_URL="${E2E_BACKEND_URL:-$BASE_URL}"

backend_ok=0
frontend_ok=0
wait_for_url "$BACKEND_URL/health/live" "$BOOT_TIMEOUT" "backend (/health/live)" && backend_ok=1
wait_for_url "$BASE_URL/" "$BOOT_TIMEOUT" "frontend (/)" && frontend_ok=1

if [[ $backend_ok -ne 1 || $frontend_ok -ne 1 ]]; then
  echo
  red "Stack no respondió en ${BOOT_TIMEOUT}s. Diagnóstico:"
  echo "  - docker compose -f $COMPOSE_ROOT ps"
  echo "  - docker compose -f $COMPOSE_ROOT logs backend --tail=80"
  echo "  - docker compose -f $COMPOSE_ROOT logs frontend --tail=80"
  exit 2
fi

# -----------------------------------------------------------------------------
# 4. PLAYWRIGHT BROWSERS
# -----------------------------------------------------------------------------
section "Playwright browsers"
cd "$FRONTEND"
if ! pnpm exec playwright --version >/dev/null 2>&1; then
  red "  playwright no instalado en mt-pricing-frontend. Ejecuta pnpm install primero."
  exit 2
fi
# Idempotente — si chromium ya está, no descarga
pnpm exec playwright install chromium >/dev/null 2>&1 || true

# -----------------------------------------------------------------------------
# 5. RUN PLAYWRIGHT
# -----------------------------------------------------------------------------
section "Run Playwright"
export E2E_BASE_URL="$BASE_URL"
export E2E_BACKEND_URL="$BACKEND_URL"

PW_ARGS=(--config=tests/e2e/playwright.config.ts --reporter=list,html)
[[ $HEADED -eq 1 ]] && PW_ARGS+=(--headed)
[[ $ONLY_HEALTH -eq 1 ]] && PW_ARGS+=(tests/e2e/01-healthchecks.spec.ts)

echo "  pnpm exec playwright test ${PW_ARGS[*]}"
set +e
pnpm exec playwright test "${PW_ARGS[@]}"
TESTS_EXIT=$?
set -e

section "Resultado"
if [[ $TESTS_EXIT -eq 0 ]]; then
  green "  Todos los tests OK."
else
  red "  Hay tests fallando (exit=$TESTS_EXIT)."
  REPORT="$FRONTEND/playwright-report/index.html"
  if [[ -f "$REPORT" ]]; then
    echo "  Report HTML: $REPORT"
    if command -v xdg-open >/dev/null 2>&1; then
      xdg-open "$REPORT" >/dev/null 2>&1 &
    elif command -v open >/dev/null 2>&1; then
      open "$REPORT" >/dev/null 2>&1 &
    fi
  fi
fi

# -----------------------------------------------------------------------------
# 6. TEARDOWN (placeholder — Docker queda arriba para reuso, alineado con .ps1)
# -----------------------------------------------------------------------------
if [[ $NO_TEARDOWN -eq 1 ]]; then
  yellow "  --no-teardown activo — stack queda arriba."
fi

exit $TESTS_EXIT
