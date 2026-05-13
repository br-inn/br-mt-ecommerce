"""fts_gin_fix — drop ix_products_fts_gin obsoleto + GIN trgm en product_translations.

ix_products_fts_gin (mig 008) referenciaba las columnas `name_en` y `brand`
directamente en la expresión GIN. La columna `name_en` fue dropeada en mig 065
(Fase B) — el índice está desactualizado y genera overhead en writes sin aportar
beneficio (el planner no lo puede usar para las queries actuales).

Nuevo índice: GIN pg_trgm en product_translations(name) WHERE lang='en'.
Permite que `search_by_text` y `search_by_name` (después del fix de JOIN
directo en product.py) usen el índice para búsquedas de similaridad.

Ref: query-missing-indexes + advanced-full-text-search best practices.

Revision ID: 20260513_104
Revises: 20260513_103
Create Date: 2026-05-13
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260513_104"
down_revision: str = "20260513_103"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Eliminar índice GIN obsoleto (referencia name_en dropeada en mig 065).
    op.execute("DROP INDEX IF EXISTS ix_products_fts_gin;")

    # 2. Asegurar extensión pg_trgm (idempotente — ya debería existir).
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # 3. GIN trgm index parcial en product_translations.name WHERE lang='en'.
    #    Partial porque todas las búsquedas de similaridad filtran lang='en'.
    #    Permite operador % (similarity) e ILIKE con el planner usando el índice.
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_pt_name_en_trgm
        ON product_translations USING GIN (name gin_trgm_ops)
        WHERE lang = 'en';
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_pt_name_en_trgm;")
    # No re-creamos ix_products_fts_gin — referenciaba name_en ya dropeado.
