---
adr: "ADR-072"
title: "Amazon SP-API integration — LWA + AWS Sigv4 + role assumption + token bucket por endpoint"
status: "proposed"
date: "2026-05-07"
author: "Pablo Sierra (Comercial · Online)"
deciders: ["Champion MT", "TI MT", "Legal MT", "Equipo backend BR"]
related:
  - "ADR-070-bright-data-scraping-policy.md"
  - "ADR-049-migration-discipline.md"
sprint: "S4"
project: "mt-pricing-mdm-phase1"
supersedes: []
superseded_by: []
---

# ADR-072 — Amazon SP-API integration

## 1. Contexto

US-1A-09-05 (Sprint 4) reemplaza el stub `AmazonSPApiStub` (S3) por el adapter real para **channel mirror** del seller MT en Amazon UAE. SP-API es la API oficial Amazon para sellers (catálogo, inventario, pricing, listings). Es funcionalmente distinto del scraping (ADR-070):

- Scraping (Bright Data) ve **competidores públicos** en el marketplace.
- SP-API ve los **propios listings del seller MT** (operaciones autenticadas con permission granted by seller).

Marketplace: Amazon.ae (`MARKETPLACE_ID=A2VIGQ35RCS4UG`). SP-API endpoint región Europe: `https://sellingpartnerapi-eu.amazon.com`.

Constraints:

- Auth: **LWA (Login with Amazon)** OAuth2 con `refresh_token` long-lived → `access_token` 60min TTL.
- Antes de Sept-2023, SP-API también requería **AWS Sigv4** sobre cada request firmando con credenciales temporales obtenidas via `sts:AssumeRole`. **Update Oct-2023**: Amazon eliminó el requisito Sigv4 para la mayoría de endpoints (ver release notes SP-API 2023-10-04). El header `x-amz-access-token` con LWA token es suficiente. **Sprint 4 sigue release post-2023 — sin Sigv4** salvo endpoints legacy (Reports + Feeds aún piden sigv4 a fecha 2026-05).
- Rate limit por endpoint distinto (e.g. `getCatalogItem`: 2 req/s burst 6; `submitListings`: 5 req/s burst 10). Necesita **token bucket por endpoint**.
- Credenciales TI MT pendientes: `SP_API_REFRESH_TOKEN`, `SP_API_LWA_CLIENT_ID`, `SP_API_LWA_CLIENT_SECRET`, `SP_API_SELLER_ID`, `AWS_ROLE_ARN_SP_API`. **BLOQUEANTE** activación real.
- Reusar `httpx.AsyncClient` y `tenacity` retry pattern de ADR-070 para coherencia.

## 2. Decisión

Adoptamos cliente **custom `AmazonSPApiAdapter`** sobre `httpx` + `tenacity`, sin SDK third-party (`python-amazon-sp-api` evaluada y descartada — ver §3.3). Reglas:

### 2.1 Endpoints implementados Sprint 4

- **`getCatalogItem`**: `GET /catalog/2022-04-01/items/{ASIN}` con `marketplaceIds`, `includedData=attributes,summaries`. Usado por `pull_listing(sku, external_id=ASIN)` para sincronizar `title_en`, `brand`, `material`, `HS_code`.
- **`submitListings` (PATCH)**: `PATCH /listings/2021-08-01/items/{seller_id}/{ASIN}` con `marketplaceIds`. Usado por `push_diff(sku, external_id, diff_payload)` para empujar cambios.

### 2.2 LWA token refresh

Implementación en `_refresh_lwa_token`:

- POST `https://api.amazon.com/auth/o2/token` con `grant_type=refresh_token`.
- Cache in-memory en el adapter: `self._lwa_token` + `self._lwa_token_expires_at = monotonic + 3500s` (margen seguridad sobre 3600s default).
- `_ensure_token` revisa expiración y refresca lazy.

### 2.3 AWS Sigv4 (defer Sprint 5)

**Sprint 4 NO firma Sigv4** para los endpoints que documenta esta ADR (`getCatalogItem`, `submitListings` están post-2023 sin Sigv4). Si en S5 se activa Reports / Feeds (que aún piden Sigv4 en 2026), el plan es:

- Lib: `boto3` + `requests-aws4auth` (port async via `httpx-aws4auth` o monkey-patch). Alternativa: SDK oficial `python-amazon-sp-api` (descartada en §3.3).
- Role assumption: `STS:AssumeRole` con `AWS_ROLE_ARN_SP_API` (provisto por TI MT) → credenciales temporales 1h. Cache temporal en Redis con TTL 50min.
- Header `Authorization: AWS4-HMAC-SHA256 ...` añadido al request firmado.

Documentamos esta decisión como **TODO S5 / ADR-XXX** cuando aplique. Sprint 4 deja método `_call_sp_api` con retry + LWA — el firmado Sigv4 se monta encima sin refactor.

### 2.4 Rate limit token bucket por endpoint (defer Sprint 5)

**Sprint 4** confía en el retry exponential (`tenacity` con 3 attempts, 1-4s) para absorber rate-limit 429. **Sprint 5** se introduce token bucket explícito:

- Lib candidata: `aiolimiter` o custom.
- Buckets por (channel, endpoint): `getCatalogItem`: 2 req/s burst 6; `submitListings`: 5 req/s burst 10.
- Estado del bucket en Redis (compartido entre workers Celery).
- Si bucket vacío → backoff hasta refill antes de hacer la request (no consume retry).

Sprint 4 acepta riesgo de 429 esporádicos absorbidos por retry — volumen Fase 1b (224 SKUs × 1 sync/24h = ~9 SKUs/h) está muy por debajo de cualquier rate limit.

### 2.5 Modo scaffold (gating con `MT_LIVE_NETWORK` + creds)

