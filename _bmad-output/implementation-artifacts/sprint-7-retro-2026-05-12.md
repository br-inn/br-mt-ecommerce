---
title: "Sprint 7 — Retrospectiva"
sprint: 7
date: "2026-05-12"
facilitator: "Amelia (Developer)"
participants: ["psierra (PM/Dev)"]
project: "MT Middle East MDM + Pricing Fase 1"
nota: "Retro tardía — ejecutada post-S8. Foco en aprendizaje, no planificación."
---

# Retrospectiva Sprint 7 — MT Middle East Pricing Fase 1

> Tercera retrospectiva documentada. Sprint goal: cerrar EP-1B-02 completa (workflow aprobación) + resolver carry-overs S6.

## Estado final S7

### Comprometidas

| Story | SP | Resultado |
|-------|----|-----------|
| US-1B-02-07 — Digest diario 18:00 UAE | 5 | ✅ Done (carry-over S6) |
| US-RND-01-10 — UI human queue MVP | 5 | ✅ Done (carry-over S6) |
| US-1B-02-01 — State machine prices.status enforcement | 5 | ✅ Done |
| US-1B-02-02 — exception_rules CRUD + versionado + UI Gerente | 8 | ✅ Done |
| US-1B-02-03 — auto_approved vs pending_review logic | 5 | ✅ Done |
| US-1B-02-05 — bulk-approve endpoint | 3 | ✅ Done |
| US-1B-02-09 — Audit trail extendido | 3 | ✅ Done |
| US-1B-05-01 — Reporte diff app vs Excel (parallel run) | 3 | ✅ Done |

**SP comprometidos:** 37 | **SP completados:** 37 (100%) ✅

### Bloqueado externo desbloqueado en sprint

| Story | SP | Resultado |
|-------|----|-----------|
| US-1B-02-06 — Cola Gerente UI (Pantalla 12 firmada 2026-05-12) | 8 | ✅ Done |

### Stretch (Wave 2 — P2/P3)

| Story | SP | Resultado |
|-------|----|-----------|
| US-1B-05-07 — Dashboards observabilidad | 5 | ✅ Done |
| US-1B-05-06 — Performance hardening | 5 | ✅ Done |
| US-1B-05-02 — Manual operativo handbook-es.md | 5 | ✅ Done |
| US-OCR-S7 — Dockerfile.worker-ocr tesseract baked | 3 | ✅ Done |
| US-DR-DRILLS — Tabla dr_drills + mig 076 + endpoint admin | 3 | ✅ Done |

**SP stretch completados:** 21/21 (100%) ✅

### Totales

| Categoría | SP |
|-----------|----|
| Comprometidas (incl. carry-overs) | 37 |
| Bloqueado externo desbloqueado | 8 |
| Stretch Wave 2 | 21 |
| **Total Sprint** | **~66 SP** |

**Épicas cerradas en S7:** EP-1B-02 ✅ (9/9 stories — S4-S7)

---

## Qué fue bien

1. **Tiempo de ejecución** — 66 SP en un solo sprint es el mayor logro del proyecto. El modelo multi-agente paralelo (Wave 1 + Wave 2) permitió throughput sostenido sin overhead de coordinación tradicional.

2. **EP-1B-02 cerrada completamente** — 9 stories, state machine completa, exception rules, bulk approve, digest, audit trail, cola Gerente. En un equipo convencional serían 3+ sprints. Cerrada limpia sin deuda técnica visible.

3. **Carry-overs S6 → cero deuda** — US-1B-02-07 y US-RND-01-10 salieron como carry-overs de S6. Ambos cerrados en S7. Sin deuda muerta acumulada.

4. **Respuesta instantánea a desbloqueo externo** — US-1B-02-06 llevaba 2 sprints bloqueada por Pantalla 12. Tan pronto se firmó (2026-05-12), se implementó y cerró en el mismo sprint.

5. **21 SP stretch sin afectar comprometidas** — Wave 2 paralela entregó dashboards, performance hardening, manual operativo, OCR y DR drills mientras Wave 1 cerraba el core.

---

## Qué no fue bien

1. **Alembic multi-head en Wave 1** — Las migraciones paralelas de Wave 1 generaron 3 heads (072 + 073 + 074) con mismo `down_revision`. Requirió merge migration manual (075). El protocolo de S6 (A1) no se formalizó en DoD ni CLAUDE.md, por lo que el error se repitió.

2. **Esta retro saltada en su momento** — A5 de S6 pedía retros regulares desde S7. La retro de S7 se marcó "optional" y no se ejecutó. Se retró en S8 (una retro) pero S7 quedó sin análisis. Patrón: retrospectivas ceden ante velocity cuando no hay un mecanismo formal de bloqueo.

3. **Worktree isolation protocol sin decidir** — A4 de S6 pedía decisión documentada sobre isolation mode. No hay evidencia de que se haya formalizado. Los agentes de S7 siguieron sin protocolo explícito.

---

## Seguimiento Action Items S6

| # | Acción S6 | Estado | Evidencia |
|---|-----------|--------|-----------|
| A1 | Protocolo alembic multi-agent en DoD | ⚠️ Parcial | Conocimiento aplicado (mig 075) pero no formalizado en CLAUDE.md |
| A2 | Confirmar Doppler creds Hetzner | ✅ | Resuelto en S8 (US-1A-IAC-01-DEPLOY Wave 5) |
| A3 | Sección "contingente externo" en backlog | ✅ | Visible en sprint-status.yaml desde S7 |
| A4 | Protocolo isolation agentes paralelos | ❌ | Sin evidencia de decisión documentada |
| A5 | Retros regulares desde S7 | ❌ | Esta retro se saltó; se recupera tardíamente |

**2/5 action items completados, 1 parcial, 2 sin completar.**

---

## Hallazgos técnicos a retener

### Alembic: el problema es estructural, no de disciplina

El multi-head en S7 (Wave 1: 072+073+074) repite exactamente el patrón de S6. La causa raíz no es olvido — es que no existe un mecanismo de enforcement. La solución es estructural: agregar al checklist de DoD de cualquier story con migración: "verificar head actual con `alembic heads` antes de generar la migración".

### Velocidad no elimina la necesidad de proceso

66 SP/sprint es posible precisamente porque el proceso está bien diseñado (stories atómicas, agentes sin solapamiento, wave planning). La omisión de retros no reduce riesgo — lo acumula silenciosamente.

### Desbloqueo externo como trigger inmediato

US-1B-02-06 demostró que cuando un bloqueador externo se resuelve mid-sprint, el modelo puede absorberlo sin disrupción. Esto es una ventaja estructural vs. equipos que necesitan planificarlo para el sprint siguiente.

---

## Action items S9 (incrementales — no duplicar S8)

| # | Acción | Responsable | Criterio |
|---|--------|-------------|---------|
| A1 | Agregar a CLAUDE.md: checklist alembic (`alembic heads` antes de generar migración) | Dev S9 | CLAUDE.md actualizado con protocolo |
| A2 | Agregar retro al Definition of Done del sprint — no opcional | psierra | sprint-status: retro != optional en S9 |

---

## Preparación S9

Ver retro S8 para lista completa. Items específicos de S7 sin impacto en S9.

**Épicas con trabajo pendiente:**
- EP-1B-04 — Shadow publish real Amazon UAE (sandbox pendiente)
- EP-RND-01 — Comparator Fase 2 (pendiente feedback cliente Fase 1)
- EP-1A-02 — PIM extensiones (EAV/taxonomy en vuelo)

---

*Generado: 2026-05-12 — Retro tardía post-S8. Sprint 7 completado (100% comprometidas + 100% stretch).*
