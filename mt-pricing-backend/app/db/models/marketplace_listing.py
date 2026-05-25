"""ORM — product_marketplace_listings: per-marketplace listing content."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if False:  # TYPE_CHECKING
    from app.db.models.product import Product

MARKETPLACE_VALUES = ("amazon_uae", "noon_uae", "shopify_storefront")
STATUS_VALUES = ("draft", "ready", "published", "paused")


class MarketplaceListing(Base):
    __tablename__ = "product_marketplace_listings"

    id: Mapped[str] = mapped_column(
        Text, primary_key=True, server_default=text("(gen_random_uuid())::text")
    )
    product_sku: Mapped[str] = mapped_column(
        Text, ForeignKey("products.sku", ondelete="CASCADE"), nullable=False
    )
    marketplace: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    listing_title: Mapped[str | None] = mapped_column(Text)
    listing_description: Mapped[str | None] = mapped_column(Text)
    bullet_points: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    search_keywords: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    ai_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ai_model: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    product: Mapped[Product] = relationship(back_populates="marketplace_listings")

    __table_args__ = (
        UniqueConstraint(
            "product_sku",
            "marketplace",
            name="uq_marketplace_listings_sku_marketplace",
        ),
        CheckConstraint(
            "marketplace IN ('amazon_uae','noon_uae','shopify_storefront')",
            name="ck_marketplace_listings_marketplace",
        ),
        CheckConstraint(
            "status IN ('draft','ready','published','paused')",
            name="ck_marketplace_listings_status",
        ),
        Index("idx_marketplace_listings_sku", "product_sku"),
        Index("idx_marketplace_listings_marketplace", "marketplace"),
        Index("idx_marketplace_listings_status", "status"),
    )


__all__ = ["MARKETPLACE_VALUES", "STATUS_VALUES", "MarketplaceListing"]
