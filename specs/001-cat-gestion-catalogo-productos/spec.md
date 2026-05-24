# Spec retrospectiva: Gestión del catálogo de productos (CAT)

**Feature Branch**: `001-cat-gestion-catalogo-productos`

**Creado**: 2026-05-24

**Tipo**: Retrospectivo — documenta el comportamiento ACTUAL del sistema, no funcionalidad futura.

**Estado**: Borrador

**Dominio**: CAT — Catálogo de Productos

**Input**: Spec retrospectiva del proceso EXISTENTE de gestión del catálogo de productos.
Los 14 endpoints en alcance son los del prefijo `/products` listados en el plan piloto F1.

---

## Clarificaciones

### Sesión 2026-05-24

- Q: ¿Qué `lifecycle_status` fija el soft-delete? → A: `'discontinued'` (confirmado en `product_service.py:619`)
- Q: ¿Cuántos campos físicos valida `patch_data_quality` para promover a `complete`? → A: 4 campos: `family`, `material`, `dn`, `pn`; la verificación de `name_en` vía translations está pendiente (`product_service.py:537-539`)
- Q: ¿Cuál es el objetivo de performance de facetas? → A: p95 < 200 ms con 5 000–50 000 products (código `products.py:693`); añadido como SC-009

---

## Escenarios de usuario y prueba *(obligatorio)*

### Historia de usuario 1 — Alta y gestión básica de ficha (Priority: P1)

El operador de catálogo (Comercial) crea nuevas fichas de producto en el PIM
y las mantiene actualizadas: edita campos técnicos parcialmente, reemplaza fichas
completas, cambia el estado de calidad de dato y da de baja productos obsoletos.

**Por qué esta prioridad**: Es el núcleo del PIM. Sin altas y ediciones, ningún
otro proceso (pricing, traducciones, exportación) tiene datos con los que operar.

**Prueba independiente**: Se puede verificar con POST /products + PATCH /products/{sku}
+ DELETE /products/{sku} en un entorno aislado. El resultado es un producto creado,
modificado y desactivado con auditoría completa registrada.

**Escenarios de aceptación**:

1. **Dado** que soy Comercial autenticado con permiso `products:write`,
   **Cuando** envío POST /products con `sku`, `name_en`, `family`, `brand` válidos y
   `specs` coherentes con el JSON Schema de la familia,
   **Entonces** el sistema crea el producto con `data_quality = partial` por defecto,
   emite un evento de auditoría con autor y timestamp, y devuelve `ProductDetail` con
   HTTP 201.

2. **Dado** un producto existente sin `manual_locked_fields`,
   **Cuando** envío PATCH /products/{sku} con campos a modificar (solo los enviados),
   **Entonces** el sistema actualiza solo esos campos, emite auditoría y devuelve
   `ProductDetail` actualizado con HTTP 200.

3. **Dado** un producto con `manual_locked_fields = ["dn"]`,
   **Cuando** envío PATCH /products/{sku} intentando cambiar el campo `dn`,
   **Entonces** el sistema rechaza con HTTP 409 y código `field_locked`.

4. **Dado** un producto existente con `If-Match: W/"<etag-valido>"`,
   **Cuando** envío PUT /products/{sku} con todos los campos editables,
   **Entonces** el sistema reemplaza la ficha y devuelve el nuevo `ETag` en el header.

5. **Dado** un producto existente con `If-Match: W/"<etag-obsoleto>"`,
   **Cuando** envío PUT /products/{sku},
   **Entonces** el sistema rechaza con HTTP 412 (Precondition Failed).

6. **Dado** un Comercial con permiso `products:delete`,
   **Cuando** envío DELETE /products/{sku},
   **Entonces** el sistema marca `lifecycle_status` equivalente a inactivo y
   `deleted_at = now()`, devuelve HTTP 204, y el producto no aparece en listados activos.

7. **Dado** un SKU inexistente,
   **Cuando** envío GET /products/{sku},
   **Entonces** el sistema devuelve HTTP 404 con cuerpo RFC 7807 (`ProblemDetails`).

---

### Historia de usuario 2 — Navegación y búsqueda del catálogo (Priority: P2)

El Comercial o cualquier usuario con `products:read` navega el catálogo con filtros
compuestos, busca fichas rápidamente por nombre/SKU y consulta facetas para exploración
no destructiva.

