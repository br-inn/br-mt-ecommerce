#!/usr/bin/env bash
# =============================================================================
# backup.sh — placeholder
# =============================================================================
# Run `pg_dump` against the production database, encrypt with age, and ship to
# Hetzner Object Storage. Triggered by cron on the prod host.
#
# Retention: 7 daily, 4 weekly, 12 monthly (per DR runbook).
# Reference: mt-dr-runbooks-sla-design.md.
# =============================================================================
set -euo pipefail

# TODO(infra-sprint-1): implement pg_dump | age | rclone copy + retention prune.
echo "backup.sh: placeholder — Sprint 0"
exit 0
