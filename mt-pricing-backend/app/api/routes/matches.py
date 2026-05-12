"""Match candidates API — Sprint 3 foundation.

Endpoints expuestos:

- ``GET    /api/v1/matches``                       — listado paginado cursor-based.
- ``GET    /api/v1/matches/{id}``                  — detalle (con scoring breakdown).
- ``POST   /api/v1/matches/{sku}/refresh``         — gatilla scrape (stubs) y persiste.
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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, require_permissions
from app.db.models.match_candidate import MatchCandidate
from app.db.models.user import User
from app.schemas.common import Cursor, Pagination, ProblemDetails
from app.schemas.matches import (
    MatchCandidateDetail,
    MatchCandidateResponse,
    MatchDiscardRequest,
    MatchRefreshResponse,
)
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
    return MatchService(session)


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
# Endpoints
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
    channel: Annotated[
        str | None, Query(pattern=r"^(amazon_uae|noon_uae)$")
    ] = None,
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
    response_model=MatchRefreshResponse,
    summary="Refrescar candidatos del SKU (stubs Sprint 3) — persiste en match_candidates",
    description=(
        "Re-corre el pipeline de matching para el SKU (stub Sprint 3) y "
        "persiste los candidates en `match_candidates`. Devuelve el set "
        "completo refrescado."
    ),
    operation_id="matchesRefresh",
    responses={404: {"model": ProblemDetails}},
)
async def refresh_matches(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    _user: User = Depends(require_permissions("matches:write")),
    service: MatchService = Depends(get_match_service),
) -> MatchRefreshResponse:
    try:
        rows = await service.refresh_candidates(sku)
    except MatchDomainError as e:
        _raise_domain(e)
    return MatchRefreshResponse(
        sku=sku,
        refreshed_count=len(rows),
        candidates=[_to_response(r) for r in rows],
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
