# Diseño — Módulo Scraper Source Builder ("Fuentes de Scraping")

- **Fecha:** 2026-05-20
- **Autor:** psierra (con asistencia de Claude)
- **Estado:** Diseño aprobado — pendiente de planes de implementación por fase
- **Alcance:** Módulo completo, organizado en 4 fases de implementación

---

## 1. Problema y motivación

Hoy el scraper de competidores soporta exactamente 2 sitios (`amazon_uae`, `noon_uae`).
Cada uno es un adapter de Python hardcodeado (~230 líneas) con selectores CSS/XPath/regex
embebidos en código. Añadir un sitio nuevo requiere: escribir una clase adapter, un
parser, un mapper, una rama en `get_fetcher()`, una feature flag y registrar el canal en
`SUPPORTED_CHANNELS`. No existe ninguna parametrización por datos.

**Objetivo:** permitir que un usuario **no técnico** dé de alta y mantenga sitios de
scraping **sin escribir código**, mediante un motor genérico data-driven y un asistente
basado en IA.

### Lo que ya existe y se reutiliza

- `BrandExtractor.attribute_map` (tabla `scraper_brand_extractors`, US-SCR-05-03): config
  JSONB generada por Claude. Es el **precedente arquitectónico**: config JSON-driven
  generada por LLM. Pero opera sobre HTML *ya extraído* — no controla la extracción misma.
- `scraper_extractor_alerts` (migración `20260602_144`): observabilidad de degradación de
  hit-rate. Su patrón se extiende para el monitoreo de sources.
- Infraestructura de fetch Tier-1 (`curl_cffi`) / Tier-2 (`Patchright` + proxies) y el
  `FetcherPort` Protocol en `adapter_registry.py`.
- `job_definitions` para scheduling; `_auto_create_brand_job()` como espejo de
  auto-creación de jobs.
- `CompetitorFetchError` + circuit breaker para errores de fetch.

### Decisiones de alcance (acordadas en brainstorming)

| Eje | Decisión |
|-----|----------|
| Propósito | Motor genérico — sirve a precios de competidores **y** datos de producto |
| Mecanismo de definición | Híbrido: la IA propone selectores + el usuario los ajusta visualmente |
| Fetch | Modo configurable por sitio (`static` / `headless` / `stealth`), reutilizando Tier-1/Tier-2 |
| Destino | Perfiles de destino predefinidos (`competitor_price`, `product_data`) |
| Enfoque arquitectónico | Híbrido A+B: config data-driven por default + snippets de código generados por LLM como escape hatch sandboxeado |

---

## 2. Concepto central

Hoy un *canal* = un adapter de código hardcodeado. El módulo introduce el concepto de
**Source**: una definición *configurable y data-driven* de un sitio a scrapear.

- Los adapters de Amazon/Noon **conviven sin modificarse** (casos especiales).
- Las sources nuevas pasan por un **motor genérico** (`GenericConfigurableFetcher`).
- `adapter_registry.get_fetcher()` gana un fallback: si el canal no es un adapter
  hardcodeado, busca una `scraper_source` activa por slug y devuelve el motor genérico
  ligado a ella.

---

## 3. Modelo de datos

Tablas nuevas en `public.*`, vía Alembic. Identificadores y datos en inglés (regla del
proyecto: todo dato en DB en inglés).

### 3.1 `scraper_sources` — identidad y estado del sitio

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | uuid PK | |
| `name` | text | nombre legible |
| `slug` | text unique | actúa como string de "canal" en `get_fetcher()` |
| `base_url` | text | |
| `description` | text nullable | |
| `destination_profile` | enum | `competitor_price` \| `product_data` |
| `fetch_mode` | enum | `static` \| `headless` \| `stealth` |
| `status` | enum | `draft` \| `testing` \| `active` \| `disabled` \| `degraded` |
| `created_by` | uuid | usuario |
| `generated_by` | text nullable | modelo LLM usado en descubrimiento |
| `created_at` / `updated_at` | timestamptz | |
| `last_validated_at` | timestamptz nullable | |

> Las columnas de enum PG usan `Enum(create_type=False)` en el modelo SQLAlchemy
> (regla del proyecto para evitar `DatatypeMismatch` en asyncpg).

### 3.2 `scraper_source_recipes` — receta de extracción versionada

Una source tiene N recetas; exactamente una tiene `is_live = true`. El versionado permite
editar/regenerar un borrador sin romper la versión en producción.

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | uuid PK | |
| `source_id` | uuid FK → `scraper_sources` | |
| `version` | int | incremental por source |
| `is_live` | bool | única `true` por source (índice parcial único) |
| `recipe` | jsonb | contenido de la receta (ver 3.3) |
| `validation_status` | enum | `unvalidated` \| `passing` \| `failing` |
| `has_unapproved_snippet` | bool | si `true`, no puede pasar a `is_live` |
| `created_by` | uuid | |
| `created_at` | timestamptz | |

