---
title: "Production-Readiness Gap Analysis — MT Middle East MDM + Pricing Fase 1"
status: "draft"
version: "1.0"
created: "2026-05-06"
project_name: "mt-pricing-mdm-phase1"
related: ["prd-mt-pricing-mdm-phase1.md", "architecture-mt-pricing-mdm-phase1.md", "epics-and-stories-mt-pricing-mdm-phase1.md", "sprint0-plan-consolidado.md"]
---

# Production-Readiness Gap Analysis — MT Middle East MDM + Pricing Fase 1

> **Lente.** Single-tenant interno (3-5 usuarios MT), 224 SKUs, criticidad operativa moderada (afecta pricing real con dinero), regulación VAT UAE 2026 + PDPL UAE. No es SaaS B2C ni fintech. La barra "profesional" se calibra a esa realidad: imprescindible auditabilidad, reproducibilidad, observabilidad mínima, DR ensayado y handoff documentado. No imprescindible: WAF managed enterprise, distributed tracing OTel completo, mutation testing, A/B platform, status page público.

---

## 1. Resumen ejecutivo

### 1.1 Estado de readiness estimado

**Cobertura agregada actual de docs (PRD v1.4 + Arch v1.4 + Épicas + Sprint0): ~62 % de readiness profesional Fase 1.**

| Bloque | % cobertura docs | Nota |
|--------|------------------|------|
| Auditoría + RBAC + RLS | 90 % | Cubierto a fondo (ADR-005, ADR-007, NFR-08/33-36, §15) |
| Arquitectura + datos | 95 % | DDL completo, ADR-045/046, hexagonal connectors |
| Importers + reglas pricing | 85 % | Bien especificados; gaps en idempotencia formal y DLQ |
| Seguridad transversal | 55 % | Headers/CSP/RBAC OK; faltan SAST, DAST, gitleaks CI, dep scan automatizado |
| Observabilidad | 60 % | Sentry + structlog + Prometheus mencionados; faltan SLO formales, runbooks, on-call rotation post-handoff |
| Reliability / DR | 55 % | RPO/RTO declarados pero **restore no ensayado**, backup retention OK, sin drill formal |
| CI/CD + IaC | 35 % | GitHub Actions skeleton mencionado; sin IaC (Terraform/Ansible), sin secret manager profesional, sin migration safety formal |
| Testing | 50 % | Pyramid mencionada en §22.6 arch; sin coverage targets, sin contract tests, sin visual regression, sin mutation |
| Compliance / Legal | 45 % | VAT UAE OK; PDPL/DPA/sub-processor list pendiente |
| Documentación operativa | 50 % | Manual ES + runbook cutover + drill log mencionados; faltan runbooks por incidente, ADR meta, schema docs autogen |
| UX / Accesibilidad | 40 % | Wireframes OK; sin audit WCAG, sin keyboard shortcuts docs, sin onboarding tour |
| Resiliencia operativa | 50 % | Idempotency keys mencionadas; sin circuit breakers explícitos, sin DLQ, sin graceful degradation OpenAI |

### 1.2 Top 10 gaps que más impactan readiness Fase 1

| # | Gap | Dimensión | Impacto |
|---|-----|-----------|---------|
| 1 | **Restore de backup nunca ensayado**: docs declaran RTO 4h/RPO 1h pero solo prometen "test restore trimestral"; sin drill firmado pre-cutover, RTO/RPO son ficción | B5, B6 | Si se cae prod, no hay confianza de recuperación |
| 2 | **Secrets en `.env.prod` con sops/age "a verificar"** (§20.5 + ADR-017): sin secret manager real (Doppler/Vault) ni rotación automatizada (NFR-12 declara 90d sin mecanismo) | A3, F9 | Rotación manual = se olvida; service_role_key filtrable |
| 3 | **Sin gitleaks/dep scan/SAST en CI**: Dependabot mencionado pero `pip-audit`, `npm audit --audit-level=high`, gitleaks pre-commit, Semgrep no son **gate bloqueante** en pipeline | A9, A11, F1 | Vulnerabilidad o secreto leakeado pasa a main |
| 4 | **Healthchecks insuficientes**: solo `/health/live` y `/health/ready` en arch §19.1; no hay split DB/Redis/Storage/Celery/JWKS por componente | C9, P5 | Caddy enruta a backend "ready" con DB caída; alertas tardías |
| 5 | **Sin SLO/error-budget formales**: NFR-14 declara 99,5 % horario laboral pero sin SLI específicos por journey ni error budget para frenar releases | C8 | No hay disciplina objetiva de "cuándo parar de shippear" |
| 6 | **Migrations sin safety checks ni rollback automático**: Alembic + Supabase split (ADR-045) pero sin expand-contract, sin dry-run obligatorio, sin DRY-RUN gate en CI | F8, P6 | Migration destructiva en prod = downtime > RTO declarado |
| 7 | **Idempotencia y DLQ formales en Celery**: idempotency_key mencionado en §16.2 pero sin contrato global, sin Dead-Letter-Queue, sin retry+backoff jitter explícito | P1, P2, P4 | Reintento doble carga PIM = duplica auditoría / corrompe FX as-of |
| 8 | **Audit log sin tamper-proof real**: append-only + retención 7y OK, pero sin hash chain ni firma criptográfica de bloques | A13, H1 | FTA puede impugnar trazabilidad si DB se modifica fuera de la app |
| 9 | **Coverage targets + quality gates ausentes**: `pytest` corre en CI pero no hay umbral mínimo (e.g., 70% líneas / 80% pricing engine), no hay flaky-test detection | E3, E9 | Tests pueden degradarse silenciosamente sprint a sprint |
| 10 | **Email transaccional sin SPF/DKIM/DMARC**: digest diario + escalación 48h dependen de email; ningún ADR define proveedor (Resend/Postmark/SES) ni autenticación dominio | K5, K7 | Notificaciones a spam = workflow excepción degrada silenciosamente |

### 1.3 Veredicto

La planificación es **sólida en arquitectura, datos, RBAC, audit y workflow de pricing** — las cosas que el cliente entendería como "funcionalidad". Los gaps son **operacionales y de hardening**: lo que separa "demo bonita" de "sistema que MT puede operar 5 años post-handoff sin BR". El esfuerzo de cierre estimado es **~95-115 SP repartidos en S0 + un "S7.5" de hardening dedicado**, sin alterar el alcance funcional.

---

## 2. Tabla maestra por dimensión (A–Q)

> **Leyenda estado**: ✅ covered (cubierto suficientemente para Fase 1) · 🟡 partial (mencionado pero incompleto) · ❌ missing (no aparece en docs).
> **Prioridad**: M = must-Fase1 · S = should-Fase1 · C = could-Fase1 · 2+ = Fase 2+ (deferrable).
> **Owner**: Dev BR (lead BR), TI MT (cliente), Sponsor MT (Christian/Paula), R&D (champion).

### A. Seguridad

| ID | Item | Estado docs | Gap concreto Fase 1 | Prioridad | Owner | SP | Sprint |
|----|------|-------------|---------------------|-----------|-------|----|--------|
| A1 | RBAC granular + tests | ✅ | Matriz ADR-005 + RLS dual; falta **suite e2e por rol** (no un caso por endpoint) | S | Dev BR | 5 | S7 |
| A2 | RLS audit / cobertura por tabla | 🟡 | RLS sobre `products/costs/prices/audit_events/storage`; faltan `users/roles/job_definitions/import_runs/exception_rules/fx_rates` declaradas y testeadas | M | Dev BR | 5 | S3 |
| A3 | Secret management profesional | 🟡 | `.env.prod + sops/age "a verificar"`; sin Doppler/Vault/Bitwarden Secrets, sin rotación automatizada NFR-12 | M | TI MT + Dev BR | 8 | S0/S7 |
| A4 | Headers HTTP completos | ✅ | CSP/HSTS/X-Frame/X-Content/Referrer/Permissions declarados §15.8; falta CSP report-uri | S | Dev BR | 2 | S7 |
| A5 | CORS estricto | 🟡 | No documentado explícitamente; FastAPI default vs allowlist por env | S | Dev BR | 1 | S1 |
| A6 | Rate limiting | 🟡 | 100/min IP, 200/min user en arch §15.5; sin spec por endpoint sensible (login, import, recálculo masivo, export) ni mención de WAF/Cloudflare | S | Dev BR | 3 | S7 |
| A7 | OWASP Top 10 review | ✅ | Tabla completa §15.6 con mitigaciones; falta ejecutar review formal | S | Dev BR | 2 | S7 |
| A8 | OWASP API Security Top 10 | ❌ | No mencionado; BOLA / mass assignment / broken auth a nivel API no auditado | S | Dev BR | 3 | S7 |
| A9 | Dependency scanning automatizado | 🟡 | Dependabot + `pip-audit` + `npm audit` mencionados sin estado de gate bloqueante en CI | M | Dev BR | 2 | S0 |
| A10 | Container scanning | ❌ | Trivy/Grype no mencionados | S | Dev BR | 2 | S0 |
| A11 | SAST (CodeQL/Semgrep) | ❌ | No mencionado | S | Dev BR | 3 | S0/S7 |
| A12 | DAST (OWASP ZAP staging) | 🟡 | "DAST opcional: OWASP ZAP automated" §15.9 — opcional ≠ planificado | S | Dev BR | 5 | S7 |
| A13 | Audit tamper-proof (hash chain) | ❌ | append-only OK; sin hash encadenado ni firma — VAT UAE puede pedirlo si auditan profundo | S | Dev BR | 5 | S7+ |
| A14 | PII detection en logs | 🟡 | redaction whitelist (`password/token/secret/...`) §19.2; falta detección automática (Presidio o equivalente) en pre-deploy | C | Dev BR | 3 | F1.5 |
| A15 | Authn endurecido | ✅ | Magic link + MFA TOTP opcional + min 12 chars + lockout (§15.1-15.3) | — | — | — | — |
| A16 | Session management | ✅ | Supabase Auth maneja TTL JWT + refresh + force-logout en revocación de rol (mt-users-module-design.md v1.1) | — | — | — | — |
| A17 | Bot mitigation / captcha | — | N/A Fase 1 (interno) | 2+ | — | — | F2+ |
| A18 | Pre-commit hooks (gitleaks, ruff, mypy) | 🟡 | gitleaks "pre-commit" mencionado §15.7; sin commit a `pre-commit.ci` o config explícito | M | Dev BR | 2 | S0 |

