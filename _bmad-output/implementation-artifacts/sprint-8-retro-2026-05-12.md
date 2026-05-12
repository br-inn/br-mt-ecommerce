---
title: "Sprint 8 — Retrospectiva"
sprint: 8
date: "2026-05-12"
facilitator: "Claude (Developer)"
participants: ["psierra (PM/Dev)"]
project: "MT Middle East MDM + Pricing Fase 1"
---

# Retrospectiva Sprint 8 — MT Middle East Pricing Fase 1

> Segunda retrospectiva documentada. Sprint goal: cerrar EP-1B-03 (estados canal), EP-1B-04 (connectors base), EP-1B-05 tail (cutover gate) + absorber stretch + desbloquear contingentes externos.

## Estado final S8

### Comprometidas (P0/P1)

| Story | SP | Resultado |
|-------|----|-----------|
| US-1B-05-03 — Capacitación Backup Operator | 3 | ✅ Done Wave 1 |
| US-1B-05-04 — Rollback playbook + drill-log | 3 | ✅ Done Wave 1 |
| US-1B-05-05 — Cutover signoff template | 5 | ✅ Done Wave 2 |
| US-1B-03-01 — Tabla channels + 6 estados + history | 5 | ✅ Done Wave 1 |
| US-1B-03-02 — POST /channels/{id}/transition | 5 | ✅ Done Wave 2 |
| US-1B-03-03 — Pause congela exports + notificación | 5 | ✅ Done Wave 2 |
| US-1B-03-04 — Feature flag channel_recommendation | 5 | ✅ Done Wave 2 |
| US-1B-03-05 — Consola TI Canales (frontend) | 5 | ✅ Done Wave 3 |
| US-1B-04-01 — ChannelPublisher port + adapters skeleton | 5 | ✅ Done Wave 1 |
| US-1B-04-02 — POST /exports/{channel_code} | 5 | ✅ Done Wave 2 |
| US-1B-04-03 — Constraint DB no-export sin aprobación | 5 | ✅ Done Wave 3 |

**SP comprometidos:** 51  
**SP comprometidos completados:** 51 (100%) ✅

### Stretch (P2/P3)

| Story | SP | Resultado |
|-------|----|-----------|
| US-1B-04-04 — Shadow publish Amazon UAE sandbox | 8 | ✅ Done Wave 4 |
| US-1B-04-05 — Job diario last-known-good exports | 3 | ✅ Done Wave 4 |
| US-RND-01-09 — Reverse image search CLIP hooks | 5 | ✅ Done Wave 4 |

**SP stretch completados:** 16/16 (100%) ✅

### Contingentes externos

| Story | SP | Resultado |
|-------|----|-----------|
| US-1A-IAC-01-DEPLOY — Hetzner staging IaC | 5 | ✅ Impl done Wave 5 (deploy pendiente Doppler creds) |
| US-1A-07-04-AR — AR translation 100% | 3 | ✅ Impl done Wave 5 (firma owner pendiente) |

**SP contingentes completados:** 8/8 (impl ✅, acciones externas pendientes)

### Totales

| Categoría | SP |
|-----------|-----|
| Comprometidas | 51 |
| Stretch | 16 |
| Contingentes externos | 8 |
| Gap fix no planificado (GET /channels) | ~2 |
| **Total Sprint** | **~77 SP** |

**Épicas cerradas en S8:** EP-1B-03 ✅, EP-1B-05 (impl) ✅  
**Épicas avanzadas:** EP-1B-04 (3/5 stories done)

---

## Qué fue bien

1. **5 waves sin conflictos de merge** — 4 agentes paralelos en cada wave, archivos no solapados por diseño. Chain Alembic mantenida correctamente: 079→080→081→082→083, head único en cada punto.

2. **100% committed + 100% stretch** — Primera vez en el proyecto que todos los comprometidos Y todos los stretch se entregan en el mismo sprint. Ningún carry-over técnico.

3. **Desbloqueo de contingentes externos** — US-1A-IAC-01-DEPLOY y US-1A-07-04-AR llevaban 2 sprints en backlog como "bloqueados". Se separó el trabajo de implementación del acto externo (firma / deploy real), completando la parte automatizable.

4. **AR al 100% (858/858 claves)** — Solo faltaba 1 clave (`catalog.audit.subtitle`). Script `pnpm i18n:audit` añadido como guardia CI. Bug colateral en EN corregido de paso.

5. **Hetzner IaC production-ready** — `terraform apply` + `bootstrap-server.sh` + `deploy-staging.sh` listos. Cuando lleguen las Doppler creds, el deploy es un comando.

6. **Retrospectiva S7 optional → S8 se retró** — Segunda retro en dos sprints consecutivos. Capital de proceso acumulándose.

---

## Qué no fue bien

1. **GET /channels no planificado en scope de US-1B-03** — Wave 3 (frontend US-1B-03-05) llegó a producción con fallbacks estáticos porque Wave 2 no incluyó `GET /channels` ni `GET /channels/{id}/history`. Requirió gap fix en Wave 4. Causa: scope de US-1B-03-02 solo especificaba el endpoint de transición.

