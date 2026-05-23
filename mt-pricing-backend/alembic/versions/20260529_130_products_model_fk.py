"""Add products.model_id FK → product_models"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260529_130"
down_revision = "20260529_129"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("model_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_products_model_id",
        "products",
        "product_models",
        ["model_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_products_model_id", "products", ["model_id"])


def downgrade() -> None:
    op.drop_index("idx_products_model_id", table_name="products")
    op.drop_constraint("fk_products_model_id", "products", type_="foreignkey")
    op.drop_column("products", "model_id")
