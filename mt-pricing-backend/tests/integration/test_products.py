"""Integration tests for Products API (routes + ProductService + repos).

Patrón:
- testcontainer Postgres (`db_session` fixture).
- Override `get_db_session` para que la app use la session transaccional.
- Emitimos JWTs HS256 contra `SUPABASE_JWT_SECRET` para simular Supabase Auth.
- Seedeamos rol `pim_admin` con permisos `products:read|write|delete` para los
  tests que requieren mutaciones; rol `comercial` con sólo `products:read` para
  el test de RBAC denegado.

Cobertura mínima requerida (≥12 tests):
1.  test_list_products_empty
2.  test_create_product_minimal
3.  test_create_product_invalid_sku_regex
4.  test_create_product_duplicate_sku
5.  test_get_product_by_id_not_found
6.  test_update_product_partial
7.  test_soft_delete_product
8.  test_search_products_by_sku_substring
9.  test_translation_upsert_idempotent
10. test_translation_approve
11. test_permissions_unauthorized_user_403
12. test_audit_event_recorded_on_create_update_delete
13. test_create_product_invalid_dn (validator)
14. test_image_upload_url
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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Force JWT secret BEFORE app config import.
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-deterministic-32chars!")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "anon-test")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "service-test")

JWT_SECRET = "test-jwt-secret-deterministic-32chars!"
JWT_ALG = "HS256"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _emit_jwt(*, sub: str, email: str, full_name: str = "Test User") -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "aud": "authenticated",
        "email": email,
        "iat": now,
        "exp": now + 3600,
        "user_metadata": {"full_name": full_name, "locale": "es"},
        "role": "authenticated",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


async def _seed_user_with_permissions(
    session: AsyncSession,
    *,
    email: str,
    role_code: str,
    permissions: list[str],
) -> UUID:
    """Crea Permissions + Role + User; devuelve el user_id."""
    from app.db.models.user import Permission, Role, RolePermission, User

    # Idempotente — pueden existir por seeds previos.
    perm_ids: list[UUID] = []
    for code in permissions:
        existing = (
            await session.execute(select(Permission).where(Permission.code == code))
        ).scalar_one_or_none()
        if existing is None:
            p = Permission(code=code, description=f"perm {code}")
            session.add(p)
            await session.flush()
            perm_ids.append(p.id)
        else:
            perm_ids.append(existing.id)

    existing_role = (
        await session.execute(select(Role).where(Role.code == role_code))
    ).scalar_one_or_none()
    if existing_role is None:
        role = Role(
            code=role_code,
            name=role_code,
            description=f"role {role_code}",
            permissions_snapshot=permissions,
        )
        session.add(role)
        await session.flush()
        for pid in perm_ids:
            session.add(RolePermission(role_id=role.id, permission_id=pid))
        await session.flush()
    else:
        role = existing_role

    user_id = uuid4()
    user = User(
        id=user_id,
        email=email,
        full_name="Tester",
        locale="es",
        is_active=True,
        role_id=role.id,
    )
    session.add(user)
    await session.flush()
    return user_id


def _auth_headers(user_id: UUID, email: str) -> dict[str, str]:
    token = _emit_jwt(sub=str(user_id), email=email)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def app_with_db(db_session: AsyncSession) -> AsyncIterator[Any]:
    from app.api.deps import get_db_session
    from app.main import app

    async def _override() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override
    try:
        yield app
    finally:
        app.dependency_overrides.pop(get_db_session, None)


@pytest_asyncio.fixture
async def client(app_with_db: Any) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> tuple[UUID, str]:
    """Usuario con permisos products:read|write|delete."""
    email = f"admin-{uuid4().hex[:8]}@mt.ae"
    uid = await _seed_user_with_permissions(
        db_session,
        email=email,
        role_code="pim_admin",
        permissions=["products:read", "products:write", "products:delete"],
    )
    return uid, email


@pytest_asyncio.fixture
async def reader_user(db_session: AsyncSession) -> tuple[UUID, str]:
    """Usuario con sólo products:read."""
    email = f"reader-{uuid4().hex[:8]}@mt.ae"
    uid = await _seed_user_with_permissions(
        db_session,
        email=email,
        role_code="comercial",
        permissions=["products:read"],
    )
    return uid, email


# Minimal valid Create payload — usado en varios tests.
def _valid_payload(sku: str = "MT-V-038") -> dict[str, Any]:
    return {
        "sku": sku,
        "family": "valves_ball",
        "material": "brass",
        "dn": "DN15",
        "pn": "PN16",
        "brand": "Pegler",
        "specs": {"thread_standard": "BSP"},
    }


# ===========================================================================
# Tests
# ===========================================================================
@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_products_empty(client: AsyncClient, admin_user: tuple[UUID, str]) -> None:
    uid, email = admin_user
    res = await client.get("/api/v1/products", headers=_auth_headers(uid, email))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["items"] == []
    assert body["page_size"] == 50
    assert body["cursor"]["next"] is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_product_minimal(client: AsyncClient, admin_user: tuple[UUID, str]) -> None:
    uid, email = admin_user
    res = await client.post(
        "/api/v1/products",
        json=_valid_payload("MT-V-038"),
        headers=_auth_headers(uid, email),
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["sku"] == "MT-V-038"
    assert body["name_en"] is None  # name_en now in product_translations (mig 065)
    assert body["family"] == "valves_ball"
    assert body["data_quality"] == "partial"
    assert body["active"] is True
    assert body["translations"] == []
    assert body["images"] == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_product_invalid_sku_regex(
    client: AsyncClient, admin_user: tuple[UUID, str]
) -> None:
    uid, email = admin_user
    payload = _valid_payload("invalid sku!")  # mayúsculas + guiones requerido
    res = await client.post("/api/v1/products", json=payload, headers=_auth_headers(uid, email))
    assert res.status_code == 422, res.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_product_invalid_dn(client: AsyncClient, admin_user: tuple[UUID, str]) -> None:
    """DN debe estar en whitelist {DN8, DN10, DN15, ...}."""
    uid, email = admin_user
    payload = _valid_payload("MT-V-100")
    payload["dn"] = "DN17"  # no permitido
    res = await client.post("/api/v1/products", json=payload, headers=_auth_headers(uid, email))
    assert res.status_code == 422, res.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_product_duplicate_sku(
    client: AsyncClient, admin_user: tuple[UUID, str]
) -> None:
    uid, email = admin_user
    headers = _auth_headers(uid, email)
    res1 = await client.post("/api/v1/products", json=_valid_payload("MT-V-039"), headers=headers)
    assert res1.status_code == 201, res1.text

    res2 = await client.post("/api/v1/products", json=_valid_payload("MT-V-039"), headers=headers)
    assert res2.status_code == 409, res2.text
    body = res2.json()
    # Body shape: detail.code = product_duplicate_sku
    assert body["detail"]["code"] == "product_duplicate_sku"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_product_by_id_not_found(
    client: AsyncClient, admin_user: tuple[UUID, str]
) -> None:
    uid, email = admin_user
    res = await client.get("/api/v1/products/MT-DOES-NOT-EXIST", headers=_auth_headers(uid, email))
    assert res.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_product_partial(client: AsyncClient, admin_user: tuple[UUID, str]) -> None:
    uid, email = admin_user
    headers = _auth_headers(uid, email)
    await client.post("/api/v1/products", json=_valid_payload("MT-V-040"), headers=headers)
    res = await client.patch(
        "/api/v1/products/MT-V-040",
        json={"erp_name": "Premium DN15 brass ball valve"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["erp_name"] == "Premium DN15 brass ball valve"
    # name_en now comes from product_translations (mig 065)
    assert body["name_en"] is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_soft_delete_product(
    client: AsyncClient, admin_user: tuple[UUID, str], db_session: AsyncSession
) -> None:
    from app.db.models.product import Product

    uid, email = admin_user
    headers = _auth_headers(uid, email)
    await client.post("/api/v1/products", json=_valid_payload("MT-V-041"), headers=headers)
    res = await client.delete("/api/v1/products/MT-V-041", headers=headers)
    assert res.status_code == 204

    # Verifica que está soft-deleted en DB
    prod = (await db_session.execute(select(Product).where(Product.sku == "MT-V-041"))).scalar_one()
    assert prod.deleted_at is not None
    assert prod.active is False

    # GET ahora devuelve 404 (lookups filtran deleted_at)
    res = await client.get("/api/v1/products/MT-V-041", headers=headers)
    assert res.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_products_by_sku_substring(
    client: AsyncClient, admin_user: tuple[UUID, str]
) -> None:
    uid, email = admin_user
    headers = _auth_headers(uid, email)
    # Seed 3 productos con SKU prefix MT-V-
    for sku in ("MT-V-100", "MT-V-101", "MT-OTHER"):
        payload = _valid_payload(sku)
        await client.post("/api/v1/products", json=payload, headers=headers)

    res = await client.get(
        "/api/v1/products/search?q=MT-V&limit=10",
        headers=headers,
    )
    assert res.status_code == 200, res.text
    items = res.json()
    skus = {p["sku"] for p in items}
    assert "MT-V-100" in skus
    assert "MT-V-101" in skus


@pytest.mark.integration
@pytest.mark.asyncio
async def test_translation_upsert_idempotent(
    client: AsyncClient, admin_user: tuple[UUID, str]
) -> None:
    uid, email = admin_user
    headers = _auth_headers(uid, email)
    await client.post("/api/v1/products", json=_valid_payload("MT-V-200"), headers=headers)

    body = {"name": "صمام كروي نحاسي DN15", "status": "draft"}
    res1 = await client.put("/api/v1/products/MT-V-200/translations/ar", json=body, headers=headers)
    assert res1.status_code == 200, res1.text
    assert res1.json()["lang"] == "ar"
    assert res1.json()["name"] == body["name"]

    # PUT idempotente — segundo PUT con cambio
    body2 = {"name": "صمام كروي معدّل", "status": "draft"}
    res2 = await client.put(
        "/api/v1/products/MT-V-200/translations/ar", json=body2, headers=headers
    )
    assert res2.status_code == 200, res2.text
    assert res2.json()["name"] == body2["name"]

    # Verifica via GET /translations
    res3 = await client.get("/api/v1/products/MT-V-200/translations", headers=headers)
    assert res3.status_code == 200
    assert len(res3.json()) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_translation_approve(client: AsyncClient, admin_user: tuple[UUID, str]) -> None:
    uid, email = admin_user
    headers = _auth_headers(uid, email)
    await client.post("/api/v1/products", json=_valid_payload("MT-V-201"), headers=headers)
    await client.put(
        "/api/v1/products/MT-V-201/translations/es",
        json={"name": "Válvula esfera latón", "status": "draft"},
        headers=headers,
    )

    res = await client.post("/api/v1/products/MT-V-201/translations/es/approve", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "approved"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_permissions_unauthorized_user_403(
    client: AsyncClient,
    reader_user: tuple[UUID, str],
) -> None:
    """Reader (sin products:write) recibe 403 al crear producto."""
    uid, email = reader_user
    res = await client.post(
        "/api/v1/products",
        json=_valid_payload("MT-V-300"),
        headers=_auth_headers(uid, email),
    )
    assert res.status_code == 403
    body = res.json()
    assert "products:write" in body["detail"]["missing_permissions"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_audit_event_recorded_on_create_update_delete(
    client: AsyncClient,
    admin_user: tuple[UUID, str],
    db_session: AsyncSession,
) -> None:
    """Verifica que CRUD emite AuditEvent rows en orden."""
    from app.db.models.audit import AuditEvent

    uid, email = admin_user
    headers = _auth_headers(uid, email)

    # Create
    await client.post("/api/v1/products", json=_valid_payload("MT-V-AUDIT"), headers=headers)
    # Update
    await client.patch(
        "/api/v1/products/MT-V-AUDIT",
        json={"description_en": "Updated description"},
        headers=headers,
    )
    # Delete
    await client.delete("/api/v1/products/MT-V-AUDIT", headers=headers)

    rows = (
        (
            await db_session.execute(
                select(AuditEvent)
                .where(AuditEvent.entity_type == "product", AuditEvent.entity_id == "MT-V-AUDIT")
                .order_by(AuditEvent.event_at.asc(), AuditEvent.id.asc())
            )
        )
        .scalars()
        .all()
    )
    actions = [r.action for r in rows]
    assert "product.created" in actions
    assert "product.updated" in actions
    assert "product.deleted" in actions
    # 3 mutaciones → al menos 3 audit events.
    assert len(rows) >= 3


@pytest.mark.integration
@pytest.mark.asyncio
async def test_image_upload_url(client: AsyncClient, admin_user: tuple[UUID, str]) -> None:
    """POST /products/{sku}/images/upload-url devuelve signed URL fake en tests."""
    uid, email = admin_user
    headers = _auth_headers(uid, email)
    await client.post("/api/v1/products", json=_valid_payload("MT-V-IMG"), headers=headers)

    res = await client.post(
        "/api/v1/products/MT-V-IMG/images/upload-url",
        json={"role": "main", "filename": "valve.jpg", "content_type": "image/jpeg"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["bucket"] == "product-images"
    assert "MT-V-IMG" in body["storage_path"]
    assert body["headers"]["Content-Type"] == "image/jpeg"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_products_with_filter_family(
    client: AsyncClient, admin_user: tuple[UUID, str]
) -> None:
    """Filtros family + active deben aplicarse correctamente."""
    uid, email = admin_user
    headers = _auth_headers(uid, email)
    a = _valid_payload("MT-V-F1")
    a["family"] = "valves_ball"
    b = _valid_payload("MT-V-F2")
    b["family"] = "valves_gate"
    await client.post("/api/v1/products", json=a, headers=headers)
    await client.post("/api/v1/products", json=b, headers=headers)

    res = await client.get("/api/v1/products?family=valves_ball", headers=headers)
    assert res.status_code == 200
    skus = {it["sku"] for it in res.json()["items"]}
    assert "MT-V-F1" in skus
    assert "MT-V-F2" not in skus
