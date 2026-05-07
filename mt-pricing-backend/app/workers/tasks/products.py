"""Tasks para mantenimiento del catálogo de productos.

- ``mt.products.classify_pim_batch`` — recorre productos con ``data_quality
  != complete`` y aplica el classifier rule-based PVF para llenar
  ``family/material/dn/pn``. Promueve a ``complete`` los que cumplen los 5
  campos requeridos. Audit trail por cada cambio.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from app.workers.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="mt.products.classify_pim_batch",
    queue="imports",
    bind=True,
    acks_late=True,
    soft_time_limit=1800,  # 30 min — 5085 SKUs × ~10ms = 50s, sobra holgado
    time_limit=2100,
)
def classify_pim_batch_task(
    self,
    actor_id: str | None = None,
    only_partial: bool = True,
    promote_to_complete: bool = True,
) -> dict[str, Any]:
    """Aplica el classifier PVF al catálogo y persiste resultados.

    Args:
        actor_id: UUID-string del admin que disparó la corrida (para audit).
            None si fue llamado por scheduler/sistema.
        only_partial: Si ``True`` solo procesa productos con
            ``data_quality='partial'`` (típico). ``False`` revisa todo,
            útil tras cambios de reglas.
        promote_to_complete: Si ``True`` y los 5 campos requeridos quedan
            poblados, transiciona a ``complete``.

    Returns:
        Dict con counters: scanned/updated/promoted/skipped + sample errors.
    """
    return asyncio.run(_run_async(actor_id, only_partial, promote_to_complete))


async def _run_async(
    actor_id: str | None,
    only_partial: bool,
    promote: bool,
) -> dict[str, Any]:
    from uuid import UUID as _UUID

    from sqlalchemy import select, update

    from app.db.engine import get_sessionmaker
    from app.db.models.product import Product
    from app.repositories.audit import AuditRepository
    from app.services.products.pvf_classifier import classify

    actor_uuid = _UUID(actor_id) if actor_id else None
    SessionFactory = get_sessionmaker()

    counters = {
        "scanned": 0,
        "field_updates": {"family": 0, "material": 0, "dn": 0, "pn": 0},
        "rows_changed": 0,
        "promoted_to_complete": 0,
        "skipped_placeholder_name": 0,
        "errors": 0,
    }
    sample_errors: list[str] = []

    async with SessionFactory() as session:
        audit = AuditRepository(session)
        # Fetch en lotes para no cargar 5085 productos a memoria de golpe.
        BATCH_SIZE = 500
        offset = 0
        while True:
            stmt = select(Product).where(Product.deleted_at.is_(None))
            if only_partial:
                stmt = stmt.where(Product.data_quality == "partial")
            stmt = stmt.order_by(Product.sku).offset(offset).limit(BATCH_SIZE)
            result = await session.execute(stmt)
            batch = list(result.scalars().all())
            if not batch:
                break

            for prod in batch:
                counters["scanned"] += 1
                # Skip placeholders — no hay info útil para extraer del nombre.
                if prod.name_en and prod.name_en.startswith("[Producto sin nombre"):
                    counters["skipped_placeholder_name"] += 1
                    continue
                if not prod.name_en:
                    continue

                try:
                    res = classify(prod.name_en)
                except Exception as exc:  # noqa: BLE001 — defensivo
                    counters["errors"] += 1
                    if len(sample_errors) < 20:
                        sample_errors.append(f"{prod.sku}: {exc!s}")
                    continue

                changed_fields: dict[str, dict[str, str | None]] = {}

                # Solo persistimos si el campo está vacío o `unclassified`.
                # Respetamos manual_locked_fields (no override de ediciones humanas).
                locked = set(prod.manual_locked_fields or [])

                if (
                    res.family
                    and "family" not in locked
                    and (prod.family in (None, "", "unclassified"))
                ):
                    changed_fields["family"] = {"from": prod.family, "to": res.family}
                    prod.family = res.family
                    counters["field_updates"]["family"] += 1

                if (
                    res.material
                    and "material" not in locked
                    and prod.material in (None, "")
                ):
                    changed_fields["material"] = {"from": prod.material, "to": res.material}
                    prod.material = res.material
                    counters["field_updates"]["material"] += 1

                if res.dn and "dn" not in locked and prod.dn in (None, ""):
                    changed_fields["dn"] = {"from": prod.dn, "to": res.dn}
                    prod.dn = res.dn
                    counters["field_updates"]["dn"] += 1

                if res.pn and "pn" not in locked and prod.pn in (None, ""):
                    changed_fields["pn"] = {"from": prod.pn, "to": res.pn}
                    prod.pn = res.pn
                    counters["field_updates"]["pn"] += 1

                if not changed_fields:
                    continue

                counters["rows_changed"] += 1
                prod.updated_by = actor_uuid
                prod.updated_at = datetime.now(tz=timezone.utc)

                # Promote to complete if eligible.
                if promote and prod.data_quality == "partial":
                    eligible = (
                        prod.name_en
                        and not prod.name_en.startswith("[Producto sin nombre")
                        and prod.family
                        and prod.family != "unclassified"
                        and prod.material
                        and prod.dn
                        and prod.pn
                    )
                    if eligible:
                        prev = prod.data_quality
                        prod.data_quality = "complete"
                        counters["promoted_to_complete"] += 1
                        await audit.record(
                            entity_type="product",
                            entity_id=prod.sku,
                            action="product.data_quality.transition",
                            actor_id=actor_uuid,
                            actor_email="system@mtme.local",
                            actor_role="system",
                            before={"data_quality": prev},
                            after={"data_quality": "complete"},
                            payload_diff={"data_quality": {"from": prev, "to": "complete"}},
                            reason="classify_pim_batch — auto-promotion",
                        )

                await audit.record(
                    entity_type="product",
                    entity_id=prod.sku,
                    action="product.classified",
                    actor_id=actor_uuid,
                    actor_email="system@mtme.local",
                    actor_role="system",
                    before=None,
                    after=None,
                    payload_diff=changed_fields,
                    reason="pvf_classifier rule-based pass",
                )

            await session.flush()
            await session.commit()
            offset += BATCH_SIZE
            logger.info(
                "classify_pim_batch progreso",
                extra={
                    "scanned": counters["scanned"],
                    "rows_changed": counters["rows_changed"],
                    "promoted": counters["promoted_to_complete"],
                },
            )

    counters["errors_sample"] = sample_errors
    return counters
