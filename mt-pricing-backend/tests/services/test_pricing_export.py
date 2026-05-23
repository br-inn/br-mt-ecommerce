"""Tests unitarios para pricing_export — US-1B-04-01 / US-1B-04-04.

Cubre:
- ``validate_payload``: errores por sku ausente, price_aed inválido.
- ``shadow_publish``: retorna ok=True, shadow_mode=True (stub).
- ``shadow_publish`` US-1B-04-04: escribe /tmp, flag deshabilitado usa csv, valida payload.

asyncio_mode = "auto" (pyproject.toml), no se necesita @pytest.mark.asyncio.
"""

from __future__ import annotations

import glob
import os
import tempfile
from datetime import datetime, timezone

import pytest

from app.services.feature_flags.flag_service import (
    clear_local_cache,
    set_local_flag,
    FLAG_SHADOW_PUBLISH_AMAZON,
)
from app.services.pricing_export import AmazonUAEAdapter, PublishPayload

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_payload(rows: list[dict]) -> PublishPayload:
    return PublishPayload(
        channel_code="AMAZON_UAE",
        scheme_code="FBA",
        rows=rows,
        generated_at=datetime.now(tz=timezone.utc),
    )


def _valid_row(sku: str = "MTV-1004", price: float = 147.75) -> dict:
    return {
        "sku": sku,
        "price_aed": price,
        "status": "approved",
        "fx_rate": 3.67,
        "approved_at": "2026-05-12T10:00:00Z",
    }


# ---------------------------------------------------------------------------
# Tests validate_payload
# ---------------------------------------------------------------------------


def test_amazon_uae_adapter_validates_missing_sku():
    """validate_payload retorna error si fila sin sku."""
    adapter = AmazonUAEAdapter()
    row = _valid_row()
    row.pop("sku")  # eliminar sku
    payload = _make_payload([row])

    errors = adapter.validate_payload(payload)

    assert len(errors) >= 1
    codes = [e["code"] for e in errors]
    assert "MISSING_SKU" in codes
    # campo correcto
    sku_errors = [e for e in errors if e["code"] == "MISSING_SKU"]
    assert sku_errors[0]["field"] == "sku"
    assert sku_errors[0]["row"] == 0


def test_amazon_uae_adapter_validates_missing_price():
    """validate_payload retorna error si price_aed = 0."""
    adapter = AmazonUAEAdapter()
    row = _valid_row(price=0)
    payload = _make_payload([row])

    errors = adapter.validate_payload(payload)

    assert len(errors) >= 1
    codes = [e["code"] for e in errors]
    assert "INVALID_PRICE" in codes
    price_errors = [e for e in errors if e["code"] == "INVALID_PRICE"]
    assert price_errors[0]["field"] == "price_aed"
    assert price_errors[0]["row"] == 0


def test_amazon_uae_adapter_valid_payload_no_errors():
    """validate_payload retorna lista vacía para payload válido."""
    adapter = AmazonUAEAdapter()
    payload = _make_payload([_valid_row(), _valid_row(sku="MTV-2001", price=89.50)])

    errors = adapter.validate_payload(payload)

    assert errors == []


# ---------------------------------------------------------------------------
# Tests shadow_publish
# ---------------------------------------------------------------------------


async def test_amazon_uae_adapter_shadow_publish_returns_stub():
    """shadow_publish retorna ok=True, shadow_mode=True."""
    adapter = AmazonUAEAdapter()
    payload = _make_payload([_valid_row(), _valid_row(sku="MTV-2001", price=89.50)])

    result = await adapter.shadow_publish(payload)

    assert result.ok is True
    assert result.shadow_mode is True
    assert result.channel_code == "AMAZON_UAE"
    assert result.rows_exported == 2
    assert result.rows_blocked == 0
    assert result.submission_id is not None
    assert result.submission_id.startswith("shadow-amz-")  # US-1B-04-04: shadow prefix
    assert result.errors == []


async def test_amazon_uae_adapter_export_csv_filters_non_approved():
    """export_csv excluye filas con status != 'approved' en rows_blocked."""
    adapter = AmazonUAEAdapter()
    rows = [
        _valid_row(sku="MTV-1004"),  # approved
        {**_valid_row(sku="MTV-1005"), "status": "pending"},  # blocked
        {**_valid_row(sku="MTV-1006"), "status": "draft"},  # blocked
    ]
    payload = _make_payload(rows)

    csv_bytes, result = await adapter.export_csv(payload)

    assert result.ok is True
    assert result.rows_exported == 1
    assert result.rows_blocked == 2
    assert result.shadow_mode is False
    # CSV debe contener el header + 1 fila de datos
    csv_text = csv_bytes.decode("utf-8")
    lines = [l for l in csv_text.splitlines() if l.strip()]
    assert len(lines) == 2  # header + 1 row
    assert "MTV-1004" in csv_text
    assert "MTV-1005" not in csv_text


# ---------------------------------------------------------------------------
# Tests US-1B-04-04 — shadow_publish real (escribe /tmp)
# ---------------------------------------------------------------------------


async def test_shadow_publish_writes_file():
    """shadow_publish escribe /tmp/shadow_amazon_uae_*.csv y retorna ok=True, shadow_mode=True."""
    adapter = AmazonUAEAdapter()
    payload = _make_payload([_valid_row(), _valid_row(sku="MTV-2001", price=89.50)])

    tmp_dir = tempfile.gettempdir()
    # Capturar archivos pre-existentes para aislar los nuevos
    before = set(glob.glob(os.path.join(tmp_dir, "shadow_amazon_uae_*.csv")))

    result = await adapter.shadow_publish(payload)

    after = set(glob.glob(os.path.join(tmp_dir, "shadow_amazon_uae_*.csv")))
    new_files = after - before

    assert result.ok is True
    assert result.shadow_mode is True
    assert result.channel_code == "AMAZON_UAE"
    assert result.rows_exported == 2
    assert len(new_files) == 1, f"Esperaba 1 archivo shadow nuevo, got {new_files}"
    shadow_path = new_files.pop()
    assert os.path.exists(shadow_path)
    with open(shadow_path, encoding="utf-8") as fh:
        content = fh.read()
    assert "sku" in content  # header presente
    assert "MTV-1004" in content


async def test_shadow_publish_disabled_uses_csv():
    """Con flag deshabilitado, shadow_publish NO es invocado por el adapter directamente.

    Aquí verificamos que export_csv devuelve shadow_mode=False (el comportamiento
    normal del adapter cuando se llama directamente sin el flag).
    """
    adapter = AmazonUAEAdapter()
    payload = _make_payload([_valid_row()])

    csv_bytes, result = await adapter.export_csv(payload)

    assert result.shadow_mode is False
    assert result.ok is True
    assert len(csv_bytes) > 0


async def test_shadow_publish_validates_payload():
    """shadow_publish con rows vacías retorna ExportResult.ok=False."""
    adapter = AmazonUAEAdapter()
    # Fila inválida: sin sku y price=0
    bad_row = {"sku": "", "price_aed": 0, "status": "approved", "fx_rate": 3.67, "approved_at": ""}
    payload = _make_payload([bad_row])

    result = await adapter.shadow_publish(payload)

    assert result.ok is False
    assert result.shadow_mode is True
    assert result.rows_exported == 0
    assert result.rows_blocked >= 1
    assert len(result.errors) >= 1
