"""AuditHashState — singleton que persiste el último hash del audit chain.

Tabla creada por migración 076 (audit_hash_chain). Siempre contiene exactamente
una fila (id=1). Usada por el trigger ``trg_audit_hash_before_insert`` para
encadenar hashes de audit_events sin hacer full-scan de la partición.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditHashState(Base):
    __tablename__ = "audit_hash_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    last_event_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_hash: Mapped[str] = mapped_column(String(64), nullable=False, server_default=text("''"))
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, server_default=text("now()")
    )

    __table_args__ = (CheckConstraint("id = 1", name="audit_hash_state_singleton"),)
