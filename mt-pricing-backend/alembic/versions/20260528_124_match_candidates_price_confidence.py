"""match_candidates_price_confidence — columnas de confiabilidad de precio.

Agrega `delivery_category` y `price_confidence_score` a match_candidates
para reflejar si el precio de mercado es comparable con el stock UAE de MT.

Revision ID: 20260528_124
Revises: 20260528_123
Create Date: 2026-05-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260528_124"
down_revision: str | Sequence[str] | None = "20260528_123"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "match_candidates",
        sa.Column("delivery_category", sa.String(32), nullable=True),
    )
    op.add_column(
        "match_candidates",
        sa.Column(
            "price_confidence_score",
            sa.Integer(),
            nullable=True,
            comment="0-100: confiabilidad del precio según plazo de entrega vs stock UAE",
        ),
    )


def downgrade() -> None:
    op.drop_column("match_candidates", "price_confidence_score")
    op.drop_column("match_candidates", "delivery_category")
