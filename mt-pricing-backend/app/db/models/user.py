"""User, Role, Permission + assoc tables.

Decisiones (ver `mt-sqlalchemy-models.md` §12.1, §12.2):
- Tabla `public.users` (NO `profiles`) — coherente con FKs del resto del DDL.
- `users.id` = `auth.users.id` (Supabase) via trigger `on_auth_user_created`.
- `roles` modelo híbrido: `id` UUID PK + `code` UNIQUE TEXT.
- Sprint 1 = un usuario tiene un solo rol (`users.role_id`); Sprint 2+ podría
  necesitar M:N pero ahora `role_permissions` es M:N entre roles y permisos.
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
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UuidPkMixin
from app.db.types import UUID_PG


class Role(UuidPkMixin, Base):
    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    permissions_snapshot: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )

    role_permissions: Mapped[list[RolePermission]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )
    users: Mapped[list[User]] = relationship(back_populates="role")

    __table_args__ = (Index("idx_roles_code", "code"),)


class Permission(UuidPkMixin, Base):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    role_permissions: Mapped[list[RolePermission]] = relationship(
        back_populates="permission", cascade="all, delete-orphan"
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[UUID] = mapped_column(
        UUID_PG, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[UUID] = mapped_column(
        UUID_PG, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    role: Mapped[Role] = relationship(back_populates="role_permissions")
    permission: Mapped[Permission] = relationship(back_populates="role_permissions")


class User(Base):
    __tablename__ = "users"

    # PK 1:1 con auth.users.id de Supabase — NO usar gen_random_uuid() default
    # para que el trigger `on_auth_user_created` pueda forzar el id correcto.
    id: Mapped[UUID] = mapped_column(UUID_PG, primary_key=True)
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    locale: Mapped[str] = mapped_column(String(2), nullable=False, server_default=text("'es'"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    role_id: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("roles.id", ondelete="SET NULL")
    )

    delegate_user_id: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL")
    )

    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_logins: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )
    # AuditMixin no se usa aquí porque created_by/updated_by referencian
    # users.id y crearía ciclo en la propia tabla — los modelamos manualmente
    # como FK self-referential con SET NULL.
    created_by: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    role: Mapped[Role | None] = relationship(back_populates="users", foreign_keys=[role_id])

    __table_args__ = (
        CheckConstraint("locale IN ('es','en','ar')", name="ck_users_locale"),
        Index("idx_users_role", "role_id"),
        Index(
            "idx_users_active",
            "is_active",
            postgresql_where=text("is_active = true"),
        ),
    )
