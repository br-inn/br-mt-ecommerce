"""Pydantic V2 schemas — Wave 3 (multi-componente).

Cubre:
- ``ProductMaterial`` — material por componente (cuerpo, cierre, asientos…).
- ``ProductConnection`` — conexión física por puerto (1..3+ vías).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# ---------------------------------------------------------------------------
# Vocabularios (sincronizados con enums Postgres en migration 038).
# ---------------------------------------------------------------------------
ComponentKind = Literal[
    "body",
    "closure",
    "seat",
    "gasket",
    "screen",
    "actuator_housing",
    "stem",
    "handle",
    "other",
]

ConnectionType = Literal[
    "flange",
    "threaded",
    "weld",
    "press",
    "push_fit",
    "compression",
    "other",
]

# Material es texto libre — el catálogo crece con el tiempo y la
# normalización se hace por importer/clasificador.
MaterialStr = Annotated[str, StringConstraints(min_length=1, max_length=128, strip_whitespace=True)]


# ---------------------------------------------------------------------------
# ProductMaterial
# ---------------------------------------------------------------------------
class ProductMaterialBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    component: ComponentKind
    position: int = Field(default=0, ge=0, le=99)
    material: MaterialStr
    observations: str | None = Field(default=None, max_length=512)


class ProductMaterialCreate(ProductMaterialBase):
    """Body para añadir un material a un producto."""


class ProductMaterialPatch(BaseModel):
    """Patch parcial — solo material y observations son editables; el PK queda fijo."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    material: MaterialStr | None = None
    observations: str | None = Field(default=None, max_length=512)


class ProductMaterialResponse(ProductMaterialBase):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    product_sku: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# ProductConnection
# ---------------------------------------------------------------------------
class ProductConnectionBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    position: int = Field(ge=1, le=8, description="Puerto físico (1..8). Position fija el orden.")
    connection_type: ConnectionType
    dn: str | None = Field(default=None, max_length=16)
    dn_real: str | None = Field(default=None, max_length=16)
    size: str | None = Field(default=None, max_length=64)
    threading: str | None = Field(default=None, max_length=32)
    notes: str | None = Field(default=None, max_length=512)


class ProductConnectionCreate(ProductConnectionBase):
    """Body para añadir una conexión a un producto."""


class ProductConnectionPatch(BaseModel):
    """Patch parcial — todo opcional; position fija."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    connection_type: ConnectionType | None = None
    dn: str | None = Field(default=None, max_length=16)
    dn_real: str | None = Field(default=None, max_length=16)
    size: str | None = Field(default=None, max_length=64)
    threading: str | None = Field(default=None, max_length=32)
    notes: str | None = Field(default=None, max_length=512)


class ProductConnectionResponse(ProductConnectionBase):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    product_sku: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Bulk replace payloads (PUT /products/{sku}/materials and /connections)
# ---------------------------------------------------------------------------
class ProductMaterialsReplaceRequest(BaseModel):
    """Reemplaza TODA la lista de materiales del producto."""

    model_config = ConfigDict(extra="forbid")

    items: list[ProductMaterialCreate] = Field(default_factory=list, max_length=64)


class ProductConnectionsReplaceRequest(BaseModel):
    """Reemplaza TODA la lista de conexiones del producto."""

    model_config = ConfigDict(extra="forbid")

    items: list[ProductConnectionCreate] = Field(default_factory=list, max_length=8)
