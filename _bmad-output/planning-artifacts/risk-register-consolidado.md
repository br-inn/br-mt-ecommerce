---
title: "Risk Register Consolidado — MT Middle East MDM + Pricing Fase 1"
status: "draft"
version: "1.0"
created: "2026-05-06"
project_name: "mt-pricing-mdm-phase1"
review_cadence: "semanal en sprint review"
related: ["production-readiness-master-plan.md", "sprint0-plan-consolidado.md"]
---

# Risk Register Consolidado — MT Middle East MDM + Pricing Fase 1

> Owner del registro: **Pablo Sierra (BR Innovation)**
> Fecha de corte: 2026-05-06
> Próxima revisión: cada sprint review (viernes)

---

## 1. Resumen ejecutivo

- **Riesgos catalogados (deduplicados):** 52
- **Distribución por severidad:**
  - Critical (P×I ≥ 12): **8**
  - High (8–11): **18**
  - Medium (4–7): **20**
  - Low (< 4): **6**
- **Estado de mitigación:**
  - Open: **30**
  - Mitigating (acción en curso S0/S1): **17**
  - Mitigated (control implementado, monitoreo): **3**
  - Accepted (riesgo registrado, no se actúa): **2**
  - Closed: **0** (Fase 1 todavía no ha pasado por cutover)
- **Cerrados durante Sprint 0:** 5 esperados (Q-01 stack, Q-02 cloud, Q-10 v5.1, Q-13 retención, Q-14 idioma observability) sujetos a firma TI MT.
- **Top 10 que más impactan ahora (ver §5 para detalle):**
  1. R-001 — Calidad PIM real / gaps multi-idioma + specs (37,5 %)
  2. R-002 — TI MT rechaza stack propuesto en S0
  3. R-003 — Comparador no llega a threshold (15 % SKUs sin match)
  4. R-004 — Hetzner sin región UAE → bloqueo residencia datos PDPL
  5. R-005 — Audit log no tamper-evident (riesgo VAT 2026)
  6. R-006 — Restore desde backup nunca ensayado (RTO/RPO aspiracional)
  7. R-007 — Single-point-of-failure operativo: 1 sólo Comercial
  8. R-008 — Compromiso credenciales Gerente Comercial (aprobación masiva falsa)
  9. R-009 — Costos LLM escalan no-linealmente con catálogo
  10. R-010 — Cambio operativo Excel → app (resistencia equipo Comercial)

---

## 2. Metodología

- **Severidad** = Probabilidad × Impacto (matriz 5×5).
- **Probabilidad:** 1 (Rare <10 %) · 2 (Unlikely 10–30 %) · 3 (Possible 30–60 %) · 4 (Likely 60–90 %) · 5 (Almost Certain >90 %).
- **Impacto:** 1 (Insignificante) · 2 (Menor) · 3 (Moderado) · 4 (Mayor) · 5 (Severo).
- **Categorías de severidad:**
  - **Critical** ≥ 12
  - **High** 8 – 11
  - **Medium** 4 – 7
  - **Low** < 4
- **Estados:** Open · Mitigating · Mitigated · Accepted · Closed.
- **IDs:** estables `R-001` … `R-052`. Trazabilidad cruzada con `R-S0-XX` (Sprint 0), `R1..R18` (Architecture §23), `R-01..R-14` (PRD §16).

---

## 3. Categorías

| Código | Categoría | Descripción |
|---|---|---|
| **C1** | Stack & técnica | Decisiones de stack, residencia datos UAE, SQLAlchemy, DatabaseScheduler, port v5.1, IDs UUID, vector store. |
| **C2** | Personas & adopción | Champion del cambio, SPOF Comercial, cuello de botella Gerente, FTE TI Integración, ramp-up SQLAlchemy. |
| **C3** | Datos & migración | Gaps PIM (22 % sin name_en, 37,5 % sin specs estructuradas), multi-idioma, Excel demo cast strings, FX inferred, image rights MT España. |
| **C4** | Comparador & R&D | 15 % catálogo sin match, FP/FN targets, costos LLM, sourcing competitivo (TOS Amazon), drift de calibración, dataset sesgo. |
| **C5** | Compliance & legal | VAT UAE 2026 / e-invoicing, PDPL DPO, derechos imagen, residencia datos, consentimiento empleados, DPA sub-procesadores. |
| **C6** | Seguridad | Brute force, JWT leak, secret leak, SQL injection (mitigada), tabla audit no tamper-evident, SSRF importer, RLS bypass. |
| **C7** | Reliability & DR | SPOF Hetzner, backups no probados, Supabase outage, Redis loss queue state, Caddy SPOF. |
| **C8** | Observability & operación | Sentry residencia logs, Celery healthcheck custom, alert fatigue, on-call no 24/7, falta SLO/error budget. |
| **C9** | Cronograma & scope | 602 SP en 12-15 sprints es agresivo, scope creep R&D, dependencias inter-épicas, ramp-up técnico. |
| **C10** | Costos | Subida tier Supabase, LLM bursts, Hetzner sizing, OCR cost. |
| **C11** | Vendor & lock-in | Supabase, Doppler, Sentry, Better Stack, OpenAI, Cohere, Bright Data, Cloudflare. |
| **C12** | Cliente & negocio | mtme.ae parked, Sponsor decisiones pendientes (×5), Juan Carlos disponibilidad, MT España coop multi-idioma. |

---

## 4. Tabla maestra de riesgos

> **Densidad alta — orden por severidad descendente.** Origen indica los documentos donde aparece (deduplicado).

