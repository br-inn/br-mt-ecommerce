#!/usr/bin/env bash
# =============================================================================
# dev-up.sh — Arranca el stack local en Docker (Caddy entry point único)
# =============================================================================
# 1. Verifica puertos disponibles (corre check-ports.sh).
# 2. Asegura que .env.deploy existe (lo crea desde template si falta).
# 3. Asegura que mt-pricing-backend/.env y mt-pricing-frontend/.env.local existen.
# 4. Arranca docker compose con --env-file .env.deploy.
#
# Uso:
#   ./infra/scripts/dev-up.sh           # Foreground
#   ./infra/scripts/dev-up.sh --build   # Rebuild antes de arrancar
#   ./infra/scripts/dev-up.sh -d        # Detach (background)
# =============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 1. Asegurar .env.deploy
if [[ ! -f ".env.deploy" ]]; then
    echo -e "${YELLOW}[!] .env.deploy no existe — creándolo desde template${NC}"
    cp .env.deploy.example .env.deploy
fi

# 2. Asegurar .env de backend y frontend
if [[ ! -f "mt-pricing-backend/.env" ]]; then
    echo -e "${YELLOW}[!] mt-pricing-backend/.env no existe — creándolo desde template${NC}"
    cp mt-pricing-backend/.env.example mt-pricing-backend/.env
fi

if [[ ! -f "mt-pricing-frontend/.env.local" ]]; then
    echo -e "${YELLOW}[!] mt-pricing-frontend/.env.local no existe — creándolo desde template${NC}"
    cp mt-pricing-frontend/.env.example mt-pricing-frontend/.env.local
fi

# 3. Verificar puertos disponibles
echo -e "${BLUE}[i] Verificando puertos disponibles...${NC}"
if ! ./infra/scripts/check-ports.sh; then
    echo -e "${YELLOW}[!] Hay puertos ocupados — editá .env.deploy con las sugerencias arriba y reintentá.${NC}"
    exit 1
fi

# 4. Cargar puertos para mostrar URLs al final
# shellcheck disable=SC1091
source .env.deploy

# 5. Arrancar docker compose
echo -e "${BLUE}[i] Arrancando docker compose...${NC}"
docker compose -f docker-compose.dev.yml --env-file .env.deploy up "$@"

# Si fue detach mode, mostrar URLs
if [[ "$*" == *"-d"* ]] || [[ "$*" == *"--detach"* ]]; then
    echo ""
    echo -e "${GREEN}[OK] Stack arrancado en modo detach.${NC}"
    echo ""
    echo "  App:        http://localhost:${CADDY_HTTP_PORT:-8080}"
    echo "  API docs:   http://localhost:${CADDY_HTTP_PORT:-8080}/docs"
    echo "  Healthcheck: http://localhost:${CADDY_HTTP_PORT:-8080}/health/live"
    echo "  Redis:      localhost:${REDIS_HOST_PORT:-6379}"
    echo "  BD:         Supabase real (https://vayatmweveoaskyejzba.supabase.co)"
    echo ""
    echo "Logs:    docker compose -f docker-compose.dev.yml --env-file .env.deploy logs -f"
    echo "Parar:   ./infra/scripts/dev-down.sh"
    echo ""
fi
