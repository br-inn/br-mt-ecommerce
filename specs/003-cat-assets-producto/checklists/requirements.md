# Checklist de calidad del spec: Assets/Imágenes de producto (CAT — sub-recurso)

**Propósito**: Validar completitud y calidad del spec antes de continuar con verificación o
tareas de implementación de brechas.
**Creado**: 2026-05-25
**Feature**: [spec.md](../spec.md)

## Calidad del contenido

- [x] Sin detalles de implementación en los requisitos funcionales (los FR describen comportamiento, no código)
- [x] Centrado en el valor de usuario y necesidades de negocio
- [x] Escrito para que un stakeholder no técnico entienda los escenarios de usuario
- [x] Todas las secciones obligatorias completadas (escenarios, requisitos, entidades, criterios de éxito, supuestos)

## Completitud de requisitos

- [x] Sin marcadores `[NEEDS CLARIFICATION]` — las ambigüedades se convirtieron en brechas documentadas
- [x] Los requisitos son verificables y no ambiguos (cada FR tiene referencia de código evidencia)
- [x] Los criterios de éxito son medibles (SC-AST-001 a SC-AST-006)
- [x] Los criterios de éxito son agnósticos de tecnología
- [x] Todos los escenarios de aceptación están definidos (3 historias × múltiples escenarios)
- [x] Casos límite identificados (sección "Casos límite")
- [x] El alcance está claramente delimitado (endpoints /assets/*, /images/* deprecados, /asset-links)
- [x] Dependencias y supuestos identificados (sección "Supuestos")

## Completitud de verificación

- [x] Cada requisito (FR/NFR/BR) tiene fila en verification.md con estado y evidencia archivo:línea
- [x] Cada brecha tiene severidad, requisito afectado, descripción y acción sugerida
- [x] Cada brecha tiene issue de GitHub enlazado (#93, #94, #95, #96, #97)
- [x] El resumen de conformidad cuadra: 25 Verificado + 9 Parcial = 34 total requisitos
- [x] El CSV de trazabilidad cubre todos los 34 requisitos con una fila cada uno

## Preparación del feature

- [x] Todos los requisitos funcionales tienen criterios de aceptación claros (en spec.md escenarios)
- [x] Los escenarios de usuario cubren los flujos primarios (upload, ciclo de vida, links polimórficos)
- [x] Sin detalles de implementación que se filtren al spec

## Notas

- El spec es **retrospectivo**: documenta lo que el sistema hace hoy, no lo que se desearía construir.
- Los IDs de requisitos siguen el esquema de la Constitución Art. 6: `FR-AST-NNN`, `NFR-AST-NNN`, `BR-AST-NNN`.
- El prefijo `AST` (AsSeT) es consistente con el plan del task (B2).
- 5 brechas encontradas, todas de severidad Baja-Media. Ninguna bloquea la funcionalidad básica.
- Los endpoints deprecados `/images/*` son funcionales y tienen header de deprecación correcto.
- El sub-recurso respeta Art. 3 de la Constitución (sin N+1) en la construcción de URLs.

**Resultado de validación**: ✅ APROBADO — el spec está completo para la verificación F1.