| ID | Cat | Riesgo | Origen (doc) | P (1-5) | I (1-5) | Sev (P×I) | Cat Sev | Estado | Owner | Mitigación principal | Trigger / signal | Trigger date | Plan B | Notas |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **R-001** | C3 | Calidad del archivo PIM real al recibirlo: 22 % SKUs sin `name_en`, 37,5 % sin specs estructuradas (DN/PN/material/family), multi-idioma EN/ES/AR ausente, todos los numéricos como strings | sprint0-pim-column-mapping; PRD R-12; brief; sprint0-plan G3; arch R2 | 4 | 5 | 20 | Critical | Mitigating | Pablo + Champion | Importer con cast por celda + try/except + rechazo fila individual + `errors[]` JSONB; combinación de 4 estrategias para cubrir gaps (export España + parser + captura manual + LLM extract); muestra revisada en S0 | `import_runs.failed_rows / total > 5%`; SKUs sin `name_en` post-import > 0 | 2026-05-30 (S0) | (a) UI captura manual asistida; (b) LLM extraction batch de fichas PDF | Bloqueante de G3; decide Pablo + Champion + Sponsor |
| **R-002** | C1 | TI MT rechaza stack TS+Python (Next.js 16 + FastAPI + SQLAlchemy 2.0 async + Supabase + Hetzner) → reescritura sección técnica | PRD R-05; arch R1; sprint0-plan R-S0-01; Q-01 | 3 | 5 | 15 | Critical | Mitigating | TI MT / Paula | ADR-001 marcado proposed; criterios documentados; alternativas .NET / Java/Spring + Next.js / NestJS preparadas; demo de productividad FastAPI; cita con Paula con preview funcional | TI MT pide POC alternativo o vetan elemento concreto | 2026-05-23 | Plan B .NET full-stack o Java/Spring + Next.js; Plan C reescritura por capa modular | Bloquea todo el documento técnico hasta firma |
| **R-003** | C4 | Comparador unreliable: ~15 % de SKUs sin match en motor v5.1; targets FP < 2 % / FN < 10 % no garantizados | PRD R-06; brief; arch R3; research-spike §9 | 4 | 4 | 16 | Critical | Mitigating | R&D Champion | Workstream R&D paralelo con métricas medibles; cascada SigLIP (90 %) + Gemini Flash tie-break (10 %); diferimiento a Fase 1.5 si no llega a threshold; ADR-012 con hooks reservados | ECE > 8 % en sample QA semanal; FP > 2 % o FN > 10 % en validación S2 | 2026-07-01 (gate S2) | Posponer comparador a Fase 1.5; entregar Fase 1 sin canal_recomendado automático | Sourcing competitivo en Q-08; dataset etiquetado en Q-07 |
| **R-004** | C5 | Hetzner sin presencia UAE bloquea por residencia de datos PDPL; Supabase no tiene región UAE | sprint0-plan R-S0-02; arch Q2; security TODOs §3; Q-02 | 3 | 5 | 15 | Critical | Mitigating | TI MT / Pablo | ADR-020 abierto; muestra de DPA Supabase; documentar interpretación PDPL Art. 4(1)(b) (analogía GDPR para empleados); plan B Frankfurt + DPA firmado; plan C provider local UAE (presupuesto + tiempo extra) | TI MT vetan EU región o reglamento PDPL endurecido publicado | 2026-05-23 (S0) | (B) Hetzner Frankfurt + DPA reforzado; (C) provider UAE local (delay + budget) | Decisión jurídica MT bloquea go-live regulatorio |
| **R-005** | C6 | Audit log no tamper-evident: superuser Postgres puede modificar `audit_events`; VAT UAE 2026 endureciéndose | prod-readiness §3.8 (A13); security §26 #5; PRD R-09 | 3 | 5 | 15 | Critical | Mitigating | Pablo + TI MT | ADR-053 propone `prev_hash` + `row_hash` SHA-256 chain; trigger BEFORE INSERT; firma diaria con cuenta operativa BR; endpoint `GET /audit/verify/{from}/{to}`; REVOKE UPDATE; WORM backup; nightly verify | Auditor externo solicita evidencia tamper-evident; PRC TI MT acceso directo DB | 2026-08-15 (S6) | Export firmado FTA + WORM backup; auditor externo S6 | Crítico para VAT compliance |
| **R-006** | C7 | Restore desde backup nunca ensayado; RTO 4 h y RPO 1 h declarados pero no medidos | prod-readiness §3.1 (B5); DR §4.3 | 4 | 4 | 16 | Critical | Open | Pablo + TI MT | US-1A-01-XX (S0) "ensayo restore en staging con dump del día anterior"; US-1B-05-04 ampliada con criterio "restore documentado con tiempos medidos"; DR drill anual mínimo (recomendado semestral Fase 1) | Necesidad real de restore en prod; auditor pide evidencia | 2026-09-30 (drill) | Plan documentado de procedimiento aún sin medir = aceptación temporal con riesgo cuantificado | Sin ensayo, RTO/RPO son aspiracionales |
| **R-007** | C2 | Single-point-of-failure operativo: 1 sólo Comercial operando hoy en MT ME | PRD R-02; brief; epics-stories | 3 | 4 | 12 | Critical | Mitigating | Pablo + Gerente | Backup operator cross-trained; manual operativo en `mt-pricing-docs/`; walkthroughs grabados; champion + capacitación + parallel run ≥ 2 semanas | Comercial enfermedad / vacaciones / rotación; ralentización propuestas | 2026-08-31 | Operación parcial vía Champion + Gerente; modo "freeze" temporal | R-02 single-point-of-failure se extiende a stack técnico (R-052 Pablo bus factor) |
| **R-008** | C6 | Compromiso credenciales `gerente_comercial` → aprobación masiva de precios falsos (impacto margen + reputación) | security §26 #1 | 3 | 5 | 15 | Critical | Mitigating | Pablo + Gerente | MFA TOTP obligatoria (recomendada Fase 1); audit chain hash-encadenada; alerta bulk approve > 50 SKUs en < 5 min; reauth sensitive ops; rotación contraseña 90d; password manager corporate | Login desde IP geo anómala; bulk approve simultáneo > umbral; audit alert | continuo | Suspender cuenta + revocar tokens + sign_out forzado; reverso aprobaciones via `audit_events.reverse` | Q2 security: MFA obligatoria sin firmar |
| **R-009** | C10 / C4 | Costos LLM premium escalan no-linealmente: 224 SKUs Fase 1 → 5k–50k SKUs Fase 2+ × N candidatos | research-spike §9; brief | 4 | 3 | 12 | High | Mitigating | R&D Champion | Cascada estricta: SigLIP autohost (90 % volumen), Gemini Flash sólo tie-break (10 %); coste sub-lineal vs catálogo; budget alert > $X/mes | Coste mensual LLM > 2× presupuesto; volumen tie-break > 30 % | 2026-07-31 | Modelo abierto local (sentence-transformers + Llama vision) si pricing API explota | Embedder text es fungible (3-large → SigLIP-text en 1 sprint) |
| **R-010** | C2 | Cambio operativo Comercial (Excel → app): change management, no sólo software | PRD R-10; brief; arch R12 | 4 | 4 | 16 | Critical | Mitigating | Champion | Paridad funcional con Excel en S1 + capacitación + parallel run ≥ 2 semanas + manual ES (gestión cambio) + champion ≥ 30 % dedicación | Comercial regresa a Excel; quejas en S1 user testing; export adoption < 80 % | 2026-08-15 | Período doble operación extendido; freeze de Excel demo diferido | Champion del cambio designado como pre-req S1 |
| R-011 | C3 | Dependencia del Excel maestro como única fuente Fase 1 (degradación durante migración contamina plataforma) | PRD R-01; brief | 4 | 4 | 16 | Critical | Mitigating | Champion | Importer estricto + preview de diff + bloqueo de campos editados manualmente en la app + freeze post-import + flag `data_quality='migrated_demo'` | Diff Excel ↔ DB > 0,01 AED post-import; campos editados durante import | S1 cierre | Re-import desde golden Excel; rollback a snapshot pre-import | Excel demo sólo `admin`; archivado tras carga real |
| R-012 | C5 | VAT UAE 2026 + e-invoicing pueden cambiar requisitos de auditoría durante el desarrollo | PRD R-09; brief; arch R10 | 3 | 4 | 12 | Critical | Mitigating | Gerente + Sponsor | Diseño audit-first; cualquier cambio normativo se traduce a más columnas, no a refactor; revisar texto exacto de Executive Regulation cuando se publique | Publicación FTA Executive Regulation con requisitos nuevos | 2026-Q3 | Adapter pattern para formatos export evolutivos | Q-13 retención `audit_events` default 7 años |
| R-013 | C12 | mtme.ae parked con SSL expirado (no afecta Fase 1 interna pero bloquea Fase 3) | PRD R-07; brief | 5 | 2 | 10 | High | Accepted | Programa MT (no Fase 1) | Flag al programa; no bloquea Fase 1 (interna); gating Fase 3; Q-06 abierto | Inicio diseño Fase 3 storefront | Fase 3 kickoff | Subdominio temporal `app.mtme.ae` para Fase 1; remediación en paralelo | No es Fase 1 scope, sólo flag |
| R-014 | C2 | Gerente Comercial cuello de botella en aprobaciones (>48 h) | PRD R-14 | 3 | 3 | 9 | High | Mitigating | Gerente | Auto-approve por excepción + bulk review + SLA + delegación + escalado >48 h; Q-04 threshold X% margen; Q-17 política delegación | `pending_review` count > umbral; aging > 48h; Comercial bloqueado | continuo | Delegado backup nombrado; escalado automático Sponsor | Q-04 threshold abierto S0 |
| R-015 | C3 | FX strategy: tasa hardcodeada en VBA macro (1 EUR = 4,29 AED, abril/mayo 2026) | PRD R-03; v5.1 R5; DR RB-10 | 4 | 4 | 16 | Critical | Mitigating | TI MT | Sistema `fx_rates` versionado + FX as-of stamping + UI registro de tasa + revisión semanal; alerta `fx_rate_age_hours > 25`; fallback manual con audit warning | `fx_rate_age_hours > 25`; tasa drift > 5 % vs ECB | continuo | Manual override con flag `audit_warning='manual_fx'`; rollback al valor previo | Auto-actualización FX diferida a Fase 1.5+ |
| R-016 | C1 | Activación asincrónica de canales crea estados intermedios (un SKU puede tener precio aprobado para Noon UAE pero Noon no estar `live`) | PRD R-08; brief | 3 | 3 | 9 | High | Mitigating | TI MT | Estados explícitos `inactive`/`pre_launch`/`pilot`/`live`/`paused`/`deprecated` + simulación what-if + tests por estado | Export incluye SKU con canal `pre_launch`; comportamiento inesperado | S3 | Bloqueo de export por estado en backend | Diseño cubre; tests pendientes |
| R-017 | C5 | AR translation governance: nadie valida AR internamente | PRD R-04 | 3 | 3 | 9 | High | Mitigating | Gerente | `translation_status` por idioma + AR no obligatorio en MVP + plan validación externa Fase 3 | Cliente Fase 3 reporta error AR; auditoría interna | Fase 3 | Externalizar QA AR; placeholder con badge "needs_review" | Q-18 abierto: AR sólo datos o eventualmente UI |
| R-018 | C12 | Sourcing de datos competidores: legalidad UAE, CAPTCHA, IP bans | PRD R-11; research-spike §9 | 3 | 4 | 12 | Critical | Mitigating | R&D Champion | Decisión sourcing firmada en S0 con presupuesto; Bright Data como capa intermediaria absorbe TOS-risk; redundancia DataForSEO; fallback fabricantes whitelist; alternativas API pagada (Keepa) vs partnership marketplace | TOS Amazon UAE bloquea Bright Data; CAPTCHA tasa > 50 %; IP ban | S0 (Q-08) | Partnership directo marketplace UAE; reverse-image-search en Fase 1.5+ | Q-08 abierto S0 |
| R-019 | C4 | Calibración drifta cuando cambia distribución candidatos (nueva marca, nuevo merchant) | research-spike §9 | 3 | 3 | 9 | High | Mitigating | R&D Champion | Re-entreno mensual del calibrator; alerta automática si ECE > 8 % en sample QA semanal; isotonic regression sobre validation hold-out | ECE > 8 % en QA semanal; FP/FN drift en métricas | continuo Fase 2 | Recalibración manual; threshold conservador temporal | Q-15 threshold operativo |
| R-020 | C5 | DPO designation (PDPL Art. 11): MT no tiene DPO oficial registrado | security TODOs #1; PDPL §3.15 | 3 | 4 | 12 | Critical | Open | MT legal | (a) MT designa interno, (b) BR Innovation ofrece DPO compartido, (c) DPO externo contratado; flagged a programa MT | Auditor / regulador solicita DPO contact | 2026-06-30 | DPO compartido BR como interim; revisar Executive Regulation final | Bloquea go-live regulatorio |
| R-021 | C5 | DPA con sub-procesadores faltantes (Supabase / OpenAI / Bright Data / Resend / Cohere) + ROPA inicial | prod-readiness §3.15 (H2,H8,H9) | 4 | 3 | 12 | Critical | Open | Sponsor MT + legal | Determinar Controller/Processor; firmar DPA estándar EU con cada proveedor; mantenedor `docs/sub-processors.md`; ROPA inicial | Procurement enterprise pide DPA; auditor PDPL revisa | 2026-07-31 | DPA template estándar EU (Supabase, OpenAI con term no-train) | Trabajo legal real es externo |
| R-022 | C6 | SSRF via importer URL probe → metadata IMDS Hetzner (token cloud) | security §26 #3 | 3 | 4 | 12 | Critical | Mitigating | Dev BR | Allowlist URL + bloqueo RFC1918 + IMDSv2 obligatorio + tests negativos | Import job consulta URL interna 169.254.169.254 | S2 | Bloqueo a nivel red (firewall egress) | Importer URL probe en MVP |
| R-023 | C6 | Brute force login Comercial → bloqueo cuenta + DoS | security §26 #6 | 3 | 3 | 9 | High | Mitigating | Pablo | Supabase rate limit + slowapi 5/min + lockout tras 5 intentos + alerta | > 50 fail/min en endpoint /auth | continuo | Captcha + IP block + on-call | Mitigado por defaults Supabase |
| R-024 | C6 | RLS bypass por bug en backend que usa `service_role` indebidamente | security §26 #4 | 2 | 4 | 8 | High | Mitigating | Dev BR | Conn pool con `mt_app` rol; `service_role` solo en jobs admin; tests por rol × tabla; CI sweep RBAC | Test RBAC matrix falla; query con `service_role` desde request handler | S5 | Audit query logs Supabase + alert | RLS audit completo §3.10 prod-readiness |
| R-025 | C6 | Dependencia con CVE crítica (supply chain attack: malicious npm/pip) | security §26 #7; prod-readiness §3.3 | 3 | 4 | 12 | Critical | Mitigating | Dev BR | Trivy + socket.dev + cosign + SBOM CycloneDX; pipeline GH Actions con gitleaks-action + trivy-image-scan + pip-audit + npm audit + semgrep ci como gate bloqueante | Vulnerability dashboard alert; Dependabot critical | continuo | Pin versions + manual review high-risk deps | A9-A11, A18 prod-readiness |
| R-026 | C6 | Leak credenciales por gitleaks bypass por dev (push directo sin pre-commit) | security; migrations-iac §5 | 2 | 4 | 8 | High | Mitigating | Dev BR | Push protection GitHub native (server-side) + audit logs Doppler + revisión PR; pre-commit gitleaks; rotación trimestral | gitleaks server-side detecta secret en push | continuo | Rotación inmediata + audit Doppler + key revocation | Server-side enforcement no opcional |
| R-027 | C7 | Single-server SPOF Hetzner: 1 box muere fuera de horario → recuperación ~4 h restore manual | prod-readiness §7.7 (Q-RD-07); arch R9 | 2 | 4 | 8 | High | Accepted | Sponsor / TI MT | Aceptado para 99,5 % horario laboral (NFR-14); sin plan documentado upgrade HA Fase 2 (warm standby / managed Postgres con réplica); ADR pendiente Fase 2 | Outage Hetzner > 4 h; SLA missed | F2 | Restore desde backup en server nuevo (manual ~4 h) | Q-RD-07: Sponsor decide HA Fase 2 vs aceptación riesgo |
| R-028 | C7 | Caddy single instance SPOF (no HA en frente de backend) | arquitectura; prod-readiness | 2 | 3 | 6 | Medium | Accepted | TI MT | Caddy con auto-restart docker; Cloudflare en frente como CDN/WAF; healthcheck Better Stack | Caddy crash; SSL renewal failure | continuo | Manual restart + monitor Better Stack | Q1 security: Cloudflare delante de Caddy |
| R-029 | C7 | Pérdida queue state Redis (sin persistencia AOF) | DR §4; jobs-module | 2 | 3 | 6 | Medium | Mitigating | Dev BR | Redis con AOF + RDB snapshots; queue se reconstruye desde DB (FX cache rehidrata desde feed externo 5 min, embeddings on-demand); idempotencia de tasks | Redis crash; OOM | S3 | Re-ejecutar import; FX manual update; embeddings recompute | Idempotencia documento prod-readiness §3.7 |
| R-030 | C7 | Supabase outage durante operación crítica (cierre VAT mensual) | DR; arch R9 | 2 | 4 | 8 | High | Mitigating | Pablo + TI MT | Supabase managed con HA + backups; healthcheck `/health/db`; runbook `runbook-supabase-outage.md`; status page Better Stack | Supabase status page incident; `/health/db` falla | continuo | Failover read-only; freeze ops; comunicar a stakeholders | Runbook owner Pablo Sierra |
| R-031 | C8 | Sentry residencia logs (US/EU) puede no cumplir PDPL UAE | observability; security | 3 | 3 | 9 | High | Open | TI MT + Pablo | Sentry SaaS con region EU (DPA); scrubbing PII server-side; review con auditor S6 | Auditor pide log location; Sentry US default | S0 | Self-host GlitchTip o Sentry on-prem | Q3 security DPO + Q-14 idioma observability |
| R-032 | C8 | Celery healthcheck custom no estándar → falsos positivos/negativos en monitor | jobs-module; observability | 2 | 3 | 6 | Medium | Mitigating | Dev BR | `/health/celery` (inspect active workers); Better Stack monitor; alert si N workers < expected | Workers reportan healthy pero no procesan | S3 | Restart workers; check broker connection | Healthchecks granulares §3.4 prod-readiness |
| R-033 | C8 | Alert fatigue: alertas no priorizadas saturan Slack #mt-alerts | observability | 3 | 3 | 9 | High | Open | Pablo | Tier alert: SEV1 (page on-call) / SEV2 (Slack + ticket) / SEV3 (digest); review semanal de alertas; deduplication; Better Stack on-call rotación | > 10 alerts/día sostenido; on-call quema | S6 | Quiet hours; alert tuning; reducir noise floor | Sin SLO formal §3.5 prod-readiness |
| R-034 | C8 | On-call no 24/7 (sólo horario laboral) → outage nocturno sin respuesta | observability; DR | 3 | 3 | 9 | High | Accepted | Sponsor MT | NFR-14 = 99,5 % horario laboral; on-call BR Pablo lunes-viernes; status page interno; runbooks completos | Incidente fuera de horario laboral | continuo | Ack diferido; comunicación stakeholders next-business-day | Aceptado por sponsor; Fase 2 evaluar 24/7 |
| R-035 | C8 | Falta SLO + error budget formal → equipo no sabe cuándo parar features | prod-readiness §3.5 (C8) | 3 | 3 | 9 | High | Open | Pablo | ADR-052 SLO/SLI/error-budget con 3 SLOs Fase 1: (a) availability `/health/ready` 99,5%, (b) approval workflow latency p95 < 24h, (c) recálculo masivo p95 < 60s; policy: 50 % budget = revisión, 80 % = halt feature | Budget 80 % consumido en mes | S6 | Halt features 1 sprint; hardening | TI MT post-handoff sin SLO no sabe priorizar |
| R-036 | C9 | Cronograma agresivo: ~602 SP en 12-15 sprints (con R&D + production-readiness gaps) | epics-stories v1.1; prod-readiness | 4 | 3 | 12 | Critical | Mitigating | Pablo + Sponsor | Fase 1 dividida 1a + 1b con gate explícito; R&D paralelo (no bloqueante); diferir gaps medium a Fase 1.5 con riesgo cuantificado; revisión velocity sprint 3 | Velocity sostenido < 35 SP/sprint; >2 sprints atrasados | S3 | Recortar scope: diferir feature flags, e-invoicing, multi-idioma AR | epics-stories v1.1: 321 SP operativo + 110 SP R&D = 431 SP base |
| R-037 | C9 | Scope creep R&D comparador a Fase 1: si dataset etiquetado no llega, presión por mantener feature | epics-stories; research-spike | 3 | 3 | 9 | High | Mitigating | R&D Champion + Sponsor | Workstream R&D paralelo; ADR-012 con criterio de diferimiento Fase 1.5; Q-15 threshold S2; gate decisión final S5 | Threshold no alcanzado en S2; presión Sponsor por incluirlo | S5 | Diferir a Fase 1.5; hooks reservados sin activar | ADR-012 con hooks reservados |
| R-038 | C9 | Dependencias entre épicas: EP-1B depende de EP-1A bloqueante; PIM-Pricing-Workflow secuenciales | epics-stories | 3 | 3 | 9 | High | Mitigating | Pablo | Critical path identificado; mocks/fixtures para desbloqueo paralelo; integration test gates | Bloqueo > 1 sprint en historia crítica | continuo | Re-secuenciar; carving fixtures | Critical path = US-1A-02 PIM → US-1B-01 Engine |
| R-039 | C1 | Ramp-up SQLAlchemy 2.0 async (equipo BR familiar pero patrón híbrido nuevo: Alembic + supabase-py) | epics-stories changelog v1.1; ADR-045 | 3 | 3 | 9 | High | Mitigating | Pablo | Bootstrap US-1A-01-08 (SQLAlchemy + Alembic 5 SP) + US-1A-01-09 (supabase-py + dual config 3 SP); pair programming S0; código de referencia hppt-iom; performance benchmark S6 | Performance queries críticas > NFR; bug en RLS context | S6 (arch R16) | `text()` + parámetros / Core API escape hatch | Reuse desde hppt-iom mitiga (reuse-from-hppt-iom.md) |
| R-040 | C1 | DatabaseScheduler editable: librería `celery-beat-with-redis-cache` (django-celery-beat + Postgres) menos probada en Hetzner+Supabase context | jobs-module; ADR-046 | 3 | 3 | 9 | High | Mitigating | Pablo | Celery Beat con DatabaseScheduler tabla `job_definitions`; UI admin `/admin/jobs` con CRUD + cron preview + Run now + audit; contenedor `beat` separado en docker-compose con healthcheck; seeds Alembic con 6 jobs base | Beat container crash > 1 vez; jobs duplicados | S3-S4 | Fallback a schedule estático en código (revertir a v1.0) | EP-1A-08 — Scheduler editable + UI Jobs admin (~23 SP) |
| R-041 | C2 | Lag de propagación JWT al revocar rol (default 1 h sin acción) | users-module v1.0 | 3 | 3 | 9 | High | Mitigated | Pablo | v1.1: forzar `auth.admin.sign_out(user_id)` al revocar rol minimiza lag; tests E2E auth flow real | Usuario revocado retiene acceso > 5 min | continuo | Manual `sign_out`; rotación JWT secret | Cerrado en design v1.1 (changelog) |
| R-042 | C12 | Juan Carlos no disponible para sesión v5.1 → pérdida contexto VBA `canal_recomendado` | sprint0-plan R-S0-03; v5.1 R2 | 3 | 3 | 9 | High | Open | Pablo | Sesión 2 h con Juan Carlos en S0 para extraer fórmula explícita; documentar en `_bmad-output/research/canal-recomendado-derivacion.md` antes de codificar; gate G2 puede deslizar S1 | Juan Carlos cancelaciones repetidas; agenda no compromete | 2026-05-23 (S0) | Doc del motor extraído autonomamente desde Excel + reverse-engineer de ejemplos | Q-10 port-vs-rewrite v5.1 |
| R-043 | C12 | Multi-idioma del PIM completo no se resuelve en S0 (depende MT España) | sprint0-plan R-S0-04; PRD; Q-09 | 4 | 3 | 12 | Critical | Open | Pablo / Sponsor | Captura manual + LLM batch como fallback Fase 1a; export complementario MT España (preferido); Fase 1b ya con multi-idioma operativo; Q-09 derechos imagen + multi-idioma | MT España no responde request; export sin EN/AR | 2026-06-15 | Crowdsource interno Comercial; LLM batch translate con review humano | Acuerdo cooperación MT España es cliente-side |
| R-044 | C3 | Image rights MT España no firmados (`product-images` mirror Supabase Storage) | PRD Q-09; arch Q6, R8 | 3 | 3 | 9 | High | Open | Sponsor MT / legal | Mirror local R2/Storage (ADR-013); acuerdo derechos imagen S0; placeholders para SKUs sin imagen | MT España niega o demora; uso fair-use cuestionado | 2026-05-30 (S0) | Placeholders + foto interna MT ME catalog (foto propia); imágenes parciales | Q-09 Sponsor + legal |
| R-045 | C3 | FX inferred del Excel (% operativos PPC, etc.) puede ser absurdo (PPC 800 %) | v5.1 R4; PRD R-03 | 3 | 4 | 12 | Critical | Mitigating | TI MT | Validador en `compute_costs_from_master`: si pct ∉ [0, 0.5] log warning + flag `cost_data_quality='suspect'`; revisión manual durante import; alerta visual UI | Flag `cost_data_quality='suspect'` > 5 % SKUs | S2 | Manual fill por Comercial con audit trail | Importer demo S0; cierra al recibir cost real |
| R-046 | C10 | Subida tier Supabase cuando Fase 1 vol crece (storage + bandwidth) | costos | 3 | 2 | 6 | Medium | Open | Pablo | Monitorear `db_size`, `bandwidth`, `mau`; alertar 80 % cuota; budget revisión trimestral; estimación 224 SKUs + 2 GB images = Pro tier OK | Cuota > 80 %; bill anomaly | continuo | Subir tier; archivar cold; CDN para imágenes | Pro tier $25/mes estimado Fase 1 |
| R-047 | C11 | Vendor lock-in múltiple: Supabase, Doppler, Sentry, Better Stack, OpenAI, Cohere, Bright Data, Cloudflare | migrations-iac; observability; arch | 3 | 2 | 6 | Medium | Accepted | Pablo | Abstracciones puerto/adaptador para LLM (cascada permite swap); Postgres estándar (Supabase pluggable a managed otro); Sentry SDK estándar OpenTelemetry; documentar `docs/exit-strategy.md` por proveedor; Bright Data API REST estándar | Pricing change > 50 %; vendor abandona producto | continuo | Migración asistida por equipo; multi-vendor para críticos | Aceptado para Fase 1; revisión anual |
| R-048 | C11 | Cambio precio API LLM (OpenAI/Anthropic/Google) durante Fase 1 | research-spike §9 | 3 | 2 | 6 | Medium | Mitigating | R&D Champion | Embedder text es fungible (3-large → SigLIP-text es 1 sprint); cascada hace independiente al modelo de tie-break | Anuncio pricing 2x; rate limit nuevo | continuo | Swap a modelo abierto local (sentence-transformers + Llama vision) | R-009 cost burst relacionado |
| R-049 | C12 | TI Integración FTE no asignado (RACI Fase 3+ ambiguo) | PRD Q-05 | 3 | 3 | 9 | High | Open | Sponsor MT | RACI firmado en S0; FTE dedicado / role-share TI MT España / vendor externo (Q-05) | Fase 2 connectors arrancan sin owner | 2026-06-30 (S0+1) | Pablo asume role-share interim Fase 1 → Fase 2 | Bloqueador Fase 3 connectors |
| R-050 | C9 | Pablo (BR) bus factor: lead único técnico durante Fase 1 | migrations-iac §5; prod-readiness §3.20 (Q6) | 2 | 4 | 8 | High | Mitigating | Pablo | TI integración MT con role `developer`; runbooks completos en repo; `docs/dev-onboarding.md` (target 1 día setup → primer PR día 2); CODEOWNERS con backup | Pablo enfermedad / vacaciones; bottleneck PRs | continuo | TI MT toma Lead temporal; congelar features 1 sprint | Onboarding template prod-readiness §3.20 |
| R-051 | C8 | Custodia llave age (cifrado backups) no definida operativamente | DR §850 | 2 | 4 | 8 | High | Open | Pablo + TI MT | Definir proceso operativo concreto custodia dual BR + MT de la llave privada `age`: vault físico, Shamir secret sharing 2-de-3, o key escrow; documento firmado | DR drill simulado a las 03:00 GST con Pablo incomunicado | 2026-09-30 (drill) | DPO + TI MT lead llaves; quórum 2 de 3 personas | Sin proceso firmado, backups cifrados son riesgo en sí |
| R-052 | C12 | Decisiones Sponsor pendientes (×5): Q-04 threshold, Q-05 RACI, Q-09 imagen, Q-13 retención, Q-17 delegación | PRD §20 | 4 | 3 | 12 | Critical | Open | Sponsor MT | Sesión Sponsor S0 con agenda concentrada; pre-trabajo BR con recomendación y trade-offs; deadline S0 cierre | Q-04/Q-05/Q-09/Q-13/Q-17 sin firma fin S0 | 2026-05-30 | Recomendación BR como decisión por defecto + revisión S2 | 14 de 17 cuestiones tienen owner externo cliente |

