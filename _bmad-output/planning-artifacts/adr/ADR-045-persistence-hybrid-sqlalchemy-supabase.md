# ADR-045: Persistencia híbrida — SQLAlchemy 2.0 async para core + supabase-py para Auth/Storage

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT
- Supersedes: aclara ADR-031 (DB Supabase Postgres) sobre la capa de acceso

## Contexto

`hppt-iom-review_1` usa **`supabase-py` puro** sin ORM (decisión histórica para minimizar piezas). Para MT, la complejidad es mayor:

- Motor de pricing multi-canal × multi-esquema con JOINs entre `products × prices × costs × fx_rates × audit_events × exception_rules`.
- Comparador con hybrid search (lexical + vectorial + RRF + reglas duras), window functions, ranking.
- Audit trail con triggers y consultas analíticas.
- Roadmap GraphRAG (Fase 2.5+) con queries complejas combinando Postgres + Neo4j.

`supabase-py` puro escala bien para CRUD simple (caso hppt-iom: emails + KB curado + advisor) pero entrega poco type-safety y testing pobre cuando la lógica de datos crece.

## Decisión

**Enfoque híbrido por responsabilidad:**

| Capa | Tecnología |
|------|------------|
| Core data (CRUD complejo, queries multi-tabla, motor pricing, comparador, audit analytics) | **SQLAlchemy 2.0 async + Alembic** |
| Auth (login, JWT, magic links, password reset) | **supabase-py + Supabase Auth nativa** |
| Storage (imágenes, fichas técnicas, exports, imports) | **supabase-py + Supabase Storage** |
| Admin de usuarios (force-logout, reset, role assignment) | **supabase-py `auth.admin`** |
| RLS policies | **Postgres puro** (definidas en migraciones Alembic Y/O Supabase migrations) |
| Migraciones de schema | **Alembic + Supabase CLI en paralelo** (Alembic para tablas aplicativas; Supabase migrations para `auth.*`, `storage.*`, RLS de `public.*` cuando convenga) |

El backend FastAPI usa **dos clientes**:
- `app/core/db.py` → SQLAlchemy async engine + sessions con asyncpg.
- `app/core/supabase.py` → cliente `supabase-py` para Auth + Storage.

La app se conecta a Postgres con un **rol específico** (no `service_role` ni `anon`) que respeta las RLS policies — defense in depth: aunque alguien evada lógica de aplicación, RLS bloquea.

## Alternativas evaluadas

### Alt 1: `supabase-py` puro (1:1 con hppt-iom)
- **Pros**: alineación máxima con hppt; reuso 1:1 de patrones; menos piezas.
- **Contras**: zero type-safety en queries; tests complejos (mockear supabase-client); JOINs multi-tabla y window functions a mano son frágiles; pricing engine y comparador escalan mal.
- **Veredicto**: rechazada — la complejidad de MT (pricing + comparador + GraphRAG) excede lo que `supabase-py` resuelve cómodamente.

### Alt 2: SQLAlchemy puro sin Supabase Auth/Storage
- **Pros**: stack 100 % autocontrolado; no lock-in con Supabase Auth.
- **Contras**: reescribir Magic Links, MFA, password reset, JWT validation, Storage signed URLs ≈ +10-15 SP sin ganancia; pierde el patrón completo de hppt para Auth.
- **Veredicto**: rechazada — Supabase Auth + Storage son commodities valiosos; reescribirlos no aporta.

### Alt 3: Híbrido (decisión adoptada)
- **Pros**: type-safety donde importa (core data); reuso de Auth/Storage hppt; RLS como defense-in-depth; tests testeables; migraciones versionadas Alembic.
- **Contras**: dos clientes en el backend; doble fuente de verdad de schema (Alembic + Supabase migrations) — mitigable con disciplina; curva de aprendizaje SQLAlchemy 2.0 async para devs nuevos.
- **Veredicto**: ADOPTADA.

## Consecuencias positivas

- Type-safety + autocomplete IDE en queries críticas (pricing, comparador, audit).
- Tests robustos con pytest + asyncpg + testcontainers Postgres (o pgTAP para RLS).
- Migraciones Alembic auto-generadas desde modelos.
- RLS sigue activo: si la app falla en autorización, la BD bloquea.
- Reuso de Auth y Storage hppt sin reescribir.
- GraphRAG futuro: SQLAlchemy + neo4j-driver coexisten limpios (ADR-038/039).

## Consecuencias negativas / riesgos

- Dos sources of truth para schema. Mitigación: convención clara — `auth.*` y `storage.*` son territorio Supabase; `public.*` es territorio Alembic; RLS se versiona con la tabla a la que aplica.
- Devs nuevos a SQLAlchemy 2.0 async: ramp-up. Mitigación: convenciones del proyecto en `CONTRIBUTING.md` con ejemplos canónicos de repository pattern + query builders.
- RLS y SQLAlchemy: si la app conecta como `service_role`, bypassa RLS. Mitigación: rol específico `mt_app` con privilegios mínimos + assertions en tests.
- Alineación parcial con hppt-iom: ~80 %. Mitigación: el 20 % faltante (core data) es exactamente lo que hppt no necesitó por su dominio simpler — la divergencia es justificada.

## Cuándo revisar

- Si en S2 (cierre Fase 1a) se observa que SQLAlchemy 2.0 async genera más fricción de la esperada (devs incómodos, tests lentos), reevaluar para Fase 1b.
- Si Supabase libera un client TypeScript-grade type-safe para Python (improbable corto plazo), reconsiderar.
- Si MT decide pivotar a otra DB (Aurora, Yugabyte, etc.), reevaluar la capa Auth/Storage.
