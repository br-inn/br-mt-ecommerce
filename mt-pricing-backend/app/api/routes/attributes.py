"""Attributes API — Fase 2 EAV typed attribute system.

Endpoints:

Public reads (products:read):
- GET  /api/v1/attributes
- GET  /api/v1/attributes/{attr_id}/options
- GET  /api/v1/families/{family_id}/attributes

Admin CRUD (admin:vocabularies):
- POST /api/v1/admin/attributes
- PATCH /api/v1/admin/attributes/{attr_id}
- DELETE /api/v1/admin/attributes/{attr_id}
- POST /api/v1/admin/attributes/{attr_id}/options
- PATCH /api/v1/admin/attributes/{attr_id}/options/{option_id}
- DELETE /api/v1/admin/attributes/{attr_id}/options/{option_id}
- POST /api/v1/admin/families/{family_id}/attributes/{attr_id}
- DELETE /api/v1/admin/families/{family_id}/attributes/{attr_id}

Product attribute values:
- GET  /api/v1/products/{sku}/attributes
- PUT  /api/v1/products/{sku}/attributes/{attr_code}
- DELETE /api/v1/products/{sku}/attributes/{attr_code}

NOTE: status_code=204 endpoints MUST include response_model=None
(FastAPI 0.115 + from_future_annotations bug — see Fase 0 doc).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.schemas.attributes import (
    AttributeDefinitionCreate,
    AttributeDefinitionPatch,
    AttributeDefinitionResponse,
    AttributeOptionCreate,
    AttributeOptionPatch,
    AttributeOptionResponse,
    AttributeValueCreate,
    AttributeValueResponse,
    FamilyAttributeCreate,
    FamilyAttributeResponse,
    FamilyAttributeWithDefinition,
)
from app.schemas.common import ProblemDetails
from app.services.attributes.attribute_service import (
    AttributeDomainError,
    AttributeService,
    AttributeValueService,
    FamilyAttributeService,
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
# Public reads
router = APIRouter(tags=["attributes"])

# Admin
admin_attributes_router = APIRouter(
    prefix="/admin",
    tags=["admin:attributes"],
)

# Product sub-resource (mounted under /products by aggregator)
products_attributes_router = APIRouter(tags=["products:attributes"])


# ---------------------------------------------------------------------------
# DI factories
# ---------------------------------------------------------------------------
def get_attribute_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AttributeService:
    return AttributeService(session)


def get_family_attribute_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FamilyAttributeService:
    return FamilyAttributeService(session)


def get_attribute_value_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AttributeValueService:
    return AttributeValueService(session)


# ---------------------------------------------------------------------------
# Error helper
# ---------------------------------------------------------------------------
def _raise_domain(err: AttributeDomainError) -> None:
    raise HTTPException(
        status_code=err.status_code,
        detail={"code": err.code, "title": err.message},
    )


# ===========================================================================
# Public reads
# ===========================================================================
@router.get(
    "/attributes",
    response_model=list[AttributeDefinitionResponse],
    summary="List attribute definitions",
)
async def list_attributes(
    only_filterable: bool = Query(default=False),
    only_seo: bool = Query(default=False),
    scope: str | None = Query(default=None, pattern=r"^(product|variant|both)$"),
    _user: User = Depends(require_permissions("products:read")),
    service: AttributeService = Depends(get_attribute_service),
) -> list[AttributeDefinitionResponse]:
    rows = await service.list_definitions(
        only_filterable=only_filterable,
        only_seo=only_seo,
        scope=scope,
    )
    return [AttributeDefinitionResponse.model_validate(r) for r in rows]


@router.get(
    "/attributes/{attr_id}/options",
    response_model=list[AttributeOptionResponse],
    summary="List options for an enum attribute",
    responses={404: {"model": ProblemDetails}},
)
async def list_attribute_options(
    attr_id: UUID,
    _user: User = Depends(require_permissions("products:read")),
    service: AttributeService = Depends(get_attribute_service),
) -> list[AttributeOptionResponse]:
    try:
        await service.get_definition(attr_id)
    except AttributeDomainError as e:
        _raise_domain(e)
    rows = await service.list_options(attr_id)
    return [AttributeOptionResponse.model_validate(r) for r in rows]


@router.get(
    "/families/{family_id}/attributes",
    response_model=list[FamilyAttributeWithDefinition],
    summary="List attribute template for a family",
)
async def list_family_attributes(
    family_id: UUID,
    _user: User = Depends(require_permissions("products:read")),
    service: FamilyAttributeService = Depends(get_family_attribute_service),
) -> list[FamilyAttributeWithDefinition]:
    rows = await service.list_for_family(family_id)
    out: list[FamilyAttributeWithDefinition] = []
    for r in rows:
        out.append(
            FamilyAttributeWithDefinition(
                id=r.id,
                family_id=r.family_id,
                attribute_id=r.attribute_id,
                group_code=r.group_code,
                order_index=r.order_index,
                is_required=r.is_required,
                default_value=r.default_value,
                validation_rule=r.validation_rule,
                attribute=AttributeDefinitionResponse.model_validate(r.attribute),
            )
        )
    return out


# ===========================================================================
# Admin: AttributeDefinition CRUD
# ===========================================================================
@admin_attributes_router.post(
    "/attributes",
    response_model=AttributeDefinitionResponse,
    status_code=http_status.HTTP_201_CREATED,
    summary="[Admin] Create attribute definition",
    responses={409: {"model": ProblemDetails}},
)
async def admin_create_attribute(
    data: AttributeDefinitionCreate,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: AttributeService = Depends(get_attribute_service),
) -> AttributeDefinitionResponse:
    try:
        row = await service.create_definition(data.model_dump())
    except AttributeDomainError as e:
        _raise_domain(e)
    return AttributeDefinitionResponse.model_validate(row)


@admin_attributes_router.patch(
    "/attributes/{attr_id}",
    response_model=AttributeDefinitionResponse,
    summary="[Admin] Patch attribute definition",
    responses={404: {"model": ProblemDetails}},
)
async def admin_patch_attribute(
    attr_id: UUID,
    data: AttributeDefinitionPatch,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: AttributeService = Depends(get_attribute_service),
) -> AttributeDefinitionResponse:
    try:
        row = await service.patch_definition(
            attr_id, data.model_dump(exclude_unset=True)
        )
    except AttributeDomainError as e:
        _raise_domain(e)
    return AttributeDefinitionResponse.model_validate(row)


@admin_attributes_router.delete(
    "/attributes/{attr_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="[Admin] Delete attribute definition",
    responses={404: {"model": ProblemDetails}, 409: {"model": ProblemDetails}},
)
async def admin_delete_attribute(
    attr_id: UUID,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: AttributeService = Depends(get_attribute_service),
):
    try:
        await service.delete_definition(attr_id)
    except AttributeDomainError as e:
        _raise_domain(e)


# ===========================================================================
# Admin: AttributeOption CRUD
# ===========================================================================
@admin_attributes_router.post(
    "/attributes/{attr_id}/options",
    response_model=AttributeOptionResponse,
    status_code=http_status.HTTP_201_CREATED,
    summary="[Admin] Create option for an enum attribute",
    responses={400: {"model": ProblemDetails}, 409: {"model": ProblemDetails}},
)
async def admin_create_option(
    attr_id: UUID,
    data: AttributeOptionCreate,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: AttributeService = Depends(get_attribute_service),
) -> AttributeOptionResponse:
    try:
        row = await service.create_option(attr_id, data.model_dump())
    except AttributeDomainError as e:
        _raise_domain(e)
    return AttributeOptionResponse.model_validate(row)


@admin_attributes_router.patch(
    "/attributes/{attr_id}/options/{option_id}",
    response_model=AttributeOptionResponse,
    summary="[Admin] Patch attribute option",
    responses={404: {"model": ProblemDetails}},
)
async def admin_patch_option(
    attr_id: UUID,  # noqa: ARG001 — kept for URL stability
    option_id: UUID,
    data: AttributeOptionPatch,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: AttributeService = Depends(get_attribute_service),
) -> AttributeOptionResponse:
    try:
        row = await service.patch_option(
            option_id, data.model_dump(exclude_unset=True)
        )
    except AttributeDomainError as e:
        _raise_domain(e)
    return AttributeOptionResponse.model_validate(row)


@admin_attributes_router.delete(
    "/attributes/{attr_id}/options/{option_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="[Admin] Delete attribute option",
    responses={404: {"model": ProblemDetails}},
)
async def admin_delete_option(
    attr_id: UUID,  # noqa: ARG001
    option_id: UUID,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: AttributeService = Depends(get_attribute_service),
):
    try:
        await service.delete_option(option_id)
    except AttributeDomainError as e:
        _raise_domain(e)


# ===========================================================================
# Admin: FamilyAttribute link/unlink
# ===========================================================================
@admin_attributes_router.post(
    "/families/{family_id}/attributes/{attr_id}",
    response_model=FamilyAttributeResponse,
    status_code=http_status.HTTP_201_CREATED,
    summary="[Admin] Link attribute to family template",
    responses={404: {"model": ProblemDetails}, 409: {"model": ProblemDetails}},
)
async def admin_link_family_attribute(
    family_id: UUID,
    attr_id: UUID,
    data: FamilyAttributeCreate,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: FamilyAttributeService = Depends(get_family_attribute_service),
) -> FamilyAttributeResponse:
    # data.attribute_id must match path
    if data.attribute_id != attr_id:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "family_attribute_id_mismatch",
                "title": "Body attribute_id does not match URL attr_id",
            },
        )
    payload = data.model_dump()
    try:
        row = await service.link(family_id, attr_id, payload)
    except AttributeDomainError as e:
        _raise_domain(e)
    return FamilyAttributeResponse.model_validate(row)


@admin_attributes_router.delete(
    "/families/{family_id}/attributes/{attr_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="[Admin] Unlink attribute from family template",
    responses={404: {"model": ProblemDetails}},
)
async def admin_unlink_family_attribute(
    family_id: UUID,
    attr_id: UUID,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: FamilyAttributeService = Depends(get_family_attribute_service),
):
    try:
        await service.unlink(family_id, attr_id)
    except AttributeDomainError as e:
        _raise_domain(e)


# ===========================================================================
# Product attribute values
# ===========================================================================
@products_attributes_router.get(
    "/{sku}/attributes",
    response_model=list[AttributeValueResponse],
    summary="List all attribute values for a product",
)
async def list_product_attributes(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    _user: User = Depends(require_permissions("products:read")),
    service: AttributeValueService = Depends(get_attribute_value_service),
) -> list[AttributeValueResponse]:
    rows = await service.list_for_product(sku)
    return [AttributeValueResponse.model_validate(r) for r in rows]


@products_attributes_router.put(
    "/{sku}/attributes/{attr_code}",
    response_model=AttributeValueResponse,
    summary="Upsert attribute value for a product",
    responses={
        404: {"model": ProblemDetails},
        409: {"model": ProblemDetails},
        400: {"model": ProblemDetails},
    },
)
async def upsert_product_attribute(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    attr_code: Annotated[str, Path(min_length=1, max_length=64)],
    data: AttributeValueCreate,
    _user: User = Depends(require_permissions("products:write")),
    service: AttributeValueService = Depends(get_attribute_value_service),
) -> AttributeValueResponse:
    try:
        row = await service.upsert_for_product(sku, attr_code, data)
    except AttributeDomainError as e:
        _raise_domain(e)
    return AttributeValueResponse.model_validate(row)


@products_attributes_router.delete(
    "/{sku}/attributes/{attr_code}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete attribute value for a product",
    responses={404: {"model": ProblemDetails}},
)
async def delete_product_attribute(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    attr_code: Annotated[str, Path(min_length=1, max_length=64)],
    _user: User = Depends(require_permissions("products:write")),
    service: AttributeValueService = Depends(get_attribute_value_service),
):
    try:
        await service.delete_for_product(sku, attr_code)
    except AttributeDomainError as e:
        _raise_domain(e)
