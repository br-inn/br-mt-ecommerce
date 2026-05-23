"""Wave 6 ORM — product_tech_tables (matrix-style technical tables)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as UUID_PG
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if False:  # TYPE_CHECKING
    from app.db.models.product import Product


class ProductTechTable(Base):
    __tablename__ = "product_tech_tables"

    id: Mapped[UUID] = mapped_column(
        UUID_PG, primary_key=True, server_default=text("gen_random_uuid()")
    )
    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(
        Enum(
            "materials_matrix",
            "dimensions_by_dn",
            "pressure_temperature",
            name="tech_table_kind",
            create_type=False,
        ),
        nullable=False,
    )
    schema_version: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'v1'"))
    source: Mapped[str] = mapped_column(
        Enum(
            "manual",
            "imported_pdf",
            "imported_excel",
            name="tech_table_source",
            create_type=False,
        ),
        nullable=False,
        server_default=text("'manual'"),
    )
    data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    source_asset_id: Mapped[UUID | None] = mapped_column(UUID_PG, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )

    product: Mapped["Product"] = relationship(back_populates="tech_tables")

    __table_args__ = (
        UniqueConstraint("product_sku", "kind", name="uq_product_tech_tables_sku_kind"),
        Index("idx_product_tech_tables_sku", "product_sku"),
        Index("idx_product_tech_tables_kind", "kind"),
    )
