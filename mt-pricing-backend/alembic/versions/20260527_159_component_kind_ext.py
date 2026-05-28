"""component_kind_ext — agrega nuevos valores al enum component_kind.

Nuevos componentes basados en análisis de fichas técnicas:
  nut           → tuercas de unión, empaquetaduras, auto-bloqueantes
  packing       → prensaestopas, packing gland, stem packing
  bonnet        → bonete / segunda pieza del cuerpo
  insert        → insertos roscados (latón, acero)
  spring        → muelles / spring washers
  washer        → arandelas (thrust washer, plain washer)
  o_ring        → O-rings de vástago
  cap           → tapas / end caps

Slot 159.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260527_159"
down_revision: str | None = "20260525_158"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_VALUES = ["nut", "packing", "bonnet", "insert", "spring", "washer", "o_ring", "cap"]


def upgrade() -> None:
    for val in _NEW_VALUES:
        op.execute(f"ALTER TYPE component_kind ADD VALUE IF NOT EXISTS '{val}'")


def downgrade() -> None:
    # PostgreSQL no permite eliminar valores de un enum sin recrearlo completo.
    # Downgrade seguro: no hace nada (los valores extra son inofensivos).
    pass
