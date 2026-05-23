"""seed_calibrator_nightly_job — seed calibrator_retrain_nightly into job_definitions.

Seeds the nightly calibrator retraining job so DatabaseScheduler fires
``mt.calibrator.retrain_nightly`` at 03:00 Asia/Dubai every night.
The Celery task (app.workers.tasks.calibrator.retrain_nightly) already
exists; this migration just wires the cron trigger.

Revision ID: 20260520_154
Revises: 20260520_153
Create Date: 2026-05-20
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260520_154"
down_revision: str | None = "20260520_153"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TASK_NAME = "mt.calibrator.retrain_nightly"
_JOB_CODE = "calibrator-retrain-nightly"


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO job_definitions
            (code, task_name, description, owner,
             schedule_type, cron_expression, timezone, queue,
             enabled, args, kwargs)
        VALUES
            ('{_JOB_CODE}',
             '{_TASK_NAME}',
             'Reentrenamiento nightly del calibrador conformal desde golden_labels',
             'infra',
             'cron',
             '0 3 * * *',
             'Asia/Dubai',
             'comparator',
             true,
             '[]'::jsonb,
             '{{}}'::jsonb)
        ON CONFLICT (code) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM job_definitions WHERE task_name = '{_TASK_NAME}';")
