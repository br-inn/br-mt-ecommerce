"""US-INV-01-01 — smoke: importación de modelos y factory ERP sin errores."""

from __future__ import annotations

from datetime import UTC

import pytest

pytestmark = pytest.mark.unit


def test_inventory_models_importable() -> None:
    """Los 5 modelos de inventario se importan sin errores circulares."""
    from app.db.models.inventory import (
        CostLot,
        GoodsReceipt,
        InventoryPosition,
        PurchaseOrder,
        PurchaseOrderLine,
    )

    assert PurchaseOrder.__tablename__ == "purchase_orders"
    assert PurchaseOrderLine.__tablename__ == "purchase_order_lines"
    assert GoodsReceipt.__tablename__ == "goods_receipts"
    assert CostLot.__tablename__ == "cost_lots"
    assert InventoryPosition.__tablename__ == "inventory_positions"


def test_inventory_models_registered_in_metadata() -> None:
    """Los 5 modelos quedan registrados en Base.metadata tras importar models."""
    from app.db import Base
    from app.db import models as _

    expected = {
        "purchase_orders",
        "purchase_order_lines",
        "goods_receipts",
        "cost_lots",
        "inventory_positions",
    }
    registered = set(Base.metadata.tables.keys())
    missing = expected - registered
    assert not missing, f"Tablas no registradas en Base.metadata: {missing}"


def test_inventory_models_in_all_exports() -> None:
    """Los 5 modelos están en app.db.models.__all__."""
    from app.db import models

    expected = {
        "PurchaseOrder",
        "PurchaseOrderLine",
        "GoodsReceipt",
        "CostLot",
        "InventoryPosition",
    }
    missing = expected - set(models.__all__)
    assert not missing, f"Faltan en __all__: {missing}"


def test_po_status_enum_values() -> None:
    """POStatus tiene exactamente los valores requeridos."""
    from app.db.enums import POStatus

    assert set(POStatus) == {
        POStatus.DRAFT,
        POStatus.CONFIRMED,
        POStatus.PARTIAL,
        POStatus.RECEIVED,
        POStatus.CANCELLED,
    }


def test_gr_status_enum_values() -> None:
    """GRStatus tiene exactamente los valores requeridos."""
    from app.db.enums import GRStatus

    assert set(GRStatus) == {GRStatus.PENDING, GRStatus.PROCESSED, GRStatus.ERROR}


def test_erp_factory_returns_noop_by_default() -> None:
    """get_erp_adapter() retorna NoOpAdapter cuando ERP_ADAPTER='noop'."""
    from app.integrations.erp.factory import get_erp_adapter
    from app.integrations.erp.noop_adapter import NoOpAdapter

    # Limpiar cache para forzar re-creación con settings de test
    get_erp_adapter.cache_clear()

    adapter = get_erp_adapter()
    assert isinstance(adapter, NoOpAdapter)

    # Cleanup para no afectar otros tests
    get_erp_adapter.cache_clear()


@pytest.mark.asyncio
async def test_noop_adapter_health_check() -> None:
    """NoOpAdapter.health_check() retorna True sin excepciones."""
    from app.integrations.erp.noop_adapter import NoOpAdapter

    adapter = NoOpAdapter()
    result = await adapter.health_check()
    assert result is True


@pytest.mark.asyncio
async def test_noop_adapter_pull_purchase_orders_returns_empty() -> None:
    """NoOpAdapter.pull_purchase_orders() retorna lista vacía."""
    from datetime import datetime

    from app.integrations.erp.noop_adapter import NoOpAdapter

    adapter = NoOpAdapter()
    result = await adapter.pull_purchase_orders(since=datetime.now(tz=UTC))
    assert result == []
