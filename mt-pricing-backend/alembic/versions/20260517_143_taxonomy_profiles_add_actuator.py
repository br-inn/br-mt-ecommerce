"""taxonomy_profiles — add actuator dimension (weight 0.0)

Revision ID: 20260517_143
Revises: 20260517_142
Create Date: 2026-05-17
"""

from __future__ import annotations

from alembic import op

revision = "20260517_143"
down_revision = "20260517_142"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE taxonomy_profiles
        SET weights = weights || '{"actuator": 0.0}'::jsonb
        WHERE NOT (weights ? 'actuator')
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE taxonomy_profiles
        SET weights = weights - 'actuator'
    """)
