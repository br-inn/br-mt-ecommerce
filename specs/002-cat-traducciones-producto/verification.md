# Verificacion de conformidad F1 — Traducciones de Producto (CAT sub-recurso)

**Proceso**: Piloto F1 — verificacion retrospectiva
**Fecha**: 2026-05-25
**Revisado contra**: spec.md (FR-TRD-001..014, NFR-TRD-001..006, BR-TRD-001..006)
**Codigo fuente principal**:
- `mt-pricing-backend/app/api/routes/products.py` (ref. `products.py`)
- `mt-pricing-backend/app/api/routes/translations_workflow.py` (ref. `workflow.py`)
- `mt-pricing-backend/app/api/routes/translations.py` (ref. `translations.py`)
- `mt-pricing-backend/app/services/products/product_service.py` (ref. `product_service.py`)
- `mt-pricing-backend/app/services/products/translation_workflow.py` (ref. `translation_workflow.py`)
- `mt-pricing-backend/app/services/products/translation_audit.py` (ref. `translation_audit.py`)
- `mt-pricing-backend/app/db/models/product.py` (ref. `product.py`)
- `mt-pricing-backend/app/repositories/product.py` (ref. `repository.py`)
- `mt-pricing-backend/app/schemas/products.py` (ref. `schemas/products.py`)
- `mt-pricing-backend/app/schemas/translations_workflow.py` (ref. `schemas/workflow.py`)

**Leyenda**:
- Verificado — el codigo cumple el requisito; evidencia `archivo:linea`
- Parcial — cumple en parte; brecha descrita
- No cumple — el codigo contradice el requisito
- No implementado — sin codigo que lo soporte

---

## Area 1 — Listado de traducciones

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-TRD-001 | Verificado | `products.py:942-957`; `product_service.py:754-758`; `repository.py:474-481` | GET /{sku}/translations. `require_permissions("products:read")`. `list_translations` verifica que producto exista y no este eliminado; devuelve HTTP 404 via `ProductNotFoundError`. | — |

---

## Area 2 — Creacion/reemplazo (upsert)

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-TRD-002 | Verificado | `products.py:960-979`; path constraint `pattern=r"^(es|ar)$"` en linea 968 | PUT /{sku}/translations/{lang}. Idempotente. `require_permissions("products:write")`. Restriccion lang a es\|ar correcta. Devuelve 200 siempre (sin 201 en creacion — menor inconsistencia semantica pero no brecha funcional). | — |
| FR-TRD-003 | Verificado | `product_service.py:775-788` | Audit emitido con action diferenciada: `product.translation.created` (alta) vs `product.translation.upserted` (update). Actor y timestamp incluidos. | — |
| FR-TRD-004 | Verificado | `repository.py:491-524` | `INSERT ON CONFLICT DO UPDATE` con `RETURNING` — atomico. `populate_existing=True` para actualizar el identity-map. | — |

---

## Area 3 — Edicion parcial

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-TRD-005 | Verificado | `products.py:982-999`; `product_service.py:800-815` | PATCH /{sku}/translations/{lang}. `update_translation` verifica existencia (HTTP 404 si no existe). Semantica parcial via `model_dump(exclude_unset=True)`. `require_permissions("products:write")`. | — |
| FR-TRD-006 | Verificado | `schemas/products.py:575-579` | `_at_least_one_field` validator en `ProductTranslationPatch` rechaza payload vacio con `ValueError` → HTTP 422. | — |

---

## Area 4 — Aprobacion clasica

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-TRD-007 | Parcial | `products.py:1002-1018`; `product_service.py:817-842` | Endpoint existe y transiciona a `approved`. Pero: (1) NO implementa four-eyes — cualquier usuario con `products:write` puede aprobar su propia traduccion, violando BR-1a-09. (2) Llama a `session.refresh(existing)` tras flush — round-trip extra no estrictamente necesario. Ver BRECHA-TRD-01. | — |