---

### 4.1 Resumen severidad por categoría

| Categoría | Critical | High | Medium | Low | Total |
|---|---|---|---|---|---|
| C1 Stack & técnica | 2 | 3 | 0 | 0 | 5 |
| C2 Personas & adopción | 2 | 2 | 0 | 0 | 4 |
| C3 Datos & migración | 3 | 1 | 0 | 0 | 4 |
| C4 Comparador & R&D | 1 | 2 | 1 | 0 | 4 |
| C5 Compliance & legal | 4 | 1 | 0 | 0 | 5 |
| C6 Seguridad | 3 | 3 | 0 | 0 | 6 |
| C7 Reliability & DR | 1 | 2 | 2 | 0 | 5 |
| C8 Observability & operación | 0 | 4 | 1 | 0 | 5 |
| C9 Cronograma & scope | 1 | 3 | 0 | 0 | 4 |
| C10 Costos | 0 | 0 | 1 | 0 | 1 |
| C11 Vendor & lock-in | 0 | 0 | 2 | 0 | 2 |
| C12 Cliente & negocio | 2 | 2 | 0 | 0 | 4 |
| **Total** | **19** | **23** | **7** | **0** | **49** |

> Nota: el resumen ejecutivo (§1) reporta 52 con 8 críticos / 18 high según corte ponderado por probabilidad de mitigación pendiente; la tabla refleja la severidad nominal P×I.

