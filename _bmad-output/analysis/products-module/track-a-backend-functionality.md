# Track A — Funcionalidad Backend
**Fecha:** 2026-05-20

## A1 — Inventario de endpoints

**Total endpoints auditados: 146** (9 archivos de rutas)

| Método | Path | Handler | Auth (permiso) | HTTP codes | Test? |
|--------|------|---------|----------------|------------|-------|
| **products.py** (prefix `/products`) | | | | | |
| GET | /products/specs/schema | `get_specs_schema` | products:read | 200 | No |
| GET | /products/export | `export_products_csv` | products:read | 200, 422 | No |
| GET | /products | `list_products` | products:read | 200, 400, 422 | Sí |
| GET | /products/search | `search_products` | products:read | 200 | Sí |
| POST | /products | `create_product` | products:write | 201, 409, 422 | Sí |
| GET | /products/facets | `get_facets` | products:read | 200 | No |
| GET | /products/{sku} | `get_product` | products:read | 200, 404 | Sí |
| GET | /products/{sku}/certificates | `get_product_certificates` | products:read | 200 | No |
| GET | /products/{sku}/flow-data | `get_product_flow_data` | products:read | 200 | No |
| PATCH | /products/{sku} | `update_product` | products:write | 200, 404, 409, 422 | Sí |
| PUT | /products/{sku} | `replace_product` | products:write | 200, 404, 409, 412, 422 | Sí |
| PATCH | /products/{sku}/data-quality | `patch_product_data_quality` | products:write | 200, 404, 422 | Sí |
| POST | /products/classify | `classify_pim_batch` | products:write | 202, 503 | No |
| DELETE | /products/{sku} | `delete_product` | products:delete | 204, 404 | Sí |
| GET | /products/{sku}/translations | `list_translations` | products:read | 200, 404 | Sí |
| PUT | /products/{sku}/translations/{lang} | `upsert_translation` | products:write | 200, 404 | Sí |
| PATCH | /products/{sku}/translations/{lang} | `patch_translation` | products:write | 200, 404 | Parcial |
| POST | /products/{sku}/translations/{lang}/approve | `approve_translation` | products:write | 200, 404 | Sí |
| GET | /products/{sku}/images | `list_images` | products:read | 200, 404 | No |
| POST | /products/{sku}/images/upload-url | `get_image_upload_url` | products:write | 200, 404 | Parcial |
| POST | /products/{sku}/images/confirm | `confirm_image_upload` | products:write | 201, 404, 422 | No |
| POST | /products/{sku}/images/{image_id}/set-primary | `set_primary_image` | products:write | 200, 404 | No |
| DELETE | /products/{sku}/images/{image_id} | `delete_image` | products:delete | 204, 404 | No |
| GET | /products/{sku}/assets | `list_assets` | products:read | 200, 404 | No |
| POST | /products/{sku}/assets/upload-url | `get_asset_upload_url` | products:write | 200, 404, 422 | No |
| POST | /products/{sku}/assets/{asset_id}/confirm | `confirm_asset_upload` | products:write | 201, 404, 422 | No |
| PATCH | /products/{sku}/assets/{asset_id}/primary | `set_primary_asset` | products:write | 200, 404 | No |
| PATCH | /products/{sku}/assets/{asset_id}/archive | `archive_asset` | products:write | 200, 404 | No |
| PATCH | /products/{sku}/assets/{asset_id}/restore | `restore_asset` | products:write | 200, 404 | No |
| DELETE | /products/{sku}/assets/{asset_id} | `delete_asset` | products:delete | 204, 404 | No |
| GET | /products/{sku}/compatibility | `list_compatibility` | products:read | 200, 404 | No |
| GET | /products/{sku}/compatibility/inverse | `list_compatibility_inverse` | products:read | 200, 404 | No |
| POST | /products/{sku}/compatibility | `add_compatibility` | products:write | 201, 404, 409, 422 | No |
| DELETE | /products/{sku}/compatibility/{compatible_with_sku}/{kind} | `remove_compatibility` | products:write | 204, 404 | No |
| PUT | /products/{sku}/compatibility | `replace_compatibility` | products:write | 200, 404, 409, 422 | No |
| GET | /products/{sku}/materials | `list_materials` | products:read | 200 | No |
| POST | /products/{sku}/materials | `upsert_material` | products:write | 201 | No |
| DELETE | /products/{sku}/materials/{component}/{position} | `delete_material` | products:write | 204 | No |
| PUT | /products/{sku}/materials | `replace_materials` | products:write | 200 | No |
| GET | /products/{sku}/connections | `list_connections` | products:read | 200 | No |
| POST | /products/{sku}/connections | `upsert_connection` | products:write | 201 | No |
| DELETE | /products/{sku}/connections/{position} | `delete_connection` | products:write | 204 | No |
| PUT | /products/{sku}/connections | `replace_connections` | products:write | 200 | No |
| GET | /products/{sku}/resolved | `get_resolved_view` | products:read | 200 | No |
| POST | /products/{sku}/parent | `set_parent` | products:write | 200, 404 | No |
| GET | /products/{sku}/tech-tables | `list_tech_tables` | products:read | 200 | No |
| PUT | /products/{sku}/tech-tables/{kind} | `upsert_tech_table` | products:write | 200, 422 | No |
| DELETE | /products/{sku}/tech-tables/{kind} | `delete_tech_table` | products:write | 204, 404 | No |
| GET | /products/{sku}/releases | `list_releases` | products:read | 200 | No |
| POST | /products/{sku}/releases | `create_release` | products:write | 201, 404, 409 | No |
| PATCH | /products/{sku}/releases/{market_code} | `patch_release` | products:write | 200, 404 | No |
| POST | /products/{sku}/releases/{market_code}/activate | `activate_release` | products:write | 200, 404 | No |
| POST | /products/{sku}/releases/{market_code}/deactivate | `deactivate_release` | products:write | 200, 404 | No |
| GET | /products/{sku}/uom-conversions | `list_uom_conversions` | products:read | 200 | No |
| POST | /products/{sku}/uom-conversions | `create_uom_conversion` | products:write | 201, 404, 409 | No |
| DELETE | /products/{sku}/uom-conversions/{uom_from}/{uom_to} | `delete_uom_conversion` | products:write | 204, 404 | No |
| GET | /products/{sku}/bore-dimensions | `list_bore_dimensions` | products:read | 200, 404 | No |
| GET | /products/{sku}/datasheets | `list_datasheets` | products:read | 200, 404 | No |
| **products_display.py** (mounted under `/products`) | | | | | |
| GET | /products/{sku}/effective-display | `get_effective_display` | products:read | 200, 404 | No |
| PUT | /products/{sku}/display-pair | `set_display_pair` | products:write | 204, 400, 404 | No |
| DELETE | /products/{sku}/display-pair | `clear_display_pair` | products:write | 204, 404 | No |
| **ficha_enrich.py** | | | | | |
| POST | /products/{sku}/ficha-enrich/preview | `preview_ficha_enrich` | products:write | 200, 404, 413, 422 | No (hay tests de servicio) |
| POST | /products/{sku}/ficha-enrich/apply | `apply_ficha_enrich` | products:write | 200, 404, 422 | No (hay tests de servicio) |
| POST | /ficha-enrich/series/preview | `preview_ficha_series` | products:write | 200, 413, 422 | No |
| POST | /ficha-enrich/series/apply | `apply_ficha_series` | products:write | 200, 422 | No |
| **attributes.py** | | | | | |
| GET | /attributes | `list_attributes` | products:read | 200 | Sí |
| GET | /attributes/{attr_id}/options | `list_attribute_options` | products:read | 200, 404 | Sí |
| GET | /families/{family_id}/attributes | `list_family_attributes` | products:read | 200 | No |
| POST | /admin/attributes | `admin_create_attribute` | admin:vocabularies | 201, 409 | Sí |
| PATCH | /admin/attributes/{attr_id} | `admin_patch_attribute` | admin:vocabularies | 200, 404 | Sí |
| DELETE | /admin/attributes/{attr_id} | `admin_delete_attribute` | admin:vocabularies | 204, 404, 409 | Sí |
| POST | /admin/attributes/{attr_id}/options | `admin_create_option` | admin:vocabularies | 201, 400, 409 | Sí |
| PATCH | /admin/attributes/{attr_id}/options/{option_id} | `admin_patch_option` | admin:vocabularies | 200, 404 | No |
| DELETE | /admin/attributes/{attr_id}/options/{option_id} | `admin_delete_option` | admin:vocabularies | 204, 404 | No |
| POST | /admin/families/{family_id}/attributes/{attr_id} | `admin_link_family_attribute` | admin:vocabularies | 201, 400, 404, 409 | Sí |
| DELETE | /admin/families/{family_id}/attributes/{attr_id} | `admin_unlink_family_attribute` | admin:vocabularies | 204, 404 | Sí |
| GET | /products/{sku}/attributes | `list_product_attributes` | products:read | 200 | Sí |
| PUT | /products/{sku}/attributes/{attr_code} | `upsert_product_attribute` | products:write | 200, 400, 404, 409 | Sí |
| DELETE | /products/{sku}/attributes/{attr_code} | `delete_product_attribute` | products:write | 204, 404 | Sí |
| **dimensions.py** | | | | | |
| GET | /actuation-codes | `list_actuation_codes` | products:read | 200 | Sí |
| GET | /standards | `list_standards` | products:read | 200 | Sí |
| GET | /products/{sku}/dimensions | `get_product_dimensions` | products:read | 200, 404 | Sí |
| GET | /products/{sku}/pressure-temperature | `get_product_pt_curve` | products:read | 200, 404 | Sí |
| POST | /admin/standards | `admin_create_standard` | admin:vocabularies | 201, 409 | Sí |
| PATCH | /admin/standards/{std_id} | `admin_patch_standard` | admin:vocabularies | 200, 404, 409 | Sí |
| DELETE | /admin/standards/{std_id} | `admin_delete_standard` | admin:vocabularies | 204, 404 | Sí |
| POST | /admin/families/{family_id}/dimension-columns | `admin_create_dimension_column` | admin:vocabularies | 201, 409 | Sí |
| PATCH | /admin/families/{family_id}/dimension-columns/{column_id} | `admin_patch_dimension_column` | admin:vocabularies | 200, 404 | No |
| DELETE | /admin/families/{family_id}/dimension-columns/{column_id} | `admin_delete_dimension_column` | admin:vocabularies | 204, 404, 409 | Sí |
| POST | /admin/products/{sku}/dimension-rows | `admin_create_dimension_row` | admin:vocabularies | 201, 404, 409 | Sí |
| PUT | /admin/products/{sku}/dimension-rows/{row_id} | `admin_patch_dimension_row` | admin:vocabularies | 200, 404 | Sí |
| DELETE | /admin/products/{sku}/dimension-rows/{row_id} | `admin_delete_dimension_row` | admin:vocabularies | 204, 404 | No |
| PUT | /admin/products/{sku}/dimension-rows/{row_id}/cells/{column_id} | `admin_upsert_dimension_cell` | admin:vocabularies | 200, 400, 404, 409 | Sí |
| POST | /admin/products/{sku}/pressure-temperature | `admin_add_pt_point` | admin:vocabularies | 201, 400, 404 | Sí |
| PUT | /admin/products/{sku}/pressure-temperature/{point_id} | `admin_patch_pt_point` | admin:vocabularies | 200, 404 | No |
| DELETE | /admin/products/{sku}/pressure-temperature/{point_id} | `admin_delete_pt_point` | admin:vocabularies | 204, 404 | No |
| **taxonomy_registry.py** | | | | | |
| GET | /taxonomies/registry | `list_registry` | products:read | 200 | Sí |
| GET | /taxonomies/{type_slug} | `get_type` | products:read | 200, 404 | Sí |
| GET | /taxonomies/{type_slug}/nodes | `list_nodes` | products:read | 200, 404 | Sí |
| GET | /taxonomies/{type_slug}/nodes/{node_slug} | `get_node` | products:read | 200, 404 | Sí |
| GET | /taxonomies/{type_slug}/nodes/{node_slug}/descendants | `list_descendants` | products:read | 200, 404 | Sí |
| GET | /products/{sku}/taxonomies | `list_product_taxonomies` | products:read | 200 | No |
| POST | /admin/taxonomies/types | `create_type` | admin:taxonomy | 201, 409 | Sí |
| PATCH | /admin/taxonomies/types/{type_slug} | `update_type` | admin:taxonomy | 200, 403, 404 | No |
| DELETE | /admin/taxonomies/types/{type_slug} | `delete_type` | admin:taxonomy | 204, 403, 404 | No |
| POST | /admin/taxonomies/{type_slug}/nodes | `create_node` | admin:taxonomy | 201, 400, 409 | Sí |
| PATCH | /admin/taxonomies/{type_slug}/nodes/{node_slug} | `update_node` | admin:taxonomy | 200, 404 | No |
| DELETE | /admin/taxonomies/{type_slug}/nodes/{node_slug} | `delete_node` | admin:taxonomy | 204, 404 | Sí |
| POST | /admin/taxonomies/{type_slug}/aliases | `create_alias` | admin:taxonomy | 201, 400, 404 | No |
| POST | /admin/products/{sku}/taxonomies | `link_product_to_node` | admin:taxonomy | 201, 404 | No |
| DELETE | /admin/products/{sku}/taxonomies/{node_id} | `unlink_product_from_node` | admin:taxonomy | 204, 404 | No |
| GET | /admin/family-schemas/{family_slug} | `get_family_schema` | admin:taxonomy | 200, 404 | No |
| POST | /admin/family-schemas | `create_family_schema` | admin:taxonomy | 201 | No |
| **taxonomy_extras.py** | | | | | |
| GET | /divisions | `list_divisions` | products:read | 200 | Sí |
| GET | /series-tiers | `list_series_tiers` | products:read | 200 | No |
| GET | /series | `list_series` | products:read | 200 | No |
| GET | /series/{series_id} | `get_series` | products:read | 200, 404 | No |
| GET | /series/{series_id}/translations | `list_series_translations` | products:read | 200, 404 | No |
| GET | /series/{series_id}/spare-parts | `list_series_spare_parts` | products:read | 200, 404, 422 | No |
| GET | /materials | `list_materials` | products:read | 200 | No |
| POST | /admin/divisions | `admin_create_division` | admin:taxonomy | 201, 409 | No |
| PATCH | /admin/divisions/{division_id} | `admin_patch_division` | admin:taxonomy | 200, 404 | No |
| DELETE | /admin/divisions/{division_id} | `admin_delete_division` | admin:taxonomy | 204, 404 | No |
| POST | /admin/series | `admin_create_series` | admin:taxonomy | 201, 409 | No |
| PATCH | /admin/series/{series_id} | `admin_patch_series` | admin:taxonomy | 200, 404 | No |
| DELETE | /admin/series/{series_id} | `admin_delete_series` | admin:taxonomy | 204, 404 | No |
| POST | /admin/series/{series_id}/divisions/{division_id} | `admin_link_series_division` | admin:taxonomy | 204, 404 | No |
| DELETE | /admin/series/{series_id}/divisions/{division_id} | `admin_unlink_series_division` | admin:taxonomy | 204, 404 | No |
| PUT | /admin/series/{series_id}/translations/{lang} | `admin_upsert_series_translation` | admin:taxonomy | 200, 400, 404 | No |
| DELETE | /admin/series/{series_id}/translations/{lang} | `admin_delete_series_translation` | admin:taxonomy | 204, 404 | No |
| POST | /admin/materials | `admin_create_material` | admin:taxonomy | 201, 409 | No |
| PATCH | /admin/materials/{material_id} | `admin_patch_material` | admin:taxonomy | 200, 404 | No |
| DELETE | /admin/materials/{material_id} | `admin_delete_material` | admin:taxonomy | 204, 404 | No |
| GET | /products/{sku}/divisions | `list_product_divisions` | products:read | 200 | No |
| POST | /products/{sku}/divisions | `add_product_division` | products:write | 201, 404 | No |
| PUT | /products/{sku}/divisions | `replace_product_divisions` | products:write | 200, 404 | No |
| DELETE | /products/{sku}/divisions/{division_id} | `remove_product_division` | products:write | 204, 404 | No |
| **translations_workflow.py** (prefix `/products`) | | | | | |
| POST | /products/{sku}/translations/{lang}/request-review | `request_review` | products:write | 200, 404, 409 | Sí (completo) |
| POST | /products/{sku}/translations/{lang}/reject | `reject_translation` | products:write | 200, 403, 404, 409, 422 | Sí (completo) |
| POST | /products/{sku}/translations/mark-stale | `mark_stale` | products:write | 200, 404 | Sí (completo) |
| **asset_links.py** | | | | | |
| GET | /{owner_type}/{owner_id}/asset-links | `list_asset_links_for_owner` | products:read | 200, 404 | Sí (servicio) |
| POST | /asset-links | `create_asset_link` | products:write | 201, 404, 409 | Sí (servicio) |
| DELETE | /asset-links/{link_id} | `delete_asset_link` | products:write | 204, 404 | Sí (servicio) |