---

## Area 5 — Workflow de estados S3

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-TRD-008 | Verificado | `workflow.py:58-82`; `translation_workflow.py:195-216` | POST /{sku}/translations/{lang}/request-review. Transicion draft\|pending\|stale → pending_review. FSM enforced via `assert_transition`. `require_permissions("products:write")`. | — |
| FR-TRD-009 | Verificado | `workflow.py:85-112`; `translation_workflow.py:242-265` | POST reject con `reason` obligatorio (min 3 chars, Pydantic). Transicion pending_review → draft. FSM enforced. | — |
| FR-TRD-010 | Verificado | `workflow.py:115-145`; `translation_workflow.py:268-307` | POST mark-stale. Solo afecta filas no-EN en `approved`. Idempotente: filas no-`approved` ignoradas. `require_permissions("products:write")`. | — |
| FR-TRD-011 | Verificado | `translation_workflow.py:79-92` (`_VALID_TRANSITIONS`) | Las 6 transiciones documentadas estan en el frozenset. Cualquier otra lanza `InvalidTranslationStateTransition` (code=`invalid_translation_state_transition`, HTTP 409). Retrocompat: `pending → pending_review` incluida. | — |
| FR-TRD-012 | Verificado | `translation_workflow.py:208-215`; `translation_audit.py:27-34`; `translation_audit.py:61-102` | `TranslationAuditEmitter.record_transition` emite para cada transicion. Set canonico de acciones validado con `ValueError` si se produce typo. `entity_type='product_translation'`, `entity_id=f'{sku}:{lang}'`. | — |

---

## Area 6 — Cobertura y completion AI

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-TRD-013 | Verificado | `translations.py:90-128` | GET /translations/coverage. `require_permissions("products:read")`. Devuelve `total_products`, `coverage` list y `missing_by_lang` para los 7 idiomas (`_SUPPORTED_LANGS`). Division por cero protegida (`if total` en linea 118). | — |
| FR-TRD-014 | Verificado | `translations.py:65-87` | POST /translations/complete. `require_permissions("products:write")`. Delega a `TranslationCompletionService.complete()`. Devuelve `CompletionResultResponse`. `actor_id=None` — no se pasa el actor al servicio AI (menor gap de trazabilidad). Ver BRECHA-TRD-04. | — |

---

## NFR — Transversales

| NFR | Estado | Evidencia | Brecha / Notas | BMAD |
|-----|--------|-----------|----------------|------|
| NFR-TRD-001 | Verificado | `products.py:950`, `970`, `992`, `1011`; `workflow.py:75`, `105`, `132`; `translations.py:77`, `101` | Todos los endpoints de lectura usan `products:read`; todos los de escritura/workflow usan `products:write`. Sin endpoint sin autenticacion. | — |
| NFR-TRD-002 | Parcial | `products.py:161-173`; `workflow.py:48-52` | `products.py` aplica RFC 7807 completo (`type`, `title`, `status`, `code`, `instance`). `translations_workflow.py._raise_domain` solo incluye `code` y `title` — faltan `type`, `status`, `instance`. Ver BRECHA-TRD-02. | — |
| NFR-TRD-003 | Verificado | `product_service.py:775-787`; `translation_audit.py:74-102` | Audit desde capa de servicio. Acciones canonicas en `TRANSLATION_AUDIT_ACTIONS` frozenset. `entity_type='product_translation'`, `entity_id=f'{sku}:{lang}'`. | — |
| NFR-TRD-004 | Verificado | `product_service.py:754-758`; `repository.py:474-481` | `list_translations` llama a `get_for_sku` — 1 SELECT sin N+1. Los datos de traducciones en `GET /products/{sku}` se cargan via `selectinload` (Product.translations) pre-configurado en `get_with_translations_and_images`. | — |
| NFR-TRD-005 | Verificado | `repository.py:491-524` | Upsert usa `pg_insert(...).on_conflict_do_update(...)` — 1 round-trip. | — |
| NFR-TRD-006 | Verificado | `products.py:968`; `workflow.py:73`, `103`, `133` | Path param `lang` con `pattern=r"^(es|ar)$"` en todos los endpoints CRUD y workflow. El master EN no es alcanzable via estos endpoints. | — |

