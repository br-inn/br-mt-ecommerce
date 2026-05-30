"""F8: tabla pricing_optimization_runs + seed job auto-optimize-check.

Crea la tabla de registro/alerta de drift de optimización (un row por
detección con su diff) y siembra el `job_definition` periódico que la
alimenta (01:30 Asia/Dubai, tras el fx-sync de las 01:00). No aplica nada
automáticamente — solo registra alerta + diff.

El enum `selling_model` ya existe (mig 147) → `create_type=False`. Tabla
`public.*` → Alembic.

Revision ID: 20260603_151
Revises: 20260603_150
Create Date: 2026-05-31
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260603_151"
down_revision: str | None = "20260603_150"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SELLING_MODEL = postgresql.ENUM("b2c", "b2b", name="selling_model", create_type=False)


def upgrade() -> None:
    op.create_table(
        "pricing_optimization_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("selling_model", _SELLING_MODEL, nullable=False),
        sa.Column("baseline_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revert_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("skus_scheme_changed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("skus_signal_changed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "drift_reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "diff_detail",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], name="fk_opt_runs_channel"),
        sa.ForeignKeyConstraint(
            ["baseline_snapshot_id"],
            ["pricing_scenarios.id"],
            name="fk_opt_runs_baseline",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["revert_snapshot_id"],
            ["pricing_scenarios.id"],
            name="fk_opt_runs_revert",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["acknowledged_by"], ["users.id"], name="fk_opt_runs_ack_by", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_opt_runs_lookup",
        "pricing_optimization_runs",
        ["channel_id", "selling_model", sa.text("detected_at DESC")],
    )
    op.create_index(
        "idx_opt_runs_unack",
        "pricing_optimization_runs",
        ["channel_id"],
        postgresql_where=sa.text("acknowledged_at IS NULL"),
    )

    # Seed job (idempotente).
    op.execute(
        """
        INSERT INTO job_definitions
            (code, task_name, description, owner, schedule_type,
             cron_expression, timezone, queue, enabled, args, kwargs)
        VALUES
            ('pricing-auto-optimize-check', 'mt.pricing.auto_optimize_check',
             'Detecta drift de params y alerta con diff (no aplica)', 'infra', 'cron',
             '30 1 * * *', 'Asia/Dubai', 'pricing', true, '[]'::jsonb, '{}'::jsonb)
        ON CONFLICT (code) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM job_definitions WHERE code = 'pricing-auto-optimize-check';")
    op.drop_index("idx_opt_runs_unack", table_name="pricing_optimization_runs")
    op.drop_index("idx_opt_runs_lookup", table_name="pricing_optimization_runs")
    op.drop_table("pricing_optimization_runs")
