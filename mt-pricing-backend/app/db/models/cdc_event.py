"""CdcEvent — outbox row for Postgres → graph (Neo4j) propagation.

US-RND-01-11 (Sprint 4) — GraphRAG scaffold + CDC outbox prototype.

Diseño (alineado con ADR-041 §Eventos):

- ``id`` BIGSERIAL PK (orden monotónico → consume por id ASC).
- ``entity_type`` TEXT NOT NULL — `product`, `supplier`, `cost`, `match_candidate`,
  `manufacturer`, `material`. Define cómo el ``schema_mapper`` traduce el payload.
- ``entity_id`` TEXT NOT NULL — PK del row origen (sku/uuid/code en string).
- ``action`` TEXT NOT NULL ∈ {insert, update, delete} — semántica CRUD; el
  dispatcher mapea `insert`+`update` a `merge_node`/`merge_edge` y `delete` a
  `delete_subgraph` (idempotente).
- ``payload_jsonb`` JSONB NOT NULL — snapshot mínimo del row tras la operación
  (NEW.* en triggers Postgres). Para `delete` puede ser solo `{ "id": ... }`.
- ``status`` TEXT NOT NULL DEFAULT 'pending' ∈ {pending, processed, failed,
  dead_letter} — FSM del worker.
- ``attempts`` INT DEFAULT 0 — backoff exponencial; tras 3 fallos pasa a
  ``dead_letter`` (alertable).
- ``last_error`` TEXT NULL — diagnóstico del último intento.
- ``processed_at`` TIMESTAMPTZ NULL — sello al pasar a ``processed``.
- ``created_at`` TIMESTAMPTZ NOT NULL DEFAULT now() — orden de inserción.

Idempotencia: el dispatcher trata `(entity_type, entity_id, action, id)` como
clave; reintentos sobre el mismo row son idempotentes porque el stub `MERGE`
sobreescribe el nodo en lugar de duplicar. Re-procesar un row `processed` es
NO-OP por filtro de status.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


CDC_EVENT_ACTIONS: tuple[str, ...] = ("insert", "update", "delete")
CDC_EVENT_STATUSES: tuple[str, ...] = (
    "pending",
    "processed",
    "failed",
    "dead_letter",
)
CDC_EVENT_ENTITY_TYPES: tuple[str, ...] = (
    "product",
    "supplier",
    "cost",
    "match_candidate",
    "manufacturer",
    "material",
)


class CdcEvent(Base):
    """Outbox row para CDC Postgres → graph store (Neo4j-stub Fase 1, real Fase 2+)."""

    __tablename__ = "cdc_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    payload_jsonb: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (
        CheckConstraint(
            "action IN ('insert','update','delete')",
            name="ck_cdc_events_action",
        ),
        CheckConstraint(
            "status IN ('pending','processed','failed','dead_letter')",
            name="ck_cdc_events_status",
        ),
        CheckConstraint("attempts >= 0", name="ck_cdc_events_attempts_nonneg"),
        # Hot-path: el worker lee `pending` ordenados por `id`.
        Index(
            "idx_cdc_events_pending",
            "id",
            postgresql_where=text("status = 'pending'"),
        ),
        Index("idx_cdc_events_entity", "entity_type", "entity_id"),
    )


__all__ = [
    "CdcEvent",
    "CDC_EVENT_ACTIONS",
    "CDC_EVENT_STATUSES",
    "CDC_EVENT_ENTITY_TYPES",
]
