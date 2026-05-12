---
title: "Sprint 8 — Backlog refinado — MT Middle East Canales + Connectors + Cutover gate"
sprint: 8
date: "2026-05-12"
status: "ready"
project: "MT Middle East MDM + Pricing Fase 1"
sprint_goal: "Cerrar gate de cutover Fase 1b + arrancar épicas de canales y connectors (EP-1B-03 completa + EP-1B-04 core)"
---

# Sprint 8 — Backlog refinado

## 1. Estado al inicio del S8

### Épicas cerradas al finalizar S7

| Épica | Estado | Nota |
|-------|--------|------|
| EP-1A-01 — Setup técnico | ✅ done | |
| EP-1A-02 — PIM | ✅ done | EAV/taxonomy bonus entregado |
| EP-1A-03 — Master proveedores | ✅ done | |
| EP-1A-04 — Master costes | ✅ done | |
| EP-1A-05 — FX versionado | ✅ done | |
| EP-1A-06 — Importers + datasheets | ✅ done | pdfplumber S6 ✅ |
| EP-1A-07 — RBAC + i18n (ES/EN) | ✅ done | AR deferred externo |
| EP-1A-08 — Scheduler + UI Jobs | ✅ done | |
| EP-1B-01 — Motor pricing multi-canal | ✅ done | bulk-recalc S5 ✅ |
| **EP-1B-02 — Workflow aprobación** | **✅ done S7** | Todas 9 stories done (S4-S7) |

### Épicas en vuelo al inicio de S8

| Épica | Estado | SP restante |
|-------|--------|-------------|
| EP-1B-05 — Hardening + cutover | in-progress | 11 SP (03/04/05) |
| EP-RND-01 — Comparator R&D | in-progress | 5 SP (US-RND-01-09) |
| **EP-1B-03 — Estados canal** | **backlog → S8** | 24 SP |
| **EP-1B-04 — Connectors + shadow** | **backlog → S8** | 29 SP |

### Velocity de referencia

| Sprint | SP comprometidos | SP entregados | SP stretch |
|--------|-----------------|---------------|------------|
| S5 | ~53 | ~53 | — |
| S6 | 23 | 13 core (+10 carry-over S7) | +46 bonus |
| S7 | 43 | 43 committed + 21 stretch | 64 total |
| **S8 target** | **~53** | — | **~16** |

---

## 2. Tabla maestra de stories S8

| ID | Título | Épica | SP | Prioridad | Dominio | Depende de |
|----|--------|-------|----|-----------|---------|------------|
| US-1B-05-03 | Capacitación Backup Operator (≥ 2 sesiones hands-on) | EP-1B-05 | 3 | P0 | ops/docs | US-1B-05-02 ✅ |
| US-1B-05-04 | Rollback playbook + Excel restorable 90 días | EP-1B-05 | 5 | P0 | ops/docs | US-1B-05-02 ✅ |
| US-1B-05-05 | Cutover gate firmado por Gerente + TI + Sponsor | EP-1B-05 | 3 | P0 | ops/docs | US-1B-05-03/04 |
| US-1B-03-01 | Tabla `channels` con 6 estados + `channel_state_history` | EP-1B-03 | 3 | P1 | backend | — |
| US-1B-03-02 | Endpoint `POST /channels/{id}/transition` + validación prerequisitos | EP-1B-03 | 8 | P1 | backend | US-1B-03-01 |
| US-1B-03-03 | Pause de canal congela exports activos | EP-1B-03 | 5 | P1 | backend | US-1B-03-02 |
| US-1B-03-04 | Feature flag `channel_recommendation` (default off) | EP-1B-03 | 3 | P1 | backend | US-1B-03-01 |
| US-1B-03-05 | Consola TI "Canales" tabla + transiciones + histórico | EP-1B-03 | 5 | P1 | frontend | US-1B-03-02/03 |
| US-1B-04-01 | Puerto `ChannelPublisher` + adapters skeleton (Amazon/Noon/Shopify) | EP-1B-04 | 5 | P1 | backend | US-1B-03-01 |
| US-1B-04-02 | Endpoint `POST /exports/{channel_code}` con filter runtime regla dura | EP-1B-04 | 8 | P1 | backend | US-1B-04-01, US-1B-02-04 ✅ |
| US-1B-04-03 | Constraint DB enforce regla dura no-export sin aprobación | EP-1B-04 | 5 | P1 | backend | US-1B-04-02 |
| **Total comprometido** | | | **53** | | | |
| US-1B-04-04 | Shadow publish sandbox Amazon UAE + captura errores | EP-1B-04 | 8 | P2/stretch | backend | US-1B-04-01/02 |
| US-1B-04-05 | Job diario `last-known-good` regenera + archiva exports | EP-1B-04 | 3 | P2/stretch | backend | US-1B-04-02 |
| US-RND-01-09 | Reverse image search hooks (CLIP, feature flag off) | EP-RND-01 | 5 | P3/stretch | R&D | pgvector ✅ |
| **Total stretch** | | | **16** | | | |
| **Total máximo** | | | **69** | | | |

