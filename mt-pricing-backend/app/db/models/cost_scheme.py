"""Scheme (cost scheme) — esquema de coste/venta seeded (US-1A-04-01).

5 esquemas inmutables: FBA, FBM, DIRECT_B2C, DIRECT_B2B, MARKETPLACE.
Cada uno define un `cost_components_template` JSONB con la lista de componentes
de coste esperados — el cost validator de S3 (US-1A-04-03) usa este template
para validar el breakdown de cada `costs` row.

Spec: `mt-sqlalchemy-models.md` §7.5 (clase `Scheme_`) + `architecture-mt-pricing-mdm-phase1.md`
§8 tabla `schemes`.

⚠ La clase Python se llama `CostScheme` (no `Scheme_`) para evitar el ugly underscore
del spec; la tabla mantiene el nombre `schemes` (alineado con architecture y FK
en `costs.scheme`, `prices.scheme`).
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.enums import Scheme, values_csv


class CostScheme(Base):
    """Esquema de coste/venta. PK = código enum (FBA/FBM/...).

    `cost_components_template` enumera los componentes esperados para validar
    breakdown en S3. Estructura ejemplo:
        {"required": ["fob","freight","customs","fba_fees","payment_fees"]}
    """

    __tablename__ = "schemes"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    cost_components_template: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    __table_args__ = (
        CheckConstraint(
            f"code IN {values_csv(Scheme)}",
            name="ck_schemes_code",
        ),
    )
