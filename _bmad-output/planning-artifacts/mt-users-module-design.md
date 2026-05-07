---
title: "Diseño del módulo de usuarios — MT Pricing/MDM"
status: "draft"
version: "1.1"
created: "2026-05-06"
updated: "2026-05-06"
project_name: "mt-pricing-mdm-phase1"
related: ["architecture-mt-pricing-mdm-phase1.md", "prd-mt-pricing-mdm-phase1.md", "epics-and-stories-mt-pricing-mdm-phase1.md", "reuse-from-hppt-iom.md"]
reference_project: "br-hppt/br-hppt-iom-review_1/Hppt-dashboard"
changelog:
  - "1.0 (2026-05-06): versión inicial — patrón hppt-iom puro (supabase-py + Pydantic, sin SQLAlchemy)."
  - "1.1 (2026-05-06): alineación con ADR-045 persistencia híbrida. Tablas `users`, `roles`, `permissions`, `user_roles`, `role_permissions` se modelan con SQLAlchemy 2.0 async ORM; integración con `auth.users` (Supabase) via supabase-py en endpoints de bootstrap-on-first-login y admin (`auth.admin.create_user`, `auth.admin.sign_out`). Decidido: forzamos `sign_out(user_id)` al revocar rol para minimizar lag de propagación del JWT (cierra TODO previo del lag de 1h)."
---

# Diseño del módulo de usuarios para MT (Task 5)

> **Decisión guía (v1.1, alineada con ADR-045).** Persistencia **híbrida**: tablas aplicativas (`users`, `roles`, `permissions`, `user_roles`, `role_permissions`, `user_role_audit`) modeladas con **SQLAlchemy 2.0 async ORM** + Alembic. Identidad y JWT siguen viniendo de **Supabase Auth** (fuente de verdad), con integración bidireccional via **supabase-py** en endpoints administrativos (`auth.admin.create_user`, `auth.admin.sign_out`, `auth.admin.invite_user_by_email`) y un trigger Postgres `on_auth_user_created` que bootstrapa la fila aplicativa. Permisos firmados en JWT (`app_metadata.permissions`) via trigger se mantienen del patrón hppt-iom. RLS Postgres como segundo cordón de defensa.

---

## 5.1 Backend (`mt-pricing-backend/`)

### 5.1.1 Modelos — SQLAlchemy 2.0 async ORM + supabase-py para Auth/Storage (ADR-045)

> **Justificación (revisada v1.1).** El módulo de usuarios sigue siendo simple, pero la decisión global del proyecto (ADR-045) es modelar todas las tablas aplicativas con SQLAlchemy 2.0 async para uniformidad con products / prices / costs / audit_events / job_definitions. La integración con `auth.users` de Supabase ocurre solo en dos puntos: (a) trigger Postgres `on_auth_user_created` que crea la fila inicial en `public.users` (sin rol), y (b) endpoints admin que llaman `supabase.auth.admin.*` antes/después de operaciones SQLAlchemy. **No hay duplicación de fuentes de verdad**: Supabase es source para identidad/sesión/JWT; SQLAlchemy es source para datos aplicativos del usuario (rol, locale, audit).

**Esquema Postgres (definido en migración Supabase, no en código):**

```sql
-- profiles: 1:1 con auth.users
create table public.profiles (
    id              uuid primary key references auth.users(id) on delete cascade,
    email           citext unique not null,
    full_name       text,
    avatar_url      text,
    locale          text not null default 'es',
    is_active       boolean not null default true,
    role_id         uuid references public.roles(id),
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),
    created_by      uuid references auth.users(id),
    last_login_at   timestamptz
);

-- roles
create table public.roles (
    id              uuid primary key default gen_random_uuid(),
    code            text unique not null,           -- 'comercial', 'gerente_comercial', 'ti_integracion', 'champion', 'backup_operator'
    name            text not null,                  -- legible
    description     text,
    is_system       boolean not null default true,  -- true para los 5 roles base
    permissions     jsonb not null default '[]'::jsonb, -- snapshot resuelto via fn
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

-- permissions catálogo
create table public.permissions (
    id              text primary key,               -- ej. 'pricing:approve'
    module          text not null,                  -- ej. 'pricing'
    description     text not null
);

-- role_permissions M:N
create table public.role_permissions (
    role_id         uuid not null references public.roles(id) on delete cascade,
    permission_id   text not null references public.permissions(id) on delete cascade,
    primary key (role_id, permission_id)
);

-- user_role_audit (asignaciones/revocaciones)
create table public.user_role_audit (
    id              uuid primary key default gen_random_uuid(),
    user_id         uuid not null references auth.users(id) on delete cascade,
    role_id         uuid not null references public.roles(id),
    action          text not null check (action in ('granted','revoked')),
    actor_id        uuid references auth.users(id),
    created_at      timestamptz not null default now(),
    note            text
);
```