### Stories contingentes externo

| ID | Título | SP | Condición de entrada |
|----|--------|----|----------------------|
| US-1A-IAC-01-DEPLOY | Hetzner staging deploy (Docker Compose + Caddy) | 5 | Doppler creds disponibles (A2 retro S6) |
| US-1A-07-04-AR | AR translation completion | 3 | Translation owner firma |

---

## 3. Fichas detalladas

### US-1B-05-03 — Capacitación Backup Operator

**Épica**: EP-1B-05
**Como** Sponsor / Champion
**Quiero** que el Backup Operator complete ≥ 2 sesiones hands-on + 1 import + 1 aprobación supervisada
**Para** mitigar single-point-of-failure (R-02).

**Criterios de aceptación**
- ≥ 2 sesiones grabadas y listadas en `docs/training-log.md`
- Backup Operator ejecuta 1 import + 1 aprobación sin errores y firma el log
- El backup operator queda listado como `ready` en el checklist de cutover

**Archivos esperados**
- `docs/training-log.md` (nuevo o actualizado)

**SP**: 3 | **Agente sugerido**: E (ops/docs) | **Bloquea**: US-1B-05-05

---

### US-1B-05-04 — Rollback playbook + Excel restorable 90 días

**Épica**: EP-1B-05
**Como** TI Integración
**Quiero** un playbook de rollback documentado y verificado con un drill
**Para** estar preparado ante fallo post-cutover.

**Criterios de aceptación**
- `docs/runbook-cutover.md` detalla pasos de rollback a Excel demo + restore DB desde backup
- Drill de rollback ejecutado y registrado en `docs/drill-log.md`, completado < 4 h (NFR-16)
- Excel `stock_dubai_v23` accesible (read-only) 90 días post-cutover

**Archivos esperados**
- `docs/runbook-cutover.md` (sección rollback)
- `docs/drill-log.md`

**SP**: 5 | **Agente sugerido**: E | **Bloquea**: US-1B-05-05

---

### US-1B-05-05 — Cutover gate firmado

**Épica**: EP-1B-05
**Como** Sponsor MT
**Quiero** firmar formalmente el cutover gate basado en checklist
**Para** que el go-live sea formal y trazable.

**Criterios de aceptación**
- Checklist 100 %: migración, 0 diff ≥5 días, audit ≥50 eventos, backup operator ready, manual aprobado
- `docs/cutover-signoff.md` firmado por Gerente + TI + Sponsor con fecha
- Excel `stock_dubai_v23` queda como `_ARCHIVE_YYYY-MM-DD` read-only

**Archivos esperados**
- `docs/cutover-signoff.md`

**SP**: 3 | **Agente sugerido**: E | **Depende de**: US-1B-05-03, US-1B-05-04

---

### US-1B-03-01 — Tabla `channels` con 6 estados

**Épica**: EP-1B-03
**Como** dev backend
**Quiero** la migration con `channels` (CHECK constraint en `state`) y `channel_state_history`
**Para** soportar transiciones gobernadas.

**Criterios de aceptación**
- CHECK constraint rechaza estados inválidos
- Canales seeded: `AMAZON_UAE`, `NOON_UAE`, `B2C_DIRECT`, `B2B_DIRECT` con `state='inactive'`
- Transición registra `from_state, to_state, actor, comment` en `channel_state_history`

**Archivos esperados**
- Migration `07x_channels_estados.py`
- `mt-pricing-backend/app/models/channels.py`
- Seed en alembic data migration

**SP**: 3 | **Agente sugerido**: A | **Notas**: PRD §10.1, FR-1b-06

---

### US-1B-03-02 — Endpoint `POST /channels/{id}/transition`

**Épica**: EP-1B-03
**Como** TI Integración
**Quiero** transicionar canal con validación de prerequisitos
**Para** evitar pilotos con datos a medias.

**Criterios de aceptación**
- Transición `pre_launch → pilot` valida SKUs subset con precios `approved`/`auto_approved`
- Override posible con `pilot_with_warnings=true` en `channel_state_history`
- RBAC: sólo rol `ti` puede transicionar (BR-1b-08)
- Sólo TI puede hacer transición, 403 para Comercial

**Archivos esperados**
- `mt-pricing-backend/app/api/routes/channels.py`
- `mt-pricing-backend/app/services/channels/transition_service.py`
- Tests (3 escenarios)

**SP**: 8 | **Agente sugerido**: A | **Depende de**: US-1B-03-01

---

### US-1B-03-03 — Pause de canal congela exports

