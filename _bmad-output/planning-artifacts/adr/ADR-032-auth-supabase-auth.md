# ADR-032: Auth Supabase Auth

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT
- Supersedes: ADR-005 (parcial — mecanismo de auth; matriz RBAC sigue vigente)

## Contexto

El stack histórico proponía **Auth.js v5** sobre Next.js. Con el pivot a backend separado FastAPI (ADR-029) y Supabase Postgres (ADR-031), Auth.js deja de ser óptimo:

- Auth.js está acoplado a Next.js. Con backend FastAPI, la verificación JWT debe hacerse en Python.
- Supabase Postgres ya viene con Supabase Auth integrado (managed).
- RLS policies en BD requieren `auth.uid()` que Supabase Auth provee nativamente.

## Decisión

**Adoptar Supabase Auth como mecanismo de autenticación.**

| Aspecto | Decisión |
|---------|----------|
| Providers Fase 1 | email + password, magic link |
| Providers opcionales | Google, Microsoft (OAuth) si TI MT lo solicita |
| MFA | TOTP nativo de Supabase Auth — recomendado para `admin` y `gerente_comercial` |
| Sesiones | JWT firmado por Supabase, gestionado por el cliente Supabase en frontend |
| Verificación backend | FastAPI verifica JWT con la clave pública / JWKS de Supabase (cache + rotación) |
| RLS en BD | policies por rol referencian `auth.uid()` y join con `user_roles`/`role_assignments` |
| Lockout | gestionado por Supabase Auth (rate limit por email + IP) + audit en `audit_events` vía webhook |
| Password policy | mínimo 12 chars, mix lower/upper/dígito/símbolo (configurable en Supabase) |
| Reset | Supabase magic link con TTL 30 min |

**Defense in depth (dos capas)**:

1. **Backend FastAPI** verifica JWT y aplica `Depends(require_permission(...))`.
2. **DB RLS** bloquea SELECT/UPDATE/DELETE no autorizado incluso si un bug skipea el dependency.

La **matriz RBAC** (3 roles operativos + admin) de ADR-005 sigue vigente; lo que cambia es la implementación.

## Alternativas evaluadas

- **Auth.js v5 (NextAuth)** (ADR-005 original): acoplado a Next.js; con backend FastAPI requiere bridge JWT manual.
- **Keycloak**: más control pero pesado para 3-10 usuarios; operación significativa.
- **Auth0 / Clerk**: managed alternativos; más caros y desalinean con hppt-iom.
- **Self-rolled** (passlib + python-jose): rechazado — Supabase resuelve mejor.

## Consecuencias positivas

- **Integración nativa con Supabase Postgres + RLS** → `auth.uid()` disponible en policies sin glue.
- **MFA, magic links, OAuth** out-of-the-box.
- **Webhooks** de eventos auth para audit.
- **Alineado con hppt-iom**.

## Consecuencias negativas / riesgos

- **Lock-in a Supabase Auth** → si se migra fuera de Supabase, hay que reemplazar Auth + RLS + Storage.
- **Residencia datos auth** → mismo trade-off que ADR-031.
- **Verificación JWT en backend** requiere mantener cache de JWKS de Supabase actualizada.

## Cuándo revisar

- **S0 — gating**: TI MT firma stack.
- Si Supabase no cumple residencia UAE, considerar Keycloak self-host.
- Antes de Fase 4 (portal B2B distribuidores): re-evaluar capacidades de invitations / org-level access.
