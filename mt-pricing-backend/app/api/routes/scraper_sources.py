"""Router REST del módulo Scraper Source Builder (F1)."""

from __future__ import annotations

import ipaddress
import socket
from typing import Annotated
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.repositories.scraper_sources import ScraperSourceRepository
from app.schemas.scraper_sources import (
    ActivateRequest,
    AnalyzeRequest,
    AnalyzeResponse,
    RecipeRead,
    RecipeSubmit,
    ScraperSourceCreate,
    ScraperSourceRead,
    ScraperSourceUpdate,
    ValidateRequest,
    ValidateResponse,
)
from app.services.matching.adapters.generic_configurable import curl_cffi_fetch
from app.services.scraper.agent_service import ScraperAgentError, ScraperAgentService
from app.services.scraper.source_validation_service import SourceValidationService

router = APIRouter(prefix="/scraper-sources", tags=["scraper-sources"])


def _assert_public_url(url: str) -> None:
    """Mitigación SSRF — rechaza URLs no-HTTP(S) o que resuelvan a IPs internas.

    ``validate_recipe`` hace un fetch en vivo de una URL provista por el usuario;
    sin este guard un usuario con ``products:write`` podría sondear servicios
    internos (metadata de la nube, red privada).
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="test_url debe usar esquema http o https",
        )
    host = parsed.hostname
    if not host:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="test_url no tiene un host válido",
        )
    try:
        addr_infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"no se pudo resolver el host de test_url: {host}",
        ) from exc
    for info in addr_infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="test_url apunta a una dirección no permitida (red interna)",
            )


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_200_OK,
    operation_id="analyzeScraperUrl",
)
async def analyze_url(
    body: AnalyzeRequest,
    _user: Annotated[User, Depends(require_permissions("products:read"))],
) -> AnalyzeResponse:
    """Fetches the URL, calls Claude to generate a scraping recipe, returns proposal.
    No DB writes — pure analysis for the wizard Step 2 preview."""
    _assert_public_url(body.url)
    service = ScraperAgentService()
    try:
        result = await service.analyze(body.url, context=body.context, hint=body.hint)
    except ScraperAgentError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return AnalyzeResponse(
        detected_mode=result.detected_mode,
        proposed_source=result.proposed_source,
        proposed_recipe=result.proposed_recipe,
        field_confidence=result.field_confidence,
        preview_records=result.preview_records,
        missing_required=result.missing_required,
        warnings=result.warnings,
    )


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


@router.get("/{source_id}", response_model=ScraperSourceRead, operation_id="getScraperSource")
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


@router.get(
    "/{source_id}/recipes",
    response_model=list[RecipeRead],
    operation_id="listScraperSourceRecipes",
)
async def list_source_recipes(
    source_id: UUID,
    _user: Annotated[User, Depends(require_permissions("products:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[RecipeRead]:
    repo = ScraperSourceRepository(session)
    if await repo.get(source_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    return [RecipeRead.model_validate(r) for r in await repo.list_recipes(source_id)]


@router.patch(
    "/{source_id}",
    response_model=ScraperSourceRead,
    operation_id="updateScraperSource",
)
async def update_source(
    source_id: UUID,
    body: ScraperSourceUpdate,
    _user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScraperSourceRead:
    repo = ScraperSourceRepository(session)
    source = await repo.update(source_id, **body.model_dump(exclude_none=True))
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    await session.commit()
    await session.refresh(source)
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
    _assert_public_url(body.test_url)
    repo = ScraperSourceRepository(session)
    if await repo.get(source_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    service = SourceValidationService(session)
    try:
        result = await service.validate(
            source_id, body.recipe_id, body.test_url, html_fetcher=curl_cffi_fetch
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    return ValidateResponse(**result)


@router.post(
    "/{source_id}/activate",
    response_model=ScraperSourceRead,
    operation_id="activateScraperSource",
)
async def activate_source(
    source_id: UUID,
    body: ActivateRequest,
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