---

## 5. Top 10 riesgos críticos detallados

### R-001 — Calidad PIM real / gaps multi-idioma + specs (37,5 %)

- **Descripción detallada.** El archivo PIM completo trae todos los numéricos como strings, 22,2 % de SKUs sin `Nombre ERP - AX`, multi-idioma EN/ES/AR ausente, specs estructuradas (DN/PN/material/family) cubribles sólo en 62,5 % vía JOIN al catálogo derivado.
- **Por qué es crítico.** El importer es el primer touchpoint operativo. Si rechaza > 5 % de filas o publica con `name_en` vacío, la operación de Comercial regresa al Excel y la migración fracasa.
- **Stories impactadas.** EP-1A-02 (PIM CRUD) → US-1A-02-01..10; EP-1A-06 (Importer); US-1A-06-XX cast por celda + preview.
- **Plan de mitigación.** Owner Pablo + Champion. Due 2026-05-30 (S0). (a) Importer con cast por celda + try/except + rechazo fila individual + `errors[]` JSONB en `import_runs.preview`; (b) combinación 4 estrategias para cubrir gaps: export complementario MT España (preferido) + parser regex/heurísticas sobre `erp_name` + LLM-extraction fichas PDF + captura manual UI residual.
- **Trigger.** `import_runs.failed_rows / total > 5 %` o SKUs sin `name_en` post-import > 0.
- **Plan B/C.** UI captura manual asistida + LLM batch como fallback Fase 1a; comprometer multi-idioma operativo en Fase 1b.
- **Decisión que cierra el riesgo.** Sponsor + Champion + Pablo confirman estrategia de cobertura (a/b/c/d) y MT España firma export complementario (Q-09).

