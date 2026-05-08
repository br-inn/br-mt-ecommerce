"""Wave 3 — repos para product_materials y product_connections."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.components import ProductConnection, ProductMaterial


class ProductMaterialRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_product(self, sku: str) -> Sequence[ProductMaterial]:
        stmt = (
            select(ProductMaterial)
            .where(ProductMaterial.product_sku == sku)
            .order_by(ProductMaterial.component, ProductMaterial.position)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def upsert(
        self,
        sku: str,
        component: str,
        position: int,
        material: str,
        observations: str | None = None,
    ) -> ProductMaterial:
        stmt = select(ProductMaterial).where(
            ProductMaterial.product_sku == sku,
            ProductMaterial.component == component,
            ProductMaterial.position == position,
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing:
            existing.material = material
            existing.observations = observations
            await self.session.flush()
            return existing
        row = ProductMaterial(
            product_sku=sku,
            component=component,
            position=position,
            material=material,
            observations=observations,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def delete(self, sku: str, component: str, position: int) -> bool:
        stmt = delete(ProductMaterial).where(
            ProductMaterial.product_sku == sku,
            ProductMaterial.component == component,
            ProductMaterial.position == position,
        )
        result = await self.session.execute(stmt)
        return (result.rowcount or 0) > 0

    async def replace_all(
        self,
        sku: str,
        items: list[dict],
    ) -> Sequence[ProductMaterial]:
        # Limpia y recrea — atómico dentro de la session.
        await self.session.execute(
            delete(ProductMaterial).where(ProductMaterial.product_sku == sku)
        )
        rows = [
            ProductMaterial(
                product_sku=sku,
                component=it["component"],
                position=int(it.get("position", 0)),
                material=it["material"],
                observations=it.get("observations"),
            )
            for it in items
        ]
        self.session.add_all(rows)
        await self.session.flush()
        return rows


class ProductConnectionRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_product(self, sku: str) -> Sequence[ProductConnection]:
        stmt = (
            select(ProductConnection)
            .where(ProductConnection.product_sku == sku)
            .order_by(ProductConnection.position)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def upsert(
        self,
        sku: str,
        position: int,
        connection_type: str,
        dn: str | None = None,
        dn_real: str | None = None,
        size: str | None = None,
        threading: str | None = None,
        notes: str | None = None,
    ) -> ProductConnection:
        stmt = select(ProductConnection).where(
            ProductConnection.product_sku == sku,
            ProductConnection.position == position,
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing:
            existing.connection_type = connection_type
            existing.dn = dn
            existing.dn_real = dn_real
            existing.size = size
            existing.threading = threading
            existing.notes = notes
            await self.session.flush()
            return existing
        row = ProductConnection(
            product_sku=sku,
            position=position,
            connection_type=connection_type,
            dn=dn,
            dn_real=dn_real,
            size=size,
            threading=threading,
            notes=notes,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def delete(self, sku: str, position: int) -> bool:
        stmt = delete(ProductConnection).where(
            ProductConnection.product_sku == sku,
            ProductConnection.position == position,
        )
        result = await self.session.execute(stmt)
        return (result.rowcount or 0) > 0

    async def replace_all(
        self,
        sku: str,
        items: list[dict],
    ) -> Sequence[ProductConnection]:
        await self.session.execute(
            delete(ProductConnection).where(ProductConnection.product_sku == sku)
        )
        rows = [
            ProductConnection(
                product_sku=sku,
                position=int(it["position"]),
                connection_type=it["connection_type"],
                dn=it.get("dn"),
                dn_real=it.get("dn_real"),
                size=it.get("size"),
                threading=it.get("threading"),
                notes=it.get("notes"),
            )
            for it in items
        ]
        self.session.add_all(rows)
        await self.session.flush()
        return rows
