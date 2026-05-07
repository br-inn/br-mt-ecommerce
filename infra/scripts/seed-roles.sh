#!/usr/bin/env bash
# =============================================================================
# seed-roles.sh — placeholder
# =============================================================================
# Idempotently create the application's RBAC roles + permissions in Postgres.
# Run once after migrations on a fresh environment, and again whenever the
# canonical role list (in code) changes.
#
# Reference: mt-users-module-design.md.
# =============================================================================
set -euo pipefail

# TODO(infra-sprint-1): call backend management command, e.g.
#   uv run python -m app.cli seed-roles
echo "seed-roles.sh: placeholder — Sprint 0"
exit 0
