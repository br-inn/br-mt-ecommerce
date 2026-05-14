# mt-pricing-backend/app/api/routes/ficha_enrich.py
"""Ficha técnica enrichment endpoints.

POST /products/{sku}/ficha-enrich/preview   — sube PDF, extrae campos, compara con producto.
POST /products/{sku}/ficha-enrich/apply     — aplica campos seleccionados al producto.
"""
from __future__ import annotations

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
)
from app.services.ficha_enrichment import (
    FichaEnrichmentApplier,
    FichaEnrichmentDiffer,
    FichaEnrichmentExtractor,
)

router = APIRouter(tags=["products", "ficha-enrich"])

_MAX_PDF_BYTES = 50 * 1024 * 1024  # 50 MB


@router.post(
    "/products/{sku}/ficha-enrich/preview",
    response_model=FichaEnrichPreviewResponse,
    summary="Extraer campos de ficha técnica PDF y comparar con producto",
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

    product = await _load_product_or_404(session, sku)

    extractor = FichaEnrichmentExtractor()
    extraction = await extractor.extract(pdf_bytes=pdf_bytes, filename=file.filename)

    differ = FichaEnrichmentDiffer()
    diffs = differ.compute(product, extraction)

    from app.services.importer_datasheets.pdf_extractor import extract_pdf_metadata
    meta = extract_pdf_metadata(pdf_bytes)

    return FichaEnrichPreviewResponse(
        sku=sku,
        filename=file.filename,
        extraction=extraction,
        diffs=diffs,
        model_gaps=extraction.model_gaps,
        page_count=meta.get("page_count", 0),
        confidence=extraction.confidence,
    )


@router.post(
    "/products/{sku}/ficha-enrich/apply",
    response_model=FichaEnrichApplyResponse,
    summary="Aplicar campos extraídos de ficha técnica al producto",
    responses={
        404: {"model": ProblemDetails},
        409: {"model": ProblemDetails, "description": "Campo bloqueado manualmente"},
    },
)
async def apply_ficha_enrich(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    body: FichaEnrichApplyRequest,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FichaEnrichApplyResponse:
    await _load_product_or_404(session, sku)
    applier = FichaEnrichmentApplier(session)
    return await applier.apply(sku, body, user)


async def _load_product_or_404(session: AsyncSession, sku: str) -> Product:
    result = await session.execute(_sa_select(Product).where(Product.sku == sku))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "product_not_found", "title": f"SKU {sku!r} no encontrado"},
        )
    return product


__all__ = ["router"]