### B. Reliability / DR

| ID | Item | Estado docs | Gap concreto | Prioridad | Owner | SP | Sprint |
|----|------|-------------|--------------|-----------|-------|----|--------|
| B1 | Backups Postgres automáticos | ✅ | Supabase WAL + dumps lógicos diarios cifrados §20.3, §20.7 | — | — | — | — |
| B2 | Backups Storage (Supabase Storage) | 🟡 | No mencionado replicación de bucket de imágenes ni retención cross-region | S | TI MT | 3 | S7 |
| B3 | RTO/RPO declarados | ✅ | RTO 4h, RPO 1h (NFR-16) — pero sin link a SLI medible | — | — | — | — |
| B4 | DR drill anual | 🟡 | "Test de restore trimestral en staging" §20.7; sin drill firmado pre-cutover | M | TI MT + Dev BR | 5 | S7 |
| B5 | Restore tested antes de cutover | ❌ | **Crítico**: no hay US explícita "ejecutar restore desde backup cifrado en staging y comparar checksums" | M | Dev BR | 5 | S7 |
| B6 | Single-server SPOF Hetzner | 🟡 | Aceptado para 99,5 % horario laboral; sin plan documentado de upgrade a HA Fase 2 (warm standby / managed Postgres con réplica) | S | TI MT | — | F2 ADR |
| B7 | Backup retention 7y para audit | ✅ | NFR-35 + §20.7 30d hot + 5y cold; ojo: 5y < 7y declarado por VAT UAE — **inconsistencia a corregir** | M | Dev BR | 1 | S0 |
| B8 | Encryption at rest + in transit | ✅ | Supabase managed at-rest + Caddy TLS 1.3 (NFR-10) | — | — | — | — |
| B9 | Encryption app-layer en `audit_events.payload` (PII/secretos) | ❌ | Hoy `payload` es JSONB plano; si registra `before/after` de campos sensibles (e.g., user email), no hay cifrado de columna ni redaction enforced | S | Dev BR | 5 | S7 |

### C. Observability

| ID | Item | Estado docs | Gap concreto | Prioridad | Owner | SP | Sprint |
|----|------|-------------|--------------|-----------|-------|----|--------|
| C1 | Logging estructurado JSON | ✅ | Schema completo §19.2 (ts, request_id, user_id, msg, ctx, duration_ms, err) | — | — | — | — |
| C2 | Centralized log aggregation | 🟡 | Better Stack mencionado §19.5; sin retention/query/alert config; sin export a S3 fría | S | Dev BR | 3 | S7 |
| C3 | Sentry FE + BE + Celery | ✅ | NFR-25 + §19.1 explícitos; ojo: incluir worker explícitamente | — | — | — | — |
| C4 | Métricas Prometheus | ✅ | Tabla §19.3-19.4 completa (técnicas + negocio) | — | — | — | — |
| C5 | Dashboards Grafana/Better Stack | 🟡 | Existe US-1B-05-07 (5 SP); falta spec de paneles concretos por journey (Comercial, Gerente, TI) | S | Dev BR | — | S7 |
| C6 | Alerting rules + escalation | 🟡 | "Sentry → Slack #mtme-alerts" §19.6; sin matriz P0/P1/P2 con SLA respuesta ni rotación post-handoff | M | TI MT | 3 | S7 |
| C7 | Distributed tracing (OTel) | ❌ | No mencionado | C | Dev BR | — | F1.5 |
| C8 | SLI/SLO/error budget | ❌ | NFR-14 99,5% sin SLI dimensionado por journey; sin error budget con regla "halt deploys" | M | Dev BR | 5 | S7 |
| C9 | Healthchecks por componente | 🟡 | `/health/live`, `/health/ready` (US-1A-01-01); faltan `/health/db`, `/health/redis`, `/health/storage`, `/health/celery`, `/health/jwks`, `/health/migration` | M | Dev BR | 3 | S0/S1 |
| C10 | On-call rotation post-handoff | 🟡 | Mencionado "rotación BR Fase 1 + TI MT post-handoff" §19.6; sin runbook ni tooling (Better Stack On-Call/PagerDuty) | S | Sponsor MT | — | S7 |
| C11 | Incident response playbooks | ❌ | runbook-cutover existe; faltan runbooks por escenario (DB caída, Celery atascado, FX import failed, Supabase outage, OpenAI down) | M | Dev BR | 5 | S7 |
| C12 | Post-mortem template | ❌ | No mencionado | S | Dev BR | 1 | S7 |

### D. Performance

| ID | Item | Estado docs | Gap | Prioridad | Owner | SP | Sprint |
|----|------|-------------|-----|-----------|-------|----|--------|
| D1 | Load testing | 🟡 | US-1B-05-06 valida p95 < 250 ms con "load test 50 RPS" sin tool/script declarado; sin escenario para recálculo masivo NFR-02 (4480 evaluaciones < 60s) | M | Dev BR | 5 | S7 |
| D2 | Database indexing review | ✅ | Índices declarados §8 incluyendo parciales | — | — | — | — |
| D3 | Connection pooling | ✅ | pgbouncer Supabase + SQLAlchemy pool §21.2 | — | — | — | — |
| D4 | Caching strategy | ✅ | Redis con TTL FX/exception_rules/channels §21.2 | — | — | — | — |
| D5 | EXPLAIN ANALYZE en queries críticas | 🟡 | US-1B-05-06 menciona "query plans" sin lista canónica de queries críticas | S | Dev BR | 2 | S7 |
| D6 | N+1 detection | ❌ | No mencionado; SQLAlchemy con eager loading explicit y React Query batching no auditados | S | Dev BR | 2 | S7 |
| D7 | Frontend bundle size | ❌ | No mencionado; sin Lighthouse target ni bundle analyzer | C | Dev BR | 2 | S7 |
| D8 | CDN para assets | 🟡 | Cloudflare DNS recomendado §20.3; sin uso explícito como CDN para `/static` y `product-images/` | S | TI MT | 2 | S7 |
| D9 | Image optimization automática | ❌ | Mirror obligatorio §10.1.6; sin pipeline AVIF/WebP/Sharp | C | Dev BR | 3 | F1.5 |

### E. Quality / Testing

