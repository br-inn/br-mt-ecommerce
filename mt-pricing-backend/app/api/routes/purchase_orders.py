"""Purchase Orders API v1 — EP-INV-01 (US-INV-01-03).

Endpoints:
- POST   /purchase-orders               — crea PO en estado draft
- GET    /purchase-orders               — lista con filtros + cursor pagination
- GET    /purchase-orders/{id}          — detalle con líneas y gr_count
- PUT    /purchase-orders/{id}          — actualiza PO (solo draft)
- POST   /purchase-orders/{id}/confirm  — draft → confirmed
- POST   /purchase-orders/{id}/cancel   — cualquier estado → cancelled
- DELETE /purchase-orders/{id}          — elimina PO (solo draft)
- POST   /purchase-orders/{id}/lines              — agrega línea (solo draft)
- PUT    /purchase-orders/{id}/lines/{line_id}    — edita línea (solo draft)
- DELETE /purchase-orders/{id}/lines/{line_id}    — elimina línea (solo draft)

Permiso requerido: purchases:write.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.repositories.purchase_order import PurchaseOrderRepository
from app.schemas.common import Cursor, Pagination, ProblemDetails
from app.schemas.purchase_orders import (
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
    PurchaseOrderLineRead,
    PurchaseOrderLineUpdate,
    PurchaseOrderRead,
    PurchaseOrderReadDetail,
    PurchaseOrderUpdate,
)

router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])


def _to_read(po) -> PurchaseOrderRead:
    return PurchaseOrderRead.model_validate(po)


def _to_detail(po) -> PurchaseOrderReadDetail:
    gr_count = getattr(po, "gr_count", 0)
    lines = getattr(po, "lines", [])
    data = PurchaseOrderRead.model_validate(po).model_dump()
    data["lines"] = [PurchaseOrderLineRead.model_validate(line) for line in lines]
    data["gr_count"] = gr_count
    return PurchaseOrderReadDetail(**data)


def _to_line_read(line) -> PurchaseOrderLineRead:
    return PurchaseOrderLineRead.model_validate(line)


# ---------------------------------------------------------------------------
# POST /purchase-orders
# ---------------------------------------------------------------------------
@router.post(
    "",
    response_model=PurchaseOrderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear Purchase Order en estado draft",
    operation_id="purchaseOrdersCreate",
    responses={
        404: {"model": ProblemDetails},
        422: {"model": ProblemDetails},
    },
)
async def create_purchase_order(
    data: PurchaseOrderCreate,
    user: Annotated[User, Depends(require_permissions("purchases:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PurchaseOrderRead:
    repo = PurchaseOrderRepository(session)
    po = await repo.create(data, created_by=user.id)
    return _to_read(po)


# ---------------------------------------------------------------------------
# GET /purchase-orders
# ---------------------------------------------------------------------------
@router.get(
    "",
    response_model=Pagination[PurchaseOrderRead],
    summary="Listar Purchase Orders con filtros y cursor pagination",
    operation_id="purchaseOrdersList",
)
async def list_purchase_orders(
    supplier_code: Annotated[str | None, Query(max_length=64)] = None,
    status: Annotated[str | None, Query(max_length=32)] = None,
    q: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    _user: User = Depends(require_permissions("purchases:write")),
    session: AsyncSession = Depends(get_db_session),
) -> Pagination[PurchaseOrderRead]:
    repo = PurchaseOrderRepository(session)
    rows, next_cursor = await repo.list(
        supplier_code=supplier_code,
        status=status,
        q=q,
        cursor=cursor,
        limit=limit,
    )
    return Pagination[PurchaseOrderRead](
        items=[_to_read(r) for r in rows],
        cursor=Cursor(next=next_cursor),
        page_size=limit,
    )


# ---------------------------------------------------------------------------
# GET /purchase-orders/{id}
# ---------------------------------------------------------------------------
@router.get(
    "/{po_id}",
    response_model=PurchaseOrderReadDetail,
    summary="Obtener detalle de Purchase Order con líneas y GRs",
    operation_id="purchaseOrdersGet",
    responses={404: {"model": ProblemDetails}},
)
async def get_purchase_order(
    po_id: UUID,
    _user: Annotated[User, Depends(require_permissions("purchases:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PurchaseOrderReadDetail:
    repo = PurchaseOrderRepository(session)
    po = await repo.get_detail(po_id)
    if po is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail={"code": "po_not_found", "title": "Purchase Order no existe"},
        )
    return _to_detail(po)


# ---------------------------------------------------------------------------
# PUT /purchase-orders/{id}
# ---------------------------------------------------------------------------
@router.put(
    "/{po_id}",
    response_model=PurchaseOrderRead,
    summary="Actualizar Purchase Order (solo en estado draft)",
    operation_id="purchaseOrdersUpdate",
    responses={
        404: {"model": ProblemDetails},
        422: {"model": ProblemDetails},
    },
)
async def update_purchase_order(
    po_id: UUID,
    data: PurchaseOrderUpdate,
    _user: Annotated[User, Depends(require_permissions("purchases:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PurchaseOrderRead:
    repo = PurchaseOrderRepository(session)
    po = await repo.update(po_id, data)
    return _to_read(po)


# ---------------------------------------------------------------------------
# POST /purchase-orders/{id}/confirm
# ---------------------------------------------------------------------------
@router.post(
    "/{po_id}/confirm",
    response_model=PurchaseOrderRead,
    summary="Confirmar PO (draft → confirmed)",
    operation_id="purchaseOrdersConfirm",
    responses={
        404: {"model": ProblemDetails},
        422: {"model": ProblemDetails},
    },
)
async def confirm_purchase_order(
    po_id: UUID,
    _user: Annotated[User, Depends(require_permissions("purchases:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PurchaseOrderRead:
    repo = PurchaseOrderRepository(session)
    po = await repo.confirm(po_id)
    return _to_read(po)


# ---------------------------------------------------------------------------
# POST /purchase-orders/{id}/cancel
# ---------------------------------------------------------------------------
@router.post(
    "/{po_id}/cancel",
    response_model=PurchaseOrderRead,
    summary="Cancelar PO (valida sin GRs procesados)",
    operation_id="purchaseOrdersCancel",
    responses={
        404: {"model": ProblemDetails},
        422: {"model": ProblemDetails},
    },
)
async def cancel_purchase_order(
    po_id: UUID,
    _user: Annotated[User, Depends(require_permissions("purchases:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PurchaseOrderRead:
    repo = PurchaseOrderRepository(session)
    po = await repo.cancel(po_id)
    return _to_read(po)


# ---------------------------------------------------------------------------
# DELETE /purchase-orders/{id}
# ---------------------------------------------------------------------------
@router.delete(
    "/{po_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Eliminar PO (solo en estado draft)",
    operation_id="purchaseOrdersDelete",
    responses={
        404: {"model": ProblemDetails},
        422: {"model": ProblemDetails},
    },
)
async def delete_purchase_order(
    po_id: UUID,
    _user: Annotated[User, Depends(require_permissions("purchases:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    repo = PurchaseOrderRepository(session)
    await repo.delete(po_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# POST /purchase-orders/{id}/lines
# ---------------------------------------------------------------------------
@router.post(
    "/{po_id}/lines",
    response_model=PurchaseOrderLineRead,
    status_code=status.HTTP_201_CREATED,
    summary="Agregar línea al PO (solo en estado draft)",
    operation_id="purchaseOrdersAddLine",
    responses={
        404: {"model": ProblemDetails},
        422: {"model": ProblemDetails},
    },
)
async def add_line(
    po_id: UUID,
    data: PurchaseOrderLineCreate,
    _user: Annotated[User, Depends(require_permissions("purchases:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PurchaseOrderLineRead:
    repo = PurchaseOrderRepository(session)
    line = await repo.add_line(po_id, data)
    return _to_line_read(line)


# ---------------------------------------------------------------------------
# PUT /purchase-orders/{id}/lines/{line_id}
# ---------------------------------------------------------------------------
@router.put(
    "/{po_id}/lines/{line_id}",
    response_model=PurchaseOrderLineRead,
    summary="Actualizar línea del PO (solo en estado draft)",
    operation_id="purchaseOrdersUpdateLine",
    responses={
        404: {"model": ProblemDetails},
        422: {"model": ProblemDetails},
    },
)
async def update_line(
    po_id: UUID,
    line_id: UUID,
    data: PurchaseOrderLineUpdate,
    _user: Annotated[User, Depends(require_permissions("purchases:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PurchaseOrderLineRead:
    repo = PurchaseOrderRepository(session)
    line = await repo.update_line(po_id, line_id, data)
    return _to_line_read(line)


# ---------------------------------------------------------------------------
# DELETE /purchase-orders/{id}/lines/{line_id}
# ---------------------------------------------------------------------------
@router.delete(
    "/{po_id}/lines/{line_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Eliminar línea del PO (solo en estado draft)",
    operation_id="purchaseOrdersDeleteLine",
    responses={
        404: {"model": ProblemDetails},
        422: {"model": ProblemDetails},
    },
)
async def delete_line(
    po_id: UUID,
    line_id: UUID,
    _user: Annotated[User, Depends(require_permissions("purchases:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    repo = PurchaseOrderRepository(session)
    await repo.delete_line(po_id, line_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
