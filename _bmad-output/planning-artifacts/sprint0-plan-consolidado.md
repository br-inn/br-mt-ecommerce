---
title: "Sprint 0 — Plan Consolidado (MT Middle East MDM + Pricing Fase 1)"
status: "draft"
version: "1.1"
created: "2026-05-06"
updated: "2026-05-06"
project_name: "mt-pricing-mdm-phase1"
sprint: "S0 (1 semana)"
gating: "Aprobación Sponsor MT + TI MT antes de arrancar Fase 1a"
changelog:
  - "1.0 (2026-05-06): versión inicial."
  - "1.1 (2026-05-06): integra ADR-045 (persistencia híbrida SQLAlchemy + supabase-py) y ADR-046 (DatabaseScheduler editable). G1 marcado como decisión preliminar tomada; espera firma TI MT. Añade entregable S0-D11b (validación SQLAlchemy 2.0 async + DatabaseScheduler con TI MT) como sub-task de D10."
---

# Sprint 0 — Plan Consolidado

## 1. Objetivo

Cerrar las **3 decisiones gating** que habilitan el arranque de Fase 1a, sin las cuales el desarrollo se detiene:

1. **Stack tecnológico firmado por TI MT** (propuesta: Next.js 16 + FastAPI + Supabase + Celery + Hetzner + Caddy alineado con `hppt-iom`).
2. **Motor v5.1 — decisión port-vs-rewrite** con evidencia (pseudocódigo + golden numbers + sesión Juan Carlos).
3. **Importer del PIM completo.xlsx — diseño aprobado** con mapping de 36 columnas + plan para los 3 gaps críticos.

## 2. Entregables Sprint 0

| ID | Entregable | Estado | Responsable | Documento |
|----|------------|--------|-------------|-----------|
| **S0-D01** | Brief ejecutivo Fase 1 | ✅ Listo | Pablo Sierra | [product-brief-mt-pricing-mdm-phase1.md](product-brief-mt-pricing-mdm-phase1.md) |
| **S0-D02** | Detail pack (distillate) | ✅ Listo | Pablo Sierra | [product-brief-mt-pricing-mdm-phase1-distillate.md](product-brief-mt-pricing-mdm-phase1-distillate.md) |
| **S0-D03** | PRD v1.3 | ✅ Listo | Pablo Sierra | [prd-mt-pricing-mdm-phase1.md](prd-mt-pricing-mdm-phase1.md) |
| **S0-D04** | Arquitectura v1.3 + 30+ ADRs | ✅ Listo | Pablo Sierra | [architecture-mt-pricing-mdm-phase1.md](architecture-mt-pricing-mdm-phase1.md) + [adr/](adr/) |
| **S0-D05** | Research spike comparador v1.2 | ✅ Listo | Pablo Sierra | [research-spike-product-comparison.md](research-spike-product-comparison.md) |
| **S0-D06** | Épicas + 56 historias, ~400 SP | ✅ Listo | Pablo Sierra | [epics-and-stories-mt-pricing-mdm-phase1.md](epics-and-stories-mt-pricing-mdm-phase1.md) |
| **S0-D07** | UX mockups (27 wireframes + 6 flujos) | ✅ Listo | Pablo Sierra | [ux-mockups-mt-pricing-mdm-phase1.md](ux-mockups-mt-pricing-mdm-phase1.md) |
| **S0-D08** | Reglas v5.1 + 15 fixtures golden | ✅ Listo | Pablo Sierra | [sprint0-v51-rules-extraction.md](sprint0-v51-rules-extraction.md) |
| **S0-D09** | PIM column mapping (36 cols) | ✅ Listo | Pablo Sierra | [sprint0-pim-column-mapping.md](sprint0-pim-column-mapping.md) |
| **S0-D10** | **Stack firmado por TI MT** | ⏳ Pendiente | TI MT / Paula | TBD |
| **S0-D11** | **Sesión port-vs-rewrite con Juan Carlos** + golden numbers re-validados | ⏳ Pendiente | Pablo + Juan Carlos | TBD |
| **S0-D11b** | **Validación SQLAlchemy 2.0 async + DatabaseScheduler con TI MT** (sub-task de D10): confirma ADR-045 (persistencia híbrida) + ADR-046 (scheduler editable); decide librería `celery-sqlalchemy-scheduler` vs scheduler custom ~150 líneas | ⏳ Pendiente | TI MT + Pablo | TBD |
| **S0-D12** | **Provisioning Supabase + Hetzner + DNS + entornos dev/staging/prod** | ⏳ Pendiente | TI MT + Pablo | TBD |
| **S0-D13** | **CI/CD GitHub Actions skeleton** + Docker Compose dev | ⏳ Pendiente | TI MT + Pablo | TBD |
| **S0-D14** | **Threshold X% margen para auto-approve** firmado por Gerente | ⏳ Pendiente | Gerente Comercial | TBD |
| **S0-D15** | **RACI TI Integración** (FTE / role-share / vendor) firmado | ⏳ Pendiente | Sponsor MT | TBD |

