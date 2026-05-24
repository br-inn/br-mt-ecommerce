# Estrategia de Gestión de Requisitos Funcionales con Spec-Driven Development

*Cómo conectar los procesos del Manual Operativo con especificaciones verificables, revisar proceso por proceso lo que ya está implementado, y llevar la aplicación br-mt-ecommerce hasta la fase de pruebas.*

| | |
|---|---|
| **Proyecto** | BR Dynamic x MT Valves · e-commerce multicanal (UAE) |
| **Aplicación** | br-mt-ecommerce · en pleno desarrollo, aún sin fase de pruebas |
| **Versión** | Borrador V2 · reorientado a GitHub Spec Kit |
| **Fecha** | 24 de mayo de 2026 |
| **Autoría** | P. Sierra · BR Dynamic Solutions |

> **SUSTITUYE AL BORRADOR ANTERIOR**
>
> Esta V2 sustituye al Borrador V1 (basado en BMAD). Tras evaluar las opciones de herramienta, el proyecto se inclina por adoptar GitHub Spec Kit; el capítulo 1.3 razona esa decisión. La estrategia de fondo —trazabilidad, identificadores, matriz, gobernanza— se conserva: es agnóstica de la herramienta.

> **NOTA SOBRE ESTE BORRADOR**
>
> Documento de trabajo. Las decisiones marcadas como NOTA AL EQUIPO requieren ratificación. La adopción de Spec Kit debería confirmarse con un piloto antes de comprometer al equipo por completo.

---

## Resumen ejecutivo

El proyecto br-mt-ecommerce se construye hoy con el método BMAD. Esta estrategia propone reorientar el desarrollo hacia Spec-Driven Development (SDD) usando GitHub Spec Kit, una herramienta más ligera, respaldada por GitHub y que funciona de forma nativa con Claude Code. La decisión se razona en el capítulo 1.3.

El punto de partida hay que verlo con honestidad. El sistema está en pleno desarrollo y no ha entrado en fase de pruebas. El fichero de seguimiento marca unas 58 historias como hechas, pero "hecho" ahí significa código escrito, no código verificado contra lo que el negocio pide. Por tanto, la primera tarea real no es planificar trabajo nuevo: es recorrer proceso por proceso lo ya implementado y comprobar si hace lo que se le pide.

A esto se suma el problema de fondo: los requisitos viven en tres mundos desconectados —el Manual Operativo, los artefactos del repositorio de código y las hojas de seguimiento— y ningún identificador recorre la cadena completa desde el proceso de negocio hasta el código.

La propuesta tiene cuatro piezas. Primero, adoptar la cadena de artefactos de Spec Kit: constitución del proyecto, especificación (spec), plan técnico, lista de tareas e implementación. Segundo, un esquema unificado de identificadores que sirve de hilo conductor. Tercero, una Matriz de Trazabilidad y Verificación que es el registro vivo del estado real de cada requisito. Cuarto, un flujo de trabajo proceso por proceso, con dos casos: verificar lo ya implementado y especificar lo nuevo.

La hoja de ruta tiene cuatro fases: instalar Spec Kit y sanear el repositorio (F0); barrer proceso por proceso lo ya construido, escribiendo su spec y verificando la implementación (F1); incorporar los procesos nuevos del Manual (F2); y operar de forma continua (F3). El sistema entra en fase de pruebas cuando la matriz está verde, no antes.

*Acompaña a este documento la Matriz de Trazabilidad y Verificación en formato Excel, lista para usarse desde el primer día.*

---

# 1. Propósito, alcance y método

## 1.1 Qué problema resuelve

El equipo planteó tres dolores; el trabajo de reorientación ha hecho aflorar un cuarto, que es hoy el más urgente:

- **Trazabilidad:** no se sabe qué requisito corresponde a qué especificación, tarea o entrega de código.
- **Completitud:** las especificaciones, los diseños y las tareas quedan a medias o se improvisan.
- **Gobernanza:** falta claridad sobre quién define qué, cuándo, y con qué criterio se da algo por listo o por terminado.
- **Verificación:** el sistema está en pleno desarrollo y no se ha probado; hay que recorrer proceso por proceso lo ya implementado y comprobar si hace lo que se pide.

## 1.2 Alcance

Dentro de alcance: el modelo de trabajo SDD con Spec Kit; el flujo proceso por proceso, tanto para verificar lo construido como para especificar lo nuevo; el esquema de identificadores; la matriz de trazabilidad y verificación; la gobernanza; la hoja de ruta de adopción; y un juego de plantillas con un ejemplo trabajado.

Fuera de alcance: la redacción de los requisitos de negocio en sí (trabajo del Manual Operativo y del equipo de negocio); la fase de pruebas formal de QA como tal, aunque esta estrategia es justamente lo que lleva al sistema hasta su umbral; y la decisión sobre los puntos pendientes del Manual.

## 1.3 Por qué Spec Kit y no BMAD

El proyecto tiene BMAD instalado (versión 6.6.0, 41 skills) y lo ha usado durante 18 sprints. La auditoría, sin embargo, mostró que el equipo se alejó del pipeline canónico de BMAD: abandonó el workflow de creación de historias, escribe informes de cierre a posteriori y marca el estado a mano. Esa deriva es la señal de que BMAD pesa demasiado para el tamaño de este equipo.

