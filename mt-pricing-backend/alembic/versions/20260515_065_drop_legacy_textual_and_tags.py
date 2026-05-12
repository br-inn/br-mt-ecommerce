"""Fase B step 1 — drop tags + textual columns superseded by product_translations(en) and vocabularies (audit DUP-01, DUP-08).

Refactor PIM Fase B (paso 1 de 2):

- Backfill ``product_translations(lang='en')`` con (name, description,
  marketing_copy) tomados de las columnas legacy ``products.name_en``,
  ``products.description_en``, ``products.marketing_copy_en`` cuando no exista
  ya un row ``(sku, 'en')``. Idempotente vía ``ON CONFLICT DO NOTHING``.
- DROP columns en orden:
    1. ``products.tags`` — superseded por ``product_certifications`` y
       ``product_applications`` (vocabularios M:N).
    2. ``products.name_en`` — superseded por
       ``product_translations(lang='en').name``.
    3. ``products.description_en`` — idem.
    4. ``products.marketing_copy_en`` — idem.

NOTA: ``products.active`` se dropea en migración separada (066) porque
afecta a más servicios y queremos aislar el blast-radius.

Downgrade: recrea las 4 columnas como NULLABLE (sin rellenar — el caller
asume que el rollback se hace antes del backfill o se acepta pérdida de
datos para columnas migradas a translations).

Revision ID: 20260515_065
Revises: 20260514_064
Create Date: 2026-05-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260515_065"
down_revision: str | None = "20260514_064"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # =====================================================================
    # 1) Backfill product_translations(lang='en') from legacy columns
    # =====================================================================
    # Sólo en Postgres — SQLite (tests) no requiere backfill porque la
    # mayoría de tests crean translations explícitamente o no dependen del
    # contenido legacy.
    if dialect == "postgresql":
        op.execute(
            sa.text(
                """
                INSERT INTO product_translations
                    (sku, lang, name, description, marketing_copy,
                     status, created_at, updated_at)
                SELECT
                    p.sku,
                    'en' AS lang,
                    p.name_en,
                    p.description_en,
                    p.marketing_copy_en,
                    'approved' AS status,
                    NOW(),
                    NOW()
                FROM products AS p
                WHERE p.name_en IS NOT NULL
                ON CONFLICT (sku, lang) DO NOTHING
                """
            )
        )

    # =====================================================================
    # 2) Drop dependientes antes de poder dropear las columnas
    # =====================================================================
    # 2.0a — Trigger mig 020 (trg_translations_stale_on_master_edit)
    #        depende de UPDATE OF name_en, description_en.
    if dialect == "postgresql":
        op.execute(
            sa.text(
                "DROP TRIGGER IF EXISTS trg_translations_stale_on_master_edit ON products"
            )
        )
        op.execute(
            sa.text(
                "DROP FUNCTION IF EXISTS mark_translations_stale_on_master_edit() CASCADE"
            )
        )

        # 2.0b — Columna GENERATED `search_tsv` (mig 003/008) referencia
        # name_en + description_en. Dropear (CASCADE quita su índice GIN).
        op.execute(sa.text("ALTER TABLE products DROP COLUMN IF EXISTS search_tsv CASCADE"))

    # =====================================================================
    # 3) DROP columns en orden
    # =====================================================================

    # 3.1 — products.tags (ARRAY)
    op.drop_column("products", "tags")

    # 3.2 — products.name_en — quitar índice trigram primero.
    # (mig 003 creó idx_products_name_trgm sobre name_en).
    if dialect == "postgresql":
        op.execute(sa.text("DROP INDEX IF EXISTS idx_products_name_trgm"))
        op.execute(sa.text("DROP INDEX IF EXISTS idx_products_name_en_trgm"))
        # FTS GIN index (mig 008) si lo creó sobre name_en — drop best-effort.
        op.execute(sa.text("DROP INDEX IF EXISTS idx_products_fts"))
        op.execute(sa.text("DROP INDEX IF EXISTS idx_products_search_vector"))
    op.drop_column("products", "name_en")

    # 3.3 — products.description_en
    op.drop_column("products", "description_en")

    # 3.4 — products.marketing_copy_en
    op.drop_column("products", "marketing_copy_en")

    # =====================================================================
    # 4) Recrear search_tsv reducido (sku + family + brand) — sin name_en/desc_en
    # =====================================================================
    # El full-text search degradado a nivel "código + clasificación" mientras
    # se implementa el JOIN a product_translations(en) en el servicio de búsqueda.
    if dialect == "postgresql":
        op.execute(
            sa.text(
                """
                ALTER TABLE products ADD COLUMN search_tsv tsvector
                GENERATED ALWAYS AS (
                    setweight(to_tsvector('simple', coalesce(sku, '')), 'A') ||
                    setweight(to_tsvector('simple', coalesce(family, '')), 'C') ||
                    setweight(to_tsvector('simple', coalesce(brand, '')), 'D')
                ) STORED
                """
            )
        )
        op.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS idx_products_search_tsv "
                "ON products USING gin (search_tsv)"
            )
        )


# ---------------------------------------------------------------------------
# downgrade
# ---------------------------------------------------------------------------
def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Recreate columns as NULLABLE (no backfill — irreversible para datos
    # ya migrados a product_translations).
    op.add_column(
        "products",
        sa.Column("name_en", sa.Text(), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("description_en", sa.Text(), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("marketing_copy_en", sa.Text(), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column(
            "tags",
            sa.dialects.postgresql.ARRAY(sa.Text())
            if dialect == "postgresql"
            else sa.Text(),
            nullable=False,
            server_default=sa.text("'{}'::text[]") if dialect == "postgresql"
            else sa.text("'[]'"),
        ),
    )

    # Recreate trigram index (best-effort) si pg_trgm está disponible.
    if dialect == "postgresql":
        op.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS idx_products_name_trgm "
                "ON products USING gin (name_en gin_trgm_ops)"
            )
        )