**Épica**: EP-1B-03
**Como** TI Integración
**Quiero** que `paused` bloquee exports sin tocar precios aprobados
**Para** poder despausar sin re-aprobar.

**Criterios de aceptación**
- Pasar a `paused` bloquea exports activos y emite alerta a Comercial + Gerente
- Retornar a `live` rehabilita exports, precios aprobados intactos
- Canal `deprecated` rechaza nuevas propuestas de precio (BR-1b-10)

**Archivos esperados**
- Extensión de `transition_service.py`
- Tests (3 escenarios)

**SP**: 5 | **Agente sugerido**: A | **Depende de**: US-1B-03-02

---

### US-1B-03-04 — Feature flag `channel_recommendation`

**Épica**: EP-1B-03
**Como** TI Integración
**Quiero** feature flag global para `canal_recomendado` (default off Fase 1)
**Para** activarlo en Fase 3 sin refactor.

**Criterios de aceptación**
- Flag `off`: respuesta SKU sin `canal_recomendado`
- Flag `on` + 2 canales `live`: retorna `canal_recomendado` con justificación
- `PATCH /feature-flags/channel_recommendation` sólo rol `ti`, registra `audit_events`

**Archivos esperados**
- `mt-pricing-backend/app/api/routes/feature_flags.py` (o extensión)
- Tests (2 escenarios)

**SP**: 3 | **Agente sugerido**: A | **Depende de**: US-1B-03-01

---

### US-1B-03-05 — Consola TI "Canales"

**Épica**: EP-1B-03
**Como** TI Integración
**Quiero** pantalla con tabla de canales, estados, transiciones e histórico
**Para** operar sin APIs.

**Criterios de aceptación**
- Tabla muestra todos los canales con estado, `schemes_supported`, último cambio
- "Transicionar": modal con destino válido + comentario obligatorio + preview de SKUs faltantes
- "Histórico": línea de tiempo con actores y comentarios

**Archivos esperados**
- `mt-pricing-frontend/app/(app)/admin/channels/page.tsx`
- `mt-pricing-frontend/app/(app)/admin/channels/_client.tsx`
- `mt-pricing-frontend/components/domain/channels/channel-table.tsx`

**SP**: 5 | **Agente sugerido**: D | **Depende de**: US-1B-03-02/03

---

### US-1B-04-01 — Puerto `ChannelPublisher` + adapters skeleton

**Épica**: EP-1B-04
**Como** dev backend
**Quiero** interfaz `ChannelPublisher` + 3 adapters skeleton
**Para** swap de adapters sin refactor.

**Criterios de aceptación**
- Interfaz con métodos abstractos: `validate_payload`, `shadow_publish`, `export_csv`
- 3 adapters: `AmazonUAEAdapter`, `NoonUAEAdapter`, `ShopifyAdapter`
- Tests: cada adapter responde a `validate_payload({sku, price, ...})` con estructura conocida

**Archivos esperados**
- `mt-pricing-backend/app/services/channels/publisher.py` (interfaz)
- `mt-pricing-backend/app/services/channels/adapters/amazon_uae.py`
- `mt-pricing-backend/app/services/channels/adapters/noon_uae.py`
- `mt-pricing-backend/app/services/channels/adapters/shopify.py`

**SP**: 5 | **Agente sugerido**: B | **Depende de**: US-1B-03-01

---

### US-1B-04-02 — Endpoint `POST /exports/{channel_code}`

**Épica**: EP-1B-04
**Como** TI / Comercial
**Quiero** generar export CSV/XLSX por canal/esquema con filter runtime de la regla dura
**Para** cumplir BR-1b-01.

**Criterios de aceptación**
- Export incluye sólo `approved`/`auto_approved`; pendientes en reporte "bloqueado"
- FX as-of estampado en cada fila
- Export archivado automáticamente como `last-known-good`
- Auditoría post-export: 0 filas con estado inválido

**Archivos esperados**
- `mt-pricing-backend/app/api/routes/exports.py`
- `mt-pricing-backend/app/services/channels/export_service.py`
- Migration `exports_manifest` table
- Tests (2 escenarios mínimo)

**SP**: 8 | **Agente sugerido**: B | **Depende de**: US-1B-04-01, US-1B-02-04 ✅

---

### US-1B-04-03 — Constraint DB regla dura no-export

**Épica**: EP-1B-04
**Como** dev backend
**Quiero** función DB + constraint que impida exportar sin aprobación
**Para** defense in depth (DB + runtime).

**Criterios de aceptación**
- Función `export_for_channel(channel_id, scheme_id)` retorna sólo `approved`/`auto_approved`
- INSERT directo con precio no aprobado en `exports_manifest` rechazado por FK + CHECK
- Auditoría 1000 exports históricos: 0 registros con estado inválido

**Archivos esperados**
- Migration con función DB + constraint
- Tests (2 escenarios)

