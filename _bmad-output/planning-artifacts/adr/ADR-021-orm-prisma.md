# ADR-021: ORM y schema management (Prisma)

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), TI MT

## Contexto

Stack Next.js + Postgres (ADR-001). Necesitamos:
- Schema management con migrations versionadas.
- Type-safety entre DB y código TS.
- Soporte para extensiones Postgres (pgvector, pgcrypto).
- Soporte para triggers / stored procedures (no todo se modela vía ORM, parte vive en SQL nativo).

## Decisión

**Prisma 5.x** como ORM principal + **SQL nativo** (raw SQL en `prisma/migrations/`) para triggers, funciones, vistas materializadas, particionado y constraints complejos.

### Convenciones

- `prisma/schema.prisma` define tablas, columnas, índices, FKs, enums.
- `prisma/migrations/` contiene cada migration con SQL nativo cuando se requiere (Prisma soporta `prisma migrate dev --create-only` para escribir SQL custom).
- Triggers, stored procedures, vistas: SQL nativo en migrations (Prisma no los modela pero los preserva).
- Extensions: definidas en `prisma.schema` con `extensions = [pgcrypto, pg_trgm, pgvector(map: "vector")]`.
- Tipos `VECTOR(1536)` se modelan como `Unsupported("vector(1536)")` (Prisma no tiene tipo nativo Fase 1; se accede vía SQL raw).

### Acceso a datos en código

- Capa **repository** (no acceso directo a `prisma.product.findMany()` desde route handlers o services de dominio).
- Repositories en `src/lib/repositories/{entity}Repository.ts`.
- Métodos retornan tipos del dominio (`Product`, `Price`), no tipos Prisma raw.
- Mapping repo → domain en cada repo (mapper functions).

### Transacciones

- `prisma.$transaction([...])` para batch.
- `prisma.$transaction(async (tx) => { ... })` para transacciones interactivas (imports, recompute).
- Aislamiento por defecto `READ COMMITTED`; `SERIALIZABLE` para flujos con riesgo de race (workflow de aprobación).

### Migrations

- `prisma migrate deploy` en CI/CD (no `migrate dev` en prod).
- Cada migration revisada en PR.
- Migrations destructivas (DROP, ALTER COLUMN type) requieren approval extra del Lead BR.
- Rollback: prisma no rollback automático; cada migration crítica tiene un script de rollback explícito en `prisma/migrations/{ts}_xxx/down.sql`.

### Validación (Zod)

- Validación de input (API + forms): Zod schemas en `src/lib/validation/`.
- Schemas Zod independientes de Prisma (no auto-derivar — derivar pierde control de mensajes y constraints específicos).

## Alternativas evaluadas

### Alternativa A: Drizzle ORM
- **Pros**: más cerca de SQL, menos abstracción, type-safety excelente.
- **Contras**: ecosistema más pequeño, migrations menos maduras (mejorando), menos guides.
- **Veredicto**: opción real; si Prisma frenase con pgvector mucho, migrar.

### Alternativa B: Knex / raw SQL puro
- **Pros**: máximo control.
- **Contras**: sin type safety automática; migrations DIY.
- **Veredicto**: descartada.

### Alternativa C: TypeORM
- **Pros**: maduro, decoradores expresivos.
- **Contras**: API enredada, migrations frágiles.
- **Veredicto**: descartada.

### Alternativa D: Sequelize
- **Pros**: viejo confiable.
- **Contras**: TS support flojo.
- **Veredicto**: descartada.

## Consecuencias positivas

- Type safety alta.
- Schema autodocumentado en `schema.prisma`.
- Migrations versionadas + atómicas.
- Capa repository protege de lock-in (si migra a Drizzle, el cambio queda contenido).

## Consecuencias negativas / riesgos

- Prisma `Unsupported("vector(1536)")` requiere acceso vía `$queryRaw` para queries vectoriales. Mitigación: encapsular en repository.
- Prisma puede ser opinionated en algunos patrones (relations, transactions) — workarounds documentados.
- Performance: el query planner de Prisma a veces no es óptimo; queries complejas se escriben con `$queryRaw` cuando el plan no rinde. Mitigación: monitorear query plans en logs.

## Cuándo revisar

- **Cierre Fase 1b**: medir performance Prisma vs SQL puro en queries críticas (recálculo masivo).
- **Si Drizzle alcanza estabilidad superior** y ahorra 20%+ en queries: considerar migración Fase 2.
