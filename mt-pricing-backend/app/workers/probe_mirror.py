"""Celery task: probe + mirror obligatorio de imágenes externas.

US-1A-02-07 (Sprint 2). Aplica el guard SSRF (ADR-055), descarga la imagen,
calcula sha256, sube al bucket `product-images/originals/{sku}/{hash}.{ext}`
y dispara la generación async de thumbnails.

Diseño:
- Idempotente: si el hash ya existe en bucket, NO redownload (verifica via
  storage list); sólo se refresca metadata del registro.
- Retry con backoff exponencial (3 intentos). Tras DLQ → audit_event de fallo.
- Audit: cada mirror exitoso o fallido genera evento `image.probe.{success,failure}`
  vía logging estructurado (la persistencia en tabla audit la consume Agente 1
  vía task `mt.audit.*`).

Routing key `mt.images.probe_and_mirror_image` → queue `images`.
"""

from __future__ import annotations

import logging
from typing import Any

from celery import Task

from app.core.config import settings
from app.services.ssrf import SSRFViolation, safe_fetch_image
from app.workers.worker import celery_app

logger = logging.getLogger(__name__)


# Mapping MIME → extensión canónica para storage path.
_MIME_TO_EXT: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


def _build_originals_key(sku: str, sha256_hex: str, mime: str) -> str:
    """`originals/{sku}/{hash}.{ext}` — aplana namespace por SKU."""
    ext = _MIME_TO_EXT.get(mime, "bin")
    return f"originals/{sku}/{sha256_hex}.{ext}"


def _get_supabase_storage() -> Any:
    """Cliente Supabase service-role para Storage. Lazy import (worker only).

    En tests (sin SUPABASE configurado) devuelve None y el caller hace fallback.
    """
    try:
        from app.core.supabase import get_supabase_admin
    except ImportError:
        return None
    try:
        client = get_supabase_admin()
    except Exception:
        return None
    return client.storage if client is not None else None


def _storage_object_exists(storage: Any, bucket: str, key: str) -> bool:
    """Checa si un objeto ya existe en el bucket (idempotencia)."""
    if storage is None:
        return False
    try:
        # Supabase-py: list con prefix exacto y filtro por nombre.
        prefix = "/".join(key.split("/")[:-1])
        name = key.split("/")[-1]
        items = storage.from_(bucket).list(prefix)
        return any(item.get("name") == name for item in (items or []))
    except Exception:
        logger.warning("probe_mirror.storage_list_failed", extra={"bucket": bucket, "key": key})
        return False


def _upload_original(storage: Any, bucket: str, key: str, body: bytes, mime: str) -> None:
    """Sube los bytes al bucket. Si existe, sobreescribe (idempotente sobre hash)."""
    if storage is None:
        logger.info(
            "probe_mirror.storage_skip_no_client",
            extra={"bucket": bucket, "key": key, "bytes": len(body)},
        )
        return
    try:
        storage.from_(bucket).upload(
            key,
            body,
            file_options={"content-type": mime, "upsert": "true"},
        )
    except Exception as e:
        logger.exception("probe_mirror.storage_upload_failed", extra={"key": key})
        raise RuntimeError(f"upload failed: {e}") from e


@celery_app.task(
    bind=True,
    name="mt.images.probe_and_mirror_image",
    autoretry_for=(RuntimeError,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
    acks_late=True,
)
def probe_and_mirror_image(
    self: Task,
    product_sku: str,
    image_url: str,
    source: str = "manual",
) -> dict[str, Any]:
    """Probe + mirror sync (ejecutado dentro del worker).

    Args:
        product_sku: SKU del producto destino.
        image_url: URL externa (debe ser HTTPS pública — ver SSRF guard).
        source: origen del trigger (`pim_es`, `manual`, `importer`, ...) — auditoría.

    Returns:
        dict con `status`, `key`, `sha256`, `mime`, `bytes`, `final_url`,
        `skipped_existing` (idempotencia) o `error` + `code` en fallo no-retryable.

    Raises:
        RuntimeError: errores transitorios (storage upload) — Celery reintenta.
    """
    log_ctx = {
        "task_id": self.request.id,
        "sku": product_sku,
        "url_host": image_url.split("/")[2] if "://" in image_url else "?",
        "source": source,
    }
    bucket = settings.SUPABASE_STORAGE_BUCKET_IMAGES
    storage = _get_supabase_storage()

    # 1. SSRF guard + fetch.
    try:
        result = safe_fetch_image(image_url)
    except SSRFViolation as e:
        logger.warning(
            "probe_mirror.ssrf_blocked",
            extra={**log_ctx, "code": e.code, "reason": str(e)},
        )
        # Audit fallo (vía logger estructurado — Agente 1 consume).
        return {
            "status": "blocked",
            "code": e.code,
            "error": str(e),
        }

    key = _build_originals_key(product_sku, result.sha256, result.detected_mime)

    # 2. Idempotencia.
    if _storage_object_exists(storage, bucket, key):
        logger.info("probe_mirror.skip_existing", extra={**log_ctx, "key": key})
        # Aún así disparamos thumbnails (puede que también existan, son idempotentes).
        _enqueue_thumbnails(product_sku, key)
        return {
            "status": "ok",
            "key": key,
            "sha256": result.sha256,
            "mime": result.detected_mime,
            "bytes": result.bytes_downloaded,
            "final_url": result.final_url,
            "skipped_existing": True,
        }

    # 3. Upload (errores aquí → retry).
    _upload_original(storage, bucket, key, result.content, result.detected_mime)

    logger.info(
        "probe_mirror.success",
        extra={
            **log_ctx,
            "key": key,
            "sha256": result.sha256,
            "mime": result.detected_mime,
            "bytes": result.bytes_downloaded,
            "final_url": result.final_url,
        },
    )

    # 4. Trigger thumbnails async (independiente).
    _enqueue_thumbnails(product_sku, key)

    return {
        "status": "ok",
        "key": key,
        "sha256": result.sha256,
        "mime": result.detected_mime,
        "bytes": result.bytes_downloaded,
        "final_url": result.final_url,
        "skipped_existing": False,
    }


def _enqueue_thumbnails(sku: str, original_key: str) -> None:
    """Dispara thumbnails async — import lazy para evitar ciclo."""
    try:
        from app.workers.thumbnails import generate_thumbnails

        generate_thumbnails.delay(sku, original_key)
    except Exception:
        logger.exception("probe_mirror.thumbnails_enqueue_failed", extra={"sku": sku})
