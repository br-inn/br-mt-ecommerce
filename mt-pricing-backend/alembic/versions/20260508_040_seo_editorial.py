"""seo_editorial — Wave 8: extend product_translations with SEO + editorial fields.

Cambios en ``product_translations``:
- meta_title (text, max 70 — recomendación SEO)
- meta_description (text, max 160 — recomendación SEO)
- applications_text (text) — descripción narrativa de aplicaciones
- technical_limits (text) — límites técnicos en prosa
- notes (text) — notas catálogo
- marketing_features (text) — características destacadas (markdown)

Slot 040.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260508_040"
down_revision: str | None = "20260508_039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("product_translations", sa.Column("meta_title", sa.Text(), nullable=True))
    op.add_column(
        "product_translations", sa.Column("meta_description", sa.Text(), nullable=True)
    )
    op.add_column(
        "product_translations", sa.Column("applications_text", sa.Text(), nullable=True)
    )
    op.add_column(
        "product_translations", sa.Column("technical_limits", sa.Text(), nullable=True)
    )
    op.add_column("product_translations", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column(
        "product_translations", sa.Column("marketing_features", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    for col in (
        "marketing_features",
        "notes",
        "technical_limits",
        "applications_text",
        "meta_description",
        "meta_title",
    ):
        op.drop_column("product_translations", col)