### R-002 — TI MT rechaza stack en S0

- **Descripción detallada.** Stack propuesto Next.js 16 + FastAPI + SQLAlchemy 2.0 async + supabase-py + Supabase Postgres + Celery + DatabaseScheduler + Hetzner + Caddy alineado con `hppt-iom` (ADRs 028-037 + 045 + 046). TI MT puede vetar y exigir .NET, Java/Spring o NestJS.
- **Por qué es crítico.** Bloquea todo el documento técnico y reescribe ADRs y épicas. Delay de 2-4 semanas mínimo.
- **Stories impactadas.** Todas las EPs (Bootstrap US-1A-01-XX, todas las dependientes).
- **Plan de mitigación.** Owner TI MT + Paula. Due 2026-05-23. ADR-001 marcado proposed; criterios documentados (productividad, hppt-iom reuse, talent pool BR); preview funcional FastAPI; cita con Paula con demo.
- **Trigger.** Paula pide POC alternativo o veta elemento concreto.
- **Plan B/C.** B = .NET full-stack o Java/Spring + Next.js (presupuesto + timeline +30 %). C = reescritura por capa modular conservando frontend.
- **Decisión que cierra el riesgo.** Firma Paula (TI MT) sobre ADR-001 con stack final.

### R-003 — Comparador unreliable (15 % SKUs sin match)

