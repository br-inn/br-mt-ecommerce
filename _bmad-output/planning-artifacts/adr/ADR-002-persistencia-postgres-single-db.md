# ADR-002: Persistencia — PostgreSQL single-DB para PIM y Pricing

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT

## Contexto

El sistema Fase 1 maneja tres dominios fuertemente acoplados:
1. **PIM** (productos, traducciones, imágenes).
2. **Master de costes** (proveedores, costes desglosados por SKU × esquema).
3. **Pricing** (precios por canal × esquema, reglas, aprobaciones, audit, FX).

Cada coste afecta al precio en cascada; cada precio depende de FX as-of; cada aprobación referencia un SKU + canal + esquema. Todas las consultas operativas y reportes necesitan **JOIN cross-dominio** (ej. "todos los SKUs con margen FBA < 8 % y traducción AR pendiente").

Decisión a tomar: ¿PIM y Pricing en una sola DB Postgres, o separar (PIM-DB + Pricing-DB)?

## Decisión

**Single PostgreSQL database** con schemas lógicos opcionales (`public` por defecto; `pim`, `pricing`, `audit` si se prefiere agrupación). Todas las tablas en el mismo cluster, mismas transacciones, mismas FKs cross-dominio.

## Alternativas evaluadas

### Alternativa A: Two databases (PIM-DB + Pricing-DB) con replicación / event sourcing
- **Pros**: separación de despliegue independiente, escalado independiente, aislamiento de fallos, equipos separables a futuro.
- **Contras**: para 224 SKUs y un equipo BR, prematuro. JOINs cross-DB obligan a duplicar datos o sincronizar via eventos → doble fuente de verdad → riesgo de drift. Audit cross-dominio se complica. Recálculo masivo (objetivo < 60 s) cruza ambos dominios → latencia de red entre DBs.
- **Veredicto**: rechazada por now. Si Fase 4 pide multi-region, se considera shard o read replicas, no DB split.

### Alternativa B: Single DB + schemas separados (`pim`, `pricing`, `audit`, `auth`)
- **Pros**: misma DB pero separación lógica clara; permite GRANT/REVOKE granular; útil para auditoría regulatoria UAE 2026.
- **Contras**: ligero overhead en herramientas (Prisma puede manejarlo pero requiere `multiSchema` preview feature en algunas versiones).
- **Veredicto**: **adoptada como sub-decisión**: usaremos `public` por defecto para Fase 1 simplicidad, y si TI MT exige separación regulatoria, se migra a multi-schema sin cambiar el modelo.

### Alternativa C: NoSQL (MongoDB / DynamoDB) para PIM + Postgres para Pricing
- **Pros**: PIM con specs JSONB-like flexible; documentos por SKU.
- **Contras**: Postgres ya soporta JSONB con índices GIN para specs. NoSQL pierde transacciones cross-dominio, FKs, constraints, audit triggers. Para 224 SKUs no aporta nada.
- **Veredicto**: descartada.

## Consecuencias positivas

- Transacciones ACID cross-dominio (un import de costes + recálculo de precios + audit en una sola transacción).
- FKs reales entre `prices`, `costs`, `products`, `channels` — integridad referencial.
- Triggers de audit nativos cubren todas las tablas críticas con un solo mecanismo.
- Reportes y queries operativas son SQL plano sin federación.
- Backup/restore atómico de todo el sistema.
- Footprint operativo mínimo (un solo cluster que monitorear, un solo schema migration tool).

## Consecuencias negativas / riesgos

- Si Fase 4 pide multi-region o multi-tenant, una DB monolítica es pasivo. Mitigación: el modelo está pensado single-tenant y eso está fijado por ADR-014; si cambia, se rediseña.
- Single point of failure operacional. Mitigación: managed Postgres (AWS RDS / Azure Postgres / Supabase managed) con HA y backups automáticos; RPO 1 h / RTO 4 h objetivo.
- Crecimiento de tablas de audit puede impactar performance. Mitigación: particionado por mes en `audit_events` desde el día uno; archivado a cold storage tras N meses.

## Cuándo revisar

- **Cierre Fase 2** (con inventarios + facturación añadidos): re-evaluar si single-DB sigue siendo apropiada o si conviene separar `inventory` por carga transaccional.
- **Si superamos 1M filas en `prices` o `audit_events`**: evaluar particionado, read replicas o split.
- **Si TI MT exige separación regulatoria**: migrar a multi-schema.
