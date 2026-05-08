"""facet_indexes — Wave 10: indexes for /products/facets performance.

Sin estos índices cada faceta hace seq scan ~600ms sobre 5K rows.
Con estos + asyncio.gather → p95 ~150ms.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260508_041"
down_revision: str | None = "20260508_040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("idx_products_material", "products", ["material"])
    op.create_index("idx_products_dn", "products", ["dn"])
    op.create_index("idx_products_pn", "products", ["pn"])
    op.create_index("idx_products_data_quality", "products", ["data_quality"])
    op.create_index("idx_products_image_status", "products", ["image_status"])
    op.create_index("idx_products_updated_at", "products", ["updated_at"])


def downgrade() -> None:
    for ix in (
        "idx_products_updated_at",
        "idx_products_image_status",
        "idx_products_data_quality",
        "idx_products_pn",
        "idx_products_dn",
        "idx_products_material",
    ):
        op.drop_index(ix, table_name="products")
