# US-SCR-04-06 — KPI Dashboard Price Gap/Index/Position + Listings por Marca

**Epic**: EP-SCR-04 — Monitoreo Autónomo + Price Intelligence  
**Sprint**: S15  
**Story Points**: 8 SP  
**Estado**: review  
**Fecha**: 2026-05-16

## Verificación de existencia

Todos los componentes existían implementados.

## Componentes implementados

### Backend — Endpoints
- **Archivo**: `mt-pricing-backend/app/api/routes/price_intelligence.py`
- Registrado en `app/api/routes/__init__.py`

#### GET `/api/v1/price-intelligence/dashboard`
- Query params: `brand_id`, `marketplace`, `date_from`, `date_to`
- Calcula desde `price_daily_stats` + `match_candidate`:
  - `market_stats.avg_price_aed`, `min_price_aed`, `max_price_aed`
  - `kpis.price_gap_pct` (requiere precio MT — calculado en frontend)
  - `kpis.price_index_base` (mkt_avg para que frontend calcule MT/avg×100)
  - `kpis.price_position_index` (rank relativo)
- RBAC: `products:read`

#### GET `/api/v1/price-intelligence/listings/{brand_id}`
- Query params: `marketplace`, `limit`, `offset`
- Lista productos de una marca con precios actuales de competidores
- RBAC: `products:read`

### Frontend — Página
- **Archivo**: `mt-pricing-frontend/app/(app)/comparator/intelligence/page.tsx`
- Cards KPI: Precio medio mercado, Precio mínimo, Price Position Index
- Selector de período: 7d / 30d / 90d
- Selector de marketplace: Amazon UAE / Noon UAE / Todos
- `RbacGuard` con `products:read`
- Client hook: `usePriceIntelligenceDashboard`

### Frontend — Sidebar
- **Archivo**: `mt-pricing-frontend/components/shell/sidebar.tsx`
- `COMPARATOR_INTELLIGENCE_NAV_ITEM` — href `/comparator/intelligence`, icono Zap, permisos `products:read`
- Incluido en render (líneas 433-434 del sidebar)

### Frontend — API Client
- **Archivo**: `mt-pricing-frontend/lib/api/endpoints/price-intelligence.ts`
- `fetchPriceIntelligenceDashboard`, `fetchPriceIntelligenceQuality`, `fetchBrandListings`

### Frontend — Hook
- **Archivo**: `mt-pricing-frontend/app/(app)/comparator/intelligence/_hooks/use-price-intelligence.ts`
- `usePriceIntelligenceDashboard`, `usePriceIntelligenceQuality`, `useBrandListings`

### i18n
- Keys `comparator.intelligence.*` completos en `es.json`, `en.json`, `ar.json`
- Cubre: title, subtitle, period, marketplace, allMarketplaces, kpis.*, quality.*, summary, errors.*
