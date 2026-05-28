"""Integration tests for offset (page-based) pagination of GET /products."""

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
        await session.execute(select(Role).where(Role.code == "offset_admin"))
    ).scalar_one_or_none()
    if role is None:
        role = Role(code="offset_admin", name="offset_admin", permissions_snapshot=perms_codes)
        session.add(role)
        await session.flush()
        for pid in perm_ids:
            session.add(RolePermission(role_id=role.id, permission_id=pid))
        await session.flush()
    uid = uuid4()
    email = f"offset-{uid.hex[:6]}@mt.ae"
    user = User(id=uid, email=email, full_name="O", locale="es", is_active=True, role_id=role.id)
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


async def _seed_products(session: AsyncSession, count: int) -> list[str]:
    """Insert `count` products with SKUs TST-001 through TST-NNN, returns sorted SKU list."""
    from app.db.models.vocabularies import Brand, Family

    # Ensure brand + family exist
    brand_row = (
        await session.execute(select(Brand).where(Brand.code == "tst"))
    ).scalar_one_or_none()
    if brand_row is None:
        brand_row = Brand(code="tst", name="TST")
        session.add(brand_row)
        await session.flush()
    brand_id = brand_row.id

    family_row = (
        await session.execute(select(Family).where(Family.code == "valves_offset"))
    ).scalar_one_or_none()
    if family_row is None:
        family_row = Family(code="valves_offset", name="valves_offset")
        session.add(family_row)
        await session.flush()
    family_id = family_row.id

    from app.db.models.product import Product

    skus = [f"TST-{i:03d}" for i in range(1, count + 1)]
    for sku in skus:
        p = Product(
            sku=sku,
            family="valves_offset",
            brand="TST",
            brand_id=brand_id,
            family_id=family_id,
            lifecycle_status="active",
            data_quality="complete",
        )
        session.add(p)
    await session.flush()
    return skus


@pytest.mark.integration
@pytest.mark.asyncio
async def test_offset_page1_returns_correct_slice(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Page 1 with limit=2 returns first 2 SKUs and total=5."""
    uid, email = await _seed_admin(db_session)
    token = _emit_jwt(sub=str(uid), email=email)
    skus = await _seed_products(db_session, 5)
    r = await client.get(
        "/api/v1/products?page=1&limit=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 5
    assert body["page"] == 1
    assert body["pages"] == 3
    assert body["page_size"] == 2
    returned_skus = [i["sku"] for i in body["items"]]
    assert returned_skus == skus[:2]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_offset_page2_returns_middle_slice(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Page 2 with limit=2 returns SKUs 3-4."""
    uid, email = await _seed_admin(db_session)
    token = _emit_jwt(sub=str(uid), email=email)
    skus = await _seed_products(db_session, 5)
    r = await client.get(
        "/api/v1/products?page=2&limit=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["page"] == 2
    assert [i["sku"] for i in body["items"]] == skus[2:4]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_offset_last_page_partial(client: AsyncClient, db_session: AsyncSession) -> None:
    """Last page (page=3, limit=2) returns only 1 item (5th SKU)."""
    uid, email = await _seed_admin(db_session)
    token = _emit_jwt(sub=str(uid), email=email)
    skus = await _seed_products(db_session, 5)
    r = await client.get(
        "/api/v1/products?page=3&limit=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["sku"] == skus[4]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cursor_mode_unchanged(client: AsyncClient, db_session: AsyncSession) -> None:
    """Without ?page=, cursor mode still works and total/page/pages are null."""
    uid, email = await _seed_admin(db_session)
    token = _emit_jwt(sub=str(uid), email=email)
    await _seed_products(db_session, 3)
    r = await client.get(
        "/api/v1/products?limit=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] is None
    assert body["page"] is None
    assert body["pages"] is None
    assert len(body["items"]) == 2
    assert body["cursor"]["next"] is not None
