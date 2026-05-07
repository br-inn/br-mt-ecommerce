"""Unit tests para `app.api.pagination` — cursor opaco base64 JSON.

Cobertura:
- encode/decode roundtrip preserva el sku.
- decode_sku_cursor(None) → None.
- Cursor base64 corrupto → 400.
- Cursor JSON válido pero sin `sku` → 400.
- Cursor que no es objeto JSON → 400.
- Cursor URL-safe (sin padding `=`) decodifica correctamente.
"""

from __future__ import annotations

import base64
import json

import pytest
from fastapi import HTTPException

from app.api.pagination import (
    decode_cursor,
    decode_sku_cursor,
    encode_cursor,
    encode_sku_cursor,
)


@pytest.mark.unit
def test_encode_decode_sku_roundtrip() -> None:
    cursor = encode_sku_cursor("MT-V-038")
    assert cursor is not None
    assert "=" not in cursor  # base64url sin padding
    assert decode_sku_cursor(cursor) == "MT-V-038"


@pytest.mark.unit
def test_decode_sku_cursor_none_passes_through() -> None:
    assert decode_sku_cursor(None) is None
    assert encode_sku_cursor(None) is None


@pytest.mark.unit
def test_decode_sku_cursor_corrupted_base64_returns_400() -> None:
    with pytest.raises(HTTPException) as exc:
        decode_sku_cursor("!!!not-valid-base64!!!")
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "invalid_cursor"


@pytest.mark.unit
def test_decode_sku_cursor_missing_sku_key_returns_400() -> None:
    bad = encode_cursor({"foo": "bar"})
    with pytest.raises(HTTPException) as exc:
        decode_sku_cursor(bad)
    assert exc.value.status_code == 400


@pytest.mark.unit
def test_decode_cursor_array_payload_rejected() -> None:
    raw = base64.urlsafe_b64encode(b'["not","an","object"]').rstrip(b"=").decode()
    with pytest.raises(HTTPException) as exc:
        decode_cursor(raw)
    assert exc.value.status_code == 400


@pytest.mark.unit
def test_encode_is_deterministic() -> None:
    """Mismo payload → mismo cursor (sort_keys + separators fijos)."""
    a = encode_cursor({"sku": "MT-V-1", "extra": 1})
    b = encode_cursor({"extra": 1, "sku": "MT-V-1"})
    assert a == b


@pytest.mark.unit
def test_encoded_cursor_decodes_to_expected_json() -> None:
    cursor = encode_sku_cursor("MT-V-999")
    raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
    payload = json.loads(raw)
    assert payload == {"sku": "MT-V-999"}
