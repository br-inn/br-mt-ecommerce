# US-SCR-03-05 — Dashboard Salud Canales + CRUD Proxies UI sin Redeploy

**Status**: review
**Sprint**: S14
**Story Points**: 8

## Implementación

### Backend

- **`mt-pricing-backend/app/api/routes/admin_scraper.py`** — nuevos endpoints:
  - `GET /api/v1/admin/scraper-health` — estado circuit breakers + stats por dominio
  - `POST /api/v1/admin/scraper-health/circuit/{domain}/reset` — reset manual del circuit
  - `GET /api/v1/admin/proxies` — lista de proxies (con proxy_b64 para URL-safe delete)
  - `POST /api/v1/admin/proxies` — añadir proxy al pool (sin redeploy)
  - `DELETE /api/v1/admin/proxies/{proxy_b64}` — eliminar proxy del pool
- Todos los endpoints requieren permiso `admin:read`
- Registrado en `app/api/routes/__init__.py`

### Frontend

- **`mt-pricing-frontend/app/(app)/admin/scraper/health/page.tsx`** — página SSR con `RbacGuard`
- **`mt-pricing-frontend/app/(app)/admin/scraper/health/_client.tsx`** — componente cliente:
  - Tabla de dominios con: circuit state (badge color), failures/threshold, requests 24h, error rate
  - Botón "Reset" circuit breaker para dominios con estado != closed
  - Tabla de proxies con add/remove (sin redeploy)
  - Dialog para añadir nuevo proxy
  - Auto-refresh cada 30s
- **`mt-pricing-frontend/app/(app)/admin/scraper/page.tsx`** — enlace "Health" añadido en header
- **`mt-pricing-frontend/messages/en.json`** — sección `admin.scraperHealth` añadida
- **`mt-pricing-frontend/messages/ar.json`** — sección `admin.scraperHealth` añadida (árabe)

## Verificación
- Endpoints registrados y router importado correctamente
- Rutas disponibles: `/admin/scraper-health`, `/admin/scraper-health/circuit/{domain}/reset`, `/admin/proxies`, etc.
