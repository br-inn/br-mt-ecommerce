# ADR-018: Cola de jobs (BullMQ + Redis)

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT

## Contexto

Operaciones que **no** caben en request/response HTTP:
- Imports masivos (PIM, costos, Excel demo) — segundos a minutos.
- Recálculo masivo de precios tras cambio FX o coste — segundos a minutos.
- Mirror de imágenes (descarga + upload S3) — minutos.
- Notificaciones (email, in-app digest) — segundos.
- Connector publish a marketplaces (Fase 3+) — segundos a minutos por batch.
- Backfill de embeddings (Fase 1.5+) — horas.

Necesitamos: cola fiable, retries con backoff, idempotencia, observabilidad, jobs delayed (cron-style).

## Decisión

**BullMQ + Redis** como sistema de jobs.

### Justificación

- Stack TS-native (Node.js).
- Madurez (sucesor de Bull, mantenido).
- Idempotencia via `jobId` único.
- Retries + exponential backoff de fábrica.
- Delayed jobs + repeated jobs (cron expressions).
- Bull Board (UI) o Arena para inspección operativa.
- Queue events → métricas Sentry / Prometheus.

### Topología

- **Redis instance**: managed (Upstash / Redis Cloud / AWS ElastiCache) o self-hosted en el mismo cluster que la app.
- **Queues por dominio**:
  - `imports` (PIM, costos, Excel demo).
  - `recompute` (recálculo precios).
  - `images` (mirror, transformaciones).
  - `notifications` (email, digest).
  - `publish` (connectors Fase 3+).
  - `embeddings` (Fase 1.5+).
- **Workers**: proceso separado (`apps/worker`) ejecutando suscripciones a las colas. NO en el mismo proceso Next.js (separación de concerns + escalado independiente).
- **Concurrency** por queue (config):
  - imports: 2 (limita carga DB).
  - recompute: 4.
  - images: 8.
  - notifications: 16.
  - publish: 4 (rate limits marketplaces).

### Idempotencia

- Cada job tiene `jobId` derivado del input (`SHA256(...)`).
- Reintentar con mismo `jobId` reusa el job, no duplica.
- Workers idempotentes por construcción (al inicio chequean si la operación ya se completó).

### Retries

- Default: 3 intentos, exponential backoff `[2^n * 1000ms]` → 1s, 4s, 9s, 16s.
- Failed jobs van a DLQ (`{queue}_failed`) tras maxAttempts.
- Alerta vía Sentry si DLQ > N items / hora.

### Observabilidad

- Métricas: `queue_size`, `job_completed_total`, `job_failed_total`, `job_duration_seconds`.
- Logs estructurados por job: `{queue, jobId, status, duration_ms, error?}`.
- Bull Board accesible solo a `admin` y `ti_integracion` vía rol auth middleware.

### Eventos de dominio (al completarse jobs)

Aunque BullMQ es queue (no event bus), publicamos eventos de dominio en otra cola dedicada `domain_events` (ver doc principal sección 10). Ej. `PriceApproved` → consumed by `recompute` listener si el approval impacta otros canales.

## Alternativas evaluadas

### Alternativa A: AWS SQS + Lambda
- **Pros**: managed, escalable.
- **Contras**: Lambda cold-start; integración con Postgres requiere VPC; lock-in AWS; coste por ejecución.
- **Veredicto**: descartada Fase 1.

### Alternativa B: Postgres-as-queue (pgmq, pgmq similar)
- **Pros**: una sola infra.
- **Contras**: Postgres no está optimizado para queue patterns (long-polling caro). Limitación de throughput.
- **Veredicto**: descartada Fase 1; Fase 4 a 50k SKUs si Redis es bottleneck reconsiderar.

### Alternativa C: Temporal
- **Pros**: workflow engine + queue + state.
- **Contras**: infra compleja + curva aprendizaje. Overkill Fase 1.
- **Veredicto**: descartada.

### Alternativa D: Inngest / Trigger.dev (SaaS workflow)
- **Pros**: zero-infra.
- **Contras**: lock-in SaaS, data residency.
- **Veredicto**: descartada Fase 1.

## Consecuencias positivas

- Stack simple (Node + Redis + Postgres).
- Operación familiar para BR.
- Escalado: añadir workers horizontalmente.
- Bull Board da visibilidad operativa rápida.

## Consecuencias negativas / riesgos

- Redis es single point of failure si no está en HA. Mitigación: Redis managed con replica + AOF persistence.
- BullMQ jobs > 30 min son inestables (recomendación de la lib). Mitigación: jobs largos se chunkean (ej. backfill de embeddings: 1 job por chunk de 1000 SKUs).

## Cuándo revisar

- **Cierre Fase 1b**: medir queue throughput real.
- **Fase 3** (connector real): re-evaluar concurrency limits para no romper rate limits marketplaces.
- **Fase 4**: si > 50k SKUs y throughput sostenido, evaluar Temporal.
