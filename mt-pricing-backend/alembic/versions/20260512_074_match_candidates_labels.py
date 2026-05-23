"""US-RND-01-10 — Human Queue: label + reviewer + calibrated_confidence en match_candidates.

Agrega las columnas necesarias para la cola de validación humana:

- ``calibrated_confidence`` NUMERIC(5,4) — confianza calibrada por el Isotonic
  Calibrator (Sprint 5). Range [0,1]. NULL hasta que corra el calibrador.
- ``label``               VARCHAR(16)  — veredicto del revisor ('accept'/'reject'/'skip').
- ``reviewer_user_id``    UUID FK      — FK a users.id (SET NULL).
- ``reviewed_at``         TIMESTAMPTZ  — timestamp de la revisión.

Index en calibrated_confidence para acelerar el filtro < 0.85 del GET /human-queue.

Revision ID: 20260512_074
Revises: 20260512_071
Create Date: 2026-05-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260512_074"
down_revision: str = "20260512_071"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "match_candidates",
        sa.Column("calibrated_confidence", sa.Numeric(5, 4), nullable=True),
    )
    op.add_column(
        "match_candidates",
        sa.Column("label", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "match_candidates",
        sa.Column(
            "reviewer_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "match_candidates",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_check_constraint(
        "ck_match_candidates_label",
        "match_candidates",
        "label IS NULL OR label IN ('accept','reject','skip')",
    )
    op.create_check_constraint(
        "ck_match_candidates_calibrated_confidence",
        "match_candidates",
        "calibrated_confidence IS NULL OR (calibrated_confidence >= 0 AND calibrated_confidence <= 1)",
    )
    op.create_index(
        "idx_match_candidates_confidence",
        "match_candidates",
        ["calibrated_confidence"],
    )


def downgrade() -> None:
    op.drop_index("idx_match_candidates_confidence", table_name="match_candidates")
    op.drop_constraint(
        "ck_match_candidates_calibrated_confidence", "match_candidates", type_="check"
    )
    op.drop_constraint("ck_match_candidates_label", "match_candidates", type_="check")
    op.drop_column("match_candidates", "reviewed_at")
    op.drop_column("match_candidates", "reviewer_user_id")
    op.drop_column("match_candidates", "label")
    op.drop_column("match_candidates", "calibrated_confidence")
