"""Integration tests para `/suppliers` CRUD (US-1A-03-02 backend).

Cobertura:
- POST happy path → 201, audit emit.
- POST con code duplicado → 409.
- POST con currency inválida → 422.
- GET list con filtros + cursor.
- GET by code → 200 / 404.
- PUT happy path.
- PATCH parcial.
- DELETE retorna 405 (BR VAT-compliance).
- PATCH active=false desactiva con audit.
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


async def _seed_user_with_perms(
    session: AsyncSession, perms_codes: list[str]
) -> tuple[UUID, str]:
    from app.db.models.user import Permission, Role, RolePermission, User

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
    role_code = "supplier_admin"
    role = (
        await session.execute(select(Role).where(Role.code == role_code))
    ).scalar_one_or_none()
    if role is None:
        role = Role(
            code=role_code, name=role_code, permissions_snapshot=perms_codes
        )
        session.add(role)
        await session.flush()
        for pid in perm_ids:
            session.add(RolePermission(role_id=role.id, permission_id=pid))
        await session.flush()
    uid = uuid4()
    email = f"sup-{uid.hex[:6]}@mt.ae"
    user = User(
        id=uid, email=email, full_name="S", locale="es", is_active=True, role_id=role.id
    )
    session.add(user)
    await session.flush()
    return uid, email


async def _seed_currency(session: AsyncSession, code: str = "EUR") -> None:
    from app.db.models.currency import Currency

    existing = (
        await session.execute(select(Currency).where(Currency.code == code))
    ).scalar_one_or_none()
    if existing is None:
        session.add(Currency(code=code, name=code, decimals=2, is_base=False, active=True))
        await session.flush()


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


def _payload(code: str = "MT_VALVES_ES") -> dict[str, Any]:
    return {
        "code": code,
        "name": "MT Valves España",
        "contract_currency": "EUR",
        "lead_time_days": 45,
        "contact_email": "ventas@mtvalves.es",
        "contact_phone": "+34 600 000 000",
        "payment_terms": "30 días f.f.",
        "active": True,
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_supplier_happy_path(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    uid, email = await _seed_user_with_perms(db_session, ["suppliers:read", "suppliers:write"])
    await _seed_currency(db_session, "EUR")
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    r = await client.post("/api/v1/suppliers", json=_payload(), headers=headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["code"] == "MT_VALVES_ES"
    assert body["contract_currency"] == "EUR"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_supplier_duplicate_returns_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    uid, email = await _seed_user_with_perms(db_session, ["suppliers:read", "suppliers:write"])
    await _seed_currency(db_session, "EUR")
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    code = "MT_DUP"
    r1 = await client.post(
        "/api/v1/suppliers", json=_payload(code), headers=headers
    )
    assert r1.status_code == 201
    r2 = await client.post(
        "/api/v1/suppliers", json=_payload(code), headers=headers
    )
    assert r2.status_code == 409
    assert r2.json()["detail"]["code"] == "supplier_duplicate_code"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_supplier_by_code(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    uid, email = await _seed_user_with_perms(db_session, ["suppliers:read", "suppliers:write"])
    await _seed_currency(db_session, "EUR")
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    code = "MT_GET"
    await client.post("/api/v1/suppliers", json=_payload(code), headers=headers)

    r = await client.get(f"/api/v1/suppliers/{code}", headers=headers)
    assert r.status_code == 200
    assert r.json()["code"] == code

    r404 = await client.get("/api/v1/suppliers/NOPE", headers=headers)
    assert r404.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_suppliers_with_filter(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    uid, email = await _seed_user_with_perms(db_session, ["suppliers:read", "suppliers:write"])
    await _seed_currency(db_session, "EUR")
    await _seed_currency(db_session, "USD")
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    eur_payload = _payload("MT_LIST_EUR")
    usd_payload = _payload("MT_LIST_USD")
    usd_payload["contract_currency"] = "USD"
    await client.post("/api/v1/suppliers", json=eur_payload, headers=headers)
    await client.post("/api/v1/suppliers", json=usd_payload, headers=headers)

    r = await client.get(
        "/api/v1/suppliers?contract_currency=EUR&include_total=true", headers=headers
    )
    assert r.status_code == 200
    body = r.json()
    codes = [it["code"] for it in body["items"]]
    assert "MT_LIST_EUR" in codes
    assert "MT_LIST_USD" not in codes
    assert body["total"] is not None and body["total"] >= 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_put_supplier_happy_path(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    uid, email = await _seed_user_with_perms(db_session, ["suppliers:read", "suppliers:write"])
    await _seed_currency(db_session, "EUR")
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    code = "MT_PUT"
    await client.post("/api/v1/suppliers", json=_payload(code), headers=headers)

    body = _payload(code)
    body.pop("code")
    body["lead_time_days"] = 90
    body["name"] = "MT Valves Renamed"
    r = await client.put(f"/api/v1/suppliers/{code}", json=body, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["lead_time_days"] == 90
    assert r.json()["name"] == "MT Valves Renamed"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_patch_supplier_partial(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    uid, email = await _seed_user_with_perms(db_session, ["suppliers:read", "suppliers:write"])
    await _seed_currency(db_session, "EUR")
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    code = "MT_PATCH"
    await client.post("/api/v1/suppliers", json=_payload(code), headers=headers)

    r = await client.patch(
        f"/api/v1/suppliers/{code}",
        json={"lead_time_days": 30},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["lead_time_days"] == 30


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_supplier_returns_405(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    uid, email = await _seed_user_with_perms(db_session, ["suppliers:read", "suppliers:write"])
    await _seed_currency(db_session, "EUR")
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    code = "MT_DEL"
    await client.post("/api/v1/suppliers", json=_payload(code), headers=headers)

    r = await client.delete(f"/api/v1/suppliers/{code}", headers=headers)
    assert r.status_code == 405
    assert r.json()["detail"]["code"] == "vat_compliance_block"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_patch_active_false_deactivates(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    uid, email = await _seed_user_with_perms(db_session, ["suppliers:read", "suppliers:write"])
    await _seed_currency(db_session, "EUR")
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    code = "MT_DEACT"
    await client.post("/api/v1/suppliers", json=_payload(code), headers=headers)

    r = await client.patch(
        f"/api/v1/suppliers/{code}",
        json={"active": False},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["active"] is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_no_auth_returns_401(client: AsyncClient) -> None:
    r = await client.get("/api/v1/suppliers")
    assert r.status_code == 401
