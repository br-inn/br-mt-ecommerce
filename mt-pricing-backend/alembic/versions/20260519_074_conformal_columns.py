"""conformal_columns — conf_lower, conf_upper, review_priority en match_candidates (US-F15-03-03).

Agrega columnas para conformal prediction / Venn-Abers:

- ``conf_lower``       NUMERIC(5,4) — cota inferior del intervalo de confianza.
- ``conf_upper``       NUMERIC(5,4) — cota superior del intervalo de confianza.
- ``review_priority``  VARCHAR(16)  — prioridad de revisión humana ('low'/'high'/NULL).

Revision ID: 074
Revises: 073
Create Date: 2026-05-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "074"
down_revision = "073"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "match_candidates",
        sa.Column("conf_lower", sa.Numeric(5, 4), nullable=True),
    )
    op.add_column(
        "match_candidates",
        sa.Column("conf_upper", sa.Numeric(5, 4), nullable=True),
    )
    op.add_column(
        "match_candidates",
        sa.Column("review_priority", sa.String(length=16), nullable=True),
    )
    op.create_index(
        "idx_mc_conf_lower",
        "match_candidates",
        ["conf_lower"],
    )
    op.create_index(
        "idx_mc_conf_upper",
        "match_candidates",
        ["conf_upper"],
    )


def downgrade() -> None:
    op.drop_index("idx_mc_conf_upper", table_name="match_candidates")
    op.drop_index("idx_mc_conf_lower", table_name="match_candidates")
    op.drop_column("match_candidates", "review_priority")
    op.drop_column("match_candidates", "conf_upper")
    op.drop_column("match_candidates", "conf_lower")
