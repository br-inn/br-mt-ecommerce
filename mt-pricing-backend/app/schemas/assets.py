"""Pydantic V2 schemas for ProductAsset (Wave 1 — asset unification).

Covers 10 asset kinds:
  photo, banner, datasheet_pdf, exploded_3d, section_drawing, dimension_drawing,
  certificate_pdf, video_link, external_url, mirror_url.

Design notes:
- Pydantic V2 with ConfigDict.
- Input schemas: extra="forbid"; Response schemas: extra="ignore".
- from_attributes=True for direct ORM mapping.
- compute_asset_urls() helper returns all CDN/storage URLs from variants + bucket.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.config import settings as _settings


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class AssetKind(StrEnum):
    PHOTO = "photo"
    BANNER = "banner"
    DATASHEET_PDF = "datasheet_pdf"
    EXPLODED_3D = "exploded_3d"
    SECTION_DRAWING = "section_drawing"
    DIMENSION_DRAWING = "dimension_drawing"
    CERTIFICATE_PDF = "certificate_pdf"
    VIDEO_LINK = "video_link"
    EXTERNAL_URL = "external_url"
    MIRROR_URL = "mirror_url"


class AssetStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    BROKEN = "broken"
    PENDING_UPLOAD = "pending_upload"
    PROCESSING = "processing"


# ---------------------------------------------------------------------------
# Kind-specific MIME and size rules (§7.2)
# ---------------------------------------------------------------------------
_MIME_RULES: dict[str, frozenset[str]] = {
    "photo": frozenset({"image/jpeg", "image/png", "image/webp", "image/avif"}),
    "banner": frozenset({"image/jpeg", "image/png", "image/webp", "image/avif"}),
    "datasheet_pdf": frozenset({"application/pdf"}),
    "certificate_pdf": frozenset({"application/pdf"}),
    "exploded_3d": frozenset({"image/jpeg", "image/png", "image/webp", "image/svg+xml", "application/pdf"}),
    "section_drawing": frozenset({"image/jpeg", "image/png", "image/webp", "image/svg+xml", "application/pdf"}),
    "dimension_drawing": frozenset({"image/jpeg", "image/png", "image/webp", "image/svg+xml", "application/pdf"}),
    "video_link": frozenset({"text/uri-list"}),  # URL-only kind, no binary upload
    "external_url": frozenset({"text/uri-list"}),
    "mirror_url": frozenset({"image/jpeg", "image/png", "image/webp", "image/avif"}),
}

_MAX_BYTES_RULES: dict[str, int] = {
    "photo": 10 * 1024 * 1024,        # 10 MB
    "banner": 10 * 1024 * 1024,
    "datasheet_pdf": 50 * 1024 * 1024, # 50 MB
    "certificate_pdf": 50 * 1024 * 1024,
    "exploded_3d": 30 * 1024 * 1024,
    "section_drawing": 30 * 1024 * 1024,
    "dimension_drawing": 30 * 1024 * 1024,
    "video_link": 0,   # no binary
    "external_url": 0,
    "mirror_url": 10 * 1024 * 1024,
}


def allowed_mimes_for_kind(kind: str) -> frozenset[str]:
    return _MIME_RULES.get(kind, frozenset())


def max_bytes_for_kind(kind: str) -> int:
    return _MAX_BYTES_RULES.get(kind, 10 * 1024 * 1024)


# ---------------------------------------------------------------------------
# Kind-specific metadata models
# ---------------------------------------------------------------------------
class AssetMetadataPhoto(BaseModel):
    """Metadata for photo/banner/mirror_url assets."""

    model_config = ConfigDict(extra="ignore")

    width: int | None = None
    height: int | None = None
    blurhash: str | None = None
    color_palette: list[str] | None = None


class AssetMetadataDatasheetPdf(BaseModel):
    """Metadata for PDF-type assets."""

    model_config = ConfigDict(extra="ignore")

    pages: int | None = None
    language: str | None = None
    doc_title: str | None = None
    revision_date: str | None = None


class AssetMetadataVideoLink(BaseModel):
    """Metadata for video_link / external_url assets."""

    model_config = ConfigDict(extra="ignore")

    url: str | None = None
    platform: str | None = None  # youtube, vimeo, etc.
    duration_seconds: int | None = None
    thumbnail_url: str | None = None


class AssetMetadataDefault(BaseModel):
    """Fallback for other asset kinds."""

    model_config = ConfigDict(extra="ignore")


# ---------------------------------------------------------------------------
# URL computation helper
# ---------------------------------------------------------------------------
def compute_asset_urls(
    bucket: str,
    storage_path: str,
    variants: dict[str, Any],
    supabase_url: str | None = None,
) -> dict[str, str | None]:
    """Build dict of CDN/storage URLs from variants jsonb + storage path.

    Returns keys: original, thumb_160, thumb_400, thumb_800, thumb_1600,
                  avif_400, avif_800, blurhash.
    """
    base = (supabase_url or getattr(_settings, "SUPABASE_URL", "")).rstrip("/")
    if not base or "your-project" in base:
        base = "https://fake-storage.local"

    def _url(path: str | None) -> str | None:
        if not path:
            return None
        return f"{base}/storage/v1/object/public/{bucket}/{path}"

    return {
        "original": _url(storage_path),
        "thumb_160": _url(variants.get("webp_160")),
        "thumb_400": _url(variants.get("webp_400")),
        "thumb_800": _url(variants.get("webp_800")),
        "thumb_1600": _url(variants.get("webp_1600")),
        "avif_400": _url(variants.get("avif_400")),
        "avif_800": _url(variants.get("avif_800")),
        "blurhash": variants.get("blurhash"),  # not a URL, just the hash string
    }


# ---------------------------------------------------------------------------
# Base schema
# ---------------------------------------------------------------------------
class ProductAssetBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: AssetKind = AssetKind.PHOTO
    alt_text: Annotated[str | None, Field(default=None, max_length=512)] = None
    locale: Annotated[str | None, Field(default=None, max_length=8)] = None
    caption: Annotated[str | None, Field(default=None, max_length=1024)] = None
    position: Annotated[int, Field(default=0, ge=0, le=9999)] = 0
    is_primary: bool = False


# ---------------------------------------------------------------------------
# Upload request — step 1: request signed URL
# ---------------------------------------------------------------------------
class ProductAssetUploadRequest(BaseModel):
    """Request body for POST /products/{sku}/assets/upload-url."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: AssetKind = AssetKind.PHOTO
    filename: Annotated[str, Field(min_length=1, max_length=256)]
    mime_type: Annotated[str, Field(default="image/jpeg")]
    locale: Annotated[str | None, Field(default=None, max_length=8)] = None
    alt_text: Annotated[str | None, Field(default=None, max_length=512)] = None
    position: Annotated[int, Field(default=0, ge=0)] = 0

    @field_validator("filename")
    @classmethod
    def _validate_filename(cls, v: str) -> str:
        if "/" in v or "\\" in v or ".." in v:
            raise ValueError("filename no puede contener separadores de ruta")
        if not re.match(r"^[A-Za-z0-9._\-]{1,256}$", v):
            raise ValueError("filename con caracteres inválidos")
        return v

    @model_validator(mode="after")
    def _validate_mime_for_kind(self) -> ProductAssetUploadRequest:
        allowed = allowed_mimes_for_kind(self.kind.value)
        if allowed and self.mime_type not in allowed:
            raise ValueError(
                f"mime_type '{self.mime_type}' no válido para kind '{self.kind.value}'; "
                f"permitidos: {sorted(allowed)}"
            )
        return self


