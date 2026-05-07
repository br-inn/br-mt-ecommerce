#!/usr/bin/env bash
# =============================================================================
# dev-down.sh — Para el stack local Docker
# =============================================================================
# Uso:
#   ./infra/scripts/dev-down.sh        # Stop, preserva volúmenes
#   ./infra/scripts/dev-down.sh -v     # Stop + BORRA volúmenes (datos Postgres/Redis)
# =============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

if [[ ! -f ".env.deploy" ]]; then
    echo "[!] .env.deploy no existe — usando defaults." >&2
fi

echo "[i] Parando docker compose..."
docker compose -f docker-compose.dev.yml --env-file .env.deploy down "$@"

if [[ "$*" == *"-v"* ]] || [[ "$*" == *"--volumes"* ]]; then
    echo "[!] Volúmenes BORRADOS — datos Postgres + Redis perdidos."
fi
