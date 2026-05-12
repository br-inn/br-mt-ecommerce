"""Pydantic V2 schemas — Fase 4 asset_links polymorphic.

Modela el contrato HTTP para crear/listar/eliminar links polimórficos entre
un asset (`product_assets.id`) y cualquier owner del catálogo.

Owner types soportados: product | variant | series | family | spare_part
Roles soportados: image_padre | banner | ficha_pdf | manual_pdf | ce_pdf
                  catalogo_pdf | exploded_3d | section_drawing
                  dimensions_drawing | video | web_image | main_image
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class AssetLinkOwnerType(StrEnum):
    PRODUCT = "product"
    VARIANT = "variant"
    SERIES = "series"
    FAMILY = "family"
    SPARE_PART = "spare_part"


class AssetLinkRole(StrEnum):
    IMAGE_PADRE = "image_padre"
    BANNER = "banner"
    FICHA_PDF = "ficha_pdf"
    MANUAL_PDF = "manual_pdf"
    CE_PDF = "ce_pdf"
    CATALOGO_PDF = "catalogo_pdf"
    EXPLODED_3D = "exploded_3d"
    SECTION_DRAWING = "section_drawing"
    DIMENSIONS_DRAWING = "dimensions_drawing"
    VIDEO = "video"
    WEB_IMAGE = "web_image"
    MAIN_IMAGE = "main_image"


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
class AssetLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    asset_id: UUID
    owner_type: AssetLinkOwnerType
    owner_id: Annotated[str, Field(min_length=1, max_length=256)]
    role: AssetLinkRole
    order_index: Annotated[int, Field(default=0, ge=0, le=9999)] = 0


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------
class AssetLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    asset_id: UUID
    owner_type: str
    owner_id: str
    role: str
    order_index: int
    created_at: datetime