**Estado global**: 9 de 15 entregables completos (60 %). Los 6 pendientes requieren **acción del cliente** (TI MT / Sponsor MT / Gerente Comercial / Juan Carlos). Pablo (BR) entrega todo lo controlable desde el lado BR.

## 3. Decisiones gating (G1, G2, G3)

### G1 — Stack tecnológico (S0) — **decisión preliminar tomada (ADR-045 + ADR-046); espera firma TI MT**

- **Propuesta v1.1**: Next.js 16 + FastAPI Python 3.11 + **SQLAlchemy 2.0 async (core data) + supabase-py (Auth/Storage/admin)** + Supabase Postgres+Auth+Storage + Celery + **Celery Beat con DatabaseScheduler editable (tabla `job_definitions`)** + Redis + Hetzner + Caddy + Docker Compose. ADRs 028-037 + ADR-045 + ADR-046.
- **Estado**: decisión preliminar registrada en PRD §17 + arquitectura §4 (tabla ADRs). Pendiente firma formal TI MT en S0-D10 + sub-task S0-D11b para validar el split SQLAlchemy/supabase-py y elegir librería del DatabaseScheduler.
- **Quién decide**: TI MT (Paula como validador técnico; Christian como sponsor).
- **Criterio**: el equipo MT (futuro mantenedor post-handoff) puede manejar TS+Python+SQLAlchemy o aceptar mantenimiento BR.
- **Bloqueante para**: 100 % de las historias técnicas Fase 1a (incluyendo nuevas US-1A-01-08, 01-09 y la épica EP-1A-08).
- **Riesgo de NO firmar**: stack queda especulativo; Sprint 1 no arranca; cronograma desliza. Si TI MT rechaza ADR-045 (SQLAlchemy), plan B es supabase-py puro 1:1 con hppt-iom — pierde tipado fuerte para queries del comparador, suma ~30 SP de wrappers manuales.

### G2 — Port-vs-rewrite del motor v5.1 (S0)

- **Recomendación**: **port-mostly + rewrite parcial** (~100 SP total, ~3-4 sprints).
  - Port directo: matemática del motor (`pricing.py:582 líneas`), reglas G1/G2, alertas, scoring básico.
  - Rewrite parcial: (1) fuente de costes Excel → tabla `costs.breakdown` JSONB; (2) `canal_recomendado` (vive en VBA — decompilar o re-derivar); (3) `regla_override_manual` (JSON disco → tabla `price_overrides` con RBAC); (4) FX hardcoded → `fx_rates` versionado.
- **Quién decide**: TI MT + Pablo + sesión con Juan Carlos (autor del motor + Excel master).
- **Criterio**: golden numbers de las 15 fixtures coinciden 100 % con `enrich_with_v51.py` re-corrido sobre las mismas referencias.
- **Riesgo si no se valida**: el motor portado puede fallar paridad y bloquear S4.

### G3 — Importer PIM (S0)

- **Riesgo bloqueante identificado**: PIM completo trae **todos los numéricos como strings**, **22,2 % de SKUs sin `Nombre ERP - AX`**, **multi-idioma EN/ES/AR ausente** del archivo, **specs estructuradas (DN/PN/material/family) cubribles sólo en 62,5 %** vía JOIN al catálogo derivado.
- **Recomendación crítica**: importer con cast por-celda con try/except + rechazo de fila individual + `errors[]` en `import_runs.preview JSONB` + conversión explícita cm→mm para dimensiones de caja.
- **Decisión que hay que tomar**: cómo cubrir los gaps de `name_en` (22 %), specs estructuradas (37,5 %), multi-idioma. Opciones:
  - (a) Parser sobre `erp_name` con regex/heurísticas + LLM extraction de fichas PDF para casos restantes.
  - (b) Captura manual asistida en la app (UI Comercial completa lo faltante por SKU).
  - (c) Solicitar a MT España un export complementario con specs estructuradas y multi-idioma.
  - (d) Combinación: export España (preferido) + parser + captura manual residual.
- **Quién decide**: Pablo + Champion del Cambio + Sponsor MT.

## 4. Cuestiones abiertas mapeadas a sprint

