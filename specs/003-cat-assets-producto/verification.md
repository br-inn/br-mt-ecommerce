# Verificación de conformidad F1 — Assets/Imágenes de producto (CAT — sub-recurso)

**Proceso**: Piloto F1 — verificación retrospectiva
**Fecha**: 2026-05-25
**Revisado contra**: spec.md (FR-AST-001..021, NFR-AST-001..006, BR-AST-001..007)
**Código fuente principal**:
- `mt-pricing-backend/app/api/routes/products.py` (ref. `products.py`)
- `mt-pricing-backend/app/api/routes/asset_links.py` (ref. `asset_links.py`)
- `mt-pricing-backend/app/services/assets/asset_service.py` (ref. `asset_service.py`)
- `mt-pricing-backend/app/services/assets/asset_link_service.py` (ref. `asset_link_service.py`)
- `mt-pricing-backend/app/services/products/image_service.py` (ref. `image_service.py`)
- `mt-pricing-backend/app/db/models/product.py` (ref. `product.py`)
- `mt-pricing-backend/app/db/models/asset_links.py` (ref. `asset_links_model.py`)
- `mt-pricing-backend/app/schemas/assets.py` (ref. `schemas_assets.py`)
- `mt-pricing-backend/app/schemas/asset_links.py` (ref. `schemas_asset_links.py`)

**Leyenda**:
- ✅ **Verificado** — el código cumple el requisito; evidencia `archivo:línea`
- ⚠️ **Parcial** — cumple en parte; brecha descrita
- ❌ **No cumple** — el código contradice el requisito
- ⬜ **No implementado** — sin código que lo soporte

---

## Área 1 — Listado y consulta de assets

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-AST-001 | ✅ Verificado | `products.py:1163-1184`; `asset_service.py:111-125` | Listado con filtro kind + include_archived; orden por kind, position, created_at. | — |
| FR-AST-002 | ✅ Verificado | `products.py:1177-1180` | Validación de existencia del SKU antes de listar assets via `service.get_product_by_id`. | — |
| FR-AST-003 | ✅ Verificado | `schemas_assets.py:140-169`; `schemas_assets.py:344-352` | `compute_asset_urls` calculado en `@model_validator(mode="after")`; 0 queries adicionales. | — |

---

## Área 2 — Flujo de upload en tres pasos

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-AST-004 | ✅ Verificado | `products.py:1187-1212` | Endpoint `POST /{sku}/assets/upload-url` con `products:write`. Acepta kind, filename, mime_type, locale, alt_text, position. | — |
| FR-AST-005 | ✅ Verificado | `schemas_assets.py:210-218` (Pydantic model_validator); `asset_service.py:159-164` | MIME validado en schema (422 Pydantic) y en servicio (422 AssetValidationError). | — |
| FR-AST-006 | ⚠️ Parcial | `asset_service.py:143-226` | Respuesta con todos los campos documentados. Degradado graceful implementado. **Brecha**: respuesta del endpoint no tiene `response_model` declarado en FastAPI — contrato OpenAPI incompleto. Ver BRECHA-AST-01. | — |
| FR-AST-007 | ✅ Verificado | `asset_service.py:59-83` (`build_storage_path`) | Convención `products/{sku}/{folder}/{uuid}_{filename}` implementada; folders correctos por kind. | — |
| FR-AST-008 | ✅ Verificado | `products.py:1215-1282`; `asset_service.py:229-291` | Endpoint `POST /{sku}/assets/{asset_id}/confirm` con HTTP 201 + `ProductAssetResponse`. | — |
| FR-AST-009 | ✅ Verificado | `products.py:1258-1265` | `generate_thumbnails.delay()` encolado en bloque try/except silencioso. | — |

---

## Área 3 — Designación de imagen primaria

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-AST-010 | ✅ Verificado | `products.py:1285-1302`; `asset_service.py:294-301` | PATCH /primary con `products:write`. Llama `set_primary` que a su vez llama `_set_primary_exclusive`. | — |
| FR-AST-011 | ✅ Verificado | `asset_service.py:303-318` (`_set_primary_exclusive`) | 2 UPDATE en transacción: desmarca todos, marca target. Garantía de exclusividad. | — |