| ID | Item | Estado docs | Gap | Prioridad | Owner | SP | Sprint |
|----|------|-------------|-----|-----------|-------|----|--------|
| E1 | Pyramid testing | 🟡 | §22.6 arch menciona unit + integration + e2e; sin matriz de qué cubre cada capa por épica | S | Dev BR | 2 | S0 |
| E2 | Contract tests FE↔BE | ❌ | OpenAPI auto-gen mencionado; sin Pact ni schema validation en CI | S | Dev BR | 5 | S2 |
| E3 | Coverage targets | ❌ | Sin umbral declarado; pyramid sin números | M | Dev BR | 1 | S0 |
| E4 | Mutation testing | ❌ | No mencionado | C | — | — | F1.5 |
| E5 | Visual regression | ❌ | No mencionado; UI con Shadcn pero sin Chromatic/Playwright snapshots | C | Dev BR | 3 | F1.5 |
| E6 | E2E con auth flow real | 🟡 | Playwright mencionado §20.2; sin spec de "login real Supabase + crear precio + aprobar + exportar" como happy path obligatorio | M | Dev BR | 5 | S7 |
| E7 | Test data management | 🟡 | Fixtures golden v5.1 (sprint0-v51-rules-extraction.md); sin factories estilo factory_boy ni seed reproducible declarado | S | Dev BR | 3 | S1 |
| E8 | Pre-commit hooks | 🟡 | `eslint + prettier + ruff + mypy` en CI; sin pre-commit framework declarado | M | Dev BR | 2 | S0 |
| E9 | CI quality gates | 🟡 | CI corre lint+test; sin "fail si coverage cae", sin flaky detection | M | Dev BR | 3 | S0 |
| E10 | Tests Celery con Redis real | 🟡 | "pytest con docker-compose: postgres, redis" §20.2; sin spec de eager mode vs integration; sin test de DLQ/retry | S | Dev BR | 3 | S2 |

### F. DevOps / CI/CD

| ID | Item | Estado docs | Gap | Prioridad | Owner | SP | Sprint |
|----|------|-------------|-----|-----------|-------|----|--------|
| F1 | Pipeline con stages | 🟡 | Skeleton §20.2 (lint/test/build/deploy); sin stage explícito de scan (Trivy/CodeQL/Semgrep/gitleaks) ni quality gate por umbral | M | Dev BR | 5 | S0 |
| F2 | Branch strategy + protected main | ❌ | No mencionado: trunk-based vs gitflow, required reviewers, status checks obligatorios | M | TI MT + Dev BR | 1 | S0 |
| F3 | Conventional commits + changelog | ❌ | No mencionado | S | Dev BR | 2 | S0 |
| F4 | Semver + git tags | 🟡 | "tag matches v*" en deploy_prod §20.2; sin convención formal | S | Dev BR | 1 | S0 |
| F5 | IaC para Hetzner | ❌ | scripts/deploy.sh ad-hoc + Caddyfile + docker-compose.prod.yml; **sin Terraform/Pulumi/Ansible** para reproducibilidad de servidor | M | TI MT | 8 | S0/S1 |
| F6 | Environment parity dev/staging/prod | 🟡 | Tabla §20.1 y compose definidos; sin garantía de paridad por IaC; dev local ≠ Hetzner | S | Dev BR | 3 | S0 |
| F7 | Blue-green / canary | ❌ | Single Hetzner, no canary; necesita al menos health-check-aware swap (Caddy) | S | TI MT | 3 | S7 |
| F8 | Migration safety | 🟡 | Alembic + Supabase split (ADR-045) + "approval Lead BR + ventana mantenimiento" §20.8; sin dry-run obligatorio en CI ni expand-contract pattern documentado | M | Dev BR | 5 | S0/S1 |
| F9 | Secrets rotation policy | 🟡 | NFR-12 declara 90d; sin mecánica (calendar reminder, rotation script, key versioning) | M | TI MT | 3 | S7 |
| F10 | Container registry | ✅ | GHCR §20.2 | — | — | — | — |
| F11 | Image signing (cosign) | ❌ | "imágenes Docker firmadas + checksums" §15.6 A08 mencionado sin mecanismo | C | Dev BR | 3 | F1.5 |

### G. Documentación operativa

| ID | Item | Estado docs | Gap | Prioridad | Owner | SP | Sprint |
|----|------|-------------|-----|-----------|-------|----|--------|
| G1 | README onboarding 5-min | 🟡 | "README en español" mencionado US-1A-01-01; sin "5-min get-started" guarantee | S | Dev BR | 2 | S0 |
| G2 | Runbooks por incidente | 🟡 | runbook-cutover.md mencionado; faltan `runbook-import-failed.md`, `runbook-celery-stuck.md`, `runbook-fx-stale.md`, `runbook-supabase-outage.md`, `runbook-restore-from-backup.md` | M | Dev BR | 5 | S7 |
| G3 | ADR registry actualizado | ✅ | 46 ADRs; superseded marcados; doc dedicado `adr/` index | — | — | — | — |
| G4 | API docs autogen | 🟡 | FastAPI OpenAPI nativo; sin Stoplight/Redoc deploy ni link interno en handbook | S | Dev BR | 2 | S7 |
| G5 | Diagramas C4 actualizados | ✅ | C4 L1/L2/L3 §5-7 arch | — | — | — | — |
| G6 | Schema docs autogen | ❌ | Sin Schemaspy/dbdocs/Atlas | C | Dev BR | 2 | F1.5 |
| G7 | User-facing handbook ES | ✅ | US-1B-05-02 (`docs/handbook-es.md`) explícito | — | — | — | — |
| G8 | Glosario de términos | ✅ | PRD §19 Glosario completo + arch §5.1 | — | — | — | — |
| G9 | Meta-ADR (cómo escribir ADRs) | ❌ | No mencionado | C | Dev BR | 1 | S0 |

### H. Compliance / Legal

| ID | Item | Estado docs | Gap | Prioridad | Owner | SP | Sprint |
|----|------|-------------|-----|-----------|-------|----|--------|
| H1 | VAT UAE 2026 audit trail | ✅ | NFR-08, NFR-35 (7y), NFR-36 (export CSV firmado FTA), audit append-only | — | — | — | — |
| H2 | PDPL UAE compliance | ❌ | No mencionado; PDPL 2022 exige consentimiento + derechos del usuario + DPO en orgs grandes | M | Sponsor MT + legal | 5 | S0/S7 |
| H3 | Data retention policy unificada | 🟡 | Audit 7y; **sin política para users (e.g., `users.deactivated_at`)**, imágenes, import_runs, competitor_listings | S | Sponsor MT | 2 | S7 |
| H4 | Right to be forgotten | ❌ | Sin endpoint admin `delete user data` ni procedimiento documentado | S | Dev BR | 5 | F1.5 |
| H5 | GDPR equivalent (Hetzner Frankfurt) | 🟡 | ADR-020 Q-02 abierto; si datos van por EU, GDPR aplica con DPA | M | Sponsor MT + legal | — | S0 |
| H6 | Cookie/privacy policy | — | N/A interno Fase 1 | 2+ | — | — | F2+ (B2B portal) |
| H7 | ToS BR↔MT | ❌ | No mencionado en docs técnicos; asumido en contrato comercial (fuera scope) | S | Sponsor MT + legal | — | S0 |
| H8 | DPA con Supabase, OpenAI, Bright Data, etc. | ❌ | Sin lista firmada de DPAs por sub-procesador | M | Sponsor MT + legal | — | S0 |
| H9 | Sub-processor list | ❌ | No mantenido | S | Sponsor MT | 1 | S0 |
| H10 | Trade compliance UAE / sanctions | — | N/A Fase 1 (B2B Fase 4) | 2+ | — | — | F4 |

### I. UX / Acceso

| ID | Item | Estado docs | Gap | Prioridad | Owner | SP | Sprint |
|----|------|-------------|-----|-----------|-------|----|--------|
| I1 | WCAG 2.1 AA | ❌ | No mencionado; Shadcn provee semántica decente pero sin audit | S | Dev BR | 3 | S7 |
| I2 | Responsive desktop+tablet | 🟡 | Wireframes desktop-first; tablet/mobile read-only no validados | C | Dev BR | 2 | F1.5 |
| I3 | Empty/error/loading states | 🟡 | Wireframes muestran happy path; sin matriz por pantalla | S | Dev BR | 3 | S6/S7 |
| I4 | Onboarding tour | ❌ | Manual ES + sesiones hands-on cubren rol; sin tour in-app (Userflow/Intercom) | C | Dev BR | — | F1.5 |
| I5 | Tooltips contextuales | 🟡 | Wireframes mencionan "i" badges; sin helper sistema | C | Dev BR | 2 | S7 |
| I6 | Keyboard shortcuts | ❌ | No mencionado | C | Dev BR | — | F1.5 |
| I7 | UI Arabic RTL | — | NFR-23 explícito: AR es export-only Fase 1 | 2+ | — | — | F2+ |

### J. Datos / Operación

| ID | Item | Estado docs | Gap | Prioridad | Owner | SP | Sprint |
|----|------|-------------|-----|-----------|-------|----|--------|
| J1 | Data quality dashboard | 🟡 | `data_quality` flag por SKU + reporte reconciliación (US-1A-06-XX); sin dashboard agregado | S | Dev BR | 3 | S7 |
| J2 | Anomaly detection feeds | — | F2.5+ scope | 2+ | — | — | F2.5 |
| J3 | Reporting & BI | ❌ | No mencionado; Metabase/Superset conectado a réplica read-only ausente | S | TI MT | — | F1.5 |
| J4 | Data lineage | 🟡 | `import_runs.source` + `audit_events.actor` permite reconstruir; sin tooling visual | C | Dev BR | — | F1.5 |
| J5 | Master data governance | 🟡 | RBAC + Champion del Cambio implícito; sin "comité MDM" formalizado | C | Sponsor MT | — | F1.5 |
| J6 | Data dictionary | ✅ | DDL §8 + Glosario PRD §19 | — | — | — | — |

