---
stepsCompleted: [init, web-research, schema-analysis, architecture]
inputDocuments:
  - ADR-070-bright-data-scraping-policy.md
  - mt-product-matching-pipeline-detail.md
  - research-spike-product-comparison.md
  - github.com/luminati-io/Amazon-scraper (README)
workflowType: research
research_type: technical
research_topic: BrightData Amazon Web Scraper API — integración en pipeline MT
research_goals: Entender modelo trigger/poll/webhook, schema de datos, costos y latencia, y arquitectura de integración en FastAPI + Celery + Supabase
user_name: psierra
date: 2026-05-13
web_research_enabled: true
source_verification: true
---

# Investigación Técnica: BrightData Amazon Web Scraper API

**Fecha:** 2026-05-13  
**Autor:** psierra  
**Tipo:** Technical Research  
**Relacionado con:** ADR-070, Sprint 5 / US-scraping-async

---

## 1. Resumen Ejecutivo

BrightData ofrece el **Web Scraper API (Datasets v3)** como producto managed que entrega JSON estructurado de Amazon sin que el caller gestione proxies, CAPTCHAs ni parsers HTML. El flujo base es **trigger → snapshot_id → poll hasta `ready`** (latencia media ~13 s/input). Para volúmenes mayores existe modo **webhook push** que evita polling.

La implementación actual del proyecto (Sprint 4) ya tiene el adapter scaffold (`bright_data_amazon_uae.py`) con trigger síncrono + circuit breaker. La arquitectura propuesta aquí cubre la **migración Sprint 5** a modo webhook async, que es el cambio pendiente indicado en ADR-070 §4 Negativas.

---

## 2. Cómo Funciona el BrightData Amazon Web Scraper

### 2.1 Modelo de Operación — Tres Modos

| Modo | Flujo | Latencia percibida | Cuándo usar |
|------|-------|-------------------|-------------|
| **Sync-poll** (S4 actual) | POST trigger → GET snapshot hasta `ready` | ~13 s/input en P50 | Volumen bajo (<50 SKUs/run), bloques sincrónicos |
| **Async-webhook** (S5 target) | POST trigger con `webhook_url` → BrightData hace POST al callback | ~13 s de proceso real, caller libre | Bursts >100 SKUs, Celery tasks |
| **Dataset comprado** (S5+ opcional) | Descarga dataset preconstruido de marketplace BD | Instantáneo | Catálogos completos, data histórica |

### 2.2 Flujo Completo — Trigger + Poll (Modo S4)

```
CALLER                       BRIGHT DATA API
  │                                 │
  │  POST /datasets/v3/trigger      │
  │  ?dataset_id=<AMAZON_AE_ID>     │
  │  Body: [{"url": "..."}]         │
  │─────────────────────────────►   │
  │                                 │  (inicia scraping + proxy rotation)
  │  200 OK: {"snapshot_id": "..."}  │
  │◄─────────────────────────────   │
  │                                 │
  │  loop: GET /datasets/v3/snapshot/<id> │
  │─────────────────────────────►   │
  │  {"status": "collecting"}       │
  │◄─────────────────────────────   │
  │  (esperar 10s)                  │
  │─────────────────────────────►   │
  │  {"status": "ready", "data":[]}  │
  │◄─────────────────────────────   │
```

**Endpoint de trigger:**
```
POST https://api.brightdata.com/datasets/v3/trigger
  ?dataset_id={BRIGHT_DATA_AMAZON_AE_DATASET_ID}
  &format=json
  [&uncompressed_webhook=true]   ← solo en modo webhook
Headers:
  Authorization: Bearer {BRIGHT_DATA_API_KEY}
  Content-Type: application/json
Body: [{"url": "https://www.amazon.ae/dp/B09XXXX"}]
     ó [{"url": "https://www.amazon.ae/s?k=ball+valve+3/4"}]
```

**Endpoint de snapshot (polling):**
```
GET https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}
Headers: Authorization: Bearer {BRIGHT_DATA_API_KEY}
Response status values: "collecting" → "digesting" → "ready"
```

### 2.3 Flujo Webhook (Modo S5 Target)

```
CALLER                        BRIGHT DATA API
  │                                  │
  │  POST trigger + webhook_url=...  │
  │─────────────────────────────►    │
  │  200 OK: {snapshot_id}           │
  │◄─────────────────────────────    │
  │  (Celery task finaliza, worker   │
  │   queda disponible)              │
  │                                  │  (BD scraping... ~13s)
  │                                  │
  │◄─────────────────────────────    │
  │  POST {webhook_url}              │
  │  Body: snapshot_id + data        │
  │  (o solo snapshot_id si         │
  │   uncompressed_webhook=false)    │
```