**Por qué esta prioridad**: La navegación del catálogo es la pantalla más visitada.
Sin listado funcional, el resto del sistema no es operable en el día a día.

**Prueba independiente**: Verificable con GET /products, GET /products/search y
GET /products/facets en un catálogo con datos de prueba; no requiere altas ni ediciones.

**Escenarios de aceptación**:

1. **Dado** un usuario con `products:read`,
   **Cuando** envío GET /products sin filtros,
   **Entonces** el sistema devuelve una página paginada (cursor-based, no offset),
   ordenada por SKU ASC, con hasta 50 ítems por defecto.

2. **Dado** un listado con más de 50 productos,
   **Cuando** envío GET /products?cursor=<token_opaco>,
   **Entonces** el sistema devuelve la siguiente página desde el punto correcto,
   sin duplicados ni saltos.

3. **Dado** filtros activos `family=VALVULAS&dn=50&data_quality=complete`,
   **Cuando** envío GET /products con esos filtros,
   **Entonces** el sistema devuelve solo los productos que cumplen todos los filtros
   simultáneamente.

4. **Dado** una búsqueda `q=brass gate`,
   **Cuando** envío GET /products/search?q=brass+gate,
   **Entonces** el sistema devuelve hasta 10 productos cuyo `name_en` coincide por
   trigrama o cuyo SKU tiene ese prefijo, ordenados por relevancia.

5. **Dado** un conjunto de filtros activos,
   **Cuando** envío GET /products/facets con esos mismos filtros,
   **Entonces** el sistema devuelve counts por dimensión aplicando todos los filtros
   EXCEPTO el de la propia dimensión (refinement no destructivo).

---

### Historia de usuario 3 — Herencia de specs en jerarquía de variantes (Priority: P3)

El Comercial gestiona familias de variantes donde una variante hereda specs, assets y
traducciones del producto padre cuando no las tiene propias.

**Por qué esta prioridad**: Fundamental para catálogos con variantes (DN distintos de la
misma válvula), pero no bloquea el PIM básico si está en degradado.

**Prueba independiente**: Verificable con POST /{sku}/parent + GET /{sku}/resolved en
un par padre/variante.

**Escenarios de aceptación**:

1. **Dado** un producto variante `V-50` y un padre `V-BASE`,
   **Cuando** envío POST /products/V-50/parent?parent_sku=V-BASE,
   **Entonces** el sistema valida que no hay ciclo, que la profundidad no supera 1 nivel,
   actualiza `parent_sku` y recalcula los flags `is_parent`/`is_variant`.

2. **Dado** una variante `V-50` cuyo padre `V-BASE` tiene `specs.pressure_max_bar=16`,
   y `V-50` no tiene ese campo,
   **Cuando** envío GET /products/V-50/resolved,
   **Entonces** el sistema devuelve el campo heredado del padre en el campo `specs`.

3. **Dado** que intento asignar como padre un producto que ya es variante de otro,
   **Cuando** envío POST /products/{sku}/parent,
   **Entonces** el sistema rechaza con error de profundidad máxima excedida.

---

### Historia de usuario 4 — Calidad de dato y clasificación masiva (Priority: P4)

El operador promueve fichas de `partial` a `complete` cuando cumplen los campos
obligatorios, y usa el clasificador PVF para asignar family/material/dn/pn en lote
desde `name_en`.

**Por qué esta prioridad**: Habilita los OKRs de Fase 1a (≥ 90 % SKUs `complete`)
pero puede operarse por separado del CRUD básico.

**Prueba independiente**: Verificable con PATCH /{sku}/data-quality y POST /classify.

**Escenarios de aceptación**:

1. **Dado** un SKU con todos los campos obligatorios poblados y `data_quality=partial`,
   **Cuando** envío PATCH /products/{sku}/data-quality con `{"data_quality": "complete"}`,
   **Entonces** el sistema transiciona el flag y emite auditoría.

2. **Dado** un SKU sin campos obligatorios completos,
   **Cuando** intento promover a `complete`,
   **Entonces** el sistema rechaza con HTTP 422 indicando los campos faltantes.

