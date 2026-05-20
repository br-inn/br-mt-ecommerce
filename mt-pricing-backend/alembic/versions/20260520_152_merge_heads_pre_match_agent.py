"""merge_heads_pre_match_agent

Revision ID: 20260520_152
Revises: 20260519_151, 20260602_144
Create Date: 2026-05-20 13:49:36.366391+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260520_152"
down_revision: str | None = ("20260519_151", "20260602_144")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
