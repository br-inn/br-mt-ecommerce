#!/usr/bin/env bash
# =============================================================================
# check-ports.sh — Verifica puertos disponibles para deploy local Docker
# =============================================================================
# Uso: ./infra/scripts/check-ports.sh
# Output: estado de cada puerto + sugerencia si está ocupado.
# Exit 0 si todos disponibles; 1 si algún puerto está ocupado.
#
# Stack local: solo Caddy (HTTP+HTTPS) + Redis exponen puertos al host.
# La BD (Postgres) vive en Supabase real — no requiere puerto local.
# =============================================================================

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ENV_FILE="${1:-$(dirname "$0")/../../.env.deploy}"
if [[ -f "$ENV_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    echo -e "${BLUE}[i] Usando configuración de: $ENV_FILE${NC}"
else
    echo -e "${YELLOW}[!] No existe .env.deploy — usando defaults del docker-compose${NC}"
fi

CADDY_HTTP_PORT="${CADDY_HTTP_PORT:-8080}"
CADDY_HTTPS_PORT="${CADDY_HTTPS_PORT:-8443}"
REDIS_HOST_PORT="${REDIS_HOST_PORT:-6379}"

detect_port_in_use() {
    local port=$1
    if command -v lsof >/dev/null 2>&1; then
        lsof -i ":$port" -sTCP:LISTEN -t >/dev/null 2>&1
    elif command -v ss >/dev/null 2>&1; then
        ss -lntH "sport = :$port" 2>/dev/null | grep -q .
    elif command -v netstat >/dev/null 2>&1; then
        netstat -an 2>/dev/null | grep -q "[.:]$port .*LISTEN"
    else
        (echo > "/dev/tcp/127.0.0.1/$port") >/dev/null 2>&1
    fi
}

find_free_port() {
    local start=$1
    for i in $(seq 0 20); do
        local candidate=$((start + i))
        if ! detect_port_in_use "$candidate"; then
            echo "$candidate"
            return 0
        fi
    done
    echo "0"
}

check_port() {
    local name=$1
    local port=$2
    local var_name=$3
    if detect_port_in_use "$port"; then
        local suggested
        suggested=$(find_free_port "$((port + 1))")
        echo -e "${RED}[✗] $name — puerto $port OCUPADO${NC}"
        if [[ "$suggested" != "0" ]]; then
            echo -e "    ${YELLOW}→ Sugerencia: cambiar $var_name=$suggested en .env.deploy${NC}"
        fi
        return 1
    else
        echo -e "${GREEN}[✓] $name — puerto $port disponible${NC}"
        return 0
    fi
}

echo ""
echo "================================================================"
echo " Verificación de puertos — MT Pricing local Docker deploy"
echo "================================================================"
echo ""

ALL_OK=0
check_port "Caddy HTTP " "$CADDY_HTTP_PORT" "CADDY_HTTP_PORT" || ALL_OK=1
check_port "Caddy HTTPS" "$CADDY_HTTPS_PORT" "CADDY_HTTPS_PORT" || ALL_OK=1
check_port "Redis      " "$REDIS_HOST_PORT" "REDIS_HOST_PORT" || ALL_OK=1

echo ""
if [[ $ALL_OK -eq 0 ]]; then
    echo -e "${GREEN}✓ Todos los puertos disponibles. Listo para arrancar:${NC}"
    echo ""
    echo "    docker compose -f docker-compose.dev.yml --env-file .env.deploy up"
    echo ""
    echo "    BD: Supabase real (https://vayatmweveoaskyejzba.supabase.co)"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Hay puertos ocupados. Editá .env.deploy con las sugerencias arriba.${NC}"
    echo ""
    echo "    Si no existe .env.deploy todavía:"
    echo "      cp .env.deploy.example .env.deploy"
    echo "      \$EDITOR .env.deploy"
    echo ""
    exit 1
fi
