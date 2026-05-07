"""ImagePipeline — orquestación del flujo probe + mirror + thumbnails.

Capa fina sobre las tasks Celery (`app.workers.probe_mirror.probe_and_mirror_image`,
`app.workers.thumbnails.generate_thumbnails`). Llamable desde routes HTTP
(p.ej. `POST /api/v1/products/{sku}/images/probe`) — encola la task y devuelve
el `job_id` para polling.

Responsabilidades:
- Pre-validación SSRF rápida (rechazo HTTP inmediato — no encolar tarea inútil).
- Encolado idempotente (mismo SKU+URL en flight: opcional dedupe vía Redis lock,
  por ahora se deja al worker hacer dedupe por hash post-download).
- Devolver `job_id` Celery y un task name humano para audit.

Refs:
- ADR-055 (SSRF policy).
- mt-jobs-module-design.md.
- US-1A-02-07 / US-1A-02-08.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.services.ssrf import SSRFViolation, validate_url

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProbeJobHandle:
    """Devuelto por `enqueue_probe`. `job_id` se usa para polling."""

    job_id: str
    task_name: str
    sku: str
    image_url: str


class ImagePipelineError(Exception):
    """Wrapper de errores del pipeline (no-retryable, route HTTP debe mapear)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ImagePipeline:
    """Servicio sin estado — depende sólo de las tasks Celery + SSRF guard."""

    def enqueue_probe(
        self,
        product_sku: str,
        image_url: str,
        source: str = "manual",
        *,
        eager_validate: bool = True,
    ) -> ProbeJobHandle:
        """Encola probe + mirror para una URL externa.

        Args:
            product_sku: SKU del producto.
            image_url: URL externa.
            source: `pim_es | manual | importer | ...` para audit.
            eager_validate: si True (default), hace pre-validación SSRF síncrona
                para rechazar HTTP 422 sin encolar tarea. Si False, se delega
                100% al worker (útil para batch importer donde no queremos
                bloquear la request HTTP en N validaciones DNS).

        Returns:
            ProbeJobHandle con `job_id` Celery.

        Raises:
            ImagePipelineError: si `eager_validate=True` y la URL falla SSRF.
        """
        if eager_validate:
            try:
                validate_url(image_url)
            except SSRFViolation as e:
                logger.warning(
                    "image_pipeline.probe_rejected_eager",
                    extra={
                        "sku": product_sku,
                        "code": e.code,
                        "url_host": image_url.split("/")[2] if "://" in image_url else "?",
                    },
                )
                raise ImagePipelineError(e.code, str(e)) from e

        # Lazy import — evita ciclos y permite que el módulo se importe en
        # entornos donde Celery no esté arrancado (tests unit puros).
        from app.workers.probe_mirror import probe_and_mirror_image

        async_result = probe_and_mirror_image.delay(product_sku, image_url, source)
        logger.info(
            "image_pipeline.probe_enqueued",
            extra={
                "sku": product_sku,
                "job_id": async_result.id,
                "source": source,
            },
        )
        return ProbeJobHandle(
            job_id=async_result.id,
            task_name="mt.images.probe_and_mirror_image",
            sku=product_sku,
            image_url=image_url,
        )

    def enqueue_thumbnails(self, product_sku: str, original_key: str) -> str:
        """Encola sólo el paso de thumbnails (re-trigger manual, e.g. tras fallo)."""
        from app.workers.thumbnails import generate_thumbnails

        async_result = generate_thumbnails.delay(product_sku, original_key)
        logger.info(
            "image_pipeline.thumbnails_enqueued",
            extra={
                "sku": product_sku,
                "job_id": async_result.id,
                "original_key": original_key,
            },
        )
        return async_result.id


__all__ = ["ImagePipeline", "ImagePipelineError", "ProbeJobHandle"]