**Trigger de sync a `auth.users.app_metadata`** (replicado de hppt; la app firma permisos en JWT para no hacer roundtrip por request):

```sql
create or replace function public.sync_user_app_metadata()
returns trigger language plpgsql security definer as $$
declare
    v_role_code text;
    v_perms     jsonb;
begin
    -- Resolver role_code y permissions a partir de profiles.role_id
    select r.code,
           coalesce(jsonb_agg(rp.permission_id) filter (where rp.permission_id is not null), '[]'::jsonb)
    into v_role_code, v_perms
    from public.roles r
    left join public.role_permissions rp on rp.role_id = r.id
    where r.id = NEW.role_id
    group by r.code;

    update auth.users
    set raw_app_meta_data =
        coalesce(raw_app_meta_data, '{}'::jsonb)
        || jsonb_build_object(
            'role',        coalesce(v_role_code, 'no_role'),
            'role_id',     NEW.role_id,
            'permissions', coalesce(v_perms, '[]'::jsonb)
        )
    where id = NEW.id;
    return NEW;
end;
$$;

create trigger trg_profiles_sync_metadata
after insert or update of role_id on public.profiles
for each row execute function public.sync_user_app_metadata();
```

**Pydantic models** (`mt-pricing-backend/app/models/users.py`):

```python
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, Literal
from uuid import UUID

class Role(BaseModel):
    id: UUID
    code: Literal["comercial","gerente_comercial","ti_integracion","champion","backup_operator"]
    name: str
    description: Optional[str] = None
    is_system: bool

class Profile(BaseModel):
    id: UUID
    email: EmailStr
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    locale: str = "es"
    is_active: bool = True
    role_id: Optional[UUID] = None
    role: Optional[Role] = None        # populated por SELECT con join
    created_at: datetime
    last_login_at: Optional[datetime] = None
```

### 5.1.2 Schemas Pydantic (Create / Update / Response)

`mt-pricing-backend/app/schemas/users.py`:

```python
class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=100)
    role_code: Literal["comercial","gerente_comercial","ti_integracion","champion","backup_operator"]
    locale: str = "es"
    send_magic_link: bool = True       # Fase 1: magic link primario

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    locale: Optional[str] = None
    is_active: Optional[bool] = None

class MeUpdate(BaseModel):
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    locale: Optional[str] = None

class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: Optional[str]
    avatar_url: Optional[str]
    locale: str
    is_active: bool
    role: Optional[Role]
    last_login_at: Optional[datetime]
    created_at: datetime

class RoleAssign(BaseModel):
    role_id: UUID
    note: Optional[str] = None
```

### 5.1.3 Endpoints REST (`mt-pricing-backend/app/routers/users.py`)

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.auth import get_current_user, require_permissions
from app.services import users as users_svc

router = APIRouter()

@router.get("/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user),
                 session: AsyncSession = Depends(get_session)):
    """
    Fetch profile + role + permissions con SQLAlchemy async (ADR-045).

    Implementación en `users_svc.get_profile`:
        stmt = (
            select(User)
            .options(joinedload(User.user_roles).joinedload(UserRole.role).joinedload(Role.permissions))
            .where(User.id == user["id"])
        )
        result = await session.execute(stmt)
        return result.scalar_one()
    """
    return await users_svc.get_profile(session, user["id"])

@router.patch("/me", response_model=UserResponse)
async def patch_me(payload: MeUpdate, user: dict = Depends(get_current_user)):
    return await users_svc.update_profile(user["id"], payload)

@router.get("/users", response_model=list[UserResponse])
async def list_users(
    role: Optional[str] = None,
    active: Optional[bool] = None,
    q: Optional[str] = Query(None, max_length=100),
    page: int = 1, size: int = Query(50, le=200),
    _user = Depends(require_permissions(["users:read"])),
):
    return await users_svc.list_users(role=role, active=active, q=q, page=page, size=size)

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: UUID, _user = Depends(require_permissions(["users:read"]))):
    return await users_svc.get_profile(user_id)

