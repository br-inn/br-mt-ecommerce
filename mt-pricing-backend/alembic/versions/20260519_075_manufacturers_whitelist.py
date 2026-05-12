"""manufacturers_whitelist — tabla de fabricantes con dominios canónicos para RIS boost (US-F15-02-03).

Agrega tabla:
- ``manufacturers_whitelist`` — whitelist de fabricantes con canonical_domains (array),
  brand_aliases (array), confidence y active para get_canonical_domains() en ris_boost.

Revision ID: 075
Revises: 074
Create Date: 2026-05-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "075"
down_revision = "074"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "manufacturers_whitelist",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("manufacturer_name", sa.String(length=128), nullable=False),
        sa.Column(
            "canonical_domains",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "brand_aliases",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=False,
            server_default=sa.text("1.0"),
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("manufacturer_name", name="uq_manufacturers_whitelist_name"),
    )
    op.create_index(
        "idx_manufacturers_whitelist_active",
        "manufacturers_whitelist",
        ["active"],
    )


def downgrade() -> None:
    op.drop_index("idx_manufacturers_whitelist_active", table_name="manufacturers_whitelist")
    op.drop_table("manufacturers_whitelist")
