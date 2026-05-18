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
    op.execute("DROP EXTENSION IF EXISTS vector")
