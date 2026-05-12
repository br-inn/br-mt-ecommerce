"""Fase 4 — versioned controlled documents (PDF §11).

Crea la tabla `documents` para fichas técnicas, manuales, declaraciones CE,
certificados y catálogos. Cada documento es una entidad gobernada con:
- `type`: clasificación funcional (ficha_tecnica, manual, declaracion_ce, ...)
- `code`: identificador editorial (e.g. 'MTFT-038', 'MTCE-2024-01')
- `version`: revisión textual (e.g. 'rev-2', '2024.1')
- `language`: ISO 639-1 (es/en/ar/...)
- `asset_id`: FK al binario en `product_assets`

Unicidad `(code, version, language)` garantiza que un documento concreto en
un idioma con una versión dada es único.

El link a productos/series/etc. se hace via `asset_links` polimórfica
(mig 058) — `documents` modela el documento en sí, `asset_links` modela
dónde se muestra.

Revision ID: 20260514_059
Revises: 20260514_058
Create Date: 2026-05-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision: str = "20260514_059"
down_revision: str | None = "20260514_058"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DOCUMENT_TYPES = (
    "ficha_tecnica",
    "manual",
    "declaracion_ce",
    "certificado",
    "catalogo",
)


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("language", sa.CHAR(length=2), nullable=False),
        sa.Column(
            "asset_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("product_assets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("issued_at", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "type IN (" + ", ".join(f"'{t}'" for t in DOCUMENT_TYPES) + ")",
            name="ck_documents_type",
        ),
        sa.UniqueConstraint(
            "code", "version", "language", name="uq_documents_code_version_language"
        ),
    )
    op.create_index("ix_doc_type", "documents", ["type"])
    op.create_index("ix_doc_asset", "documents", ["asset_id"])


def downgrade() -> None:
    op.drop_index("ix_doc_asset", table_name="documents")
    op.drop_index("ix_doc_type", table_name="documents")
    op.drop_table("documents")