| Cuestión PRD | Tema | Owner | Sprint |
|-------------|------|-------|--------|
| Q-01 | Stack tecnológico | TI MT / Paula | S0 |
| Q-02 | Cloud y residencia datos UAE | TI MT / Pablo | S0 |
| Q-03 | Confirmación PIM real + costos | Pablo / Champion | S0 |
| Q-04 | Threshold X% margen auto-approve | Gerente | S0 |
| Q-05 | TI Integración RACI | Sponsor MT | S0 |
| Q-06 | mtme.ae remediación (Fase 3 gating) | Programa MT | S0 (flag) |
| Q-07 | Dataset etiquetado comparador | R&D Champion | S0–S2 |
| Q-08 | Fuente datos competidores | R&D Champion | S0 |
| Q-09 | Derechos imagen MT España | Sponsor MT / legal | S0–S1 |
| Q-10 | Port-vs-rewrite v5.1 | TI MT + Pablo | S0 |
| Q-11 | "Óptimo" para recomendador | Gerente | S4 (Fase 3 gating) |
| Q-12 | Ventanas de mantenimiento | TI / Gerente | S7 |
| Q-13 | Retención `audit_events` (default 7y VAT) | Sponsor / legal | S0 |
| Q-14 | Idioma observabilidad | TI | S0 |
| Q-15 | Threshold calibración comparador | R&D Champion | S2 |
| Q-16 | Selección 3.º marketplace POC | Comercial MT | S0 |
| Q-17 | Re-notificación 48h pending | Gerente | S0 |

**14 de 17 cuestiones tienen owner externo (cliente)**. Sin S0 cerrado, Sprint 1 no arranca con confianza.

## 5. Plan de la semana de Sprint 0 (T+0 a T+7 días)

| Día | Actividad | Owner | Output |
|-----|-----------|-------|--------|
| L | Sesión kickoff con Christian + Paula. Walkthrough brief + PRD + ADR-001 (stack proposal). | Pablo | Acta + decisión preliminar stack |
| L | Sesión Juan Carlos: walkthrough motor v5.1 + golden numbers re-corridos. | Pablo + JC | Validación de los 15 fixtures |
| M | Sesión Gerente Comercial: workflow excepción + thresholds + UI cola aprobación (P14). | Pablo + Gerente | Q-04, Q-17 firmados |
| M | Provisioning Supabase project (dev) + Hetzner box (dev). DNS + Caddy bootstrap. | TI MT + Pablo | Entornos dev verde |
| X | Diseño RACI TI Integración + decisión sobre Q-05. | Sponsor + TI | RACI firmado |
| X | Solicitud a MT España de export complementario (multi-idioma + specs estructuradas) si la decisión Q-03 es opción (c) o (d). | Sponsor MT | Compromiso de fechas |
| J | Plan de calibración comparador: contrato con freelance UAE (Q-08), POC 500 SKUs × 3 marketplaces; preselección 3.º marketplace (Q-16). | R&D Champion | Plan + presupuesto |
| J | CI/CD skeleton (GitHub Actions) + Docker Compose dev + healthchecks `/health/live` y `/health/ready` en FastAPI bootstrap. | Pablo + TI MT | PR mergeado a `main` con setup base |
| V | Retro Sprint 0 + commit gates G1+G2+G3 + arranque Sprint 1. | Pablo + sponsor + TI | Ack arranque Fase 1a |

## 6. Definition of Done — Sprint 0

Sprint 0 está cerrado cuando:

- [ ] Stack firmado por TI MT (G1) — sin ambigüedades sobre lenguajes y proveedores cloud.
- [ ] Port-vs-rewrite v5.1 decidido con evidencia (G2) — golden numbers validados por Juan Carlos.
- [ ] Estrategia de carga PIM cerrada (G3) — gaps con plan concreto.
- [ ] Provisioning de entornos dev (Supabase + Hetzner + Caddy + DNS) operativo.
- [ ] CI/CD baseline en GitHub Actions con build + test + deploy a dev.
- [ ] Cuestiones Q-01 a Q-10 resueltas o con dueño + fecha firme.
- [ ] Backlog Sprint 1 con ~30-40 SP refinados (DoR pasada).
- [ ] Acuerdo de derechos de imagen MT España ↔ MT ME documentado.

## 7. Riesgos top a mitigar en Sprint 0

