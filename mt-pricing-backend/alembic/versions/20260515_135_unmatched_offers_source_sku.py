"""Add source_sku to unmatched_offers for re-matching phase 2"""

from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "20260515_135"
down_revision = "20260515_134"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("unmatched_offers", sa.Column("source_sku", sa.Text(), nullable=True))
    op.create_index("idx_unmatched_offers_source_sku", "unmatched_offers", ["source_sku"])


def downgrade() -> None:
    op.drop_index("idx_unmatched_offers_source_sku", table_name="unmatched_offers")
    op.drop_column("unmatched_offers", "source_sku")
