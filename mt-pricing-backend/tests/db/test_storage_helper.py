"""US-1A-02-06 — DoD: storage helper para signed URLs y path builder.

Tests unit (sin Supabase real):
- `build_product_image_path` produce paths según convenciones por role.
- TTL clamping respeta default 1h, max 24h, rechaza valores ≤ 0.
- `create_signed_url` invoca el cliente Supabase con args correctos
  (mockeado vía dependency injection del parámetro `client`).
- Bucket privado `product-images` configurado en settings.

Marca `unit` — no toca red.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.services import storage as storage_svc

pytestmark = [pytest.mark.unit]


# --------------------------------------------------------------------------
# Path builder
# --------------------------------------------------------------------------
def test_build_path_primary_master() -> None:
    """role='primary' → master/{sku}/{uuid|id}.{ext}."""
    path = storage_svc.build_product_image_path(
        sku="MT-V-038", role="primary", ext="png", image_id="abc-123"
    )
    assert path == "master/MT-V-038/abc-123.png"


def test_build_path_gallery_uses_master_prefix() -> None:
    path = storage_svc.build_product_image_path(
        sku="MT-V-100", role="gallery", ext="webp", image_id="img-uuid"
    )
    assert path == "master/MT-V-100/img-uuid.webp"


def test_build_path_external_mirror_prefix() -> None:
    path = storage_svc.build_product_image_path(
        sku="MT-V-200", role="external_mirror", ext="jpg", image_id="m-1"
    )
    assert path == "external_mirror/MT-V-200/m-1.jpg"


def test_build_path_thumbnail_size_required() -> None:
    """role='thumbnail' requiere thumbnail_size 256/512/1024."""
    with pytest.raises(ValueError, match="thumbnail_size"):
        storage_svc.build_product_image_path(sku="MT-V-038", role="thumbnail", ext="webp")


def test_build_path_thumbnail_path_format() -> None:
    path = storage_svc.build_product_image_path(
        sku="MT-V-038", role="thumbnail", ext="webp", thumbnail_size=512
    )
    assert path == "thumbnails/MT-V-038/512/primary.webp"


def test_build_path_invalid_role_raises() -> None:
    with pytest.raises(ValueError, match="role inválido"):
        storage_svc.build_product_image_path(sku="X", role="bogus", ext="png")


def test_build_path_generates_uuid_when_no_image_id() -> None:
    """Sin image_id, build_product_image_path genera un UUID estable."""
    path = storage_svc.build_product_image_path(sku="X", role="primary", ext="png")
    # master/X/{uuid}.png — 32 hex + 4 dashes = 36 chars
    parts = path.split("/")
    assert parts[0] == "master"
    assert parts[1] == "X"
    assert parts[2].endswith(".png")
    uuid_part = parts[2].rsplit(".", 1)[0]
    assert len(uuid_part) == 36
    assert uuid_part.count("-") == 4


def test_build_path_normalizes_extension() -> None:
    """Extensión con punto o mayúsculas se normaliza a sin-punto + lowercase."""
    path = storage_svc.build_product_image_path(sku="X", role="primary", ext=".PNG", image_id="i")
    assert path == "master/X/i.png"


# --------------------------------------------------------------------------
# TTL clamping
# --------------------------------------------------------------------------
def test_clamp_ttl_default() -> None:
    assert storage_svc._clamp_ttl(None) == storage_svc.DEFAULT_SIGNED_URL_TTL_SECONDS == 3600


def test_clamp_ttl_max_24h() -> None:
    """TTL > 24h se trunca a 24h."""
    assert storage_svc._clamp_ttl(99999) == storage_svc.MAX_SIGNED_URL_TTL_SECONDS == 86400


def test_clamp_ttl_negative_or_zero_raises() -> None:
    with pytest.raises(ValueError):
        storage_svc._clamp_ttl(0)
    with pytest.raises(ValueError):
        storage_svc._clamp_ttl(-1)


def test_clamp_ttl_passthrough() -> None:
    assert storage_svc._clamp_ttl(1800) == 1800


# --------------------------------------------------------------------------
# create_signed_url — mocked Supabase client
# --------------------------------------------------------------------------
def _make_mock_client(signed_url: str = "https://example.com/signed?token=xyz") -> Any:
    """Construye un mock que se comporta como `supabase.Client.storage.from_(bucket)`."""
    client = MagicMock()
    bucket_op = MagicMock()
    bucket_op.create_signed_url.return_value = {"signedURL": signed_url}
    client.storage.from_.return_value = bucket_op
    return client, bucket_op


def test_create_signed_url_invokes_supabase_with_default_ttl() -> None:
    client, bucket_op = _make_mock_client()
    result = storage_svc.create_signed_url("master/MT-V-038/abc.png", client=client)
    bucket_op.create_signed_url.assert_called_once_with(
        path="master/MT-V-038/abc.png", expires_in=3600
    )
    assert result["signed_url"].startswith("https://")
    assert result["expires_in"] == 3600
    assert result["storage_path"] == "master/MT-V-038/abc.png"


def test_create_signed_url_clamps_ttl_to_max() -> None:
    client, bucket_op = _make_mock_client()
    result = storage_svc.create_signed_url("x.png", ttl_seconds=99999, client=client)
    bucket_op.create_signed_url.assert_called_once_with(path="x.png", expires_in=86400)
    assert result["expires_in"] == 86400


def test_create_signed_url_custom_ttl_in_range() -> None:
    client, bucket_op = _make_mock_client()
    storage_svc.create_signed_url("x.png", ttl_seconds=7200, client=client)
    bucket_op.create_signed_url.assert_called_once_with(path="x.png", expires_in=7200)


def test_create_signed_url_raises_on_missing_url() -> None:
    """Si Supabase devuelve dict sin signedURL, helper raisea RuntimeError."""
    client = MagicMock()
    bucket_op = MagicMock()
    bucket_op.create_signed_url.return_value = {"error": "boom"}
    client.storage.from_.return_value = bucket_op

    with pytest.raises(RuntimeError, match="signed URL"):
        storage_svc.create_signed_url("x.png", client=client)


def test_create_signed_url_uses_settings_bucket_default() -> None:
    """Bucket default = settings.SUPABASE_STORAGE_BUCKET_IMAGES."""
    from app.core.config import settings

    client, _bucket_op = _make_mock_client()
    storage_svc.create_signed_url("x.png", client=client)
    client.storage.from_.assert_called_once_with(settings.SUPABASE_STORAGE_BUCKET_IMAGES)


# --------------------------------------------------------------------------
# upload_bytes — mocked
# --------------------------------------------------------------------------
def test_upload_bytes_calls_supabase_with_options() -> None:
    client = MagicMock()
    bucket_op = MagicMock()
    client.storage.from_.return_value = bucket_op

    data = b"fake png bytes"
    result = storage_svc.upload_bytes(
        "master/X/abc.png", data, content_type="image/png", client=client
    )

    bucket_op.upload.assert_called_once()
    call_kwargs = bucket_op.upload.call_args.kwargs
    assert call_kwargs["path"] == "master/X/abc.png"
    assert call_kwargs["file"] == data
    assert call_kwargs["file_options"]["content-type"] == "image/png"
    assert call_kwargs["file_options"]["upsert"] == "false"

    assert result["bytes"] == len(data)
    assert result["storage_path"] == "master/X/abc.png"
