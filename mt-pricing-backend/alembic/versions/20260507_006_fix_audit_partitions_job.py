"""fix_audit_partitions_job — alinea el seed de `job_definitions` con la task real.

Migration 001 sembró `audit_partitions_ensure` apuntando a `app.workers.tasks.audit.ensure_partitions`,
pero la task real (S2) vive en `app.workers.audit_partitions.ensure_partitions` y
se registra en Celery como `mt.audit.ensure_partitions` (decorator `@celery_app.task(name=...)`).

Actualizamos el `task_name` en `job_definitions` para que el DatabaseScheduler
emita send_task con el nombre correcto.

R-S2-08, US-1A-07-01.

Revision ID: 20260507_006
Revises: 20260507_005
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260507_006"
down_revision: str | None = "20260507_005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE job_definitions
           SET task_name = 'mt.audit.ensure_partitions',
               kwargs    = jsonb_build_object('months_ahead', 2),
               description = 'Crea particiones de audit_events para los próximos 2 meses si no existen (idempotente)',
               cron_expression = '0 2 * * *',
               queue = 'audit'
         WHERE code = 'audit_partitions_ensure';
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE job_definitions
           SET task_name = 'app.workers.tasks.audit.ensure_partitions',
               kwargs    = '{}'::jsonb,
               description = 'Crea partición del mes siguiente para audit_events',
               cron_expression = '0 2 1 * *',
               queue = 'default'
         WHERE code = 'audit_partitions_ensure';
        """
    )