Spec Kit va en la dirección contraria. Es ligero —nueve comandos en lugar de un reparto de agentes y decenas de skills—, está respaldado por GitHub, es agnóstico del agente de IA (más de 30 integraciones) y funciona de forma nativa con Claude Code, que es lo que el proyecto ya usa. Su modelo mental cabe en una línea: constitución, spec, plan, tareas, implementación.

Un matiz importante reduce el coste del cambio: las historias ya implementadas no necesitan ninguna herramienta de planificación —ya son código—; lo que necesitan es verificación. El valor de la herramienta es de aquí en adelante. Por eso migrar a Spec Kit no tira por la borda el trabajo hecho.

> **NOTA AL EQUIPO · CONFIRMAR CON UN PILOTO**
>
> La adopción de Spec Kit es una recomendación, no un hecho consumado. Spec Kit nació orientado a proyectos nuevos (greenfield) y br-mt-ecommerce ya es un código existente grande (brownfield); ese es su punto relativamente débil. Se recomienda confirmarlo con un piloto: aplicar Spec Kit a la verificación de un proceso real (ver fase F1) y decidir en firme con datos antes de comprometer al equipo por completo. El Anexo G describe la migración desde BMAD.

## 1.4 Cómo se construyó

El documento se apoya en cuatro investigaciones: las mejores prácticas de SDD y de trazabilidad de requisitos; la auditoría del uso de BMAD en el repositorio; el inventario de los requisitos dispersos; y una revisión detallada de GitHub Spec Kit. Las fuentes se listan en el Anexo H.

---

# 2. Marco de referencia: Spec-Driven Development y Spec Kit

## 2.1 Qué es Spec-Driven Development

Spec-Driven Development (SDD) invierte la relación habitual entre la especificación y el código. En lugar de escribir código y documentar después, la especificación es el artefacto primario y duradero, y el código es su expresión regenerable. La spec es el contrato: define cómo debe comportarse el sistema y es la fuente de verdad desde la que el agente de IA genera, prueba y valida el código. GitHub Spec Kit es el conjunto de herramientas que pone en práctica este método: un CLI llamado `specify` y un juego de comandos para el agente.

## 2.2 Los comandos de Spec Kit

Tras instalar Spec Kit, el agente (en este caso Claude Code) recibe nueve comandos. Los seis primeros forman el flujo principal; los tres últimos son comandos de calidad.

| Comando | Qué hace | Artefacto |
|---|---|---|
| `/speckit.constitution` | Crea o actualiza los principios rectores del proyecto. | `memory/constitution.md` |
| `/speckit.specify` | Define qué construir: historias de usuario y requisitos. Crea la carpeta de la feature. | `specs/NNN-<dom>-.../spec.md` |
| `/speckit.clarify` | Aflora y resuelve las zonas mal especificadas, antes de planificar. | Actualiza `spec.md` |
| `/speckit.plan` | Genera el plan técnico de implementación a partir de la spec. | `plan.md`, `research.md`, `data-model.md`, `contracts/` |
| `/speckit.tasks` | Deriva la lista de tareas ordenada por dependencias. | `tasks.md` |
| `/speckit.analyze` | Análisis de consistencia y cobertura entre spec, plan y tareas. | Informe (solo lectura) |
| `/speckit.implement` | Ejecuta las tareas y construye la feature. | Código fuente |
| `/speckit.checklist` | Genera listas de comprobación de calidad de la spec. | `checklists/` |
| `/speckit.taskstoissues` | Convierte las tareas en issues de GitHub. | Issues de GitHub |

## 2.3 La cadena de artefactos

La cadena de SDD es corta y clara. Cada eslabón produce un fichero que alimenta al siguiente.

| Eslabón | Descripción |
|---|---|
| **1 Constitución** | Principios y restricciones del proyecto. Gobierna todo lo demás. Vive en `memory/constitution.md`. |
| **2 Spec (`spec.md`)** | El qué: historias de usuario, requisitos funcionales, criterios de aceptación y criterios de éxito medibles. Sin tecnología. |
| **3 Plan (`plan.md`)** | El cómo: stack, arquitectura, modelo de datos, contratos. Cada decisión enlaza con un requisito. |
| **4 Tareas (`tasks.md`)** | La lista accionable, ordenada por dependencias, con rutas de fichero por tarea. |
| **5 Implementación** | El código, generado al ejecutar las tareas. |
| **6 Verificación** | Análisis de cobertura y listas de comprobación. Confirma que el código cumple la spec. |

*Frente a BMAD, la cadena es más simple: no hay un reparto de agentes ni una capa separada de épicas e historias. Las historias de usuario viven dentro de la propia spec; las tareas, en `tasks.md`.*

## 2.4 La spec como fuente de verdad

El fichero `spec.md` es el corazón del método. Contiene las historias de usuario, los requisitos funcionales, los criterios de aceptación y unos criterios de éxito medibles. Tiene dos reglas que conviene conocer. La primera: la spec describe el qué y el por qué, nunca el cómo; no se nombra tecnología, ni API, ni estructura de código (eso aparece por primera vez en el plan). La segunda: cuando la entrada es ambigua, la plantilla obliga a marcar el punto con `[NEEDS CLARIFICATION]` en lugar de adivinar. La spec incluye además una lista de aceptación —sin marcadores de aclaración pendientes, requisitos verificables, criterios de éxito medibles— que actúa de puerta antes de planificar.

