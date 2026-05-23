"""comparator_model_registry — tabla de registro de modelos embedding fine-tuned (US-F15-03-02).

Revision ID: 073
Revises: 072
Create Date: 2026-05-19
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "073"
down_revision = "072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "comparator_model_registry",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("base_model", sa.String(256), nullable=False),
        sa.Column("storage_path", sa.Text, nullable=False),
        sa.Column(
            "eval_metrics_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "trained_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="candidate",
        ),
    )
    op.create_index(
        "ix_comparator_model_registry_status",
        "comparator_model_registry",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_comparator_model_registry_status",
        table_name="comparator_model_registry",
    )
    op.drop_table("comparator_model_registry")
