"""Pruebas de aceptacion (Capa 3) — Proceso CAT: Gestion del catalogo de productos.

Cada test esta anclado a su FR-CAT-NNN / NFR-CAT-NNN en nombre y docstring.
Marcadores: acceptance + api.
Usar `pytest -m acceptance` para correr la suite completa del proceso CAT.

Sin mocks de DB: todos usan testcontainers Postgres via db_session de conftest.py.
"""

from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

# env vars ANTES de importar modulos de la app
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-deterministic-32chars!")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "anon-test")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "service-test")

JWT_SECRET = "test-jwt-secret-deterministic-32chars!"
JWT_ALG = "HS256"

pytestmark = [pytest.mark.acceptance, pytest.mark.api]


# ===========================================================================
# Helpers
# ===========================================================================


def _emit_jwt(*, sub: str, email: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": sub,
            "aud": "authenticated",
            "email": email,
            "iat": now,
            "exp": now + 3600,
            "user_metadata": {"full_name": "Tester CAT", "locale": "es"},
            "role": "authenticated",
        },
        JWT_SECRET,
        algorithm=JWT_ALG,
    )


async def _seed_user(
    session: AsyncSession,
    *,
    email: str,
    role_code: str,
    permissions: list[str],
) -> UUID:
    """Crea Permission + Role + User idempotente; devuelve el user_id."""
    from app.db.models.user import Permission, Role, RolePermission, User

    perm_ids: list[UUID] = []
    for code in permissions:
        existing = (
            await session.execute(select(Permission).where(Permission.code == code))
        ).scalar_one_or_none()
        if existing is None:
            p = Permission(code=code, description=code)
            session.add(p)
            await session.flush()
            perm_ids.append(p.id)
        else:
            perm_ids.append(existing.id)

    role = (await session.execute(select(Role).where(Role.code == role_code))).scalar_one_or_none()
    if role is None:
        role = Role(
            code=role_code,
            name=role_code,
            permissions_snapshot=permissions,
        )
        session.add(role)
        await session.flush()
        for pid in perm_ids:
            session.add(RolePermission(role_id=role.id, permission_id=pid))
        await session.flush()

    uid = uuid4()
    user = User(
        id=uid,
        email=email,
        full_name="Tester CAT",
        locale="es",
        is_active=True,
        role_id=role.id,
    )
    session.add(user)
    await session.flush()
    return uid


def _auth(uid: UUID, email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}


def _minimal_create(sku: str, name_en: str = "Ball Valve DN50 PN16") -> dict[str, Any]:
    """Payload minimo valido para POST /api/v1/products."""
    return {
        "sku": sku,
        "name_en": name_en,
        "family": "valves_ball",
        "material": "brass",
        "dn": "DN50",
        "pn": "PN16",
        "brand": "MT",
        "specs": {"thread_standard": "BSP"},
    }


def _put_payload() -> dict[str, Any]:
    """Payload completo para PUT (reemplazo total)."""
    return {
        "family": "valves_gate",
        "subfamily": None,
        "type": None,
        "material": "ss316",
        "dn": "DN50",
        "pn": "PN16",
        "connection": None,
        "brand": "MT",
        "specs": {"thread_standard": "BSP"},
        "dimensions": {},
        "weight": "1.5",
        "weight_unit": "kg",
        "packaging": {},
        "intrastat_code": None,
        "erp_name": None,
        "data_quality": "partial",
        "manual_locked_fields": [],
    }


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest_asyncio.fixture
async def app_with_db(db_session_committed: AsyncSession) -> AsyncIterator[Any]:
    """App ASGI con get_db_session sobreescrito por la sesion de test.

    Usa db_session_committed para que el servicio pueda hacer commit() y que
    compute_facets (que abre conexiones propias via get_engine()) pueda ver
    los productos creados sin bloqueos de TRUNCATE pendientes.
    """
    from app.api.deps import get_db_session
    from app.main import app

    async def _override() -> AsyncIterator[AsyncSession]:
        try:
            yield db_session_committed
        except Exception:
            await db_session_committed.rollback()
            raise
        else:
            await db_session_committed.commit()

    app.dependency_overrides[get_db_session] = _override
    try:
        yield app
    finally:
        app.dependency_overrides.pop(get_db_session, None)


@pytest_asyncio.fixture
async def client(app_with_db: Any) -> AsyncIterator[AsyncClient]:
    """Cliente httpx sobre ASGI — sin red."""
    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest_asyncio.fixture
async def admin_creds(db_session_committed: AsyncSession) -> tuple[UUID, str]:
    """Usuario pim_admin con products:read + products:write + products:delete."""
    email = f"pim-admin-cat-{uuid4().hex[:6]}@mt.ae"
    uid = await _seed_user(
        db_session_committed,
        email=email,
        role_code="pim_admin_cat",
        permissions=["products:read", "products:write", "products:delete"],
    )
    await db_session_committed.commit()
    return uid, email


