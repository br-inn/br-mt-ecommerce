"""Wave 11 — EffectiveDisplayService unit tests.

Cubre union/dedupe de tags + certifications:
- Series defaults solos
- Product certs solos
- Union ambos lados
- Dedupe por código
- 404 si SKU no existe
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.products.effective_display_service import EffectiveDisplayService
from app.services.vocabularies.vocabulary_service import VocabularyDomainError


def _cert(code: str, name: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        code=code,
        name=name or f"Cert {code}",
        issued_by="ISO",
        scope="EU",
        logo_url=f"/img/{code}.png",
    )


def _build_session(
    *,
    product: object | None,
    pc_rows: list = None,
    series: object | None = None,
) -> AsyncMock:
    """Construye AsyncMock session devolviendo en orden:
    1) product (scalar_one_or_none)
    2) ProductCertification rows (scalars().all())
    3) series si product.series_id is not None (scalar_one_or_none)
    """
    pc_rows = pc_rows or []
    session = AsyncMock()

    product_result = MagicMock()
    product_result.scalar_one_or_none.return_value = product

    pc_result = MagicMock()
    pc_result.scalars.return_value.all.return_value = pc_rows

    series_result = MagicMock()
    series_result.scalar_one_or_none.return_value = series

    side = [product_result, pc_result]
    if product is not None and getattr(product, "series_id", None) is not None:
        side.append(series_result)

    session.execute = AsyncMock(side_effect=side)
    return session


# ---- 404 ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compute_missing_sku_raises_404() -> None:
    session = _build_session(product=None)
    svc = EffectiveDisplayService(session)
    with pytest.raises(VocabularyDomainError) as exc:
        await svc.compute("NOPE")
    assert exc.value.status_code == 404
    assert exc.value.code == "product_not_found"


# ---- Only series defaults (no product certs, no product tags) ----------------


@pytest.mark.asyncio
async def test_compute_only_series_defaults() -> None:
    cert_ce = _cert("CE")
    cert_wras = _cert("WRAS")
    series = SimpleNamespace(
        id=uuid4(),
        features_tags=["lead-free", "drinkable"],
        series_certifications=[
            SimpleNamespace(certification=cert_ce),
            SimpleNamespace(certification=cert_wras),
        ],
    )
    product = SimpleNamespace(
        sku="MTV-100",
        # Fase B (mig 065): products.tags dropeado — ignorado en el servicio.
        series_id=series.id,
        product_certifications=[],
    )
    session = _build_session(product=product, pc_rows=[], series=series)

    svc = EffectiveDisplayService(session)
    result = await svc.compute("MTV-100")

    assert result["tags"] == ["lead-free", "drinkable"]
    codes = [c["code"] for c in result["certifications"]]
    assert codes == ["CE", "WRAS"]


# ---- Only product certs (series None) ----------------------------------------


@pytest.mark.asyncio
async def test_compute_only_product_certs_no_series() -> None:
    # Fase B (mig 065): products.tags dropeado; el effective display ahora
    # sólo agrega features_tags de la serie. Sin serie → tags vacíos.
    cert_iso = _cert("ISO9001")
    pc = SimpleNamespace(certification=cert_iso)
    product = SimpleNamespace(
        sku="MTV-200",
        series_id=None,
        product_certifications=[pc],
    )
    session = _build_session(product=product, pc_rows=[pc], series=None)

    svc = EffectiveDisplayService(session)
    result = await svc.compute("MTV-200")

    assert result["tags"] == []
    assert [c["code"] for c in result["certifications"]] == ["ISO9001"]


# ---- Union both sides + dedupe by cert code ----------------------------------


@pytest.mark.asyncio
async def test_compute_union_dedupe_by_code() -> None:
    # Same code 'CE' on both product (specific) and series (default).
    # Product version must win the dedupe (first), series 'WRAS' adds.
    cert_ce_product_id = uuid4()
    cert_ce_product = SimpleNamespace(
        id=cert_ce_product_id,
        code="CE",
        name="CE Product Override",
        issued_by="X",
        scope="prod",
        logo_url="/p/ce.png",
    )
    cert_ce_series = _cert("CE", name="CE Series Default")
    cert_wras = _cert("WRAS")

    pc = SimpleNamespace(certification=cert_ce_product)
    series = SimpleNamespace(
        id=uuid4(),
        features_tags=["x", "shared"],
        series_certifications=[
            SimpleNamespace(certification=cert_ce_series),
            SimpleNamespace(certification=cert_wras),
        ],
    )
    product = SimpleNamespace(
        sku="MTV-300",
        # Fase B (mig 065): products.tags dropeado — sólo features_tags de serie.
        series_id=series.id,
        product_certifications=[pc],
    )
    session = _build_session(product=product, pc_rows=[pc], series=series)

    svc = EffectiveDisplayService(session)
    result = await svc.compute("MTV-300")

    # Tags: sólo serie (product.tags ya no existe en BD).
    assert result["tags"] == ["x", "shared"]

    # Certs: CE comes from product (override wins), then WRAS from series
    certs = result["certifications"]
    assert [c["code"] for c in certs] == ["CE", "WRAS"]
    ce = next(c for c in certs if c["code"] == "CE")
    assert ce["id"] == cert_ce_product_id
    assert ce["name"] == "CE Product Override"


# ---- Tags-only product, no certs ---------------------------------------------


@pytest.mark.asyncio
async def test_compute_dedupe_only_tags_no_certs() -> None:
    # Fase B (mig 065): products.tags dropeado — sólo features_tags de serie.
    series = SimpleNamespace(
        id=uuid4(),
        features_tags=["a", "b", "c"],
        series_certifications=[],
    )
    product = SimpleNamespace(
        sku="MTV-400",
        series_id=series.id,
        product_certifications=[],
    )
    session = _build_session(product=product, pc_rows=[], series=series)

    svc = EffectiveDisplayService(session)
    result = await svc.compute("MTV-400")

    # Sólo tags de la serie (product.tags removido).
    assert result["tags"] == ["a", "b", "c"]
    assert result["certifications"] == []
