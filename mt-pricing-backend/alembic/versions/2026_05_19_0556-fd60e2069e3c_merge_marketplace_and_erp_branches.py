"""merge_marketplace_and_erp_branches

Revision ID: fd60e2069e3c
Revises: 20260518138a, 20260602_143
Create Date: 2026-05-19 05:56:51.439015+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'fd60e2069e3c'
down_revision: str | None = ('20260518138a', '20260602_143')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
