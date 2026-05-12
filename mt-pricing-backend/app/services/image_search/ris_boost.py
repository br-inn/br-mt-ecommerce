"""Whitelist boost para Reverse Image Search — US-F15-02-03.

get_canonical_domains: actualmente retorna frozenset() porque el schema
no tiene suppliers.website ni brands.domain en esta sprint.  El AC#4 queda
cubierto estructuralmente; la data real se conecta cuando la tabla tenga
el campo.  Ver Dev Notes T7.2 en US-F15-02-03.md.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.comparator.interfaces import ReverseImageSearchResult

_BOOST_AMOUNT = Decimal("0.15")
_BOOST_CAP = Decimal("1.0")


async def get_canonical_domains(
    *, session: AsyncSession, product_sku: str
) -> frozenset[str]:
    """Retorna dominios canónicos del fabricante para el SKU dado.

    Retorna frozenset() — suppliers.website / brands.domain aún no existen
    en el schema.  Sin efecto sobre el boost hasta que se agregue la columna.
    """
    return frozenset()


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
