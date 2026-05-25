# Verificación de conformidad F1 — Compatibilidad y Variantes (sub-recurso CAT)

**Proceso**: Piloto F1 — verificación retrospectiva
**Fecha**: 2026-05-25
**Revisado contra**: spec.md (FR-CPT-001..012, NFR-CPT-001..004, BR-CPT-001..007)
**Nota**: FR-CAT-033..035 ya verificados en `specs/001-cat-gestion-catalogo-productos/verification.md`
Área 12. Este documento cubre únicamente el alcance adicional.

**Código fuente principal**:
- `mt-pricing-backend/app/db/models/compatibility.py` (ref. `compat_model.py`)
- `mt-pricing-backend/app/db/models/product.py` (ref. `product.py`)
- `mt-pricing-backend/app/repositories/compatibility.py` (ref. `compat_repo.py`)
- `mt-pricing-backend/app/services/compatibility/compatibility_service.py` (ref. `compat_svc.py`)
- `mt-pricing-backend/app/services/products/display_pair_service.py` (ref. `dp_svc.py`)
- `mt-pricing-backend/app/services/products/effective_display_service.py` (ref. `ed_svc.py`)
- `mt-pricing-backend/app/api/routes/products.py` (ref. `products.py`)
- `mt-pricing-backend/app/api/routes/products_display.py` (ref. `display.py`)
- `mt-pricing-backend/app/api/routes/taxonomy_extras.py` (ref. `taxo.py`)
- `mt-pricing-backend/app/schemas/compatibility.py` (ref. `compat_schema.py`)
- `mt-pricing-backend/app/schemas/products_display.py` (ref. `display_schema.py`)

**Leyenda**:
- ✅ **Verificado** — el código cumple el requisito; evidencia `archivo:línea`
- ⚠️ **Parcial** — cumple en parte; brecha descrita
- ❌ **No cumple** — el código contradice el requisito
- ⬜ **No implementado** — sin código que lo soporte

---

## Área 1 — Compatibilidad M:N: endpoints de consulta

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-CPT-001 | ✅ Verificado | `products.py:1402-1423` | `GET /products/{sku}/compatibility` con filtro opcional `kind`. `selectinload` en repo evita N+1. | — |
| FR-CPT-002 | ⚠️ Parcial | `products.py:1426-1462` | Endpoint existe y filtra por `kind`. **Brecha**: respuesta no desnormaliza el producto ORIGEN — `compatible_product=None` siempre. Ver BRECHA-CPT-03. | — |

---

## Área 2 — Compatibilidad M:N: mutaciones

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-CPT-003 | ✅ Verificado | `products.py:1465-1502`; `compat_svc.py:116-185` | POST con validación de ambos SKUs, no auto-enlace, no duplicado. HTTP 201 + respuesta desnormalizada. | — |
| FR-CPT-004 | ✅ Verificado | `products.py:1505-1534`; `compat_svc.py:187-215` | DELETE devuelve 204. `CompatibilityNotFoundError` → 404. Elimina inverso `replaces/replaced_by`. | — |
| FR-CPT-005 | ✅ Verificado | `products.py:1537-1579`; `compat_svc.py:217-266`; `compat_repo.py:184-232` | PUT reemplaza todos los outgoing. Body vacío `[]` elimina todo. Valida destinos antes de mutar. | — |

---

## Área 3 — Tipos y semántica de compatibilidad

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-CPT-006 | ✅ Verificado | `compat_schema.py:20-28` | `CompatibilityKind` Enum: 5 valores exactos. Pydantic valida en request; valor inválido → 422. | — |
| FR-CPT-007 | ✅ Verificado | `compat_repo.py:24-27` (`_INVERSE`); `add_link:129-147`; `remove_link:170-181` | Mapa inverso sincroniza `replaces↔replaced_by` en mismo flush. | — |

---

