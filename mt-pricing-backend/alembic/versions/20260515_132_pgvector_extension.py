"""Enable pgvector extension for vector similarity search"""

from __future__ import annotations

from alembic import op

revision = "20260515_132"
down_revision = "20260529_131"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    # Extension managed by mig 001 which deliberately does not drop extensions.
    # Dropping here would fail with dependent objects (competitor_listings.embedding,
    # unmatched_offers.embedding) and is not safe during downgrade base.
    pass
