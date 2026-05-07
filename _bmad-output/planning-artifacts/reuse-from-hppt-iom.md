---
title: "Reuso de patrones desde hppt-iom — Inventario y catálogo"
status: "draft"
version: "1.1"
created: "2026-05-06"
updated: "2026-05-06"
project_name: "mt-pricing-mdm-phase1"
related: ["architecture-mt-pricing-mdm-phase1.md", "prd-mt-pricing-mdm-phase1.md", "epics-and-stories-mt-pricing-mdm-phase1.md"]
reference_project: "br-hppt/br-hppt-iom-review_1/Hppt-dashboard"
changelog:
  - "1.0 (2026-05-06): versión inicial, recomendación 'sin ORM, idem hppt' y 'solo Celery beat estático'."
  - "1.1 (2026-05-06): MT diverge consciemente en dos puntos (ADR-045 + ADR-046). Persistencia: hppt no usa SQLAlchemy → MT introduce SQLAlchemy 2.0 async para core data y mantiene supabase-py SOLO para Auth/Storage. Scheduler: hppt mezcla APScheduler + Celery → MT usa Celery Beat con DatabaseScheduler editable. Tabla §4 actualizada: patrón #18 (APScheduler) y #20 (job_definitions UI scheduler) ahora son **adoptados parcialmente** en Fase 1, no diferidos a Fase 2."
---

# Reuso de patrones desde hppt-iom (Tasks 1-4)

> **Objetivo.** Identificar patrones probados en `hppt-iom` (BR Innovation, en producción) y catalogarlos por valor de reuso para el nuevo proyecto MT Pricing/MDM. Evitar reinventar el bootstrap de stack y enfocar Fase 1 en lógica de negocio.
>
> **Stack idéntico confirmado**: Next.js 16 + React 19 (frontend), FastAPI Python 3.11 (backend), Supabase (Postgres + Auth + Storage + RLS + pgvector + uuidv7), Celery 5.3 + Redis 7 (jobs), Hetzner + Docker Compose + Caddy (deploy).

---

## Task 1 — Inventario estructural del backend hppt-iom

### Top-level (`hppt-iom-backend/`)

| Path | Propósito |
|------|-----------|
| `Dockerfile` | Imagen Python 3.11-slim con usuario no-root, gunicorn + UvicornWorker, healthcheck via `/health`. Reusable directo. |
| `requirements.txt` | FastAPI 0.115, supabase-py >=2.13, pydantic 2.10, pydantic-settings 2.6, celery 5.3.6, redis 5.0.3, apscheduler 3.10.4, gunicorn 21.2, httpx 0.28. |
| `requirements-dev.txt` | Pytest + dev tooling. |
| `pytest.ini` + `conftest.py` | Configuración tests integración. |
| `.env` / `.env.example` (raíz) | Plantilla de variables; ver `c:/BR-Github/br-hppt/br-hppt-iom-review_1/Hppt-dashboard/.env.example`. |
| `migrations/` | 3 SQL fuera de Supabase (legado). |
| `scripts/` | Utilitarios ETL, seeds, inspección de schema. |

### `app/` (3 niveles)

```
app/
├── main.py                       # FastAPI bootstrap + lifespan + middleware + router include
├── database.py                   # Singleton supabase client (sync, service-role)
├── celery_config.py              # Celery settings (broker, beat schedule)
├── worker.py                     # @celery_app.task definitions (3+ tasks)
├── core/
│   ├── auth.py                   # get_current_user + require_permissions (Supabase JWT)
│   ├── config.py                 # Pydantic Settings + production secret validator
│   ├── http_bearer_unauthorized.py  # 401-friendly HTTPBearer
│   ├── logger.py                 # log_event() → tabla system_logs
│   ├── middleware.py             # RequestContext + Logging + SecurityHeaders + DynamicCORS
│   ├── origin_guard.py           # CSRF defense in depth (Origin allowlist)
│   ├── rate_limit.py             # In-memory rate limit
│   ├── redis_rate_limit.py       # Redis-backed rate limit
│   ├── scheduler.py              # APScheduler + JOB_REGISTRY + circuit breaker + auto-heal
│   ├── security.py               # encrypt_text / decrypt_text (Fernet)
│   ├── orchestrator.py           # Orquestación pipelines AI
│   ├── privacy.py                # PII masking
│   ├── llm_logger.py             # Audit de llamadas LLM
│   ├── request_context.py        # request_id contextvar
│   └── task_registry.py          # Registry tasks Celery por nombre
├── data/
├── models/                       # Pydantic models (no SQLAlchemy)
│   ├── domain.py                 # Tipos compartidos
│   ├── business_partners.py
│   ├── cases.py
│   ├── control_tower.py
│   ├── kpi.py
│   ├── kpi_admin.py
│   ├── margin_policies.py
│   └── tracker_import.py
├── routers/                      # ~50 routers REST por módulo
│   ├── admin.py                  # /api/admin/* (users, integraciones, settings)
│   ├── admin_jobs.py             # /api/admin/jobs (status, history, run_now)
│   ├── pricing.py                # /api/pricing (cost+margin, propose, approval)
│   ├── kpi.py / kpi_admin.py     # Dashboards
│   ├── observability.py          # Sink logs FE
│   └── … (rfq, mirs, cases, contracts, products, …)
└── services/                     # Lógica de negocio
    ├── tracker_import_service.py # ETL pipeline 9 fases
    ├── pricing_engine.py         # Cost+margin
    ├── notifications.py          # Email outbox
    ├── kpi_metric_engine.py      # Compute métricas
    ├── kpi_alerting.py           # Eval alertas
    ├── kpi_report_sender.py      # Digest emails
    ├── advisors/                 # Briefings LLM
    ├── ai_agents/                # Email triage, master_data, products
    ├── graph/                    # Neo4j sync (ontology, taxonomy, CDC)
    ├── storage.py                # Supabase Storage helpers
    ├── embeddings.py             # pgvector
    └── … (~50 services)
```

