# ADR-052: SLI / SLO / Error budget — definición canónica Fase 1

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT, Gerente Comercial
- Related: ADR-047 (stack observabilidad), ADR-048 (healthchecks), ADR-007 (audit trail), ADR-010 (no aprobado no integra)

## Contexto

Criterios de éxito Fase 1 (PRD + brief) son cuantitativos:
- Recálculo masivo (5086 SKUs × 5 esquemas × 4 canales) < 60 s.
- p95 endpoints CRUD < 500 ms.
- Tasa éxito imports > 99 %.
- Cobertura traducción AR/ES > 95 % al go-live.
- Compliance VAT UAE 2026 → audit completeness 100 %.

Sin SLI/SLO formales: cada release es decisión basada en intuición ("se ve bien"). Con SLI/SLO + error budget: el equipo tiene una métrica objetiva para decidir "freeze releases" vs "ship features". Error budget también define burn rate alerts → on-call accionable y evita fatigue.

## Decisión

Definir **7 SLIs canónicos** con SLOs Fase 1 y error budgets calculados sobre ventana mensual rolling de 30 días. Burn rate alerts en 3 ventanas (1h / 6h / 24h) según multi-window multi-burn-rate alerting (Google SRE workbook).

### SLIs / SLOs

| # | SLI | Formula | SLO Fase 1 | Error budget mes (30d) | Owner |
|---|-----|---------|------------|------------------------|-------|
| 1 | Disponibilidad API backend | `1 - (5xx_count / total_count)` excluyendo `/health/*` | **99.5 %** | 3 h 36 min downtime | TI MT |
| 2 | Latencia p95 endpoints CRUD | `histogram_quantile(0.95, ...)` para `/products`, `/costs`, `/prices` | **< 500 ms** | 5 % requests pueden exceder | TI MT |
| 3 | Latencia p95 motor pricing recálculo SKU individual | duración endpoint `POST /pricing/recompute/{sku}` | **< 5 s** | 5 % requests exceder | BR |
| 4 | Latencia p95 recálculo masivo | duración task `mt.pricing.recompute_full` | **< 60 s** | 5 % runs exceder | BR |
| 5 | Tasa éxito imports | `import_runs[status=ok] / import_runs[total]` | **> 99 %** | 1 % runs pueden fallar | BR / Comercial |
| 6 | Tasa éxito tasks Celery por queue | `celery_task_succeeded / (succeeded+failed)` | **> 99 %** queues `pricing` `imports`; **> 95 %** queue `comparator` (research) | acorde | BR |
| 7 | Audit completeness | `audit_events_count / dml_count_critical_tables` | **100 %** | 0 — gate compliance | TI MT |

#### Notas por SLI

- **SLI 1**: ventana de medición = mes rolling 30d (no calendario). Excluye downtime planificado anunciado con ≥ 24 h.
- **SLI 4**: el recálculo masivo Fase 1 = 5086 × 5 × 4 = 101 720 combinaciones; 60 s es target Fase 1; Fase 2 con 50K SKUs = 1M combinaciones → SLO se reescala a < 5 min.
- **SLI 6**: queue `comparator` tiene SLO laxo (95 %) porque es research workstream (ADR-012); fallos transitorios de OCR/VLM/Bright Data son aceptables.
- **SLI 7**: 100 % es no-negociable por compliance VAT UAE 2026; cualquier mismatch es P0.

### Error budget calculation

Para SLI de availability con SLO 99.5 % en ventana 30d:
- Total minutos: 30 × 24 × 60 = 43 200.
- Permitido downtime: 43 200 × (1 - 0.995) = **216 min = 3 h 36 min**.

Para SLI latencia p95 con SLO < 500 ms y 100 K requests/mes:
- Permitido requests > 500 ms: 100 000 × 0.05 = **5 000 requests**.

### Burn rate alerts (multi-window multi-burn)

Burn rate = `(error_rate_actual / (1 - SLO))` — cuántas veces más rápido se está consumiendo budget que el ritmo sostenible.

| Ventana | Burn rate | Significado | Severidad | Acción |
|---------|-----------|-------------|-----------|--------|
| 1 h | > 14.4× | A este ritmo, budget mes consumido en ≤ 2 h | **P0** | SMS + on-call + freeze deploys |
| 6 h | > 6× | Budget consumido en ≤ 5 días | **P1** | Slack + on-call |
| 24 h | > 1× | Budget consumido en ≤ 30 días | **P2** | Slack |
| 24 h | > 0× sostenido 7d | Drift hacia consumo total | **P3** | review en weekly |