El webhook POST llega a un endpoint HTTP en nuestra infra → Celery task `process_bright_data_webhook` recoge el snapshot_id y descarga el payload.

### 2.4 Input — Formatos Soportados

BrightData acepta tanto URLs de producto (PDP) como URLs de búsqueda:

```json
[
  {"url": "https://www.amazon.ae/dp/B09XXXX"},
  {"url": "https://www.amazon.ae/s?k=ball+valve+dn15&ref=..."},
  {"url": "https://www.amazon.ae/dp/B08YYYY", "zipcode": "00000", "language": "en_AE"}
]
```

Para el caso MT: preferimos **búsqueda por keyword** (`s?k=<query>`) que retorna los top N resultados del SERP de Amazon, no un producto individual. El adapter actual ya usa este patrón.

---

## 3. Schema de Datos — Respuesta JSON

### 3.1 Campos Confirmados (Product Detail Page)

```json
{
  "url":          "https://www.amazon.ae/dp/B07PZF3QS3",
  "asin":         "B07PZF3QS3",
  "title":        "KitchenAid All Purpose Kitchen Shears...",
  "brand":        "KitchenAid",
  "description":  "These all-purpose shears...",
  "seller_name":  "Amazon.com",
  "initial_price": 11.99,
  "final_price":   8.99,
  "currency":     "USD",
  "availability": "In Stock",
  "rating":       4.8,
  "reviews_count": 77557,
  "categories":   ["Home & Kitchen", "Kitchen & Dining", "..."],
  "images": [
    "https://m.media-amazon.com/images/I/41E7ALk+uXL._AC_SL1200_.jpg",
    "https://m.media-amazon.com/images/I/710B9HpzMPL._AC_SL1500_.jpg"
  ],
  "delivery": [
    "FREE delivery Friday, October 25 on orders over $35",
    "Or fastest Same-Day delivery Today 10 AM - 3 PM"
  ],
  "specifications": {}
}
```

> BrightData documenta **686 campos estructurados** en su dataset Amazon completo. El subset que parseamos (ADR-070 §2.5) cubre los campos necesarios para el match: `asin`, `title`, `brand`, `final_price`, `currency`, `delivery`, `specifications`, `images`.

### 3.2 Mapeo al modelo interno `CandidateRaw`

| Campo BD | Campo `CandidateRaw` | Transformación |
|----------|---------------------|----------------|
| `asin` | `external_id` | directo |
| `title` | `title` | directo |
| `brand` | `brand` | directo |
| `final_price` | `price` | Decimal |
| `currency` | `currency` | directo |
| `images[0]` | `image_url` | primer elemento |
| `delivery` | `delivery_text` | join(", ") |
| `specifications` | `specifications` | dict |
| `seller_name` | `seller` | solo nombre comercial (PDPL) |
| `url` | `source_url` | directo |

### 3.3 Campos PDPL — No Almacenar

Los siguientes campos **NO deben** persistirse según ADR-070 §2.5 y PDPL UAE 2021:
- `reviews` (texto con datos de usuarios)
- `rating_distribution` (si contiene por usuario)
- Cualquier campo `user_id`, `reviewer_name`

---

## 4. Performance y Costos

### 4.1 Latencias

| Métrica | Valor | Fuente |
|---------|-------|--------|
| Latencia media por input | **~13 s** | BrightData README oficial |
| P95 (proyectado) | < 30 s | ADR-070 estimación |
| Modo poll interval recomendado | 10 s | GitHub example |
| Modo webhook delivery | ~13 s desde trigger | BrightData docs |

### 4.2 Pricing

| Plan | Precio | Nota |
|------|--------|------|
| Pay-per-success (general WS API) | $0.75/1,000 req | WebSearch 2026 |
| **Amazon dataset específico** | **$1.50/1,000 req** | Nuestro research spike |
| Volumen Fase 1b (224 SKUs × 1/día) | ~$30/mes | ADR-070 §1 |
| Volumen Fase 2 (5k SKUs × 1/semana) | ~$150/mes | pipeline-detail §4.1 |

> BrightData cobra **solo por requests exitosos** — los 4xx o timeouts no se facturan. Esto es crítico para el circuit breaker: solo los 5xx/HTTPError cuentan hacia el failure threshold.

