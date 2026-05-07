#!/usr/bin/env bash
# =============================================================================
# deploy.sh — placeholder
# =============================================================================
# Deploy the application stack (backend image, frontend bundle, migrations) to
# the target environment.
#
# Real implementation lives in Sprint 1. Expected flow:
#   1. Validate Doppler context.
#   2. Pull signed images (cosign verify) from GHCR.
#   3. Run migrations via migrate.sh (idempotent).
#   4. Rolling restart docker compose services on the host.
#   5. Smoke-test /health/* endpoints.
#
# Usage (target):
#   ./deploy.sh --env prod --tag sha-abcdef
# =============================================================================
set -euo pipefail

# TODO(infra-sprint-1): implement real deploy.
echo "deploy.sh: placeholder — Sprint 0"
echo "Args received: $*"
exit 0
