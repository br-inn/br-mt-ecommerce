"""Tasks para la queue `images` — health + mirror externo + thumbnails.

Las tasks principales viven en módulos específicos:
- `app.workers.probe_mirror.probe_and_mirror_image` — SSRF guard + mirror sync.
- `app.workers.thumbnails.generate_thumbnails` — resize WebP 256/512/1024.

Aquí: shims/wrappers + healthcheck + mirror_external (FR-IMG-02 — entrypoint
desde importer / PIM España).
"""

from __future__ import annotations

import logging
from typing import Any

from celery import Task

from app.workers.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="mt.images.health_ping")
def health_ping() -> str:
    return "ok"


@celery_app.task(
    bind=True,
    name="mt.images.mirror_external",
    autoretry_for=(RuntimeError,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
    acks_late=True,
)
def mirror_external_image_task(
    self: Task,
    product_sku: str,
    external_url: str,
    source: str = "pim_es",
) -> dict[str, Any]:
    """FR-IMG-02 — descarga imagen externa y la mirror al bucket master/.

    Wrapper sobre `probe_and_mirror_image` (que ya implementa SSRF guard +
    mirror + thumbnails enqueue). Se mantiene este nombre task para alinear
    con el seed `job_definitions` y los callers del importer.

    Args:
        product_sku: SKU destino.
        external_url: URL externa pública (PIM España, manual import, ...).
        source: origen del trigger (audit).

    Returns:
        dict con status + key/sha256/mime/bytes.
    """
    # Lazy import — evita ciclo con probe_mirror.
    from app.workers.probe_mirror import probe_and_mirror_image

    # Reusamos la task ya implementada — invocación inline (no .delay) porque
    # ya estamos en worker context y queremos el retry policy local.
    return probe_and_mirror_image(  # type: ignore[no-any-return]
        product_sku=product_sku,
        image_url=external_url,
        source=source,
    )