### Implementación PromQL

```promql
# Burn rate 1h SLI 1 (availability)
(
  sum(rate(http_requests_total{status=~"5..", path!~"/health/.*"}[1h]))
  /
  sum(rate(http_requests_total{path!~"/health/.*"}[1h]))
) / (1 - 0.995)

# Burn rate 1h SLI 2 (latency p95)
(
  sum(rate(http_request_duration_seconds_bucket{le="0.5", path=~"/(products|costs|prices).*"}[1h]))
  /
  sum(rate(http_request_duration_seconds_count{path=~"/(products|costs|prices).*"}[1h]))
)
```

### Release policy basada en error budget

| Estado budget | Política releases |
|---------------|-------------------|
| > 50 % restante | Ship features sin restricción. |
| 20 – 50 % restante | Ship features con review extra; priorizar fixes operativos. |
| < 20 % restante | **Freeze releases nuevas features**; solo bugfixes / mejoras reliability. |
| Agotado | Postmortem obligatorio + plan de mejora reliability antes de próximo deploy de feature. |

### Dashboard Grafana "Error Budget"

- Gauge por SLI: `% budget restante mes en curso`.
- Time series: burn rate 1h vs umbrales 14.4× / 6×.
- Tabla: días restantes proyectados (lineal) por SLI.
- Annotations: deploys (vinculados a release Sentry).

### SLI 7 (audit completeness) — caso especial

No tiene error budget tradicional (SLO = 100 %). Se reporta como:
- Counter `mt_audit_completeness_violations_total` — cualquier valor > 0 es alarma P0.
- Sanity check nightly: `count(audit_events WHERE created_at::date = yesterday) vs count(mutations on critical tables yesterday)`.
- Discrepancia → ticket compliance + investigación.

## Alternativas evaluadas

### SLOs sin error budget (solo metas)
- Pros: simple.
- Contras: no informa decisiones release; equipo no sabe cuándo "frenar".
- Veredicto: descartado.

### SLOs por endpoint individual (granularidad fina)
- Pros: precisión.
- Contras: 50+ SLOs, no ownable Fase 1 con equipo de 3.
- Veredicto: agrupado por dominio (CRUD / pricing recompute SKU / recompute masivo).

### Ventana 7d (en lugar de 30d)
- Pros: respuesta más rápida a regresiones.
- Contras: ruido alto con tráfico bajo (3-10 usuarios concurrentes Fase 1).
- Veredicto: 30d Fase 1; revisar a 7d Fase 3 cuando tráfico crezca.

### SLO disponibilidad 99.9 % (3 9s)
- Pros: estándar industria.
- Contras: implica 43 min/mes downtime → necesita HA replica Postgres + multi-replica backend; coste e infra Fase 1 no lo justifican.
- Veredicto: 99.5 % Fase 1 (3 h 36 min); revisar Fase 3+.

## Consecuencias positivas

- Decisiones release basadas en datos (error budget).
- On-call accionable: P0 cuando burn rate 14.4× evita fatigue.
- KPIs de reliability comunicables a Christian (sponsor) sin detalles técnicos.
- Compliance VAT 2026: SLI 7 medible y auditable.
- Equipo MT post-handoff hereda metas claras.

## Consecuencias negativas / riesgos

- Tracking SLI burn rate requiere PromQL queries no-triviales; documentar en runbooks (US-1A-09-11).
- Mes 1 baseline puede mostrar SLOs no alcanzables → ajustar (no relajar arbitrariamente; revisar arquitectura).
- 99.5 % availability requiere disciplina deploys (canary, rollback rápido) — coste organizacional.

## Cuándo revisar

- **S5 (cierre Fase 1a)**: validar baseline SLI con 4 semanas datos staging.
- **S10 (cierre Fase 1b)**: ajustar SLOs si baseline real ≠ proyección; consensuar con TI MT + Christian.
- **Fase 2** (mensual ops): elevar SLO availability 99.5 → 99.9 si infra HA en marcha.
- **Fase 3** (storefront público): SLI separado customer-facing vs admin (storefront SLO 99.9 %, admin 99.5 %).
