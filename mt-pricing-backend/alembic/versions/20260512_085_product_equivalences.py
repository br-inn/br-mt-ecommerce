"""Tabla product_equivalences — US-F15-01-05 (ingestión fichas técnicas PDF).

Almacena pares de productos equivalentes extraídos de PDFs o declarados
manualmente. Se sincroniza al Knowledge Graph como edges EQUIVALENT_TO via
la task Celery mt.graphrag.ingest_equivalences_from_pdf.

Revision ID: 20260512_085
Revises: 20260512_084
Create Date: 2026-05-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260512_085"
down_revision: str = "20260512_084"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_equivalences",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "product_id_a",
            sa.Text(),
            sa.ForeignKey("products.sku", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id_b",
            sa.Text(),
            sa.ForeignKey("products.sku", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.8"),
        sa.Column("source", sa.String(200), nullable=False, server_default="manual"),
        sa.Column(
            "extracted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "synced_to_kg",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.UniqueConstraint("product_id_a", "product_id_b", name="uq_product_equivalences_pair"),
    )

    op.create_index(
        "ix_product_equivalences_product_id_a",
        "product_equivalences",
        ["product_id_a"],
    )
    op.create_index(
        "ix_product_equivalences_product_id_b",
        "product_equivalences",
        ["product_id_b"],
    )
    op.create_index(
        "ix_product_equivalences_synced",
        "product_equivalences",
        ["synced_to_kg"],
        postgresql_where=sa.text("synced_to_kg = false"),
    )


def downgrade() -> None:
    op.drop_index("ix_product_equivalences_synced", table_name="product_equivalences")
    op.drop_index("ix_product_equivalences_product_id_b", table_name="product_equivalences")
    op.drop_index("ix_product_equivalences_product_id_a", table_name="product_equivalences")
    op.drop_table("product_equivalences")