### 4.3 Rate Limits

No hay documentación pública de rate limits duros para el Web Scraper API (a diferencia de SP-API). El sistema gestiona internamente la rotación de proxies. El constraint real es el presupuesto mensual y el concurrency de jobs simultáneos (configurable en el dashboard BD).

---

## 5. Arquitectura de Integración — Sprint 5

### 5.1 Componentes

```
┌─────────────────────────────────────────────────────────────────┐
│                    CELERY WORKER (mt-worker)                     │
│                                                                  │
│  MatchingPipelineTask                                            │
│    ↓                                                             │
│  BrightDataAmazonUaeFetcher.fetch(query)                        │
│    ├─ [MT_LIVE_NETWORK=false] → AmazonUaeStubFetcher             │
│    └─ [MT_LIVE_NETWORK=true]                                     │
│         ↓                                                        │
│      CircuitBreaker.call()                                       │
│         ↓                                                        │
│      _trigger_with_webhook(query, webhook_url)                  │
│         ↓  POST /datasets/v3/trigger + webhook_url              │
│         ↓  returns snapshot_id                                   │
│      store_in_redis(snapshot_id, task_id, TTL=300s)             │
│         ↓  task suspende / ack'd                                 │
│                                                                  │
└────────────────────────────────────────────────────────────────-┘

                     ┌──────────────────┐
                     │   BRIGHT DATA    │
                     │   (13s scraping) │
                     └────────┬─────────┘
                              │ POST webhook_url
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              FastAPI Webhook Endpoint                            │
│  POST /internal/webhooks/bright-data                            │
│    ├─ Valida X-BD-Signature (HMAC)                              │
│    ├─ Extrae snapshot_id                                        │
│    ├─ Busca task_id en Redis                                    │
│    └─ Encola: process_bright_data_result.delay(snapshot_id)     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Celery Task: process_bright_data_result(snapshot_id)           │
│    ├─ GET /datasets/v3/snapshot/{snapshot_id}                   │
│    ├─ parse_bright_data_amazon(payload)                         │
│    ├─ Filtra campos PDPL                                        │
│    ├─ Persiste en match_candidates (Supabase/Postgres)          │
│    └─ Emite audit log                                           │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Cambios respecto a S4

| Aspecto | Sprint 4 (actual) | Sprint 5 (propuesta) |
|---------|-------------------|----------------------|
| Modo trigger | sync poll en mismo request | trigger async + webhook callback |
| Celery task | bloquea 13s+ esperando snapshot | libera inmediatamente tras trigger |
| Throughput | ~30 candidatos/min (límite poll) | ~300+ candidatos/min (async) |
| Webhook endpoint | no existe | `POST /internal/webhooks/bright-data` |
| Firma webhook | no existe | `X-BD-Signature` HMAC-SHA256 |
| Redis | circuit breaker state | + snapshot_id → task_id map |
| Circuit breaker | implementado (5 fallos) | igual, sin cambios |

### 5.3 Endpoints de la API interna a agregar (S5)

```python
# app/api/routes/webhooks.py
POST /internal/webhooks/bright-data
  Headers: X-BD-Signature: sha256=...
  Body: {"snapshot_id": "...", "status": "ready"}
  → 200 OK (siempre — BrightData reintenta en 4xx/5xx)
```

> **Nota de seguridad**: el endpoint debe estar en una ruta `/internal/` que Caddy solo expone a IPs allowlist (BrightData publica su rango de IPs para callbacks). Alternativa: validar HMAC con `BRIGHT_DATA_WEBHOOK_SECRET`.

### 5.4 Schema Redis para handoff webhook

```
Key:   bright_data:snapshot:{snapshot_id}
Value: {"task_id": "...", "sku": "...", "query": "...", "created_at": timestamp}
TTL:   300s (5 min — si BD no llama en 5 min, el task debe retry via poll)
```

### 5.5 Fallback ante webhook tardío

Si el webhook no llega en 300s (Redis TTL expira), la `MatchingPipelineTask` tiene un step de **reconciliación**: al finalizar el timeout del batch, consulta los `snapshot_id` sin resultado y hace GET poll manual. Esto evita pérdida silenciosa.

---

## 6. Modelo de Datos — Persistencia

```sql
-- match_candidates (ya existente, adiciones S5 marcadas con *)
ALTER TABLE match_candidates
  ADD COLUMN IF NOT EXISTS snapshot_id TEXT,        -- * para rastrear el webhook
  ADD COLUMN IF NOT EXISTS bd_latency_ms INTEGER,   -- * para métricas
  ADD COLUMN IF NOT EXISTS degraded_mode BOOLEAN DEFAULT FALSE;
