#!/usr/bin/env bash
# openapi-gen.sh — regenera lib/api/types.ts desde el spec backend (US-1A-DEV-01).
#
# Estrategia:
#   1. Si MT_API_BASE está set (e.g. http://localhost:8000), pulla /openapi.json en runtime.
#   2. Si no, llama scripts/export_openapi.py del backend (via uv run o python).
#   3. openapi-typescript genera lib/api/types.ts.
#
# Uso:
#   ./scripts/openapi-gen.sh                 # static (export_openapi.py)
#   MT_API_BASE=http://localhost:8000 ./scripts/openapi-gen.sh   # runtime pull

set -euo pipefail

FRONTEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${FRONTEND_DIR}/.." && pwd)"
BACKEND_DIR="${REPO_ROOT}/mt-pricing-backend"
SPEC_OUT="${REPO_ROOT}/_bmad-output/planning-artifacts/mt-api-contract-openapi.json"
TYPES_OUT="${FRONTEND_DIR}/lib/api/types.ts"

if [[ -n "${MT_API_BASE:-}" ]]; then
  echo "[openapi-gen] pulling spec from ${MT_API_BASE}/openapi.json"
  curl -fsSL "${MT_API_BASE}/openapi.json" -o "${SPEC_OUT}"
else
  echo "[openapi-gen] exporting via backend script"
  if command -v uv >/dev/null 2>&1; then
    (cd "${BACKEND_DIR}" && uv run python -m app.scripts.export_openapi --out "${SPEC_OUT}")
  elif docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^mt-backend$'; then
    docker exec mt-backend python /app/app/scripts/export_openapi.py --out /tmp/mt-openapi.json
    docker cp mt-backend:/tmp/mt-openapi.json "${SPEC_OUT}"
  else
    (cd "${BACKEND_DIR}" && python -m app.scripts.export_openapi --out "${SPEC_OUT}")
  fi
fi

echo "[openapi-gen] generating ${TYPES_OUT}"
cd "${FRONTEND_DIR}"
npx --yes openapi-typescript "${SPEC_OUT}" -o "${TYPES_OUT}"

echo "[openapi-gen] done — paths=$(jq -r '.paths | length' "${SPEC_OUT}" 2>/dev/null || echo '?')"
