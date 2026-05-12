"""Registra (UPSERT) el job nocturno de integridad del audit hash chain en job_definitions.

ADR-076 / R-005 / VAT UAE 2026.

Uso:
    python -m scripts.data.seed_audit_jobs [--dry-run]

Idempotente: usa INSERT ... ON CONFLICT (code) DO UPDATE para actualizar
la definición si ya existe.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

_JOB = {
    "code": "audit.nightly_integrity_check",
    "task_name": "audit.nightly_integrity_check",
    "description": "Verifica integridad del hash chain de audit_events (R-005 / ADR-076)",
    "owner": "infra",
    "schedule_type": "cron",
    "cron_expression": "0 3 * * *",  # 03:00 Asia/Dubai = 23:00 UTC del día anterior
    "timezone": "Asia/Dubai",
    "queue": "default",
    "enabled": True,
}

_UPSERT_SQL = text(
    """
    INSERT INTO job_definitions
        (code, task_name, description, owner,
         schedule_type, cron_expression, timezone, queue, enabled)
    VALUES
        (:code, :task_name, :description, :owner,
         :schedule_type, :cron_expression, :timezone, :queue, :enabled)
    ON CONFLICT (code) DO UPDATE SET
        task_name      = EXCLUDED.task_name,
        description    = EXCLUDED.description,
        owner          = EXCLUDED.owner,
        schedule_type  = EXCLUDED.schedule_type,
        cron_expression = EXCLUDED.cron_expression,
        timezone       = EXCLUDED.timezone,
        queue          = EXCLUDED.queue,
        enabled        = EXCLUDED.enabled,
        updated_at     = now()
    RETURNING id, code, enabled
    """
)


async def _seed(dry_run: bool) -> None:
    engine = create_async_engine(str(settings.DATABASE_URL), echo=False)
    try:
        if dry_run:
            print("[dry-run] Job que se registraría en job_definitions:")
            for k, v in _JOB.items():
                print(f"  {k}: {v!r}")
            return

        async with engine.begin() as conn:
            result = await conn.execute(_UPSERT_SQL, _JOB)
            row = result.fetchone()
            print(f"[seed] job_definitions upserted: id={row.id} code={row.code} enabled={row.enabled}")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed audit nightly job definition.")
    parser.add_argument("--dry-run", action="store_true", help="Mostrar sin persistir.")
    args = parser.parse_args()

    try:
        asyncio.run(_seed(dry_run=args.dry_run))
    except Exception as exc:
        print(f"[seed] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
