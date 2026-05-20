"""merge heads — unifica los linajes 20260520_154 y 20260602_145.

Revision ID: 20260602_146
Revises: 20260520_154, 20260602_145
Create Date: 2026-05-20

Migración de merge (no-op) para resolver los dos heads divergentes de Alembic
que la rama traía de la integración de features paralelas. Permite que
`alembic upgrade head` resuelva a un único head. No modifica el schema.
"""
from __future__ import annotations

# revision identifiers, used by Alembic.
revision = "20260602_146"
down_revision = ("20260520_154", "20260602_145")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