### 3.3 Contenido del campo `recipe` (JSONB)

```jsonc
{
  "url_templates": {
    // competitor_price: search + pdp. product_data: list + product.
    "search": "https://site.com/s?q={query}",
    "pdp": "https://site.com/p/{sku}"
  },
  "pagination": {                       // opcional
    "next_selector": "a.next",
    "max_pages": 5
  },
  "list_item_selector": "div.result",   // contenedor de cada resultado
  "fields": [
    {
      "name": "price",                  // mapea a campo del perfil destino
      "selector": ".price-now",
      "extract": "text",                // text | attr:href | attr:src | html
      "type": "currency",               // str | float | int | currency | bool
      "transform": { /* ver 3.4 */ }    // opcional
    }
  ],
  "anti_bot_hints": {                   // para headless/stealth
    "wait_for": "div.result",
    "scroll": true
  }
}
```

### 3.4 `transform` — el híbrido A+B

Cada campo puede tener un `transform` con una de dos modalidades:

**Declarativo (A) — default, ~90 % de los casos.** Operaciones predefinidas y seguras:
`regex_capture`, `unit_factor`, `strip_currency`, `to_float`, `trim`, `map_values`.

```jsonc
{ "type": "declarative", "op": "regex_capture", "pattern": "([0-9.]+)" }
```

**Snippet LLM (B) — escape hatch.** Para lógica que lo declarativo no cubre. **No es
Python arbitrario:** es una función pura `transform(value: str) -> str|float|int`,
generada por Claude, ejecutada en sandbox.

```jsonc
{
  "type": "llm_snippet",
  "code": "def transform(value):\n    ...",
  "description": "Convierte '2.5K' a 2500",
  "approved": false
}
```

### 3.5 `scraper_source_test_runs` — resultados de validación

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | uuid PK | |
| `source_id` | uuid FK | |
| `recipe_id` | uuid FK | |
| `test_url` | text | |
| `html_snapshot_ref` | text nullable | referencia a snapshot (Storage) |
| `extracted` | jsonb | resultado extraído |
| `field_results` | jsonb | `{ "price": "pass", "title": "fail" }` |
| `created_at` | timestamptz | |

### 3.6 Reutilización

- Errores de fetch → `CompetitorFetchError` existente.
- Monitoreo de degradación → extiende el patrón de `scraper_extractor_alerts`
  (alertas por caída de hit-rate por campo de la source).

---

## 4. Componentes backend

### 4.1 `SourceDiscoveryService` (parte IA — Enfoque A)

Dada una URL de muestra + perfil destino: hace fetch con el modo elegido, recorta el DOM
renderizado y se lo pasa a Claude, que devuelve una **receta borrador** (`url_templates`,
`list_item_selector`, selectores de `fields`, transforms sugeridos). Extiende el patrón de
`BrandExtractorService`. El resultado se guarda como `scraper_source_recipes` borrador.

### 4.2 `GenericConfigurableFetcher`

Implementa el `FetcherPort` existente (`channel` + `async fetch`), construido ligado a una
source + su receta `is_live`. Flujo:

1. Construye URLs desde `url_templates`.
2. Fetch según `fetch_mode`:
   - `static` → `curl_cffi` (Tier-1).
   - `headless` / `stealth` → `Patchright` (Tier-2), aplicando `anti_bot_hints`.
3. Parsea HTML; aplica `list_item_selector` + selectores de `fields`.
4. Aplica `transform` de cada campo (declarativo o snippet sandboxeado).
5. Mapea al perfil destino → `CandidateRaw` (`competitor_price`) o DTO de datos de
   producto (`product_data`).

### 4.3 Fallback en `adapter_registry.get_fetcher()`

Si el `channel` no resuelve a un adapter hardcodeado, busca una `scraper_source` activa
por slug y devuelve `GenericConfigurableFetcher` ligado a ella. Amazon/Noon intactos.

### 4.4 `SourceValidationService`

Corre una receta contra 1-3 URLs de muestra y devuelve resultado **por campo**
(pass/fail). Alimenta el botón "probar" del editor y la task periódica de monitoreo.
Persiste un `scraper_source_test_run`.

### 4.5 Sandbox de snippets

