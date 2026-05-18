"""match_candidates_image_source_url — agrega image_url y source_url a match_candidates.

Los campos estaban siendo extraídos correctamente por el scraper pero
descartados al persistir (raw_payload no se guardaba). Esta migración los
agrega como columnas opcionales para que la UI de validación pueda mostrar
la foto del producto y enlazar a la URL real de Amazon/Noon.

Revision ID: 20260528_122
Revises: 20260528_121
Create Date: 2026-05-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260528_122"
down_revision: str | Sequence[str] | None = "20260528_121"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("match_candidates", sa.Column("image_url", sa.Text(), nullable=True))
    op.add_column("match_candidates", sa.Column("source_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("match_candidates", "source_url")
    op.drop_column("match_candidates", "image_url")