# ---------------------------------------------------------------------------
# Confirm request — step 3: confirm upload completed
# ---------------------------------------------------------------------------
class ProductAssetConfirmRequest(BaseModel):
    """Request body for POST /products/{sku}/assets/{asset_id}/confirm."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    storage_path: Annotated[str, Field(min_length=1, max_length=512)]
    kind: AssetKind = AssetKind.PHOTO
    mime_type: Annotated[str, Field(default="image/jpeg")]
    bytes_size: Annotated[int | None, Field(default=None, ge=0, le=100 * 1024 * 1024)] = None
    width: Annotated[int | None, Field(default=None, ge=1, le=20000)] = None
    height: Annotated[int | None, Field(default=None, ge=1, le=20000)] = None
    alt_text: Annotated[str | None, Field(default=None, max_length=512)] = None
    locale: Annotated[str | None, Field(default=None, max_length=8)] = None
    caption: Annotated[str | None, Field(default=None, max_length=1024)] = None
    is_primary: bool = False
    position: Annotated[int, Field(default=0, ge=0)] = 0

    @field_validator("storage_path")
    @classmethod
    def _validate_storage_path(cls, v: str) -> str:
        if v.startswith("/") or ".." in v:
            raise ValueError("storage_path inválido")
        return v

    @model_validator(mode="after")
    def _validate_mime_for_kind(self) -> ProductAssetConfirmRequest:
        allowed = allowed_mimes_for_kind(self.kind.value)
        if allowed and self.mime_type not in allowed:
            raise ValueError(
                f"mime_type '{self.mime_type}' no válido para kind '{self.kind.value}'; "
                f"permitidos: {sorted(allowed)}"
            )
        return self


# ---------------------------------------------------------------------------
# Patch schema
# ---------------------------------------------------------------------------
class ProductAssetPatch(BaseModel):
    """PATCH body for partial asset update."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    alt_text: Annotated[str | None, Field(default=None, max_length=512)] = None
    caption: Annotated[str | None, Field(default=None, max_length=1024)] = None
    locale: Annotated[str | None, Field(default=None, max_length=8)] = None
    position: Annotated[int | None, Field(default=None, ge=0, le=9999)] = None
    is_primary: bool | None = None
    revision: Annotated[str | None, Field(default=None, max_length=128)] = None

    @model_validator(mode="after")
    def _at_least_one_field(self) -> ProductAssetPatch:
        if not self.model_dump(exclude_unset=True):
            raise ValueError("PATCH payload vacío — al menos un campo requerido.")
        return self


