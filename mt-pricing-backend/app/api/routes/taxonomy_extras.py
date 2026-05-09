"""Taxonomy extras API — divisions, series (rica), materials.

Stage 3 (Wave 11) — modelado de jerarquía de catálogo.

Endpoints:

Public (products:read):
- GET  /divisions
- GET  /series                       (?division_id=<uuid>)
- GET  /series/{series_id}
- GET  /series-tiers
- GET  /materials

Admin (admin:taxonomy):
- POST/PATCH/DELETE /admin/divisions/*
- POST/PATCH/DELETE /admin/series/*
- POST/DELETE       /admin/series/{id}/divisions/{div_id}
- POST/DELETE       /admin/series/{id}/certifications/{cert_id}
- PUT/DELETE        /admin/series/{id}/translations/{lang}
- POST/PATCH/DELETE /admin/series-tiers/*
- POST/PATCH/DELETE /admin/materials/*

Product sub-resource (mounted by routes/__init__.py with /products prefix):
- GET    /products/{sku}/divisions
- POST   /products/{sku}/divisions   (add one)
- PUT    /products/{sku}/divisions   (replace all)
- DELETE /products/{sku}/divisions/{div_id}
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.schemas.common import ProblemDetails
from app.schemas.vocabularies import (
    DivisionCreate,
    DivisionPatch,
    DivisionResponse,
    MaterialCreate,
    MaterialPatch,
    MaterialResponse,
    ProductDivisionLink,
    ProductDivisionResponse,
    SeriesCertificationLink,
    SeriesCreate,
    SeriesDivisionLink,
    SeriesPatch,
    SeriesResponse,
    SeriesTierCreate,
    SeriesTierPatch,
    SeriesTierResponse,
    SeriesTranslationResponse,
    SeriesTranslationUpsert,
)
from app.services.vocabularies.vocabulary_service import (
    DivisionService,
    MaterialService,
    ProductDivisionService,
    SeriesService,
    SeriesTierService,
    VocabularyDomainError,
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
divisions_router = APIRouter(tags=["divisions"])
series_router = APIRouter(tags=["series"])
materials_router = APIRouter(tags=["materials"])

admin_divisions_router = APIRouter(prefix="/admin", tags=["admin:taxonomy"])
admin_series_router = APIRouter(prefix="/admin", tags=["admin:taxonomy"])
admin_materials_router = APIRouter(prefix="/admin", tags=["admin:taxonomy"])

# Product sub-router (mounted at /products by routes/__init__.py)
products_divisions_router = APIRouter(tags=["products:divisions"])


# ---------------------------------------------------------------------------
# DI factories
# ---------------------------------------------------------------------------
def get_division_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DivisionService:
    return DivisionService(session)


def get_product_division_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProductDivisionService:
    return ProductDivisionService(session)


def get_series_tier_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SeriesTierService:
    return SeriesTierService(session)


def get_series_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SeriesService:
    return SeriesService(session)


def get_material_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MaterialService:
    return MaterialService(session)


# ---------------------------------------------------------------------------
# Error helper
# ---------------------------------------------------------------------------
def _raise_domain(e: VocabularyDomainError) -> None:
    raise HTTPException(
        status_code=e.status_code,
        detail=ProblemDetails(
            title=e.message, status=e.status_code, type=e.code
        ).model_dump(),
    )


# ===========================================================================
# Public catalog reads
# ===========================================================================
@divisions_router.get(
    "/divisions",
    response_model=list[DivisionResponse],
    summary="Listar divisiones activas (Hidrosanitario / Industrial / …)",
)
async def list_divisions(
    _user: User = Depends(require_permissions("products:read")),
    service: DivisionService = Depends(get_division_service),
) -> list[DivisionResponse]:
    rows = await service.list_active()
    return [DivisionResponse.model_validate(r) for r in rows]


@series_router.get(
    "/series-tiers",
    response_model=list[SeriesTierResponse],
    summary="Listar tiers de serie (PLATINUM, GOLD, …)",
)
async def list_series_tiers(
    _user: User = Depends(require_permissions("products:read")),
    service: SeriesTierService = Depends(get_series_tier_service),
) -> list[SeriesTierResponse]:
    rows = await service.list_active()
    return [SeriesTierResponse.model_validate(r) for r in rows]


@series_router.get(
    "/series",
    response_model=list[SeriesResponse],
    summary="Listar series activas, opcionalmente filtradas por división",
)
async def list_series(
    division_id: Annotated[
        UUID | None, Query(description="Filtrar por división (M:N)")
    ] = None,
    _user: User = Depends(require_permissions("products:read")),
    service: SeriesService = Depends(get_series_service),
) -> list[SeriesResponse]:
    rows = (
        await service.list_by_division(division_id)
        if division_id
        else await service.list_active()
    )
    return [SeriesResponse.model_validate(r) for r in rows]


@series_router.get(
    "/series/{series_id}",
    response_model=SeriesResponse,
    summary="Detalle de serie por id",
    responses={404: {"model": ProblemDetails}},
)
async def get_series(
    series_id: UUID,
    _user: User = Depends(require_permissions("products:read")),
    service: SeriesService = Depends(get_series_service),
) -> SeriesResponse:
    try:
        row = await service.get_by_id(series_id)
    except VocabularyDomainError as e:
        _raise_domain(e)
    return SeriesResponse.model_validate(row)


@series_router.get(
    "/series/{series_id}/translations",
    response_model=list[SeriesTranslationResponse],
    summary="Listar traducciones de una serie",
    responses={404: {"model": ProblemDetails}},
)
async def list_series_translations(
    series_id: UUID,
    _user: User = Depends(require_permissions("products:read")),
    service: SeriesService = Depends(get_series_service),
) -> list[SeriesTranslationResponse]:
    try:
        rows = await service.list_translations(series_id)
    except VocabularyDomainError as e:
        _raise_domain(e)
    return [SeriesTranslationResponse.model_validate(r) for r in rows]


@materials_router.get(
    "/materials",
    response_model=list[MaterialResponse],
    summary="Listar vocabulario de materiales activos",
)
async def list_materials(
    _user: User = Depends(require_permissions("products:read")),
    service: MaterialService = Depends(get_material_service),
) -> list[MaterialResponse]:
    rows = await service.list_active()
    return [MaterialResponse.model_validate(r) for r in rows]


# ===========================================================================
# Admin: Divisions CRUD
# ===========================================================================
@admin_divisions_router.get(
    "/divisions",
    response_model=list[DivisionResponse],
    summary="[Admin] Listar todas las divisiones (incluye inactivas)",
)
async def admin_list_divisions(
    _user: User = Depends(require_permissions("admin:taxonomy")),
    service: DivisionService = Depends(get_division_service),
) -> list[DivisionResponse]:
    rows = await service.list_all()
    return [DivisionResponse.model_validate(r) for r in rows]


@admin_divisions_router.post(
    "/divisions",
    response_model=DivisionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ProblemDetails}},
)
async def admin_create_division(
    data: DivisionCreate,
    _user: User = Depends(require_permissions("admin:taxonomy")),
    service: DivisionService = Depends(get_division_service),
) -> DivisionResponse:
    try:
        row = await service.create(data.model_dump())
    except VocabularyDomainError as e:
        _raise_domain(e)
    return DivisionResponse.model_validate(row)


@admin_divisions_router.patch(
    "/divisions/{division_id}",
    response_model=DivisionResponse,
    responses={404: {"model": ProblemDetails}},
)
async def admin_patch_division(
    division_id: UUID,
    data: DivisionPatch,
    _user: User = Depends(require_permissions("admin:taxonomy")),
    service: DivisionService = Depends(get_division_service),
) -> DivisionResponse:
    try:
        row = await service.patch(
            division_id, data.model_dump(exclude_unset=True)
        )
    except VocabularyDomainError as e:
        _raise_domain(e)
    return DivisionResponse.model_validate(row)


@admin_divisions_router.delete(
    "/divisions/{division_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ProblemDetails}},
)
async def admin_delete_division(
    division_id: UUID,
    _user: User = Depends(require_permissions("admin:taxonomy")),
    service: DivisionService = Depends(get_division_service),
) -> None:
    try:
        await service.delete(division_id)
    except VocabularyDomainError as e:
        _raise_domain(e)


# ===========================================================================
# Admin: SeriesTier CRUD
# ===========================================================================
@admin_series_router.get(
    "/series-tiers",
    response_model=list[SeriesTierResponse],
)
async def admin_list_series_tiers(
    _user: User = Depends(require_permissions("admin:taxonomy")),
    service: SeriesTierService = Depends(get_series_tier_service),
) -> list[SeriesTierResponse]:
    rows = await service.list_all()
    return [SeriesTierResponse.model_validate(r) for r in rows]


@admin_series_router.post(
    "/series-tiers",
    response_model=SeriesTierResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ProblemDetails}},
)
async def admin_create_series_tier(
    data: SeriesTierCreate,
    _user: User = Depends(require_permissions("admin:taxonomy")),
    service: SeriesTierService = Depends(get_series_tier_service),
) -> SeriesTierResponse:
    try:
        row = await service.create(data.model_dump())
    except VocabularyDomainError as e:
        _raise_domain(e)
    return SeriesTierResponse.model_validate(row)


@admin_series_router.patch(
    "/series-tiers/{tier_id}",
    response_model=SeriesTierResponse,
    responses={404: {"model": ProblemDetails}},
)
async def admin_patch_series_tier(
    tier_id: UUID,
    data: SeriesTierPatch,
    _user: User = Depends(require_permissions("admin:taxonomy")),
    service: SeriesTierService = Depends(get_series_tier_service),
) -> SeriesTierResponse:
    try:
        row = await service.patch(tier_id, data.model_dump(exclude_unset=True))
    except VocabularyDomainError as e:
        _raise_domain(e)
    return SeriesTierResponse.model_validate(row)


@admin_series_router.delete(
    "/series-tiers/{tier_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ProblemDetails}},
)
async def admin_delete_series_tier(
    tier_id: UUID,
    _user: User = Depends(require_permissions("admin:taxonomy")),
    service: SeriesTierService = Depends(get_series_tier_service),
) -> None:
    try:
        await service.delete(tier_id)
    except VocabularyDomainError as e:
        _raise_domain(e)


# ===========================================================================
# Admin: Series CRUD + relations
# ===========================================================================
@admin_series_router.get(
    "/series",
    response_model=list[SeriesResponse],
)
async def admin_list_series(
    _user: User = Depends(require_permissions("admin:taxonomy")),
    service: SeriesService = Depends(get_series_service),
) -> list[SeriesResponse]:
    rows = await service.list_all()
    return [SeriesResponse.model_validate(r) for r in rows]


@admin_series_router.post(
    "/series",
    response_model=SeriesResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ProblemDetails}},
)
async def admin_create_series(
    data: SeriesCreate,
    _user: User = Depends(require_permissions("admin:taxonomy")),
    service: SeriesService = Depends(get_series_service),
) -> SeriesResponse:
    try:
        row = await service.create(data.model_dump())
    except VocabularyDomainError as e:
        _raise_domain(e)
    return SeriesResponse.model_validate(row)


@admin_series_router.patch(
    "/series/{series_id}",
    response_model=SeriesResponse,
    responses={404: {"model": ProblemDetails}},
)
async def admin_patch_series(
    series_id: UUID,
    data: SeriesPatch,
    _user: User = Depends(require_permissions("admin:taxonomy")),
    service: SeriesService = Depends(get_series_service),
) -> SeriesResponse:
    try:
        row = await service.patch(series_id, data.model_dump(exclude_unset=True))
    except VocabularyDomainError as e:
        _raise_domain(e)
    return SeriesResponse.model_validate(row)


@admin_series_router.delete(
    "/series/{series_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ProblemDetails}},
)
async def admin_delete_series(
    series_id: UUID,
    _user: User = Depends(require_permissions("admin:taxonomy")),
    service: SeriesService = Depends(get_series_service),
) -> None:
    try:
        await service.delete(series_id)
    except VocabularyDomainError as e:
        _raise_domain(e)


# ---- Series ↔ Division links ----
@admin_series_router.get(
    "/series/{series_id}/divisions",
    response_model=list[DivisionResponse],
    summary="[Admin] Listar divisiones enlazadas a la serie",
    responses={404: {"model": ProblemDetails}},
)
async def admin_list_series_divisions(
    series_id: UUID,
    _user: User = Depends(require_permissions("admin:taxonomy")),
    service: SeriesService = Depends(get_series_service),
) -> list[DivisionResponse]:
    try:
        links = await service.list_divisions(series_id)
    except VocabularyDomainError as e:
        _raise_domain(e)
    return [DivisionResponse.model_validate(link.division) for link in links]


@admin_series_router.post(
    "/series/{series_id}/divisions/{division_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ProblemDetails}},
)
async def admin_link_series_division(
    series_id: UUID,
    division_id: UUID,
    _user: User = Depends(require_permissions("admin:taxonomy")),
    service: SeriesService = Depends(get_series_service),
) -> None:
    try:
        await service.add_division(series_id, division_id)
    except VocabularyDomainError as e:
        _raise_domain(e)


@admin_series_router.delete(
    "/series/{series_id}/divisions/{division_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ProblemDetails}},
)
async def admin_unlink_series_division(
    series_id: UUID,
    division_id: UUID,
    _user: User = Depends(require_permissions("admin:taxonomy")),
    service: SeriesService = Depends(get_series_service),
) -> None:
    try:
        await service.remove_division(series_id, division_id)
    except VocabularyDomainError as e:
        _raise_domain(e)


# ---- Series ↔ Certification links (default package) ----
@admin_series_router.get(
    "/series/{series_id}/certifications",
    response_model=list[dict],
    summary="[Admin] Listar certificaciones default enlazadas a la serie",
    responses={404: {"model": ProblemDetails}},
)
async def admin_list_series_certifications(
    series_id: UUID,
    _user: User = Depends(require_permissions("admin:taxonomy")),
    service: SeriesService = Depends(get_series_service),
) -> list[dict]:
    try:
        links = await service.list_certifications(series_id)
    except VocabularyDomainError as e:
        _raise_domain(e)
    return [
        {
            "certification_id": link.certification_id,
            "code": link.certification.code,
            "name": link.certification.name,
            "issued_by": link.certification.issued_by,
            "scope": link.certification.scope,
            "logo_url": link.certification.logo_url,
        }
        for link in links
    ]


@admin_series_router.post(
    "/series/{series_id}/certifications/{certification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ProblemDetails}},
)
async def admin_link_series_certification(
    series_id: UUID,
    certification_id: UUID,
    _user: User = Depends(require_permissions("admin:taxonomy")),
    service: SeriesService = Depends(get_series_service),
) -> None:
    try:
        await service.add_certification(series_id, certification_id)
    except VocabularyDomainError as e:
        _raise_domain(e)


@admin_series_router.delete(
    "/series/{series_id}/certifications/{certification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ProblemDetails}},
)
async def admin_unlink_series_certification(
    series_id: UUID,
    certification_id: UUID,
    _user: User = Depends(require_permissions("admin:taxonomy")),
    service: SeriesService = Depends(get_series_service),
) -> None:
    try:
        await service.remove_certification(series_id, certification_id)
    except VocabularyDomainError as e:
        _raise_domain(e)


# ---- Series translations (upsert per lang) ----
@admin_series_router.put(
    "/series/{series_id}/translations/{lang}",
    response_model=SeriesTranslationResponse,
    responses={404: {"model": ProblemDetails}},
)
async def admin_upsert_series_translation(
    series_id: UUID,
    lang: str,
    data: SeriesTranslationUpsert,
    _user: User = Depends(require_permissions("admin:taxonomy")),
    service: SeriesService = Depends(get_series_service),
) -> SeriesTranslationResponse:
    if lang != data.lang:
        raise HTTPException(
            status_code=400,
            detail=ProblemDetails(
                title="Path lang and body lang must match",
                status=400,
                type="lang_mismatch",
            ).model_dump(),
        )
    try:
        row = await service.upsert_translation(
            series_id,
            data.lang,
            name=data.name,
            description=data.description,
            bullets=data.bullets,
        )
    except VocabularyDomainError as e:
        _raise_domain(e)
    return SeriesTranslationResponse.model_validate(row)


@admin_series_router.delete(
    "/series/{series_id}/translations/{lang}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ProblemDetails}},
)
async def admin_delete_series_translation(
    series_id: UUID,
    lang: str,
    _user: User = Depends(require_permissions("admin:taxonomy")),
    service: SeriesService = Depends(get_series_service),
) -> None:
    try:
        await service.delete_translation(series_id, lang)
    except VocabularyDomainError as e:
        _raise_domain(e)


# ===========================================================================
# Admin: Materials CRUD
# ===========================================================================
@admin_materials_router.get(
    "/materials",
    response_model=list[MaterialResponse],
)
async def admin_list_materials(
    _user: User = Depends(require_permissions("admin:taxonomy")),
    service: MaterialService = Depends(get_material_service),
) -> list[MaterialResponse]:
    rows = await service.list_all()
    return [MaterialResponse.model_validate(r) for r in rows]


@admin_materials_router.post(
    "/materials",
    response_model=MaterialResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ProblemDetails}},
)
async def admin_create_material(
    data: MaterialCreate,
    _user: User = Depends(require_permissions("admin:taxonomy")),
    service: MaterialService = Depends(get_material_service),
) -> MaterialResponse:
    try:
        row = await service.create(data.model_dump())
    except VocabularyDomainError as e:
        _raise_domain(e)
    return MaterialResponse.model_validate(row)


@admin_materials_router.patch(
    "/materials/{material_id}",
    response_model=MaterialResponse,
    responses={404: {"model": ProblemDetails}},
)
async def admin_patch_material(
    material_id: UUID,
    data: MaterialPatch,
    _user: User = Depends(require_permissions("admin:taxonomy")),
    service: MaterialService = Depends(get_material_service),
) -> MaterialResponse:
    try:
        row = await service.patch(
            material_id, data.model_dump(exclude_unset=True)
        )
    except VocabularyDomainError as e:
        _raise_domain(e)
    return MaterialResponse.model_validate(row)


@admin_materials_router.delete(
    "/materials/{material_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ProblemDetails}},
)
async def admin_delete_material(
    material_id: UUID,
    _user: User = Depends(require_permissions("admin:taxonomy")),
    service: MaterialService = Depends(get_material_service),
) -> None:
    try:
        await service.delete(material_id)
    except VocabularyDomainError as e:
        _raise_domain(e)


# ===========================================================================
# Product sub-resource: Divisions (M:N)
# ===========================================================================
@products_divisions_router.get(
    "/{sku}/divisions",
    response_model=list[ProductDivisionResponse],
    summary="Listar divisiones donde aparece este producto",
)
async def list_product_divisions(
    sku: str,
    _user: User = Depends(require_permissions("products:read")),
    service: ProductDivisionService = Depends(get_product_division_service),
) -> list[ProductDivisionResponse]:
    rows = await service.list_for_product(sku)
    return [ProductDivisionResponse.from_link(r) for r in rows]


@products_divisions_router.post(
    "/{sku}/divisions",
    response_model=ProductDivisionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"model": ProblemDetails}},
)
async def add_product_division(
    sku: str,
    data: ProductDivisionLink,
    _user: User = Depends(require_permissions("products:write")),
    service: ProductDivisionService = Depends(get_product_division_service),
) -> ProductDivisionResponse:
    try:
        row = await service.add(sku, data.division_id)
    except VocabularyDomainError as e:
        _raise_domain(e)
    # Re-fetch with division eager-loaded
    rows = await service.list_for_product(sku)
    match = next(
        (r for r in rows if r.division_id == data.division_id), None
    )
    if match is None:
        return ProductDivisionResponse(
            division_id=row.division_id,
            code="",
            name="",
            created_at=row.created_at,
        )
    return ProductDivisionResponse.from_link(match)


@products_divisions_router.put(
    "/{sku}/divisions",
    response_model=list[ProductDivisionResponse],
    summary="Reemplazar set de divisiones del producto (atómico)",
    responses={404: {"model": ProblemDetails}},
)
async def replace_product_divisions(
    sku: str,
    division_ids: list[UUID],
    _user: User = Depends(require_permissions("products:write")),
    service: ProductDivisionService = Depends(get_product_division_service),
) -> list[ProductDivisionResponse]:
    try:
        await service.replace_all(sku, division_ids)
    except VocabularyDomainError as e:
        _raise_domain(e)
    rows = await service.list_for_product(sku)
    return [ProductDivisionResponse.from_link(r) for r in rows]


@products_divisions_router.delete(
    "/{sku}/divisions/{division_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ProblemDetails}},
)
async def remove_product_division(
    sku: str,
    division_id: UUID,
    _user: User = Depends(require_permissions("products:write")),
    service: ProductDivisionService = Depends(get_product_division_service),
) -> None:
    try:
        await service.remove(sku, division_id)
    except VocabularyDomainError as e:
        _raise_domain(e)
