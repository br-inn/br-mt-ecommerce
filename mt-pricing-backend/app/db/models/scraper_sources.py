"""Modelos del módulo Scraper Source Builder — motor de scraper configurable.

Ver docs/superpowers/specs/2026-05-20-scraper-source-builder-design.md
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UuidPkMixin
from app.db.types import UUID_PG

_DESTINATION_PROFILE = Enum(
    "competitor_price",
    "product_data",
    name="scraper_destination_profile",
    create_type=False,
)
_FETCH_MODE = Enum(
    "static",
    "headless",
    "stealth",
    name="scraper_fetch_mode",
    create_type=False,
)
_SOURCE_STATUS = Enum(
    "draft",
    "testing",
    "active",
    "disabled",
    "degraded",
    name="scraper_source_status",
    create_type=False,
)
_VALIDATION_STATUS = Enum(
    "unvalidated",
    "passing",
    "failing",
    name="scraper_recipe_validation_status",
    create_type=False,
)


class ScraperSource(UuidPkMixin, TimestampMixin, Base):
    """Definición configurable y data-driven de un sitio a scrapear."""

    __tablename__ = "scraper_sources"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    destination_profile: Mapped[str] = mapped_column(_DESTINATION_PROFILE, nullable=False)
    fetch_mode: Mapped[str] = mapped_column(
        _FETCH_MODE, nullable=False, server_default=text("'static'::scraper_fetch_mode")
    )
    status: Mapped[str] = mapped_column(
        _SOURCE_STATUS, nullable=False, server_default=text("'draft'::scraper_source_status")
    )
    competitor_brand_id: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("competitor_brands.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    generated_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (UniqueConstraint("slug", name="uq_scraper_sources_slug"),)


class ScraperSourceRecipe(UuidPkMixin, Base):
    """Receta de extracción versionada. Una receta is_live por source."""

    __tablename__ = "scraper_source_recipes"

    source_id: Mapped[UUID] = mapped_column(
        UUID_PG, ForeignKey("scraper_sources.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_live: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    recipe: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    validation_status: Mapped[str] = mapped_column(
        _VALIDATION_STATUS,
        nullable=False,
        server_default=text("'unvalidated'::scraper_recipe_validation_status"),
    )
    has_unapproved_snippet: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    created_by: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (UniqueConstraint("source_id", "version", name="uq_recipe_source_version"),)


class ScraperSourceTestRun(UuidPkMixin, Base):
    """Resultado de validar una receta contra una URL de muestra."""

    __tablename__ = "scraper_source_test_runs"

    source_id: Mapped[UUID] = mapped_column(
        UUID_PG, ForeignKey("scraper_sources.id", ondelete="CASCADE"), nullable=False
    )
    recipe_id: Mapped[UUID] = mapped_column(
        UUID_PG, ForeignKey("scraper_source_recipes.id", ondelete="CASCADE"), nullable=False
    )
    test_url: Mapped[str] = mapped_column(Text, nullable=False)
    html_snapshot_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    field_results: Mapped[dict[str, str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
