"""AuditEvent — particionable por mes (PARTITION BY RANGE on event_at).

Decisiones (architecture §8.10):
- PK compuesta `(id, event_at)` para soportar partitioning por rango temporal.
- Hash chain `prev_hash` / `current_hash` calculado server-side por trigger
  (ver `supabase/migrations/20260506_002_audit_chain.sql`).
- Particiones mensuales se crean en migraciones futuras (Sprint 1: tabla
  declarativa con `postgresql_partition_by`; las particiones concretas
  `audit_events_YYYY_MM` se crean en `op.execute` aparte — TODO Sprint 2).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UUID_PG


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(BigInteger, autoincrement=True, nullable=False)
    event_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    actor_id: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL")
    )
    actor_email: Mapped[str | None] = mapped_column(Text)
    actor_role: Mapped[str | None] = mapped_column(Text)

    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)

    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    payload_diff: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    reason: Mapped[str | None] = mapped_column(Text)

    # Hash chain — calculado por trigger BEFORE INSERT.
    prev_hash: Mapped[str | None] = mapped_column(String(64))
    current_hash: Mapped[str | None] = mapped_column(String(64))

    request_id: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        PrimaryKeyConstraint("id", "event_at", name="pk_audit_events"),
        Index("idx_audit_entity", "entity_type", "entity_id", "event_at"),
        Index("idx_audit_actor", "actor_id", "event_at"),
        Index("idx_audit_action", "action", "event_at"),
        Index("idx_audit_request", "request_id"),
        {"postgresql_partition_by": "RANGE (event_at)"},
    )
