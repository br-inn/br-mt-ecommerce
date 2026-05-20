# US-SCR-05-04 — Métricas de Cobertura del Extractor y Alerta de Degradación

**Epic**: EP-SCR-05 — Brand Extractor  
**Sprint**: S18  
**Story Points**: 3 SP  
**Estado**: pending  
**Fecha**: 2026-05-20

---

## Historia

Como Rami (TI),
quiero ver métricas de cuántos specs se extraen con y sin el brand extractor,
y recibir alerta cuando la cobertura de un extractor cae significativamente,
para detectar cuando Amazon cambia el formato de sus tablas de atributos y regenerar el mapping.

---

## Contexto técnico

`scraper_brand_extractors.hit_rate` ya se actualiza con EMA (α=0.1) vía
`BrandExtractorService.record_hit()` (implementado en US-SCR-05-02). Esta story
agrega el endpoint de métricas históricas y la alerta proactiva cuando la cobertura
degrada por debajo del umbral configurable.

---

## Acceptance Criteria

**AC-1: Histograma de cobertura en el panel de extractor**

**Given** que `hit_rate` se actualiza por cada uso del extractor  
**When** Rami abre el panel de extractor de una marca (US-SCR-05-03)  
**Then** ve el gauge visual de `hit_rate` actual (ej. semicírculo con porcentaje)  
**And** el color del gauge sigue el semáforo: verde ≥80%, amarillo 60-79%, rojo <60%  
**And** el tooltip explica: "Porcentaje de candidatos en los que el extractor encontró al menos 1 atributo canónico"

**AC-2: Alerta proactiva cuando hit_rate cae > 20pp en 7 días**

**Given** que `hit_rate` de un extractor cae más de 20 puntos porcentuales en los últimos 7 días  
**When** `price_monitor_batch_task` finaliza su ciclo diario  
**Then** crea o actualiza un registro en `scraper_extractor_alerts` (nueva tabla, mig 151+1):  
  ```
  brand_id, marketplace, triggered_at, hit_rate_now, hit_rate_baseline, delta_pp, resolved_at
  ```
**And** aparece badge de alerta en la columna "Extractor" de la tabla de marcas (ícono ⚠ amarillo)  
**And** el badge tiene tooltip: "Cobertura degradó 23pp — considera regenerar el extractor"

**AC-3: Endpoint de métricas de cobertura por brand**

**Given** que Rami quiere ver la evolución de cobertura  
**When** hace `GET /api/v1/competitor-brands/{id}/extractor/coverage-stats`  
**Then** retorna:
  ```json
  {
    "brand_id": "...",
    "marketplace": "amazon_uae",
    "hit_rate_current": 0.61,
    "hit_rate_30d_ago": 0.84,
    "delta_pp": -23.0,
    "total_candidates_last_7d": 142,
    "candidates_with_extraction_last_7d": 87,
    "alert_active": true
  }
  ```
**And** `candidates_with_extraction_last_7d` se calcula contando `normalized_jsonb` que contengan al menos 1 key del `attribute_map` (sin round-trip extra: columna `extraction_hit` añadida al upsert en US-SCR-05-02)  
**And** el endpoint requiere permiso `scraper:read`

**AC-4: Botón "Marcar como resuelto" en la alerta activa**

**Given** que existe una alerta activa de degradación para una brand  
**When** Rami regenera el extractor (AC-3 de US-SCR-05-03) o hace click en "Marcar como resuelto"  
**Then** `resolved_at` se actualiza a `now()` en `scraper_extractor_alerts`  
**And** el badge de alerta ⚠ desaparece de la tabla de marcas  
**And** el evento queda en historial: quién resolvió (usuario) y cómo (regeneración vs manual)

**AC-5: Migración Alembic para scraper_extractor_alerts**

**Given** que la tabla `scraper_extractor_alerts` no existe  
**When** se ejecuta la migración Alembic (nombre `YYYYMMDD_NNN_scraper_extractor_alerts`)  
**Then** crea la tabla con columnas: `id` (uuid PK), `brand_id` (FK competitor_brands), `marketplace` (varchar 32), `triggered_at` (timestamptz), `hit_rate_now` (numeric 5,4), `hit_rate_baseline` (numeric 5,4), `delta_pp` (numeric 6,2), `resolved_at` (timestamptz nullable), `resolved_by` (uuid FK users nullable)  
**And** índice en `(brand_id, marketplace, resolved_at)` para queries de alertas activas  
**And** la migración es reversible (downgrade elimina tabla)

---

## Archivos a crear/modificar

### Backend
- `mt-pricing-backend/alembic/versions/YYYYMMDD_NNN_scraper_extractor_alerts.py` — nueva migración
- `mt-pricing-backend/app/db/models/comparator.py` — modelo `ExtractorAlert`
- `mt-pricing-backend/app/workers/tasks/price_monitor.py` — al final de `price_monitor_batch_task`, evaluar degradación de hit_rate y crear alertas
- `mt-pricing-backend/app/api/routes/competitor_brands.py` — endpoint `GET /competitor-brands/{id}/extractor/coverage-stats`

### Frontend
- `mt-pricing-frontend/app/(app)/admin/competitor-brands/_client.tsx` — badge ⚠ en columna Extractor cuando alerta activa
- `mt-pricing-frontend/app/(app)/admin/competitor-brands/[id]/extractor-panel.tsx` — gauge de hit_rate + botón "Marcar como resuelto"
- `mt-pricing-frontend/messages/es.json` — keys de alerta en `admin.brandExtractor`
- `mt-pricing-frontend/messages/en.json` — ídem
- `mt-pricing-frontend/messages/ar.json` — ídem

---

## FRs cubiertos

FR-35 (monitor calidad de matching — análogo para extractors), FR-20 (dashboard listings por marca)

## NFRs

NFR-03 (i18n), NFR-04 (RBAC), NFR-07 (queries de stats <100ms — índice en migración)

## Prerequisitos

US-SCR-05-01 (DONE): `hit_rate` en modelo + `record_hit`  
US-SCR-05-02 (S18): `record_hit` llamado desde tasks  
US-SCR-05-03 (S18): panel de extractor en UI (mismo componente que amplía esta story)

## Estimación

3 SP — migración + 1 endpoint + evaluación de alerta en batch task + UI mínima (gauge + badge)