### K. Soporte interno / customer-facing

| ID | Item | Estado docs | Gap | Prioridad | Owner | SP | Sprint |
|----|------|-------------|-----|-----------|-------|----|--------|
| K1 | Feedback channel | ❌ | No mencionado; tickets vía email a Pablo asumido | C | Dev BR | 2 | F1.5 |
| K2 | Bug report template | ❌ | No mencionado | C | Dev BR | 1 | S0 |
| K3 | Help / contact info en UI | ❌ | No mencionado | C | Dev BR | 1 | S7 |
| K4 | Status page | ❌ | No relevante interno; podría usarse Better Stack public para handoff | C | TI MT | — | F1.5 |
| K5 | Email transaccional | 🟡 | Digest diario (FR-1b-05) + escalado 48h (FR-1b-13) dependen de email; **sin proveedor declarado** (Resend/Postmark/SES) | M | Dev BR + TI MT | 5 | S5/S7 |
| K6 | Templates email branded | ❌ | No mencionado | S | Dev BR | 2 | S5 |
| K7 | SMTP con SPF/DKIM/DMARC | ❌ | No mencionado; sin esto el digest entra a spam → workflow degrada | M | TI MT | 2 | S5 |

### L. Costos / Sostenibilidad

| ID | Item | Estado docs | Gap | Prioridad | Owner | SP | Sprint |
|----|------|-------------|-----|-----------|-------|----|--------|
| L1 | Cost monitoring | ❌ | Sin dashboard agregado Hetzner+Supabase+OpenAI+Bright Data+Better Stack | S | TI MT | 2 | S7 |
| L2 | Budget alerts | ❌ | No mencionado | S | TI MT | 1 | S7 |
| L3 | Resource right-sizing | 🟡 | "DB managed instance medium $50-100/mes" §21.3; sin revisión post-prod | C | TI MT | — | F1.5 |
| L4 | Idle resource cleanup | ❌ | No mencionado | C | TI MT | — | F1.5 |
| L5 | FinOps practices | — | F2+ | 2+ | — | — | F2+ |

### M. Feature management

| ID | Item | Estado docs | Gap | Prioridad | Owner | SP | Sprint |
|----|------|-------------|-----|-----------|-------|----|--------|
| M1 | Feature flags | 🟡 | `settings + feature flags` tabla §8.12 sin gestor (Unleash/Flagsmith); flags dispersos en config (`channel_recommendation=off`, `reverse_image_search=off`) | S | Dev BR | 3 | S6 |
| M2 | A/B testing | — | N/A interno | 2+ | — | — | F2+ |
| M3 | Progressive rollout / canary | 🟡 | Single server; canary requiere 2 backends + Caddy upstream | S | TI MT | — | F1.5 |
| M4 | Kill switches | 🟡 | Implícitos via feature flags; sin contrato explícito (e.g., "kill_switch.export_disable") | S | Dev BR | 2 | S6 |

### N. Internationalization

| ID | Item | Estado docs | Gap | Prioridad | Owner | SP | Sprint |
|----|------|-------------|-----|-----------|-------|----|--------|
| N1 | i18n strings extraction pipeline | ✅ | next-intl declarado NFR-24, US-1A-01-06; sin Crowdin/Lokalise (no hace falta interno 2 idiomas) | — | — | — | — |
| N2 | Pluralization rules | 🟡 | next-intl soporta ICU; sin matriz de strings con plurales validada | C | Dev BR | 1 | S3 |
| N3 | Number/date/currency formatting | ✅ | NFR-31, NFR-32 explícitos | — | — | — | — |
| N4 | RTL preparado | 🟡 | NFR-23 dice "sin RTL Fase 1"; sin checklist de componentes que **no rompan** al activarse Fase 2+ (e.g., layouts con `flex-row` hardcoded) | C | Dev BR | 2 | F1.5 |

### O. Customer success / training

| ID | Item | Estado docs | Gap | Prioridad | Owner | SP | Sprint |
|----|------|-------------|-----|-----------|-------|----|--------|
| O1 | Training plan Comercial | ✅ | US-1B-05-03 + sec. 15.1 PRD | — | — | — | — |
| O2 | Manual operativo ES | ✅ | US-1B-05-02 (`docs/handbook-es.md`) | — | — | — | — |
| O3 | Walkthroughs grabados | 🟡 | US-1B-05-03 menciona "sesiones grabadas en `training-log.md`"; sin biblioteca curada | S | Champion MT | 2 | S7 |
| O4 | Sandbox / training environment | 🟡 | `staging` env existe §20.1; sin "sandbox aislado para entrenamiento sin polución" | S | TI MT | 2 | S7 |
| O5 | Office hours BR primer mes | 🟡 | Implícito post-cutover, no formalizado SLA | S | Sponsor BR | — | S7+ |

### P. Resiliencia operativa

| ID | Item | Estado docs | Gap | Prioridad | Owner | SP | Sprint |
|----|------|-------------|-----|-----------|-------|----|--------|
| P1 | Idempotencia en imports | 🟡 | `idempotency_key` mencionado §16.2; sin contrato global ni tests "ejecutar 2× = mismo estado" | M | Dev BR | 5 | S2 |
| P2 | Idempotencia en tasks Celery | 🟡 | task_id = idempotency_key mencionado; sin política de "deduplicate within window" en Redis | M | Dev BR | 3 | S2 |
| P3 | Circuit breakers | ❌ | OpenAI/Cohere/Bright Data llamadas sin circuit breaker (e.g., `pybreaker`) | S | Dev BR | 3 | F1.5 (R&D) |
| P4 | Retry strategy + DLQ | 🟡 | Celery retry default; **sin DLQ explícito** ni `task_failed_total` con triage manual | M | Dev BR | 5 | S2/S7 |
| P5 | Graceful degradation | 🟡 | Comparador Fase 1.5+ tolera OpenAI down (R&D); pricing engine no llama externos = OK; sin matriz por servicio externo | S | Dev BR | 2 | S7 |
| P6 | Migrations zero-downtime (expand-contract) | ❌ | ADR-045 split bien; sin pattern documentado (add column nullable → backfill → enforce) | S | Dev BR | 3 | S0 |
| P7 | Background tasks no bloqueantes | ✅ | Celery + apply async §16.2 + Beat database scheduler ADR-046 | — | — | — | — |

### Q. Cross-cutting

| ID | Item | Estado docs | Gap | Prioridad | Owner | SP | Sprint |
|----|------|-------------|-----|-----------|-------|----|--------|
| Q1 | License compliance OSS | ❌ | Sin SBOM ni `license-checker` en CI | S | Dev BR | 2 | S7 |
| Q2 | SBOM generation (CycloneDX/SPDX) | ❌ | No mencionado; relevante VAT UAE auditor + procurement MT | S | Dev BR | 2 | S7 |
| Q3 | Accessibility audit por release | ❌ | No mencionado | C | Dev BR | — | F1.5 |
| Q4 | Performance budget por release | ❌ | NFR-01/02 son targets prod; sin gate "build PR cae si recálculo > 70s en CI" | C | Dev BR | 2 | F1.5 |
| Q5 | CODEOWNERS | 🟡 | "README y Codeowners" mencionado US-1A-01-01; sin contenido concreto | S | Dev BR | 1 | S0 |
| Q6 | Onboarding template nuevo dev | ❌ | No mencionado; importante para handoff TI MT post-cutover | M | Dev BR | 3 | S7 |

---

## 3. Top 20 gaps críticos must-Fase1 con detalle expandido

> Ordenados por impacto descendente. Estos son los que **no deberían** salir a prod sin estar en verde.

### 3.1 Restore desde backup ensayado pre-cutover (B5)

- **Estado actual.** §20.7 promete "test de restore trimestral en staging" sin fecha firme; US-1B-05-04 contempla "drill rollback" pero el rollback ahí es a Excel demo, no restore de DB Postgres desde backup cifrado.
- **Gap.** Sin haber ejecutado un restore real de un dump cifrado de Supabase + comparación de checksums por tabla crítica + verificación de RLS post-restore, RTO 4h y RPO 1h son aspiracionales.
- **Acción.** Añadir US-1A-01-XX (Sprint 0) "ensayo restore en staging con dump del día anterior" + US-1B-05-04 ampliada con criterio "restore documentado en `docs/runbook-restore-from-backup.md` con tiempos medidos".
- **SP.** 5.

