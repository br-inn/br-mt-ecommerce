"""AssetLink ORM model — Fase 4 polymorphic asset references (PDF §11).

`asset_links` permite que un asset (`product_assets`) esté vinculado a
cualquier owner del catálogo (`product`, `variant`, `series`, `family`,
`spare_part`) con un `role` semántico (image_padre, ficha_pdf, etc.).

Diseño:
- `owner_type` + `owner_id` polimórficos — sin relationship hacia el owner;
  la resolución se hace manualmente en el servicio (cada owner_type tiene su
  tabla destino: products.sku, series.id, ...).
- `asset_id` FK a `product_assets.id` con relationship.
- Único constraint `(asset_id, owner_type, owner_id, role)` para evitar
  duplicados lógicos del mismo asset bajo el mismo rol.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UuidPkMixin
from app.db.types import UUID_PG


OWNER_TYPES = ("product", "variant", "series", "family", "spare_part")

ROLES = (
    "image_padre",
    "banner",
    "ficha_pdf",
    "manual_pdf",
    "ce_pdf",
    "catalogo_pdf",
    "exploded_3d",
    "section_drawing",
    "dimensions_drawing",
    "video",
    "web_image",
    "main_image",
)


class AssetLink(UuidPkMixin, Base):
    """Link polimórfico entre `product_assets` y cualquier owner."""

    __tablename__ = "asset_links"

    asset_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("product_assets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    owner_type: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    order_index: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relationship hacia ProductAsset (no back_populates — viewonly desde aquí).
    asset: Mapped["ProductAsset"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "ProductAsset",
        foreign_keys=[asset_id],
        lazy="joined",
    )

    __table_args__ = (
        CheckConstraint(
            "owner_type IN (" + ", ".join(f"'{t}'" for t in OWNER_TYPES) + ")",
            name="ck_asset_links_owner_type",
        ),
        CheckConstraint(
            "role IN (" + ", ".join(f"'{r}'" for r in ROLES) + ")",
            name="ck_asset_links_role",
        ),
        UniqueConstraint(
            "asset_id",
            "owner_type",
            "owner_id",
            "role",
            name="uq_asset_links_asset_owner_role",
        ),
        Index("ix_al_owner", "owner_type", "owner_id"),
        Index("ix_al_asset", "asset_id"),
    )
