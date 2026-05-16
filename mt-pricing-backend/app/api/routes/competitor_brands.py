"""Competitor Brands — gestión de marcas competidoras + trigger de scraping."""
from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.repositories.competitor_brands import CompetitorBrandRepository
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
    await session.commit()
    return CompetitorBrandRead.model_validate(brand)


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
