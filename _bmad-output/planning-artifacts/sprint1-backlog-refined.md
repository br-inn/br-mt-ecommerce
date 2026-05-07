---
title: "Sprint 1 Backlog Refinado — MT Middle East MDM + Pricing Fase 1a"
status: "draft"
version: "1.0"
created: "2026-05-06"
project_name: "mt-pricing-mdm-phase1"
sprint: "S1"
sprint_goal: "Tener el shell de la app autenticado funcionando + primera tabla `products` accesible CRUD desde la UI por un Comercial real."
related: ["epics-and-stories-mt-pricing-mdm-phase1.md", "sprint0-plan-consolidado.md"]
---

# Sprint 1 Backlog Refinado — MT Middle East MDM + Pricing Fase 1a

## 1. Sprint goal

> "Tener el shell de la app autenticado funcionando + primera tabla `products` accesible CRUD desde la UI por un Comercial real."

Demo objetivo (Friday-of-S1, 30 min):
1. Comercial real entra a `https://dev.mtme.example`, hace login con magic link.
2. La home muestra "Hola {nombre} — eres comercial".
3. Click en "Productos" abre listado paginado vacío + botón "Nuevo SKU".
4. Crear `MT-V-038` con `name_en`, `family`, `dn`, `pn`, `material` → toast "Guardado".
5. La row aparece en el listado, abrir detalle muestra tab Ficha técnica con datos.
6. `audit_events` registra el INSERT con `actor=comercial-real`.

Si los 6 puntos pasan en staging, S1 está done.

## 2. Capacidad asumida

| Concepto | Valor |
|----------|-------|
| Devs FTE | 2-3 (a confirmar tras Q-05 RACI TI Integración) |
| Velocity asumida | 30-40 SP/sprint |
| Sprint length | 2 semanas (10 días laborables) |
| Reservas | 20 % buffer (ceremonias, code review, refinement S2) |
| Capacidad efectiva | ~28-32 SP de código nuevo |

> Si TI Integración entra a S1 como FTE dedicado (decisión Q-05), capacidad sube a 40 SP. Si entra como role-share o vendor part-time, capacidad baja a 24-28 SP — en ese caso aplicar §6 (stories candidatas a S2).

## 3. Stories incluidas

> Convención: `US-{epic}-{nn}` por consistencia con `epics-and-stories-mt-pricing-mdm-phase1.md` v1.1. Donde la historia ya existe en el doc fuente, se preserva el ID; donde se crea en S1 (variantes/splits), se sufija con sub-id (`-01`, `-02`).

---

### US-1A-01-01 — Setup repos `mt-pricing-frontend` + `mt-pricing-backend` + `mt-pricing-infra` con scaffolding

