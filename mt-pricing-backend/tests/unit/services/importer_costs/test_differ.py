"""Unit tests para `app.services.importer_costs.differ` (sin DB real)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.importer_costs.differ import (
    CostRowAction,
    OrphanReport,
    _compute_field_diff,
    compute_cost_diff,
)
from app.services.importer_costs.parser import CostRow

pytestmark = pytest.mark.unit


def _row(
    *,
    row_index=1,
    sku="SKU001",
    scheme="FBA",
    supplier="SUP-A",
    total="100.50",
    breakdown=None,
    errors=None,
    currency="AED",
):
    return CostRow(
        row_index=row_index,
        sku=sku,
        scheme_code=scheme,
        supplier_code=supplier,
        currency=currency,
        total=Decimal(total) if total is not None else None,
        breakdown=breakdown or {"fob": "80"},
        effective_at=None,
        errors=list(errors or []),
    )


class _FakeCost:
    def __init__(
        self,
        sku: str,
        scheme: str,
        supplier: str | None,
        total: Decimal,
        currency: str = "AED",
        breakdown: dict[str, Any] | None = None,
    ) -> None:
        self.product_sku = sku
        self.scheme_code = scheme
        self.supplier_code = supplier
        self.total = total
        self.currency = currency
        self.breakdown = breakdown or {}


def _mk_session_with(
    *,
    products: list[str] | None = None,
    schemes: list[str] | None = None,
    suppliers: list[str] | None = None,
    active_costs: list[_FakeCost] | None = None,
) -> MagicMock:
    session = MagicMock()
    products = products or []
    schemes = schemes or []
    suppliers = suppliers or []
    active_costs = active_costs or []

    call_counter = {"i": 0}

    async def _execute(stmt: Any) -> MagicMock:
        # Devuelve resultados según el orden de invocación esperado
        # por compute_cost_diff: products, schemes, suppliers, active_costs.
        call_counter["i"] += 1
        idx = call_counter["i"]
        result = MagicMock()
        if idx == 1:
            result.all.return_value = [(s,) for s in products]
        elif idx == 2:
            result.all.return_value = [(s,) for s in schemes]
        elif idx == 3:
            result.all.return_value = [(s,) for s in suppliers]
        else:
            result.scalars.return_value.all.return_value = active_costs
        return result

    session.execute = AsyncMock(side_effect=_execute)
    return session


async def test_compute_field_diff_detects_total_change() -> None:
    cur = _FakeCost("A", "FBA", "S", Decimal("100"))
    diff = _compute_field_diff(
        {
            "total": Decimal("120"),
            "currency": "AED",
            "supplier_code": "S",
            "breakdown": {},
        },
        cur,
    )
    assert "total" in diff
    assert diff["total"]["from"] == "100"
    assert diff["total"]["to"] == "120"


async def test_create_action_when_no_active_cost() -> None:
    session = _mk_session_with(
        products=["SKU001"],
        schemes=["FBA"],
        suppliers=["SUP-A"],
        active_costs=[],
    )
    diffs, orphans = await compute_cost_diff(session, [_row()])
    assert len(diffs) == 1
    assert diffs[0].action == CostRowAction.CREATE
    assert orphans.sku_not_in_pim == []


async def test_orphan_when_sku_missing() -> None:
    session = _mk_session_with(
        products=[],  # SKU001 no existe
        schemes=["FBA"],
        suppliers=["SUP-A"],
    )
    diffs, orphans = await compute_cost_diff(session, [_row()])
    assert diffs[0].action == CostRowAction.ORPHAN
    assert "sku_not_in_pim" in diffs[0].orphan_reasons
    assert orphans.sku_not_in_pim == ["SKU001"]


async def test_orphan_when_scheme_missing() -> None:
    session = _mk_session_with(
        products=["SKU001"],
        schemes=[],  # FBA no existe
        suppliers=["SUP-A"],
    )
    diffs, orphans = await compute_cost_diff(session, [_row()])
    assert diffs[0].action == CostRowAction.ORPHAN
    assert "scheme_unknown" in diffs[0].orphan_reasons
    assert orphans.scheme_unknown == ["FBA"]


async def test_orphan_when_supplier_missing() -> None:
    session = _mk_session_with(
        products=["SKU001"],
        schemes=["FBA"],
        suppliers=[],
    )
    diffs, orphans = await compute_cost_diff(session, [_row()])
    assert diffs[0].action == CostRowAction.ORPHAN
    assert "supplier_unknown" in diffs[0].orphan_reasons


async def test_update_when_total_changed() -> None:
    cur = _FakeCost("SKU001", "FBA", "SUP-A", Decimal("80.00"), "AED", {"fob": "70"})
    session = _mk_session_with(
        products=["SKU001"],
        schemes=["FBA"],
        suppliers=["SUP-A"],
        active_costs=[cur],
    )
    diffs, _ = await compute_cost_diff(session, [_row(total="100.50")])
    assert diffs[0].action == CostRowAction.UPDATE
    assert "total" in diffs[0].diff
    assert "breakdown" in diffs[0].diff


async def test_no_change_when_identical() -> None:
    cur = _FakeCost(
        "SKU001",
        "FBA",
        "SUP-A",
        Decimal("100.50"),
        "AED",
        {"fob": "80"},
    )
    session = _mk_session_with(
        products=["SKU001"],
        schemes=["FBA"],
        suppliers=["SUP-A"],
        active_costs=[cur],
    )
    diffs, _ = await compute_cost_diff(session, [_row(total="100.50")])
    assert diffs[0].action == CostRowAction.NO_CHANGE


async def test_error_row_passes_through() -> None:
    bad = _row(errors=["broken"])
    session = _mk_session_with()
    diffs, _ = await compute_cost_diff(session, [bad])
    assert diffs[0].action == CostRowAction.ERROR
    assert "broken" in diffs[0].errors


def test_orphan_report_to_dict() -> None:
    orph = OrphanReport(
        sku_not_in_pim=["A"], scheme_unknown=["B"], supplier_unknown=["C"]
    )
    d = orph.to_dict()
    assert d == {
        "sku_not_in_pim": ["A"],
        "scheme_unknown": ["B"],
        "supplier_unknown": ["C"],
    }