### 3.2 Secret manager profesional + rotación (A3, F9)

- **Estado actual.** §15.7 + §20.5 + ADR-017 mencionan `.env.prod` con sops/age o ansible-vault "a verificar contra hppt-iom". NFR-12 declara rotación 90d.
- **Gap.** Sin Doppler / Bitwarden Secrets / Vault, la rotación es manual (= se olvida) y `service_role_key` Supabase, OpenAI key, Bright Data credentials viven en disco del server. ADR-017 fue escrito antes de ADR-031/032 (Supabase) y necesita revisión.
- **Acción.** Decisión S0 entre Doppler ($7/mes) vs SOPS+age con repo cifrado vs Bitwarden Secrets Manager ($6/mes seat). Refrescar ADR-017 → ADR-051. Implementar entrega automática a containers via env injection.
- **SP.** 8 (incl. cron de rotación + tests + doc).

### 3.3 SAST + SCA + container scan + gitleaks como gate bloqueante en CI (A9-A11, A18)

- **Estado actual.** Dependabot trimestral, `pip-audit` y `npm audit` mencionados sin gate; gitleaks "pre-commit" sin config.
- **Gap.** Vulnerabilidad CVE crítica en deps o secret leakeado puede mergear sin que CI lo detenga. Trivy/Grype no escanean imágenes Docker antes de push a GHCR.
- **Acción.** Pipeline GH Actions con jobs paralelos: `gitleaks-action`, `trivy-image-scan`, `pip-audit --strict`, `npm audit --audit-level=high`, `semgrep ci`. Quality gate: cualquier fallo en main = pipeline rojo. Generar SBOM CycloneDX como artifact por release.
- **SP.** 5.

### 3.4 Healthchecks granulares por componente (C9)

- **Estado actual.** US-1A-01-01 promete `/health/live` + `/health/ready`. ADR-019 menciona healthchecks sin desagregar.
- **Gap.** Caddy enruta a backend "ready" cuando DB Supabase está caída; Celery con Redis caído no lo reporta; JWKS rotation puede fallar silenciosamente.
- **Acción.** Implementar `/health/db` (SELECT 1), `/health/redis` (PING), `/health/storage` (HEAD bucket), `/health/celery` (inspect active workers), `/health/jwks` (fetch + parse), `/health/migration` (compara Alembic head vs DB). `/health/ready` agrega todos. Better Stack monitor cada uno.
- **SP.** 3.

### 3.5 SLO + error budget formal (C8)

- **Estado actual.** NFR-14 = 99,5 % horario laboral. Sin SLI por journey (e.g., "p95 export por canal < 30s con éxito 99,9 %") ni error budget que **detenga deploys** cuando se quema.
- **Gap.** Métricas existen (§19.3-19.4) pero no hay disciplina objetiva de "cuándo el equipo deja de añadir features y se va a hardening". En operación post-handoff, sin SLO el TI MT no sabe qué priorizar.
- **Acción.** ADR-052 SLO/SLI/error-budget con 3 SLOs Fase 1: (a) availability `/health/ready` 99,5%, (b) approval workflow latency p95 < 24h, (c) recálculo masivo p95 < 60s. Error budget mensual → policy: 50% consumido = revisión, 80% = halt feature, 100% = solo bugfix.
- **SP.** 5.

### 3.6 Migrations safety: dry-run + expand-contract + rollback (F8, P6)

- **Estado actual.** ADR-045 split Alembic/Supabase; §20.8 "destructive requiere approval Lead BR + ventana de mantenimiento".
- **Gap.** Sin dry-run obligatorio en CI (Alembic offline mode), sin guía de expand-contract documentada, sin rollback automático ante fallo de migration en deploy.
- **Acción.** US-1A-01-XX "Migration discipline doc + CI dry-run + automated rollback step" — incluye: (a) PR check `alembic upgrade head --sql` debe pasar lint pgFormatter, (b) "destructive" detection (DROP/ALTER COLUMN type) bloquea PR sin approval label, (c) deploy step ejecuta `alembic upgrade head` con timeout y rollback `alembic downgrade -1` si smoke test post-deploy falla, (d) doc `docs/migration-playbook.md` con expand-contract.
- **SP.** 5.

### 3.7 Idempotencia + DLQ + retry/jitter en Celery (P1, P2, P4)

- **Estado actual.** §16.2 menciona `task_id = idempotency_key`; Celery default retry; sin DLQ.
- **Gap.** Reintento de import PIM puede duplicar audit events o corromper FX as-of stamping. Task que falla 5 veces se pierde sin alerta. No hay mecanismo de re-driving manual.
- **Acción.** Contrato global `@idempotent_task(key_field, window_minutes)` decorator. Configurar Celery `task_acks_late=True`, `task_reject_on_worker_lost=True`. Añadir DLQ via routing a queue `dlq.{original_queue}`. UI en `/admin/jobs` lista DLQ con botón "re-drive" o "drop".
- **SP.** 8 (5 backend + 3 UI).

### 3.8 Audit log con hash chain (A13)

- **Estado actual.** `audit_events` particionada append-only (NFR-34), retención 7y (NFR-35), export firmado FTA (NFR-36).
- **Gap.** "Append-only" es policy de aplicación; un superuser Postgres con acceso fuera de la app puede modificar filas y borrar evidencia. VAT UAE 2026 se está endureciendo; defensa profunda exige hash encadenado o firma criptográfica de bloques diarios.
- **Acción.** ADR-053 propone añadir `audit_events.prev_hash` + `audit_events.row_hash`; trigger BEFORE INSERT calcula `row_hash = sha256(payload || prev_hash)`. Job nocturno firma el último hash con clave de la cuenta operativa BR. Endpoint `GET /audit/verify/{from}/{to}` re-calcula y devuelve "tamper detected" si rompe.
- **SP.** 5 (3 si solo hash chain sin firma; 5 con firma).

### 3.9 Coverage targets + flaky-test detection (E3, E9)

- **Estado actual.** CI corre pytest sin umbral.
- **Gap.** Sin "fail PR si coverage cae", sin `pytest-rerunfailures` con detection, sin reporte agregado por épica. La calidad puede degradar invisiblemente.
- **Acción.** Configurar `coverage.py` con fail-under: global 70%, pricing engine 90%, importers 80%, RBAC 90%. CI publica reporte como PR comment. Detectar flaky con `pytest --reruns 2 --reruns-delay 1 --only-rerun-failed-tests` y abrir issue automático cuando un test re-runea > 1 vez en 5 PRs.
- **SP.** 3.

### 3.10 RLS audit completo por tabla (A2)

- **Estado actual.** §15.4 + US-1A-07-04 declaran RLS sobre `products / costs / prices / audit_events / storage.objects`.
- **Gap.** Faltan políticas explícitas y testeadas en `users`, `roles`, `user_roles`, `job_definitions`, `job_runs`, `import_runs`, `import_run_rows`, `exception_rules`, `fx_rates`, `currencies`, `suppliers`, `channels`, `match_decisions`. Sin tests negativos por rol.
- **Acción.** US-1A-07-04 ampliada: (a) inventario de todas las tablas `public.*` con su política, (b) suite pytest "for each role × each table × each operation: assert allow/deny", (c) CI ejecuta el sweep con seed users de cada rol.
- **SP.** 5.

### 3.11 Email transaccional con SPF/DKIM/DMARC (K5, K7)

- **Estado actual.** Digest diario (FR-1b-05) y escalado 48h (FR-1b-13) son funcionales del workflow; **sin proveedor declarado**.
- **Gap.** Si email entra a spam, el Gerente no aprueba → pricing no se exporta → cascada operativa. Sin SPF/DKIM/DMARC en `mtme.ae` (o subdominio dedicado tipo `notifications.mtme.ae`), reputation es nula desde día 1.
- **Acción.** ADR-XXX (extra): elegir Resend (preferido por DX + DPA EU) o Postmark (preferido por delivery rate). Configurar DNS SPF + DKIM + DMARC `p=quarantine`. Templates branded MT con MJML. Sandbox en staging.
- **SP.** 5 + 2 (DNS TI MT).

### 3.12 Backup retention inconsistente (B7)

- **Estado actual.** NFR-35 dice "≥ 7 años audit"; §20.7 dice "30 días hot + 5 años cold".
- **Gap.** Inconsistencia 5 vs 7 años. VAT UAE FTA puede pedir hasta 7 años de auditoría inmutable (algunos casos hasta 15 para corporate tax).
- **Acción.** Ajustar §20.7 a "30d hot + 7y cold" para `audit_events`. Resto de tablas (PIM, costos, prices) política separada — definir con sponsor.
- **SP.** 1.

