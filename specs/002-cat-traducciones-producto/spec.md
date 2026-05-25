# Spec retrospectiva: Traducciones de Producto (CAT — sub-recurso)

**Feature Branch**: `docs/f1-traducciones-producto`

**Creado**: 2026-05-25

**Tipo**: Retrospectivo — documenta el comportamiento ACTUAL del sistema, no funcionalidad futura.

**Estado**: Borrador

**Dominio**: CAT — sub-recurso Traducciones de Producto

**Input**: Spec retrospectiva del proceso EXISTENTE de gestión de traducciones de producto.
Los endpoints en alcance son los que gestionen el sub-recurso `product_translations`
(langues es, ar; master EN gestionado via upsert). Excluido explícitamente del
spec 001-cat-gestion-catalogo-productos.

---

## Clarificaciones

### Sesión 2026-05-25

- Q: ¿Qué idiomas soporta el sub-recurso? → A: `es` y `ar` para CRUD + workflow;
  `en` como master read-only expuesto vía `hybrid_property`; el completion service
  soporta además `fr`, `de`, `it`, `pt` (`translations.py:27`).
- Q: ¿El endpoint `/approve` en `products.py` usa four-eyes? → A: No; solo el workflow
  `TranslationWorkflowService.approve()` en `translation_workflow.py:218-240` lo valida.
  El endpoint clásico `approve_translation` en `products.py:1002-1018` llama directamente
  a `ProductService.approve_translation` que NO implementa four-eyes. Brecha confirmada.
- Q: ¿Qué campo de la tabla define el estado de workflow? → A: `product_translations.status`
  (`String(16)`) con CHECK constraint `IN ('pending','draft','pending_review','approved',
  'pending_review','stale')` via `TranslationStatus` enum (`enums.py:57-64`).
- Q: ¿Existe DELETE para traducciones? → A: No hay endpoint DELETE expuesto. El repositorio
  usa `ON CONFLICT DO UPDATE` (upsert); no hay hard-delete expuesto.

---

## Escenarios de usuario y prueba *(obligatorio)*

### Historia de usuario 1 — CRUD de traducciones por idioma (Priority: P1)

El operador de catálogo (Comercial) gestiona las traducciones individuales de un producto
para los idiomas es y ar: crea o reemplaza la traducción completa, aplica cambios
parciales, y consulta el estado de todas las traducciones de un SKU.

**Por qué esta prioridad**: Sin traducciones, los productos no pueden exportarse ni
publicarse en mercados hispanohablantes y árabes. Es el bloque fundamental de trabajo
de traducción diario.

**Prueba independiente**: Verificable con PUT /{sku}/translations/{lang} seguido de
GET /{sku}/translations en un entorno aislado sin workflow activo.

**Escenarios de aceptación**:

1. **Dado** que soy Comercial autenticado con permiso `products:write`,
   **Cuando** envío PUT /products/MT-001/translations/es con `name`, `description`,
   `marketing_copy` y `status=draft`,
   **Entonces** el sistema crea o reemplaza la traducción ES, emite auditoría
   (`product.translation.created` o `product.translation.upserted`) y devuelve
   `ProductTranslationResponse` con HTTP 200.

2. **Dado** una traducción ES ya existente para MT-001,
   **Cuando** envío PATCH /products/MT-001/translations/es con solo `marketing_copy`,
   **Entonces** el sistema actualiza únicamente ese campo (semantica `exclude_unset=True`)
   y devuelve la traducción actualizada.

3. **Dado** un usuario con `products:read`,
   **Cuando** envío GET /products/MT-001/translations,
   **Entonces** el sistema devuelve la lista de todas las traducciones del producto
   (incluyendo EN, ES, AR si existen) sin lanzar queries adicionales por traducción.

4. **Dado** un SKU inexistente,
   **Cuando** envío GET /products/NOSKÚ/translations,
   **Entonces** el sistema devuelve HTTP 404 con cuerpo RFC 7807.

5. **Dado** un PATCH sin ningún campo en el body,
   **Cuando** envío PATCH /products/MT-001/translations/es con `{}`,
   **Entonces** el sistema rechaza con HTTP 422 (payload vacío).

---

### Historia de usuario 2 — Workflow de aprobación four-eyes (Priority: P2)

