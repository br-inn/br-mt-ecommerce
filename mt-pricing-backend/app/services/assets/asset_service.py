"""AssetService — Wave 1 unified asset management.

Extends the semantics of the old ImageService to cover all 10 asset kinds:
  photo, banner, datasheet_pdf, exploded_3d, section_drawing, dimension_drawing,
  certificate_pdf, video_link, external_url, mirror_url.

Key methods:
- generate_signed_upload_url(sku, kind, filename, mime_type)
- confirm_upload(sku, storage_path, kind, ...)
- set_primary(asset_id)
- archive(asset_id, actor_id)
- restore(asset_id, actor_id)
- delete_hard(asset_id)
- mirror_external(url, sku, kind)
- list_for_product(sku, kind?)

Path convention: {kind_prefix}/{sku}/{uuid}_{filename}
  - photo/banner → "products/{sku}/photos/{uuid}_{filename}"
  - datasheet_pdf/certificate_pdf → "products/{sku}/docs/{uuid}_{filename}"
  - drawings → "products/{sku}/drawings/{uuid}_{filename}"
  - video_link/external_url/mirror_url → "products/{sku}/links/{uuid}_{filename}"
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.product import ProductAsset
from app.schemas.assets import AssetKind, allowed_mimes_for_kind, max_bytes_for_kind


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
class AssetValidationError(ValueError):
    """Validation failed — MIME, size, path."""


class AssetNotFoundError(LookupError):
    """Asset row not found."""

    def __init__(self, asset_id: UUID | str) -> None:
        super().__init__(f"Asset {asset_id} not found.")
        self.asset_id = asset_id


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------
_KIND_FOLDER: dict[str, str] = {
    "photo": "photos",
    "banner": "photos",
    "mirror_url": "photos",
    "datasheet_pdf": "docs",
    "certificate_pdf": "docs",
    "exploded_3d": "drawings",
    "section_drawing": "drawings",
    "dimension_drawing": "drawings",
    "video_link": "links",
    "external_url": "links",
}


def _safe_filename(filename: str) -> str:
    if not re.match(r"^[A-Za-z0-9._\-]{1,256}$", filename):
        raise AssetValidationError("filename inválido")
    return filename


def build_storage_path(sku: str, kind: str, filename: str) -> str:
    """Canonical storage path: products/{sku}/{folder}/{uuid}_{filename}."""
    clean = _safe_filename(filename)
    folder = _KIND_FOLDER.get(kind, "assets")
    return f"products/{sku}/{folder}/{uuid4().hex}_{clean}"


def _mirror_storage_path(sku: str, kind: str, url: str) -> str:
    """Deterministic path for mirrored external URLs."""
    digest = hashlib.sha256(f"{sku}|{url}".encode()).hexdigest()[:16]
    m = re.search(r"\.([a-zA-Z0-9]{2,5})($|\?)", urlparse(url).path)
    ext = m.group(1).lower() if m else "bin"
    folder = _KIND_FOLDER.get(kind, "assets")
    return f"products/{sku}/{folder}/mirror_{digest}.{ext}"


# ---------------------------------------------------------------------------
# AssetService
# ---------------------------------------------------------------------------
class AssetService:
    """Stateless service — all deps via constructor or method args.

    Pass ``session`` for DB ops; Supabase interactions are best-effort
    (degrade gracefully in test environments without real Supabase).
    """

    DEFAULT_BUCKET = "product-images"

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---------------------------------------------------------------- Queries
    async def list_for_product(
        self,
        sku: str,
        kind: str | None = None,
        include_archived: bool = False,
    ) -> list[ProductAsset]:
        """List assets for a product, optionally filtered by kind."""
        stmt = select(ProductAsset).where(ProductAsset.sku == sku)
        if kind is not None:
            stmt = stmt.where(ProductAsset.kind == kind)
        if not include_archived:
            stmt = stmt.where(ProductAsset.status != "archived")
        stmt = stmt.order_by(ProductAsset.kind, ProductAsset.position, ProductAsset.created_at)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, asset_id: UUID) -> ProductAsset | None:
        """Fetch single asset by id."""
        result = await self.session.execute(select(ProductAsset).where(ProductAsset.id == asset_id))
        return result.scalar_one_or_none()

    async def get_for_product(self, sku: str, asset_id: UUID) -> ProductAsset | None:
        """Fetch asset ensuring it belongs to the given SKU."""
        result = await self.session.execute(
            select(ProductAsset).where(
                ProductAsset.id == asset_id,
                ProductAsset.sku == sku,
            )
        )
        return result.scalar_one_or_none()

    # ------------------------------------------------------- Signed upload URL
    def generate_signed_upload_url(
        self,
        sku: str,
        kind: str,
        filename: str,
        mime_type: str,
        expires_in: int = 600,
    ) -> dict[str, Any]:
        """Generate a Supabase Storage signed URL for direct upload.

        Returns dict: { storage_path, upload_url, token, method, headers,
                        expires_in, bucket, kind }.

        Degrades gracefully in test environments (fake URL).
        """
        # Validate MIME for the kind.
        allowed = allowed_mimes_for_kind(kind)
        if allowed and mime_type not in allowed:
            raise AssetValidationError(
                f"mime_type '{mime_type}' no válido para kind '{kind}'; "
                f"permitidos: {sorted(allowed)}"
            )

        storage_path = build_storage_path(sku, kind, filename)
        bucket = self.DEFAULT_BUCKET

        admin_url = getattr(settings, "SUPABASE_URL", None)
        admin_key_obj = getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", None)
        admin_key = (
            admin_key_obj.get_secret_value()
            if admin_key_obj is not None and hasattr(admin_key_obj, "get_secret_value")
            else admin_key_obj
        )
        is_placeholder = (
            not admin_url
            or "your-project" in str(admin_url)
            or not admin_key
            or "your-service-role-key" in str(admin_key)
        )
        if is_placeholder:
            return {
                "storage_path": storage_path,
                "upload_url": f"https://fake-storage.local/{bucket}/{storage_path}",
                "token": "fake-token",
                "method": "PUT",
                "headers": {"Content-Type": mime_type},
                "expires_in": expires_in,
                "bucket": bucket,
                "kind": kind,
            }

        try:
            from app.core.supabase import get_supabase_admin  # type: ignore[import]

            client = get_supabase_admin()
            signed = client.storage.from_(bucket).create_signed_upload_url(storage_path)
        except Exception:  # noqa: BLE001
            return {
                "storage_path": storage_path,
                "upload_url": (
                    f"{admin_url}/storage/v1/object/upload/sign/{bucket}/{storage_path}"
                ),
                "token": "",
                "method": "PUT",
                "headers": {"Content-Type": mime_type},
                "expires_in": expires_in,
                "bucket": bucket,
                "kind": kind,
            }

        upload_url = (
            signed.get("signed_url") or signed.get("signedURL") or signed.get("signedUrl") or ""
        )
        token = signed.get("token", "")
        return {
            "storage_path": storage_path,
            "upload_url": upload_url,
            "token": token,
            "method": "PUT",
            "headers": {"Content-Type": mime_type},
            "expires_in": expires_in,
            "bucket": bucket,
            "kind": kind,
        }

    # ------------------------------------------------------ Confirm upload
    async def confirm_upload(
        self,
        sku: str,
        *,
        storage_path: str,
        kind: str,
        mime_type: str | None = None,
        bytes_size: int | None = None,
        width: int | None = None,
        height: int | None = None,
        alt_text: str | None = None,
        locale: str | None = None,
        caption: str | None = None,
        is_primary: bool = False,
        position: int = 0,
        actor_id: UUID | None = None,
    ) -> ProductAsset:
        """Create a ProductAsset row after a successful upload to Storage."""
        # Validate MIME if provided.
        if mime_type is not None:
            allowed = allowed_mimes_for_kind(kind)
            if allowed and mime_type not in allowed:
                raise AssetValidationError(f"mime_type '{mime_type}' no válido para kind '{kind}'")
        # Validate bytes_size if provided.
        if bytes_size is not None:
            max_bytes = max_bytes_for_kind(kind)
            if max_bytes > 0 and bytes_size > max_bytes:
                raise AssetValidationError(
                    f"bytes_size {bytes_size} excede límite {max_bytes} para kind '{kind}'"
                )

        # Build initial metadata from width/height for photos.
        meta: dict[str, Any] = {}
        if kind in ("photo", "banner", "mirror_url") and (width or height):
            meta = {"width": width, "height": height}

        asset = ProductAsset(
            sku=sku,
            kind=kind,
            bucket=self.DEFAULT_BUCKET,
            storage_path=storage_path,
            mime_type=mime_type,
            bytes_size=bytes_size,
            width=width,
            height=height,
            alt_text=alt_text,
            locale=locale,
            caption=caption,
            is_primary=is_primary,
            position=position,
            status="active",
            asset_meta=meta,
            variants={},
            created_by=actor_id,
        )
        self.session.add(asset)
        await self.session.flush()

        # If is_primary requested, demote others for this (sku, kind).
        if is_primary:
            await self._set_primary_exclusive(sku, kind, asset.id)

        return asset

    # ---------------------------------------------------------- Set primary
    async def set_primary(self, asset_id: UUID, sku: str) -> ProductAsset:
        """Mark asset as primary, demoting others in same (sku, kind)."""
        asset = await self.get_for_product(sku, asset_id)
        if asset is None:
            raise AssetNotFoundError(asset_id)
        await self._set_primary_exclusive(sku, asset.kind, asset_id)
        await self.session.refresh(asset)
        return asset

    async def _set_primary_exclusive(self, sku: str, kind: str, primary_id: UUID) -> None:
        """Demote all except primary_id; set primary_id.is_primary=True."""
        # Demote others.
        await self.session.execute(
            update(ProductAsset)
            .where(
                ProductAsset.sku == sku,
                ProductAsset.kind == kind,
                ProductAsset.id != primary_id,
            )
            .values(is_primary=False)
        )
        # Promote.
        await self.session.execute(
            update(ProductAsset).where(ProductAsset.id == primary_id).values(is_primary=True)
        )

    # ------------------------------------------------------------ Archive
    async def archive(self, asset_id: UUID, sku: str, actor_id: UUID | None = None) -> ProductAsset:
        """Soft-archive an asset."""
        asset = await self.get_for_product(sku, asset_id)
        if asset is None:
            raise AssetNotFoundError(asset_id)
        asset.status = "archived"
        asset.archived_at = datetime.now(tz=UTC)
        asset.archived_by = actor_id
        await self.session.flush()
        return asset

    # ------------------------------------------------------------ Restore
    async def restore(self, asset_id: UUID, sku: str) -> ProductAsset:
        """Restore an archived asset back to active."""
        asset = await self.get_for_product(sku, asset_id)
        if asset is None:
            raise AssetNotFoundError(asset_id)
        asset.status = "active"
        asset.archived_at = None
        asset.archived_by = None
        await self.session.flush()
        return asset

    # ------------------------------------------------------- Hard delete
    async def delete_hard(self, asset_id: UUID, sku: str) -> None:
        """Permanently delete an asset row (no soft-delete)."""
        asset = await self.get_for_product(sku, asset_id)
        if asset is None:
            raise AssetNotFoundError(asset_id)
        await self.session.delete(asset)
        await self.session.flush()

    # ------------------------------------------------- Mirror external URL
    async def mirror_external(
        self,
        url: str,
        sku: str,
        kind: str = "mirror_url",
        actor_id: UUID | None = None,
    ) -> ProductAsset:
        """Create an asset row representing a mirrored external URL.

        The actual download + reupload happens in a Celery worker (not here).
        This method only creates the DB row with status='pending_upload'.
        """
        if not url:
            raise AssetValidationError("URL externa vacía")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise AssetValidationError(f"esquema no soportado: {parsed.scheme}")

        storage_path = _mirror_storage_path(sku, kind, url)

        asset = ProductAsset(
            sku=sku,
            kind=kind,
            bucket=self.DEFAULT_BUCKET,
            storage_path=storage_path,
            original_url=url,
            status="pending_upload",
            asset_meta={},
            variants={},
            created_by=actor_id,
        )
        self.session.add(asset)
        await self.session.flush()
        return asset

    # ------------------------------------------------- Write variants/metadata
    async def update_variants(
        self,
        asset_id: UUID,
        variants: dict[str, Any],
        metadata_patch: dict[str, Any] | None = None,
    ) -> ProductAsset | None:
        """Update variants and/or metadata jsonb for an asset (used by worker)."""
        asset = await self.get_by_id(asset_id)
        if asset is None:
            return None
        asset.variants = {**asset.variants, **variants}
        if metadata_patch:
            asset.asset_meta = {**asset.asset_meta, **metadata_patch}
        await self.session.flush()
        return asset
