"""ImportRun — persistencia de runs del importer batch (US-1A-06-01).

Complementa al `ImporterService` in-memory (preview/apply wizard, S2):
- El wizard sincrono (preview→apply) sigue viviendo en memoria por proceso.
- El **batch importer** (PimImporter / Celery) usa esta tabla para persistir
  estado de runs disparados async — necesario para que el dashboard pueda
  consultar `GET /imports/{run_id}/status` después de un restart o desde otro
  worker.

Status FSM (`status` column):
    queued   → running → completed
                      → completed_with_errors
                      → failed

Notas:
- `errors` JSONB cap a 100 entradas (display) — el run completo NO se aborta
  por filas individuales malas (ver `pim_importer.run`).
- `summary` JSONB libre para counters extra (e.g. ``data_quality_complete``,
  ``locked_field_skips_total``).
- `triggered_by` nullable porque el endpoint de fixture (dev-only) puede
  correr sin actor — se rellena con un usuario placeholder o NULL.
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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UuidPkMixin
from app.db.types import UUID_PG

# Status FSM permitido — hace match con el CHECK constraint a nivel SQL.
IMPORT_RUN_STATUSES: tuple[str, ...] = (
    "queued",
    "running",
    "completed",
    "completed_with_errors",
    "failed",
)

# Tipos válidos del importer (Fase 1a). Costs/datasheets se enchufan a este
# mismo modelo cuando lleguen sus historias.
IMPORT_RUN_TYPES: tuple[str, ...] = ("pim", "costs", "datasheets")


class ImportRun(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "import_runs"

    import_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_filename: Mapped[str] = mapped_column(Text, nullable=False)
    # Path en Supabase Storage (bucket `imports-raw`) o filesystem path en dev.
    source_storage_path: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'queued'")
    )

    total_rows: Mapped[int | None] = mapped_column(Integer)
    inserted_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    updated_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    skipped_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    error_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    errors: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    summary: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    triggered_by: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL")
    )
    celery_task_id: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "import_type IN ('pim','costs','datasheets')",
            name="ck_import_runs_type",
        ),
        CheckConstraint(
            "status IN ('queued','running','completed','completed_with_errors','failed')",
            name="ck_import_runs_status",
        ),
        Index("idx_import_runs_status", "status"),
        Index("idx_import_runs_type_created", "import_type", "created_at"),
    )
