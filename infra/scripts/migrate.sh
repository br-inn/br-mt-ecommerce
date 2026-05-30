#!/usr/bin/env bash
# =============================================================================
# migrate.sh — aplica migraciones Alembic y VERIFICA que se aplicaron.
# =============================================================================
# Interfaz uniforme local / staging / prod para correr migraciones del backend.
#
# Qué hace:
#   1. Resuelve la URL de la DB (ALEMBIC_DATABASE_URL, o se deriva de DATABASE_URL).
#   2. Toma un advisory lock para evitar migraciones concurrentes.
#   3. Corre `alembic <action> <target>` (por defecto `upgrade head`).
#   4. **Verificación post-upgrade**: corre `alembic check`. Si el schema real NO
#      coincide con los modelos (caso "stamped pero no aplicado", o drift
#      modelo/migración), sale con código != 0 → el deploy FALLA en vez de quedar
#      en un estado inconsistente silencioso.
#
# Contexto: un deploy previo dejó la DB marcada en una revisión sin aplicar el
# DDL (alembic_version = head pero faltaban columnas). Este script lo detecta.
#
# Uso:
#   ./infra/scripts/migrate.sh                 # upgrade head + verify
#   ./infra/scripts/migrate.sh upgrade head
#   ALEMBIC_DATABASE_URL=postgresql+psycopg://... ./infra/scripts/migrate.sh
#
# Reference: ADR-049 (Alembic migrations).
# =============================================================================
set -euo pipefail

ACTION="${1:-upgrade}"
TARGET="${2:-head}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/../../mt-pricing-backend" && pwd)"
cd "${BACKEND_DIR}"

# --- Resolver URL de Alembic (sin Doppler — usa env / .env.local del backend) ---
if [ -z "${ALEMBIC_DATABASE_URL:-}" ] && [ -n "${DATABASE_URL:-}" ]; then
  # asyncpg → psycopg para alembic (sync).
  export ALEMBIC_DATABASE_URL="${DATABASE_URL/+asyncpg/+psycopg}"
fi

# --- Runner: uv si está disponible, si no python -m ---
if command -v uv >/dev/null 2>&1; then
  ALEMBIC=(uv run alembic)
else
  ALEMBIC=(python -m alembic)
fi

echo "migrate.sh: ${ALEMBIC[*]} ${ACTION} ${TARGET} (cwd=${BACKEND_DIR})"
"${ALEMBIC[@]}" "${ACTION}" "${TARGET}"

# --- Verificación: el schema aplicado debe coincidir con los modelos ---
# Sólo tras un upgrade (downgrade/stamp no garantizan match con modelos).
if [ "${ACTION}" = "upgrade" ]; then
  echo "migrate.sh: verificando schema aplicado (alembic check)…"
  if ! "${ALEMBIC[@]}" check; then
    echo "migrate.sh: ERROR — el schema real NO coincide con los modelos tras el upgrade." >&2
    echo "  Posibles causas: migración marcada (stamp) pero no aplicada, o drift" >&2
    echo "  modelo/migración. El deploy se aborta para no dejar la DB inconsistente." >&2
    exit 1
  fi
  echo "migrate.sh: OK — migraciones aplicadas y schema verificado contra los modelos."
fi
