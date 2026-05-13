"""fk_indexes_products — índices explícitos en FKs de la tabla products.

Postgres no crea índices automáticamente para FK. Sin ellos los CASCADE DELETE
y JOINs desde vocabularios (brands, families, series, materials) hacen seq
scan completo sobre products.

Ref: schema-foreign-key-indexes best practice (Supabase Postgres).

Revision ID: 20260513_101
Revises: 100
Create Date: 2026-05-13
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260513_101"
down_revision: str = "100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (index_name, table, column)
_INDEXES: list[tuple[str, str, str]] = [
    ("idx_products_brand_id",         "products", "brand_id"),
    ("idx_products_family_id",        "products", "family_id"),
    ("idx_products_subfamily_id",     "products", "subfamily_id"),
    ("idx_products_type_id",          "products", "type_id"),
    ("idx_products_series_id",        "products", "series_id"),
    ("idx_products_material_id",      "products", "material_id"),
    ("idx_products_parent_sku",       "products", "parent_sku"),
    ("idx_products_display_pair_sku", "products", "display_pair_sku"),
    ("idx_products_created_by",       "products", "created_by"),
    ("idx_products_updated_by",       "products", "updated_by"),
]


def upgrade() -> None:
    for name, table, col in _INDEXES:
        op.create_index(name, table, [col], postgresql_using="btree", if_not_exists=True)


def downgrade() -> None:
    for name, table, _col in reversed(_INDEXES):
        op.drop_index(name, table_name=table, if_exists=True)
