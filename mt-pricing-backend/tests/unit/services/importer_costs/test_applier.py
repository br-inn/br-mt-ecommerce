"""Unit tests para `app.services.importer_costs.applier` con CostService mockeado.

NO necesita DB — el applier sólo invoca ``cost_service.create_cost(**kwargs)``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.importer_costs.applier import (
    FxMissingError,
    apply_cost_diffs,
)
from app.services.importer_costs.differ import CostDiff, CostRowAction

pytestmark = pytest.mark.unit


def _diff(action: CostRowAction, *, sku="SKU1", row=1, scheme="FBA") -> CostDiff:
    return CostDiff(
        row_index=row,
        sku=sku,
        scheme_code=scheme,
        supplier_code="SUP-A",
        action=action,
        payload={
            "product_sku": sku,
            "scheme_code": scheme,
            "supplier_code": "SUP-A",
            "currency": "AED",
            "total": Decimal("100"),
            "breakdown": {"fob": "80"},
            "effective_at": None,
        },
    )


def _mk_actor() -> Any:
    actor = MagicMock()
    actor.id = "00000000-0000-0000-0000-000000000001"
    actor.email = "tester@mt.ae"
    return actor


async def test_apply_create_calls_cost_service() -> None:
    cost_service = MagicMock()
    cost_service.create_cost = AsyncMock(return_value=MagicMock(id="x"))
    diffs = [_diff(CostRowAction.CREATE)]
    res = await apply_cost_diffs(diffs, _mk_actor(), cost_service=cost_service, run_id="r1")
    assert res.created == 1
    assert res.updated == 0
    assert res.errors == 0
    assert cost_service.create_cost.await_count == 1
    # Asegura que pasamos el run_id como _import_run_id (audit hint).
    call_kwargs = cost_service.create_cost.call_args.kwargs
    assert call_kwargs["_import_run_id"] == "r1"
    assert call_kwargs["product_sku"] == "SKU1"


async def test_apply_update_increments_counter() -> None:
    cost_service = MagicMock()
    cost_service.create_cost = AsyncMock()
    diffs = [_diff(CostRowAction.UPDATE)]
    res = await apply_cost_diffs(diffs, _mk_actor(), cost_service=cost_service, run_id="r1")
    assert res.updated == 1
    assert res.created == 0


async def test_apply_skips_no_change_orphan_error() -> None:
    cost_service = MagicMock()
    cost_service.create_cost = AsyncMock()
    diffs = [
        _diff(CostRowAction.NO_CHANGE, row=1),
        _diff(CostRowAction.ORPHAN, row=2),
        _diff(CostRowAction.ERROR, row=3),
    ]
    res = await apply_cost_diffs(diffs, _mk_actor(), cost_service=cost_service, run_id="r1")
    assert res.no_change == 1
    assert res.orphans == 1
    assert res.errors == 1
    assert cost_service.create_cost.await_count == 0


async def test_apply_handles_fx_missing() -> None:
    cost_service = MagicMock()
    cost_service.create_cost = AsyncMock(side_effect=FxMissingError("no fx for EUR @ 2026-05-07"))
    diffs = [_diff(CostRowAction.CREATE)]
    res = await apply_cost_diffs(diffs, _mk_actor(), cost_service=cost_service, run_id="r1")
    assert res.errors_fx_missing == 1
    assert res.created == 0
    assert len(res.failure_details) == 1
    assert res.failure_details[0]["code"] == "fx_missing"


async def test_apply_continues_on_unexpected_error() -> None:
    cost_service = MagicMock()
    cost_service.create_cost = AsyncMock(side_effect=[RuntimeError("boom"), MagicMock(id="ok")])
    diffs = [
        _diff(CostRowAction.CREATE, row=1, sku="A"),
        _diff(CostRowAction.CREATE, row=2, sku="B"),
    ]
    res = await apply_cost_diffs(diffs, _mk_actor(), cost_service=cost_service, run_id="r1")
    # Primera falla, segunda OK.
    assert res.errors == 1
    assert res.created == 1
    assert res.failure_details[0]["sku"] == "A"
    assert res.failure_details[0]["code"] == "RuntimeError"


async def test_apply_result_to_dict_serializable() -> None:
    cost_service = MagicMock()
    cost_service.create_cost = AsyncMock()
    res = await apply_cost_diffs(
        [_diff(CostRowAction.CREATE)],
        _mk_actor(),
        cost_service=cost_service,
        run_id="r1",
    )
    d = res.to_dict()
    assert d["created"] == 1
    assert isinstance(d["started_at"], str)
    assert isinstance(d["finished_at"], str)
