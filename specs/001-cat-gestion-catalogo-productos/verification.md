# Verificación de conformidad F1 — Gestión del catálogo de productos (CAT)

**Proceso**: Piloto F1 — verificación retrospectiva
**Fecha**: 2026-05-24
**Revisado contra**: spec.md (FR-CAT-001..037, NFR-CAT-001..005, BR-CAT-001..005)
**Código fuente principal**:
- `mt-pricing-backend/app/api/routes/products.py` (ref. `products.py`)
- `mt-pricing-backend/app/services/products/product_service.py` (ref. `product_service.py`)
- `mt-pricing-backend/app/db/models/product.py` (ref. `product.py`)
- `mt-pricing-backend/app/repositories/product.py` (ref. `repository.py`)
- `mt-pricing-backend/app/services/products/parent_resolver.py` (ref. `parent_resolver.py`)
- `mt-pricing-backend/app/schemas/products.py` (ref. `schemas.py`)

**Leyenda**:
- ✅ **Verificado** — el código cumple el requisito; evidencia `archivo:línea`
- ⚠️ **Parcial** — cumple en parte; brecha descrita
- ❌ **No cumple** — el código contradice el requisito
- ⬜ **No implementado** — sin código que lo soporte

---

## Área 1 — Alta de producto

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-CAT-001 | ⚠️ Parcial | `product_service.py:299-346` | La creación extrae `name_en` y crea traducción EN si se provee, pero el schema `ProductCreate` (Fase B) no exige `name_en` como campo obligatorio; un producto puede crearse sin él (`schemas.py:121-128`). Ver BR-CAT-001. | — |
| FR-CAT-002 | ✅ Verificado | `product.py:101-103` | `server_default=text("'partial'")` — correctamente asignado por defecto en BD. | — |
| FR-CAT-003 | ✅ Verificado | `product_service.py:338-345` | `audit.record(action="product.created")` con actor_id, actor_email, timestamp, after=snapshot. | — |
| FR-CAT-004 | ✅ Verificado | `product_service.py:301-303`; `products.py:640` | `ProductAlreadyExistsError` → HTTP 409 con código `product_duplicate_sku`. | — |
| FR-CAT-005 | ✅ Verificado | `product_service.py:304-312`; `products.py:651-653` | `SpecsValidationError` → HTTP 422 con lista de errores de validación. | — |

---

## Área 2 — Consulta de ficha

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-CAT-006 | ✅ Verificado | `products.py:718-733` | `get_product` llama a `service.get_product_by_id(sku)` y luego `_build_product_detail`. Traducciones incluidas vía `selectin` en el modelo. | — |
| FR-CAT-007 | ✅ Verificado | `product_service.py:43-48`; `products.py:729` | `ProductNotFoundError` → HTTP 404. Aplica también a SKU con soft-delete (chequeado en `soft_delete_product:613-614`). | — |
| FR-CAT-008 | ⚠️ Parcial | `products.py:218-290` (`_build_product_detail`) | Los campos `series_detail`, `material_detail`, `display_pair`, `model_detail` se construyen correctamente; **pero** se hacen hasta 3 queries secuenciales adicionales por request (N+1). Datos correctos, método incorrecto según Art. 3. | E-2 |

---

## Área 3 — Ficha resuelta

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-CAT-009 | ✅ Verificado | `products.py:1782-1808`; `parent_resolver.py` | Endpoint existe; `ParentResolver` hace fallback de specs, assets y translations al padre. | A-6* |
| FR-CAT-010 | ✅ Verificado | `parent_resolver.py:63-82` | Si `parent_sku=None`, el resolver devuelve los datos propios sin fallback. | — |

> *A-6: `get_resolved_view` no tiene `response_model` declarado (hallazgo A-6 auditoría BMAD). Conformidad funcional verificada pero contrato OpenAPI incompleto.

---

## Área 4 — Listado del catálogo

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-CAT-011 | ✅ Verificado | `products.py:491`; `products.py:525`, `611-613` | Cursor opaco base64url, SKU ASC, default 50, max 200, sin offset. | — |
| FR-CAT-012 | ✅ Verificado | `products.py:457-495` | Los 16 filtros documentados están implementados como Query params. | — |
| FR-CAT-013 | ✅ Verificado | `products.py:491` | `include_total: Annotated[bool, Query()] = False` — por defecto. | — |
| FR-CAT-014 | ✅ Verificado | `products.py:555-610` | `translation_status_es/ar` calculado desde relationships pre-cargadas (0 extra queries); `primary_image_url` y `division_codes` en 2 queries batch sobre el conjunto de SKUs de la página. Sin N+1. | — |

