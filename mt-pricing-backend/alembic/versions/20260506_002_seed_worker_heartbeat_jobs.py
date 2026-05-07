"""seed_worker_heartbeat_jobs

Data-only migration: agenda 6 entradas en `job_definitions` para que Beat
dispare `mt.system.publish_heartbeat` cada 30s a cada queue. Cada queue
refresca su key `mt:worker:heartbeat:<queue>` y `/health/celery` puede
detectar workers caídos en < 60s.

ADR-048 (healthcheck custom — no celery.control.ping).

Revision ID: 20260506_002
Revises: 20260506_001
Create Date: 2026-05-06
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260506_002"
down_revision: str | None = "20260506_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Colas alineadas con app.workers.worker._QUEUE_NAMES (sin "default" — no
# tiene workers dedicados, no necesita heartbeat).
_QUEUES: tuple[str, ...] = (
    "imports",
    "pricing",
    "images",
    "comparator",
    "notifications",
    "audit",
)


def upgrade() -> None:
    # 30s = "*/30 * * * * *" no es soportado por croniter estándar (5 campos);
    # usamos schedule_type='interval' con interval_seconds=30 para Beat.
    for queue in _QUEUES:
        op.execute(
            f"""
            INSERT INTO job_definitions
                (code, task_name, description, owner,
                 schedule_type, interval_seconds, queue, enabled,
                 args, kwargs)
            VALUES
                ('worker_heartbeat__{queue}',
                 'mt.system.publish_heartbeat',
                 'Publica heartbeat del worker en queue {queue} (ADR-048)',
                 'infra', 'interval', 30, '{queue}', true,
                 '[]'::jsonb, '{{}}'::jsonb)
            ON CONFLICT (code) DO NOTHING;
            """
        )


def downgrade() -> None:
    op.execute(
        "DELETE FROM job_definitions "
        "WHERE code LIKE 'worker_heartbeat__%';"
    )