## 2.5 La constitución del proyecto

La constitución es el ADN del proyecto: un conjunto de principios y restricciones no negociables. Para br-mt-ecommerce es el sitio natural para codificar las convenciones que hoy viven en el fichero `CLAUDE.md`: el stack (Next.js, FastAPI, SQLAlchemy async), las directrices de rendimiento, las reglas de migraciones. Los demás comandos comprueban su trabajo contra la constitución: el plan, por ejemplo, pasa por unas puertas (simplicidad, anti-abstracción) y, si las incumple, debe documentar la excepción.

## 2.6 Las puertas de calidad: clarify y analyze

Spec Kit codifica dos puertas de calidad como comandos:

**`/speckit.clarify`** se ejecuta antes de planificar. Hace preguntas estructuradas para reducir el riesgo de las zonas mal especificadas y registra las respuestas en la spec. Reduce el retrabajo aguas abajo.

**`/speckit.analyze`** se ejecuta después de generar las tareas y antes de implementar. Cruza spec, plan y tareas en busca de contradicciones, huecos y requisitos sin ninguna tarea que los cubra. Es de solo lectura: informa, no corrige. Es la puerta de cobertura de requisitos.

## 2.7 Los workflows YAML y las puertas de revisión humana

Spec Kit permite definir workflows: tuberías de automatización de varios pasos, reanudables, descritas en YAML. Encadenan comandos y pueden incluir pasos de tipo puerta (gate) que detienen la ejecución y esperan la aprobación de una persona. Spec Kit trae un workflow integrado, el ciclo SDD completo, que ejecuta specify, una puerta de revisión de la spec, plan, una puerta de revisión del plan, tareas e implementación. El estado de cada ejecución se guarda, de modo que un workflow pausado o fallido se puede reanudar desde el paso exacto.

## 2.8 SDD sobre un sistema ya empezado (brownfield)

Conviene ser honestos: Spec Kit nació orientado a proyectos nuevos. Sobre un código ya existente y grande —como br-mt-ecommerce— el patrón recomendado es la especificación incremental: no se intenta especificar todo el sistema de golpe, sino que se escribe una spec acotada por cada proceso o cambio, opcionalmente precedida de un `research.md` que documenta cómo funciona hoy el código. Esta limitación no es un obstáculo para esta estrategia: encaja exactamente con el trabajo proceso por proceso que el sistema necesita (capítulo 5).

---

# 3. Diagnóstico del estado actual

## 3.1 Los tres mundos desconectados

Los requisitos del proyecto existen, pero viven en tres mundos paralelos que no se referencian entre sí:

**El mundo de la documentación.** El Manual Operativo: 31 capítulos en 7 partes, todo en estado borrador, con 276 notas abiertas (92 de acción requerida, 117 de decisión pendiente, 59 de dato por confirmar, 8 de pregunta al equipo). La Parte C describe los procesos de operación como fichas de extremo a extremo de 16 campos; dos de ellos —Automatización en br-mt-ecommerce e Integraciones técnicas— son enunciados directos de requisito.

**El mundo de la ingeniería.** La carpeta `_bmad-output` del repositorio: una PRD que solo cubre la Fase 1, cinco ficheros de épicas, más de 70 ADR, documentos de diseño por módulo y unas 58 historias implementadas.

**El mundo del seguimiento.** Las hojas de cálculo de fichas DR de la carpeta de cronograma: un tercer índice, independiente de los otros dos.

## 3.2 El estado del repositorio: lo "hecho" no está verificado

Este es el punto que más hay que matizar. El fichero `sprint-status.yaml` marca todas las épicas e historias como hechas a lo largo de 18 sprints. Pero el sistema está en pleno desarrollo y no ha entrado en fase de pruebas. "Hecho" en ese fichero significa código escrito; no significa código verificado contra los requisitos, ni probado. Tratar esas 58 historias como trabajo cerrado y validado sería un error: son implementación sin contrastar.

A esto se suman siete huecos de proceso que la auditoría identificó y que esta estrategia resuelve:

| # | Hueco |
|---|---|
| 1 | No hay una especificación que cubra todo el alcance; gran parte del trabajo se condujo desde informes de investigación. |
| 2 | Los identificadores de requisito son locales a cada épica y no enlazan entre sí ni con un origen común. |
| 3 | No hay capa de trazabilidad ni de verificación: nada une una historia con un requisito ni registra si la implementación lo cumple. |
| 4 | Especificación funcional y diseño técnico están mezclados de forma inconsistente entre varios artefactos. |
| 5 | Los nombres de fichero no son canónicos; el pipeline automático no localiza sus entradas. |
| 6 | El fichero de seguimiento es internamente inconsistente y, sobre todo, su estado "hecho" no refleja verificación. |
| 7 | Hay deriva de proceso documentada: el equipo abandonó el pipeline canónico y trabaja a mano. |

## 3.3 El Manual y los requisitos dispersos

Las Partes C y D del Manual (capítulos 8 a 18) son el material listo para convertirse en specs: su plantilla de ficha de extremo a extremo está estructuralmente preparada para la extracción de requisitos. Las Partes A, B, E, F y G dependen de las decisiones pendientes. Las carpetas `06_Tecnologia_BMAD`, `08_Tecnologia_y_app` y `02_Fichas_DR` son hoy marcadores vacíos.

