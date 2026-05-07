"""FastAPI dependencies — auth, db session, supabase clients.

Auth real (no más stubs) — implementación E2E:
- `get_current_user` lee Bearer JWT, verifica firma con `SUPABASE_JWT_SECRET`
  (HS256 — Supabase usa secret simétrico para emitir el access_token), mapea
  el claim `sub` al row aplicativo `public.users` y bootstrap-ea la fila la
  primera vez que un usuario se autentica.
- `optional_current_user` devuelve `User | None` (sin lanzar 401) — útil para
  endpoints públicos que enriquecen respuesta si hay usuario.
- `require_permissions` factory que cruza claims/permisos aplicativos contra
  los `RolePermission` cargados eager via `selectinload`.
- `require_role` helper para gating por código de rol (ej. ti_integracion).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Annotated, Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

# Re-exports — los routers importan supabase clients y db session desde aquí.
from app.core.supabase import get_supabase_admin, get_supabase_client
from app.db import get_db_session
from app.db.models.user import User
from app.repositories.user import UserRepository

if TYPE_CHECKING:
    from app.services.users.auth_service import AuthService


__all__ = [
    "extract_role_claim",
    "get_current_user",
    "get_db_session",
    "get_supabase_admin",
    "get_supabase_client",
    "optional_current_user",
    "require_permissions",
    "require_role",
    "require_role_claim",
]


def extract_role_claim(payload: dict[str, Any]) -> str | None:
    """Extrae el custom-claim `role` del JWT de Supabase.

    Convención (US-1A-01-05): el rol aplicativo (`comercial`, `gerente`, `ti`,
    `admin`) viaja en `app_metadata.role` (no se confunde con el claim `role`
    raíz de Supabase, que siempre vale `authenticated`).

    Retorna `None` si no está presente — el caller decide si lanzar 403.
    """
    app_metadata = payload.get("app_metadata") or {}
    if not isinstance(app_metadata, dict):
        return None
    role = app_metadata.get("role")
    if isinstance(role, str) and role:
        return role
    # Fallback: algunos proyectos antiguos lo ponen en user_metadata.
    user_metadata = payload.get("user_metadata") or {}
    if isinstance(user_metadata, dict):
        role = user_metadata.get("role")
        if isinstance(role, str) and role:
            return role
    return None


_bearer = HTTPBearer(auto_error=False)


# --- ProblemDetails helpers ----------------------------------------------------
def _problem(
    *,
    status_code: int,
    title: str,
    type_: str,
    detail: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Devuelve el dict que FastAPI serializa como ProblemDetails (RFC 7807)."""
    body: dict[str, Any] = {
        "type": type_,
        "title": title,
        "status": status_code,
    }
    if detail is not None:
        body["detail"] = detail
    if extra:
        body.update(extra)
    return body


# --- JWT decoding --------------------------------------------------------------
async def _decode_jwt(token: str) -> dict[str, Any]:
    """Decodifica + verifica el JWT emitido por Supabase Auth.

    Soporta dos modos (controlado por `settings.SUPABASE_JWT_VERIFICATION_MODE`):

    - ``hs256`` (default Supabase legacy): HS256 firmado con `SUPABASE_JWT_SECRET`.
    - ``jwks`` (asymmetric signing keys): RS256/ES256 contra el JWKS público de
      Supabase, con cache TTL en memoria (ver `app.core.jwks`).

    El `aud` claim siempre es `authenticated` para usuarios logueados.
    """
    try:
        if settings.SUPABASE_JWT_VERIFICATION_MODE == "jwks":
            # Import diferido — sólo cargamos httpx + JWKS si el modo lo pide.
            from app.core.jwks import decode_with_jwks

            payload = await decode_with_jwks(token, audience="authenticated")
        else:
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET.get_secret_value(),
                algorithms=[settings.JWT_ALGORITHM],
                audience="authenticated",
                options={"require": ["exp", "sub"]},
            )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_problem(
                status_code=401,
                title="Invalid or expired token",
                type_="https://mtme.ae/errors/invalid-token",
                detail=str(exc),
            ),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return payload


