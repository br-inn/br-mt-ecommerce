# ADR-019: Observabilidad (Sentry + Pino + Better Stack / Grafana)

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT

## Contexto

Fase 1 es uso interno MT (3-10 usuarios concurrentes), pero compliance UAE 2026 + criterios de éxito (recálculo masivo < 60 s, p95 latencia, tasa auto_approve, cobertura traducción) requieren métricas reales, no anécdota.

Necesitamos: errores capturados, logs estructurados searchables, métricas de negocio, métricas técnicas, dashboard.

## Decisión

### Triángulo de observabilidad

#### 1. Errores → Sentry SaaS

- SDK `@sentry/nextjs` integrado en frontend + backend.
- Breadcrumbs, scope con `user.id`, `user.role`, `request.id`.
- Filtros para excluir errores user-side esperados (validación Zod).
- Source maps subidos en CI.
- Alertas Slack a canal `#mtme-alerts`.

#### 2. Logs estructurados → Pino → STDOUT (recolectado por plataforma)

Formato JSON line-per-event. Campos obligatorios:

```json
{
  "ts": "2026-05-06T12:34:56.789Z",
  "level": "info|warn|error|debug",
  "service": "web|worker|api",
  "request_id": "uuid",
  "user_id": "uuid|null",
  "user_role": "comercial|gerente_comercial|...",
  "msg": "Price approved",
  "ctx": { "sku": "VLV-001", "channel": "amazon_uae", "scheme": "FBA", "price_id": "uuid" },
  "duration_ms": 12,
  "err": { "type": "...", "message": "...", "stack": "..." }
}
```

Pino config:
- Redaction: `password`, `token`, `secret`, `authorization`, `cookie`, `*.encrypted`.
- Level por entorno: `debug` dev, `info` staging, `info` prod.
- Pretty-print solo dev (Pino-pretty); prod always JSON.

Recolección:
- Plataforma de despliegue (Vercel / Railway / Fly.io) recoge STDOUT y reenvía.
- Destino: **Better Stack Logs** (recomendado Fase 1 — barato, search rápido, dashboard incluido), o Grafana Loki si TI MT prefiere self-hosted.

#### 3. Métricas → Better Stack / Grafana

**Métricas técnicas**:

| Métrica | Tipo | Labels | Alerta |
|---------|------|--------|--------|
| `http_requests_total` | counter | route, method, status | p95 > 500 ms |
| `http_request_duration_ms` | histogram | route, method | — |
| `db_query_duration_ms` | histogram | query_name | p95 > 200 ms |
| `queue_size` | gauge | queue_name | > 1000 |
| `job_duration_ms` | histogram | queue_name, job_type | p95 > 5 min |
| `job_failed_total` | counter | queue_name, error_type | rate > 5/min |
| `db_connections` | gauge | — | > 80 % pool |

**Métricas de negocio** (críticas — declaradas en brief):

| Métrica | Definición | Alerta |
|---------|------------|--------|
| `price_auto_approve_rate` | % de submits que pasan a auto_approved | si > 90 % o < 30 % por 1 día |
| `price_recompute_duration_ms` | duración recálculo masivo | p95 > 60 s |
| `translation_coverage_ratio` | % SKUs publicables con AR/ES approved | < 95 % |
| `price_rejection_rate` | % `pending_review` rechazados | > 30 % |
| `import_run_success_rate` | % imports completados sin error | < 95 % |
| `audit_events_per_day` | count por día (sanity check audit funciona) | < 10 (anomalía) |
| `approval_latency_hours` | tiempo entre `pending_review` y `approved` | p95 > 24 h |
| `unmatched_skus_total` | SKUs sin match en comparador | > 15 % (research workstream) |

**Implementación**:
- En Node.js: `prom-client` exporta a `/metrics` endpoint.
- Better Stack (Vector / OpenTelemetry agent) scrappea endpoint cada 30 s.
- Dashboard "MT ME — Operations" con paneles:
  - Top: tráfico, errores, latencia.
  - Mid: queue health, DB.
  - Bottom: KPIs de negocio.

#### Dashboard recomendado

**Better Stack** Fase 1 (logs + metrics + uptime + dashboard combinado, ~$25/mes equipo pequeño). Si TI MT exige self-hosted: Grafana + Prometheus + Loki.

#### Alerting

- Pager Sentry → Slack canal `#mtme-alerts`.
- On-call rotación BR (Fase 1) + TI MT post-handoff.
- Escalación: P0 (sistema caído / regla dura ADR-010 violada) → SMS + llamada.

#### Tracing (opcional Fase 2+)

- OpenTelemetry instrumentation en Node.js, traza HTTP → DB → Queue.
- Destino Honeycomb / Datadog APM si se necesita.
- Fase 1: solo logs estructurados con `request_id` (poor man's tracing).

### Privacidad y residencia

- Logs no contienen PII más allá de email + role.
- Better Stack tiene regiones EU/US — configurar EU si UAE no disponible.
- Audit log canónico vive en Postgres (ADR-007); Better Stack es secundario para operación.

## Alternativas evaluadas

### Alternativa A: Datadog (todo-en-uno)
- **Pros**: APM + logs + metrics + síntesis.
- **Contras**: caro a escala. Overkill Fase 1.
- **Veredicto**: revisar Fase 3+.

### Alternativa B: Grafana Cloud
- **Pros**: ecosistema open + cloud.
- **Contras**: setup más complejo que Better Stack.
- **Veredicto**: opción si TI MT prefiere ecosistema Grafana.

### Alternativa C: Self-hosted ELK
- **Pros**: control total.
- **Contras**: ops nightmare para equipo pequeño.
- **Veredicto**: descartada Fase 1.

### Alternativa D: Sólo logs (sin métricas dedicadas)
- **Pros**: simplicidad.
- **Contras**: agregar métricas de negocio desde logs es lento + costo de query.
- **Veredicto**: descartada — métricas son criterio de éxito.

## Consecuencias positivas

- Visibilidad rápida de problemas.
- KPIs de negocio derivables del sistema, no de Excel paralelo.
- Cumple criterios de éxito (recálculo < 60 s medible).

## Consecuencias negativas / riesgos

- Coste mensual SaaS (~$50-100 Fase 1; escala con volumen).
- Si MT exige residency UAE estricta para logs, Better Stack puede no servir → Grafana Cloud EU o self-hosted.

## Cuándo revisar

- **Cierre Fase 1a**: probar dashboard con datos reales.
- **Cierre Fase 1b**: validar que las métricas capturan los criterios de éxito.
- **Fase 3** (cargas mayores): revisar pricing tier o migrar a Datadog.