## 3.4 Síntesis del diagnóstico

| Dolor | Causa raíz | Qué lo resuelve |
|---|---|---|
| Trazabilidad | Tres mundos sin clave común | Identificadores unificados (§4.4) y matriz (cap. 6) |
| Artefactos incompletos | Especificación y diseño mezclados; sin definición de listo | Cadena de artefactos de Spec Kit (§4.2) y plantillas (Anexos A–D) |
| Gobernanza | Sin roles ni puertas claras | RACI (§7.2), puertas clarify/analyze y revisión (§7.3) |
| Verificación | Lo "hecho" es código sin contrastar; sistema sin probar | Flujo proceso por proceso (cap. 5) y fase F1 de verificación (cap. 9) |

---

# 4. El modelo objetivo

## 4.1 Principios rectores

1. **Un solo origen.** Todo lo que se construye o se verifica nace de un requisito con identificador.
2. **Una sola fuente de verdad.** Cada tipo de información tiene un único sitio donde vive su definición.
3. **Hecho es verificado.** Nada se da por hecho hasta que su implementación se ha contrastado contra los criterios de aceptación de su spec.
4. **El identificador es el hilo.** El identificador de requisito conecta el Manual, la spec, las tareas, el código y la prueba.
5. **SDD por defecto.** Se usa el flujo canónico de Spec Kit; las desviaciones se documentan.

## 4.2 La cadena de artefactos en br-mt-ecommerce

| Eslabón | Descripción |
|---|---|
| **1 Proceso de negocio** | La ficha de proceso del Manual Operativo. Responde al por qué. |
| **2 Constitución** | Las convenciones del proyecto (hoy en `CLAUDE.md`), codificadas una vez. |
| **3 Spec del proceso** | Una carpeta `specs/NNN-...` con su `spec.md`: historias, requisitos FR y criterios de aceptación. |
| **4 Plan técnico** | `plan.md` y sus anexos: arquitectura, modelo de datos, contratos. Enlaza con los ADR. |
| **5 Tareas** | `tasks.md`: la lista accionable, o el conjunto de comprobaciones de verificación si el proceso ya está implementado. |
| **6 Código** | La implementación. Nueva, o la ya existente que se está verificando. |
| **7 Verificación** | `analyze` y checklists. Marca el requisito como verificado o con gap en la matriz. |

## 4.3 Fuentes de verdad

| Información | Fuente de verdad única | Quién la mantiene |
|---|---|---|
| Proceso de negocio (por qué) | Manual Operativo, ficha de proceso | Equipo de negocio (MT) |
| Requisito funcional (qué) | `spec.md` del proceso, en `specs/NNN-.../` | Analista / PM |
| Convenciones del proyecto | `memory/constitution.md` | Arquitecto |
| Decisión técnica (cómo) | `plan.md` y ADR | Arquitecto |
| Estado de trazabilidad y verificación | Matriz de Trazabilidad y Verificación | Scrum Master / PM |

## 4.4 Esquema unificado de identificadores

Spec Kit aporta una trazabilidad ligera por convención: numera las carpetas de feature (`001-`, `002-`...) y las tareas dentro de `tasks.md`. Sobre esa base se añade un esquema de identificadores de requisito, que es la clave de unión de la matriz.

| Tipo | Patrón | Ejemplo | Dónde vive |
|---|---|---|---|
| Requisito funcional | `FR-<DOM>-NNN` | `FR-INV-014` | Dentro de `spec.md` |
| Requisito no funcional | `NFR-<DOM>-NNN` | `NFR-PLT-003` | Dentro de `spec.md` |
| Regla de negocio | `BR-<DOM>-NNN` | `BR-PRC-007` | Dentro de `spec.md` |
| Spec / proceso | `NNN-<dom>-<slug>` | `014-inv-caducidades` | Carpeta en `specs/` |
| Tarea | `T0NN` (dentro de su spec) | `T012` | Dentro de `tasks.md` |
| Decisión técnica | `ADR-NNN` | `ADR-042` | `docs/adr/` |

Los diez dominios (DOM): `CAT` catálogo/PIM · `PRC` pricing · `INV` inventario · `PUR` compras · `SAL` ventas · `BIL` facturación · `FIN` finanzas · `CHN` canales · `SIC` inteligencia competitiva · `PLT` plataforma. El identificador FR es la clave de unión de la matriz; vive dentro del `spec.md` del proceso y se conserva intacto en plan, tareas y pruebas.

---

# 5. El flujo proceso por proceso

Con cualquier herramienta, el trabajo real de este proyecto es ir proceso por proceso: establecer qué se pide y comprobar qué hay. Spec Kit estructura ese trabajo. El flujo tiene dos casos —verificar lo implementado y especificar lo nuevo— que convergen en la misma matriz.

## 5.1 El bucle general

La unidad de trabajo es el proceso: una ficha del Manual, o un módulo ya codificado. Para cada proceso se decide si está ya implementado (Caso A) o es nuevo (Caso B), se ejecuta el caso correspondiente y se actualiza la matriz. El sistema avanza hacia la fase de pruebas a medida que los procesos pasan a verde.

## 5.2 Caso A: proceso ya implementado (verificación)

Es el trabajo dominante de la fase F1. Para un proceso que ya tiene código:

