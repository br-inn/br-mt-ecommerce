"""match_candidates_pack_units — número de unidades por pack de Amazon/Noon.

Agrega `pack_units` a match_candidates. Cuando Amazon lista un producto en
packs (ej. "Pack of 10"), price_aed es el precio del pack completo y
pack_units indica cuántas unidades incluye. El precio comparable con MT es
price_aed / pack_units.

Revision ID: 20260528_125
Revises: 20260528_124
Create Date: 2026-05-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260528_125"
down_revision: str | Sequence[str] | None = "20260528_124"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "match_candidates",
        sa.Column(
            "pack_units",
            sa.Integer(),
            nullable=True,
            comment="Unidades por pack (NULL o 1 = precio por unidad individual)",
        ),
    )


def downgrade() -> None:
    op.drop_column("match_candidates", "pack_units")
