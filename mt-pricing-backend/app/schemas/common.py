"""Shared API schemas — RFC 7807 + paginación.

Alineado con `mt-api-contract-openapi.yaml`. Cualquier endpoint que devuelve
error sigue el shape de `ProblemDetails`.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ProblemDetails(BaseModel):
    """RFC 7807 Problem Details — formato canónico de errores HTTP."""

    model_config = ConfigDict(populate_by_name=True)

    type: str = Field(
        default="about:blank",
        description="URI que identifica el tipo de error (e.g. https://mtme-api/errors/<code>).",
    )
    title: str = Field(description="Resumen corto, human-readable, agnóstico de instancia.")
    status: int = Field(ge=400, le=599, description="HTTP status code.")
    detail: str | None = Field(default=None, description="Explicación específica de la instancia.")
    instance: str | None = Field(
        default=None,
        description="URI que identifica la ocurrencia concreta (e.g. /api/v1/products/123).",
    )
    code: str | None = Field(default=None, description="Código aplicativo estable.")
    extra: dict[str, Any] | None = Field(default=None, description="Contexto adicional opcional.")


class Cursor(BaseModel):
    """Cursor opaco para paginación keyset.

    Convención: serializar como base64url(json({"k": <last_key>, "ts": <iso>})).
    Los repositorios (Agente G) son los que codifican/decodifican; aquí sólo
    declaramos el shape público.
    """

    model_config = ConfigDict(extra="forbid")

    next: str | None = Field(default=None, description="Cursor para la página siguiente.")
    prev: str | None = Field(default=None, description="Cursor para la página anterior.")


class Pagination(BaseModel, Generic[T]):
    """Envoltorio paginado estándar para listados."""

    model_config = ConfigDict(extra="forbid")

    items: list[T] = Field(description="Página actual de resultados.")
    cursor: Cursor = Field(default_factory=Cursor, description="Cursores de navegación.")
    total: int | None = Field(
        default=None,
        ge=0,
        description="Total absoluto si el endpoint lo expone (puede ser caro).",
    )
    page_size: int = Field(ge=1, le=500, description="Tamaño de página solicitado.")
