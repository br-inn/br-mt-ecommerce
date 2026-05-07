"""products_search_index — tsvector + GIN para búsqueda full-text.

Sprint 1: añadimos `search_tsv` GENERATED ALWAYS sobre name_en + sku +
description_en + family + brand. Útil para queries `to_tsquery` futuras
(Sprint 2 lo combina con embeddings).

Por ahora el repository no usa este índice — depende de pg_trgm — pero lo
dejamos creado para que el rollout esté listo cuando activemos hybrid search.

Revision ID: 20260506_003
Revises: 20260506_002
Create Date: 2026-05-06
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260506_003"
down_revision: str | None = "20260506_002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # tsvector generated column — coalesce defensivo en NULLs.
    op.execute(
        """
        ALTER TABLE products
        ADD COLUMN search_tsv tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('simple', coalesce(sku, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(name_en, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(description_en, '')), 'C') ||
            setweight(to_tsvector('simple', coalesce(family, '') || ' ' || coalesce(brand, '')), 'D')
        ) STORED;
        """
    )
    op.execute(
        "CREATE INDEX idx_products_search_tsv ON products USING gin (search_tsv);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_products_search_tsv;")
    op.execute("ALTER TABLE products DROP COLUMN IF EXISTS search_tsv;")
