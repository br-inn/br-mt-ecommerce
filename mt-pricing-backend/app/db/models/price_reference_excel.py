"""PriceReferenceExcel — precios de referencia provenientes del proceso Excel manual.

Creada por migración 20260512_073 (US-1B-05-01). Almacena los precios del
proceso Excel previo para el cálculo de diff en el reporte de parallel run
(app vs Excel).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, Index, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UUID_PG


class PriceReferenceExcel(Base):
    __tablename__ = "price_reference_excel"

    id: Mapped[UUID] = mapped_column(
        UUID_PG, primary_key=True, server_default=text("gen_random_uuid()"), nullable=False
    )
    sku: Mapped[str] = mapped_column(String(128), nullable=False)
    channel: Mapped[str] = mapped_column(String(64), nullable=False)
    reference_price_aed: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        Index("idx_price_reference_excel_loaded_at", "loaded_at"),
        Index("idx_price_reference_excel_sku_channel", "sku", "channel"),
    )
