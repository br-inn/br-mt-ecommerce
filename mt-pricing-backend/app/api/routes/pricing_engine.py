"""Pricing Engine API S4 (US-1B-01-04).

Endpoints añadidos sobre la base de ``app.api.routes.pricing``:

- ``POST /pricing/prices/bulk-publish``        — publica `approved` → `exported` con audit + rollback opcional.
- ``POST /pricing/prices/recalc-batch``        — encola Celery tasks para una lista de SKUs.
- ``POST /pricing/prices/{price_id}/revise-counter`` — revise con counter-proposal.

NO modifica el router base ``app.api.routes.pricing.router`` — este router se
**registra aparte** en ``app/api/routes/__init__.py`` (parche reportado al
final). Comparte ``prefix='/pricing'`` y ``tags=['pricing']`` para no duplicar
secciones en OpenAPI.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.schemas.common import ProblemDetails
from app.schemas.pricing_engine import (
    BulkPublishRequest,
    BulkPublishResponse,
    CounterProposalRequest,
    CounterProposalResponse,
    RecalcBatchRequest,
    RecalcBatchResponse,
)
from app.services.pricing import PricingDomainError, PricingService
from app.services.pricing.bulk_publish_service import BulkPublishService
from app.services.pricing.revise_service import ReviseService

router = APIRouter(prefix="/pricing", tags=["pricing"])


# ---------------------------------------------------------------------------
# DI
# ---------------------------------------------------------------------------
def get_pricing_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PricingService:
    return PricingService(session)


def get_bulk_publish_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BulkPublishService:
    return BulkPublishService(session)


def get_revise_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReviseService:
    return ReviseService(session)


def _raise_domain(err: PricingDomainError) -> None:
    raise HTTPException(
        status_code=err.status_code,
        detail={"code": err.code, "title": err.message},
    )


# ---------------------------------------------------------------------------
# Bulk publish
# ---------------------------------------------------------------------------
@router.post(
    "/prices/bulk-publish",
    response_model=BulkPublishResponse,
    summary="Publica precios approved → exported con audit + rollback opcional",
    description=(
        "Transiciona un lote de precios `approved` → `exported` con "
        "auditoría individual y opción `rollback_on_error` para abortar "
        "ante el primer fallo de FSM."
    ),
    operation_id="pricingBulkPublish",
    responses={
        409: {"model": ProblemDetails},
        422: {"model": ProblemDetails},
    },
)
async def bulk_publish(
    data: BulkPublishRequest,
    user: Annotated[User, Depends(require_permissions("prices:export"))],
    service: Annotated[BulkPublishService, Depends(get_bulk_publish_service)],
) -> BulkPublishResponse:
    result = await service.publish(data.price_ids, user, rollback_on_error=data.rollback_on_error)
    payload = result.to_dict()
    return BulkPublishResponse.model_validate(payload)


# ---------------------------------------------------------------------------
# Recalc batch
# ---------------------------------------------------------------------------
@router.post(
    "/prices/recalc-batch",
    response_model=RecalcBatchResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Encola tasks Celery para recalcular un batch de SKUs",
    description=(
        "Encola un task Celery `mt.pricing.recalculate_sku` por SKU "
        "(fan-out manual). Devuelve task_ids para poll posterior."
    ),
    operation_id="pricingRecalcBatch",
)
async def recalc_batch(
    data: RecalcBatchRequest,
    user: Annotated[User, Depends(require_permissions("prices:propose"))],
) -> RecalcBatchResponse:
    # Import diferido para evitar ciclos / facilitar mocking en tests.
    try:
        from app.workers.tasks.pricing import recalculate_sku_task
    except Exception as exc:  # pragma: no cover  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail={
                "code": "celery_unavailable",
                "title": f"Worker pricing no disponible: {exc!s}",
            },
        ) from exc

    task_ids: list[str] = []
    for sku in data.skus:
        async_result = recalculate_sku_task.delay(sku, str(user.id))
        task_ids.append(getattr(async_result, "id", "") or "")
    return RecalcBatchResponse(
        skus_queued=len(data.skus),
        task_ids=task_ids,
        trigger=data.trigger,
    )


# ---------------------------------------------------------------------------
# Revise — counter-proposal
# ---------------------------------------------------------------------------
@router.post(
    "/prices/{price_id}/revise-counter",
    response_model=CounterProposalResponse,
    summary="Revise con counter-proposal explícito (audit price.counter_proposed)",
    description=(
        "Aplica una counter-proposal sobre un precio existente con razón "
        "obligatoria. Audit `price.counter_proposed`. Permission "
        "`prices:override_review` (Sprint 5 RBAC fino)."
    ),
    operation_id="pricingReviseCounter",
    responses={
        404: {"model": ProblemDetails},
        409: {"model": ProblemDetails},
        422: {"model": ProblemDetails},
    },
)
async def revise_with_counter(
    price_id: UUID,
    data: CounterProposalRequest,
    # `revise_with_counter` aplica una counter-proposal — distinto de un
    # propose nuevo. Requiere `prices:override_review` (Sprint 5 RBAC fino,
    # US-1A-07-04) para evitar que cualquier usuario con `prices:propose`
    # pueda saltarse el flujo de review/override.
    user: Annotated[User, Depends(require_permissions("prices:override_review"))],
    service: Annotated[ReviseService, Depends(get_revise_service)],
) -> CounterProposalResponse:
    try:
        result = await service.revise_with_counter(
            price_id=price_id,
            new_amount=data.new_amount,
            reason=data.reason,
            actor=user,
        )
    except PricingDomainError as exc:
        _raise_domain(exc)
        raise  # pragma: no cover  # _raise_domain raises always
    return CounterProposalResponse.model_validate(result.to_dict())


__all__ = [
    "get_bulk_publish_service",
    "get_pricing_service",
    "get_revise_service",
    "router",
]