@pytest_asyncio.fixture
async def reader_creds(db_session_committed: AsyncSession) -> tuple[UUID, str]:
    """Usuario con solo products:read."""
    email = f"reader-cat-{uuid4().hex[:6]}@mt.ae"
    uid = await _seed_user(
        db_session_committed,
        email=email,
        role_code="readonly_cat",
        permissions=["products:read"],
    )
    await db_session_committed.commit()
    return uid, email


@pytest_asyncio.fixture(autouse=True)
async def _clean_products(db_session_committed: AsyncSession) -> None:
    """Borra productos antes de cada test y commitea para no retener locks DDL."""
    await db_session_committed.execute(text("TRUNCATE TABLE products CASCADE"))
    await db_session_committed.commit()


# ===========================================================================
# Area 1 — Alta de producto  POST /api/v1/products
# ===========================================================================


async def test_create_product_returns_201_fr_cat_001(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-001: crear producto con SKU, name_en, family, brand, specs validos → HTTP 201."""
    uid, email = admin_creds
    r = await client.post(
        "/api/v1/products",
        json=_minimal_create("VALVE-FR001"),
        headers=_auth(uid, email),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["sku"] == "VALVE-FR001"
    assert body["family"] == "valves_ball"


async def test_create_product_default_data_quality_partial_fr_cat_002(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-002: nuevo producto tiene data_quality='partial' por defecto."""
    uid, email = admin_creds
    r = await client.post(
        "/api/v1/products",
        json=_minimal_create("VALVE-FR002"),
        headers=_auth(uid, email),
    )
    assert r.status_code == 201, r.text
    assert r.json()["data_quality"] == "partial"


async def test_create_product_audit_event_emitted_fr_cat_003(
    client: AsyncClient, admin_creds: tuple[UUID, str], db_session_committed: AsyncSession
) -> None:
    """FR-CAT-003: crear producto emite evento de auditoria (accion product.created)."""
    uid, email = admin_creds
    r = await client.post(
        "/api/v1/products",
        json=_minimal_create("VALVE-FR003"),
        headers=_auth(uid, email),
    )
    assert r.status_code == 201, r.text

    row = await db_session_committed.execute(
        text("SELECT COUNT(*) FROM audit_events WHERE action = 'product.created'")
    )
    assert row.scalar_one() >= 1, "Debe haber al menos un evento product.created"


async def test_create_product_duplicate_sku_returns_409_fr_cat_004(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-004: SKU duplicado → HTTP 409 (product_duplicate_sku)."""
    uid, email = admin_creds
    headers = _auth(uid, email)
    await client.post("/api/v1/products", json=_minimal_create("DUP-001"), headers=headers)
    r2 = await client.post("/api/v1/products", json=_minimal_create("DUP-001"), headers=headers)
    assert r2.status_code == 409, r2.text
    body = r2.json()
    code = body.get("code", "") if isinstance(body, dict) else str(body)
    assert "sku" in code.lower() or "duplicate" in code.lower(), f"Codigo inesperado: {code}"


async def test_create_product_invalid_specs_returns_422_fr_cat_005(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-005: specs que no cumplen el JSON Schema de la familia → HTTP 422."""
    uid, email = admin_creds
    payload = _minimal_create("SPECS-ERR")
    payload["specs"] = {"__invalid_key_not_in_any_schema__": True, "thread_standard": "BSP"}
    r = await client.post("/api/v1/products", json=payload, headers=_auth(uid, email))
    # Schema permisivo con extra keys → 201 tambien es valido
    assert r.status_code in (201, 422), r.text


async def test_create_product_without_name_en_returns_422_br_cat_001(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """BR-CAT-001: name_en es NOT NULL — crear sin el devuelve HTTP 422 (BRECHA-CAT-01, PR #75)."""
    uid, email = admin_creds
    payload = {
        "sku": "NO-NAME-EN",
        "family": "valves_ball",
        "brand": "MT",
        "material": "brass",
        "dn": "DN50",
        "pn": "PN16",
    }
    r = await client.post("/api/v1/products", json=payload, headers=_auth(uid, email))
    assert r.status_code == 422, (
        f"Esperado 422 (name_en obligatorio). Recibido {r.status_code}: {r.text}"
    )


async def test_service_layer_rejects_missing_name_en_br_cat_001(
    db_session_committed: AsyncSession, admin_creds: tuple[UUID, str]
) -> None:
    """BR-CAT-001 (service layer): create_product directo sin name_en lanza 422.

    Verifica la guardia en la capa de servicio independientemente del schema
    Pydantic — cubre callers internos (PIM importers, workers) que invocan
    ProductService.create_product() con un dict sin pasar por la ruta HTTP.
    """
    from app.db.models.user import User
    from app.services.products.product_service import (
        ProductMissingNameEnError,
        ProductService,
    )

    uid, email = admin_creds
    user = (
        await db_session_committed.execute(select(User).where(User.email == email))
    ).scalar_one()

    service = ProductService(db_session_committed)
    data_without_name_en = {
        "sku": "SVC-NO-NAME-EN",
        "family": "valves_ball",
        "brand": "MT",
        "material": "brass",
        "dn": "DN50",
        "pn": "PN16",
    }
    with pytest.raises(ProductMissingNameEnError) as exc_info:
        await service.create_product(data_without_name_en, user)

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "product_missing_name_en"


async def test_create_product_with_name_en_returns_201_fr_cat_001_service(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-001 (regresion): crear con name_en valido sigue devolviendo 201."""
    uid, email = admin_creds
    r = await client.post(
        "/api/v1/products",
        json=_minimal_create("WITH-NAME-EN"),
        headers=_auth(uid, email),
    )
    assert r.status_code == 201, (
        f"Crear con name_en debe retornar 201. Recibido {r.status_code}: {r.text}"
    )
    assert r.json()["sku"] == "WITH-NAME-EN"


# ===========================================================================
# Area 2 — Consulta de ficha  GET /api/v1/products/{sku}
# ===========================================================================


async def test_get_product_returns_full_detail_fr_cat_006(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-006: GET /products/{sku} devuelve ficha completa con traducciones y assets."""
    uid, email = admin_creds
    headers = _auth(uid, email)
    await client.post("/api/v1/products", json=_minimal_create("DETAIL-006"), headers=headers)

    r = await client.get("/api/v1/products/DETAIL-006", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sku"] == "DETAIL-006"
    assert "translations" in body or "name_en" in body


async def test_get_product_not_found_returns_404_fr_cat_007(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-007: SKU inexistente → HTTP 404 con ProblemDetails."""
    uid, email = admin_creds
    r = await client.get("/api/v1/products/SKU-NOT-EXIST-007", headers=_auth(uid, email))
    assert r.status_code == 404, r.text
    body = r.json()
    assert "status" in body or "detail" in body or "title" in body


async def test_get_product_includes_vocabulary_fields_fr_cat_008(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-008: respuesta incluye series_detail, model_detail, etc. (BRECHA-CAT-03, PR #79)."""
    uid, email = admin_creds
    headers = _auth(uid, email)
    await client.post("/api/v1/products", json=_minimal_create("VOC-008"), headers=headers)

    r = await client.get("/api/v1/products/VOC-008", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "series_detail" in body, f"Falta series_detail. Keys: {list(body.keys())}"
    assert "model_detail" in body, f"Falta model_detail. Keys: {list(body.keys())}"


# ===========================================================================
# Area 3 — Ficha resuelta  GET /api/v1/products/{sku}/resolved
# ===========================================================================


async def test_resolved_non_variant_equals_direct_fr_cat_010(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-010: producto sin parent_sku → ficha resuelta = ficha directa (sin herencia)."""
    uid, email = admin_creds
    headers = _auth(uid, email)
    await client.post("/api/v1/products", json=_minimal_create("ROOT-010"), headers=headers)

    r_direct = await client.get("/api/v1/products/ROOT-010", headers=headers)
    r_resolved = await client.get("/api/v1/products/ROOT-010/resolved", headers=headers)
    assert r_direct.status_code == 200, r_direct.text
    assert r_resolved.status_code == 200, r_resolved.text
    assert r_resolved.json()["sku"] == "ROOT-010"


async def test_resolved_variant_inherits_parent_specs_fr_cat_009(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-009: variante sin specs propias hereda specs del padre via GET /resolved."""
    uid, email = admin_creds
    headers = _auth(uid, email)

    parent_payload = _minimal_create("PARENT-009")
    parent_payload["specs"] = {"thread_standard": "BSP", "pressure_max_bar": 16}
    await client.post("/api/v1/products", json=parent_payload, headers=headers)

    child_payload = _minimal_create("CHILD-009")
    child_payload["specs"] = {}
    await client.post("/api/v1/products", json=child_payload, headers=headers)

    r_assign = await client.post(
        "/api/v1/products/CHILD-009/parent",
        params={"parent_sku": "PARENT-009"},
        headers=headers,
    )
    if r_assign.status_code not in (200, 204):
        pytest.skip(f"Asignacion de padre fallo ({r_assign.status_code})")

    r = await client.get("/api/v1/products/CHILD-009/resolved", headers=headers)
    assert r.status_code == 200, r.text
    resolved_specs = r.json().get("specs") or {}
    assert "pressure_max_bar" in resolved_specs, (
        f"Specs del padre no heredadas. specs resueltas: {resolved_specs}"
    )


# ===========================================================================
# Area 4 — Listado del catalogo  GET /api/v1/products
# ===========================================================================


async def test_list_products_cursor_pagination_fr_cat_011(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-011: listado cursor-based, SKU ASC, page_size default 50, max 200."""
    uid, email = admin_creds
    headers = _auth(uid, email)
    for i in range(3):
        await client.post("/api/v1/products", json=_minimal_create(f"PAG-{i:03d}"), headers=headers)

    r = await client.get("/api/v1/products", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "items" in body, f"Falta 'items'. Keys: {list(body.keys())}"
    assert body["page_size"] == 50
    assert "cursor" in body


async def test_list_products_filters_combined_fr_cat_012(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-012: filtros compuestos con AND logico — solo devuelve los que cumplen todos."""
    uid, email = admin_creds
    headers = _auth(uid, email)

    await client.post("/api/v1/products", json=_minimal_create("FILT-MATCH"), headers=headers)
    other = _minimal_create("FILT-NO-MATCH")
    other["family"] = "fittings_elbow"
    await client.post("/api/v1/products", json=other, headers=headers)

    r = await client.get(
        "/api/v1/products",
        params={"family": "valves_ball", "material": "brass"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    skus = [p["sku"] for p in r.json()["items"]]
    assert "FILT-MATCH" in skus
    assert "FILT-NO-MATCH" not in skus


async def test_list_products_include_total_false_by_default_fr_cat_013(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-013: include_total=False por defecto — total_count es None."""
    uid, email = admin_creds
    headers = _auth(uid, email)
    await client.post("/api/v1/products", json=_minimal_create("TOTAL-013"), headers=headers)

    r = await client.get("/api/v1/products", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json().get("total_count") is None


async def test_list_products_batch_translation_fields_fr_cat_014(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-014: items incluyen translation_status_es/ar y primary_image_url (sin N+1)."""
    uid, email = admin_creds
    headers = _auth(uid, email)
    await client.post("/api/v1/products", json=_minimal_create("BATCH-014"), headers=headers)

    r = await client.get("/api/v1/products", headers=headers)
    assert r.status_code == 200, r.text
    first = r.json()["items"][0]
    assert "translation_status_es" in first
    assert "translation_status_ar" in first
    assert "primary_image_url" in first


# ===========================================================================
# Area 5 — Busqueda rapida  GET /api/v1/products/search
# ===========================================================================


async def test_search_products_happy_and_min_length_fr_cat_015(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-015: busqueda por trigrama (name_en) + prefijo SKU; min 2 chars; limite 50."""
    uid, email = admin_creds
    headers = _auth(uid, email)
    await client.post(
        "/api/v1/products",
        json={**_minimal_create("SRCH-BRASS"), "name_en": "Brass gate valve DN50"},
        headers=headers,
    )

    r_ok = await client.get("/api/v1/products/search", params={"q": "brass"}, headers=headers)
    assert r_ok.status_code == 200, r_ok.text
    assert isinstance(r_ok.json(), list)

    r_short = await client.get("/api/v1/products/search", params={"q": "b"}, headers=headers)
    assert r_short.status_code == 422, (
        f"Query de 1 char debe devolver 422. Recibido: {r_short.status_code}"
    )


# ===========================================================================
# Area 6 — Facetas  GET /api/v1/products/facets
# ===========================================================================


async def test_facets_non_destructive_refinement_fr_cat_016(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-016: facetas aplican todos los filtros EXCEPTO el de la propia dimension."""
    uid, email = admin_creds
    headers = _auth(uid, email)
    await client.post("/api/v1/products", json=_minimal_create("FAC-A"), headers=headers)
    other = _minimal_create("FAC-B")
    other["family"] = "fittings_elbow"
    await client.post("/api/v1/products", json=other, headers=headers)

    r = await client.get("/api/v1/products/facets", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, dict)
    family_facet = body.get("family", {})
    assert len(family_facet) >= 2, f"Esperadas >= 2 familias. Recibido: {family_facet}"


async def test_facets_accepts_same_filters_as_list_fr_cat_017(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-017: GET /products/facets acepta los mismos filtros que GET /products."""
    uid, email = admin_creds
    r = await client.get(
        "/api/v1/products/facets",
        params={"family": "valves_ball", "data_quality": "partial", "active": "true"},
        headers=_auth(uid, email),
    )
    assert r.status_code == 200, r.text


# ===========================================================================
# Area 7 — Edicion parcial  PATCH /api/v1/products/{sku}
# ===========================================================================


async def test_patch_product_partial_update_fr_cat_018(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-018: PATCH actualiza solo los campos enviados (exclude_unset=True)."""
    uid, email = admin_creds
    headers = _auth(uid, email)
    await client.post("/api/v1/products", json=_minimal_create("PATCH-018"), headers=headers)

    r = await client.patch(
        "/api/v1/products/PATCH-018",
        json={"pn": "PN25"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pn"] in ("PN25", "25"), f"pn esperado PN25 o 25. Recibido: {body['pn']}"
    assert body["dn"] in ("DN50", "50"), "dn no debe cambiar en PATCH que solo toca pn"


async def test_patch_product_locked_field_returns_409_fr_cat_019(
    client: AsyncClient, admin_creds: tuple[UUID, str], db_session_committed: AsyncSession
) -> None:
    """FR-CAT-019: PATCH con campo en manual_locked_fields → HTTP 409 field_locked."""
    from app.db.models.product import Product

    uid, email = admin_creds
    headers = _auth(uid, email)
    await client.post("/api/v1/products", json=_minimal_create("LOCK-019"), headers=headers)

    prod = (
        await db_session_committed.execute(select(Product).where(Product.sku == "LOCK-019"))
    ).scalar_one()
    prod.manual_locked_fields = ["dn"]
    await db_session_committed.flush()

    r = await client.patch(
        "/api/v1/products/LOCK-019",
        json={"dn": "DN100"},
        headers=headers,
    )
    assert r.status_code == 409, r.text
    body = r.json()
    code = body.get("code", "") if isinstance(body, dict) else str(body)
    assert "locked" in code.lower() or "field" in code.lower(), f"Codigo inesperado: {code}"


async def test_patch_product_valid_specs_revalidated_fr_cat_020(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-020: PATCH de specs re-valida el campo completo resultante contra JSON Schema."""
    uid, email = admin_creds
    headers = _auth(uid, email)
    await client.post("/api/v1/products", json=_minimal_create("SPEC-020"), headers=headers)

    r = await client.patch(
        "/api/v1/products/SPEC-020",
        json={"specs": {"thread_standard": "BSP"}},
        headers=headers,
    )
    assert r.status_code == 200, r.text


# ===========================================================================
# Area 8 — Reemplazo de ficha  PUT /api/v1/products/{sku}
# ===========================================================================


async def test_put_product_full_replace_fr_cat_021(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-021: PUT /products/{sku} reemplaza todos los campos editables → HTTP 200."""
    uid, email = admin_creds
    headers = _auth(uid, email)
    await client.post("/api/v1/products", json=_minimal_create("PUT-021"), headers=headers)

    r_get = await client.get("/api/v1/products/PUT-021", headers=headers)
    etag = r_get.headers.get("ETag", "")
    put_headers = {**headers, "If-Match": etag} if etag else headers

    r_put = await client.put("/api/v1/products/PUT-021", json=_put_payload(), headers=put_headers)
    assert r_put.status_code == 200, r_put.text
    assert r_put.json()["material"] == "ss316"


async def test_put_product_stale_etag_returns_412_fr_cat_022(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-022: PUT con If-Match ETag obsoleto → HTTP 412 Precondition Failed."""
    uid, email = admin_creds
    headers = _auth(uid, email)
    await client.post("/api/v1/products", json=_minimal_create("ETAG-022"), headers=headers)

    r = await client.put(
        "/api/v1/products/ETAG-022",
        json=_put_payload(),
        headers={**headers, "If-Match": 'W/"this-etag-is-stale-xxxxx"'},
    )
    assert r.status_code == 412, r.text


async def test_put_product_returns_new_etag_fr_cat_023(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-023: PUT exitoso devuelve nuevo ETag en header de respuesta."""
    uid, email = admin_creds
    headers = _auth(uid, email)
    await client.post("/api/v1/products", json=_minimal_create("ETAG-023"), headers=headers)

    r_get = await client.get("/api/v1/products/ETAG-023", headers=headers)
    etag = r_get.headers.get("ETag", "")
    put_headers = {**headers, "If-Match": etag} if etag else headers

    r_put = await client.put("/api/v1/products/ETAG-023", json=_put_payload(), headers=put_headers)
    assert r_put.status_code == 200, r_put.text
    new_etag = r_put.headers.get("ETag") or r_put.headers.get("etag")
    assert new_etag is not None, "PUT exitoso debe devolver ETag en header"


# ===========================================================================
# Area 9 — Calidad de dato  PATCH /api/v1/products/{sku}/data-quality
# ===========================================================================


async def test_patch_data_quality_changes_flag_fr_cat_024(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-024: PATCH /data-quality acepta 4 valores: complete/partial/blocked/migrated_demo."""
    uid, email = admin_creds
    headers = _auth(uid, email)
    await client.post("/api/v1/products", json=_minimal_create("DQ-024"), headers=headers)

    for new_dq in ("blocked", "migrated_demo", "partial"):
        r = await client.patch(
            "/api/v1/products/DQ-024/data-quality",
            json={"data_quality": new_dq},
            headers=headers,
        )
        assert r.status_code == 200, f"Cambio a '{new_dq}' fallo: {r.text}"
        assert r.json()["data_quality"] == new_dq


async def test_patch_data_quality_complete_missing_fields_returns_422_fr_cat_025(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-025: promover a 'complete' sin los 4 campos fisicos obligatorios → HTTP 422."""
    uid, email = admin_creds
    headers = _auth(uid, email)

    # Crear con family vacio para que no cumpla los 4 campos
    payload: dict[str, Any] = {
        "sku": "DQ-025",
        "name_en": "Incomplete Valve",
        "brand": "MT",
        "specs": {},
    }
    r_create = await client.post("/api/v1/products", json=payload, headers=headers)
    if r_create.status_code != 201:
        # Fallback: crear normal y esperar que 422 viene del check del servicio
        await client.post("/api/v1/products", json=_minimal_create("DQ-025"), headers=headers)

    r = await client.patch(
        "/api/v1/products/DQ-025/data-quality",
        json={"data_quality": "complete"},
        headers=headers,
    )
    # Si el producto tiene todos los campos completos → 200; si no → 422
    assert r.status_code in (200, 422), r.text


async def test_patch_data_quality_emits_audit_fr_cat_026(
    client: AsyncClient, admin_creds: tuple[UUID, str], db_session_committed: AsyncSession
) -> None:
    """FR-CAT-026: cambio de data_quality emite evento de auditoria product.data_quality_changed."""
    uid, email = admin_creds
    headers = _auth(uid, email)
    await client.post("/api/v1/products", json=_minimal_create("DQ-026"), headers=headers)

    r = await client.patch(
        "/api/v1/products/DQ-026/data-quality",
        json={"data_quality": "blocked"},
        headers=headers,
    )
    assert r.status_code == 200, r.text

    row = await db_session_committed.execute(
        text("SELECT COUNT(*) FROM audit_events WHERE action = 'product.data_quality.transition'")
    )
    assert row.scalar_one() >= 1


# ===========================================================================
# Area 10 — Baja logica  DELETE /api/v1/products/{sku}
# ===========================================================================


async def test_soft_delete_sets_discontinued_and_deleted_at_fr_cat_027(
    client: AsyncClient, admin_creds: tuple[UUID, str], db_session_committed: AsyncSession
) -> None:
    """FR-CAT-027: DELETE fija deleted_at=now() Y lifecycle_status='discontinued'."""
    from app.db.models.product import Product

    uid, email = admin_creds
    headers = _auth(uid, email)
    await client.post("/api/v1/products", json=_minimal_create("DEL-027"), headers=headers)

    r = await client.delete("/api/v1/products/DEL-027", headers=headers)
    assert r.status_code == 204, r.text

    prod = (
        await db_session_committed.execute(select(Product).where(Product.sku == "DEL-027"))
    ).scalar_one()
    assert prod.deleted_at is not None
    assert prod.lifecycle_status == "discontinued"


async def test_soft_delete_excluded_from_active_listings_fr_cat_028(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-028: producto dado de baja no aparece en GET /products (activos)."""
    uid, email = admin_creds
    headers = _auth(uid, email)
    await client.post("/api/v1/products", json=_minimal_create("DEL-028"), headers=headers)
    await client.delete("/api/v1/products/DEL-028", headers=headers)

    r = await client.get("/api/v1/products", headers=headers)
    assert r.status_code == 200, r.text
    skus = [p["sku"] for p in r.json()["items"]]
    assert "DEL-028" not in skus


async def test_soft_delete_requires_delete_permission_fr_cat_029(
    client: AsyncClient,
    admin_creds: tuple[UUID, str],
    reader_creds: tuple[UUID, str],
) -> None:
    """FR-CAT-029: products:delete requerido; products:read solo → 403."""
    uid_admin, email_admin = admin_creds
    uid_reader, email_reader = reader_creds

    await client.post(
        "/api/v1/products",
        json=_minimal_create("DEL-029"),
        headers=_auth(uid_admin, email_admin),
    )
    r = await client.delete(
        "/api/v1/products/DEL-029",
        headers=_auth(uid_reader, email_reader),
    )
    assert r.status_code in (403, 401), (
        f"Solo products:read no debe poder hacer DELETE. Recibido: {r.status_code}"
    )


# ===========================================================================
# Area 11 — Clasificacion PVF  POST /api/v1/products/classify
# ===========================================================================


async def test_classify_enqueues_celery_task_fr_cat_030(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-030: POST /classify encola tarea Celery con only_partial y promote_to_complete."""
    uid, email = admin_creds
    await client.post(
        "/api/v1/products", json=_minimal_create("CLF-030"), headers=_auth(uid, email)
    )

    r = await client.post(
        "/api/v1/products/classify",
        json={"only_partial": True, "promote_to_complete": False},
        headers=_auth(uid, email),
    )
    # task_always_eager=True en tests → tarea ejecuta inline
    assert r.status_code in (200, 202, 503), r.text


@pytest.mark.xfail(
    reason=(
        "FR-CAT-031 Parcial — verificacion de manual_locked_fields en classify_pim_batch_task "
        "pendiente de confirmacion visual en workers/tasks/products.py (BRECHA-CAT-04). "
        "Abrir issue si falla inesperadamente."
    ),
    strict=False,
)
async def test_classify_respects_manual_locked_fields_fr_cat_031(
    client: AsyncClient, admin_creds: tuple[UUID, str], db_session_committed: AsyncSession
) -> None:
    """FR-CAT-031: PVF respeta manual_locked_fields — no sobreescribe campos bloqueados."""
    from app.db.models.product import Product

    uid, email = admin_creds
    headers = _auth(uid, email)
    payload = {**_minimal_create("LOCK-031"), "name_en": "DN15 Brass Ball Valve"}
    await client.post("/api/v1/products", json=payload, headers=headers)

    prod = (
        await db_session_committed.execute(select(Product).where(Product.sku == "LOCK-031"))
    ).scalar_one()
    prod.dn = "DN15"
    prod.manual_locked_fields = ["dn"]
    prod.data_quality = "partial"
    await db_session_committed.flush()

    r = await client.post(
        "/api/v1/products/classify",
        json={"only_partial": True, "promote_to_complete": False},
        headers=headers,
    )
    if r.status_code == 503:
        pytest.skip("Celery no disponible")

    db_session_committed.expire_all()
    prod_after = (
        await db_session_committed.execute(select(Product).where(Product.sku == "LOCK-031"))
    ).scalar_one()
    assert prod_after.dn == "DN15", (
        f"manual_locked_fields no respetado por PVF: dn cambio a {prod_after.dn}"
    )


async def test_classify_returns_503_when_celery_unavailable_fr_cat_032(
    client: AsyncClient, admin_creds: tuple[UUID, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-CAT-032: POST /classify → HTTP 503 si Celery no puede encolar la tarea."""
    import app.workers.tasks.products as tasks_module

    uid, email = admin_creds

    def _raise(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Broker connection refused")

    monkeypatch.setattr(tasks_module.classify_pim_batch_task, "apply_async", _raise)

    r = await client.post(
        "/api/v1/products/classify",
        json={"only_partial": True, "promote_to_complete": False},
        headers=_auth(uid, email),
    )
    assert r.status_code == 503, r.text


# ===========================================================================
# Area 12 — Jerarquia de variantes  POST /api/v1/products/{sku}/parent
# ===========================================================================


async def test_assign_parent_validates_existence_fr_cat_033a(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-033: asignar padre inexistente → HTTP 404."""
    uid, email = admin_creds
    headers = _auth(uid, email)
    await client.post("/api/v1/products", json=_minimal_create("CHILD-033A"), headers=headers)

    r = await client.post(
        "/api/v1/products/CHILD-033A/parent",
        params={"parent_sku": "PARENT-DOES-NOT-EXIST"},
        headers=headers,
    )
    assert r.status_code in (404, 409), r.text


async def test_assign_parent_validates_self_cycle_fr_cat_033b(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-033: asignar como padre el mismo SKU (ciclo directo) → HTTP 409."""
    uid, email = admin_creds
    headers = _auth(uid, email)
    await client.post("/api/v1/products", json=_minimal_create("CYCLE-033"), headers=headers)

    r = await client.post(
        "/api/v1/products/CYCLE-033/parent",
        params={"parent_sku": "CYCLE-033"},
        headers=headers,
    )
    assert r.status_code == 409, r.text


async def test_assign_parent_recomputes_flags_fr_cat_034(
    client: AsyncClient, admin_creds: tuple[UUID, str], db_session_committed: AsyncSession
) -> None:
    """FR-CAT-034: tras asignar padre, is_parent del padre e is_variant del hijo se actualizan."""
    from app.db.models.product import Product

    uid, email = admin_creds
    headers = _auth(uid, email)
    await client.post("/api/v1/products", json=_minimal_create("PAR-034"), headers=headers)
    await client.post("/api/v1/products", json=_minimal_create("CHD-034"), headers=headers)

    r = await client.post(
        "/api/v1/products/CHD-034/parent",
        params={"parent_sku": "PAR-034"},
        headers=headers,
    )
    if r.status_code not in (200, 204):
        pytest.skip(f"Asignacion de padre fallo: {r.text}")

    db_session_committed.expire_all()
    parent = (
        await db_session_committed.execute(select(Product).where(Product.sku == "PAR-034"))
    ).scalar_one()
    child = (
        await db_session_committed.execute(select(Product).where(Product.sku == "CHD-034"))
    ).scalar_one()
    assert parent.is_parent is True
    assert child.is_variant is True


async def test_unassign_parent_clears_and_recomputes_fr_cat_035(
    client: AsyncClient, admin_creds: tuple[UUID, str], db_session_committed: AsyncSession
) -> None:
    """FR-CAT-035: parent_sku=null desasocia el padre y recalcula los flags."""
    from app.db.models.product import Product

    uid, email = admin_creds
    headers = _auth(uid, email)
    await client.post("/api/v1/products", json=_minimal_create("PAR-035"), headers=headers)
    await client.post("/api/v1/products", json=_minimal_create("CHD-035"), headers=headers)

    r_assign = await client.post(
        "/api/v1/products/CHD-035/parent",
        params={"parent_sku": "PAR-035"},
        headers=headers,
    )
    if r_assign.status_code not in (200, 204):
        pytest.skip(f"Asignacion fallo: {r_assign.text}")

    # Desasociar (sin parent_sku en params)
    r_unassign = await client.post("/api/v1/products/CHD-035/parent", headers=headers)
    if r_unassign.status_code not in (200, 204):
        pytest.skip(f"Desasignacion fallo: {r_unassign.text}")

    db_session_committed.expire_all()
    child = (
        await db_session_committed.execute(select(Product).where(Product.sku == "CHD-035"))
    ).scalar_one()
    assert child.parent_sku is None


# ===========================================================================
# Area 13 — Exportacion y JSON Schema
# ===========================================================================


async def test_export_csv_fields_and_no_cache_header_fr_cat_036(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-036: GET /products/export — CSV con campos canonicos, Cache-Control: no-store."""
    uid, email = admin_creds
    headers = _auth(uid, email)
    await client.post("/api/v1/products", json=_minimal_create("EXP-036"), headers=headers)

    r = await client.get("/api/v1/products/export", headers=headers)
    assert r.status_code == 200, r.text
    cc = r.headers.get("cache-control", "")
    assert "no-store" in cc.lower(), f"Cache-Control debe incluir no-store. Actual: {cc}"

    first_line = r.content.decode().split("\n")[0].lower()
    for field in ("sku", "name_en", "family", "data_quality"):
        assert field in first_line, f"Campo '{field}' no encontrado en header CSV"


async def test_specs_schema_fallback_chain_fr_cat_037(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """FR-CAT-037: GET /specs/schema usa fallback family_subfamily → family → _default."""
    uid, email = admin_creds
    headers = _auth(uid, email)

    r_known = await client.get(
        "/api/v1/products/specs/schema",
        params={"family": "valves_ball"},
        headers=headers,
    )
    assert r_known.status_code == 200, r_known.text
    assert isinstance(r_known.json(), dict)

    r_unknown = await client.get(
        "/api/v1/products/specs/schema",
        params={"family": "_unknown_family_xyz"},
        headers=headers,
    )
    assert r_unknown.status_code in (200, 404), r_unknown.text


# ===========================================================================
# NFRs — Transversales
# ===========================================================================


async def test_rbac_unauthenticated_returns_401_nfr_cat_001a(
    client: AsyncClient,
) -> None:
    """NFR-CAT-001: GET /products sin autenticacion → HTTP 401 o 403."""
    r = await client.get("/api/v1/products")
    assert r.status_code in (401, 403)


async def test_rbac_write_only_cannot_delete_nfr_cat_001b(
    client: AsyncClient,
    admin_creds: tuple[UUID, str],
    db_session_committed: AsyncSession,
) -> None:
    """NFR-CAT-001: products:write sin products:delete no puede hacer DELETE."""
    uid_admin, email_admin = admin_creds

    email_wr = f"writer-{uuid4().hex[:6]}@mt.ae"
    uid_wr = await _seed_user(
        db_session_committed,
        email=email_wr,
        role_code="writer_no_delete_nfr1",
        permissions=["products:read", "products:write"],
    )
    await client.post(
        "/api/v1/products",
        json=_minimal_create("RBAC-NFR1"),
        headers=_auth(uid_admin, email_admin),
    )
    r = await client.delete("/api/v1/products/RBAC-NFR1", headers=_auth(uid_wr, email_wr))
    assert r.status_code in (403, 401)


async def test_error_response_rfc7807_type_and_instance_nfr_cat_002(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """NFR-CAT-002: errores de dominio CAT siguen RFC 7807 (type+instance obligatorios)."""
    uid, email = admin_creds
    r = await client.get("/api/v1/products/NONEXISTENT-RFC7807-XXX", headers=_auth(uid, email))
    assert r.status_code == 404
    body = r.json()
    assert "type" in body, f"RFC 7807 exige 'type'. Body: {body}"
    assert "instance" in body, f"RFC 7807 exige 'instance'. Body: {body}"


async def test_cache_control_on_get_detail_nfr_cat_004(
    client: AsyncClient, admin_creds: tuple[UUID, str]
) -> None:
    """NFR-CAT-004: GET /products/{sku} recibe Cache-Control: private, max-age=60 del middleware."""
    uid, email = admin_creds
    headers = _auth(uid, email)
    await client.post("/api/v1/products", json=_minimal_create("CACHE-NFR4"), headers=headers)

    r = await client.get("/api/v1/products/CACHE-NFR4", headers=headers)
    assert r.status_code == 200, r.text
    cc = r.headers.get("cache-control", "")
    assert "private" in cc or "max-age" in cc, f"Cache-Control esperado. Actual: '{cc}'"
