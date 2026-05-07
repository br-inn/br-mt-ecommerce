"""matching_v2 — Sprint 4 provenance + calibration columns para `match_candidates`.

Cambios:

- Añade columnas a ``match_candidates``:
    * ``raw_payload_jsonb``    JSONB NULL  — payload crudo del fetcher (Bright Data
      response, Noon HTML scrape, etc.) para auditoría / replay.
    * ``fetched_at``           TIMESTAMPTZ NULL  — momento exacto del fetch (≠ created_at
      que es el insert local). Permite calcular SLA del adapter.
    * ``calibrated_score``     NUMERIC(5,4) NULL  — score post-isotonic calibrator
      en [0,1] con 4 decimales (probabilidad real de match).
    * ``vlm_verdict``          TEXT NULL — uno de {match, drift, reject, uncertain}
      con CHECK constraint.
    * ``vlm_reasoning``        TEXT NULL — rationale corto del VLM judge (max 280).
    * ``pipeline_version``     TEXT NULL — bump de S3-foundation-v1 → S4-real-adapters-v1.
    * ``calibrator_version``   TEXT NULL — id semántico del calibrator usado.

NOTA — gestión de slot 024 (preasignado al agente Sprint 4 adapters):
- Esta migración asume que 021/022/023 están reservadas para agentes hermanos
  del mismo sprint.
- ``down_revision`` apunta a ``20260507_023`` — si al merge ese slot todavía
  no existe, se renumerará en code review.
- NO se aplica con ``alembic upgrade head`` (se difiere igual que 020).

Revision ID: 20260507_024
Revises: 20260507_023
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260507_024"
down_revision: str | None = "20260507_023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "match_candidates",
        sa.Column(
            "raw_payload_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "match_candidates",
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "match_candidates",
        sa.Column("calibrated_score", sa.Numeric(5, 4), nullable=True),
    )
    op.add_column(
        "match_candidates",
        sa.Column("vlm_verdict", sa.Text(), nullable=True),
    )
    op.add_column(
        "match_candidates",
        sa.Column("vlm_reasoning", sa.Text(), nullable=True),
    )
    op.add_column(
        "match_candidates",
        sa.Column("pipeline_version", sa.Text(), nullable=True),
    )
    op.add_column(
        "match_candidates",
        sa.Column("calibrator_version", sa.Text(), nullable=True),
    )

    op.create_check_constraint(
        "ck_match_candidates_vlm_verdict",
        "match_candidates",
        "vlm_verdict IS NULL OR vlm_verdict IN ('match','drift','reject','uncertain')",
    )
    op.create_check_constraint(
        "ck_match_candidates_calibrated_score_range",
        "match_candidates",
        "calibrated_score IS NULL OR (calibrated_score >= 0 AND calibrated_score <= 1)",
    )

    # Index util para listados "auto_match candidates" filtrando por calibrated_score.
    op.create_index(
        "idx_match_candidates_calibrated",
        "match_candidates",
        ["product_sku", "calibrated_score"],
        postgresql_where=sa.text("calibrated_score IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_match_candidates_calibrated", table_name="match_candidates")
    op.drop_constraint(
        "ck_match_candidates_calibrated_score_range",
        "match_candidates",
        type_="check",
    )
    op.drop_constraint(
        "ck_match_candidates_vlm_verdict",
        "match_candidates",
        type_="check",
    )
    op.drop_column("match_candidates", "calibrator_version")
    op.drop_column("match_candidates", "pipeline_version")
    op.drop_column("match_candidates", "vlm_reasoning")
    op.drop_column("match_candidates", "vlm_verdict")
    op.drop_column("match_candidates", "calibrated_score")
    op.drop_column("match_candidates", "fetched_at")
    op.drop_column("match_candidates", "raw_payload_jsonb")
