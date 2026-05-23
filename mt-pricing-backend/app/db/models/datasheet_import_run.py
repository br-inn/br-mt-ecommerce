"""ProductDatasheet — fila aux para persistir la asociación N:M producto ↔
PDF datasheet (Sprint 4 / US-1A-06-04).

Se complementa con ``ImportRun`` (kind='datasheets') que rastrea la corrida
batch del importer. Aquí guardamos sólo el resultado: cada datasheet
asociado a uno o más SKUs.

Decisión Sprint 4 (revisión preasignada 023): reusamos ``import_runs`` con
``kind='datasheets'`` para el run del importer (CHECK ya extendido en
migración 019). Sólo añadimos esta tabla auxiliar para la persistencia del
binario lookup que el frontend / VLM necesitan consultar.
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

DATASHEET_KINDS: tuple[str, ...] = ("ficha_tecnica", "compliance", "manual")


class ProductDatasheet(UuidPkMixin, TimestampMixin, Base):
    """Datasheet PDF asociado a uno o más SKUs.

    Storage path puntúa al bucket Supabase (``product-datasheets/<filename>``)
    o a la ruta local en dev. ``specs_extracted`` JSONB contiene el output
    del :class:`DatasheetSpecs` (DN, PN, material, seal).
    """

    __tablename__ = "product_datasheets"

    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    # SKUs asociados (lista plana; la tabla N:M la dejamos para Fase 1.5+
    # — el ProductService.attach_datasheet decide la persistencia final).
    sku_list: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )

    specs_extracted: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    import_run_id: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("import_runs.id", ondelete="SET NULL")
    )
    uploaded_by: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL")
    )
    uploaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "kind IN ('ficha_tecnica','compliance','manual')",
            name="ck_product_datasheets_kind",
        ),
        UniqueConstraint("storage_path", name="uq_product_datasheets_storage_path"),
        Index("idx_product_datasheets_kind", "kind"),
    )


__all__ = ["DATASHEET_KINDS", "ProductDatasheet"]
