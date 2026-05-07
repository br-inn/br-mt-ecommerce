"""FeatureFlag — runtime toggle persistente con audit (US-1A-09-08, Sprint 5).

Single-row-per-key JSONB store con audit columns:
- ``key``         TEXT PK   — nombre canónico (e.g. ``MT_LIVE_NETWORK_AMAZON_UAE``).
- ``value_jsonb`` JSONB     — para soportar valores complejos en futuras iteraciones
  (S5 sólo guardamos ``{"enabled": true|false}``).
- ``updated_by``  UUID NULL — usuario que hizo el último toggle.
- ``updated_at``  TIMESTAMPTZ NOT NULL — wall-clock del último toggle.
- ``created_at``  TIMESTAMPTZ NOT NULL — primer insert.

Audit per-toggle: la migración `027` siembra los flags conocidos a `false`.
Cada UPDATE escribe `updated_by` + `updated_at`. Para audit trail completo
(quien tocó qué cuándo) hay un trigger BEFORE UPDATE que copia el row anterior
a ``audit_events`` (mismo patrón que jobs/users — ver migración 027).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UUID_PG


class FeatureFlag(Base):
    """Runtime toggle persistente — backend de :class:`FlagService`."""

    __tablename__ = "feature_flags"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{\"enabled\": false}'::jsonb"),
    )
    updated_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


__all__ = ["FeatureFlag"]
