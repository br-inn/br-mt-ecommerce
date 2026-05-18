"""product_search_query_cache — caché de queries LLM por SKU+canal.

Evita llamar al LLM cada vez que se refresca el matching. La query se
regenera solo cuando cambia el hash del producto o el usuario la marca
como `manual_override`.

Revision ID: 20260528_123
Revises: 20260528_122
Create Date: 2026-05-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260528_123"
down_revision: str | Sequence[str] | None = "20260528_122"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_search_queries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sku", sa.Text(), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("product_hash", sa.String(64), nullable=False),
        sa.Column("model_used", sa.String(64), nullable=True),
        sa.Column("manual_override", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["sku"], ["products.sku"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku", "channel", name="uq_product_search_queries_sku_channel"),
    )
    op.create_index(
        "ix_product_search_queries_sku",
        "product_search_queries",
        ["sku"],
    )


def downgrade() -> None:
    op.drop_index("ix_product_search_queries_sku", table_name="product_search_queries")
    op.drop_table("product_search_queries")
