"""PricingGoldenTier — configuración de tiers de bundling psicológico v5.1.

Creada por migración 20260507_021 (pricing_engine_v51). Permite al motor de
precios leer las reglas de redondeo psicológico sin recompilar, soportando
override en runtime. Los tiers son firmados por el área comercial (Paula).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PricingGoldenTier(Base):
    __tablename__ = "pricing_golden_tiers"

    name: Mapped[str] = mapped_column(String, primary_key=True, nullable=False)
    upper_bound: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    endings: Mapped[str] = mapped_column(Text, nullable=False)
    modulus: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    tolerance: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