El autor de una traducción la envía a revisión y un aprobador diferente (four-eyes)
la aprueba o rechaza con motivo. El sistema lleva trazabilidad completa de qué usuario
hizo cada acción y cuándo.

**Por qué esta prioridad**: El proceso four-eyes (BR-1a-09) es un requisito regulatorio
de control interno: evita que la misma persona traduzca y apruebe. Sin este flujo,
las traducciones no pueden publicarse formalmente.

**Prueba independiente**: Verificable con POST request-review → POST approve (usuario
diferente) en un entorno con dos cuentas.

**Escenarios de aceptación**:

1. **Dado** una traducción ES en estado `draft`,
   **Cuando** el autor envía POST /products/MT-001/translations/es/request-review,
   **Entonces** el sistema transiciona a `pending_review`, actualiza `translated_by`
   y `translated_at`, emite auditoría y devuelve `TranslationWorkflowResponse`.

2. **Dado** una traducción en `pending_review`,
   **Cuando** un usuario DIFERENTE al autor envía POST /products/MT-001/translations/es/approve,
   **Entonces** el sistema transiciona a `approved`, actualiza `reviewed_by`/`reviewed_at`
   y emite `product.translation.approved`.

3. **Dado** una traducción en `pending_review`,
   **Cuando** el mismo usuario que la tradujo intenta aprobarla (four-eyes violation),
   **Entonces** el sistema rechaza con HTTP 403 y código `translation_four_eyes_violation`.

4. **Dado** una traducción en `pending_review`,
   **Cuando** el aprobador envía POST reject con `reason` obligatorio,
   **Entonces** el sistema transiciona de vuelta a `draft`, persiste `rejection_reason`
   y emite auditoría `product.translation.rejected`.

5. **Dado** una transición no permitida (ej. `approved → pending_review` directa),
   **Cuando** el usuario intenta esa transición,
   **Entonces** el sistema rechaza con HTTP 409 y código `invalid_translation_state_transition`.

---

### Historia de usuario 3 — Gestión de staleness y cobertura (Priority: P3)

Cuando el master EN de un producto cambia, las traducciones aprobadas se marcan
automáticamente como `stale` para forzar re-validación. El equipo TI puede disparar
manualmente el mismo efecto. Gestión puede consultar la cobertura global de traducciones.

**Por qué esta prioridad**: Sin el mecanismo stale, las traducciones quedarían
desincronizadas con el contenido EN sin que el equipo lo detecte.

**Prueba independiente**: Verificable con POST mark-stale + GET coverage en un entorno
con traducciones aprobadas.

**Escenarios de aceptación**:

1. **Dado** un SKU con traducciones ES y AR en `approved`,
   **Cuando** el master EN cambia (o TI dispara POST mark-stale manualmente),
   **Entonces** el sistema marca ES y AR como `stale`, NO toca la traducción EN, y
   devuelve la lista de traducciones afectadas con `affected_count`.

2. **Dado** un SKU donde ninguna traducción está en `approved`,
   **Cuando** se ejecuta mark-stale,
   **Entonces** el sistema devuelve `affected_count=0` (idempotente).

3. **Dado** un usuario con `products:read`,
   **Cuando** envío GET /api/v1/products/translations/coverage,
   **Entonces** el sistema devuelve `total_products`, lista de cobertura por idioma
   (`{lang, count, pct}`) y `missing_by_lang` para los 7 idiomas soportados.

4. **Dado** que el AI-completion service está disponible,
   **Cuando** envío POST /api/v1/products/translations/complete con lista de SKUs y
   target_langs,
   **Entonces** el sistema invoca `TranslationCompletionService.complete()` y devuelve
   `{completed, skipped, errors, details}`.

---

### Casos límite

- ¿Qué ocurre al enviar PUT /translations/en (master EN via CRUD endpoint)?
  → Rechazado por regex path constraint `^(es|ar)$`.
- ¿Qué ocurre al aprobar una traducción vía endpoint clásico siendo el mismo autor?
  → SIN four-eyes check (brecha vs. workflow service).
- ¿Qué ocurre al intentar request-review sobre una traducción `approved`?
  → HTTP 409 con `invalid_translation_state_transition`.
- ¿Qué ocurre con reject sin `reason`?
  → HTTP 422 (Pydantic: `min_length=3`).
- ¿Qué ocurre con GET /translations sin autenticación? → HTTP 401/403.

---

## Requisitos *(obligatorio)*

