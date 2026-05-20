# US-SCR-05-03 — UI Admin para Gestión de Brand Extractors

**Epic**: EP-SCR-05 — Brand Extractor  
**Sprint**: S18  
**Story Points**: 5 SP  
**Estado**: pending  
**Fecha**: 2026-05-20

---

## Historia

Como Rami (TI),
quiero ver y gestionar los extractors de atributos generados por marca en `/admin/competitor-brands`,
para saber qué marcas tienen mapping activo, cuándo se generó, y poder regenerar el mapping
cuando Amazon cambia el formato de sus tablas de atributos.

---

## Contexto técnico

La tabla `scraper_brand_extractors` (mig 150) almacena `attribute_map`, `generated_at`,
`generated_by`, `sample_asins`, `last_used_at` y `hit_rate` por brand × marketplace.
El endpoint `POST /bootstrap-scan` (US-SCR-05-01) lanza `generate_brand_extractor_task`
pero no hay ninguna UI que muestre el estado del extractor ni permita regenerarlo.

---

## Acceptance Criteria

**AC-1: Columna "Extractor" en tabla de marcas competidoras**

**Given** que Rami visita `/admin/competitor-brands`  
**When** la página carga  
**Then** la tabla muestra una columna "Extractor" con badge por marketplace:  
  - `amazon_uae`: verde si `generated_at` < 30 días, amarillo 30-90 días, rojo > 90 días o sin extractor  
  - El badge muestra la fecha relativa (ej. "hace 3 días") en tooltip  
**And** si la brand no tiene extractor para `amazon_uae`, muestra badge gris "Sin extractor"

**AC-2: Panel de detalle del extractor en el dialog de marca**

**Given** que Rami abre el dialog de edición de una marca  
**When** hace click en la pestaña "Extractor"  
**Then** ve la información del extractor activo:  
  - `generated_at` formateado como fecha local  
  - `generated_by` (modelo Claude que lo generó)  
  - `hit_rate` como porcentaje de cobertura (ej. "82% cobertura")  
  - `sample_asins` lista de ASINs usados como muestra (máx 5, formato link a Amazon)  
  - Número de campos en `attribute_map` (ej. "7 atributos mapeados")  
  - `last_used_at` — último uso en un scrape

**AC-3: Botón "Regenerar extractor" en el dialog**

**Given** que Rami está en la pestaña "Extractor" de una marca  
**When** hace click en "Regenerar extractor"  
**Then** aparece dialog de confirmación: "Se llamará a Claude para regenerar el mapping. Esto consume ~1K tokens. ¿Continuar?"  
**And** al confirmar, llama a `POST /api/v1/competitor-brands/{id}/bootstrap-scan` con `marketplace=amazon_uae`  
**And** el botón muestra spinner durante la request y se deshabilita hasta recibir respuesta  
**And** al completar, muestra toast: "Extractor regenerado — N atributos mapeados"  
**And** el panel de detalle se refresca con los nuevos datos sin recargar la página

**AC-4: Endpoint GET extractor info**

**Given** que el frontend necesita mostrar el estado del extractor  
**When** hace `GET /api/v1/competitor-brands/{id}/extractor?marketplace=amazon_uae`  
**Then** retorna 200 con payload:  
  ```json
  {
    "brand_id": "...",
    "marketplace": "amazon_uae",
    "generated_at": "2026-05-17T12:00:00Z",
    "generated_by": "claude-haiku-4-5-20251001",
    "hit_rate": 0.82,
    "sample_asins": ["B0...", "B1..."],
    "attribute_count": 7,
    "last_used_at": "2026-05-19T03:00:00Z"
  }
  ```
**And** si no existe extractor para esa brand × marketplace, retorna 404 con `{"detail": "No extractor found"}`  
**And** el endpoint requiere permiso `scraper:read`

**AC-5: Listado de extractors en tabla paginada (`GET /extractor-stats`)**

**Given** que Rami quiere ver un resumen global del estado de todos los extractors  
**When** hace `GET /api/v1/scraper/extractor-stats`  
**Then** retorna lista con: `brand_id`, `brand_name`, `marketplace`, `hit_rate`, `generated_at`, `attribute_count`  
**And** ordenada por `hit_rate` ASC (primero los con peor cobertura)  
**And** la UI muestra esta tabla en la sección "Brand Extractors" de `/admin/scraper`

