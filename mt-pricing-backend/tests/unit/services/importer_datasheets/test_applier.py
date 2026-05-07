"""Unit tests para `app.services.importer_datasheets.applier`."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.importer_datasheets.applier import (
    DatasheetDiff,
    apply_datasheet_diffs,
)
from app.services.importer_datasheets.spec_parser import DatasheetSpecs

pytestmark = pytest.mark.unit


def _mk_actor() -> Any:
    a = MagicMock()
    a.id = uuid4()
    a.email = "tester@mt.ae"
    return a


def _diff(*, sku: str = "MT-V-001", row: int = 0) -> DatasheetDiff:
    return DatasheetDiff(
        row_index=row,
        filename=f"MTFT_{sku.split('-')[-1]}.pdf",
        kind="ficha_tecnica",
        product_sku=sku,
        storage_path=f"product-datasheets/MTFT_{sku.split('-')[-1]}.pdf",
        specs=DatasheetSpecs(dn="DN50", pn="PN16", material="brass"),
        file_size_bytes=1024,
    )


async def test_apply_invokes_attach() -> None:
    product_service = MagicMock()
    product_service.attach_datasheet = AsyncMock(return_value=MagicMock(id="x"))
    res = await apply_datasheet_diffs(
        [_diff()],
        _mk_actor(),
        product_service=product_service,
        run_id="r1",
    )
    assert res.attached == 1
    assert res.errors == 0
    assert product_service.attach_datasheet.await_count == 1
    kwargs = product_service.attach_datasheet.call_args.kwargs
    assert kwargs["product_sku"] == "MT-V-001"
    assert kwargs["kind"] == "ficha_tecnica"
    assert kwargs["specs"]["dn"] == "DN50"
    assert kwargs["_import_run_id"] == "r1"


async def test_apply_continues_on_error() -> None:
    product_service = MagicMock()
    product_service.attach_datasheet = AsyncMock(
        side_effect=[RuntimeError("boom"), MagicMock(id="ok")]
    )
    res = await apply_datasheet_diffs(
        [_diff(sku="MT-V-A", row=1), _diff(sku="MT-V-B", row=2)],
        _mk_actor(),
        product_service=product_service,
    )
    assert res.attached == 1
    assert res.errors == 1
    assert res.errors_details[0]["sku"] == "MT-V-A"
    assert res.errors_details[0]["code"] == "internal_error"


async def test_apply_empty_returns_zero() -> None:
    product_service = MagicMock()
    product_service.attach_datasheet = AsyncMock()
    res = await apply_datasheet_diffs([], _mk_actor(), product_service=product_service)
    assert res.attached == 0
    assert res.total_rows == 0


async def test_result_to_dict_serializable() -> None:
    product_service = MagicMock()
    product_service.attach_datasheet = AsyncMock(return_value=MagicMock(id="x"))
    res = await apply_datasheet_diffs(
        [_diff()],
        _mk_actor(),
        product_service=product_service,
    )
    d = res.to_dict()
    assert d["attached"] == 1
    assert isinstance(d["started_at"], str)
    assert isinstance(d["finished_at"], str)
