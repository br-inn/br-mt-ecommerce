"""Competitor Brands — gestión de marcas competidoras + trigger de scraping."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.comparator import BrandExtractor, ExtractorAlert
from app.db.models.user import User
from app.repositories.competitor_brands import CompetitorBrandRepository
from app.schemas.brand_extractor import BrandExtractorRead, ExtractorCoverageStats
from app.schemas.competitor_brands import (
    BrandScrapeRunRequest,
    BrandScrapeRunResponse,
    CompetitorBrandCreate,
    CompetitorBrandRead,
    CompetitorBrandUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/competitor-brands", tags=["competitor-brands"])


@router.post(
    "/",
    response_model=CompetitorBrandRead,
    status_code=status.HTTP_201_CREATED,
    operation_id="createCompetitorBrand",
)
async def create_brand(
    body: CompetitorBrandCreate,
    _user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CompetitorBrandRead:
    repo = CompetitorBrandRepository(session)
    existing = await repo.get_by_name(body.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "duplicate_name", "detail": f"Brand '{body.name}' ya existe."},
        )
    brand = await repo.create(
        name=body.name,
        amazon_search_term=body.amazon_search_term,
        amazon_dept=body.amazon_dept,
        amazon_category_node=body.amazon_category_node,
        is_active=body.is_active,
        notes=body.notes,
    )

    # US-SCR-04-04 — Auto-crear job_definition para scraping diario de esta marca
    await _auto_create_brand_job(session, brand_name=body.name, brand_id=str(brand.id))

    await session.commit()
    return CompetitorBrandRead.model_validate(brand)


async def _auto_create_brand_job(session: AsyncSession, brand_name: str, brand_id: str) -> None:
    """Crea un job_definition de scraping diario para la nueva marca competidora.

    Usa ON CONFLICT DO NOTHING para idempotencia (código único por marca).
    """
    from sqlalchemy import text

    safe_name = brand_name.lower().replace(" ", "_").replace("-", "_")[:40]
    job_code = f"scrape_brand_{safe_name}"

    try:
        await session.execute(
            text("""
                INSERT INTO job_definitions (
                    code, task_name, description, owner, schedule_type,
                    cron_expression, queue, kwargs, enabled
                )
                VALUES (
                    :code,
                    'mt.scraper.scrape_brand',
                    :description,
                    'business',
                    'cron',
                    '0 2 * * *',
                    'scraper',
                    CAST(:kwargs AS jsonb),
                    true
                )
                ON CONFLICT (code) DO NOTHING
            """),
            {
                "code": job_code,
                "description": f"Scraping diario de marca competidora '{brand_name}' en Amazon UAE.",
                "kwargs": f'{{"brand_id": "{brand_id}"}}',
            },
        )
        logger.info(
            "scraper.brand_job_created",
            extra={"brand_id": brand_id, "job_code": job_code},
        )
    except Exception as exc:
        # Non-fatal: la marca se creó pero sin job automático
        logger.warning(
            "scraper.brand_job_create_failed",
            extra={"brand_id": brand_id, "error": str(exc)[:120]},
        )


@router.get(
    "/",
    response_model=list[CompetitorBrandRead],
    operation_id="listCompetitorBrands",
)
async def list_brands(
    _user: Annotated[User, Depends(require_permissions("products:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    active_only: bool = False,
) -> list[CompetitorBrandRead]:
    repo = CompetitorBrandRepository(session)
    brands = await repo.list_active() if active_only else await repo.list_all()
    return [CompetitorBrandRead.model_validate(b) for b in brands]


@router.get(
    "/{brand_id}",
    response_model=CompetitorBrandRead,
    operation_id="getCompetitorBrand",
)
async def get_brand(
    brand_id: UUID,
    _user: Annotated[User, Depends(require_permissions("products:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CompetitorBrandRead:
    repo = CompetitorBrandRepository(session)
    brand = await repo.get(brand_id)
    if not brand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
    return CompetitorBrandRead.model_validate(brand)


@router.get(
    "/{brand_id}/extractor",
    response_model=BrandExtractorRead,
    operation_id="getCompetitorBrandExtractor",
    summary="Obtener extractor de atributos de una marca (US-SCR-05-03)",
)
async def get_brand_extractor(
    brand_id: UUID,
    _user: Annotated[User, Depends(require_permissions("scraper:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    marketplace: str = "amazon_uae",
) -> BrandExtractorRead:
    stmt = select(BrandExtractor).where(
        BrandExtractor.brand_id == brand_id,
        BrandExtractor.marketplace == marketplace,
    )
    result = await session.execute(stmt)
    extractor = result.scalar_one_or_none()
    if extractor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No extractor found",
        )
    return BrandExtractorRead(
        brand_id=extractor.brand_id,
        marketplace=extractor.marketplace,
        generated_at=extractor.generated_at,
        generated_by=extractor.generated_by,
        hit_rate=float(extractor.hit_rate),
        sample_asins=extractor.sample_asins or [],
        attribute_count=len(extractor.attribute_map or {}),
        last_used_at=extractor.last_used_at,
    )


@router.get(
    "/{brand_id}/extractor/coverage-stats",
    response_model=ExtractorCoverageStats,
    operation_id="getExtractorCoverageStats",
    summary="Métricas de cobertura del extractor para una marca (US-SCR-05-04)",
)
async def get_extractor_coverage_stats(
    brand_id: UUID,
    _user: Annotated[User, Depends(require_permissions("scraper:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    marketplace: str = "amazon_uae",
) -> ExtractorCoverageStats:
    ext_result = await session.execute(
        select(BrandExtractor).where(
            BrandExtractor.brand_id == brand_id,
            BrandExtractor.marketplace == marketplace,
        )
    )
    extractor = ext_result.scalar_one_or_none()
    if extractor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No extractor found")

    alert_result = await session.execute(
        select(ExtractorAlert).where(
            ExtractorAlert.brand_id == brand_id,
            ExtractorAlert.marketplace == marketplace,
            ExtractorAlert.resolved_at.is_(None),
        )
    )
    active_alert = alert_result.scalar_one_or_none()

    hit_rate_current = float(extractor.hit_rate)
    baseline = float(active_alert.hit_rate_baseline) if active_alert else 0.80
    delta_pp = (baseline - hit_rate_current) * 100

    return ExtractorCoverageStats(
        brand_id=brand_id,
        marketplace=marketplace,
        hit_rate_current=hit_rate_current,
        hit_rate_baseline=baseline,
        delta_pp=delta_pp,
        alert_active=active_alert is not None,
        alert_id=active_alert.id if active_alert else None,
    )


@router.patch(
    "/{brand_id}/extractor/alerts/{alert_id}/resolve",
    status_code=status.HTTP_200_OK,
    operation_id="resolveExtractorAlert",
    summary="Marcar alerta de degradación como resuelta (US-SCR-05-04)",
)
async def resolve_extractor_alert(
    brand_id: UUID,
    alert_id: UUID,
    user: Annotated[User, Depends(require_permissions("scraper:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    alert_result = await session.execute(
        select(ExtractorAlert).where(
            ExtractorAlert.id == alert_id,
            ExtractorAlert.brand_id == brand_id,
            ExtractorAlert.resolved_at.is_(None),
        )
    )
    alert = alert_result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active alert not found")

    alert.resolved_at = datetime.now(UTC)
    alert.resolved_by = user.id
    await session.commit()
    return {"alert_id": str(alert_id), "resolved": True}


@router.patch(
    "/{brand_id}",
    response_model=CompetitorBrandRead,
    operation_id="updateCompetitorBrand",
)
async def update_brand(
    brand_id: UUID,
    body: CompetitorBrandUpdate,
    _user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CompetitorBrandRead:
    repo = CompetitorBrandRepository(session)
    brand = await repo.get(brand_id)
    if not brand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
    updated = await repo.update(brand, **body.model_dump(exclude_none=True))
    await session.commit()
    return CompetitorBrandRead.model_validate(updated)


@router.post(
    "/run",
    response_model=BrandScrapeRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="runBrandScrape",
)
async def run_brand_scrape(
    body: BrandScrapeRunRequest,
    _user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BrandScrapeRunResponse:
    from celery import group as celery_group

    from app.workers.tasks.scraper import scrape_brand_task

    repo = CompetitorBrandRepository(session)
    if body.brand_ids:
        brands = [b for bid in body.brand_ids if (b := await repo.get(bid)) is not None]
    else:
        brands = await repo.list_active()

    if not brands:
        return BrandScrapeRunResponse(job_id=None, total_brands=0, status="nothing_to_do")

    job = celery_group(
        scrape_brand_task.s(str(b.id), force=body.force) for b in brands
    ).apply_async(queue="comparator")
    job.save()

    logger.info(
        "scraper.brand_batch_queued",
        extra={"total_brands": len(brands), "group_id": job.id},
    )
    return BrandScrapeRunResponse(
        job_id=job.id,
        total_brands=len(brands),
        status="queued",
    )


class MonitoringToggleResponse(BaseModel):
    brand_id: str
    monitoring_active: bool


@router.post(
    "/{brand_id}/toggle-monitoring",
    response_model=MonitoringToggleResponse,
    operation_id="toggleBrandMonitoring",
)
async def toggle_brand_monitoring(
    brand_id: UUID,
    _user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MonitoringToggleResponse:
    """Activa o desactiva el monitoreo continuo de precios para una marca competidora.

    Cuando ``monitoring_active=True``, el job ``bootstrap_price_monitoring``
    incluirá esta marca en el siguiente ciclo de scraping de precios.
    """
    repo = CompetitorBrandRepository(session)
    brand = await repo.get(brand_id)
    if not brand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")

    new_state = not brand.monitoring_active
    await repo.update(brand, monitoring_active=new_state)
    await session.commit()

    logger.info(
        "scraper.brand.monitoring_toggled",
        extra={"brand_id": str(brand_id), "monitoring_active": new_state},
    )
    return MonitoringToggleResponse(brand_id=str(brand_id), monitoring_active=new_state)


@router.post(
    "/{brand_id}/bootstrap-scan",
    status_code=202,
    summary="Lanzar Bootstrap Scan: genera extractor de atributos via Claude (US-SCR-05-01)",
    operation_id="competitorBrandsBootstrapScan",
)
async def bootstrap_scan(
    brand_id: UUID,
    _user: Annotated[User, Depends(require_permissions("scraper:write"))],
    marketplace: str = "amazon_uae",
) -> dict:
    from app.workers.tasks.scraper import generate_brand_extractor_task

    task = generate_brand_extractor_task.apply_async(
        args=[str(brand_id), marketplace],
        queue="comparator",
    )
    return {"task_id": task.id, "status": "queued", "brand_id": str(brand_id)}
