"""approval_timeout_job_definition — seed check-approval-timeouts into job_definitions.

Moves the approval timeout beat schedule from the hardcoded beat_schedule dict in
worker.py into job_definitions so DatabaseScheduler owns it. The hardcoded entry in
worker.py must be removed after this migration is applied.

Revision ID: 20260519_148
Revises: 20260519_147
Create Date: 2026-05-19
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260519_148"
down_revision: str | None = "20260519_147"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TASK_NAME = "mt.procurement.check_approval_timeouts"
_JOB_CODE = "check-approval-timeouts"


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
             'Escalate PRs stuck in approval beyond timeout threshold',
             'infra',
             'cron',
             '0 * * * *',
             'Asia/Dubai',
             'default',
             true,
             '[]'::jsonb,
             '{{}}'::jsonb)
        ON CONFLICT (code) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        f"DELETE FROM job_definitions WHERE task_name = '{_TASK_NAME}';"
    )