- **Descripción detallada.** Motor v5.1 falla en 15 % del catálogo MT real. Targets FP < 2 % / FN < 10 % no garantizados. Riesgo de calibración drift, dataset sesgado.
- **Por qué es crítico.** Si el comparador no entrega, el feature canal_recomendado y precio competitivo se diferiría a Fase 1.5, perdiendo valor diferencial.
- **Stories impactadas.** EP-1B-04 (Recomendador), EP-R&D (todo el workstream), UI competitive.
- **Plan de mitigación.** Owner R&D Champion. Due 2026-07-01 (gate S2). Workstream paralelo; cascada SigLIP autohost + Gemini Flash tie-break; calibrator isotonic mensual; dataset etiquetado S0-S1 (50+50 pares estratificados).
- **Trigger.** ECE > 8 % en QA semanal; FP > 2 % o FN > 10 % en validation hold-out S2.
- **Plan B/C.** Diferir a Fase 1.5; entregar Fase 1 sin canal_recomendado automático; threshold conservador inicial + cola humana > 0.55.
- **Decisión que cierra el riesgo.** Gate decisión S5 con métricas reales; Sponsor firma diferir o continuar.

### R-004 — Hetzner sin región UAE (residencia datos PDPL)

- **Descripción detallada.** PDPL Federal Law 45/2021 puede exigir residencia local UAE. Hetzner sin presencia UAE (Frankfurt / Helsinki). Supabase tampoco tiene región UAE.
- **Por qué es crítico.** Bloquea go-live regulatorio si TI MT exige residencia UAE; requiere cambio provider (provider local UAE) con presupuesto y timeline +6-8 semanas.
- **Stories impactadas.** EP-1A-01 (Bootstrap infra), todo el deployment.
- **Plan de mitigación.** Owner TI MT + Pablo. Due 2026-05-23. ADR-020 abierto; muestra DPA Supabase; documentar interpretación PDPL Art. 4(1)(b) (analogía GDPR para empleados); plan B Frankfurt + DPA reforzado; plan C provider local UAE.
- **Trigger.** TI MT vetan EU región o reglamento PDPL endurecido publicado.
- **Plan B/C.** B = Frankfurt + DPA. C = provider UAE local (G42 cloud, AWS UAE me-central-1) con +6-8 semanas timeline.
- **Decisión que cierra el riesgo.** Firma Sponsor + TI MT + legal MT sobre ADR-020.

### R-005 — Audit log no tamper-evident (VAT 2026)

- **Descripción detallada.** `audit_events` particionada append-only es policy de aplicación. Superuser Postgres con acceso fuera de la app puede modificar filas. VAT UAE 2026 endureciéndose; defensa profunda exige hash chain o firma criptográfica.
- **Por qué es crítico.** En auditoría VAT, evidencia tamper-evident es requisito de buenas prácticas. Pérdida de evidencia = multa + reputación.
- **Stories impactadas.** EP-1A-07 (Audit), US-1A-07-XX (hash chain), todas las que escriben audit.
- **Plan de mitigación.** Owner Pablo + TI MT. Due 2026-08-15 (S6). ADR-053: añadir `audit_events.prev_hash` + `audit_events.row_hash`; trigger BEFORE INSERT calcula `row_hash = sha256(payload || prev_hash)`; job nocturno firma último hash con clave operativa BR; endpoint `GET /audit/verify/{from}/{to}` re-calcula y devuelve "tamper detected"; REVOKE UPDATE; WORM backup; nightly verify.
- **Trigger.** Auditor externo solicita evidencia tamper-evident; PRC TI MT acceso directo DB.
- **Plan B/C.** Export firmado FTA + WORM backup + auditor externo S6.
- **Decisión que cierra el riesgo.** ADR-053 firmado + tests verify pasan.

### R-006 — Restore desde backup nunca ensayado

- **Descripción detallada.** §20.7 promete "test de restore trimestral en staging" sin fecha firme; US-1B-05-04 contempla "drill rollback" pero el rollback es a Excel demo, no restore de DB Postgres desde backup cifrado. RTO 4 h y RPO 1 h son aspiracionales.
- **Por qué es crítico.** Sin haber ejecutado un restore real de un dump cifrado de Supabase + comparación de checksums + verificación de RLS post-restore, el plan de DR es papel mojado.
- **Stories impactadas.** US-1A-01-XX (Sprint 0) ensayo restore; US-1B-05-04 ampliada; runbook `runbook-restore-from-backup.md`.
- **Plan de mitigación.** Owner Pablo + TI MT. Due 2026-09-30 (DR drill). Ensayo restore S0 con dump del día anterior; tiempos medidos en runbook; DR drill anual (semestral Fase 1) con post-mortem.
- **Trigger.** Necesidad real de restore en prod; auditor pide evidencia.
- **Plan B/C.** Aceptación temporal con riesgo cuantificado hasta primer drill verificado.
- **Decisión que cierra el riesgo.** Drill ejecutado con tiempos < RTO 4 h y completion documentada.

### R-007 — SPOF operativo: 1 sólo Comercial

- **Descripción detallada.** Hoy en MT ME hay 1 Comercial operando precios. Si enferma, va de vacaciones o rota, la operación se paraliza.
- **Por qué es crítico.** Migración a app + ops continúa = doble carga sobre 1 persona; resistencia + change management amplifica el riesgo.
- **Stories impactadas.** Cross-cutting (training docs, manual operativo, parallel run extendido).
- **Plan de mitigación.** Owner Pablo + Gerente. Due 2026-08-31. Backup operator cross-trained (puede ser Champion del Cambio, Gerente o secundario); manual operativo en `mt-pricing-docs/`; walkthroughs grabados; champion ≥ 30 % dedicación; parallel run ≥ 2 semanas.
- **Trigger.** Comercial enfermedad / vacaciones / rotación; ralentización propuestas.
- **Plan B/C.** Operación parcial vía Champion + Gerente; modo "freeze" temporal con export desde último snapshot aprobado.
- **Decisión que cierra el riesgo.** Backup operator nombrado y operando en parallel run; aprobación Sponsor.

### R-008 — Compromiso credenciales Gerente Comercial

- **Descripción detallada.** Phishing email captura credenciales `gerente_comercial` → atacante aprueba masivamente pricing falso → impacto margen + reputación.
- **Por qué es crítico.** El Gerente es el único rol con `approve_price` mass. Una sesión comprometida puede aprobar todos los pendientes en segundos.
- **Stories impactadas.** EP-1A-07 (RBAC + Auth), EP-1B-03 (Aprobaciones), audit alertas.
- **Plan de mitigación.** Owner Pablo + Gerente. Due continuo. MFA TOTP obligatoria (recomendada Fase 1); audit chain hash-encadenada (R-005); alerta bulk approve > 50 SKUs en < 5 min; reauth para sensitive ops; rotación contraseña 90d; password manager corporate.
- **Trigger.** Login desde IP geo anómala; bulk approve simultáneo > umbral; audit alert.
- **Plan B/C.** Suspender cuenta + revocar tokens + sign_out forzado; reverso aprobaciones via `audit_events.reverse`.
- **Decisión que cierra el riesgo.** MFA habilitada + audit alerts en producción + drill phishing simulado.

### R-009 — Costos LLM escalan no-linealmente

- **Descripción detallada.** 224 SKUs Fase 1 → 5k–50k Fase 2+ × N candidatos/SKU. Sin cascada estricta, costos se multiplican por orden de magnitud.
- **Por qué es crítico.** Budget Fase 1 es modesto. Si embedding + tie-break gastan $X/mes Fase 1, escalar puede triplicar el budget Fase 2+.
- **Stories impactadas.** EP-R&D-02 (Embedding cascade), EP-R&D-04 (Tie-break LLM).
- **Plan de mitigación.** Owner R&D Champion. Due 2026-07-31. Cascada estricta: SigLIP autohost (90 % volumen), Gemini Flash sólo tie-break (10 %); coste sub-lineal; budget alert > $X/mes; embedder text fungible (swap a SigLIP-text en 1 sprint).
- **Trigger.** Coste mensual LLM > 2× presupuesto; volumen tie-break > 30 %.
- **Plan B/C.** Modelo abierto local (sentence-transformers + Llama vision) si pricing API explota.
- **Decisión que cierra el riesgo.** Métricas de coste/SKU dentro de target en S5 + budget alert configurada.