3. **Dado** que ejecuto POST /classify,
   **Cuando** el clasificador PVF procesa los SKUs encolados,
   **Entonces** asigna `family`, `material`, `dn`, `pn` solo a campos vacíos (no sobreescribe
   `manual_locked_fields`) y promueve a `complete` los que cumplen los 4 campos físicos requeridos (`family`, `material`, `dn`, `pn`).

---

### Historia de usuario 5 — Exportación y consulta de JSON Schema (Priority: P5)

El operador exporta el catálogo filtrado como CSV para uso offline, y la UI consulta
el JSON Schema de `specs` por familia/subfamilia para validar formularios de alta.

**Por qué esta prioridad**: Soporte operacional útil pero no crítico para el flujo
diario de PIM.

**Prueba independiente**: Verificable con GET /products/export y GET /products/specs/schema.

**Escenarios de aceptación**:

1. **Dado** un filtro activo `family=VALVULAS`,
   **Cuando** envío GET /products/export,
   **Entonces** el sistema devuelve un CSV con hasta 10 000 filas, cabecera con los
   campos canónicos, y sin cache HTTP (header `Cache-Control: no-store`).

2. **Dado** una familia `VALVULAS` con subfamilia `COMPUERTA`,
   **Cuando** envío GET /products/specs/schema?family=VALVULAS&subfamily=COMPUERTA,
   **Entonces** el sistema devuelve el JSON Schema que rige el campo `specs` para esa
   combinación, usando el fallback chain `family_subfamily → family → _default`.

---

### Casos límite

- ¿Qué ocurre al crear un SKU con uno ya existente? → HTTP 409 (`sku_conflict`).
- ¿Qué ocurre al filtrar con un cursor mal formado? → HTTP 400.
- ¿Qué ocurre al enviar `specs` que no cumple el JSON Schema de la familia? → HTTP 422.
- ¿Qué ocurre si Celery no está disponible al clasificar? → HTTP 503 (`classify_celery_unavailable`).
- ¿Qué ocurre al asignar un padre que crea un ciclo (A→B→A)? → Error de ciclo detectado.
- ¿Qué ocurre con GET /products sin autenticación? → HTTP 401/403.

---

## Requisitos *(obligatorio)*

### Requisitos funcionales

#### Área 1 — Alta de producto

- **FR-CAT-001**: El sistema DEBE permitir crear un producto con SKU como clave primaria
  (texto, máx. 64 caracteres), `name_en` obligatorio no nulo, `family` y `brand` resueltos
  a sus IDs de vocabulario, y un campo `specs` JSONB validado contra el JSON Schema de
  la familia/subfamilia en el momento de la creación.
  *Origen: PRD FR-1a-01; contrato API POST /products; código `products.py:635`.*

- **FR-CAT-002**: El sistema DEBE asignar `data_quality = partial` por defecto al crear
  cualquier producto nuevo.
  *Origen: PRD FR-1a-01 BDD; código `product.py:101`.*

- **FR-CAT-003**: El sistema DEBE emitir un evento de auditoría (autor, timestamp, acción
  "create") por cada producto creado.
  *Origen: PRD OKR O1a.4; código `product_service.py` (auditoría delegada al servicio).*

- **FR-CAT-004**: El sistema DEBE devolver HTTP 409 con código `sku_conflict` si se intenta
  crear un producto con un SKU ya existente.
  *Origen: contrato API; código `products.py:640`.*

- **FR-CAT-005**: El sistema DEBE rechazar la creación si `specs` no cumple el JSON Schema
  de la familia/subfamilia, devolviendo HTTP 422 con la lista de errores de validación.
  *Origen: contrato API; código `products.py:651-653`.*

#### Área 2 — Consulta de ficha

- **FR-CAT-006**: El sistema DEBE devolver la ficha completa de un producto por SKU
  (`GET /products/{sku}`), incluyendo traducciones cargadas por `selectinload` y assets
  (fotos) cargados de forma eficiente.
  *Origen: PRD FR-1a-01; contrato API; código `products.py:718-733`.*

- **FR-CAT-007**: El sistema DEBE devolver HTTP 404 con `ProblemDetails` (RFC 7807) para
  cualquier SKU inexistente o dado de baja.
  *Origen: contrato API; código `products.py:729`.*

