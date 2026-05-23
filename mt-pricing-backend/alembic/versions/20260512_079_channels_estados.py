"""Tabla channels con 6 estados + channel_state_history.

Revision ID: 20260512_079
Revises: 20260512_078
Create Date: 2026-05-12

Cambios:
- ADD COLUMN channels.pilot_with_warnings (Boolean, default false)
- ADD INDEX idx_channels_code en channels.code (ya existía UNIQUE, pero faltaba idx explícito)
- CREATE TABLE channel_state_history (audit log de transiciones de estado)
- Seed: 4 canales canónicos con código UPPER_CASE (ON CONFLICT DO NOTHING)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260512_079"
down_revision: str = "20260512_078"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Añadir pilot_with_warnings a channels (tabla ya existe desde mig 010)
    # ------------------------------------------------------------------
    op.add_column(
        "channels",
        sa.Column(
            "pilot_with_warnings",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # Índice explícito en code (la UNIQUE constraint ya garantiza unicidad,
    # pero el índice nombrado facilita EXPLAIN y el modelo ORM)
    op.create_index("idx_channels_code", "channels", ["code"])

    # ------------------------------------------------------------------
    # 2. Crear channel_state_history
    # ------------------------------------------------------------------
    op.create_table(
        "channel_state_history",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("channel_id", sa.UUID(), nullable=False),
        sa.Column("from_state", sa.String(32), nullable=False),
        sa.Column("to_state", sa.String(32), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "comment",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column(
            "pilot_with_warnings",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_channel_state_history"),
        sa.ForeignKeyConstraint(
            ["channel_id"],
            ["channels.id"],
            ondelete="CASCADE",
            name="fk_csh_channel_id",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            ondelete="SET NULL",
            name="fk_csh_actor_user_id",
        ),
    )
    op.create_index(
        "idx_channel_state_history_channel",
        "channel_state_history",
        ["channel_id"],
    )

    # ------------------------------------------------------------------
    # 3. Seed 4 canales canónicos (UPPER_CASE codes — US-1B-03-01)
    #    ON CONFLICT DO NOTHING para no pisar los 5 canales snake_case
    #    seeded en mig 010.
    # ------------------------------------------------------------------
    op.execute("""
INSERT INTO channels (code, name, state, schemes_supported)
VALUES
  ('AMAZON_UAE',  'Amazon UAE',  'inactive', '[]'),
  ('NOON_UAE',    'Noon UAE',    'inactive', '[]'),
  ('B2C_DIRECT',  'B2C Direct',  'inactive', '[]'),
  ('B2B_DIRECT',  'B2B Direct',  'inactive', '[]')
ON CONFLICT (code) DO NOTHING;
""")


def downgrade() -> None:
    op.drop_index("idx_channel_state_history_channel", table_name="channel_state_history")
    op.drop_table("channel_state_history")
    op.drop_index("idx_channels_code", table_name="channels")
    op.drop_column("channels", "pilot_with_warnings")