1. Escribir la spec retrospectiva del proceso con `/speckit.specify`: qué se le pide, con sus requisitos FR y sus criterios de aceptación. Esta spec es "lo que piden", redactada desde el Manual, no desde el código.
2. Opcionalmente, generar un `research.md` que documente cómo funciona hoy el código, para tener ambas caras delante.
3. Ejecutar `/speckit.analyze` para cruzar la spec con lo que hay y detectar requisitos sin cobertura.
4. Comparar, criterio de aceptación por criterio de aceptación, lo que la spec pide contra lo que el código hace. Cada criterio queda verificado o con gap.
5. Registrar el resultado en la matriz: el proceso pasa a verificado, o a implementado con gap.
6. Para los gaps: generar plan y tareas para cerrarlos, e implementarlos.

> **NOTA · POR QUÉ ESCRIBIR LA SPEC AUNQUE EL CÓDIGO YA EXISTA**
>
> En el Caso A puede parecer redundante escribir la spec de algo ya programado. No lo es: la spec es "lo que el negocio pide", y solo teniéndola por escrito y con criterios verificables se puede afirmar que el código cumple. Sin spec, "verificar" se reduce a una opinión. La spec retrospectiva es, además, la que permite que el sistema entre algún día en una fase de pruebas con criterios objetivos.

## 5.3 Caso B: proceso nuevo

Para un proceso del Manual que aún no está implementado, el flujo es el ciclo SDD completo de Spec Kit:

1. `/speckit.specify` a partir de la ficha aprobada del Manual.
2. `/speckit.clarify` para resolver los `[NEEDS CLARIFICATION]`.
3. `/speckit.plan` para el diseño técnico.
4. `/speckit.tasks` para la lista de tareas.
5. `/speckit.analyze` como puerta de cobertura.
6. `/speckit.implement`, y verificación con checklists.

## 5.4 El cierre del lazo

En ambos casos, el último paso es el mismo y es el que cierra la brecha entre los tres mundos: se actualiza la matriz con el identificador de spec y el estado de verificación, y se anota en la ficha del Manual el identificador FR del proceso. El Manual y las specs quedan referenciándose mutuamente.

---

# 6. La Matriz de Trazabilidad y Verificación

La matriz es el registro vivo del estado real de cada requisito. Frente a una matriz de trazabilidad clásica, esta pone el acento en la verificación, porque es lo que el proyecto necesita ahora. Se entrega como fichero Excel adjunto.

## 6.1 Estructura

| Columna | Contenido |
|---|---|
| ID Requisito | `FR-<DOM>-NNN`. La clave de unión. |
| Descripción | El enunciado verificable del requisito. |
| Dominio | Uno de los diez dominios. |
| Origen (Manual) | Capítulo y ficha del Manual, o decisión de plataforma. |
| Spec | Carpeta `specs/NNN-...` que lo contiene. |
| Estado del requisito | Borrador / Revisado / Aprobado. |
| Tareas | Identificadores de tarea en `tasks.md`. |
| Diseño / ADR | ADR o sección del plan que lo gobierna. |
| Estado implementación | Pendiente / Implementado sin verificar / Implementado con gap / Verificado. |
| Resultado de verificación | Criterios verificados frente al total; descripción del gap si lo hay. |
| Prueba(s) | Casos de prueba que lo cubren. |
| Notas | Observaciones, decisiones pendientes, riesgos. |

## 6.2 Los estados de implementación

La columna de estado es la que refleja la realidad del sistema. Cuatro valores: **Pendiente** (no hay código); **Implementado sin verificar** (hay código, pero no se ha contrastado contra la spec; es el estado de casi todo lo actual); **Implementado con gap** (verificado, y la implementación no cumple algún criterio); y **Verificado** (la implementación cumple todos los criterios de aceptación). El sistema está listo para la fase de pruebas cuando no quedan requisitos en los tres primeros estados.

## 6.3 Cómo se mantiene

La matriz tiene tres momentos de actualización obligatorios: al registrar un requisito (se crea la fila), al verificar un proceso (se completan las columnas de verificación), y al cerrar un gap (el estado pasa a Verificado). Mantenerla al día forma parte de la Definición de Hecho. Responsable: el Scrum Master, con apoyo del PM.

> **NOTA · ESTADO DE LA MATRIZ ADJUNTA**
>
> La matriz adjunta se entrega prerrellenada con el inventario de lo construido. Casi todas las filas están en estado "Implementado sin verificar": es el reflejo honesto de un sistema que aún no se ha probado. El trabajo de la fase F1 es llevarlas a "Verificado". Las celdas en amarillo requieren confirmación del equipo.

---

# 7. Gobernanza: roles, responsabilidades y puertas

## 7.1 Roles

| Rol | Responsabilidad principal |
|---|---|
| Product Owner de negocio | Define y aprueba el proceso de negocio y el requisito. Lado MT. |
| Analista / PM | Escribe y mantiene las specs; ejecuta specify y clarify. |
| Arquitecto | Constitución, plan técnico, ADR. |
| Scrum Master | Tareas, matriz de trazabilidad y verificación, workflows. |
| Desarrollo | Implementación de las tareas y sus pruebas. |
| Revisión / QA | Ejecuta analyze y las verificaciones; puertas de revisión. |

> **NOTA AL EQUIPO · ASIGNACIÓN NOMINAL DE ROLES**
>
> La tabla define roles, no personas. El equipo debe nominar cada rol y, sobre todo, decidir quién ejerce de Product Owner de negocio por el lado de MT: sin él, nadie aprueba los requisitos contra los que se verifica.

