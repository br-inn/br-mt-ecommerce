"""products_fts_gin — índice GIN tsvector alineado al runtime (NFR-06).

S2 — Gap-fix backend. La búsqueda full-text del listing
(`GET /products?q=...`) construye el tsvector en runtime con `simple` para
TODOS los campos y peso por sku/name/family/brand (ver
`app/repositories/product.py::list_products`):

    setweight(to_tsvector('simple', coalesce(sku, '')),    'A') ||
    setweight(to_tsvector('simple', coalesce(name_en, '')), 'B') ||
    setweight(to_tsvector('simple', coalesce(family, '')),  'C') ||
    setweight(to_tsvector('simple', coalesce(brand, '')),   'D')

La migración 003 (`idx_products_search_tsv`) usaba `english` para
`name_en`/`description_en` — Postgres no puede usar ese índice cuando la
expresión runtime usa `simple` (las funciones inmutables deben matchear
EXACTAMENTE para que el planner elija el GIN expresional).

Este índice cubre la expresión runtime → permite cumplir NFR-06 (<500ms
sobre ~5k filas). El índice 003 (`search_tsv` STORED) se conserva por
compatibilidad con el ranking en hybrid search Sprint 3+; ambos coexisten
sin conflicto.

Revision ID: 20260507_008
Revises: 20260507_007
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260507_008"
down_revision: str | None = "20260507_007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_products_fts_gin ON products USING GIN (
            (
                setweight(to_tsvector('simple', coalesce(sku, '')), 'A') ||
                setweight(to_tsvector('simple', coalesce(name_en, '')), 'B') ||
                setweight(to_tsvector('simple', coalesce(family, '')), 'C') ||
                setweight(to_tsvector('simple', coalesce(brand, '')), 'D')
            )
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_products_fts_gin;")
