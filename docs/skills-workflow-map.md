---
tags: [referencia, skills, workflow]
---

# Mapa de Skills BMAD → Obsidian

Guía de qué skill usar en cada momento del ciclo de desarrollo.

---

## Ciclo completo de una story

```
1. bmad-sprint-status     → ver qué story viene
2. bmad-create-story      → generar el archivo de story
3. superpowers:writing-plans → plan antes de tocar código
4. bmad-dev-story         → implementar (con TDD)
5. bmad-code-review       → revisar lo implementado
6. sprint-status.yaml     → marcar done manualmente
```

---

## Skills por situación

| Situación | Skill a usar | Template Obsidian |
|-----------|-------------|-------------------|
| Ver estado del sprint | `bmad-sprint-status` | [Sprint Dashboard](sprint-dashboard.md) |
| Crear la próxima story | `bmad-create-story` | — (BMAD genera el archivo) |
| Planificar implementación | `superpowers:writing-plans` | — (genera en `docs/superpowers/plans/`) |
| Implementar una story | `bmad-dev-story` | [Notas de implementación](obsidian-templates/story-implementation-notes.md) |
| Encontrar un bug | `superpowers:systematic-debugging` | — |
| Revisar código terminado | `bmad-code-review` | [Code Review Notes](obsidian-templates/code-review-notes.md) |
| Cerrar un sprint | `bmad-retrospective` | [Retrospectiva](obsidian-templates/retrospectiva-sprint.md) |
| Documentar una sesión | `save-chat-md` | [Session Chat Doc](obsidian-templates/session-chat-doc.md) |
| Registrar una decisión nueva | Manual | [ADR Nuevo](obsidian-templates/adr-nuevo.md) |
| Tareas paralelas independientes | `superpowers:dispatching-parallel-agents` | — |

---

## Artefactos generados por BMAD (no editar manualmente)

| Artefacto | Ubicación | Se edita con |
|-----------|-----------|-------------|
| Sprint status | `_bmad-output/implementation-artifacts/sprint-status.yaml` | Editor de texto directo |
| Stories | `_bmad-output/planning-artifacts/` | Solo Claude Code via `bmad-dev-story` |
| Epics | `_bmad-output/planning-artifacts/epics-and-stories-*.md` | Solo BMAD |
| ADRs oficiales | `_bmad-output/planning-artifacts/adr/` | Solo Claude Code |
| Planes de implementación | `docs/superpowers/plans/` | Solo `writing-plans` |

---

## Cómo usar los templates en Obsidian

1. Crear nota nueva (`Ctrl+N`)
2. `Ctrl+P` → "Templates: Insert template"
3. Seleccionar el template de la lista
4. Completar los campos con `{{title}}` y `{{date}}` ya autorrellenos

---

## Skills de soporte (usar cuando aplique)

- `superpowers:test-driven-development` — antes de implementar features con lógica compleja
- `superpowers:verification-before-completion` — antes de reportar una story como done
- `superpowers:finishing-a-development-branch` — al cerrar una rama de trabajo
- `bmad-domain-research` / `bmad-technical-research` — antes de diseñar algo nuevo
- `bmad-sprint-planning` — cuando hay que planificar el siguiente sprint completo