## 7.2 Matriz RACI por artefacto

R = Responsable; A = Aprobador (uno solo); C = Consultado; I = Informado.

| Artefacto | PO neg. | Analista/PM | Arquit. | SM | Dev | QA |
|---|---|---|---|---|---|---|
| Proceso de negocio | A | R | C | I | I | I |
| Constitución | C | C | A/R | C | C | I |
| Spec (`spec.md`) | A | R | C | C | I | C |
| Plan técnico | I | C | A/R | C | C | I |
| Tareas (`tasks.md`) | I | C | C | A/R | R | C |
| Código | I | I | C | I | A/R | C |
| Verificación | I | C | C | C | C | A/R |
| Matriz | I | C | I | A/R | I | C |

## 7.3 Puertas de calidad

El proceso tiene cuatro puertas; ninguna se salta:

- **Puerta de constitución:** el plan se comprueba contra la constitución; las excepciones se documentan.
- **Puerta de clarificación:** antes de planificar, `/speckit.clarify`; no debe quedar ningún `[NEEDS CLARIFICATION]` sin resolver.
- **Puerta de análisis:** antes de implementar, `/speckit.analyze`; no debe haber requisitos sin tarea ni contradicciones.
- **Puerta de revisión:** en los workflows, los pasos de tipo gate detienen la ejecución y esperan aprobación humana de la spec y del plan.

La Definición de Listo de una spec: sin marcadores de aclaración pendientes, requisitos verificables, criterios de éxito medibles, origen trazado al Manual. La Definición de Hecho de un proceso: todos los criterios de aceptación verificados contra la implementación, pruebas en verde, matriz actualizada a estado Verificado.

---

# 8. Mapeo de comandos Spec Kit al flujo

| Eslabón del flujo | Comando Spec Kit | Cuándo se usa |
|---|---|---|
| Convenciones del proyecto | `/speckit.constitution` | Una vez en F0; se revisa al cambiar el stack. |
| Especificar un proceso | `/speckit.specify` | Caso A (spec retrospectiva) y Caso B (proceso nuevo). |
| Resolver ambigüedades | `/speckit.clarify` | Tras specify, antes de plan. |
| Diseño técnico | `/speckit.plan` | Para cerrar gaps y para procesos nuevos. |
| Lista de tareas | `/speckit.tasks` | Tras el plan. |
| Puerta de cobertura | `/speckit.analyze` | Verificación del Caso A, y antes de implementar en el Caso B. |
| Implementar | `/speckit.implement` | Procesos nuevos y cierre de gaps. |
| Listas de verificación | `/speckit.checklist` | Para construir las comprobaciones de aceptación. |
| Tareas a issues | `/speckit.taskstoissues` | Opcional, si se quiere seguir el trabajo en GitHub Issues. |

*El CLI `specify` se usa en F0: `specify init` configura el proyecto y elige Claude Code como agente; `specify check` valida el entorno; `specify workflow` ejecuta y reanuda los workflows.*

---

# 9. Hoja de ruta de adopción

**F0 · Instalar Spec Kit y sanear el repositorio** *(1–2 semanas)*

Deja el proyecto listo para trabajar con SDD.

- Ejecutar `specify init` con la integración de Claude Code; validar con `specify check`.
- Redactar la constitución (`/speckit.constitution`) a partir del fichero `CLAUDE.md`.
- Crear la Matriz de Trazabilidad y Verificación y dejarla en `06_Tecnologia_BMAD`.
- Congelar `_bmad-output` como archivo histórico de consulta.

**F1 · Barrido de verificación proceso por proceso** *(6–10 semanas)*

Es la fase central y la más larga. Recorre todo lo ya implementado, proceso por proceso, aplicando el Caso A del capítulo 5.

- Priorizar los procesos por dominio: catálogo, pricing, inventario, canales.
- Por cada proceso: escribir su spec retrospectiva, ejecutar analyze, verificar criterio a criterio, registrar el resultado en la matriz.
- Abrir y cerrar los gaps detectados con plan, tareas e implementación.
- La fase termina cuando la matriz no tiene requisitos sin verificar.

**F2 · Procesos nuevos del Manual** *(Continua, por capítulo)*

A medida que el negocio aprueba capítulos del Manual, se incorporan como procesos nuevos aplicando el Caso B.

- Priorizar las Partes C y D, estructuralmente listas.
- Por cada ficha aprobada, ejecutar el ciclo SDD completo.
- No convertir capítulos bloqueados por decisiones pendientes.

**F3 · Operación continua y entrada en pruebas** *(Permanente)*

El régimen estable. Cuando la matriz está verde, el sistema está listo para entrar en fase de pruebas formal.

- Todo requisito nuevo entra por el flujo proceso por proceso.
- Las puertas de calidad se aplican en cada proceso.
- La entrada en fase de pruebas se decide con la matriz, no con el calendario.

> **NOTA AL EQUIPO · F1 ES EL CAMINO CRÍTICO**
>
> La fase F1 es la más larga y la que de verdad determina cuándo el sistema puede probarse. Su duración depende del número de procesos implementados y de cuántos gaps aparezcan. Conviene empezarla con un piloto de uno o dos procesos para calibrar el esfuerzo real por proceso antes de comprometer un calendario.

