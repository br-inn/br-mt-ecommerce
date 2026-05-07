---
title: "Production-Readiness Master Plan — MT Middle East MDM + Pricing Fase 1"
status: "draft"
version: "1.0"
created: "2026-05-06"
project_name: "mt-pricing-mdm-phase1"
purpose: "Síntesis ejecutiva de los 5 design docs de production-readiness; one-page para sponsor + roadmap consolidado"
related:
  - "production-readiness-gap-analysis.md"
  - "mt-observability-design.md"
  - "mt-migrations-iac-secrets-design.md"
  - "mt-security-compliance-design.md"
  - "mt-dr-runbooks-sla-design.md"
adrs_nuevos: ["ADR-047", "ADR-048", "ADR-049", "ADR-050", "ADR-051", "ADR-052", "ADR-053", "ADR-054"]
---

# Production-Readiness Master Plan

## 1. Estado actual

**Readiness estimado: ~62 %.** Bloques fuertes (arquitectura+datos 95 %, audit/RBAC 90 %, importers/pricing 85 %); bloques débiles (CI/CD+IaC 35 %, UX/a11y 40 %, compliance 45 %, testing 50 %, reliability/DR 55 %, seguridad transversal 55 %, observability 60 %).

## 2. Lo que se acaba de cerrar (puntos 3, 4, 5)

| Punto | Decisión aplicada |
|-------|-------------------|
| **3 — Healthchecks** | 6 endpoints + 1 frontend: `/health/live`, `/health/ready`, `/health/db`, `/health/redis`, `/health/storage`, `/health/celery` (custom non-blocking via Redis heartbeat — el nativo está deshabilitado en hppt). Bypass rate-limit en Caddy. |
| **4 — Observability profesional** | **Sentry SaaS** (errores) + **structlog/loguru + Vector → Better Stack Logs** (logs centralizados con PII redaction) + **Prometheus self-host → Grafana Cloud Free** (métricas) + **OpenTelemetry → Tempo** (tracing) + **Better Stack Uptime/On-call/Status**. Tests Celery con `task_always_eager` + testcontainers Postgres+Redis + Schemathesis contract. |
| **5 — Disciplina de migraciones** | **Alembic** gestiona `public.*` (tablas + funciones + triggers); **Supabase migrations** gestiona `auth.*` + `storage.*` + RLS críticas. CI corre suite migrate-up + migrate-down; expand-contract pattern obligatorio; pgTAP para RLS. **Drift detection semanal** que compara prod vs migraciones. **Terraform + hcloud + Ansible** para IaC Hetzner. **Doppler** para secrets con rotación trimestral + gitleaks pre-commit. |

## 3. Documentos producidos (5 nuevos design + 8 ADRs)

| Documento | Path |
|-----------|------|
| Production-Readiness Gap Analysis | [_bmad-output/planning-artifacts/production-readiness-gap-analysis.md](production-readiness-gap-analysis.md) |
| Observability + Healthchecks design | [_bmad-output/planning-artifacts/mt-observability-design.md](mt-observability-design.md) |
| Migrations + IaC + Secrets design | [_bmad-output/planning-artifacts/mt-migrations-iac-secrets-design.md](mt-migrations-iac-secrets-design.md) |
| Security + Compliance design | [_bmad-output/planning-artifacts/mt-security-compliance-design.md](mt-security-compliance-design.md) |
| DR + Runbooks + SLAs design | [_bmad-output/planning-artifacts/mt-dr-runbooks-sla-design.md](mt-dr-runbooks-sla-design.md) |
| ADR-047 Observability stack | [adr/ADR-047-observability-stack.md](adr/ADR-047-observability-stack.md) |
| ADR-048 Healthchecks endpoints | [adr/ADR-048-healthchecks-endpoints.md](adr/ADR-048-healthchecks-endpoints.md) |
| ADR-049 Migration discipline | [adr/ADR-049-migration-discipline.md](adr/ADR-049-migration-discipline.md) |
| ADR-050 IaC Hetzner Terraform | [adr/ADR-050-iac-hetzner-terraform.md](adr/ADR-050-iac-hetzner-terraform.md) |
| ADR-051 Secrets management Doppler | [adr/ADR-051-secrets-management-doppler.md](adr/ADR-051-secrets-management-doppler.md) |
| ADR-052 SLI/SLO + error budget | [adr/ADR-052-sli-slo-error-budget.md](adr/ADR-052-sli-slo-error-budget.md) |
| ADR-053 Backup + DR strategy | [adr/ADR-053-backup-dr-strategy.md](adr/ADR-053-backup-dr-strategy.md) |
| ADR-054 Rate limiting + WAF | [adr/ADR-054-rate-limiting-waf-strategy.md](adr/ADR-054-rate-limiting-waf-strategy.md) |

## 4. Top 10 gaps must-Fase1 (~52 SP)

