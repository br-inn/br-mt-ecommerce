# US-SCR-05-02 — Integración del Brand Extractor en scrape_brand_task y price_monitor_task

**Epic**: EP-SCR-05 — Brand Extractor  
**Sprint**: S18  
**Story Points**: 5 SP  
**Estado**: pending  
**Fecha**: 2026-05-20

---

## Historia

Como sistema de scraping de marcas competidoras,
quiero que `scrape_brand_task` cargue automáticamente el mapping de atributos desde la BD
y lo pase al fetcher antes de cada scrape de monitoreo,
para que los specs enriquecidos generados por el extractor se persistan en `normalized_jsonb`
sin incurrir en ningún costo adicional de LLM por scrape.

---

## Contexto técnico

`US-SCR-05-01` generó `BrandExtractorService.apply_mapping()` y el modelo
`scraper_brand_extractors` (mig 150), pero `scrape_brand_task` **no carga el mapping**
desde la BD: construye el fetcher sin `brand_attribute_map`, por lo que el bloque
`apply_mapping` en `curl_cffi_amazon_uae.py` siempre recibe un dict vacío y nunca
produce specs enriquecidos. Esta story cierra ese gap.

---

## Acceptance Criteria

**AC-1: scrape_brand_task carga el mapping antes de hacer fetch**

**Given** que existe un `BrandExtractor` en BD para brand × marketplace con `attribute_map` no vacío  
**When** `scrape_brand_task(brand_id)` se ejecuta  
**Then** antes de construir el fetcher, carga `BrandExtractorService.get_mapping(brand_id, marketplace)` en la misma sesión DB  
**And** pasa `brand_attribute_map=attribute_map` al constructor del fetcher (`get_fetcher("amazon_uae", brand_attribute_map=mapping)`)  
**And** los listings resultantes tienen `normalized_jsonb["specs"]` con los campos canónicos del mapping (ej. `material`, `dn`, `pn`) además de los specs genéricos

**AC-2: `BrandExtractorService.record_hit` se llama por cada candidate**

**Given** que el fetcher aplica `apply_mapping` a los `raw_pairs` de cada candidato  
**When** `apply_mapping` retorna un dict no vacío para un candidato  
**Then** `BrandExtractorService.record_hit(brand_id, marketplace, hit=True)` se llama una vez por ese candidato  
**And** cuando `apply_mapping` retorna `{}` (ningún label coincide), se llama con `hit=False`  
**And** `hit_rate` en `scraper_brand_extractors` converge hacia la cobertura real con α=0.1 (exponential moving average ya implementado)

**AC-3: Sin mapping en BD, el scraping funciona igual que antes**

**Given** que no existe `BrandExtractor` para esa brand × marketplace  
**When** `scrape_brand_task(brand_id)` se ejecuta  
**Then** el fetcher se construye con `brand_attribute_map={}` (comportamiento anterior)  
**And** `scraper.brand.no_extractor` se registra en logs a nivel DEBUG — nunca ERROR  
**And** no hay round-trip adicional al LLM

**AC-4: `price_monitor_task` también usa el mapping al actualizar precios**

**Given** que existe un `BrandExtractor` para el `competitor_brand_id` del listing monitoreado  
**When** `price_monitor_task(listing_id, asin, source)` hace fetch del PDP  
**Then** carga el mapping por `competitor_brand_id` + marketplace antes del fetch PDP directo  
**And** los specs obtenidos del PDP se enriquecen con `apply_mapping` y se persisten en `normalized_jsonb["specs"]` al actualizar el listing  
**And** si el listing no tiene `competitor_brand_id`, se omite la carga del mapping sin error

**AC-5: Un solo round-trip a DB por task para cargar el mapping**

**Given** que el fetcher necesita el mapping para hacer scraping de una marca  
**When** `scrape_brand_task` carga el mapping  
**Then** usa una sola query `SELECT` (no N queries por candidate) — carga el mapping una vez antes del bucle de candidates  
**And** el mapping cargado se reutiliza para todos los candidates de esa ejecución de task

---

## Archivos a modificar

- `mt-pricing-backend/app/workers/tasks/scraper.py` — `scrape_brand_task`: cargar mapping antes del fetch loop; llamar `record_hit` por candidate
- `mt-pricing-backend/app/workers/tasks/price_monitor.py` — `price_monitor_task`: cargar mapping por `competitor_brand_id`; enriquecer specs al actualizar listing
- `mt-pricing-backend/app/services/matching/adapter_registry.py` — asegurar que `get_fetcher` acepta `brand_attribute_map` kwargs
- `mt-pricing-backend/tests/tasks/test_scraper_brand_extractor_integration.py` — tests con mock de `BrandExtractorService.get_mapping`

