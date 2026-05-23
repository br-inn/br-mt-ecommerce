"""Tests probe_and_mirror_image task — US-1A-02-07.

Cubre:
- SSRF block return path (no excepción, retorna `status=blocked`).
- Idempotencia (skip si hash ya existe).
- Upload + trigger thumbnails enqueue.

Usa `celery_app_eager` fixture (conftest.py) para correr inline.
"""

from __future__ import annotations

import socket
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _mock_dns_public(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda host, port, *a, **kw: [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", port))
        ],
    )


def test_probe_returns_blocked_for_ssrf_violation(celery_app_eager):
    """SSRF guard rechaza → task retorna dict status=blocked, NO lanza."""
    from app.workers.probe_mirror import probe_and_mirror_image

    result = probe_and_mirror_image.apply(
        args=("MT-V-001", "http://169.254.169.254/latest/meta-data/", "test")
    ).get()
    assert result["status"] == "blocked"
    assert "code" in result
    assert result["code"].startswith("ssrf_blocked")


def test_probe_returns_blocked_for_pim_es_when_flag_off(celery_app_eager, monkeypatch):
    from app.services import ssrf as ssrf_module
    from app.workers.probe_mirror import probe_and_mirror_image

    monkeypatch.setattr(ssrf_module.settings, "ALLOW_PROBE_FROM_PIM_ES", False, raising=False)
    result = probe_and_mirror_image.apply(
        args=("MT-V-001", "https://pim.mt-valves.es/img.jpg", "pim_es")
    ).get()
    assert result["status"] == "blocked"
    assert result["code"] == "image_rights_pending"


def test_probe_uploads_and_triggers_thumbnails(celery_app_eager):
    """Happy path: SSRF OK → safe_fetch OK → upload OK → thumbnails enqueue."""
    from app.workers import probe_mirror as pm

    fake_storage = MagicMock()
    # No existe en bucket → debe subir.
    fake_storage.from_().list.return_value = []
    fake_storage.from_().upload.return_value = {"Key": "ok"}

    fake_fetch_result = MagicMock()
    fake_fetch_result.content = b"\xff\xd8\xff" + b"\x00" * 100
    fake_fetch_result.detected_mime = "image/jpeg"
    fake_fetch_result.sha256 = "a" * 64
    fake_fetch_result.bytes_downloaded = 103
    fake_fetch_result.final_url = "https://example.com/img.jpg"

    enqueued: list[tuple[str, str]] = []

    def fake_enqueue(sku: str, key: str) -> None:
        enqueued.append((sku, key))

    with (
        patch.object(pm, "_get_supabase_storage", return_value=fake_storage),
        patch.object(pm, "safe_fetch_image", return_value=fake_fetch_result),
        patch.object(pm, "_enqueue_thumbnails", side_effect=fake_enqueue),
    ):
        result = pm.probe_and_mirror_image.apply(
            args=("MT-V-038", "https://example.com/img.jpg", "manual")
        ).get()

    assert result["status"] == "ok"
    assert result["skipped_existing"] is False
    assert result["mime"] == "image/jpeg"
    assert result["sha256"] == "a" * 64
    assert result["key"] == f"originals/MT-V-038/{'a' * 64}.jpg"
    fake_storage.from_().upload.assert_called()
    assert enqueued == [("MT-V-038", f"originals/MT-V-038/{'a' * 64}.jpg")]


def test_probe_idempotent_skips_existing(celery_app_eager):
    """Si el hash ya existe en bucket → skip upload, igual dispara thumbnails."""
    from app.workers import probe_mirror as pm

    fake_storage = MagicMock()
    sha = "b" * 64
    fake_storage.from_().list.return_value = [{"name": f"{sha}.jpg"}]

    fake_fetch_result = MagicMock()
    fake_fetch_result.content = b"\xff\xd8\xff"
    fake_fetch_result.detected_mime = "image/jpeg"
    fake_fetch_result.sha256 = sha
    fake_fetch_result.bytes_downloaded = 3
    fake_fetch_result.final_url = "https://example.com/img.jpg"

    enqueued: list[Any] = []

    with (
        patch.object(pm, "_get_supabase_storage", return_value=fake_storage),
        patch.object(pm, "safe_fetch_image", return_value=fake_fetch_result),
        patch.object(pm, "_enqueue_thumbnails", side_effect=lambda s, k: enqueued.append((s, k))),
    ):
        result = pm.probe_and_mirror_image.apply(
            args=("MT-V-001", "https://example.com/img.jpg", "manual")
        ).get()

    assert result["status"] == "ok"
    assert result["skipped_existing"] is True
    fake_storage.from_().upload.assert_not_called()
    # Thumbnails sí se disparan (también son idempotentes).
    assert len(enqueued) == 1