### `hppt-iom-frontend/src/`

```
src/
├── app/
│   ├── (auth)/                  # Login, register, forgot/update password
│   ├── (dashboard)/             # ~25 sub-rutas autenticadas
│   ├── api/                     # API routes Next 16
│   ├── auth/callback/           # OAuth + magic link callback
│   ├── layout.tsx               # AuthProvider + Theme + Toaster
│   ├── global-error.tsx
│   └── not-found.tsx
├── auth-module/                 # AuthProvider + useAuth + RegisterForm
├── components/                  # ~30 grupos por módulo (admin, kpi, rfq, …)
├── hooks/                       # usePermissions, useApiClient, useEditMode, …
├── lib/                         # auth-events, auth-session-cookie, rate-limit, errors, …
├── utils/supabase/              # client.ts (browser), server.ts (RSC), update-session.ts (middleware), admin.ts (service-role)
├── actions/                     # Server Actions (admin-actions, admin-roles-actions, …)
├── repositories/                # Acceso a tabla → DTO
├── services/                    # Cliente API
├── types/                       # database.types.ts (autogen Supabase), rbac.types.ts
├── middleware.ts                # HTTPS upgrade + rate-limit + updateSession
└── config/                      # Constantes
```

### Configuración / deploy raíz

- `docker-compose.yml` (dev): frontend, backend, redis (healthcheck), celery-worker (healthcheck `celery inspect ping`), neo4j.
- `docker-compose.prod.yml`: añade caddy + celery-beat (PersistentScheduler).
- `Caddyfile`: reverse-proxy `/api/*` → backend, resto → frontend, TLS Let's Encrypt HTTP-01.
- `supabase/migrations/`: SQL versionado (proyecto cuenta también con migraciones gestionadas por la consola Supabase, no todas se commitean).

---

## Task 2 — Deep dive: módulo de usuarios

### Diferencia clave de stack: hppt-iom NO usa SQLAlchemy → **MT diverge consciemente (ADR-045)**

`hppt-iom-backend` **no usa SQLAlchemy ni Alembic**. Toda persistencia va vía `supabase-py` (cliente PostgREST) con la tabla `profiles` (que extiende `auth.users` de Supabase). `app/models/` contiene únicamente Pydantic models de dominio, no ORM.

**Decisión MT (ADR-045, divergencia consciente del 2026-05-06).** MT introduce **SQLAlchemy 2.0 async + Alembic** para el **core data** (products, prices, costs, audit_events, job_definitions, …) por la complejidad del motor de pricing, comparador, audit analytics e importer (joins multi-tabla, transacciones con savepoints, queries con CTEs). Mantiene **supabase-py SOLO para Auth y Storage** (reuso 1:1 del patrón hppt-iom donde aporta valor: identidad/sesión/JWT/buckets). El backend usa **dos clientes** coordinados (`app/core/db.py` SQLAlchemy + `app/core/supabase.py` supabase-py). El módulo de usuarios MT migra al esquema con SQLAlchemy ORM (ver `mt-users-module-design.md` v1.1) y la integración con `auth.users` se reduce a un trigger de bootstrap + endpoints admin que llaman `supabase.auth.admin.*`. Trade-off aceptado: el equipo post-handoff debe manejar SQLAlchemy 2.0 async además de supabase-py; ROI es código tipado para el motor de pricing y queries complejas del comparador.

### Modelo de datos (Supabase, según uso real)

