"""Tests unitarios para get_canonical_domains() con query real a ManufacturerWhitelist.

Tests — US-F15-02-03 (mig. 075):
- T_DOMAINS_KNOWN_BRAND  — mock session con fila ManufacturerWhitelist → frozenset con dominios
- T_DOMAINS_UNKNOWN_BRAND — mock session sin filas → frozenset()
- T_DOMAINS_ALIAS_MATCH   — match vía brand_aliases → frozenset con dominios del alias
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.image_search.ris_boost import get_canonical_domains


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(
    brand_for_sku: str | None,
    whitelist_rows: list[list[str]],
) -> AsyncMock:
    """Construye un AsyncSession mock con dos execute() programados:
    - 1ª llamada (brand lookup) → devuelve brand_for_sku
    - 2ª llamada (whitelist query) → devuelve rows de canonical_domains
    """
    session = AsyncMock()

    # Resultado 1: scalar_one_or_none() para obtener brand del producto
    brand_scalar_result = MagicMock()
    brand_scalar_result.scalar_one_or_none.return_value = brand_for_sku

    # Resultado 2: iteración de filas de ManufacturerWhitelist.canonical_domains
    # rows retorna una lista de tuplas (domains_list,)
    whitelist_result = MagicMock()
    whitelist_result.__iter__ = MagicMock(
        return_value=iter([(row,) for row in whitelist_rows])
    )

    session.execute = AsyncMock(side_effect=[brand_scalar_result, whitelist_result])
    return session


# ---------------------------------------------------------------------------
# T_DOMAINS_KNOWN_BRAND — fila existente → frozenset con dominios
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_canonical_domains_returns_frozenset_for_known_brand() -> None:
    """Dado un SKU cuyo brand matchea en manufacturers_whitelist, retorna los dominios."""
    session = _make_session(
        brand_for_sku="Danfoss",
        whitelist_rows=[["danfoss.com"]],
    )

    result = await get_canonical_domains(session=session, product_sku="SKU-001")

    assert isinstance(result, frozenset)
    assert "danfoss.com" in result
    assert len(result) == 1


# ---------------------------------------------------------------------------
# T_DOMAINS_UNKNOWN_BRAND — sin filas → frozenset()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_canonical_domains_returns_empty_for_unknown_brand() -> None:
    """Dado un SKU cuyo brand no está en manufacturers_whitelist, retorna frozenset()."""
    session = _make_session(
        brand_for_sku="MarcaDesconocida",
        whitelist_rows=[],  # sin resultados en whitelist
    )

    result = await get_canonical_domains(session=session, product_sku="SKU-002")

    assert isinstance(result, frozenset)
    assert len(result) == 0


# ---------------------------------------------------------------------------
# T_DOMAINS_ALIAS_MATCH — match por alias → frozenset con dominios
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_canonical_domains_uses_brand_aliases() -> None:
    """Dado un SKU con brand='Heimeier' (alias de IMI), retorna dominios de IMI."""
    session = _make_session(
        brand_for_sku="Heimeier",
        whitelist_rows=[["imi-hydronic.com"]],
    )

    result = await get_canonical_domains(session=session, product_sku="SKU-003")

    assert isinstance(result, frozenset)
    assert "imi-hydronic.com" in result


# ---------------------------------------------------------------------------
# Edge case: brand es None → frozenset() sin llamar whitelist
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_canonical_domains_returns_empty_when_brand_is_none() -> None:
    """Dado un SKU sin brand (NULL), retorna frozenset() sin hacer query al whitelist."""
    session = AsyncMock()

    brand_scalar_result = MagicMock()
    brand_scalar_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=brand_scalar_result)

    result = await get_canonical_domains(session=session, product_sku="SKU-NULL")

    assert isinstance(result, frozenset)
    assert len(result) == 0
    # Solo debería haberse llamado execute una vez (brand lookup)
    assert session.execute.call_count == 1
