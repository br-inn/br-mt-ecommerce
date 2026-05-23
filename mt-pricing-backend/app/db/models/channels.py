"""Channel + ChannelStateHistory — EP-1B-03 Sprint 8.

Dos tablas:
- channels: estado operacional de canal (6 estados)
- channel_state_history: audit log de transiciones

NOTA: La tabla `channels` y el modelo `Channel` se introdujeron en pricing.py
(mig 010). Este módulo extiende ese modelo con `pilot_with_warnings` y añade
`ChannelStateHistory` como tabla de audit separada (mig 079).

El modelo `Channel` aquí definido reemplaza al de `pricing.py`.
`pricing.py` re-exporta `Channel` desde aquí para backward-compat.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UuidPkMixin
from app.db.types import UUID_PG

# Única fuente de verdad de los valores posibles — usada también en el
# CHECK constraint DDL (ver migración 079).
CHANNEL_STATES: tuple[str, ...] = (
    "inactive",
    "pre_launch",
    "pilot",
    "live",
    "paused",
    "deprecated",
)

_STATES_SQL = "(" + ", ".join(f"'{s}'" for s in CHANNEL_STATES) + ")"


class Channel(UuidPkMixin, TimestampMixin, Base):
    """Canal de venta con ciclo de vida operacional de 6 estados.

    Ciclo: inactive → pre_launch → pilot → live → paused → deprecated.
    Las transiciones quedan registradas en `ChannelStateHistory`.
    """

    __tablename__ = "channels"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'inactive'"),
    )
    schemes_supported: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    # Legado: JSONB inline de transiciones — mantenido para backward-compat
    # con app.api.routes.pricing (actualiza channel.state_history).
    # Las nuevas transiciones deben usar ChannelStateHistory (tabla dedicada).
    state_history: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    # flag: True cuando el paso a pilot fue aprobado con SKUs faltantes
    pilot_with_warnings: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    # Relación de audit log
    state_transitions: Mapped[list[ChannelStateHistory]] = relationship(
        "ChannelStateHistory",
        back_populates="channel",
        cascade="all, delete-orphan",
        lazy="select",
    )

    __table_args__ = (
        CheckConstraint(
            f"state IN {_STATES_SQL}",
            name="ck_channels_state",
        ),
        Index("idx_channels_code", "code"),
        Index("idx_channels_state", "state"),
    )


class ChannelStateHistory(UuidPkMixin, Base):
    """Audit log de transiciones de estado de un canal.

    Cada fila registra: de qué estado vino, a cuál fue, quién lo hizo y
    un comentario opcional.  `pilot_with_warnings` se copia desde el canal
    en el momento de la transición a 'pilot'.
    """

    __tablename__ = "channel_state_history"

    channel_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("channels.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_state: Mapped[str] = mapped_column(String(32), nullable=False)
    to_state: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    comment: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''"),
    )
    pilot_with_warnings: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relación inversa
    channel: Mapped[Channel] = relationship(
        "Channel",
        back_populates="state_transitions",
        lazy="select",
    )

    __table_args__ = (Index("idx_channel_state_history_channel", "channel_id"),)


__all__ = ["CHANNEL_STATES", "Channel", "ChannelStateHistory"]
