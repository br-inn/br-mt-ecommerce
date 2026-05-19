"""AuthService — orquesta usuarios + Supabase Auth.

Responsabilidades:
- Bootstrap de la fila aplicativa `users` la primera vez que un Supabase
  user se autentica (no asigna rol — lo hace TI Integración explícitamente).
- Resolución de perfil + permisos efectivos para `/me`.
- Asignación / revocación de roles (cruza con `auth.admin.sign_out` para
  forzar logout cuando se revoca un rol — ADR-032 / ADR-045).
- Invitaciones por email vía `auth.admin.invite_user_by_email`.

Convenciones:
- Cada operación que modifica estado emite un `AuditEvent` (hash chain via
  trigger DB) — el actor_id puede ser None para mutaciones de sistema.
- Los errores Supabase se traducen a `HTTPException` con ProblemDetails.
- No commitea — el caller (FastAPI dep / Celery task) decide la transacción.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.supabase import get_supabase_admin
from app.db.models.audit import AuditEvent
from app.db.models.user import Permission, Role, User
from app.repositories.user import (
    PermissionRepository,
    RoleRepository,
    UserRepository,
)
from app.services.users.force_logout_publisher import ForceLogoutPublisher

logger = logging.getLogger(__name__)


class AuthService:
    """Service orquestador de auth + user management."""

    def __init__(
        self,
        session: AsyncSession,
        force_logout_publisher: ForceLogoutPublisher | None = None,
    ) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.role_repo = RoleRepository(session)
        self.permission_repo = PermissionRepository(session)
        self.force_logout_publisher = force_logout_publisher or ForceLogoutPublisher()

    # ---------- Bootstrap on first login ----------
    async def bootstrap_user_from_jwt(self, payload: dict[str, Any]) -> User:
        """Crea la fila aplicativa la primera vez que un usuario Supabase se autentica.

        El usuario queda creado SIN rol — TI Integración debe asignarlo
        explícitamente (vía `POST /users/{id}/roles`). Hasta entonces, el
        usuario solo puede operar `/me` (no tiene permisos efectivos).
        """
        sub = payload["sub"]
        user_id = UUID(str(sub))

        existing = await self.user_repo.get_with_role(user_id)
        if existing is not None:
            return existing

        email = str(payload.get("email") or "").lower()
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "type": "https://mtme.ae/errors/invalid-token",
                    "title": "Token missing 'email' claim",
                    "status": 400,
                },
            )

        meta = payload.get("user_metadata") or {}
        full_name = meta.get("full_name") or meta.get("name")
        avatar_url = meta.get("avatar_url")
        locale_claim = str(meta.get("locale") or "es").lower()
        locale = locale_claim if locale_claim in {"es", "en", "ar"} else "es"

        user = User(
            id=user_id,
            email=email,
            full_name=full_name,
            avatar_url=avatar_url,
            locale=locale,
            is_active=True,
            role_id=None,  # SIN rol — TI Integración lo asigna explícitamente.
        )
        self.session.add(user)
        await self.session.flush()

        await self._record_audit(
            actor_id=None,
            entity_id=str(user.id),
            action="user.bootstrap",
            after={
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "source": "jwt_first_login",
            },
        )
        # Reload con role (None) para mantener invariante del caller.
        loaded = await self.user_repo.get_with_role(user.id)
        assert loaded is not None  # noqa: S101 — invariante post-flush
        return loaded

    # ---------- Profile + permissions ----------
    async def get_user_with_permissions(
        self,
        user_id: UUID,
    ) -> tuple[User, list[Permission]]:
        """Devuelve User + lista de Permission efectivos.

        Resuelve los permisos via `RolePermission` (no via `permissions_snapshot`
        para garantizar source-of-truth en lecturas de `/me`).
        """
        user = await self.user_repo.get_with_role(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "type": "https://mtme.ae/errors/user-not-found",
                    "title": "User not found",
                    "status": 404,
                },
            )
        permissions: list[Permission] = []
        if user.role is not None:
            role_full = await self.role_repo.get_with_permissions(user.role.id)
            if role_full is not None:
                permissions = [rp.permission for rp in role_full.role_permissions]
        return user, permissions

    # ---------- Role assignment ----------
    async def assign_role(
        self,
        *,
        user_id: UUID,
        role_code: str,
        granted_by: UUID,
        note: str | None = None,
    ) -> User:
        """Asigna `role_code` a `user_id`. Solo TI Integración (gating en router)."""
        role = await self.role_repo.get_by_code(role_code)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "type": "https://mtme.ae/errors/invalid-role",
                    "title": "Unknown role code",
                    "status": 400,
                    "role_code": role_code,
                },
            )

        user = await self.user_repo.get(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "type": "https://mtme.ae/errors/user-not-found",
                    "title": "User not found",
                    "status": 404,
                },
            )

        before_role_id = user.role_id
        user.role_id = role.id
        await self.session.flush()

        await self._record_audit(
            actor_id=granted_by,
            entity_id=str(user.id),
            action="user.assign_role",
            before={"role_id": str(before_role_id) if before_role_id else None},
            after={"role_id": str(role.id), "role_code": role.code, "note": note},
        )

        loaded = await self.user_repo.get_with_role(user.id)
        assert loaded is not None  # noqa: S101
        return loaded

    async def revoke_role(
        self,
        *,
        user_id: UUID,
        granted_by: UUID,
        reason: str | None = None,
    ) -> User:
        """Revoca rol y fuerza logout en Supabase Auth (ADR-032 / ADR-045)."""
        user = await self.user_repo.get(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "type": "https://mtme.ae/errors/user-not-found",
                    "title": "User not found",
                    "status": 404,
                },
            )

        before_role_id = user.role_id
        user.role_id = None
        await self.session.flush()

        # Force logout en Supabase: invalida refresh tokens; el access_token
        # vivo (TTL ~1h) seguirá funcionando hasta expirar — el frontend
        # también escucha el canal Realtime `force_logout_events` para
        # cortar UI inmediatamente. ADR-032.
        try:
            self._sign_out_supabase(user.id)
        except Exception:  # noqa: BLE001 — best-effort, no romper transacción
            logger.exception("supabase.auth.admin.sign_out failed for %s", user.id)

        # Publicar evento Realtime — el frontend del user (si está abierto)
        # dispara `signOut` local. Fail-soft: si falla, JWT TTL cubre el caso.
        await self.force_logout_publisher.publish(
            user_id=user.id,
            reason=reason or "role_revoked",
            actor_id=granted_by,
        )

        await self._record_audit(
            actor_id=granted_by,
            entity_id=str(user.id),
            action="user.revoke_role",
            before={"role_id": str(before_role_id) if before_role_id else None},
            after={"role_id": None, "force_logout": True, "reason": reason},
        )

        loaded = await self.user_repo.get_with_role(user.id)
        assert loaded is not None  # noqa: S101
        return loaded

    async def force_logout(
        self,
        *,
        user_id: UUID,
        actor_id: UUID,
        reason: str | None = None,
    ) -> None:
        """Cierra sessions de Supabase sin tocar role (ej. compromiso de cuenta)."""
        user = await self.user_repo.get(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "type": "https://mtme.ae/errors/user-not-found",
                    "title": "User not found",
                    "status": 404,
                },
            )
        try:
            self._sign_out_supabase(user.id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("supabase.auth.admin.sign_out failed for %s", user.id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "type": "https://mtme.ae/errors/supabase-error",
                    "title": "Supabase admin sign_out failed",
                    "status": 502,
                    "detail": str(exc),
                },
            ) from exc

        # Realtime broadcast — frontend del user dispara signOut inmediato.
        await self.force_logout_publisher.publish(
            user_id=user.id,
            reason=reason or "force_logout",
            actor_id=actor_id,
        )

        await self._record_audit(
            actor_id=actor_id,
            entity_id=str(user.id),
            action="user.force_logout",
            after={"reason": reason, "force_logout": True},
        )

    # ---------- Invite ----------
    async def invite_user(
        self,
        *,
        email: str,
        full_name: str,
        role_code: str,
        locale: str,
        invited_by: UUID,
    ) -> User:
        """Invita por email, asigna rol inicial y crea row aplicativo placeholder.

        Flujo:
        1. `auth.admin.invite_user_by_email` → Supabase envía magic-link.
        2. Crear row en `public.users` con id devuelto por Supabase + rol.
        3. Compensación: si el INSERT falla, intentar borrar el auth.user.
        """
        role = await self.role_repo.get_by_code(role_code)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "type": "https://mtme.ae/errors/invalid-role",
                    "title": "Unknown role code",
                    "status": 400,
                    "role_code": role_code,
                },
            )

        existing = await self.user_repo.get_by_email(email)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "type": "https://mtme.ae/errors/user-exists",
                    "title": "User with this email already exists",
                    "status": 409,
                    "email": email,
                },
            )

        admin = get_supabase_admin()
        redirect_url = f"{settings.APP_URL}/auth/callback"
        try:
            invite = admin.auth.admin.invite_user_by_email(
                email,
                {
                    "data": {"full_name": full_name, "locale": locale},
                    "redirect_to": redirect_url,
                },
            )
        except Exception as exc:  # noqa: BLE001 — supabase-py raises broad
            logger.exception("supabase.auth.admin.invite_user_by_email failed")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "type": "https://mtme.ae/errors/supabase-error",
                    "title": "Supabase invite failed",
                    "status": 502,
                    "detail": str(exc),
                },
            ) from exc

        # supabase-py returns an object with .user attribute; defensively coerce.
        auth_user = getattr(invite, "user", None) or invite
        auth_user_id_raw = getattr(auth_user, "id", None) or (
            auth_user.get("id") if isinstance(auth_user, dict) else None
        )
        if not auth_user_id_raw:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "type": "https://mtme.ae/errors/supabase-error",
                    "title": "Supabase invite returned no user id",
                    "status": 502,
                },
            )
        auth_user_id = UUID(str(auth_user_id_raw))

        user = User(
            id=auth_user_id,
            email=email.lower(),
            full_name=full_name,
            locale=locale,
            is_active=True,
            role_id=role.id,
            created_by=invited_by,
        )
        self.session.add(user)
        try:
            await self.session.flush()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Insert public.users failed; compensating auth.user delete")
            try:
                admin.auth.admin.delete_user(str(auth_user_id))
            except Exception:  # noqa: BLE001
                logger.exception("Compensation delete_user failed for %s", auth_user_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "type": "https://mtme.ae/errors/invite-failed",
                    "title": "User invitation failed",
                    "status": 500,
                    "detail": str(exc),
                },
            ) from exc

        await self._record_audit(
            actor_id=invited_by,
            entity_id=str(user.id),
            action="user.invite",
            after={
                "email": user.email,
                "role_code": role.code,
                "full_name": user.full_name,
            },
        )

        loaded = await self.user_repo.get_with_role(user.id)
        assert loaded is not None  # noqa: S101
        return loaded

    # ---------- Internals ----------
    def _sign_out_supabase(self, user_id: UUID) -> None:
        """Invalida todas las sessions del usuario en Supabase Auth."""
        admin = get_supabase_admin()
        # supabase-py expone sign_out con user_id (admin scope).
        admin.auth.admin.sign_out(str(user_id))

    async def _record_audit(
        self,
        *,
        actor_id: UUID | None,
        entity_id: str,
        action: str,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        reason: str | None = None,
    ) -> None:
        """Inserta un AuditEvent — el hash chain lo calcula el trigger DB."""
        event = AuditEvent(
            actor_id=actor_id,
            entity_type="user",
            entity_id=entity_id,
            action=action,
            before=before,
            after=after,
            payload_diff={"before": before or {}, "after": after or {}},
            reason=reason,
        )
        self.session.add(event)
        await self.session.flush()
