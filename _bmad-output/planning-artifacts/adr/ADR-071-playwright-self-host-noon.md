---
adr: "ADR-071"
title: "Playwright self-host en worker MT para Noon UAE — Chromium headless + circuit breaker"
status: "proposed"
date: "2026-05-07"
author: "Pablo Sierra (Comercial · Online)"
deciders: ["Champion MT", "Paula (DPO)", "Legal MT", "TI MT", "Equipo backend BR"]
related:
  - "ADR-070-bright-data-scraping-policy.md"
  - "ADR-055-ssrf-policy-image-probe.md"
sprint: "S4"
project: "mt-pricing-mdm-phase1"
supersedes: []
superseded_by: []
---

# ADR-071 — Playwright self-host para Noon UAE

## 1. Contexto

US-1A-09-03 / US-1A-09-04 (Sprint 4) requieren matching pipeline etapa 2 sobre **Noon UAE** además de Amazon UAE. Bright Data (ADR-070) **no tiene dataset oficial Noon UAE**. Las opciones eran:

1. Custom Bright Data scraper actor (Web Scraper IDE) — coste de mantenimiento alto, contrato comercial separado.
2. Self-host Playwright en el worker Celery MT — control total, infra ya existe.
3. Otro provider (Apify, Zyte) — vendor adicional, fricción legal.

Análisis Sprint 4: Noon UAE tiene anti-bot menos agresivo que Amazon, aceptable con Chromium headless + retry conservador. Volumen Fase 1b: ~6 700 calls/mes (igual que Amazon). 

Constraints:
- Q-NEW-S3 (acuerdo legal scraping) cubre TANTO Bright Data como self-host Playwright.
- Pipeline `FetcherPort` ya abstrae el adapter — el comparador no distingue entre Bright Data y Playwright.
- Worker MT corre en Hetzner Docker → tenemos espacio para instalar Chromium (~150 MB binary).
- Tests unit deben pasar SIN Playwright instalado (CI ligero).

## 2. Decisión

Self-host **Playwright + Chromium headless** en el worker Celery MT como adapter Noon UAE (`PlaywrightNoonUaeFetcher`). Reglas:

### 2.1 Stack técnico

- `playwright==1.x` (lib Python sync/async), `chromium` headless (no `firefox`/`webkit` para Fase 1b — single browser reduce maintenance).
- Browser context **pool**: 1 context por request inicialmente; **TODO Sprint 5** evaluar pool de 3-5 contexts pre-cargados para reducir latencia (~2s saving/request).
- Lazy import: `import playwright` solo dentro del método `fetch` cuando `MT_LIVE_NETWORK=true` y `browser_factory` está inyectada — los tests unit y el CI sin browser instalado NO importan la lib.
- Inyección dependencia: el adapter recibe `browser_factory: async callable -> _BrowserContext` (Protocol minimal). Producción usa closure que abre Playwright; tests usan fake con `goto`/`content`/`close`.

### 2.2 Parser HTML aislado

`parse_noon_html(html)` usa regex (Sprint 4 lightweight). **TODO Sprint 5**: swap a `selectolax` o `BeautifulSoup` para robustez ante cambios de DOM. Razón Sprint 4: regex es suficiente para parsear los bloques `data-qa="product-block"` con campos `productTitle`, `priceNow`, `brand`, `lang="ar"` (título árabe).

Parser separado del fetcher → testeable con HTML capturado en `tests/fixtures/noon_uae/*.html`.

### 2.3 Retry y circuit breaker

- **Failure threshold** del circuit breaker: 3 fallos (vs. 5 de Bright Data). Razón: Playwright es operación cara (~3-5s por request). Cortar antes evita degradar el worker.
- **Reset timeout**: 10 min (600s vs. 5 min Bright Data). Self-host requiere más tiempo para que Noon "olvide" el patrón sospechoso.
- **No tenacity retry interno**: si `goto` o `content` lanza, fallamos rápido. La etapa 2 ya tolera fallback stub vía `_degraded()` con flag `degraded_mode=true` en `raw_payload`.

### 2.4 Modo scaffold (gating con `MT_LIVE_NETWORK`)

Igual patrón que ADR-070: `MT_LIVE_NETWORK=false` o `browser_factory=None` → fallback transparente al stub `NoonUaeStubFetcher` con log WARNING. Permite mergear infra sin Q-NEW-S3 firmado.

### 2.5 Despliegue

- `Dockerfile.worker` añade en Sprint 5: `RUN playwright install --with-deps chromium`. Tamaño imagen +200 MB (Chromium + libs).
- Worker corre en cgroup propio con CPU limit (max 2 cores) + memory limit 1.5 GB para evitar que un browser leak afecte otros workers.
- Single browser context por request → no compartir state entre SKUs (cookies, localStorage). `await ctx.close()` en `finally` (ya implementado, líneas 211-213).

