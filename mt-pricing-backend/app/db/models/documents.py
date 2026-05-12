"""Document ORM model — Fase 4 versioned controlled documents (PDF §11).

Tabla `documents`: fichas técnicas, manuales, declaraciones CE, certificados
y catálogos como entidades gobernadas, con versionado e idioma.

El binario vive en `product_assets` (FK `asset_id`). El link a productos /
series / etc. se hace via `asset_links` polimórfica — `Document` modela
"qué documento es", `AssetLink` modela "dónde se muestra".
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UuidPkMixin
from app.db.types import UUID_PG


DOCUMENT_TYPES = (
    "ficha_tecnica",
    "manual",
    "declaracion_ce",
    "certificado",
    "catalogo",
)


class Document(UuidPkMixin, Base):
    """Documento controlado con versión + idioma."""

    __tablename__ = "documents"

    type: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(CHAR(length=2), nullable=False)
    asset_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("product_assets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    issued_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relationship hacia ProductAsset (joined eager — siempre se quiere el binario).
    asset: Mapped["ProductAsset"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "ProductAsset",
        foreign_keys=[asset_id],
        lazy="joined",
    )

    __table_args__ = (
        CheckConstraint(
            "type IN (" + ", ".join(f"'{t}'" for t in DOCUMENT_TYPES) + ")",
            name="ck_documents_type",
        ),
        UniqueConstraint(
            "code", "version", "language", name="uq_documents_code_version_language"
        ),
        Index("ix_doc_type", "type"),
        Index("ix_doc_asset", "asset_id"),
    )