## Área 4 — Desnormalización y response

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-CPT-008 | ⚠️ Parcial | `products.py:1372-1399` | `_build_compat_response` desnormaliza `compatible_product` correctamente. **Brecha**: omite `owner_type`, `dn_min`, `dn_max` del dict → la respuesta siempre devuelve defaults (`'product'`, `None`, `None`) aunque la fila DB tenga valores reales. Ver BRECHA-CPT-01 / issue #92. | — |
| FR-CPT-009 | ✅ Verificado | `taxo.py:225-274`; `compat_repo.py:238-278` | `GET /vocabularies/series/{series_id}/spare-parts` con filtro DN. Lógica de rango: `(dn_min IS NULL OR dn_min <= dn) AND (dn_max IS NULL OR dn_max >= dn)`. | — |

---

## Área 5 — Display pair

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-CPT-010 | ✅ Verificado | `display.py:84-103`; `dp_svc.py:42-73` | PUT 204. Limpieza simétrica de parejas previas. Self-link → 400 `display_pair_self`. Operación en tx única. | — |
| FR-CPT-011 | ✅ Verificado | `display.py:106-121`; `dp_svc.py:75-88` | DELETE 204. Nullifica ambos lados. Idempotente si no hay pareja (`return` early). | — |

---

## Área 6 — Effective display

| FR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| FR-CPT-012 | ✅ Verificado | `ed_svc.py:76-117`; `display.py:63-81` | GET 200 con `EffectiveDisplayResponse`. Tags desde `series.features_tags`. Certs: dedup por `code`, overrides del producto primero, defaults de serie complementan. `response_model` declarado. | — |

---

## Área 7 — No funcionales

| NFR | Estado | Evidencia | Brecha / Notas | BMAD |
|-----|--------|-----------|----------------|------|
| NFR-CPT-001 (RBAC) | ✅ Verificado | `display.py:71,97,111`; `products.py:1411,1435,1479,1517,1551` | Todos los 8 endpoints tienen `Depends(require_permissions(...))` con permiso correcto. | — |
| NFR-CPT-002 (No N+1 outgoing) | ✅ Verificado | `compat_repo.py:48` | `selectinload(ProductCompatibility.compatible_with)` en `list_for_product`. 1 query batch. | — |
| NFR-CPT-003 (No N+1 effective display) | ✅ Verificado | `ed_svc.py:52-74` | `selectinload(ProductCertification.certification)` en query de overrides; `selectinload(SeriesCertification.certification)` en query de serie. 2-3 queries fijas. | — |
| NFR-CPT-004 (Formato error) | ⚠️ Parcial | `products.py:173-182`; `display.py:53-57` | `_raise_compat` en `products.py` incluye `{type, title, status, code}`. `_raise_domain` en `display.py` usa `ProblemDetails.model_dump()` que incluye todos los campos RFC 7807. **Brecha menor**: `_raise_compat` no incluye `instance`. Ver contexto de BRECHA-CAT-02 del spec núcleo. | — |

---

## Área 8 — Reglas de negocio

| BR | Estado | Evidencia | Brecha / Notas | BMAD |
|----|--------|-----------|----------------|------|
| BR-CPT-001 (No auto-enlace) | ✅ Verificado | `compat_svc.py:140-141`; `compat_model.py:103-107` | Validado en servicio + DB CHECK `chk_no_self_compatibility`. | — |
| BR-CPT-002 (No duplicados) | ✅ Verificado | `compat_model.py:116-120`; `compat_svc.py:165-166` | UNIQUE constraint `uq_product_compatibility(product_sku, compatible_with_sku, kind)`. `IntegrityError` → `CompatibilityDuplicateError` → HTTP 409. | — |
| BR-CPT-003 (Unidireccional) | ✅ Verificado | `compat_model.py:8-14` | Diseño documentado en docstring del modelo. La vista inversa usa `compatibilities_incoming` (viewonly). | — |
| BR-CPT-004 (Display pair 1:1) | ✅ Verificado | `product.py:194-198`; `dp_svc.py:53-64` | Campo escalar nullable `display_pair_sku`. Limpieza de pareja previa antes de establecer nueva. | — |
| BR-CPT-005 (DN range) | ✅ Verificado | `compat_model.py:74-77`; `compat_svc.py:146-151` | Campos `dn_min`/`dn_max` en modelo. Validación `dn_max >= dn_min` en servicio + schema Pydantic + DB CHECK `ck_compat_dn_range`. | — |
| BR-CPT-006 (Auditoría compat) | ⚠️ Parcial | `compat_svc.py:168-184,204-215,258-265` | Auditoría emitida en `add_link`, `remove_link`, `replace_all`. **Brecha**: `display_pair_service.py` no importa `AuditRepository` — set/clear pair NO se auditan. Ver BRECHA-CPT-02 / issue #93. | — |
| BR-CPT-007 (Tags eliminados) | ✅ Verificado | `product.py:412-421` | `Product.tags` hybrid property devuelve `[]` siempre. `ed_svc.py:76-79` usa `series.features_tags`. Comentario en ambos archivos documenta la migración mig. 065. | — |