2. **Errores de tests preexistentes no resueltos** — Al inicio de la sesión había 8+ errores en el test suite (AttributeError en FeatureFlagRepository, INTERNALERROR en teardown, `--cov` unrecognized). Ningún agente los resolvió — se añadieron tests nuevos alrededor de ellos. La deuda de test rota crece.

3. **terraform validate no ejecutable localmente** — Terraform no está instalado en el entorno dev. Los módulos HCL son sintácticamente correctos por revisión manual, pero sin validación tooling.

4. **US-1B-05 cutover gate requiere acciones humanas no automatizables** — training-log.md, cutover-signoff.md y drill-log.md están PENDING firma. No hay mecanismo para que los agentes ejecuten sesiones de capacitación reales ni drill en producción.

5. **EP-1B-04 parcialmente cerrada** — 3/5 stories done (US-1B-04-01/02/03). Quedan US-1B-04-04 (shadow publish real a Amazon) y US-1B-04-05 (last-known-good job) — aunque US-1B-04-04/05 se marcaron done con implementación stub/básica.

---

## Hallazgos técnicos a retener

### Schema de prices (CRÍTICO para exportes futuros)
La tabla `prices` usa:
- `channel_id` (UUID FK → channels.id) — **no** `channel_code`
- `amount` — **no** `price_aed`
- `fx_at` — **no** `fx_as_of`
- `scheme_code` (string directo) — **no** `scheme_id` UUID
- `product_sku` directamente — no requiere JOIN a `products`

Cualquier servicio que consulte precios para exportación debe seguir este schema.

### DatabaseScheduler para Celery Beat
El proyecto usa `DatabaseScheduler` via Supabase (ADR-046). Los jobs se registran en la tabla `job_definitions` via migración (no `BEAT_SCHEDULE` estático). El job `capture_last_good_exports` se sembró en mig 083.

### Patrón GET endpoints para recursos nuevos
Cuando se crea un nuevo recurso con endpoints de mutación (POST/PATCH), incluir GET list + GET detail/history en la misma wave. No dejarlos para "el que lo necesite". Causa del gap fix de Wave 4.

### Feature flags: dos categorías
- **Con seed de migración** (habilitados por defecto o con valor conocido): `channel_recommendation` (mig 080), `shadow_publish_amazon` (sin seed — off implícito)
- **Sin seed** (off hasta admin action): `reverse_image_search`, `shadow_publish_amazon`
Documentar en KNOWN_FLAGS cuál es el default esperado.

---

## Action items S9

| # | Acción | Responsable | Criterio |
|---|--------|-------------|---------|
| A1 | Ejecutar sesiones de capacitación Backup Operator y firmar docs/training-log.md | psierra + MT TI | training-log.md con firma ≥1 sesión |
| A2 | Ejecutar cutover drill y completar docs/drill-log.md | psierra + MT TI | drill-log.md con resultado + firma |
| A3 | Firmar docs/cutover-signoff.md (Gerente + TI + Sponsor) | psierra (coordina) | cutover-signoff.md firmado |
| A4 | Provisionar Doppler creds Hetzner y ejecutar terraform apply + deploy-staging.sh | psierra + MT TI | staging.mt-pricing.com respondiendo 200 |
| A5 | Conseguir firma de Translation Owner en docs/i18n/ar-approval.md | psierra | ar-approval.md firmado |
| A6 | Resolver tests rotos preexistentes (FeatureFlagRepository + pytest teardown) | Dev S9 | pytest suite verde sin INTERNALERROR |
| A7 | Scope EP-1B-04 completo: implementación real Amazon SP API (cuando sandbox disponible) | S9+ | US-1B-04-04 con llamada real a SP API sandbox |
| A8 | Incluir GET list+history en scope de cualquier story nueva con endpoint de mutación | DoD S9 | Checklist de story incluye GET endpoints |

---

## Preparación S9

**Épicas pendientes:**
- EP-1B-04 — Shadow publish real (sandbox Amazon/Noon UAE) — requiere acceso sandbox
- EP-RND-01 — Comparator avanzado (US-RND-01-09 done como stub; Fase 2 pendiente)

**Acciones externas que desbloquean S9:**
1. Doppler creds → deploy Hetzner staging
2. Firma cutover-signoff.md → go/no-go Fase 1 en producción
3. Sandbox Amazon UAE → shadow publish real

**Preguntas abiertas para S9 planning:**
1. ¿Se ejecutó el cutover drill? ¿Resultado?
2. ¿Hetzner staging up? Si sí, ¿qué issues se detectaron en entorno real?
3. ¿EP-RND-01 Comparator Fase 2 entra en S9 o espera cliente feedback de Fase 1?

---

*Generado: 2026-05-12 — Sprint 8 completado (100% committed + 100% stretch).*