### 3.13 Branch protection + CODEOWNERS reales (F2, Q5)

- **Estado actual.** US-1A-01-01 menciona "Codeowners"; sin contenido. No hay ADR sobre branch strategy.
- **Gap.** Sin protected main + required reviewers + required status checks, alguien puede mergear con CI rojo o sin revisión. Sin CODEOWNERS, ownership es ambiguo en handoff.
- **Acción.** ADR-XXX trunk-based + protected main + 1 required reviewer + status checks (CI verde + scan verde + migration dry-run verde). CODEOWNERS por path: `/mt-pricing-backend/app/pricing/**` → @pablo-sierra; `/supabase/migrations/**` → @ti-mt-lead; `/.github/workflows/**` → @pablo-sierra.
- **SP.** 1 (config) + ya cubierto en F2.

### 3.14 IaC para Hetzner (F5)

- **Estado actual.** `scripts/deploy.sh` ad-hoc + `Caddyfile` + `docker-compose.prod.yml`.
- **Gap.** Reproducir el server de prod tras desastre o crear staging idéntico es tribal knowledge. Provisioning DNS, firewall, ufw, fail2ban, swap, system-limits, backup cron — todo manual.
- **Acción.** ADR-050 IaC con Ansible (playbooks idempotentes en `mt-pricing-infra/ansible/`) o Pulumi (TypeScript alineado con stack). Recomendado: Ansible + hcloud module para Hetzner Cloud + cloudflare module para DNS. CI valida `ansible-lint` + `ansible-playbook --check` en PR.
- **SP.** 8.

### 3.15 PDPL UAE compliance + DPA con sub-procesadores (H2, H8, H9)

- **Estado actual.** PDPL no mencionado; DPA con Supabase/OpenAI/Bright Data no listado.
- **Gap.** PDPL Federal Law No. 45/2021 entró en vigor 2023 con compliance pleno 2024. Aplica a procesamiento de datos personales en UAE. Aunque MT es procesador interno con datos B2B, el `users.email` es PII. Sub-processor list mantenida es expectativa estándar de procurement enterprise.
- **Acción.** Sponsor MT + legal: (a) determinar si MT es Data Controller/Processor para users de la app, (b) firmar DPA con Supabase (template estándar EU), OpenAI (DPA con term para no entrenar), Bright Data, Resend/Postmark. (c) `docs/sub-processors.md` mantenido. (d) ROPA (Record of Processing Activities) inicial.
- **SP.** Tracking 5; el trabajo legal real es externo.

### 3.16 Runbooks por incidente (G2, C11)

- **Estado actual.** `runbook-cutover.md` mencionado US-1B-05-04. Sin más runbooks.
- **Gap.** Cuando algo falle (Supabase outage, Celery atascado, FX import failed, OpenAI rate limit), el on-call (TI MT post-handoff) no tiene playbook. Tribal knowledge BR no escala.
- **Acción.** Set inicial 6 runbooks: `runbook-celery-stuck.md`, `runbook-import-failed.md`, `runbook-fx-stale.md`, `runbook-supabase-outage.md`, `runbook-restore-from-backup.md`, `runbook-deploy-rollback.md`. Cada uno: síntomas → diagnostic commands → fix steps → escalation → post-mortem template.
- **SP.** 5.

### 3.17 Load testing real (D1)

- **Estado actual.** US-1B-05-06: "load test 50 RPS p95 < 250 ms" sin tool ni script.
- **Gap.** El reto NFR-02 "recálculo masivo 4480 evals < 60s" no se mide nunca contra carga real. p95 < 250 ms en CRUD es laxo si el rato simultáneo de aprobación y export está en juego.
- **Acción.** k6 (preferido por JS familiar) o Locust. Escenarios: (a) 10 usuarios concurrentes navegando UI + 1 importer corriendo, (b) recálculo masivo solo, (c) export CSV concurrente con aprobación. Targets: NFR-01/02/06 + recálculo masivo + export. Tests corren en staging post-deploy. Resultados en `docs/load-test-baseline.md`.
- **SP.** 5.

### 3.18 E2E auth flow real (E6)

- **Estado actual.** Playwright mencionado; sin spec de "happy path login → editar SKU → proponer precio → aprobar → exportar".
- **Gap.** Tests unitarios y de integración pueden estar verdes y la app aún romperse en el flow real (token expiration mid-session, RLS context perdido, race condition workflow).
- **Acción.** Suite Playwright E2E con auth real Supabase (test users `comercial@test`, `gerente@test`, `ti@test`, `admin@test` pre-seedeados). 5 happy paths críticos: (a) Comercial propone precio → Gerente aprueba → export filtrado, (b) Importer PIM dry-run → apply, (c) Excepción dispara → Gerente aprueba → audit, (d) Cambio FX → recálculo masivo, (e) Job admin "Run now" → audit. Corre en staging post-deploy.
- **SP.** 5.

### 3.19 RBAC e2e tests por rol (A1)

- **Estado actual.** Matriz §15.4; tests unitarios de `require_permission` implícitos.
- **Gap.** Tests negativos sistemáticos por rol × endpoint × operación faltan. Bug en RLS o en dependency puede pasar.
- **Acción.** Suite pytest `test_rbac_matrix.py` con parametrize: para cada (rol, endpoint, método), verifica esperado vs obtenido. CI ejecuta. ~60 endpoints × 4 roles × 5 métodos = ~1200 casos parametrizados (rápidos con auth fake).
- **SP.** 5.

### 3.20 Onboarding template para nuevo dev (Q6)

- **Estado actual.** README US-1A-01-01 implícito, sin onboarding dedicated.
- **Gap.** Cuando MT contrate dev junior post-handoff, el path "0 → primer PR" no está documentado. Riesgo R-02 single-point-of-failure se extiende a stack técnico.
- **Acción.** `docs/dev-onboarding.md`: clone → setup pre-commit → docker compose dev → seed DB → run tests → tour de codebase (5 archivos clave) → primer "good-first-issue" labeleado. Target: 1 día setup → primer PR mergeable día 2.
- **SP.** 3.

---

## 4. Roadmap de remediation distribuido

### 4.1 Reparto sugerido por sprint

| Sprint | Trabajo de hardening añadido | SP |
|--------|------------------------------|----|
| **S0** (Sprint 0 — gating) | A3 secret manager decisión + ADR-051 (3) · A9/A10/A11/A18 scan + gitleaks + Trivy en CI (5) · F1/F2 pipeline stages + protected main (3) · F8 migration dry-run setup (2) · E3/E8/E9 coverage gate + pre-commit framework (3) · B7 retention 5y→7y fix (1) · G9 meta-ADR (1) · H8/H9 sub-processor list arrancada (1) · Q5 CODEOWNERS (1) · K2 bug template (1) | **21** |
| **S1** | C9 healthchecks granulares (3) · A5 CORS allowlist + E7 factories + seed reproducible (3) · F5 IaC Ansible playbooks v0 (5) · F6 environment parity (2) | **13** |
| **S2** | A2 RLS audit + tests por tabla (5) · P1/P2 idempotency contract + tests (5) · P4 DLQ + retry+jitter (3) · E2 contract tests OpenAPI (5) · E10 Celery integration tests (3) | **21** |
| **S3** | A1 RBAC e2e suite (5) · N2 ICU pluralization check (1) | **6** |
| **S4** | (sin trabajo dedicado de hardening; foco motor pricing) | 0 |
| **S5** | K5/K6/K7 email transaccional + SPF/DKIM/DMARC (7) | **7** |
| **S6** | M1 feature flags (Unleash OSS o tabla DB con UI) + M4 kill switches (5) | **5** |
| **S7** | B5 restore drill ensayado (5) · B4 DR drill firmado (3) · C6 alerting matrix + on-call (3) · C8 SLO/error budget ADR-052 + impl (5) · C11 6 runbooks por incidente (5) · C12 post-mortem template (1) · D1 k6 load tests (5) · E6 Playwright E2E auth flow (5) · A4 CSP report-uri + A6 rate-limit per-endpoint (3) · A7/A8 OWASP review (3) · A12 ZAP DAST (3) · A13 audit hash chain ADR-053 (5) · F7 health-aware swap (3) · F9 secrets rotation crons (2) · G2 runbooks index (incluido en C11) · G4 API docs Redoc deploy (2) · O3 walkthroughs library (2) · O4 sandbox env (2) · I1 a11y audit (3) · I3 empty/error states matrix (3) · J1 DQ dashboard (3) · L1/L2 cost monitoring + alerts (3) · Q1/Q2 SBOM + license-checker (3) · Q6 dev onboarding (3) · B9 audit payload encryption (5) | **84** |
| **F1.5** (post-cutover) | D6 N+1 detection · D7 bundle size · D8 CDN · D9 image optimization · E4 mutation · E5 visual regression · F11 cosign · H4 right-to-be-forgotten · I2/I4/I5/I6 UX polish · K1/K3/K4 feedback/help/status page · M3 progressive rollout · N4 RTL prep · P3 circuit breakers · A14 PII scan · J3 BI tool · J4 data lineage tooling | ~50 |