---

## Área 4 — Archivado y restauración

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-AST-012 | ✅ Verificado | `products.py:1305-1322`; `asset_service.py:321-330` | PATCH /archive: `status='archived'`, registra `archived_at`, `archived_by` (user.id). | — |
| FR-AST-013 | ✅ Verificado | `products.py:1325-1342`; `asset_service.py:333-342` | PATCH /restore: `status='active'`, limpia `archived_at=None`, `archived_by=None`. | — |

---

## Área 5 — Eliminación permanente

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-AST-014 | ⚠️ Parcial | `products.py:1345-1364`; `asset_service.py:345-350` | Hard-delete con `products:delete`. **Brecha**: el docstring menciona `assets:certify` para `certificate_pdf` pero el handler no implementa esta lógica diferenciada — solo verifica `products:delete` para todos los kinds. Ver BRECHA-AST-02. | — |

---

## Área 6 — Endpoints deprecados

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-AST-015 | ✅ Verificado | `products.py:1022-1159` | 5 endpoints /images con header `Deprecation: true` y `Link: rel=successor-version`. Proxies funcionales a los nuevos endpoints de assets. | — |

---

## Área 7 — Links polimórficos (asset_links)

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-AST-016 | ⚠️ Parcial | `asset_links.py:68-90`; `asset_link_service.py:37-75` | Endpoint POST /asset-links funcional. **Brecha**: errores de dominio no devuelven `ProblemDetails` RFC 7807 completo (falta `instance`, `code`). Ver BRECHA-AST-04. | — |
| FR-AST-017 | ✅ Verificado | `asset_links.py:49-62`; `asset_link_service.py:78-88` | GET /{owner_type}/{owner_id}/asset-links ordenado correctamente. | — |
| FR-AST-018 | ⚠️ Parcial | `asset_links.py:96-111`; `asset_link_service.py:104-113` | DELETE /asset-links/{link_id} funcional. **Brecha**: no maneja FK RESTRICT cuando el asset tiene links activos (ese error es del endpoint DELETE /assets, no de este). Misma brecha RFC 7807 en error 404. Ver BRECHA-AST-04. | — |
| FR-AST-019 | ✅ Verificado | `asset_link_service.py:51-63` | Chequeo de duplicado antes del INSERT; devuelve 409 con código `asset_link_conflict`. | — |

---

## Área 8 — Mirror de URLs externas

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-AST-020 | ⚠️ Parcial | `asset_service.py:354-387` | `mirror_external()` en servicio está implementado. **Brecha**: No existe endpoint HTTP expuesto en la API REST para disparar esta operación directamente — solo se consume desde workers o código interno. Sin endpoint público, la funcionalidad no es accesible por clientes API. Ver BRECHA-AST-05. | — |

---

## Área 9 — Deduplicación de assets por hash

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-AST-021 | ⚠️ Parcial | `asset_link_service.py:116-160` | `find_or_create_asset_by_hash` implementado en el servicio. **Brecha**: No hay endpoint HTTP expuesto para aprovechar este helper directamente. Se usa solo internamente. Mismo patrón que BRECHA-AST-05. | — |

---

## Requisitos no funcionales

| NFR | Estado | Evidencia | Brecha / Notas | BMAD |
|-----|--------|-----------|----------------|------|
| NFR-AST-001 | ✅ Verificado | `products.py:1032,1051,1121,1146,1173,1195,1226,1294,1314,1334,1356`; `asset_links.py:58,77,105` | Todos los endpoints verifican permisos vía `Depends(require_permissions(...))`. | — |
| NFR-AST-002 | ⚠️ Parcial | `products.py:147-157` (helper `_problem`); `products.py:1211-1212,1255-1256` | Errores 404 usan `_problem` RFC 7807 completo. Errores 422 de `AssetValidationError` se lanzan como `HTTPException(422, detail=str(exc))` — detail es string plano, no ProblemDetails. Ver BRECHA-AST-03. | — |
| NFR-AST-003 | ✅ Verificado | `asset_service.py:105` (`DEFAULT_BUCKET = "product-images"`) | Bucket fijo como constante de clase. | — |
| NFR-AST-004 | ✅ Verificado | `schemas_assets.py:140-169` | URLs calculadas en memoria desde `variants` JSONB; 0 queries adicionales por asset. | — |
| NFR-AST-005 | ✅ Verificado | `schemas_assets.py:201-208`; `asset_service.py:73-76` | Validación de filename en schema Pydantic y en función `_safe_filename` del servicio. | — |
| NFR-AST-006 | ✅ Verificado | `asset_service.py:169-211` | Detección de placeholder en `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY`; retorna payload fake sin excepción. | — |