## 3. Alternativas consideradas

### 3.1 Bright Data custom scraper (Web Scraper IDE)

**Rechazada**. Coste contractual + curva de aprendizaje (DSL Bright Data). Para 1 channel adicional Fase 1b no compensa. Mantener Playwright in-house es más predecible.

### 3.2 Selenium

**Rechazada**. Playwright es superior en async/await, network mocking, performance. Selenium es legacy en el ecosistema Python actual.

### 3.3 HTTP scraping puro (`httpx` + parsing HTML)

**Rechazada**. Noon UAE renderiza precios y stock con JavaScript client-side (React) — sin browser real, los selectores devuelven placeholders vacíos. Probado en S0 spike interno BR.

### 3.4 Stealth plugins (`playwright-stealth`, fingerprint randomization)

**Defer Sprint 5**. Si en producción detectamos block rate >5 %, añadir `playwright-stealth` o rotación de user-agent. Sprint 4 base implementation, sin stealth.

## 4. Consecuencias

### Positivas

- **Cobertura Noon UAE** sin vendor adicional.
- **Control total** del browser context → podemos añadir cookies de sesión, headers custom, network interceptors si Noon evoluciona.
- **Coste**: cero costo variable (solo CPU/RAM del worker que ya tenemos).
- **Parser aislado y fixturable** → tests deterministas con HTML capturado.

### Negativas

- **Maintenance burden**: si Noon UAE cambia DOM, romperá el parser regex hasta nuevo PR. Mitigación: alarma Sentry sobre `result_count==0` durante >2h consecutivas.
- **Latencia**: ~3-5s por request (browser startup + page render + parse). 224 SKUs × 1 query = ~15 min por full pass. Aceptable para batch nocturno; **TODO S5** evaluar pool reuse.
- **Imagen Docker pesada** (+200 MB). Aceptable para Hetzner; impacta CI build time ~30s.
- **Anti-bot risk**: Noon puede en cualquier momento subir defensas y bloquear Chromium puro. Plan B: añadir `playwright-stealth` (S5) o evaluar Bright Data Custom Scraper (escalar coste).
- **Browser context pool no implementado** Sprint 4 → cada request abre un browser nuevo. Cuesta ~1.5s/request. **TODO S5** US-perf-noon-pool.

## 5. Open questions

- **Q1 (TODO Legal MT)**: confirmar que Q-NEW-S3 cubre self-host Playwright (no solo Bright Data). Si requiere addendum, bloquear activación.
- **Q2 (TODO TI MT)**: dimensionar memoria worker — 1.5 GB inicial. Monitorizar OOM kills primer mes.
- **Q3 (TODO Sprint 5)**: implementar context pool + stealth + parser robusto (selectolax). Crear US-perf-noon-pool con 3 SP.
- **Q4 (TODO Champion MT)**: si Noon agrega CAPTCHA persistente, ¿escalamos a Bright Data Custom Scraper o aceptamos que Noon queda bloqueado? Decision pendiente con datos S5.

## 6. Implementation status

- `mt-pricing-backend/app/services/matching/adapters/playwright_noon_uae.py` — implementado (Sprint 4 scaffold):
  - `_CB_FAILURE_THRESHOLD = 3`, `_CB_RESET_TIMEOUT_S = 600` (líneas 35-36) — más conservador que Bright Data.
  - `_CircuitBreaker` (líneas 39-62).
  - `_BrowserContext` Protocol (líneas 65-77) — contrato testable sin Playwright real.
  - `parse_noon_html` (líneas 80-115) — regex parser stand-alone.
  - `map_noon_to_candidate` (líneas 118-149) — DTO mapping con título árabe en `specs.arabic_title`.
  - `PlaywrightNoonUaeFetcher.fetch` (líneas 182-217) — gating + circuit breaker + browser context lifecycle.
- Lib `playwright` **NO añadida a `pyproject.toml` Sprint 4** — se añade Sprint 5 cuando Q-NEW-S3 firmado y se active red real.
- Tests esperados: `tests/services/matching/adapters/test_playwright_noon_uae.py` con `_BrowserContext` fake (HTML hardcoded) cubriendo parser + circuit breaker.

## 7. Trazabilidad

- Sprint 4 backlog US-1A-09-04.
- `mt-product-matching-pipeline-detail.md` §4.1.
- ADR-070 — adapter complementario (Amazon UAE).
- Risk register: R-scraping-legal (Q-NEW-S3), R-noon-anti-bot (mitigado por circuit breaker + plan B Bright Data).