---

## Resumen de conformidad

| Categoría | Total | ✅ Verificado | ⚠️ Parcial | ❌ No cumple | ⬜ No implementado |
|-----------|-------|--------------|-----------|-------------|-------------------|
| FR (funcionales) | 12 | 10 | 2 | 0 | 0 |
| NFR (no funcionales) | 4 | 3 | 1 | 0 | 0 |
| BR (reglas negocio) | 7 | 6 | 2 | 0 | 0 |  
| **Total** | **23** | **19** | **4** | **0** | **0** |

**Cobertura**: 83 % Verificado + 17 % Parcial + 0 % No cumple = 100 % con código existente.

---

## Brechas identificadas

### BRECHA-CPT-01 — _build_compat_response omite owner_type/dn_min/dn_max — issue #92

**Issue**: https://github.com/br-inn/br-mt-ecommerce/issues/92
**Severidad**: Media
**FR/BR afectados**: FR-CPT-008, FR-CPT-009
**Descripción**: `_build_compat_response` (utilidad interna en `products.py:1372-1399`) no
incluye `owner_type`, `dn_min`, `dn_max` en el dict que pasa a `model_validate`.
`ProductCompatibilityResponse` usa sus defaults (`'product'`, `None`, `None`), ocultando
los valores reales de la fila DB. Las compatibilidades Fase 5 con `owner_type='series'`
o con DN range se devuelven con datos incorrectos en el listado outgoing.
**Evidencia**: `products.py:1388-1399` — faltan 3 claves en el dict.
**Acción sugerida**: Añadir `"owner_type": row.owner_type`, `"dn_min": row.dn_min`,
`"dn_max": row.dn_max` al dict.

### BRECHA-CPT-02 — Display pair no emite auditoría — issue #93

**Issue**: https://github.com/br-inn/br-mt-ecommerce/issues/93
**Severidad**: Baja
**FR/BR afectados**: BR-CPT-006
**Descripción**: `DisplayPairService` no importa ni usa `AuditRepository`. Las operaciones
`set_pair` y `clear_pair` no quedan registradas en `audit_log`. Inconsistente con el
principio de auditoría completa del dominio (NFR-CAT-003 del spec núcleo).
**Evidencia**: `dp_svc.py` — ninguna referencia a `AuditRepository`.
**Acción sugerida**: Inyectar `AuditRepository` en el servicio y emitir eventos
`display_pair.set` / `display_pair.clear`.

### BRECHA-CPT-03 — Lista inverse no desnormaliza el producto origen — issue #94

**Issue**: https://github.com/br-inn/br-mt-ecommerce/issues/94
**Severidad**: Baja-Media
**FR/BR afectados**: FR-CPT-002, FR-CPT-008
**Descripción**: `list_compatibility_inverse` (`products.py:1447-1462`) siempre retorna
`compatible_product=None`. El cliente no puede obtener el nombre/familia del SKU origen
sin hacer N queries adicionales (N+1 desde el frontend).
**Evidencia**: `products.py:1459` — `compatible_product=None` hardcoded.
**Acción sugerida**: Para el endpoint inverse, cargar y desnormalizar `row.product`
(el SKU origen) en `compatible_product` o añadir campo `source_product` al schema.