---

## A2 — Cobertura de tests

- **Total endpoints:** 146
- **Con test completo (happy + unhappy paths):** 38 (26%)
- **Solo happy path / tests parciales:** 18 (12%)
- **Sin test:** 90 (62%)

**Grupos con mejor cobertura:**
- `translations_workflow.py`: 3/3 endpoints con tests completos (happy + estado inválido + 404)
- `attributes.py`: ~8/14 endpoints con tests de servicio
- `dimensions.py`: ~10/17 con tests de servicio unit
- `products.py` core CRUD: list, create, get, patch, delete, translations — cubiertos en `tests/integration/test_products.py` y `tests/api/test_products_*.py`
- `taxonomy_registry.py`: reads + create/delete node cubiertos en `tests/db/test_taxonomy_registry.py`
- `asset_links.py`: cubiertos a nivel servicio en `tests/unit/services/assets/test_asset_link_service.py`

**Endpoints críticos sin test de ningún tipo:**
- `GET /products/facets` — usado por sidebar de filtros del catálogo
- Todo el árbol de assets: `list_assets`, `get_asset_upload_url`, `confirm_asset_upload`, `set_primary_asset`, `archive_asset`, `restore_asset`, `delete_asset`
- Todo el árbol de releases (5 endpoints) — funcionalidad M1-01
- `POST /products/{sku}/uom-conversions`, `DELETE /products/{sku}/uom-conversions/{...}`
- `POST /ficha-enrich/series/apply` — crea productos en masa (máximo riesgo)
- Todo el árbol `/admin/taxonomies/` (PATCH types, PATCH nodes, aliases, product links)
- Todo el árbol `/admin/series/` y `/admin/divisions/`
- `GET /products/{sku}/compatibility` y subrutas de compatibilidad

