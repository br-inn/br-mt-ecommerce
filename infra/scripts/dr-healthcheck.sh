#!/usr/bin/env bash
# dr-healthcheck.sh — verifica que los pre-requisitos DR siguen sanos.
# Sprint 6 (US-1B-05-04). Cada 15 min vía cron o systemd timer.
# exit 0 = OK; exit 1 = al menos un check failed.
#
# Variables de entorno:
#   PG_DUMP_DIR        — directorio donde caen los pg_dump (default /var/backups/postgres)
#   PG_DUMP_MAX_AGE_H  — edad máxima del dump más reciente, default 26h
#   BACKEND_URL        — URL backend para healthchecks (default http://localhost:8000)
#   CADDY_URL          — URL Caddy (default http://localhost)
#   SENTRY_DSN_HOST    — host Sentry para verificar ingest (opcional)
#   STORAGE_REPLICA_LAG_MAX_S — default 60
#   BEAT_HEARTBEAT_KEY — Redis key del beat heartbeat (default mt:beat:heartbeat)

set -uo pipefail

PG_DUMP_DIR="${PG_DUMP_DIR:-/var/backups/postgres}"
PG_DUMP_MAX_AGE_H="${PG_DUMP_MAX_AGE_H:-26}"
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
CADDY_URL="${CADDY_URL:-http://localhost}"
STORAGE_REPLICA_LAG_MAX_S="${STORAGE_REPLICA_LAG_MAX_S:-60}"
BEAT_HEARTBEAT_KEY="${BEAT_HEARTBEAT_KEY:-mt:beat:heartbeat}"

failures=0
log_ok()   { printf '[OK]   %s\n' "$*"; }
log_fail() { printf '[FAIL] %s\n' "$*"; failures=$((failures + 1)); }
log_warn() { printf '[WARN] %s\n' "$*"; }

check_pg_dump() {
  if [[ ! -d "$PG_DUMP_DIR" ]]; then
    log_fail "pg_dump dir not present: $PG_DUMP_DIR"
    return
  fi
  latest=$(ls -1t "$PG_DUMP_DIR"/*.dump 2>/dev/null | head -1 || true)
  if [[ -z "$latest" ]]; then
    log_fail "no .dump file in $PG_DUMP_DIR"
    return
  fi
  age_s=$(( $(date +%s) - $(stat -c %Y "$latest") ))
  age_h=$(( age_s / 3600 ))
  if (( age_h > PG_DUMP_MAX_AGE_H )); then
    log_fail "pg_dump stale ${age_h}h > ${PG_DUMP_MAX_AGE_H}h ($latest)"
  else
    size=$(du -h "$latest" | cut -f1)
    log_ok "pg_dump ${age_h}h ago ($(basename "$latest"), $size)"
  fi
}

check_http() {
  local label="$1" url="$2" expected="${3:-200}"
  code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 "$url" 2>/dev/null || echo "000")
  if [[ "$code" == "$expected" ]]; then
    log_ok "$label: $code"
  else
    log_fail "$label: expected $expected got $code ($url)"
  fi
}

check_beat_heartbeat() {
  if ! command -v redis-cli >/dev/null 2>&1; then
    log_warn "redis-cli no disponible — skip beat heartbeat"
    return
  fi
  ts=$(redis-cli GET "$BEAT_HEARTBEAT_KEY" 2>/dev/null || true)
  if [[ -z "$ts" ]]; then
    log_fail "beat heartbeat ausente ($BEAT_HEARTBEAT_KEY)"
    return
  fi
  now=$(date +%s)
  age_s=$(( now - ts ))
  age_min=$(( age_s / 60 ))
  if (( age_min > 6 )); then
    log_fail "beat heartbeat stale ${age_min}m > 6m"
  else
    log_ok "beat.heartbeat ${age_min}m ago"
  fi
}

check_pg_dump
check_http "caddy" "$CADDY_URL/healthz" 200
check_http "backend.db" "$BACKEND_URL/api/v1/healthz/db" 200
check_http "backend.redis" "$BACKEND_URL/healthz/redis" 200
check_beat_heartbeat

if (( failures > 0 )); then
  printf '\nDR healthcheck FAILED — %d checks did not pass.\n' "$failures" >&2
  exit 1
fi

printf '\nDR healthcheck PASSED — all checks green.\n'
exit 0