- `auth.users` (Supabase nativa) — fuente de verdad de identidad: `id` UUID, `email`, `app_metadata`, `user_metadata`, `banned_until`, `last_sign_in_at`.
- `profiles` (aplicativa) — extiende auth.users: `id` (FK 1:1 a auth.users), `full_name`, `avatar_url`, `email`, `is_active`, `role_id` (FK a `roles`), `updated_at`.
- `roles` — `id` UUID, `name`, `description`, `is_custom` boolean, `created_at`.
- `permissions` — `id` (string ej. `admin:users:manage`), `description`, `module`.
- `role_permissions` — `role_id` FK + `permission_id` FK (M:N).

Las migraciones Supabase del repo no incluyen RLS de roles porque el módulo lo administra Supabase Studio + un trigger que copia `role_id` y `permissions` a `auth.users.app_metadata` para que estén firmadas dentro del JWT.

### Backend: validación JWT y RBAC

**Path**: `hppt-iom-backend/app/core/auth.py:14-144`

```python
async def _resolve_current_user(credentials):
    token = credentials.credentials
    supabase = get_supabase_client()
    user_response = supabase.auth.get_user(token)        # valida JWT contra Supabase Auth
    if not user_response or not user_response.user:
        raise HTTPException(401, "Invalid or expired token")
    user = user_response.user
    app_meta  = getattr(user, "app_metadata", None) or {}
    role      = app_meta.get("role", "")
    raw_permissions = app_meta.get("permissions", [])

    # Fallback: si app_metadata.role está vacío, leer profiles.roles(name)
    if not role:
        profile_resp = supabase.table("profiles").select("roles(name)").eq("id", user.id).single().execute()
        role = (profile_resp.data or {}).get("roles", {}).get("name", "client")
    # Admin → permission set completo (override)
    if role in ADMIN_ROLES: permissions = ADMIN_PERMISSIONS
    else: permissions = raw_permissions
    return {"id": user.id, "email": user.email, "role": role, "permissions": permissions}

def require_permissions(required_permissions: list[str], match_logic: str = "all"):
    async def permission_dependency(user: dict = Depends(get_current_user)):
        if match_logic == "all":  has = all(p in user["permissions"] for p in required_permissions)
        elif match_logic == "any": has = any(p in user["permissions"] for p in required_permissions)
        if not has: raise HTTPException(403, "Insufficient permissions")
        return user
    return permission_dependency
```

**Propósito.** Una sola función `Depends(get_current_user)` valida el JWT firmado por Supabase contra `auth.users` (network call por cada request — alto coste, candidato a cachear con jose+JWKS local). Una *factory* `require_permissions([...])` aplica gating fino. Patrón limpio para reusar tal cual en MT.

### Frontend: middleware + AuthProvider + permisos

**Middleware** (`hppt-iom-frontend/src/middleware.ts:21-44` y `src/utils/supabase/update-session.ts:9-121`):

```ts
// update-session.ts (núcleo)
const supabase = createServerClient(NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, { cookies: { getAll(), setAll() } });
const { data: { user } } = await supabase.auth.getUser();

const isAuthRoute = ["/login","/register","/forgot-password","/update-password"].some(p => pathname.startsWith(p));
const isPublicPath = isAuthRoute || pathname.startsWith("/api/") || pathname.startsWith("/auth/callback");

// Sliding inactivity: cookie last_activity con TTL configurable
if (user && !isAuthRoute) {
  const last = parseInt(request.cookies.get(AUTH_LAST_ACTIVITY_COOKIE_NAME)?.value);
  if (Date.now() - last > idleMinutes * 60 * 1000) {
    await supabase.auth.signOut();
    return NextResponse.redirect(new URL("/login?reason=idle", request.url));
  }
}
if (!user && !isPublicPath) return NextResponse.redirect(new URL("/login", request.url));

// First-login enforcement: requires_password_reset flag → forzar /update-password
if (user?.user_metadata?.requires_password_reset === true && !pathname.startsWith("/update-password"))
  return NextResponse.redirect(new URL("/update-password?reason=first-login", request.url));
```

**AuthProvider** (`src/auth-module/AuthProvider.tsx:25-103`): contexto React con cross-tab sync vía `BroadcastChannel`. `onAuthStateChange` actualiza state; `SIGNED_OUT` se difunde a otras pestañas para forzar logout sincronizado.

**Hook de permisos** (`src/hooks/usePermissions.ts:11-58`): lee `session.user.app_metadata.permissions` y expone `hasPermission`, `hasAnyPermission`, `hasAllPermissions`. JWT contiene los permisos firmados → no hay round-trip.

**Server Actions admin** (`src/actions/admin-actions.ts:65-143`):

```ts
export const getUsers = withPermissionAuth(["admin:users:read"], async (): Promise<UserInfo[]> => {
  const supabase = createRawAdminClient();   // service-role
  const [usersRes, rolesRes] = await Promise.all([
    supabase.auth.admin.listUsers({ perPage: 1000 }),
    supabase.from("roles").select("id, name"),
  ]);
  const roleMap = new Map(rolesRes.data.map(r => [r.id, r.name]));
  return usersRes.data.users.map(u => ({
    id: u.id, email: u.email, full_name: u.user_metadata?.full_name,
    role_id: u.app_metadata?.role_id, role_name: roleMap.get(u.app_metadata?.role_id),
    is_banned: !!u.banned_until,
  }));
});
```

