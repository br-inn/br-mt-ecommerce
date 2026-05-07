"""Channel Mirror API — Sprint 3.

Endpoints expuestos al frontend:

- ``GET    /channels/{channel_code}/listings``           — paginado de listings.
- ``GET    /channels/{channel_code}/{sku}/diff``         — diff field-by-field.
- ``POST   /channels/{channel_code}/{sku}/sync``         — pull on-demand + diff.
- ``POST   /channels/{channel_code}/{sku}/publish``      — push diff (stub).
- ``GET    /channels/{channel_code}/sync-log``           — últimas N entradas.

Convención cursor pagination: ``base64url(json({"sku": "<last_sku>"}))``
(igual que productos — ver ``app/api/pagination.py``).

RBAC: usa permisos existentes ``channels:read`` (listings/diff/sync-log) y
``channels:manage`` (sync/publish). Ya están seedeados por la migración
20260507_010_pricing_models.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.api.pagination import decode_sku_cursor, encode_sku_cursor
from app.db.models.product import Product, ProductTranslation
from app.db.models.user import User
from app.repositories.channel_listings import (
    ChannelListingRepository,
    ChannelSyncEventRepository,
)
from app.schemas.channel_mirror import (
    ChannelCodeStr,
    ChannelListingResponse,
    DiffResponse,
    DiffSummary,
    FieldDiffResponse,
    PublishRequest,
    PublishResponseModel,
    SyncLogEntry,
)
from app.schemas.common import Cursor, Pagination, ProblemDetails
from app.services.channel_mirror import MirrorService
from app.services.channel_mirror.adapters import AmazonSPApiStub, NoonApiStub
from app.services.channel_mirror.mirror_service import (
    CanonicalNotFoundError,
    UnknownChannelError,
)
from app.services.channel_mirror.ports import ChannelMirrorPort


router = APIRouter(prefix="/channels", tags=["Channel Mirror"])


# ---------------------------------------------------------------------------
# DI factories
# ---------------------------------------------------------------------------
def get_channel_adapters() -> dict[str, ChannelMirrorPort]:
    """Mapping ``channel_code → adapter`` instanciado por request.

    Sprint 3: stubs canned. Sprint 4+: se sustituyen por adapters HTTP
    inyectando creds via ``settings``.
    """
    return {
        "amazon_uae": AmazonSPApiStub(),
        "noon_uae": NoonApiStub(),
    }


async def _canonical_loader_factory(
    session: AsyncSession,
) -> Any:
    """Devuelve un callable async ``(sku) -> dict`` que arma el canonical
    a partir de ``products`` + ``product_translations``.

    El shape resultante mapea 1:1 los fields que el frontend espera ver en
    el comparador (title_en, title_ar, bullet_1, etc.). Los campos
    desconocidos quedan como ``None`` (el diff los pintará como missing
    si el canal sí los expone).
    """

    async def _load(sku: str) -> dict[str, Any]:
        # 1. Producto base.
        product = await session.get(Product, sku)
        if product is None:
            return {}

        # 2. Translations.
        stmt = select(ProductTranslation).where(ProductTranslation.product_sku == sku)
        result = await session.execute(stmt)
        translations = {t.lang: t for t in result.scalars().all()}

        title_en = product.name_en
        title_ar = translations.get("ar").name if translations.get("ar") else None

        canonical: dict[str, Any] = {
            "title_en": title_en,
            "title_ar": title_ar,
            "brand": product.brand,
            "material": product.material,
            "DN": product.dn,
            "PN": product.pn,
            # specs / dimensions / packaging viven en JSONB; exponemos los
            # subcampos típicos que el frontend muestra.
            "HS_code": (product.specs or {}).get("HS_code"),
            "weight": (product.dimensions or {}).get("weight"),
        }
        return canonical

    return _load


def get_mirror_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    adapters: Annotated[dict[str, ChannelMirrorPort], Depends(get_channel_adapters)],
) -> MirrorService:
    listings_repo = ChannelListingRepository(session)
    events_repo = ChannelSyncEventRepository(session)

    async def _loader(sku: str) -> dict[str, Any]:
        loader = await _canonical_loader_factory(session)
        return await loader(sku)

    return MirrorService(
        listings_repo=listings_repo,
        events_repo=events_repo,
        adapters=adapters,
        canonical_loader=_loader,
    )


# ---------------------------------------------------------------------------
# Error helper
# ---------------------------------------------------------------------------
def _raise_404(detail: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "type": "https://mtme-api/errors/listing-not-found",
            "title": "Listing not found",
            "status": 404,
            "code": "listing_not_found",
            "detail": detail,
        },
    )


def _raise_400(detail: str, *, code: str = "invalid_channel") -> None:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "type": f"https://mtme-api/errors/{code}",
            "title": "Bad request",
            "status": 400,
            "code": code,
            "detail": detail,
        },
    )


# ---------------------------------------------------------------------------
# GET /channels/{channel_code}/listings
# ---------------------------------------------------------------------------
@router.get(
    "/{channel_code}/listings",
    response_model=Pagination[ChannelListingResponse],
    summary="Listar listings sincronizados de un canal (paginado por SKU)",
)
async def list_channel_listings(
    channel_code: Annotated[ChannelCodeStr, Path()],
    diff_status: Annotated[
        str | None,
        Query(
            alias="status",
            pattern=r"^(match|drift|missing|queued|clean)$",
            description="Filtra por status agregado del diff_summary.",
        ),
    ] = None,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    _user: User = Depends(require_permissions("channels:read")),
    session: AsyncSession = Depends(get_db_session),
) -> Pagination[ChannelListingResponse]:
    repo = ChannelListingRepository(session)
    sku_cursor = decode_sku_cursor(cursor)
    rows, next_sku = await repo.list_by_channel(
        channel_code,
        cursor=sku_cursor,
        limit=limit,
        diff_status=diff_status,
    )
    return Pagination[ChannelListingResponse](
        items=[ChannelListingResponse.model_validate(r) for r in rows],
        cursor=Cursor(next=encode_sku_cursor(next_sku)),
        page_size=limit,
    )


# ---------------------------------------------------------------------------
# GET /channels/{channel_code}/{sku}/diff
# ---------------------------------------------------------------------------
@router.get(
    "/{channel_code}/{sku}/diff",
    response_model=DiffResponse,
    summary="Diff field-by-field MT canonical vs canal externo",
    responses={404: {"model": ProblemDetails}},
)
async def get_channel_diff(
    channel_code: Annotated[ChannelCodeStr, Path()],
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    _user: User = Depends(require_permissions("channels:read")),
    service: MirrorService = Depends(get_mirror_service),
    session: AsyncSession = Depends(get_db_session),
) -> DiffResponse:
    try:
        diffs, summary = await service.compute_diff(channel_code, sku)
    except CanonicalNotFoundError as e:
        _raise_404(str(e))
    except UnknownChannelError as e:
        _raise_400(str(e))

    listing = await ChannelListingRepository(session).get_by_channel_sku(
        channel_code, sku
    )
    return DiffResponse(
        channel_code=channel_code,
        sku=sku,
        external_id=listing.external_id if listing else "",
        diffs=[FieldDiffResponse(**d.to_dict()) for d in diffs],
        summary=DiffSummary(**summary),
        fetched_at=listing.last_sync_at if listing else None,
    )


# ---------------------------------------------------------------------------
# POST /channels/{channel_code}/{sku}/sync
# ---------------------------------------------------------------------------
@router.post(
    "/{channel_code}/{sku}/sync",
    response_model=DiffResponse,
    summary="Pull on-demand del canal + recalcular diff (stub Sprint 3)",
    responses={404: {"model": ProblemDetails}, 400: {"model": ProblemDetails}},
)
async def sync_channel_listing(
    channel_code: Annotated[ChannelCodeStr, Path()],
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    external_id: Annotated[str | None, Query(max_length=64)] = None,
    _user: User = Depends(require_permissions("channels:manage")),
    service: MirrorService = Depends(get_mirror_service),
) -> DiffResponse:
    try:
        outcome = await service.sync(
            channel_code, sku, external_id=external_id
        )
    except CanonicalNotFoundError as e:
        _raise_404(str(e))
    except UnknownChannelError as e:
        _raise_400(str(e))

    return DiffResponse(
        channel_code=outcome.channel_code,
        sku=outcome.sku,
        external_id=outcome.external_id,
        diffs=[FieldDiffResponse(**d.to_dict()) for d in outcome.diffs],
        summary=DiffSummary(**outcome.summary),
    )


# ---------------------------------------------------------------------------
# POST /channels/{channel_code}/{sku}/publish
# ---------------------------------------------------------------------------
@router.post(
    "/{channel_code}/{sku}/publish",
    response_model=PublishResponseModel,
    summary="Empujar diferencias al canal (stub Sprint 3 — solo persiste intento)",
    responses={404: {"model": ProblemDetails}, 400: {"model": ProblemDetails}},
)
async def publish_channel_diff(
    channel_code: Annotated[ChannelCodeStr, Path()],
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    payload: PublishRequest | None = None,
    _user: User = Depends(require_permissions("channels:manage")),
    service: MirrorService = Depends(get_mirror_service),
) -> PublishResponseModel:
    fields = payload.fields if payload else None
    try:
        result = await service.publish(channel_code, sku, fields=fields)
    except CanonicalNotFoundError as e:
        _raise_404(str(e))
    except UnknownChannelError as e:
        _raise_400(str(e))

    return PublishResponseModel(
        ok=result.ok,
        submission_id=result.submission_id,
        accepted_fields=result.accepted_fields,
        rejected_fields=result.rejected_fields,
        message=result.message,
    )


# ---------------------------------------------------------------------------
# GET /channels/{channel_code}/sync-log
# ---------------------------------------------------------------------------
@router.get(
    "/{channel_code}/sync-log",
    response_model=list[SyncLogEntry],
    summary="Últimas N entradas del log de sync (pull/push/diff)",
)
async def get_channel_sync_log(
    channel_code: Annotated[ChannelCodeStr, Path()],
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
    _user: User = Depends(require_permissions("channels:read")),
    session: AsyncSession = Depends(get_db_session),
) -> list[SyncLogEntry]:
    repo = ChannelSyncEventRepository(session)
    rows = await repo.recent(channel_code, limit=limit)
    return [SyncLogEntry.model_validate(r) for r in rows]


__all__ = ["router"]
