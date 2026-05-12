"""Unit tests del router `app.api.routes.internal_cdc` (US-F15-01-03).

Estrategia:
- FastAPI ad-hoc con el router montado bajo `/api/v1`.
- Patcheamos `sync_product_to_kg.delay` para no arrancar Celery real.
- Cubrimos: 202 sin secret configurado, 401 con secret incorrecto,
  202 con secret correcto, y que .delay() se llama con los args correctos.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes.internal_cdc import router as internal_cdc_router

pytestmark = pytest.mark.unit


def _build_app() -> FastAPI:
    """FastAPI mínima con el router CDC montado."""
    app = FastAPI()
    app.include_router(internal_cdc_router, prefix="/api/v1")
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cdc_product_202_no_secret_configured() -> None:
    """Sin INTERNAL_CDC_SECRET configurado, acepta cualquier request → 202."""
    app = _build_app()

    with patch("app.core.config.settings") as mock_settings:
        mock_settings.INTERNAL_CDC_SECRET = ""  # vacío = dev mode

        mock_task = MagicMock()
        mock_task.delay = MagicMock()

        with patch(
            "app.api.routes.internal_cdc.sync_product_to_kg", mock_task
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/v1/internal/cdc/product",
                    json={
                        "table": "products",
                        "operation": "INSERT",
                        "record_id": "abc-123",
                    },
                )

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "queued"
    assert data["record_id"] == "abc-123"
    assert data["operation"] == "INSERT"


@pytest.mark.asyncio
async def test_cdc_product_401_wrong_secret() -> None:
    """Header X-Internal-Secret incorrecto → 401."""
    app = _build_app()

    with patch("app.api.routes.internal_cdc.settings") as mock_settings:
        mock_settings.INTERNAL_CDC_SECRET = "correct-secret"

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/internal/cdc/product",
                json={
                    "table": "products",
                    "operation": "INSERT",
                    "record_id": "abc-123",
                },
                headers={"X-Internal-Secret": "wrong-secret"},
            )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_cdc_product_202_correct_secret() -> None:
    """Header X-Internal-Secret correcto → 202 y .delay() invocado."""
    app = _build_app()

    with patch("app.api.routes.internal_cdc.settings") as mock_settings:
        mock_settings.INTERNAL_CDC_SECRET = "correct-secret"

        mock_task = MagicMock()
        mock_task.delay = MagicMock()

        with patch(
            "app.api.routes.internal_cdc.sync_product_to_kg", mock_task
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/v1/internal/cdc/product",
                    json={
                        "table": "products",
                        "operation": "UPDATE",
                        "record_id": "prod-999",
                    },
                    headers={"X-Internal-Secret": "correct-secret"},
                )

    assert resp.status_code == 202
    mock_task.delay.assert_called_once_with(
        product_id="prod-999", operation="update"
    )


@pytest.mark.asyncio
async def test_cdc_product_delete_operation() -> None:
    """operation=DELETE se pasa en lowercase al task."""
    app = _build_app()

    with patch("app.api.routes.internal_cdc.settings") as mock_settings:
        mock_settings.INTERNAL_CDC_SECRET = ""

        mock_task = MagicMock()
        mock_task.delay = MagicMock()

        with patch(
            "app.api.routes.internal_cdc.sync_product_to_kg", mock_task
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/v1/internal/cdc/product",
                    json={
                        "table": "products",
                        "operation": "DELETE",
                        "record_id": "prod-del-001",
                    },
                )

    assert resp.status_code == 202
    mock_task.delay.assert_called_once_with(
        product_id="prod-del-001", operation="delete"
    )
