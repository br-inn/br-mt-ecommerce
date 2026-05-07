#!/usr/bin/env bash
# =============================================================================
# restore.sh — placeholder
# =============================================================================
# Restore a backup created by backup.sh into a target database. Used during DR
# drills (quarterly) and real recovery.
#
# Usage (target):
#   ./restore.sh --backup s3://mt-pricing/backups/2026-05-06.sql.age --target staging
# =============================================================================
set -euo pipefail

# TODO(infra-sprint-1): rclone copy + age decrypt + psql restore + verify row counts.
echo "restore.sh: placeholder — Sprint 0"
exit 0
