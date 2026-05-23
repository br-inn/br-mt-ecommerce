"""Tabla kg_integrity_results — US-F15-01-06 (dashboard monitoreo KG + integridad nightly).

Almacena el historial de chequeos nocturnos de integridad del Knowledge Graph:
conteo de nodos, edges, orphans y lag CDC. La Celery task
``mt.graphrag.kg_integrity_check`` escribe una fila por ejecución.

Revision ID: 20260512_086
Revises: 20260512_085
Create Date: 2026-05-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260512_086"
down_revision: str = "20260512_085"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "kg_integrity_results",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("node_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("edge_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("orphan_nodes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cdc_lag_seconds", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="ok",
        ),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.create_index(
        "ix_kg_integrity_results_checked_at",
        "kg_integrity_results",
        ["checked_at"],
        postgresql_using="btree",
    )


def downgrade() -> None:
    op.drop_index("ix_kg_integrity_results_checked_at", table_name="kg_integrity_results")
    op.drop_table("kg_integrity_results")
