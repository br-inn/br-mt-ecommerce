"""Wave 5 — parent/child resolver for variants.

Cuando un producto es una *variante* (``parent_sku`` no null), las consultas de
assets, traducciones y specs DEBEN hacer fallback al padre cuando la variante
no tiene esos datos propios. Este módulo centraliza esa lógica.

Restricciones (Fase 1):
- Profundidad máxima 1: ``parent_sku`` no puede tener a su vez ``parent_sku``
  (no se permiten "nietos").
- Sin ciclos: ``parent_sku == sku`` rechazado por DB CHECK + validación service.
- ``is_parent`` y ``is_variant`` son flags computados; pueden mantenerse
  manualmente o derivarse via ``recompute_parent_flags()``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import Product, ProductAsset, ProductTranslation


class ParentResolverError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class CycleError(ParentResolverError):
    def __init__(self, sku: str) -> None:
        super().__init__(
            "parent_cycle", f"parent_sku creates a cycle: '{sku}' cannot be its own ancestor", 409
        )


class DepthExceededError(ParentResolverError):
    def __init__(self, sku: str) -> None:
        super().__init__(
            "parent_depth_exceeded",
            f"product '{sku}' is itself a variant; nested variants are not allowed (max depth 1)",
            409,
        )


class ParentNotFoundError(ParentResolverError):
    def __init__(self, parent_sku: str) -> None:
        super().__init__(
            "parent_not_found", f"parent product '{parent_sku}' does not exist", 404
        )


class ParentResolver:
    """Resuelve la jerarquía padre→variante con validación + fallback."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---- Validation -------------------------------------------------------

    async def validate_parent_link(self, child_sku: str, parent_sku: str | None) -> None:
        """Valida que ``child.parent_sku = parent_sku`` sea legal.

        Reglas:
        - parent_sku == child_sku → cycle (rejected).
        - parent debe existir.
        - parent NO puede ser variante (max depth 1).
        """
        if parent_sku is None:
            return
        if parent_sku == child_sku:
            raise CycleError(child_sku)

        parent = await self.session.execute(
            select(Product.sku, Product.parent_sku, Product.is_variant).where(
                Product.sku == parent_sku
            )
        )
        row = parent.first()
        if row is None:
            raise ParentNotFoundError(parent_sku)
        # Si parent es variante (parent_sku no null), profundidad excedida.
        if row.parent_sku is not None or bool(row.is_variant):
            raise DepthExceededError(parent_sku)

    # ---- Flag recomputation -----------------------------------------------

    async def recompute_parent_flags(self, sku: str) -> None:
        """Tras cambiar ``parent_sku`` actualiza is_parent/is_variant en self y padre.

        - self.is_variant = (parent_sku IS NOT NULL).
        - parent.is_parent = exists any other product with parent_sku=parent.
        """
        # Re-leer self para conocer parent_sku actual.
        result = await self.session.execute(
            select(Product.parent_sku).where(Product.sku == sku)
        )
        parent_sku = result.scalar_one_or_none()

        # Marca self.is_variant.
        await self.session.execute(
            update(Product)
            .where(Product.sku == sku)
            .values(is_variant=parent_sku is not None)
        )

        if parent_sku:
            # Recompute padre.is_parent (debería ser true si tiene al menos
            # una variante — esta misma).
            await self.session.execute(
                update(Product)
                .where(Product.sku == parent_sku)
                .values(is_parent=True)
            )

    # ---- Resolution (fallback chain) --------------------------------------

    async def resolve_assets(
        self, sku: str, *, kind: str | None = None
    ) -> tuple[Sequence[ProductAsset], str | None]:
        """Devuelve (assets, inherited_from).

        Si la variante no tiene assets propios del kind, busca en el padre.
        ``inherited_from`` es el sku origen (None si propios).
        """
        own_stmt = select(ProductAsset).where(ProductAsset.sku == sku)
        if kind:
            own_stmt = own_stmt.where(ProductAsset.kind == kind)
        own = (await self.session.execute(own_stmt)).scalars().all()
        if own:
            return own, None
        # Fallback: ¿variante con padre?
        result = await self.session.execute(
            select(Product.parent_sku).where(Product.sku == sku)
        )
        parent_sku = result.scalar_one_or_none()
        if not parent_sku:
            return [], None
        parent_stmt = select(ProductAsset).where(ProductAsset.sku == parent_sku)
        if kind:
            parent_stmt = parent_stmt.where(ProductAsset.kind == kind)
        parent_assets = (await self.session.execute(parent_stmt)).scalars().all()
        return parent_assets, (parent_sku if parent_assets else None)

    async def resolve_translations(
        self, sku: str
    ) -> tuple[Sequence[ProductTranslation], str | None]:
        own = (
            await self.session.execute(
                select(ProductTranslation).where(ProductTranslation.sku == sku)
            )
        ).scalars().all()
        if own:
            return own, None
        result = await self.session.execute(
            select(Product.parent_sku).where(Product.sku == sku)
        )
        parent_sku = result.scalar_one_or_none()
        if not parent_sku:
            return [], None
        inherited = (
            await self.session.execute(
                select(ProductTranslation).where(ProductTranslation.sku == parent_sku)
            )
        ).scalars().all()
        return inherited, (parent_sku if inherited else None)

    async def resolve_specs(self, sku: str) -> tuple[dict[str, Any], str | None]:
        """Combina specs propios + padre. Propios sobrescriben padre."""
        result = await self.session.execute(
            select(Product.specs, Product.parent_sku).where(Product.sku == sku)
        )
        row = result.first()
        if row is None:
            return {}, None
        own_specs = dict(row.specs or {})
        if not row.parent_sku:
            return own_specs, None
        parent_result = await self.session.execute(
            select(Product.specs).where(Product.sku == row.parent_sku)
        )
        parent_specs = dict(parent_result.scalar_one_or_none() or {})
        merged = {**parent_specs, **own_specs}
        # inherited_from sólo si hubo herencia real (al menos una key vino del padre y no del propio)
        inherited_keys = set(parent_specs) - set(own_specs)
        return merged, (row.parent_sku if inherited_keys else None)
