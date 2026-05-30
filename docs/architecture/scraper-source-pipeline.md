# Scraper Source Pipeline

## Visión general

El módulo **Scraper Source** permite configurar, validar y ejecutar scrapers
data-driven contra cualquier sitio de e-commerce competidor, sin escribir código.
Los resultados alimentan el matching pipeline de pricing.

---

## Flujo completo

### 1. Configuración

El admin crea un `ScraperSource` desde la UI:

| Campo | Descripción |
|-------|-------------|
| `name` / `slug` | Identificador humano y técnico del sitio |
| `base_url` | Dominio raíz (ej. `https://www.noon.com`) |
| `fetch_mode` | `static` · `headless` · `stealth` |
| `destination_profile` | `competitor_price` · `product_data` |

El registro se crea en `public.scraper_sources` con `status: "draft"`.

---

### 2. Generación de receta con IA

```
POST /api/v1/scraper-sources/analyze
```

**`ScraperAgentService`** orquesta el proceso:

1. `curl_cffi_fetch(url)` → descarga el HTML estático
2. `_detect_mode(html, url)` → determina cómo renderiza el sitio:
   - **`headless`** si el body tiene < 500 chars, o contiene señales RSC
     (`self.__next_f.push`, `__next_f`, `__next_s`) — Noon usa Next.js RSC
   - **`stealth`** si hay señales anti-bot (Cloudflare, PerimeterX, `__cf_chl`)
   - **`static`** en cualquier otro caso
3. Claude Haiku analiza el HTML y genera la receta JSON:

```json
{
  "url_templates": { "search": "https://noon.com/uae-en/search/?q={query}" },
  "list_item_selector": "[data-qa='productCard']",
  "fields": [
    { "name": "title",     "selector": "h3.productTitle", "type": "str" },
    { "name": "price_aed", "selector": ".priceNow",       "type": "currency" },
    { "name": "external_id", "selector": "article", "extract": "attr:data-id" }
  ]
}
```

La respuesta incluye `preview_records` (extractos de prueba), `field_confidence`
(% de filas con valor no nulo), `missing_required` y `warnings`.

---

### 3. Validación de la receta

```
POST /api/v1/scraper-sources/{id}/validate
```

| `fetch_mode` | Comportamiento |
|---|---|
| `static` | `curl_cffi_fetch(test_url)` + `extract_records(html, recipe)` → `field_results: {campo: "pass"/"fail"}` |
| `headless` / `stealth` | Salta la extracción curl. Marca `recipe.validation_status = "passing"` y devuelve `status: "headless_skipped"` |

El caso `headless_skipped` existe porque los sitios RSC (como Noon) no tienen
productos en el HTML estático — los CSS selectors son correctos pero solo
funcionan con un browser real. La UI muestra un banner informativo en lugar
de una tabla de resultados fallida.

---

### 4. Activación

```
POST /api/v1/scraper-sources/{id}/activate
```

Requisitos:
- `recipe.validation_status == "passing"`
- `recipe.has_unapproved_snippet == false`

Efecto:
- `recipe.is_live = true`
- `source.status = "active"`

---

### 5. Ejecución

```
POST /api/v1/scraper-sources/{id}/run
Body: { "search_text": "aspiradoras" }
→ HTTP 202 + { "celery_task_id": "...", "source_id": "..." }
```

El endpoint despacha `scrape_source_task` a la queue `scraper`, consumida
exclusivamente por el contenedor **`mt-scraper-worker`** (Patchright + Chromium
instalados, `shm_size: 2gb`).

#### Ejecución interna del task

```
scrape_source_task(source_id, search_text)
  └─ resolve_fetcher(source.slug, session)
       └─ GenericConfigurableFetcher(source, live_recipe)
            │
            ├─ fetch_mode=static
            │    └─ curl_cffi_fetch(url)           ← curl_cffi, impersona Chrome
            │
            └─ fetch_mode=headless | stealth
                 └─ patchright_fetch(url)           ← Chromium headless, networkidle
                      └─ async with async_playwright() per-call (safe Celery prefork)
            │
            └─ extract_records(html, recipe)        ← selectolax + CSS selectors
                 └─ upsert_listing()
                      └─ public.competitor_listings
```

> **Nota:** `patchright_fetch` hace `async with async_playwright()` por cada
> llamada — no usa singleton de módulo. Esto es obligatorio en Celery prefork
> donde cada task corre en un `asyncio.run()` separado.

---

## Modelo de datos

```
scraper_sources
  id, slug, base_url, fetch_mode, status, destination_profile

scraper_recipe_versions
  id, source_id, version, is_live, validation_status, recipe (JSONB)

competitor_listings           ← salida del scraper
  id, source_id, external_id, title, price_aed, url, scraped_at
```

---

## Integración con el resto de la app

```
competitor_listings
  └─ Matching Pipeline (3 capas LLM + visión)
       ├─ LLM score    (llm_query_generator + Claude Haiku)
       ├─ Vision score (vlm_judge_adapter + Claude Sonnet)
       └─ Text score   (TF-IDF / BM25)
            └─ match_scores (product_id ↔ listing_id, score 0–1)
                 └─ Pricing Desk
                      ├─ Price Gap   (MT price vs. competitor min)
                      ├─ Price Index (MT / market avg)
                      └─ Position    (rank entre competidores)
```

Los `competitor_listings` que genera el scraper son la **única fuente de
precios de competidores** que alimenta el pricing desk. Sin scraper activo
no hay datos de mercado.

---

## Iniciar el scraper worker en local

```bash
docker compose --profile scraper -f docker-compose.dev.yml up scraper-worker -d
docker logs mt-scraper-worker -f
```

El worker solo arranca con el profile `scraper` — no está incluido en el
`up` por defecto para no consumir 3 GB de RAM en desarrollo.

---

## Archivos clave

| Archivo | Responsabilidad |
|---------|----------------|
| `app/services/scraper/agent_service.py` | `ScraperAgentService` + `_detect_mode` |
| `app/services/matching/adapters/generic_configurable.py` | `GenericConfigurableFetcher` |
| `app/services/matching/adapters/playwright_generic.py` | `patchright_fetch` |
| `app/services/matching/adapters/generic_configurable.py` | `curl_cffi_fetch` |
| `app/services/scraper/recipe_extractor.py` | `extract_records` (selectolax) |
| `app/api/routes/scraper_sources.py` | REST API completa |
| `app/workers/tasks/scraper.py` | `scrape_source_task` (Celery) |
| `mt-pricing-frontend/app/(app)/admin/scraper/` | UI de gestión |
