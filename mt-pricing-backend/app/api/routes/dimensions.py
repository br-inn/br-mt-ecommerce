"""Dimensions API — Fase 3 tablas técnicas granulares (PDF §9).

Endpoints públicos (``products:read``):
- GET  /api/v1/products/{sku}/dimensions             (tabla completa)
- GET  /api/v1/products/{sku}/pressure-temperature   (curva P-T)
- GET  /api/v1/actuation-codes                       (catálogo seed)
- GET  /api/v1/standards                             (catálogo)

Admin CRUD (``admin:vocabularies``):
- POST/PATCH/DELETE /api/v1/admin/families/{family_id}/dimension-columns
- POST/PUT/DELETE   /api/v1/admin/products/{sku}/dimension-rows
- POST/PUT/DELETE   /api/v1/admin/products/{sku}/pressure-temperature
- POST/PATCH/DELETE /api/v1/admin/standards

NOTE: status_code=204 endpoints DEBEN incluir ``response_model=None``
(FastAPI 0.115 + ``from __future__ import annotations`` bug).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.schemas.common import ProblemDetails
from app.schemas.dimensions import (
    ActuationCodeResponse,
    DimensionCellCreate,
    DimensionCellPatch,
    DimensionCellResponse,
    DimensionColumnCreate,
    DimensionColumnPatch,
    DimensionColumnResponse,
    DimensionRowCreate,
    DimensionRowPatch,
    DimensionRowResponse,
    DimensionRowWithCells,
    DimensionTableResponse,
    PressureTemperatureCurveResponse,
    PressureTemperaturePointCreate,
    PressureTemperaturePointPatch,
    PressureTemperaturePointResponse,
    StandardCreate,
    StandardPatch,
    StandardResponse,
)
from app.services.dimensions.dimension_service import (
    ActuationCodeService,
    DimensionDomainError,
    DimensionService,
    PressureTemperatureService,
    StandardService,
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
router = APIRouter(tags=["dimensions"])
admin_router = APIRouter(prefix="/admin", tags=["admin:dimensions"])


# ---------------------------------------------------------------------------
# DI factories
# ---------------------------------------------------------------------------
def get_actuation_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ActuationCodeService:
    return ActuationCodeService(session)


def get_standard_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> StandardService:
    return StandardService(session)


def get_dimension_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DimensionService:
    return DimensionService(session)


def get_pt_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PressureTemperatureService:
    return PressureTemperatureService(session)


# ---------------------------------------------------------------------------
# Error helper
# ---------------------------------------------------------------------------
def _raise_domain(err: DimensionDomainError) -> None:
    raise HTTPException(
        status_code=err.status_code,
        detail={"code": err.code, "title": err.message},
    )


# ===========================================================================
# Public reads — catálogos
# ===========================================================================
@router.get(
    "/actuation-codes",
    response_model=list[ActuationCodeResponse],
    summary="List actuation codes (catálogo curado).",
)
async def list_actuation_codes(
    _user: User = Depends(require_permissions("products:read")),
    service: ActuationCodeService = Depends(get_actuation_service),
) -> list[ActuationCodeResponse]:
    rows = await service.list_all()
    return [ActuationCodeResponse.model_validate(r) for r in rows]


@router.get(
    "/standards",
    response_model=list[StandardResponse],
    summary="List standards (ASTM/EN/ISO/…).",
)
async def list_standards(
    _user: User = Depends(require_permissions("products:read")),
    service: StandardService = Depends(get_standard_service),
) -> list[StandardResponse]:
    rows = await service.list_all()
    return [StandardResponse.model_validate(r) for r in rows]


# ===========================================================================
# Public reads — dimensiones y P-T por producto
# ===========================================================================
@router.get(
    "/products/{sku}/dimensions",
    response_model=DimensionTableResponse,
    summary="Tabla de dimensiones (columnas + filas + celdas) por producto.",
    responses={404: {"model": ProblemDetails}},
)
async def get_product_dimensions(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    _user: User = Depends(require_permissions("products:read")),
    service: DimensionService = Depends(get_dimension_service),
) -> DimensionTableResponse:
    try:
        composite = await service.get_table_for_product(sku)
    except DimensionDomainError as e:
        _raise_domain(e)
    columns = [
        DimensionColumnResponse.model_validate(c) for c in composite["columns"]
    ]
    rows: list[DimensionRowWithCells] = []
    for r in composite["rows"]:
        rows.append(
            DimensionRowWithCells(
                id=r.id,
                product_sku=r.product_sku,
                size_label=r.size_label,
                dn=r.dn,
                actuation_code_id=r.actuation_code_id,
                order_index=r.order_index,
                created_at=r.created_at,
                cells=[DimensionCellResponse.model_validate(c) for c in r.cells],
            )
        )
    return DimensionTableResponse(
        product_sku=composite["product_sku"],
        family_id=composite["family_id"],
        columns=columns,
        rows=rows,
    )


@router.get(
    "/products/{sku}/pressure-temperature",
    response_model=PressureTemperatureCurveResponse,
    summary="Curva presión-temperatura para un producto.",
    responses={404: {"model": ProblemDetails}},
)
async def get_product_pt_curve(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    series_variant_code: str | None = Query(default=None, max_length=64),
    _user: User = Depends(require_permissions("products:read")),
    service: PressureTemperatureService = Depends(get_pt_service),
) -> PressureTemperatureCurveResponse:
    try:
        composite = await service.get_curve_for_product(sku, series_variant_code)
    except DimensionDomainError as e:
        _raise_domain(e)
    return PressureTemperatureCurveResponse(
        product_sku=composite["product_sku"],
        series_variant_code=composite["series_variant_code"],
        points=[
            PressureTemperaturePointResponse.model_validate(p)
            for p in composite["points"]
        ],
    )


# ===========================================================================
# Admin — Standards CRUD
# ===========================================================================
@admin_router.post(
    "/standards",
    response_model=StandardResponse,
    status_code=http_status.HTTP_201_CREATED,
    summary="[Admin] Create standard.",
    responses={409: {"model": ProblemDetails}},
)
async def admin_create_standard(
    data: StandardCreate,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: StandardService = Depends(get_standard_service),
) -> StandardResponse:
    try:
        row = await service.create(data.model_dump())
    except DimensionDomainError as e:
        _raise_domain(e)
    return StandardResponse.model_validate(row)


@admin_router.patch(
    "/standards/{std_id}",
    response_model=StandardResponse,
    summary="[Admin] Patch standard.",
    responses={404: {"model": ProblemDetails}, 409: {"model": ProblemDetails}},
)
async def admin_patch_standard(
    std_id: UUID,
    data: StandardPatch,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: StandardService = Depends(get_standard_service),
) -> StandardResponse:
    try:
        row = await service.patch(std_id, data.model_dump(exclude_unset=True))
    except DimensionDomainError as e:
        _raise_domain(e)
    return StandardResponse.model_validate(row)


@admin_router.delete(
    "/standards/{std_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="[Admin] Delete standard.",
    responses={404: {"model": ProblemDetails}},
)
async def admin_delete_standard(
    std_id: UUID,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: StandardService = Depends(get_standard_service),
):
    try:
        await service.delete(std_id)
    except DimensionDomainError as e:
        _raise_domain(e)


# ===========================================================================
# Admin — DimensionColumn CRUD (family-level)
# ===========================================================================
@admin_router.post(
    "/families/{family_id}/dimension-columns",
    response_model=DimensionColumnResponse,
    status_code=http_status.HTTP_201_CREATED,
    summary="[Admin] Create dimension column for a family.",
    responses={409: {"model": ProblemDetails}},
)
async def admin_create_dimension_column(
    family_id: UUID,
    data: DimensionColumnCreate,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: DimensionService = Depends(get_dimension_service),
) -> DimensionColumnResponse:
    try:
        row = await service.create_column(
            family_id=family_id,
            code=data.code,
            label_en=data.label_en,
            unit=data.unit,
            order_index=data.order_index,
        )
    except DimensionDomainError as e:
        _raise_domain(e)
    return DimensionColumnResponse.model_validate(row)


@admin_router.patch(
    "/families/{family_id}/dimension-columns/{column_id}",
    response_model=DimensionColumnResponse,
    summary="[Admin] Patch dimension column.",
    responses={404: {"model": ProblemDetails}},
)
async def admin_patch_dimension_column(
    family_id: UUID,  # noqa: ARG001 — kept for URL stability
    column_id: UUID,
    data: DimensionColumnPatch,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: DimensionService = Depends(get_dimension_service),
) -> DimensionColumnResponse:
    try:
        row = await service.patch_column(
            column_id, data.model_dump(exclude_unset=True)
        )
    except DimensionDomainError as e:
        _raise_domain(e)
    return DimensionColumnResponse.model_validate(row)


@admin_router.delete(
    "/families/{family_id}/dimension-columns/{column_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="[Admin] Delete dimension column.",
    responses={404: {"model": ProblemDetails}, 409: {"model": ProblemDetails}},
)
async def admin_delete_dimension_column(
    family_id: UUID,  # noqa: ARG001
    column_id: UUID,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: DimensionService = Depends(get_dimension_service),
):
    try:
        await service.delete_column(column_id)
    except DimensionDomainError as e:
        _raise_domain(e)


# ===========================================================================
# Admin — DimensionRow CRUD (per product) + Cell upsert
# ===========================================================================
@admin_router.post(
    "/products/{sku}/dimension-rows",
    response_model=DimensionRowResponse,
    status_code=http_status.HTTP_201_CREATED,
    summary="[Admin] Create / upsert dimension row for a product.",
    responses={404: {"model": ProblemDetails}, 409: {"model": ProblemDetails}},
)
async def admin_create_dimension_row(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    data: DimensionRowCreate,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: DimensionService = Depends(get_dimension_service),
) -> DimensionRowResponse:
    try:
        row = await service.upsert_row(
            product_sku=sku,
            size_label=data.size_label,
            dn=data.dn,
            actuation_code_id=data.actuation_code_id,
            order_index=data.order_index,
        )
        # Optionally bulk-set cells if provided.
        for cell_payload in data.cells:
            await service.set_cell(
                row_id=row.id,
                column_id=cell_payload.column_id,
                value_number=cell_payload.value_number,
                value_text=cell_payload.value_text,
            )
    except DimensionDomainError as e:
        _raise_domain(e)
    return DimensionRowResponse.model_validate(row)


@admin_router.put(
    "/products/{sku}/dimension-rows/{row_id}",
    response_model=DimensionRowResponse,
    summary="[Admin] Patch dimension row.",
    responses={404: {"model": ProblemDetails}},
)
async def admin_patch_dimension_row(
    sku: Annotated[str, Path(min_length=1, max_length=64)],  # noqa: ARG001
    row_id: UUID,
    data: DimensionRowPatch,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: DimensionService = Depends(get_dimension_service),
) -> DimensionRowResponse:
    try:
        row = await service.patch_row(row_id, data.model_dump(exclude_unset=True))
    except DimensionDomainError as e:
        _raise_domain(e)
    return DimensionRowResponse.model_validate(row)


@admin_router.delete(
    "/products/{sku}/dimension-rows/{row_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="[Admin] Delete dimension row.",
    responses={404: {"model": ProblemDetails}},
)
async def admin_delete_dimension_row(
    sku: Annotated[str, Path(min_length=1, max_length=64)],  # noqa: ARG001
    row_id: UUID,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: DimensionService = Depends(get_dimension_service),
):
    try:
        await service.delete_row(row_id)
    except DimensionDomainError as e:
        _raise_domain(e)


@admin_router.put(
    "/products/{sku}/dimension-rows/{row_id}/cells/{column_id}",
    response_model=DimensionCellResponse,
    summary="[Admin] Upsert dimension cell value.",
    responses={
        400: {"model": ProblemDetails},
        404: {"model": ProblemDetails},
        409: {"model": ProblemDetails},
    },
)
async def admin_upsert_dimension_cell(
    sku: Annotated[str, Path(min_length=1, max_length=64)],  # noqa: ARG001
    row_id: UUID,
    column_id: UUID,
    data: DimensionCellPatch,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: DimensionService = Depends(get_dimension_service),
) -> DimensionCellResponse:
    try:
        cell = await service.set_cell(
            row_id=row_id,
            column_id=column_id,
            value_number=data.value_number,
            value_text=data.value_text,
        )
    except DimensionDomainError as e:
        _raise_domain(e)
    return DimensionCellResponse.model_validate(cell)


# ===========================================================================
# Admin — PressureTemperaturePoint CRUD
# ===========================================================================
@admin_router.post(
    "/products/{sku}/pressure-temperature",
    response_model=PressureTemperaturePointResponse,
    status_code=http_status.HTTP_201_CREATED,
    summary="[Admin] Add pressure-temperature point.",
    responses={404: {"model": ProblemDetails}, 400: {"model": ProblemDetails}},
)
async def admin_add_pt_point(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    data: PressureTemperaturePointCreate,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: PressureTemperatureService = Depends(get_pt_service),
) -> PressureTemperaturePointResponse:
    try:
        row = await service.add_point(
            sku,
            temperature_c=data.temperature_c,
            pressure_max_bar=data.pressure_max_bar,
            series_variant_code=data.series_variant_code,
            condition_en=data.condition_en,
            order_index=data.order_index,
        )
    except DimensionDomainError as e:
        _raise_domain(e)
    return PressureTemperaturePointResponse.model_validate(row)


@admin_router.put(
    "/products/{sku}/pressure-temperature/{point_id}",
    response_model=PressureTemperaturePointResponse,
    summary="[Admin] Patch pressure-temperature point.",
    responses={404: {"model": ProblemDetails}},
)
async def admin_patch_pt_point(
    sku: Annotated[str, Path(min_length=1, max_length=64)],  # noqa: ARG001
    point_id: UUID,
    data: PressureTemperaturePointPatch,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: PressureTemperatureService = Depends(get_pt_service),
) -> PressureTemperaturePointResponse:
    try:
        row = await service.patch_point(
            point_id, data.model_dump(exclude_unset=True)
        )
    except DimensionDomainError as e:
        _raise_domain(e)
    return PressureTemperaturePointResponse.model_validate(row)


@admin_router.delete(
    "/products/{sku}/pressure-temperature/{point_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="[Admin] Delete pressure-temperature point.",
    responses={404: {"model": ProblemDetails}},
)
async def admin_delete_pt_point(
    sku: Annotated[str, Path(min_length=1, max_length=64)],  # noqa: ARG001
    point_id: UUID,
    _user: User = Depends(require_permissions("admin:vocabularies")),
    service: PressureTemperatureService = Depends(get_pt_service),
):
    try:
        await service.delete_point(point_id)
    except DimensionDomainError as e:
        _raise_domain(e)