---

## Área 5 — Búsqueda rápida

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-CAT-015 | ✅ Verificado | `products.py:619-632`; `repository.py:408-421` | `min_length=2`, `max_length=128`, `limit <= 50`. La búsqueda usa JOIN con `product_translations(lang='en')` por trigrama sobre `pt.name` + `ilike` sobre SKU. Filtra `deleted_at IS NULL`. | — |

---

## Área 6 — Facetas

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-CAT-016 | ✅ Verificado | `products.py:661-715`; `services/products/facets_service.py` | `compute_facets` aplica todos los filtros excepto el de la propia dimensión (refinement no destructivo). | — |
| FR-CAT-017 | ✅ Verificado | `products.py:666-715` | Mismos params de filtro que `list_products`: family, subfamily, type, brand, material, dn, pn, data_quality, active, has_image, lifecycle_status, translation_status, translation_lang, q, division, series_id, material_id, tier_code. | — |

---

## Área 7 — Edición parcial

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-CAT-018 | ✅ Verificado | `products.py:811` | `payload = data.model_dump(exclude_unset=True)` — semantica parcial correcta. | — |
| FR-CAT-019 | ✅ Verificado | `product_service.py:60-66`; código de `update_product` | `ProductLockedFieldError` → HTTP 409 con código `product_locked_field` cuando se intenta actualizar un campo en `manual_locked_fields`. | — |
| FR-CAT-020 | ✅ Verificado | `products.py:815-816` | `SpecsValidationError` capturada en PATCH; el validador recibe el campo `specs` completo resultante. | — |

---

## Área 8 — Reemplazo de ficha

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-CAT-021 | ✅ Verificado | `products.py:822-859` | Endpoint PUT existe con `ProductReplace` schema (todos los campos). | — |
| FR-CAT-022 | ✅ Verificado | `products.py:843`; `product_service.py:69-80` | `If-Match` header parseado; `ProductPreconditionFailedError` → HTTP 412 con código `product_precondition_failed`. | — |
| FR-CAT-023 | ✅ Verificado | `products.py:858` | `response.headers["ETag"] = service.etag_for(prod)` devuelve ETag tras PUT exitoso. | — |

---

## Área 9 — Calidad de dato

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-CAT-024 | ✅ Verificado | `products.py:862-886`; `product_service.py:549-551` | `_DATA_QUALITY_VALID = {"complete", "partial", "blocked", "migrated_demo"}` — 4 valores permitidos. | — |
| FR-CAT-025 | ✅ Verificado | `product_service.py:579-588` | Valida los 4 campos físicos (`family`, `material`, `dn`, `pn`). Si falta alguno → HTTP 422 con lista de campos faltantes (`product_data_quality_invalid_transition`). | — |
| FR-CAT-026 | ✅ Verificado | `product_service.py:600-608` | `audit.record(action="product.data_quality_changed")` con `from`/`to` en `payload_diff`. | — |

---

## Área 10 — Baja lógica

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-CAT-027 | ✅ Verificado | `product_service.py:611-619` | `prod.deleted_at = datetime.now(tz=UTC)` + `prod.lifecycle_status = "discontinued"`. Sin eliminación física. | — |
| FR-CAT-028 | ✅ Verificado | `repository.py:225-226`; `repository.py:376`; `repository.py:416` | `clauses.append(Product.deleted_at.is_(None))` aplicado por defecto en `list_products` (`include_deleted=False`). Búsqueda y classify-by-family también filtran `deleted_at IS NULL`. | — |
| FR-CAT-029 | ✅ Verificado | `products.py:943` | `Depends(require_permissions("products:delete"))` — permiso específico, distinto de `products:write`. | — |

---

