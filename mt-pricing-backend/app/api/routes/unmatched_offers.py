"""Unmatched Offers API — ofertas sin match del pipeline de matching.

Endpoints:

- ``GET /api/v1/unmatched-offers``        — listado paginado cursor-based.
- ``GET /api/v1/unmatched-offers/stats``  — contadores por estado.

Cursor opaco: base64url(json({"id": "<uuid>"})) — mismo patrón que matches.py.
"""

from __future__ import annotations

import base64
import binascii
import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.repositories.unmatched_offers import UnmatchedOfferRepository
from app.schemas.common import Cursor, Pagination
from app.schemas.unmatched_offers import (
    UnmatchedOfferResponse,
    UnmatchedOffersStats,
)

router = APIRouter(prefix="/unmatched-offers", tags=["comparator"])


# ---------------------------------------------------------------------------
# Cursor helpers — same pattern as matches.py
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


def _get_repo(session: AsyncSession = Depends(get_db_session)) -> UnmatchedOfferRepository:
    return UnmatchedOfferRepository(session)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/stats",
    response_model=UnmatchedOffersStats,
    summary="Estadísticas del pool de unmatched offers",
    description=(
        "Devuelve contadores de ofertas por estado (pending/matched/exhausted) "
        "y métricas temporales (últimas 24h / últimos 7 días)."
    ),
    operation_id="unmatchedOffersStats",
)
async def get_unmatched_offers_stats(
    _user: User = Depends(require_permissions("matches:read")),
    repo: UnmatchedOfferRepository = Depends(_get_repo),
) -> UnmatchedOffersStats:
    stats = await repo.get_stats()
    return UnmatchedOffersStats(**stats)


@router.get(
    "",
    response_model=Pagination[UnmatchedOfferResponse],
    summary="Listar unmatched offers con filtros",
    description=(
        "Lista paginada (cursor UUID-based) de ofertas sin match con filtros "
        "opcionales por marketplace, status (pending/matched/exhausted), "
        "source_sku y búsqueda de texto en título."
    ),
    operation_id="unmatchedOffersList",
)
async def list_unmatched_offers(
    marketplace: Annotated[
        str | None,
        Query(pattern=r"^(amazon_uae|noon_uae)$"),
    ] = None,
    offer_status: Annotated[
        str | None,
        Query(alias="status", pattern=r"^(pending|matched|exhausted)$"),
    ] = None,
    source_sku: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
    q: Annotated[str | None, Query(min_length=1, max_length=256)] = None,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    _user: User = Depends(require_permissions("matches:read")),
    repo: UnmatchedOfferRepository = Depends(_get_repo),
) -> Pagination[UnmatchedOfferResponse]:
    cursor_uuid = _decode_id_cursor(cursor)
    rows, next_id = await repo.list_with_filters(
        marketplace=marketplace,
        status=offer_status,
        source_sku=source_sku,
        q=q,
        cursor=cursor_uuid,
        limit=limit,
    )

    items = [_build_response(offer) for offer in rows]

    return Pagination[UnmatchedOfferResponse](
        items=items,
        cursor=Cursor(next=_encode_id_cursor(next_id)),
        page_size=limit,
    )


def _build_response(offer: object) -> UnmatchedOfferResponse:
    """Build UnmatchedOfferResponse with correct has_embedding value."""
    # Validate from ORM object
    data = UnmatchedOfferResponse.model_validate(offer)
    # has_embedding is a @computed_field — we can't set it directly.
    # Reconstruct via subclass that overrides it.
    embedding_present = getattr(offer, "embedding", None) is not None

    class _WithEmbedding(UnmatchedOfferResponse):
        @property  # type: ignore[override]
        def has_embedding(self) -> bool:  # type: ignore[override]
            return embedding_present

    result = _WithEmbedding.model_validate(offer)
    return result