Ejecuta los snippets `llm_snippet` de forma aislada: sin imports, sin I/O, sin red, con
límite de CPU y tiempo. Implementación con `RestrictedPython` o subproceso aislado.
Cualquier violación aborta la ejecución y marca el snippet como inválido.

**Tres barreras de seguridad sobre los snippets LLM:**

1. **Sandbox** — I/O/red/import abortan la ejecución.
2. **Aprobación humana** — un snippet solo se ejecuta tras aprobación explícita del
   usuario en el editor. Una receta `is_live` no puede contener snippets sin aprobar
   (`has_unapproved_snippet = false` es precondición de activación).
3. **Versionado** — el snippet vive dentro de la receta versionada; revertir = mover el
   puntero `is_live`.

### 4.6 Destination sinks

- `CompetitorPriceSink` — escribe a `CompetitorListing`; entra al pipeline de matching
  existente.
- `ProductDataSink` — escribe a staging del PIM; reutiliza la ruta de ingesta de ficha
  enrichment.

El perfil de destino define los campos canónicos a los que la receta debe mapear sus
`fields`.

### 4.7 Endpoints API (`/api/v1/scraper/sources`)

- `GET /sources` — listado con estado.
- `POST /sources` — crear (paso identidad del wizard).
- `GET /sources/{id}` — detalle + recetas.
- `POST /sources/{id}/discover` — dispara `SourceDiscoveryService`.
- `POST /sources/{id}/preview` — re-evalúa un selector contra HTML cacheado (editor).
- `POST /sources/{id}/validate` — dispara `SourceValidationService`.
- `POST /sources/{id}/activate` — promueve la receta a `is_live`, source a `active`.
- `POST /sources/{id}/recipes/{rid}/approve-snippet` — aprueba un snippet LLM.

---

## 5. Frontend (Next.js admin)

### 5.1 Sección `/admin/scraper/sources`

Hermana de `competitor-brands` y `scraper/health`. Lista de sources con badge de estado
semáforo (reutiliza el patrón de `extractor-panel.tsx`): `active` verde, `degraded` ámbar,
`draft`/`testing` gris, `disabled` neutro.

### 5.2 Wizard de creación de Source (multi-paso)

1. **Identidad** — nombre, base URL, perfil destino, modo de fetch.
2. **Descubrimiento** — pegar URL de muestra → "Analizar con IA" → `SourceDiscoveryService`
   devuelve la receta borrador.
3. **Editor de receta (híbrido):**
   - **Modo formulario/preview** — tabla de campos: `name`, `selector`, valor extraído en
     vivo (vía endpoint `/preview`). Base, funciona siempre, sin IA.
   - **Modo point-and-click visual** — página renderizada (snapshot servido por el backend
     para esquivar CORS y el anti-bot del sitio); click en un elemento → captura su
     selector. Clicks interceptados por un overlay inyectado.
   - Snippets LLM mostrados con su descripción + botón **"Aprobar"**.
4. **Probar y validar** — corre la receta contra URLs de muestra; muestra pass/fail por
   campo; mapeo de campos extraídos → campos del perfil destino.
5. **Activar** — receta a `is_live`, source a `active`, auto-creación de `job_definition`
   (espejo de `_auto_create_brand_job()`).

### 5.3 Detalle / salud de Source

Extiende `scraper/health`: hit-rate por campo, últimas corridas, alertas de degradación,
botón "regenerar receta" (re-dispara descubrimiento → nueva versión borrador, sin tocar la
`is_live`).

### 5.4 Patrón de datos

React Query: vocabulario de sources `staleTime` 300 000 ms; preview del editor sin caché
(`staleTime: 0`). Imágenes de snapshot con `loading="lazy"`.

### Riesgo destacado

El **modo point-and-click** (5.2 paso 3) es el componente de mayor riesgo técnico —
servir el snapshot renderizado e interceptar clicks de forma fiable es no-trivial. El modo
formulario/preview entrega el "ajuste" completo sin ese riesgo, por lo que el
point-and-click queda en una fase posterior (ver §8).

---

## 6. Flujo de datos

| Fase | Flujo |
|------|-------|
| Descubrimiento | URL muestra → fetch → DOM recortado → Claude → receta borrador → editor |
| Edición | usuario ajusta selector → `/preview` re-evalúa contra HTML cacheado → valor en vivo |
| Validación | receta + URLs muestra → `SourceValidationService` → pass/fail por campo |
| Activación | receta `is_live=true`, source `active`, se crea `job_definition` |
| Producción | Celery task → `get_fetcher(slug)` → `GenericConfigurableFetcher` → fetch+extraer+transform → destination sink → `CompetitorListing` / staging PIM |
| Monitoreo | task periódica calcula hit-rate por campo → caída → `degraded` + alerta |