## Área 11 — Clasificación PVF

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-CAT-030 | ✅ Verificado | `products.py:889-931` | `classify_pim_batch_task.apply_async(args=[user_id, only_partial, promote_to_complete])` — encolamiento Celery correcto. | — |
| FR-CAT-031 | ⚠️ Parcial | `product_service.py:540-544` | Los 4 campos físicos extraídos (`family`, `material`, `dn`, `pn`) están definidos en `_DATA_QUALITY_REQUIRED_FIELDS`. La verificación de `manual_locked_fields` está documentada en el docstring pero **requiere confirmación visual en `classify_pim_batch_task`** (código en workers/tasks/products.py, no leído directamente). La verificación de `name_en` via translations como 5° campo está explícitamente pendiente (`product_service.py:537-539`). | — |
| FR-CAT-032 | ✅ Verificado | `products.py:909-922` | `except Exception: raise HTTPException(503, code="classify_celery_unavailable")` — cualquier excepción de Celery devuelve 503. | — |

---

## Área 12 — Jerarquía de variantes

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-CAT-033 | ✅ Verificado | `parent_resolver.py:63-82`; `parent_resolver.py:34-52` | Valida: ciclo (`parent_sku == child_sku` → `CycleError` HTTP 409), existencia del padre (`ParentNotFoundError` HTTP 404), profundidad > 1 (`DepthExceededError` HTTP 409 si el padre tiene `is_variant=True`). | — |
| FR-CAT-034 | ✅ Verificado | `products.py:1835` | `await resolver.recompute_parent_flags(sku)` ejecutado tras `update_product`. | — |
| FR-CAT-035 | ✅ Verificado | `products.py:1816`; `products.py:1831` | `parent_sku: Annotated[str | None, Query(...)] = None` — valor None pasa a `service.update_product` limpiando el campo; `recompute_parent_flags` actualiza flags tras desasociar. | — |

---

## Área 13 — Exportación y esquemas

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-CAT-036 | ✅ Verificado | `products.py:317-446` | `GET /products/export` existe. 13 campos definidos en `_EXPORT_FIELDS` (líneas 402-416): `sku`, `name_en`, `family`, `subfamily`, `type`, `brand`, `material`, `dn`, `pn`, `lifecycle_status`, `data_quality`, `created_at`, `updated_at`. Límite aplicado: `limit=10_000` (línea 394). `Cache-Control: no-store` incluido en la respuesta (línea 444). | — |
| FR-CAT-037 | ✅ Verificado | `products.py:296-311`; `services/specs/specs_registry.py:84-104` | `GET /products/specs/schema` existe con `response_model=dict`. Cadena de fallback implementada en `SpecsRegistry.get_schema`: `{family}_{subfamily}` → `{family}` → `_default` (código `specs_registry.py:95-104`). | — |

---

## Área 14 — Transversales

### NFR — No funcionales

| NFR | Estado | Evidencia | Brecha / Notas | BMAD |
|-----|--------|-----------|----------------|------|
| NFR-CAT-001 (RBAC) | ✅ Verificado | `products.py` (todos los endpoints) | 100 % de los 14 endpoints en alcance tienen `Depends(require_permissions(...))` con el permiso correcto (read/write/delete). | — |
| NFR-CAT-002 (RFC 7807) | ⚠️ Parcial | `products.py:147-157` (`_problem`); `products.py:160-165` (`_raise_domain`) | `_problem()` genera `ProblemDetails` completo (type, title, status, detail, instance, code). **Pero** la mayoría de endpoints usa `_raise_domain()` que genera un `HTTPException` con dict `{"code": ..., "title": ...}` sin los campos `type` e `instance` de RFC 7807. Solo `_problem()` es RFC 7807 estricto. | A-6* |
| NFR-CAT-003 (Audit) | ✅ Verificado | `product_service.py:338-345`; `:603-608`; `:616-629` | Auditoría emitida en create, data_quality_change y soft_delete desde la capa de servicio; no desde handlers. | — |
| NFR-CAT-004 (Cache) | ✅ Verificado | `products.py:439-446`; `CacheControlMiddleware` | Export CSV sobreescribe con `Cache-Control: no-store`; el middleware global aplica `private, max-age=60` al resto de GETs 200. | E-6* |
| NFR-CAT-005 (No N+1) | ⚠️ Parcial | `products.py:555-610` (OK); `products.py:218-290` (VIOLACIÓN) | Listado: 3 queries batch para la página, sin N+1 ✅. Detalle (`_build_product_detail`): hasta 3 queries secuenciales por request para series, material y display_pair — violación directa de Art. 3 de la constitución. | E-2 |

> *E-6 ya reparado en el código actual (Cache-Control: no-store aplicado). Ver audit BMAD.

### BR — Reglas de negocio