- **FR-CAT-008**: La respuesta de detalle DEBE incluir `series_detail`, `material_detail`,
  `display_pair` y `model_detail` cuando los respectivos IDs de vocabulario estén
  poblados en el producto.
  *Origen: as-built; código `products.py:218-290` (`_build_product_detail`).*

#### Área 3 — Ficha resuelta

- **FR-CAT-009**: El sistema DEBE devolver una vista resuelta del producto
  (`GET /products/{sku}/resolved`) que hereda specs, assets y traducciones del producto
  padre cuando la variante no los tiene propios.
  *Origen: as-built; código `products.py:1782-1808`.*

- **FR-CAT-010**: Para un producto que no es variante (sin `parent_sku`), la ficha resuelta
  DEBE coincidir con su ficha directa sin herencia.
  *Origen: as-built; código `parent_resolver.py`.*

#### Área 4 — Listado del catálogo

- **FR-CAT-011**: El sistema DEBE soportar listado paginado con cursor opaco (base64url
  sobre SKU) ordenado por SKU ASC; el parámetro `cursor` permite avanzar páginas sin
  offset. El tamaño de página por defecto es 50, máximo 200.
  *Origen: CLAUDE.md directriz 1; contrato API; código `products.py:452-616`.*

- **FR-CAT-012**: El sistema DEBE soportar los siguientes filtros en GET /products:
  `family`, `subfamily`, `type`, `brand`, `material`, `dn`, `pn`, `data_quality`,
  `active`, `translation_status`, `lang`, `created_after`, `created_before`, `q`
  (full-text), `division`, `series_id`, `material_id`, `tier_code`.
  Todos los filtros se aplican conjuntamente (AND lógico).
  *Origen: contrato API; código `products.py:457-495`.*

- **FR-CAT-013**: El parámetro `include_total=false` DEBE ser el valor por defecto en el
  listado; el `total_count` solo se calcula cuando se solicita explícitamente.
  *Origen: CLAUDE.md directriz 4; código `products.py:491`.*

- **FR-CAT-014**: El listado DEBE incluir por cada producto `translation_status_es`,
  `translation_status_ar` y `primary_image_url` como campos computados en tiempo de
  respuesta (obtenidos en dos queries adicionales de batch, no N+1).
  *Origen: as-built; código `products.py:555-610`.*

#### Área 5 — Búsqueda rápida

- **FR-CAT-015**: El sistema DEBE ofrecer búsqueda rápida (`GET /products/search?q=<texto>`)
  combinando similitud trigramas sobre `name_en` y prefijo sobre SKU. La longitud mínima
  de la consulta es 2 caracteres; el límite de resultados es 50.
  *Origen: contrato API; código `products.py:619-632`.*

#### Área 6 — Facetas

- **FR-CAT-016**: El sistema DEBE calcular counts por dimensión (`GET /products/facets`)
  aplicando todos los filtros activos EXCEPTO el de la dimensión que se está midiendo
  (refinement no destructivo, estilo Algolia).
  *Origen: contrato API; código `products.py:661-715`.*

- **FR-CAT-017**: Las mismas dimensiones de filtro de GET /products DEBEN estar disponibles
  como parámetros de GET /products/facets.
  *Origen: as-built; código `products.py:666-715`.*

#### Área 7 — Edición parcial

- **FR-CAT-018**: El sistema DEBE aplicar PATCH parcial sobre una ficha (`PATCH /products/{sku}`)
  actualizando solo los campos presentes en el cuerpo de la petición (semantica
  `exclude_unset=True`).
  *Origen: contrato API; código `products.py:796-818`.*

- **FR-CAT-019**: El sistema DEBE rechazar con HTTP 409 y código `field_locked` cualquier
  intento de PATCH que incluya un campo presente en `manual_locked_fields` del producto.
  *Origen: as-built; código `product_service.py` (validación en servicio).*

- **FR-CAT-020**: El PATCH de `specs` DEBE re-validar el campo completo resultante contra
  el JSON Schema de la familia/subfamilia, no solo el fragmento enviado.
  *Origen: as-built; código `products.py:815-816`.*

#### Área 8 — Reemplazo de ficha

- **FR-CAT-021**: El sistema DEBE soportar reemplazo completo de ficha (`PUT /products/{sku}`)
  donde todos los campos editables son enviados en el cuerpo.
  *Origen: contrato API; código `products.py:822-859`.*