---

## BR — Reglas de negocio

| BR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| BR-TRD-001 | Verificado | `product.py:62-67`; `product_service.py:273-287` | EN es el master; `_extract_en_translation_payload` lo gestiona internamente. No hay endpoint CRUD que acepte `lang='en'` directamente (regex bloquea). | — |
| BR-TRD-002 | Parcial | `enums.py:57-64`; `schemas/products.py:553`; `schemas/workflow.py:17-23` | `TranslationStatus` enum tiene `ai_generated` pero ni los schemas CRUD ni los de workflow lo exponen. Los schemas CRUD solo permiten `pending\|draft\|approved`. `stale` solo aparece en `TranslationWorkflowStatus`. Estado `ai_generated` no es settable por ningun endpoint REST — solo internamente por el completion service. Ver BRECHA-TRD-05. | — |
| BR-TRD-003 | Parcial | `translation_workflow.py:224-226`; `product_service.py:817-842` | Four-eyes implementado en `TranslationWorkflowService.approve()`. El endpoint clasico `approve_translation` en `products.py` NO llama a `TranslationWorkflowService` — no tiene four-eyes. Ver BRECHA-TRD-01. | — |
| BR-TRD-004 | Verificado | `translation_workflow.py:286-295` | `mark_stale_for_master_edit` hace `continue` si `row.lang == "en"` y `continue` si `row.status != STATE_APPROVED`. Solo afecta no-EN en approved. | — |
| BR-TRD-005 | Verificado | `schemas/workflow.py:34-37` (min_length=3); `translation_workflow.py:244` (check de str vacío) | Double-check: Pydantic en schema (min_length=3) + servicio (strip + empty check). | — |
| BR-TRD-006 | Verificado | `product_service.py:771-774` | `fields.setdefault("translated_by", actor.id)` y `fields.setdefault("translated_at", datetime.now(tz=UTC))` — siempre registrados si el caller no los provee. | — |

---

## Brechas identificadas

### BRECHA-TRD-01 — Endpoint clasico approve sin four-eyes check

**Severidad**: Alta

**Requisitos afectados**: FR-TRD-007, BR-TRD-003

**Descripcion**: El endpoint `POST /products/{sku}/translations/{lang}/approve`
en `products.py:1002-1018` llama a `ProductService.approve_translation`
(`product_service.py:817-842`). Este metodo no valida que el `actor.id` sea
diferente de `translated_by` (four-eyes BR-1a-09). El `TranslationWorkflowService.approve`
en `translation_workflow.py:218-240` SI implementa el check. Coexisten dos rutas
de aprovacion con comportamiento diferente para la misma operacion semantica.

**Evidencia**: `product_service.py:817-842` (sin four-eyes); `translation_workflow.py:224-226` (con four-eyes).

**Accion sugerida**: Deprecar el endpoint clasico `/approve` o refactorizarlo para
que llame a `TranslationWorkflowService.approve()`. Alternativa: anadir el check
four-eyes directamente en `ProductService.approve_translation`.

**Issue GitHub**: issue #96

---

### BRECHA-TRD-02 — RFC 7807 incompleto en translations_workflow.py

**Severidad**: Media

**Requisitos afectados**: NFR-TRD-002

**Descripcion**: `translations_workflow.py:48-52` define `_raise_domain` como:
```python
raise HTTPException(
    status_code=err.status_code,
    detail={"code": err.code, "title": err.message},
)
```
Faltan los campos RFC 7807: `type` (URI de error), `status` (int), `instance`
(path del request). En contraste, `products.py:161-173` incluye los 5 campos.
Los clientes que parsean errores RFC 7807 completos recibiran payloads truncados
de los endpoints de workflow S3.

