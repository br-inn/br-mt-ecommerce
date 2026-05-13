"""product_releases_erp01 — EP-ERP-01-02: índice de rendimiento en product_releases.

La tabla `product_releases` ya existe (mig 097). Esta migración añade un
índice parcial sobre `status='active'` para acelerar las consultas de catálogo
por mercado, y documenta el cumplimiento de US-ERP-01-02.

Revision ID: 20260514_105
Revises: 20260513_104
Create Date: 2026-05-14
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260514_105"
down_revision: str = "20260513_104"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_product_releases_status_active
        ON product_releases (product_sku)
        WHERE status = 'active';
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_product_releases_status_active;")