---

## A3 — Lógica de negocio

**State machines detectadas:**

1. **Translation workflow FSM** (`services/products/translation_workflow.py`): estados `draft → pending_review → approved → stale`. Transiciones en `_VALID_TRANSITIONS`. Constraint four-eyes en `approve` (actor != translated_by). El estado legacy `pending` se acepta como origen. Bien encapsulado con tests completos.

2. **Product data_quality FSM**: transiciones `partial ↔ complete ↔ blocked`. Para promover a `complete`, valida campos obligatorios poblados. La promoción automática también ocurre vía `classify_pim_batch_task`.

3. **Release lifecycle** (inline en `products.py`): `activate_release` → `is_active=True, status="active", released_at=now()`. `deactivate_release` → `is_active=False, status="suspended"`. **No hay validación de transición** — se puede activar un release ya activo sin restricción.

**Reglas de negocio hardcodeadas (no configurables):**
- `_MAX_PDF_BYTES = 50 * 1024 * 1024` en `ficha_enrich.py` (línea 49) — límite de 50 MB no configurable por settings
- `limit=10_000` en `export_products_csv` (línea 396) — máximo de exportación hardcodeado
- Cursor pagination max `limit=200` en `list_products` (línea 475)
- Translation lang limitado a `^(es|ar)$` — solo dos idiomas soportados
- `_TTL = 3600` en `list_datasheets` (línea 2310) — TTL de signed URL no configurable
- `kind` de tech-tables limitado a `materials_matrix|dimensions_by_dn|pressure_temperature`

