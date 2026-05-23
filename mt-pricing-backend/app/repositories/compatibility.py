"""CompatibilityRepo — queries de la tabla product_compatibility.

Todas las operaciones son flush-only (no commit). La session y el commit son
responsabilidad del caller (FastAPI Depends / transacción de servicio).

Bidireccionalidad para ``replaces``/``replaced_by``:
    - add_link: al añadir A → replaces → B crea automáticamente B → replaced_by → A.
    - remove_link: al eliminar A → replaces → B elimina también B → replaced_by → A.
    - El resto de tipos se almacenan unidireccionalmente.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.compatibility import ProductCompatibility

# Mapa de inversos semánticos que deben sincronizarse.
_INVERSE: dict[str, str] = {
    "replaces": "replaced_by",
    "replaced_by": "replaces",
}


class CompatibilityRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def list_for_product(
        self,
        sku: str,
        *,
        kind: str | None = None,
    ) -> Sequence[ProductCompatibility]:
        """Devuelve los enlaces OUTGOING de ``sku`` (sku es el origen)."""
        stmt = (
            select(ProductCompatibility)
            .where(ProductCompatibility.product_sku == sku)
            .options(selectinload(ProductCompatibility.compatible_with))
            .order_by(ProductCompatibility.position.asc(), ProductCompatibility.created_at.asc())
        )
        if kind is not None:
            stmt = stmt.where(ProductCompatibility.kind == kind)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_inverse(
        self,
        sku: str,
        *,
        kind: str | None = None,
    ) -> Sequence[ProductCompatibility]:
        """Devuelve los enlaces INCOMING de ``sku`` (sku es el destino).

        Útil para "¿qué productos usan este SKU como recambio/accesorio?"
        """
        stmt = (
            select(ProductCompatibility)
            .where(ProductCompatibility.compatible_with_sku == sku)
            .options(selectinload(ProductCompatibility.product))
            .order_by(ProductCompatibility.position.asc(), ProductCompatibility.created_at.asc())
        )
        if kind is not None:
            stmt = stmt.where(ProductCompatibility.kind == kind)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_link(
        self,
        product_sku: str,
        compatible_with_sku: str,
        kind: str,
    ) -> ProductCompatibility | None:
        """Busca una fila exacta por clave natural (product_sku, compatible_with_sku, kind)."""
        stmt = select(ProductCompatibility).where(
            and_(
                ProductCompatibility.product_sku == product_sku,
                ProductCompatibility.compatible_with_sku == compatible_with_sku,
                ProductCompatibility.kind == kind,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    async def add_link(
        self,
        product_sku: str,
        compatible_with_sku: str,
        kind: str,
        *,
        notes: str | None = None,
        position: int = 0,
        created_by: UUID | None = None,
        owner_type: str = "product",
        dn_min: int | None = None,
        dn_max: int | None = None,
    ) -> ProductCompatibility:
        """Crea el enlace directo. Para replaces/replaced_by crea también el inverso.

        Raises ``IntegrityError`` si ya existe (UNIQUE constraint).
        """
        link = ProductCompatibility(
            product_sku=product_sku,
            compatible_with_sku=compatible_with_sku,
            kind=kind,
            notes=notes,
            position=position,
            created_by=created_by,
            owner_type=owner_type,
            dn_min=dn_min,
            dn_max=dn_max,
        )
        self.session.add(link)
        await self.session.flush()

        # Sincronización bidireccional para replaces/replaced_by.
        inverse_kind = _INVERSE.get(kind)
        if inverse_kind is not None:
            existing = await self.get_link(compatible_with_sku, product_sku, inverse_kind)
            if existing is None:
                inv = ProductCompatibility(
                    product_sku=compatible_with_sku,
                    compatible_with_sku=product_sku,
                    kind=inverse_kind,
                    notes=notes,
                    position=position,
                    created_by=created_by,
                    owner_type=owner_type,
                    dn_min=dn_min,
                    dn_max=dn_max,
                )
                self.session.add(inv)
                await self.session.flush()

        return link

    async def remove_link(
        self,
        product_sku: str,
        compatible_with_sku: str,
        kind: str,
    ) -> bool:
        """Elimina el enlace directo. Para replaces/replaced_by elimina también el inverso.

        Returns True si se eliminó al menos una fila.
        """
        stmt = delete(ProductCompatibility).where(
            and_(
                ProductCompatibility.product_sku == product_sku,
                ProductCompatibility.compatible_with_sku == compatible_with_sku,
                ProductCompatibility.kind == kind,
            )
        )
        result = await self.session.execute(stmt)
        deleted = result.rowcount > 0  # type: ignore[union-attr]

        # Eliminación bidireccional para replaces/replaced_by.
        inverse_kind = _INVERSE.get(kind)
        if inverse_kind is not None:
            inv_stmt = delete(ProductCompatibility).where(
                and_(
                    ProductCompatibility.product_sku == compatible_with_sku,
                    ProductCompatibility.compatible_with_sku == product_sku,
                    ProductCompatibility.kind == inverse_kind,
                )
            )
            await self.session.execute(inv_stmt)

        return deleted

    async def replace_all_for_product(
        self,
        sku: str,
        links: list[dict],
        *,
        created_by: UUID | None = None,
    ) -> list[ProductCompatibility]:
        """Reemplaza TODOS los enlaces OUTGOING de ``sku`` con la lista dada.

        IMPORTANTE: también elimina los inversos huérfanos de replaces/replaced_by
        que quedan sin par después del reemplazo.
        """
        # 1. Obtener estado actual para gestionar los inversos.
        existing = await self.list_for_product(sku)
        for row in existing:
            inv_kind = _INVERSE.get(row.kind)
            if inv_kind is not None:
                # Eliminar el inverso antes de borrar el origen.
                inv_stmt = delete(ProductCompatibility).where(
                    and_(
                        ProductCompatibility.product_sku == row.compatible_with_sku,
                        ProductCompatibility.compatible_with_sku == sku,
                        ProductCompatibility.kind == inv_kind,
                    )
                )
                await self.session.execute(inv_stmt)

        # 2. Borrar todos los outgoing.
        del_stmt = delete(ProductCompatibility).where(ProductCompatibility.product_sku == sku)
        await self.session.execute(del_stmt)
        await self.session.flush()

        # 3. Insertar los nuevos.
        created: list[ProductCompatibility] = []
        for item in links:
            link = await self.add_link(
                product_sku=sku,
                compatible_with_sku=item["compatible_with_sku"],
                kind=item["kind"],
                notes=item.get("notes"),
                position=item.get("position", 0),
                created_by=created_by,
                owner_type=item.get("owner_type", "product"),
                dn_min=item.get("dn_min"),
                dn_max=item.get("dn_max"),
            )
            created.append(link)

        return created

    # ------------------------------------------------------------------
    # Fase 5 — polymorphic / DN-aware queries
    # ------------------------------------------------------------------

    async def list_for_owner(
        self,
        owner_type: str,
        owner_id: str,
        *,
        kind: str | None = None,
        dn: int | None = None,
    ) -> Sequence[ProductCompatibility]:
        """Lista enlaces por owner polymorphic (Fase 5).

        - Para ``owner_type='product'`` el ``owner_id`` se compara contra
          ``product_sku`` (compat layer — owner_id no se almacena en
          product_compatibility, se deriva de product_sku).
        - Para ``owner_type='series'`` filtra por ``owner_type`` + ``product_sku``
          (que en este caso hace de owner_id de la serie en el modelo actual).
        - Si ``dn`` se provee, aplica filtro de rango DN: la fila aplica si
          (dn_min IS NULL OR dn_min <= dn) AND (dn_max IS NULL OR dn_max >= dn).
        """
        stmt = (
            select(ProductCompatibility)
            .where(
                ProductCompatibility.owner_type == owner_type,
                ProductCompatibility.product_sku == owner_id,
            )
            .options(selectinload(ProductCompatibility.compatible_with))
            .order_by(
                ProductCompatibility.position.asc(),
                ProductCompatibility.created_at.asc(),
            )
        )
        if kind is not None:
            stmt = stmt.where(ProductCompatibility.kind == kind)
        if dn is not None:
            stmt = stmt.where(
                and_(
                    (ProductCompatibility.dn_min.is_(None)) | (ProductCompatibility.dn_min <= dn),
                    (ProductCompatibility.dn_max.is_(None)) | (ProductCompatibility.dn_max >= dn),
                )
            )
        result = await self.session.execute(stmt)
        return result.scalars().all()
