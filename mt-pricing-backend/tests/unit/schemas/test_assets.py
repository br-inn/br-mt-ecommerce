"""Unit tests for app.schemas.assets — Wave 1 asset unification.

Cobertura:
- AssetKind / AssetStatus enum values.
- ProductAssetUploadRequest validation (mime per kind, filename sanitization).
- ProductAssetConfirmRequest validation (storage_path sanitization, mime/kind).
- ProductAssetPatch validation (at least one field).
- ProductAssetResponse model_validate from dict + url computation.
- compute_asset_urls helper.
- allowed_mimes_for_kind / max_bytes_for_kind helpers.
- Backward compat: ProductImageResponse alias.
"""

from __future__ import annotations

from datetime import UTC
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.assets import (
    AssetKind,
    AssetStatus,
    ProductAssetConfirmRequest,
    ProductAssetPatch,
    ProductAssetResponse,
    ProductAssetUploadRequest,
    allowed_mimes_for_kind,
    compute_asset_urls,
    max_bytes_for_kind,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
def test_asset_kind_values() -> None:
    expected = {
        "photo",
        "banner",
        "datasheet_pdf",
        "exploded_3d",
        "section_drawing",
        "dimension_drawing",
        "certificate_pdf",
        "video_link",
        "external_url",
        "mirror_url",
    }
    assert {k.value for k in AssetKind} == expected


def test_asset_status_values() -> None:
    expected = {"active", "archived", "broken", "pending_upload", "processing"}
    assert {s.value for s in AssetStatus} == expected


# ---------------------------------------------------------------------------
# allowed_mimes_for_kind / max_bytes_for_kind
# ---------------------------------------------------------------------------
def test_allowed_mimes_photo() -> None:
    mimes = allowed_mimes_for_kind("photo")
    assert "image/jpeg" in mimes
    assert "image/png" in mimes
    assert "application/pdf" not in mimes


def test_allowed_mimes_datasheet_pdf() -> None:
    mimes = allowed_mimes_for_kind("datasheet_pdf")
    assert mimes == frozenset({"application/pdf"})


def test_max_bytes_photo() -> None:
    assert max_bytes_for_kind("photo") == 10 * 1024 * 1024


def test_max_bytes_datasheet_pdf() -> None:
    assert max_bytes_for_kind("datasheet_pdf") == 50 * 1024 * 1024


# ---------------------------------------------------------------------------
# ProductAssetUploadRequest
# ---------------------------------------------------------------------------
def test_upload_request_valid_photo() -> None:
    req = ProductAssetUploadRequest(
        kind=AssetKind.PHOTO,
        filename="product.jpg",
        mime_type="image/jpeg",
    )
    assert req.kind == AssetKind.PHOTO
    assert req.filename == "product.jpg"


def test_upload_request_invalid_mime_for_photo() -> None:
    with pytest.raises(ValidationError, match="mime_type"):
        ProductAssetUploadRequest(
            kind=AssetKind.PHOTO,
            filename="doc.pdf",
            mime_type="application/pdf",
        )


def test_upload_request_valid_datasheet() -> None:
    req = ProductAssetUploadRequest(
        kind=AssetKind.DATASHEET_PDF,
        filename="datasheet.pdf",
        mime_type="application/pdf",
    )
    assert req.kind == AssetKind.DATASHEET_PDF


def test_upload_request_invalid_filename_with_slash() -> None:
    with pytest.raises(ValidationError, match="filename"):
        ProductAssetUploadRequest(
            kind=AssetKind.PHOTO,
            filename="../../../etc/passwd",
            mime_type="image/jpeg",
        )


def test_upload_request_invalid_filename_traversal() -> None:
    with pytest.raises(ValidationError, match="filename"):
        ProductAssetUploadRequest(
            kind=AssetKind.PHOTO,
            filename="foo/../bar.jpg",
            mime_type="image/jpeg",
        )


def test_upload_request_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        ProductAssetUploadRequest(  # type: ignore[call-arg]
            kind=AssetKind.PHOTO,
            filename="img.jpg",
            mime_type="image/jpeg",
            unexpected_field="bad",
        )


# ---------------------------------------------------------------------------
# ProductAssetConfirmRequest
# ---------------------------------------------------------------------------
def test_confirm_request_valid() -> None:
    req = ProductAssetConfirmRequest(
        storage_path="products/MT-V-038/photos/abc123_img.jpg",
        kind=AssetKind.PHOTO,
        mime_type="image/jpeg",
        bytes_size=1024,
        width=800,
        height=600,
        is_primary=True,
    )
    assert req.is_primary is True
    assert req.kind == AssetKind.PHOTO


def test_confirm_request_invalid_storage_path_absolute() -> None:
    with pytest.raises(ValidationError, match="storage_path"):
        ProductAssetConfirmRequest(
            storage_path="/absolute/path/img.jpg",
            kind=AssetKind.PHOTO,
            mime_type="image/jpeg",
        )


def test_confirm_request_invalid_storage_path_traversal() -> None:
    with pytest.raises(ValidationError, match="storage_path"):
        ProductAssetConfirmRequest(
            storage_path="../../etc/shadow",
            kind=AssetKind.PHOTO,
            mime_type="image/jpeg",
        )


def test_confirm_request_wrong_mime_for_kind() -> None:
    with pytest.raises(ValidationError, match="mime_type"):
        ProductAssetConfirmRequest(
            storage_path="products/MT-V-038/docs/abc.pdf",
            kind=AssetKind.PHOTO,
            mime_type="application/pdf",
        )


# ---------------------------------------------------------------------------
# ProductAssetPatch
# ---------------------------------------------------------------------------
def test_patch_valid_single_field() -> None:
    p = ProductAssetPatch(alt_text="New alt text")
    assert p.alt_text == "New alt text"


def test_patch_empty_raises() -> None:
    with pytest.raises(ValidationError, match="PATCH payload vacío"):
        ProductAssetPatch()


def test_patch_position_valid() -> None:
    p = ProductAssetPatch(position=5)
    assert p.position == 5


# ---------------------------------------------------------------------------
# compute_asset_urls
# ---------------------------------------------------------------------------
def test_compute_asset_urls_with_variants() -> None:
    variants = {
        "webp_160": "products/MT-V-038/photos/thumbs/abc_160.webp",
        "webp_400": "products/MT-V-038/photos/thumbs/abc_400.webp",
        "blurhash": "LGF5?xYk^6#M@-5c,1J5@[or[Q6.",
    }
    urls = compute_asset_urls(
        bucket="product-images",
        storage_path="products/MT-V-038/photos/abc_img.jpg",
        variants=variants,
        supabase_url="https://myproject.supabase.co",
    )
    assert urls["original"] == (
        "https://myproject.supabase.co/storage/v1/object/public/"
        "product-images/products/MT-V-038/photos/abc_img.jpg"
    )
    assert urls["thumb_160"] is not None
    assert "thumbs/abc_160.webp" in urls["thumb_160"]
    assert urls["blurhash"] == "LGF5?xYk^6#M@-5c,1J5@[or[Q6."


def test_compute_asset_urls_empty_variants() -> None:
    urls = compute_asset_urls(
        bucket="product-images",
        storage_path="products/MT-V-038/photos/abc_img.jpg",
        variants={},
        supabase_url="https://myproject.supabase.co",
    )
    assert urls["original"] is not None
    assert urls["thumb_160"] is None
    assert urls["thumb_400"] is None


def test_compute_asset_urls_fake_supabase() -> None:
    """Degrades gracefully when supabase URL is placeholder."""
    urls = compute_asset_urls(
        bucket="product-images",
        storage_path="some/path/img.jpg",
        variants={},
        supabase_url="https://your-project.supabase.co",
    )
    assert "fake-storage.local" in urls["original"]


# ---------------------------------------------------------------------------
# ProductAssetResponse from_attributes
# ---------------------------------------------------------------------------
def test_asset_response_validates_from_dict() -> None:
    from datetime import datetime

    now = datetime.now(tz=UTC)
    asset_id = uuid4()
    # The field is aliased as 'metadata' in JSON but stored as 'asset_meta' in ORM.
    data = {
        "id": asset_id,
        "sku": "MT-V-038",
        "kind": "photo",
        "bucket": "product-images",
        "storage_path": "products/MT-V-038/photos/abc_img.jpg",
        "is_primary": True,
        "position": 0,
        "status": "active",
        "variants": {},
        "metadata": {"width": 800},  # uses alias
        "created_at": now,
    }
    resp = ProductAssetResponse.model_validate(data)
    assert resp.id == asset_id
    assert resp.sku == "MT-V-038"
    assert resp.kind == "photo"
    assert resp.urls["original"] is not None
    assert resp.asset_meta == {"width": 800}


def test_asset_response_validates_from_orm_object() -> None:
    """Verify from_attributes mode works with asset_meta ORM attribute."""
    from datetime import datetime

    now = datetime.now(tz=UTC)

    # Use a simple namespace object to simulate ORM (avoids MagicMock auto-attrs).
    class _FakeORM:
        pass

    orm_obj = _FakeORM()
    orm_obj.id = uuid4()
    orm_obj.sku = "MT-V-038"
    orm_obj.kind = "photo"
    orm_obj.bucket = "product-images"
    orm_obj.storage_path = "products/MT-V-038/photos/abc_img.jpg"
    orm_obj.is_primary = False
    orm_obj.position = 0
    orm_obj.status = "active"
    orm_obj.variants = {}
    orm_obj.asset_meta = {"width": 1920, "height": 1080}
    orm_obj.original_url = None
    orm_obj.alt_text = None
    orm_obj.locale = None
    orm_obj.caption = None
    orm_obj.width = 1920
    orm_obj.height = 1080
    orm_obj.bytes_size = None
    orm_obj.mime_type = "image/jpeg"
    orm_obj.hash_sha256 = None
    orm_obj.revision = None
    orm_obj.supersedes_id = None
    orm_obj.archived_at = None
    orm_obj.created_at = now
    orm_obj.created_by = None

    resp = ProductAssetResponse.model_validate(orm_obj)
    assert resp.asset_meta == {"width": 1920, "height": 1080}


# ---------------------------------------------------------------------------
# Backward compat alias
# ---------------------------------------------------------------------------
def test_product_image_response_is_alias() -> None:
    from app.schemas.assets import ProductImageResponse

    assert ProductImageResponse is ProductAssetResponse


def test_product_image_response_imported_from_products_schemas() -> None:
    from app.schemas.products import ProductAssetResponse as PAR
    from app.schemas.products import ProductImageResponse as PIR

    assert PIR is PAR
