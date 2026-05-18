"""Resize unmatched_offers.embedding VECTOR(1536) → VECTOR(384) for sentence-transformers"""
from __future__ import annotations
from alembic import op

revision = "20260515_134"
down_revision = "20260515_133"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_unmatched_offers_embedding")
    op.execute("ALTER TABLE unmatched_offers DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE unmatched_offers ADD COLUMN embedding VECTOR(384)")
    op.execute(
        "CREATE INDEX idx_unmatched_offers_embedding "
        "ON unmatched_offers "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_unmatched_offers_embedding")
    op.execute("ALTER TABLE unmatched_offers DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE unmatched_offers ADD COLUMN embedding VECTOR(1536)")
    op.execute(
        "CREATE INDEX idx_unmatched_offers_embedding "
        "ON unmatched_offers "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )
