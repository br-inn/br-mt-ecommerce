"""Match candidates API — Sprint 3 foundation.

Endpoints expuestos:

- ``GET    /api/v1/matches``                       — listado paginado cursor-based.
- ``GET    /api/v1/matches/{id}``                  — detalle (con scoring breakdown).
- ``POST   /api/v1/matches/{sku}/refresh``         — gatilla scrape y persiste (adapter vía feature flags).
- ``POST   /api/v1/matches/{id}/validate``         — marca como validated.
- ``POST   /api/v1/matches/{id}/discard``          — marca como discarded.
- ``GET    /api/v1/comparator/dataset/export``     — exporta pares etiquetados JSONL.

Cursor opaco: base64url(json({"id": "<uuid>"})) — distinto del cursor sku
de Products porque la PK aquí es UUID.
"""

from __future__ import annotations

import base64
import binascii
import json
from datetime import date
from typing import Annotated, Any, AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, require_permissions
from app.db.models.match_candidate import MatchCandidate
from app.db.models.user import User
from app.schemas.common import Cursor, Pagination, ProblemDetails
from app.schemas.matches import (
    MatchBulkValidateRequest,
    MatchBulkValidateResponse,
    MatchCandidateDetail,
    MatchCandidateResponse,
    MatchDiscardRequest,
    MatchRefreshJobResponse,
    MatchRefreshResponse,
    MatchRefreshStatusResponse,
    ThreeWaySummaryResponse,
)
from app.repositories.match_agent import (
    MatchAgentConfigRepository,
    MatchAgentDecisionRepository,
)
from app.schemas.match_agent import (
    MatchAgentConfigResponse,
    MatchAgentConfigUpdate,
    MatchAgentMetrics,
)
from app.services.matching.adapter_registry import get_fetcher
from app.services.matching.match_service import (
    MatchDomainError,
    MatchService,
)

router = APIRouter(prefix="/matches", tags=["matches"])
dataset_router = APIRouter(prefix="/comparator", tags=["comparator"])


# ---------------------------------------------------------------------------
# Cursor helpers (UUID-based) — paralelo a `app.api.pagination` (sku-based).
# ---------------------------------------------------------------------------
def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(token: str) -> bytes:
    padding = "=" * (-len(token) % 4)
    return base64.urlsafe_b64decode(token + padding)


def _encode_id_cursor(uid: UUID | None) -> str | None:
    if uid is None:
        return None
    raw = json.dumps({"id": str(uid)}, separators=(",", ":")).encode("utf-8")
    return _b64url_encode(raw)


def _decode_id_cursor(cursor: str | None) -> UUID | None:
    if cursor is None:
        return None
    try:
        raw = _b64url_decode(cursor)
        payload = json.loads(raw)
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_cursor",
                "title": "Invalid cursor",
                "detail": "Cursor opaco corrupto.",
            },
        ) from exc
    if not isinstance(payload, dict) or "id" not in payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_cursor",
                "title": "Invalid cursor",
                "detail": "Cursor falta clave 'id'.",
            },
        )
    try:
        return UUID(str(payload["id"]))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_cursor",
                "title": "Invalid cursor",
                "detail": "Cursor 'id' no es UUID válido.",
            },
        ) from exc


# ---------------------------------------------------------------------------
# DI
# ---------------------------------------------------------------------------
def get_match_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MatchService:
    import logging as _logging

    fetchers = [get_fetcher("amazon_uae"), get_fetcher("noon_uae")]
    _logging.getLogger(__name__).info(
        "match_service.fetchers",
        extra={"fetchers": [type(f).__name__ for f in fetchers]},
    )
    return MatchService(session, fetchers=fetchers)


def _raise_domain(err: MatchDomainError) -> None:
    raise HTTPException(
        status_code=err.status_code,
        detail={"code": err.code, "title": err.message},
    )


def _to_response(row: Any) -> MatchCandidateResponse:
    return MatchCandidateResponse.model_validate(row)


def _to_detail(row: Any) -> MatchCandidateDetail:
    base = MatchCandidateResponse.model_validate(row).model_dump()
    specs = base.get("specs_jsonb") or {}
    scoring = specs.get("_scoring") if isinstance(specs, dict) else None
    base["scoring"] = scoring
    return MatchCandidateDetail.model_validate(base)


# ---------------------------------------------------------------------------
# Endpoints — agent config / metrics (MUST come before /{candidate_id} routes)
# ---------------------------------------------------------------------------
@router.get(
    "/agent/config",
    response_model=MatchAgentConfigResponse,
    summary="Configuración del agente de validación",
    operation_id="matchesAgentConfig",
)
async def get_agent_config(
    _user: User = Depends(require_permissions("matches:read")),
    session: AsyncSession = Depends(get_db_session),
) -> MatchAgentConfigResponse:
    cfg = await MatchAgentConfigRepository(session).get()
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "agent_config_missing", "title": "Falta la fila singleton de config."},
        )
    return MatchAgentConfigResponse.model_validate(cfg)


@router.put(
    "/agent/config",
    response_model=MatchAgentConfigResponse,
    summary="Actualizar la configuración del agente",
    operation_id="matchesAgentConfigUpdate",
)
async def update_agent_config(
    payload: MatchAgentConfigUpdate,
    user: User = Depends(require_permissions("matches:write")),
    session: AsyncSession = Depends(get_db_session),
) -> MatchAgentConfigResponse:
    from sqlalchemy import func as _func  # noqa: PLC0415

    repo = MatchAgentConfigRepository(session)
    cfg = await repo.get()
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "agent_config_missing", "title": "Config ausente"},
        )

    if payload.mode == "active":
        try:
            from app.db.models.golden_label import GoldenLabel  # noqa: PLC0415

            total = int(
                (await session.execute(select(_func.count(GoldenLabel.id)))).scalar_one() or 0
            )
        except Exception:  # noqa: BLE001
            total = 0
        gate = int(payload.min_labels_gate or cfg.min_labels_gate)
        if total < gate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "labels_gate_not_reached",
                    "title": f"Faltan golden_labels: {total}/{gate}.",
                },
            )

    updated = await repo.update(
        mode=payload.mode,
        alpha=payload.alpha,
        min_labels_gate=payload.min_labels_gate,
        updated_by=user.id,
    )
    await session.commit()
    return MatchAgentConfigResponse.model_validate(updated)


@router.get(
    "/agent/metrics",
    response_model=MatchAgentMetrics,
    summary="Métricas del agente (labels, precisión sombra, salud del calibrador)",
    operation_id="matchesAgentMetrics",
)
async def get_agent_metrics(
    _user: User = Depends(require_permissions("matches:read")),
    session: AsyncSession = Depends(get_db_session),
) -> MatchAgentMetrics:
    from sqlalchemy import func as _func  # noqa: PLC0415

    cfg = await MatchAgentConfigRepository(session).get()
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "agent_config_missing", "title": "Config ausente"},
        )

    total = 0
    try:
        from app.db.models.golden_label import GoldenLabel  # noqa: PLC0415

        total = int((await session.execute(select(_func.count(GoldenLabel.id)))).scalar_one() or 0)
    except Exception:  # noqa: BLE001
        pass

    decision_repo = MatchAgentDecisionRepository(session)
    shadow_count = await decision_repo.count_shadow()
    _, precision = await decision_repo.shadow_precision()

    active_cal = None
    try:
        from app.repositories.golden_labels import CalibratorVersionRepository  # noqa: PLC0415

        active_cal = await CalibratorVersionRepository(session).get_active()
    except Exception:  # noqa: BLE001
        pass

    return MatchAgentMetrics(
        golden_labels_total=total,
        min_labels_gate=cfg.min_labels_gate,
        gate_reached=total >= cfg.min_labels_gate,
        shadow_decisions=shadow_count,
        shadow_precision=precision,
        calibrator_version=active_cal.version if active_cal else None,
        calibrator_brier=(
            float(active_cal.brier_score)
            if active_cal and getattr(active_cal, "brier_score", None) is not None
            else None
        ),
        calibrator_ece=(
            float(active_cal.ece)
            if active_cal and getattr(active_cal, "ece", None) is not None
            else None
        ),
        calibrator_trained_on=(
            getattr(active_cal, "trained_on_count", None) if active_cal else None
        ),
        mode=cfg.mode,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Endpoints — candidates listing / detail
# ---------------------------------------------------------------------------
@router.get(
    "",
    response_model=Pagination[MatchCandidateResponse],
    summary="Listar candidatos de matching con filtros",
    description=(
        "Lista paginada (cursor UUID-based) de match candidates con filtros "
        "opcionales por SKU, status (pending/validated/discarded) y canal "
        "(amazon_uae/noon_uae)."
    ),
    operation_id="matchesList",
)
async def list_matches(
    sku: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
    candidate_status: Annotated[
        str | None,
        Query(alias="status", pattern=r"^(pending|validated|discarded)$"),
    ] = None,
    channel: Annotated[str | None, Query(pattern=r"^(amazon_uae|noon_uae)$")] = None,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    _user: User = Depends(require_permissions("matches:read")),
    service: MatchService = Depends(get_match_service),
) -> Pagination[MatchCandidateResponse]:
    cursor_uuid = _decode_id_cursor(cursor)
    rows, next_id = await service.list_candidates(
        sku=sku,
        status=candidate_status,
        channel=channel,
        cursor=cursor_uuid,
        limit=limit,
    )
    return Pagination[MatchCandidateResponse](
        items=[_to_response(r) for r in rows],
        cursor=Cursor(next=_encode_id_cursor(next_id)),
        page_size=limit,
    )


@router.get(
    "/{candidate_id}",
    response_model=MatchCandidateDetail,
    summary="Detalle de un match candidate (incluye scoring breakdown)",
    description=(
        "Devuelve un match candidate por ID con su scoring breakdown "
        "(specs jsonb._scoring) para inspección desde la UI."
    ),
    operation_id="matchesGet",
    responses={404: {"model": ProblemDetails}},
)
async def get_match(
    candidate_id: UUID,
    _user: User = Depends(require_permissions("matches:read")),
    service: MatchService = Depends(get_match_service),
) -> MatchCandidateDetail:
    try:
        row = await service.get_candidate(candidate_id)
    except MatchDomainError as e:
        _raise_domain(e)
    return _to_detail(row)


@router.post(
    "/{sku}/refresh",
    response_model=MatchRefreshJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Encolar refresh de candidatos del SKU (async — background scraping)",
    description=(
        "Encola un job Celery que corre el pipeline de matching completo para el SKU. "
        "Devuelve 202 inmediatamente con el estado actual de la DB y un task_id para polling. "
        "Usar GET /matches/{sku}/refresh/status/{task_id} para saber cuando terminó."
    ),
    operation_id="matchesRefresh",
    responses={404: {"model": ProblemDetails}},
)
async def refresh_matches(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    _user: User = Depends(require_permissions("matches:write")),
    service: MatchService = Depends(get_match_service),
    session: AsyncSession = Depends(get_db_session),
) -> MatchRefreshJobResponse:
    from app.workers.tasks.comparator import refresh_sku_task  # noqa: PLC0415

    # Verify SKU exists before enqueuing.
    from app.repositories.product import ProductRepository  # noqa: PLC0415

    product = await ProductRepository(session).get_by_sku(sku)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "sku_not_found", "title": f"SKU {sku!r} no existe."},
        )

    # Current DB state (stale) — returned immediately so UI has something to show.
    rows, _ = await service.list_candidates(sku=sku, limit=50)
    current_candidates = [_to_response(r) for r in rows]

    # Enqueue background task.
    task = refresh_sku_task.apply_async(args=[sku])

    return MatchRefreshJobResponse(
        sku=sku,
        task_id=task.id,
        task_status="queued",
        refreshed_count=len(current_candidates),
        candidates=current_candidates,
    )


@router.get(
    "/{sku}/refresh/status/{task_id}",
    response_model=MatchRefreshStatusResponse,
    summary="Estado del job de refresh (polling)",
    description=(
        "Devuelve el estado de un job de refresh encolado con POST /matches/{sku}/refresh. "
        "Hacer polling cada 3-5s hasta que task_status sea 'done' o 'failed'."
    ),
    operation_id="matchesRefreshStatus",
)
async def refresh_status(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    task_id: Annotated[str, Path(min_length=1)],
    _user: User = Depends(require_permissions("matches:read")),
    service: MatchService = Depends(get_match_service),
) -> MatchRefreshStatusResponse:
    from celery.result import AsyncResult  # noqa: PLC0415

    result = AsyncResult(task_id)
    celery_state = result.state  # PENDING | STARTED | SUCCESS | FAILURE | RETRY

    if celery_state in ("SUCCESS",):
        task_result = result.result or {}
        rows, _ = await service.list_candidates(sku=sku, limit=50)
        return MatchRefreshStatusResponse(
            sku=sku,
            task_id=task_id,
            task_status="done",
            refreshed_count=task_result.get("refreshed_count", len(rows)),
            candidates=[_to_response(r) for r in rows],
        )

    if celery_state in ("FAILURE",):
        return MatchRefreshStatusResponse(
            sku=sku,
            task_id=task_id,
            task_status="failed",
            error=str(result.result) if result.result else "Error desconocido",
        )

    task_status = "running" if celery_state == "STARTED" else "queued"
    return MatchRefreshStatusResponse(
        sku=sku,
        task_id=task_id,
        task_status=task_status,
    )


@router.post(
    "/{candidate_id}/validate",
    response_model=MatchCandidateResponse,
    summary="Marcar candidate como `validated`",
    description=(
        "Transiciona un match candidate a estado `validated` (asociación "
        "humana confirmada). 409 si la transición FSM es ilegal."
    ),
    operation_id="matchesValidate",
    responses={
        404: {"model": ProblemDetails},
        409: {"model": ProblemDetails, "description": "Transición ilegal"},
    },
)
async def validate_match(
    candidate_id: UUID,
    user: Annotated[User, Depends(require_permissions("matches:write"))],
    service: Annotated[MatchService, Depends(get_match_service)],
) -> MatchCandidateResponse:
    try:
        row = await service.validate_candidate(candidate_id, user_id=user.id)
    except MatchDomainError as e:
        _raise_domain(e)
    return _to_response(row)


@router.post(
    "/bulk-validate",
    response_model=MatchBulkValidateResponse,
    summary="Validar varios candidatos en una sola petición",
    description=(
        "Valida en bloque hasta 200 candidatos. Reemplaza N llamadas a "
        "POST /matches/{id}/validate por una sola. Los candidatos cuya "
        "transición FSM sea ilegal (o que no existan) se omiten y se listan "
        "en `skipped`; el resto se valida igualmente."
    ),
    operation_id="matchesBulkValidate",
)
async def bulk_validate_matches(
    payload: MatchBulkValidateRequest,
    user: Annotated[User, Depends(require_permissions("matches:write"))],
    service: Annotated[MatchService, Depends(get_match_service)],
) -> MatchBulkValidateResponse:
    validated = 0
    skipped: list[UUID] = []
    for candidate_id in payload.ids:
        try:
            await service.validate_candidate(candidate_id, user_id=user.id)
            validated += 1
        except MatchDomainError:
            skipped.append(candidate_id)
    return MatchBulkValidateResponse(validated=validated, skipped=skipped)


@router.get(
    "/{sku}/three-way-summary",
    response_model=ThreeWaySummaryResponse,
    summary="Three-way summary de pricing para un SKU",
    description=(
        "Cruza los tres legs de pricing:\n"
        "- **Leg 1**: producto MT (SKU debe existir en el catálogo).\n"
        "- **Leg 2**: mejor candidato validado del scraper (price_aed del MatchCandidate "
        "con status='validated' y score más alto).\n"
        "- **Leg 3**: último costo de compra real (CostLot.unit_cost_aed con qty_remaining > 0).\n\n"
        "El campo `is_three_way_complete` indica si los tres legs tienen datos. "
        "`missing_legs` detalla qué falta ('market_candidate', 'purchase_cost')."
    ),
    operation_id="matchesThreeWaySummary",
    responses={404: {"model": ProblemDetails}},
)
async def get_three_way_summary(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    _user: User = Depends(require_permissions("matches:read")),
    service: MatchService = Depends(get_match_service),
) -> ThreeWaySummaryResponse:
    try:
        data = await service.get_three_way_summary(sku)
    except MatchDomainError as e:
        _raise_domain(e)
    return ThreeWaySummaryResponse.model_validate(data)


@router.post(
    "/{candidate_id}/discard",
    response_model=MatchCandidateResponse,
    summary="Marcar candidate como `discarded`",
    description=(
        "Transiciona un match candidate a estado `discarded` con razón "
        "opcional. 409 si la transición FSM es ilegal."
    ),
    operation_id="matchesDiscard",
    responses={
        404: {"model": ProblemDetails},
        409: {"model": ProblemDetails, "description": "Transición ilegal"},
    },
)
async def discard_match(
    candidate_id: UUID,
    user: Annotated[User, Depends(require_permissions("matches:write"))],
    service: Annotated[MatchService, Depends(get_match_service)],
    payload: MatchDiscardRequest | None = None,
) -> MatchCandidateResponse:
    reason = payload.reason if payload else None
    try:
        row = await service.discard_candidate(candidate_id, reason=reason)
    except MatchDomainError as e:
        _raise_domain(e)
    return _to_response(row)