**Totales hardening Fase 1**: ~157 SP distribuidos en S0-S7 (~20% del esfuerzo total operativo + R&D, alineado con regla de oro 15-25% para hardening en proyecto serio).

### 4.2 Si el budget no admite los 157 SP completos

**Mínimo viable irreductible para "no irresponsable" en prod (~70 SP)**:
- S0: 21 SP (todos)
- S1-S2: idempotency + DLQ + RLS audit + healthchecks + IaC v0 = ~25 SP
- S5: email SPF/DKIM = 7 SP
- S7: restore drill + SLO + 6 runbooks + RBAC e2e + load tests + Playwright E2E = ~20 SP

**Lo demás se diferiría a Fase 1.5 con riesgo cuantificado** (que el sponsor debe aceptar explícitamente).

---

## 5. Nuevos ADRs propuestos

> Lista — los ADRs completos los escribirán otros agentes / agente arquitecto. ID continuando desde ADR-046 ya activo.

| ADR | Tema | Driver | Owner |
|-----|------|--------|-------|
| **ADR-047** | Observability stack consolidado (Sentry + structlog + Prometheus + Grafana/Better Stack) | C2-C6 | Dev BR |
| **ADR-048** | Healthchecks endpoints granulares (live/ready/db/redis/storage/celery/jwks/migration) | C9, P5 | Dev BR |
| **ADR-049** | Migration discipline (Alembic + Supabase + dry-run + expand-contract + rollback automático) | F8, P6 | Dev BR |
| **ADR-050** | IaC para Hetzner (Ansible vs Pulumi vs Terraform) | F5, F6 | TI MT |
| **ADR-051** | Secrets management (Doppler vs SOPS+age vs Bitwarden Secrets) — supersede ADR-017 | A3, F9 | TI MT |
| **ADR-052** | SLI/SLO + error budget policy | C8 | Dev BR |
| **ADR-053** | Backup + DR strategy + audit hash chain | B1-B7, A13 | Dev BR + TI MT |
| **ADR-054** | Rate limiting + WAF (Caddy native vs Cloudflare frente) | A6 | Dev BR |
| **ADR-055** | Feature flags strategy (tabla DB con UI vs Unleash OSS) | M1, M4 | Dev BR |
| **ADR-056** | Conventional commits + semver + release-please automation | F3, F4 | Dev BR |
| **ADR-057** | Email transaccional provider (Resend vs Postmark vs SES) + SPF/DKIM/DMARC | K5, K7 | Dev BR + TI MT |
| **ADR-058** | Branch protection + CODEOWNERS + PR review policy | F2, Q5 | Dev BR |
| **ADR-059** | PDPL UAE compliance posture + DPA management | H2, H8, H9 | Sponsor MT + legal |

---

## 6. Nuevas épicas e historias propuestas

> Para añadir a `epics-and-stories-mt-pricing-mdm-phase1.md` v1.5+. Numeradas siguiendo el patrón existente.

### 6.1 Resumen ejecutivo de épicas nuevas

| Épica | Objetivo | Sprints | SP estimados |
|-------|----------|---------|--------------|
| **EP-1A-09 — Observability stack** | Sentry FE+BE+Worker, structlog, Prometheus, Better Stack dashboards + alerting con SLO/error-budget + on-call rotation | S0 (skeleton) → S7 (cierre) | 16 |
| **EP-1A-10 — Healthchecks + status interno** | 7 endpoints granulares + Better Stack monitor + página interna `/status` para TI MT (no público Fase 1) | S1, S7 | 5 |
| **EP-1A-11 — Security hardening** | CSP report-uri, rate-limit per-endpoint, secrets manager, gitleaks/Trivy/SAST/DAST gate, OWASP review, RBAC e2e, RLS audit completo, audit hash chain | S0 (CI gates) → S7 (audit + hash chain) | 32 |
| **EP-1A-12 — Migration discipline + IaC** | Alembic dry-run + expand-contract docs + rollback automático; Ansible playbooks Hetzner + Cloudflare DNS; environment parity dev/staging/prod | S0, S1 | 18 |
| **EP-1A-13 — Quality gates + tests pyramid** | Coverage targets enforced, pre-commit framework, contract tests OpenAPI, factories+seed, Celery integration, Playwright E2E auth flow real, RBAC e2e suite, k6 load tests | S0, S2, S3, S7 | 30 |
| **EP-1A-14 — DR + Backup + runbooks operativos** | Restore drill ensayado, DR drill firmado, backup retention 7y consistente, audit payload encryption, 6 runbooks por incidente, post-mortem template | S0, S7 | 22 |
| **EP-1A-15 — Documentación operativa profesional** | Sub-processor list + DPAs, dev onboarding 1-día, API docs Redoc, walkthroughs library, sandbox training, runbooks index, meta-ADR, ADR-049 a ADR-059 escritos | S0 (frame) → S7 (cierre) | 14 |
| **EP-1A-16 — Email transaccional + feature flags + branch hygiene** | Email provider con SPF/DKIM/DMARC + templates branded MT, feature flags (Unleash o tabla DB), kill switches, branch protection + CODEOWNERS + conventional commits + release automation | S0, S5, S6 | 20 |

**Total nuevo trabajo Fase 1 = ~157 SP** (alineado con tabla §4.1).

> **Nota.** El backlog actual declara 321 SP operativos + 110 R&D = 431 SP. Añadir 157 SP de hardening lleva a **588 SP totales**. A 30-40 SP/sprint con 2-3 devs FTE, los sprints S0-S7 proyectados (8 × 35 SP = 280 SP de capacidad nominal) **no caben sin redistribuir**. Implicaciones en §7.

### 6.2 Historias clave (selección priorizada)

> Lista resumen — el backlog detallado lo expande otro agente.

| ID | Historia | Épica | SP | Sprint |
|----|----------|-------|----|--------|
| US-1A-09-01 | Pipeline Sentry FE+BE+Celery con sourcemaps y release tags | EP-1A-09 | 5 | S0 |
| US-1A-09-02 | Better Stack dashboards (Aprobaciones + Salud + Negocio) con alerting matrix | EP-1A-09 | 5 | S7 |
| US-1A-09-03 | SLO definition + error budget policy + halt-deploy rule | EP-1A-09 | 5 | S7 |
| US-1A-09-04 | On-call rotation + escalation policy post-handoff | EP-1A-09 | 1 | S7 |
| US-1A-10-01 | 7 healthcheck endpoints granulares + Better Stack monitors | EP-1A-10 | 3 | S1 |
| US-1A-10-02 | Página `/status` interna para TI MT con histórico 30d | EP-1A-10 | 2 | S7 |
| US-1A-11-01 | gitleaks + Trivy + Semgrep + pip-audit + npm-audit como gate bloqueante | EP-1A-11 | 5 | S0 |
| US-1A-11-02 | Secret manager seleccionado + integrado + rotation script | EP-1A-11 | 8 | S0/S7 |
| US-1A-11-03 | RLS audit completo + suite tests por (rol × tabla × op) | EP-1A-11 | 5 | S2 |
| US-1A-11-04 | RBAC e2e suite parametrizada por matriz | EP-1A-11 | 5 | S3 |
| US-1A-11-05 | OWASP Top 10 + API Top 10 review documentado | EP-1A-11 | 3 | S7 |
| US-1A-11-06 | DAST OWASP ZAP automated en staging + remediation | EP-1A-11 | 3 | S7 |
| US-1A-11-07 | Audit hash chain + endpoint verify | EP-1A-11 | 5 | S7 |
| US-1A-11-08 | Audit payload encryption para campos PII | EP-1A-11 | 5 | S7 |
| US-1A-11-09 | Rate limit per-endpoint sensible + CSP report-uri | EP-1A-11 | 3 | S7 |
| US-1A-12-01 | Alembic dry-run en CI + expand-contract doc + destructive detection | EP-1A-12 | 5 | S0 |
| US-1A-12-02 | Rollback automático en deploy con smoke test | EP-1A-12 | 3 | S1 |
| US-1A-12-03 | Ansible playbooks Hetzner + Cloudflare + dev/staging/prod parity | EP-1A-12 | 8 | S1 |
| US-1A-12-04 | Migration playbook documentado en handbook | EP-1A-12 | 2 | S1 |
| US-1A-13-01 | Coverage targets configurados + pre-commit framework + flaky detection | EP-1A-13 | 3 | S0 |
| US-1A-13-02 | Contract tests OpenAPI FE↔BE en CI | EP-1A-13 | 5 | S2 |
| US-1A-13-03 | Factories factory_boy + seed reproducible | EP-1A-13 | 3 | S1 |
| US-1A-13-04 | Idempotency contract + DLQ + retry+jitter en Celery | EP-1A-13 | 8 | S2 |
| US-1A-13-05 | Celery integration tests con Redis real + DLQ tests | EP-1A-13 | 3 | S2 |
| US-1A-13-06 | Playwright E2E auth flow real (5 happy paths) | EP-1A-13 | 5 | S7 |
| US-1A-13-07 | k6 load tests con escenarios críticos + baseline doc | EP-1A-13 | 5 | S7 |
| US-1A-14-01 | Restore drill ensayado pre-cutover + tiempos medidos | EP-1A-14 | 5 | S7 |
| US-1A-14-02 | DR drill firmado por TI MT + Sponsor | EP-1A-14 | 3 | S7 |
| US-1A-14-03 | Backup retention reconciliado a 7y consistente | EP-1A-14 | 1 | S0 |
| US-1A-14-04 | 6 runbooks operativos + post-mortem template | EP-1A-14 | 6 | S7 |
| US-1A-15-01 | Sub-processor list + DPA tracking | EP-1A-15 | 1 | S0 |
| US-1A-15-02 | Dev onboarding 1-day-to-PR doc | EP-1A-15 | 3 | S7 |
| US-1A-15-03 | API docs Redoc deployed en staging | EP-1A-15 | 2 | S7 |
| US-1A-15-04 | Walkthroughs library + sandbox training env | EP-1A-15 | 4 | S7 |
| US-1A-15-05 | ADR-047 a ADR-059 escritos y firmados | EP-1A-15 | 4 | S0-S7 |
| US-1A-16-01 | Email provider integrado + SPF/DKIM/DMARC en `mtme.ae` | EP-1A-16 | 5 | S5 |
| US-1A-16-02 | Templates email branded MT (digest + escalado) | EP-1A-16 | 2 | S5 |
| US-1A-16-03 | Feature flags + kill switches (tabla DB + UI admin) | EP-1A-16 | 5 | S6 |
| US-1A-16-04 | Branch protection + CODEOWNERS + conventional commits + release-please | EP-1A-16 | 3 | S0 |
| US-1A-16-05 | OWASP A06 dependency scan trimestral automatizado | EP-1A-16 | 1 | S0 |

