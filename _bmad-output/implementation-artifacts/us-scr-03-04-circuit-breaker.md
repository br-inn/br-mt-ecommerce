# US-SCR-03-04 — Circuit Breaker Dominio + Proxy Pool Distribuido Redis

**Status**: review
**Sprint**: S14
**Story Points**: 8

## Implementación

### Archivos creados/modificados

- **`mt-pricing-backend/app/services/scraper/circuit_breaker.py`** — Circuit breaker + ProxyPool:
  - `CircuitBreaker` — estados CLOSED/OPEN/HALF_OPEN en Redis
  - `ScraperCircuitOpenError` — excepción lanzada cuando el circuit está OPEN
  - `ProxyPool` — rotación round-robin con RPOPLPUSH
  - Singletons `get_circuit_breaker()` y `get_proxy_pool()`
- **`mt-pricing-backend/app/core/config.py`** — nuevas config keys:
  - `SCRAPER_CB_FAILURE_THRESHOLD=5`
  - `SCRAPER_CB_RECOVERY_TIMEOUT=60`
- **`mt-pricing-backend/app/workers/tasks/scraper.py`** — integrado en `scrape_brand_task`:
  - `circuit_breaker.check_and_raise(domain)` antes del fetch
  - `circuit_breaker.record_success/failure(domain)` según resultado
  - Proxy rotation via `proxy_pool.get_proxy()`

### Redis Keys
- `circuit:{domain}:state` — "closed" | "open" | "half_open"
- `circuit:{domain}:failures` — contador de fallos (TTL: failure_window)
- `circuit:{domain}:opened_at` — timestamp UNIX cuando se abrió
- `proxy_pool` — lista de proxies (LPUSH para añadir, RPOPLPUSH para rotar)

## Tests
- Import tests OK en contenedor
