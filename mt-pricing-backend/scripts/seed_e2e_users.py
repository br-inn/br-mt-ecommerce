"""Seed E2E test users — idempotente.

Crea (o actualiza) los usuarios de test requeridos por el suite de Playwright
en `mt-pricing-frontend/tests/e2e/`. Registra en Supabase Auth y en
`public.users` con el rol apropiado.

Diseño:
- Usa `admin.create_user` con `email_confirm=True` + password conocida, lo que
  genera un JWT válido para login real (necesario contra servidor real donde el
  Next.js SSR valida la sesión con el Supabase secret real).
- Si el usuario ya existe en Supabase Auth, actualiza su password y continúa.
- Si la fila `public.users` ya existe, sólo actualiza el `role_id` si cambió.
- 100% idempotente: re-run seguro en cualquier momento.

Prerrequisitos:
    SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, DATABASE_URL en el entorno.

Uso local (desde dentro del contenedor backend o con uv):
    docker exec mt-backend python -m scripts.seed_e2e_users
    uv run python -m scripts.seed_e2e_users         # desde mt-pricing-backend/

Uso contra servidor remoto:
    SUPABASE_URL=https://...supabase.co \\
    SUPABASE_SERVICE_ROLE_KEY=service-role-xxx \\
    DATABASE_URL=postgresql+asyncpg://... \\
    uv run python -m scripts.seed_e2e_users
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from typing import Any
from uuid import UUID

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("seed_e2e_users")

# ---------------------------------------------------------------------------
# Definición de usuarios de test
# ---------------------------------------------------------------------------


@dataclass
class E2EUser:
    email: str
    password: str
    full_name: str
    role_code: str
    locale: str = "es"
    note: str = ""


# Un único usuario polivalente con rol más amplio — los tests de Playwright
# mockan `/api/v1/me` para simular distintos roles sin necesitar múltiples
# cuentas reales. Usar `gerente_comercial` da acceso a la mayoría de rutas.
E2E_USERS: list[E2EUser] = [
    E2EUser(
        email="e2e@mt.ae",
        password="Test1234!Test1234!",
        full_name="E2E Test User",
        role_code="gerente_comercial",
        note="Usuario genérico de pruebas E2E — Playwright lo impersona via mocks",
    ),
    E2EUser(
        email="e2e-admin@mt.ae",
        password="Test1234!Test1234!",
        full_name="E2E Admin User",
        role_code="admin",
        note="Alternativo para tests que requieren permisos admin sin mock",
    ),
]


# ---------------------------------------------------------------------------
# Helpers Supabase
# ---------------------------------------------------------------------------


def _get_admin_client() -> Any:
    """Crea cliente Supabase admin (service_role)."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        log.error("SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY deben estar en el entorno.")
        sys.exit(1)
    from supabase import create_client

    return create_client(url, key)


def _ensure_supabase_user(admin: Any, user: E2EUser) -> UUID:
    """Crea o actualiza el usuario en Supabase Auth. Devuelve el UUID."""
    try:
        # Intentar crear con email ya confirmado + password conocida.
        result = admin.auth.admin.create_user(
            {
                "email": user.email,
                "password": user.password,
                "email_confirm": True,
                "user_metadata": {
                    "full_name": user.full_name,
                    "locale": user.locale,
                },
            }
        )
        auth_user = getattr(result, "user", None) or result
        uid = UUID(str(auth_user.id if hasattr(auth_user, "id") else auth_user["id"]))
        log.info("  Supabase: usuario creado  %s → %s", user.email, uid)
        return uid
    except Exception as exc:
        err_msg = str(exc).lower()
        if (
            "already been registered" in err_msg
            or "email_exists" in err_msg
            or "already registered" in err_msg
        ):
            # Existe — listar y obtener id + actualizar password.
            log.info("  Supabase: usuario ya existe, actualizando password…")
            # list_users devuelve Page con .users
            page = admin.auth.admin.list_users()
            users_list = getattr(page, "users", None) or (page if isinstance(page, list) else [])
            for au in users_list:
                au_email = au.email if hasattr(au, "email") else au.get("email", "")
                if au_email.lower() == user.email.lower():
                    uid = UUID(str(au.id if hasattr(au, "id") else au["id"]))
                    admin.auth.admin.update_user_by_id(
                        str(uid),
                        {"password": user.password, "email_confirm": True},
                    )
                    log.info("  Supabase: password actualizada  %s → %s", user.email, uid)
                    return uid
            log.error("  No se encontró %s en la lista de Supabase.", user.email)
            sys.exit(1)
        raise


# ---------------------------------------------------------------------------
# Helpers DB (asyncpg vía SQLAlchemy)
# ---------------------------------------------------------------------------


async def _ensure_db_user(user: E2EUser, supabase_id: UUID) -> None:
    """Upsert en public.users asignando el rol indicado."""
    # Imports tardíos para no requerir app.* antes de setear DATABASE_URL.
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        log.error("DATABASE_URL debe estar en el entorno.")
        sys.exit(1)

    engine = create_async_engine(db_url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        # Obtener role_id del role_code.
        role_id_row = await session.execute(
            text("SELECT id FROM roles WHERE code = :code"),
            {"code": user.role_code},
        )
        role_row = role_id_row.first()
        if role_row is None:
            log.error(
                "  Role '%s' no encontrado en public.roles. ¿Migraciones al día?",
                user.role_code,
            )
            sys.exit(1)
        role_id = role_row[0]

        # Comprobar si ya existe la fila.
        existing = await session.execute(
            text("SELECT id, role_id FROM users WHERE id = :uid"),
            {"uid": supabase_id},
        )
        row = existing.first()

        if row is None:
            await session.execute(
                text(
                    """
                    INSERT INTO users (id, email, full_name, locale, is_active, role_id)
                    VALUES (:id, :email, :full_name, :locale, true, :role_id)
                    ON CONFLICT (id) DO UPDATE
                        SET role_id   = EXCLUDED.role_id,
                            full_name = EXCLUDED.full_name,
                            is_active = true
                    """
                ),
                {
                    "id": supabase_id,
                    "email": user.email.lower(),
                    "full_name": user.full_name,
                    "locale": user.locale,
                    "role_id": role_id,
                },
            )
            log.info("  DB: fila creada  %s  rol=%s", user.email, user.role_code)
        else:
            existing_role_id = row[1]
            if existing_role_id != role_id:
                await session.execute(
                    text("UPDATE users SET role_id = :role_id WHERE id = :uid"),
                    {"role_id": role_id, "uid": supabase_id},
                )
                log.info(
                    "  DB: rol actualizado  %s  %s → %s",
                    user.email,
                    existing_role_id,
                    user.role_code,
                )
            else:
                log.info("  DB: sin cambios  %s", user.email)

        await session.commit()

    await engine.dispose()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


async def main() -> None:
    log.info("=== seed_e2e_users ===")
    admin = _get_admin_client()

    for user in E2E_USERS:
        log.info("Procesando: %s  (rol: %s)", user.email, user.role_code)
        supabase_id = _ensure_supabase_user(admin, user)
        await _ensure_db_user(user, supabase_id)
        log.info("OK: %s", user.email)

    log.info("=== Completado (%d usuarios) ===", len(E2E_USERS))


if __name__ == "__main__":
    asyncio.run(main())