```

> `raw_payload` ya existe en el schema (ADR-070). TTL 90 días → purge job pendiente ADR S5.

---

## 7. Métricas y Observabilidad (TODO S5)

Siguiendo ADR-070 §2.3 "Métricas Prometheus pendientes":

| Métrica | Tipo | Labels |
|---------|------|--------|
| `bright_data_request_total` | Counter | `outcome: success/error/degraded` |
| `bright_data_latency_ms` | Histogram | `mode: sync/webhook` |
| `bright_data_circuit_state` | Gauge | `state: closed/open/half_open` |
| `bright_data_failure_count` | Gauge | — |
| `bright_data_webhook_received_total` | Counter | `status: ready/error` |
| `bright_data_snapshot_pending` | Gauge | snapshots en Redis esperando webhook |

---

## 8. Open Questions / Tareas Pendientes

| ID | Pregunta / Tarea | Owner | Sprint |
|----|-----------------|-------|--------|
| Q1 | Firmar Q-NEW-S3 (contrato legal scraping) | Legal MT | Bloqueante para prod |
| Q2 | Provisionar `BRIGHT_DATA_AMAZON_AE_DATASET_ID` + `BRIGHT_DATA_API_KEY` en Doppler | TI MT | Bloqueante |
| Q3 | Obtener IP range BrightData para webhook allowlist en Caddy | DevOps BR | S5 |
| Q4 | Definir `BRIGHT_DATA_WEBHOOK_SECRET` para firma HMAC | DevOps BR | S5 |
| Q5 | Implementar `POST /internal/webhooks/bright-data` endpoint | Backend BR | S5 |
| Q6 | Migrar `BrightDataAmazonUaeFetcher.fetch` a modo webhook | Backend BR | S5 |
| Q7 | Implementar reconciliación por TTL Redis (fallback poll) | Backend BR | S5 |
| Q8 | Agregar métricas Prometheus listadas en §7 | Backend BR | S5 |
| Q9 | Purge job `raw_payload` a 90 días | Backend BR | S5 |

---

## 9. Conclusiones

1. **El mecanismo BrightData es sólido**: trigger async → snapshot_id → webhook es el patrón correcto para Celery. La implementación S4 sync-poll es funcional para 224 SKUs/día pero no escala.

2. **El schema JSON está confirmado**: los campos clave (`asin`, `title`, `brand`, `final_price`, `images`, `delivery`) ya están implementados en `parse_bright_data_amazon`. No hay sorpresas.

3. **El costo es predecible**: $1.50/1k req → $30/mes Fase 1b, escalable linealmente. Dentro del presupuesto.

4. **El bloqueante es legal, no técnico**: `Q-NEW-S3` (firma del acuerdo) es el único bloqueante real para activar `MT_LIVE_NETWORK=true`. La infra puede mergearse ahora.

5. **La migración a webhook (S5) es ~1-2 SP**: el adapter ya tiene la estructura correcta; es agregar el endpoint de callback, el Redis handoff, y cambiar `_call_bright_data` de sync-poll a trigger+return.

---

## 10. Referencias y Fuentes

- [BrightData Amazon Scraper — Página de producto](https://brightdata.com/products/web-scraper/amazon)
- [GitHub: luminati-io/Amazon-scraper — README oficial con schema y código Python](https://github.com/luminati-io/Amazon-scraper)
- [BrightData Docs: Trigger data collection API](https://docs.brightdata.com/scraping-automation/web-data-apis/web-scraper-api/trigger-a-collection)
- [BrightData Docs: Async requests + webhook](https://docs.brightdata.com/api-reference/web-scraper-api/asynchronous-requests)
- [BrightData Pricing: Web Scraper](https://brightdata.com/pricing/web-scraper)
- ADR-070 (este proyecto) — `_bmad-output/planning-artifacts/adr/ADR-070-bright-data-scraping-policy.md`
- ADR-072 (este proyecto) — `_bmad-output/planning-artifacts/adr/ADR-072-amazon-sp-api-integration.md`
- `mt-product-matching-pipeline-detail.md` §4 — `_bmad-output/planning-artifacts/`