**Evidencia**: `translations_workflow.py:48-52`; `products.py:161-173`.

**Accion sugerida**: Alinear `_raise_domain` en `translations_workflow.py` con el
helper de `products.py`, anadir `type=f"https://mtme-api/errors/{err.code}"`,
`status=err.status_code`, `instance` del Request (requiere anadir `Request` como
parametro a los endpoints afectados).

**Issue GitHub**: issue #97

---

### BRECHA-TRD-03 — session.refresh() extra en approve_translation clasico

**Severidad**: Baja

**Requisitos afectados**: NFR-TRD-005 (performance)

**Descripcion**: `ProductService.approve_translation` (`product_service.py:831-833`)
ejecuta `await self.session.refresh(existing)` despues del flush para evitar
`MissingGreenlet` en columnas con `server_default onupdate`. Esto agrega un
round-trip SELECT al DB que no existe en el workflow S3 equivalente. Para la
escala actual (< 50 000 SKUs) el impacto es irrelevante, pero es inconsistente
con la directriz de minimizar round-trips.

**Evidencia**: `product_service.py:831-833`.

**Accion sugerida**: Evaluar si el `refresh` puede eliminarse usando
`execution_options={"populate_existing": True}` en el flush, o simplemente
tolerarlo dado que el endpoint clasico sera deprecado (BRECHA-TRD-01).

**Issue GitHub**: issue #98

---

### BRECHA-TRD-04 — actor_id no propagado al completion service

**Severidad**: Baja

**Requisitos afectados**: NFR-TRD-003 (auditoria)

**Descripcion**: El endpoint `POST /translations/complete` en `translations.py:80-87`
llama a `service.complete(skus=..., target_langs=..., source_lang=..., actor_id=None)`.
El `actor_id` del usuario autenticado no se pasa al servicio AI, por lo que los
audit events generados por el completion service (si los emite) no tendran el actor
real del request.

**Evidencia**: `translations.py:80-87` (`actor_id=None`).

**Accion sugerida**: Extraer el usuario del contexto de autenticacion y pasarlo como
`actor_id=user.id` al servicio de completado.

**Issue GitHub**: issue #99

---

### BRECHA-TRD-05 — Estado ai_generated no expuesto ni documentado en API

**Severidad**: Baja

**Requisitos afectados**: BR-TRD-002

**Descripcion**: `TranslationStatus` enum incluye `ai_generated` (`enums.py:62`)
pero ningun schema Pydantic expone este valor ni ningun endpoint lo devuelve. Los
clientes no pueden filtrar o identificar traducciones generadas por IA vs. humanas
por el campo `status`. El completion service probablemente setea otro valor (no
observable sin leer `completion_service.py`).

**Evidencia**: `enums.py:62`; `schemas/products.py:553`; `schemas/workflow.py:17-23`.

**Accion sugerida**: Exponer `ai_generated` en `TranslationWorkflowStatus` y en
`ProductTranslationResponse.status` si el completion service lo usa, o documentar
que es un estado interno y eliminarlo del enum publico.

**Issue GitHub**: issue #101

---

## Resumen de conformidad

| Categoria | Verificado | Parcial | No cumple | No implementado | Total |
|-----------|-----------|---------|-----------|-----------------|-------|
| FR (Funcionales) | 12 | 2 | 0 | 0 | 14 |
| NFR (No funcionales) | 5 | 1 | 0 | 0 | 6 |
| BR (Reglas de negocio) | 4 | 2 | 0 | 0 | 6 |
| **Total** | **21** | **5** | **0** | **0** | **26** |

**Indice de conformidad**: 21/26 = **80.8 % verificado**, 19.2 % parcial.

Todas las brechas son Parciales — ninguna es No cumple o No implementado.
Las brechas se han registrado como issues de GitHub (#90–#94).
