"""Tabla last_good_exports — US-1B-04-05 (job diario last-known-good exports).

Almacena el export completado más reciente por combinación (channel_code, scheme_code).
Actualizada diariamente por el job Celery `mt.pricing.capture_last_good_exports`.

Revision ID: 20260512_083
Revises: 20260512_082
Create Date: 2026-05-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260512_083"
down_revision: str = "20260512_082"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "last_good_exports",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column("channel_code", sa.Text(), nullable=False),
        sa.Column("scheme_code", sa.Text(), nullable=False),
        sa.Column(
            "export_manifest_id",
            sa.UUID(),
            sa.ForeignKey("exports_manifest.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("rows_exported", sa.Integer(), nullable=False),
        sa.Column("file_ref", sa.Text(), nullable=True),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("channel_code", "scheme_code", name="uq_last_good_exports_channel_scheme"),
    )

    # Seed beat job for the new daily task
    op.execute(
        """
        INSERT INTO job_definitions
            (code, task_name, description, owner,
             schedule_type, cron_expression, queue, enabled,
             args, kwargs)
        VALUES
            ('capture_last_good_exports',
             'mt.pricing.capture_last_good_exports',
             'Captura el export completado más reciente por canal/scheme en last_good_exports (US-1B-04-05)',
             'business', 'cron', '0 2 * * *', 'default', true,
             '[]'::jsonb, '{}'::jsonb)
        ON CONFLICT (code) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM job_definitions WHERE code = 'capture_last_good_exports';"
    )
    op.drop_table("last_good_exports")
