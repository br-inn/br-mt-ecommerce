#!/usr/bin/env python3
"""ficha_bulk_runner.py — Bulk enrichment desde fichas técnicas PDF.

Procesa PDFs en FICHAS_DIR:
1. Extrae datos estructurados con Claude (FichaEnrichmentExtractor)
2. Resuelve los SKUs correspondientes por serie desde el PDF y la BD
3. Crea SKUs nuevos si no existen; actualiza los existentes
4. Extrae y sube imágenes (dibujos, secciones) a Supabase Storage
5. Guarda Document de referencia por PDF
6. Guarda progreso en JSON para poder reanudar (--resume)

Uso dentro del contenedor:
  # Copiar fichas al contenedor (una sola vez):
  docker cp "Documentos referencia de articulos/FICHAS TÉCNICAS" \\
      mt-backend:/tmp/fichas

  # Copiar este script:
  docker cp scripts/ficha_bulk_runner.py mt-backend:/tmp/ficha_bulk_runner.py

  # Test con un solo PDF:
  docker exec mt-backend python /tmp/ficha_bulk_runner.py --test MTFT_0910.pdf

  # Procesar todos:
  docker exec mt-backend python /tmp/ficha_bulk_runner.py

  # Reanudar desde donde quedó:
  docker exec mt-backend python /tmp/ficha_bulk_runner.py --resume

  # Modo rápido (sin imágenes, sin page classification):
  docker exec mt-backend python /tmp/ficha_bulk_runner.py --no-images
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import text

sys.path.insert(0, "/app")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

FICHAS_DIR = "/tmp/fichas"
PROGRESS_FILE = "/tmp/ficha_bulk_progress.json"
DELAY_BETWEEN_PDFS = 2.0   # segundos entre PDFs (respetar rate limits de Claude)
MAX_PAGES_FOR_IMAGES = 8   # máximo de páginas a clasificar para imágenes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ficha_bulk")


# ---------------------------------------------------------------------------
# Progreso
# ---------------------------------------------------------------------------

@dataclass
class Progress:
    done: set[str] = field(default_factory=set)
    failed: dict[str, str] = field(default_factory=dict)

    def save(self) -> None:
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {"done": sorted(self.done), "failed": self.failed},
                f, indent=2, ensure_ascii=False,
            )

    @classmethod
    def load(cls) -> "Progress":
        if not os.path.exists(PROGRESS_FILE):
            return cls()
        try:
            with open(PROGRESS_FILE, encoding="utf-8") as f:
                data = json.load(f)
            return cls(
                done=set(data.get("done", [])),
                failed=dict(data.get("failed", {})),
            )
        except Exception:
            return cls()


# ---------------------------------------------------------------------------
# Mapping de MTFT_XXXX.pdf → series prefix
# ---------------------------------------------------------------------------

def pdf_to_series_prefix(filename: str) -> str | None:
    """MTFT_0910.pdf → '0910', MTFT_01A.pdf → '01A', MTFT_S09014.pdf → 'S09014'."""
    # Numeric with optional trailing alpha suffix: MTFT_NNNN.pdf, MTFT_NNNAx.pdf
    # e.g. "MTFT_01A" → "01A" (not just "01") to avoid LIKE '01%' over-matching.
    m = re.search(r"MTFT[_\-]?(\d+[A-Za-z]*)", filename, re.IGNORECASE)
    if m:
        return m.group(1)
    # Pure alpha prefix: MTFT_S09014.pdf, MTFT_AGMA.pdf, etc.
    m2 = re.search(r"MTFT[_\-]?([A-Za-z]\w+)", filename, re.IGNORECASE)
    if m2:
        return m2.group(1)
    return None


# ---------------------------------------------------------------------------
# Core processor — un PDF a la vez
# ---------------------------------------------------------------------------

async def process_one_pdf(
    pdf_path: Path,
    session_factory: Any,
    actor: Any,
    *,
    classify_pages: bool = True,
    apply_images: bool = True,
) -> dict[str, Any]:
    """Extrae datos del PDF y los aplica a la BD.

    Retorna un resumen con:
      filename, series, skus_updated, skus_created, warnings, confidence
    """
    filename = pdf_path.name
    series_prefix = pdf_to_series_prefix(filename)

    logger.info("▶ %s  (series=%s)", filename, series_prefix or "?")

    # Leer PDF
    try:
        pdf_bytes = pdf_path.read_bytes()
    except Exception as exc:
        return {"filename": filename, "error": f"read_failed: {exc}"}

    if not pdf_bytes.lstrip().startswith(b"%PDF"):
        return {"filename": filename, "error": "not_a_pdf"}
    if len(pdf_bytes) < 1000:
        return {"filename": filename, "error": "pdf_too_small"}

    # Extraer texto del PDF una sola vez (el extractor también lo llama internamente,
    # pero necesitamos el texto completo para detect_series_from_text).
    from app.services.importer_datasheets.pdf_extractor import extract_pdf_metadata
    from app.services.ficha_enrichment.series_resolver import (
        extract_all_series_from_text,
        resolve_all_series,
        resolve_series,
        generate_candidate_skus,
    )

    logger.info("  parsing PDF text...")
    t_meta = time.time()
    try:
        meta = extract_pdf_metadata(pdf_bytes)
        pdf_text: str = meta.get("text", "") or ""
    except Exception:
        pdf_text = ""
    logger.info("  pdf_text len=%d  (%.1fs)", len(pdf_text), time.time() - t_meta)

    # Extracción con Claude
    from app.services.ficha_enrichment.extractor import FichaEnrichmentExtractor

    extractor = FichaEnrichmentExtractor()
    t0 = time.time()
    try:
        extraction = await extractor.extract(
            pdf_bytes=pdf_bytes,
            filename=filename,
            classify_pages=classify_pages and apply_images,
        )
    except Exception as exc:
        logger.error("extraction failed %s: %s", filename, exc)
        return {"filename": filename, "error": f"extraction_failed: {type(exc).__name__}: {exc}"}

    elapsed_extract = time.time() - t0
    logger.info(
        "  extracted: confidence=%.2f  gaps=%d  (%.1fs)",
        extraction.confidence, len(extraction.model_gaps), elapsed_extract,
    )

    # Skip apply when the extraction has near-zero confidence (image scans,
    # non-datasheet PDFs, or API failures) to avoid overwriting good DB data.
    MIN_CONFIDENCE = 0.05
    if extraction.confidence < MIN_CONFIDENCE:
        logger.warning(
            "  skipping apply: confidence=%.2f below %.2f",
            extraction.confidence, MIN_CONFIDENCE,
        )
        return {
            "filename": filename,
            "series": series_prefix,
            "confidence": extraction.confidence,
            "skus_created": [],
            "skus_updated": [],
            "warnings": [
                f"confidence={extraction.confidence:.2f} below "
                f"threshold={MIN_CONFIDENCE} — apply skipped"
            ],
            "model_gaps": [],
        }

    skus_created: list[str] = []
    skus_updated: list[str] = []
    all_warnings: list[str] = []

    # Paso 1: resolver grupos de series (lectura rápida, sin modificar nada)
    # Retries por ConnectionDoesNotExist / QueryCanceledError de PgBouncer.
    logger.info("  resolving series groups...")
    series_groups = []
    for _attempt in range(3):
        try:
            async with session_factory() as session:
                async with session.begin():
                    await session.execute(text("SET LOCAL statement_timeout = 0"))
                    await session.execute(text("SET LOCAL lock_timeout = '60s'"))
                    series_groups = await resolve_all_series(
                        session, pdf_text, extraction, filename_prefix=series_prefix
                    )
            break
        except Exception as exc:
            logger.warning("  resolve_all_series failed (attempt %d): %s", _attempt + 1, exc)
            if _attempt == 2:
                logger.warning("  falling back to filename prefix only")

    if not series_groups and series_prefix:
        series_groups_list = [(series_prefix, None)]
    else:
        series_groups_list = [
            (g.base_series, g.variant_series) for g in series_groups
        ]
    logger.info("  series groups: %s", series_groups_list)

    # Paso 2: aplicar por serie — cada SKU en su propia transacción
    # para evitar que un timeout o error rompa toda la operación.
    for base_series, variant_series in series_groups_list:
        for current_series in filter(None, [base_series, variant_series]):
            logger.info("  applying series %s ...", current_series)
            await _apply_series(
                session_factory,
                current_series,
                extraction,
                pdf_bytes if apply_images else b"",
                actor,
                skus_created,
                skus_updated,
                all_warnings,
            )
            logger.info("  series %s done (+%d created, +%d updated)",
                        current_series, len(skus_created), len(skus_updated))

    # Paso 3: datos de modelo (dimensiones, P/T curves, certs, flow)
    logger.info("  writing model data...")
    primary_series = series_groups_list[0][0] if series_groups_list else (series_prefix or "")
    variant_series_primary = series_groups_list[0][1] if series_groups_list else None
    async with session_factory() as session:
        async with session.begin():
            await session.execute(text("SET LOCAL statement_timeout = 0"))
            from app.services.ficha_enrichment.model_writer import write_model_data
            try:
                await write_model_data(
                    session, primary_series, extraction,
                    variant_series=variant_series_primary,
                )
            except Exception as exc:
                logger.warning("write_model_data failed %s: %s", filename, exc)
                all_warnings.append(f"model_data: {exc}")

    # Paso 4: guardar referencia al documento PDF
    logger.info("  saving document reference...")
    all_skus = skus_created + skus_updated
    if all_skus:
        async with session_factory() as session:
            async with session.begin():
                await session.execute(text("SET LOCAL statement_timeout = 0"))
                try:
                    from app.services.ficha_enrichment.document_saver import save_ficha_document
                    await save_ficha_document(
                        session=session,
                        pdf_bytes=pdf_bytes,
                        filename=filename,
                        series=series_prefix or primary_series,
                        skus=all_skus,
                    )
                except Exception as exc:
                    logger.warning("save_ficha_document failed %s: %s", filename, exc)

    logger.info("  done ✓")

    return {
        "filename": filename,
        "series": series_prefix,
        "confidence": extraction.confidence,
        "skus_created": skus_created,
        "skus_updated": skus_updated,
        "warnings": all_warnings,
        "model_gaps": extraction.model_gaps[:5],
    }


async def _apply_series(
    session_factory: Any,
    series_prefix: str,
    extraction: Any,
    pdf_bytes: bytes,
    actor: Any,
    skus_created: list[str],
    skus_updated: list[str],
    all_warnings: list[str],
) -> None:
    """Aplica extraction a todos los SKUs de la serie (existentes + nuevos candidatos).

    Cada SKU corre en su propia transacción con statement_timeout = 0 para
    evitar que un timeout de PG o un error de un SKU corrompa los demás.
    """
    from sqlalchemy import select as _select
    from app.db.models.product import Product
    from app.services.ficha_enrichment.applier import FichaEnrichmentApplier
    from app.services.ficha_enrichment.product_creator import create_product_from_extraction
    from app.services.ficha_enrichment.series_resolver import generate_candidate_skus
    from app.schemas.ficha_enrich import FichaEnrichApplyRequest

    # Candidatos generados desde tablas de dimensiones del PDF
    candidate_skus = generate_candidate_skus(series_prefix, extraction)

    # Fase 1: consulta de solo lectura — qué SKUs existen ya en BD
    # Retries por ConnectionDoesNotExist / statement_timeout de PgBouncer.
    existing_sku_set: set[str] = set()
    for _attempt in range(3):
        try:
            async with session_factory() as session:
                async with session.begin():
                    await session.execute(text("SET LOCAL statement_timeout = 0"))
                    await session.execute(text("SET LOCAL lock_timeout = '60s'"))
                    existing_result = await session.execute(
                        _select(Product.sku)
                        .where(Product.sku.like(f"{series_prefix}%"))
                        .order_by(Product.sku)
                    )
                    existing_sku_set = {row[0] for row in existing_result.all()}
            break
        except Exception as exc:
            logger.warning("  SKU query failed (attempt %d): %s", _attempt + 1, exc)
            if _attempt == 2:
                raise

    # SKUs a procesar = candidatos + existentes
    all_target_skus = sorted(set(candidate_skus) | existing_sku_set)

    if not all_target_skus:
        logger.debug("  no SKUs for series %s", series_prefix)
        return

    # apply_request describe QUÉ campos actualizar (igual para todos los SKUs)
    apply_request = FichaEnrichApplyRequest(
        extraction=extraction,
        apply_to_skus=all_target_skus,
        apply_scalars=True,
        apply_specs=True,
        apply_materials=True,
        apply_dimensions=True,
        apply_translations=True,
        apply_assets=bool(pdf_bytes) and bool(extraction.extracted_assets),
        apply_pt_curve=bool(extraction.pt_curve_points),
    )

    # Fase 2: una transacción por SKU para aislar fallos
    total_skus = len(all_target_skus)
    logger.info("  series %s: %d SKUs to process", series_prefix, total_skus)
    for sku_idx, target_sku in enumerate(all_target_skus):
        if sku_idx % 10 == 0 or sku_idx == total_skus - 1:
            logger.info("  [%d/%d] %s", sku_idx + 1, total_skus, target_sku)
        if target_sku in existing_sku_set:
            # Producto existente → actualizar
            try:
                async with session_factory() as session:
                    async with session.begin():
                        await session.execute(text("SET LOCAL statement_timeout = 0"))
                        await session.execute(text("SET LOCAL lock_timeout = '60s'"))
                        applier = FichaEnrichmentApplier(session)
                        result = await applier.apply(
                            target_sku, apply_request, actor, pdf_bytes=pdf_bytes
                        )
                if result.warnings:
                    all_warnings.extend([f"{target_sku}: {w}" for w in result.warnings])
                skus_updated.append(target_sku)
                logger.debug("  updated %s: %s", target_sku, result.applied_fields)
            except Exception as exc:
                logger.warning("  apply failed %s: %s", target_sku, exc)
                all_warnings.append(f"{target_sku}: {exc}")
        else:
            # SKU nuevo → crear
            try:
                async with session_factory() as session:
                    async with session.begin():
                        await session.execute(text("SET LOCAL statement_timeout = 0"))
                        await session.execute(text("SET LOCAL lock_timeout = '60s'"))
                        result = await create_product_from_extraction(
                            session, target_sku, extraction, is_variant=False, actor=actor,
                        )
                if result.warnings:
                    all_warnings.extend([f"{target_sku}(new): {w}" for w in result.warnings])
                if not result.warnings:
                    skus_created.append(target_sku)
                    logger.debug("  created %s", target_sku)
            except Exception as exc:
                logger.warning("  create failed %s: %s", target_sku, exc)
                all_warnings.append(f"{target_sku}(new): {exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk ficha enrichment")
    parser.add_argument("--test", metavar="FILENAME",
                        help="Procesar solo este archivo PDF (modo validación)")
    parser.add_argument("--resume", action="store_true",
                        help="Saltar PDFs ya procesados según " + PROGRESS_FILE)
    parser.add_argument("--no-images", action="store_true",
                        help="No extraer ni subir imágenes (más rápido)")
    parser.add_argument("--dir", default=FICHAS_DIR, metavar="PATH",
                        help=f"Directorio con PDFs (default: {FICHAS_DIR})")
    args = parser.parse_args()

    fichas_dir = Path(args.dir)
    if not fichas_dir.is_dir():
        print(f"ERROR: {fichas_dir} no existe. Copiar fichas primero:")
        print(f'  docker cp "Documentos referencia de articulos/FICHAS TÉCNICAS" mt-backend:/tmp/fichas')
        sys.exit(1)

    # Listar PDFs
    all_pdfs = sorted(p for p in fichas_dir.iterdir()
                      if p.suffix.lower() == ".pdf" and p.name.startswith("MTFT_"))
    if not all_pdfs:
        print(f"ERROR: no se encontraron archivos MTFT_*.pdf en {fichas_dir}")
        sys.exit(1)

    # Modo test: solo un archivo
    if args.test:
        test_path = fichas_dir / args.test
        if not test_path.exists():
            print(f"ERROR: {test_path} no encontrado")
            sys.exit(1)
        all_pdfs = [test_path]

    # Cargar progreso
    progress = Progress.load() if args.resume else Progress()

    to_process = [p for p in all_pdfs if p.name not in progress.done]
    if args.resume:
        skipped = len(all_pdfs) - len(to_process)
        logger.info("Reanudando: %d ya procesados, %d pendientes", skipped, len(to_process))

    print("=" * 65)
    print(f"Ficha Bulk Runner — {len(to_process)} PDFs a procesar")
    print(f"Directorio : {fichas_dir}")
    print(f"Imágenes   : {'NO' if args.no_images else 'SÍ (classify_pages)'}")
    print("=" * 65)

    # Obtener session factory y actor
    from app.db.engine import get_sessionmaker
    from app.db.models.user import User
    from sqlalchemy import select

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        result = await session.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        if user is None:
            print("ERROR: no hay usuarios en la BD")
            sys.exit(1)
    actor = user
    print(f"Actor      : {actor.email}")

    # Procesar
    total_created = 0
    total_updated = 0
    total_errors = 0
    t_global = time.time()

    for i, pdf_path in enumerate(to_process, 1):
        pct = (i / len(to_process)) * 100
        print(f"\n[{i:>3}/{len(to_process)}  {pct:>5.1f}%]  {pdf_path.name}")

        try:
            summary = await process_one_pdf(
                pdf_path,
                session_factory,
                actor,
                classify_pages=not args.no_images,
                apply_images=not args.no_images,
            )
        except Exception as exc:
            logger.exception("FATAL for %s", pdf_path.name)
            summary = {"filename": pdf_path.name, "error": str(exc)[:200]}

        if "error" in summary:
            total_errors += 1
            progress.failed[pdf_path.name] = summary["error"]
            print(f"  ✗ ERROR: {summary['error']}")
        else:
            nc = len(summary.get("skus_created", []))
            nu = len(summary.get("skus_updated", []))
            total_created += nc
            total_updated += nu
            progress.done.add(pdf_path.name)
            print(
                f"  ✓ series={summary.get('series','?')}  "
                f"created={nc}  updated={nu}  "
                f"conf={summary.get('confidence', 0):.2f}  "
                f"warns={len(summary.get('warnings', []))}"
            )
            if summary.get("warnings"):
                for w in summary["warnings"][:3]:
                    print(f"    ⚠ {w}")

        # Guardar progreso después de cada PDF
        if not args.test:
            progress.save()

        # Delay entre PDFs para respetar rate limits de Claude API
        if i < len(to_process):
            await asyncio.sleep(DELAY_BETWEEN_PDFS)

    elapsed = time.time() - t_global
    print("\n" + "=" * 65)
    print(f"COMPLETADO en {elapsed:.0f}s")
    print(f"  SKUs creados   : {total_created}")
    print(f"  SKUs actualizados : {total_updated}")
    print(f"  Errores        : {total_errors}")
    if progress.failed:
        print(f"\n  PDFs con error ({len(progress.failed)}):")
        for fn, err in list(progress.failed.items())[:10]:
            print(f"    {fn}: {err}")
    print("=" * 65)


def _asyncio_exception_handler(loop: asyncio.AbstractEventLoop, context: dict) -> None:
    # Suppress all asyncpg background task errors (connection monitoring,
    # cleanup, cancellation) — these are noisy but don't affect correctness
    # since each SKU runs in its own isolated transaction with error handling.
    exc = context.get("exception")
    msg = context.get("message", "")
    exc_module = getattr(type(exc), "__module__", "") if exc else ""
    exc_name = type(exc).__name__ if exc else ""
    if "asyncpg" in exc_module or "asyncpg" in exc_name:
        return
    if "connection" in msg.lower():
        return
    if "Task was destroyed but it is pending" in msg:
        return
    loop.default_exception_handler(context)


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.set_exception_handler(_asyncio_exception_handler)
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    finally:
        loop.close()
