"""SQLAlchemy models para exports — US-1B-04-02 (ExportManifest) y US-1B-04-05 (LastGoodExport)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base
from app.db.mixins import TimestampMixin, UuidPkMixin
from app.db.types import UUID_PG


class ExportManifest(UuidPkMixin, TimestampMixin, Base):
    """Registro de cada export de precios generado por canal."""

    __tablename__ = "exports_manifest"

    channel_code: Mapped[str] = mapped_column(String(64), nullable=False)
    scheme_code: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("''")
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'pending'")
    )
    rows_exported: Mapped[int] = mapped_column(
        Integer(), nullable=False, server_default=text("0")
    )
    rows_blocked: Mapped[int] = mapped_column(
        Integer(), nullable=False, server_default=text("0")
    )
    file_ref: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("''")
    )
    fx_as_of: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    generated_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'completed', 'failed')",
            name="ck_exports_manifest_status",
        ),
        Index("idx_exports_manifest_channel_created", "channel_code", "created_at"),
    )


class LastGoodExport(Base, UuidPkMixin):
    """Registro del export completado más reciente por canal/scheme — US-1B-04-05."""

    __tablename__ = "last_good_exports"

    channel_code: Mapped[str] = mapped_column(String, nullable=False)
    scheme_code: Mapped[str] = mapped_column(String, nullable=False)
    export_manifest_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("exports_manifest.id", ondelete="SET NULL"),
        nullable=True,
    )
    rows_exported: Mapped[int] = mapped_column(Integer, nullable=False)
    file_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("uq_last_good_exports_channel_scheme", "channel_code", "scheme_code", unique=True),
    )


__all__ = ["ExportManifest", "LastGoodExport"]