@router.patch("/users/{user_id}", response_model=UserResponse)
async def patch_user(user_id: UUID, payload: UserUpdate, _user = Depends(require_permissions(["users:manage"]))):
    return await users_svc.update_profile(user_id, payload)

@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user(payload: UserCreate, actor = Depends(require_permissions(["users:manage"]))):
    """Admin invita: crea auth.users + profiles + role_id, opcional magic link."""
    return await users_svc.invite_user(payload, actor_id=actor["id"])

@router.post("/users/{user_id}/roles", status_code=204)
async def assign_role(user_id: UUID, payload: RoleAssign, actor = Depends(require_permissions(["users:manage"]))):
    await users_svc.assign_role(user_id, payload.role_id, actor_id=actor["id"], note=payload.note)

@router.delete("/users/{user_id}/roles/{role_id}", status_code=204)
async def revoke_role(user_id: UUID, role_id: UUID, actor = Depends(require_permissions(["users:manage"]))):
    await users_svc.revoke_role(user_id, role_id, actor_id=actor["id"])

@router.get("/roles", response_model=list[Role])
async def list_roles(_user = Depends(require_permissions(["users:read"]))):
    return await users_svc.list_roles()
```

### 5.1.4 Servicio (`mt-pricing-backend/app/services/users.py`)

```python
from app.database import get_supabase_client
from app.core.security import generate_secure_password

async def invite_user(payload: UserCreate, actor_id: str) -> Profile:
    sb = get_supabase_client()  # service-role
    # 1. Crear auth.users vía Admin API
    if payload.send_magic_link:
        admin_resp = sb.auth.admin.invite_user_by_email(
            email=payload.email,
            options={"data": {"full_name": payload.full_name, "locale": payload.locale}},
        )
    else:
        # Fallback: crear con password temporal y flag requires_password_reset
        temp_pwd = generate_secure_password()
        admin_resp = sb.auth.admin.create_user(
            email=payload.email, password=temp_pwd, email_confirm=True,
            user_metadata={"full_name": payload.full_name,
                           "requires_password_reset": True,
                           "locale": payload.locale},
        )
    auth_user_id = admin_resp.user.id
    # 2. Resolver role_id desde code
    role = sb.table("roles").select("id").eq("code", payload.role_code).single().execute().data
    # 3. UPSERT profiles (el trigger sync_user_app_metadata corre en update de role_id)
    sb.table("profiles").upsert({
        "id": auth_user_id, "email": payload.email,
        "full_name": payload.full_name, "locale": payload.locale,
        "role_id": role["id"], "created_by": actor_id,
    }).execute()
    # 4. Audit
    sb.table("user_role_audit").insert({
        "user_id": auth_user_id, "role_id": role["id"],
        "action": "granted", "actor_id": actor_id,
        "note": "initial assignment via invite_user",
    }).execute()
    return await get_profile(auth_user_id)
```

### 5.1.5 Dependency injection helpers — patrones MT

Replica directa de `hppt-iom-backend/app/core/auth.py`:

```python
# app/core/auth.py — MT version
async def get_current_user(creds = Depends(security_scheme)) -> dict:
    """Valida JWT contra Supabase Auth, devuelve {id, email, role, permissions}."""
    ...

def require_permissions(required: list[str], match_logic: str = "all"):
    """Dependency factory: 403 si falta el permiso. all|any."""
    ...

