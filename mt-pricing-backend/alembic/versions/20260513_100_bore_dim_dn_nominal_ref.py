"""bore_dim_dn_nominal_ref — columna dn_nominal_ref faltante en product_bore_dimensions.

La migración 099 creó la tabla product_bore_dimensions pero omitió la columna
dn_nominal_ref (FK a dn_nps_reference.dn_nominal) que está definida en el modelo ORM.

Slot 100.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "100"
down_revision: str = "099"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "product_bore_dimensions",
        sa.Column(
            "dn_nominal_ref",
            sa.Text,
            sa.ForeignKey("dn_nps_reference.dn_nominal", ondelete="SET NULL"),
            nullable=True,
            comment="FK a dn_nps_reference para obtener OD de tubería y equivalencia NPS",
        ),
    )
    op.create_index(
        "idx_product_bore_dim_dn_ref",
        "product_bore_dimensions",
        ["dn_nominal_ref"],
    )


def downgrade() -> None:
    op.drop_index("idx_product_bore_dim_dn_ref", table_name="product_bore_dimensions")
    op.drop_column("product_bore_dimensions", "dn_nominal_ref")
