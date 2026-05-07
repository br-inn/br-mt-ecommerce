"""UserRepository + RoleRepository."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models.user import Permission, Role, RolePermission, User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User
    pk_field = "id"
    soft_delete_field = "deleted_at"

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_role(self, user_id: UUID) -> User | None:
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.role).selectinload(Role.role_permissions))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active(self, *, limit: int = 100) -> Sequence[User]:
        stmt = (
            select(User)
            .where(User.is_active.is_(True), User.deleted_at.is_(None))
            .order_by(User.email.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def assign_role(self, user_id: UUID, role_id: UUID | None) -> User | None:
        return await self.update(user_id, role_id=role_id)


class RoleRepository(BaseRepository[Role]):
    model = Role
    pk_field = "id"
    soft_delete_field = None

    async def get_by_code(self, code: str) -> Role | None:
        stmt = select(Role).where(Role.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_permissions(self, role_id: UUID) -> Role | None:
        stmt = (
            select(Role)
            .where(Role.id == role_id)
            .options(selectinload(Role.role_permissions).selectinload(RolePermission.permission))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class PermissionRepository(BaseRepository[Permission]):
    model = Permission
    pk_field = "id"
    soft_delete_field = None

    async def get_by_code(self, code: str) -> Permission | None:
        stmt = select(Permission).where(Permission.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
