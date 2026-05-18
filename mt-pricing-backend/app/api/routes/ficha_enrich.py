"""Ficha técnica enrichment endpoints — Multi-SKU por serie.

POST /products/{sku}/ficha-enrich/preview
    Detecta la serie desde el filename (MTFT_4097.pdf → "4097"),
    busca todos los SKUs matching, devuelve diffs por SKU.

POST /products/{sku}/ficha-enrich/apply
    Aplica campos seleccionados a la lista de SKUs indicada.
"""
from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Path, UploadFile
from sqlalchemy import select as _sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.product import Product
from app.db.models.user import User
from app.schemas.common import ProblemDetails
from app.schemas.ficha_enrich import (
    FichaEnrichApplyRequest,
    FichaEnrichApplyResponse,
    FichaEnrichPreviewResponse,
    FichaSeriesApplyRequest,
    FichaSeriesApplyResponse,
    FichaSeriesPreviewResponse,
    SkuApplyResult,
    SkuDiffResult,
)
from app.services.ficha_enrichment import (
    FichaEnrichmentApplier,
    FichaEnrichmentDiffer,
    FichaEnrichmentExtractor,
)
from app.services.ficha_enrichment.document_saver import save_ficha_document
from app.services.ficha_enrichment.product_creator import create_product_from_extraction
from app.services.ficha_enrichment.series_resolver import (
    extract_series_prefix,
    resolve_all_series,
    resolve_series,
)
from app.services.importer_datasheets.pdf_extractor import extract_pdf_metadata

router = APIRouter(tags=["products", "ficha-enrich"])

_MAX_PDF_BYTES = 50 * 1024 * 1024  # 50 MB


def _extract_series_prefix(filename: str, anchor_sku: str) -> str:
    """Extrae el prefijo de serie: MTFT_4097.pdf → '4097'. Fallback: primeros N-3 chars del SKU."""
    match = re.search(r'MTFT[_\-]?(\d+)', filename, re.IGNORECASE)
    if match:
        return match.group(1)
    # Fallback: asume que los últimos 3 dígitos son el tamaño (ej. 015 = DN15)
    return anchor_sku[:-3] if len(anchor_sku) > 3 else anchor_sku


async def _find_series_products(session: AsyncSession, prefix: str) -> list[Product]:
    """Busca todos los productos cuyo SKU empieza con el prefijo de serie."""
    result = await session.execute(
        _sa_select(Product)
        .where(Product.sku.like(f"{prefix}%"))
        .order_by(Product.sku)
    )
    return list(result.scalars().all())


async def _load_product_or_404(session: AsyncSession, sku: str) -> Product:
    result = await session.execute(_sa_select(Product).where(Product.sku == sku))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "product_not_found", "title": f"SKU {sku!r} no encontrado"},
        )
    return product


@router.post(
    "/products/{sku}/ficha-enrich/preview",
    response_model=FichaEnrichPreviewResponse,
    summary="Extraer campos de ficha técnica PDF — diffs para toda la serie",
    responses={
        404: {"model": ProblemDetails},
        413: {"model": ProblemDetails, "description": "PDF > 50 MB"},
        422: {"model": ProblemDetails},
    },
)
async def preview_ficha_enrich(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    file: Annotated[UploadFile, File(description="PDF de ficha técnica (≤ 50 MB)")],
    _user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FichaEnrichPreviewResponse:
    if file.filename is None:
        raise HTTPException(status_code=422, detail={"code": "missing_filename", "title": "Filename requerido"})

    pdf_bytes = await file.read()
    if len(pdf_bytes) > _MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail={"code": "pdf_too_large", "title": "PDF > 50 MB"})
    if not pdf_bytes.lstrip().startswith(b"%PDF"):
        raise HTTPException(status_code=422, detail={"code": "not_a_pdf", "title": "El archivo no es un PDF válido"})

    # Verificar que el SKU anchor existe
    anchor = await _load_product_or_404(session, sku)

    # Detectar serie y buscar todos los SKUs matching
    series = _extract_series_prefix(file.filename, sku)
    products = await _find_series_products(session, series)
    if not products:
        products = [anchor]  # fallback: solo el anchor

    # Extracción Claude (una sola vez para toda la serie)
    extractor = FichaEnrichmentExtractor()
    extraction = await extractor.extract(pdf_bytes=pdf_bytes, filename=file.filename)

    # Diff por SKU
    differ = FichaEnrichmentDiffer()
    series_skus = differ.compute_batch(products, extraction)

    meta = extract_pdf_metadata(pdf_bytes)

    return FichaEnrichPreviewResponse(
        sku=sku,
        series=series,
        filename=file.filename,
        extraction=extraction,
        series_skus=series_skus,
        model_gaps=extraction.model_gaps,
        page_count=meta.get("page_count", 0),
        confidence=extraction.confidence,
    )


