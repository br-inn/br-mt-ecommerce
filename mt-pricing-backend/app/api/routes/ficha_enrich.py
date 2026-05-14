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
    SkuApplyResult,
)
from app.services.ficha_enrichment import (
    FichaEnrichmentApplier,
    FichaEnrichmentDiffer,
    FichaEnrichmentExtractor,
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


__all__ = ["router"]
