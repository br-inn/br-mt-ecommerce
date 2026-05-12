#!/usr/bin/env bash
# =============================================================================
# rollback-staging.sh — Rollback rápido a una imagen anterior en staging
# =============================================================================
# Uso:
#   ./scripts/rollback-staging.sh <ROLLBACK_TAG>
#
# Target: < 2 minutos (AC US-1A-IAC-01-DEPLOY)
#
# Variables de entorno requeridas:
#   STAGING_API_HOST    — IP o hostname del servidor API/frontend
#   STAGING_WORKER_HOST — IP o hostname del servidor worker
#   DEPLOY_USER         — Usuario SSH (default: deploy)
# =============================================================================
set -euo pipefail

ROLLBACK_TAG="${1:?Uso: rollback-staging.sh <tag>  — ejemplo: rollback-staging.sh 1.2.2}"
DEPLOY_USER="${DEPLOY_USER:-deploy}"
STAGING_API_HOST="${STAGING_API_HOST:?STAGING_API_HOST no está definido}"
STAGING_WORKER_HOST="${STAGING_WORKER_HOST:?STAGING_WORKER_HOST no está definido}"
APP_DIR="/opt/mt-pricing"
COMPOSE_FILE="docker-compose.staging.yml"
HEALTH_URL="https://${STAGING_DOMAIN:-staging.mt-pricing.com}/health/ready"
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10 -o BatchMode=yes"

log() { echo "[rollback] $(date -u +%Y-%m-%dT%H:%M:%SZ) $*"; }
die() { log "ERROR: $*" >&2; exit 1; }

log "=== Rollback MT Pricing Staging → tag: ${ROLLBACK_TAG} ==="
ROLLBACK_START=$(date +%s)

remote_exec() {
  local host="$1"
  shift
  # shellcheck disable=SC2086
  ssh ${SSH_OPTS} "${DEPLOY_USER}@${host}" "$@"
}

# ---------------------------------------------------------------------------
# 1. Pull de la imagen de rollback en servidor API (imágenes ya en registro)
# ---------------------------------------------------------------------------
log "Pulling imagen ${ROLLBACK_TAG} en API server..."
remote_exec "${STAGING_API_HOST}" \
  "cd ${APP_DIR} && IMAGE_TAG=${ROLLBACK_TAG} doppler run -- \
    docker compose -f ${COMPOSE_FILE} pull"

# ---------------------------------------------------------------------------
# 2. Up con tag de rollback en servidor API
# ---------------------------------------------------------------------------
log "Restaurando stack en API server..."
remote_exec "${STAGING_API_HOST}" \
  "cd ${APP_DIR} && IMAGE_TAG=${ROLLBACK_TAG} doppler run -- \
    docker compose -f ${COMPOSE_FILE} up -d --remove-orphans"

# ---------------------------------------------------------------------------
# 3. Worker server (si es diferente)
# ---------------------------------------------------------------------------
if [ "${STAGING_WORKER_HOST}" != "${STAGING_API_HOST}" ]; then
  log "Restaurando worker + beat en Worker server..."
  remote_exec "${STAGING_WORKER_HOST}" \
    "cd ${APP_DIR} && IMAGE_TAG=${ROLLBACK_TAG} doppler run -- \
      docker compose -f ${COMPOSE_FILE} pull worker beat"
  remote_exec "${STAGING_WORKER_HOST}" \
    "cd ${APP_DIR} && IMAGE_TAG=${ROLLBACK_TAG} doppler run -- \
      docker compose -f ${COMPOSE_FILE} up -d --remove-orphans worker beat"
fi

# ---------------------------------------------------------------------------
# 4. NO ejecutar alembic downgrade automáticamente (requiere intervención manual
#    si el rollback cruza una migración de schema).
# ---------------------------------------------------------------------------
log "AVISO: Alembic NO se revirtió automáticamente."
log "       Si la migración cambió schema, ejecutar manualmente:"
log "       doppler run -- docker compose exec backend alembic downgrade -1"

# ---------------------------------------------------------------------------
# 5. Health check rápido (target < 2 min total)
# ---------------------------------------------------------------------------
log "Health check post-rollback..."
MAX_RETRIES=6
RETRY_INTERVAL=8
for i in $(seq 1 ${MAX_RETRIES}); do
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    --max-time 8 --retry 0 "${HEALTH_URL}" || echo "000")
  if [ "${HTTP_CODE}" = "200" ]; then
    ROLLBACK_END=$(date +%s)
    ELAPSED=$(( ROLLBACK_END - ROLLBACK_START ))
    log "Health check OK (HTTP ${HTTP_CODE}) — rollback completado en ${ELAPSED}s"
    break
  fi
  if [ "${i}" -eq "${MAX_RETRIES}" ]; then
    die "Health check falló tras ${MAX_RETRIES} intentos (último HTTP ${HTTP_CODE})"
  fi
  log "Intento ${i}/${MAX_RETRIES}: HTTP ${HTTP_CODE}. Reintentando en ${RETRY_INTERVAL}s..."
  sleep "${RETRY_INTERVAL}"
done

log "=== Rollback a ${ROLLBACK_TAG} completado ==="
