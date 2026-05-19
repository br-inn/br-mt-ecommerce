---
skill: bmad-code-review
fecha: {{date}}
story_id: 
pr_branch: 
estado: in-review
---

# Code Review — {{title}}

> Skill: `/bmad:bmm:workflows:code-review`

## Story revisada

- **Story:** 
- **Branch:** 
- **Archivos cambiados:** 

## Checklist pre-review

- [ ] Tests unitarios pasan
- [ ] Migrations aplicadas (`./infra/scripts/migrate.sh`)
- [ ] Container reiniciado (`docker restart mt-backend`)
- [ ] Smoke test: `curl http://localhost:8081/health/live`
- [ ] Frontend reiniciado si aplica

## Hallazgos — Blind Hunter (bugs / seguridad)

| Archivo | Línea | Problema | Severidad |
|---------|-------|----------|-----------|
|         |       |          | P0/P1/P2  |

## Hallazgos — Edge Case Hunter

| Caso | ¿Cubierto? | Acción |
|------|-----------|--------|
|      | Sí/No     |        |

## Hallazgos — Acceptance Auditor

<!-- ¿La implementación cumple todos los criterios de la story? -->

| Criterio de aceptación | Estado |
|----------------------|--------|
|                      | ✅/❌  |

## Resultado

- [ ] **Aprobado** — listo para marcar `done` en sprint-status.yaml
- [ ] **Aprobado con cambios menores** — fixes rápidos antes de marcar done
- [ ] **Requiere revisión** — blocker encontrado

## Cambios aplicados post-review

- 
