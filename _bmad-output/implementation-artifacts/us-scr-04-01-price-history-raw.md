# US-SCR-04-01 — TimescaleDB Hypertable + price_daily_stats Continuous Aggregate

**Status**: review
**Sprint**: S14
**Story Points**: 8

## Implementación

> TimescaleDB no disponible en la instancia local → se usa tabla particionada nativa PG (PARTITION BY RANGE) como especifica la story (fallback oficial).

### Archivos creados/modificados

- **`mt-pricing-backend/alembic/versions/20260601_134_price_history_raw.py`** — migración:
  - Tabla `price_history_raw` particionada por `RANGE(scraped_at)`
  - Particiones físicas: `price_history_raw_2026`, `price_history_raw_2027`
  - Índices en (match_id, marketplace, scraped_at) + (sku, scraped_at)
  - Vista materializada `price_daily_stats` con min/max/avg/close por (match_id, marketplace, date)
  - Índice único en `price_daily_stats(match_id, marketplace, stat_date)` para REFRESH CONCURRENTLY
  - `ALTER competitor_brands ADD COLUMN monitoring_active BOOLEAN DEFAULT false`
  - Seed `job_definitions`: `refresh_price_daily_stats` (cron: `0 * * * *`, queue: scraper.price_monitor)
- **`mt-pricing-backend/app/db/models/price_history.py`** — modelo `PriceHistoryRaw`
- **`mt-pricing-backend/app/db/models/__init__.py`** — exporta `PriceHistoryRaw`

### Alembic
- `down_revision = "20260531_133"` ✓
- Único HEAD: `20260601_134` ✓
- Migración ejecutada correctamente en contenedor local

## Verificación
```
$ docker exec mt-backend python -m alembic heads
20260601_134 (head)
```