**Páginas** detectadas:

- `src/app/(auth)/login/page.tsx` — login email+password con localStorage-based brute-force protection.
- `src/app/(auth)/register/` — register form (Fase actual: registro abierto; en MT estará deshabilitado).
- `src/app/(auth)/forgot-password/` y `update-password/`.
- `src/app/(dashboard)/admin/users/page.tsx` — gestión usuarios + bulk-invite (usa Gemini para parsear texto libre).
- `src/app/(dashboard)/profile/` — perfil propio.

### Flujos detectados

| Flujo | Implementación |
|-------|----------------|
| **Signup** | `useAuth.signUp(email, password, firstName, lastName)` → `supabase.auth.signUp` con `user_metadata.full_name`. |
| **Login** | `useAuth.signIn(email, password)`. OAuth Google soportado. |
| **Password reset** | `useAuth.sendPasswordResetEmail` + `redirectTo=/update-password`. |
| **First-login forced rotation** | Admin crea usuario con flag `requires_password_reset=true` en `user_metadata`. Middleware bloquea acceso hasta rotar. |
| **Bulk invite** | `parseBulkUsers` (Gemini) extrae name+email+role_hint de texto pegado, luego `createUser` 1×1. |
| **Logout** | `signOut({ scope: "local" })` o `"global"` (revoca refresh token). BroadcastChannel propaga a otras pestañas. |
| **Cross-tab logout** | `BroadcastChannel("hppt-auth")` + custom event `session-stale`. |
| **Sliding session** | Cookie `auth-last-activity` actualizada en cada request, expiry idle config en BD `system_settings.idle_timeout_minutes`. |

---

## Task 3 — Deep dive: módulo de jobs (Celery + APScheduler)

### Hallazgo clave: HÍBRIDO Celery + APScheduler

`hppt-iom` **usa los dos sistemas en paralelo, con responsabilidades distintas**:

- **Celery** (`app/worker.py` + `app/celery_config.py`): tasks pesadas / largas / fan-out (tracker_import 1.5h, homologation 6h, RFQ extraction LLM, KPI digest). Beat-schedule corto (2 jobs).
- **APScheduler** (`app/core/scheduler.py`): jobs internos del API process — email polling, MIR auto-chase, contract lifecycle tick, KPI alerts, advisors. Configurables vía tabla `job_definitions` + UI `/admin/scheduler`.

Esta dualidad permite: (a) APScheduler corre **dentro** del proceso FastAPI con file-lock para que sólo un worker gunicorn ejecute → simple, sin infra extra; (b) Celery se reserva para tasks que necesitan CPU/IO largo o paralelismo. En MT recomendamos consolidar todo a Celery beat para simplicidad operativa (ver Task 4).

### Configuración Celery

**Path**: `hppt-iom-backend/app/celery_config.py:1-39`

```python
class CeleryConfig:
    broker_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    result_backend = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    task_serializer = "json"
    result_serializer = "json"
    accept_content = ["json"]
    result_expires = 3600
    broker_connection_retry_on_startup = True
    beat_schedule = {
        "kpi-alert-evaluation": {
            "task": "evaluate_kpi_alerts_task",
            "schedule": crontab(minute="*/15"),
            "options": {"expires": 60 * 14},
        },
        "kpi-weekly-digest": {
            "task": "kpi_weekly_digest_task",
            "schedule": crontab(hour=8, minute=0, day_of_week=1),
            "options": {"expires": 3600},
        },
    }
    beat_scheduler = "celery.beat:PersistentScheduler"
```

**Observaciones**:
- No hay queues nombradas — todas las tasks corren en `default`. **MT debe extender** con queues por dominio (imports, pricing, images, comparator, notifications, audit).
- No hay task routing.
- Backend de resultados es Redis (no postgres).

### Patrón de tasks (representativo)

**Path**: `hppt-iom-backend/app/worker.py:20-126` (tracker_import_task):

```python
@celery_app.task(
    name="tracker_import_task",
    bind=True,
    max_retries=2,
    soft_time_limit=60 * 60,        # 1h alerta
    time_limit=60 * 90,             # 1.5h hard kill
    acks_late=True,                 # re-encolar si worker muere
    reject_on_worker_lost=True,
)
def tracker_import_task(self, file_bytes_b64: str, run_id: str, ...):
    file_bytes = base64.b64decode(file_bytes_b64)
    from app.services.tracker_import_service import tracker_import_service
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(
            tracker_import_service.run_import(file_bytes=file_bytes, run_id=run_id, ...)
        )
        return f"SUCCESS run_id={run_id}"
    except Exception as e:
        try: raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        except self.MaxRetriesExceededError: return f"FAILURE max retries"
    finally:
        # Idempotente: snapshot de reconciliación (UPSERT por run_id)
        get_supabase_client().rpc("tracker_import_refresh_snapshot", {"p_run_id": run_id}).execute()
        loop.close()
```

