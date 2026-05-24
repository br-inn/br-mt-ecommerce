# docs/estrategia — Documentación de estrategia del proyecto

Esta carpeta contiene los documentos de estrategia de `br-mt-ecommerce`. Vive en el
repositorio y se versiona con git. El repo también es un vault de Obsidian, por lo que los
`[[wiki-links]]` entre los `.md` resuelven directamente.

Los documentos de conocimiento de negocio (Manual Operativo, legales) siguen en `MT-ME`.

---

## Documentos

### [[Estrategia_Requisitos_Funcionales_SpecKit_ES]] `.docx`

**Para quién:** todo el equipo (PM, tech lead, desarrolladores).

Marco de trabajo para capturar y gestionar requisitos funcionales usando el flujo SpecKit
(spec → verificación → automatización). Define cómo se nombran los FR (`FR-<DOM>-NNN`),
cómo se redactan los escenarios Given/When/Then y cuándo un proceso está "hecho".

---

### [[Estrategia_Desarrollo_Guia_Equipo_ES]] `.docx`

**Para quién:** desarrolladores y tech lead.

Guía práctica del equipo: convenciones de código, flujo git/PR, stack técnico, reglas de
CI y cómo encajan el backend, frontend, worker y base de datos en el día a día.

---

### [[Estrategia_Pruebas_Validacion_SpecKit_ES]]

**Para quién:** todo el equipo; especialmente QA y tech lead.

Capa de pruebas de la estrategia de requisitos. Define las cuatro capas de prueba (Capa 1
desarrollo, Capa 2 e2e, Capa 3 proceso/aceptación, Capa 4 calidad del dato), el flujo del
requisito a la prueba, la Definición de Hecho de pruebas y los gates de CI.

---

### [[F1-CAT_Plan_de_Pruebas]]

**Para quién:** equipo técnico + responsable de F1.

Aplicación concreta de la estrategia de pruebas al proceso piloto CAT (catálogo de
productos). Mapea las 13 áreas de requisito contra los tests existentes, define objetivos
de cobertura y proporciona ejemplos de casos de prueba para la Capa 3.

---

### [[F1-CAT_Control_Piloto]]

**Para quién:** responsable de F1 y PM.

Control centralizado del piloto F1 sobre el proceso CAT. Tabla de tareas con su estado,
matriz de trazabilidad por FR, criterios de validación del piloto y bitácora de eventos.
Se mantiene actualizado desde Cowork tras cada ejecución de Claude Code.

---

## Nota — Matriz maestra de trazabilidad

`Matriz_Trazabilidad_Verificacion_SpecKit.xlsx` aún no tiene hogar estable. Decisión
pendiente (ver [[F1-CAT_Control_Piloto]] §5 NOTA 2): versionar en `specs/_matriz/` del
repo o mantener en `MT-ME\F1-Control\`. Hasta resolverlo, la fuente de verdad por proceso
es el `traceability-<dom>.csv` en `specs/NNN-<dom>-<slug>/`.