### Requisitos funcionales

#### Área 1 — Listado de traducciones

- **FR-TRD-001**: El sistema DEBE permitir listar todas las traducciones de un producto
  (`GET /products/{sku}/translations`) devolviendo `list[ProductTranslationResponse]`.
  Requiere permiso `products:read`. Devuelve HTTP 404 si el SKU no existe o está eliminado.
  *Origen: as-built; código `products.py:942-957`.*

#### Área 2 — Creación/reemplazo (upsert)

- **FR-TRD-002**: El sistema DEBE permitir crear o reemplazar una traducción completa
  (`PUT /products/{sku}/translations/{lang}`) de forma idempotente. El lang está
  restringido a `es` o `ar`. Requiere `products:write`. Devuelve HTTP 200 siempre
  (creación o actualización).
  *Origen: as-built; código `products.py:960-979`.*

- **FR-TRD-003**: El PUT de traducción DEBE emitir un evento de auditoría
  (`product.translation.created` en alta, `product.translation.upserted` en actualización)
  con actor, timestamp y campos después.
  *Origen: as-built; código `product_service.py:775-788`.*

- **FR-TRD-004**: El upsert de traducción DEBE implementarse como `INSERT ... ON CONFLICT
  DO UPDATE` (atómico), evitando la condición de carrera SELECT→INSERT/UPDATE.
  *Origen: as-built; código `product.py:491-524` (`ProductTranslationRepository.upsert`).*

#### Área 3 — Edición parcial

- **FR-TRD-005**: El sistema DEBE soportar edición parcial de una traducción existente
  (`PATCH /products/{sku}/translations/{lang}`), actualizando solo los campos presentes
  en el body (`exclude_unset=True`). Devuelve HTTP 404 si la traducción no existe.
  Requiere `products:write`.
  *Origen: as-built; código `products.py:982-999`.*

- **FR-TRD-006**: El PATCH de traducción DEBE rechazar con HTTP 422 un payload vacío
  (sin ningún campo). El validator de Pydantic `_at_least_one_field` implementa esta
  restricción.
  *Origen: as-built; código `schemas/products.py:575-579`.*

#### Área 4 — Aprobación clásica

- **FR-TRD-007**: El sistema DEBE ofrecer un endpoint de aprobación clásica
  (`POST /products/{sku}/translations/{lang}/approve`) que transiciona el `status` a
  `approved` y registra `reviewed_by`/`reviewed_at`. Requiere `products:write`.
  *Origen: as-built; código `products.py:1002-1018`.*

#### Área 5 — Workflow de estados S3

- **FR-TRD-008**: El sistema DEBE soportar el endpoint de solicitud de revisión
  (`POST /products/{sku}/translations/{lang}/request-review`) que transiciona de
  `draft|pending|stale` a `pending_review`. Requiere `products:write`.
  *Origen: as-built; código `translations_workflow.py:58-82`.*

- **FR-TRD-009**: El sistema DEBE soportar el endpoint de rechazo
  (`POST /products/{sku}/translations/{lang}/reject`) con `reason` obligatorio
  (min 3 chars). Transiciona de `pending_review` a `draft`. Requiere `products:write`.
  *Origen: as-built; código `translations_workflow.py:85-112`.*

- **FR-TRD-010**: El sistema DEBE soportar el endpoint de marcado-stale
  (`POST /products/{sku}/translations/mark-stale`) que transiciona todas las traducciones
  no-EN en estado `approved` a `stale`. Idempotente. Requiere `products:write`.
  *Origen: as-built; código `translations_workflow.py:115-145`.*

- **FR-TRD-011**: La máquina de estados DEBE implementar las transiciones:
  `draft → pending_review` (request-review),
  `pending → pending_review` (retro-compat legacy),
  `stale → pending_review` (re-revisión post-stale),
  `pending_review → approved` (approve),
  `pending_review → draft` (reject),
  `approved → stale` (mark-stale).
  Cualquier otra transición DEBE lanzar HTTP 409 con código
  `invalid_translation_state_transition`.
  *Origen: as-built; código `translation_workflow.py:79-92`.*

- **FR-TRD-012**: El workflow DEBE registrar el actor (`translated_by`/`reviewed_by`)
  y timestamp en cada transición. Cada transición emite un audit event canónico vía
  `TranslationAuditEmitter`.
  *Origen: as-built; código `translation_workflow.py:195-307`;
  `translation_audit.py:27-34`.*

