"""Wave 3 — service unificado para materials + connections de un producto."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.components import ProductConnection, ProductMaterial
from app.db.models.product import Product
from app.repositories.components import ProductConnectionRepo, ProductMaterialRepo


class ComponentsDomainError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class ProductNotFoundError(ComponentsDomainError):
    def __init__(self, sku: str) -> None:
        super().__init__("product_not_found", f"product '{sku}' not found", 404)


class ComponentsService:
    """Operaciones sobre materiales y conexiones de un producto."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.materials = ProductMaterialRepo(session)
        self.connections = ProductConnectionRepo(session)

    async def _ensure_product(self, sku: str) -> None:
        row = await self.session.execute(select(Product.sku).where(Product.sku == sku))
        if row.scalar_one_or_none() is None:
            raise ProductNotFoundError(sku)

    # ---- Materials ---------------------------------------------------------
    async def list_materials(self, sku: str) -> Sequence[ProductMaterial]:
        await self._ensure_product(sku)
        return await self.materials.list_for_product(sku)

    async def add_material(
        self,
        sku: str,
        *,
        component: str,
        position: int,
        material: str,
        observations: str | None = None,
    ) -> ProductMaterial:
        await self._ensure_product(sku)
        return await self.materials.upsert(
            sku, component, position, material, observations
        )

    async def delete_material(self, sku: str, component: str, position: int) -> None:
        await self._ensure_product(sku)
        if not await self.materials.delete(sku, component, position):
            raise ComponentsDomainError(
                "material_not_found",
                f"material ({component}, {position}) not found for sku '{sku}'",
                404,
            )

    async def replace_materials(
        self,
        sku: str,
        items: list[dict],
    ) -> Sequence[ProductMaterial]:
        await self._ensure_product(sku)
        return await self.materials.replace_all(sku, items)

    # ---- Connections -------------------------------------------------------
    async def list_connections(self, sku: str) -> Sequence[ProductConnection]:
        await self._ensure_product(sku)
        return await self.connections.list_for_product(sku)

    async def add_connection(
        self,
        sku: str,
        *,
        position: int,
        connection_type: str,
        dn: str | None = None,
        dn_real: str | None = None,
        size: str | None = None,
        threading: str | None = None,
        notes: str | None = None,
    ) -> ProductConnection:
        await self._ensure_product(sku)
        return await self.connections.upsert(
            sku,
            position,
            connection_type,
            dn=dn,
            dn_real=dn_real,
            size=size,
            threading=threading,
            notes=notes,
        )

    async def delete_connection(self, sku: str, position: int) -> None:
        await self._ensure_product(sku)
        if not await self.connections.delete(sku, position):
            raise ComponentsDomainError(
                "connection_not_found",
                f"connection at position {position} not found for sku '{sku}'",
                404,
            )

    async def replace_connections(
        self,
        sku: str,
        items: list[dict],
    ) -> Sequence[ProductConnection]:
        await self._ensure_product(sku)
        return await self.connections.replace_all(sku, items)