- Si `MT_LIVE_NETWORK != true` o faltan `SP_API_REFRESH_TOKEN` / `SP_API_LWA_CLIENT_ID` / `SP_API_LWA_CLIENT_SECRET` → fallback transparente a `AmazonSPApiStub` (S3).
- Permite mergear infra sin credenciales TI MT.

### 2.6 Retry y errores

- 3 attempts (`stop_after_attempt(3)`), backoff 1-4s, retry sobre `httpx.HTTPError`.
- 4xx (auth fail, ASIN missing) NO se reintenta.
- Si `pull_listing` retry exhausted → fallback stub. `push_diff` retry exhausted → `PublishResult(ok=False, message=sp_api_error: ...)` (no se cae al stub porque el stub no representa el resultado real).

## 3. Alternativas consideradas

### 3.1 SDK oficial Amazon (Java / .NET)

**Rechazada**. No tenemos Java/.NET en stack. Mantener bridge a Python SDK no compensa.

### 3.2 `python-amazon-sp-api` (Saleweaver)

**Rechazada**. Lib popular pero síncrona — no encaja con worker async Celery. El refactor a async es mantenible (~50 LOC para LWA + Sigv4 helper) y nos da control del retry/circuit breaker patterns ya estandarizados en ADR-070.

### 3.3 `selling-partner-api-sdk-python` (oficial Amazon)

**Rechazada para Sprint 4**. SDK relativamente nuevo (2023), API surface incompleta para `submitListings 2021-08-01`. Reconsiderar S5 si Amazon mejora cobertura.

### 3.4 SP-API + scraping en lugar de scraping puro (ADR-070)

**No alternativa**: SP-API solo da listings del propio seller, NO competidores. Las dos integraciones coexisten.

## 4. Consecuencias

### Positivas

- **Cliente nativo httpx async** → consistente con resto del stack (`bright_data_amazon_uae.py`, `vlm_judge.py`).
- **LWA token caching** elimina overhead de OAuth en cada request (~300ms saving).
- **Scaffold gradual**: arrancar con endpoints catalog + listings basic; sumar Reports/Feeds + Sigv4 cuando haga falta sin refactor.
- **Coste cero** (SP-API gratuito hasta cierto volumen).

### Negativas

- **Sigv4 deferred**: si en S5 activamos Reports, se necesita firma. ADR-072 marca el plan pero no implementa. **TODO ADR S5**.
- **Token bucket per-endpoint deferred**: riesgo 429 mayor a volumen Fase 2 (B2C marketplace). Mitigación: monitorizar `sp_api_429_total` y avanzar US-perf-sp-api-bucket S5.
- **Credenciales bloqueantes**: TI MT debe completar `SP_API_*` env. Sin esas vars el adapter funciona en modo stub indefinidamente (no es bug, es feature scaffold).
- **Token refresh in-memory**: cada worker process tiene su propio LWA token. Aceptable Fase 1b. En S5 con multi-worker compartir vía Redis ahorra calls LWA (~2/h).
- **Sin Sigv4 → `submitListings` puede fallar** en regiones que aún lo exigen (raro post-2023, pero validar en staging UAE).

## 5. Open questions

- **Q1 (TODO TI MT)**: provisionar `SP_API_REFRESH_TOKEN`, `SP_API_LWA_CLIENT_ID`, `SP_API_LWA_CLIENT_SECRET`, `SP_API_SELLER_ID`, `AWS_ROLE_ARN_SP_API` en Doppler. **BLOQUEANTE**.
- **Q2 (TODO Champion MT)**: confirmar que el seller account MT tiene las roles SP-API necesarios (`Product Listing`, `Pricing`).
- **Q3 (TODO Sprint 5)**: si `submitListings` retorna 403 por Sigv4 missing → priorizar US-sp-api-sigv4 (1-2 SP).
- **Q4 (TODO Sprint 5)**: implementar token bucket per-endpoint con estado Redis (US-perf-sp-api-bucket).

## 6. Implementation status

- `mt-pricing-backend/app/services/channel_mirror/adapters/amazon_sp_api.py` — implementado (Sprint 4 scaffold):
  - `MARKETPLACE_ID = "A2VIGQ35RCS4UG"` Amazon.ae (línea 43).
  - `_DEFAULT_BASE_URL = "https://sellingpartnerapi-eu.amazon.com"` (línea 44).
  - `_DEFAULT_LWA_URL = "https://api.amazon.com/auth/o2/token"` (línea 45).
  - `_LWA_TOKEN_TTL_S = 3500` (línea 48).
  - `parse_catalog_item` (líneas 51-88) — parser pure-function.
  - `_refresh_lwa_token` (líneas 133-153).
  - `_ensure_token` (líneas 155-158) — cache TTL.
  - `_call_sp_api` (líneas 160-179) — HTTP wrapper con `tenacity` retry.
  - `pull_listing` (líneas 181-210) — `getCatalogItem` integration con fallback stub.
  - `push_diff` (líneas 212-256) — `submitListings 2021-08-01` PATCH.
- Stub legacy preservado en `amazon_sp_api_stub.py` para fallback.
- Tests esperados: `tests/services/channel_mirror/test_amazon_sp_api.py` mockeando `httpx.AsyncClient` (LWA refresh + getCatalogItem + submitListings success/failure paths).

## 7. Trazabilidad

- Sprint 4 backlog US-1A-09-05.
- ADR-070 — adapter scraping complementario (NO autenticado).
- Channel mirror module design: `mt-product-matching-pipeline-detail.md` §11.
- Risk register: R-sp-api-creds-missing (BLOQUEANTE TI MT), R-sp-api-rate-limit (mitigado parcialmente por retry, deferred bucket).
