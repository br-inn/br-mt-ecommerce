"""Currency — moneda ISO-4217 mínima (Sprint 2).

Tabla seed-only en S2: contiene USD, EUR, AED (base), SAR. La gestión completa
de FX (`fx_rates`, triggers as-of stamping, UI admin) llega en S3 (US-1A-05-01,
US-1A-05-03). Aquí sólo dejamos la tabla + 4 filas para que `suppliers.contract_currency`
y, más adelante, `costs.currency` puedan validar FK.

Spec: `mt-sqlalchemy-models.md` §7.4. Adelantado a S2 por dependencia de
US-1A-03-01 (suppliers); ver decisión Apéndice B sprint2-backlog-refined.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Currency(Base):
    __tablename__ = "currencies"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    symbol: Mapped[str | None] = mapped_column(Text)
    decimals: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("2")
    )
    is_base: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint("decimals BETWEEN 0 AND 8", name="ck_currencies_decimals"),
        # Una sola moneda base permitida (partial unique index sobre is_base=true).
        Index(
            "uq_currencies_one_base",
            "is_base",
            unique=True,
            postgresql_where=text("is_base = true"),
        ),
    )
