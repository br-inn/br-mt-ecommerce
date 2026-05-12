"""Seed feature flag channel_recommendation = false.

US-1B-03-04 — channel_recommendation feature flag (default off Fase 1).

Revision ID: 20260512_080
Revises: 20260512_079
Create Date: 2026-05-12
"""

from __future__ import annotations

from alembic import op

# ---------------------------------------------------------------------------
# Alembic identifiers
# ---------------------------------------------------------------------------
revision: str = "20260512_080"
down_revision: str = "20260512_079"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO feature_flags (key, value_jsonb, created_at, updated_at)
        VALUES ('channel_recommendation', '{"enabled": false}', now(), now())
        ON CONFLICT (key) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("DELETE FROM feature_flags WHERE key = 'channel_recommendation'")