---

## 7. Manejo de errores y máquina de estados

### Errores

- **Fetch fallido** → `CompetitorFetchError` + circuit breaker por source.
- **Selector sin match** → campo a `null` + registrado en hit-rate; bajo umbral →
  source `degraded`.
- **Error de transform/snippet** → capturado, campo a `null`, log; recurrente → alerta.
- **Violación de sandbox** → snippet rechazado; la receta no puede pasar a `is_live`.
- **Fallo de descubrimiento LLM** → el wizard muestra error; el usuario reintenta o llena
  la receta a mano (el modo formulario funciona sin IA).
- **Bloqueo anti-bot** → se sugiere escalar el `fetch_mode` (`static` → `headless` →
  `stealth`).
- **Receta degradada en producción** → la source sigue con la última `is_live`; la alerta
  invita a regenerar; nunca se auto-aplica una receta sin validar.

### Máquina de estados de una Source

```
draft ──(validación OK)──> testing ──(activación)──> active
                                                       │
                          active <──(regenerar+validar)─┤
                                                       │
                                          degraded <──(hit-rate cae)
disabled  ← (manual, desde cualquier estado)
```

---

## 8. Testing

- **Unit:** parser de recetas, motor de transforms declarativos, sandbox (incl. **test
  explícito de rechazo de snippets maliciosos** — I/O/red/import abortan), templating de
  URLs, máquina de estados.
- **Integración:** `GenericConfigurableFetcher` contra **snapshots HTML de fixture** (sin
  red en vivo) para cada modo de fetch.
- **Descubrimiento:** respuestas de Claude mockeadas → validación de la forma de la
  receta.
- **E2E:** happy path del wizard con un sitio fixture.
- **Regresión (crítico):** los tests de los adapters Amazon/Noon existentes deben seguir
  pasando — el motor genérico no debe alterar esa ruta.

---

## 9. Fases de implementación

El spec cubre el módulo completo; la implementación se decompone en 4 fases, cada una
entregable y con valor propio. Cada fase tendrá su propio plan de implementación
(skill `writing-plans`) cuando se vaya a ejecutar.

| Fase | Alcance | Entrega |
|------|---------|---------|
| **F1 — Núcleo del motor** | Modelo de datos (§3), `GenericConfigurableFetcher`, recetas declarativas, perfil `competitor_price`, fallback en `get_fetcher()`, editor formulario/preview, validación/test | "Añadir un sitio de precios sin código, escribiendo la receta en un formulario" end-to-end |
| **F2 — Descubrimiento IA** | `SourceDiscoveryService`, paso de descubrimiento del wizard, recetas borrador desde Claude | "La IA propone la receta" |
| **F3 — Editor visual + híbrido B** | Captura point-and-click sobre snapshot, snippets LLM + sandbox + flujo de aprobación | El híbrido "IA propone + ajuste visual" completo |
| **F4 — Datos de producto + monitoreo** | Perfil `product_data` → PIM, monitoreo de hit-rate, alertas, auto-creación de `job_definition`, ciclo `degraded` | Segundo perfil destino + operación sostenible |

### Dependencias entre fases

F1 es fundacional. F2 depende de F1 (necesita el modelo de recetas). F3 depende de F2
(el editor visual ajusta lo que F2 propone; el híbrido B necesita el sandbox). F4 depende
de F1 (perfil destino + estados) y es independiente de F2/F3.

---

## 10. Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| Ejecutar código generado por LLM | Sandbox + aprobación humana + versionado (§4.5) |
| Modo point-and-click técnicamente complejo | Aislado en F3; el modo formulario entrega el ajuste sin él |
| El motor genérico rompe Amazon/Noon | Adapters hardcodeados intactos; fallback solo para canales no hardcodeados; tests de regresión |
| Recetas data-driven no cubren lógica rara | Escape hatch de snippets LLM (híbrido B) |
| Sitios con anti-bot agresivo | `fetch_mode` `stealth` reutiliza Tier-2 + proxies existentes |
| Calidad variable del descubrimiento LLM | El modo formulario funciona sin IA; la validación por campo expone fallos antes de activar |

---

## 11. Fuera de alcance (YAGNI)

- Scraping de webs arbitrarias fuera de los dos perfiles de destino.
- Mapeo libre a columnas arbitrarias de cualquier tabla.
- Integración con scrapers externos de terceros (Browse AI / Apify).
- Generación de adapters como código Python completo (descartado por riesgo de seguridad;
  el híbrido B usa snippets sandboxeados, no adapters).
- Multi-tenancy de sources (Fase 1 del programa MT es single-tenant).
