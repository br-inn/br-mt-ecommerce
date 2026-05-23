"""comparator hooks — tablas vacías + flag seed (ADR-012, §17.1).

Fase 1 deja las tablas creadas pero **vacías**; la lógica real entra en
Fase 1.5+ tras research workstream. Esta migración:

1. ``competitor_listings`` — listings normalizados con embedding ``VECTOR(1536)``
   + índice HNSW (``vector_cosine_ops``) para búsqueda ANN. Match opcional
   contra ``products.sku``.
2. ``match_decisions`` — decisiones humanas (match / no_match / uncertain)
   con ``evidence_jsonb`` para audit.
3. Seed flag ``COMPARATOR_ENABLED`` → ``false`` (default seguro: el
   :class:`ComparatorServiceFactory` devuelve :class:`NoopComparatorService`
   cuando este flag está OFF).

⚠ pgvector ya está habilitado desde la migración inicial 001 (``CREATE
EXTENSION vector``). Si por alguna razón se ejecuta esta migración en un
entorno sin la extensión, el ``CREATE EXTENSION`` es idempotente.

⚠ HNSW: el índice se crea **vacío**. Cost de mantenimiento despreciable
mientras la tabla esté a 0 filas. Cuando Fase 1.5+ empiece a poblar, queda
listo sin re-índice. Para detallar parámetros (``m`` / ``ef_construction``)
ver ADR-011.

Revision ID: 20260517_069
Revises: 20260516_068
Create Date: 2026-05-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID

revision: str = "20260517_069"
down_revision: str | None = "20260516_068"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Extension defensiva — idempotente
    # ------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # ------------------------------------------------------------------
    # 1. competitor_listings — listings normalizados
    # ------------------------------------------------------------------
    op.create_table(
        "competitor_listings",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column(
            "raw_payload_jsonb",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "normalized_jsonb",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("image_sha256", sa.String(64), nullable=True),
        # embedding: pgvector dim 1536 — nullable hasta que el research
        # workstream firme un modelo de embedding (ADR-012).
        sa.Column(
            "embedding",
            sa.ARRAY(sa.Float()),
            nullable=True,
        ),
        sa.Column(
            "matched_product_sku",
            sa.Text(),
            sa.ForeignKey("products.sku", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("match_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "match_confidence IS NULL OR (match_confidence >= 0 AND match_confidence <= 1)",
            name="ck_competitor_listings_confidence_range",
        ),
    )

    # La columna ``embedding`` se creó arriba como ARRAY(Float) para que el
    # autogenerate de Alembic la entienda; ahora la convertimos a VECTOR(1536)
    # real (preserva nullable) — sólo si la extensión está habilitada.
    op.execute(
        "ALTER TABLE competitor_listings ALTER COLUMN embedding TYPE vector(1536) USING NULL;"
    )

    op.create_index(
        "ux_competitor_listings_source",
        "competitor_listings",
        ["source", "source_id"],
        unique=True,
    )
    op.create_index(
        "ix_competitor_listings_matched_sku",
        "competitor_listings",
        ["matched_product_sku"],
    )
    # HNSW index sobre embedding (cosine). Se crea vacío — coste mantenimiento
    # despreciable mientras la tabla está sin datos. Ver ADR-011.
    op.execute(
        "CREATE INDEX ix_competitor_listings_embedding_hnsw "
        "ON competitor_listings USING hnsw (embedding vector_cosine_ops);"
    )

    # ------------------------------------------------------------------
    # 2. match_decisions — decisiones humanas (audit-grade)
    # ------------------------------------------------------------------
    op.create_table(
        "match_decisions",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "competitor_listing_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("competitor_listings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_sku",
            sa.Text(),
            sa.ForeignKey("products.sku", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column(
            "evidence_jsonb",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "decided_by",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "decided_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "decision IN ('match','no_match','uncertain')",
            name="ck_match_decisions_decision",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_match_decisions_confidence_range",
        ),
    )
    op.create_index(
        "ix_match_decisions_listing",
        "match_decisions",
        ["competitor_listing_id"],
    )
    op.create_index(
        "ix_match_decisions_sku",
        "match_decisions",
        ["product_sku"],
    )

    # ------------------------------------------------------------------
    # 3. Seed flag COMPARATOR_ENABLED (default OFF)
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO feature_flags (key, value_jsonb)
        VALUES ('COMPARATOR_ENABLED', '{"enabled": false}'::jsonb)
        ON CONFLICT (key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM feature_flags WHERE key = 'COMPARATOR_ENABLED';")

    op.drop_index("ix_match_decisions_sku", table_name="match_decisions")
    op.drop_index("ix_match_decisions_listing", table_name="match_decisions")
    op.drop_table("match_decisions")

    op.execute("DROP INDEX IF EXISTS ix_competitor_listings_embedding_hnsw;")
    op.drop_index("ix_competitor_listings_matched_sku", table_name="competitor_listings")
    op.drop_index("ux_competitor_listings_source", table_name="competitor_listings")
    op.drop_table("competitor_listings")
