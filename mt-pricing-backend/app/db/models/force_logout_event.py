"""ForceLogoutEvent — cola para Realtime broadcast de force-logout (ADR-032).

Creada por migración 20260507_013. El backend popula esta tabla cuando TI
Integración revoca un rol o ejecuta force-logout. La tabla está enrolada en la
publication ``supabase_realtime``, por lo que cada INSERT dispara un evento
Realtime que el frontend del usuario afectado consume para deslogarse
inmediatamente (sin esperar TTL JWT 1h).

Cleanup periódico via Celery task ``mt.audit.cleanup_force_logout_events``
(job_definition sembrado en la misma migración): borra rows > 24h.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UUID_PG


class ForceLogoutEvent(Base):
    __tablename__ = "force_logout_events"

    id: Mapped[UUID] = mapped_column(
        UUID_PG, primary_key=True, server_default=text("gen_random_uuid()"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (Index("ix_force_logout_user_created", "user_id", "created_at"),)