**Patrones extraídos**:
1. `bind=True` para acceso a `self.retry()`.
2. `acks_late + reject_on_worker_lost` → at-least-once + supervivencia a OOM.
3. `soft_time_limit + time_limit` separados (alerta vs kill).
4. `name="…"` explícito (rutea por nombre, no por path import).
5. **State persistido en DB** (`job_run_history` + `processing_status` JSONB) — el cliente pollea, no escucha el broker.
6. **Backoff manual** con `self.retry(countdown=...)` (no `retry_backoff=True`).
7. `acks_late + asyncio.new_event_loop()` por task — workers Celery son sync, así que cada task crea su loop para llamar servicios async.
8. **Idempotency en `finally`**: aún en FAILURE, refresca snapshot. RPC es UPSERT.

### APScheduler — patrón complementario

**Path**: `hppt-iom-backend/app/core/scheduler.py:97-484`

Características destacables:

```python
JOB_REGISTRY = {
    'EMAIL_POLLER_PRIMARY': email_monitor_service.run_email_poll,
    'MIR_AUTO_CHASE': mir_service.run_mir_auto_chase,
    'CONTRACT_LIFECYCLE_TICK': contract_service.run_lifecycle_tick,
    'KPI_ALERTS_EVALUATE': alerting_service.evaluate_all_active,
    'KPI_REPORTS_DISPATCH': kpi_report_sender.dispatch_due_reports,
    'ADVISOR_CUSTOMER_RUN': _advisor_run_customer,
    # …12 jobs
}

async def job_wrapper(job_id, func, *args):
    # 1. Stale-RUNNING guard (auto-heal jobs en RUNNING > 15min de un crash)
    # 2. Insert job_run_history(status=RUNNING)
    # 3. Retry loop (3 attempts, exponential backoff 1s/2s/4s)
    # 4. Circuit breaker: 4 fallas seguidas → marca job_definitions.is_active=False y remove_job
    # 5. Update job_run_history con status final + duration_ms + items_processed
```

Y en `app/main.py:22-56` un **file-lock por gunicorn**:

```python
@asynccontextmanager
async def lifespan(app):
    _lock_fd = open("/tmp/.scheduler.lock", "w")
    try:
        fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        start_scheduler()           # solo un worker entra
    except BlockingIOError:
        logging.info("scheduler lock held — skipping")
    yield
```

**Propósito.** Evita N×duplicación de jobs cuando gunicorn arranca 4 workers. **Anti-pattern moderado**: en MT, con Celery beat, este file-lock no se necesita.

### Routing de tasks por queue

**No existente** en hppt-iom. Todas las tasks van a la queue `default`. **MT debe diseñarlo desde cero**.

### Healthchecks

**Path**: `hppt-iom-backend/docker-compose.yml:88-93`

```yaml
celery-worker:
  healthcheck:
    test: ["CMD", "celery", "-A", "app.worker.celery_app", "inspect", "ping", "--timeout", "10"]
    interval: 30s
    timeout: 15s
    retries: 3
```

**En prod** (`docker-compose.prod.yml:64-65`):

```yaml
celery-worker:
  healthcheck:
    disable: true     # Comentario: el inspect ping se cuelga bajo carga, deshabilitado
```

**Nota.** Hay regresión de fiabilidad — en prod el healthcheck está disabled. **MT debería usar un endpoint `/health/celery` en backend que envía `inspect ping` en background con timeout estricto** (mejor que el healthcheck nativo).

### Logging y observabilidad

- `app/core/logger.py` con `log_event(level, module, message, metadata)` → tabla `system_logs` (Supabase).
- No hay Sentry integrado en backend.
- No hay Prometheus exporter.
- No hay structlog ni loguru — `logging.getLogger(__name__)` estándar.
- Frontend tiene sink a `/api/observability` que escribe a `system_logs`.

**Para MT**: sumar Sentry SDK Python + structlog/loguru (ADR-019 ya lo prevé).

### Tests de tasks

No se observa configuración `CELERY_TASK_ALWAYS_EAGER` ni mocks de Redis en `tests/`. Las pruebas de Celery son end-to-end vía `docker compose` o se omiten. **MT debe instaurar tests con eager mode**.

### Docker Compose servicios