def require_role(*roles: str):
    """Atajo: cualquier rol coincidente. Útil para endpoints simples."""
    async def dep(user: dict = Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(403, "Role not allowed")
        return user
    return dep
```

### 5.1.6 RLS policies Supabase (defensa en profundidad)

> **Principio.** Aún si el backend FastAPI tuviera bug de auth, la BD impone RLS. Ningún rol no-admin debe poder leer otros perfiles ni mutar `roles`/`role_permissions`. Las tablas de negocio (productos, precios, costos, …) llevan policies por rol siguiendo la matriz del PRD.

`supabase/migrations/20260506_users_module.sql` (extracto):

```sql
alter table public.profiles enable row level security;
alter table public.roles enable row level security;
alter table public.role_permissions enable row level security;
alter table public.user_role_audit enable row level security;

-- profiles: cada usuario lee su propio perfil; ti_integracion lee/edita todos
create policy "profiles_self_read" on public.profiles
    for select using (auth.uid() = id);

create policy "profiles_admin_all" on public.profiles
    for all using ( (auth.jwt() -> 'app_metadata' ->> 'role') = 'ti_integracion' )
    with check ( (auth.jwt() -> 'app_metadata' ->> 'role') = 'ti_integracion' );

-- roles + role_permissions: read all auth, write only ti_integracion
create policy "roles_read_authenticated" on public.roles for select using (auth.role() = 'authenticated');
create policy "roles_admin_write" on public.roles for all
    using ( (auth.jwt() -> 'app_metadata' ->> 'role') = 'ti_integracion' )
    with check ( (auth.jwt() -> 'app_metadata' ->> 'role') = 'ti_integracion' );

-- Ejemplo dominio: products (en Fase 1)
-- comercial: SELECT/INSERT/UPDATE
-- gerente_comercial: SELECT + (UPDATE solo si is_approved cambia)
-- ti_integracion: ALL
create policy "products_read_all_active" on public.products
    for select using (auth.role() = 'authenticated');

create policy "products_write_comercial_or_admin" on public.products
    for insert with check (
        (auth.jwt() -> 'app_metadata' ->> 'role') in ('comercial','ti_integracion')
    );

create policy "products_update_owner_or_admin" on public.products
    for update using (
        (auth.jwt() -> 'app_metadata' ->> 'role') in ('comercial','ti_integracion')
        or (
            (auth.jwt() -> 'app_metadata' ->> 'role') = 'gerente_comercial'
            and current_setting('app.is_approval_change', true) = 'on'
        )
    );
```

> **Nota.** `current_setting('app.is_approval_change')` es un guard que el backend setea en transacciones de aprobación; mantiene la policy declarativa pero acotada al flujo correcto.

### 5.1.7 Sync Supabase ↔ aplicativa: trigger `on_auth_user_created`

> **Rol del trigger (v1.1).** Safety net **idempotente**: garantiza que toda fila en `auth.users` tenga su contrapartida en `public.users`/`public.profiles`, **sin rol asignado**. El rol se asigna luego desde un endpoint admin (`POST /users/{id}/roles`) que es el único path autorizado para mutar `user_roles`. El bootstrap completo (auth + role) en flujo normal lo hace `users_service.invite_user` (ver F-USR-02) en una transacción coordinada SQLAlchemy + supabase-py.

```sql
-- Bootstrap inicial: si un admin crea un user vía supabase.auth.admin.create_user
-- o invite_user_by_email, el trigger garantiza que profiles existe (idempotente, sin rol)
create or replace function public.on_auth_user_created()
returns trigger language plpgsql security definer as $$
begin
    insert into public.profiles (id, email, full_name, locale)
    values (
        NEW.id,
        NEW.email,
        coalesce(NEW.raw_user_meta_data ->> 'full_name', NEW.email),
        coalesce(NEW.raw_user_meta_data ->> 'locale', 'es')
    )
    on conflict (id) do nothing;
    -- NOTA: no inserta en user_roles. El rol se asigna explícitamente vía endpoint admin.
    return NEW;
end;
$$;

create trigger trg_on_auth_user_created
after insert on auth.users
for each row execute function public.on_auth_user_created();
```

**Decisión.** No usar Edge Functions — patrón hppt usa trigger + service-role. Más simple y trazable. Trigger gestionado en `supabase/migrations/` (toca `auth.*`, fuera de Alembic — ver ADR-045 §8.0.4 split de migraciones).

### 5.1.8 Migraciones Supabase (archivo SQL)

`supabase/migrations/20260506_120000_users_module.sql` debe contener, en orden:

1. Extensiones requeridas (`citext`, `pgcrypto` para `gen_random_uuid()`).
2. Tablas: `roles`, `permissions`, `role_permissions`, `profiles`, `user_role_audit`.
3. Funciones: `sync_user_app_metadata`, `handle_new_auth_user`.
4. Triggers asociados.
5. RLS enable + policies.
6. Seed: 5 roles base + permisos del PRD + asignación inicial.

---

## 5.2 Frontend (`mt-pricing-frontend/`)

### 5.2.1 Auth providers Supabase (idéntico a hppt)

- `src/utils/supabase/client.ts` — `createBrowserClient` para Client Components.
- `src/utils/supabase/server.ts` — `createServerClient` para RSC.
- `src/utils/supabase/admin.ts` — `createRawAdminClient` con service-role (solo Server Actions admin).
- `src/utils/supabase/update-session.ts` — utilizada por el middleware.

### 5.2.2 Middleware Next.js

`src/middleware.ts` (idéntico estructuralmente al hppt):

```ts
export async function middleware(request: NextRequest) {
  if (!request.nextUrl.pathname.startsWith("/api/")) {
    const upgraded = httpsUpgradeIfNeeded(request);
    if (upgraded) return upgraded;
  }
  if (request.nextUrl.pathname.startsWith('/api/')) {
    const rl = apiRateLimit(request);
    if (rl.status === 429) return rl;
  }
  return await updateSession(request);
}
export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)"],
};
```

### 5.2.3 Páginas

```
src/app/
├── (auth)/
│   ├── login/page.tsx                    # email + magic link primario; password fallback
│   ├── magic-link-sent/page.tsx
│   ├── auth/callback/route.ts            # exchange code → session
│   └── update-password/page.tsx          # forced rotation tras invitación con password
├── (dashboard)/
│   ├── account/page.tsx                  # perfil propio
│   ├── admin/
│   │   ├── users/page.tsx                # tabla CRUD
│   │   ├── users/[id]/page.tsx
│   │   └── roles/page.tsx                # solo lectura Fase 1 (5 roles fijos)
│   └── layout.tsx
```

### 5.2.4 Componentes

```
src/components/
├── auth/
│   ├── LoginForm.tsx                     # magic-link + password fallback
│   ├── UpdatePasswordForm.tsx
│   └── RbacGuard.tsx                     # <RbacGuard role="ti_integracion">{children}</RbacGuard>
├── admin/
│   ├── UsersTable.tsx                    # adapta hppt RolesTable
│   ├── UserDialog.tsx                    # create/edit
│   ├── RoleBadge.tsx
│   └── BulkInviteDialog.tsx              # opcional Fase 1
└── layout/
    └── UserMenu.tsx                      # avatar + name + signout
