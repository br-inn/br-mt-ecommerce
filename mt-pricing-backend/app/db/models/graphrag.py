"""KgIntegrityResult — historial de chequeos de integridad del Knowledge Graph.

US-F15-01-06 (dashboard monitoreo KG + integridad nightly, Sprint 10 Wave 5-B).

Cada fila corresponde a una ejecución de la task Celery
``mt.graphrag.kg_integrity_check``. La tarea corre a las 02:00 UTC (daily) y
persiste las métricas recogidas del Neo4j para análisis de tendencias.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Float, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP

from app.db.base import Base


class KgIntegrityResult(Base):
    """Resultado de un chequeo nightly de integridad del Knowledge Graph."""

    __tablename__ = "kg_integrity_results"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    checked_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    node_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    edge_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    orphan_nodes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cdc_lag_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ok")
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


__all__ = ["KgIntegrityResult"]
