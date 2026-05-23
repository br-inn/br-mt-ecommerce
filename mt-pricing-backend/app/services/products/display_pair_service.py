"""Display pair service — Wave 11 Stage 3.

Sincronización simétrica de ``products.display_pair_sku`` para emparejar
modelos por color (rojo 4295 ↔ azul 42952).

Reglas:

- ``set_pair(a, b)``: ambos SKUs deben existir y ser distintos. Si alguno
  ya tenía un emparejamiento previo distinto, el partner anterior queda
  con ``display_pair_sku = NULL`` (consistencia simétrica). Single tx.
- ``clear_pair(sku)``: si el SKU tiene pareja, se nullify-an ambos lados.
  Idempotente — si no hay pareja, no-op.
"""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import Product
from app.services.vocabularies.vocabulary_service import VocabularyDomainError


class DisplayPairService:
    """Manage symmetric color-pair links between products."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _get_or_404(self, sku: str) -> Product:
        row = (
            await self.session.execute(select(Product).where(Product.sku == sku))
        ).scalar_one_or_none()
        if row is None:
            raise VocabularyDomainError(
                f"Product '{sku}' not found",
                code="product_not_found",
                status_code=404,
            )
        return row

    async def set_pair(self, sku_a: str, sku_b: str) -> None:
        """Establece ``a ↔ b`` simétricamente. Limpia parejas previas si existen."""
        if sku_a == sku_b:
            raise VocabularyDomainError(
                "Cannot pair a product with itself",
                code="display_pair_self",
                status_code=400,
            )
        prod_a = await self._get_or_404(sku_a)
        prod_b = await self._get_or_404(sku_b)

        # Limpiar parejas previas si difieren del nuevo emparejamiento.
        prior_a = prod_a.display_pair_sku
        prior_b = prod_b.display_pair_sku

        if prior_a is not None and prior_a != sku_b:
            await self.session.execute(
                update(Product).where(Product.sku == prior_a).values(display_pair_sku=None)
            )
        if prior_b is not None and prior_b != sku_a:
            await self.session.execute(
                update(Product).where(Product.sku == prior_b).values(display_pair_sku=None)
            )

        # Set simétrico.
        await self.session.execute(
            update(Product).where(Product.sku == sku_a).values(display_pair_sku=sku_b)
        )
        await self.session.execute(
            update(Product).where(Product.sku == sku_b).values(display_pair_sku=sku_a)
        )
        await self.session.commit()

    async def clear_pair(self, sku: str) -> None:
        """Limpia el emparejamiento del SKU (y de su partner). Idempotente."""
        product = await self._get_or_404(sku)
        partner_sku = product.display_pair_sku
        if partner_sku is None:
            return  # idempotent no-op

        await self.session.execute(
            update(Product).where(Product.sku == sku).values(display_pair_sku=None)
        )
        await self.session.execute(
            update(Product).where(Product.sku == partner_sku).values(display_pair_sku=None)
        )
        await self.session.commit()