| ID | Riesgo | Severidad | Mitigación S0 |
|----|--------|-----------|---------------|
| R-S0-01 | TI MT rechaza stack TS+Python | Alta | Plan B preparado (.NET full-stack o Java/Spring + Next.js); demo de productividad FastAPI; cita con Paula con preview funcional |
| R-S0-02 | Hetzner sin presencia UAE bloquea por residencia datos | Media | Plan B Frankfurt + DPA firmado; Plan C provider local UAE (presupuesto + tiempo extra) |
| R-S0-03 | Juan Carlos no disponible para sesión v5.1 | Media | Plan B doc del motor extraído autonomamente; gate G2 puede deslizar a S1 sin afectar G1 |
| R-S0-04 | Multi-idioma del PIM completo no se resuelve en S0 | Alta | Comprometer captura manual + LLM batch como fallback Fase 1a; Fase 1b ya con multi-idioma operativo |
| R-S0-05 | mtme.ae remediación se vuelve bloqueante prematuro | Baja | Reconfirmar que es Fase 3 gating, no Fase 1; flagged al Programa MT pero sin scope este sprint |

## 8. Backlog Sprint 1 sugerido (post G1+G2+G3)

Si los 3 gates pasan en S0, Sprint 1 arranca con (~32 SP):

| Historia | Épica | SP |
|----------|-------|----|
| US-1A-01-04 Repos `mt-pricing-frontend` + `mt-pricing-backend` con scaffolding | EP-1A-01 | 5 |
| US-1A-01-05 Auth Supabase + RBAC base + RLS policies skeleton | EP-1A-01 | 8 |
| US-1A-01-06 i18n UI ES/EN con next-intl | EP-1A-01 | 3 |
| US-1A-02-01 Modelo `products` con migración Supabase + uuidv7 | EP-1A-02 | 5 |
| US-1A-02-02 CRUD básico de SKU (FastAPI + Next.js) | EP-1A-02 | 8 |
| US-1A-07-01 Tabla `audit_events` + triggers Postgres | EP-1A-07 | 3 |

**Total**: 32 SP — alineado con capacidad asumida 30-40 SP/sprint para 2-3 devs FTE.

## 9. Indicadores de salud para tracking continuo

- **Velocity** (SP completados/sprint).
- **Burn-up de épicas** Fase 1a y 1b.
- **% historias listas (DoR)** entrando a sprint.
- **Tasa de defectos** post-deploy a staging.
- **Cobertura de PRD** (FR/BR mapeados a historias completadas).
- **Q-XX abiertas** y SLA de cierre por owner.

## 10. Próximos pasos inmediatos (handoff)

Tras revisión del usuario:

1. **Convocar reunión kickoff** con Christian + Paula + Pablo para presentar Brief + ADR-001.
2. **Coordinar sesión técnica** con Juan Carlos para validar 15 fixtures.
3. **Solicitar export complementario a MT España** (multi-idioma + specs estructuradas) — si aplica.
4. **Iniciar contratación freelance UAE** para etiquetar el dataset del comparador (10h/sem × $15/h × 4 sem ≈ $600/mes).
5. **Pedir demos** a Intelligence Node + Skuuudle + DataWeave en paralelo (50-100 fotos reales de válvulas MT).
6. **Lanzar provisioning** de entornos dev (Supabase + Hetzner) en cuanto G1 firme.

---

## Apéndice — Mapa de artefactos producidos

```
_bmad-output/planning-artifacts/
├── product-brief-mt-pricing-mdm-phase1.md            # Brief ejecutivo (revision_1)
├── product-brief-mt-pricing-mdm-phase1-distillate.md # Detail pack v1.2
├── stage2-contextual-discovery.md                     # Research Etapa 2
├── prd-mt-pricing-mdm-phase1.md                       # PRD v1.3 (~1300 líneas)
├── architecture-mt-pricing-mdm-phase1.md              # Arquitectura v1.3 (~111 KB)
├── research-spike-product-comparison.md               # Research spike v1.2
├── epics-and-stories-mt-pricing-mdm-phase1.md         # 13 épicas + 56 historias
├── ux-mockups-mt-pricing-mdm-phase1.md                # 27 wireframes + 6 flujos
├── sprint0-v51-rules-extraction.md                    # 18 reglas + 15 fixtures
├── sprint0-pim-column-mapping.md                      # 36 columnas mapeadas
├── sprint0-plan-consolidado.md                        # Este documento
└── adr/
    ├── ADR-001 a ADR-021 (algunos superseded por 028-037)
    ├── ADR-022 a ADR-027 (research spike OCR/RIS/build-vs-buy)
    ├── ADR-028 a ADR-037 (stack pivot FastAPI+Supabase+Hetzner)
    └── ADR-038 a ADR-041 (RAG → Hybrid → GraphRAG roadmap)
```

**Total ADRs**: 41. Activos en Fase 1: 26 (5 superseded, 10 deferred a Fases 2+).
