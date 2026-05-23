"""Tests del NoOpAdapter y factory — US-INV-01-06.

Tests puramente unitarios (sin I/O). Verifican:
- NoOpAdapter retorna los valores correctos.
- La factory selecciona NoOpAdapter para ERP_ADAPTER="noop".
- La factory lanza ValueError para adapters desconocidos.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.integrations.erp.events import GoodsReceivedEvent, MAPUpdatedEvent
from app.integrations.erp.noop_adapter import NoOpAdapter

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_gr_event(gr_id: str = "abcdef1234567890") -> GoodsReceivedEvent:
    return GoodsReceivedEvent(
        gr_id=gr_id,
        po_number="PO-001",
        sku="SKU-TEST-001",
        supplier_code="SUP-001",
        scheme_code="AE",
        qty_received=Decimal("10"),
        actual_unit_price=Decimal("100.00"),
        actual_breakdown={"base": "90.00", "freight": "10.00"},
        map_before=None,
        map_after=Decimal("100.00"),
        received_at=datetime.now(UTC),
        mt_system_ref=f"MT-GR-{gr_id[:8]}",
    )


def _make_map_event() -> MAPUpdatedEvent:
    return MAPUpdatedEvent(
        sku="SKU-TEST-001",
        supplier_code="SUP-001",
        scheme_code="AE",
        map_before=Decimal("95.00"),
        map_after=Decimal("100.00"),
        triggered_by_gr_id="abcdef12",
        updated_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# NoOpAdapter tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_push_goods_receipt_returns_ref() -> None:
    """push_goods_receipt retorna 'noop-ref-' seguido de los 8 primeros chars del gr_id."""
    adapter = NoOpAdapter()
    event = _make_gr_event(gr_id="abcdef1234567890")
    ref = await adapter.push_goods_receipt(event)
    assert ref.startswith("noop-ref-")
    assert ref == "noop-ref-abcdef12"


@pytest.mark.asyncio
async def test_pull_purchase_orders_returns_empty() -> None:
    """pull_purchase_orders retorna lista vacía."""
    adapter = NoOpAdapter()
    result = await adapter.pull_purchase_orders(since=datetime.now(UTC))
    assert result == []


@pytest.mark.asyncio
async def test_health_check_true() -> None:
    """health_check retorna True."""
    adapter = NoOpAdapter()
    result = await adapter.health_check()
    assert result is True


@pytest.mark.asyncio
async def test_push_map_update_returns_none() -> None:
    """push_map_update retorna None sin lanzar excepciones."""
    adapter = NoOpAdapter()
    event = _make_map_event()
    result = await adapter.push_map_update(event)
    assert result is None


# ---------------------------------------------------------------------------
# Factory tests
# ---------------------------------------------------------------------------


def test_factory_returns_noop_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_erp_adapter() retorna NoOpAdapter cuando ERP_ADAPTER='noop'."""
    from app.core.config import settings
    from app.integrations.erp.factory import get_erp_adapter

    monkeypatch.setattr(settings, "ERP_ADAPTER", "noop")
    get_erp_adapter.cache_clear()
    try:
        adapter = get_erp_adapter()
        assert isinstance(adapter, NoOpAdapter)
    finally:
        get_erp_adapter.cache_clear()


def test_factory_raises_on_unknown_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_erp_adapter() lanza ValueError para ERP_ADAPTER desconocido."""
    from app.core.config import settings
    from app.integrations.erp.factory import get_erp_adapter

    monkeypatch.setattr(settings, "ERP_ADAPTER", "unknown_erp")
    get_erp_adapter.cache_clear()
    try:
        with pytest.raises(ValueError, match="unknown_erp"):
            get_erp_adapter()
    finally:
        get_erp_adapter.cache_clear()
