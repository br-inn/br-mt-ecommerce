---
stepsCompleted: [1, 2, 3, 4]
inputDocuments: []
session_topic: 'Revisión UX completa del módulo Productos — vista tabla y vista detalle'
session_goals: 'Generar ideas para mejorar usabilidad, visualización de datos, jerarquía de información y profesionalismo del módulo productos'
selected_approach: 'ai-recommended'
techniques_used: ['Assumption Reversal', 'SCAMPER Method', 'Solution Matrix']
ideas_generated: [50]
session_active: false
workflow_completed: true
---

# Brainstorming Session Results

**Facilitador:** psierra
**Fecha:** 2026-05-17

## Session Overview

**Tema:** Revisión UX completa del módulo Productos — vista tabla y vista detalle

**Goals:**
- Mejorar la usabilidad de la vista tabla (listado de productos)
- Mejorar la vista detalle de cada artículo
- Validar qué datos se muestran y en qué orden
- Proponer una solución profesional, usable y con información bien organizada

### Session Setup

_Sesión nueva iniciada el 2026-05-17. Enfoque: módulo productos del sistema mt-pricing-backend / frontend Next.js._

---

## Técnicas Utilizadas

**Enfoque:** AI-Recommended · 3 técnicas en secuencia

1. **Assumption Reversal** — Diagnóstico: supuestos de diseño invertidos para abrir el espacio de soluciones
2. **SCAMPER Method** — Generación sistemática: 7 lentes aplicadas sobre componentes concretos del UI
3. **Solution Matrix** — Convergencia: organización por impacto/esfuerzo y propuesta en 3 fases

**Insight de partida del usuario:** *"El scroll infinito no permite ver claramente la taxonomía de los productos"* → detonó toda la línea de exploración sobre navegación taxonómica.

---

## Inventario Completo de Ideas

### Assumption Reversal — Supuestos invertidos

