# US-SCR-04-03 — Bootstrap Coordinator + Workers On-Demand + UI Diferenciación

**Status**: review
**Sprint**: S14
**Story Points**: 8

## Implementación

### Bootstrap Coordinator

- `bootstrap_price_monitoring_task()` en `price_monitor.py`:
  - Query: `SELECT name FROM competitor_brands WHERE is_active=true AND monitoring_active=true`
  - Fan-out: `price_monitor_task(brand_name, marketplace)` por cada marca × marketplace

### Endpoint toggle-monitoring

- **`mt-pricing-backend/app/api/routes/competitor_brands.py`** — nuevo endpoint:
  - `POST /api/v1/competitor-brands/{brand_id}/toggle-monitoring`
  - Invierte `monitoring_active` (true→false, false→true)
  - Requiere permiso `products:write`
  - Retorna `{brand_id, monitoring_active}`

### Schema
- **`mt-pricing-backend/app/schemas/competitor_brands.py`** — `CompetitorBrandRead.monitoring_active: bool = False`

### UI Diferenciación

- **`mt-pricing-frontend/app/(app)/admin/competitor-brands/_client.tsx`**:
  - Nueva columna "Monitoring" en la tabla (visible en lg+)
  - Badge azul "Monitoring on" cuando `monitoring_active=true` (con ícono Activity)
  - Badge gris "Monitoring off" cuando `false`
  - Click en el badge hace `POST /toggle-monitoring` (toggle inmediato)
  - Hook `useToggleCompetitorBrandMonitoring()` con invalidación de queries

### API/Hooks
- **`mt-pricing-frontend/lib/api/endpoints/competitor-brands.ts`**:
  - `CompetitorBrandRead.monitoring_active: boolean` añadido
  - `competitorBrandsApi.toggleMonitoring(id)` añadido
- **`mt-pricing-frontend/lib/hooks/admin/use-competitor-brands.ts`**:
  - `useToggleCompetitorBrandMonitoring()` hook añadido
