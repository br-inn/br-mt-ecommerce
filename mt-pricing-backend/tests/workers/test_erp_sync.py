"""US-INV-01-07 — Celery task ``push_erp_event``.

Tests unitarios que validan el comportamiento del processor sin Postgres real.
Llaman directamente a ``_process_event`` (función async extraída) usando
``pytest-asyncio`` y mocks en memoria.

Las importaciones se hacen localmente dentro de ``_process_event``, así que
los patches apuntan a los módulos fuente (no al módulo erp_sync):
- ``app.db.engine.get_sessionmaker``
- ``app.integrations.erp.factory.get_erp_adapter``
- ``app.core.config.settings``

Criterios cubiertos:
- test_skip_on_noop_adapter      : ERP_ADAPTER='noop' → status='skipped'
- test_skip_on_already_processed : evento con status='delivered' → sin cambios
- test_failed_after_max_retries  : attempts=4 + exception → status='failed', no retry
- test_hmac_computed_when_secret_set : ERP_WEBHOOK_SECRET != '' → hmac en logs DEBUG
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---- Helpers -----------------------------------------------------------------

def _make_event(
    *,
    status: str = "pending",
    attempts: int = 0,
    adapter: str = "sap",
    event_type: str = "goods_received",
    payload: dict | None = None,
) -> MagicMock:
    """Construye un mock liviano de ERPSyncEvent."""
    ev = MagicMock()
    ev.id = uuid.uuid4()
    ev.status = status
    ev.attempts = attempts
    ev.adapter = adapter
    ev.event_type = event_type
    ev.payload = payload or {
        "gr_id": str(uuid.uuid4()),
        "po_number": "PO-001",
        "sku": "SKU-TEST",
        "supplier_code": "SUP-01",
        "scheme_code": "SCH-AE",
        "qty_received": "10.000",
        "actual_unit_price": "100.00",
        "actual_breakdown": {},
        "map_before": None,
        "map_after": "100.00",
        "received_at": "2026-05-12T10:00:00+00:00",
        "mt_system_ref": "MT-GR-abcd1234",
    }
    ev.last_error = None
    ev.last_attempted_at = None
    ev.delivered_at = None
    ev.external_ref = None
    return ev


def _build_sessionmaker(event: MagicMock):
    """Devuelve un mock de get_sessionmaker() cuyo context manager retorna session."""
    session = AsyncMock()
    session.get = AsyncMock(return_value=event)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)

    sm_instance = MagicMock(return_value=cm)
    sm_factory = MagicMock(return_value=sm_instance)
    # Exponer session para asserts
    sm_factory._session = session
    return sm_factory


def _make_settings(adapter: str = "noop", secret: str = "") -> MagicMock:
    s = MagicMock()
    s.ERP_ADAPTER = adapter
    s.ERP_WEBHOOK_SECRET = secret
    return s


# ---- Tests -------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.unit
async def test_skip_on_noop_adapter() -> None:
    """Con ERP_ADAPTER='noop' el evento debe marcarse 'skipped' sin llamar al adapter."""
    from app.workers.tasks.erp_sync import _process_event

    event = _make_event(status="pending", adapter="noop")
    sm_factory = _build_sessionmaker(event)

    with (
        patch("app.db.engine.get_sessionmaker", sm_factory),
        patch("app.integrations.erp.factory.get_erp_adapter") as mock_factory,
        patch("app.core.config.settings", _make_settings(adapter="noop")),
    ):
        result = await _process_event(str(event.id), MagicMock())

    assert result["status"] == "skipped"
    assert event.status == "skipped"
    mock_factory.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_skip_on_already_processed() -> None:
    """Evento con status='delivered' → retorna sin commitear nada."""
    from app.workers.tasks.erp_sync import _process_event

    event = _make_event(status="delivered", adapter="sap")
    sm_factory = _build_sessionmaker(event)
    session = sm_factory._session

    with (
        patch("app.db.engine.get_sessionmaker", sm_factory),
        patch("app.core.config.settings", _make_settings(adapter="sap")),
    ):
        result = await _process_event(str(event.id), MagicMock())

    assert result["status"] == "delivered"
    session.commit.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_failed_after_max_retries() -> None:
    """Con attempts=4 y una excepción, el evento queda en 'failed' sin retry.

    La tarea no debe llamar a task_self.retry() porque ya alcanzó el máximo.
    """
    from app.workers.tasks.erp_sync import _process_event

    event = _make_event(status="pending", attempts=4, adapter="sap")
    sm_factory = _build_sessionmaker(event)

    broken_adapter = AsyncMock()
    broken_adapter.push_goods_receipt = AsyncMock(side_effect=ConnectionError("ERP down"))

    # Si se llamara a retry, el test fallaría con AssertionError
    task_self = MagicMock()
    task_self.retry = MagicMock(
        side_effect=AssertionError("retry no debe llamarse cuando attempts >= MAX_RETRIES")
    )

    with (
        patch("app.db.engine.get_sessionmaker", sm_factory),
        patch("app.integrations.erp.factory.get_erp_adapter", return_value=broken_adapter),
        patch("app.core.config.settings", _make_settings(adapter="sap")),
    ):
        result = await _process_event(str(event.id), task_self)

    assert result["status"] == "failed"
    assert event.status == "failed"
    assert event.attempts == 5  # 4 previos + 1 actual


@pytest.mark.asyncio
@pytest.mark.unit
async def test_hmac_computed_when_secret_set(caplog: pytest.LogCaptureFixture) -> None:
    """Con ERP_WEBHOOK_SECRET definido, la firma HMAC debe aparecer en logs DEBUG."""
    from app.workers.tasks.erp_sync import _process_event

    secret = "super-secret-key-for-tests"
    event = _make_event(status="pending", adapter="noop")
    sm_factory = _build_sessionmaker(event)

    with (
        patch("app.db.engine.get_sessionmaker", sm_factory),
        patch("app.core.config.settings", _make_settings(adapter="noop", secret=secret)),
        caplog.at_level(logging.DEBUG, logger="app.workers.tasks.erp_sync"),
    ):
        await _process_event(str(event.id), MagicMock())

    expected_sig = hmac.new(
        secret.encode(),
        json.dumps(event.payload, sort_keys=True, default=str).encode(),
        hashlib.sha256,
    ).hexdigest()

    hmac_logged = any(
        expected_sig in record.message
        for record in caplog.records
        if record.levelno == logging.DEBUG
    )
    assert hmac_logged, (
        f"HMAC sha256={expected_sig} no encontrado en logs DEBUG. "
        f"Registros: {[r.message for r in caplog.records]}"
    )