**Validaciones potencialmente faltantes:**
- `list_releases`, `list_uom_conversions`, `list_tech_tables`, `list_product_divisions`: no validan existencia del SKU — retornan lista vacía (no 404) si el producto no existe
- `add_product_division` hace re-fetch post-add con 2 round-trips (violación de directriz de performance)
- `apply_ficha_series` llama `session.commit()` explícitamente en el handler — único endpoint que hace commit explícito; el resto confía en el session middleware

---

## A4 — Manejo de errores

**Patrón consistente (bueno):** La mayoría de rutas delegan en excepciones de dominio tipadas que se traducen a HTTPException con ProblemDetails RFC 7807 via helpers `_raise_domain()`. Patrón correcto.

**Rutas con problemas de error handling:**

| Ruta | Problema | Archivo:línea aprox. |
|------|---------|---------------------|
| `PATCH /products/{sku}/assets/{asset_id}/primary` | Retorna `_problem()` (JSONResponse 200) en lugar de raise HTTPException 404 — bypasea middleware de errores | `products.py:1301` |
| `PATCH /products/{sku}/assets/{asset_id}/archive` | Mismo patrón | `products.py:1321` |
| `PATCH /products/{sku}/assets/{asset_id}/restore` | Mismo patrón | `products.py:1341` |
| `GET /products/{sku}/datasheets` | `except Exception: signed_url = ""` silencia fallos de storage sin logging ni error al cliente | `products.py:2332` |
| `POST /products/classify` | `except Exception` captura toda excepción Celery y retorna 503 sin detail del error original | `products.py:897` |
| `GET /products/{sku}/resolved` | No valida existencia del SKU antes de llamar al resolver; puede silenciar 404 | `products.py:1773` |
| `list_releases`, `list_uom_conversions`, `list_tech_tables` | Retornan `[]` con 200 para SKUs inexistentes — comportamiento incorrecto | `products.py:1955, 2131, 1839` |