# ---------------------------------------------------------------------------
# Create schema (internal use — service layer)
# ---------------------------------------------------------------------------
class ProductAssetCreate(ProductAssetBase):
    """Internal create schema (not exposed as HTTP body)."""

    storage_path: Annotated[str, Field(min_length=1, max_length=512)]
    bucket: str = "product-images"
    original_url: str | None = None
    mime_type: str | None = None
    bytes_size: int | None = None
    width: int | None = None
    height: int | None = None
    hash_sha256: str | None = None
    revision: str | None = None


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------
class ProductAssetResponse(BaseModel):
    """API response schema for a ProductAsset row."""

    model_config = ConfigDict(
        from_attributes=True,
        extra="ignore",
        populate_by_name=True,  # allow both `asset_meta` and `metadata` as input keys
    )

    id: UUID
    sku: str
    kind: str
    bucket: str
    storage_path: str
    original_url: str | None = None
    is_primary: bool
    position: int = 0
    alt_text: str | None = None
    locale: str | None = None
    caption: str | None = None
    width: int | None = None
    height: int | None = None
    bytes_size: int | None = None
    mime_type: str | None = None
    hash_sha256: str | None = None
    variants: dict[str, Any] = Field(default_factory=dict)
    # ORM attr is `asset_meta` (DB column: `metadata`). We expose as `metadata` in JSON.
    asset_meta: dict[str, Any] = Field(default_factory=dict, alias="metadata")
    revision: str | None = None
    supersedes_id: UUID | None = None
    status: str
    archived_at: datetime | None = None
    created_at: datetime
    created_by: UUID | None = None
    # Computed URL dict — populated by validator below.
    urls: dict[str, str | None] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _compute_urls(self) -> ProductAssetResponse:
        """Populate urls from variants + bucket + storage_path."""
        self.urls = compute_asset_urls(
            bucket=self.bucket,
            storage_path=self.storage_path,
            variants=self.variants,
        )
        return self


# ---------------------------------------------------------------------------
# Backward-compat alias
# ---------------------------------------------------------------------------
# Kept so existing code referencing ProductImageResponse still compiles.
# Will be removed in Wave 2.
ProductImageResponse = ProductAssetResponse  # type: ignore[misc]
