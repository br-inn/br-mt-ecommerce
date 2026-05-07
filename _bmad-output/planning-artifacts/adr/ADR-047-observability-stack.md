# ADR-047: Stack de Observabilidad — Sentry + structlog + Better Stack + Prometheus + Grafana Cloud + OpenTelemetry

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT
- Supersedes: parcialmente ADR-019 (mismo dominio en stack Node.js; ADR-047 lo reescribe para FastAPI/Python + Celery + Next.js)

## Contexto

`hppt-iom-review_1` (proyecto de referencia) **NO tiene**: Sentry integrado consistentemente, structlog/loguru con processors, Prometheus, Grafana, OpenTelemetry, ni tests Celery con eager mode. Healthcheck nativo Celery (`celery inspect ping`) cuelga bajo carga (broadcast pub/sub se queda sin ack).

MT requiere observabilidad profesional desde Sprint 0 por:
- Compliance VAT UAE 2026 → audit completeness medible.
- Criterios de éxito cuantitativos (recálculo masivo < 60 s, p95 endpoints < 500 ms, tasa éxito imports > 99 %).
- Equipo MT post-handoff de 3 personas necesita diagnóstico autoservicio.
- Workflow de aprobación por excepción → SLI sobre `approval_latency_hours` debe ser instrumentable.

ADR-019 cubría el stack de observabilidad cuando el backend era Next.js Route Handlers (pino + prom-client en Node). El pivote a FastAPI/Python + Celery (ADR-029, ADR-030) deja ADR-019 incompleto: no cubre structlog, sentry-sdk[celery], celery-exporter ni eager-mode testing. ADR-047 lo reescribe.

## Decisión

Adoptar el stack triángulo + tracing **Sentry + structlog + Better Stack + Prometheus + Grafana Cloud + OpenTelemetry → Tempo**, con ingestión vía **Vector** y exporters Prometheus para Postgres / Redis / Celery.

### Componentes

| Capa | Tooling | Donde corre |
|------|---------|-------------|
| Logs estructurados Python | structlog + loguru compat → JSON STDOUT | `app/core/logging.py` (FastAPI) y signals Celery |
| Logs estructurados Node | pino (server) + browser sink HTTP a `/api/observability/logs` | `web/src/lib/logger.ts` |
| Log shipper | Vector (Docker socket source → JSON parse → HTTPS sink) | container `vector` Hetzner |
| Log aggregation | **Better Stack Logs** (managed) | SaaS EU |
| Error tracking | **Sentry SaaS** + integraciones FastAPI/Starlette/Celery/SQLAlchemy/Redis + `@sentry/nextjs` | SaaS |
| Métricas técnicas | `prometheus-fastapi-instrumentator` + `celery-exporter` + `postgres-exporter` + `redis-exporter` | self-host Hetzner |
| Métricas long-term + dashboards | **Grafana Cloud** (Free tier inicial; Pro si > 10K series) | SaaS EU |
| Tracing distribuido | OpenTelemetry SDK + OTLP HTTP → **Tempo (Grafana stack)** | SaaS |
| Frontend RUM (web vitals) | `next/web-vitals` → endpoint backend → Prometheus | self-host + SaaS |

### Decisiones puntuales y justificación

#### Sentry SaaS vs self-host
- Self-host Sentry requiere Postgres + Kafka + Redis + Snuba — ops nightmare para equipo de 3.
- Plan Team USD 26/mes cubre 50K errors + 10K transactions + 100K replays — más que suficiente Fase 1.
- Source maps + release tracking + commits-to-issues integrados out-of-the-box.

#### Better Stack Logs vs Loki self-host vs Datadog
- **Better Stack** (recomendado): alineado con stack BR Innovation, on-call y status integrados, USD 25/mes para 30 GB ingestion.
- **Loki self-host**: USD 10 infra + 1 día/mes ops; descartado Fase 1 (equipo pequeño), revisar Fase 3+ si volumen > 100 GB/mes.
- **Datadog**: USD 100+/mes, overkill Fase 1.

#### Grafana Cloud (free tier) vs Prometheus self-host puro
- TSDB local Prometheus en Hetzner con retention 15d.
- Remote write a Grafana Cloud Free Tier (10K series, 50 GB logs, 14d) para dashboards persistentes y long-term.
- Si > 10K series → upgrade a Pro USD 49/mes; pivote disponible sin tocar app code.