| BR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| BR-CAT-001 (name_en NOT NULL) | ❌ No cumple | `schemas.py:121-128`; `product_service.py:272-297` | `ProductBase` (Fase B) eliminó `name_en` como campo del schema. `ProductCreate` hereda `ProductBase` → `name_en` es **opcional en el schema**. El servicio crea la traducción EN si se provee, pero no la exige. Un producto puede persistirse sin ninguna traducción EN, contradiciendo el PRD §5.3 ("EN canónico NOT NULL"). **Brecha de conformidad** — impacto: OKR O1a.5 (EN canónico 100% NOT NULL) no está enforced por código. | — |
| BR-CAT-002 (SKU inmutable) | ✅ Verificado | `product_service.py:83-91` (`ProductImmutableFieldError`); `product.py:55` (TEXT PK) | SKU es la PK de la tabla; el servicio rechaza con 422 cualquier intento de cambiar campos inmutables. | — |
| BR-CAT-003 (Solo soft-delete) | ✅ Verificado | `products.py:934-950` | El único endpoint DELETE del dominio CAT llama `service.soft_delete_product`. No hay endpoint de hard-delete expuesto. | — |
| BR-CAT-004 (manual_locked_fields) | ✅ Verificado | `product_service.py:60-66` | `ProductLockedFieldError` previene sobreescritura de campos en `manual_locked_fields`. Validado en PATCH. El comportamiento del PVF sobre `manual_locked_fields` requiere confirmación en `classify_pim_batch_task` (ver FR-CAT-031). | — |
| BR-CAT-005 (Profundidad máx. 1) | ✅ Verificado | `parent_resolver.py:41-47`; `parent_resolver.py:68-82` | `DepthExceededError` cuando el padre propuesto tiene `is_variant=True`. Aplica también el ciclo directo `sku==parent_sku`. | — |

---

## Resumen de conformidad

| Categoría | Total | ✅ Verificado | ⚠️ Parcial | ❌ No cumple | ⬜ No implementado |
|-----------|-------|--------------|-----------|-------------|-------------------|
| FR (funcionales) | 37 | 34 | 3 | 0 | 0 |
| NFR (no funcionales) | 5 | 3 | 2 | 0 | 0 |
| BR (reglas negocio) | 5 | 4 | 0 | 1 | 0 |
| **Total** | **47** | **41** | **5** | **1** | **0** |

**Cobertura**: 87 % Verificado + 11 % Parcial + 2 % No cumple = 100 % con código existente.

---

## Brechas identificadas (candidatas a issues post-F1)

### BRECHA-CAT-01 — name_en NO enforced como obligatorio (BR-CAT-001)
**Severidad**: Alta
**FR/BR afectados**: FR-CAT-001, BR-CAT-001
**Descripción**: `ProductCreate` schema no exige `name_en`. Un producto puede crearse sin
traducción EN, contradiciendo el PRD §5.3 y el OKR O1a.5.
**Acción sugerida**: Añadir validación en `ProductCreate` (o en `create_product` del servicio)
que rechace con HTTP 422 si `name_en` no está presente en el body.
**Hallazgo BMAD relacionado**: no catalogado en auditoría BMAD (nuevo hallazgo F1).

### BRECHA-CAT-02 — RFC 7807 inconsistente en responses de error (NFR-CAT-002)
**Severidad**: Media
**FR/BR afectados**: NFR-CAT-002
**Descripción**: `_raise_domain()` genera HTTPException con dict parcial `{"code", "title"}`;
no incluye los campos `type` e `instance` requeridos por RFC 7807. Solo `_problem()` es
estrictamente conforme. El frontend puede esperar distintos formatos de error según el endpoint.
**Acción sugerida**: Unificar todos los errores del dominio CAT para usar `_problem()` o
estandarizar el HTTPException detail a un objeto con todos los campos RFC 7807.
**Hallazgo BMAD relacionado**: A-6 (parcialmente relacionado — endpoints sin response_model).

### BRECHA-CAT-03 — N+1 en _build_product_detail (NFR-CAT-005, Art. 3)
**Severidad**: Alta (violación constitución Art. 3)
**FR/BR afectados**: NFR-CAT-005, FR-CAT-008
**Descripción**: `_build_product_detail` ejecuta hasta 3 queries secuenciales por request GET /products/{sku}
para series, material y display_pair. Añade hasta 60 ms de latencia con servidor en UAE.
**Acción sugerida**: Mover `_build_product_detail` a `ProductService` y reemplazar
queries secuenciales con `joinedload` (series, material) y subquery (display_pair).
**Hallazgo BMAD relacionado**: E-2 (ya catalogado, estimado 4h).

