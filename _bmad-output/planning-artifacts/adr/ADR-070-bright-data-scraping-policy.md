---
adr: "ADR-070"
title: "Bright Data — adapter Amazon UAE oficial con residential proxy + retry + circuit breaker"
status: "proposed"
date: "2026-05-07"
author: "Pablo Sierra (Comercial · Online)"
deciders: ["Champion MT", "Paula (DPO)", "Legal MT", "TI MT", "Equipo backend BR"]
related:
  - "ADR-055-ssrf-policy-image-probe.md"
  - "ADR-071-playwright-self-host-noon.md"
  - "ADR-049-migration-discipline.md"
sprint: "S4"
project: "mt-pricing-mdm-phase1"
supersedes: []
superseded_by: []
---

# ADR-070 — Bright Data scraping policy para Amazon UAE

## 1. Contexto

US-1A-09-03 (Sprint 4) reemplaza el stub `AmazonUaeStubFetcher` (S3) por el adapter real para la etapa 2 del pipeline matching (`mt-product-matching-pipeline-detail.md` §4.2). Amazon UAE bloquea scraping directo desde IPs cloud (Hetzner, AWS) — IP rotation residential + cumplimiento de robots.txt + manejo legal son obligatorios.

Constraints:

- **Q-NEW-S3** (acuerdo legal scraping con Champion + Legal MT) **bloquea** la activación real hasta firma. Mientras tanto, scaffold infra mergeable.
- Volumen objetivo Fase 1b: 224 SKUs × 1 query Amazon UAE/24h = ~6 700 calls/mes. Bursts esperados al lanzar nuevos SKUs.
- PDPL UAE (Personal Data Protection Law 2021) requiere no almacenar datos personales del seller (solo product attributes públicos).
- Coste ≈ $0.001-0.005 por request en plan Bright Data Web Scraper API → ~$30/mes Fase 1b. Aceptable.
- Necesitamos **fallback gracioso** al stub canned cuando el provider está degradado, para no romper el pipeline aguas abajo.

## 2. Decisión

Adoptamos **Bright Data Web Scraper API** como adapter oficial para Amazon UAE con:

### 2.1 Stack técnico

- HTTP cliente `httpx.AsyncClient` con `Bearer` auth via `BRIGHT_DATA_API_KEY` (env, Doppler en prod).
- Endpoint default: `https://api.brightdata.com/datasets/v3/trigger` (override via `BRIGHT_DATA_BASE_URL`).
- Dataset ID via `BRIGHT_DATA_AMAZON_AE_DATASET_ID`.
- Marketplace fixed: `amazon_ae`. Limit por query: 20 candidatos.
- Bright Data gestiona el residential proxy pool — NO gestionamos IPs nosotros.

### 2.2 Retry exponencial (`tenacity`)

- 3 attempts max (`stop_after_attempt(3)`).
- Backoff exponencial: `wait_exponential(multiplier=1.0, max=4.0)` → ~1s, 2s, 4s entre attempts.
- Solo retry sobre `httpx.HTTPError` (timeouts, 5xx). 4xx no se reintenta.

### 2.3 Circuit breaker `_CircuitBreaker`

Implementación mínima (no `pybreaker`, no thread-safe — worker async single-loop):

- **Failure threshold**: 5 fallos seguidos → state `OPEN`.
- **Reset timeout**: 5 min (300s) → state `HALF_OPEN` automático en siguiente request, que cuenta como probe.
- **State `OPEN`**: rechaza inmediato, devuelve fallback `_degraded(stub_results)` con flag `raw_payload.degraded_mode=true`.
- Métricas Prometheus pendientes (TODO US-S5): `bright_data_circuit_state`, `bright_data_failure_count`, `bright_data_request_total{outcome}`.

### 2.4 Modo scaffold (gating con `MT_LIVE_NETWORK`)

Mientras `MT_LIVE_NETWORK != true` (default `false` en dev/CI/staging actual):

- El adapter cae transparente al stub `AmazonUaeStubFetcher` sin abrir conexión real. Mismo contrato `FetcherPort` → no afecta consumidores.
- Tests unit pasan sin Bright Data ni red.

Al activar `MT_LIVE_NETWORK=true` + credenciales completas:

- Primera invocación abre HTTP cliente con `Bearer` token.
- Si faltan credenciales pero el flag está on → fallback stub con `degraded_mode=true` y log WARNING (no abort).

### 2.5 Cumplimiento PDPL + Q-NEW-S3

- **NO almacenar** datos personales: el parser `parse_bright_data_amazon` extrae solo `asin`, `title`, `brand`, `price`, `currency`, `delivery_text`, `specifications`, `image_urls`, `seller` (anónimo solo nombre comercial). Nunca direcciones, ratings asociados a usuarios, comentarios.
- **Audit log obligatorio**: cada request live emite log INFO con `actor='matching_pipeline'`, `sku`, `query_text`, `latency_ms`, `result_count`.
- **Retention**: el `raw_payload` se guarda en `match_candidates.raw_payload` (S3) con TTL 90 días — pasado el TTL, purge job (TODO ADR Sprint 5).
- **Robots.txt**: Bright Data se compromete contractualmente (Web Scraper API ToS) a respetar robots.txt y rate limits. NO replicamos esa lógica nosotros.
- **Legal sign-off**: Q-NEW-S3 firmado por Champion + Legal MT antes de flipar `MT_LIVE_NETWORK=true` en staging/prod. ADR-070 referenciado en el contrato.

