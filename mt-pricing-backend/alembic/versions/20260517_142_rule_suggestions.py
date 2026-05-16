"""rule_suggestions — AI agent suggestion inbox

Revision ID: 20260517_142
Revises: 20260517_141
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260517_142"
down_revision = "20260517_141"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rule_suggestions",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("taxonomy_profile_id", sa.UUID(), sa.ForeignKey("taxonomy_profiles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("suggestion_type", sa.Text(), nullable=False),
        sa.Column("analysis_summary", sa.Text(), nullable=True),
        sa.Column("proposed_change", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("suggestion_type IN ('false_positive','false_negative','slow_confirmation')", name="ck_rule_suggestion_type"),
        sa.CheckConstraint("status IN ('pending','applied','dismissed')", name="ck_rule_suggestion_status"),
    )
    op.create_index("idx_rule_suggestions_profile_status", "rule_suggestions", ["taxonomy_profile_id", "status"])


def downgrade() -> None:
    op.drop_index("idx_rule_suggestions_profile_status")
    op.drop_table("rule_suggestions")
