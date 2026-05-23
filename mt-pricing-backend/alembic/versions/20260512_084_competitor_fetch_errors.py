"""Tabla competitor_fetch_errors — US-F15-02-01 (Amazon SP API fetcher).

Registra errores de fetch de precios de competidores para trazabilidad y
diagnóstico. Poblada por AmazonSPApiFetcherAdapter._log_fetch_error (best-effort).

Revision ID: 20260512_084
Revises: 20260512_083
Create Date: 2026-05-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260512_084"
down_revision: str = "20260512_083"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "competitor_fetch_errors",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column("asin", sa.String(20), nullable=False),
        sa.Column("error_type", sa.String(100), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_competitor_fetch_errors_asin",
        "competitor_fetch_errors",
        ["asin"],
    )
    op.create_index(
        "ix_competitor_fetch_errors_created_at",
        "competitor_fetch_errors",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_competitor_fetch_errors_created_at", table_name="competitor_fetch_errors")
    op.drop_index("ix_competitor_fetch_errors_asin", table_name="competitor_fetch_errors")
    op.drop_table("competitor_fetch_errors")
