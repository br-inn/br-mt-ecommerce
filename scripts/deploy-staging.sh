#!/usr/bin/env bash
# =============================================================================
# deploy-staging.sh — Deploy de imagen al servidor de staging en Hetzner
# =============================================================================
# Uso:
#   ./scripts/deploy-staging.sh <IMAGE_TAG>
#
# Variables de entorno requeridas:
#   STAGING_API_HOST    — IP o hostname del servidor API/frontend
#   STAGING_WORKER_HOST — IP o hostname del servidor worker (puede ser igual a API)
#   DEPLOY_USER         — Usuario SSH (default: deploy)
#
# El servidor debe tener Doppler configurado con `doppler configure`.
# =============================================================================
set -euo pipefail

IMAGE_TAG="${1:-latest}"
DEPLOY_USER="${DEPLOY_USER:-deploy}"
STAGING_API_HOST="${STAGING_API_HOST:?STAGING_API_HOST no está definido}"
STAGING_WORKER_HOST="${STAGING_WORKER_HOST:?STAGING_WORKER_HOST no está definido}"
APP_DIR="/opt/mt-pricing"
COMPOSE_FILE="docker-compose.staging.yml"
HEALTH_URL="https://${STAGING_DOMAIN:-staging.mt-pricing.com}/health/ready"
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10 -o BatchMode=yes"

log() { echo "[deploy] $(date -u +%Y-%m-%dT%H:%M:%SZ) $*"; }
die() { log "ERROR: $*" >&2; exit 1; }

log "=== Deploy MT Pricing Staging — tag: ${IMAGE_TAG} ==="

# ---------------------------------------------------------------------------
# Helper: ejecutar comando en servidor remoto
# ---------------------------------------------------------------------------
remote_exec() {
  local host="$1"
  shift
  # shellcheck disable=SC2086
  ssh ${SSH_OPTS} "${DEPLOY_USER}@${host}" "$@"
}

# ---------------------------------------------------------------------------
# Helper: copiar archivo al servidor remoto
# ---------------------------------------------------------------------------
remote_copy() {
  local src="$1"
  local host="$2"
  local dst="$3"
  # shellcheck disable=SC2086
  scp ${SSH_OPTS} "${src}" "${DEPLOY_USER}@${host}:${dst}"
}

# ---------------------------------------------------------------------------
# 1. Copiar docker-compose.staging.yml y Caddyfile.staging al servidor API
# ---------------------------------------------------------------------------
log "Copiando archivos de configuración al servidor API (${STAGING_API_HOST})..."
remote_copy "docker-compose.staging.yml" "${STAGING_API_HOST}" "${APP_DIR}/docker-compose.staging.yml"
remote_copy "Caddyfile.staging"          "${STAGING_API_HOST}" "${APP_DIR}/Caddyfile.staging"

# ---------------------------------------------------------------------------
# 2. Pull de imágenes en servidor API
# ---------------------------------------------------------------------------
log "Pulling imágenes (tag=${IMAGE_TAG}) en API server..."
remote_exec "${STAGING_API_HOST}" \
  "cd ${APP_DIR} && IMAGE_TAG=${IMAGE_TAG} doppler run -- \
    docker compose -f ${COMPOSE_FILE} pull"

# ---------------------------------------------------------------------------
# 3. Up del stack en servidor API
# ---------------------------------------------------------------------------
log "Levantando stack en API server..."
remote_exec "${STAGING_API_HOST}" \
  "cd ${APP_DIR} && IMAGE_TAG=${IMAGE_TAG} doppler run -- \
    docker compose -f ${COMPOSE_FILE} up -d --remove-orphans"

# ---------------------------------------------------------------------------
# 4. Copiar compose al servidor worker (si es diferente)
# ---------------------------------------------------------------------------
if [ "${STAGING_WORKER_HOST}" != "${STAGING_API_HOST}" ]; then
  log "Copiando archivos al servidor Worker (${STAGING_WORKER_HOST})..."
  remote_copy "docker-compose.staging.yml" "${STAGING_WORKER_HOST}" "${APP_DIR}/docker-compose.staging.yml"

  log "Pulling imágenes en Worker server..."
  remote_exec "${STAGING_WORKER_HOST}" \
    "cd ${APP_DIR} && IMAGE_TAG=${IMAGE_TAG} doppler run -- \
      docker compose -f ${COMPOSE_FILE} pull worker beat"

  log "Levantando worker + beat en Worker server..."
  remote_exec "${STAGING_WORKER_HOST}" \
    "cd ${APP_DIR} && IMAGE_TAG=${IMAGE_TAG} doppler run -- \
      docker compose -f ${COMPOSE_FILE} up -d --remove-orphans worker beat"
fi

# ---------------------------------------------------------------------------
# 5. Alembic migrations — ejecutar en el backend del servidor API
# ---------------------------------------------------------------------------
log "Ejecutando alembic upgrade head..."
remote_exec "${STAGING_API_HOST}" \
  "cd ${APP_DIR} && doppler run -- \
    docker compose -f ${COMPOSE_FILE} exec -T backend \
      alembic upgrade head"

# ---------------------------------------------------------------------------
# 6. Health check
# ---------------------------------------------------------------------------
log "Esperando 15s para que Caddy obtenga TLS y servicios arranquen..."
sleep 15

MAX_RETRIES=10
RETRY_INTERVAL=10
for i in $(seq 1 ${MAX_RETRIES}); do
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    --max-time 10 --retry 0 "${HEALTH_URL}" || echo "000")
  if [ "${HTTP_CODE}" = "200" ]; then
    log "Health check OK (HTTP ${HTTP_CODE}) — ${HEALTH_URL}"
    break
  fi
  if [ "${i}" -eq "${MAX_RETRIES}" ]; then
    die "Health check falló tras ${MAX_RETRIES} intentos (último HTTP ${HTTP_CODE}) — ${HEALTH_URL}"
  fi
  log "Health check intento ${i}/${MAX_RETRIES}: HTTP ${HTTP_CODE}. Reintentando en ${RETRY_INTERVAL}s..."
  sleep "${RETRY_INTERVAL}"
done

log "=== Deploy ${IMAGE_TAG} completado ==="