```yaml
# docker-compose.yml (dev)
redis:        image: redis:alpine; healthcheck: redis-cli ping
celery-worker: command: celery -A app.worker.celery_app worker --loglevel=info
              healthcheck: celery inspect ping
backend:      depends_on: [redis: service_healthy, neo4j: service_healthy]

# docker-compose.prod.yml
celery-beat:  command: celery -A app.worker.celery_app beat --loglevel=info --scheduler celery.beat:PersistentScheduler
              depends_on: [backend, redis, celery-worker]
```

**Falta** en hppt-iom: queues múltiples, prioridad, autoscaling, Flower (dashboard Celery).

---

## Task 4 — Inventario de patrones reusables

### Tabla maestra (ordenada por valor)

| # | Patrón | Path origen | Reusabilidad | Adaptación necesaria | Dónde aplicarlo en MT | SP estimados ahorrados |
|---|--------|-------------|--------------|----------------------|------------------------|------------------------|
| 1 | **Auth dependency `get_current_user` + `require_permissions`** | `hppt-iom-backend/app/core/auth.py` | Alta | Cambiar permisos a vocabulario MT (`pricing:approve`, `costing:read`, …). Agregar caché JWKS local opcional. | `mt-pricing-backend/app/core/auth.py` | 5 |
| 2 | **Middleware Next.js `updateSession` + sliding idle + first-login enforcement** | `hppt-iom-frontend/src/utils/supabase/update-session.ts` + `src/middleware.ts` | Alta | Mantener idéntico; ajustar lista `authRoutes`. | `mt-pricing-frontend/src/utils/supabase/update-session.ts` | 5 |
| 3 | **AuthProvider con cross-tab sync (BroadcastChannel)** | `hppt-iom-frontend/src/auth-module/AuthProvider.tsx` | Alta | Mínima — renombrar canal `mt-auth`. | `mt-pricing-frontend/src/auth-module/` | 3 |
| 4 | **Hook `usePermissions` con permisos del JWT** | `hppt-iom-frontend/src/hooks/usePermissions.ts` | Alta | Importar `PermissionId` MT. | `mt-pricing-frontend/src/hooks/usePermissions.ts` | 2 |
| 5 | **Celery worker setup + tasks con `acks_late + soft/hard time_limit`** | `hppt-iom-backend/app/worker.py`, `app/celery_config.py` | Alta | Añadir queues nombradas + routing por dominio. | `mt-pricing-backend/app/worker.py` y `app/celery_config.py` | 8 |
| 6 | **`job_run_history` + estado polleable por cliente (idempotency en `finally`)** | `app/worker.py` (tracker_import_task) y `app/core/scheduler.py` | Alta | Usar tabla `job_runs` MT con misma forma. | Backend `mt-pricing-backend` (tabla + servicio status) | 5 |
| 7 | **Configuración Pydantic Settings con validador en producción** | `hppt-iom-backend/app/core/config.py` | Alta | Adaptar variables a MT (URLs, bucket names, FX provider, …). | `mt-pricing-backend/app/core/config.py` | 2 |
| 8 | **Server Actions con `withPermissionAuth([...])`** | `hppt-iom-frontend/src/lib/auth/permission-guard.ts` + `src/actions/*` | Alta | Adoptar HOF tal cual. | `mt-pricing-frontend/src/actions/*.ts` | 3 |
| 9 | **Admin Users management UI (tabla + dialog + bulk invite)** | `src/app/(dashboard)/admin/users/` + `src/components/admin/RolesTable.tsx` | Media | Reusar componentes shadcn; sustituir Gemini bulk-parse por entrada manual o usar mismo Gemini. | `mt-pricing-frontend/src/app/(dashboard)/admin/users/` | 5 |
| 10 | **`createRawAdminClient` (service-role) para Server Actions de admin** | `src/utils/supabase/admin.ts` | Alta | Mínima. | `mt-pricing-frontend/src/utils/supabase/admin.ts` | 1 |
| 11 | **Dockerfile Python 3.11-slim + non-root user + healthcheck + gunicorn UvicornWorker** | `hppt-iom-backend/Dockerfile` | Alta | Cambiar `--timeout 900` (largos imports) a 300 si MT no necesita; adaptar puertos. | `mt-pricing-backend/Dockerfile` | 2 |
| 12 | **`docker-compose.yml` (dev) con healthchecks de redis + backend + celery + Caddy en prod** | `docker-compose.yml` + `docker-compose.prod.yml` | Alta | Añadir servicios: celery-beat (siempre), separar workers por queue (worker-imports, worker-pricing). Quitar Neo4j (Fase 1.5). | Raíz `br-mt-ecommerce/` | 5 |
| 13 | **Caddyfile reverse-proxy + Let's Encrypt HTTP-01** | `Caddyfile` | Alta | Cambiar hostname a `mt.br-innovation.com` o el que MT defina. | Raíz `br-mt-ecommerce/Caddyfile` | 1 |
| 14 | **`log_event` async → tabla `system_logs` con `metadata JSONB`** | `app/core/logger.py` | Alta | Sumar Sentry SDK Python en paralelo (ADR-019). | `mt-pricing-backend/app/core/logger.py` + tabla `system_logs` Supabase | 2 |
| 15 | **Middleware FastAPI: RequestContext + Logging + SecurityHeaders + DynamicCORS + OriginGuard** | `app/core/middleware.py`, `app/core/origin_guard.py`, `app/core/request_context.py` | Alta | Mínima; ajustar headers. | `mt-pricing-backend/app/core/middleware.py` | 3 |
| 16 | **Rate limiting Redis** | `app/core/redis_rate_limit.py` | Alta | Reutilizar; aplicar a endpoints sensibles (login, exports). | `mt-pricing-backend/app/core/redis_rate_limit.py` | 2 |
| 17 | **`encrypt_text/decrypt_text` (Fernet) para credenciales en BD** | `app/core/security.py` | Alta | Mínima; ENV `ENCRYPTION_KEY`. | Útil para guardar API keys de e-commerce, FX, comparator vendors | 2 |
| 18 | **APScheduler con `JOB_REGISTRY` + circuit-breaker + auto-heal stale RUNNING** | `app/core/scheduler.py` | Media | **No reusamos APScheduler como tal** (MT usa Celery Beat con DatabaseScheduler — ADR-046). El circuit-breaker pattern + auto-heal stale RUNNING SÍ se replican: el scheduler custom (~150 líneas) en `app/scheduler/database_scheduler.py` los implementa sobre `celery_app.send_task`. | `mt-pricing-backend/app/scheduler/database_scheduler.py` | 3 |
| 19 | **`global-error.tsx` + `not-found.tsx` + `error.tsx` por sub-ruta** | `src/app/global-error.tsx`, `src/app/not-found.tsx`, `src/app/(dashboard)/admin/error.tsx` | Alta | Mínima. | `mt-pricing-frontend/src/app/*` | 1 |
| 20 | **Tabla `job_definitions` (UI scheduler editable)** | `app/core/scheduler.py:load_jobs_from_db()` | **Alta** | **Adoptado en Fase 1 (ADR-046)**, no diferido. MT usa Celery Beat + DatabaseScheduler que lee `public.job_definitions`. Reusamos: estructura conceptual de la tabla, polling pattern, persistencia de `last_run_at`/`next_run_at`. Adaptamos: tipos enum, RLS por owner business/infra, audit trigger, integración con SQLAlchemy 2.0 async. | `mt-pricing-backend/app/db/models/job_definition.py` + `app/scheduler/database_scheduler.py` + UI `/admin/jobs` (EP-1A-08) | 5 |
| 21 | **Observability sink frontend → backend `/api/observability`** | `app/routers/observability.py` + frontend logger client | Alta | Mínima. | Útil para detectar JS errors prod | 2 |
| 22 | **Drift baseline JSON (`drift-baseline.json`) + script `check-drift.mjs`** | `hppt-iom-frontend/drift-baseline.json` + `scripts/check-drift.mjs` | Media | Adoptar para detectar desincronización schema BD vs `database.types.ts`. | Frontend MT | 2 |
| 23 | **Lifespan `asynccontextmanager` con file-lock single-leader (gunicorn)** | `app/main.py:22-56` | Baja | NO reusar si vamos a Celery beat puro. | — | 0 |
| 24 | **Patrón `processing_status` JSONB para steps largos (tracker)** | `app/services/tracker_import_service.py` (escrituras a `job_run_history.processing_status`) | Alta | Reusar para imports MT (PIM, costos, comparator) — el cliente puede mostrar progreso fase por fase. | `mt-pricing-backend/app/services/imports/*` | 3 |
| 25 | **HTTP-only `auth-last-activity` cookie + sliding TTL configurable** | `src/lib/auth-session-cookie.ts` + `update-session.ts` | Alta | Mínima. | `mt-pricing-frontend` | 1 |
| 26 | **Server-side `requires_password_reset` flag → first-login forced rotation** | `update-session.ts:97-101` + `useAuth.updatePassword` | Alta | Mínima. | `mt-pricing-frontend` | 2 |
| 27 | **`HTTPBearerUnauthorized` (devuelve 401 en lugar de 403 al faltar bearer)** | `app/core/http_bearer_unauthorized.py` | Alta | Mínima. | `mt-pricing-backend/app/core/` | 1 |
| 28 | **Estructura monorepo: `<service>-backend/`, `<service>-frontend/`, `supabase/`, `docker-compose*.yml`, `Caddyfile` raíz** | Raíz `Hppt-dashboard/` | Alta | Espejo. | Raíz `br-mt-ecommerce/` | — (estructural) |

