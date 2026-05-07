# Runbook — Observability stack (Sentry + Better Stack)

**Story**: US-1A-OBS-01 · **ADR**: ADR-077 (carries ADR-019 + ADR-047)
**Owner**: DevOps / on-call rotation MT
**Última actualización**: 2026-05-07

---

## 1. Componentes

| Componente | Provider | Región | Doppler secret |
|------------|----------|--------|----------------|
| Sentry backend | Sentry SaaS | EU | `SENTRY_DSN_BACKEND` |
| Sentry worker | Sentry SaaS | EU | `SENTRY_DSN_WORKER` |
| Sentry frontend | Sentry SaaS | EU | `SENTRY_DSN_FRONTEND` |
| Better Stack logs | Better Stack | EU | `BETTER_STACK_LOGS_TOKEN_*` |
| Prometheus `/metrics` | self-hosted | Hetzner | n/a (scrape interno) |

Stack se inicializa en lifespan startup via `app.core.observability.configure_observability()`.
Idempotente — las pruebas resetean estado con `reset_observability_state_for_tests()`.

## 2. Sample rates

| Ambiente | Backend traces | Worker traces | Frontend traces | Replay (frontend) |
|----------|---------------|---------------|-----------------|-------------------|
| dev | 100% | 100% | 100% | 0% |
| staging | 10% | 20% | 10% | 0% |
| production | 5% | 10% | 5% | 1% session / 100% on-error |

Razonamiento: workers tienen menos cardinalidad y son más interesantes para investigar
latencias batch. Frontend en producción mantiene replay solo 1% para no saturar quota.

## 3. PII redaction — defensa en profundidad

1. **structlog processor** (`app/core/logging.py::_redact_pii`) — primera línea, redacta keys
   sensibles ANTES del render.
2. **Sentry `before_send`** (`app/core/sentry.py::_scrub`) — segunda línea, scrub headers + body.
3. **BetterStackHandler** (`app/core/log_handlers.py::_record_to_payload`) — tercera línea,
   redacta extras antes de POST HTTPS.

Lista de keys: `password`, `token`, `secret`, `jwt`, `api_key`, `authorization`, `cookie`,
`x-api-key`, `x-supabase-auth`, `service_role_key`. Emails enmascarados a `xx***@dominio`.

## 4. Alertas — matriz SEV

| SEV | Trigger | Target | Escalation |
|-----|---------|--------|------------|
| SEV1 | error rate > 0.5% (5 min) prod backend | Slack `#mt-alerts` + PagerDuty primary | 10 min → secondary |
| SEV1 | cost ceiling Bright Data > $150 mes | Slack + PagerDuty | inmediato |
| SEV2 | p95 latency > 1s (10 min) | Slack `#mt-alerts` | 30 min |
| SEV2 | Celery task failure rate > 1% (15 min) | Slack | 30 min |
| SEV3 | warning logs > 10/min sostenido | Slack `#mt-tech` | best-effort |

Smoke test alarmas: `infra/scripts/smoke-alerts.sh` (TODO Sprint 6 — generar tráfico sintético).

## 5. On-call rotation

- **Primary**: rotación semanal entre TI MT + DevOps BR (calendario en PagerDuty
  schedule `mt-pricing-primary`).
- **Secondary**: psierra@br-innovation.com (BR backstop).
- **Escalation**: Slack post-mortem en `#mt-alerts`, RCA a 24h, ADR si proceso roto.

## 6. Procedimiento — incidente SEV1 (ejemplo error rate spike)

1. Alarma dispara en `#mt-alerts` + PagerDuty al primary.
2. Primary acuse en 5 min.
3. Abrir Sentry issue link adjunto en alarma. Validar `environment=production` filter.
4. Cross-check Better Stack dashboard `mt-pricing-overview` — confirmar correlation
   con deploy, FX refresh, o DB load spike.
5. Si correlated con deploy reciente (< 30 min), invocar `infra/scripts/hetzner-deploy.sh
   --rollback` (ver `docs/runbooks/cicd.md`).
6. Si no, escalar a secondary y abrir thread RCA.

## 7. Comandos útiles

```bash
# Verificar handler montado en root logger (en runtime)
python -c "from app.core.observability import root_logger_handler_count; print(root_logger_handler_count())"

# Validar Sentry DSN antes de deploy
python -c "from app.core.config import settings; print(bool(settings.SENTRY_DSN))"

# Tail logs en Better Stack via CLI (si betterstack-cli instalado)
betterstack-cli tail --source mt-backend-production --filter level:ERROR
```

## 8. Bloqueos conocidos

- **Sentry DSN reales pendientes** — TI MT debe seedearlos en Doppler workspace MT.
  Mientras `SENTRY_DSN=""`, `configure_sentry()` queda no-op (safe by design).
- **Better Stack source token pendiente** — mismo patrón: `BETTER_STACK_LOGS_TOKEN=""`
  hace que `attach_better_stack_handler()` devuelva `None`.
- **PagerDuty integration** — Sprint 6, no en S5.
