"""Tests para MAPService — US-INV-01-02.

Suite:
- test_calculate_map_formula   : fórmula WAC pura, sin DB
- test_map_primer_lote         : process_gr con posición inexistente
- test_map_segundo_lote        : process_gr sobre posición existente
- test_map_idempotente         : segundo process_gr no muta la posición
- test_map_actualiza_costs     : cost.scheme_landed_aed == map_after post-process_gr

asyncio_mode = "auto" (pyproject.toml). Usa mocks — sin DB real para la suite
de servicios (aislada de integración).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.inventory.map_service import MAPService, _infer_currency

pytestmark = pytest.mark.unit


# ===========================================================================
# Helpers
# ===========================================================================


def _make_gr(
    *,
    gr_id: uuid.UUID | None = None,
    po_line_id: uuid.UUID | None = None,
    qty_received: str = "10",
    actual_unit_price: str | None = None,
    actual_breakdown: dict | None = None,
    fx_rate_id: uuid.UUID | None = None,
    status: str = "pending",
    map_before: str | None = None,
    map_after: str | None = None,
) -> MagicMock:
    gr = MagicMock()
    gr.id = gr_id or uuid.uuid4()
    gr.po_line_id = po_line_id or uuid.uuid4()
    gr.qty_received = Decimal(qty_received)
    gr.actual_unit_price = Decimal(actual_unit_price) if actual_unit_price else None
    gr.actual_breakdown = actual_breakdown or {}
    gr.fx_rate_id = fx_rate_id
    gr.status = status
    gr.map_before = Decimal(map_before) if map_before else None
    gr.map_after = Decimal(map_after) if map_after else None
    gr.received_at = datetime(2026, 5, 12, tzinfo=timezone.utc)
    gr.notes = None
    return gr


def _make_pol(
    *,
    pol_id: uuid.UUID | None = None,
    po_id: uuid.UUID | None = None,
    sku: str = "SKU-001",
    scheme_code: str = "AE_STANDARD",
    unit_price: str = "10.00",
    landed_cost_breakdown: dict | None = None,
    supplier_code: str = "SUP-01",
) -> MagicMock:
    pol = MagicMock()
    pol.id = pol_id or uuid.uuid4()
    pol.po_id = po_id or uuid.uuid4()
    pol.sku = sku
    pol.scheme_code = scheme_code
    pol.unit_price = Decimal(unit_price)
    pol.landed_cost_breakdown = landed_cost_breakdown or {}
    pol._po_supplier_code = supplier_code
    return pol


def _make_position(
    *,
    sku: str = "SKU-001",
    supplier_code: str = "SUP-01",
    scheme_code: str = "AE_STANDARD",
    qty_on_hand: str = "10",
    map_aed: str = "11.20",
) -> MagicMock:
    pos = MagicMock()
    pos.sku = sku
    pos.supplier_code = supplier_code
    pos.scheme_code = scheme_code
    pos.qty_on_hand = Decimal(qty_on_hand)
    pos.map_aed = Decimal(map_aed)
    qty = Decimal(qty_on_hand)
    mp = Decimal(map_aed)
    pos.total_stock_value_aed = qty * mp
    pos.last_gr_id = None
    pos.last_updated_at = None
    return pos


# ===========================================================================
# test_calculate_map_formula
# ===========================================================================


class TestCalculateMapFormula:
    def test_primer_lote_returns_unit_cost(self) -> None:
        svc = MAPService(session=MagicMock())
        result = svc.calculate_map(
            qty_existing=Decimal("0"),
            value_existing_aed=Decimal("0"),
            qty_new=Decimal("10"),
            unit_cost_aed_new=Decimal("11.20"),
        )
        assert result == Decimal("11.2000")

    def test_segundo_lote_weighted_average(self) -> None:
        svc = MAPService(session=MagicMock())
        result = svc.calculate_map(
            qty_existing=Decimal("10"),
            value_existing_aed=Decimal("10") * Decimal("11.20"),
            qty_new=Decimal("10"),
            unit_cost_aed_new=Decimal("13.35"),
        )
        assert result == Decimal("12.2750")

    def test_rounding_round_half_up(self) -> None:
        svc = MAPService(session=MagicMock())
        result = svc.calculate_map(
            qty_existing=Decimal("3"),
            value_existing_aed=Decimal("3") * Decimal("10"),
            qty_new=Decimal("1"),
            unit_cost_aed_new=Decimal("10"),
        )
        assert result == Decimal("10.0000")


# ===========================================================================
# test_map_primer_lote
# ===========================================================================


class TestMapPrimerLote:
    @pytest.mark.asyncio
    async def test_map_primer_lote(self) -> None:
        """Posición inexistente → MAP = unit_cost_aed (11.20)."""
        gr_id = uuid.uuid4()
        gr = _make_gr(gr_id=gr_id, qty_received="10", actual_unit_price="11.20")
        pol = _make_pol(sku="SKU-001", scheme_code="AE_STANDARD", supplier_code="SUP-01")

        session = AsyncMock()

        expected_pos = _make_position(qty_on_hand="10", map_aed="11.2000")

        svc = MAPService(session=session)

        with (
            patch.object(svc, "_load_gr", AsyncMock(return_value=_attach_pol(gr, pol))),
            patch.object(svc, "_get_position", AsyncMock(return_value=None)),
            patch.object(svc, "_resolve_unit_cost_aed", AsyncMock(return_value=Decimal("11.20"))),
            patch.object(svc, "_upsert_inventory_position", AsyncMock(return_value=expected_pos)),
            patch.object(svc, "_insert_cost_lot", AsyncMock()),
            patch.object(svc, "_update_cost", AsyncMock()),
        ):
            pos = await svc.process_gr(gr_id)

        assert pos.map_aed == Decimal("11.2000")
        assert gr.map_before is None
        assert gr.map_after == Decimal("11.2000")
        assert gr.status == "processed"


# ===========================================================================
# test_map_segundo_lote
# ===========================================================================


class TestMapSegundoLote:
    @pytest.mark.asyncio
    async def test_map_segundo_lote(self) -> None:
        """Posición existente (10 × 11.20), nuevo lote (10 × 13.35) → MAP = 12.275."""
        gr_id = uuid.uuid4()
        gr = _make_gr(gr_id=gr_id, qty_received="10", actual_unit_price="13.35")
        pol = _make_pol(sku="SKU-001", scheme_code="AE_STANDARD", supplier_code="SUP-01")

        existing_pos = _make_position(qty_on_hand="10", map_aed="11.20")

        session = AsyncMock()

        expected_pos = _make_position(qty_on_hand="20", map_aed="12.2750")

        svc = MAPService(session=session)

        with (
            patch.object(svc, "_load_gr", AsyncMock(return_value=_attach_pol(gr, pol))),
            patch.object(svc, "_get_position", AsyncMock(return_value=existing_pos)),
            patch.object(svc, "_resolve_unit_cost_aed", AsyncMock(return_value=Decimal("13.35"))),
            patch.object(svc, "_upsert_inventory_position", AsyncMock(return_value=expected_pos)),
            patch.object(svc, "_insert_cost_lot", AsyncMock()),
            patch.object(svc, "_update_cost", AsyncMock()),
        ):
            pos = await svc.process_gr(gr_id)

        assert pos.map_aed == Decimal("12.2750")
        assert gr.map_before == Decimal("11.20")
        assert gr.map_after == Decimal("12.2750")


# ===========================================================================
# test_map_idempotente
# ===========================================================================


class TestMapIdempotente:
    @pytest.mark.asyncio
    async def test_map_idempotente(self) -> None:
        """Si gr.status == 'processed', process_gr retorna posición sin cambios."""
        gr_id = uuid.uuid4()
        gr = _make_gr(gr_id=gr_id, status="processed", map_before="11.20", map_after="12.2750")
        pol = _make_pol()
        existing_pos = _make_position(qty_on_hand="20", map_aed="12.2750")

        session = AsyncMock()

        svc = MAPService(session=session)

        with (
            patch.object(svc, "_load_gr", AsyncMock(return_value=_attach_pol(gr, pol))),
            patch.object(svc, "_get_position", AsyncMock(return_value=existing_pos)),
            patch.object(svc, "_resolve_unit_cost_aed", AsyncMock()) as mock_resolve,
            patch.object(svc, "_upsert_inventory_position", AsyncMock()) as mock_upsert,
            patch.object(svc, "_insert_cost_lot", AsyncMock()) as mock_lot,
            patch.object(svc, "_update_cost", AsyncMock()) as mock_cost,
        ):
            pos = await svc.process_gr(gr_id)

        mock_resolve.assert_not_called()
        mock_upsert.assert_not_called()
        mock_lot.assert_not_called()
        mock_cost.assert_not_called()
        assert pos.map_aed == Decimal("12.2750")


# ===========================================================================
# test_map_actualiza_costs
# ===========================================================================


class TestMapActualizaCosts:
    @pytest.mark.asyncio
    async def test_map_actualiza_costs(self) -> None:
        """Después de process_gr, _update_cost es llamado con el map_after."""
        gr_id = uuid.uuid4()
        gr = _make_gr(gr_id=gr_id, qty_received="10", actual_unit_price="11.20")
        pol = _make_pol(sku="SKU-001", scheme_code="AE_STANDARD", supplier_code="SUP-01")

        session = AsyncMock()

        expected_pos = _make_position(qty_on_hand="10", map_aed="11.2000")

        svc = MAPService(session=session)
        update_cost_mock = AsyncMock()

        with (
            patch.object(svc, "_load_gr", AsyncMock(return_value=_attach_pol(gr, pol))),
            patch.object(svc, "_get_position", AsyncMock(return_value=None)),
            patch.object(svc, "_resolve_unit_cost_aed", AsyncMock(return_value=Decimal("11.20"))),
            patch.object(svc, "_upsert_inventory_position", AsyncMock(return_value=expected_pos)),
            patch.object(svc, "_insert_cost_lot", AsyncMock()),
            patch.object(svc, "_update_cost", update_cost_mock),
        ):
            await svc.process_gr(gr_id)

        update_cost_mock.assert_awaited_once()
        call_kwargs = update_cost_mock.call_args.kwargs
        assert call_kwargs["map_aed"] == Decimal("11.2000")
        assert call_kwargs["sku"] == "SKU-001"
        assert call_kwargs["scheme_code"] == "AE_STANDARD"


# ===========================================================================
# test__infer_currency helper
# ===========================================================================


class TestInferCurrency:
    def test_all_aed_returns_aed(self) -> None:
        assert _infer_currency({"fob_aed": 100, "freight_aed": 20}) == "AED"

    def test_eur_key_returns_eur(self) -> None:
        assert _infer_currency({"fob_eur": 100, "customs_aed": 20}) == "EUR"

    def test_empty_returns_aed(self) -> None:
        assert _infer_currency({}) == "AED"


# ===========================================================================
# Internal helpers
# ===========================================================================


def _attach_pol(gr: MagicMock, pol: MagicMock) -> MagicMock:
    gr._po_line = pol
    gr._pol_sku = pol.sku
    gr._pol_supplier_code = pol._po_supplier_code
    gr._pol_scheme_code = pol.scheme_code
    return gr