#### Área 6 — Cobertura y completion AI

- **FR-TRD-013**: El sistema DEBE devolver estadísticas de cobertura de traducciones
  (`GET /api/v1/products/translations/coverage`) — total de productos, conteo y
  porcentaje por idioma, y faltantes por idioma. Requiere `products:read`.
  *Origen: as-built; código `translations.py:90-128`.*

- **FR-TRD-014**: El sistema DEBE ofrecer un endpoint de completado AI
  (`POST /api/v1/products/translations/complete`) que delega a
  `TranslationCompletionService`. Requiere `products:write`.
  *Origen: as-built; código `translations.py:65-87`.*

### Requisitos no funcionales

**Control de acceso (RBAC)**

- **NFR-TRD-001**: Todos los endpoints de lectura del sub-recurso TRD DEBEN requerir
  al menos `products:read`. Todos los endpoints de escritura/workflow DEBEN requerir
  `products:write`.
  *Origen: CLAUDE.md; código `products.py:950`, `products.py:970`, `products.py:992`,
  `products.py:1011`; `translations_workflow.py:75`, `translations_workflow.py:105`,
  `translations_workflow.py:132`; `translations.py:77`, `translations.py:101`.*

**Formato de errores**

- **NFR-TRD-002**: Los errores de los endpoints en `products.py` DEBEN seguir RFC 7807
  con campos `type`, `title`, `status`, `code` (`instance` incluido en errores
  construidos con `_problem`). Los errores en `translations_workflow.py` usan
  `HTTPException` con `detail={"code": ..., "title": ...}` — formato reducido sin
  `type`/`instance`.
  *Origen: as-built; código `products.py:161-173`; `translations_workflow.py:48-52`.*

**Auditoría**

- **NFR-TRD-003**: La emisión de audit events de traducciones DEBE hacerse desde la
  capa de servicio. Las acciones canónicas son: `product.translation.created`,
  `product.translation.upserted`, `product.translation.approved` (clásico),
  `product.translation.review_requested`, `product.translation.rejected`,
  `product.translation.marked_stale`.
  *Origen: as-built; código `product_service.py:775-787`;
  `translation_audit.py:27-34`.*

**Performance**

- **NFR-TRD-004**: El listado de traducciones (`GET /{sku}/translations`) DEBE
  resolverse sin N+1: el producto se carga con `selectinload(Product.translations)`;
  el endpoint llama a `service.list_translations` que usa
  `ProductTranslationRepository.get_for_sku` (1 query SELECT).
  *Origen: CLAUDE.md directriz 1-2; código `product_service.py:754-758`;
  `product.py:474-481`.*

- **NFR-TRD-005**: El upsert atómico de traducciones DEBE usar `INSERT ON CONFLICT
  DO UPDATE` (1 round-trip) en lugar de SELECT + INSERT/UPDATE por separado.
  *Origen: CLAUDE.md directriz 1; código `product.py:491-524`.*

**Idiomas soportados**

- **NFR-TRD-006**: El sub-recurso TRD DEBE restringir el parámetro `lang` en los
  endpoints CRUD y workflow a `es` o `ar` mediante validación regex en Path. El master
  EN no es modificable directamente por los endpoints de traducciones.
  *Origen: as-built; código `products.py:968`
  (`lang: Annotated[str, Path(pattern=r"^(es|ar)$")]`).*

### Reglas de negocio

- **BR-TRD-001**: La traducción EN (`lang='en'`) es el master canónico del producto.
  No está expuesta como recurso modificable desde los endpoints del sub-recurso TRD;
  su escritura ocurre internamente vía `ProductService._extract_en_translation_payload`
  durante alta/edición del producto.
  *Origen: PRD §5.3; código `product.py:62-67`; `product_service.py:273-287`.*

- **BR-TRD-002**: El campo `status` del ORM acepta los valores del enum `TranslationStatus`:
  `pending`, `draft`, `pending_review`, `ai_generated`, `approved`, `stale`. Los schemas
  Pydantic de CRUD solo exponen `pending|draft|approved`; el workflow S3 amplía a
  `pending_review` y `stale`.
  *Origen: as-built; código `enums.py:57-64`; `schemas/products.py:553`;
  `schemas/translations_workflow.py:17-23`.*

