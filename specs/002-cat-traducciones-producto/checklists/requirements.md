# Checklist de calidad del spec: Traducciones de Producto (CAT sub-recurso)

**Proposito**: Validar completitud y calidad del spec antes de continuar con
verificacion de conformidad F1.
**Creado**: 2026-05-25
**Feature**: [spec.md](../spec.md)

## Calidad del contenido

- [x] Sin detalles de implementacion en los requisitos funcionales
- [x] Centrado en el valor de usuario y necesidades de negocio
- [x] Escrito para que un stakeholder no tecnico entienda los escenarios de usuario
- [x] Todas las secciones obligatorias completadas (Clarificaciones, Escenarios,
      Requisitos, Criterios de exito, Supuestos)

## Completitud de requisitos

- [x] Sin marcadores `[NEEDS CLARIFICATION]` — todas las ambiguedades resueltas
      con evidencia de codigo
- [x] Los requisitos son verificables y no ambiguos (cada FR/NFR/BR tiene evidencia
      archivo:linea)
- [x] Los criterios de exito son medibles (SC-TRD-001 a SC-TRD-006)
- [x] Casos limite identificados (seccion "Casos limite")
- [x] El alcance esta claramente delimitado:
      - CRUD: GET lista, PUT upsert, PATCH parcial, POST approve clasico
      - Workflow S3: request-review, reject, mark-stale
      - AI coverage: GET coverage, POST complete
- [x] Dependencias y supuestos identificados (seccion "Supuestos")
- [x] Todos los IDs de requisitos siguen el prefijo TRD:
      FR-TRD-001..014, NFR-TRD-001..006, BR-TRD-001..006

## Completitud de la verificacion

- [x] Todos los requisitos tienen estado en verification.md
      (Verificado / Parcial / No cumple / No implementado)
- [x] Cada estado tiene evidencia archivo:linea
- [x] Todas las brechas tienen severidad, requisitos afectados, descripcion,
      accion sugerida e issue de GitHub (#90-#94)
- [x] El resumen de conformidad cuadra: 21 Verificado + 5 Parcial = 26 total
      (14 FR + 6 NFR + 6 BR)
- [x] La traceability-cat.csv tiene una fila por requisito (26 filas de datos)

## Preparacion del feature

- [x] Todos los requisitos funcionales tienen criterios de aceptacion en los escenarios
- [x] Los escenarios cubren: CRUD basico, workflow four-eyes, staleness, cobertura AI
- [x] Sin detalles de implementacion que se filtren al spec
- [x] El spec es RETROSPECTIVO — no modifica codigo fuente

## Issues de GitHub creados

- [x] BRECHA-TRD-01 — issue #96 — Endpoint clasico approve sin four-eyes (Alta)
- [x] BRECHA-TRD-02 — issue #97 — RFC 7807 incompleto en workflow endpoints (Media)
- [x] BRECHA-TRD-03 — issue #98 — session.refresh() extra en approve clasico (Baja)
- [x] BRECHA-TRD-04 — issue #99 — actor_id no propagado al completion service (Baja)
- [x] BRECHA-TRD-05 — issue #101 — Estado ai_generated no expuesto en API (Baja)

## Notas

- El spec es **retrospectivo**: documenta lo que el sistema hace hoy.
- Los IDs siguen el esquema Art. 6: `FR-TRD-NNN`, `NFR-TRD-NNN`, `BR-TRD-NNN`.
- La brecha mas critica (BRECHA-TRD-01) implica un control interno incumplido
  (four-eyes) que debe resolverse antes del proximo sprint de traducciones.
- El Manual Operativo BR Dynamic x MT Valves no estaba accesible; origen primario
  del requisito four-eyes = PRD BR-1a-09.

**Resultado de validacion**: APROBADO — el spec esta completo y listo para F1.
