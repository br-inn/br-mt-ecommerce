"""Celery task: generación async de thumbnails WebP.

US-1A-02-08 (Sprint 2). Descarga el original desde Supabase Storage, genera
3 variantes WebP (256/512/1024 px) manteniendo aspect ratio (fit-inside, no
crop), y las sube a `product-images/thumbnails/{sku}/{size}.webp`.

Diseño:
- Idempotente: re-ejecutar es seguro — sobreescribe con `upsert=true`.
- Healthcheck: task `thumbnails_health` (no-op) para `celery inspect ping`.
- Calidad WebP: 85 (balance tamaño/calidad razonable para listing).
- Pillow es lazy-import (sólo lo necesita el worker, no el API).

Routing key `mt.images.generate_thumbnails` → queue `images`.
"""

from __future__ import annotations

import io
import logging
from typing import Any

from celery import Task

from app.core.config import settings
from app.workers.worker import celery_app

logger = logging.getLogger(__name__)

# Tamaños target — bordes máx (fit-inside).
THUMBNAIL_SIZES: tuple[int, ...] = (256, 512, 1024)
WEBP_QUALITY: int = 85


def _get_supabase_storage() -> Any:
    """Cliente Supabase service-role para Storage. Lazy import (worker only)."""
    try:
        from app.core.supabase import get_supabase_admin
    except ImportError:
        return None
    try:
        client = get_supabase_admin()
    except Exception:  # noqa: BLE001
        return None
    return client.storage if client is not None else None


def _download_original(storage: Any, bucket: str, key: str) -> bytes:
    """Descarga el original. Lanza RuntimeError para retry."""
    if storage is None:
        raise RuntimeError("supabase storage no configurado")
    try:
        return storage.from_(bucket).download(key)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"download {key} failed: {e}") from e


def _resize_to_webp(original_bytes: bytes, max_side: int) -> bytes:
    """Resize manteniendo aspect ratio. Devuelve bytes WebP quality 85.

    Pillow se importa aquí (lazy) porque el API no lo necesita.
    """
    try:
        from PIL import Image  # type: ignore[import-not-found]
    except ImportError as e:
        raise RuntimeError(
            "Pillow no instalado en el worker — añadir a pyproject.toml (Agente 1)"
        ) from e

    with Image.open(io.BytesIO(original_bytes)) as img:
        # Convertir a RGB si es paletizada/RGBA con transparencia opcional.
        if img.mode in ("P", "CMYK"):
            img = img.convert("RGB")
        # thumbnail() es in-place y mantiene aspect ratio (fit-inside).
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="WEBP", quality=WEBP_QUALITY, method=6)
        return out.getvalue()


def _build_thumbnail_key(sku: str, size: int) -> str:
    return f"thumbnails/{sku}/{size}.webp"


def _upload_thumbnail(storage: Any, bucket: str, key: str, body: bytes) -> None:
    if storage is None:
        logger.info(
            "thumbnails.storage_skip_no_client",
            extra={"key": key, "bytes": len(body)},
        )
        return
    try:
        storage.from_(bucket).upload(
            key,
            body,
            file_options={"content-type": "image/webp", "upsert": "true"},
        )
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"upload {key} failed: {e}") from e


@celery_app.task(
    bind=True,
    name="mt.images.generate_thumbnails",
    autoretry_for=(RuntimeError,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=2,  # Story dice max_retries=2 → 3 intentos totales.
    acks_late=True,
)
def generate_thumbnails(
    self: Task,
    product_sku: str,
    original_key: str,
) -> dict[str, Any]:
    """Genera 3 thumbnails WebP a partir del original ya en bucket.

    Args:
        product_sku: SKU del producto.
        original_key: clave del original en bucket (e.g. `originals/MT-V-038/abc.jpg`).

    Returns:
        dict con `status`, `sku`, `original_key`, `variants` (lista de paths).
    """
    log_ctx: dict[str, Any] = {
        "task_id": self.request.id,
        "sku": product_sku,
        "original_key": original_key,
    }
    bucket = settings.SUPABASE_STORAGE_BUCKET_IMAGES
    storage = _get_supabase_storage()

    original = _download_original(storage, bucket, original_key)
    log_ctx["original_bytes"] = len(original)

    variants: list[str] = []
    for size in THUMBNAIL_SIZES:
        thumb = _resize_to_webp(original, size)
        key = _build_thumbnail_key(product_sku, size)
        _upload_thumbnail(storage, bucket, key, thumb)
        variants.append(key)
        logger.info(
            "thumbnails.variant_generated",
            extra={**log_ctx, "size": size, "variant_key": key, "variant_bytes": len(thumb)},
        )

    logger.info("thumbnails.success", extra={**log_ctx, "variants": variants})
    return {
        "status": "ok",
        "sku": product_sku,
        "original_key": original_key,
        "variants": variants,
    }


@celery_app.task(name="mt.images.thumbnails_health")
def thumbnails_health() -> str:
    """No-op para `celery inspect ping` — verifica que el worker autoload tasks."""
    return "ok"