| # | Gap | SP | Sprint |
|---|-----|----|----|
| 1 | Restore desde backup ensayado pre-cutover | 5 | S6 |
| 2 | Secret manager (Doppler) + rotación | 8 | S0-S1 |
| 3 | SAST + SCA + container scan + gitleaks como gate CI | 5 | S0 |
| 4 | Healthchecks granulares por componente | 3 | S0-S1 |
| 5 | SLO + error budget formal | 5 | S3 |
| 6 | Migrations safety: dry-run + expand-contract + rollback | 5 | S0-S1 |
| 7 | Idempotencia + DLQ + retry/jitter en Celery | 8 | S2 |
| 8 | Audit log con hash chain (tamper-evident) | 5 | S2 |
| 9 | Coverage targets + flaky-test detection | 3 | S0-S1 |
| 10 | RLS audit completo por tabla con pgTAP | 5 | S2 |
| **Total** | | **52** | |

## 5. Trabajo total de hardening

**~157 SP adicionales** distribuidos en 8 nuevas épicas:

| Épica | SP | Foco |
|-------|----|----|
| EP-1A-09 Observability stack | 58 | Sentry + Better Stack + Prometheus + Grafana + OTel + 6 dashboards + alerting + SLO |
| EP-1A-10 Healthchecks + status page | 8 | 6 endpoints + status page Better Stack |
| EP-1A-11 Security hardening | 21 | OWASP + headers + rate limit + RLS audit + MFA + dep scanning |
| EP-1A-12 Migration discipline | 13 | Alembic + Supabase split + pgTAP + drift detector |
| EP-1A-13 IaC Terraform | 21 | Modules + envs + bootstrap + DR drill |
| EP-1A-14 Secrets management | 8 | Doppler + rotation + gitleaks |
| EP-1A-15 Compliance VAT/PDPL | 13 | DPA + retention + right-to-be-forgotten + DPO designation |
| EP-1A-17 DR + Backups | 13 | 3-2-1 cross-provider + restore drill |
| EP-1A-18 Runbooks operativos | 8 | 15 runbooks |
| EP-1A-19 Incident management | 8 | On-call + post-mortem + status page |
| **Total** | **171** | |

(Total previo Fase 1: ~431 SP. Total con hardening: ~602 SP — 12-15 sprints de 2 semanas con 2-3 devs FTE = ~6-7 meses Fase 1 completa.)

## 6. Stack de operación profesional adicional al stack base

| Categoría | Servicio elegido | Costo aprox. mensual |
|-----------|------------------|----------------------|
| Error tracking | Sentry Team | USD 26 |
| Logs centralizados | Better Stack Logs | USD 25 |
| On-call + Status page | Better Stack Uptime + On-call | USD 30 |
| Métricas + dashboards | Grafana Cloud Free → Pro | USD 0-49 |
| Secrets management | Doppler Team | USD 20-40 |
| IaC backend | Terraform Cloud Free | USD 0 (free tier) |
| Backup cross-provider | Cloudflare R2 + Backblaze B2 | USD 10-30 |
| **Total observability + ops** | | **USD 110-200/mes** |
| Cap budget recomendado | | **USD 250/mes** |

(Excluye Hetzner servers + Supabase tier + LLM/embeddings/scrapers que son del stack base.)

## 7. SLI / SLO / Error Budget Fase 1

| SLI | SLO | Error budget mensual |
|-----|-----|---------------------|
| Disponibilidad backend API horario laboral GCC (8-18 GST L-V) | 99.5 % | ~3.6 h/mes |
| Latencia p95 endpoints CRUD | < 500 ms | 5 % de requests >SLO |
| Latencia p95 motor pricing recálculo SKU | < 5 s | 5 % requests |
| Latencia p95 recálculo masivo (5086 × 5 × 4) | < 60 s | 5 % runs |
| Tasa de éxito imports | > 99 % | 1 % falla |
| Tasa de éxito tasks Celery por queue | > 99 % | 1 % falla |
| **Total burn rate alerts**: 1h/6h/24h windows con multi-burn-rate. |

## 8. RTO / RPO Fase 1

| Target | Valor Fase 1 | Valor Fase 3 (proyectado) |
|--------|-------------|---------------------------|
| RTO | 4 h | 1 h |
| RPO | 1 h | 15 min |
| Disponibilidad horario laboral GCC | 99.5 % | 99.9 % |
| Disponibilidad fuera de horario | best-effort | 99 % |

Backups: **3-2-1 cross-provider** — Supabase PITR (primary) + Cloudflare R2 (secondary) + Backblaze B2 (tertiary cold). Cifrado age. Restore weekly drill. Retention 7 días daily + 4 weekly + 12 monthly + 7 yearly (audit VAT UAE).

## 9. Top 5 decisiones que requieren acción del cliente / sponsor