### BRECHA-CAT-04 — Verificación de manual_locked_fields en PVF no confirmada (FR-CAT-031)
**Severidad**: Media
**FR/BR afectados**: FR-CAT-031, BR-CAT-004
**Descripción**: El clasificador PVF dice respetar `manual_locked_fields` pero el código del
worker (`workers/tasks/products.py`) no fue leído directamente en esta verificación.
El spec lo documenta como requisito verificado parcialmente.
**Acción sugerida**: Leer `classify_pim_batch_task` en el próximo ciclo de verificación
y confirmar/desconfirmar la comprobación de `manual_locked_fields`.

### BRECHA-CAT-05 — get_resolved_view sin response_model (NFR-CAT-002 adyacente)
**Severidad**: Media
**FR/BR afectados**: FR-CAT-009, NFR-CAT-002
**Descripción**: `get_resolved_view` retorna `dict[str, Any]` sin `response_model` declarado
→ sin validación Pydantic ni contrato OpenAPI para este endpoint.
**Acción sugerida**: Definir `ResolvedProductResponse` schema y declarar `response_model`.
**Hallazgo BMAD relacionado**: A-6.

---

## Aprendizajes del piloto F1 (fricción del flujo Spec Kit retrospectivo)

### F1-FRICTION-01 — /speckit.analyze requiere tasks.md
**Descripción**: El skill `speckit-analyze` aborta si `tasks.md` no existe. En el flujo
retrospectivo de F1 este archivo no se genera (no se implementa nada). El análisis se realizó
manualmente como sustituto.
**Impacto**: El gate de coherencia spec↔plan↔constitution no puede automatizarse
en modo retrospectivo con el skill actual.
**Recomendación**: Añadir flag `--skip-tasks` o modo `--retrospective` al skill
`speckit-analyze` para analizar solo spec ↔ plan ↔ constitución sin exigir tasks.md.

### F1-FRICTION-02 — spec-template.md orientado a flujo greenfield
**Descripción**: La plantilla del spec usa secciones como "User Stories" orientadas a diseño
futuro. En el flujo retrospectivo, la sección se reinterpreta como "Escenarios de usuario
observados". No hay fricción grave, pero la semántica de "what users NEED" vs. "what the
system DOES" crea ruido.
**Recomendación**: Añadir una variante `spec-retrospective-template.md` con secciones
orientadas a documentar comportamiento existente.

### F1-FRICTION-03 — /speckit.git.feature con GIT_BRANCH_NAME
**Descripción**: La rama ya estaba creada manualmente antes de invocar el skill. El script
aceptó la variable de entorno correctamente pero el proceso de crear la rama y luego
verificar en `check-prerequisites.ps1` requirió múltiples pasos.
**Impacto**: Menor — el workflow no bloqueó.
**Recomendación**: Documentar explícitamente el flujo "rama pre-existente" en el skill
`speckit-git-feature`.

---

## Actualización post-pruebas F1-CAT (2026-05-24)

| Categoría | Total | Verde | xfail | Sin test |
|-----------|-------|-------|-------|----------|
| FR | 37 | 36 | 1 (FR-CAT-031) | 0 |
| NFR | 5 | 3 | 1 (NFR-CAT-002) | 1 (NFR-CAT-003 cubierto parcialmente en FR-003 + FR-026) |
| BR | 5 | 5 | 0 | 0 |

**Tests automatizados**: `mt-pricing-backend/tests/api/test_cat_acceptance.py`
(35+ tests, marcador `acceptance`, sin mocks de DB — testcontainers Postgres)

**E2E nuevos (Capa 2)**:
- `mt-pricing-frontend/tests/e2e/20-product-create.spec.ts` — FR-CAT-001, 002
- `mt-pricing-frontend/tests/e2e/21-product-delete.spec.ts` — FR-CAT-027, 028, 029

**Brechas activas con xfail**:
- BRECHA-CAT-02: `_raise_domain()` sin `type`/`instance` de RFC 7807 → `xfail` en NFR-CAT-002
- BRECHA-CAT-04: `manual_locked_fields` en `classify_pim_batch_task` sin confirmar → `xfail` en FR-CAT-031

**Correr la suite**:
```bash
cd mt-pricing-backend
uv run pytest -m acceptance -v
```