---

## FRs cubiertos

FR-10 (CompetitorBrand entity), FR-13 (scrape_brand_task), FR-40 (price_monitor_task liviana)

## NFRs

NFR-01 (cobertura tests ≥80% en paths modificados)

## Prerequisitos

US-SCR-05-01 (DONE): `scraper_brand_extractors` + `BrandExtractorService` + `apply_mapping`

## Estimación

5 SP — modificación quirúrgica de dos tasks existentes + tests

---

## Tasks / Subtasks

- [x] T1: Extender `get_fetcher` en `adapter_registry.py` para aceptar `brand_id` + `brand_attribute_map` kwargs y pasarlos a `CurlCffiAmazonUaeFetcher`
- [x] T2: Modificar `scrape_brand_task` en `scraper.py`: cargar mapping antes del fetch, pasar a fetcher, llamar `record_hit` por candidate
- [x] T3: Modificar `price_monitor_task` en `price_monitor.py`: resolver `CompetitorBrand` por nombre, cargar mapping, pasar a fetcher, actualizar `normalized_jsonb`
- [x] T4: Escribir tests unitarios en `tests/unit/workers/tasks/test_scraper_brand_extractor_integration.py`

---

## Dev Agent Record

### Implementation Plan

- T1: `get_fetcher(channel, *, brand_id=None, brand_attribute_map=None)` — solo Amazon UAE pasa los kwargs al constructor de `CurlCffiAmazonUaeFetcher`
- T2: En `scrape_brand_task._run_async()`, tras cargar `brand`: `svc.get_mapping(brand.id, "amazon_uae")` (1 SELECT), DEBUG log si None, construir fetcher con mapping, post-fetch calcular `canonical_fields` del mapping y llamar `record_hit` por candidate
- T3: En `price_monitor_task._run()`, antes del fetch: `SELECT CompetitorBrand WHERE name==sku`, cargar mapping, pasar a fetcher. Post-fetch: buscar `CompetitorListing` por source+ASIN y actualizar `normalized_jsonb["specs"]`
- T4: Tests con `unittest.mock.AsyncMock` y `patch` — no DB real

### Debug Log

### Completion Notes

Implementación completada + review findings aplicados. Gap cerrado: `scrape_brand_task` ahora carga el mapping desde BD (1 SELECT antes del fetch loop) y lo pasa a `CurlCffiAmazonUaeFetcher` vía `get_fetcher("amazon_uae", brand_id=..., brand_attribute_map=...)`. Post-fetch, `record_hit` se llama una vez por candidato basándose en si sus specs contienen algún campo canónico del mapping.

`price_monitor_task` resuelve `CompetitorBrand` por nombre, carga el mapping, pasa al fetcher, y actualiza `normalized_jsonb["specs"]` en `CompetitorListing` si se encuentra el listing.

**Review fixes (2026-05-20):**
- Critical #1: `await session.flush()` añadido tras actualizar `normalized_jsonb` en `price_monitor_task` — evita pérdida de datos en el early-return `no_price` con `autoflush=False`.
- Critical #2: Sentinel `None` preservado en `scraper.py` (no coerción a `{}`); guard cambiado a `if mapping is not None:` — extractor vacío (`{}`) ahora registra hits all-miss correctamente en EMA.
- Tests actualizados: `test_get_mapping_none_sentinel_preserved`, `test_record_hit_not_called_when_no_extractor`, `test_record_hit_called_with_miss_when_extractor_empty` (16/16 passing).

---

## File List

- `mt-pricing-backend/app/services/matching/adapter_registry.py`
- `mt-pricing-backend/app/workers/tasks/scraper.py`
- `mt-pricing-backend/app/workers/tasks/price_monitor.py`
- `mt-pricing-backend/tests/unit/workers/tasks/test_scraper_brand_extractor_integration.py`

---

## Change Log

- 2026-05-20: Implementación US-SCR-05-02 — Brand Extractor integrado en scrape_brand_task y price_monitor_task; 15 tests nuevos passing
- 2026-05-20: Review fixes aplicados — Critical #1 session.flush, Critical #2 None sentinel; 16 tests passing

---

## Status

done