```

**`<RbacGuard>` (HOC declarativo):**

```tsx
"use client";
import { usePermissions } from "@/hooks/usePermissions";

export function RbacGuard({
  role, permission, children, fallback = null,
}: { role?: string; permission?: PermissionId; children: ReactNode; fallback?: ReactNode }) {
  const { hasPermission, roleId, isLoading } = usePermissions();
  const { user } = useAuth();
  if (isLoading) return null;
  const okRole = role ? user?.app_metadata?.role === role : true;
  const okPerm = permission ? hasPermission(permission) : true;
  if (!okRole || !okPerm) return <>{fallback}</>;
  return <>{children}</>;
}
```

### 5.2.5 Hooks

`src/hooks/useUser.ts`:

```ts
export function useUser() {
  const { user, session, loading } = useAuthContext();
  return {
    user, session, loading,
    isAuthenticated: !!user,
    role: (user?.app_metadata as any)?.role as string | undefined,
    fullName: user?.user_metadata?.full_name as string | undefined,
  };
}
```

`src/hooks/useRoles.ts`: tan-stack-query a `/api/roles`.

`src/hooks/useHasRole.ts`:

```ts
export function useHasRole(role: string | string[]): boolean {
  const { role: current } = useUser();
  if (!current) return false;
  return Array.isArray(role) ? role.includes(current) : current === role;
}
```

`src/hooks/usePermissions.ts`: idéntico a `c:/BR-Github/br-hppt/br-hppt-iom-review_1/Hppt-dashboard/hppt-iom-frontend/src/hooks/usePermissions.ts:11-58`.

### 5.2.6 Server Actions (`src/actions/users-actions.ts`)

Patrón hppt con `withPermissionAuth`:

```ts
"use server";
import { withPermissionAuth } from "@/lib/auth/permission-guard";
import { createRawAdminClient } from "@/utils/supabase/admin";

export const getUsers = withPermissionAuth(["users:read"], async () => {
  const sb = createRawAdminClient();
  const [users, roles] = await Promise.all([
    sb.auth.admin.listUsers({ perPage: 1000 }),
    sb.from("roles").select("id,code,name"),
  ]);
  const roleMap = new Map((roles.data ?? []).map(r => [r.id, r]));
  return (users.data?.users ?? []).map(u => ({
    id: u.id, email: u.email, full_name: u.user_metadata?.full_name,
    role: roleMap.get(u.app_metadata?.role_id),
    is_active: !u.banned_until,
    last_sign_in_at: u.last_sign_in_at,
  }));
});

