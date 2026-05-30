"""F2: backfill fx_rates desde trade_route_params + seed jobs FX/cleanup.

Backfill no destructivo: si no existe un rate activo EUR→AED en `fx_rates`,
inserta el `fx_rate` actual de las rutas como `source='manual'` (preserva el
precio del engine en el deploy; el job ECB lo actualiza al día siguiente).
Seed idempotente de los 2 `job_definitions` (FX diario + cleanup nightly).

La fila `source_health(tesoreria_fx)` ya la sembró F1 (mig 149); el job la
UPDATE — esta migración no la toca.

Revision ID: 20260603_150
Revises: 20260603_149
Create Date: 2026-05-31
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260603_150"
down_revision: str | None = "20260603_149"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (code, task_name, description, cron, queue)
_JOBS: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "fx-sync-daily",
        "mt.fx.sync_daily",
        "Sync diario EUR->AED desde ECB hacia fx_rates",
        "0 1 * * *",
        "default",
    ),
    (
        "pricing-cleanup-auto-snapshots",
        "mt.pricing.cleanup_auto_snapshots",
        "Limpieza nightly de snapshots auto vencidos (>90d)",
        "0 2 * * *",
        "pricing",
    ),
)


def upgrade() -> None:
    # 1. Backfill no destructivo: si no hay rate activo EUR->AED en fx_rates,
    #    insertar UN rate manual con el fx_rate de cualquier ruta existente.
    #    El FX es un peg global EUR->AED (no por-ruta), así que basta 1 rate
    #    activo. El trigger `fx_rates_close_previous_trg` cierra anteriores.
    op.execute(
        """
        INSERT INTO fx_rates (id, from_currency, to_currency, rate, effective_from, source)
        SELECT gen_random_uuid(), 'EUR', 'AED', t.fx_rate, now(), 'manual'
        FROM (SELECT DISTINCT fx_rate FROM trade_route_params WHERE fx_rate IS NOT NULL) t
        WHERE NOT EXISTS (
            SELECT 1 FROM fx_rates f
            WHERE f.from_currency='EUR' AND f.to_currency='AED' AND f.effective_to IS NULL
        )
        LIMIT 1;
        """
    )

    # 2. Seed jobs (idempotente).
    for code, task, desc, cron, queue in _JOBS:
        op.execute(
            f"""
            INSERT INTO job_definitions
                (code, task_name, description, owner, schedule_type,
                 cron_expression, timezone, queue, enabled, args, kwargs)
            VALUES
                ('{code}', '{task}', '{desc}', 'infra', 'cron',
                 '{cron}', 'Asia/Dubai', '{queue}', true, '[]'::jsonb, '{{}}'::jsonb)
            ON CONFLICT (code) DO NOTHING;
            """
        )


def downgrade() -> None:
    op.execute(
        "DELETE FROM job_definitions WHERE code IN "
        "('fx-sync-daily','pricing-cleanup-auto-snapshots');"
    )
    op.execute(
        "DELETE FROM fx_rates WHERE from_currency='EUR' AND to_currency='AED' "
        "AND source='manual' AND created_by IS NULL;"
    )
