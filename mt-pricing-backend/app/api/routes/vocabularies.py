"""Vocabularies API — certifications, applications, product vocabulary links.

Endpoints:
- GET /certifications          — public catalog read (products:read)
- GET /applications            — public catalog read (products:read)
- Admin CRUD /admin/certifications/* — admin:vocabularies permission
- Admin CRUD /admin/applications/*  — admin:vocabularies permission
- Product sub-resources on products router (imported by products.py):
    GET/PUT/POST/DELETE /products/{sku}/certifications
    GET/PUT/POST/DELETE /products/{sku}/applications
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, require_permissions
from app.db.models.user import User
from app.schemas.common import ProblemDetails
from app.schemas.vocabularies import (
    ApplicationCreate,
    ApplicationPatch,
    ApplicationResponse,
    CertificationCreate,
    CertificationPatch,
    CertificationResponse,
    ProductApplicationLink,
    ProductApplicationResponse,
    ProductCertificationLink,
    ProductCertificationResponse,
    TaxonomyTreeResponse,
)
from app.services.vocabularies.vocabulary_service import (
    ApplicationService,
    CertificationService,
    FamilyService,
    ProductVocabularyService,
    VocabularyDomainError,
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
router = APIRouter(tags=["vocabularies"])

# Admin sub-router (prefix added at registration time)
admin_vocab_router = APIRouter(
    prefix="/admin",
    tags=["admin:vocabularies"],
)

# Product vocabulary sub-router (prefix /products/{sku} added by products.py)
products_vocab_router = APIRouter(tags=["products:vocabularies"])

# Taxonomy tree — GET /taxonomy/tree
taxonomy_router = APIRouter(prefix="/taxonomy", tags=["taxonomy"])


# ---------------------------------------------------------------------------
# DI factories
# ---------------------------------------------------------------------------
def get_cert_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CertificationService:
    return CertificationService(session)


def get_app_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApplicationService:
    return ApplicationService(session)


def get_product_vocab_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProductVocabularyService:
    return ProductVocabularyService(session)


# ---------------------------------------------------------------------------
# Error helper
# ---------------------------------------------------------------------------
def _problem(
    request: Request, status_code: int, code: str, title: str, detail: str | None = None
) -> JSONResponse:
    payload = ProblemDetails(
        type=f"https://mtme-api/errors/{code}",
        title=title,
        status=status_code,
        detail=detail,
        instance=str(request.url.path),
        code=code,
    ).model_dump(exclude_none=True)
    return JSONResponse(status_code=status_code, content=payload)


def _raise_domain(err: VocabularyDomainError) -> None:
    raise HTTPException(
        status_code=err.status_code,
        detail={"code": err.code, "title": err.message},
    )


# ===========================================================================
# Public catalog read endpoints
# ===========================================================================
@router.get(
    "/certifications",
    response_model=list[CertificationResponse],
    summary="Listar certificaciones activas del catálogo",
)
async def list_certifications(
    _user: User = Depends(require_permissions("products:read")),
    service: CertificationService = Depends(get_cert_service),
) -> list[CertificationResponse]:
    rows = await service.list_active()
    return [CertificationResponse.model_validate(r) for r in rows]


@router.get(
    "/applications",
    response_model=list[ApplicationResponse],
    summary="Listar aplicaciones activas del catálogo",
)
async def list_applications(
    _user: User = Depends(require_permissions("products:read")),
    service: ApplicationService = Depends(get_app_service),
) -> list[ApplicationResponse]:
    rows = await service.list_active()
    return [ApplicationResponse.model_validate(r) for r in rows]


# ===========================================================================
# Admin: Certifications CRUD
# ===========================================================================
@admin_vocab_router.get(
    "/certifications",
    response_model=list[CertificationResponse],
    summary="[Admin] Listar todas las certificaciones (incluye inactivas)",
)
async def admin_list_certifications(
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: CertificationService = Depends(get_cert_service),
) -> list[CertificationResponse]:
    rows = await service.list_all()
    return [CertificationResponse.model_validate(r) for r in rows]


@admin_vocab_router.post(
    "/certifications",
    response_model=CertificationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="[Admin] Crear certificación",
    responses={409: {"model": ProblemDetails}},
)
async def admin_create_certification(
    data: CertificationCreate,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: CertificationService = Depends(get_cert_service),
) -> CertificationResponse:
    try:
        row = await service.create(data.model_dump())
    except VocabularyDomainError as e:
        _raise_domain(e)
    return CertificationResponse.model_validate(row)


@admin_vocab_router.get(
    "/certifications/{cert_id}",
    response_model=CertificationResponse,
    summary="[Admin] Obtener certificación por ID",
    responses={404: {"model": ProblemDetails}},
)
async def admin_get_certification(
    cert_id: UUID,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: CertificationService = Depends(get_cert_service),
) -> CertificationResponse:
    try:
        row = await service.get_by_id(cert_id)
    except VocabularyDomainError as e:
        _raise_domain(e)
    return CertificationResponse.model_validate(row)


@admin_vocab_router.patch(
    "/certifications/{cert_id}",
    response_model=CertificationResponse,
    summary="[Admin] Modificar certificación",
    responses={404: {"model": ProblemDetails}},
)
async def admin_patch_certification(
    cert_id: UUID,
    data: CertificationPatch,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: CertificationService = Depends(get_cert_service),
) -> CertificationResponse:
    try:
        row = await service.patch(cert_id, data.model_dump(exclude_unset=True))
    except VocabularyDomainError as e:
        _raise_domain(e)
    return CertificationResponse.model_validate(row)


@admin_vocab_router.delete(
    "/certifications/{cert_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="[Admin] Eliminar certificación",
)
async def admin_delete_certification(
    cert_id: UUID,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: CertificationService = Depends(get_cert_service),
):
    try:
        await service.delete(cert_id)
    except VocabularyDomainError as e:
        _raise_domain(e)


# ===========================================================================
# Admin: Applications CRUD
# ===========================================================================
@admin_vocab_router.get(
    "/applications",
    response_model=list[ApplicationResponse],
    summary="[Admin] Listar todas las aplicaciones (incluye inactivas)",
)
async def admin_list_applications(
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: ApplicationService = Depends(get_app_service),
) -> list[ApplicationResponse]:
    rows = await service.list_all()
    return [ApplicationResponse.model_validate(r) for r in rows]


@admin_vocab_router.post(
    "/applications",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="[Admin] Crear aplicación",
    responses={409: {"model": ProblemDetails}},
)
async def admin_create_application(
    data: ApplicationCreate,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: ApplicationService = Depends(get_app_service),
) -> ApplicationResponse:
    try:
        row = await service.create(data.model_dump())
    except VocabularyDomainError as e:
        _raise_domain(e)
    return ApplicationResponse.model_validate(row)


@admin_vocab_router.get(
    "/applications/{app_id}",
    response_model=ApplicationResponse,
    summary="[Admin] Obtener aplicación por ID",
    responses={404: {"model": ProblemDetails}},
)
async def admin_get_application(
    app_id: UUID,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: ApplicationService = Depends(get_app_service),
) -> ApplicationResponse:
    try:
        row = await service.get_by_id(app_id)
    except VocabularyDomainError as e:
        _raise_domain(e)
    return ApplicationResponse.model_validate(row)


@admin_vocab_router.patch(
    "/applications/{app_id}",
    response_model=ApplicationResponse,
    summary="[Admin] Modificar aplicación",
    responses={404: {"model": ProblemDetails}},
)
async def admin_patch_application(
    app_id: UUID,
    data: ApplicationPatch,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: ApplicationService = Depends(get_app_service),
) -> ApplicationResponse:
    try:
        row = await service.patch(app_id, data.model_dump(exclude_unset=True))
    except VocabularyDomainError as e:
        _raise_domain(e)
    return ApplicationResponse.model_validate(row)


@admin_vocab_router.delete(
    "/applications/{app_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="[Admin] Eliminar aplicación",
)
async def admin_delete_application(
    app_id: UUID,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: ApplicationService = Depends(get_app_service),
):
    try:
        await service.delete(app_id)
    except VocabularyDomainError as e:
        _raise_domain(e)


# ===========================================================================
# Product sub-resource: Certifications
# ===========================================================================
@products_vocab_router.get(
    "/{sku}/certifications",
    response_model=list[ProductCertificationResponse],
    summary="Listar certificaciones de un producto",
    responses={404: {"model": ProblemDetails}},
)
async def list_product_certifications(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    _user: User = Depends(require_permissions("products:read")),
    service: ProductVocabularyService = Depends(get_product_vocab_service),
) -> list[ProductCertificationResponse]:
    links = await service.list_certifications(sku)
    return [ProductCertificationResponse.from_link(lnk) for lnk in links]


@products_vocab_router.post(
    "/{sku}/certifications",
    response_model=ProductCertificationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Añadir certificación a un producto",
    responses={404: {"model": ProblemDetails}},
)
async def add_product_certification(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    data: ProductCertificationLink,
    _user: User = Depends(require_permissions("products:write")),
    service: ProductVocabularyService = Depends(get_product_vocab_service),
) -> ProductCertificationResponse:
    try:
        link = await service.add_certification(
            sku,
            data.certification_id,
            certificate_pdf_asset_id=data.certificate_pdf_asset_id,
            obtained_at=data.obtained_at,
            expires_at=data.expires_at,
            notes=data.notes,
            owner_type=data.owner_type.value,
            owner_id=data.owner_id,
        )
    except VocabularyDomainError as e:
        _raise_domain(e)
    # Reload with cert
    links = await service.list_certifications(sku)
    for lnk in links:
        if lnk.certification_id == data.certification_id:
            return ProductCertificationResponse.from_link(lnk)
    # Fallback: should not happen
    return ProductCertificationResponse.from_link(link)  # type: ignore[possibly-undefined]


@products_vocab_router.put(
    "/{sku}/certifications",
    response_model=list[ProductCertificationResponse],
    summary="Reemplazar todas las certificaciones de un producto",
    responses={404: {"model": ProblemDetails}},
)
async def replace_product_certifications(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    data: list[ProductCertificationLink],
    _user: User = Depends(require_permissions("products:write")),
    service: ProductVocabularyService = Depends(get_product_vocab_service),
) -> list[ProductCertificationResponse]:
    try:
        # Fase 5 — model_dump(mode='json') normaliza Enums a strings antes de
        # propagar al repo/service.
        await service.replace_certifications(
            sku, [d.model_dump(mode="json") for d in data]
        )
    except VocabularyDomainError as e:
        _raise_domain(e)
    links = await service.list_certifications(sku)
    return [ProductCertificationResponse.from_link(lnk) for lnk in links]


@products_vocab_router.delete(
    "/{sku}/certifications/{cert_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Eliminar certificación de un producto",
)
async def remove_product_certification(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    cert_id: UUID,
    _user: User = Depends(require_permissions("products:write")),
    service: ProductVocabularyService = Depends(get_product_vocab_service),
):
    try:
        await service.remove_certification(sku, cert_id)
    except VocabularyDomainError as e:
        _raise_domain(e)


# ===========================================================================
# Product sub-resource: Applications
# ===========================================================================
@products_vocab_router.get(
    "/{sku}/applications",
    response_model=list[ProductApplicationResponse],
    summary="Listar aplicaciones de un producto",
    responses={404: {"model": ProblemDetails}},
)
async def list_product_applications(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    _user: User = Depends(require_permissions("products:read")),
    service: ProductVocabularyService = Depends(get_product_vocab_service),
) -> list[ProductApplicationResponse]:
    links = await service.list_applications(sku)
    return [ProductApplicationResponse.from_link(lnk) for lnk in links]


@products_vocab_router.post(
    "/{sku}/applications",
    response_model=ProductApplicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Añadir aplicación a un producto",
    responses={404: {"model": ProblemDetails}},
)
async def add_product_application(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    data: ProductApplicationLink,
    _user: User = Depends(require_permissions("products:write")),
    service: ProductVocabularyService = Depends(get_product_vocab_service),
) -> ProductApplicationResponse:
    try:
        link = await service.add_application(
            sku,
            data.application_id,
            is_primary=data.is_primary,
            position=data.position,
        )
    except VocabularyDomainError as e:
        _raise_domain(e)
    # Reload with app
    links = await service.list_applications(sku)
    for lnk in links:
        if lnk.application_id == data.application_id:
            return ProductApplicationResponse.from_link(lnk)
    return ProductApplicationResponse.from_link(link)  # type: ignore[possibly-undefined]


@products_vocab_router.put(
    "/{sku}/applications",
    response_model=list[ProductApplicationResponse],
    summary="Reemplazar todas las aplicaciones de un producto",
    responses={404: {"model": ProblemDetails}},
)
async def replace_product_applications(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    data: list[ProductApplicationLink],
    _user: User = Depends(require_permissions("products:write")),
    service: ProductVocabularyService = Depends(get_product_vocab_service),
) -> list[ProductApplicationResponse]:
    try:
        await service.replace_applications(sku, [d.model_dump() for d in data])
    except VocabularyDomainError as e:
        _raise_domain(e)
    links = await service.list_applications(sku)
    return [ProductApplicationResponse.from_link(lnk) for lnk in links]


@products_vocab_router.delete(
    "/{sku}/applications/{app_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Eliminar aplicación de un producto",
)
async def remove_product_application(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    app_id: UUID,
    _user: User = Depends(require_permissions("products:write")),
    service: ProductVocabularyService = Depends(get_product_vocab_service),
):
    try:
        await service.remove_application(sku, app_id)
    except VocabularyDomainError as e:
        _raise_domain(e)


# ---------------------------------------------------------------------------
# Taxonomy tree — GET /taxonomy/tree
# ---------------------------------------------------------------------------
@taxonomy_router.get(
    "/tree",
    response_model=TaxonomyTreeResponse,
    summary="Árbol completo families → subfamilies → product_types",
)
async def get_taxonomy_tree(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _: Annotated[None, Depends(require_permissions("products:read"))],
) -> TaxonomyTreeResponse:
    svc = FamilyService(db)
    families = await svc.list_tree()
    return TaxonomyTreeResponse(families=list(families))
