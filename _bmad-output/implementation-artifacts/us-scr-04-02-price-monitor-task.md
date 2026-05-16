# US-SCR-04-02 — price_monitor_task + Workers Colas Especializadas

**Status**: review
**Sprint**: S14
**Story Points**: 8

## Implementación

### Archivos creados/modificados

- **`mt-pricing-backend/app/workers/tasks/price_monitor.py`** — 3 tareas Celery:
  - `price_monitor_task(sku, marketplace)` — cola `scraper.price_monitor`:
    - Verifica circuit breaker antes del fetch
    - Respeta rate limiter
    - Usa `get_fetcher(marketplace)` para obtener precio actual
    - Guarda en `price_history_raw`
    - Detecta variación > 5% vs precio anterior → alerta en log estructurado
    - Retry: 2 reintentos con backoff exponencial
  - `bootstrap_price_monitoring_task()` — cola `scraper.price_monitor`:
    - Itera marcas con `monitoring_active=True` × MONITORED_MARKETPLACES
    - Lanza `price_monitor_task` por combinación
  - `refresh_price_daily_stats_task()` — cola `scraper.price_monitor`:
    - `REFRESH MATERIALIZED VIEW CONCURRENTLY price_daily_stats`
    - Fallback a REFRESH sin CONCURRENTLY si falla (vista sin datos)
- **`mt-pricing-backend/app/workers/worker.py`** — registros:
  - Nueva cola `scraper.price_monitor` en `_QUEUE_NAMES`
  - Módulo `app.workers.tasks.price_monitor` en `include`
  - Routes explícitas para `mt.scraper.price_monitor`, `mt.scraper.bootstrap_price_monitoring`, `mt.scraper.refresh_price_daily_stats`

### Cola dedicada
- `scraper.price_monitor` — separada de `scraper.brand` para no bloquear scraping inicial
- Routing: `mt.scraper.price_monitor*` → `scraper.price_monitor`

## Verificación
```python
from app.workers.tasks.price_monitor import price_monitor_task  # OK
```
