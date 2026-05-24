# Control del Piloto F1 — Proceso CAT (catálogo de productos)

> **Qué es este documento.** El control centralizado del piloto de la fase F1. Se
> mantiene desde Cowork. Sirve para (a) saber qué tareas componen el piloto y (b)
> **validar después** que Claude Code las completó. El prompt de ejecución vive en
> `MT-ME\_INBOX\Prompt_ClaudeCode_F1_CAT_Piloto_ES.md`.

- **Fase:** F1 — barrido de verificación proceso por proceso.
- **Proceso piloto:** Gestión del catálogo de productos (dominio **CAT**).
- **Modo de ejecución:** prompt para Claude Code en la máquina del usuario (toca repo +
  GitHub) + este control en Cowork.
- **Creado:** 2026-05-24 · **Última actualización:** 2026-05-24.
- **Estado global del piloto:** 🟡 Pendiente de ejecución.

---

## 1. Estado de las tareas

Estados: `Pendiente` · `En curso` · `Hecho (Claude Code)` · `Verificado` · `Bloqueado`.
La columna **Verificado** la cerramos desde Cowork tras revisar el repo y el PR.

| ID | Tarea | Definición de hecho | Estado | Verificado |
|----|-------|--------------------|--------|-----------|
| T0 | Preparar git | `main` actualizada, working tree limpio, rama `001-cat-...` creada | Pendiente | ☐ |
| T1 | `/speckit.specify` — spec retrospectiva | Existe `specs/001-cat-gestion-catalogo-productos/spec.md` | Pendiente | ☐ |
| T2 | Editar `spec.md` | IDs `FR-CAT-NNN`; 13 áreas del Apéndice A cubiertas; orígenes trazados | Pendiente | ☐ |
| T3 | `/speckit.clarify` | Cero marcadores `[NEEDS CLARIFICATION]` sin resolver | Pendiente | ☐ |
| T4 | Plan retrospectivo + `/speckit.analyze` | `plan.md` «as-built» presente; salida de analyze resumida en el PR | Pendiente | ☐ |
| T5 | Verificación de conformidad | `verification.md` con cada FR clasificado + evidencia `archivo:línea` | Pendiente | ☐ |
| T6 | Matriz de trazabilidad | `traceability-cat.csv` con una fila por FR | Pendiente | ☐ |
| T7 | Commit + PR | PR a `main` abierto con el «Resumen de estado» en la descripción | Pendiente | ☐ |

## 2. Inventario de requisitos esperados (FR-CAT)

El `spec.md` debe cubrir, como mínimo, estas 13 áreas. Sirve para validar que la spec no
deja huecos. Tras la ejecución, anotar aquí cuántos FR-CAT generó cada área.

| Área | Capacidad | Endpoint principal | FR generados |
|------|-----------|--------------------|:---:|
| A1 | Alta de producto | `POST /products` | — |
| A2 | Consulta de ficha por SKU | `GET /products/{sku}` | — |
| A3 | Ficha resuelta (fallback al padre) | `GET /products/{sku}/resolved` | — |
| A4 | Listado del catálogo | `GET /products` | — |
| A5 | Búsqueda rápida | `GET /products/search` | — |
| A6 | Facetas | `GET /products/facets` | — |
| A7 | Edición parcial | `PATCH /products/{sku}` | — |
| A8 | Reemplazo de ficha (optimistic locking) | `PUT /products/{sku}` | — |
| A9 | Calidad de dato | `PATCH /products/{sku}/data-quality` | — |
| A10 | Baja lógica | `DELETE /products/{sku}` | — |
| A11 | Clasificación PVF | `POST /products/classify` | — |
| A12 | Jerarquía de variantes | `POST /products/{sku}/parent` | — |
| A13 | Transversales (RBAC, RFC 7807, audit, export, schema) | varios | — |

## 3. Matriz de trazabilidad — CAT

Se rellena tras la ejecución, desde `traceability-cat.csv`. Es el extracto CAT que debe
volcarse a la matriz maestra `Matriz_Trazabilidad_Verificacion_SpecKit.xlsx`.

Estados de verificación: `Verificado` · `Parcial` · `No cumple` · `No implementado` ·
`Sin verificar`.

| FR-CAT | Descripción | Origen | Estado | Evidencia | Brecha / Hallazgo BMAD |
|--------|-------------|--------|--------|-----------|------------------------|
| _(pendiente de ejecución)_ | | | Sin verificar | | |

