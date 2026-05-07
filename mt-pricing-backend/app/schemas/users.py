"""Pydantic schemas — Users / Roles / Permissions API contracts.

Alineado con `mt-api-contract-openapi.yaml` y con el modelo SQLAlchemy
(`app/db/models/user.py`). Idioma de campos = inglés (canónico API).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# Locales soportados Fase 1 — coincide con CheckConstraint `ck_users_locale`.
LocaleStr = Literal["es", "en", "ar"]

# Roles de sistema (seed Agente C).
RoleCode = Literal[
    "comercial",
    "gerente_comercial",
    "ti_integracion",
    "champion",
    "backup_operator",
]


class PermissionResponse(BaseModel):
    """Catálogo de permisos."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    description: str | None = None


class RoleResponse(BaseModel):
    """Rol de sistema con sus permisos efectivos."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None = None
    is_system: bool


class RoleWithPermissionsResponse(RoleResponse):
    permissions: list[PermissionResponse] = Field(default_factory=list)


class UserResponse(BaseModel):
    """Perfil aplicativo del usuario."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str | None = None
    avatar_url: str | None = None
    locale: LocaleStr = "es"
    is_active: bool
    role: RoleResponse | None = None
    last_login_at: datetime | None = None
    created_at: datetime


class MeResponse(UserResponse):
    """`GET /me` enriquece con permisos efectivos resueltos."""

    permissions: list[str] = Field(
        default_factory=list,
        description="Códigos de permiso efectivos (e.g. ['products:read', 'prices:propose']).",
    )


class MeUpdate(BaseModel):
    """`PATCH /me` — solo el propio usuario, sin cambiar role/active."""

    model_config = ConfigDict(extra="forbid")

    full_name: Annotated[str, Field(min_length=2, max_length=100)] | None = None
    avatar_url: str | None = None
    locale: LocaleStr | None = None


class UserInvite(BaseModel):
    """`POST /users/invite` — TI Integración invita por email."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    full_name: Annotated[str, Field(min_length=2, max_length=100)]
    role_code: RoleCode
    locale: LocaleStr = "es"


class UserUpdate(BaseModel):
    """`PATCH /users/{id}` — admin update."""

    model_config = ConfigDict(extra="forbid")

    full_name: Annotated[str, Field(min_length=2, max_length=100)] | None = None
    locale: LocaleStr | None = None
    is_active: bool | None = None


class RoleAssignment(BaseModel):
    """`POST /users/{id}/roles` — asignar rol a usuario."""

    model_config = ConfigDict(extra="forbid")

    role_code: RoleCode
    note: str | None = Field(default=None, max_length=500)


class UserListItem(BaseModel):
    """Listado paginado — versión liviana sin permisos."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str | None
    is_active: bool
    role: RoleResponse | None
    last_login_at: datetime | None
    created_at: datetime