---

# 10. Backlog de remediación inmediata (F0)

Acciones concretas de F0, en orden. Se recomienda ejecutarlas en una rama de trabajo controlada, con revisión.

| # | Acción |
|---|---|
| 1 | Ejecutar `specify init --integration claude` en el repositorio; resolver lo que indique `specify check`. |
| 2 | Redactar `memory/constitution.md` con `/speckit.constitution`, volcando las convenciones de `CLAUDE.md` (stack, rendimiento, migraciones). |
| 3 | Definir los diez dominios y el esquema de identificadores como sección de la constitución. |
| 4 | Crear la Matriz de Trazabilidad y Verificación (fichero adjunto) y ubicarla en `06_Tecnologia_BMAD` del repositorio MT-ME. |
| 5 | Congelar `_bmad-output` como archivo histórico; no se borra, se deja como consulta. |
| 6 | Elegir el primer proceso para el piloto de verificación de F1 y ejecutarlo de principio a fin. |
| 7 | Decidir, con el resultado del piloto, si se confirma la adopción de Spec Kit. |

---

# 11. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Spec Kit es débil en brownfield y el código de br-mt-ecommerce ya es grande. | Alto | Especificación incremental: una spec acotada por proceso, con `research.md` del código existente; nunca especificar todo de golpe. |
| F1 se alarga más de lo previsto por el volumen de gaps. | Alto | Empezar con un piloto para calibrar el esfuerzo por proceso; priorizar dominios; medir el avance con la matriz. |
| La spec retrospectiva se escribe mirando el código y no el Manual. | Alto | La spec se redacta desde la ficha del Manual; el código se mira después, en el `research.md`; el Product Owner aprueba la spec. |
| Coste de migrar desde BMAD. | Medio | No se migra el pasado: `_bmad-output` se congela como archivo. Spec Kit se usa de aquí en adelante. Ver Anexo G. |
| Doble fuente de verdad entre la spec y las hojas de seguimiento. | Medio | Regla de fuente única (§4.3); las hojas de fichas DR pasan a ser índice de seguimiento, no fuente de requisitos. |
| La adopción de Spec Kit no convence tras el piloto. | Medio | El piloto es justamente el punto de decisión; la estrategia de fondo (identificadores, matriz, gobernanza) es válida con cualquier herramienta. |

---

# Anexo A. Plantilla de spec.md

Estructura de la especificación de un proceso. La spec describe el qué, nunca el cómo.

> **Carpeta:** `specs/NNN-<dom>-<slug>/spec.md`
>
> **Título y resumen:** El proceso en una frase.
>
> **Origen:** Capítulo y ficha del Manual Operativo.
>
> **Historias de usuario:** Como `<rol>`, quiero `<capacidad>`, para `<beneficio>`.
>
> **Requisitos funcionales:** Lista de `FR-<DOM>-NNN`, enunciados verificables.
>
> **Reglas de negocio:** `BR-<DOM>-NNN` aplicables.
>
> **Criterios de aceptación:** Escenarios Dado/Cuando/Entonces, uno por comportamiento.
>
> **Criterios de éxito:** Métricas medibles de que el proceso cumple su objetivo.
>
> **Aclaraciones pendientes:** Marcadores `[NEEDS CLARIFICATION]` sin resolver.
>
> **Lista de aceptación:** Sin marcadores pendientes; requisitos verificables; criterios medibles.

# Anexo B. Plantilla de plan.md

> **Fichero:** `specs/NNN-.../plan.md` (con `research.md`, `data-model.md`, `contracts/`)
>
> **Stack y contexto técnico:** Tecnologías; aquí aparece el cómo por primera vez.
>
> **Cumplimiento de la constitución:** Puertas superadas o excepciones documentadas.
>
> **Arquitectura:** Componentes y su relación.
>
> **Modelo de datos:** Entidades y cambios de esquema.
>
> **Contratos:** Endpoints de API afectados.
>
> **Decisiones:** ADR que genera o referencia.
>
> **Trazabilidad:** Cada decisión enlaza con los FR que habilita.

# Anexo C. Plantilla de tasks.md

> **Fichero:** `specs/NNN-.../tasks.md`
>
> **Tareas:** Lista numerada T001, T002... ordenada por dependencias.
>
> **Marcado de paralelismo:** Las tareas independientes se marcan como paralelizables.
>
> **Ruta de fichero:** Cada tarea indica los ficheros concretos que toca.
>
> **Requisito cubierto:** Cada tarea referencia el `FR-<DOM>-NNN` que satisface.
>
> **Tareas de verificación:** En el Caso A, cada criterio de aceptación es una tarea de comprobación.

# Anexo D. Plantilla de constitution.md

> **Fichero:** `.specify/memory/constitution.md`
>
> **Principios:** Las reglas no negociables del proyecto.
>
> **Stack obligatorio:** Next.js 16, React 19, FastAPI, SQLAlchemy async, Celery.
>
> **Directrices de rendimiento:** Reglas de queries, carga de imágenes, cachés.
>
> **Reglas de migraciones:** Orden Supabase y luego Alembic.
>
> **Esquema de identificadores:** Los diez dominios y los patrones FR/NFR/BR.
>
> **Puertas:** Las comprobaciones que el plan debe pasar.
>
> **Proceso de enmienda:** Cómo se modifica la propia constitución.

