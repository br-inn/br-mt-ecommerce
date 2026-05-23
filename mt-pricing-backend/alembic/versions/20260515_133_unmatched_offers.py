"""Create unmatched_offers table (Silver layer candidate store for re-matching)"""

from __future__ import annotations
from alembic import op

revision = "20260515_133"
down_revision = "20260515_132"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE unmatched_offers (
            id                UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
            marketplace       VARCHAR(32)     NOT NULL,
            external_id       TEXT            NOT NULL,
            title             TEXT            NOT NULL,
            brand             TEXT,
            price_aed         NUMERIC(18, 4),
            delivery_text     TEXT,
            specs_jsonb       JSONB           NOT NULL DEFAULT '{}'::jsonb,
            image_url         TEXT,
            source_url        TEXT,
            fingerprint       TEXT            NOT NULL UNIQUE,
            embedding         VECTOR(1536),
            match_attempts    INTEGER         NOT NULL DEFAULT 0,
            matched_at        TIMESTAMPTZ,
            scraped_at        TIMESTAMPTZ     NOT NULL DEFAULT now(),
            created_at        TIMESTAMPTZ     NOT NULL DEFAULT now(),
            updated_at        TIMESTAMPTZ     NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE INDEX idx_unmatched_offers_marketplace
        ON unmatched_offers (marketplace)
    """)

    op.execute("""
        CREATE INDEX idx_unmatched_offers_pending
        ON unmatched_offers (scraped_at)
        WHERE matched_at IS NULL
    """)

    op.execute("""
        CREATE INDEX idx_unmatched_offers_embedding
        ON unmatched_offers
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_unmatched_offers_embedding")
    op.execute("DROP INDEX IF EXISTS idx_unmatched_offers_pending")
    op.execute("DROP INDEX IF EXISTS idx_unmatched_offers_marketplace")
    op.execute("DROP TABLE IF EXISTS unmatched_offers")
