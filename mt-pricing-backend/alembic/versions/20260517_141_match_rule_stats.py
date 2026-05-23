"""match_rule_stats — instrumentación del pipeline

Revision ID: 20260517_141
Revises: 20260517_140
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from alembic import op

revision = "20260517_141"
down_revision = "20260517_140"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "match_rule_stats",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "match_candidate_id",
            sa.UUID(),
            sa.ForeignKey("match_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "taxonomy_profile_id",
            sa.UUID(),
            sa.ForeignKey("taxonomy_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "score_breakdown", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "dimensions_fired",
            ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_match_rule_stats_candidate", "match_rule_stats", ["match_candidate_id"])
    op.create_index("idx_match_rule_stats_profile", "match_rule_stats", ["taxonomy_profile_id"])


def downgrade() -> None:
    op.drop_index("idx_match_rule_stats_profile")
    op.drop_index("idx_match_rule_stats_candidate")
    op.drop_table("match_rule_stats")
