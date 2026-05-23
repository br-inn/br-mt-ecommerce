import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.ficha_enrichment.applier import FichaEnrichmentApplier
from app.schemas.ficha_enrich import (
    FichaEnrichApplyRequest,
    FichaExtractionResult,
    ExtractedScalars,
    ExtractedSpecs,
    ExtractedMaterial,
)


def _make_actor():
    actor = MagicMock()
    actor.id = "00000000-0000-0000-0000-000000000001"
    return actor


def _make_product(sku="4097015", **kwargs):
    p = MagicMock()
    p.sku = sku
    p.manual_locked_fields = []
    p.specs = {}
    for k, v in kwargs.items():
        setattr(p, k, v)
    return p


def _make_session(product):
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=product),
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))),
        )
    )
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.mark.asyncio
async def test_apply_scalars_updates_product():
    product = _make_product()
    session = _make_session(product)

    applier = FichaEnrichmentApplier(session)
    req = FichaEnrichApplyRequest(
        extraction=FichaExtractionResult(
            scalars=ExtractedScalars(pn="30", temp_min_c=-20, temp_max_c=120),
            specs=ExtractedSpecs(),
            confidence=0.9,
        ),
        apply_to_skus=["4097015"],
        apply_scalars=True,
        apply_specs=False,
        apply_materials=False,
        apply_dimensions=False,
        apply_assets=False,
        apply_pt_curve=False,
    )
    result = await applier.apply("4097015", req, _make_actor())

    assert "pn" in result.applied_fields
    assert "temp_min_c" in result.applied_fields
    assert product.pn == "30"
    assert product.temp_min_c == -20
    assert result.warnings == []


@pytest.mark.asyncio
async def test_apply_product_not_found():
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )

    applier = FichaEnrichmentApplier(session)
    req = FichaEnrichApplyRequest(
        extraction=FichaExtractionResult(
            scalars=ExtractedScalars(pn="30"),
            specs=ExtractedSpecs(),
            confidence=0.9,
        ),
        apply_to_skus=["9999999"],
        apply_assets=False,
        apply_pt_curve=False,
    )
    result = await applier.apply("9999999", req, _make_actor())
    assert any("product_not_found" in e for e in result.warnings)


@pytest.mark.asyncio
async def test_apply_locked_field_skipped():
    product = _make_product(manual_locked_fields=["pn"])
    session = _make_session(product)

    applier = FichaEnrichmentApplier(session)
    req = FichaEnrichApplyRequest(
        extraction=FichaExtractionResult(
            scalars=ExtractedScalars(pn="30", temp_min_c=-20),
            specs=ExtractedSpecs(),
            confidence=0.9,
        ),
        apply_to_skus=["4097015"],
        apply_materials=False,
        apply_dimensions=False,
        apply_assets=False,
        apply_pt_curve=False,
    )
    result = await applier.apply("4097015", req, _make_actor())
    assert any("pn" in s for s in result.skipped_fields)
    assert "temp_min_c" in result.applied_fields


@pytest.mark.asyncio
async def test_apply_selected_fields_only():
    product = _make_product()
    session = _make_session(product)

    applier = FichaEnrichmentApplier(session)
    req = FichaEnrichApplyRequest(
        extraction=FichaExtractionResult(
            scalars=ExtractedScalars(pn="30", brand="MT"),
            specs=ExtractedSpecs(),
            confidence=0.9,
        ),
        apply_to_skus=["4097015"],
        apply_scalars=True,
        apply_specs=False,
        apply_materials=False,
        apply_dimensions=False,
        apply_assets=False,
        apply_pt_curve=False,
        selected_scalar_fields=["pn"],
    )
    result = await applier.apply("4097015", req, _make_actor())
    assert "pn" in result.applied_fields
    assert "brand" not in result.applied_fields
    assert "brand" in result.skipped_fields
