"""AssetLinkService — Fase 4 polymorphic asset links + dedup helper.

CRUD básico para `asset_links` + helper `find_or_create_asset_by_hash` que
implementa dedup binario por SHA-256 (cuando el constraint UNIQUE en
`product_assets.hash_sha256` está activo, ver mig 060).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.asset_links import AssetLink
from app.db.models.product import ProductAsset


class AssetLinkDomainError(Exception):
    """Errores de dominio del servicio de asset_links."""

    def __init__(self, message: str, code: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class AssetLinkService:
    """Servicio stateless — todas las deps por sesión."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---------------------------------------------------------------- Create
    async def create_link(
        self,
        *,
        asset_id: UUID,
        owner_type: str,
        owner_id: str,
        role: str,
        order_index: int = 0,
    ) -> AssetLink:
        """Crea un link asset ↔ owner. Falla con 409 si ya existe la tupla.

        El check de unicidad se hace ANTES del INSERT para devolver 409 limpio
        en lugar de propagar IntegrityError del UNIQUE constraint.
        """
        existing = await self.session.execute(
            select(AssetLink).where(
                AssetLink.asset_id == asset_id,
                AssetLink.owner_type == owner_type,
                AssetLink.owner_id == owner_id,
                AssetLink.role == role,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise AssetLinkDomainError(
                f"AssetLink ya existe para "
                f"({asset_id}, {owner_type}, {owner_id}, {role})",
                code="asset_link_conflict",
                status_code=409,
            )

        link = AssetLink(
            asset_id=asset_id,
            owner_type=owner_type,
            owner_id=owner_id,
            role=role,
            order_index=order_index,
        )
        self.session.add(link)
        await self.session.flush()
        return link

    # ---------------------------------------------------------------- Reads
    async def list_links_for_owner(
        self, owner_type: str, owner_id: str
    ) -> list[AssetLink]:
        """Lista todos los assets vinculados al owner, ordenados por order_index."""
        result = await self.session.execute(
            select(AssetLink)
            .where(
                AssetLink.owner_type == owner_type,
                AssetLink.owner_id == owner_id,
            )
            .order_by(AssetLink.role, AssetLink.order_index, AssetLink.created_at)
        )
        return list(result.scalars().all())

    async def list_links_for_asset(self, asset_id: UUID) -> list[AssetLink]:
        """Lista todos los owners a los que está vinculado un asset."""
        result = await self.session.execute(
            select(AssetLink)
            .where(AssetLink.asset_id == asset_id)
            .order_by(AssetLink.owner_type, AssetLink.owner_id, AssetLink.role)
        )
        return list(result.scalars().all())

    async def get_link(self, link_id: UUID) -> AssetLink | None:
        result = await self.session.execute(
            select(AssetLink).where(AssetLink.id == link_id)
        )
        return result.scalar_one_or_none()

    # ---------------------------------------------------------------- Delete
    async def delete_link(self, link_id: UUID) -> None:
        link = await self.get_link(link_id)
        if link is None:
            raise AssetLinkDomainError(
                f"AssetLink {link_id} no encontrado",
                code="asset_link_not_found",
                status_code=404,
            )
        await self.session.delete(link)
        await self.session.flush()

    # ---------------------------------------------------------- Dedup helper
    async def find_or_create_asset_by_hash(
        self,
        *,
        hash_sha256: str,
        sku: str,
        kind: str,
        storage_path: str,
        bucket: str = "product-images",
        mime_type: str | None = None,
        bytes_size: int | None = None,
        width: int | None = None,
        height: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> tuple[ProductAsset, bool]:
        """Busca asset por SHA-256; si existe devuelve (existing, False);
        si no existe lo crea y devuelve (new, True).

        Se asume que `hash_sha256` es no-vacío. Si llega vacío/None,
        directamente crea un asset nuevo (sin dedup).
        """
        if hash_sha256:
            result = await self.session.execute(
                select(ProductAsset).where(ProductAsset.hash_sha256 == hash_sha256)
            )
            existing = result.scalar_one_or_none()
            if existing is not None:
                return existing, False

        asset = ProductAsset(
            sku=sku,
            kind=kind,
            bucket=bucket,
            storage_path=storage_path,
            mime_type=mime_type,
            bytes_size=bytes_size,
            width=width,
            height=height,
            hash_sha256=hash_sha256 or None,
            status="active",
            variants={},
            asset_meta=extra or {},
        )
        self.session.add(asset)
        await self.session.flush()
        return asset, True
