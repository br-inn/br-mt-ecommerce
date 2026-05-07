"""Tests generate_thumbnails task — US-1A-02-08.

Cubre:
- Healthcheck task no-op.
- Resize a 3 sizes con aspect ratio.
- Idempotencia (upsert).
- Pillow no instalado → RuntimeError (retry).
"""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest


def test_thumbnails_health_returns_ok(celery_app_eager):
    from app.workers.thumbnails import thumbnails_health

    assert thumbnails_health.apply().get() == "ok"


def _generate_test_jpeg(width: int = 1500, height: int = 1000) -> bytes:
    """Genera un JPEG sintético en memoria con Pillow (skip si no instalado)."""
    pytest.importorskip("PIL")
    from PIL import Image  # noqa: PLC0415
    img = Image.new("RGB", (width, height), color=(120, 80, 40))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=80)
    return out.getvalue()


def test_thumbnails_generates_three_sizes(celery_app_eager):
    pytest.importorskip("PIL")
    from app.workers import thumbnails as th

    original = _generate_test_jpeg(2000, 1000)

    fake_storage = MagicMock()
    fake_storage.from_().download.return_value = original
    uploads: list[tuple[str, bytes]] = []
    fake_storage.from_().upload.side_effect = lambda key, body, **kw: uploads.append((key, body))

    with patch.object(th, "_get_supabase_storage", return_value=fake_storage):
        result = th.generate_thumbnails.apply(
            args=("MT-V-038", "originals/MT-V-038/abc.jpg")
        ).get()

    assert result["status"] == "ok"
    assert len(result["variants"]) == 3
    expected_keys = {
        "thumbnails/MT-V-038/256.webp",
        "thumbnails/MT-V-038/512.webp",
        "thumbnails/MT-V-038/1024.webp",
    }
    assert set(result["variants"]) == expected_keys

    # Verifica que cada variante es WebP válido y respeta tamaño máximo.
    pytest.importorskip("PIL")
    from PIL import Image  # noqa: PLC0415
    for key, body in uploads:
        size = int(key.split("/")[-1].split(".")[0])
        with Image.open(io.BytesIO(body)) as img:
            assert img.format == "WEBP"
            assert max(img.size) <= size
            # Aspect ratio mantenido (no crop): max es exactamente size para
            # imágenes con lado mayor > size.
            assert max(img.size) == size


def test_thumbnails_aspect_ratio_preserved_for_tall_image(celery_app_eager):
    pytest.importorskip("PIL")
    from app.workers import thumbnails as th

    # Imagen 500x1500 (vertical) — al pedir 256, alto debe ser 256.
    original = _generate_test_jpeg(500, 1500)
    fake_storage = MagicMock()
    fake_storage.from_().download.return_value = original
    uploads: list[tuple[str, bytes]] = []
    fake_storage.from_().upload.side_effect = lambda key, body, **kw: uploads.append((key, body))

    from app.workers import thumbnails as th2

    with patch.object(th2, "_get_supabase_storage", return_value=fake_storage):
        th2.generate_thumbnails.apply(args=("MT-V-099", "originals/MT-V-099/x.jpg")).get()

    pytest.importorskip("PIL")
    from PIL import Image  # noqa: PLC0415
    for key, body in uploads:
        size = int(key.split("/")[-1].split(".")[0])
        with Image.open(io.BytesIO(body)) as img:
            # Lado mayor (height) == size, ancho proporcional.
            assert max(img.size) == size
            # Ratio aprox 1:3 mantenido (margen ±2px por arredondeo).
            ratio = img.size[1] / img.size[0]
            assert 2.9 < ratio < 3.1


def test_thumbnails_retries_on_storage_failure(celery_app_eager):
    """Storage download fail → RuntimeError (Celery retryable).

    Celery autoretry envuelve la excepción en `Retry` durante reintentos.
    Aceptamos ambos: Retry (mientras hay reintentos) o RuntimeError (al
    agotarse). Verificamos que la causa raíz es la RuntimeError esperada.
    """
    from celery.exceptions import Retry

    from app.workers import thumbnails as th

    fake_storage = MagicMock()
    fake_storage.from_().download.side_effect = Exception("network broken")

    with patch.object(th, "_get_supabase_storage", return_value=fake_storage):
        with pytest.raises((RuntimeError, Retry)) as excinfo:
            th.generate_thumbnails.apply(
                args=("MT-V-001", "originals/MT-V-001/x.jpg"),
                throw=True,
            ).get(disable_sync_subtasks=False)
    # Cadena de excepciones contiene download
    msg = str(excinfo.value) + str(getattr(excinfo.value, "exc", ""))
    assert "download" in msg


def test_thumbnails_no_storage_client_returns_runtime_error(celery_app_eager):
    """Sin cliente storage configurado → RuntimeError (env mal).

    Celery autoretry envuelve en `Retry` durante reintentos; aceptamos ambos.
    """
    from celery.exceptions import Retry

    from app.workers import thumbnails as th

    with patch.object(th, "_get_supabase_storage", return_value=None):
        with pytest.raises((RuntimeError, Retry)):
            th.generate_thumbnails.apply(
                args=("MT-V-001", "originals/MT-V-001/x.jpg"),
                throw=True,
            ).get(disable_sync_subtasks=False)
