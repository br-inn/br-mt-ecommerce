"""Roles + Permissions catalog routes (read-only Fase 1)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import Permission, Role, RolePermission
from app.repositories.user import RoleRepository
from app.schemas.users import (
    PermissionResponse,
    RoleResponse,
    RoleWithPermissionsResponse,
)

router = APIRouter(tags=["Roles"])


@router.get(
    "/roles",
    response_model=list[RoleResponse],
    dependencies=[Depends(require_permissions("users:read"))],
    summary="List roles catalog",
)
async def list_roles(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[RoleResponse]:
    stmt = select(Role).order_by(Role.code.asc())
    result = await session.execute(stmt)
    return [RoleResponse.model_validate(r) for r in result.scalars().all()]


@router.get(
    "/roles/{role_id}/permissions",
    response_model=RoleWithPermissionsResponse,
    dependencies=[Depends(require_permissions("users:read"))],
    summary="Get role + its permissions",
)
async def get_role_permissions(
    role_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RoleWithPermissionsResponse:
    stmt = (
        select(Role)
        .where(Role.id == role_id)
        .options(selectinload(Role.role_permissions).selectinload(RolePermission.permission))
    )
    result = await session.execute(stmt)
    role = result.scalar_one_or_none()
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "https://mtme.ae/errors/role-not-found",
                "title": "Role not found",
                "status": 404,
            },
        )
    permissions = [PermissionResponse.model_validate(rp.permission) for rp in role.role_permissions]
    return RoleWithPermissionsResponse(
        id=role.id,
        code=role.code,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permissions=permissions,
    )


@router.get(
    "/permissions",
    response_model=list[PermissionResponse],
    dependencies=[Depends(require_permissions("users:read"))],
    summary="List permissions catalog",
)
async def list_permissions(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[PermissionResponse]:
    stmt = select(Permission).order_by(Permission.code.asc())
    result = await session.execute(stmt)
    return [PermissionResponse.model_validate(p) for p in result.scalars().all()]


# Repo unused-import guard — silenced for explicit re-export of the helper.
__all__ = ["router", "RoleRepository"]
