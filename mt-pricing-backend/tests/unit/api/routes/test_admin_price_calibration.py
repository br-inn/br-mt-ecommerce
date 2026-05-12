"""Unit tests del router `app.api.routes.admin_price_calibration` (US-F15-02-04).

Estrategia:
- FastAPI ad-hoc con el router montado en /api/v1 (sin tocar app/main.py).
- Se overridean get_db_session y get_current_user.
- La sesión se reemplaza por un AsyncMock que devuelve filas sintéticas.
- El Celery task se mockea con unittest.mock.patch.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db_session
from app.api.routes.admin_price_calibration import router as price_cal_router

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _FakeRole:
    def __init__(self, perms: list[str]) -> None:
        self.code = "tester"
        self.permissions_snapshot = perms


class _FakeUser:
    def __init__(self, perms: list[str] | None = None) -> None:
        self.id: UUID = uuid4()
        self.email = "tester@mt.ae"
        self.is_active = True
        self.role = _FakeRole(perms or ["calibrator:train"])


def _make_range_row(
    *,
    category_id: str = "valve_family",
    min_p10: Decimal = Decimal("15.00"),
    max_p90: Decimal = Decimal("850.00"),
    currency: str = "AED",
) -> MagicMock:
    row = MagicMock()
    row.id = uuid4()
    row.category_id = category_id
    row.expected_min_p10 = min_p10
    row.expected_max_p90 = max_p90
    row.currency = currency
    row.updated_at = datetime.now(tz=UTC)
    return row


def _make_scalars_result(rows: list[Any]) -> MagicMock:
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = rows
    result = MagicMock()
    result.scalars.return_value = scalars_mock
    return result


def _make_scalar_one_result(value: Any) -> MagicMock:
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def _make_scalar_one_or_none_result(value: Any) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


# ---------------------------------------------------------------------------
# App builder
# ---------------------------------------------------------------------------
def _build_app(
    fake_session: AsyncMock,
    user: _FakeUser | None = None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(price_cal_router, prefix="/api/v1")

    the_user = user or _FakeUser()

    async def _override_db():
        yield fake_session

    async def _override_user():
        return the_user

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    # Override all require_permissions closures (named _check)
    for route in price_cal_router.routes:
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        for dep in dependant.dependencies:
            call = dep.call
            if call is not None and getattr(call, "__name__", "") == "_check":

                async def _allow(_call=call):  # noqa: ARG001
                    return the_user

                app.dependency_overrides[call] = _allow

    return app


async def _client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
async def test_list_returns_empty_when_no_ranges() -> None:
    """GET /admin/price-calibration → [] cuando no hay rangos."""
    session = AsyncMock()
    # Primera llamada: COUNT(*) → 0
    # Segunda llamada: SELECT rangos → []
    session.execute.side_effect = [
        _make_scalar_one_result(0),
        _make_scalars_result([]),
    ]

    app = _build_app(session)
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/admin/price-calibration")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == 1


async def test_list_returns_existing_ranges() -> None:
    """GET /admin/price-calibration → lista con rangos existentes."""
    row1 = _make_range_row(category_id="valve_family", min_p10=Decimal("15.00"), max_p90=Decimal("850.00"))
    row2 = _make_range_row(category_id="fitting_family", min_p10=Decimal("2.50"), max_p90=Decimal("320.00"))

    session = AsyncMock()
    session.execute.side_effect = [
        _make_scalar_one_result(2),
        _make_scalars_result([row1, row2]),
    ]

    app = _build_app(session)
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/admin/price-calibration")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    assert body["items"][0]["category_id"] == "valve_family"
    assert body["items"][0]["expected_min_p10"] == "15.00"
    assert body["items"][0]["expected_max_p90"] == "850.00"
    assert body["items"][0]["currency"] == "AED"


async def test_import_csv_validates_negative_min() -> None:
    """POST /admin/price-calibration/import-csv con expected_min_p10 < 0 → HTTP 422."""
    csv_content = (
        "category_id,expected_min_p10,expected_max_p90,currency\n"
        "valve_family,-5.00,850.00,AED\n"
    ).encode("utf-8")

    session = AsyncMock()
    app = _build_app(session)
    async with await _client(app) as ac:
        resp = await ac.post(
            "/api/v1/admin/price-calibration/import-csv",
            files={"file": ("ranges.csv", io.BytesIO(csv_content), "text/csv")},
        )

    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert "errors" in body["detail"]
    assert len(body["detail"]["errors"]) >= 1
    # Verificar que el error menciona el campo correcto
    assert any("expected_min_p10" in e for e in body["detail"]["errors"])


async def test_import_csv_validates_min_greater_than_max() -> None:
    """POST /admin/price-calibration/import-csv con min >= max → HTTP 422."""
    csv_content = (
        "category_id,expected_min_p10,expected_max_p90,currency\n"
        "valve_family,900.00,100.00,AED\n"
    ).encode("utf-8")

    session = _make_session_with_begin([])
    app = _build_app(session)
    async with await _client(app) as ac:
        resp = await ac.post(
            "/api/v1/admin/price-calibration/import-csv",
            files={"file": ("ranges.csv", io.BytesIO(csv_content), "text/csv")},
        )

    assert resp.status_code == 422, resp.text


def _make_session_with_begin(
    execute_side_effects: list[Any],
) -> AsyncMock:
    """Construye un AsyncMock de sesión con begin() como async context manager."""
    session = AsyncMock()
    session.execute.side_effect = execute_side_effects
    session.add = MagicMock()

    # begin() debe ser un método que retorne un async context manager (no una coroutine)
    begin_ctx = MagicMock()
    begin_ctx.__aenter__ = AsyncMock(return_value=None)
    begin_ctx.__aexit__ = AsyncMock(return_value=False)
    session.begin = MagicMock(return_value=begin_ctx)

    return session


async def test_import_csv_upserts_valid_rows() -> None:
    """POST /admin/price-calibration/import-csv con CSV válido → inserted: 2, updated: 0."""
    csv_content = (
        "category_id,expected_min_p10,expected_max_p90,currency\n"
        "valve_family,15.00,850.00,AED\n"
        "fitting_family,2.50,320.00,AED\n"
    ).encode("utf-8")

    session = _make_session_with_begin([
        _make_scalar_one_or_none_result(None),  # valve_family → no existe
        _make_scalar_one_or_none_result(None),  # fitting_family → no existe
    ])

    app = _build_app(session)
    async with await _client(app) as ac:
        resp = await ac.post(
            "/api/v1/admin/price-calibration/import-csv",
            files={"file": ("ranges.csv", io.BytesIO(csv_content), "text/csv")},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["inserted"] == 2
    assert body["updated"] == 0
    assert body["errors"] == []


async def test_import_csv_counts_updates_for_existing_rows() -> None:
    """POST /admin/price-calibration/import-csv con fila existente → updated: 1."""
    csv_content = (
        "category_id,expected_min_p10,expected_max_p90,currency\n"
        "valve_family,20.00,900.00,AED\n"
    ).encode("utf-8")

    existing_row = _make_range_row(
        category_id="valve_family",
        min_p10=Decimal("15.00"),
        max_p90=Decimal("850.00"),
    )

    session = _make_session_with_begin([
        _make_scalar_one_or_none_result(existing_row),  # valve_family → existe
    ])

    app = _build_app(session)
    async with await _client(app) as ac:
        resp = await ac.post(
            "/api/v1/admin/price-calibration/import-csv",
            files={"file": ("ranges.csv", io.BytesIO(csv_content), "text/csv")},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["inserted"] == 0
    assert body["updated"] == 1
    # Verificar que el row se actualizó
    assert existing_row.expected_min_p10 == Decimal("20.00")
    assert existing_row.expected_max_p90 == Decimal("900.00")


async def test_recalibrate_dispatches_task() -> None:
    """POST /admin/price-calibration/recalibrate → llama task.delay() y retorna task_id."""
    fake_task_id = str(uuid4())
    fake_async_result = MagicMock()
    fake_async_result.id = fake_task_id

    session = AsyncMock()
    app = _build_app(session)

    with patch(
        "app.api.routes.admin_price_calibration.recalibrate_price_ranges"
        if False  # el import es diferido dentro del endpoint
        else "app.workers.tasks.price_sanity.recalibrate_price_ranges",
    ) as mock_task, patch(
        "app.api.routes.admin_price_calibration.recalibrate_price_ranges",
        create=True,
    ):
        pass  # parche no aplica aquí — usamos el approach directo abajo

    # Parchamos la importación dentro del endpoint (import diferido)
    with patch(
        "app.workers.tasks.price_sanity.recalibrate_price_ranges"
    ) as mock_task:
        mock_task.delay.return_value = fake_async_result

        # Inyectamos el mock en el namespace del módulo del router
        with patch.dict(
            "app.api.routes.admin_price_calibration.__dict__",
            {},
            clear=False,
        ):
            # El endpoint importa la task de forma diferida dentro de la función.
            # Parchamos a nivel de módulo origen.
            with patch(
                "app.api.routes.admin_price_calibration.recalibrate_price_ranges",
                mock_task,
                create=True,
            ):
                async with await _client(app) as ac:
                    resp = await ac.post("/api/v1/admin/price-calibration/recalibrate")

    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "queued"
    # task_id es una string no vacía
    assert isinstance(body["task_id"], str)
    assert len(body["task_id"]) > 0


async def test_recalibrate_dispatches_task_via_module_patch() -> None:
    """POST /admin/price-calibration/recalibrate — verifica que delay() se llame."""
    fake_task_id = str(uuid4())
    fake_async_result = MagicMock()
    fake_async_result.id = fake_task_id

    session = AsyncMock()
    app = _build_app(session)

    # Parcheamos en el módulo de origen (price_sanity) antes de que el endpoint
    # haga su import diferido.
    with patch(
        "app.workers.tasks.price_sanity.recalibrate_price_ranges"
    ) as mock_task:
        mock_task.delay.return_value = fake_async_result

        async with await _client(app) as ac:
            resp = await ac.post("/api/v1/admin/price-calibration/recalibrate")

    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "queued"
    assert body["task_id"] == fake_task_id
    mock_task.delay.assert_called_once()


async def test_import_csv_rejects_invalid_currency() -> None:
    """POST /admin/price-calibration/import-csv con currency no permitida → HTTP 422."""
    csv_content = (
        "category_id,expected_min_p10,expected_max_p90,currency\n"
        "valve_family,15.00,850.00,GBP\n"
    ).encode("utf-8")

    session = _make_session_with_begin([])
    app = _build_app(session)
    async with await _client(app) as ac:
        resp = await ac.post(
            "/api/v1/admin/price-calibration/import-csv",
            files={"file": ("ranges.csv", io.BytesIO(csv_content), "text/csv")},
        )

    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert any("currency" in e for e in body["detail"]["errors"])
