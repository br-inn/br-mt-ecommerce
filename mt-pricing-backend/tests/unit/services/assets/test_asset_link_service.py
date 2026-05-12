"""Unit tests for app.services.assets.asset_link_service — Fase 4.

Sin DB real — AsyncSession mock + fake rows in-memory.

Cobertura:
- create_link OK + 409 unique conflict
- list_links_for_owner / list_links_for_asset / get_link
- delete_link OK + 404 not found
- find_or_create_asset_by_hash: hit (returns existing, created=False) y miss
  (insert nuevo, created=True) + no-hash bypass
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.services.assets.asset_link_service import (
    AssetLinkDomainError,
    AssetLinkService,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _FakeLink:
    def __init__(
        self,
        *,
        id: UUID | None = None,
        asset_id: UUID | None = None,
        owner_type: str = "product",
        owner_id: str = "MT-V-038",
        role: str = "web_image",
        order_index: int = 0,
    ) -> None:
        self.id = id or uuid4()
        self.asset_id = asset_id or uuid4()
        self.owner_type = owner_type
        self.owner_id = owner_id
        self.role = role
        self.order_index = order_index


class _FakeAsset:
    def __init__(
        self,
        *,
        id: UUID | None = None,
        hash_sha256: str | None = None,
        sku: str = "MT-V-038",
        kind: str = "photo",
    ) -> None:
        self.id = id or uuid4()
        self.hash_sha256 = hash_sha256
        self.sku = sku
        self.kind = kind
        self.bucket = "product-images"
        self.storage_path = "products/MT-V-038/photos/x.jpg"
        self.mime_type: str | None = None
        self.bytes_size: int | None = None
        self.width: int | None = None
        self.height: int | None = None
        self.status = "active"
        self.variants: dict[str, Any] = {}
        self.asset_meta: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Session builder
# ---------------------------------------------------------------------------
def _make_session(scalar_one_or_none_seq: list[Any] | None = None,
                  scalars_all_seq: list[list[Any]] | None = None) -> Any:
    """Mock AsyncSession; cada execute() devuelve siguiente valor de la cola."""
    session = MagicMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.flush = AsyncMock()

    one_q = list(scalar_one_or_none_seq or [])
    all_q = list(scalars_all_seq or [])

    async def _execute(_stmt: Any) -> Any:
        result = MagicMock()
        next_one = one_q.pop(0) if one_q else None
        next_all = all_q.pop(0) if all_q else []
        result.scalar_one_or_none.return_value = next_one
        scalars = MagicMock()
        scalars.all.return_value = next_all
        result.scalars.return_value = scalars
        return result

    session.execute = _execute
    return session


# ---------------------------------------------------------------------------
# create_link
# ---------------------------------------------------------------------------
async def test_create_link_ok() -> None:
    # 1ª execute (check unicidad) → None → no conflict
    session = _make_session(scalar_one_or_none_seq=[None])
    added: list[Any] = []
    session.add = lambda obj: added.append(obj)

    svc = AssetLinkService(session)
    asset_id = uuid4()
    link = await svc.create_link(
        asset_id=asset_id,
        owner_type="product",
        owner_id="MT-V-038",
        role="web_image",
        order_index=3,
    )
    assert len(added) == 1
    assert link.asset_id == asset_id
    assert link.role == "web_image"
    assert link.order_index == 3


async def test_create_link_conflict_409() -> None:
    session = _make_session(scalar_one_or_none_seq=[_FakeLink()])
    svc = AssetLinkService(session)
    with pytest.raises(AssetLinkDomainError) as exc:
        await svc.create_link(
            asset_id=uuid4(),
            owner_type="product",
            owner_id="MT-V-038",
            role="web_image",
        )
    assert exc.value.status_code == 409
    assert exc.value.code == "asset_link_conflict"


# ---------------------------------------------------------------------------
# list_links_for_owner / list_links_for_asset / get_link
# ---------------------------------------------------------------------------
async def test_list_links_for_owner() -> None:
    links = [_FakeLink(role="web_image"), _FakeLink(role="banner")]
    session = _make_session(scalars_all_seq=[links])
    svc = AssetLinkService(session)
    result = await svc.list_links_for_owner("product", "MT-V-038")
    assert result == links


async def test_list_links_for_asset() -> None:
    aid = uuid4()
    links = [_FakeLink(asset_id=aid, owner_type="product")]
    session = _make_session(scalars_all_seq=[links])
    svc = AssetLinkService(session)
    result = await svc.list_links_for_asset(aid)
    assert result == links


async def test_get_link_found() -> None:
    link = _FakeLink()
    session = _make_session(scalar_one_or_none_seq=[link])
    svc = AssetLinkService(session)
    result = await svc.get_link(link.id)
    assert result is link


async def test_get_link_missing() -> None:
    session = _make_session(scalar_one_or_none_seq=[None])
    svc = AssetLinkService(session)
    result = await svc.get_link(uuid4())
    assert result is None


# ---------------------------------------------------------------------------
# delete_link
# ---------------------------------------------------------------------------
async def test_delete_link_ok() -> None:
    link = _FakeLink()
    session = _make_session(scalar_one_or_none_seq=[link])
    svc = AssetLinkService(session)
    await svc.delete_link(link.id)
    session.delete.assert_awaited_once_with(link)


async def test_delete_link_not_found() -> None:
    session = _make_session(scalar_one_or_none_seq=[None])
    svc = AssetLinkService(session)
    with pytest.raises(AssetLinkDomainError) as exc:
        await svc.delete_link(uuid4())
    assert exc.value.status_code == 404
    assert exc.value.code == "asset_link_not_found"


# ---------------------------------------------------------------------------
# find_or_create_asset_by_hash — dedup helper
# ---------------------------------------------------------------------------
async def test_find_or_create_hash_hit_returns_existing() -> None:
    existing = _FakeAsset(hash_sha256="abc123")
    session = _make_session(scalar_one_or_none_seq=[existing])
    added: list[Any] = []
    session.add = lambda obj: added.append(obj)

    svc = AssetLinkService(session)
    asset, created = await svc.find_or_create_asset_by_hash(
        hash_sha256="abc123",
        sku="MT-V-038",
        kind="photo",
        storage_path="products/MT-V-038/photos/x.jpg",
    )
    assert asset is existing
    assert created is False
    assert added == []  # no INSERT


async def test_find_or_create_hash_miss_creates_new() -> None:
    session = _make_session(scalar_one_or_none_seq=[None])
    added: list[Any] = []
    session.add = lambda obj: added.append(obj)

    svc = AssetLinkService(session)
    asset, created = await svc.find_or_create_asset_by_hash(
        hash_sha256="zzz999",
        sku="MT-V-039",
        kind="datasheet_pdf",
        storage_path="products/MT-V-039/docs/y.pdf",
        mime_type="application/pdf",
        bytes_size=1024,
    )
    assert created is True
    assert len(added) == 1
    new_asset = added[0]
    assert new_asset.hash_sha256 == "zzz999"
    assert new_asset.sku == "MT-V-039"
    assert new_asset.kind == "datasheet_pdf"
    assert new_asset.mime_type == "application/pdf"


async def test_find_or_create_no_hash_bypasses_dedup() -> None:
    # Sin hash → no se hace SELECT, directamente INSERT.
    session = _make_session(scalar_one_or_none_seq=[])
    added: list[Any] = []
    session.add = lambda obj: added.append(obj)

    svc = AssetLinkService(session)
    asset, created = await svc.find_or_create_asset_by_hash(
        hash_sha256="",
        sku="MT-V-040",
        kind="photo",
        storage_path="products/MT-V-040/photos/x.jpg",
    )
    assert created is True
    assert len(added) == 1
    assert added[0].hash_sha256 is None