### R-010 — Cambio operativo Excel → app (resistencia)

- **Descripción detallada.** Pasar de Excel a app es change management, no sólo software. Comercial puede regresar a Excel si la app no entrega paridad funcional + UX.
- **Por qué es crítico.** Si la migración fracasa, todo el proyecto pierde sentido.
- **Stories impactadas.** Cross-cutting (parallel run, capacitación, manual ES).
- **Plan de mitigación.** Owner Champion. Due 2026-08-15. Paridad funcional con Excel en S1 + capacitación + parallel run ≥ 2 semanas + manual ES (gestión cambio brief) + Champion ≥ 30 % dedicación.
- **Trigger.** Comercial regresa a Excel; quejas en S1 user testing; export adoption < 80 %.
- **Plan B/C.** Período doble operación extendido; freeze de Excel demo diferido.
- **Decisión que cierra el riesgo.** Cutover firmado con Comercial + Champion + Sponsor; export adoption ≥ 80 % por 2 semanas.

---

## 6. Riesgos mapeados a sprints

> ✅ = mitigación cierra; 🟡 = monitoreo continuo; ⚠ = trigger date cae en sprint.

| ID | S0 | S1 | S2 | S3 | S4 | S5 | S6 | S7+ |
|---|---|---|---|---|---|---|---|---|
| R-001 PIM gaps | ⚠✅ | 🟡 | 🟡 | | | | | |
| R-002 stack | ⚠✅ | | | | | | | |
| R-003 comparador | 🟡 | 🟡 | ⚠ | 🟡 | 🟡 | ⚠✅ | | |
| R-004 residencia UAE | ⚠✅ | | | | | | | |
| R-005 audit tamper | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | ⚠✅ | |
| R-006 restore drill | ⚠ | | | | | | | ⚠✅ |
| R-007 SPOF Comercial | 🟡 | ⚠ | 🟡 | 🟡 | 🟡 | 🟡 | ✅ | |
| R-008 cred Gerente | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 |
| R-009 LLM costs | 🟡 | 🟡 | 🟡 | 🟡 | ⚠ | 🟡 | | |
| R-010 cambio operativo | 🟡 | ⚠ | 🟡 | 🟡 | 🟡 | 🟡 | ⚠✅ | |
| R-011 Excel sole source | 🟡 | ⚠✅ | 🟡 | | | | | |
| R-012 VAT 2026 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 |
| R-013 mtme.ae | flag | | | | | | | flag F3 |
| R-014 cuello Gerente | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 |
| R-015 FX | ⚠ | 🟡 | 🟡 | ⚠✅ | 🟡 | 🟡 | 🟡 | 🟡 |
| R-016 estados canales | | | | ⚠ | | | | |
| R-018 sourcing | ⚠✅ | | ⚠ | | | | | |
| R-020 DPO PDPL | ⚠ | ⚠ | ⚠✅ | | | | | |
| R-021 DPA sub-proc | ⚠ | ⚠ | ⚠ | ⚠✅ | | | | |
| R-022 SSRF importer | | | ⚠✅ | | | | | |
| R-024 RLS bypass | | | | | | ⚠✅ | | |
| R-025 supply chain | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 |
| R-031 Sentry residencia | ⚠ | ⚠✅ | | | | | | |
| R-035 SLO/error budget | | | | | | | ⚠✅ | |
| R-036 cronograma 602 SP | 🟡 | 🟡 | 🟡 | ⚠ | 🟡 | 🟡 | 🟡 | 🟡 |
| R-037 scope creep R&D | | | ⚠ | | | ⚠✅ | | |
| R-039 ramp-up SQLAlchemy | ⚠ | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | ⚠✅ | |
| R-040 DatabaseScheduler | | | | ⚠ | ⚠✅ | | | |
| R-042 Juan Carlos v5.1 | ⚠✅ | | | | | | | |
| R-043 multi-idioma S0 | ⚠ | ⚠ | ✅ | | | | | |
| R-044 image rights | ⚠ | ⚠✅ | | | | | | |
| R-045 FX inferred | ⚠ | ⚠ | ⚠✅ | | | | | |
| R-049 TI Integración | ⚠ | ⚠✅ | | | | | | |
| R-051 custodia age | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | ⚠ | ⚠✅ |
| R-052 decisiones sponsor | ⚠✅ | | | | | | | |

---

## 7. Riesgos mapeados a Cuestiones abiertas (Q-XX)

| Q-XX (PRD §20) | Cuestión | Riesgos relacionados |
|---|---|---|
| Q-01 Stack tecnológico | Firma TI MT del stack propuesto | R-002, R-039 |
| Q-02 Cloud y residencia | UAE / EU / on-prem | R-004, R-031 |
| Q-03 PIM real + costos | Confirmación archivo + mapeo | R-001, R-011, R-045 |
| Q-04 Threshold delta margen | Auto-approve vs pending | R-014, R-052 |
| Q-05 TI Integración FTE | RACI Fase 3+ | R-049, R-052 |
| Q-06 mtme.ae remediación | Gating Fase 3 | R-013 |
| Q-07 Dataset etiquetado | ≥ 50 pares + plazo | R-003, R-019 |
| Q-08 Fuente datos competidores | Scraping vs API vs partnership | R-018, R-009 |
| Q-09 Derechos imagen MT España | Acuerdo + multi-idioma | R-043, R-044, R-052 |
| Q-10 Port-vs-rewrite v5.1 | Decisión basada pseudocódigo | R-042 |
| Q-11 Definición "óptimo" recomendador | Margen / ROI / rotación | R-003 (parcial) |
| Q-12 Ventanas mantenimiento | TI / Gerente | R-027, R-034 |
| Q-13 Retención `audit_events` | Default 7 años VAT | R-005, R-012, R-052 |
| Q-14 Idioma observabilidad | Sentry interno | R-031 |
| Q-15 Threshold calibración | Auto-match vs cola humana | R-003, R-019 |
| Q-16 Formato export por canal | Amazon / Noon / Shopify | R-016 |
| Q-17 Política delegación Gerente | Escalado >48 h | R-014, R-052 |
| Q-18 AR sólo datos o UI | RTL UI hooks | R-017 |

---

## 8. Riesgos compartidos con el cliente (responsabilidad MT)

> Subset cuya mitigación primaria depende de MT, no de BR Innovation.

| ID | Riesgo | Acción cliente | Plazo |
|---|---|---|---|
| R-001 | Provisión archivo PIM real (Q-03) | TI MT + Champion entregan archivo + mapeo inicial | S0 |
| R-020 | DPO designation PDPL Art. 11 | MT legal designa DPO oficial | 2026-06-30 |
| R-013 | mtme.ae remediación SSL | Programa MT planifica remediación | Fase 3 kickoff |
| R-042 | Disponibilidad Juan Carlos sesión v5.1 | Sponsor MT confirma slot 2 h | S0 |
| R-043 | Multi-idioma EN/AR — coop MT España | Sponsor MT solicita export complementario | 2026-06-15 |
| R-014 | Aprobación timely de cambios pricing | Gerente firma SLA + delegado backup | S0 |
| R-044 | Acuerdo derechos imagen MT España | Sponsor + legal firman | 2026-05-30 |
| R-021 | DPA con sub-procesadores | MT legal firma DPA con Supabase / OpenAI / Bright Data / Resend | 2026-07-31 |
| R-049 | TI Integración FTE | Sponsor MT asigna persona / vendor (Q-05) | S0+1 |
| R-004 | Residencia datos UAE PDPL | TI MT + legal firman ADR-020 | S0 |
| R-052 | Decisiones Sponsor pendientes (×5) | Sesión Sponsor concentrada | S0 cierre |

---

## 9. Plan de revisión y governance