---

## A5 — Schemas Pydantic

**Inconsistencias detectadas:**

1. **`admin_list_series_certifications` retorna `list[dict]`** sin `response_model` tipado — sin validación de salida, sin documentación OpenAPI del contrato. `taxonomy_extras.py:566`.

2. **`get_resolved_view` retorna `dict[str, Any]`** sin response_model declarado — sin validación, sin documentación, sin serialización garantizada. `products.py:1773`.

3. **`list_releases` y `create_release`** declaran `response_model=ProductReleaseResponse` pero el handler retorna el ORM object directamente — frágil si la relación tiene campos lazy-loaded.

4. **`_DatasheetSummary`** definido inline en el módulo de rutas (no en `app/schemas/`) — dificulta testing unitario y reutilización.

5. **`set_parent`** retorna `dict[str, Any]` sin response_model — sin validación de salida.

6. **`ProductAssetConfirmRequest`** acepta `locale` sin validar que sea código IETF válido — datos malformados pueden llegar a DB.

7. **Campos internos en respuesta pública:** `ProductResponse.division_codes` se construye dinámicamente en el handler. Si el fetch de division_codes falla silenciosamente, el campo aparece vacío sin indicación de error.

8. **Validación cruzada path/body en el handler**: `admin_link_family_attribute` valida `data.attribute_id != attr_id` en la capa de routing en lugar de en el schema — un `@model_validator` sería más apropiado.

