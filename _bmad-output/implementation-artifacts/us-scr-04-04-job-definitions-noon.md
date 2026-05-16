# US-SCR-04-04 — Job Definitions Automáticos + Noon UAE en scrape_brand

**Status**: review
**Sprint**: S14
**Story Points**: 5

## Implementación

### Auto-create job_definition al crear marca

- **`mt-pricing-backend/app/api/routes/competitor_brands.py`** — `create_brand` endpoint:
  - Tras crear la marca, llama a `_auto_create_brand_job(session, brand_name, brand_id)`
  - Inserta en `job_definitions` con `ON CONFLICT (code) DO NOTHING` (idempotente)
  - Código: `scrape_brand_{safe_name}` (lowercase, underscores)
  - Task: `mt.scraper.scrape_brand`
  - Schedule: cron `0 2 * * *` (daily 2am Dubai)
  - Queue: `scraper`
  - owner: `business`
  - kwargs: `{"brand_id": "{uuid}"}`
  - Non-fatal: si falla el INSERT, la marca se crea de todas formas

### Noon UAE en scrape_brand

- **Estado**: El adapter `playwright_noon_uae.py` ya existe y está integrado en `adapter_registry.py` mediante el flag `FLAG_LIVE_NETWORK_NOON_UAE` (feature_flags table).
- No se requieren cambios adicionales — el pipeline ya soporta noon_uae via `get_fetcher("noon_uae")`.
- La task `price_monitor_task` ya incluye noon_uae en `MONITORED_MARKETPLACES`.

### Verificación
- `_auto_create_brand_job` usa `ON CONFLICT DO NOTHING` → seguro en duplicados
- Job code único por marca garantizado por `job_definitions(code) UNIQUE`