@router.post(
    "/{candidate_id}/revert",
    response_model=MatchCandidateResponse,
    summary="Revertir una decisión del agente (vuelve a pending)",
    operation_id="matchesRevert",
)
async def revert_agent_decision(
    candidate_id: UUID,
    _user: User = Depends(require_permissions("matches:write")),
    session: AsyncSession = Depends(get_db_session),
    service: MatchService = Depends(get_match_service),
) -> MatchCandidateResponse:
    try:
        row = await service.get_candidate(candidate_id)
    except MatchDomainError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "title": e.message},
        ) from e
    agent_block = (row.specs_jsonb or {}).get("_agent")
    if not isinstance(agent_block, dict) or not agent_block.get("applied"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "not_agent_decision",
                "title": "El candidato no fue resuelto por el agente.",
            },
        )
    specs = dict(row.specs_jsonb or {})
    specs.pop("_agent", None)
    row.specs_jsonb = specs
    row.status = "pending"
    row.label = None
    if hasattr(row, "validated_by"):
        row.validated_by = None
    if hasattr(row, "validated_at"):
        row.validated_at = None
    if hasattr(row, "discarded_reason"):
        row.discarded_reason = None
    await session.commit()
    await session.refresh(row)
    return _to_response(row)


@router.delete(
    "",
    summary="Limpiar todos los candidatos (solo ENV=development)",
    operation_id="matchesClearAll",
    responses={403: {"model": ProblemDetails}},
)
async def clear_all_matches(
    _user: User = Depends(require_permissions("matches:write")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, int]:
    from app.core.config import settings  # noqa: PLC0415

    if not settings.is_dev:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "title": "Solo disponible en ENV=development"},
        )
    result = await session.execute(sa_delete(MatchCandidate))
    await session.commit()
    return {"deleted": result.rowcount}


@router.delete(
    "/cache/model-enriched",
    summary="Invalida caché LLM para SKUs con model_id asignado",
    status_code=200,
)
async def invalidate_model_enriched_cache(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Borra product_search_queries para SKUs con products.model_id != NULL.

    Fuerza regeneración de queries LLM con contexto del modelo en el próximo refresh.
    """
    from app.db.models.search_query import ProductSearchQuery  # noqa: PLC0415
    from app.db.models.product import Product  # noqa: PLC0415

    skus_with_model = select(Product.sku).where(Product.model_id.is_not(None)).scalar_subquery()
    stmt = sa_delete(ProductSearchQuery).where(ProductSearchQuery.sku.in_(skus_with_model))
    result = await session.execute(stmt)
    await session.commit()
    return {"deleted_count": result.rowcount}


# ---------------------------------------------------------------------------
# Dataset export — US-F15-03-01
# ---------------------------------------------------------------------------
_LABEL_MAP: dict[str, int] = {"accept": 1, "reject": 0}


async def _stream_labeled_pairs(
    session: AsyncSession,
) -> AsyncIterator[str]:
    """Yields JSONL lines for validated labeled candidates."""
    stmt = select(MatchCandidate).where(
        MatchCandidate.label.in_(["accept", "reject"]),
        MatchCandidate.status == "validated",
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    for row in rows:
        payload = {
            "sku_mt": row.product_sku,
            "candidate_id": str(row.id),
            "title": row.title,
            "specs_jsonb": row.specs_jsonb,
            "label": _LABEL_MAP[row.label],  # type: ignore[index]
        }
        yield json.dumps(payload, ensure_ascii=False) + "\n"


@dataset_router.get(
    "/dataset/export",
    summary="Exportar pares etiquetados como JSONL (US-F15-03-01)",
    description=(
        "Devuelve un stream NDJSON con los match candidates que tienen "
        "``label IN ('accept','reject')`` y ``status='validated'``. "
        "Si el total disponible es menor que ``min_pairs`` responde HTTP 422."
    ),
    operation_id="comparatorDatasetExport",
    responses={
        200: {
            "content": {"application/x-ndjson": {}},
            "description": "Stream JSONL de pares etiquetados.",
        },
        422: {"description": "Pares insuficientes."},
    },
)
async def export_dataset(
    format: Annotated[str, Query(pattern=r"^jsonl$")] = "jsonl",
    min_pairs: Annotated[int, Query(ge=1)] = 1000,
    _user: User = Depends(require_permissions("matches:read")),
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    # Count available labeled+validated pairs first
    from sqlalchemy import func

    count_stmt = select(func.count()).where(
        MatchCandidate.label.in_(["accept", "reject"]),
        MatchCandidate.status == "validated",
    )
    count_result = await session.execute(count_stmt)
    available = count_result.scalar_one()

    if available < min_pairs:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "insufficient_pairs",
                "available": available,
                "required": min_pairs,
            },
        )

    filename = f"labeled_pairs_{date.today().isoformat()}.jsonl"

    async def _generate() -> AsyncIterator[str]:
        async for line in _stream_labeled_pairs(session):
            yield line

    return StreamingResponse(
        _generate(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
