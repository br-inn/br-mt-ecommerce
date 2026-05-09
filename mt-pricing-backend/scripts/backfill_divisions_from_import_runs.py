"""Backfill de divisiones para productos importados antes de Stage 3 Wave 11.

Recorre todos los ``import_runs`` con ``import_type='pim'`` y, para cada SKU
tocado por ese run (rastreado via ``audit_events.payload_diff._import_run_id``),
asigna las divisiones definidas en:

  1. ``import_runs.summary.division_codes`` (lista) — preferido por run.
  2. ``--default-divisions`` CLI flag (comma-sep) — fallback si el run no
     trae metadata.

Uso:
    docker exec mt-backend python -m scripts.backfill_divisions_from_import_runs \
        --dry-run --default-divisions hidrosanitario

    docker exec mt-backend python -m scripts.backfill_divisions_from_import_runs \
        --default-divisions hidrosanitario,industrial

Idempotente: re-correr no duplica links (el helper hace get_link antes de
insertar). Reporta counts agrupados.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from collections import defaultdict
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_sessionmaker
from app.db.models.import_run import ImportRun
from app.services.imports.division_assignment import assign_divisions

logger = logging.getLogger("backfill_divisions")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


async def _skus_for_run(session: AsyncSession, run_id: str) -> list[str]:
    """Devuelve SKUs únicos tocados por un ImportRun.

    Patrón: ``audit_events.payload_diff->>_import_run_id == run_id``. Pim
    importer + wizard ambos escriben este marker (ver pim_importer.py linea 263
    y importer/applier.py linea 129).
    """
    stmt = text(
        """
        SELECT DISTINCT entity_id
        FROM audit_events
        WHERE entity_type = 'product'
          AND payload_diff->>'_import_run_id' = :run_id
        """
    )
    result = await session.execute(stmt, {"run_id": str(run_id)})
    return [r[0] for r in result.fetchall() if r[0]]


async def backfill(
    *,
    dry_run: bool,
    default_codes: list[str],
) -> dict[str, Any]:
    """Ejecuta el backfill. Devuelve dict con counts agregados."""
    sm = get_sessionmaker()
    summary: dict[str, Any] = {
        "runs_scanned": 0,
        "runs_skipped_no_codes": 0,
        "skus_processed": 0,
        "links_created": 0,
        "per_run": [],
    }

    async with sm() as session:
        # 1) Listar todos los import_runs PIM (cualquier estado — un run que
        #    falló a mitad camino igual tocó algunos SKUs antes del crash).
        stmt = (
            select(ImportRun)
            .where(ImportRun.import_type == "pim")
            .order_by(ImportRun.created_at.asc())
        )
        result = await session.execute(stmt)
        runs = result.scalars().all()

        summary["runs_scanned"] = len(runs)

        for run in runs:
            run_summary = run.summary or {}
            summary_codes = run_summary.get("division_codes")
            if isinstance(summary_codes, list) and summary_codes:
                codes = [str(c) for c in summary_codes if c]
                source = "run.summary"
            else:
                codes = list(default_codes)
                source = "cli_default"

            if not codes:
                summary["runs_skipped_no_codes"] += 1
                logger.info(
                    "run_id=%s SKIP (sin codes ni default).", run.id
                )
                continue

            skus = await _skus_for_run(session, str(run.id))
            run_links_created = 0
            cache: dict[str, Any] = {}
            for sku in skus:
                if dry_run:
                    # En dry-run aún resolvemos los codes para detectar errores
                    # de configuración, pero NO escribimos.
                    continue
                try:
                    n = await assign_divisions(
                        session, sku, codes, code_id_cache=cache
                    )
                    run_links_created += n
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "backfill failed sku=%s run_id=%s", sku, run.id
                    )

            if not dry_run:
                await session.commit()

            summary["skus_processed"] += len(skus)
            summary["links_created"] += run_links_created
            summary["per_run"].append(
                {
                    "run_id": str(run.id),
                    "filename": run.source_filename,
                    "status": run.status,
                    "codes_source": source,
                    "codes": codes,
                    "skus_touched": len(skus),
                    "links_created": run_links_created,
                    "dry_run": dry_run,
                }
            )
            logger.info(
                "run_id=%s codes=%s source=%s skus=%d links_created=%d dry_run=%s",
                run.id, codes, source, len(skus), run_links_created, dry_run,
            )

    return summary


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="No escribe en BD; sólo reporta counts esperados.",
    )
    p.add_argument(
        "--default-divisions",
        type=str,
        default="",
        help=(
            "Lista comma-sep de division codes a usar cuando el run no "
            "trae summary.division_codes. Ej: 'hidrosanitario' o "
            "'hidrosanitario,industrial'."
        ),
    )
    return p.parse_args()


async def _main() -> None:
    args = _parse_args()
    default_codes: list[str] = [
        c.strip() for c in (args.default_divisions or "").split(",") if c.strip()
    ]
    logger.info(
        "Starting backfill dry_run=%s default_codes=%s",
        args.dry_run, default_codes,
    )
    result = await backfill(dry_run=args.dry_run, default_codes=default_codes)
    logger.info("=" * 60)
    logger.info("BACKFILL SUMMARY (dry_run=%s):", args.dry_run)
    logger.info("  runs_scanned         = %d", result["runs_scanned"])
    logger.info("  runs_skipped_no_codes= %d", result["runs_skipped_no_codes"])
    logger.info("  skus_processed       = %d", result["skus_processed"])
    logger.info("  links_created        = %d", result["links_created"])
    logger.info("=" * 60)
    for entry in result["per_run"]:
        logger.info(
            "  run %s | %s | codes=%s (%s) | skus=%d | created=%d",
            entry["run_id"][:8],
            entry["status"],
            entry["codes"],
            entry["codes_source"],
            entry["skus_touched"],
            entry["links_created"],
        )


if __name__ == "__main__":
    asyncio.run(_main())