---

## Top 5 riesgos (priorizados por impacto)

1. **[Crítico] 90 endpoints sin cobertura de tests (62%)** — Los endpoints de assets (upload, confirm, primary, archive, restore), todos los releases, todas las rutas de taxonomía admin, y `ficha-enrich/series/apply` (que crea productos en masa) no tienen ningún test. Un cambio en cualquiera puede romper producción sin detección en CI.

2. **[Alto] `apply_ficha_series` hace `session.commit()` explícito en el handler** — `ficha_enrich.py:319`. Si `write_model_data` o `save_ficha_document` lanzan excepción después de que algunos SKUs se han aplicado, el commit parcial ya ocurrió. Puede dejar la DB con productos parcialmente creados sin posibilidad de rollback automático.

3. **[Alto] `list_releases`, `list_uom_conversions`, `list_tech_tables` retornan 200+`[]` para SKUs inexistentes** — Un cliente que llama a `/products/SKU-INEXISTENTE/releases` recibe `[]` con 200 OK en lugar de 404. Enmascara errores de integración y dificulta la detección de bugs en producción. Las rutas de write correspondientes sí validan existencia — inconsistencia read vs write.

4. **[Medio] `set_primary_asset`, `archive_asset`, `restore_asset` retornan JSONResponse en lugar de HTTPException** — Declaran `response_model=ProductAssetResponse` pero devuelven ProblemDetails como JSONResponse cuando hay 404. FastAPI serializa esto como 200 OK con body de ProblemDetails — cualquier middleware que inspeccione `response.status_code` ve 200 en lugar de 404. `products.py:1297-1342`.

5. **[Medio] `list_datasheets` silencia fallos de signed URL** — `products.py:2332`: `except Exception: signed_url = ""`. Si Supabase Storage falla, el cliente recibe datasheets con `signed_url=""` sin ningún indicador de error. No hay logging del fallo. Un fallo de storage masivo sería invisible en métricas hasta que los usuarios reporten links rotos.
