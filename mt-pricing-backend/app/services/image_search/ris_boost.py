"""Whitelist boost para Reverse Image Search — US-F15-02-03.

get_canonical_domains: busca el fabricante del SKU en ``manufacturers_whitelist``
vía ``products.brand`` y retorna el union de ``canonical_domains`` de todos los
registros activos que hagan match por nombre o alias.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.comparator import ManufacturerWhitelist
from app.db.models.product import Product
from app.services.comparator.interfaces import ReverseImageSearchResult

_BOOST_AMOUNT = Decimal("0.15")
_BOOST_CAP = Decimal("1.0")


async def get_canonical_domains(*, session: AsyncSession, product_sku: str) -> frozenset[str]:
    """Obtiene dominios canónicos del fabricante del SKU vía manufacturers_whitelist.

    Flujo:
    1. Obtiene ``brand`` del producto desde ``products`` donde sku = :product_sku.
    2. Busca en ``manufacturers_whitelist`` (active=True) donde
       ``manufacturer_name ILIKE :brand`` OR ``:brand = ANY(brand_aliases)``.
    3. Aplana canonical_domains de todos los matches a frozenset.

    Retorna frozenset() si no hay producto, si brand es NULL, o si no hay match
    — comportamiento graceful sin excepción.
    """
    # 1. Obtener brand del producto
    product_result = await session.execute(select(Product.brand).where(Product.sku == product_sku))
    brand: str | None = product_result.scalar_one_or_none()

    if not brand:
        return frozenset()

    # 2. Query manufacturers_whitelist: match por nombre (ILIKE) o por alias (ANY)
    stmt = select(ManufacturerWhitelist.canonical_domains).where(
        ManufacturerWhitelist.active.is_(True),
        text("manufacturer_name ILIKE :brand OR :brand = ANY(brand_aliases)").bindparams(
            brand=brand
        ),
    )
    rows = await session.execute(stmt)
    all_domains: list[str] = []
    for (domains,) in rows:
        if domains:
            all_domains.extend(domains)

    return frozenset(all_domains)


def apply_ris_boost(
    confidence: Decimal,
    result: ReverseImageSearchResult,
    canonical_domains: frozenset[str],
) -> tuple[Decimal, bool]:
    """Aplica boost +0.15 (capped a 1.0) si algún hit.domain está en canonical_domains."""
    if not canonical_domains:
        return confidence, False
    for hit in result.hits:
        if hit.domain in canonical_domains:
            return min(confidence + _BOOST_AMOUNT, _BOOST_CAP), True
    return confidence, False


__all__ = ["apply_ris_boost", "get_canonical_domains"]
