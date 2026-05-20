# Products Module Audit — Plan de Análisis

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:dispatching-parallel-agents` to execute Tracks A–E in parallel. Each track produces a self-contained report in `_bmad-output/analysis/products-module/`. Run the Consolidation task only after all parallel tracks complete.

**Goal:** Producir un diagnóstico completo del módulo de productos (catálogo, fichas, series) en sus dimensiones de funcionalidad, UX/usabilidad, seguridad, performance y calidad de código, con hallazgos priorizados por impacto.

**Architecture:** El módulo de productos abarca frontend (`/catalogo`, `/fichas`, `/products`, `/series`) con hooks React Query y API client, y backend con rutas FastAPI (`products.py`, `products_display.py`, `ficha_enrich.py`, `attributes.py`, `taxonomy_*`, `translations_workflow.py`). Cada track de análisis es independiente y puede ejecutarse en paralelo sobre la rama `analysis/products-module-audit`.

**Tech Stack:** Next.js 16 + React 19 + TypeScript + Tailwind v4 + React Query; FastAPI + SQLAlchemy 2.0 async + Pydantic; Supabase Auth; Celery (enrichment workers).

**Output dir:** `_bmad-output/analysis/products-module/`

---

## Scope del módulo de productos

### Frontend
| Área | Ruta | Descripción |
|------|------|-------------|
| Catálogo (lista) | `app/(app)/catalogo/page.tsx` + `_components/` | Grid/tabla, filtros, facets, búsqueda, vistas guardadas |
| Detalle producto | `app/(app)/catalogo/[sku]/` | Header, specs, tabs (audit/costos/datasheets/edit/enriquecer/imagenes/mercados/recambios/traducciones/unidades) |
| Creación | `app/(app)/catalogo/nuevo/page.tsx` | Wizard de producto nuevo |
| Validación | `app/(app)/catalogo/validacion/` | Flujo de validación de calidad |
| Fichas | `app/(app)/fichas/` | Visualización de fichas técnicas |
| Series | `app/(app)/series/[code]/` | Detalle de serie |
| Products (legacy?) | `app/(app)/products/` | Página alternativa de productos |

### Backend
| Área | Archivo | Descripción |
|------|---------|-------------|
| CRUD productos | `api/routes/products.py` | Endpoints principales |
| Display/PIM | `api/routes/products_display.py` | Endpoints de presentación |
| Enrichment | `api/routes/ficha_enrich.py` | Pipeline de enriquecimiento LLM |
| Atributos/EAV | `api/routes/attributes.py` | Sistema EAV |
| Dimensiones | `api/routes/dimensions.py` | Dimensiones físicas |
| Taxonomía | `api/routes/taxonomy_registry.py`, `taxonomy_extras.py` | Clasificación |
| Traducciones | `api/routes/translations_workflow.py` | Workflow i18n |
| Asset links | `api/routes/asset_links.py` | Vinculación de imágenes/docs |

---

## Track A — Funcionalidad Backend (agente independiente)

**Agente lee:** `mt-pricing-backend/app/api/routes/products.py`, `products_display.py`, `ficha_enrich.py`, `attributes.py`, `dimensions.py`, `taxonomy_registry.py`, `taxonomy_extras.py`, `translations_workflow.py`, `asset_links.py`; también `app/services/` y `app/repositories/` relacionados con productos; `tests/api/` para productos.

**Output:** `_bmad-output/analysis/products-module/track-a-backend-functionality.md`

- [ ] **A1: Mapear todos los endpoints del módulo de productos**

  Leer cada archivo de ruta listado arriba. Para cada endpoint registrar:
  ```
  METHOD /path → función → HTTP codes devueltos → tiene test en tests/api/?
  ```
  Buscar en `tests/api/` archivos relacionados con products, ficha, attributes, dimensions.

- [ ] **A2: Verificar cobertura de tests**

  Cruzar la lista de endpoints del paso A1 con los tests existentes.
  Identificar: endpoints sin ningún test, endpoints con test sólo del happy path, endpoints con tests de error.
  Anotar cobertura estimada (%).

- [ ] **A3: Revisar lógica de negocio en services**

  Leer los services invocados por las rutas de productos (buscar en `app/services/` con grep de imports desde las rutas).
  Verificar: ¿hay validaciones de estado (ej. no se puede publicar sin imagen)? ¿Hay transiciones de estado definidas? ¿Hay reglas de negocio hardcodeadas vs configurables?

- [ ] **A4: Revisar manejo de errores**

  Para cada ruta: ¿qué pasa si el SKU no existe (404 correcto)?¿Si falla el enrichment (task Celery)?¿Si hay conflicto de datos?
  Anotar casos donde el error devuelto es genérico 500 en lugar de 4xx específico.

- [ ] **A5: Revisar consistencia de esquemas Pydantic**

  Leer `app/schemas/` relacionados con productos. Verificar:
  - ¿Los campos opcionales/requeridos son coherentes entre Create/Update/Read schemas?
  - ¿Hay validadores custom (`@field_validator`) que podrían fallar silenciosamente?
  - ¿Los schemas de respuesta exponen campos que no deberían (data leakage)?

- [ ] **A6: Redactar reporte Track A**

  Crear `_bmad-output/analysis/products-module/track-a-backend-functionality.md` con secciones:
  ```
  # Track A — Funcionalidad Backend
  ## Inventario de endpoints (tabla)
  ## Cobertura de tests (% + gaps críticos)
  ## Lógica de negocio: hallazgos
  ## Manejo de errores: hallazgos
  ## Schemas: hallazgos
  ## Top 5 riesgos priorizados por impacto
  ```

---

## Track B — Funcionalidad Frontend (agente independiente)

**Agente lee:** `mt-pricing-frontend/app/(app)/catalogo/` (todos los archivos), `app/(app)/fichas/`, `app/(app)/products/`, `app/(app)/series/`, `lib/hooks/products/`, `lib/api/endpoints/products.ts`, `lib/api/types.ts`.

**Output:** `_bmad-output/analysis/products-module/track-b-frontend-functionality.md`

- [ ] **B1: Mapear flujos de usuario implementados**

  Leer `catalogo/page.tsx`, `catalogo/nuevo/page.tsx`, `catalogo/validacion/page.tsx`, `catalogo/[sku]/page.tsx`, `catalogo/[sku]/layout.tsx`.
  Documentar los flujos disponibles:
  - Búsqueda y filtrado → selección de producto
  - Creación de producto nuevo (wizard)
  - Edición de producto (`/edit`)
  - Enriquecimiento (`/enriquecer`)
  - Subida de imágenes (`/imagenes`)
  - Gestión de traducciones (`/traducciones`)
  - Ver costos, mercados, datasheets, unidades, recambios

- [ ] **B2: Verificar manejo de estados en cada tab de detalle**

  Para cada tab de detalle (`_client.tsx` + `page.tsx` de cada sub-ruta):
  - ¿Hay estado `isLoading` con skeleton?
  - ¿Hay estado `isError` con mensaje y botón de retry?
  - ¿Hay estado `isEmpty` cuando no hay datos?
  - ¿El tab muestra datos stale mientras recarga?

- [ ] **B3: Auditar uso de React Query en hooks de productos**

  Leer todos los archivos en `lib/hooks/products/`. Para cada `useQuery`:
  ```
  hook → queryKey → staleTime → gcTime → conforme con tabla CLAUDE.md?
  ```
  Tabla de referencia (de CLAUDE.md):
  - Detalle producto: staleTime ≥ 60 000
  - Listados paginados: staleTime ≥ 30 000
  - Vocabularios (series, materiales): staleTime ≥ 300 000

  Anotar cualquier hook sin `staleTime` explícito (usa default 0 = siempre refetch).

- [ ] **B4: Verificar deduplicación de queries**

  Buscar si hay múltiples componentes que hacen `useProduct(sku)` o `useProducts()` independientemente con queryKeys distintas (duplicación de requests).
  Revisar `product-wizard.tsx` (47 symbols — componente más complejo) para detectar queries anidadas.

- [ ] **B5: Revisar página `/products` vs `/catalogo`**

  Leer `app/(app)/products/page.tsx` y sus `_components/`. ¿Es una ruta legacy? ¿Duplica funcionalidad de `/catalogo`? ¿Está vinculada en la navegación?

- [ ] **B6: Redactar reporte Track B**

  Crear `_bmad-output/analysis/products-module/track-b-frontend-functionality.md`:
  ```
  # Track B — Funcionalidad Frontend
  ## Flujos implementados (tabla: flujo → estado → gaps)
  ## Estado de loading/error/empty por tab (tabla)
  ## React Query compliance (tabla staleTime)
  ## Queries duplicadas encontradas
  ## Ruta /products: ¿legacy o activa?
  ## Top 5 problemas priorizados
  ```

---

## Track C — UX / Usabilidad (agente independiente)

**Agente lee:** Todos los archivos `.tsx` en `catalogo/`, `catalogo/[sku]/`, `catalogo/_components/`, componentes de `components/domain/` si existen archivos relacionados con productos.

**Output:** `_bmad-output/analysis/products-module/track-c-ux-usability.md`

- [ ] **C1: Evaluar flujo de navegación y arquitectura de información**

  Leer `catalogo/[sku]/layout.tsx` para entender la estructura de tabs.
  Documentar: ¿cuántos tabs hay? ¿El orden es lógico para el flujo de trabajo del usuario? ¿Hay breadcrumb? ¿Hay forma de volver al catálogo?

- [ ] **C2: Revisar formulario de creación (wizard)**

  Leer `catalogo/nuevo/page.tsx` y `_components/product-wizard.tsx`.
  Evaluar:
  - ¿Cuántos pasos tiene el wizard?
  - ¿Hay validación en tiempo real o sólo al enviar?
  - ¿Se guarda progreso si el usuario recarga?
  - ¿Los mensajes de error del server se muestran al usuario?
  - ¿Los campos requeridos están marcados claramente?

- [ ] **C3: Revisar el componente de catálogo (lista)**

  Leer `catalogo/page.tsx`, `_components/catalog-filters.tsx`, `_components/facet-sidebar.tsx`, `_components/top-filter-bar.tsx`, `_components/active-filters-bar.tsx`, `_components/saved-views-bar.tsx`, `_components/paginator.tsx`.
  Evaluar:
  - ¿Los filtros activos son visibles y removibles individualmente?
  - ¿Hay indicador de total de resultados?
  - ¿La paginación muestra página actual / total?
  - ¿Hay estado vacío cuando no hay resultados?
  - ¿Las vistas guardadas tienen nombre descriptivo y se pueden borrar?

- [ ] **C4: Revisar visualización de specs del producto**

  Leer `_components/product-specs.tsx`, `product-specs-eav.tsx`, `product-specs-eav-connected.tsx`, `product-header.tsx`, `product-certificates.tsx`, `product-materials.tsx`, `product-flow-data.tsx`, `product-bore-dimensions.tsx`.
  Evaluar:
  - ¿Los datos técnicos están agrupados lógicamente?
  - ¿Hay unidades de medida visibles junto a los valores?
  - ¿Los certificados se muestran con nombre legible (no sólo código)?
  - ¿Hay tooltips o ayuda contextual para campos técnicos complejos?

- [ ] **C5: Revisar consistencia visual y accesibilidad básica**

  Para los componentes clave:
  - ¿Los botones de acción tienen texto descriptivo o sólo iconos (sin aria-label)?
  - ¿Los estados deshabilitados son visualmente distintos?
  - ¿Las tablas tienen headers con scope?
  - ¿Los inputs tienen label asociado (no sólo placeholder)?
  - ¿Los mensajes de error usan color rojo + texto (no sólo color)?

- [ ] **C6: Revisar cobertura de i18n**

  Leer los archivos de la carpeta `lib/i18n/` para entender las claves disponibles para el módulo de productos.
  Buscar en los componentes de catálogo strings hardcodeados en español/inglés que deberían estar en el sistema de traducciones.

- [ ] **C7: Redactar reporte Track C**

  Crear `_bmad-output/analysis/products-module/track-c-ux-usability.md`:
  ```
  # Track C — UX / Usabilidad
  ## Arquitectura de información: hallazgos
  ## Wizard de creación: hallazgos
  ## Catálogo (lista): hallazgos
  ## Visualización de specs: hallazgos
  ## Accesibilidad: hallazgos (con severidad: crítico/mayor/menor)
  ## i18n: strings hardcodeados encontrados
  ## Top 5 problemas priorizados por impacto en usuario
  ```

---

## Track D — Seguridad (agente independiente)

**Agente lee:** `api/deps.py`, `api/routes/products.py`, `api/routes/products_display.py`, `api/routes/ficha_enrich.py`, `app/core/middleware.py`, `middleware.ts` (frontend), `lib/api/client.ts`.

**Output:** `_bmad-output/analysis/products-module/track-d-security.md`

- [ ] **D1: Verificar autenticación en todos los endpoints de productos**

  Leer `api/deps.py` para entender las dependencias de auth (`get_current_user`, etc.).
  Para cada endpoint en `products.py` y `products_display.py`: ¿tiene `Depends(get_current_user)` u equivalente? ¿Hay algún endpoint accesible sin autenticar que no debería?

- [ ] **D2: Verificar autorización (RBAC)**

  ¿Existen checks de rol/permiso (ej. sólo admin puede crear, sólo ciertos roles pueden ver costos)?
  Buscar en `deps.py` y en las rutas: `require_role`, `check_permission`, o equivalente.
  ¿Las rutas de `ficha_enrich.py` y `products_display.py` tienen restricciones de rol?

- [ ] **D3: Revisar inyección SQL / ORM**

  En las rutas y services de productos: ¿hay algún uso de `text()` de SQLAlchemy con f-strings o concatenación de strings del usuario?
  Buscar patrones: `text(f"...")`  o `execute(f"SELECT...")`. Listar cada ocurrencia con archivo y línea.

- [ ] **D4: Revisar exposición de datos sensibles**

  ¿Las respuestas de la API de productos incluyen campos que no deberían exponerse al frontend? (ej. costos internos visibles en endpoints públicos, claves internas, IDs de proveedor).
  Revisar schemas de respuesta (`Response` models) vs. lo que retorna la BD.

- [ ] **D5: Revisar manejo de archivos (imágenes/datasheets)**

  Leer `api/routes/asset_links.py` e `imagenes/_client.tsx`.
  ¿Se valida tipo de archivo en el backend (no sólo en frontend)?
  ¿Se valida tamaño máximo?
  ¿El path de storage en Supabase es predecible/enumerable?

- [ ] **D6: Revisar el frontend (XSS, CSRF, client secrets)**

  Leer `lib/api/client.ts` y `middleware.ts`.
  ¿Se usan `dangerouslySetInnerHTML` en componentes de productos (riesgo XSS)?
  ¿Hay tokens/keys expuestos en variables `NEXT_PUBLIC_` que deberían ser server-only?
  ¿Las mutaciones usan CSRF token o dependen del mismo-origen?

- [ ] **D7: Redactar reporte Track D**

  Crear `_bmad-output/analysis/products-module/track-d-security.md`:
  ```
  # Track D — Seguridad
  ## Autenticación: endpoints sin protección (tabla)
  ## Autorización: gaps de RBAC
  ## Inyección SQL: ocurrencias (archivo:línea)
  ## Exposición de datos: campos sensibles en respuestas
  ## Manejo de archivos: vulnerabilidades
  ## Frontend: XSS/CSRF/secrets
  ## Severidad CVSS estimada por hallazgo
  ## Top 3 críticos a resolver primero
  ```

---

## Track E — Performance (agente independiente)

**Agente lee:** `api/routes/products.py`, `api/routes/products_display.py`, `api/routes/attributes.py`, `api/routes/dimensions.py`, `app/repositories/` (archivos de productos), `lib/hooks/products/`, `app/(app)/catalogo/page.tsx`, `_components/products-table.tsx`, `_components/product-grid-card.tsx`.

**Output:** `_bmad-output/analysis/products-module/track-e-performance.md`

- [ ] **E1: Detectar queries N+1 en el backend**

  Leer las rutas y repositories de productos.
  Buscar patrones de: queries secuenciales en loops, `await session.get()` dentro de un for, subqueries que podrían ser JOINs.
  Referencia del CLAUDE.md:
  ```python
  # ❌ 2 round-trips al DB
  model_id = (await session.execute(select(Product.model_id).where(...))).scalar()
  rows = await session.execute(select(Cert).where(Cert.model_id == model_id))

  # ✅ 1 round-trip
  subq = select(Product.model_id).where(...).scalar_subquery()
  rows = await session.execute(select(Cert).where(Cert.model_id == subq))
  ```

- [ ] **E2: Verificar uso correcto de selectinload vs joinedload**

  Buscar todos los `options(` en las queries de productos.
  Para cada relación verificar: ¿es colección (N filas) → debe ser `selectinload`? ¿Es 1:1 → debe ser `joinedload`?
  Anotar errores (ej. `joinedload` en colección → cartesian product).

- [ ] **E3: Verificar `include_total` en listados**

  En el endpoint de listado de catálogo (`/products` o `/catalogo`): ¿usa `include_total`? ¿Está en `False` por defecto según CLAUDE.md?
  Buscar en `pagination.py` y en los endpoints que usen paginación.

- [ ] **E4: Auditar staleTime en hooks del módulo de productos**

  Leer todos los hooks en `lib/hooks/products/` y los hooks usados en `/catalogo`.
  Crear tabla:
  ```
  Hook | queryKey | staleTime configurado | ¿Cumple CLAUDE.md?
  use-products.ts | [...] | X ms | ✅/❌
  use-product.ts | [...] | X ms | ✅/❌
  ```

- [ ] **E5: Revisar carga de imágenes en catálogo**

  Leer `product-grid-card.tsx` y la página de detalle `catalogo/[sku]/page.tsx`.
  Para cada `<img>`:
  - ¿Primera imagen del detalle tiene `fetchPriority="high"`?
  - ¿Imágenes en grid/lista tienen `loading="lazy"`?
  - ¿Se usa `<Image>` de Next.js sin `width`/`height` explícito?

- [ ] **E6: Revisar CacheControl del backend**

  Leer `app/core/middleware.py` para verificar que `CacheControlMiddleware` está activo.
  En las rutas de productos: ¿algún endpoint sobreescribe el header manualmente? ¿Los endpoints de mutación (POST/PATCH/DELETE) no tienen `Cache-Control` inapropiado?

- [ ] **E7: Redactar reporte Track E**

  Crear `_bmad-output/analysis/products-module/track-e-performance.md`:
  ```
  # Track E — Performance
  ## Queries N+1 encontradas (archivo:línea + impacto estimado)
  ## selectinload/joinedload: errores encontrados
  ## include_total: estado actual
  ## React Query staleTime compliance (tabla completa)
  ## Imágenes: problemas de loading strategy
  ## CacheControl: estado
  ## Top 5 cuellos de botella priorizados por impacto
  ```

---

## Track F — Calidad de Código (agente independiente)

**Agente lee:** `app/(app)/catalogo/_components/product-wizard.tsx` (47 símbolos — el más complejo), `catalogo/page.tsx`, `catalogo/[sku]/layout.tsx`, los 10 hooks de productos, `api/routes/products.py`, `api/routes/products_display.py`.

**Output:** `_bmad-output/analysis/products-module/track-f-code-quality.md`

- [ ] **F1: Analizar complejidad de product-wizard.tsx**

  Leer el archivo completo. Anotar:
  - ¿Cuántas líneas tiene?
  - ¿Cuántos hooks usa (`useState`, `useEffect`, hooks custom)?
  - ¿Hay lógica de negocio mezclada con presentación?
  - ¿Hay efectos con dependencias sospechosas (array vacío, dependencias que deberían actualizarse)?
  - ¿Hay cualquier `any` en TypeScript?

- [ ] **F2: Revisar consistencia de patrones en hooks de productos**

  En `lib/hooks/products/`: ¿todos los hooks usan el mismo patrón (React Query v5 `useQuery`/`useMutation`)? ¿Hay hooks que usen `useEffect` + `useState` para fetching en lugar de React Query?

- [ ] **F3: Revisar TypeScript strictness**

  En los archivos clave del módulo: buscar `any`, `as any`, `// @ts-ignore`, `// @ts-expect-error`.
  Listar cada ocurrencia con archivo y línea.

- [ ] **F4: Detectar código duplicado**

  ¿Hay lógica similar repetida en múltiples tabs de `[sku]/`? (ej. el mismo fetch pattern copiado en `costos/_client.tsx`, `mercados/_client.tsx`, etc.)
  ¿Hay utilidades que podrían moverse a `lib/` pero están inlined?

- [ ] **F5: Revisar el patrón page.tsx + _client.tsx**

  ¿Todos los tabs siguen el mismo patrón server component (`page.tsx`) → client component (`_client.tsx`)? ¿Hay tabs que deberían ser client pero son server o viceversa?

- [ ] **F6: Revisar calidad del backend (products.py + products_display.py)**

  - ¿Las rutas tienen docstrings o son auto-documentadas vía tipos?
  - ¿Hay rutas con más de 50 líneas que podrían refactorizarse a services?
  - ¿Hay duplicación entre `products.py` y `products_display.py`?

- [ ] **F7: Redactar reporte Track F**

  Crear `_bmad-output/analysis/products-module/track-f-code-quality.md`:
  ```
  # Track F — Calidad de Código
  ## product-wizard.tsx: análisis de complejidad
  ## TypeScript: usos de `any` (tabla archivo:línea)
  ## Código duplicado: hallazgos
  ## Patrones inconsistentes: hallazgos
  ## Backend: rutas que necesitan refactor
  ## Deuda técnica total: estimación (horas)
  ## Top 5 refactors de mayor impacto
  ```

---

## Task G — Consolidación (ejecutar DESPUÉS de Tracks A–F)

**Agente lee:** Los 6 reportes de `_bmad-output/analysis/products-module/`.

**Output:** `_bmad-output/analysis/products-module/00-resumen-ejecutivo.md`

- [ ] **G1: Agregar todos los hallazgos en una matriz de impacto**

  Crear tabla con todos los hallazgos de los 6 tracks:
  ```
  | ID | Track | Hallazgo | Severidad (Crítico/Alto/Medio/Bajo) | Esfuerzo (h) | Quick win? |
  ```

- [ ] **G2: Identificar los 10 problemas más críticos**

  Seleccionar los ítems de mayor severidad × menor esfuerzo. Estos son el backlog prioritario.

- [ ] **G3: Identificar quick wins (< 2h)**

  Filtrar hallazgos que se pueden corregir en menos de 2 horas. Estos van a un sprint de deuda técnica exprés.

- [ ] **G4: Proponer plan de remediation**

  Para los 10 críticos: proponer qué epics/stories crear, en qué orden abordarlos, y qué requiere spike técnico vs. implementación directa.

- [ ] **G5: Redactar resumen ejecutivo**

  Crear `_bmad-output/analysis/products-module/00-resumen-ejecutivo.md`:
  ```
  # Auditoría Módulo de Productos — Resumen Ejecutivo
  **Fecha:** 2026-05-20
  **Rama:** analysis/products-module-audit

  ## Estado general del módulo (semáforo por dimensión)
  | Dimensión | Estado | Issues críticos |
  |-----------|--------|----------------|
  | Funcionalidad Backend | 🟡 | X |
  | Funcionalidad Frontend | 🟡 | X |
  | UX/Usabilidad | 🔴 | X |
  | Seguridad | 🔴 | X |
  | Performance | 🟡 | X |
  | Calidad de Código | 🟡 | X |

  ## Top 10 hallazgos críticos (tabla)
  ## Quick wins (< 2h)
  ## Plan de remediation propuesto
  ## Próximos pasos recomendados
  ```

---

## Ejecución paralela — Resumen

```
┌─────────────────────────────────────────────────┐
│           FASE 1 — Paralelo (Tracks A–F)        │
│                                                 │
│  Track A   Track B   Track C   Track D   Track E   Track F
│  Backend   Frontend  UX/UX     Security  Perf    Code Quality
│  Func.     Func.     Usab.     Audit     Audit   Audit
│                                                 │
└──────────────────┬──────────────────────────────┘
                   │ (todos terminados)
                   ▼
           FASE 2 — Secuencial
           Track G: Consolidación + Resumen Ejecutivo
```

Cada agente de Fase 1 trabaja sólo sus archivos listados y escribe sólo su reporte.
El agente de Fase 2 sólo lee los 6 reportes y escribe el resumen.

**Tiempo estimado:**
- Fase 1 (paralelo): ~15–20 min por agente
- Fase 2 (secuencial): ~10 min
- Total wall-clock: ~25–30 min