export const inviteUser = withPermissionAuth(["users:manage"], async (input: {
  email: string; full_name: string; role_code: string;
}) => {
  // Llama backend FastAPI → POST /api/users
  const session = await getSessionToken();
  const res = await fetch(`${BACKEND_URL()}/api/users`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${session}` },
    body: JSON.stringify({ ...input, send_magic_link: true }),
  });
  if (!res.ok) throw await handleSecureError(res);
  revalidatePath("/admin/users");
  return res.json();
});
```

---

## 5.3 Flujos

### F-USR-01 Login (magic link primario, password fallback)

1. Usuario abre `/login`.
2. Ingresa email → click "Enviar enlace".
3. FE llama `supabase.auth.signInWithOtp({ email, options: { emailRedirectTo: `${origin}/auth/callback` } })`.
4. Email llega → click → Supabase redirige a `/auth/callback?code=…`.
5. Server route en `/auth/callback/route.ts` ejecuta `supabase.auth.exchangeCodeForSession(code)` → setea cookies.
6. Middleware permite acceso; redirect a `/`.
7. **Fallback password**: si user marca "Tengo password", se muestra input + `signInWithPassword`.

### F-USR-02 Admin invita usuario (patrón híbrido ADR-045)

1. TI abre `/admin/users`.
2. Click "Nuevo usuario" → `<UserDialog>`.
3. Escribe email, full_name, role_code → "Enviar invitación".
4. FE → Server Action `inviteUser` → backend `POST /auth/register` con `send_magic_link=true`.
5. Backend `users_service.invite_user(...)` ejecuta como transacción coordinada:
   1. `supabase.auth.admin.create_user(email=..., email_confirm=False, user_metadata={...})` (cliente supabase-py, ver `app/core/supabase.py`).
   2. Si éxito, abre transacción SQLAlchemy async (`async with db.begin():`) y hace INSERT en `public.users` (con el `auth_user_id` retornado), INSERT en `public.user_roles(user_id, role_id, granted_by, granted_at)`, INSERT en `public.user_role_audit`.
   3. Si la transacción SQLAlchemy falla, compensación: `supabase.auth.admin.delete_user(auth_user_id)` para no dejar identidad huérfana.
   4. Si todo ok, `supabase.auth.admin.invite_user_by_email(...)` para enviar el magic link (separado del create_user para que la fila aplicativa exista antes de que el usuario aterrice).
6. Trigger `on_auth_user_created` (Postgres) actúa como **safety net idempotente**: si por cualquier razón el endpoint falla entre paso 5.1 y 5.2, el trigger crea una fila inicial en `public.users` sin rol; un endpoint admin posterior puede asignar el rol via `POST /users/{id}/roles`.
7. Trigger `sync_user_app_metadata` propaga el rol al `auth.users.raw_app_meta_data` → JWT lo refleja en próximo refresh.
8. Email magic-link sale al invitado.
9. Invitado click → `/auth/callback` → primer login → `/account` para completar perfil.

### F-USR-03 Cambio de rol (con force-logout — ADR-045 v1.1)

1. TI abre `/admin/users/{id}`.
2. Selector de rol → "Guardar".
3. Server Action → backend `POST /api/users/{id}/roles` con nuevo `role_id`.
4. Backend (transacción SQLAlchemy async):
   - UPDATE `public.user_roles` SET `role_id` = …, `granted_by` = actor, `granted_at` = now().
   - INSERT `public.user_role_audit(action='granted', actor_id, …)`. Si había rol previo, INSERT adicional con `action='revoked'`.
5. Trigger Postgres refresca `auth.users.raw_app_meta_data.permissions` automáticamente.
6. **Force-logout (decidido v1.1).** Tras commit de la transacción, el backend invoca `supabase.auth.admin.sign_out(user_id)` (cliente supabase-py admin) para revocar el refresh token activo del usuario afectado. El próximo request del usuario fallará 401 → la SPA redirige a `/login` y al re-autenticarse el JWT trae el rol nuevo.
7. **Decidido (cierra TODO previo del lag de 1h):** forzamos `sign_out` al revocar/cambiar rol para minimizar el lag de propagación. Trade-off UX (re-login forzado) aceptado a cambio de coherencia inmediata de permisos.

### F-USR-04 Recuperación de contraseña

1. `/login` → "Olvidé mi contraseña" → `/forgot-password`.
2. Email → `supabase.auth.resetPasswordForEmail(email, { redirectTo: '/update-password' })`.
3. Email link → `/update-password` con code en URL.
4. Form `newPassword + confirm` → `supabase.auth.updateUser({ password })`.
5. Tras éxito, redirect a `/`.

### F-USR-05 Logout

1. UserMenu → click "Cerrar sesión".
2. `supabase.auth.signOut({ scope: "local" })`.
3. AuthProvider broadcast a otras pestañas via `BroadcastChannel("mt-auth")`.
4. Middleware redirige a `/login` en próximo request.
5. Opción "Cerrar sesión en todas las sesiones" → `scope: "global"` (revoca refresh token server-side).

### F-USR-06 RBAC check en endpoint protegido (backend)

```python
@router.post("/products")
async def create_product(payload: ProductCreate,
                         user = Depends(require_permissions(["products:manage"]))):
    # JWT ya validado, permiso ya chequeado, sigue lógica de negocio
    return await products_svc.create(payload, actor_id=user["id"])
```

Si falta el permiso → 403 automático con mensaje genérico. Logs internos detallan qué permiso faltó.

### F-USR-07 RBAC check en componente protegido (frontend)

```tsx
<RbacGuard permission="pricing:approve" fallback={<ApprovalReadOnly />}>
  <ApprovalForm />
</RbacGuard>
```

O imperativo:

```tsx
const { hasPermission } = usePermissions();
return (
  <Button disabled={!hasPermission("pricing:approve")}>Aprobar</Button>
);
```

---

## 5.4 Migración inicial / seed

`supabase/migrations/20260506_130000_users_seed.sql`:

```sql
-- 1. Permisos catálogo (Fase 1)
insert into public.permissions (id, module, description) values
  ('users:read',         'users',   'Ver usuarios y roles'),
  ('users:manage',       'users',   'Crear/editar usuarios y asignar roles'),
  ('products:read',      'products','Ver productos'),
  ('products:manage',    'products','Crear/editar productos'),
  ('costs:read',         'costs',   'Ver costos'),
  ('costs:manage',       'costs',   'Cargar y editar costos'),
  ('pricing:read',       'pricing', 'Ver precios'),
  ('pricing:simulate',   'pricing', 'Simular what-if'),
  ('pricing:approve',    'pricing', 'Aprobar cambios de precio'),
  ('comparator:read',    'comparator','Ver pipeline R&D comparator'),
  ('comparator:manage',  'comparator','Calibrar/promover comparator'),
  ('imports:run',        'imports', 'Disparar imports'),
  ('imports:read',       'imports', 'Ver historial imports'),
  ('audit:read',         'audit',   'Leer audit trail'),
  ('integrations:manage','integrations','Configurar conectores e-com'),
  ('admin:system:read',  'admin',   'Lectura admin sistema'),
  ('admin:system:manage','admin',   'Cambios admin sistema')
on conflict (id) do nothing;

-- 2. Roles base (5)
insert into public.roles (code, name, description, is_system) values
  ('comercial',          'Comercial',           'Carga productos, costos, sugiere precios', true),
  ('gerente_comercial',  'Gerente Comercial',   'Aprueba precios, excepciones, reportes', true),
  ('ti_integracion',     'TI / Integración',    'Admin sistema, integraciones, usuarios', true),
  ('champion',           'Champion / R&D',      'Calibrador comparator, owner de reglas', true),
  ('backup_operator',    'Operador Backup',     'Acceso de respaldo, lectura amplia', true)
on conflict (code) do nothing;

-- 3. Mapping role → permissions
with role_perm as (
  select r.id as role_id, p.id as permission_id
  from public.roles r cross join public.permissions p
  where (r.code = 'ti_integracion')                                                            -- admin total
     or (r.code = 'comercial'         and p.id in ('users:read','products:read','products:manage','costs:read','costs:manage','pricing:read','pricing:simulate','imports:read','audit:read'))
     or (r.code = 'gerente_comercial' and p.id in ('users:read','products:read','costs:read','pricing:read','pricing:simulate','pricing:approve','imports:read','audit:read'))
     or (r.code = 'champion'          and p.id in ('users:read','products:read','comparator:read','comparator:manage','audit:read'))
     or (r.code = 'backup_operator'   and p.id in ('users:read','products:read','costs:read','pricing:read','imports:read','audit:read'))
)
insert into public.role_permissions (role_id, permission_id)
select role_id, permission_id from role_perm
on conflict do nothing;

-- 4. Crear primer admin (Pablo Sierra)
-- NOTA: el row en auth.users debe existir antes (creado vía Supabase Studio o
-- vía supabase.auth.admin.create_user). Aquí solo conectamos el profile + role.
do $$
declare v_admin_uid uuid; v_role_id uuid;
begin
  select id into v_admin_uid from auth.users where email = 'psierra@br-innovation.com' limit 1;
  if v_admin_uid is null then
    raise notice 'Admin user psierra@br-innovation.com no existe aún en auth.users — crear vía Supabase Studio antes de re-correr este seed.';
    return;
  end if;
  select id into v_role_id from public.roles where code = 'ti_integracion';

  insert into public.profiles (id, email, full_name, role_id, is_active, locale)
  values (v_admin_uid, 'psierra@br-innovation.com', 'Pablo Sierra', v_role_id, true, 'es')
  on conflict (id) do update
    set role_id = excluded.role_id,
        full_name = excluded.full_name,
        is_active = true,
        updated_at = now();

  insert into public.user_role_audit (user_id, role_id, action, actor_id, note)
  values (v_admin_uid, v_role_id, 'granted', v_admin_uid, 'Seed inicial: bootstrap admin');
end $$;
```

### Run-book de bootstrap

1. Aplicar migración estructural (`20260506_120000_users_module.sql`).
2. Crear `psierra@br-innovation.com` en Supabase Studio (`Authentication → Users → Invite`).
3. Aplicar seed (`20260506_130000_users_seed.sql`).
4. Verificar JWT: `select raw_app_meta_data from auth.users where email = 'psierra@br-innovation.com'` debe contener `role: ti_integracion` y `permissions: [...]`.
5. Pablo hace login → llega a `/admin/users` y crea los demás usuarios desde la UI.

---

## Dependencias y orden de implementación

| Sprint | Historia | Patrón hppt origen |
|--------|----------|--------------------|
| Sprint 1 | EP-1A-01: Bootstrap auth (backend `core/auth.py` + frontend middleware + AuthProvider) | hppt:`app/core/auth.py`, `src/utils/supabase/*`, `src/auth-module/*` |
| Sprint 1 | EP-1A-02: Migraciones módulo usuarios (5 tablas + triggers + RLS) | hppt:`supabase/migrations` (esquema implícito via Studio) |
| Sprint 1 | EP-1A-03: Endpoints `/me`, `/users` CRUD básico + Server Actions | hppt:`src/actions/admin-actions.ts`, `app/routers/admin.py` |
| Sprint 1 | EP-1A-04: UI `/login` (magic link + password fallback) + `/account` | hppt:`src/app/(auth)/login/`, `(dashboard)/profile/` |
| Sprint 2 | EP-1A-05: UI `/admin/users` + `RbacGuard` + `<UsersTable>` | hppt:`src/app/(dashboard)/admin/users/`, `components/admin/RolesTable.tsx` |
| Sprint 2 | EP-1A-06: Seed roles + permisos + primer admin | nuevo |
| Sprint 2 | EP-1A-07: RLS policies para tablas de dominio Fase 1 (`products`, `costs`, `prices`) | hppt:no equivalente directo — diseño nuevo MT |

## Notas finales

- **Single-tenant** (ADR-014): no hay `org_id` en tablas — simplifica RLS dramáticamente.
- **i18n** (ADR-004): `profiles.locale` ya provisto.
- **Auditoría**: cada cambio de rol → `user_role_audit`. Cambios en `profiles` se loggean a `audit_events` (módulo audit, separado).
- **Fase 1 NO incluye**: SSO/SAML, MFA por TOTP (Supabase soporta MFA nativa pero la encendemos Fase 2 cuando haya usuarios externos), self-signup.
- **Lag de revocación (decidido v1.1)**: forzamos `supabase.auth.admin.sign_out(user_id)` al revocar/cambiar rol para minimizar el lag de propagación del JWT (ver F-USR-03). Cierra el TODO previo del "lag de 1h".