**AC-6: i18n completo en los 3 idiomas**

**Given** que los textos de la UI de extractor son nuevos  
**When** se añaden a los archivos de mensajes  
**Then** todas las keys están en `messages/es.json`, `messages/en.json`, `messages/ar.json`  
**And** el namespace es `admin.brandExtractor.*`  
**And** no hay strings hardcodeados en componentes React

---

## Archivos a crear/modificar

### Backend
- `mt-pricing-backend/app/api/routes/competitor_brands.py` — nuevos endpoints:
  - `GET /competitor-brands/{id}/extractor`
  - `GET /scraper/extractor-stats`
- `mt-pricing-backend/app/schemas/brand_extractor.py` — schemas Pydantic de respuesta

### Frontend
- `mt-pricing-frontend/app/(app)/admin/competitor-brands/_client.tsx` — columna "Extractor" en tabla
- `mt-pricing-frontend/app/(app)/admin/competitor-brands/[id]/extractor-panel.tsx` — panel de detalle (nuevo componente)
- `mt-pricing-frontend/messages/es.json` — namespace `admin.brandExtractor`
- `mt-pricing-frontend/messages/en.json` — namespace `admin.brandExtractor`
- `mt-pricing-frontend/messages/ar.json` — namespace `admin.brandExtractor`

---

## FRs cubiertos

FR-12 (Frontend admin competitor brands), FR-11 (API REST competitor brands)

## NFRs

NFR-03 (i18n ES/EN/AR), NFR-04 (RBAC `scraper:read/write`), NFR-02 (respuesta <500ms)

## Prerequisitos

US-SCR-05-01 (DONE): tabla `scraper_brand_extractors` + `generate_brand_extractor_task` + `POST /bootstrap-scan`

## Estimación

5 SP — 2 endpoints backend + componente React de panel + i18n

---

## Dev Agent Record

### Completion Notes

Implementación completada con 2 agentes en paralelo (backend + frontend).

**Backend:**
- `app/schemas/brand_extractor.py` — `BrandExtractorRead` + `ExtractorStatRow` (Pydantic v2)
- `app/api/routes/competitor_brands.py` — `GET /{brand_id}/extractor?marketplace=` (scraper:read, 404 si no existe)
- `app/api/routes/scraper.py` — `GET /extractor-stats` (JOIN competitor_brands, ordenado por hit_rate ASC)
- 5/5 tests unitarios pasando

**Frontend:**
- `extractor-panel.tsx` — hook `useExtractorStatus`, badge semáforo (gris/verde/amarillo/rojo), panel completo con links amazon.ae, `ConfirmDialog` para regenerar
- `_client.tsx` — columna "Extractor" con `ExtractorBadge` por fila; pestaña "Extractor" en dialog de edición (tabs General/Extractor)
- `messages/es.json`, `en.json`, `ar.json` — namespace `admin.brandExtractor` con 20 keys; 0 errores TypeScript

---

## File List

- `mt-pricing-backend/app/schemas/brand_extractor.py` (nuevo)
- `mt-pricing-backend/app/api/routes/competitor_brands.py`
- `mt-pricing-backend/app/api/routes/scraper.py`
- `mt-pricing-backend/app/api/routes/procurement.py` (fix pre-existente FastAPI compat)
- `mt-pricing-backend/tests/unit/api/routes/test_brand_extractor_endpoints.py` (nuevo)
- `mt-pricing-frontend/app/(app)/admin/competitor-brands/extractor-panel.tsx` (nuevo)
- `mt-pricing-frontend/app/(app)/admin/competitor-brands/_client.tsx`
- `mt-pricing-frontend/messages/es.json`
- `mt-pricing-frontend/messages/en.json`
- `mt-pricing-frontend/messages/ar.json`

---

## Change Log

- 2026-05-20: Implementación US-SCR-05-03 — 2 endpoints backend + UI badge/panel extractor + i18n; 5 tests backend passing

---

## Status

done
