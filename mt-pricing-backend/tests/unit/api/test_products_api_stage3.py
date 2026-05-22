"""Stage 3 (Wave 11) — Products API: nuevos query params + ProductDetail enriched.

Patrón: FastAPI ad-hoc con el router products montado, override de
``get_product_service`` con un AsyncMock; sin DB real.

Cobertura:
1.  GET /products?division=hidrosanitario → 200 (sin auth → 401, comprobado en
    validation curl). Aquí, con auth fake, el route debe forwardear el filtro al
    service y devolver Pagination vacío.
2.  GET /products?series_id=<uuid> → 200 con kwarg propagado.
3.  GET /products?material_id=<uuid> → 200 con kwarg propagado.
4.  GET /products?tier_code=platinum → 200 con kwarg propagado.
5.  GET /products?division=foo&series_id=<uuid>&tier_code=gold → combinación.
6.  GET /products/{sku} (detail) — payload incluye llaves Stage 3
    ``series``, ``material``, ``display_pair``, ``division_codes``.
7.  Listado: ``ProductResponse`` incluye ``division_codes`` (default []).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db_session
from app.api.routes.products import get_product_service
from app.api.routes.products import router as products_router
from app.services.products.product_service import ProductService

pytestmark = pytest.mark.unit

NOW = datetime.now(tz=UTC)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _FakeRole:
    def __init__(self, perms: list[str]) -> None:
        self.code = "tester"
        self.permissions_snapshot = perms


class _FakeUser:
    def __init__(self, perms: list[str] | None = None) -> None:
        self.id = uuid4()
        self.email = "tester@mt.ae"
        self.is_active = True
        self.role = _FakeRole(perms or ["products:read", "products:write"])


def _fake_product_orm(
    sku: str = "MT-V-001",
    *,
    series_id: UUID | None = None,
    material_id: UUID | None = None,
    display_pair_sku: str | None = None,
) -> Any:
    """Construye un objeto compatible con ProductResponse.model_validate."""
    p = MagicMock()
    p.sku = sku
    p.internal_id = uuid4()
    # Fase B (mig 065): name_en/description_en/marketing_copy_en ahora son
    # hybrid_property en el ORM; el response acepta None si no hay translation EN.
    p.name_en = f"Product {sku}"
    p.description_en = None
    p.marketing_copy_en = None
    p.family = "valve"
    p.family_id = None
    p.subfamily = None
    p.type = None
    p.material = None
    p.dn = "15"
    p.pn = "16"
    p.connection = None
    p.brand = "mt"
    p.specs = {}
    p.dimensions = {}
    p.weight = None
    p.weight_unit = None
    p.packaging = {}
    p.intrastat_code = None
    p.erp_name = None
    p.data_quality = "partial"
    p.manual_locked_fields = []
    # Fase B (mig 066): active es computed_field en ProductResponse derivado
    # de lifecycle_status='active'. Aquí lo dejamos en True para mocks (no se
    # pasa al schema).
    p.active = True
    p.created_at = NOW
    p.updated_at = NOW
    p.deleted_at = None
    p.lifecycle_status = "active"
    p.revision = None
    p.series = None  # TEXT escalar Wave 2
    p.parent_sku = None
    p.is_parent = False
    p.is_variant = False
    p.dn_real = None
    p.size = None
    p.temp_min_c = None
    p.temp_max_c = None
    p.pressure_max_bar = None
    p.manufacturing_method = None
    p.actuator = None
    p.kv = None
    p.kv2 = None
    p.torque_nm = None
    p.iso5211_interface = None
    p.tags = []
    p.video_url = None
    p.external_url = None
    p.model_id = None
    p.gtin = None
    # Stage 3
    p.series_id = series_id
    p.material_id = material_id
    p.display_pair_sku = display_pair_sku
    p.product_divisions = []
    p.translations = []
    p.assets = []
    # Pydantic ProductResponse opcionales que MagicMock auto-genera; explícitos.
    p.translation_status_es = None
    p.translation_status_ar = None
    p.primary_image_url = None
    p.division_codes = []
    return p


# ---------------------------------------------------------------------------
# App builder
# ---------------------------------------------------------------------------
def _build_app(user: _FakeUser, product_svc: ProductService) -> FastAPI:
    app = FastAPI()
    app.include_router(products_router, prefix="/api/v1")

    fake_session = MagicMock()

    # session.execute → AsyncMock devolviendo Result vacío con .all() y
    # .scalar_one_or_none() apropiados.
    async def _execute(*_a: Any, **_k: Any) -> Any:
        result = MagicMock()
        result.all.return_value = []
        result.scalar_one_or_none.return_value = None
        return result

    fake_session.execute = AsyncMock(side_effect=_execute)
    product_svc.session = fake_session

    async def _override_db():  # pragma: no cover
        yield fake_session

    async def _override_user():
        return user

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_product_service] = lambda: product_svc

    for route in products_router.routes:
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        for dep in dependant.dependencies:
            call = dep.call
            if call is not None and getattr(call, "__name__", "") == "_check":

                async def _allow(_call=call):
                    return user

                app.dependency_overrides[call] = _allow

    return app


async def _client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


def _mock_svc() -> ProductService:
    svc = MagicMock(spec=ProductService)
    svc.list_products = AsyncMock(return_value=([], None, None))
    return svc


# ---------------------------------------------------------------------------
# Tests — list with new Stage 3 query params
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_products_stage3_division_filter_passes_to_service() -> None:
    user = _FakeUser()
    svc = _mock_svc()

    app = _build_app(user, svc)
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/products?division=hidrosanitario")
    assert resp.status_code == 200
    svc.list_products.assert_awaited_once()
    call_kwargs = svc.list_products.await_args.kwargs
    assert call_kwargs["division_code"] == "hidrosanitario"


@pytest.mark.asyncio
async def test_list_products_stage3_series_id_filter() -> None:
    user = _FakeUser()
    svc = _mock_svc()
    sid = uuid4()

    app = _build_app(user, svc)
    async with await _client(app) as ac:
        resp = await ac.get(f"/api/v1/products?series_id={sid}")
    assert resp.status_code == 200
    # Route accepts UUID OR slug, so kwarg is forwarded as str (registry resolves slug→UUID).
    assert svc.list_products.await_args.kwargs["series_id"] == str(sid)


@pytest.mark.asyncio
async def test_list_products_stage3_material_id_filter() -> None:
    user = _FakeUser()
    svc = _mock_svc()
    mid = uuid4()

    app = _build_app(user, svc)
    async with await _client(app) as ac:
        resp = await ac.get(f"/api/v1/products?material_id={mid}")
    assert resp.status_code == 200
    assert svc.list_products.await_args.kwargs["material_id"] == str(mid)


@pytest.mark.asyncio
async def test_list_products_stage3_tier_code_filter() -> None:
    user = _FakeUser()
    svc = _mock_svc()

    app = _build_app(user, svc)
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/products?tier_code=platinum")
    assert resp.status_code == 200
    assert svc.list_products.await_args.kwargs["tier_code"] == "platinum"


@pytest.mark.asyncio
async def test_list_products_stage3_combined_filters() -> None:
    user = _FakeUser()
    svc = _mock_svc()
    sid = uuid4()
    mid = uuid4()

    app = _build_app(user, svc)
    async with await _client(app) as ac:
        resp = await ac.get(
            f"/api/v1/products?division=industrial&series_id={sid}&material_id={mid}&tier_code=gold"
        )
    assert resp.status_code == 200
    kwargs = svc.list_products.await_args.kwargs
    assert kwargs["division_code"] == "industrial"
    # UUID or slug both accepted; forwarded as str (see series_id_filter test).
    assert kwargs["series_id"] == str(sid)
    assert kwargs["material_id"] == str(mid)
    assert kwargs["tier_code"] == "gold"


@pytest.mark.asyncio
async def test_list_products_stage3_response_includes_division_codes_default_empty() -> None:
    user = _FakeUser()
    svc = _mock_svc()
    # Devuelve un producto fake; el route adjunta division_codes=[] por default.
    svc.list_products = AsyncMock(return_value=([_fake_product_orm("MT-V-001")], None, 1))

    app = _build_app(user, svc)
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/products?include_total=true")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"][0]["division_codes"] == []
    # También Stage 3 fields por defecto.
    assert body["items"][0]["series_id"] is None
    assert body["items"][0]["material_id"] is None
    assert body["items"][0]["display_pair_sku"] is None


# ---------------------------------------------------------------------------
# Tests — detail response shape (Stage 3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_product_detail_stage3_keys_present() -> None:
    user = _FakeUser()
    svc = _mock_svc()
    prod = _fake_product_orm("MT-V-001")
    svc.get_product_by_id = AsyncMock(return_value=prod)

    app = _build_app(user, svc)
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/products/MT-V-001")
    assert resp.status_code == 200
    body = resp.json()
    # Stage 3 keys deben existir en el payload.
    for key in ("series", "material", "display_pair", "division_codes"):
        assert key in body, f"missing key {key!r} in ProductDetail"
    # Defaults — sin series_id/material_id/display_pair_sku → None.
    assert body["series"] is None
    assert body["material"] is None
    assert body["display_pair"] is None
    assert body["division_codes"] == []


# ---------------------------------------------------------------------------
# Tests — query param signature: no 422 (matches validation contract)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_products_stage3_invalid_series_id_too_long_returns_422() -> None:
    """series_id excediendo max_length=64 debe devolver 422 (validación FastAPI), no 500.

    Nota: el route acepta UUID O slug del registry como str(max_length=64) post-mig 050+.
    Por eso ya no valida formato UUID en el query param; un slug arbitrario pasa.
    Solo se rechaza si excede longitud (sanity bound).
    """
    user = _FakeUser()
    svc = _mock_svc()

    app = _build_app(user, svc)
    async with await _client(app) as ac:
        resp = await ac.get(f"/api/v1/products?series_id={'x' * 65}")
    assert resp.status_code == 422
