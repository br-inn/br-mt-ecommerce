# ADR-031: DB Supabase Postgres con RLS + pgvector + uuidv7

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT
- Supersedes: ADR-002 (parcial — single Postgres DB), ADR-021 (parcial — ORM)

## Contexto

La plataforma MT Middle East requiere una base de datos relacional con:

- ACID transactions cross-dominio (PIM + Pricing + Audit).
- Row Level Security (RLS) para enforce parcial de RBAC en BD (defense in depth).
- pgvector para embeddings (research del comparador, Fase 1.5+).
- uuidv7 para PK con orden temporal natural.
- Particionado declarativo para tablas grandes (`audit_events`, `prices_history`).
- Auth + Storage gestionados sin construir tooling propio.

El stack histórico (ADR-002) usaba PostgreSQL "managed o self-hosted" sin tooling integrado.

## Decisión

**Adoptar Supabase Postgres** (alineado con hppt-iom — a verificar contra el repo de referencia).

| Aspecto | Decisión |
|---------|----------|
| Plataforma | Supabase managed (Postgres + Auth + Storage + Realtime + Edge Functions opcionales) |
| Versión Postgres | la que ofrece Supabase actual (≥ 15) |
| Extensiones | `pgcrypto`, `pg_trgm`, `pgvector`, `pg_uuidv7` |
| PK convention | `id UUID DEFAULT uuidv7()` en todas las tablas |
| RLS | habilitada en todas las tablas con datos de usuario; policies por rol referencian `auth.uid()` y `user_roles` |
| Migrations | bajo `supabase/migrations/` (estilo hppt-iom, ~132 migrations como orden de magnitud — alineado con hppt-iom (a verificar)) |
| Particionado | declarativo por mes en `audit_events`, `prices_history` |
| ORM backend | SQLAlchemy 2.0 + Alembic (Alembic complementa para cambios de modelo backend; migrations principales SQL bajo `supabase/migrations/`) |
| pgvector dim | a definir en research spike de comparación (hppt-iom usa 768 con Gemini; este proyecto puede usar otra dim según el modelo elegido) |
| Backups | Supabase WAL streaming (PITR managed) + dumps lógicos diarios cifrados a Supabase Storage / S3 externo |

## Alternativas evaluadas

- **Postgres self-host en Hetzner**: mayor control, pero hay que construir Auth + Storage + tooling backup; tiempo y costo no justificados Fase 1.
- **AWS RDS + Cognito + S3**: más caro, menos integrado, fuera del alineamiento BR.
- **Neon / Crunchy Bridge**: alternativas managed razonables; Supabase gana por la integración con Auth y Storage out-of-the-box.

## Consecuencias positivas

- **Auth + Storage + Postgres en un solo BaaS** → reduce piezas a operar.
- **RLS** enforce parcial de RBAC en BD — defense in depth con backend FastAPI.
- **pgvector activo** desde día 1 (sin esperar Fase 1.5+) — embeddings cuando research lo determine.
- **uuidv7** → orden temporal natural, mejor locality que uuid v4, simplifica cursors de paginación.
- **Migrations versionadas** estilo hppt-iom → review en PR, rollback claro.
- Alineado con hppt-iom.

## Consecuencias negativas / riesgos

- **Lock-in parcial a Supabase** → mitigación: la mayoría es Postgres puro; Auth y Storage sí son específicos.
- **Residencia UAE** → Supabase ofrece regiones limitadas; si TI MT exige UAE, evaluar Supabase región más cercana o self-host (ADR-020 open).
- **Costo mensual managed** → evaluar tier vs costo self-host conforme escala.
- **`supabase/migrations/` + Alembic** → dos sistemas que coexisten; necesita disciplina (alinear con hppt-iom — a verificar).

## Cuándo revisar

- **S0**: confirmar plan Supabase (Free / Pro / Team / Enterprise) y región.
- Cuando catálogo > 50k SKUs o usuarios > 100, evaluar tier upgrade o self-host.
- Antes de Fase 2.5 (IA): confirmar dim de pgvector y benchmark HNSW.
