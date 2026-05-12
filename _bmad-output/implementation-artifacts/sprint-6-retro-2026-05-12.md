---
title: "Sprint 6 — Retrospectiva"
sprint: 6
date: "2026-05-12"
facilitator: "Amelia (Developer)"
participants: ["psierra (PM)", "Alice (PO)", "Charlie (Senior Dev)", "Dana (QA)", "Elena (Junior Dev)"]
project: "MT Middle East MDM + Pricing Fase 1"
---

# Retrospectiva Sprint 6 — MT Middle East Pricing Fase 1

> Primera retrospectiva documentada del proyecto (S1-S5 sin retro formal). Sprint goal: cerrar cola operacional Fase 1b.

## Estado final S6

| Story | SP | Resultado |
|-------|----|-----------|
| US-1B-02-08 — Escalation job >48h + delegado | 5 | ✅ Done S6 |
| US-1A-06-04-V2-S6 — pdfplumber tablas estructuradas | 5 | ✅ Done S6 |
| US-1B-05-04-DOC — DR runbook + drill plan | 3 | ✅ Done S6 |
| US-1B-02-07 — Digest diario 18:00 UAE | 5 | ⏩ Carry-over → Done S7 |
| US-RND-01-10 — UI human queue scaffold | 5 | ⏩ Carry-over → Done S7 |
| US-1B-02-06 — Cola Gerente UI | 8 | ❌ Blocked externo → Done S7 (Pantalla 12 firmada) |
| US-1A-IAC-01-DEPLOY — Hetzner staging | 5 | ❌ Blocked externo (Doppler creds) → deferred |
| US-1A-07-04-AR — AR translation | 3 | ❌ Blocked externo (owner sin firmar) → deferred |

**SP comprometidos:** 23 core  
**SP completados en sprint:** 13 (57%)  
**SP carry-over completados en S7:** 10 (43%)  
**SP bloqueados externos deferred:** 16 (fuera de control del equipo)

**Bonus no planificado (paralelo post-S6):**
- Taxonomy registry: ~25 SP
- PIM EAV: ~10 SP
- PIM frontend: ~8 SP
- Comparator Fase 1 hooks: ~3 SP
- **Total bonus: ~46 SP** — más del doble del sprint comprometido

---

## Qué fue bien

1. **Modelo multi-agente en paralelo** — 4+ agentes simultáneos sin conflictos de merge graves. Throughput sostenido sprint tras sprint (35/35 S1 → 41/41 S2 → 49/53 S5).

2. **Bonus 2x** — 46 SP de trabajo no planificado entregados mientras el sprint core se ejecutaba. Taxonomy, PIM EAV, PIM frontend, Comparator hooks son entregables de alto valor que en proyectos típicos quedan para "algún día".

3. **DR runbook entregado** — US-1B-05-04-DOC cerrado como P1 a pesar de ser documentación. Drill plan incluido. Deuda de continuidad resuelta.

4. **pdfplumber cerrado** — US-1A-06-04-V2-S6 era carry-over de S4 con dependency externa (signoff Comercial). Se cerró limpio con tablas estructuradas + screenshots por página.

5. **Carry-overs eventualmente cero-deuda** — Los dos carry-overs (US-1B-02-07, US-RND-01-10) se entregaron en S7. No hay deuda muerta de S6.

---

## Qué no fue bien

1. **43% del sprint en carry-over** — US-1B-02-07 y US-RND-01-10 salieron sin cerrar. Latencia de 1 sprint.

2. **Bloqueadores externos sistémicos** — Pantalla 12 (UX), AR translation owner, Doppler creds Hetzner: 3 bloqueadores fuera del control del equipo que suman 16 SP deferred. El sprint goal los mencionaba pero seguían apareciendo en la tabla maestra como stretch, inflando el backlog visible.

3. **Cero retros S1-S5** — No hay capital de aprendizaje documentado de los sprints anteriores. La velocity sostenida enmascara deuda de proceso.

4. **Alembic multi-head** — En S7 se generaron 3 migraciones paralelas con el mismo `down_revision`, creando 3 heads que rompían `alembic upgrade head`. Requirió merge migration manual (075). Sin protocolo formal este riesgo se repite.

5. **Worktree isolation no funcional** — `isolation: "worktree"` en agentes paralelos no aisló los cambios; los agentes escribieron en el working tree de main. Los worktrees quedaron vacíos y debieron limpiarse manualmente.

6. **Config.py como hot-spot** — Variables de múltiples agentes (SMTP_*, HUMAN_QUEUE_ENABLED) se acumularon sin conflicto esta vez, pero es un archivo de alto riesgo en commits selectivos.

---

## Hallazgos técnicos a retener

### Alembic multi-agent protocol (NUEVO)
Si hay >1 agente tocando migraciones alembic en el mismo sprint:
- El segundo agente debe partir del último `revision` ya creado, no de un `down_revision` compartido.
- Si se generaron paralelas con el mismo `down_revision`, crear merge migration vacía antes del primer `alembic upgrade head`.
- **Agregar como DoD de cualquier story con migración:** "si hay otras migraciones en vuelo, crear merge migration".

### Worktree isolation decision
- `isolation: "worktree"` útil solo si se planea mergear desde las ramas.  
- Para agentes que deben escribir directo en main: no usar `isolation`, usar `mode: "auto"` + commits manuales por story.
- Para aislamiento real: usar ramas nombradas explícitamente y mergear al final.

### Dependency chain en workers
- US-1B-02-07 dependía de US-1B-02-08 (notifications infra). Si la escalación toma más SP que el estimado, la dependency comprime el tiempo del digest.
- En S8+: serializar stories con dependency dura en el sprint (no paralelas) o estimarlas como bloque único.

---

## Action items S8

| # | Acción | Responsable | Criterio |
|---|--------|-------------|---------|
| A1 | Documentar protocolo alembic multi-agent como checklist en DoD de stories con migración | Dev (psierra) | Está en CLAUDE.md o checklist S8 |
| A2 | Confirmar con MT si Doppler creds Hetzner disponibles | psierra | Go/no-go para US-1A-IAC-01-DEPLOY en S8 |
| A3 | Mover stretch bloqueados externos a sección separada "contingente externo" en template de backlog | PM | Template actualizado en S8 backlog |
| A4 | Decidir protocolo de isolation para agentes paralelos (worktree vs ramas reales vs directo en main) | Dev | Decisión en CLAUDE.md antes de S8 kickoff |
| A5 | Iniciar retrospectivas regulares desde S7 (no esperar a S8) | psierra | Esta retro es el primer hito |

---

## Preparación S8

**Stories backlog disponibles (P2/P3):**
- US-1B-05-07 — Dashboards observabilidad (5 SP)
- US-1B-05-06 — Performance hardening (5 SP)
- US-1B-05-02 — Manual operativo handbook-es.md (5 SP)
- US-OCR-S7 — Dockerfile.worker-ocr tesseract (3 SP)
- US-DR-DRILLS — Tabla dr_drills + migración (3 SP)

**Épicas siguientes:**
- EP-1B-03 — Estados de canal + simulación (backlog)
- EP-1B-04 — Connectors base + shadow publish (backlog)

**Preguntas abiertas para S8 planning:**
1. ¿EP-1B-03 completa o solo stories P0?
2. ¿Hetzner deploy desbloqueado? (A2 arriba)
3. ¿AR translation owner firma? Si sí, US-1A-07-04-AR entra como P1.

---

*Generado: 2026-05-12 — Primera retrospectiva documentada del proyecto.*
