"""match_candidates — Sprint 3 foundation del Matching Pipeline.

Crea la tabla `match_candidates` que persiste los resultados del comparador
(stubs Amazon UAE / Noon UAE en Sprint 3 — pipeline real en sprints
siguientes). Refs:

- `_bmad-output/planning-artifacts/mt-product-matching-pipeline-detail.md`
- ADR-022..025 (OCR, RIS, VLM judge, capa humana)

Schema:

- `id` UUID PK (gen_random_uuid)
- `product_sku` FK → products.sku (CASCADE)
- `channel` String(32) CHECK ∈ {amazon_uae, noon_uae}
- `external_id` Text NOT NULL (ASIN, Noon SKU, etc.)
- `brand`, `title`, `price_aed` Numeric(18,4), `delivery_text`
- `specs_jsonb` JSONB NOT NULL DEFAULT '{}'
- `kind` String(16) CHECK ∈ {peer, drop, unknown} default 'unknown'
- `score` Integer CHECK 0..100 default 0
- `status` String(16) CHECK ∈ {pending, validated, discarded} default 'pending'
- `validated_by` FK users.id, `validated_at`, `discarded_reason`
- `created_at`, `updated_at`
- Index `(product_sku, status)`
- UNIQUE `(product_sku, channel, external_id)` — idempotencia upsert.

NO se aplica en este sprint (`alembic upgrade head` se difiere).

Revision ID: 20260507_015
Revises: 20260507_014
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260507_016"
down_revision: str | None = "20260507_015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "match_candidates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "product_sku",
            sa.Text(),
            sa.ForeignKey("products.sku", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("brand", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("price_aed", sa.Numeric(18, 4), nullable=True),
        sa.Column("delivery_text", sa.Text(), nullable=True),
        sa.Column(
            "specs_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "kind",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'unknown'"),
        ),
        sa.Column(
            "score",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "validated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "validated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("discarded_reason", sa.Text(), nullable=True),
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
            "channel IN ('amazon_uae','noon_uae')",
            name="ck_match_candidates_channel",
        ),
        sa.CheckConstraint(
            "kind IN ('peer','drop','unknown')",
            name="ck_match_candidates_kind",
        ),
        sa.CheckConstraint(
            "status IN ('pending','validated','discarded')",
            name="ck_match_candidates_status",
        ),
        sa.CheckConstraint(
            "score >= 0 AND score <= 100",
            name="ck_match_candidates_score",
        ),
    )
    op.create_index(
        "idx_match_candidates_sku_status",
        "match_candidates",
        ["product_sku", "status"],
    )
    op.create_index(
        "idx_match_candidates_unique_external",
        "match_candidates",
        ["product_sku", "channel", "external_id"],
        unique=True,
    )
    op.execute(
        "CREATE TRIGGER trg_match_candidates_updated_at "
        "BEFORE UPDATE ON match_candidates "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_match_candidates_updated_at ON match_candidates;")
    op.drop_index("idx_match_candidates_unique_external", table_name="match_candidates")
    op.drop_index("idx_match_candidates_sku_status", table_name="match_candidates")
    op.drop_table("match_candidates")
