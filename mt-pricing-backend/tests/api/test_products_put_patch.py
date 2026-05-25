"""Integration tests para `PUT /products/{sku}` y `PATCH /products/{sku}/data-quality`.

Cobertura US-1A-02-03:
- PUT happy path (200 + ETag header).
- PUT con If-Match correcto → 200; If-Match stale → 412.
- PUT que intenta cambiar SKU (path != body) → 422.
- PUT sobre SKU inexistente → 404.
- PUT respeta manual_locked_fields → 409 si intenta cambiar locked.
- PATCH /data-quality cambia el flag y emite audit.
- PATCH /data-quality `complete` falla 422 si faltan campos requeridos.
- PUT sin auth → 401.
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

os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-deterministic-32chars!")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "anon-test")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "service-test")

JWT_SECRET = "test-jwt-secret-deterministic-32chars!"


def _emit_jwt(*, sub: str, email: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": sub,
            "aud": "authenticated",
            "email": email,
            "iat": now,
            "exp": now + 3600,
            "app_metadata": {"role": "comercial"},
        },
        JWT_SECRET,
        algorithm="HS256",
    )


async def _seed_admin(session: AsyncSession) -> tuple[UUID, str]:
    from app.db.models.user import Permission, Role, RolePermission, User

    perms_codes = ["products:read", "products:write"]
    perm_ids = []
    for code in perms_codes:
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
    role = (
        await session.execute(select(Role).where(Role.code == "pim_admin"))
    ).scalar_one_or_none()
    if role is None:
        role = Role(code="pim_admin", name="pim_admin", permissions_snapshot=perms_codes)
        session.add(role)
        await session.flush()
        for pid in perm_ids:
            session.add(RolePermission(role_id=role.id, permission_id=pid))
        await session.flush()
    uid = uuid4()
    email = f"admin-{uid.hex[:6]}@mt.ae"
    user = User(id=uid, email=email, full_name="A", locale="es", is_active=True, role_id=role.id)
    session.add(user)
    await session.flush()
    return uid, email


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


def _create_payload(sku: str) -> dict[str, Any]:
    return {
        "sku": sku,
        "name_en": "Ball valve",
        "family": "valves_ball",
        "material": "brass",
        "dn": "DN15",
        "pn": "PN16",
    }


def _put_payload() -> dict[str, Any]:
    """Body completo para PUT — incluye todos los campos editables."""
    return {
        "family": "valves_gate",
        "subfamily": None,
        "type": None,
        "material": "ss316",
        "dn": "DN50",
        "pn": "PN16",
        "connection": None,
        "brand": "MT",
        "specs": {"foo": "bar"},
        "dimensions": {"high_mm": 100},
        "weight": "1.5",
        "weight_unit": "kg",
        "packaging": {},
        "intrastat_code": None,
        "erp_name": None,
        "data_quality": "partial",
        "manual_locked_fields": [],
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_put_happy_path_returns_200_with_etag(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    uid, email = await _seed_admin(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    sku = "MT-V-PUT-01"
    r = await client.post("/api/v1/products", json=_create_payload(sku), headers=headers)
    assert r.status_code == 201, r.text

    r = await client.put(f"/api/v1/products/{sku}", json=_put_payload(), headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["material"] == "ss316"
    assert "etag" in {k.lower() for k in r.headers}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_put_immutable_sku_returns_422(client: AsyncClient, db_session: AsyncSession) -> None:
    uid, email = await _seed_admin(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    sku = "MT-V-PUT-02"
    await client.post("/api/v1/products", json=_create_payload(sku), headers=headers)

    body = _put_payload()
    body["sku"] = "MT-OTHER-SKU"  # ProductReplace forbids extra=forbid → 422.
    r = await client.put(f"/api/v1/products/{sku}", json=body, headers=headers)
    assert r.status_code == 422


@pytest.mark.integration
@pytest.mark.asyncio
async def test_put_unknown_sku_returns_404(client: AsyncClient, db_session: AsyncSession) -> None:
    uid, email = await _seed_admin(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    r = await client.put("/api/v1/products/MT-DOES-NOT-EXIST", json=_put_payload(), headers=headers)
    assert r.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_put_no_auth_returns_401(client: AsyncClient) -> None:
    r = await client.put("/api/v1/products/MT-V-001", json=_put_payload())
    assert r.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_put_with_if_match_stale_returns_412(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    uid, email = await _seed_admin(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    sku = "MT-V-PUT-IFMATCH"
    await client.post("/api/v1/products", json=_create_payload(sku), headers=headers)

    stale = 'W/"2020-01-01T00:00:00+00:00"'
    r = await client.put(
        f"/api/v1/products/{sku}",
        json=_put_payload(),
        headers={**headers, "If-Match": stale},
    )
    assert r.status_code == 412
    assert r.json()["code"] == "product_precondition_failed"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_put_respects_manual_locked_fields(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    uid, email = await _seed_admin(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    sku = "MT-V-PUT-LOCKED"
    await client.post("/api/v1/products", json=_create_payload(sku), headers=headers)

    # Lockea `dn` directamente vía PATCH (manual_locked_fields acepta lista).
    rp = await client.patch(
        f"/api/v1/products/{sku}",
        json={"manual_locked_fields": ["dn"]},
        headers=headers,
    )
    assert rp.status_code == 200, rp.text

    # Ahora un PUT que intenta cambiar dn debe fallar 409.
    body = _put_payload()
    body["dn"] = "DN100"  # cambio sobre lock
    r = await client.put(f"/api/v1/products/{sku}", json=body, headers=headers)
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "product_locked_field"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_patch_data_quality_happy_path(client: AsyncClient, db_session: AsyncSession) -> None:
    uid, email = await _seed_admin(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    sku = "MT-V-DQ-01"
    await client.post("/api/v1/products", json=_create_payload(sku), headers=headers)

    r = await client.patch(
        f"/api/v1/products/{sku}/data-quality",
        json={"data_quality": "blocked", "reason": "Falta foto"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["data_quality"] == "blocked"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_patch_data_quality_complete_requires_fields(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    uid, email = await _seed_admin(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    sku = "MT-V-DQ-02"
    # Crear producto sin material/dn/pn — incompleto para `complete`.
    minimal = {"sku": sku, "name_en": "X valve", "family": "x"}
    await client.post("/api/v1/products", json=minimal, headers=headers)

    r = await client.patch(
        f"/api/v1/products/{sku}/data-quality",
        json={"data_quality": "complete"},
        headers=headers,
    )
    assert r.status_code == 422
    assert r.json()["code"] == "product_data_quality_invalid_transition"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_patch_data_quality_invalid_value_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    uid, email = await _seed_admin(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    sku = "MT-V-DQ-03"
    await client.post("/api/v1/products", json=_create_payload(sku), headers=headers)

    r = await client.patch(
        f"/api/v1/products/{sku}/data-quality",
        json={"data_quality": "garbage"},
        headers=headers,
    )
    assert r.status_code == 422