async def _resolve_user(
    payload: dict[str, Any],
    session: AsyncSession,
) -> User:
    """Carga (o bootstrappea) el usuario aplicativo desde el JWT payload."""
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_problem(
                status_code=401,
                title="Token missing 'sub' claim",
                type_="https://mtme.ae/errors/invalid-token",
            ),
        )
    try:
        user_id = UUID(str(sub))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_problem(
                status_code=401,
                title="Token 'sub' is not a valid UUID",
                type_="https://mtme.ae/errors/invalid-token",
            ),
        ) from exc

    user_repo = UserRepository(session)
    user = await user_repo.get_with_role(user_id)
    if user is None:
        # Primera vez que el usuario se autentica → crear row aplicativo.
        # Import diferido para evitar ciclo (auth_service usa deps).
        from app.services.users.auth_service import AuthService

        service: AuthService = AuthService(session)
        user = await service.bootstrap_user_from_jwt(payload)

    if not user.is_active or user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_problem(
                status_code=403,
                title="User account is inactive",
                type_="https://mtme.ae/errors/user-inactive",
            ),
        )
    return user


# --- Public dependencies -------------------------------------------------------
async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    """Verifica Bearer JWT y devuelve usuario aplicativo (con role + permisos)."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_problem(
                status_code=401,
                title="Missing bearer token",
                type_="https://mtme.ae/errors/missing-token",
            ),
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = await _decode_jwt(credentials.credentials)
    return await _resolve_user(payload, session)


async def optional_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User | None:
    """Igual que `get_current_user` pero devuelve None si no hay/JWT inválido."""
    if credentials is None:
        return None
    try:
        payload = await _decode_jwt(credentials.credentials)
        return await _resolve_user(payload, session)
    except HTTPException:
        return None


def require_role_claim(*allowed_codes: str) -> Callable[..., Any]:
    """Gating por el claim `app_metadata.role` del JWT (sin tocar DB).

    Diferencia clave vs `require_role`: ese resuelve el rol aplicativo desde
    `public.users`/`roles`. Este lee directamente del JWT — útil para
    pre-filtrado fast-path o en endpoints donde aún no se ha bootstrapeado
    `public.users`. Si el claim falta → 403 (no 401).
    """
    allowed = frozenset(allowed_codes)

    async def _check(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    ) -> str:
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=_problem(
                    status_code=401,
                    title="Missing bearer token",
                    type_="https://mtme.ae/errors/missing-token",
                ),
                headers={"WWW-Authenticate": "Bearer"},
            )
        payload = await _decode_jwt(credentials.credentials)
        role = extract_role_claim(payload)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_problem(
                    status_code=403,
                    title="Missing role claim",
                    type_="https://mtme.ae/errors/role-claim-missing",
                    detail="JWT no contiene `app_metadata.role`.",
                ),
            )
        if role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_problem(
                    status_code=403,
                    title="Role not allowed",
                    type_="https://mtme.ae/errors/role-denied",
                    detail=f"Rol '{role}' no permitido. Permitidos: {sorted(allowed)}",
                ),
            )
        return role

    return _check


def _user_permission_codes(user: User) -> set[str]:
    """Extrae los códigos de permiso efectivos del usuario.

    Se apoya en que `get_with_role` carga eager `role.role_permissions`. Para
    obtener el `permission.code` necesitamos otra carga; aquí usamos
    `permissions_snapshot` (JSONB) que el Agente C mantiene sincronizado en
    cada `assign_role` para evitar un join extra en el hot-path.
    """
    if user.role is None:
        return set()
    snapshot = user.role.permissions_snapshot or []
    if isinstance(snapshot, list):
        return {str(p) for p in snapshot}
    return set()


def require_permissions(*required: str) -> Callable[..., Any]:
    """Factory de dependency — gating por permisos aplicativos.

    Uso::

        @router.post(
            "/users/invite",
            dependencies=[Depends(require_permissions("users:invite"))],
        )
    """
    required_set = frozenset(required)

    async def _check(
        user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        user_perms = _user_permission_codes(user)
        missing = required_set - user_perms
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_problem(
                    status_code=403,
                    title="Permission denied",
                    type_="https://mtme.ae/errors/permission-denied",
                    detail=f"Missing permissions: {', '.join(sorted(missing))}",
                    extra={"missing_permissions": sorted(missing)},
                ),
            )
        return user

    return _check


def require_role(*role_codes: str) -> Callable[..., Any]:
    """Gating por código de rol (admin shortcut: `require_role('ti_integracion')`)."""
    allowed: Iterable[str] = role_codes

    async def _check(
        user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if user.role is None or user.role.code not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_problem(
                    status_code=403,
                    title="Role not allowed",
                    type_="https://mtme.ae/errors/role-denied",
                    detail=f"Required role(s): {', '.join(allowed)}",
                ),
            )
        return user

    return _check
