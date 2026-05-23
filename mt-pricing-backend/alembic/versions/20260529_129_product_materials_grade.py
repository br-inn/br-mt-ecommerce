"""Add material_grade, material_standard, surface_treatment to product_materials"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260529_129"
down_revision = "20260529_128"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("product_materials", sa.Column("material_grade", sa.Text(), nullable=True))
    op.add_column("product_materials", sa.Column("material_standard", sa.Text(), nullable=True))
    op.add_column("product_materials", sa.Column("surface_treatment", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("product_materials", "surface_treatment")
    op.drop_column("product_materials", "material_standard")
    op.drop_column("product_materials", "material_grade")