- **FR-CAT-022**: Si el header `If-Match: W/"<etag>"` está presente en el PUT, el sistema
  DEBE verificarlo contra el ETag actual del recurso y rechazar con HTTP 412 si no coincide.
  *Origen: PRD BR-1a-OPT-LOCK-01; código `products.py:844-858`.*

- **FR-CAT-023**: El sistema DEBE devolver el nuevo ETag en el header de respuesta tras un
  PUT exitoso.
  *Origen: as-built; código `products.py:858`.*

#### Área 9 — Calidad de dato

- **FR-CAT-024**: El sistema DEBE permitir cambiar el flag `data_quality` de un producto
  (`PATCH /products/{sku}/data-quality`) entre los valores: `complete`, `partial`,
  `blocked`, `migrated_demo`.
  *Origen: contrato API; código `products.py:862-886`.*

- **FR-CAT-025**: Para promover a `complete`, el producto DEBE tener todos los campos
  obligatorios poblados; si no, el sistema rechaza con HTTP 422.
  *Origen: PRD BR-1a-DQ-01; código `products.py:879`.*

- **FR-CAT-026**: El cambio de `data_quality` DEBE emitir un evento de auditoría.
  *Origen: PRD OKR O1a.4; código `product_service.py` (`patch_data_quality`).*

#### Área 10 — Baja lógica

- **FR-CAT-027**: El sistema DEBE implementar soft-delete: DELETE /products/{sku} establece
  `deleted_at = now()` Y fija `lifecycle_status = 'discontinued'`, sin eliminar el registro
  de la base de datos.
  *Origen: contrato API; código `products.py:934-950`; `product_service.py:611-619`.*

- **FR-CAT-028**: Los productos con soft-delete aplicado NO DEBEN aparecer en los listados
  activos de GET /products cuando se filtra por `active=true` o sin filtro de estado.
  *Origen: as-built; código `product_service.py` (`soft_delete_product`).*

- **FR-CAT-029**: La baja lógica DEBE requerir permiso `products:delete`; `products:write`
  no es suficiente.
  *Origen: contrato API; código `products.py:943`.*

#### Área 11 — Clasificación PVF

- **FR-CAT-030**: El sistema DEBE ofrecer un endpoint de clasificación PVF en lote
  (`POST /products/classify`) que encola una tarea Celery asíncrona con los parámetros
  `only_partial` y `promote_to_complete`.
  *Origen: as-built; código `products.py:889-931`.*

- **FR-CAT-031**: El clasificador PVF DEBE extraer `family`, `material`, `dn`, `pn` del
  campo `name_en` de cada producto, y SOLO actualizar campos vacíos o con valor
  `'unclassified'`, respetando `manual_locked_fields`.
  Los 4 campos físicos extraídos son: `family`, `material`, `dn`, `pn`. La verificación
  de `name_en` vía translations está pendiente de implementar (ver `product_service.py:537-539`).
  *Origen: as-built; código `workers/tasks/products.py` (`classify_pim_batch_task`);
  `product_service.py:540-544`.*

- **FR-CAT-032**: El endpoint de clasificación DEBE devolver HTTP 503 si Celery no está
  disponible al encolar la tarea.
  *Origen: as-built; código `products.py:915-922`.*

#### Área 12 — Jerarquía de variantes

- **FR-CAT-033**: El sistema DEBE permitir asignar o cambiar el `parent_sku` de un
  producto (`POST /products/{sku}/parent`), validando: existencia del padre, ausencia de
  ciclos, y profundidad máxima de 1 nivel.
  *Origen: as-built; código `products.py:1810-1836`.*

- **FR-CAT-034**: Tras asignar el padre, el sistema DEBE recalcular los flags `is_parent`
  e `is_variant` tanto del hijo como del padre afectado.
  *Origen: as-built; código `products.py:1835`.*

- **FR-CAT-035**: Desasociar el padre (`POST /{sku}/parent` con `parent_sku=null`) DEBE
  limpiar `parent_sku` y recalcular los flags.
  *Origen: as-built; código `products.py:1816`.*

#### Área 13 — Transversales

**Control de acceso (RBAC)**

