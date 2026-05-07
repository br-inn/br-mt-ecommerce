"""Mixins comunes para modelos ORM.

- `TimestampMixin`: `created_at` / `updated_at` con `now()` server-side y
  `onupdate` también server-side (trigger `set_updated_at` en migración).
- `AuditMixin`: `created_by` / `updated_by` FK→users.id (nullable, ON DELETE
  SET NULL para no perder histórico al eliminar un usuario).
- `SoftDeleteMixin`: `deleted_at` nullable (queries de negocio filtran por
  `deleted_at IS NULL`).
- `UuidPkMixin`: `id` UUID PK con `gen_random_uuid()` server-side.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.types import UUID_DEFAULT_SQL, UUID_PG


class UuidPkMixin:
    """PK UUID server-side (gen_random_uuid)."""

    id: Mapped[UUID] = mapped_column(
        UUID_PG,
        primary_key=True,
        server_default=UUID_DEFAULT_SQL,
    )


class TimestampMixin:
    """`created_at` / `updated_at` con server defaults + onupdate.

    `updated_at` adicionalmente se mantiene via trigger `set_updated_at`
    instalado en la migración inicial — el `onupdate` Python-side cubre el
    caso de UPDATEs vía SQLAlchemy ORM, el trigger cubre updates SQL crudos.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )


class AuditMixin:
    """`created_by` / `updated_by` referencian users.id."""

    created_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class SoftDeleteMixin:
    """`deleted_at` nullable. Queries de negocio deben filtrar `IS NULL`."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
