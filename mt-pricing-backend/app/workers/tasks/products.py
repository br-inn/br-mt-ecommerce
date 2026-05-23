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
    """Implementación bulk-SQL.

    El trigger ``audit_events_hash_chain`` serializa por-row → 5085 audits
    individuales toman >30 min. Para un backfill one-shot preferimos:
      1. Read-pass en Python (clasifica y agrupa por field).
      2. Bulk UPDATE SQL por campo (5 statements en total).
      3. Un solo audit ``classifier.run.completed`` con counters resumen.
    """
    from uuid import UUID as _UUID

    from sqlalchemy import select, text

    from app.db.engine import get_sessionmaker
    from app.db.models.product import Product
    from app.repositories.audit import AuditRepository
    from app.services.products.pvf_classifier import classify

    from app.db.models.product import ProductTranslation

    actor_uuid = _UUID(actor_id) if actor_id else None
    SessionFactory = get_sessionmaker()

    counters: dict[str, Any] = {
        "scanned": 0,
        "field_updates": {"family": 0, "material": 0, "dn": 0, "pn": 0},
        "rows_changed": 0,
        "promoted_to_complete": 0,
        "skipped_placeholder_name": 0,
        "errors": 0,
    }
    sample_errors: list[str] = []

    # Acumuladores: sku → valor a setear (solo si el actual es vacío/unclassified).
    fam_updates: dict[str, str] = {}
    mat_updates: dict[str, str] = {}
    dn_updates: dict[str, str] = {}
    pn_updates: dict[str, str] = {}
    promote_skus: list[str] = []

    async with SessionFactory() as session:
        # ---------- Pass 1: read + classify in memory ----------
        # Fase B (mig 065): name_en vive en product_translations(lang='en').
        # LEFT JOIN para mantener filas sin translation EN.
        stmt = (
            select(
                Product.sku,
                ProductTranslation.name.label("name_en"),
                Product.family,
                Product.material,
                Product.dn,
                Product.pn,
                Product.data_quality,
                Product.manual_locked_fields,
            )
            .select_from(Product)
            .outerjoin(
                ProductTranslation,
                (ProductTranslation.sku == Product.sku) & (ProductTranslation.lang == "en"),
            )
            .where(Product.deleted_at.is_(None))
        )
        if only_partial:
            stmt = stmt.where(Product.data_quality == "partial")
        result = await session.execute(stmt)

        for sku, name_en, family, material, dn, pn, dq, locked_raw in result.all():
            counters["scanned"] += 1
            if not name_en or name_en.startswith("[Producto sin nombre"):
                counters["skipped_placeholder_name"] += 1
                continue
            try:
                r = classify(name_en)
            except Exception as exc:  # noqa: BLE001 — defensivo
                counters["errors"] += 1
                if len(sample_errors) < 20:
                    sample_errors.append(f"{sku}: {exc!s}")
                continue

            locked = set(locked_raw or [])
            row_changed = False

            new_family = family
            if r.family and "family" not in locked and family in (None, "", "unclassified"):
                fam_updates[sku] = r.family
                counters["field_updates"]["family"] += 1
                new_family = r.family
                row_changed = True

            new_material = material
            if r.material and "material" not in locked and material in (None, ""):
                mat_updates[sku] = r.material
                counters["field_updates"]["material"] += 1
                new_material = r.material
                row_changed = True

            new_dn = dn
            if r.dn and "dn" not in locked and dn in (None, ""):
                dn_updates[sku] = r.dn
                counters["field_updates"]["dn"] += 1
                new_dn = r.dn
                row_changed = True

            new_pn = pn
            if r.pn and "pn" not in locked and pn in (None, ""):
                pn_updates[sku] = r.pn
                counters["field_updates"]["pn"] += 1
                new_pn = r.pn
                row_changed = True

            if row_changed:
                counters["rows_changed"] += 1
                if (
                    promote
                    and dq == "partial"
                    and new_family
                    and new_family != "unclassified"
                    and new_material
                    and new_dn
                    and new_pn
                ):
                    promote_skus.append(sku)

        # ---------- Pass 2: bulk UPDATE por campo via UNNEST ----------
        # 4 UPDATE statements + 1 promotion + 1 audit summary.
        if fam_updates:
            await session.execute(
                text("""
                    UPDATE public.products AS p
                    SET family = u.val, updated_at = NOW(), updated_by = :uid
                    FROM unnest(CAST(:skus AS text[]), CAST(:vals AS text[])) AS u(sku, val)
                    WHERE p.sku = u.sku AND p.family IN ('unclassified', '')
                """),
                {
                    "skus": list(fam_updates.keys()),
                    "vals": list(fam_updates.values()),
                    "uid": actor_uuid,
                },
            )
        if mat_updates:
            await session.execute(
                text("""
                    UPDATE public.products AS p
                    SET material = u.val, updated_at = NOW(), updated_by = :uid
                    FROM unnest(CAST(:skus AS text[]), CAST(:vals AS text[])) AS u(sku, val)
                    WHERE p.sku = u.sku AND (p.material IS NULL OR p.material = '')
                """),
                {
                    "skus": list(mat_updates.keys()),
                    "vals": list(mat_updates.values()),
                    "uid": actor_uuid,
                },
            )
        if dn_updates:
            await session.execute(
                text("""
                    UPDATE public.products AS p
                    SET dn = u.val, updated_at = NOW(), updated_by = :uid
                    FROM unnest(CAST(:skus AS text[]), CAST(:vals AS text[])) AS u(sku, val)
                    WHERE p.sku = u.sku AND (p.dn IS NULL OR p.dn = '')
                """),
                {
                    "skus": list(dn_updates.keys()),
                    "vals": list(dn_updates.values()),
                    "uid": actor_uuid,
                },
            )
        if pn_updates:
            await session.execute(
                text("""
                    UPDATE public.products AS p
                    SET pn = u.val, updated_at = NOW(), updated_by = :uid
                    FROM unnest(CAST(:skus AS text[]), CAST(:vals AS text[])) AS u(sku, val)
                    WHERE p.sku = u.sku AND (p.pn IS NULL OR p.pn = '')
                """),
                {
                    "skus": list(pn_updates.keys()),
                    "vals": list(pn_updates.values()),
                    "uid": actor_uuid,
                },
            )
        if promote and promote_skus:
            await session.execute(
                text("""
                    UPDATE public.products
                    SET data_quality = 'complete', updated_at = NOW(), updated_by = :uid
                    WHERE sku = ANY(CAST(:skus AS text[])) AND data_quality = 'partial'
                """),
                {"skus": promote_skus, "uid": actor_uuid},
            )
            counters["promoted_to_complete"] = len(promote_skus)

        # Single audit summary (en lugar de 5085 — el trigger hash chain solo
        # corre una vez aquí).
        audit = AuditRepository(session)
        await audit.record(
            entity_type="system",
            entity_id="classifier",
            action="classifier.run.completed",
            actor_id=actor_uuid,
            actor_email="system@mtme.local",
            actor_role="system",
            payload_diff={
                "field_updates": counters["field_updates"],
                "rows_changed": counters["rows_changed"],
                "promoted_to_complete": counters["promoted_to_complete"],
                "scanned": counters["scanned"],
                "skipped_placeholder_name": counters["skipped_placeholder_name"],
                "errors": counters["errors"],
                "only_partial": only_partial,
                "promote_to_complete": promote,
            },
            reason="pvf_classifier bulk run",
        )
        await session.commit()

    logger.info(
        "classify_pim_batch completed",
        extra={
            "scanned": counters["scanned"],
            "rows_changed": counters["rows_changed"],
            "promoted": counters["promoted_to_complete"],
        },
    )

    counters["errors_sample"] = sample_errors
    return counters