**[Tabla #1]** El scroll infinito rompe la percepción de taxonomía
_Concepto:_ Cuando la tabla carga filas infinitas sin agrupación visual, el usuario ve una lista plana de SKUs — no ve la jerarquía familia → serie → producto. La estructura del catálogo desaparece en la planitud del scroll.
_Novedad:_ No es un problema de paginación — es pérdida de contexto estructural.

**[Tabla #2]** Los filtros son el mapa, pero están escondidos como herramienta
_Concepto:_ Los filtros actuales son funcionales pero no comunican la estructura del catálogo. El usuario tiene que saber qué familia existe para filtrarla — no puede descubrirla navegando.
_Novedad:_ Los filtros actúan como buscador avanzado, no como navegación de estructura.

**[Tabla #3]** Filtros como drill-down de zoom taxonómico
_Concepto:_ La vista del catálogo tiene 3 niveles automáticos. Sin filtro: familias con conteos. Seleccionando familia: series dentro de ella. Seleccionando serie: tabla flat de SKUs técnicos. Los filtros activos = posición en el árbol.
_Novedad:_ El filtro deja de ser "restricción" y se convierte en "navegación con memoria de posición".

**[Tabla #4]** Breadcrumb de posición taxonómica como filtro interactivo
_Concepto:_ `Productos > Ball Valves > S4000 > DN25` completamente clickeable para subir niveles. Cada segmento es un nodo del árbol, no un chip que desaparece.
_Novedad:_ El usuario nunca se pierde — siempre sabe dónde está y puede hacer back sin perder contexto.

**[Tabla #5]** Panel izquierdo de taxonomía persistente con counts en tiempo real
_Concepto:_ Panel fijo ~220px mostrando árbol División → Familia → Serie. Los counts se actualizan con cualquier filtro adicional. Si filtro "DN25", el panel muestra cuántos SKUs DN25 hay en cada familia/serie.
_Novedad:_ Combina faceted navigation (Elasticsearch) con árbol jerárquico — orientación en dos modos simultáneamente.

**[Tabla #6]** Toggle Vista Árbol / Vista Tabla con estado persistido por usuario
_Concepto:_ Control en el header `⊞ Tabla | 🌲 Árbol` que cambia el modo. Vista Tabla = comportamiento actual mejorado. Vista Árbol = panel lateral + grupos colapsables. Estado guardado en localStorage / saved views.
_Novedad:_ No rompe el flujo del power-user mientras habilita la navegación exploratoria.

**[Tabla #7]** Jerarquía visual dentro de la fila — primario / secundario / meta
_Concepto:_ Celdas de cada fila en 3 pesos visuales. Primario (bold, ink1): SKU + Nombre. Secundario (regular, ink2): Familia + Serie + Material. Meta (small, ink4): División + Estado + Calidad + Trad + Fecha.
_Novedad:_ No se quitan columnas — se rejerarquizan visualmente. Misma información, completamente diferente legibilidad.

**[Tabla #8]** Columna "Nombre" como celda compuesta de 2 líneas estructuradas
_Concepto:_ Línea 1 = nombre del producto (bold). Línea 2 = `Familia · Serie · Tipo` en texto pequeño monocromo. Elimina las columnas Familia y Serie como columnas separadas en la vista default.
_Novedad:_ Reduce de 15 columnas a ~9 visibles sin perder información.

**[Tabla #9]** Imagen como hover-preview, no como columna
_Concepto:_ Eliminar la columna img de 40px. Al hacer hover sobre una fila, aparece tooltip/popover con imagen 160x160 + nombre completo + datos clave. La tabla gana 40px para datos más importantes.
_Novedad:_ La imagen tiene más impacto en 160px que en 40px, sin ocupar columna permanente.

**[Transición #10]** El detalle no es un destino — es una extensión de la tabla
_Concepto:_ La transición tabla→detalle es un salto completo de contexto. Al navegar a `/catalogo/SKU` pierdes posición, vecinos y estado de filtros.
_Novedad:_ La desconexión entre lista y detalle obliga al usuario a usar "atrás" del browser perdiendo el estado.

**[Transición #11]** Panel lateral de detalle (split view)
_Concepto:_ Al hacer click en una fila, la tabla no navega — se divide. Mitad izquierda: tabla con fila activa resaltada. Mitad derecha: detalle del SKU. Navegar con j/k cambia el detalle en tiempo real.
_Novedad:_ Los shortcuts j/k/Enter ya están implementados — este patrón los convierte en la funcionalidad principal.

**[Transición #12]** Detalle con navegación prev/next dentro del contexto de búsqueda
_Concepto:_ El header del detalle muestra `← SKU anterior | 23 de 89 en Ball Valves DN25 | SKU siguiente →`. El contexto de filtros viaja con el usuario al detalle.
_Novedad:_ Patrón conocido en e-commerce, casi nunca en PIM internos — aquí tiene más sentido porque se comparan SKUs similares.

**[Transición #13]** Quick view como paso intermedio
_Concepto:_ Hover sobre una fila → botón "Vista rápida". Click → modal/drawer con imagen grande, specs clave, estado, acciones rápidas. Sin salir de la tabla.
_Novedad:_ Reduce el costo cognitivo de explorar un producto de 2 navegaciones a 0.

**[Detalle #14]** Los 10 tabs responden a 3 tipos de usuario completamente distintos
_Concepto:_ Pricing analyst: Mercados + Costos. PIM editor: Specs + Traducciones + Imágenes + Enriquecer. Operaciones: Recambios + Datasheets. Hoy los 10 tabs los ven todos por igual.
_Novedad:_ La información no está mal en tabs — está mal agrupada para los roles reales.

**[Detalle #15]** Tabs reorganizados: primarios (5) + secundarios en overflow
_Concepto:_ Tabs visibles: `Specs · Precios · Imágenes · Traducciones · Datasheets`. Overflow `···`: `Unidades · Recambios · Auditoría · Enriquecer`. Auditoría y Enriquecer son flujos operacionales, no de consulta.
_Novedad:_ Reduce carga cognitiva de 10 items a 5 visibles + overflow.

**[Detalle #16]** Header orientado a "estado de completitud" no a "datos de identidad"
_Concepto:_ El elemento más prominente del header es el indicador de completitud: imagen ✓, specs ✓, traducción ES ✗, precio mercado AE ✗. El `CompletenessRing` ya existe pero está diminuto.
_Novedad:_ Cambia el frame mental al abrir un producto de "ver datos" a "¿qué le falta?".

**[Detalle #17]** Quick stats en el header — los 3 números que importan
_Concepto:_ Junto al nombre, 3 métricas calculadas: `4 mercados activos · 2 imágenes · 89% completo`. Le dicen al usuario en 2 segundos si el producto está en buen estado.
_Novedad:_ Mueve el header de "formulario de datos" a "dashboard de estado del SKU".

**[Detalle #18]** Specs organizadas por "dimensiones de aplicación"
_Concepto:_ En vez de listar campos sueltos, agrupar en 3 bloques: **¿Para qué fluido?** (material, cert, temperatura), **¿Para qué presión/caudal?** (PN, pressure_max, flow data), **¿Cómo conecta?** (DN, connection, bore dimensions).
_Novedad:_ No requiere nuevos datos — solo reordenar los 8 componentes existentes con headers semánticos.

**[Detalle #19]** Specs con valor "semáforo" vs. rango de aplicación típica
_Concepto:_ `Temp máx: 120°C 🟡` (límite estándar), `Presión máx: 40 bar 🟢` (sobrado). Rangos típicos por familia — transforma datos estáticos en información interpretada.
_Novedad:_ El usuario sabe si el producto "alcanza" sin consultar a un ingeniero.

**[Tabla #20]** Acciones inline en la fila — las 2 más usadas siempre visibles
_Concepto:_ Hover sobre fila → 2 botones: `✏️ Editar` y `📋 Duplicar`. El menú ··· queda solo para Archivar, Ver historial, Exportar.
_Novedad:_ El `MoreHorizontal` actual solo navega al detalle — ni siquiera es un menú de acciones.

**[Tabla #21]** Bulk actions expandidas
_Concepto:_ Con múltiples SKUs seleccionados: `Exportar CSV · Cambiar estado lifecycle · Mover a familia · Asignar serie · Activar/Archivar`. Hoy solo exporta.
_Novedad:_ La infraestructura de selección múltiple ya existe — falta conectar las acciones.

**[Detalle #22]** Floating action bar sticky en el detalle
_Concepto:_ Al scrollear, el header desaparece con los botones de acción. Barra flotante sticky inferior: `← anterior | [SKU] | siguiente →` + `Editar · Enriquecer · Exportar`.
_Novedad:_ Resuelve simultáneamente navegación prev/next y visibilidad de acciones en scroll largo.

**[Detalle #23]** Imagen del producto como elemento de primer nivel en el header
_Concepto:_ Header en dos columnas: izquierda imagen 200x200 (o placeholder profesional), derecha nombre + KVPs + badges. Hoy no hay imagen en el header — hay que ir al tab Imágenes para ver el producto.
_Novedad:_ Un PIM sin imagen en el header del producto es como un e-commerce sin fotos.

**[Tabla #24]** Modo galería — vista grid de cards con imagen prominente
_Concepto:_ Toggle de modo incluye tercera opción `⊟ Galería`. Cards de ~160x200px con imagen arriba, SKU + nombre + familia + estado abajo. Perfecta para revisión visual o presentación.
_Novedad:_ Tres modos para tres casos de uso: Tabla=operación técnica, Árbol=exploración, Galería=visual.

**[Detalle #25]** Comparador de SKUs — abrir 2-3 en paralelo
_Concepto:_ Desde la tabla, seleccionar 2-3 SKUs → `Comparar`. Vista de comparación en columnas con diferencias resaltadas en amarillo. Especialmente útil para variantes (DN25 vs DN32 de la misma serie).
_Novedad:_ El modelo tiene `is_variant` y `parent_sku` — la comparación tiene sentido semántico.

**[UX #26]** Estado vacío inteligente con sugerencias
_Concepto:_ En vez de "Sin resultados — ajusta los filtros": *"No hay Ball Valves DN25 PN40. Hay 12 Ball Valves DN25 en PN16/PN25. ¿Ver esos?"* con botón de filtro alternativo.
_Novedad:_ El estado vacío se convierte en guía de navegación, no en dead end.

**[UX #27]** Búsqueda global tipo command palette
_Concepto:_ La barra de búsqueda activada con `/` muestra dropdown tipo command palette con resultados agrupados: `SKUs (3) · Familias (1) · Series (2)`. Click navega directo sin pasar por la tabla.
_Novedad:_ La búsqueda actual es un filtro de tabla — esto la convierte en navegación universal.

**[UX #28]** Historial de productos visitados recientemente
_Concepto:_ Dropdown `Recientes` en el header del catálogo con los últimos 5-8 SKUs visitados (localStorage). Al volver al catálogo, acceso inmediato sin refiltrar.
_Novedad:_ Patrón universal en IDEs — casi nunca en PIM internos a pesar de que los usuarios trabajan con un subset pequeño.

**[UX #29]** Indicadores de actividad reciente en la tabla
_Concepto:_ SKUs modificados en 24h → dot azul. Traducción pendiente → dot naranja. Sin imagen → dot rojo. Los dots son filtros clickeables.
_Novedad:_ Convierte la tabla en dashboard de trabajo pendiente sin agregar columnas.

**[UX #30]** Modo "revisión de calidad" — vista guiada por completitud
_Concepto:_ Saved view especial: solo SKUs con data_quality=partial/blocked, ordenados por "más fácil de completar primero". Cada fila muestra exactamente qué campos faltan.
_Novedad:_ Transforma el catálogo en herramienta de gestión de calidad de datos — flujo dedicado para PIM editor.

---

### SCAMPER Method — 7 lentes sistemáticas

**[SCAMPER #31]** S: Reemplazar scroll infinito por paginación con URL-state
_Concepto:_ Paginación real `< 1 2 3 ... 12 >`. El usuario salta a página 5, comparte URL, sabe cuántas páginas existen. El paginator ya existe — falta convertirlo en navegación real con `?page=5`.
_Novedad:_ La URL-state hace el catálogo bookmarkable y compartible entre usuarios del equipo.

**[SCAMPER #32]** S: Reemplazar tabs de texto plano por tabs con iconos + badges de alertas
_Concepto:_ Cada tab lleva icono y badge numérico cuando hay pendientes: `📐 Specs · 🌍 Mercados (3) · 🖼 Imágenes ⚠️ · 🌐 Traducciones (2 pendientes)`.
_Novedad:_ Los tabs dejan de ser solo navegación y se convierten en indicadores de estado.

**[SCAMPER #33]** S: Reemplazar toggle activo/inactivo por LifecycleStatusBadge clickeable
_Concepto:_ El toggle switch binario actual → badge de lifecycle que al hacer click abre mini-dropdown con todos los estados (`draft → in_review → active → deprecated`).
_Novedad:_ El toggle binario oculta que el producto puede estar en `in_review` o `deprecated` — estados con significado operacional distinto.

**[SCAMPER #34]** C: Fusionar búsqueda + filtros en query builder visual
_Concepto:_ Una sola barra combina texto libre y filtros estructurados como chips editables. Escribes `Ball Valves DN25 brass active` y el sistema parsea familia + DN + material + estado automáticamente.
_Novedad:_ Patrón de Linear/Notion — elimina la separación artificial entre "buscar" y "filtrar".

**[SCAMPER #35]** C: Fusionar columnas Familia + Serie + Material en celda "Clasificación"
_Concepto:_ En vez de 3 columnas separadas, una celda muestra: `Ball Valves / S4000 · Brass` en dos líneas. Libera 2 columnas de ancho para datos que hoy no caben.
_Novedad:_ La clasificación es un concepto unitario — familia/serie/material se leen siempre juntos.

**[SCAMPER #36]** C: Fusionar tab "Imágenes" con el header del detalle
_Concepto:_ La imagen principal vive en el header. Miniaturas adicionales como galería horizontal pequeña. El tab "Imágenes" se convierte en gestión avanzada (subir, ordenar) — no en la única forma de ver las fotos.
_Novedad:_ Hoy hay que navegar al tab Imágenes para ver si el producto tiene foto.

**[SCAMPER #37]** C: Fusionar "Enriquecer" + "Editar completo" en un único flujo
_Concepto:_ Hoy hay 3 formas de editar: inline edit, `/edit` page, y tab "Enriquecer". Un único panel de edición contextual que detecta si tienes PDF (enriquecimiento) o editas a mano (formulario).
_Novedad:_ Elimina la confusión de "¿edito aquí o en enriquecer?" que existe para el usuario.

**[SCAMPER #38]** A: Vista Kanban por lifecycle_status (patrón Linear/Trello)
_Concepto:_ Vista adicional en modo Kanban: columnas por estado (`Draft | In Review | Active | Deprecated`). Las cards de SKU se arrastran entre columnas para cambiar estado.
_Novedad:_ El lifecycle ya está modelado como enum con estados ordenados — el Kanban es una proyección natural.

**[SCAMPER #39]** A: SAP Fiori Object Page — el estándar de facto para PIM enterprise
_Concepto:_ Header completo según patrón SAP Fiori: imagen izquierda, title area derecha con KVPs, sección de "header facets" con mini-charts/stats. El código ya tiene el comentario `// SAP Fiori Object Page — KVP row (UX-02)` — la intención estaba, la implementación quedó incompleta.
_Novedad:_ Es el patrón que esperan usuarios que vienen de ERPs como SAP.

**[SCAMPER #40]** A: Diff view tipo GitHub en tab Auditoría
_Concepto:_ En vez de log de cambios en texto, diff visual: campos anteriores en rojo, campos nuevos en verde. Para enrichment de fichas especialmente valioso — ver exactamente qué cambió en specs tras procesar un PDF.
_Novedad:_ El audit trail ya existe en el backend — solo falta renderizarlo como diff visual.

**[SCAMPER #41]** M: Reducir el header — sacar translation pills
_Concepto:_ Los 3 translation pills en el header agregan ruido para usuarios que no gestionan traducciones. Moverlos al tab "Traducciones" como header del tab, no del producto completo.
_Novedad:_ No se pierde información — se reubica al contexto donde es relevante.

**[SCAMPER #42]** M: Ampliar columna "Nombre" al doble de ancho
_Concepto:_ Actualmente `max-w-xs` (288px) con `line-clamp-2`. Duplicar a ~500px y mostrar siempre en 1 línea clara. Los nombres de productos técnicos son largos y se truncan antes de ser legibles.
_Novedad:_ El nombre es el campo más usado para identificar — darle espacio es el cambio de mayor impacto con menos código.

**[SCAMPER #43]** M: Reordenar columnas por frecuencia de uso real
_Concepto:_ Orden propuesto: `[img] [SKU] [Nombre+clasificación] [DN] [PN] [Estado] [Calidad] [Actualizado] [···]`. División, Serie, Material, Trad → columnas opcionales o en hover/quick view. Caben en pantalla 1440px sin scroll horizontal.
_Novedad:_ La tabla actual requiere scroll horizontal en 1440px — el reorden elimina ese problema sin quitar datos.

**[SCAMPER #44]** P: Saved views como reportes compartibles por URL
_Concepto:_ Las saved views actuales (localStorage) se extienden para generar URL compartible `?view=abc123`. Se convierten en "reportes vivos" del catálogo compartibles entre usuarios del equipo.
_Novedad:_ El sistema ya está implementado — solo falta serializar el estado en URL en vez de localStorage.

**[SCAMPER #45]** P: CompletenessRing como widget en el dashboard principal
_Concepto:_ El `CompletenessRing` del detalle usado en el dashboard como widget agregado: "X% del catálogo completo · 47 SKUs sin imagen · 23 SKUs sin traducción ES".
_Novedad:_ Convierte una métrica individual en KPI de gestión del catálogo entero.

**[SCAMPER #46]** E: Eliminar columna División de la tabla
_Concepto:_ La barra de División (Todas / Hidrosanitario / Industrial) ya filtra por división. La columna es redundante cuando el filtro está activo — solo agrega ruido visual. Libera ~110px de ancho.
_Novedad:_ Eliminar esta columna libera espacio para columnas más útiles sin perder ninguna información.

**[SCAMPER #47]** E: Eliminar select inline de data_quality del header
_Concepto:_ El `<select>` nativo para cambiar data_quality junto al badge es una acción de administración mezclada con datos de consulta. Moverla al panel de edición o al menú de acciones.
_Novedad:_ El `<select>` nativo rompe el lenguaje visual del design system (usa Shadcn/ui en todo lo demás).

**[SCAMPER #48]** E: Eliminar "Editar completo" como botón separado — drawer unificado
_Concepto:_ Hoy hay `Editar (inline)` + `Editar completo (link a /edit)`. Un único `Editar` que abre un panel lateral (drawer) con todos los campos — sin navegar a otra página, sin modo inline parcial.
_Novedad:_ El drawer unificado es el patrón correcto para edición en herramientas de gestión.

**[SCAMPER #49]** R: Invertir jerarquía de tab default — imagen primero, specs después
_Concepto:_ La primera pantalla del detalle muestra imagen grande + nombre + clasificación + estado + acciones. Las specs técnicas están más abajo. La identidad visual primero, los datos técnicos después.
_Novedad:_ Las specs son para el ingeniero que ya decidió trabajar con el SKU. La imagen y el nombre son para cualquier usuario que acaba de abrirlo.

**[SCAMPER #50]** R: Invertir el enriquecimiento — sistema sugiere, usuario aprueba
_Concepto:_ En vez de que el usuario vaya al tab "Enriquecer" y suba manualmente un PDF, el sistema detecta SKUs con data incompleta y muestra: `💡 3 SKUs con ficha disponible no procesada`. El sistema propone, el usuario aprueba con un click.
_Novedad:_ Invierte de push (usuario busca enriquecer) a pull (sistema notifica oportunidades).

---

## Organización Temática

### Tema A — Navegación Taxonómica
Ideas: #1, #3, #4, #5, #6, #38
**Patrón:** El catálogo no comunica su estructura jerárquica. El scroll infinito y la tabla plana destruyen la percepción de familia → serie → SKU.
**Solución central:** Zoom taxonómico por niveles + panel árbol lateral persistente.

### Tema B — Vista Tabla: columnas e información
Ideas: #7, #8, #9, #31, #33, #42, #43, #46
**Patrón:** 15 columnas con el mismo peso visual, scroll horizontal en 1440px, imagen de 40px inútil, toggle activo binario.
**Solución central:** Jerarquía visual primario/secundario/meta + celda nombre compuesta + reorden de columnas.

### Tema C — Conexión Tabla ↔ Detalle
Ideas: #10, #11, #12, #13, #24, #25
**Patrón:** El detalle es un universo separado — pierdes posición, contexto y vecinos al abrirlo.
**Solución central:** Navegación prev/next en contexto + quick view drawer.

### Tema D — Header del Detalle
Ideas: #16, #17, #23, #39, #41, #47, #48
**Patrón:** El header mezcla identidad + estado + edición + acciones + traducción — demasiado ruido en un espacio pequeño.
**Solución central:** Imagen como primer nivel + SAP Fiori Object Page + drawer de edición unificado.

### Tema E — Tabs del Detalle
Ideas: #14, #15, #32, #36, #37, #49
**Patrón:** 10 tabs horizontales para 3 roles distintos — nadie tiene su flujo optimizado.
**Solución central:** 5 tabs primarios + overflow con badges de alerta.

### Tema F — Specs Técnicas
Ideas: #18, #19, #40
**Patrón:** Los 8 componentes de la tab default son un dump de campos sin jerarquía semántica.
**Solución central:** Specs organizadas por preguntas de aplicación + semáforos de rangos.

### Tema G — Búsqueda y Filtros
Ideas: #2, #26, #27, #34
**Patrón:** Los filtros actúan como restricciones, no como navegación. La búsqueda es un filtro de tabla, no navegación universal.
**Solución central:** Query builder visual unificado + command palette.

### Tema H — Acciones y Flujos de Trabajo
Ideas: #20, #21, #22, #50
**Patrón:** Las acciones más frecuentes están escondidas detrás del menú ···.
**Solución central:** Acciones inline en hover + bulk actions expandidas + floating action bar.

### Tema I — Productividad y Gestión de Calidad
Ideas: #28, #29, #30, #44, #45
**Patrón:** No hay herramientas de gestión de calidad ni productividad — el PIM editor no tiene flujos dedicados.
**Solución central:** Modo revisión de calidad + dots de actividad + saved views como URLs compartibles.

---

## Solution Matrix — Propuesta Priorizada

### 🟢 Fase 1 — Quick Wins (1-2 semanas)

| Idea | Cambio | Impacto | Esfuerzo |
|------|--------|---------|----------|
| #8 + #43 | Celda nombre compuesta + reorden columnas | Alto | Bajo |
| #46 | Eliminar columna División | Alto | Muy bajo |
| #15 + #32 | Tabs: 5 primarios + overflow + badges de alerta | Alto | Bajo |
| #23 | Imagen del producto en el header del detalle | Alto | Bajo |
| #41 + #47 | Sacar translation pills y select data_quality del header | Medio | Muy bajo |
| #48 | Unificar Editar + Editar completo en drawer lateral | Alto | Medio |

### 🟡 Fase 2 — Mejoras estructurales (2-4 semanas)

| Idea | Cambio | Impacto | Esfuerzo |
|------|--------|---------|----------|
| #6 + #24 | Toggle Vista Tabla / Vista Galería | Alto | Medio |
| #12 | Navegación prev/next en el detalle con contexto de filtros | Alto | Medio |
| #13 | Quick view drawer en hover de fila | Alto | Medio |
| #20 + #21 | Acciones inline en hover + bulk actions expandidas | Alto | Medio |
| #30 | Modo "revisión de calidad" como saved view especial | Alto | Bajo |
| #31 + #44 | Paginación real con URL-state + saved views compartibles | Medio | Medio |
| #26 | Estado vacío inteligente con sugerencias de filtros | Medio | Bajo |

### 🔵 Fase 3 — Rediseño profundo (1+ mes)

| Idea | Cambio | Impacto | Esfuerzo |
|------|--------|---------|----------|
| #3 + #5 | Zoom taxonómico + panel árbol lateral persistente | Muy alto | Alto |
| #34 + #27 | Query builder visual unificado + command palette | Alto | Alto |
| #18 + #19 | Specs reorganizadas por dimensiones de aplicación | Alto | Medio |
| #39 | SAP Fiori Object Page completo | Alto | Alto |
| #38 | Vista Kanban por lifecycle_status | Medio | Alto |
| #50 | Sistema sugiere enriquecimiento (pull vs. push) | Alto | Alto |

---

## Session Summary

**Total de ideas generadas:** 50
**Técnicas completadas:** Assumption Reversal · SCAMPER Method · Solution Matrix
**Insight raíz de la sesión:** El scroll infinito no es solo un problema de paginación — es un problema de pérdida de contexto taxonómico. Toda la jerarquía familia → serie → SKU del catálogo desaparece en la planitud de la lista.

**Breakthrough principal:** Los filtros no deben ser "restricciones de búsqueda" sino "niveles de zoom en la taxonomía". Cuando seleccionas una familia, deberías estar navegando el catálogo, no filtrando una tabla.

**Quick win de mayor impacto:** Reorganizar las columnas de la tabla + celda nombre compuesta. Transforma la legibilidad de la tabla sin cambiar la arquitectura. Ejecutable en horas.

**Propuesta recomendada de inicio:** Implementar Fase 1 completa como un PR de UX/polish, medir feedback de usuarios internos, y usar ese aprendizaje para priorizar dentro de Fase 2.
