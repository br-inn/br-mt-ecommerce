#!/usr/bin/env bash
# =============================================================================
# Doppler bootstrap — workspace MT (US-1A-IAC-01)
# =============================================================================
# Crea la estructura de project + configs en Doppler workspace MT y valida
# que los secrets canónicos (ver `infra/terraform/secrets.tf::expected_secrets`)
# estén seedeados. Si falta alguno, falla con lista clara.
#
# Idempotente — se puede ejecutar N veces sin riesgo.
#
# Pre-requisitos:
#   - Doppler CLI instalado y autenticado (`doppler login`).
#   - Permisos owner/admin en workspace MT.
# =============================================================================
set -euo pipefail

PROJECT="${DOPPLER_PROJECT:-mt-pricing}"
CONFIGS=("dev" "staging" "prd")

# Lista canónica — debe coincidir con `infra/terraform/secrets.tf::expected_secrets`.
EXPECTED_SECRETS=(
  DATABASE_URL SUPABASE_URL SUPABASE_ANON_KEY SUPABASE_SERVICE_ROLE_KEY
  JWT_SECRET JWKS_URL REDIS_URL CELERY_BROKER_URL
  SENTRY_DSN SENTRY_DSN_BACKEND SENTRY_DSN_WORKER SENTRY_DSN_FRONTEND
  BETTER_STACK_LOGS_TOKEN BETTER_STACK_LOGS_HOST
  BRIGHT_DATA_API_KEY GEMINI_API_KEY OPENAI_API_KEY
  SP_API_REFRESH_TOKEN SP_API_LWA_CLIENT_ID SP_API_LWA_CLIENT_SECRET
  AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
  HCLOUD_TOKEN CLOUDFLARE_API_TOKEN CLOUDFLARE_ZONE_ID
)

log()  { printf '\033[1;34m[doppler-bootstrap]\033[0m %s\n' "$*" >&2; }
fail() { printf '\033[1;31m[doppler-bootstrap ERROR]\033[0m %s\n' "$*" >&2; exit 1; }

command -v doppler >/dev/null 2>&1 || fail "Doppler CLI no instalado. Instala: https://docs.doppler.com/docs/install-cli"
doppler me >/dev/null 2>&1 || fail "No autenticado. Corre: doppler login"

log "Project objetivo: $PROJECT"

# 1. Crear project si no existe
if ! doppler projects get "$PROJECT" >/dev/null 2>&1; then
  log "Creando project $PROJECT ..."
  doppler projects create "$PROJECT" \
    --description "MT Middle East — Pricing & MDM platform" \
    || fail "No se pudo crear project $PROJECT"
else
  log "Project $PROJECT ya existe — skip create."
fi

# 2. Crear configs (dev, staging, prd) si no existen
for cfg in "${CONFIGS[@]}"; do
  if ! doppler configs get "$cfg" --project "$PROJECT" >/dev/null 2>&1; then
    log "Creando config $cfg ..."
    doppler configs create "$cfg" --project "$PROJECT" \
      || fail "No se pudo crear config $cfg"
  else
    log "Config $cfg ya existe — skip."
  fi
done

# 3. Validar secrets seedeados — sólo en `staging` y `prd` (dev = local)
MISSING_SUMMARY=""
for cfg in staging prd; do
  log "Validando secrets en $PROJECT/$cfg ..."
  EXISTING=$(doppler secrets --project "$PROJECT" --config "$cfg" --json 2>/dev/null \
    | jq -r 'keys[]' || echo "")
  MISSING=()
  for secret in "${EXPECTED_SECRETS[@]}"; do
    if ! grep -qx "$secret" <<< "$EXISTING"; then
      MISSING+=("$secret")
    fi
  done
  if (( ${#MISSING[@]} > 0 )); then
    log "ATENCIÓN: secrets faltantes en $cfg: ${MISSING[*]}"
    MISSING_SUMMARY+="${cfg}: ${MISSING[*]}\n"
  else
    log "$cfg OK — todos los secrets canónicos presentes."
  fi
done

if [[ -n "$MISSING_SUMMARY" ]]; then
  log ""
  log "Resumen secrets faltantes:"
  printf "%b\n" "$MISSING_SUMMARY"
  log "Seedea con: doppler secrets set --project $PROJECT --config <env> KEY=VALUE"
  log "Bootstrap completado con WARNINGS — Terraform apply fallará hasta cubrir."
  exit 0
fi

log "Bootstrap completado — todos los secrets seedeados correctamente."