## 3. Alternativas consideradas

### 3.1 Self-host Playwright en residential proxy propio

**Rechazada para Amazon UAE**. Amazon detecta y bloquea Playwright headless en minutos sin investment fuerte en stealth (CAPTCHA solving, fingerprint randomization). Bright Data es state-of-the-art en este vertical y mucho más barato vs. construir infra propia. **Sí** la adoptamos para Noon (ADR-071) porque Bright Data NO cubre Noon UAE.

### 3.2 Apify

**Rechazada**. Coste similar (~$0.005/req) pero menos cobertura UAE marketplaces. Bright Data tiene dataset oficial Amazon AE; Apify requeriría custom actor + maintenance.

### 3.3 Scrapy + BrightData proxies (DIY)

**Rechazada**. Implica mantener parsers HTML, manejar CAPTCHAs, retries específicos de Amazon. La API de Bright Data ya provee JSON estructurado → reduce superficie 5x.

### 3.4 Amazon SP-API search en lugar de scraping

**Rechazada para etapa 2**. SP-API (ADR-072) cubre productos del seller MT, NO búsqueda libre por keyword en el catálogo Amazon completo (esa API requiere Buyer scope). Etapa 2 del pipeline necesita ver competidores → scrape público.

## 4. Consecuencias

### Positivas

- **Compliance-friendly**: BrightData absorbe responsabilidad de robots.txt y rate limit. Nuestro layer hace audit + PDPL filtering.
- **Resiliencia**: circuit breaker + fallback stub = pipeline aguas abajo nunca queda bloqueado por outage upstream.
- **Coste predecible** ($30-50/mes Fase 1b).
- **Testabilidad**: scaffold mode con `MT_LIVE_NETWORK=false` permite CI verde sin Bright Data.

### Negativas

- **Vendor lock-in light**: cambio a otro provider requiere reescribir parser (~50 LOC) y re-firmar acuerdo legal. Mitigación: parser aislado en función pura `parse_bright_data_amazon`.
- **Latencia**: Bright Data Web Scraper API es asíncrono (trigger + poll dataset). Sprint 4 implementación usa endpoint sincrónico simple — funcional pero limitado a ~30 candidatos/min. **TODO S5**: migrar a webhook callback async para bursts >100 SKUs.
- **No thread-safe** circuit breaker — válido para worker async single-loop. Si en el futuro corremos multi-process Celery, swap a `pybreaker` (TODO ADR Sprint 5/6).
- **PDPL audit retention 90 días**: requiere job purge — pendiente ADR Sprint 5.

## 5. Open questions

- **Q1 (TODO Legal MT)**: firmar Q-NEW-S3 antes de `MT_LIVE_NETWORK=true` en staging. **BLOQUEANTE** activación real.
- **Q2 (TODO TI MT)**: provisionar `BRIGHT_DATA_AMAZON_AE_DATASET_ID` y `BRIGHT_DATA_API_KEY` en Doppler.
- **Q3 (TODO Sprint 5)**: migrar a webhook async + métricas Prometheus + retention purge.

## 6. Implementation status

- `mt-pricing-backend/app/services/matching/adapters/bright_data_amazon_uae.py` — implementado (Sprint 4 scaffold):
  - `_DEFAULT_RETRY_ATTEMPTS = 3`, `_DEFAULT_RETRY_MIN_WAIT_S = 1.0`, `_DEFAULT_RETRY_MAX_WAIT_S = 4.0` (líneas 47-50).
  - `_CB_FAILURE_THRESHOLD = 5`, `_CB_RESET_TIMEOUT_S = 300` (líneas 51-52).
  - `_CircuitBreaker` (líneas 55-91) — estados CLOSED/OPEN/HALF_OPEN.
  - `parse_bright_data_amazon` (líneas 94-147) — parser pure-function.
  - `BrightDataAmazonUaeFetcher.fetch` (líneas 200-234) — orquesta gating live + circuit breaker + retry + fallback stub.
  - `_call_bright_data` (líneas 236-271) — HTTP envuelto en `AsyncRetrying`.
- Tests esperados: `tests/services/matching/adapters/test_bright_data_amazon_uae.py` (≥ 8 tests cubriendo gating off → stub, circuit open → degraded, parser robusto, retry exhausted → degraded).

## 7. Trazabilidad

- Sprint 4 backlog US-1A-09-03.
- `mt-product-matching-pipeline-detail.md` §4.2.
- ADR-055 SSRF — los image probes downstream del adapter aplican SSRF guard.
- ADR-071 — adapter Noon (alternativa para channel no cubierto por Bright Data).
- Risk register: R-scraping-legal (Q-NEW-S3), R-vendor-outage (mitigado por circuit breaker).