#### structlog + loguru compat (no solo loguru)
- structlog tiene processors componibles → fácil añadir PII redaction, contextvars merge, JSONRenderer.
- Loguru se mantiene como fachada para libs (legacy) que llaman `loguru.logger.info()`.
- Decisión: structlog primario; loguru-to-structlog handler.

#### OpenTelemetry → Tempo (no Jaeger / no Honeycomb)
- Tempo está incluido en Grafana Cloud Free Tier (50 GB traces/mes).
- Misma UI que Grafana → un panel para metrics + logs + traces (correlación trace_id ↔ logs).
- Sample rate: 100 % errores (tail-sampling Tempo) + 10 % éxito + 0 % healthchecks.

#### Custom business metrics
- `mt_prices_auto_approved_total{channel,scheme}` (Counter)
- `mt_prices_pending_review_total{channel}` (Gauge)
- `mt_prices_approval_latency_seconds` (Histogram)
- `mt_import_runs_duration_seconds{source,status}` (Histogram)
- `mt_comparator_match_confidence{competitor}` (Histogram)
- `mt_translation_coverage_ratio{lang}` (Gauge)
- `mt_external_api_calls_total{provider,operation}` + `mt_external_api_cost_usd_total{provider}` (Counter)

### Dashboards Grafana mínimos (6)

1. Service Health — RPS, p50/p95/p99, error rate, saturación.
2. Celery Health — queue depth, active workers, task rate succeed/failed/retried, task duration p95.
3. Database Health — connections, slow queries, replication lag, table bloat, index hit ratio.
4. Business KPIs — pending_review, auto-approve %, cobertura traducción, comparator confidence.
5. Cost Dashboard — APIs externas USD/día, Hetzner uso, Supabase storage.
6. Error Budget — SLO compliance %, burn rate 1h/6h/24h.

### PII redaction

Procesador structlog redacta automáticamente claves: `password`, `passwd`, `token`, `secret`, `authorization`, `cookie`, `api_key`, `apikey`, `access_token`, `refresh_token`. Email se enmascara parcialmente: `pablo@x.com` → `p***@x.com`. Audit canónico vive en Postgres (ADR-007) y NO atraviesa Better Stack.

## Alternativas evaluadas

### Datadog all-in-one
- Pros: APM + logs + metrics + RUM en un panel.
- Contras: USD 200+/mes Fase 1, overkill.
- Veredicto: Revisar Fase 3+.

### ELK self-host
- Pros: control total, sin coste licencia.
- Contras: Elasticsearch JVM (RAM intensiva en Hetzner), ops complejas.
- Veredicto: descartado.

### Honeycomb (tracing)
- Pros: best-in-class para tracing exploratorio.
- Contras: separado de logs/metrics, otro proveedor.
- Veredicto: descartado por unificación con Grafana Cloud.

### Sentry self-host
- Pros: residencia datos.
- Contras: stack pesado (Postgres + Kafka + Redis + Snuba).
- Veredicto: descartado por ops.

### Solo logs (sin métricas dedicadas)
- Contras: derivar KPIs de logs es lento + caro; criterios de éxito son cuantitativos.
- Veredicto: descartado.

## Consecuencias positivas

- Errores capturados con stacktrace + source maps + release vinculado a commit.
- Logs JSON searchables con request_id ↔ trace_id ↔ user_id correlacionables.
- 6 dashboards Grafana operativos S1; KPIs de negocio derivables del sistema (no Excel paralelo).
- SLOs medibles → error budget basis para release decisions.
- Stack agnóstico: Vector permite pivotar Better Stack → Loki sin tocar app; Prometheus permite pivotar Grafana Cloud → self-host.

## Consecuencias negativas / riesgos

- Coste mensual SaaS USD 145–180 Fase 1 (cap USD 250 con alerta).
- Si MT exige residencia UAE estricta para logs operativos, Better Stack EU no alcanza → pivote forzado a Loki self-host UAE (impacto: +1 día setup + ops).
- structlog + processors añade ~5 ms latencia por request en p99 (medido con instrumentator); aceptable.
- Equipo MT post-handoff debe manejar Grafana queries básicas (PromQL); incluir en runbooks (US-1A-09-11).

## Cuándo revisar

- **Cierre Fase 1a (S5)**: validar 6 dashboards funcionando con datos reales.
- **Cierre Fase 1b (S10)**: SLO compliance medible; ajustar targets si baseline ≠ proyección.
- **Fase 3 (storefront live)**: revisar volumen logs (probable upgrade Better Stack); evaluar Datadog si tráfico > 1M req/día.
