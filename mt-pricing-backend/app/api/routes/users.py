"""Admin user management routes.

Toda mutación requiere `users:*` permission o role `ti_integracion`.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import (
    get_current_user,
    get_db_session,
    require_permissions,
)
from app.db.models.user import Role, User
from app.repositories.user import UserRepository
from app.schemas.users import (
    RoleAssignment,
    UserInvite,
    UserListItem,
    UserResponse,
    UserUpdate,
)
from app.services.users.auth_service import AuthService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "",
    response_model=list[UserListItem],
    dependencies=[Depends(require_permissions("users:read"))],
    summary="List users (paginated, filterable)",
)
async def list_users(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    role: Annotated[str | None, Query(description="Filter by role code")] = None,
    is_active: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[UserListItem]:
    stmt = (
        select(User)
        .options(selectinload(User.role))
        .where(User.deleted_at.is_(None))
        .order_by(User.email.asc())
        .limit(limit)
        .offset(offset)
    )
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))
    if role is not None:
        stmt = stmt.join(Role, User.role_id == Role.id).where(Role.code == role)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [UserListItem.model_validate(u) for u in rows]


@router.post(
    "/invite",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions("users:invite"))],
    summary="Invite user by email + assign initial role",
)
async def invite_user(
    payload: UserInvite,
    actor: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserResponse:
    service = AuthService(session)
    user = await service.invite_user(
        email=payload.email,
        full_name=payload.full_name,
        role_code=payload.role_code,
        locale=payload.locale,
        invited_by=actor.id,
    )
    return UserResponse.model_validate(user)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(require_permissions("users:read"))],
    summary="Get user by id",
)
async def get_user(
    user_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserResponse:
    repo = UserRepository(session)
    user = await repo.get_with_role(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "https://mtme.ae/errors/user-not-found",
                "title": "User not found",
                "status": 404,
            },
        )
    return UserResponse.model_validate(user)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(require_permissions("users:write"))],
    summary="Update user (admin)",
)
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserResponse:
    repo = UserRepository(session)
    user = await repo.get(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "https://mtme.ae/errors/user-not-found",
                "title": "User not found",
                "status": 404,
            },
        )
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.locale is not None:
        user.locale = payload.locale
    if payload.is_active is not None:
        user.is_active = payload.is_active
    await session.flush()
    user_with_role = await repo.get_with_role(user.id)
    return UserResponse.model_validate(user_with_role)


@router.post(
    "/{user_id}/roles",
    response_model=UserResponse,
    dependencies=[Depends(require_permissions("users:assign_role"))],
    summary="Assign role to user",
)
async def assign_role(
    user_id: UUID,
    payload: RoleAssignment,
    actor: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserResponse:
    service = AuthService(session)
    user = await service.assign_role(
        user_id=user_id,
        role_code=payload.role_code,
        granted_by=actor.id,
        note=payload.note,
    )
    return UserResponse.model_validate(user)


@router.delete(
    "/{user_id}/roles",
    response_model=UserResponse,
    dependencies=[Depends(require_permissions("users:assign_role"))],
    summary="Revoke user role + force logout",
)
async def revoke_role(
    user_id: UUID,
    actor: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    reason: Annotated[str | None, Query(max_length=500)] = None,
) -> UserResponse:
    service = AuthService(session)
    user = await service.revoke_role(
        user_id=user_id,
        granted_by=actor.id,
        reason=reason,
    )
    return UserResponse.model_validate(user)


@router.post(
    "/{user_id}/force-logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(require_permissions("users:force_logout"))],
    summary="Force logout (revoke all Supabase sessions)",
)
async def force_logout(
    user_id: UUID,
    actor: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    reason: Annotated[str | None, Query(max_length=500)] = None,
) -> Response:
    service = AuthService(session)
    await service.force_logout(
        user_id=user_id,
        actor_id=actor.id,
        reason=reason,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
