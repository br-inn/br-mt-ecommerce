"""Admin feature flags routes — US-1A-09-08 (Sprint 5).

Endpoints:
- ``GET    /admin/flags``                — list all flags + audit columns.
- ``PATCH  /admin/flags/{key}``          — set enabled (perm ``flags:manage``).
- ``POST   /admin/flags/kill-switch``    — engage/disengage atomic
  (perm ``kill-switch:execute``; admin tiene este perm).

RBAC seed (migración 027):
- ``flags:manage``        → ``ti_integracion``, ``admin``.
- ``kill-switch:execute`` → ``ti_integracion``, ``admin``.

Diseño:
- Router montable independiente — patch en `app/api/routes/__init__.py`
  documentado en el reporte (no se modifica directamente).
- DI: ``get_flag_service`` builds :class:`FlagService` con repo + redis;
  tests overridean para fakes in-memory.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.repositories.feature_flags import FeatureFlagRepository  # noqa: F401 — used by get_flag_service
from app.schemas.feature_flags import (
    FeatureFlagItem,
    FeatureFlagListResponse,
    FeatureFlagUpdateRequest,
    KillSwitchRequest,
    KillSwitchResponse,
)
from app.services.feature_flags.flag_service import (
    KNOWN_FLAGS,
    FlagService,
)
from app.services.feature_flags.kill_switch import KillSwitch

router = APIRouter(prefix="/admin/flags", tags=["Feature Flags Admin"])


# ---------------------------------------------------------------------------
# DI
# ---------------------------------------------------------------------------
def get_flag_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FlagService:
    """Build :class:`FlagService` con repo DB + Redis singleton.

    Tests overridean esta dependency para inyectar un fake in-memory.
    """
    from app.core.redis import get_redis

    repo = FeatureFlagRepository(session)
    return FlagService(flag_repo=repo, redis=get_redis())


def get_kill_switch(
    flag_service: Annotated[FlagService, Depends(get_flag_service)],
) -> KillSwitch:
    return KillSwitch(flag_service)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get(
    "",
    response_model=FeatureFlagListResponse,
    summary="List feature flags + audit (admin only — flags:manage)",
)
async def list_flags(
    flag_service: Annotated[FlagService, Depends(get_flag_service)],
    _user: User = Depends(require_permissions("flags:manage")),
) -> FeatureFlagListResponse:
    repo = flag_service.flag_repo
    rows = await repo.list_all()  # type: ignore[attr-defined]
    items: list[FeatureFlagItem] = []
    seen: set[str] = set()
    for row in rows:
        items.append(
            FeatureFlagItem(
                key=row.key,
                enabled=bool(row.value_jsonb.get("enabled", False)),
                updated_by=row.updated_by,
                updated_at=row.updated_at,
                created_at=row.created_at,
            )
        )
        seen.add(row.key)

    # Asegurar que todos los KNOWN_FLAGS aparezcan (incluso si nunca se
    # tocaron post-seed — defensa ante backfills incompletos).
    for k in KNOWN_FLAGS:
        if k not in seen:
            items.append(FeatureFlagItem(key=k, enabled=False))

    return FeatureFlagListResponse(flags=items)


@router.patch(
    "/{key}",
    response_model=FeatureFlagItem,
    summary="Toggle feature flag (admin only — flags:manage)",
)
async def update_flag(
    key: str,
    payload: FeatureFlagUpdateRequest,
    flag_service: Annotated[FlagService, Depends(get_flag_service)],
    user: User = Depends(require_permissions("flags:manage")),
) -> FeatureFlagItem:
    if key not in KNOWN_FLAGS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "https://mtme.ae/errors/flag-unknown",
                "title": "Flag desconocido",
                "status": 404,
                "detail": f"key={key!r} no está en KNOWN_FLAGS",
                "known_flags": sorted(KNOWN_FLAGS),
            },
        )
    await flag_service.set_flag(
        key, payload.enabled, updated_by=user.id
    )
    # Reload para devolver audit columns.
    repo = flag_service.flag_repo
    row = await repo.get(key)  # type: ignore[attr-defined]
    if row is None:
        # No debería pasar tras un set_flag exitoso, pero defendemos.
        return FeatureFlagItem(key=key, enabled=payload.enabled)
    return FeatureFlagItem(
        key=row.key,
        enabled=bool(row.value_jsonb.get("enabled", False)),
        updated_by=row.updated_by,
        updated_at=row.updated_at,
        created_at=row.created_at,
    )


@router.post(
    "/kill-switch",
    response_model=KillSwitchResponse,
    status_code=status.HTTP_200_OK,
    summary="Engage/disengage global kill-switch (perm kill-switch:execute)",
)
async def toggle_kill_switch(
    payload: KillSwitchRequest,
    kill_switch: Annotated[KillSwitch, Depends(get_kill_switch)],
    user: User = Depends(require_permissions("kill-switch:execute")),
) -> KillSwitchResponse:
    if payload.engaged:
        await kill_switch.engage(updated_by=user.id, reason=payload.reason)
    else:
        await kill_switch.disengage(updated_by=user.id, reason=payload.reason)

    # Recargar audit columns.
    from app.services.feature_flags.flag_service import FLAG_KILL_SWITCH

    row = await kill_switch.flag_service.flag_repo.get(FLAG_KILL_SWITCH)  # type: ignore[attr-defined]
    if row is None:
        return KillSwitchResponse(engaged=payload.engaged)
    return KillSwitchResponse(
        engaged=bool(row.value_jsonb.get("enabled", False)),
        updated_by=row.updated_by,
        updated_at=row.updated_at,
    )


__all__ = [
    "get_flag_service",
    "get_kill_switch",
    "router",
]
