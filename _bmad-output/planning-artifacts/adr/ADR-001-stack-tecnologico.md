# ADR-001: Stack tecnológico (Next.js + PostgreSQL) — HISTÓRICO

- Status: **superseded by ADR-028..ADR-035** (2026-05-06)
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT
- Supersedes: —
- Superseded by: ADR-028 (Frontend Next.js 16 + React 19), ADR-029 (Backend FastAPI Python 3.11), ADR-030 (Worker Celery + Redis), ADR-031 (Supabase Postgres + RLS + pgvector + uuidv7), ADR-032 (Supabase Auth), ADR-033 (Supabase Storage), ADR-034 (Hetzner + Docker Compose prod), ADR-035 (Caddy reverse proxy).

> **Nota**: Esta ADR queda como referencia histórica. El stack se pivotó a la arquitectura de referencia BR Innovation `hppt-iom`: frontend Next.js 16 + backend FastAPI + Supabase + Celery + Redis + Hetzner + Docker Compose + Caddy. La sección "Consecuencias" del documento original aplica al stack histórico; las consecuencias del stack vigente se documentan en los ADRs sucesores.

## Contexto

El master doc original proponía Shopify Advanced + Supabase + Make.com como stack del programa MT Middle East. El cliente descartó ese stack y pidió redefinirlo para Fase 1 (PIM + master de costes + pricing + workflow de aprobación). Necesitamos un stack que:

- Permita control total del modelo de datos (no Shopify-as-DB).
- Soporte i18n (EN canónico + ES + AR), audit trail denso, RBAC y workflow de estado.
- Sea operable single-tenant para uso interno MT (3-10 usuarios concurrentes Fase 1, 224 SKUs hoy, 5k-50k SKUs visión 2-3 años).
- Deje hooks para IA (embeddings) sin pagar coste hoy.
- Sea factible para BR Innovation entregar y mantener.
- Pueda ser firmado por TI MT en Sprint 0 (puede pedir cambios — esta decisión es reversible hasta firma).

## Decisión

Stack propuesto (sujeto a firma TI MT en S0):

| Capa | Tecnología | Versión target |
|------|------------|----------------|
| Frontend + Backend monorepo | Next.js (App Router) + React + TypeScript | Next.js 15.x, React 19.x, TS 5.x |
| UI kit | shadcn/ui + Tailwind CSS | Tailwind 3.4+ |
| i18n cliente | next-intl | latest LTS |
| API | Next.js Route Handlers (REST) + Zod validation | — |
| Auth | Auth.js (NextAuth) v5, credenciales + sessions JWT | v5.x |
| ORM | Prisma | 5.x |
| Base de datos | PostgreSQL | 16.x |
| Extensiones DB | `pgcrypto`, `uuid-ossp`, `pg_trgm`, `pgvector` (reservada, no activada Fase 1) | — |
| Cola de jobs | BullMQ + Redis | BullMQ 5.x, Redis 7.x |
| Object storage | S3-compatible (Cloudflare R2 default; AWS S3 si TI MT lo exige) | — |
| Observabilidad errores | Sentry SaaS | — |
| Logging | Pino → STDOUT JSON estructurado | Pino 9.x |
| CI/CD | GitHub Actions | — |
| Testing | Vitest (unit) + Playwright (e2e) | Vitest 1.x, Playwright 1.45+ |

**Criterios de decisión aplicados** (orden de prioridad):
1. Tiempo a primer entregable utilizable (Fase 1a en ~6-8 sem).
2. Control sobre el modelo de datos relacional (no SaaS-as-DB).
3. Single language en frontend + backend reduce coste de mantenimiento BR.
4. Postgres es lingua franca de MT España (PIM/ERP) — facilita Fase 2 de integración bidireccional.
5. Hooks IA (pgvector) sin reescritura.

## Alternativas evaluadas

### Alternativa A: NestJS (backend) + Next.js (frontend) separados
- **Pros**: separación clara backend/frontend, modular, decoradores expresivos para RBAC/validation.
- **Contras**: dos repos / dos pipelines / dos despliegues; doble overhead para un equipo BR pequeño; tracking de tipos cross-stack más caro; sin ganancia funcional para 224 SKUs.
- **Veredicto**: descartada salvo que TI MT exija backend dedicado.

### Alternativa B: .NET 8 + Blazor / ASP.NET Core
- **Pros**: si TI MT España opera en stack Microsoft, alineamiento de skills.
- **Contras**: BR Innovation no es shop .NET por defecto; ecosistema i18n + workflow + cola más fragmentado; menos librerías mid-market off-the-shelf para PIM/audit; tiempo de bootstrap mayor.
- **Veredicto**: queda como opción de respaldo si TI MT MENA / España exige .NET en S0.

### Alternativa C: Python + Django + DRF + Celery + Postgres + React (separado)
- **Pros**: el motor de pricing v5.1 ya está en Python — port directo posible; Django Admin acelera CRUD/audit; Celery + Redis para colas.
- **Contras**: dos lenguajes (Python backend + TS frontend) duplican modelos/types; Django Admin es feo para uso de negocio externo; Auth + RBAC + i18n requieren más glue; team velocity menor para BR.
- **Veredicto**: opción razonable; el motor v5.1 se reescribe en TypeScript independientemente del stack elegido (las reglas son reglas, no Python).

### Alternativa D: Akeneo / Pimcore / Odoo (suites)
- Descartadas a nivel programa (ver brief y ADR-015).

## Consecuencias positivas

- Un solo repo, un solo lenguaje (TypeScript), un solo despliegue inicial → velocidad alta para BR.
- Postgres como single source de verdad — control total de constraints, triggers, audit, FX, RBAC.
- pgvector reservado abre Fase 1.5+ sin migración de stack.
- Auth.js + Prisma + Zod cubren auth + ORM + validation con baja fricción.
- Stack atractivo para reclutar refuerzos si MT crece el equipo.

## Consecuencias negativas / riesgos

- TI MT puede rechazar el stack (riesgo principal — gating S0). Mitigación: documento de criterios y alternativas listas; ADR es **proposed**, no **accepted**, hasta firma.
- Next.js App Router + Auth.js v5 son relativamente recientes; algunos breaking changes esperables.
- Single Node.js process puede ser limitante si se necesitan workers heavy CPU (pricing recálculo masivo) — mitigado vía BullMQ + worker process separado.
- Equipo MT post-handoff necesitará perfil TS/Postgres; si no existe, se contrata o se externaliza mantenimiento BR.

## Cuándo revisar

- **S0 — gating obligatorio**: TI MT firma o pide alternativa. Si pide alternativa, esta ADR se reemplaza y el resto del documento de arquitectura se ajusta antes de S1.
- **Cierre Fase 1b**: revisar si la elección sostiene volumen real esperado en Fase 2 (5k-50k SKUs, integración con PIM España, B2B portal).
- **Antes de Fase 2.5** (capa IA): re-evaluar si pgvector + HNSW basta o si conviene servicio dedicado (Pinecone, Qdrant).