- **BR-TRD-003**: El principio four-eyes (BR-1a-09) exige que el usuario que aprueba
  una traducción sea distinto del usuario que la tradujo (`translated_by`). Este check
  solo está implementado en `TranslationWorkflowService.approve()` (workflow S3),
  NO en el endpoint clásico `approve_translation` de `products.py`.
  *Origen: PRD BR-1a-09; código `translation_workflow.py:224-226`.*

- **BR-TRD-004**: El marcado `stale` se aplica exclusivamente a traducciones no-EN
  cuyo `status == 'approved'`. Las traducciones EN y las que no están en `approved`
  se ignoran (idempotente).
  *Origen: as-built; código `translation_workflow.py:286-295`.*

- **BR-TRD-005**: El `reject` de una traducción DEBE incluir un `reason` de al menos
  3 caracteres (validado por Pydantic y verificado además en la capa de servicio).
  *Origen: PRD BR-1a-09; código `schemas/translations_workflow.py:34-37`;
  `translation_workflow.py:244`.*

- **BR-TRD-006**: La operación de upsert de traducciones registra siempre `translated_by`
  (con el actor si el caller no lo especifica) y `translated_at` (hora actual UTC).
  *Origen: as-built; código `product_service.py:771-774`.*

---

### Entidades clave

- **ProductTranslation**: PK compuesto `(sku, lang)`. Campos:
  `name` (TEXT, max 512), `description` (max 4000), `marketing_copy` (max 8000),
  `meta_title` (max 70), `meta_description` (max 160), `applications_text`,
  `technical_limits`, `notes`, `marketing_features`, `status` (String(16)),
  `translated_by` (UUID FK), `translated_at`, `reviewed_by` (UUID FK),
  `reviewed_at`, `created_at`, `updated_at`.
  CHECK constraints: `lang IN ('es','ar','en')`, `status IN (...)`.

- **TranslationWorkflowService**: Orquestador de la FSM. No reemplaza
  `ProductService` — vive en paralelo y sirve los endpoints de workflow.

- **TranslationAuditEmitter**: Wrapper sobre `AuditRepository` con el shape canónico
  de audit events de traducciones. Valida que la `action` pertenezca al conjunto
  canónico.

- **TranslationCompletionService**: Servicio AI (Claude) para completar traducciones
  faltantes dado un conjunto de SKUs y target_langs.

---

## Criterios de éxito *(obligatorio)*

- **SC-TRD-001**: Un operador puede crear una traducción ES vía PUT, editarla
  parcialmente vía PATCH y consultar el listado vía GET sin errores, con auditoría
  completa.

- **SC-TRD-002**: El flujo request-review → approve (usuario diferente) transiciona
  correctamente la FSM y rechaza la aprobación por el mismo autor con HTTP 403.

- **SC-TRD-003**: El rechazo con motivo transiciona a `draft` y persiste
  `rejection_reason`. El rechazo sin motivo devuelve HTTP 422.

- **SC-TRD-004**: El mark-stale solo afecta traducciones no-EN en `approved`; las
  demás permanecen intactas. Verificable inspeccionando `status` antes y después.

- **SC-TRD-005**: GET /coverage devuelve resultados correctos con `total_products`,
  `coverage` por idioma y `missing_by_lang` para los 7 idiomas soportados.

- **SC-TRD-006**: 100 % de los endpoints del sub-recurso TRD requieren autenticación;
  sin credenciales devuelven 401/403.

---

## Supuestos

- El stack subyacente es FastAPI + PostgreSQL + SQLAlchemy 2.0 async. Todos los
  endpoints documentados ya existen en el repositorio.

- Los idiomas de trabajo primarios son `es` (español) y `ar` (árabe) para CRUD y
  workflow. La traducción `en` es el master y se gestiona internamente.

- El `TranslationCompletionService` (LLM) usa Claude para completar traducciones;
  su lógica interna está fuera del alcance de este spec (cubierta por
  `tests/unit/services/translations/test_completion_service.py`).

- El trigger DB que marca traducciones como `stale` cuando cambia el master EN
  existe en la base de datos (referenciado en `translation_workflow.py:19`);
  su DDL está en las migraciones Alembic y fuera del alcance de este spec.

- El status `ai_generated` definido en `TranslationStatus` enum no está expuesto
  en los schemas Pydantic de S3; se asume que es un estado interno del
  completion service.
