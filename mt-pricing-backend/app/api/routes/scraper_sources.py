"""Router REST del módulo Scraper Source Builder (F1)."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.repositories.scraper_sources import ScraperSourceRepository
from app.schemas.scraper_sources import (
    RecipeRead,
    RecipeSubmit,
    ScraperSourceCreate,
    ScraperSourceRead,
    ValidateRequest,
    ValidateResponse,
)
from app.services.matching.adapters.generic_configurable import _curl_cffi_fetch
from app.services.scraper.source_validation_service import SourceValidationService

router = APIRouter(prefix="/scraper-sources", tags=["scraper-sources"])


@router.post(
    "",
    response_model=ScraperSourceRead,
    status_code=status.HTTP_201_CREATED,
    operation_id="createScraperSource",
)
async def create_source(
    body: ScraperSourceCreate,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScraperSourceRead:
    repo = ScraperSourceRepository(session)
    if await repo.get_by_slug(body.slug) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "duplicate_slug", "detail": f"slug '{body.slug}' ya existe."},
        )
    source = await repo.create(
        name=body.name,
        slug=body.slug,
        base_url=body.base_url,
        destination_profile=body.destination_profile,
        fetch_mode=body.fetch_mode,
        description=body.description,
        competitor_brand_id=body.competitor_brand_id,
        created_by=user.id,
    )
    await session.commit()
    return ScraperSourceRead.model_validate(source)


@router.get("", response_model=list[ScraperSourceRead], operation_id="listScraperSources")
async def list_sources(
    _user: Annotated[User, Depends(require_permissions("products:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[ScraperSourceRead]:
    repo = ScraperSourceRepository(session)
    return [ScraperSourceRead.model_validate(s) for s in await repo.list_all()]


@router.get(
    "/{source_id}", response_model=ScraperSourceRead, operation_id="getScraperSource"
)
async def get_source(
    source_id: UUID,
    _user: Annotated[User, Depends(require_permissions("products:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScraperSourceRead:
    repo = ScraperSourceRepository(session)
    source = await repo.get(source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    return ScraperSourceRead.model_validate(source)


@router.post(
    "/{source_id}/recipes",
    response_model=RecipeRead,
    status_code=status.HTTP_201_CREATED,
    operation_id="addScraperSourceRecipe",
)
async def add_recipe(
    source_id: UUID,
    body: RecipeSubmit,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RecipeRead:
    repo = ScraperSourceRepository(session)
    if await repo.get(source_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    recipe_row = await repo.add_recipe(
        source_id, body.recipe.model_dump(mode="json"), created_by=user.id
    )
    await session.commit()
    return RecipeRead.model_validate(recipe_row)


@router.post(
    "/{source_id}/validate",
    response_model=ValidateResponse,
    operation_id="validateScraperSourceRecipe",
)
async def validate_recipe(
    source_id: UUID,
    body: ValidateRequest,
    _user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ValidateResponse:
    repo = ScraperSourceRepository(session)
    if await repo.get(source_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    service = SourceValidationService(session)
    try:
        result = await service.validate(
            source_id, body.recipe_id, body.test_url, html_fetcher=_curl_cffi_fetch
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    await session.commit()
    return ValidateResponse(**result)


@router.post(
    "/{source_id}/activate",
    response_model=ScraperSourceRead,
    operation_id="activateScraperSource",
)
async def activate_source(
    source_id: UUID,
    body: ValidateRequest,
    _user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScraperSourceRead:
    """Promueve una receta a is_live y la source a 'active'.

    Requiere que la receta esté ``passing`` y sin snippets sin aprobar.
    """
    repo = ScraperSourceRepository(session)
    source = await repo.get(source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    recipe = await repo.get_recipe(body.recipe_id)
    if recipe is None or recipe.source_id != source_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="recipe not found")
    if recipe.validation_status != "passing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="la receta debe estar 'passing' para activarse",
        )
    if recipe.has_unapproved_snippet:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="la receta tiene snippets sin aprobar",
        )
    await repo.set_recipe_live(body.recipe_id)
    source.status = "active"
    await session.commit()
    return ScraperSourceRead.model_validate(source)