**Recuento (rellenar):** Verificado __ · Parcial __ · No cumple __ · No implementado __.

## 4. Criterios de validación del piloto

Lista de comprobación que cierra el control. Desde Cowork (o Claude Code) se verifica
contra el repo y el PR. El piloto está **Verificado** sólo cuando todo está marcado.

- [ ] La rama `001-cat-gestion-catalogo-productos` existe y `main` no fue tocada.
- [ ] Existe `specs/001-cat-gestion-catalogo-productos/` con `spec.md`, `plan.md`,
      `verification.md` y `traceability-cat.csv`.
- [ ] `spec.md` usa el esquema `FR-CAT-NNN` (no `FR-001` genérico) y cubre las 13 áreas.
- [ ] `spec.md` no contiene marcadores `[NEEDS CLARIFICATION]` sin resolver.
- [ ] Cada FR-CAT en `verification.md` tiene estado + evidencia `archivo:línea`.
- [ ] `traceability-cat.csv` tiene una fila por cada FR-CAT del spec (sin huecos).
- [ ] El PR a `main` está abierto, con CI en verde y el «Resumen de estado».
- [ ] No hay cambios en código de aplicación — sólo archivos bajo `specs/` (regla R4).
- [ ] Los aprendizajes del flujo Spec Kit retrospectivo están registrados.

## 5. Notas y decisiones abiertas

> **NOTA 1 — Frontera del proceso.** El alcance piloto (la ficha de producto: CRUD +
> búsqueda + clasificación, ≈14 endpoints) es una propuesta razonada. Falta confirmarlo
> contra la cola de 24 procesos del documento F0 (`F0_SpecKit_Arranque_y_Bloqueos_ES.md`),
> que no estaba a la vista al redactar este control. Si el F0 nombra el primer proceso
> CAT de otro modo, ajustar slug y alcance en el prompt y aquí.

> **NOTA 2 — Hogar de la matriz maestra.** `Matriz_Trazabilidad_Verificacion_SpecKit.xlsx`
> se entregó en `_INBOX` pero no tiene una ubicación estable. Decisión pendiente:
> versionarla en el repo (p. ej. `specs/_matriz/`) o mantenerla en `MT-ME\F1-Control\`.
> Hasta resolverlo, la fuente de verdad por proceso es el `traceability-cat.csv` del repo.

> **NOTA 3 — F1 es verificación, no remediación.** El piloto NO corrige código. Las
> brechas (Parcial / No cumple / No implementado) se documentan y se vuelven issues o
> historias futuras. La auditoría BMAD de deuda técnica
> (`_bmad-output/analysis/products-module/`) ya cataloga 40 hallazgos de calidad; F1 los
> cruza por la lente de conformidad funcional, no los duplica.

> **NOTA 4 — Sub-procesos CAT futuros.** Quedan fuera del piloto y son procesos F1
> propios: traducciones, imágenes/assets, compatibilidad, materiales, conexiones,
> certificados, flow-data, tablas técnicas, releases por mercado, conversiones UoM,
> bore-dimensions y datasheets.

## 6. Bitácora

| Fecha | Evento |
|-------|--------|
| 2026-05-24 | Control creado. Prompt de Claude Code entregado en `_INBOX`. Piloto listo para ejecutar. |
| 2026-05-24 | Estrategia de pruebas añadida: marco estratégico, plan de pruebas F1-CAT y prompt de automatización de pruebas. |

---

### Enlaces

- Prompt de verificación: `MT-ME\_INBOX\Prompt_ClaudeCode_F1_CAT_Piloto_ES.md`
- Prompt de automatización de pruebas: `MT-ME\_INBOX\Prompt_ClaudeCode_F1_CAT_Pruebas_ES.md`
- Estrategia de pruebas: [[Estrategia_Pruebas_Validacion_SpecKit_ES]]
- Plan de pruebas del piloto: [[F1-CAT_Plan_de_Pruebas]]
- Constitución del proyecto: `br-mt-ecommerce\.specify\memory\constitution.md`
- Auditoría BMAD del módulo: `br-mt-ecommerce\_bmad-output\analysis\products-module\`
- PRD origen: `br-mt-ecommerce\_bmad-output\planning-artifacts\prd-mt-pricing-mdm-phase1.md`
