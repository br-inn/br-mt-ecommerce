"""Unit tests for Wave 3 — ComponentsService.

Mock-based: stub the AsyncSession + repos to avoid hitting Postgres.
Mirrors the testing style used in tests/unit/services/assets/test_asset_service.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.components.components_service import (
    ComponentsDomainError,
    ComponentsService,
    ProductNotFoundError,
)


@pytest.fixture
def session_with_product() -> AsyncMock:
    """AsyncMock that simulates `session.execute` returning a row with product sku."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = "MT-V-038"
    session.execute = AsyncMock(return_value=result)
    return session


@pytest.fixture
def session_no_product() -> AsyncMock:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)
    return session


# ---- _ensure_product ----------------------------------------------------------

@pytest.mark.asyncio
async def test_ensure_product_not_found_raises(session_no_product: AsyncMock) -> None:
    svc = ComponentsService(session_no_product)
    with pytest.raises(ProductNotFoundError) as exc:
        await svc.list_materials("UNKNOWN-SKU")
    assert exc.value.status_code == 404
    assert exc.value.code == "product_not_found"


# ---- Materials ----------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_materials_calls_repo(session_with_product: AsyncMock) -> None:
    svc = ComponentsService(session_with_product)
    svc.materials.list_for_product = AsyncMock(return_value=[])
    result = await svc.list_materials("MT-V-038")
    svc.materials.list_for_product.assert_awaited_once_with("MT-V-038")
    assert result == []


@pytest.mark.asyncio
async def test_add_material_calls_upsert(session_with_product: AsyncMock) -> None:
    svc = ComponentsService(session_with_product)
    expected = MagicMock()
    svc.materials.upsert = AsyncMock(return_value=expected)
    out = await svc.add_material(
        "MT-V-038",
        component="body",
        position=0,
        material="stainless_steel_316l",
        observations="food grade",
    )
    svc.materials.upsert.assert_awaited_once_with(
        "MT-V-038", "body", 0, "stainless_steel_316l", "food grade"
    )
    assert out is expected


@pytest.mark.asyncio
async def test_delete_material_missing_raises_404(session_with_product: AsyncMock) -> None:
    svc = ComponentsService(session_with_product)
    svc.materials.delete = AsyncMock(return_value=False)
    with pytest.raises(ComponentsDomainError) as exc:
        await svc.delete_material("MT-V-038", "body", 0)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_material_existing_succeeds(session_with_product: AsyncMock) -> None:
    svc = ComponentsService(session_with_product)
    svc.materials.delete = AsyncMock(return_value=True)
    await svc.delete_material("MT-V-038", "body", 0)


@pytest.mark.asyncio
async def test_replace_materials_calls_repo(session_with_product: AsyncMock) -> None:
    svc = ComponentsService(session_with_product)
    svc.materials.replace_all = AsyncMock(return_value=[])
    items = [{"component": "body", "position": 0, "material": "brass"}]
    out = await svc.replace_materials("MT-V-038", items)
    svc.materials.replace_all.assert_awaited_once_with("MT-V-038", items)
    assert out == []


# ---- Connections --------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_connections_calls_repo(session_with_product: AsyncMock) -> None:
    svc = ComponentsService(session_with_product)
    svc.connections.list_for_product = AsyncMock(return_value=[])
    await svc.list_connections("MT-V-038")
    svc.connections.list_for_product.assert_awaited_once_with("MT-V-038")


@pytest.mark.asyncio
async def test_add_connection_calls_upsert(session_with_product: AsyncMock) -> None:
    svc = ComponentsService(session_with_product)
    expected = MagicMock()
    svc.connections.upsert = AsyncMock(return_value=expected)
    out = await svc.add_connection(
        "MT-V-038",
        position=1,
        connection_type="flange",
        dn="DN50",
        size="4inch",
    )
    svc.connections.upsert.assert_awaited_once_with(
        "MT-V-038",
        1,
        "flange",
        dn="DN50",
        dn_real=None,
        size="4inch",
        threading=None,
        notes=None,
    )
    assert out is expected


@pytest.mark.asyncio
async def test_delete_connection_missing_raises_404(session_with_product: AsyncMock) -> None:
    svc = ComponentsService(session_with_product)
    svc.connections.delete = AsyncMock(return_value=False)
    with pytest.raises(ComponentsDomainError) as exc:
        await svc.delete_connection("MT-V-038", 1)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_connection_existing_succeeds(session_with_product: AsyncMock) -> None:
    svc = ComponentsService(session_with_product)
    svc.connections.delete = AsyncMock(return_value=True)
    await svc.delete_connection("MT-V-038", 1)


@pytest.mark.asyncio
async def test_replace_connections_calls_repo(session_with_product: AsyncMock) -> None:
    svc = ComponentsService(session_with_product)
    svc.connections.replace_all = AsyncMock(return_value=[])
    items = [{"position": 1, "connection_type": "flange"}]
    await svc.replace_connections("MT-V-038", items)
    svc.connections.replace_all.assert_awaited_once_with("MT-V-038", items)


# ---- Domain errors ------------------------------------------------------------

def test_components_domain_error_attrs() -> None:
    err = ComponentsDomainError("foo", "bar baz", 409)
    assert err.code == "foo"
    assert err.message == "bar baz"
    assert err.status_code == 409


def test_product_not_found_error_defaults() -> None:
    err = ProductNotFoundError("X")
    assert err.code == "product_not_found"
    assert err.status_code == 404
    assert "X" in err.message