- **NFR-CAT-001**: Todos los endpoints del dominio CAT DEBEN requerir al menos permiso
  `products:read` para operaciones de consulta y `products:write` para operaciones de
  creación/modificación. El permiso `products:delete` es necesario únicamente para baja
  lógica.
  *Origen: CLAUDE.md; código `products.py` (header de módulo + cada endpoint).*

**Formato de errores**

- **NFR-CAT-002**: Todos los errores del dominio CAT DEBEN seguir el estándar RFC 7807
  (`ProblemDetails`) con campos `type`, `title`, `status`, `detail`, `instance`, `code`.
  *Origen: CLAUDE.md; código `products.py:147-157` (`_problem` helper).*

**Auditoría**

- **NFR-CAT-003**: La emisión de eventos de auditoría DEBE realizarse desde la capa de
  servicio (`ProductService`), no desde los handlers de la API. Cada evento incluye:
  actor (user id), timestamp, acción, SKU afectado y datos anteriores/nuevos.
  *Origen: CLAUDE.md header de `products.py`; código `product_service.py`.*

**Cache**

- **NFR-CAT-004**: Los endpoints de consulta (GET) DEBEN recibir automáticamente el
  header `Cache-Control: private, max-age=60` aplicado por `CacheControlMiddleware`.
  La exportación CSV (`GET /products/export`) DEBE sobreescribir con `no-store`.
  *Origen: CLAUDE.md directriz 3; código `products.py:439-446`.*

**Performance**

- **NFR-CAT-005**: Ningún handler del dominio CAT DEBE ejecutar queries secuenciales al
  DB donde quepa un subquery, JOIN o batch fetch. Los listados DEBEN obtener datos de
  traducción y fotos primarias en queries de batch (no N+1 por producto).
  *Origen: CLAUDE.md directives 1-2; código `products.py:555-610`.*

**Exportación CSV**

- **FR-CAT-036**: El sistema DEBE exportar el catálogo filtrado como CSV
  (`GET /products/export`) con los campos: `sku`, `name_en`, `family`, `subfamily`,
  `type`, `brand`, `material`, `dn`, `pn`, `lifecycle_status`, `data_quality`,
  `created_at`, `updated_at`. Límite: 10 000 filas por export.
  *Origen: as-built; código `products.py:317-446`.*

**JSON Schema de specs**

- **FR-CAT-037**: El sistema DEBE devolver el JSON Schema que rige el campo `specs` para
  una combinación familia/subfamilia (`GET /products/specs/schema`). La cadena de
  fallback DEBE ser: `{family}_{subfamily}` → `{family}` → `_default`.
  *Origen: as-built; código `products.py:296-311`.*

**Reglas de negocio**

- **BR-CAT-001**: El campo `name_en` es el identificador semántico canónico del producto
  (EN) y es NOT NULL obligatorio en alta y reemplazo.
  *Origen: PRD §5.3; código `product.py` (columnas eliminadas en Fase B, sustituidas
  por `product_translations(lang='en')`; el campo `name_en` se expone como
  `hybrid_property`).*

- **BR-CAT-002**: El campo `sku` actúa como clave primaria de negocio (texto opaco,
  máx. 64 caracteres). Es inmutable una vez creado.
  *Origen: PRD §8.4; código `product.py:55`.*

- **BR-CAT-003**: El soft-delete es la única forma de desactivar un producto; no existe
  eliminación física (hard-delete) expuesta en la API.
  *Origen: as-built; código `products.py:934-950`.*

- **BR-CAT-004**: El campo `manual_locked_fields` es un array de nombres de campo que el
  sistema no permite sobreescribir vía PATCH ni por el clasificador PVF.
  *Origen: as-built; código `product.py:104-106`.*

- **BR-CAT-005**: La jerarquía de variantes tiene profundidad máxima de 1 nivel
  (un producto puede ser hijo de un padre, pero el padre no puede ser hijo de otro).
  *Origen: as-built; código `products.py:1823`.*

---

### Entidades clave

- **Product**: Entidad central. PK = `sku` (TEXT). Campos clave: `internal_id` (UUID
  auxiliar), `family`, `subfamily`, `brand`, `material`, `dn`, `pn`, `specs` (JSONB),
  `data_quality`, `lifecycle_status`, `manual_locked_fields`, `parent_sku`,
  `is_parent`, `is_variant`, `deleted_at`.

