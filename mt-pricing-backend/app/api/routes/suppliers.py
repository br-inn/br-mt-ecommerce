"""Suppliers — API v1 routes (US-1A-03-02 backend half).

Convenciones (alineadas con `mt-api-contract-openapi.yaml` §Suppliers):
- Path PK = ``code`` (string TEXT).
- Cursor-based pagination (cursor opaco base64url(json({"code": "..."}))).
- RBAC: read=``suppliers:read``, write=``suppliers:write``, deactivate=write.
- Soft-delete only (BR VAT-compliance) — ``DELETE /suppliers/{code}`` retorna
  405 sin tocar la fila; el endpoint operativo es PATCH active=false.
- Audit emission desde el service.
- Errores → ``ProblemDetails`` RFC 7807.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.api.pagination import decode_cursor, encode_cursor
from app.db.models.user import User
from app.schemas.common import Cursor, Pagination, ProblemDetails
from app.schemas.supplier import (
    SupplierCreate,
    SupplierPatch,
    SupplierResponse,
    SupplierUpdate,
)
from app.services.suppliers import SupplierService
from app.services.suppliers.supplier_service import SupplierDomainError

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


def get_supplier_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SupplierService:
    return SupplierService(session)


def _raise_domain(err: SupplierDomainError) -> None:
    raise HTTPException(
        status_code=err.status_code,
        detail={"code": err.code, "title": err.message},
    )


def _decode_code_cursor(cursor: str | None) -> str | None:
    if cursor is None:
        return None
    payload = decode_cursor(cursor)
    code = payload.get("code")
    if not isinstance(code, str) or not code:
        raise HTTPException(
            status_code=400,
            detail={
                "type": "https://mtme-api/errors/invalid-cursor",
                "title": "Invalid cursor",
                "status": 400,
                "code": "invalid_cursor",
                "detail": "Cursor falta clave 'code'.",
            },
        )
    return code


def _encode_code_cursor(code: str | None) -> str | None:
    if code is None:
        return None
    return encode_cursor({"code": code})


# =============================================================================
# Listing / CRUD
# =============================================================================
@router.get(
    "",
    response_model=Pagination[SupplierResponse],
    summary="Listar proveedores con filtros y cursor pagination",
)
async def list_suppliers(
    active: Annotated[bool | None, Query()] = None,
    contract_currency: Annotated[
        str | None, Query(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    ] = None,
    q: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    include_total: Annotated[bool, Query()] = False,
    _user: User = Depends(require_permissions("suppliers:read")),
    service: SupplierService = Depends(get_supplier_service),
) -> Pagination[SupplierResponse]:
    code_cursor = _decode_code_cursor(cursor)
    rows, next_code, total = await service.list_suppliers(
        active=active,
        contract_currency=contract_currency,
        search=q,
        cursor=code_cursor,
        limit=limit,
        include_total=include_total,
    )
    return Pagination[SupplierResponse](
        items=[SupplierResponse.model_validate(r) for r in rows],
        cursor=Cursor(next=_encode_code_cursor(next_code)),
        page_size=limit,
        total=total,
    )


@router.post(
    "",
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear proveedor",
    responses={
        409: {"model": ProblemDetails, "description": "Code duplicado"},
        422: {"model": ProblemDetails, "description": "Currency inválida o validación"},
    },
)
async def create_supplier(
    data: SupplierCreate,
    user: Annotated[User, Depends(require_permissions("suppliers:write"))],
    service: Annotated[SupplierService, Depends(get_supplier_service)],
) -> SupplierResponse:
    try:
        sup = await service.create_supplier(data.model_dump(), user)
    except SupplierDomainError as e:
        _raise_domain(e)
    return SupplierResponse.model_validate(sup)


@router.get(
    "/{code}",
    response_model=SupplierResponse,
    summary="Obtener proveedor por code",
    responses={404: {"model": ProblemDetails}},
)
async def get_supplier(
    code: Annotated[str, Path(min_length=1, max_length=64)],
    _user: User = Depends(require_permissions("suppliers:read")),
    service: SupplierService = Depends(get_supplier_service),
) -> SupplierResponse:
    try:
        sup = await service.get_by_code(code)
    except SupplierDomainError as e:
        _raise_domain(e)
    return SupplierResponse.model_validate(sup)


@router.put(
    "/{code}",
    response_model=SupplierResponse,
    summary="Reemplazar proveedor (PUT, full update)",
    responses={
        404: {"model": ProblemDetails},
        422: {"model": ProblemDetails},
    },
)
async def replace_supplier(
    code: Annotated[str, Path(min_length=1, max_length=64)],
    data: SupplierUpdate,
    user: Annotated[User, Depends(require_permissions("suppliers:write"))],
    service: Annotated[SupplierService, Depends(get_supplier_service)],
) -> SupplierResponse:
    try:
        sup = await service.replace_supplier(code, data.model_dump(), user)
    except SupplierDomainError as e:
        _raise_domain(e)
    return SupplierResponse.model_validate(sup)


@router.patch(
    "/{code}",
    response_model=SupplierResponse,
    summary="Actualizar parcialmente proveedor",
    responses={404: {"model": ProblemDetails}},
)
async def patch_supplier(
    code: Annotated[str, Path(min_length=1, max_length=64)],
    data: SupplierPatch,
    user: Annotated[User, Depends(require_permissions("suppliers:write"))],
    service: Annotated[SupplierService, Depends(get_supplier_service)],
) -> SupplierResponse:
    try:
        sup = await service.patch_supplier(code, data.model_dump(exclude_unset=True), user)
    except SupplierDomainError as e:
        _raise_domain(e)
    return SupplierResponse.model_validate(sup)


@router.delete(
    "/{code}",
    status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
    response_class=Response,
    summary="DELETE bloqueado (VAT-compliance) — usar PATCH active=false",
    responses={
        405: {
            "model": ProblemDetails,
            "description": "DELETE no permitido (BR VAT-compliance UAE)",
        }
    },
)
async def delete_supplier_blocked(
    code: Annotated[str, Path(min_length=1, max_length=64)],
    _user: User = Depends(require_permissions("suppliers:write")),
) -> Any:
    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail={
            "code": "vat_compliance_block",
            "title": "DELETE no permitido sobre suppliers (BR VAT-compliance UAE).",
            "detail": "Usa PATCH /suppliers/{code} con `active=false` para desactivar.",
        },
    )