---

## Reglas de negocio

| BR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| BR-AST-001 | ✅ Verificado | `asset_service.py:303-318` | Exclusividad de primario por (sku, kind) garantizada. | — |
| BR-AST-002 | ✅ Verificado | `products.py:1258-1265` | Celery encolado solo para photo/banner/mirror_url. | — |
| BR-AST-003 | ✅ Verificado | `schemas_assets.py:73-84` (`_MAX_BYTES_RULES`) | Límites por kind definidos y validados en `asset_service.py:253-258`. | — |
| BR-AST-004 | ✅ Verificado | `product.py:614` (`uq_assets_bucket_path` índice único) | Unicidad bucket+path a nivel de BD. | — |
| BR-AST-005 | ✅ Verificado | `asset_service.py:119-121` | Filtro `status != 'archived'` por defecto en `list_for_product`. | — |
| BR-AST-006 | ⚠️ Parcial | `asset_links_model.py:62-64` (`ON DELETE RESTRICT`) | FK RESTRICT existe en BD. **Brecha**: el handler `DELETE /assets/{id}` no captura `IntegrityError` de FK para devolver un error de dominio amigable (409 o 422). Ver BRECHA-AST-03. | — |
| BR-AST-007 | ✅ Verificado | `asset_links_model.py:37-52`; `schemas_asset_links.py:25-45` | 5 owner_types y 12 roles validados en BD (CheckConstraint) y en schema (StrEnum). | — |

---

## Brechas identificadas

### BRECHA-AST-01 — `POST /assets/upload-url` sin `response_model` en FastAPI

**Severidad**: Baja

**Requisito afectado**: FR-AST-006, NFR-AST-002

**Evidencia**: `products.py:1187-1212` — el decorador `@router.post` no declara
`response_model=`. Retorna `dict[str, Any]`.

**Descripción**: El endpoint de solicitud de URL firmada devuelve un dict sin schema
Pydantic declarado en FastAPI. El contrato OpenAPI generado no documenta la forma
exacta del response, lo que dificulta la validación por clientes y la generación
de SDK. Este mismo patrón aparece en el endpoint legacy `/images/upload-url`.

**Acción sugerida**: Crear schema `ProductAssetUploadResponse` (Pydantic) con los
campos `storage_path`, `upload_url`, `token`, `method`, `headers`, `expires_in`,
`bucket`, `kind`, y declararlo como `response_model` en el decorador.

**Issue**: #100

---

### BRECHA-AST-02 — Hard-delete de `certificate_pdf` sin permiso `assets:certify`

**Severidad**: Media

**Requisito afectado**: FR-AST-014, NFR-AST-001

**Evidencia**: `products.py:1345-1364` — docstring indica que `assets:certify` es
necesario para `certificate_pdf`, pero el handler solo verifica `products:delete`
para todos los kinds.

**Descripción**: El comentario en el docstring indica la intención de requerir un
permiso especial para eliminar certificados PDF (documentos con valor regulatorio),
pero la lógica de verificación de permisos diferenciada por kind no está implementada.
Cualquier usuario con `products:delete` puede eliminar un `certificate_pdf`.

**Acción sugerida**: Agregar verificación en el handler: si `asset.kind == 'certificate_pdf'`,
requerir permiso `assets:certify` adicionalmente a `products:delete`.

**Issue**: #102

---

### BRECHA-AST-03 — Errores 422 de assets y FK RESTRICT no devuelven RFC 7807

**Severidad**: Media

**Requisito afectado**: NFR-AST-002, BR-AST-006