### Score total

- **Patrones identificados:** 28 (mínimo solicitado: 15).
- **Suma SP estimados ahorrados:** ~73 SP (vs construcción desde cero).

### Diferencias de stack detectadas (alertas a documentar)

| Tema | hppt-iom | Decisión MT (architecture-mt) | Acción |
|------|----------|------------------------------|--------|
| ORM | **Ninguno** — `supabase-py` directo (sync) | **Diverge (ADR-045)**: SQLAlchemy 2.0 async + Alembic para core data; supabase-py solo para Auth/Storage/admin | **Resuelto v1.1**: persistencia híbrida adoptada. ADR-045 documenta el patrón de dos clientes (`app/core/db.py` + `app/core/supabase.py`). El módulo de usuarios MT (v1.1) migra a SQLAlchemy ORM. |
| Async ORM/DB | Sync (supabase-py) + asyncio puntual en services | SQLAlchemy 2.0 async + asyncpg driver | **Resuelto v1.1**: backend usa `AsyncSession` por request (`Depends(get_session)`); supabase-py sync queda solo en endpoints admin (auth.admin.*) corriendo bajo `run_in_threadpool` cuando se necesita. |
| Migrations | Mezcla SQL versionada + Supabase Studio | Alembic (`public.*`) + Supabase migrations (`auth.*`/`storage.*`/RLS) | **Resuelto v1.1 (ADR-045 §8.0.4)**: split por schema. Alembic para tablas aplicativas; Supabase migrations para schemas Auth/Storage y RLS críticas. |
| Cola jobs | Celery + APScheduler | ADR-030 vigente: Celery+Redis | OK. ADR-018 (BullMQ) marcado superseded por ADR-030. |
| Beat scheduler | Celery beat + APScheduler dual | **Diverge (ADR-046)**: Celery Beat con DatabaseScheduler editable (tabla `job_definitions`) | **Resuelto v1.1**: MT consolida en Celery Beat pero adopta el patrón hppt de schedules en BD (no estáticos en código). UI admin `/admin/jobs` permite ajustar horarios sin redeploy. |
| Logging | `logging` stdlib + `system_logs` BD | ADR-019 prevé Sentry + structlog | Sumar Sentry y structlog en MT desde día 1 (no esperar a tener problemas como en hppt). |
| Tests Celery | No tests integrados (solo e2e docker) | — | MT: instaurar `task_always_eager=True` en pytest fixtures. |
| Healthcheck Celery | `celery inspect ping` (disabled en prod) | — | MT: endpoint `/health/celery` propio + `flower` opcional. |
| Neo4j | Sí (Fase 1) | Fase 1.5 (ADR-037) | Quitar Neo4j de docker-compose Fase 1; añadir en 1.5. |
| Frontend Next.js | 16 + React 19 + `@supabase/ssr` 0.8 | Idem | OK alineado. |
| Backend Python | 3.11 + FastAPI 0.115 | Idem | OK. |

