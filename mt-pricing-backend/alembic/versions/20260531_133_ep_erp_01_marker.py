"""ep_erp_01_marker — Marcador EP-ERP-01: UX Producto SAP Fiori/Akeneo.

Documenta que las tablas y columnas de EP-ERP-01 ya existen en la cadena
de migraciones anteriores (migración 097):

  - M1-01: tabla ``product_releases`` (US-ERP-01-02)
  - M1-04: columna ``products.base_uom`` + tabla ``product_uom_conversions`` (US-ERP-01-03)
  - M1-05: valor 'in_review' en enum ``lifecycle_status`` (US-ERP-01-01)
  - M1-08: columna ``products.gtin`` (US-ERP-01-04)

Esta migración es un marcador no-op que establece la continuidad de la
cadena lineal desde 20260530_132 (competitor_brands HEAD).

Slot 133.

Revision ID: 20260531_133
Revises: 20260530132
Create Date: 2026-05-31
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "20260531_133"
down_revision: str = "20260530132"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # No-op: todos los objetos de EP-ERP-01 ya existen en la BD
    # (creados por migraciones 097-098 en la rama M1).
    pass


def downgrade() -> None:
    pass
