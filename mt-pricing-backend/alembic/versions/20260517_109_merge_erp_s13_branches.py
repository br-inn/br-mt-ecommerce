"""merge_erp_s13_branches — consolida heads paralelos EP-ERP-01/02/03.

EP-ERP-01 (feat/erp-01-ux): 20260514_105→106 — UX Producto SAP Fiori/Akeneo
EP-ERP-02 (feat/erp-02-inv): 20260515_105→108 — Inventario v2 Movement Types
EP-ERP-03 (feat/erp-03-p2p): 20260516_105→107 — Compras P2P PR/Approval/PIR

Revision ID: 20260517_109
Revises: 20260514_106, 20260515_108, 20260516_107
Create Date: 2026-05-17
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "20260517_109"
down_revision: tuple[str, ...] = (
    "20260514_106",
    "20260515_108",
    "20260516_107",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
