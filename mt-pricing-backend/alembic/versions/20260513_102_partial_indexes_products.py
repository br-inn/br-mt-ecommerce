"""partial_indexes_products — índices parciales WHERE deleted_at IS NULL.

Todos los queries del catálogo filtran `deleted_at IS NULL`. Un partial index
incluye solo filas no-eliminadas: más pequeño, más rápido en writes, y el
planner lo usa en queries que incluyen ese predicado.

Ref: query-partial-indexes best practice (Supabase Postgres).

Revision ID: 20260513_102
Revises: 20260513_101
Create Date: 2026-05-13
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "20260513_102"
down_revision: str = "20260513_101"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # (lifecycle_status) WHERE deleted_at IS NULL
    # Cubre: Product.lifecycle_status == 'active' AND deleted_at IS NULL (hot path).
    op.create_index(
        "idx_products_active_lifecycle",
        "products",
        ["lifecycle_status"],
        postgresql_using="btree",
        postgresql_where=text("deleted_at IS NULL"),
        if_not_exists=True,
    )
    # (family) WHERE deleted_at IS NULL
    # Cubre: list_by_family (family + not deleted + lifecycle).
    op.create_index(
        "idx_products_family_not_deleted",
        "products",
        ["family"],
        postgresql_using="btree",
        postgresql_where=text("deleted_at IS NULL"),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("idx_products_family_not_deleted", table_name="products", if_exists=True)
    op.drop_index("idx_products_active_lifecycle", table_name="products", if_exists=True)
