"""Auth routes — `/me` endpoints (perfil propio) + signout proxy.

Estos endpoints SOLO requieren un usuario autenticado (no permisos
explícitos). Cualquier acción admin sobre usuarios vive en `users.py`.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, get_supabase_admin
from app.db.models.user import User
from app.schemas.users import MeResponse, MeUpdate, RoleResponse
from app.services.users.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/me", tags=["Auth"])


def _build_me_response(user: User, permission_codes: list[str]) -> MeResponse:
    role_payload: RoleResponse | None = None
    if user.role is not None:
        role_payload = RoleResponse.model_validate(user.role)
    return MeResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        locale=user.locale,  # type: ignore[arg-type]
        is_active=user.is_active,
        role=role_payload,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        permissions=permission_codes,
    )


@router.get("", response_model=MeResponse, summary="Get current user profile + permissions")
async def get_me(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MeResponse:
    service = AuthService(session)
    user, permissions = await service.get_user_with_permissions(user.id)
    return _build_me_response(user, [p.code for p in permissions])


@router.patch("", response_model=MeResponse, summary="Update own profile")
async def update_me(
    payload: MeUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MeResponse:
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.avatar_url is not None:
        user.avatar_url = payload.avatar_url
    if payload.locale is not None:
        user.locale = payload.locale
    await session.flush()

    service = AuthService(session)
    user, permissions = await service.get_user_with_permissions(user.id)
    return _build_me_response(user, [p.code for p in permissions])


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Sign out current session (Supabase)",
)
async def logout(
    user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """Invalida refresh tokens del usuario en Supabase Auth.

    El frontend debe igualmente llamar `supabase.auth.signOut()` en cliente
    para limpiar las cookies de sesión locales.
    """
    try:
        get_supabase_admin().auth.admin.sign_out(str(user.id))
    except Exception as exc:  # noqa: BLE001
        logger.exception("supabase sign_out failed for %s", user.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "type": "https://mtme.ae/errors/supabase-error",
                "title": "Supabase sign_out failed",
                "status": 502,
                "detail": str(exc),
            },
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
