"""Celery task: generación async de thumbnails WebP.

US-1A-02-08 (Sprint 2). Descarga el original desde Supabase Storage, genera
variantes WebP (160/400/800/1600 px) manteniendo aspect ratio (fit-inside, no
crop), y las sube a `product-images/products/{sku}/photos/thumbs/{uuid}_{size}.webp`.

Wave 1 additions:
- Write variants jsonb to product_assets row after generation.
- Compute blurhash for photo-like kinds (photo, banner, mirror_url).
- Compute SHA-256 of original if missing in DB.
- Only photo/banner/mirror_url kinds run thumbnail generation; others return early.

Diseño:
- Idempotente: re-ejecutar es seguro — sobreescribe con `upsert=true`.
- Healthcheck: task `thumbnails_health` (no-op) para `celery inspect ping`.
- Calidad WebP: 85 (balance tamaño/calidad razonable para listing).
- Pillow es lazy-import (sólo lo necesita el worker, no el API).

Routing key `mt.images.generate_thumbnails` → queue `images`.
"""

from __future__ import annotations

import hashlib
import io
import logging
from typing import Any

from celery import Task

from app.core.config import settings
from app.workers.worker import celery_app

logger = logging.getLogger(__name__)

# Tamaños target — bordes máx (fit-inside). Wave 1 adds 160 and 1600.
THUMBNAIL_SIZES: tuple[int, ...] = (160, 400, 800, 1600)
WEBP_QUALITY: int = 85

# Kinds that support thumbnail / blurhash generation.
PHOTO_KINDS: frozenset[str] = frozenset({"photo", "banner", "mirror_url"})


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


def _build_thumbnail_key(sku: str, size: int, original_key: str) -> str:
    """Build the storage key for a webp thumbnail.

    Uses the original_key stem to keep thumbnails co-located with their source.
    Falls back to legacy path for backward compat.
    """
    # If original_key is in new Wave-1 path format (products/{sku}/photos/{uuid}_*)
    # produce: products/{sku}/photos/thumbs/{uuid}_{size}.webp
    import os

    dirname = os.path.dirname(original_key)
    basename = os.path.basename(original_key)
    stem = os.path.splitext(basename)[0]
    return f"{dirname}/thumbs/{stem}_{size}.webp"


def _compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _compute_blurhash(image_bytes: bytes) -> str | None:
    """Compute blurhash from image bytes. Returns None if library unavailable."""
    try:
        import blurhash  # type: ignore[import-not-found]
        from PIL import Image  # type: ignore[import-not-found]

        with Image.open(io.BytesIO(image_bytes)) as img:
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
            # Resize to small for blurhash computation (performance).
            small = img.copy()
            small.thumbnail((128, 128))
            return blurhash.encode(small, x_components=4, y_components=3)
    except Exception:  # noqa: BLE001
        return None


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
    asset_kind: str = "photo",
) -> dict[str, Any]:
    """Genera thumbnails WebP a partir del original ya en bucket.

    Wave 1: only photo/banner/mirror_url kinds generate thumbnails.
    Other kinds return early (no-op).

    Args:
        product_sku: SKU del producto.
        original_key: clave del original en bucket.
        asset_kind: kind of the asset (default 'photo' for backward compat).

    Returns:
        dict con `status`, `sku`, `original_key`, `variants` (dict de paths).
    """
    log_ctx: dict[str, Any] = {
        "task_id": self.request.id,
        "sku": product_sku,
        "original_key": original_key,
        "kind": asset_kind,
    }

    # Only photo-like kinds generate thumbnails.
    if asset_kind not in PHOTO_KINDS:
        logger.info(
            "thumbnails.skip_non_photo_kind",
            extra={**log_ctx},
        )
        return {
            "status": "skipped",
            "reason": f"kind '{asset_kind}' does not require thumbnails",
            "sku": product_sku,
            "original_key": original_key,
            "variants": {},
        }

    bucket = settings.SUPABASE_STORAGE_BUCKET_IMAGES
    storage = _get_supabase_storage()

    original = _download_original(storage, bucket, original_key)
    log_ctx["original_bytes"] = len(original)

    # Compute SHA-256 of original for dedup.
    sha256 = _compute_sha256(original)

    # Compute blurhash.
    blurhash_value = _compute_blurhash(original)

    variants_dict: dict[str, str] = {}
    for size in THUMBNAIL_SIZES:
        thumb = _resize_to_webp(original, size)
        key = _build_thumbnail_key(product_sku, size, original_key)
        _upload_thumbnail(storage, bucket, key, thumb)
        variants_dict[f"webp_{size}"] = key
        logger.info(
            "thumbnails.variant_generated",
            extra={**log_ctx, "size": size, "variant_key": key, "variant_bytes": len(thumb)},
        )

    if blurhash_value:
        variants_dict["blurhash"] = blurhash_value

    # Write variants + sha256 + metadata to product_assets row (best-effort).
    _persist_variants_to_db(
        storage_path=original_key,
        variants=variants_dict,
        sha256=sha256,
        width=None,  # Width/height will be read from DB if already there.
        height=None,
        blurhash_value=blurhash_value,
    )

    logger.info("thumbnails.success", extra={**log_ctx, "variants": list(variants_dict.keys())})
    return {
        "status": "ok",
        "sku": product_sku,
        "original_key": original_key,
        "variants": variants_dict,
    }


def _persist_variants_to_db(
    storage_path: str,
    variants: dict[str, str],
    sha256: str,
    width: int | None,
    height: int | None,
    blurhash_value: str | None,
) -> None:
    """Write variants jsonb + metadata to the matching product_assets row.

    Uses a synchronous DB session (Celery worker context — sync by default).
    Best-effort: errors are logged but not re-raised.
    """
    try:
        import asyncio

        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        db_url = str(settings.DATABASE_URL)
        engine = create_async_engine(db_url, pool_pre_ping=True)
        async_session = async_sessionmaker(engine, expire_on_commit=False)

        async def _update() -> None:
            from app.db.models.product import ProductAsset

            async with async_session() as session:
                result = await session.execute(
                    select(ProductAsset).where(ProductAsset.storage_path == storage_path)
                )
                asset = result.scalar_one_or_none()
                if asset is None:
                    return
                asset.variants = {**asset.variants, **variants}
                if sha256 and not asset.hash_sha256:
                    asset.hash_sha256 = sha256
                # Patch metadata with blurhash if available.
                if blurhash_value:
                    asset.asset_meta = {**asset.asset_meta, "blurhash": blurhash_value}
                await session.commit()

        # Run in existing event loop if available, else create one.
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Can't run sync in running loop — schedule as future.
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    pool.submit(asyncio.run, _update()).result(timeout=10)
            else:
                loop.run_until_complete(_update())
        except RuntimeError:
            asyncio.run(_update())

        import asyncio as _asyncio

        _asyncio.run(engine.dispose())
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "thumbnails.db_persist_failed",
            extra={"storage_path": storage_path, "error": str(exc)},
        )


@celery_app.task(name="mt.images.thumbnails_health")
def thumbnails_health() -> str:
    """No-op para `celery inspect ping` — verifica que el worker autoload tasks."""
    return "ok"
