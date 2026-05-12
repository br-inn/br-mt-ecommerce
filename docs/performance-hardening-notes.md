# Performance Hardening — US-1B-05-06

## Índices añadidos (migración 20260512_077)

### Tabla `prices`

| Índice | Columnas | Tipo | Razón |
|--------|----------|------|-------|
| `idx_prices_channel_status` | `(channel_id, status)` | btree | Listado de precios pendientes por canal (pantalla 14 — cola aprobación gerente) |
| `idx_prices_updated_at` | `(updated_at DESC)` | btree | Orden cronológico inverso en list_prices con filtros |
| `idx_prices_escalated` | `(escalated)` WHERE `escalated = true` | btree partial | Dashboard gerente: precios escalados pendientes |
| `idx_exception_rules_active_channel` | `(active, channel_id)` | btree | ExceptionEvaluator filtra reglas activas por canal o globales (channel_id IS NULL) |
| `idx_match_candidates_label` | `(label)` WHERE `label IS NOT NULL` | btree partial | Queries training data: filtrar accept/reject/skip |
| `idx_audit_events_entity_type_event_at` | `(entity_type, event_at DESC)` | btree | Timeline por tipo sin entity_id (ej. "todos los price events últimas 24h") |

### Índices NO creados (ya existen)

- `prices.status` — índice implícito (`index=True` en modelo)
- `prices.product_sku` — índice implícito (`index=True` en modelo)
- `idx_prices_pending` — partial WHERE `status IN ('pending_review','draft')`
- `idx_prices_lookup` — `(product_sku, channel_id, scheme_code)`
- `idx_prices_active` — partial WHERE `valid_to IS NULL`
- `idx_match_candidates_confidence` — creado en mig 074
- `idx_audit_entity/actor/action/request` — todos presentes en el modelo

## Queries optimizadas

No se detectaron N+1 ni SELECT * sin LIMIT en `pricing.py` ni `matches.py`. Ambas rutas usan repositorios con paginación cursor-based y `service.*` encapsula los queries. No se modificaron routes.

## Medir p95 en producción

```sql
-- Activar timing y plan detallado
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT id, status, amount, updated_at
FROM prices
WHERE channel_id = '<uuid>'
  AND status IN ('pending_review', 'auto_approved')
ORDER BY updated_at DESC
LIMIT 50;
```

Para medir p95 con pgBadger o `pg_stat_statements`:

```sql
SELECT
  query,
  calls,
  mean_exec_time,
  percentile_cont(0.95) WITHIN GROUP (ORDER BY total_exec_time / calls) AS p95_ms
FROM pg_stat_statements
WHERE query ILIKE '%prices%'
ORDER BY p95_ms DESC
LIMIT 20;
```

Reiniciar estadísticas antes de una prueba de carga: `SELECT pg_stat_statements_reset();`
