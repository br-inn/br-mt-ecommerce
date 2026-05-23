"""Scraper Amazon UAE — endpoints de control (EP-SCR-01).

Endpoints expuestos:

- ``POST /api/v1/scraper/run``       — encola batch de scraping para una lista
                                       de SKUs o todos los productos activos.
- ``GET  /api/v1/scraper/job/{id}``  — consulta estado de un job Celery.

RBAC:
- POST: requiere ``products:write``
- GET:  requiere ``products:read``

La lógica real de scraping vive en ``app.workers.tasks.scraper``. Los
endpoints sólo coordinan: resuelven SKUs activos (si no se pasan), encolan
el grupo Celery y devuelven el ``group_id`` para polling.
"""

from __future__ import annotations

import logging
from typing import Annotated

from celery.result import GroupResult
from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.comparator import BrandExtractor, CompetitorBrand
from app.db.models.user import User
from app.schemas.brand_extractor import ExtractorStatRow
from app.schemas.scraper import ScrapeJobStatus, ScrapeRunRequest, ScrapeRunResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scraper", tags=["scraper"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _resolve_skus(
    request: ScrapeRunRequest,
    session: AsyncSession,
) -> list[str]:
    """Devuelve la lista de SKUs a procesar.

    Si ``request.skus`` está vacío/None consulta todos los productos activos.
    Si ``force=False`` excluye SKUs que ya tienen candidatos recientes
    (lógica delegada al task individual por ahora — el batch siempre incluye
    todos los activos para simplificar el routing).
    """
    if request.skus:
        return request.skus

    # Importación lazy para evitar ciclo de importación en cold-start
    from app.db.models.product import Product  # type: ignore[import]

    stmt = select(Product.sku).where(Product.lifecycle_status == "active")
    result = await session.execute(stmt)
    skus = [row[0] for row in result.all()]

    if not skus:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "no_active_skus",
                "detail": "No hay productos activos para scrapear.",
            },
        )

    return skus


def _celery_group_status(group_id: str) -> ScrapeJobStatus:
    """Consulta el estado de un GroupResult de Celery."""
    from app.workers.worker import celery_app  # importación lazy

    result = GroupResult.restore(group_id, app=celery_app)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "job_not_found",
                "detail": f"No se encontró el job con id={group_id!r}. "
                "Puede haber expirado (TTL 24h) o el id es incorrecto.",
            },
        )

    total = len(result)
    completed = result.completed_count()
    failed = sum(1 for r in result.results if r.failed())

    if result.ready():
        job_status = "failed" if result.failed() else "completed"
    elif completed > 0:
        job_status = "running"
    else:
        job_status = "pending"

    return ScrapeJobStatus(
        job_id=group_id,
        completed=completed,
        total=total,
        failed=failed,
        status=job_status,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/run",
    response_model=ScrapeRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Disparar scraping Amazon UAE (EP-SCR-01)",
    description=(
        "Encola un batch de ``scrape_sku_task`` por cada SKU indicado (o todos "
        "los productos activos si ``skus`` es None). Retorna el ``job_id`` del "
        "GroupResult para consultar estado vía ``GET /scraper/job/{job_id}``."
    ),
    operation_id="scraperRun",
)
async def run_scraper(
    body: ScrapeRunRequest,
    _user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScrapeRunResponse:
    from app.workers.tasks.scraper import scrape_sku_task  # importación lazy

    skus = await _resolve_skus(body, session)

    from celery import group as celery_group

    job = celery_group(scrape_sku_task.s(sku, force=body.force) for sku in skus).apply_async(
        queue="comparator"
    )

    # Persistir el GroupResult para que pueda ser recuperado por id
    job.save()

    logger.info(
        "scraper.batch_queued",
        extra={"total_skus": len(skus), "group_id": job.id, "force": body.force},
    )

    return ScrapeRunResponse(
        job_id=job.id,
        total_skus=len(skus),
        status="queued",
    )


@router.get(
    "/job/{job_id}",
    response_model=ScrapeJobStatus,
    summary="Estado de un job de scraping (EP-SCR-01)",
    description=(
        "Consulta el estado del GroupResult de Celery identificado por "
        "``job_id``. Devuelve contadores de tasks completadas, fallidas y "
        "estado general: ``pending`` | ``running`` | ``completed`` | ``failed``."
    ),
    operation_id="scraperJobStatus",
    responses={
        404: {"description": "Job no encontrado (expirado o id incorrecto)."},
    },
)
async def get_scraper_job(
    job_id: Annotated[str, Path(min_length=1, max_length=128)],
    _user: Annotated[User, Depends(require_permissions("products:read"))],
) -> ScrapeJobStatus:
    return _celery_group_status(job_id)


@router.get(
    "/extractor-stats",
    response_model=list[ExtractorStatRow],
    summary="Estadísticas de extractores de marcas (US-SCR-05-03)",
    description=(
        "Lista todos los extractores generados ordenados por hit_rate ASC "
        "(primero los de menor cobertura). JOIN con competitor_brands para "
        "incluir el nombre de la marca."
    ),
    operation_id="listExtractorStats",
)
async def list_extractor_stats(
    _user: Annotated[User, Depends(require_permissions("scraper:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[ExtractorStatRow]:
    stmt = (
        select(
            BrandExtractor.brand_id,
            CompetitorBrand.name.label("brand_name"),
            BrandExtractor.marketplace,
            BrandExtractor.hit_rate,
            BrandExtractor.generated_at,
            BrandExtractor.attribute_map,
        )
        .join(CompetitorBrand, BrandExtractor.brand_id == CompetitorBrand.id)
        .order_by(BrandExtractor.hit_rate.asc())
    )
    result = await session.execute(stmt)
    rows = result.all()
    return [
        ExtractorStatRow(
            brand_id=row.brand_id,
            brand_name=row.brand_name,
            marketplace=row.marketplace,
            hit_rate=float(row.hit_rate),
            generated_at=row.generated_at,
            attribute_count=len(row.attribute_map or {}),
        )
        for row in rows
    ]
