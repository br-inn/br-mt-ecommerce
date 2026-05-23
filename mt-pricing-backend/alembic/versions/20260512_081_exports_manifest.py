"""Tabla exports_manifest — US-1B-04-02.

Registra cada export de precios generado por canal, con filas exportadas,
bloqueadas, referencia al archivo CSV y FX timestamp.

Revision ID: 20260512_081
Revises: 20260512_080
Create Date: 2026-05-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PgUUID

from alembic import op

revision: str = "20260512_081"
down_revision: str = "20260512_080"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exports_manifest",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("channel_code", sa.String(64), nullable=False),
        sa.Column(
            "scheme_code",
            sa.String(64),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "rows_exported",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "rows_blocked",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "file_ref",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column("fx_as_of", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "generated_by",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
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
        sa.CheckConstraint(
            "status IN ('pending', 'completed', 'failed')",
            name="ck_exports_manifest_status",
        ),
    )
    op.create_index(
        "idx_exports_manifest_channel_created",
        "exports_manifest",
        ["channel_code", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_exports_manifest_channel_created", table_name="exports_manifest")
    op.drop_table("exports_manifest")