@router.post(
    "/products/{sku}/ficha-enrich/apply",
    response_model=FichaEnrichApplyResponse,
    summary="Aplicar campos extraídos a todos los SKUs seleccionados de la serie",
    responses={
        404: {"model": ProblemDetails},
    },
)
async def apply_ficha_enrich(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    body: FichaEnrichApplyRequest,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FichaEnrichApplyResponse:
    if not body.apply_to_skus:
        raise HTTPException(status_code=422, detail={"code": "no_skus", "title": "apply_to_skus no puede estar vacío"})

    series = _extract_series_prefix(body.apply_to_skus[0], sku)
    results: list[SkuApplyResult] = []

    for target_sku in body.apply_to_skus:
        try:
            applier = FichaEnrichmentApplier(session)
            result = await applier.apply(target_sku, body, user)
            results.append(result)
        except HTTPException as exc:
            if exc.status_code == 404:
                results.append(SkuApplyResult(
                    sku=target_sku,
                    applied_fields=[],
                    skipped_fields=[],
                    warnings=[f"SKU no encontrado"],
                ))
            else:
                raise

    return FichaEnrichApplyResponse(series=series, results=results)


@router.post(
    "/ficha-enrich/series/preview",
    response_model=FichaSeriesPreviewResponse,
    summary="Vista previa serie completa — detecta SKUs existentes y nuevos desde el PDF",
    responses={
        422: {"model": ProblemDetails},
        413: {"model": ProblemDetails},
    },
)
async def preview_ficha_series(
    file: Annotated[UploadFile, File(description="PDF ficha técnica (≤ 50 MB)")],
    _user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FichaSeriesPreviewResponse:
    if file.filename is None:
        raise HTTPException(status_code=422, detail={"code": "missing_filename", "title": "Filename requerido"})

    pdf_bytes = await file.read()
    if len(pdf_bytes) > _MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail={"code": "pdf_too_large", "title": "PDF > 50 MB"})
    if not pdf_bytes.lstrip().startswith(b"%PDF"):
        raise HTTPException(status_code=422, detail={"code": "not_a_pdf", "title": "No es un PDF válido"})

    filename_series = extract_series_prefix(file.filename)

    extractor = FichaEnrichmentExtractor()
    extraction = await extractor.extract(pdf_bytes=pdf_bytes, filename=file.filename)

    meta = extract_pdf_metadata(pdf_bytes)
    pdf_text: str = meta.get("text", "") or ""

    series_groups = await resolve_all_series(
        session, pdf_text, extraction, filename_prefix=filename_series
    )

    if not series_groups:
        if not filename_series:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "no_series",
                    "title": "No se pudo detectar la serie. Formato esperado: MTFT_XXXX.pdf",
                },
            )
        series_skus = await resolve_series(session, filename_series, extraction)
        primary_series = filename_series
        detected_series: list[str] = [filename_series]
    else:
        # Flatten all SKUs for backward-compat series_skus field
        flat: list[SkuDiffResult] = []
        for g in series_groups:
            flat.extend(g.base_skus)
            flat.extend(g.variant_skus)
        series_skus = flat
        primary_series = series_groups[0].base_series
        detected_series = []
        for g in series_groups:
            detected_series.append(g.base_series)
            if g.variant_series:
                detected_series.append(g.variant_series)

    return FichaSeriesPreviewResponse(
        series=primary_series,
        filename=file.filename,
        extraction=extraction,
        series_skus=series_skus,
        series_groups=series_groups,
        detected_series=detected_series,
        model_gaps=extraction.model_gaps,
        page_count=meta.get("page_count", 0),
        confidence=extraction.confidence,
    )


@router.post(
    "/ficha-enrich/series/apply",
    response_model=FichaSeriesApplyResponse,
    summary="Aplicar ficha técnica — crea SKUs nuevos + actualiza existentes + guarda Document",
    responses={
        422: {"model": ProblemDetails},
    },
)
async def apply_ficha_series(
    body: FichaSeriesApplyRequest,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FichaSeriesApplyResponse:
    if not body.apply_to_skus:
        raise HTTPException(status_code=422, detail={"code": "no_skus", "title": "apply_to_skus vacío"})

    results: list[SkuApplyResult] = []
    skus_created: list[str] = []
    skus_updated: list[str] = []

    # Determinar cuáles existen
    from sqlalchemy import select as _select
    existing_result = await session.execute(
        _select(Product).where(Product.sku.in_(body.apply_to_skus))
    )
    existing_skus = {p.sku for p in existing_result.scalars().all()}

    for target_sku in body.apply_to_skus:
        if target_sku in existing_skus:
            try:
                applier = FichaEnrichmentApplier(session)
                result = await applier.apply(target_sku, body, user)
                results.append(result)
                skus_updated.append(target_sku)
            except HTTPException as exc:
                results.append(SkuApplyResult(
                    sku=target_sku, applied_fields=[], skipped_fields=[],
                    warnings=[f"Error {exc.status_code}: {exc.detail}"],
                ))
        else:
            variant_of = body.variant_links.get(target_sku)
            result = await create_product_from_extraction(
                session,
                target_sku,
                body.extraction,
                is_variant=variant_of is not None,
                display_pair_sku=variant_of,
                actor=user,
            )
            results.append(result)
            if not result.warnings:
                skus_created.append(target_sku)

    # Write model-level data (dimensions, P/T curves, certificates, flow data)
    from app.services.ficha_enrichment.model_writer import write_model_data
    await write_model_data(session, body.series, body.extraction, variant_series=body.variant_series)

    document_id: str | None = None
    if body.save_document and body.pdf_filename:
        all_processed_skus = skus_created + skus_updated
        document_id = await save_ficha_document(
            session=session,
            pdf_bytes=b"",  # PDF bytes not re-sent in apply; document saved without binary
            filename=body.pdf_filename,
            series=body.series,
            skus=all_processed_skus,
        )

    await session.commit()

    return FichaSeriesApplyResponse(
        series=body.series,
        results=results,
        document_id=document_id,
        skus_created=skus_created,
        skus_updated=skus_updated,
    )


__all__ = ["router"]
