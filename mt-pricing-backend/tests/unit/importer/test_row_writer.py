"""Tests para RowWriter pipeline."""
from __future__ import annotations
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.services.importer.row_writer import ScalarWriter, JsonbWriter, WriteResult
from app.services.importer.parsed_product import ParsedProduct


def _make_product(sku: str = "MT-001", **kwargs) -> MagicMock:
    p = MagicMock()
    p.sku = sku
    p.manual_locked_fields = []
    for k, v in kwargs.items():
        setattr(p, k, v)
    return p


@pytest.mark.asyncio
async def test_scalar_writer_sets_fields_on_existing_product():
    session = AsyncMock()
    product = _make_product(sku="MT-001", weight=None, connection=None)
    writer = ScalarWriter()
    result = await writer.write(
        session=session,
        sku="MT-001",
        existing=product,
        scalars={"weight": Decimal("1.5"), "connection": "Rosca"},
        locked_fields=set(),
    )
    assert product.weight == Decimal("1.5")
    assert product.connection == "Rosca"
    assert result.bucket == "updated"
    assert "weight" in result.changed_fields


@pytest.mark.asyncio
async def test_scalar_writer_respects_locked_fields():
    session = AsyncMock()
    product = _make_product(sku="MT-001", weight=Decimal("2.0"))
    writer = ScalarWriter()
    await writer.write(
        session=session,
        sku="MT-001",
        existing=product,
        scalars={"weight": Decimal("1.5")},
        locked_fields={"weight"},
    )
    assert product.weight == Decimal("2.0")  # no change


@pytest.mark.asyncio
async def test_scalar_writer_no_change_when_equal():
    session = AsyncMock()
    product = _make_product(sku="MT-001", weight=Decimal("1.5"))
    writer = ScalarWriter()
    result = await writer.write(
        session=session,
        sku="MT-001",
        existing=product,
        scalars={"weight": Decimal("1.5")},
        locked_fields=set(),
    )
    assert result.bucket == "no_change"
    assert result.changed_fields == []


@pytest.mark.asyncio
async def test_jsonb_writer_merges_not_replaces():
    session = AsyncMock()
    product = _make_product(
        dimensions={"high_mm": "50.0", "wide_mm": "30.0"},
        packaging={},
        specs={},
    )
    writer = JsonbWriter()
    await writer.write(
        session=session,
        existing=product,
        jsonb={"dimensions": {"high_mm": "60.0"}},  # solo high_mm
        locked_fields=set(),
    )
    assert product.dimensions["high_mm"] == "60.0"
    assert product.dimensions["wide_mm"] == "30.0"  # untouched


@pytest.mark.asyncio
async def test_jsonb_writer_skips_empty_buckets():
    session = AsyncMock()
    product = _make_product(dimensions={}, packaging={}, specs={})
    writer = JsonbWriter()
    await writer.write(
        session=session,
        existing=product,
        jsonb={"dimensions": {}, "packaging": {}, "specs": {}},
        locked_fields=set(),
    )
    assert product.dimensions == {}


@pytest.mark.asyncio
async def test_scalar_writer_no_change_when_existing_is_none():
    session = AsyncMock()
    writer = ScalarWriter()
    result = await writer.write(
        session=session,
        sku="MT-NEW",
        existing=None,
        scalars={"weight": Decimal("1.5")},
        locked_fields=set(),
    )
    # When existing is None, there is nothing to setattr on — no_change
    assert result.bucket == "no_change"


# ── TranslationWriter ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_translation_writer_upserts_by_sku_lang():
    from app.services.importer.row_writer import TranslationWriter

    session = AsyncMock()
    session.execute = AsyncMock()

    writer = TranslationWriter()
    await writer.write(
        session=session,
        sku="MT-001",
        translations={"en": "Ball valve", "fr": "Robinet"},
        locked_fields=set(),
    )
    assert session.execute.call_count == 2


@pytest.mark.asyncio
async def test_translation_writer_skips_locked_lang():
    from app.services.importer.row_writer import TranslationWriter

    session = AsyncMock()
    session.execute = AsyncMock()
    writer = TranslationWriter()
    await writer.write(
        session=session,
        sku="MT-001",
        translations={"en": "Ball valve"},
        locked_fields={"translations.en"},
    )
    session.execute.assert_not_called()


# ── CertificationWriter ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_certification_writer_creates_if_not_found():
    from unittest.mock import MagicMock
    from app.services.importer.row_writer import CertificationWriter
    from app.db.models.vocabularies import Certification

    session = AsyncMock()
    # First execute: SELECT → not found; second execute: INSERT M:N
    not_found_result = MagicMock()
    not_found_result.scalar_one_or_none.return_value = None
    insert_result = MagicMock()
    session.execute = AsyncMock(side_effect=[not_found_result, insert_result])

    writer = CertificationWriter()
    await writer.write(
        session=session,
        sku="MT-001",
        certifications=["CE"],
    )
    session.add.assert_called_once()
    added = session.add.call_args[0][0]
    assert isinstance(added, Certification)
    assert added.code == "CE"
    session.flush.assert_called_once()
