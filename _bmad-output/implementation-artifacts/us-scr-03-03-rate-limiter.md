# US-SCR-03-03 — Rate Limiter Redis Token Bucket + Fingerprint Rotation

**Status**: review
**Sprint**: S14
**Story Points**: 5

## Implementación

### Archivos creados/modificados

- **`mt-pricing-backend/app/services/scraper/rate_limiter.py`** — Token bucket rate limiter por dominio con:
  - Script Lua atómico para adquirir tokens (`EVALSHA`)
  - Pool de 8 User-Agent strings + 6 Accept-Language strings rotados aleatoriamente
  - `acquire(domain)` — espera con backoff si el bucket está vacío
  - `get_headers()` — devuelve headers HTTP con UA + Accept-Language rotados
  - Singleton `get_rate_limiter()` lazy inicializado desde settings
- **`mt-pricing-backend/app/services/scraper/__init__.py`** — módulo init
- **`mt-pricing-backend/app/core/config.py`** — nuevas config keys:
  - `SCRAPER_RATE_LIMIT_RPM=20` (default)
  - `SCRAPER_UA_POOL=""` (separado por `||`)
- **`mt-pricing-backend/.env.example`** — documentadas las nuevas variables
- **`mt-pricing-backend/app/workers/tasks/scraper.py`** — integrado rate limiter + circuit breaker en `scrape_brand_task`

### Redis Keys
- `rate_limit:{domain}` — número de tokens disponibles (TTL: `window_seconds`)

## Tests
- Import tests OK en contenedor
- Unit tests no aplican a esta story (infraestructura async)
