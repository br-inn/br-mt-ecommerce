"""ProductSearchQuery — caché de queries de búsqueda generadas por LLM.

Almacena la query más efectiva para cada (SKU, canal). Se regenera cuando
cambia el hash del producto o el usuario la sobreescribe manualmente.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProductSearchQuery(Base):
    __tablename__ = "product_search_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(
        Text, ForeignKey("products.sku", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    product_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    model_used: Mapped[str | None] = mapped_column(String(64), nullable=True)
    manual_override: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        Index("ix_product_search_queries_sku", "sku"),
    )