---

# Anexo E. Ejemplo trabajado: verificación de un proceso

Ilustra el Caso A —verificar un proceso ya implementado— sobre el control de caducidades del inventario.

## E.1 La spec del proceso

`specs/014-inv-caducidades-fefo/spec.md`

**Requisito FR-INV-014:** el sistema debe alertar de los lotes próximos a caducar según la política FEFO, con antelación configurable por categoría de producto.

*Historia: como responsable de almacén, quiero recibir alertas de los lotes próximos a caducar, para retirarlos antes de que generen merma.*

**Criterios de aceptación:**

- Dado un lote con caducidad dentro de la ventana de su categoría, cuando corre el job diario, entonces se genera una alerta en el panel de inventario.
- Dado un producto sin fecha de caducidad, cuando corre el job, entonces no se genera alerta para ese producto.
- Dada una categoría con ventana configurada a 30 días, cuando un lote entra en esa ventana, entonces la alerta indica días restantes y cantidad.

## E.2 La verificación

Se ejecuta `/speckit.analyze` y se compara cada criterio contra la implementación existente (la historia `us-erp-02-05`, ya codificada). Resultado del ejemplo:

| Criterio | Implementación | Resultado |
|---|---|---|
| Alerta del job diario | El job existe y genera la alerta | Verificado |
| Producto sin caducidad no alerta | Comprobado en código | Verificado |
| Ventana configurable por categoría | El código usa una ventana fija de 60 días; no es configurable | **Gap** |

## E.3 El resultado en la matriz

`FR-INV-014` queda en estado "Implementado con gap": 2 de 3 criterios verificados. El gap —la ventana configurable por categoría— genera su plan y sus tareas, se implementa, y entonces el requisito pasa a "Verificado". Sin la spec escrita, ese gap habría llegado invisible a la fase de pruebas.

---

# Anexo F. Comandos y layout de ficheros de Spec Kit

## F.1 Estructura que crea Spec Kit

```
.specify/
  memory/constitution.md     principios del proyecto
  templates/                 plantillas de spec, plan, tasks
  scripts/                   scripts de apoyo

specs/
  014-inv-caducidades-fefo/
    spec.md                  el qué
    plan.md                  el cómo
    tasks.md                 las tareas
    research.md              (opcional) el código existente
    checklists/              listas de verificación

CLAUDE.md                    contexto del agente, en la raíz
```

## F.2 Orden de los comandos

```
specify init --integration claude    (una vez, en F0)

/speckit.constitution     →  constitution.md
/speckit.specify          →  spec.md
/speckit.clarify          →  actualiza spec.md
/speckit.plan             →  plan.md + anexos
/speckit.tasks            →  tasks.md
/speckit.analyze          →  informe de cobertura
/speckit.implement        →  código
```

---

# Anexo G. Migración desde BMAD

La migración no consiste en convertir el pasado, sino en cambiar de herramienta para el trabajo futuro.

- **Lo construido:** el directorio `_bmad-output` se congela y se conserva como archivo histórico de consulta. No se borra ni se convierte.
- **Las historias:** las historias de BMAD ya codificadas se tratan como procesos del Caso A: se les escribe una spec retrospectiva y se verifican. No se migran como artefactos.
- **Los ADR:** los ADR existentes se conservan; se unifican en `docs/adr/` y se referencian desde los nuevos `plan.md`.
- **Las convenciones:** las convenciones de `CLAUDE.md` pasan a la constitución de Spec Kit.
- **La estrategia:** el esquema de identificadores, la matriz y la gobernanza son agnósticos de la herramienta y se conservan tal cual.

Conviven sin conflicto: BMAD y Spec Kit escriben en carpetas distintas. Durante el piloto pueden coexistir; la decisión de desinstalar BMAD se toma solo cuando el equipo confirma la adopción.

---

# Anexo H. Glosario y referencias

## H.1 Glosario

| Término | Significado |
|---|---|
| SDD | Spec-Driven Development. Método en que la especificación es el artefacto primario y el código su expresión regenerable. |
| Spec Kit | El conjunto de herramientas de GitHub que implementa SDD: el CLI `specify` y los comandos del agente. |
| Constitución | Fichero con los principios y restricciones no negociables del proyecto. |
| Spec | La especificación de un proceso o feature: el qué, con requisitos y criterios de aceptación. |
| Plan | El diseño técnico derivado de la spec: el cómo. |
| Brownfield | Trabajo sobre un código ya existente, frente a greenfield (proyecto nuevo). |
| Gap | Diferencia entre lo que un criterio de aceptación pide y lo que la implementación hace. |
| `FR-<DOM>-NNN` | Identificador de requisito funcional; la clave de unión de la matriz. |

## H.2 Referencias

- GitHub Spec Kit, repositorio oficial — github.com/github/spec-kit
- Spec-Driven Development, metodología completa — github.com/github/spec-kit, `spec-driven.md`
- GitHub Spec Kit, documentación — github.github.io/spec-kit
- Spec Kit, referencia de workflows — github.github.io/spec-kit/reference/workflows
- *Diving Into Spec-Driven Development With GitHub Spec Kit* — Microsoft for Developers
- *Spec-driven development with AI: get started with a new open source toolkit* — The GitHub Blog
- Auditoría interna del repositorio br-mt-ecommerce y del repositorio MT-ME, mayo de 2026
