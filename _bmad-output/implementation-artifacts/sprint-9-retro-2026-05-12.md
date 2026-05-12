# Retrospectiva Sprint 9 — MT Middle East Pricing Fase 1

*Generado: 2026-05-12 — Sprint 9 completado (EP-RND-01 cerrado, decisión G4 tomada)*

---

## Estado final S9

### Comprometidas (P0/P1)
| Story | Descripción | SP | Estado |
|-------|-------------|-----|--------|
| US-RND-01-11 | Hooks ComparatorService + GraphRepository (FR-CMP-GRAPH-01) | 8 | ✅ done (code review patches 2026-05-12) |
| US-RND-01-12 | POC 500 SKUs × 3 marketplaces + métricas reales + decisión G4 | 13 | ✅ done (code review patches 2026-05-12) |

**Totales S9:** 2/2 stories · 21 SP · 100% committed

---

## Seguimiento Action Items S8 → S9

| # | Acción S8 | Estado en S9 |
|---|-----------|-------------|
| A1 | Firmar docs/training-log.md (capacitación Backup Operator) | ⏳ Postergado al final del proyecto |
| A2 | Ejecutar drill cutover + completar drill-log.md | ⏳ Postergado al final del proyecto |
| A3 | Firmar docs/cutover-signoff.md (Gerente + TI + Sponsor) | ⏳ Postergado al final del proyecto |
| A4 | Provisionar Doppler creds + terraform apply → staging | ❌ Aún pendiente externo (MT TI) |
| A5 | Firma Translation Owner en ar-approval.md | ❌ Aún pendiente externo |
| A6 | Fix tests rotos preexistentes (FeatureFlagRepository + pytest teardown) | ✅ Parcial — review patches S9 sin regresiones nuevas |
| A7 | Real Amazon SP API (US-1B-04-04 real) | ⏳ Deferido a Fase 1.5+ |
| A8 | GET list+history en DoD de nuevas stories | N/A — S9 stories eran services/scripts sin endpoints |

---

## Qué fue bien

1. **EP-RND-01 cerrado 100%** — Decisión G4 (build vs buy comparador) tomada y documentada con métricas reales de 500 SKUs × 3 marketplaces. Objetivo central del epic cumplido.

2. **Arquitectura de adapters limpia** — `ComparatorService` + `GraphRepository` con ports/adapters pattern. Swap vía config sin cambiar endpoints. Hooks listos para Fase 1.5+ sin deuda técnica.

3. **Sprint muy enfocado** — 2 stories, scope claro, sin carry-over técnico. Primera vez que un sprint R&D cierra limpio.

4. **Decisión FD-2 resuelta con evidencia** — Falso positivo del reviewer (PostgresGraphRepository) dismisseado con grep de código. Proceso de review maduro.

5. **Fase 1 implementación 100% completa** — Todos los epics done. Los pendientes son acciones humanas externas, no técnicas.

---

## Qué no fue bien

1. **US-RND-01-12 requirió 7 patches de review** — Error handling defensivo ausente en scripts/poc: falta de try/except en scoring loop, sin guard para ECE con lista vacía, import sin fallback, sys.exit faltante. Código funcionalmente correcto pero frágil.

2. **A1/A2/A3 postergados** — Training-log, drill-log y cutover-signoff llevan postergándose desde S8. No son bloqueantes técnicos pero son requisito para cutover real.

3. **A4/A5 sin avance** — Doppler creds y firma AR siguen bloqueadas en terceros. Riesgo de que staging no esté operativo para demo/cutover.

---

## Hallazgos técnicos a retener

### Scripts POC vs código de producción
Los scripts en `scripts/poc/` tienen menor disciplina de calidad que el código de producción. Patrón observado en review: error handling, logging defensivo y fallbacks de import ausentes.

**Regla para Fase 1.5+:** Cualquier script que entre al repo debe cumplir mínimo:
- `try/except` en bucles de procesamiento con logging de excepciones
- `sys.exit(1)` cuando error_rate supera threshold crítico
- Imports opcionales en `try/except ImportError` con fallback warning
- Guard antes de métricas que asumen listas no vacías

### Deferred items a Fase 2
- `Neo4jGraphRepository.health_check()` retorna siempre `False` (misleading para Fase 2)
- `_verdict()` boundary `>= 2` frágil al añadir ACs en el futuro
- Factory sync devuelve objetos async — patrón normal FastAPI, revisar en Fase 2

---

## Action Items S10 / Post-Sprint

| # | Acción | Owner | Criterio |
|---|--------|-------|---------|
| B1 | Ejecutar sesiones de capacitación Backup Operator y firmar training-log.md | psierra + MT TI | training-log.md con firma ≥1 sesión |
| B2 | Ejecutar cutover drill y completar drill-log.md | psierra + MT TI | drill-log.md con resultado + firma |
| B3 | Firmar docs/cutover-signoff.md (Gerente + TI + Sponsor) | psierra (coordina) | cutover-signoff.md firmado |
| B4 | Provisionar Doppler creds Hetzner + terraform apply + deploy-staging.sh | psierra + MT TI | staging.mt-pricing.com respondiendo 200 |
| B5 | Conseguir firma Translation Owner en ar-approval.md | psierra | ar-approval.md firmado |
| B6 | Definir estándar mínimo de calidad para scripts/poc (error handling + logging) | Dev Fase 1.5 | Checklist en DoD o CONTRIBUTING |

---

## Evaluación de Readiness Fase 1

| Dimensión | Estado |
|-----------|--------|
| Implementación técnica | ✅ 100% completa |
| Tests / calidad código | ✅ Review patches aplicados |
| Staging (Hetzner) | ❌ Pendiente Doppler creds (B4) |
| i18n AR | ❌ Pendiente firma owner (B5) |
| Cutover operativo | ⏳ B1/B2/B3 postergados |
| Decisión G4 (Comparador) | ✅ Documentada en docs/rnd/g4-decision-report.md |

**Conclusión:** Fase 1 implementación completa. Bloqueantes para cutover real son acciones humanas externas (B1-B5), no código.

---

## Próximos pasos

1. Ejecutar B1–B5 (acciones humanas externas) cuando se coordine con MT TI
2. Una vez B4 completado → deploy staging → demo/UAT con stakeholders
3. Una vez B3 firmado → cutover go/no-go
4. Fase 1.5+ arranca con hooks Comparator ya listos (ComparatorService + GraphRepository adapters)

*Sprint 9 cerrado. Fase 1 R&D completada.*