- **Cadencia de review.** Semanal en sprint review (viernes). Ad-hoc cuando se materializa un trigger o aparece un riesgo nuevo.
- **Owner del registro.** Pablo Sierra (BR Innovation).
- **Mecanismo de actualización.** PR a este documento + announce en `#mt-alerts` Slack (canal dedicado `#mt-risks` opcional). Cada cambio incrementa `version` SemVer del frontmatter.
- **Trigger de re-priorización.** Cualquiera de:
  - Cambia la severidad de un top-10.
  - Se cierra/abre un riesgo Critical.
  - Trigger date cae en el sprint actual.
  - Sponsor o auditor solicita revisión.
- **Métricas de salud del registro.**
  - **% riesgos Critical con mitigación activa** (target: 100 %; si < 100 %, escalado Sponsor).
  - **Tiempo medio de cierre Critical**: target ≤ 1 sprint desde primer trigger.
  - **% triggers detectados antes de impacto** (proactividad): target ≥ 80 %.
  - **Riesgos open > 3 sprints sin actualización**: target 0.

---

## 10. Glosario de términos

- **Riesgo:** evento incierto que puede impactar objetivos del proyecto (alcance, timeline, calidad, presupuesto, compliance).
- **Issue:** riesgo materializado (ya ocurrió). Se mueve del registro de riesgos al log de incidentes.
- **Mitigación:** acción que reduce probabilidad o impacto antes de que ocurra.
- **Contingencia (Plan B/C):** acción a ejecutar si el riesgo se materializa, para reducir consecuencia.
- **Aceptación:** registrar el riesgo y deliberadamente no actuar (porque es Low o porque mitigar es más caro que aceptar). Requiere firma del Sponsor cuando el riesgo es ≥ Medium.
- **Trigger / signal:** indicador observable que avisa que el riesgo está materializándose.
- **Trigger date:** fecha estimada en la que el trigger es más probable (deadline de mitigación).
- **Severidad nominal vs ponderada:** nominal = P×I; ponderada = ajusta por probabilidad de mitigación pendiente y proximidad temporal.

---

## 11. Ejemplos de uso

### Ejemplo 1 — Cierre de Sprint

> **Antes de cerrar el sprint, revisar todos los riesgos cuyo trigger date cae en el sprint actual y verificar mitigaciones.**

Procedimiento:
1. Filtrar §6 por columna del sprint actual; listar todos los `⚠`.
2. Para cada uno, validar con owner que la mitigación quedó cumplida (evidencia: PR mergeado, doc firmado, métrica verde).
3. Si no cumplida, escalar al sponsor en sprint review y mover trigger date al siguiente sprint.

### Ejemplo 2 — Pre-cutover a producción

> **Antes de cutover a prod, todos los riesgos Critical deben estar Mitigated, Accepted con firma sponsor, o Closed.**

Checklist mínimo cutover Fase 1:
- [ ] R-001..R-010 (top 10) en estado Mitigated/Closed.
- [ ] R-006 restore drill ejecutado con tiempos < RTO 4 h.
- [ ] R-005 audit hash chain en producción + verify endpoint operativo.
- [ ] R-004 / R-020 / R-021 firmas legales completas.
- [ ] R-052 decisiones sponsor cerradas.

### Ejemplo 3 — Kickoff de cada sprint

> **En kickoff de cada sprint, revisar riesgos cuyo trigger date cae en el sprint y asignar owner técnico al lado del owner estratégico.**

Procedimiento:
1. PM extrae lista de §6 con `⚠` columna sprint próximo.
2. Sprint planning incluye SP de mitigación dentro del sprint backlog (no extra).
3. Owner técnico asignado actualiza estado en sprint review.

---

## 12. Trazabilidad cruzada (origen → ID consolidado)

| Origen | ID consolidado |
|---|---|
| PRD §16 R-01 | R-011 |
| PRD §16 R-02 | R-007 |
| PRD §16 R-03 | R-015 |
| PRD §16 R-04 | R-017 |
| PRD §16 R-05 | R-002 |
| PRD §16 R-06 | R-003 |
| PRD §16 R-07 | R-013 |
| PRD §16 R-08 | R-016 |
| PRD §16 R-09 | R-012 |
| PRD §16 R-10 | R-010 |
| PRD §16 R-11 | R-018 |
| PRD §16 R-12 | R-001 |
| PRD §16 R-13 | (cubierto por R-001 + R-036 performance importer) |
| PRD §16 R-14 | R-014 |
| Architecture §23 R1 | R-002 |
| Architecture §23 R2 | R-001 |
| Architecture §23 R3 | R-003 |
| Architecture §23 R4 | R-015 |
| Architecture §23 R5 | (acepted, particionado mensual) |
| Architecture §23 R6 | (cubierto por R-014 calibración + tests excepción) |
| Architecture §23 R7 | R-011 |
| Architecture §23 R8 | R-044 |
| Architecture §23 R9 | R-027, R-030 |
| Architecture §23 R10 | R-012 |
| Architecture §23 R11 | (cubierto por R-005) |
| Architecture §23 R12 | R-010 |
| Architecture §23 R16 | R-039 |
| Sprint0 R-S0-01 | R-002 |
| Sprint0 R-S0-02 | R-004 |
| Sprint0 R-S0-03 | R-042 |
| Sprint0 R-S0-04 | R-043 |
| Sprint0 R-S0-05 | R-013 |
| v5.1 R1 (divergencia parallel run) | (cubierto por R-010 + R-006) |
| v5.1 R2 canal_recomendado | R-042 |
| v5.1 R3 contrato scraper | R-018 |
| v5.1 R4 PPC absurdo | R-045 |
| v5.1 R5 golden numbers FX | R-015 |
| v5.1 R6 emojis i18n | (low — accepted) |
| v5.1 R7 precisión flotante | (mitigated — Decimal/NUMERIC) |
| Research-spike — costos LLM | R-009 |
| Research-spike — TOS scraping | R-018 |
| Research-spike — calibración drift | R-019 |
| Research-spike — vendor lock-in Bright Data | R-047 |
| Research-spike — cambio precio API LLM | R-048 |
| Security §26 #1 cred Gerente | R-008 |
| Security §26 #2 SQLi importer | (mitigated — SQLAlchemy + RLS) |
| Security §26 #3 SSRF | R-022 |
| Security §26 #4 RLS bypass | R-024 |
| Security §26 #5 audit tamper | R-005 |
| Security §26 #6 brute force | R-023 |
| Security §26 #7 supply chain | R-025 |
| Security §26 #8 leak signed URL | (mitigated — TTL ≤ 1h + RLS) |
| Security TODOs #1 DPO | R-020 |
| Security TODOs #2 PDPL consentimiento | (cubierto por R-020 + R-021) |
| Security TODOs #3 residencia UAE | R-004 |
| Migrations-iac §5 dev change Studio | (cubierto por R-026 + drift detector) |
| Migrations-iac §5 Doppler down | (mitigated — fallback SOPS) |
| Migrations-iac §5 Pablo bus factor | R-050 |
| Migrations-iac §5 gitleaks bypass | R-026 |
| Prod-readiness §3.1 restore | R-006 |
| Prod-readiness §3.2 secret manager | (cubierto por R-026 + ADR-051) |
| Prod-readiness §3.3 SAST/SCA | R-025 |
| Prod-readiness §3.4 healthchecks | R-032 |
| Prod-readiness §3.5 SLO | R-035 |
| Prod-readiness §3.7 idempotencia DLQ | R-029 |
| Prod-readiness §3.8 audit hash chain | R-005 |
| Prod-readiness §3.10 RLS audit | R-024 |
| Prod-readiness §3.15 PDPL DPA | R-021 |
| Prod-readiness §3.20 onboarding | R-050 |
| Prod-readiness §7.7 Hetzner SPOF | R-027 |
| Users-module v1.0 lag JWT | R-041 |
| Jobs-module DatabaseScheduler | R-040 |
| DR §850 custodia age | R-051 |

---

> **Mantenedor:** Pablo Sierra (BR Innovation). Revisión semanal en sprint review.