- **ProductTranslation**: Traducción por producto × idioma (`es`, `ar`). Campos:
  `sku`, `lang`, `name`, `description`, `marketing_copy`, `status`
  (`pending`/`draft`/`approved`).

- **ProductAsset**: Asset multimedia vinculado a un SKU. Campos: `sku`, `kind`
  (`photo`, etc.), `is_primary`, `status` (`active`/`archived`), `storage_path`,
  `bucket`, `variants` (JSONB con miniaturas webp).

- **SpecsRegistry**: Catálogo de JSON Schemas por familia/subfamilia. Singleton cargado
  al arrancar el módulo.

- **ProductFilters**: VO de filtros de listado; compartido entre `list_products` y
  `compute_facets` para garantizar coherencia de filtros.

---

## Criterios de éxito *(obligatorio)*

### Resultados medibles

- **SC-001**: Un operador de catálogo puede crear un producto, editarlo parcialmente,
  reemplazarlo completamente y darlo de baja en una sesión sin errores ni pérdida de
  trazabilidad (auditoría registrada en cada paso).

- **SC-002**: El listado paginado devuelve la página siguiente sin duplicados ni saltos,
  independientemente del tamaño del catálogo (verificable con un catálogo de > 200 SKUs).

- **SC-003**: Los filtros compuestos en GET /products (mínimo 3 dimensiones simultáneas)
  devuelven solo productos que cumplen todas las condiciones.

- **SC-004**: La búsqueda rápida devuelve resultados relevantes para términos parciales
  de nombre o SKU en menos de 500 ms con un catálogo de al menos 5 000 productos.

- **SC-005**: El clasificador PVF en lote respeta `manual_locked_fields` y no sobreescribe
  campos bloqueados; verificable comparando before/after con campos bloqueados intactos.

- **SC-006**: La jerarquía de variantes con asignación de padre y consulta resuelta
  devuelve los campos heredados correctamente sin campos propios sobreescritos.

- **SC-007**: 100 % de los endpoints del alcance CAT requieren autenticación y el permiso
  declarado; sin credenciales devuelven 401/403.

- **SC-008**: El CSV exportado contiene exactamente los 13 campos canónicos y no más de
  10 000 filas, sin header `Cache-Control` de caché positivo.

- **SC-009**: El endpoint de facetas devuelve respuesta en p95 < 200 ms con un catálogo
  de entre 5 000 y 50 000 productos activos, con los índices de la migración 041 activos.
  *Origen: as-built; código `products.py:693`.*

---

## Supuestos

- El sistema actual está desplegado sobre FastAPI + PostgreSQL + SQLAlchemy 2.0 async
  según la constitución del proyecto (Art. 1). Todos los endpoints documentados ya
  existen en `mt-pricing-backend/app/api/routes/products.py`.

- Los JSON Schemas de specs por familia están cargados en `SpecsRegistry` al arrancar
  la aplicación; su contenido exacto está fuera del alcance de esta spec.

- El Manual Operativo BR Dynamic × MT Valves no estaba accesible en el repositorio en
  el momento de elaborar esta spec; los requisitos de negocio se han derivado del PRD
  (`_bmad-output/planning-artifacts/prd-mt-pricing-mdm-phase1.md`) como origen primario.
  **NOTA AL EQUIPO**: confirmar si algún requisito del Manual contradice lo documentado
  aquí, especialmente en lo relativo a `data_quality` y profundidad de jerarquía.

- La auditoría BMAD del módulo (2026-05-20) en `_bmad-output/analysis/products-module/`
  cubre deuda técnica/calidad. Esta spec cubre conformidad funcional; ambas son
  complementarias.

- Los sub-recursos fuera de alcance (traducciones, assets, compatibilidades, materiales,
  certificados, releases, etc.) son procesos F1 futuros y se referencian aquí solo donde
  sus datos son parte de la respuesta de un endpoint en alcance (p.ej., traducciones y
  assets incluidos en `ProductDetail`).

- El campo `name_en` se expone como `hybrid_property` read-only en el modelo ORM desde
  la migración 065 (Fase B); para escritura se usa el endpoint de traducciones con
  `lang='en'`. En el contexto de esta spec, `name_en` se considera el campo semántico
  canónico obligatorio, independientemente del mecanismo de persistencia subyacente.