### TODOs / dudas que dejo abiertos para validación humana

1. ~~**¿MT usa SQLAlchemy o supabase-py directo en backend?**~~ **Resuelto v1.1 (ADR-045)**: persistencia híbrida — SQLAlchemy 2.0 async para core data + supabase-py para Auth/Storage/admin. Sujeto a firma TI MT en S0.
2. ~~**¿Beat scheduler puro Celery o seguir el modelo dual APScheduler+Celery?**~~ **Resuelto v1.1 (ADR-046)**: Celery Beat con DatabaseScheduler editable — recoge lo mejor de ambos (uniformidad de Celery + editabilidad de la tabla `job_definitions` de hppt). Sujeto a firma TI MT en S0.
3. **¿Migrar la lógica `requires_password_reset` con flag en `user_metadata` o usar Supabase Magic Link directo (sin password inicial)?** El docvento maestro MT prioriza magic link como método primario; hppt asume password-first.

---

## Top 5 patrones más valiosos

| # | Patrón | SP ahorrados | Justificación |
|---|--------|--------------|---------------|
| 1 | Celery worker + acks_late + idempotency en `finally` | 8 | Construir esto a mano cuesta una semana; el patrón evita varias clases de bugs (lost updates, double-execution, OOM kills). |
| 2 | Auth dependency `require_permissions` + middleware Next.js `updateSession` | 10 (5+5) | Bootstrap completo de auth Supabase backend+frontend. |
| 3 | Server Actions admin (createUser, getUsers, getRoles, role_permissions M:N) + `withPermissionAuth` HOF | 8 (5+3) | Toda la fontanería de gestión de usuarios desde UI sin REST extra. |
| 4 | Estructura monorepo + docker-compose dev/prod + Caddyfile + Dockerfile | 8 (5+2+1) | Plumbing operacional reusable 1:1. |
| 5 | `job_run_history` + processing_status JSONB + scheduler con circuit-breaker | 8 (5+3) | Plataforma de jobs trazables que la UI puede pollear; circuit-breaker evita ciclos infinitos. |

**Total Top 5: ~42 SP de ahorro estimado.**
