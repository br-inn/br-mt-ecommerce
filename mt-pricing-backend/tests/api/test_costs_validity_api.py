"""Integration tests — API de vigencia de costes (Task 7).

Cubren los endpoints de `costs` tras la migración a vigencia por rangos
(``valid_from`` / ``valid_to``, mig ``20260603_148``):

- ``POST /costs`` con ``valid_from`` → 201; un segundo POST con ``valid_from``
  posterior para la misma clave ENCADENA (cierra el rango previo).
- ``GET /costs/as-of`` → resuelve la fila vigente a una fecha (404 si ninguna).
- ``POST /costs/{id}/close`` → 200, fija ``valid_to``.
- ``PATCH /costs/{id}`` → 200, corrección IN-PLACE.
- ``GET /costs?valid_on=`` y ``?include_history=true`` → filtro/orden correcto.
- POST que solapa un rango existente → 409 ``cost_range_overlap``.

Patrón auth: seed user/role con ``costs:read``+``costs:write`` y JWT HS256
(igual que ``test_suppliers_crud.py``). FBA exige el breakdown completo
``{fob, freight, customs, fba_fees, payment_fees}`` (seed mig 004). Usamos
``currency_origin='AED'`` para evitar dependencia de un FX rate vigente.
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

_FBA_BASE: dict[str, Any] = {
    "fob": 100,
    "freight": 10,
    "customs": 5,
    "fba_fees": 8,
    "payment_fees": 3,
}


def _bk(*, fob: int | None = None) -> dict[str, Any]:
    out = dict(_FBA_BASE)
    if fob is not None:
        out["fob"] = fob
    return out


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


async def _seed_user_with_perms(session: AsyncSession, perms_codes: list[str]) -> tuple[UUID, str]:
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
    role_code = "cost_admin"
    role = (await session.execute(select(Role).where(Role.code == role_code))).scalar_one_or_none()
    if role is None:
        role = Role(code=role_code, name=role_code, permissions_snapshot=perms_codes)
        session.add(role)
        await session.flush()
        for pid in perm_ids:
            session.add(RolePermission(role_id=role.id, permission_id=pid))
        await session.flush()
    uid = uuid4()
    email = f"cost-{uid.hex[:6]}@mt.ae"
    user = User(id=uid, email=email, full_name="C", locale="es", is_active=True, role_id=role.id)
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


async def _auth(db_session: AsyncSession) -> dict[str, str]:
    uid, email = await _seed_user_with_perms(db_session, ["costs:read", "costs:write"])
    return {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}


def _create_payload(sku: str, valid_from: str, *, fob: int = 100) -> dict[str, Any]:
    return {
        "sku": sku,
        "scheme_code": "FBA",
        "currency_origin": "AED",
        "valid_from": valid_from,
        "breakdown": _bk(fob=fob),
    }


# ---------------------------------------------------------------------------
# POST /costs — create + auto-chaining
# ---------------------------------------------------------------------------
@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_cost_creates_and_chains(
    client: AsyncClient, db_session: AsyncSession, make_product
) -> None:
    await make_product("_API_CHAIN")
    headers = await _auth(db_session)

    r1 = await client.post(
        "/api/v1/costs", json=_create_payload("_API_CHAIN", "2026-01-01", fob=100), headers=headers
    )
    assert r1.status_code == 201, r1.text
    first_id = r1.json()["cost"]["id"]
    assert r1.json()["cost"]["valid_from"] == "2026-01-01"
    assert r1.json()["cost"]["valid_to"] is None

    r2 = await client.post(
        "/api/v1/costs", json=_create_payload("_API_CHAIN", "2026-06-01", fob=120), headers=headers
    )
    assert r2.status_code == 201, r2.text
    assert r2.json()["cost"]["valid_to"] is None

    # First row's range must now be closed (valid_to = 2026-05-31).
    r_first = await client.get(f"/api/v1/costs/{first_id}", headers=headers)
    assert r_first.status_code == 200
    assert r_first.json()["valid_to"] == "2026-05-31"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_overlapping_range_returns_409(
    client: AsyncClient, db_session: AsyncSession, make_product
) -> None:
    await make_product("_API_OVL")
    headers = await _auth(db_session)

    # Open-ended range from 2026-01-01.
    r1 = await client.post(
        "/api/v1/costs", json=_create_payload("_API_OVL", "2026-01-01"), headers=headers
    )
    assert r1.status_code == 201, r1.text
    cost_id = r1.json()["cost"]["id"]
    # Close it explicitly at 2026-12-31 so there is a bounded range to overlap.
    rc = await client.post(
        f"/api/v1/costs/{cost_id}/close", json={"valid_to": "2026-12-31"}, headers=headers
    )
    assert rc.status_code == 200, rc.text

    # New range starting inside the closed one → overlap → 409.
    r2 = await client.post(
        "/api/v1/costs", json=_create_payload("_API_OVL", "2026-06-01"), headers=headers
    )
    assert r2.status_code == 409, r2.text
    assert r2.json()["detail"]["code"] == "cost_range_overlap"


# ---------------------------------------------------------------------------
# GET /costs/as-of
# ---------------------------------------------------------------------------
@pytest.mark.integration
@pytest.mark.asyncio
async def test_as_of_returns_right_row(
    client: AsyncClient, db_session: AsyncSession, make_product
) -> None:
    await make_product("_API_ASOF")
    headers = await _auth(db_session)

    await client.post(
        "/api/v1/costs", json=_create_payload("_API_ASOF", "2026-01-01", fob=100), headers=headers
    )
    await client.post(
        "/api/v1/costs", json=_create_payload("_API_ASOF", "2026-06-01", fob=120), headers=headers
    )

    r_past = await client.get(
        "/api/v1/costs/as-of?sku=_API_ASOF&scheme_code=FBA&date=2026-03-01", headers=headers
    )
    assert r_past.status_code == 200, r_past.text
    assert r_past.json()["valid_from"] == "2026-01-01"
    assert r_past.json()["breakdown"]["fob"] == 100

    r_now = await client.get(
        "/api/v1/costs/as-of?sku=_API_ASOF&scheme_code=FBA&date=2026-07-01", headers=headers
    )
    assert r_now.status_code == 200, r_now.text
    assert r_now.json()["valid_from"] == "2026-06-01"
    assert r_now.json()["breakdown"]["fob"] == 120


@pytest.mark.integration
@pytest.mark.asyncio
async def test_as_of_404_when_no_cost(
    client: AsyncClient, db_session: AsyncSession, make_product
) -> None:
    await make_product("_API_ASOF_NONE")
    headers = await _auth(db_session)

    await client.post(
        "/api/v1/costs", json=_create_payload("_API_ASOF_NONE", "2026-06-01"), headers=headers
    )
    r = await client.get(
        "/api/v1/costs/as-of?sku=_API_ASOF_NONE&scheme_code=FBA&date=2026-01-01", headers=headers
    )
    assert r.status_code == 404, r.text
    assert r.json()["detail"]["code"] == "cost_not_found"


# ---------------------------------------------------------------------------
# POST /costs/{id}/close
# ---------------------------------------------------------------------------
@pytest.mark.integration
@pytest.mark.asyncio
async def test_close_sets_valid_to(
    client: AsyncClient, db_session: AsyncSession, make_product
) -> None:
    await make_product("_API_CLOSE")
    headers = await _auth(db_session)

    r = await client.post(
        "/api/v1/costs", json=_create_payload("_API_CLOSE", "2026-01-01"), headers=headers
    )
    cost_id = r.json()["cost"]["id"]

    rc = await client.post(
        f"/api/v1/costs/{cost_id}/close", json={"valid_to": "2026-09-30"}, headers=headers
    )
    assert rc.status_code == 200, rc.text
    assert rc.json()["valid_to"] == "2026-09-30"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_close_404_when_not_found(client: AsyncClient, db_session: AsyncSession) -> None:
    headers = await _auth(db_session)
    rc = await client.post(
        f"/api/v1/costs/{uuid4()}/close", json={"valid_to": "2026-09-30"}, headers=headers
    )
    assert rc.status_code == 404, rc.text


# ---------------------------------------------------------------------------
# PATCH /costs/{id} — in-place correction
# ---------------------------------------------------------------------------
@pytest.mark.integration
@pytest.mark.asyncio
async def test_patch_in_place_correction(
    client: AsyncClient, db_session: AsyncSession, make_product
) -> None:
    await make_product("_API_PATCH")
    headers = await _auth(db_session)

    r = await client.post(
        "/api/v1/costs", json=_create_payload("_API_PATCH", "2026-01-01", fob=100), headers=headers
    )
    cost_id = r.json()["cost"]["id"]
    landed_before = r.json()["cost"]["scheme_landed_aed"]

    rp = await client.patch(
        f"/api/v1/costs/{cost_id}", json={"breakdown": _bk(fob=200)}, headers=headers
    )
    assert rp.status_code == 200, rp.text
    body = rp.json()
    assert body["id"] == cost_id  # same row, no new version
    assert body["breakdown"]["fob"] == 200
    assert body["valid_from"] == "2026-01-01"
    assert body["scheme_landed_aed"] != landed_before


# ---------------------------------------------------------------------------
# GET /costs — valid_on + include_history
# ---------------------------------------------------------------------------
@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_valid_on_and_history(
    client: AsyncClient, db_session: AsyncSession, make_product
) -> None:
    await make_product("_API_LIST")
    headers = await _auth(db_session)

    await client.post(
        "/api/v1/costs", json=_create_payload("_API_LIST", "2026-01-01", fob=100), headers=headers
    )
    await client.post(
        "/api/v1/costs", json=_create_payload("_API_LIST", "2026-06-01", fob=120), headers=headers
    )

    # valid_on inside the first range → only the first row.
    r_on = await client.get("/api/v1/costs?sku=_API_LIST&valid_on=2026-03-01", headers=headers)
    assert r_on.status_code == 200, r_on.text
    items = r_on.json()["items"]
    assert len(items) == 1
    assert items[0]["valid_from"] == "2026-01-01"

    # include_history=true → both ranges, ordered by valid_from desc.
    r_hist = await client.get("/api/v1/costs?sku=_API_LIST&include_history=true", headers=headers)
    assert r_hist.status_code == 200, r_hist.text
    hist = r_hist.json()["items"]
    vfs = [it["valid_from"] for it in hist if it["sku"] == "_API_LIST"]
    assert "2026-01-01" in vfs
    assert "2026-06-01" in vfs


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_default_only_current(
    client: AsyncClient, db_session: AsyncSession, make_product
) -> None:
    """Sin valid_on ni include_history → sólo vigentes HOY (rango abierto)."""
    await make_product("_API_CUR")
    headers = await _auth(db_session)

    # Past closed range (ends before today) + current open-ended range.
    await client.post(
        "/api/v1/costs", json=_create_payload("_API_CUR", "2020-01-01", fob=100), headers=headers
    )
    await client.post(
        "/api/v1/costs", json=_create_payload("_API_CUR", "2020-06-01", fob=120), headers=headers
    )

    r = await client.get("/api/v1/costs?sku=_API_CUR", headers=headers)
    assert r.status_code == 200, r.text
    items = [it for it in r.json()["items"] if it["sku"] == "_API_CUR"]
    # Only the open-ended (current) row is vigente today.
    assert len(items) == 1
    assert items[0]["valid_to"] is None
    assert items[0]["valid_from"] == "2020-06-01"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_no_auth_returns_401(client: AsyncClient) -> None:
    r = await client.get("/api/v1/costs")
    assert r.status_code == 401