---

## 7. Cuestiones abiertas (decisiones que sponsor / TI MT deben tomar)

> Estas no las puede decidir el agente — requieren input humano.

### 7.1 Q-RD-01 — Residencia de datos UAE (extensión de Q-02)

- **Pregunta.** Hetzner Frankfurt + Supabase EU es default. ¿TI MT acepta o exige UAE?
- **Implicación.** Si exige UAE: Supabase tiene region MEA pendiente; alternativa AWS me-central-1 con managed Postgres + S3 + Cognito (cambio de stack significativo). Hetzner no tiene UAE.
- **Bloquea.** ADR-050 (IaC), ADR-053 (DR — compliance dataflow EU vs UAE).
- **Quién decide.** TI MT (Paula) + Sponsor (Christian) + legal MT.

### 7.2 Q-RD-02 — RTO/RPO targets son aspiracionales o vinculantes

- **Pregunta.** NFR-16 dice RTO 4h / RPO 1h. ¿Es objetivo o SLA contractual?
- **Implicación.** Si vinculante: Supabase tier `Pro` con WAL streaming continuo (~$25/mo) puede no cumplir RPO 1h sin Point-in-Time Recovery activado y testeado; revisar tier. Si aspiracional: documentar como "objetivo, no SLA" en NFR-16.
- **Bloquea.** ADR-053, contrato con sponsor.
- **Quién decide.** Sponsor MT + TI MT.

### 7.3 Q-RD-03 — Presupuesto observability + email transaccional

- **Pregunta.** Better Stack ~$25/mo, Sentry SaaS ~$26/mo, Resend ~$20/mo, Doppler ~$7/mo, Cloudflare ~free, k6 cloud opcional ~$50/mo. Total ~$80-130/mo. ¿Aprobado?
- **Implicación.** Si presupuesto cero, alternativas self-host: Sentry self-host (memoria-hambriento), Loki+Grafana en mismo Hetzner (ahorro pero ops carga), MailHog + relay propio (mala delivery rate). Costo de "ahorrar" = ops + DR del propio observability.
- **Bloquea.** ADR-047, ADR-051, ADR-057.
- **Quién decide.** Sponsor MT.

### 7.4 Q-RD-04 — PDPL UAE: ¿MT es Data Controller o Processor para users de la app?

- **Pregunta.** PDPL aplica si MT procesa datos personales de personas físicas. Los `users.email` de la app (3-5 internos) son PII pero acotados. ¿Hay clientes B2C cuyos datos pasen por la plataforma Fase 1?
- **Implicación.** Si solo internos: PDPL aplica de manera ligera (DPA con sub-procesadores + ROPA). Si datos B2C: DPO obligatorio + consent management + data subject rights endpoints.
- **Bloquea.** ADR-059, alcance de H4 (right-to-be-forgotten).
- **Quién decide.** Legal MT + Sponsor.

### 7.5 Q-RD-05 — Nivel de hardening Fase 1 vs Fase 1.5

- **Pregunta.** Ante 157 SP de hardening propuestos, ¿el sponsor acepta el sprint S7 cargado a 84 SP (irreal) o se diferiere parte a "Fase 1.5 hardening" post-cutover?
- **Implicación.** Tres caminos:
  - (a) **Stretch S7**: sumar 2-3 semanas a S7 → cutover desliza ~1 mes.
  - (b) **Mínimo viable + Fase 1.5**: implementar solo los ~70 SP irreductibles (§4.2) en S0-S7 y planificar Fase 1.5 explícita post-cutover de 2 sprints.
  - (c) **Reducir alcance funcional Fase 1**: dejar fuera workstream R&D (110 SP) o EP-1A-08 scheduler editable (23 SP) para liberar capacidad.
- **Bloquea.** Reflow del backlog, expectativa go-live.
- **Quién decide.** Sponsor + Champion + TI MT en sesión dedicada post-S0.

### 7.6 Q-RD-06 — Retención `audit_events` definitiva: 5 o 7 años

- **Pregunta.** §20.7 dice 5y, NFR-35 dice 7y. Inconsistencia.
- **Implicación.** VAT UAE 2026 + Corporate Tax 2024 sugieren mínimo 7y para registros fiscales. PDPL requiere "durante el tiempo necesario para los fines del procesamiento" — flexible.
- **Bloquea.** Política de archivado, costo storage cold.
- **Quién decide.** Sponsor MT + legal MT (recomendado: 7y).

### 7.7 Q-RD-07 — Hetzner SPOF: ¿plan HA Fase 2 firmado o aceptación riesgo?

- **Pregunta.** 99,5 % horario laboral aceptado por NFR-14. Si Hetzner box muere fuera de horario → recuperación con restore manual ~4h. ¿Sponsor acepta riesgo o quiere warm standby Fase 2?
- **Implicación.** Si quiere HA Fase 2: presupuestar ~+€100/mo (segundo Hetzner CCX + Caddy upstream switching) + infra para failover.
- **Bloquea.** ADR-053 evolución, presupuesto Fase 2.
- **Quién decide.** Sponsor MT.

---

## 8. Cierre

Este documento identifica **157 SP de trabajo de hardening profesional** que el plan actual no cubre completamente. La buena noticia: la **arquitectura, datos, RBAC, audit trail, workflow de pricing y comparador** están documentados a nivel maduro. Los gaps son **operacionales y de hardening** — patrón habitual cuando se prioriza arquitectura+funcionalidad sobre operabilidad+resiliencia.

**Recomendación final**: aceptar la cifra, cargar S7 con dedicación explícita "hardening sprint" + abrir Fase 1.5 de 2 sprints post-cutover. El alternativo "lanzar Fase 1 sin hardening" es factible con un backup operator BR pegado al teléfono 24/7 — viable a corto plazo, insostenible para handoff a TI MT.

**Documentos relacionados**:
- `prd-mt-pricing-mdm-phase1.md` v1.4
- `architecture-mt-pricing-mdm-phase1.md` v1.4
- `epics-and-stories-mt-pricing-mdm-phase1.md` v1.4 (necesita v1.5 con EP-1A-09 a EP-1A-16)
- `sprint0-plan-consolidado.md` v1.1 (necesita v1.2 con S0-D16/D17/D18 para gates de hardening: secret manager + scan stack + IaC v0)

**Fin del documento — Production-Readiness Gap Analysis v1.0**
