"""Integration tests para cursor pagination de `GET /products`.

Complementa `tests/integration/test_products.py` con cobertura específica del
contrato cursor base64-JSON añadido en US-1A-02-02-S1.

Cobertura:
- 3 productos + limit=2 → primera página devuelve cursor decodificable a `{"sku": ...}`.
- Segunda página con cursor decoded devuelve los restantes y next_cursor=None.
- Cursor corrupto → 400 con `code=invalid_cursor`.
- Cursor JSON sin clave `sku` → 400.
- Limit > 200 → 422.
"""

from __future__ import annotations

import base64
import json
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
    role = (await session.execute(select(Role).where(Role.code == "pim_admin"))).scalar_one_or_none()
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


def _payload(sku: str) -> dict[str, Any]:
    return {
        "sku": sku,
        "name_en": f"Product {sku}",
        "family": "valves_ball",
        "material": "brass",
        "dn": "DN15",
        "pn": "PN16",
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pagination_cursor_two_pages(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    uid, email = await _seed_admin(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    # Seed 3 productos ordenados por sku ASC.
    for sku in ("MT-V-001", "MT-V-002", "MT-V-003"):
        r = await client.post("/api/v1/products", json=_payload(sku), headers=headers)
        assert r.status_code == 201, r.text

    # Página 1 — limit=2.
    r1 = await client.get("/api/v1/products?limit=2", headers=headers)
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    assert len(body1["items"]) == 2
    next_cursor = body1["cursor"]["next"]
    assert next_cursor is not None

    # Verifica que el cursor es base64url-JSON con {"sku": ...}.
    padding = "=" * (-len(next_cursor) % 4)
    raw = base64.urlsafe_b64decode(next_cursor + padding)
    decoded = json.loads(raw)
    assert "sku" in decoded
    assert decoded["sku"] == body1["items"][-1]["sku"]

    # Página 2 — pasamos el cursor.
    r2 = await client.get(
        f"/api/v1/products?limit=2&cursor={next_cursor}", headers=headers
    )
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert len(body2["items"]) == 1
    assert body2["cursor"]["next"] is None
    # No solapamiento entre páginas.
    skus_p1 = {it["sku"] for it in body1["items"]}
    skus_p2 = {it["sku"] for it in body2["items"]}
    assert skus_p1.isdisjoint(skus_p2)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_cursor_returns_400(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    uid, email = await _seed_admin(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    r = await client.get(
        "/api/v1/products?cursor=!!not-base64!!", headers=headers
    )
    assert r.status_code == 400
    body = r.json()
    assert body["detail"]["code"] == "invalid_cursor"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cursor_missing_sku_key_returns_400(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    uid, email = await _seed_admin(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    bad_cursor = base64.urlsafe_b64encode(b'{"foo":"bar"}').rstrip(b"=").decode()
    r = await client.get(
        f"/api/v1/products?cursor={bad_cursor}", headers=headers
    )
    assert r.status_code == 400


@pytest.mark.integration
@pytest.mark.asyncio
async def test_limit_exceeds_max_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    uid, email = await _seed_admin(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}
    r = await client.get("/api/v1/products?limit=500", headers=headers)
    assert r.status_code == 422
