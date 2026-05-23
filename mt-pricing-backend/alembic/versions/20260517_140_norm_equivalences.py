"""norm_equivalences table (empty seed — admin fills)

Revision ID: 20260517_140
Revises: 20260517_139
"""

import sqlalchemy as sa

from alembic import op

revision = "20260517_140"
down_revision = "20260517_139"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "norm_equivalences",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("norm_a", sa.Text(), nullable=False),
        sa.Column("system_a", sa.Text(), nullable=False),
        sa.Column("norm_b", sa.Text(), nullable=False),
        sa.Column("system_b", sa.Text(), nullable=False),
        sa.Column("equivalence_type", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "equivalence_type IN ('exact','subset','compatible')", name="ck_norm_equiv_type"
        ),
    )


def downgrade() -> None:
    op.drop_table("norm_equivalences")