**Evidencia**:
- `products.py:1211-1212`: `raise HTTPException(status_code=422, detail=str(exc))`
- `products.py:1255-1256`: `raise HTTPException(status_code=422, detail=str(exc))`
- FK RESTRICT: no hay manejo de `sqlalchemy.exc.IntegrityError` en `delete_asset`

**Descripción**: Dos brechas relacionadas:
1. Los errores `AssetValidationError` (MIME inválido, bytes_size excedido) se
   propagan como `HTTPException` con `detail` como string plano. No siguen RFC 7807
   — faltan campos `type`, `instance`, `code`.
2. Si se intenta borrar un `ProductAsset` que tiene `AssetLink`s activos, la FK
   `ON DELETE RESTRICT` genera un `IntegrityError` de SQLAlchemy no capturado,
   resultando en HTTP 500 en lugar de un 409 descriptivo.

**Acción sugerida**:
1. Envolver `AssetValidationError` en el helper `_problem()` con código apropiado.
2. Capturar `IntegrityError` en `delete_asset` y devolver HTTP 409 con
   `ProblemDetails` indicando que el asset tiene links activos.

**Issue**: #103

---

### BRECHA-AST-04 — `_raise_domain` en `asset_links.py` no cumple RFC 7807 completo

**Severidad**: Baja

**Requisito afectado**: NFR-AST-002 (aplicado a asset_links)

**Evidencia**: `asset_links.py:39-43`:
```python
def _raise_domain(err: AssetLinkDomainError) -> None:
    raise HTTPException(
        status_code=err.status_code,
        detail={"type": "about:blank", "title": err.code, "detail": err.message},
    )
```

**Descripción**: El `detail` del HTTPException usa `about:blank` para `type` (genérico)
y no incluye los campos `status`, `instance`, ni `code` que define el helper `_problem`
en `products.py`. Hay inconsistencia entre el formato de errores de asset_links y el
del módulo principal de productos.

**Acción sugerida**: Unificar `_raise_domain` en `asset_links.py` con el patrón del
helper `_problem()` en `products.py`, añadiendo `instance` (desde `request.url.path`),
`status`, y normalizando `type` a `https://mtme-api/errors/{code}`.

**Issue**: #104

---

### BRECHA-AST-05 — `mirror_external` y dedup por hash sin endpoint HTTP público

**Severidad**: Baja

**Requisito afectado**: FR-AST-020, FR-AST-021

**Evidencia**:
- `asset_service.py:354-387` (`mirror_external`) — método de servicio sin endpoint.
- `asset_link_service.py:116-160` (`find_or_create_asset_by_hash`) — helper sin endpoint.

**Descripción**: Las funcionalidades de mirror de URLs externas y deduplicación por
SHA-256 están implementadas en la capa de servicio pero no están expuestas como
endpoints HTTP. Solo son accesibles desde workers Celery o código interno. Los clientes
de la API no pueden disparar un mirror de imagen externa directamente.

**Acción sugerida**: Si el caso de uso está activo (operador sube imagen por URL),
considerar exponer `POST /products/{sku}/assets/mirror` que acepte `{ url, kind }`
y devuelva el `ProductAsset` con `status='pending_upload'`. Si el caso de uso es
puramente interno (scraper), documentarlo como tal y cerrar como no-brecha.

**Issue**: #106

---

## Resumen de conformidad

| Categoría | Verificado | Parcial | No cumple | No implementado | Total |
|-----------|------------|---------|-----------|-----------------|-------|
| FR (Funcionales) | 14 | 7 | 0 | 0 | 21 |
| NFR (No funcionales) | 5 | 1 | 0 | 0 | 6 |
| BR (Reglas de negocio) | 6 | 1 | 0 | 0 | 7 |
| **Total** | **25** | **9** | **0** | **0** | **34** |

**Tasa de conformidad**: 25/34 = 73.5 % Verificado; 9/34 = 26.5 % Parcial.
No hay requisitos incumplidos ni no implementados.

**Nota**: Todos los requisitos parciales corresponden a brechas de calidad
(OpenAPI incompleto, RFC 7807 inconsistente, permiso diferenciado no implementado)
— no afectan la funcionalidad básica del sub-recurso.