**SP**: 5 | **Agente sugerido**: B | **Depende de**: US-1B-04-02

---

### US-1B-04-04 — Shadow publish sandbox Amazon UAE (stretch)

**Épica**: EP-1B-04
**SP**: 8 | **Agente sugerido**: B | **Depende de**: US-1B-04-01/02

Envía export a sandbox Amazon UAE Seller Central, captura respuesta + errores estructurados en `shadow_publish_runs`. Detalla campo/fila/código en fallos de formato.

---

### US-1B-04-05 — Job diario `last-known-good` (stretch)

**Épica**: EP-1B-04
**SP**: 3 | **Agente sugerido**: B | **Depende de**: US-1B-04-02

Job 23:00 UAE regenera export por canal en estado `live`/`pilot`, archiva en `exports/last-known-good/{channel}/{YYYY-MM-DD}/`, purga > 90 días.

---

### US-RND-01-09 — Reverse image search hooks (stretch P3)

**Épica**: EP-RND-01
**SP**: 5 | **Agente sugerido**: C | **Depende de**: pgvector ✅

Adapter de reverse image search (TinEye/Google Lens via SerpAPI) invocado si `calibrated_confidence < 0.50` y `feature.reverse_image_search_enabled = true` (default off). Persiste en `competitor_listings.reverse_image_hits` (JSONB).

---

## 4. Orden de ejecución sugerido

```
Wave 1 (paralelo — sin dependencias cruzadas):
  Agente A: US-1B-03-01 (3 SP) → US-1B-03-02 (8 SP) → US-1B-03-03 (5 SP) → US-1B-03-04 (3 SP)
  Agente B: US-1B-04-01 (5 SP) [puede arrancar tras US-1B-03-01]
  Agente E: US-1B-05-03 (3 SP) + US-1B-05-04 (5 SP) [paralelo con Wave 1]

Wave 2 (tras Wave 1):
  Agente A: US-1B-03-05 frontend (5 SP)
  Agente B: US-1B-04-02 (8 SP) → US-1B-04-03 (5 SP)
  Agente E: US-1B-05-05 cutover gate (3 SP) [tras 03+04]

Wave 3 — stretch:
  Agente B: US-1B-04-04 (8 SP) + US-1B-04-05 (3 SP)
  Agente C: US-RND-01-09 (5 SP)
```

**Nota alembic multi-agent**: cualquier story con migración aplica protocolo DoD: si hay otra migración en vuelo, crear merge migration antes de `alembic upgrade head`.

---

## 5. Riesgos S8

| ID | Riesgo | Probabilidad | Mitigación |
|----|--------|-------------|------------|
| R-S8-01 | Cutover gate (US-1B-05-05) requiere firma de Sponsor/Gerente/TI — coordinación externa | alta | Iniciar scheduling de sesión día 1 del sprint |
| R-S8-02 | US-1B-03-02 (8 SP transition) más complejo que estimado si lógica de prerequisitos es ambigua | media | Limitar a 3 tipos de validación en ACs; resto → S9 |
| R-S8-03 | Doppler creds Hetzner sin desbloquear → US-1A-IAC-01-DEPLOY sigue bloqueado | alta | No incluido en committed; solo si A2 retro S6 se resuelve |
| R-S8-04 | Alembic multi-head en Wave 1 si A y B crean migraciones simultáneas | media | Agente B espera confirmación de migration de US-1B-03-01 antes de crear la suya |
| R-S8-05 | EP-1B-04 shadow publish depende de sandbox Amazon UAE Seller Central (externo) | media | US-1B-04-04 es stretch; no bloquea committed |

---

## 6. Próximos pasos

1. **S8 kick-off**: confirmar acción A2 (Doppler creds Hetzner) con MT antes de arrancar
2. **Sesión cutover gate**: psierra coordina con Gerente + TI + Sponsor para firmar US-1B-05-05
3. **Paralelo Wave 1**: Agente A (canales backend) + Agente E (cutover docs) día 1
4. **AR translation**: si owner firma en S8, agregar US-1A-07-04-AR como P1 a mid-sprint

---

## 7. Apéndice — Épicas completadas al cierre de S7

EP-1B-02 — Workflow aprobación por excepción (CERRADA S7):
- US-1B-02-01: done S4 (state machine)
- US-1B-02-02: done S7 (exception_rules CRUD + UI)
- US-1B-02-03: done S4 (auto_approved logic)
- US-1B-02-04: done S4 (approve/reject endpoints)
- US-1B-02-05: done S4 (bulk-approve)
- US-1B-02-06: done S7 (Cola Gerente UI — Pantalla 12 firmada 2026-05-12)
- US-1B-02-07: done S7 (Digest diario)
- US-1B-02-08: done S6 (Escalation job)
- US-1B-02-09: done S7 (Audit trail extendido)