**Épica**: EP-1A-01 ([epics-and-stories-mt-pricing-mdm-phase1.md §EP-1A-01](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** TI Integración
**Quiero** que existan tres repos GitHub con scaffolding base (Next.js 16 + FastAPI 0.x + docker-compose.prod.yml + Caddyfile)
**Para** que el equipo pueda hacer commits desde el día 1 con CI verde.

#### Contexto
Esta es la primera historia que toca código. Todo lo demás depende de ella. Si ya quedó hecha en S0 (entregable S0-D13), confirmar y mover los SP a buffer; si quedó parcial, completar aquí.

#### Criterios de aceptación (BDD)
- [ ] **Dado** el repo `mt-pricing-frontend` no existe **Cuando** el TI ejecuta el bootstrap **Entonces** queda creado con Next.js 16 + React 19 + Tailwind v4 + Shadcn/ui (new-york), `next-intl`, lockfile `pnpm-lock.yaml` commiteado y README en español.
- [ ] **Dado** el repo `mt-pricing-backend` recién creado **Cuando** se ejecuta `pytest -q` localmente **Entonces** corre 0 tests con exit code 0 y reporta cobertura 0 % sin errores.
- [ ] **Dado** el repo `mt-pricing-infra` **Cuando** se inspecciona **Entonces** contiene `docker-compose.prod.yml`, `Caddyfile`, `scripts/deploy.sh` y un `.env.example` con variables documentadas.
- [ ] **Dado** los 3 repos **Cuando** un dev nuevo clona **Entonces** `make dev` (o equivalente documentado en README) levanta los servicios en menos de 5 min.

#### Tareas técnicas (subtasks)
- [ ] Backend: `mt-pricing-backend` con `pyproject.toml`, `app/main.py` FastAPI hello-world, `app/core/config.py` Pydantic Settings, layout de `app/api/`, `app/services/`, `app/repositories/`, `app/db/`.
- [ ] Frontend: `mt-pricing-frontend` con `app/` (Next.js App Router), `components/ui/` (Shadcn instalado), `lib/`, `messages/{es,en}.json` para next-intl.
- [ ] Infra: `docker-compose.dev.yml` con `db` (Postgres local fallback), `redis`, `backend`, `frontend`, `caddy`. `docker-compose.prod.yml` con perfiles para Hetzner.
- [ ] Docs: README ES en cada repo + CODEOWNERS + branch protection con check obligatorio `ci`.
- [ ] Tests: pipeline arranca con un test trivial verde en cada repo.
- [ ] Docs: ADR-036 (repos separados) referenciado en README raíz.

#### Dependencias
- Bloqueada por: ninguna (S0-D13 idealmente lo dejó listo).
- Bloquea a: TODAS las demás stories del sprint.

#### Mocks / Wireframes
- N/A (infra-only).
- Datos test: ninguno.

#### Endpoints API afectados
- `GET /` (hello world), `GET /health/live` (placeholder, se completa en US-1A-07-02-S1).

#### Modelos afectados
- Ninguno.

#### Observability
- Métricas: build time del CI (target < 5 min).
- Logs: stdout JSON básico desde el día 1 (formato: `{"ts","level","msg"}`).
- Error scenarios: deploy fallido → notificación a canal Slack/email.

#### Definition of Ready (DoR) — checklist
- [ ] Mocks revisados con UX/Comercial (N/A — infra).
- [ ] API contract acordado y mergeado (mínimo: `GET /` y `/health/live`).
- [ ] Modelo SQLAlchemy disponible (N/A en esta story).
- [ ] Permisos RBAC definidos (N/A).
- [ ] Datos test disponibles (N/A).
- [ ] No tiene dependencias bloqueantes pendientes.
- [ ] Story points ≤ 8.
- [ ] Aceptación clara con BDD.
- [ ] Owner técnico identificado (TBD).

#### Definition of Done (DoD) — checklist
- [ ] Code review aprobado por 2 devs.
- [ ] Tests pasan (smoke test trivial).
- [ ] Coverage ≥ 80 % en código nuevo (trivial: hello world).
- [ ] Lint + typecheck OK (`ruff` + `mypy` backend; `eslint` + `tsc --noEmit` frontend).
- [ ] Migración Alembic up + down testeada (N/A — esta story sólo deja Alembic init listo, la primera migración real es US-1A-01-08-S1).
- [ ] Deploy a staging exitoso (`/health/live` responde 200).
- [ ] Smoke test en staging por dev distinto al autor.
- [ ] Audit event verificado (N/A).
- [ ] Documentación actualizada (README en español).
- [ ] PR mergeado a main.
- [ ] Sentry sin errores nuevos sustained.

#### Notas
Si el monorepo (Turborepo) gana en S0, ajustar a un repo único con `apps/frontend`, `apps/backend`, `infra/`. La decisión está pendiente en S0; esta story asume multirepo (ADR-036).

#### SP
**5**

#### Sprint asignado
S1.

#### Owner técnico (placeholder)
TBD en kickoff.

---

### US-1A-01-04-S1 — Pre-commit + commitlint + base CI workflows (lint + test + build)

**Épica**: EP-1A-01
**Como** TI Integración / dev backend
**Quiero** pre-commit hooks (`ruff`, `eslint`, `prettier`, `commitlint`) y workflows de GitHub Actions con `lint + test + build`
**Para** que ningún PR llegue a review con problemas básicos.

#### Contexto
Hardening del flujo de PR. Sin esto, code review se gasta en typos/format. Versión simplificada del US-1A-01-03 del doc fuente (CI/CD completo) para no acoplar el deploy a esta story.

#### Criterios de aceptación (BDD)
- [ ] **Dado** un dev hace commit con un mensaje sin formato Conventional Commits **Cuando** intenta `git commit` **Entonces** el hook bloquea con mensaje claro.
- [ ] **Dado** un PR a `main` con código mal formateado **Cuando** se abre **Entonces** GitHub Actions reporta status `lint` rojo y bloquea merge (branch protection).
- [ ] **Dado** un PR con tests rotos **Cuando** se abre **Entonces** status `test` rojo bloquea merge.
- [ ] **Dado** un PR limpio **Cuando** se abre **Entonces** los 3 checks (`lint`, `test`, `build`) pasan en < 5 min.

#### Tareas técnicas (subtasks)
- [ ] Backend: configurar `pre-commit` con `ruff`, `mypy --strict` (en código nuevo), `pytest` (subset rápido).
- [ ] Frontend: `husky` + `lint-staged` con `eslint --fix` y `prettier --write`. `commitlint` con preset `@commitlint/config-conventional`.
- [ ] CI: `.github/workflows/ci-backend.yml` y `ci-frontend.yml` con jobs `lint`, `test`, `build`, paralelos.
- [ ] Caching: pip + pnpm caches via `actions/cache@v4`.
- [ ] Branch protection: requerir `ci-backend / lint`, `ci-backend / test`, `ci-frontend / lint`, `ci-frontend / test`.
- [ ] Docs: README documenta cómo instalar pre-commit local.

#### Dependencias
- Bloqueada por: US-1A-01-01.
- Bloquea a: code review velocity (no bloquea code, sí salud del flujo).

#### Mocks / Wireframes
- N/A.
- Datos test: ninguno.

#### Endpoints API afectados
- Ninguno.

#### Modelos afectados
- Ninguno.

#### Observability
- Métricas: CI build time, % PRs con check rojo.
- Logs: GH Actions logs estándar.
- Error scenarios: nada que reportar a Sentry desde CI.

#### Definition of Ready (DoR) — checklist
- [ ] Mocks revisados con UX/Comercial (N/A).
- [ ] API contract acordado y mergeado (N/A).
- [ ] Modelo SQLAlchemy disponible (N/A).
- [ ] Permisos RBAC definidos (N/A).
- [ ] Datos test disponibles (N/A).
- [ ] No tiene dependencias bloqueantes pendientes (espera US-1A-01-01).
- [ ] Story points ≤ 8.
- [ ] Aceptación clara con BDD.
- [ ] Owner técnico identificado.

#### Definition of Done (DoD) — checklist
- [ ] Code review aprobado por 2 devs.
- [ ] Tests pasan en CI con tiempo total < 5 min.
- [ ] Coverage ≥ 80 % en código nuevo (config de coverage threshold ya en CI).
- [ ] Lint + typecheck OK.
- [ ] Migración Alembic up + down testeada (N/A).
- [ ] Deploy a staging exitoso (no aplica, no hay deploy en esta story).
- [ ] Smoke test en staging por dev distinto al autor (verificar: PR de prueba con violación deliberada → check rojo).
- [ ] Audit event verificado (N/A).
- [ ] Documentación actualizada (README "How to set up pre-commit").
- [ ] PR mergeado a main.
- [ ] Sentry sin errores nuevos sustained (N/A).

#### Notas
No incluye deploy a staging — eso queda para US-1A-01-03 en S2/S3 (cuando exista runtime estable). En S1 los deploys a `dev.mtme.example` se disparan manualmente vía `scripts/deploy.sh`.

#### SP
**3**

#### Sprint asignado
S1.

#### Owner técnico (placeholder)
TBD en kickoff.

---

### US-1A-01-05 — Auth Supabase end-to-end (Magic Link + JWT validation backend + AuthProvider + middleware)

**Épica**: EP-1A-01
**Como** Comercial / Gerente / TI
**Quiero** poder loguearme con magic link y que la app me reconozca con mi rol en cada request
**Para** trabajar con el shell de la app real.

#### Contexto
Sin auth no hay app. Esta story es la "spine" que conecta frontend (sesión) ↔ backend (JWT) ↔ Postgres (RLS). Es la story más arriesgada del sprint por la integración Next.js middleware ↔ FastAPI dependency.

#### Criterios de aceptación (BDD)
- [ ] **Dado** un usuario va a `/login` **Cuando** introduce email + click "Enviar magic link" **Entonces** recibe email Supabase en < 30 s con link al callback `/auth/callback`.
- [ ] **Dado** el usuario click el link **Cuando** llega al callback **Entonces** Supabase setea cookies HTTPOnly y la app redirige a `/` (home autenticada).
- [ ] **Dado** un usuario autenticado **Cuando** llama `GET /api/v1/me` (FastAPI) con la cookie de Supabase **Entonces** el backend valida el JWT (verify firma + iss + aud + exp) y retorna `{user_id, email, role, ui_locale}`.
- [ ] **Dado** un usuario sin token **Cuando** llama `GET /api/v1/products` **Entonces** retorna 401.
- [ ] **Dado** un usuario nuevo via magic link **Cuando** completa el flujo **Entonces** se inserta automáticamente en `public.users` con `role='comercial'`, `ui_locale='es'` (via trigger `on_auth_user_created`).
- [ ] **Dado** un Comercial autenticado **Cuando** intenta `GET /api/v1/admin/jobs` (placeholder de ti-only) **Entonces** retorna 403 (RLS o RBAC backend deniega).

#### Tareas técnicas (subtasks)
- [ ] Backend: `app/auth/jwt.py` con `verify_supabase_jwt(token)` usando `python-jose` y JWKS de Supabase. Cache JWKS in-memory con TTL 1 h.
- [ ] Backend: `app/auth/dependencies.py` con `get_current_user` y `require_role(role)` dependencies de FastAPI.
- [ ] Backend: trigger Postgres `on_auth_user_created` que inserta en `public.users` con defaults (`role='comercial'`, `ui_locale='es'`). Migración Alembic separada para el trigger.
- [ ] Backend: tabla `public.users` mínima (id FK auth.users, email, role enum, ui_locale, created_at, updated_at). Migración Alembic.
- [ ] Frontend: `lib/supabase/server.ts` y `lib/supabase/browser.ts` (clientes SSR + browser via `@supabase/ssr`).
- [ ] Frontend: `middleware.ts` que refresca la sesión Supabase en cada request, redirige a `/login` si no hay sesión y la ruta es protected.
- [ ] Frontend: `/login`, `/auth/callback`, `/auth/signout` páginas server-side.
- [ ] Frontend: `lib/auth/AuthProvider.tsx` (React context) con hook `useUser()`.
- [ ] Frontend: hook `useFetch()` que adjunta automáticamente la cookie Supabase + maneja 401 redirigiendo a `/login`.
- [ ] Tests: unit del JWT verifier (firma OK, exp expirado, iss inválido, aud inválido). Integration test con Supabase staging del flujo completo magic-link → `GET /me`.
- [ ] Docs: README "Cómo loguearse en dev" + diagrama del flujo en arquitectura §6.

#### Dependencias
- Bloqueada por: US-1A-01-01 + US-1A-01-08-S1 (necesita Alembic listo para crear `public.users` y el trigger).
- Bloquea a: US-1A-02-01-S1 (RLS policies sobre `products` necesitan tabla `users` con roles).

#### Mocks / Wireframes
- Referencia: `ux-mockups-mt-pricing-mdm-phase1.md` Pantalla 23 (Login).
- Datos test: 3 usuarios seeded en Supabase staging — `comercial+test@mtme.example`, `gerente+test@...`, `ti+test@...`.

#### Endpoints API afectados
- `GET /api/v1/me` (nuevo, retorna usuario actual).
- `GET /api/v1/products` (placeholder; integración real en US-1A-02-01-S1).

#### Modelos afectados
- `public.users` (clase SQLAlchemy `User` en `app/db/models/user.py`).

#### Observability
- Métricas: `auth.login.success` / `auth.login.failure`, latencia JWT verify p95.
- Logs: `actor=user_id, action=login_success|login_failure, source=magic_link`.
- Error scenarios: JWT verify exception → Sentry con tag `auth.error`. Trigger `on_auth_user_created` falla → Sentry crit (bloquea signup).

#### Definition of Ready (DoR) — checklist
- [ ] Mocks revisados con UX/Comercial (Pantalla 23).
- [ ] API contract acordado y mergeado (`/me` + flow magic link).
- [ ] Modelo SQLAlchemy disponible (`User` SQLAlchemy class).
- [ ] Permisos RBAC definidos (`comercial`, `gerente`, `ti` enum).
- [ ] Datos test disponibles (3 usuarios seeded staging).
- [ ] No tiene dependencias bloqueantes pendientes (US-1A-01-01 + US-1A-01-08-S1 listos).
- [ ] Story points ≤ 8.
- [ ] Aceptación clara con BDD.
- [ ] Owner técnico identificado.

#### Definition of Done (DoD) — checklist
- [ ] Code review aprobado por 2 devs.
- [ ] Tests pasan (unit JWT + integration login flow).
- [ ] Coverage ≥ 80 % en `app/auth/`.
- [ ] Lint + typecheck OK.
- [ ] Migración Alembic up + down testeada (`public.users` + trigger).
- [ ] Deploy a staging exitoso.
- [ ] Smoke test en staging por dev distinto al autor (login real, comprobar `/me` retorna rol).
- [ ] Audit event verificado (`role.assign` registrado al crear usuario nuevo).
- [ ] Documentación actualizada (README + ADR-032 referenciado).
- [ ] PR mergeado a main.
- [ ] Sentry sin errores nuevos sustained.

#### Notas
Esta story es 8 SP "duros". Si en mid-sprint vemos que el middleware Next.js + cookies cross-domain dan problemas, splitear: (a) backend JWT + `/me` (5 SP), (b) frontend AuthProvider + middleware (5 SP) y mover (b) a S2. Aviso de splitting si al día 4 no hay `GET /me` con JWT real verde.

#### SP
**8**

#### Sprint asignado
S1.

#### Owner técnico (placeholder)
TBD en kickoff (idealmente el dev con experiencia Next.js + Supabase SSR).

---

### US-1A-01-06-S1 — i18n UI ES/EN con next-intl + selector de idioma

**Épica**: EP-1A-01
**Como** Comercial / Gerente
**Quiero** elegir idioma de la UI (ES o EN) y que persista entre sesiones
**Para** trabajar cómodo según preferencia.

#### Contexto
Variante temprana del US-1A-07-04 (que en el doc fuente está en S3). Se adelanta a S1 con cobertura ES + EN para evitar deuda técnica de strings hardcoded. Si capacidad lo demanda, el doc fuente lo permite diferir a S3 sin romper nada.

#### Criterios de aceptación (BDD)
- [ ] **Dado** un usuario con `users.ui_locale='es'` **Cuando** entra a la app **Entonces** todos los strings se renderizan en español.
- [ ] **Dado** un usuario click el selector y elige `EN` **Cuando** confirma **Entonces** la sesión recarga UI en inglés y persiste en `users.ui_locale`.
- [ ] **Dado** un string sin traducción EN **Cuando** se renderiza **Entonces** se muestra en español con un warning en consola dev (no bloqueante en prod).
- [ ] **Dado** un usuario nuevo **Cuando** entra **Entonces** el `Accept-Language` HTTP del browser determina el default (ES si `es-*`, EN otherwise) y se persiste.

#### Tareas técnicas (subtasks)
- [ ] Frontend: `next-intl` configurado con `app/[locale]/layout.tsx`, `messages/es.json`, `messages/en.json`.
- [ ] Frontend: `components/LanguageSelector.tsx` en topbar usando `useLocale()` + `Link` de next-intl.
- [ ] Backend: `PATCH /api/v1/me` con body `{ui_locale: "es"|"en"}` que actualiza `users.ui_locale`.
- [ ] Frontend: cambio de selector llama el PATCH y refresca via `router.refresh()`.
- [ ] Tests: unit test que un componente render igual en ES vs EN. Integration test que cambio de locale persiste.
- [ ] Docs: README "Cómo agregar una nueva clave de traducción".
- [ ] Glosario: `messages/glossary.md` para términos críticos del dominio (SKU, family, breakdown, etc.).

#### Dependencias
- Bloqueada por: US-1A-01-01, US-1A-01-05 (necesita `users.ui_locale`).
- Bloquea a: ninguna directa (todas las stories siguientes asumen i18n disponible).

#### Mocks / Wireframes
- Referencia: `ux-mockups-mt-pricing-mdm-phase1.md` (selector de idioma en topbar — patrón global, no pantalla específica).
- Datos test: messages/{es,en}.json con ~30 keys mínimas (login, nav, common buttons, validation errors).

#### Endpoints API afectados
- `PATCH /api/v1/me` (nuevo).

#### Modelos afectados
- `User` (campo `ui_locale`).

#### Observability
- Métricas: `i18n.locale_changed` count.
- Logs: `actor=user_id, action=ui_locale_changed, source=ui, before=es, after=en`.
- Error scenarios: clave de traducción missing → console.warn + Sentry breadcrumb (no error).

#### Definition of Ready (DoR) — checklist
- [ ] Mocks revisados con UX/Comercial.
- [ ] API contract acordado y mergeado (`PATCH /me`).
- [ ] Modelo SQLAlchemy disponible.
- [ ] Permisos RBAC definidos (cualquier user puede cambiar su propio `ui_locale`).
- [ ] Datos test disponibles.
- [ ] No tiene dependencias bloqueantes pendientes.
- [ ] Story points ≤ 8.
- [ ] Aceptación clara con BDD.
- [ ] Owner técnico identificado.

#### Definition of Done (DoD) — checklist
- [ ] Code review aprobado por 2 devs.
- [ ] Tests pasan.
- [ ] Coverage ≥ 80 % en código nuevo.
- [ ] Lint + typecheck OK.
- [ ] Migración Alembic up + down testeada (campo `ui_locale` ya existe desde US-1A-01-05).
- [ ] Deploy a staging exitoso.
- [ ] Smoke test en staging por dev distinto al autor (cambiar idioma → cerrar sesión → re-login → idioma persiste).
- [ ] Audit event verificado (`ui_locale_changed`).
- [ ] Documentación actualizada.
- [ ] PR mergeado a main.
- [ ] Sentry sin errores nuevos sustained.

#### Notas
Cobertura S1: sólo ES + EN. AR (RTL) entra en S3 (US-1A-02-05 + EP-1A-07).

#### SP
**3**

#### Sprint asignado
S1.

#### Owner técnico (placeholder)
TBD.

---

### US-1A-01-08-S1 — Bootstrap SQLAlchemy 2.0 async + Alembic + primera migración

**Épica**: EP-1A-01 (US-1A-01-08 del doc fuente, traída de S0 si quedó pendiente — ver §1794 nota de slip)
**Como** dev backend
**Quiero** SQLAlchemy 2.0 async configurado con asyncpg + Alembic init + factory de sesión por request + primera migración con tabla `users`
**Para** que las historias de S1 puedan modelar `products` sobre ORM tipado y sobre BD migrada con Alembic.

#### Contexto
Esta story estaba en S0, slipeable a S1 según `epics-and-stories-mt-pricing-mdm-phase1.md` §1794. Si TI MT no entregó S0-D11b a tiempo, vive aquí. Es prerequisito de TODAS las historias de modelos (US-1A-01-05, US-1A-02-01-S1).

#### Criterios de aceptación (BDD)
- [ ] **Dado** `mt-pricing-backend/app/core/db.py` recién creado **Cuando** se importa `engine` y `AsyncSessionLocal` **Entonces** ambos quedan disponibles, configurados con driver `asyncpg`, pool size adaptado al worker mode (web=20, worker=10), `pool_pre_ping=True`.
- [ ] **Dado** Alembic inicializado bajo `mt-pricing-backend/alembic/` con `env.py` configurado para autogenerate **Cuando** ejecuto `alembic revision --autogenerate -m "init users"` **Entonces** se genera una migración válida que crea `public.users` (id, email, role, ui_locale, created_at, updated_at) y aplica con `alembic upgrade head` contra Supabase staging.
- [ ] **Dado** un endpoint FastAPI con `Depends(get_session)` **Cuando** se invoca **Entonces** la sesión se crea por request, se commitea al final si no hay excepción, hace rollback si la hay, y se cierra sin leak (verificado con integration test que cuenta conexiones activas en `pg_stat_activity`).
- [ ] **Dado** el rol Postgres `mt_app` (creado vía Supabase migration) **Cuando** el backend se conecta con DSN `postgresql+asyncpg://mt_app@...` **Entonces** las RLS policies aplican (test prueba que `mt_app` NO puede SELECT filas de otro usuario).
- [ ] **Dado** la migración aplicada **Cuando** ejecuto `alembic downgrade -1` **Entonces** la tabla `users` se elimina sin errores y se puede re-aplicar `upgrade head` idempotentemente.

#### Tareas técnicas (subtasks)
- [ ] Backend: `app/core/db.py` con `engine`, `AsyncSessionLocal`, `get_session()` async generator.
- [ ] Backend: `app/db/base.py` con `Base = DeclarativeBase` + `Mapped[]` typing.
- [ ] Backend: `app/db/models/user.py` clase `User`.
- [ ] DB: `alembic init` + `alembic/env.py` configurado para `target_metadata = Base.metadata` + DSN desde Pydantic Settings.
- [ ] DB: migración Alembic `0001_init_users.py` con `op.create_table('users', ...)` + enum `role_t` + enum `ui_locale_t`.
- [ ] Tests: unit del session factory (sesión se cierra). Integration test con Supabase staging: insert + select + RLS deniega.
- [ ] Docs: README "Cómo crear una nueva migración" + comando `make migration name=...`.
- [ ] Docs: ADR-045 referenciado.

#### Dependencias
- Bloqueada por: US-1A-01-01 (repo backend), Supabase project provisioned (S0-D12).
- Bloquea a: US-1A-01-05 (auth necesita tabla `users`), US-1A-02-01-S1 (products migration), US-1A-07-01-S1 (audit_events).

#### Mocks / Wireframes
- N/A (data layer).
- Datos test: ninguno; los seeds de usuarios entran via US-1A-01-05.

#### Endpoints API afectados
- Ninguno directamente, pero habilita `Depends(get_session)` en los siguientes.

#### Modelos afectados
- `User` (clase SQLAlchemy).

#### Observability
- Métricas: pool size actual (`db.pool.checked_out`), query duration p95.
- Logs: query lentas (> 500 ms) loggeadas con `actor` + SQL truncado.
- Error scenarios: `OperationalError` (DB unreachable) → Sentry crit + healthcheck `/health/ready` retorna 503.

#### Definition of Ready (DoR) — checklist
- [ ] Mocks revisados con UX/Comercial (N/A).
- [ ] API contract acordado y mergeado (N/A — esta story es infra).
- [ ] Modelo SQLAlchemy disponible (`User`).
- [ ] Permisos RBAC definidos (rol `mt_app` Postgres acordado en S0).
- [ ] Datos test disponibles (N/A).
- [ ] No tiene dependencias bloqueantes pendientes.
- [ ] Story points ≤ 8.
- [ ] Aceptación clara con BDD.
- [ ] Owner técnico identificado.

#### Definition of Done (DoD) — checklist
- [ ] Code review aprobado por 2 devs.
- [ ] Tests pasan (unit + integration).
- [ ] Coverage ≥ 80 % en `app/core/db.py` y `app/db/`.
- [ ] Lint + typecheck OK.
- [ ] Migración Alembic up + down testeada (CI corre `upgrade head && downgrade base && upgrade head`).
- [ ] Deploy a staging exitoso (alembic ejecuta clean en staging).
- [ ] Smoke test en staging por dev distinto al autor.
- [ ] Audit event verificado (N/A).
- [ ] Documentación actualizada (README + ADR-045).
- [ ] PR mergeado a main.
- [ ] Sentry sin errores nuevos sustained.

#### Notas
Si la decisión de S0-D11b sobre `celery-sqlalchemy-scheduler` se complicó, esta story sigue siendo viable porque sólo cubre el motor SQLAlchemy core, no el scheduler.

#### SP
**5**

#### Sprint asignado
S1.

#### Owner técnico (placeholder)
TBD (idealmente dev con experiencia SQLAlchemy 2.0 async).

---

### US-1A-01-09-S1 — Cliente supabase-py + dual config + smoke test

**Épica**: EP-1A-01 (US-1A-01-09 del doc fuente)
**Como** dev backend
**Quiero** `mt-pricing-backend/app/core/supabase.py` con factories diferenciadas (`get_supabase_client` anon / `get_supabase_admin` service-role) + Pydantic Settings + smoke test contra Supabase Auth
**Para** que las historias de auth y storage puedan invocar `auth.admin.*` y `storage.from_(...)` sin re-implementar boilerplate.

#### Contexto
ADR-045 — patrón de dos clientes. Necesario para `auth.admin.sign_out(user_id)` (force-logout futuro en EP-1A-07), invitar usuarios manualmente, y subir thumbnails a Storage.

#### Criterios de aceptación (BDD)
- [ ] **Dado** `app/core/supabase.py` recién creado **Cuando** se importa `get_supabase_admin` **Entonces** retorna un cliente supabase-py inicializado con `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` (cargados via Pydantic Settings) y validados al boot (rechaza service_role key vacía en producción).
- [ ] **Dado** un smoke test de integración **Cuando** se ejecuta `sb.auth.admin.list_users(per_page=1)` contra Supabase staging **Entonces** la llamada retorna 200 sin error.
- [ ] **Dado** una petición desde un endpoint **Cuando** invoca tanto SQLAlchemy (`Depends(get_session)`) como supabase-py (`Depends(get_supabase_admin)`) **Entonces** ambos clientes coexisten sin conflicto.
- [ ] **Dado** logs estructurados **Cuando** una llamada a supabase-py falla **Entonces** el error se loggea con `request_id` + `supabase_error_code` y se reporta a Sentry.

#### Tareas técnicas (subtasks)
- [ ] Backend: `app/core/supabase.py` con `get_supabase_client()` (anon) y `get_supabase_admin()` (service_role, lazy singleton).
- [ ] Backend: Pydantic Settings `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`. Validador que rechaza service_role vacía cuando `ENV=prod`.
- [ ] Tests: unit que mockea supabase-py + integration smoke test (skip en CI si secrets no presentes).
- [ ] Docs: README "Cuándo usar SQLAlchemy vs supabase-py" + tabla de decisión.

#### Dependencias
- Bloqueada por: US-1A-01-01.
- Bloquea a: US-1A-07-01-S1 (Sentry + structlog dependen del wrapper de error). En S1 sólo es smoke; usos reales (force-logout, storage) son S2/S3.

#### Mocks / Wireframes
- N/A.
- Datos test: variables de entorno cargadas vía Doppler en CI.

#### Endpoints API afectados
- Ninguno directamente.

#### Modelos afectados
- Ninguno.

#### Observability
- Métricas: `supabase.api.calls` count + p95 latency por método.
- Logs: cada llamada admin loggeada con `actor` + método + duration.
- Error scenarios: 4xx/5xx de supabase-py → Sentry tag `supabase.error`.

#### Definition of Ready (DoR) — checklist
- [ ] Mocks revisados con UX/Comercial (N/A).
- [ ] API contract acordado y mergeado (N/A).
- [ ] Modelo SQLAlchemy disponible (N/A).
- [ ] Permisos RBAC definidos (service_role solo backend; anon nunca expuesta server-side de forma cross-tenant).
- [ ] Datos test disponibles (Supabase staging accesible).
- [ ] No tiene dependencias bloqueantes pendientes.
- [ ] Story points ≤ 8.
- [ ] Aceptación clara con BDD.
- [ ] Owner técnico identificado.

#### Definition of Done (DoD) — checklist
- [ ] Code review aprobado por 2 devs.
- [ ] Tests pasan (unit + smoke skip-able).
- [ ] Coverage ≥ 80 % en `app/core/supabase.py`.
- [ ] Lint + typecheck OK.
- [ ] Migración Alembic up + down testeada (N/A).
- [ ] Deploy a staging exitoso.
- [ ] Smoke test en staging por dev distinto al autor.
- [ ] Audit event verificado (N/A).
- [ ] Documentación actualizada.
- [ ] PR mergeado a main.
- [ ] Sentry sin errores nuevos sustained.

#### Notas
Esta story es candidata #1 a deferir a S2 si capacidad demanda (ver §6). Su valor inmediato es bajo en S1 — el primer uso real es invitar usuarios o generar signed URLs (S2/S3).

#### SP
**3**

#### Sprint asignado
S1.

#### Owner técnico (placeholder)
TBD.

---

### US-1A-02-01-S1 — Modelo `products` SQLAlchemy + migración Alembic + RLS policies básicas

**Épica**: EP-1A-02 (US-1A-02-01 del doc fuente expandido con RLS de S1)
**Como** dev backend
**Quiero** la migración Alembic que crea `products` con todos los campos del PRD + RLS policies básicas (SELECT abierto para `comercial+`, WRITE para `comercial+`)
**Para** que UC-1a-01 a UC-1a-15 tengan tabla destino y la app respete defense-in-depth.

#### Contexto
Tabla central del MDM. Sin RLS la BD queda expuesta a queries arbitrarios desde JWT comprometidos. RLS aquí es básica; las políticas finas (ej. `prices.status='approved'` only por gerente) llegan en S3 con US-1A-07-02.

#### Criterios de aceptación (BDD)
- [ ] **Dado** la migración inicial aplicada **Cuando** se inserta una fila con `name_en` NULL **Entonces** el INSERT falla por NOT NULL constraint (BR-1a-02).
- [ ] **Dado** una fila con `sku` duplicado **Cuando** se intenta insertar **Entonces** el INSERT falla por UNIQUE (BR-1a-01).
- [ ] **Dado** la columna `embedding VECTOR(1536)` **Cuando** se consulta `\d products` **Entonces** existe pero todas las filas tienen NULL (reservado Fase 1.5+, NFR-20).
- [ ] **Dado** un usuario sin sesión **Cuando** intenta `SELECT * FROM products` directamente con `mt_app` role **Entonces** RLS deniega (0 filas).
- [ ] **Dado** un usuario `comercial` autenticado **Cuando** ejecuta `SELECT * FROM products` **Entonces** RLS permite y retorna todas las filas (tenant único en S1).
- [ ] **Dado** la tabla creada **Cuando** se ejecuta `alembic downgrade -1` **Entonces** la tabla y sus enums se eliminan limpio.

#### Tareas técnicas (subtasks)
- [ ] Backend: `app/db/models/product.py` clase `Product` con campos identidad (sku, name_en, family, brand, dn, pn, material, type, active, data_quality), `specs JSONB`, `embedding VECTOR(1536)` reservado, `created_at`, `updated_at`, `created_by`, `updated_by`.
- [ ] DB: migración Alembic `0002_create_products.py` con extensión `pgvector`, enum `data_quality_t (full|partial|blocked)`, enum `family_t` (gate_valve, ball_valve, etc. — seed inicial 8 valores), índices `(family, active)`, `(data_quality, active)`, GIN sobre `specs`.
- [ ] DB: RLS policies: `products_select_all_authenticated` (cualquier rol auth puede SELECT), `products_insert_comercial` (solo `comercial+`), `products_update_comercial` (solo `comercial+`).
- [ ] Tests: unit de la clase `Product` (validación de constraints). Integration: insert/update/delete + verificar RLS.
- [ ] Docs: actualizar `mt-products-module-design.md` (si existe) o agregar nota en arquitectura §10.

#### Dependencias
- Bloqueada por: US-1A-01-08-S1 (Alembic listo), US-1A-01-05 (auth + tabla `users`).
- Bloquea a: US-1A-02-02-S1, US-1A-02-03-S1, US-1A-07-01-S1 (audit triggers).

#### Mocks / Wireframes
- N/A (data layer).
- Datos test: 5 SKUs fixture en `tests/fixtures/products.json` (MT-V-038, MT-V-5114, MT-V-200, MT-V-301, MT-V-450) con specs reales del PIM.

#### Endpoints API afectados
- Ninguno directamente, pero habilita US-1A-02-02-S1.

#### Modelos afectados
- `Product` (clase SQLAlchemy).

#### Observability
- Métricas: `products.count` (total), `products.data_quality.{full,partial,blocked}` (count).
- Logs: queries lentas con `actor`.
- Error scenarios: violación de constraint → 422 al cliente, breadcrumb a Sentry; nunca 500 silencioso.

#### Definition of Ready (DoR) — checklist
- [ ] Mocks revisados con UX/Comercial (N/A directo, pero usado por Pantalla 2 y 3).
- [ ] API contract acordado y mergeado.
- [ ] Modelo SQLAlchemy disponible.
- [ ] Permisos RBAC definidos (RLS policy spec acordado).
- [ ] Datos test disponibles (5 fixtures).
- [ ] No tiene dependencias bloqueantes pendientes.
- [ ] Story points ≤ 8.
- [ ] Aceptación clara con BDD.
- [ ] Owner técnico identificado.

#### Definition of Done (DoD) — checklist
- [ ] Code review aprobado por 2 devs.
- [ ] Tests pasan.
- [ ] Coverage ≥ 80 % en `app/db/models/product.py`.
- [ ] Lint + typecheck OK.
- [ ] Migración Alembic up + down testeada en CI.
- [ ] Deploy a staging exitoso.
- [ ] Smoke test en staging por dev distinto al autor (insert + select + RLS deniega anon).
- [ ] Audit event verificado (N/A — triggers en S3, pero `created_by`/`updated_by` poblados manualmente desde service layer).
- [ ] Documentación actualizada.
- [ ] PR mergeado a main.
- [ ] Sentry sin errores nuevos sustained.

#### Notas
RLS de S1 es minimalista (auth=yes/no por rol). La granularidad fina (gerente only para `prices.approved`) llega en S3 con US-1A-07-02 del doc fuente.

#### SP
**5**

#### Sprint asignado
S1.

#### Owner técnico (placeholder)
TBD.

---

### US-1A-02-02-S1 — Endpoints REST `GET /products`, `POST /products`, `GET /products/{sku}` con paginación cursor

**Épica**: EP-1A-02 (combina US-1A-02-02 + US-1A-02-09 del doc fuente, scoped a S1)
**Como** Comercial
**Quiero** poder listar, crear y leer SKUs vía API
**Para** que la UI tenga endpoints reales contra los que conectar.

#### Contexto
Cubre los 3 endpoints más críticos. `PUT/PATCH` se difiere a S2 (US-1A-02-03 doc fuente) para acotar S1 a "create-list-read" CRUD parcial. El listado usa cursor pagination según arquitectura §11.1.

#### Criterios de aceptación (BDD)
- [ ] **Dado** que soy Comercial autenticado **Cuando** envío `POST /api/v1/products` con payload válido (`sku, name_en, family, dn, pn, material, type`) **Entonces** el sistema persiste con `data_quality='partial'`, retorna 201 con el ID y location header.
- [ ] **Dado** un payload sin `name_en` **Cuando** lo envío **Entonces** retorna 422 con `error.code = "BR_1A_02"` y `error.field = "name_en"`.
- [ ] **Dado** un SKU duplicado **Cuando** intento crearlo **Entonces** retorna 409 `Conflict`.
- [ ] **Dado** 224 SKUs cargados (fixture o futuro PIM) **Cuando** envío `GET /api/v1/products?family=gate_valve&limit=50` **Entonces** retorna ≤ 50 filas con `meta.next_cursor`, `meta.total` opcional.
- [ ] **Dado** un cursor inválido **Cuando** lo envío **Entonces** retorna 400.
- [ ] **Dado** un `limit=500` **Cuando** consulto **Entonces** retorna 422 (max 200, NFR-06).
- [ ] **Dado** un SKU `MT-V-038` existente **Cuando** envío `GET /api/v1/products/MT-V-038` **Entonces** retorna 200 con la ficha completa.
- [ ] **Dado** un SKU inexistente **Cuando** consulto **Entonces** retorna 404.
- [ ] **Dado** un usuario sin auth **Cuando** llama cualquiera de los 3 **Entonces** retorna 401.

#### Tareas técnicas (subtasks)
- [ ] Backend: `app/api/v1/products.py` router con 3 endpoints, Pydantic schemas (`ProductCreate`, `ProductRead`, `ProductListItem`).
- [ ] Backend: `app/services/product_service.py` con `create_product`, `get_product_by_sku`, `list_products(filters, cursor, limit)`.
- [ ] Backend: `app/repositories/product_repository.py` SQLAlchemy queries.
- [ ] Backend: cursor pagination helper en `app/api/pagination.py` (cursor = base64-encoded `(created_at, id)`).
- [ ] Backend: filtros query: `family`, `active`, `data_quality`, `q` (full-text en name_en — usar `to_tsvector` simple en S1).
- [ ] Backend: dependency `get_current_user` aplicado en los 3 endpoints.
- [ ] Tests: unit del service. Integration de los 3 endpoints (auth, validación, paginación, edge cases). Test de carga ligero (1k SKUs en fixture, listado p95 < 500 ms).
- [ ] Docs: OpenAPI spec actualizado en `mt-pricing-backend/openapi.yaml` o auto-generado por FastAPI.

#### Dependencias
- Bloqueada por: US-1A-02-01-S1, US-1A-01-05 (auth).
- Bloquea a: US-1A-02-03-S1 (UI listado).

#### Mocks / Wireframes
- Referencia: `ux-mockups-mt-pricing-mdm-phase1.md` Pantalla 2 (Lista de SKUs) y Pantalla 9 (Alta de SKU wizard).
- Datos test: 5 SKUs fixture (mismos que US-1A-02-01-S1).

#### Endpoints API afectados
- `GET /api/v1/products` (arquitectura §11.1 → líneas 1349-1357 del doc).
- `GET /api/v1/products/:sku`.
- `POST /api/v1/products`.

#### Modelos afectados
- `Product`.

#### Observability
- Métricas: `products.list.duration_p95`, `products.create.success/failure` count, `products.list.requests_per_min`.
- Logs: cada POST con `actor`, `sku`, `request_id`. Cada GET list con filtros aplicados.
- Error scenarios: violación constraint → 422 + Sentry breadcrumb. 5xx → Sentry crit con request_id.

#### Definition of Ready (DoR) — checklist
- [ ] Mocks revisados con UX/Comercial (Pantalla 2, 9).
- [ ] API contract acordado y mergeado.
- [ ] Modelo SQLAlchemy disponible.
- [ ] Permisos RBAC definidos.
- [ ] Datos test disponibles.
- [ ] No tiene dependencias bloqueantes pendientes.
- [ ] Story points ≤ 8.
- [ ] Aceptación clara con BDD.
- [ ] Owner técnico identificado.

#### Definition of Done (DoD) — checklist
- [ ] Code review aprobado por 2 devs.
- [ ] Tests pasan (unit + integration).
- [ ] Coverage ≥ 80 % en `app/api/v1/products.py` y `app/services/product_service.py`.
- [ ] Lint + typecheck OK.
- [ ] Migración Alembic up + down testeada (heredada de US-1A-02-01-S1).
- [ ] Deploy a staging exitoso.
- [ ] Smoke test en staging por dev distinto al autor (POST + GET con curl/httpie).
- [ ] Audit event verificado (`products.create` registrado manualmente desde service layer en S1; trigger automático en S3).
- [ ] Documentación actualizada (OpenAPI).
- [ ] PR mergeado a main.
- [ ] Sentry sin errores nuevos sustained.

#### Notas
Cursor pagination simple en S1 (sólo forward). Backward cursor llega cuando UI lo necesite (S2 con la table component completa).

#### SP
**5**

#### Sprint asignado
S1.

#### Owner técnico (placeholder)
TBD.

---

### US-1A-02-03-S1 — UI listado de productos (DataTable) + detalle (tab Ficha técnica)

**Épica**: EP-1A-02 (subset del US-1A-02-04 del doc fuente, scoped a 2 tabs)
**Como** Comercial
**Quiero** ver la lista de SKUs y abrir el detalle de cualquiera
**Para** localizar un producto y ver su ficha técnica.

#### Contexto
Primera UI funcional de la app. Cubre Pantallas 2 y 3 del UX. El resto de tabs (Imágenes, Costes, Precios, Traducciones, Auditoría) entran en S2-S3. Esta story es 8 SP por requerir DataTable Shadcn + react-query + filtros + detail page con SSR.

#### Criterios de aceptación (BDD)
- [ ] **Dado** un Comercial autenticado **Cuando** entra a `/productos` **Entonces** ve una DataTable con columnas `SKU, Nombre, Familia, DN, PN, Material, Estado calidad`, paginada (50 por defecto), con filtros por familia y data_quality.
- [ ] **Dado** la lista vacía **Cuando** se carga **Entonces** se muestra empty state "No hay productos. ¿Quieres crear el primero?" con CTA → wizard de creación.
- [ ] **Dado** un Comercial click "Nuevo SKU" **Cuando** completa el form (sku, name_en, family, dn, pn, material, type) y submit **Entonces** llama `POST /api/v1/products`, muestra toast "SKU creado" y refresca la lista.
- [ ] **Dado** un Comercial click una row **Cuando** abre el detalle **Entonces** ve la página `/productos/{sku}` con tab activo "Ficha técnica" mostrando los campos de identidad + specs.
- [ ] **Dado** un filtro `family=gate_valve` **Cuando** se aplica **Entonces** la URL refleja `?family=gate_valve` (state in URL) y la lista se filtra.
- [ ] **Dado** un error 422 al crear (ej. duplicado) **Cuando** ocurre **Entonces** el form muestra el error inline en el campo correspondiente.

#### Tareas técnicas (subtasks)
- [ ] Frontend: ruta `/productos` (listado) usando `@tanstack/react-query` + Shadcn `DataTable`.
- [ ] Frontend: ruta `/productos/[sku]` con tabs (Shadcn Tabs); en S1 sólo "Ficha técnica" activa, otras tabs disabled con tooltip "Próximamente S2".
- [ ] Frontend: form de "Nuevo SKU" en modal o página `/productos/nuevo` usando `react-hook-form` + `zod`.
- [ ] Frontend: i18n keys (es + en) para todos los strings.
- [ ] Frontend: `lib/api/products.ts` con typed fetcher.
- [ ] Tests: unit de los componentes (testing-library). E2E light con Playwright: login → crear SKU → ver en lista → abrir detalle.
- [ ] Docs: README "Cómo añadir una nueva tab al detalle de SKU".

#### Dependencias
- Bloqueada por: US-1A-02-02-S1, US-1A-01-05, US-1A-01-06-S1.
- Bloquea a: ninguna directa en S1; abre el camino a S2 tabs (Imágenes, Costes).

#### Mocks / Wireframes
- Referencia: `ux-mockups-mt-pricing-mdm-phase1.md` Pantalla 2 (Lista) y Pantalla 3 (Detalle SKU · tab Ficha técnica).
- Datos test: 5 SKUs fixture insertados via seed o manualmente desde POST.

#### Endpoints API afectados
- Consume: `GET /api/v1/products`, `GET /api/v1/products/:sku`, `POST /api/v1/products`.

#### Modelos afectados
- Frontend types reflejan `Product` SQLAlchemy.

#### Observability
- Métricas (Sentry frontend): page load time `/productos` p95, tasa de error en submit del form.
- Logs (browser console + Sentry breadcrumbs): `actor=user_id, action=open_product_detail`.
- Error scenarios: 5xx del backend → toast error + Sentry. 422 → mostrar inline.

#### Definition of Ready (DoR) — checklist
- [ ] Mocks revisados con UX/Comercial (Pantalla 2, 3).
- [ ] API contract acordado y mergeado.
- [ ] Modelo SQLAlchemy disponible (consume el endpoint).
- [ ] Permisos RBAC definidos.
- [ ] Datos test disponibles.
- [ ] No tiene dependencias bloqueantes pendientes.
- [ ] Story points ≤ 8.
- [ ] Aceptación clara con BDD.
- [ ] Owner técnico identificado.

#### Definition of Done (DoD) — checklist
- [ ] Code review aprobado por 2 devs.
- [ ] Tests pasan (unit components + 1 E2E happy path).
- [ ] Coverage ≥ 80 % en componentes nuevos (lib/components).
- [ ] Lint + typecheck OK.
- [ ] Migración Alembic up + down testeada (N/A frontend).
- [ ] Deploy a staging exitoso (Vercel-like deploy o Caddy server side).
- [ ] Smoke test en staging por dev distinto al autor — flujo completo demo del sprint goal.
- [ ] Audit event verificado (consume audit que produce el backend).
- [ ] Documentación actualizada.
- [ ] PR mergeado a main.
- [ ] Sentry sin errores nuevos sustained.

#### Notas
Esta story es la "money story" del sprint — la que demos. Si llega tarde, reducir scope quitando el form de "Nuevo SKU" (puede ir manualmente vía API) y dejando solo lista + detalle (5 SP).

#### SP
**8**

#### Sprint asignado
S1.

#### Owner técnico (placeholder)
TBD (idealmente dev frontend con experiencia Next.js App Router).

---

### US-1A-07-01-S1 — Tabla `audit_events` + triggers Postgres + helper de inserción desde backend

**Épica**: EP-1A-07 (combina US-1A-07-03 del doc fuente, scoped a S1 con 1 sola tabla auditada)
**Como** dev backend / Gerente
**Quiero** la tabla `audit_events` con trigger genérico funcionando sobre `products`
**Para** tener trazabilidad VAT-compliant desde el día 1.

#### Contexto
Auditoría es NFR-33/34 — mandatory para FTA UAE 2026. Empezar con `products` y validar el patrón. En S2/S3 se extiende a `costs`, `currencies`, `fx_rates`, `users`.

#### Criterios de aceptación (BDD)
- [ ] **Dado** la migración aplicada **Cuando** consulto `\d audit_events` **Entonces** existen columnas `id, ts, actor, action, entity, entity_id, payload_before, payload_after, diff, source, request_id` con tipos correctos.
- [ ] **Dado** un INSERT en `products` **Cuando** se ejecuta **Entonces** el trigger inserta una fila en `audit_events` con `action='create', entity='products', payload_after`, `actor=auth.uid()`.
- [ ] **Dado** un UPDATE en `products.name_en` de `"X"` a `"Y"` **Cuando** se ejecuta **Entonces** el trigger inserta `action='update', diff={"name_en": ["X","Y"]}`.
- [ ] **Dado** un intento de UPDATE o DELETE sobre `audit_events` **Cuando** se ejecuta **Entonces** falla por constraint (append-only, BR-1a-12, NFR-34).
- [ ] **Dado** una consulta `GET /api/v1/audit?entity=products&entity_id=42` por un Gerente **Cuando** la ejecuta **Entonces** retorna histórico cronológico desc.
- [ ] **Dado** un Comercial **Cuando** ejecuta el GET **Entonces** RLS le deja ver sólo eventos donde es actor (S1 mínimo: deny everything else).

#### Tareas técnicas (subtasks)
- [ ] DB: migración Alembic `0003_create_audit_events.py` con tabla, índices `(entity, entity_id, ts DESC)`, `(actor, ts DESC)`.
- [ ] DB: función PL/pgSQL `audit.log_event()` genérica.
- [ ] DB: trigger `BEFORE INSERT/UPDATE/DELETE` en `products` que llama `audit.log_event()`.
- [ ] DB: regla/trigger que rechaza UPDATE/DELETE en `audit_events`.
- [ ] DB: RLS policies: gerente+ ve todo, comercial ve sólo donde `actor=auth.uid()`.
- [ ] Backend: `app/api/v1/audit.py` con `GET /audit?entity=&entity_id=&from=&to=&cursor=`.
- [ ] Backend: helper `app/services/audit_service.py` con `record_event(...)` para casos donde el trigger no aplica (ej. login).
- [ ] Tests: unit del helper. Integration: insert/update/delete `products` → verificar audit_event creado correctamente. Test de inmutabilidad (UPDATE rechazado).
- [ ] Docs: ADR sobre auditoría append-only + diff format.

#### Dependencias
- Bloqueada por: US-1A-02-01-S1.
- Bloquea a: smoke test del sprint goal (audit_events del INSERT del SKU demo).

#### Mocks / Wireframes
- Referencia: `ux-mockups-mt-pricing-mdm-phase1.md` Pantalla 8 (Detalle SKU · tab Audit) — UI no entra en S1, sólo backend; UI llega en S3.
- Datos test: 5 fixtures de products + simular 10 cambios → 15 audit_events esperados.

#### Endpoints API afectados
- `GET /api/v1/audit` (arquitectura §11 línea 1556).

#### Modelos afectados
- `AuditEvent` (clase SQLAlchemy `app/db/models/audit_event.py`).

#### Observability
- Métricas: `audit_events.count` total, `audit_events.insert_rate` por minuto.
- Logs: cada INSERT propio (pg_log_statement opcional para debug local).
- Error scenarios: trigger falla por excepción → BLOCK la transacción origen (preferimos consistencia sobre disponibilidad para audit).

#### Definition of Ready (DoR) — checklist
- [ ] Mocks revisados con UX/Comercial (N/A — backend only).
- [ ] API contract acordado y mergeado.
- [ ] Modelo SQLAlchemy disponible.
- [ ] Permisos RBAC definidos.
- [ ] Datos test disponibles.
- [ ] No tiene dependencias bloqueantes pendientes.
- [ ] Story points ≤ 8.
- [ ] Aceptación clara con BDD.
- [ ] Owner técnico identificado.

#### Definition of Done (DoD) — checklist
- [ ] Code review aprobado por 2 devs.
- [ ] Tests pasan.
- [ ] Coverage ≥ 80 % en código nuevo.
- [ ] Lint + typecheck OK.
- [ ] Migración Alembic up + down testeada.
- [ ] Deploy a staging exitoso.
- [ ] Smoke test en staging por dev distinto al autor (crear SKU → verificar audit_events).
- [ ] Audit event verificado.
- [ ] Documentación actualizada.
- [ ] PR mergeado a main.
- [ ] Sentry sin errores nuevos sustained.

#### Notas
La función PL/pgSQL `audit.log_event()` será reutilizada por TODAS las tablas auditadas en S2/S3. Diseñar pensando en eso (parámetros vía TG_TABLE_NAME, TG_OP).

#### SP
**3**

#### Sprint asignado
S1.

#### Owner técnico (placeholder)
TBD (idealmente alguien con experiencia PL/pgSQL).

---

### US-1A-07-02-S1 — structlog + Sentry init backend + frontend + healthchecks `/health/live` + `/health/ready`

**Épica**: EP-1A-07 (variante temprana del US-1A-01-06 doc fuente)
**Como** TI Integración
**Quiero** observabilidad mínima funcionando desde S1 (Sentry frontend+backend, logs JSON estructurados, healthchecks)
**Para** que cualquier bug post-deploy a staging sea diagnosticable.

#### Contexto
Hardening must-S1 del production-readiness gap analysis. Sin Sentry, los bugs en staging son ciegos. Sin healthchecks, Caddy no sabe cuándo reiniciar containers. Con esta historia salimos de S1 con observability básica y nos ahorramos refactoring en S3.

#### Criterios de aceptación (BDD)
- [ ] **Dado** un error sin manejar en backend FastAPI **Cuando** ocurre en staging **Entonces** Sentry recibe el evento con `request_id`, `user_id` (si auth), tags (`env=staging`, `service=backend`) y stacktrace.
- [ ] **Dado** un error en el frontend Next.js **Cuando** ocurre **Entonces** Sentry lo captura con sourcemap mapeado.
- [ ] **Dado** cualquier endpoint backend **Cuando** se invoca **Entonces** el log JSON estructurado contiene `ts, level, msg, request_id, actor, entity, action, duration_ms`.
- [ ] **Dado** `GET /health/live` **Cuando** se invoca **Entonces** retorna 200 si el proceso vive (sin chequear DB).
- [ ] **Dado** `GET /health/ready` **Cuando** la DB está accesible y Redis responde **Entonces** retorna 200; **si DB cae** retorna 503 con `{ "checks": { "db": "fail", "redis": "ok" } }`.
- [ ] **Dado** Caddy con healthcheck a `/health/ready` **Cuando** el backend retorna 503 **Entonces** Caddy marca el upstream como unhealthy.

#### Tareas técnicas (subtasks)
- [ ] Backend: `app/core/logging.py` con `structlog` configurado (JSON formatter, contextvars para request_id).
- [ ] Backend: middleware FastAPI que inyecta `request_id` (UUID v7) en cada request y lo agrega al log + response header `X-Request-Id`.
- [ ] Backend: `sentry-sdk[fastapi]` init en `app/main.py` con DSN desde Pydantic Settings, `traces_sample_rate=0.1` en staging.
- [ ] Backend: `app/api/v1/health.py` con endpoints `/health/live` y `/health/ready`. Ready chequea DB (`SELECT 1`) y Redis (`PING`) con timeout 1 s cada uno.
- [ ] Frontend: `@sentry/nextjs` init en `sentry.client.config.ts` y `sentry.server.config.ts`. Sourcemaps se suben en build.
- [ ] Frontend: ErrorBoundary en `app/error.tsx` que captura y reporta a Sentry.
- [ ] Infra: `docker-compose.dev.yml` actualizado con healthcheck en backend container.
- [ ] Tests: unit test que el middleware inyecta request_id. Integration test del health endpoint con DB caída (mock).
- [ ] Docs: README "Cómo configurar Sentry DSN local" + ADR de logging.

#### Dependencias
- Bloqueada por: US-1A-01-01, US-1A-01-08-S1 (health/ready necesita conectar BD).
- Bloquea a: el "smoke test por dev distinto al autor" de TODAS las stories restantes (sin Sentry, no hay forma de saber si hay errores latentes).

#### Mocks / Wireframes
- Referencia: `ux-mockups-mt-pricing-mdm-phase1.md` Pantalla 27 (errores 404/403/500) — UI de error pages se queda fuera de S1, sólo el infra de captura.
- Datos test: error deliberado inyectado en endpoint de prueba para verificar Sentry.

#### Endpoints API afectados
- `GET /health/live`, `GET /health/ready` (arquitectura §11 línea 1325).

#### Modelos afectados
- Ninguno.

#### Observability
- Métricas: `health.ready.duration_ms` p95, `sentry.events.captured` count.
- Logs: cada request loggea start + end con `duration_ms`.
- Error scenarios: la story misma habilita el observabilidad — su DoD verifica que Sentry recibe eventos sintéticos.

#### Definition of Ready (DoR) — checklist
- [ ] Mocks revisados con UX/Comercial (N/A).
- [ ] API contract acordado y mergeado.
- [ ] Modelo SQLAlchemy disponible (N/A).
- [ ] Permisos RBAC definidos (`/health/*` es público).
- [ ] Datos test disponibles.
- [ ] No tiene dependencias bloqueantes pendientes.
- [ ] Story points ≤ 8.
- [ ] Aceptación clara con BDD.
- [ ] Owner técnico identificado.

#### Definition of Done (DoD) — checklist
- [ ] Code review aprobado por 2 devs.
- [ ] Tests pasan.
- [ ] Coverage ≥ 80 % en código nuevo.
- [ ] Lint + typecheck OK.
- [ ] Migración Alembic up + down testeada (N/A).
- [ ] Deploy a staging exitoso.
- [ ] Smoke test en staging por dev distinto al autor (curl `/health/ready`, provocar error y ver Sentry).
- [ ] Audit event verificado (N/A).
- [ ] Documentación actualizada.
- [ ] PR mergeado a main.
- [ ] Sentry sin errores nuevos sustained.

#### Notas
Esta story habilita el resto del DoD. Es candidata #2 a S2 si capacidad obliga, pero genera deuda inmediata. Recomendación: mantener en S1.

#### SP
**5**

#### Sprint asignado
S1.

#### Owner técnico (placeholder)
TBD.

---

## 4. Resumen de SP del sprint

| Story | SP | Comentario |
|-------|----|------------|
| US-1A-01-01 | 5 | Setup repos |
| US-1A-01-04-S1 | 3 | Pre-commit + CI |
| US-1A-01-05 | 8 | Auth E2E |
| US-1A-01-06-S1 | 3 | i18n |
| US-1A-01-08-S1 | 5 | SQLAlchemy + Alembic |
| US-1A-01-09-S1 | 3 | supabase-py dual config |
| US-1A-02-01-S1 | 5 | Modelo `products` + RLS |
| US-1A-02-02-S1 | 5 | Endpoints REST products |
| US-1A-02-03-S1 | 8 | UI listado + detalle |
| US-1A-07-01-S1 | 3 | audit_events + trigger |
| US-1A-07-02-S1 | 5 | structlog + Sentry + healthchecks |
| **TOTAL** | **53 SP** | sobre target 30-40 |

> El total **53 SP** excede el target 30-40 SP. Ver §6 para sugerencia de qué bajar a S2.

## 5. Stories con dependencias críticas (bloqueos)

| Story | Bloqueada por (intra-S1) | Bloqueada por (externa) | Resolución antes de S1 start |
|-------|--------------------------|-------------------------|------------------------------|
| US-1A-01-01 | — | S0-D13 (CI/CD skeleton) | Confirmar S0-D13 done; si no, hacer aquí |
| US-1A-01-04-S1 | US-1A-01-01 | — | Ordering interno |
| US-1A-01-05 (Auth) | US-1A-01-01, US-1A-01-08-S1 | Q-01 (stack firmado), Supabase dev provisioned (S0-D12) | S0-D10 + S0-D12 |
| US-1A-01-06-S1 (i18n) | US-1A-01-01, US-1A-01-05 | — | Ordering interno |
| US-1A-01-08-S1 (SQLAlchemy) | US-1A-01-01 | Supabase dev (S0-D12), S0-D11b validado | Provisioning + ADR-045 firmado |
| US-1A-01-09-S1 (supabase-py) | US-1A-01-01 | S0-D12 | — |
| US-1A-02-01-S1 (`products`) | US-1A-01-08-S1, US-1A-01-05 | Q-03 (PIM real recibido — no bloquea, usa fixtures) | Ordering interno |
| US-1A-02-02-S1 (API products) | US-1A-02-01-S1 | — | Ordering interno |
| US-1A-02-03-S1 (UI products) | US-1A-02-02-S1, US-1A-01-05, US-1A-01-06-S1 | UX mocks Pantalla 2 + 3 firmados | UX firma |
| US-1A-07-01-S1 (audit) | US-1A-02-01-S1 | Q-13 (retención 7y) | Q-13 firmado o default 7y aceptado |
| US-1A-07-02-S1 (Sentry) | US-1A-01-01, US-1A-01-08-S1 | Sentry org+projects creados | TI MT crea cuentas |

## 6. Stories candidatas a S2 si capacity insuficiente

Si capacidad real cierra en 28-32 SP (escenario probable si TI Integración no es FTE), bajar 18-23 SP a S2 en este orden:

1. **US-1A-01-09-S1 (supabase-py dual)** — 3 SP. Sin uso real en S1. Smoke test innecesario hasta que invitemos usuarios o subamos imágenes (S2/S3).
2. **US-1A-01-06-S1 (i18n ES/EN)** — 3 SP. UI con sólo ES funciona perfectamente para los 3 demos S1. Agregar EN en S2 cuando aparezca el primer Comercial que prefiera EN.
3. **US-1A-07-02-S1 (structlog + Sentry)** — 5 SP. No funcional. Riesgo: deploys a staging sin observability. **Mitigación**: si bajamos esta, agregar story de "Sentry mínimo viable" en S2 antes de la primera importación real (US-1A-06-01).
4. **US-1A-02-03-S1 (UI listado + detalle)** — 8 SP. ÚLTIMO recurso. Si bajamos esta, NO hay demo. Equivale a re-scopear el sprint goal.

**Plan B canónico (32 SP)**: bajar #1 + #2 + #3 → S1 = 53 - 11 = **42 SP** (sigue >40). Bajar adicionalmente la mitad de US-1A-02-03 (cortar el form de "Nuevo SKU", crear via API directa) → -3 SP → **39 SP**. Aceptable.

**Plan C agresivo (28 SP)**: Plan B + diferir US-1A-01-04-S1 (pre-commit/CI) a S2 → -3 SP → **36 SP**. NO recomendable: code review se vuelve un infierno sin lint/format automático.

## 7. Tooling / setup pre-Sprint 1 (checklist dev lead)

- [ ] Repos `mt-pricing-frontend`, `mt-pricing-backend`, `mt-pricing-infra` creados con CODEOWNERS, branch protection, PR templates.
- [ ] Doppler proyectos `dev`, `staging`, `prod` configurados con secrets: `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SENTRY_DSN_BACKEND`, `SENTRY_DSN_FRONTEND`, `REDIS_URL`.
- [ ] Hetzner box dev provisionado (Terraform/Ansible aplicado) con Docker + Caddy.
- [ ] Supabase proyectos `dev` / `staging` / `prod` creados con admin invite a equipo. RLS enabled. Extensions `pgvector`, `pg_uuidv7` habilitadas.
- [ ] DNS `dev.mtme.example` apuntando al server Hetzner.
- [ ] Caddy + docker-compose dev arrancando con `https://dev.mtme.example` válido (ACME).
- [ ] OpenAPI spec base (`mt-pricing-backend/openapi.yaml` o auto-FastAPI) mergeado a main con stubs de `/health/live`, `/me`, `/products`.
- [ ] SQLAlchemy + Alembic configurado con primera revisión vacía committed (si S0-D11b validado).
- [ ] CI básico (lint + test) corriendo en PRs (vía US-1A-01-04-S1 o S0-D13).
- [ ] Sentry org + projects (`mt-pricing-backend`, `mt-pricing-frontend`) creados; DSNs en Doppler.
- [ ] 3 usuarios de test seeded en Supabase staging (`comercial+test@`, `gerente+test@`, `ti+test@`).
- [ ] UX firma de Pantallas 2 + 3 (necesarias para US-1A-02-03-S1).

## 8. Riesgos del sprint

| ID | Riesgo | Severidad | Probabilidad | Mitigación |
|----|--------|-----------|--------------|------------|
| R-S1-01 | Q-01 stack no firmado por TI MT antes de S1 start | Alta | Media | Stack queda especulativo; sprint sigue contra Supabase staging "as if" pero con riesgo de retrabajo si TI MT pivota a Java/.NET. **Plan B**: arrancar contra Postgres local + abstracciones que no acoplen a Supabase. |
| R-S1-02 | PIM real no entregado (Q-03) | Media | Media | Stories US-1A-02-XX usan 5 fixtures internos. No bloquea S1, pero retrasa US-1A-06-01 (PIM importer en S2). |
| R-S1-03 | Dev lead nuevo a SQLAlchemy 2.0 async → ramp-up lento | Alta | Alta | Pair programming en US-1A-01-08-S1; Pablo (BR) disponible 4h/sem para review; ejemplos canónicos en `hppt-iom`. |
| R-S1-04 | Supabase Auth + middleware Next.js: integración no trivial | Alta | Media | US-1A-01-05 marcada para split mid-sprint si día 4 no hay `GET /me` verde. Buffer 8 SP en plan. |
| R-S1-05 | Capacidad real < 30 SP si TI Integración no es FTE | Alta | Alta | Q-05 bloquea capacidad real. Aplicar §6 plan B/C. |
| R-S1-06 | UX Pantalla 2/3 no firmados antes del día 1 | Media | Baja | Pablo confirma firma en kickoff; sin firma, US-1A-02-03-S1 baja a S2. |
| R-S1-07 | Sentry account no creada por TI MT antes del sprint | Baja | Media | Self-service tier free funciona; Pablo crea como fallback. |
| R-S1-08 | Pre-commit hooks fallan en Windows del equipo MT | Media | Media | Documentar `git config core.autocrlf` + smoke test en kickoff. |

## 9. Métricas a trackear durante el sprint

- **Velocity real** (SP done) vs estimado (53 SP target / 32 SP realista).
- **Burn-down chart** diario.
- **Stories estado**: backlog → in-progress → in-review → done. Alerta si una story queda > 3 días en in-review.
- **Defect ratio**: bugs detectados (Sentry crit + crítical PR comments) / stories cerradas.
- **Coverage delta**: line coverage antes vs después del sprint.
- **CI build time** p50/p95.
- **Sprint goal viability**: cada miércoles, demo informal del flujo end-to-end. Si rompe, alarma.
- **Q-05 status**: días desde decisión pendiente.

## 10. Sprint 2 preview (alto nivel)

Stories candidatas (con racional):

| Story | SP | Racional |
|-------|----|----------|
| US-1A-02-03 (PUT/PATCH products) | 3 | Editar SKU; ya tienes el listado y detalle |
| US-1A-02-04 (UI tabs Imágenes/Costes/Precios resto) | 8 | Completar la ficha de SKU; depende de US-1A-04-XX y US-1A-02-06 |
| US-1A-02-06 (Bucket `product-images` + signed URLs) | 5 | Imágenes core requirement |
| US-1A-02-07 (Probe + mirror imágenes externas) | 5 | Critical para no depender de hot-links PIM |
| US-1A-02-08 (Thumbnails async via Celery) | 3 | UX rápida en lista |
| US-1A-04-01 (Schemas seeded FBA/FBM/...) | 2 | Inicia EP-1A-04 master de costes |
| US-1A-03-01 (`suppliers` schema) | 2 | Master proveedores arranca |
| US-1A-03-02 (CRUD suppliers UI+API) | 3 | UI primer maestro auxiliar |
| US-1A-06-01 (Importer PIM completo wizard) | 8 | First import real — gating Q-03 |
| US-1A-06-06 (Excel demo importer fixture) | 5 | Fallback si PIM real tarda |
| US-1A-02-09 (Filtros avanzados list) | 3 | Completar listado |
| US-1A-02-10 (Bloqueo DELETE físico) | 2 | VAT-compliance hardening |

**Total candidatos S2**: ~49 SP (aplicar selección a 32-40 SP realistas).

**S2 stretch goals**: traer US-1A-01-06-S1 (i18n) o US-1A-07-02-S1 (Sentry) si bajaron a S2 desde S1.

**S2 MUST**: US-1A-06-01 (importer PIM) si Q-03 destrabado, o US-1A-06-06 (importer fixture) como fallback. Sin un importer en S2, S3 arranca con BD vacía.

---

## Apéndice A — Mapeo de stories del doc fuente vs stories S1

| Doc fuente (epics-and-stories v1.1) | Sprint asignado original | S1 backlog refinado | Cambio |
|-------------------------------------|--------------------------|---------------------|--------|
| US-1A-01-01 (repos scaffolding) | S0 | US-1A-01-01 (S1) | Slip si S0-D13 no done |
| US-1A-01-04 (ADRs firmados) | S0 | — | Queda en S0 |
| US-1A-01-05 (Hetzner) | S0 | — | Queda en S0 |
| US-1A-01-06 (Sentry/healthchecks) | S0 | US-1A-07-02-S1 (S1, expandido) | Adelantado a S1 |
| US-1A-01-07 (Auth Supabase + RBAC) | S0 | US-1A-01-05 (S1) | Adelantado/expandido |
| US-1A-01-08 (SQLAlchemy bootstrap) | S0 | US-1A-01-08-S1 (S1) | Slip si S0-D11b pending |
| US-1A-01-09 (supabase-py dual) | S0 | US-1A-01-09-S1 (S1) | Slip |
| US-1A-02-01 (schema `products`) | S1 | US-1A-02-01-S1 (S1) | Expandido con RLS |
| US-1A-02-02 (POST products) | S1 | US-1A-02-02-S1 (S1) | Combinado con GET |
| US-1A-02-09 (GET list paginado) | S1 | US-1A-02-02-S1 (S1) | Combinado |
| US-1A-02-04 (UI tabs ficha) | S1 | US-1A-02-03-S1 (S1) | Scoped a 1 tab |
| US-1A-07-03 (audit triggers) | S3 | US-1A-07-01-S1 (S1) | Adelantado, scoped a `products` |
| US-1A-07-04 (i18n) | S3 | US-1A-01-06-S1 (S1) | Adelantado |
| (nueva) Pre-commit + CI | — | US-1A-01-04-S1 (S1) | Hardening must-S1 |

## Apéndice B — TODOs / cosas dudadas

1. **Estado real de S0-D13 (CI/CD skeleton)**: si está done, US-1A-01-01 baja a 2 SP (sólo ajustes); si no, queda 5 SP. Confirmar en kickoff.
2. **Supabase plan tier**: free vs pro. Free no tiene daily backup automático, riesgo para staging post-S1. Confirmar con TI MT antes del sprint.
3. **Frontend deploy target**: Hetzner con Caddy proxy a Next.js standalone, o Vercel con redirect a backend Hetzner. ADR-034 dice Hetzner pero no detalla el modo Next.js (standalone vs SSR vs Edge). US-1A-02-03-S1 asume standalone — confirmar.

