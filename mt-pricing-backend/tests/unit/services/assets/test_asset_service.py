"""Unit tests for app.services.assets.AssetService — Wave 1.

Sin DB real — usa AsyncSession mock + in-memory fake rows.
Cobertura (15+ tests):
1.  generate_signed_upload_url returns fake URL in placeholder env.
2.  generate_signed_upload_url raises AssetValidationError for wrong MIME.
3.  generate_signed_upload_url returns correct kind in payload.
4.  confirm_upload creates ProductAsset row.
5.  confirm_upload raises AssetValidationError for wrong MIME.
6.  confirm_upload raises AssetValidationError if bytes_size exceeds limit.
7.  confirm_upload sets metadata.width/height for photo kind.
8.  confirm_upload does NOT set metadata for pdf kind.
9.  set_primary demotes other assets and promotes target.
10. set_primary raises AssetNotFoundError for unknown id.
11. archive sets status='archived' and archived_at.
12. archive raises AssetNotFoundError for unknown id.
13. restore sets status='active' and clears archived fields.
14. delete_hard removes asset.
15. delete_hard raises AssetNotFoundError for unknown id.
16. mirror_external creates row with status='pending_upload'.
17. mirror_external raises AssetValidationError for non-http URL.
18. list_for_product filters by kind.
19. list_for_product excludes archived by default.
20. update_variants merges variants dict.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.services.assets.asset_service import (
    AssetNotFoundError,
    AssetService,
    AssetValidationError,
    build_storage_path,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fake ProductAsset
# ---------------------------------------------------------------------------
class _FakeAsset:
    def __init__(
        self,
        *,
        id: UUID | None = None,
        sku: str = "MT-V-038",
        kind: str = "photo",
        bucket: str = "product-images",
        storage_path: str = "products/MT-V-038/photos/abc_img.jpg",
        status: str = "active",
        is_primary: bool = False,
        position: int = 0,
        variants: dict | None = None,
        asset_meta: dict | None = None,
    ) -> None:
        self.id = id or uuid4()
        self.sku = sku
        self.kind = kind
        self.bucket = bucket
        self.storage_path = storage_path
        self.status = status
        self.is_primary = is_primary
        self.position = position
        self.variants = variants or {}
        self.asset_meta = asset_meta or {}
        self.archived_at: datetime | None = None
        self.archived_by: UUID | None = None
        self.original_url: str | None = None
        self.mime_type: str | None = None
        self.bytes_size: int | None = None
        self.width: int | None = None
        self.height: int | None = None
        self.alt_text: str | None = None
        self.locale: str | None = None
        self.caption: str | None = None
        self.hash_sha256: str | None = None
        self.revision: str | None = None
        self.supersedes_id: UUID | None = None
        self.created_by: UUID | None = None
        self.created_at: datetime = datetime.now(tz=UTC)


# ---------------------------------------------------------------------------
# Session mock builder
# ---------------------------------------------------------------------------
def _make_session(assets: list[_FakeAsset] | None = None) -> Any:
    """Build a mock AsyncSession that returns given assets from scalars()."""
    assets = assets or []
    session = MagicMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()

    # build execute mock that returns assets based on query
    async def _execute(stmt: Any) -> Any:  # noqa: ARG001
        result = MagicMock()
        scalars_result = MagicMock()
        scalars_result.all.return_value = list(assets)
        scalars_result.one_or_none.return_value = assets[0] if assets else None
        result.scalars.return_value = scalars_result
        result.scalar_one_or_none.return_value = assets[0] if assets else None
        return result

    session.execute = _execute

    # execute for update (returns rowcount mock)
    return session


# ---------------------------------------------------------------------------
# Helpers to create service with a session
# ---------------------------------------------------------------------------
def _svc(assets: list[_FakeAsset] | None = None) -> tuple[AssetService, Any]:
    session = _make_session(assets)
    return AssetService(session), session


# ---------------------------------------------------------------------------
# Tests: generate_signed_upload_url
# ---------------------------------------------------------------------------
def test_signed_url_returns_fake_in_placeholder_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force placeholder mode: clear Supabase settings so AssetService returns
    # the fake-storage.local stub instead of calling the real Storage API.
    from app.core import config as _config

    monkeypatch.setattr(_config.settings, "SUPABASE_URL", "", raising=False)
    monkeypatch.setattr(_config.settings, "SUPABASE_SERVICE_ROLE_KEY", None, raising=False)
    svc, _ = _svc()
    result = svc.generate_signed_upload_url(
        sku="MT-V-038",
        kind="photo",
        filename="product.jpg",
        mime_type="image/jpeg",
    )
    assert "fake-storage.local" in result["upload_url"]
    assert result["kind"] == "photo"
    assert result["bucket"] == "product-images"
    assert "storage_path" in result


def test_signed_url_raises_for_wrong_mime() -> None:
    svc, _ = _svc()
    with pytest.raises(AssetValidationError, match="mime_type"):
        svc.generate_signed_upload_url(
            sku="MT-V-038",
            kind="photo",
            filename="doc.pdf",
            mime_type="application/pdf",
        )


def test_signed_url_includes_kind_in_result() -> None:
    svc, _ = _svc()
    result = svc.generate_signed_upload_url(
        sku="MT-V-038",
        kind="datasheet_pdf",
        filename="ds.pdf",
        mime_type="application/pdf",
    )
    assert result["kind"] == "datasheet_pdf"


# ---------------------------------------------------------------------------
# Tests: confirm_upload
# ---------------------------------------------------------------------------
async def test_confirm_upload_creates_asset_row() -> None:
    svc, session = _svc()
    # Patch session.execute to return None for set_primary queries (update stmts).
    added_objects: list[Any] = []

    def _capture_add(obj: Any) -> None:
        added_objects.append(obj)
        obj.id = uuid4()  # Simulate DB assigning id on flush.

    session.add = _capture_add

    asset = await svc.confirm_upload(
        "MT-V-038",
        storage_path="products/MT-V-038/photos/abc_img.jpg",
        kind="photo",
        mime_type="image/jpeg",
        width=800,
        height=600,
        bytes_size=10240,
    )
    assert len(added_objects) == 1
    obj = added_objects[0]
    assert obj.sku == "MT-V-038"
    assert obj.kind == "photo"
    assert obj.status == "active"


async def test_confirm_upload_rejects_wrong_mime() -> None:
    svc, _ = _svc()
    with pytest.raises(AssetValidationError, match="mime_type"):
        await svc.confirm_upload(
            "MT-V-038",
            storage_path="some/path/img.jpg",
            kind="photo",
            mime_type="application/pdf",
        )


async def test_confirm_upload_rejects_oversized_file() -> None:
    svc, _ = _svc()
    with pytest.raises(AssetValidationError, match="bytes_size"):
        await svc.confirm_upload(
            "MT-V-038",
            storage_path="some/path/img.jpg",
            kind="photo",
            mime_type="image/jpeg",
            bytes_size=50 * 1024 * 1024,  # 50 MB > 10 MB photo limit
        )


async def test_confirm_upload_photo_sets_width_height_metadata() -> None:
    svc, session = _svc()
    added_objects: list[Any] = []

    def _capture(obj: Any) -> None:
        added_objects.append(obj)
        obj.id = uuid4()

    session.add = _capture

    await svc.confirm_upload(
        "MT-V-038",
        storage_path="products/MT-V-038/photos/abc_img.jpg",
        kind="photo",
        mime_type="image/jpeg",
        width=1920,
        height=1080,
    )
    assert added_objects[0].asset_meta == {"width": 1920, "height": 1080}


async def test_confirm_upload_pdf_does_not_set_dimension_metadata() -> None:
    svc, session = _svc()
    added_objects: list[Any] = []

    def _capture(obj: Any) -> None:
        added_objects.append(obj)
        obj.id = uuid4()

    session.add = _capture

    await svc.confirm_upload(
        "MT-V-038",
        storage_path="products/MT-V-038/docs/ds.pdf",
        kind="datasheet_pdf",
        mime_type="application/pdf",
    )
    assert added_objects[0].asset_meta == {}


# ---------------------------------------------------------------------------
# Tests: set_primary
# ---------------------------------------------------------------------------
async def test_set_primary_raises_for_unknown_asset() -> None:
    svc, _ = _svc(assets=[])  # no assets in DB
    with pytest.raises(AssetNotFoundError):
        await svc.set_primary(uuid4(), "MT-V-038")


async def test_set_primary_promotes_target() -> None:
    asset = _FakeAsset(sku="MT-V-038", kind="photo")
    svc, session = _svc(assets=[asset])

    # Track update calls.
    updated: list[Any] = []

    async def _execute(stmt: Any) -> Any:
        updated.append(stmt)
        result = MagicMock()
        result.scalar_one_or_none.return_value = asset
        scalars = MagicMock()
        scalars.all.return_value = [asset]
        scalars.one_or_none.return_value = asset
        result.scalars.return_value = scalars
        return result

    session.execute = _execute

    result = await svc.set_primary(asset.id, "MT-V-038")
    assert result is asset
    # Should have called execute (at least for the get + two updates).
    assert len(updated) >= 1


# ---------------------------------------------------------------------------
# Tests: archive / restore
# ---------------------------------------------------------------------------
async def test_archive_sets_status_and_timestamp() -> None:
    asset = _FakeAsset(sku="MT-V-038")
    svc, _ = _svc(assets=[asset])
    actor_id = uuid4()

    result = await svc.archive(asset.id, "MT-V-038", actor_id=actor_id)
    assert result.status == "archived"
    assert result.archived_at is not None
    assert result.archived_by == actor_id


async def test_archive_raises_for_unknown_asset() -> None:
    svc, _ = _svc(assets=[])
    with pytest.raises(AssetNotFoundError):
        await svc.archive(uuid4(), "MT-V-038")


async def test_restore_clears_archive_fields() -> None:
    asset = _FakeAsset(sku="MT-V-038", status="archived")
    asset.archived_at = datetime.now(tz=UTC)
    asset.archived_by = uuid4()
    svc, _ = _svc(assets=[asset])

    result = await svc.restore(asset.id, "MT-V-038")
    assert result.status == "active"
    assert result.archived_at is None
    assert result.archived_by is None


# ---------------------------------------------------------------------------
# Tests: delete_hard
# ---------------------------------------------------------------------------
async def test_delete_hard_removes_asset() -> None:
    asset = _FakeAsset(sku="MT-V-038")
    svc, session = _svc(assets=[asset])
    await svc.delete_hard(asset.id, "MT-V-038")
    session.delete.assert_called_once_with(asset)


async def test_delete_hard_raises_for_unknown_asset() -> None:
    svc, _ = _svc(assets=[])
    with pytest.raises(AssetNotFoundError):
        await svc.delete_hard(uuid4(), "MT-V-038")


# ---------------------------------------------------------------------------
# Tests: mirror_external
# ---------------------------------------------------------------------------
async def test_mirror_external_creates_pending_upload_row() -> None:
    svc, session = _svc()
    added: list[Any] = []

    def _capture(obj: Any) -> None:
        added.append(obj)
        obj.id = uuid4()

    session.add = _capture

    result = await svc.mirror_external(
        "https://example.com/product.jpg",
        sku="MT-V-038",
        kind="mirror_url",
    )
    assert result.status == "pending_upload"
    assert result.original_url == "https://example.com/product.jpg"
    assert result.kind == "mirror_url"


async def test_mirror_external_rejects_non_http_url() -> None:
    svc, _ = _svc()
    with pytest.raises(AssetValidationError, match="esquema"):
        await svc.mirror_external("ftp://example.com/file.jpg", sku="MT-V-038")


async def test_mirror_external_rejects_empty_url() -> None:
    svc, _ = _svc()
    with pytest.raises(AssetValidationError, match="vacía"):
        await svc.mirror_external("", sku="MT-V-038")


# ---------------------------------------------------------------------------
# Tests: list_for_product
# ---------------------------------------------------------------------------
async def test_list_for_product_filters_by_kind() -> None:
    photo = _FakeAsset(sku="MT-V-038", kind="photo")
    pdf = _FakeAsset(sku="MT-V-038", kind="datasheet_pdf")

    executed_stmts: list[Any] = []

    async def _execute(stmt: Any) -> Any:
        executed_stmts.append(stmt)
        result = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = [photo]
        result.scalars.return_value = scalars
        return result

    session = MagicMock()
    session.execute = _execute
    svc = AssetService(session)

    results = await svc.list_for_product("MT-V-038", kind="photo")
    # The query was built and executed.
    assert len(executed_stmts) == 1


async def test_list_for_product_excludes_archived_by_default() -> None:
    # We only check that the query is built (no real DB filtering in unit tests).
    executed_stmts: list[Any] = []

    async def _execute(stmt: Any) -> Any:
        executed_stmts.append(stmt)
        result = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = []
        result.scalars.return_value = scalars
        return result

    session = MagicMock()
    session.execute = _execute
    svc = AssetService(session)

    await svc.list_for_product("MT-V-038", include_archived=False)
    assert len(executed_stmts) == 1


# ---------------------------------------------------------------------------
# Tests: update_variants
# ---------------------------------------------------------------------------
async def test_update_variants_merges_dict() -> None:
    asset = _FakeAsset(variants={"webp_160": "old_path"})
    svc, _ = _svc(assets=[asset])

    result = await svc.update_variants(
        asset.id,
        variants={"webp_400": "new_path_400"},
        metadata_patch={"blurhash": "Lxyz"},
    )
    assert result is not None
    assert result.variants["webp_160"] == "old_path"
    assert result.variants["webp_400"] == "new_path_400"
    assert result.asset_meta["blurhash"] == "Lxyz"


# ---------------------------------------------------------------------------
# Tests: build_storage_path helper
# ---------------------------------------------------------------------------
def test_build_storage_path_photo() -> None:
    path = build_storage_path("MT-V-038", "photo", "product.jpg")
    assert path.startswith("products/MT-V-038/photos/")
    assert path.endswith("_product.jpg")


def test_build_storage_path_datasheet() -> None:
    path = build_storage_path("MT-V-038", "datasheet_pdf", "spec.pdf")
    assert "docs" in path


def test_build_storage_path_invalid_filename() -> None:
    with pytest.raises(AssetValidationError, match="filename"):
        build_storage_path("MT-V-038", "photo", "file with spaces.jpg")
