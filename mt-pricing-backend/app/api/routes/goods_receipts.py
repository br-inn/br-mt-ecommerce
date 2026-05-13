"""Goods Receipts API v1 — EP-INV-01 (US-INV-01-04).

Endpoints:
- POST   /goods-receipts               — registra recepción (→ recalc_map_on_gr)
- GET    /goods-receipts               — lista con filtros + cursor pagination
- GET    /goods-receipts/{id}          — detalle con po_line inline
- GET    /goods-receipts/{id}/status   — polling ligero (status + map values)
- POST   /goods-receipts/{id}/retry    — re-encola si status='error'

Permiso requerido: purchases:write.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.repositories.goods_receipt import GoodsReceiptRepository
from app.schemas.common import Cursor, Pagination, ProblemDetails
from app.schemas.goods_receipts import (
    GoodsReceiptCreate,
    GoodsReceiptRead,
    GoodsReceiptStatusRead,
)
from app.schemas.purchase_orders import PurchaseOrderLineRead

router = APIRouter(prefix="/goods-receipts", tags=["goods-receipts"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_read(gr) -> GoodsReceiptRead:  # type: ignore[no-untyped-def]
    pol = gr.po_line
    pol_read = PurchaseOrderLineRead.model_validate(pol)
    data = {
        "id": gr.id,
        "po_line_id": gr.po_line_id,
        "qty_received": gr.qty_received,
        "received_at": gr.received_at,
        "received_by": gr.received_by,
        "actual_unit_price": gr.actual_unit_price,
        "actual_breakdown": gr.actual_breakdown,
        "map_before": gr.map_before,
        "map_after": gr.map_after,
        "fx_rate_id": gr.fx_rate_id,
        "notes": gr.notes,
        "status": gr.status,
        "processed_at": gr.processed_at,
        "created_at": gr.created_at,
        "po_line": pol_read,
    }
    return GoodsReceiptRead(**data)


# ---------------------------------------------------------------------------
# POST /goods-receipts
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=GoodsReceiptRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una recepción de mercancía",
    operation_id="goodsReceiptsCreate",
    responses={
        404: {"model": ProblemDetails},
        422: {"model": ProblemDetails},
    },
)
async def create_goods_receipt(
    data: GoodsReceiptCreate,
    user: Annotated[User, Depends(require_permissions("purchases:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> GoodsReceiptRead:
    repo = GoodsReceiptRepository(session)
    gr = await repo.create(data, received_by=user.id)
    await session.commit()
    await session.refresh(gr)

    # Recargar con relaciones tras commit
    gr_loaded = await repo.get(gr.id)
    assert gr_loaded is not None  # noqa: S101

    # Disparar tarea asíncrona
    from app.workers.tasks.inventory import recalc_map_on_gr

    recalc_map_on_gr.delay(str(gr_loaded.id))

    return _to_read(gr_loaded)


# ---------------------------------------------------------------------------
# GET /goods-receipts
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=Pagination[GoodsReceiptRead],
    summary="Listar Goods Receipts con filtros y cursor pagination",
    operation_id="goodsReceiptsList",
)
async def list_goods_receipts(
    sku: Annotated[str | None, Query(max_length=64)] = None,
    po_id: Annotated[UUID | None, Query()] = None,
    status: Annotated[str | None, Query(max_length=32)] = None,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    _user: User = Depends(require_permissions("purchases:write")),
    session: AsyncSession = Depends(get_db_session),
) -> Pagination[GoodsReceiptRead]:
    repo = GoodsReceiptRepository(session)
    rows, next_cursor = await repo.list(
        sku=sku,
        po_id=po_id,
        status_filter=status,
        cursor=cursor,
        limit=limit,
    )
    return Pagination[GoodsReceiptRead](
        items=[_to_read(r) for r in rows],
        cursor=Cursor(next=next_cursor),
        page_size=limit,
    )


# ---------------------------------------------------------------------------
# GET /goods-receipts/{id}
# ---------------------------------------------------------------------------


@router.get(
    "/{gr_id}",
    response_model=GoodsReceiptRead,
    summary="Detalle de un Goods Receipt",
    operation_id="goodsReceiptsGet",
    responses={404: {"model": ProblemDetails}},
)
async def get_goods_receipt(
    gr_id: UUID,
    _user: Annotated[User, Depends(require_permissions("purchases:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> GoodsReceiptRead:
    from fastapi import HTTPException

    repo = GoodsReceiptRepository(session)
    gr = await repo.get(gr_id)
    if gr is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "gr_not_found", "title": "Goods Receipt no encontrado"},
        )
    return _to_read(gr)


# ---------------------------------------------------------------------------
# GET /goods-receipts/{id}/status
# ---------------------------------------------------------------------------


@router.get(
    "/{gr_id}/status",
    response_model=GoodsReceiptStatusRead,
    summary="Polling ligero de estado de un Goods Receipt",
    operation_id="goodsReceiptsGetStatus",
    responses={404: {"model": ProblemDetails}},
)
async def get_goods_receipt_status(
    gr_id: UUID,
    _user: Annotated[User, Depends(require_permissions("purchases:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> GoodsReceiptStatusRead:
    repo = GoodsReceiptRepository(session)
    return await repo.get_status(gr_id)


# ---------------------------------------------------------------------------
# POST /goods-receipts/{id}/retry
# ---------------------------------------------------------------------------


@router.post(
    "/{gr_id}/retry",
    response_model=GoodsReceiptRead,
    summary="Reintentar un Goods Receipt en estado error",
    operation_id="goodsReceiptsRetry",
    responses={
        404: {"model": ProblemDetails},
        422: {"model": ProblemDetails},
    },
)
async def retry_goods_receipt(
    gr_id: UUID,
    _user: Annotated[User, Depends(require_permissions("purchases:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> GoodsReceiptRead:
    repo = GoodsReceiptRepository(session)
    gr = await repo.retry(gr_id)
    await session.commit()

    # Re-encolar tarea
    from app.workers.tasks.inventory import recalc_map_on_gr

    recalc_map_on_gr.delay(str(gr.id))

    gr_loaded = await repo.get(gr.id)
    assert gr_loaded is not None  # noqa: S101
    return _to_read(gr_loaded)
