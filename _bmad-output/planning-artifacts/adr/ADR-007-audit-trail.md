# ADR-007: Audit trail (tabla audit_events + triggers Postgres)

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT

## Contexto

VAT UAE 2026 + e-invoicing exigen trazabilidad de cada decisión de precio: autor, aprobador, timestamp, regla aplicada, breakdown de costes. La FTA UAE puede pedir auditoría retroactiva.

Más allá del compliance, el equipo necesita responder en operación: "quién subió este coste el día X", "por qué se rechazó este precio".

## Decisión

### Tabla central `audit_events`

```sql
CREATE TABLE audit_events (
    id              BIGSERIAL PRIMARY KEY,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor_id        UUID NULL,                          -- NULL = sistema / cron / connector
    actor_email     TEXT NULL,                          -- snapshot del email al momento
    actor_role      TEXT NULL,                          -- snapshot del rol activo
    entity_type     TEXT NOT NULL,                      -- 'product' | 'price' | 'cost' | ...
    entity_id       TEXT NOT NULL,                      -- usar TEXT por flexibilidad de PKs
    action          TEXT NOT NULL,                      -- 'create' | 'update' | 'delete' | 'approve' | ...
    before          JSONB NULL,
    after           JSONB NULL,
    diff            JSONB NULL,                         -- delta calculada
    reason          TEXT NULL,                          -- texto opcional (obligatorio en reject)
    rules_evaluated JSONB NULL,                         -- snapshot de reglas de excepción evaluadas
    request_id      UUID NULL,                          -- correlation id HTTP
    ip              INET NULL,
    user_agent      TEXT NULL
) PARTITION BY RANGE (occurred_at);

CREATE INDEX idx_audit_entity ON audit_events (entity_type, entity_id, occurred_at DESC);
CREATE INDEX idx_audit_actor  ON audit_events (actor_id, occurred_at DESC);
CREATE INDEX idx_audit_action ON audit_events (action, occurred_at DESC);
```

Particionado por mes desde el día 1: `audit_events_2026_05`, `audit_events_2026_06`, ...

### Mecanismo de captura

**Doble vía** (defense in depth):

1. **Triggers Postgres** sobre tablas críticas (`products`, `product_translations`, `costs`, `prices`, `channels`, `fx_rates`, `exception_rules`, `users`, `user_roles`):
   - Función `audit_row_change()` que inserta una fila en `audit_events` en cada `INSERT`/`UPDATE`/`DELETE`.
   - El `actor_id` se obtiene de un GUC custom `app.current_actor_id` que el backend setea en cada conexión (`SET LOCAL app.current_actor_id = '<uuid>'`).
   - Si `app.current_actor_id` está vacío, se registra `actor_id = NULL` con `actor_role = 'system'`.

2. **Audit a nivel servicio** (capa app) para acciones sin DML directo (login, logout, export trigger, recompute job, connector emit). Estas se insertan vía service `AuditService.log(...)` desde código.

### Qué se registra

- Todas las **mutaciones DML** de las tablas críticas (vía trigger).
- Todas las **acciones de workflow**: `propose`, `approve`, `reject`, `revise`, `export`.
- Todas las **acciones administrativas**: cambio de regla de excepción, cambio de FX, alta/baja de usuario, asignación de rol.
- Todas las **operaciones de import**: comienzo, fin, count, errores, conflicto resolvido.
- Todos los **logins y logouts** (incluyendo failed logins por brute-force detection).
- Todos los **exports** y **publicaciones a connectors** (Fase 3+).

### Qué NO se registra

- Reads (no auditamos lectura — no exigido por VAT UAE 2026; si MT lo pide se añade Fase 2).
- Cambios de UI prefs, locale, etc. (no relevante).

### Retención

- **Hot** (Postgres): 24 meses de particiones online.
- **Cold** (S3 / Glacier): particiones > 24 meses se vuelcan a parquet a S3, encriptadas, con manifest. Restorables on-demand.
- **Mínimo legal**: 5 años (VAT UAE typical retention) — toda la cold storage debe sobrevivir 5 años.

### Acceso

- Sólo `gerente_comercial` y `admin` pueden leer `audit_events` vía UI.
- Endpoint API `/api/audit/...` con paginación cursor-based, filtros (entity, actor, action, range temporal).
- TI MT y BR Innovation tienen acceso directo a la DB (read replica) para investigación / soporte.
- Audit del audit: cualquier acceso a `audit_events` se loguea en log estructurado app (no recursivo en la propia tabla, para evitar loop).

### Inmutabilidad

- Postgres GRANT: `audit_events` es `INSERT-only` para el rol de aplicación. `UPDATE` y `DELETE` revocados.
- Sólo el rol superusuario / `admin` puede borrar (sólo en operación de archivado mensual).
- Hash chain (opcional Fase 2): cada fila incluye `prev_hash` + `current_hash` para detectar tampering. Fase 1 sin hash chain (overkill); evaluable Fase 2 si TI MT exige.

## Alternativas evaluadas

### Alternativa A: Audit sólo en código (sin triggers)
- **Pros**: simplicidad — un único entry point.
- **Contras**: cualquier acceso directo a la DB (script, debug, hotfix) bypasa el audit. Riesgo regulatorio.
- **Veredicto**: descartada — la doble vía es defense in depth.

### Alternativa B: Sistema externo (Datadog audit, AWS CloudTrail equivalent, ElasticSearch)
- **Pros**: separación física de la DB → tampering más difícil.
- **Contras**: ingestión async puede perder eventos; reportes para FTA requieren join con DB principal; coste adicional.
- **Veredicto**: descartada Fase 1; puede añadirse Fase 2 como destino secundario.

### Alternativa C: Event sourcing (toda la DB es eventos, estado actual derivado)
- **Pros**: audit es la fuente de verdad por construcción.
- **Contras**: cambio masivo de paradigma; query operativa más cara; overkill.
- **Veredicto**: descartada.

## Consecuencias positivas

- Compliance VAT UAE 2026 desde el día 1.
- Defense in depth (triggers + service).
- Particionado evita degradación de performance.
- Inmutabilidad por GRANT impide tampering accidental.

## Consecuencias negativas / riesgos

- Triggers añaden latencia de escritura (~ 1-3 ms por DML). Aceptable para 224 SKUs.
- JSONB de `before`/`after` puede ser grande para imports masivos (1000s filas). Mitigación: import bulk loguea 1 fila resumen + N filas por SKU sin payload completo si excede 100kB.
- Particionado requiere maintenance job (crear partición next-month con cron). Se automatiza con `pg_partman` o trigger.

## Cuándo revisar

- **S3** (cuando se implementa): probar volumen real de eventos por día, ajustar particionado si hace falta.
- **Cierre Fase 1b**: validar lectura de audit con el Gerente Comercial; ajustar UI si es ilegible.
- **Antes de Fase 3** (publicación externa): re-evaluar hash chain por riesgo regulatorio incrementado.
- **Auditoría externa primera FTA**: validar que el formato exportado satisface al auditor.
