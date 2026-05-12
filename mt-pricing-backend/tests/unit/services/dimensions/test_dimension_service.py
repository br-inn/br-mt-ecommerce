"""Unit tests for dimension services — Fase 3 tablas técnicas.

Covers:
- ActuationCodeService: list + get not-found.
- StandardService: CRUD happy path + 404.
- DimensionService: create_column conflict, delete_column blocked when in
  use, upsert_row (insert vs update), set_cell value mandatory + family
  mismatch.
- PressureTemperatureService: add_point happy path, product not found,
  delete_all bulk.
- get_table_for_product composes columns + rows correctly.

All tests use in-memory async mocks — no DB.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.dimensions.dimension_service import (
    ActuationCodeService,
    DimensionDomainError,
    DimensionService,
    PressureTemperatureService,
    StandardService,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _fake_session(
    *,
    scalar_result: Any = None,
    scalars_all: Any = None,
    get_returns: Any = ...,
    rowcount: int = 1,
) -> MagicMock:
    """Build an AsyncMock session whose execute() returns a settable result."""
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    if get_returns is ...:
        session.get = AsyncMock(return_value=None)
    else:
        session.get = AsyncMock(return_value=get_returns)

    exec_result = MagicMock()
    exec_result.scalar_one_or_none = MagicMock(return_value=scalar_result)
    if scalars_all is not None:
        scalars = MagicMock()
        scalars.all = MagicMock(return_value=scalars_all)
        exec_result.scalars = MagicMock(return_value=scalars)
    exec_result.rowcount = rowcount
    session.execute = AsyncMock(return_value=exec_result)
    return session


def _make_actuation(code: str = "MR") -> MagicMock:
    m = MagicMock()
    m.id = uuid4()
    m.code = code
    m.name_en = code.title()
    m.type = "gearbox"
    return m


def _make_standard(code: str = "ASTM A105") -> MagicMock:
    m = MagicMock()
    m.id = uuid4()
    m.code = code
    m.edition = ""
    m.title_en = "Title"
    m.reference_url = None
    return m


def _make_column(family_id: Any = None, code: str = "dn") -> MagicMock:
    m = MagicMock()
    m.id = uuid4()
    m.family_id = family_id or uuid4()
    m.code = code
    m.label_en = code.upper()
    m.unit = "mm"
    m.order_index = 0
    return m


def _make_row(product_sku: str = "SKU-1", family_id: Any = None) -> MagicMock:
    m = MagicMock()
    m.id = uuid4()
    m.product_sku = product_sku
    m.size_label = "DN50"
    m.dn = 50
    m.actuation_code_id = None
    m.order_index = 0
    m.cells = []
    return m


def _make_product(sku: str = "SKU-1", family_id: Any = None) -> MagicMock:
    m = MagicMock()
    m.sku = sku
    m.family_id = family_id or uuid4()
    return m


# ===========================================================================
# ActuationCodeService
# ===========================================================================
class TestActuationCodeService:
    @pytest.mark.asyncio
    async def test_list_all(self) -> None:
        rows = [_make_actuation("free"), _make_actuation("MR")]
        session = _fake_session(scalars_all=rows)
        svc = ActuationCodeService(session)
        out = await svc.list_all()
        assert out == rows

    @pytest.mark.asyncio
    async def test_get_not_found(self) -> None:
        session = _fake_session(get_returns=None)
        svc = ActuationCodeService(session)
        with pytest.raises(DimensionDomainError) as exc:
            await svc.get(uuid4())
        assert exc.value.code == "actuation_code_not_found"
        assert exc.value.status_code == 404


# ===========================================================================
# StandardService
# ===========================================================================
class TestStandardService:
    @pytest.mark.asyncio
    async def test_create_ok(self) -> None:
        session = _fake_session()
        svc = StandardService(session)
        row = await svc.create(
            {"code": "ASTM A105", "edition": "", "title_en": "X"}
        )
        assert row is not None
        session.add.assert_called_once()
        session.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_get_not_found(self) -> None:
        session = _fake_session(get_returns=None)
        svc = StandardService(session)
        with pytest.raises(DimensionDomainError) as exc:
            await svc.get(uuid4())
        assert exc.value.status_code == 404
        assert exc.value.code == "standard_not_found"

    @pytest.mark.asyncio
    async def test_patch_ok(self) -> None:
        existing = _make_standard()
        session = _fake_session(get_returns=existing)
        svc = StandardService(session)
        out = await svc.patch(existing.id, {"edition": "2015"})
        assert out.edition == "2015"

    @pytest.mark.asyncio
    async def test_delete_ok(self) -> None:
        existing = _make_standard()
        session = _fake_session(get_returns=existing)
        svc = StandardService(session)
        await svc.delete(existing.id)
        session.delete.assert_awaited_once_with(existing)


# ===========================================================================
# DimensionService — columns
# ===========================================================================
class TestDimensionServiceColumns:
    @pytest.mark.asyncio
    async def test_list_columns_for_family(self) -> None:
        family_id = uuid4()
        cols = [_make_column(family_id, "dn"), _make_column(family_id, "a")]
        session = _fake_session(scalars_all=cols)
        svc = DimensionService(session)
        out = await svc.list_columns_for_family(family_id)
        assert out == cols

    @pytest.mark.asyncio
    async def test_create_column_ok(self) -> None:
        session = _fake_session()
        svc = DimensionService(session)
        out = await svc.create_column(
            family_id=uuid4(),
            code="dn",
            label_en="Nominal DN",
            unit="mm",
        )
        assert out is not None
        session.add.assert_called_once()
        session.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_delete_column_blocked_if_in_use(self) -> None:
        existing_col = _make_column()
        # Session.get returns the column; execute returns a non-None for the
        # in-use check.
        session = _fake_session(get_returns=existing_col, scalar_result=uuid4())
        svc = DimensionService(session)
        with pytest.raises(DimensionDomainError) as exc:
            await svc.delete_column(existing_col.id)
        assert exc.value.code == "dimension_column_in_use"
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_delete_column_ok(self) -> None:
        existing_col = _make_column()
        # in-use check returns None (no cells) → delete proceeds.
        session = _fake_session(get_returns=existing_col, scalar_result=None)
        svc = DimensionService(session)
        await svc.delete_column(existing_col.id)
        session.delete.assert_awaited_once_with(existing_col)


# ===========================================================================
# DimensionService — rows
# ===========================================================================
class TestDimensionServiceRows:
    @pytest.mark.asyncio
    async def test_upsert_row_inserts_new(self) -> None:
        product = _make_product(sku="SKU-1")
        # First .get returns product; execute().scalar_one_or_none returns None
        # → insert path.
        session = _fake_session(get_returns=product, scalar_result=None)
        svc = DimensionService(session)
        out = await svc.upsert_row(
            product_sku="SKU-1", size_label="DN50", dn=50
        )
        assert out is not None
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_row_updates_existing(self) -> None:
        product = _make_product(sku="SKU-1")
        existing_row = _make_row("SKU-1")
        session = _fake_session(get_returns=product, scalar_result=existing_row)
        svc = DimensionService(session)
        out = await svc.upsert_row(
            product_sku="SKU-1", size_label="DN50", dn=80, order_index=2
        )
        assert out is existing_row
        assert existing_row.dn == 80
        assert existing_row.order_index == 2
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_upsert_row_product_not_found(self) -> None:
        session = _fake_session(get_returns=None)
        svc = DimensionService(session)
        with pytest.raises(DimensionDomainError) as exc:
            await svc.upsert_row(product_sku="NOPE")
        assert exc.value.code == "product_not_found"
        assert exc.value.status_code == 404


# ===========================================================================
# DimensionService — cells
# ===========================================================================
class TestDimensionServiceCells:
    @pytest.mark.asyncio
    async def test_set_cell_requires_value(self) -> None:
        session = _fake_session()
        svc = DimensionService(session)
        with pytest.raises(DimensionDomainError) as exc:
            await svc.set_cell(uuid4(), uuid4())
        assert exc.value.code == "dimension_cell_value_missing"

    @pytest.mark.asyncio
    async def test_set_cell_family_mismatch(self) -> None:
        family_a = uuid4()
        family_b = uuid4()
        row = _make_row("SKU-1")
        column = _make_column(family_id=family_a)
        product = _make_product(sku="SKU-1", family_id=family_b)

        # get() called for row, then column, then product.
        session = MagicMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.add = MagicMock()
        session.refresh = AsyncMock()
        get_mock = AsyncMock(side_effect=[row, column, product])
        session.get = get_mock
        exec_result = MagicMock()
        exec_result.scalar_one_or_none = MagicMock(return_value=None)
        session.execute = AsyncMock(return_value=exec_result)

        svc = DimensionService(session)
        with pytest.raises(DimensionDomainError) as exc:
            await svc.set_cell(
                row.id, column.id, value_number=Decimal("1")
            )
        assert exc.value.code == "dimension_cell_family_mismatch"
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_set_cell_insert_new(self) -> None:
        family_id = uuid4()
        row = _make_row("SKU-1")
        column = _make_column(family_id=family_id)
        product = _make_product(sku="SKU-1", family_id=family_id)

        session = MagicMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.add = MagicMock()
        session.refresh = AsyncMock()
        session.get = AsyncMock(side_effect=[row, column, product])
        exec_result = MagicMock()
        exec_result.scalar_one_or_none = MagicMock(return_value=None)
        session.execute = AsyncMock(return_value=exec_result)

        svc = DimensionService(session)
        out = await svc.set_cell(
            row.id, column.id, value_number=Decimal("100")
        )
        assert out is not None
        session.add.assert_called_once()


# ===========================================================================
# DimensionService — composite
# ===========================================================================
class TestGetTableForProduct:
    @pytest.mark.asyncio
    async def test_product_not_found(self) -> None:
        session = _fake_session(get_returns=None)
        svc = DimensionService(session)
        with pytest.raises(DimensionDomainError) as exc:
            await svc.get_table_for_product("NOPE")
        assert exc.value.code == "product_not_found"

    @pytest.mark.asyncio
    async def test_composite_ok(self) -> None:
        family_id = uuid4()
        product = _make_product(sku="SKU-1", family_id=family_id)
        cols = [_make_column(family_id, "dn")]
        rows = [_make_row("SKU-1")]

        # execute() returns different result objects depending on call —
        # easiest: build a side_effect list of MagicMock result objects.
        session = MagicMock()
        session.get = AsyncMock(return_value=product)

        cols_result = MagicMock()
        cols_scalars = MagicMock()
        cols_scalars.all = MagicMock(return_value=cols)
        cols_result.scalars = MagicMock(return_value=cols_scalars)

        rows_result = MagicMock()
        rows_scalars = MagicMock()
        rows_scalars.all = MagicMock(return_value=rows)
        rows_result.scalars = MagicMock(return_value=rows_scalars)

        session.execute = AsyncMock(side_effect=[cols_result, rows_result])

        svc = DimensionService(session)
        out = await svc.get_table_for_product("SKU-1")
        assert out["product_sku"] == "SKU-1"
        assert out["family_id"] == family_id
        assert out["columns"] == cols
        assert out["rows"] == rows


# ===========================================================================
# PressureTemperatureService
# ===========================================================================
class TestPressureTemperatureService:
    @pytest.mark.asyncio
    async def test_add_point_product_not_found(self) -> None:
        session = _fake_session(get_returns=None)
        svc = PressureTemperatureService(session)
        with pytest.raises(DimensionDomainError) as exc:
            await svc.add_point(
                "NOPE",
                temperature_c=Decimal("20"),
                pressure_max_bar=Decimal("16"),
            )
        assert exc.value.code == "product_not_found"
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_add_point_ok(self) -> None:
        product = _make_product(sku="SKU-1")
        session = _fake_session(get_returns=product)
        svc = PressureTemperatureService(session)
        out = await svc.add_point(
            "SKU-1",
            temperature_c=Decimal("100"),
            pressure_max_bar=Decimal("16"),
            series_variant_code="PN16",
        )
        assert out is not None
        session.add.assert_called_once()
        session.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_add_point_negative_pressure_rejected(self) -> None:
        product = _make_product(sku="SKU-1")
        session = _fake_session(get_returns=product)
        svc = PressureTemperatureService(session)
        with pytest.raises(DimensionDomainError) as exc:
            await svc.add_point(
                "SKU-1",
                temperature_c=Decimal("20"),
                pressure_max_bar=Decimal("-1"),
            )
        assert exc.value.code == "ptp_invalid_pressure"
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_get_curve_for_product_ok(self) -> None:
        product = _make_product(sku="SKU-1")
        # First .get returns product; execute returns scalars w/ empty list.
        session = _fake_session(get_returns=product, scalars_all=[])
        svc = PressureTemperatureService(session)
        out = await svc.get_curve_for_product("SKU-1", "PN16")
        assert out["product_sku"] == "SKU-1"
        assert out["series_variant_code"] == "PN16"
        assert out["points"] == []

    @pytest.mark.asyncio
    async def test_delete_all_for_product(self) -> None:
        session = _fake_session(rowcount=3)
        svc = PressureTemperatureService(session)
        out = await svc.delete_all_for_product("SKU-1")
        assert out == 3
        session.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_get_point_not_found(self) -> None:
        session = _fake_session(get_returns=None)
        svc = PressureTemperatureService(session)
        with pytest.raises(DimensionDomainError) as exc:
            await svc.get_point(uuid4())
        assert exc.value.code == "ptp_not_found"