| # | Decisión | Owner | Bloquea |
|---|----------|-------|---------|
| 1 | **Plan tier Supabase** (Pro $25 vs Team) — define si PITR cubre RPO 1h | TI MT + Pablo | Backups + DR |
| 2 | **Residencia datos UAE estricta** (Hetzner Frankfurt OK o forzar UAE) | TI MT + Sponsor | Provider stack |
| 3 | **DPO designation PDPL UAE** — interno MT, compartido BR, o consultor externo | Sponsor MT + legal | Compliance go-live |
| 4 | **MFA obligatorio** para `gerente_comercial` y `ti_integracion` Fase 1 | Sponsor MT | Security baseline |
| 5 | **Cap presupuestal observability** — USD 250/mes razonable Fase 1 | Sponsor MT | Stack final |

## 10. Recomendación priorización 

Como la app es **single-tenant interna con 3 usuarios**, no necesita el mismo nivel de hardening que un SaaS B2C público. Recomendación honesta:

- **Sí must Fase 1** (no negociable): top 10 gaps (52 SP) + observability core (Sentry + healthchecks + structlog) + secrets + migration discipline + DR básico (backups cross-provider + restore drill).
- **Should Fase 1 si tiempo alcanza**: dashboards Grafana completos + IaC Terraform + threat modeling + 15 runbooks completos + status page público.
- **Could Fase 1, mover a Fase 1.5 si presión cronograma**: SAST avanzado + mutation testing + visual regression + DPO formal (pero compliance VAT 2026 no se posterga).
- **Fase 2+**: HA Postgres + DR drill anual + chaos testing + on-call 24/7.

## 11. Próximos pasos inmediatos

1. **Decisiones Sponsor (esta semana)**: 5 puntos del §9.
2. **Refinement backlog**: integrar las 8 nuevas épicas a `epics-and-stories-mt-pricing-mdm-phase1.md` con SP definitivos por sprint.
3. **Sprint 0 expandido**: agregar entregables hardening críticos (Doppler setup + healthchecks base + structlog + Sentry init + first migration con expand-contract pattern).
4. **Threat modeling session** con TI MT en S0 (output: STRIDE + top 10 threats + controls residual).
5. **Decision sobre tier Supabase + residencia datos** — gate para provisioning S0-D12.

## 12. Métricas de éxito del plan

Al cierre de Fase 1:
- Readiness ≥ 92 % (todos los must + 80 % de los should).
- 0 SEV1 sin runbook.
- DR drill ejecutado al menos 1 vez con tiempo medido < target.
- Pen-test externo opcional con 0 critical findings.
- Compliance VAT UAE 2026 verificado por audit muestra de 50 cambios de precio.
- SLO compliance > 95 % de meses.
- Cobertura tests > 80 % core / 100 % motor pricing.
- Audit trail tamper-evident validado (hash chain).
- All ADRs status `accepted`.

---

**Total ADRs activos**: 54 (45 anteriores + 8 nuevos + ADR-046 que se confirmó).
**Total documentos planificación**: 16 (los 11 anteriores + 5 nuevos design docs).
**Total SP Fase 1 con hardening**: ~602 SP (12-15 sprints, ~6-7 meses).
**Total stack ops adicional**: USD 110-200/mes.

---

## Adendum (ronda 2 — 2026-05-06)

7 artefactos críticos adicionales producidos para cerrar la planificación autónoma antes de Sprint 1:

| Artefacto | Path | Métrica clave |
|-----------|------|---------------|
| OpenAPI 3.1 contract | [mt-api-contract-openapi.yaml](mt-api-contract-openapi.yaml) | 82 operations, 67 paths, 80 schemas, 20 tags |
| SQLAlchemy 2.0 async models | [mt-sqlalchemy-models.md](mt-sqlalchemy-models.md) | 28 tablas, mixins, JSONB tipado, repository skeleton |
| CI/CD pipeline + workflows | [mt-cicd-pipeline.md](mt-cicd-pipeline.md) | 11 workflows + 4 Dockerfiles + Caddyfile + scripts |
| Frontend tech design | [mt-frontend-tech-design.md](mt-frontend-tech-design.md) | 22 decisiones + 7 patrones canónicos + estructura completa |
| Sprint 1 backlog refinado | [sprint1-backlog-refined.md](sprint1-backlog-refined.md) | 11 stories, 53 SP (con plan de descarga a 36-39 SP) |
| Risk register consolidado | [risk-register-consolidado.md](risk-register-consolidado.md) | 49 riesgos (19 Critical, 23 High, 7 Medium) |
| Cost estimate full stack | [cost-estimate-full-stack.md](cost-estimate-full-stack.md) | Mínimo USD 169/mo · Recomendado USD 734/mo · Cap USD 850/mo · POC USD 1900 one-time · Fase 3 USD 3258/mo |

**Total documentos planificación**: 23 (los 16 anteriores + 7 nuevos).
**Total ADRs**: 54 (sin nuevos en esta ronda — los nuevos diseños referencian ADRs existentes).
