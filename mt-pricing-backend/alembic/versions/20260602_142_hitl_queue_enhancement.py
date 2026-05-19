"""hitl_queue_enhancement — high_value_review + is_first_appearance columns (US-SCR-04-08b).

Revision ID: 20260602_142
Revises: 20260602_141
Create Date: 2026-06-02

Cambios en ``hitl_queue``:
- ``high_value_review BOOLEAN NOT NULL DEFAULT false`` — true para items VLM grade A/B
  con precio > AED 1000.
- ``is_first_appearance BOOLEAN NOT NULL DEFAULT false`` — true si el SKU nunca antes
  había aparecido en match_candidates.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "20260602_142"
down_revision = "20260602_141"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # high_value_review — marcador para items de alto valor con VLM A/B
    # ------------------------------------------------------------------
    op.add_column(
        "hitl_queue",
        sa.Column(
            "high_value_review",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # ------------------------------------------------------------------
    # is_first_appearance — marcador para SKUs que nunca se habían visto
    # ------------------------------------------------------------------
    op.add_column(
        "hitl_queue",
        sa.Column(
            "is_first_appearance",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # Índice parcial para facilitar búsquedas de primera aparición pendientes
    op.create_index(
        "ix_hitl_queue_first_appearance",
        "hitl_queue",
        ["is_first_appearance", "priority_score"],
        postgresql_where=sa.text("status = 'pending' AND is_first_appearance = true"),
    )


def downgrade() -> None:
    op.drop_index("ix_hitl_queue_first_appearance", table_name="hitl_queue")
    op.drop_column("hitl_queue", "is_first_appearance")
    op.drop_column("hitl_queue", "high_value_review")
