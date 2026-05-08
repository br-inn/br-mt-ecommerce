"""merge waves 1-4-7 heads

Revision ID: 80af479d704d
Revises: 20260508_030, 20260508_033, 20260508_035
Create Date: 2026-05-08 06:48:57.873270+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '80af479d704d'
down_revision: str | None = ('20260508_030', '20260508_033', '20260508_035')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
