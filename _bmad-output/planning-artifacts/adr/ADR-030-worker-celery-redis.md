# ADR-030: Worker async Celery + Redis

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT
- Supersedes: ADR-018 (BullMQ + Redis)

## Contexto

La plataforma necesita ejecutar tareas largas / asíncronas / batch:

- Imports masivos (PIM, costos, traducciones, FX).
- Recálculos masivos de pricing tras cambio de FX o coste.
- OCR pipeline (Fase 1.5+, listings competidores).
- Embeddings (Fase 1.5+).
- Fan-out del comparador (búsqueda de candidatos, scoring).
- Notificaciones (digest diario, emails).
- Publish a marketplaces (Fase 3+).

Con el pivot a backend Python (ADR-029), BullMQ deja de tener sentido (es JS-native).

## Decisión

**Adoptar Celery (Python) con broker Redis.**

| Componente | Implementación |
|-----------|----------------|
| Broker | Redis (compartido con cache + rate-limit; bases lógicas separadas) |
| Result backend | Redis (TTL configurable) o Postgres para tareas auditables |
| Beat scheduler | `celery beat` (refresh FX, digest 18:00 UAE, retención de jobs) |
| Workers | `celery worker` por queue, escalado horizontal independiente |
| Routing | Por queue (`imports`, `recompute`, `images`, `notifications`, `publish`, `embeddings`, `ocr`, `domain_events`) |
| Idempotencia | `task_id = SHA256(input)` para deduplicar |
| Retries | Configurables por task (retries + exponential backoff) |
| DLQ | Queue dedicada `dlq_*` consumida por task que registra y notifica |
| Schedule jobs ligeros | APScheduler in-process en backend FastAPI (no Celery) |

## Alternativas evaluadas

- **BullMQ + Redis (ADR-018)**: descartada — requiere worker en Node.js; con backend Python no tiene sentido.
- **Dramatiq**: API más simple que Celery, broker RabbitMQ/Redis. Menos ecosistema, menos integraciones con Sentry/Prometheus listos.
- **RQ (Redis Queue)**: minimalista pero le faltan beat scheduler nativo, prioridades, complex routing.
- **Arq**: async Celery competitor — más nuevo, menos battle-tested.
- **Temporal / Cadence**: overkill Fase 1.

## Consecuencias positivas

- **Maduro y battle-tested** en producción Python.
- **Beat** + APScheduler cubren todos los schedules.
- **Routing por queue + concurrency tuning** permiten escalar piezas calientes sin tocar las frías.
- **Sentry + Prometheus instrumentation** out-of-the-box.
- Alineado con hppt-iom (a verificar contra el repo de referencia).

## Consecuencias negativas / riesgos

- **Configuración non-trivial** (settings, rutas, serialización).
- **Errores de serialización** clásicos si se pasan objetos complejos — convención: tasks reciben IDs primitivos, fetch dentro del task.
- **Beat single-instance** → si Beat cae, jobs programados se pierden; mitigación: monitor de Beat + restart automático.

## Cuándo revisar

- **Fase 2** si volumen de tareas crece > 100k/día → considerar particionado por broker o pasar a Temporal.
- Si la latencia de tareas críticas no es aceptable, evaluar Dramatiq/Arq.
