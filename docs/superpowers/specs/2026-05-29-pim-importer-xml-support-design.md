---
tags:
  - design
  - importer
  - pim
  - xml
created: 2026-05-29
status: approved
audience: claude-code, backend, dirección técnica
related:
  - "[[articulos-xsd-template]]"
target_repo: br-mt-ecommerce
component: mt-pricing-backend/app/services/importer
---

# Diseño — Soporte de importación XML en el importador PIM

## 1. Contexto y objetivo

Existe una **plantilla estándar de artículos** en formato XSD + XML
(`docs/templates/articulos/articulos.xsd` + `articulos-ejemplo.xml`) para que los
usuarios completen la información de los artículos. Hoy el importador PIM solo
acepta `.xlsx`; el objetivo es que **también pueda importar el archivo XML de la
plantilla**, dejando el producto con todos sus datos persistidos.

Decisiones acordadas en brainstorming (2026-05-29):

1. **Flujos soportados:** ambos — wizard con preview (`POST /imports/preview` →
   diff → `apply`) y carga async (`POST /imports/pim/upload` → Storage → Celery).
2. **Alcance de datos:** completo — además de escalares + JSONB + nombres de
   traducción, persistir `releases` por mercado, `uom_conversions`,
   `bore_dimensions` y campos SEO de traducción.
3. **Validación:** tolerante por fila — no se rechaza el archivo entero; los
   errores de cada `<article>` se reportan a nivel fila (igual que el flujo xlsx).

## 2. Principio rector

El pipeline `parse → ParseResult → compute_diff → apply_diffs_chunked` es
**agnóstico al formato** una vez producido el `ParseResult`. Por tanto:

- Se añade un parser XML que produce el **mismo** `ParseResult`/`ParsedRow` que el
  parser xlsx.
- El **differ no se toca**.
- El **applier se extiende** para persistir los bloques ricos que la plantilla
  XML lleva y que el xlsx no tiene.

## 3. Arquitectura y componentes

| Componente | Tipo | Responsabilidad única |
|------------|------|----------------------|
| `app/services/importer/xml_parser.py` | **nuevo** | `parse_xml_stream(source) -> ParseResult`. Parsea `<catalog>` con `xml.etree.ElementTree` (stdlib), valida cada `<article>` reutilizando `ProductCreate`, detecta SKU duplicados. Errores → `ParsedRow.errors`. |
| `app/services/importer/source_dispatch.py` | **nuevo (pequeño)** | `parse_source(file_bytes, filename, *, custom_mapping=None) -> ParseResult`. Detecta xlsx vs XML por extensión/content-type y delega. Único punto de detección. |
| `parser.py` (xlsx) | sin cambios | Parser Excel actual. |
| `differ.py` | sin cambios | Diffea solo escalares; los bloques ricos viajan en `payload` bajo claves reservadas y pasan a través intactos. |
| `applier.py` (`_apply_one`) | **extender** | Tras upsert del producto, consumir claves reservadas del payload y hacer upsert idempotente de bloques ricos. |
| `app/repositories/product.py` | **añadir** upsert para `ProductRelease` y `ProductUomConversion` | `ProductTranslationRepository.upsert` y `ProductBoreDimensionRepository` ya existen. |
| `importer_service.preview()` | **wire** | Reemplaza la llamada directa a `parse_xlsx_stream` por `parse_source`. |
| worker `run_pim_import_task` / `import_orchestrator` | **wire** | Usa `parse_source`; al subir a Storage, fija content-type según extensión (`text/xml` para `.xml`). |
| Frontend wizard (Pantalla 10) | **cambio mínimo** | El input de archivo acepta también `.xml`. |

### Diseño por aislamiento

- `xml_parser` tiene una sola entrada (`bytes`/file-like) y una sola salida
  (`ParseResult`). No conoce HTTP, BD ni Celery. Testeable en aislamiento.
- `source_dispatch` solo decide formato. Sin lógica de parseo propia.
- La extensión del applier se acota a un helper privado
  `_apply_related(session, sku, payload, actor)` invocado tras el upsert del
  producto, para no inflar `_apply_one`.

## 4. Contrato de datos: claves reservadas en `payload`

El `xml_parser` produce el mismo payload escalar que `map_row` (mismas claves:
`sku`, `name_en`, `family`, `subfamily`, `type`, `series`, `brand`, `material`,
`dn`, `pn`, `connection`, `size`, `temp_min_c`, `temp_max_c`,
`pressure_max_bar`, `manufacturing_method`, `gtin`, `intrastat_code`,
`erp_name`, `weight`, `weight_unit`, `lifecycle_status`, `revision`,
`data_quality`, `parent_sku`, `is_parent`, `is_variant`, `display_pair_sku`,
`video_url`, `external_url`, `division_codes`) más los buckets JSONB
`dimensions`, `packaging`, `specs`.

Adicionalmente añade **claves reservadas** (prefijo `_`) que el differ ignora y
el applier consume:

| Clave | Forma | Destino BD |
|-------|-------|-----------|
| `name_en` (escalar, ya existente) | str | `product_translations(lang='en').name` + requerido por `ProductCreate`/differ |
| `_translations` | `list[{lang, status, name, description, marketing_copy, meta_title, meta_description, applications_text, technical_limits, notes, marketing_features}]` | `product_translations` (en/es/ar, campos completos) |
| `_releases` | `list[{market_code, local_name, local_description, local_sku, local_uom, list_price, price_currency, tax_class}]` | `product_releases` (upsert por `product_sku`+`market_code`) |
| `_uom_conversions` | `list[{uom_from, uom_to, factor}]` | `product_uom_conversions` (upsert por `product_sku`+`uom_from`+`uom_to`) |
| `_bore_dimensions` | `list[{standard_system, standard_code, is_primary, dn_nominal_ref, pressure_class, bore_mm, ...}]` | `product_bore_dimensions` (upsert por `product_sku`+`standard_system`+`standard_code`) |

`name_en` se mantiene como escalar (lo exige `ProductCreate` y lo usa el differ).
El nombre EN dentro de `_translations` es la fuente de los campos extendidos de la
traducción inglesa (description/marketing/SEO); el applier reconcilia ambos.

## 5. Flujo de datos

```
.xml (catalog)
   │  preview wizard  POST /imports/preview          (in-memory, con diff)
   │  async batch     POST /imports/pim/upload → Storage → Celery
   ▼
parse_source()  ──(.xml)──►  parse_xml_stream()
   │                              por cada <article>:
   │                               • escalares → valida con ProductCreate (errores→fila)
   │                               • dimensions/packaging/specs → JSONB
   │                               • _translations/_releases/_uom/_bore → payload
   ▼
ParseResult(rows[].payload)  ── idéntico al de xlsx ──►  compute_diff()  ──►  apply_diffs_chunked()
                                                              (escalares)        CREATE/UPDATE:
                                                                                  • product upsert (igual que hoy)
                                                                                  • + _apply_related(): upsert
                                                                                    translations/releases/uom/bore
                                                                                 ▼
                                                                              BD
```

## 6. Validación y manejo de errores (tolerante por fila)

- **Nivel archivo:** XML no *well-formed* o raíz distinta de `<catalog>` →
  `ImporterDomainError(code="import_parse_failed", status=422)` (igual que un
  xlsx corrupto). No se persiste nada.
- **Nivel artículo:** cada `<article>` se valida construyendo `ProductCreate` con
  el subconjunto escalar. Los `ValidationError` (SKU regex, DN/PN, lifecycle,
  weight_unit, data_quality, temp range…) se acumulan en `ParsedRow.errors`. El
  differ los marca `action=ERROR` → visibles en
  `GET /imports/{run_id}/rejected-rows` y en el reporte CSV/JSON. Las demás filas
  continúan.
- **SKU duplicado** dentro del archivo → error en la fila duplicada (misma regla
  que el parser xlsx).
- **XSD:** queda como contrato del lado del usuario (validación local, documentada
  en `docs/templates/articulos/README.md`). El backend **no** añade `lxml`.

## 7. Idempotencia de bloques ricos (decisión v1)

Los bloques `_translations/_releases/_uom/_bore` se aplican (upsert) en filas con
`action == CREATE` o `UPDATE`. En la **primera importación** todo es `CREATE`, por
lo que el producto queda con todos los datos completos.

**Limitación conocida v1:** si en una re-importación los campos escalares no
cambian pero sí un bloque anidado, la fila resulta `NO_CHANGE` y el bloque **no**
se re-aplica. Evitar esto exigiría diffing de colecciones en el differ (fuera de
alcance v1). Workaround: re-subir con cualquier cambio escalar o crear el SKU.
Esta limitación se documentará en el README de la plantilla.

## 8. Endpoints y contrato API

- No cambian las firmas: `POST /imports/preview` y `POST /imports/pim/upload`
  siguen recibiendo `UploadFile`. Solo cambia internamente el dispatch por
  extensión. RBAC sin cambios (`imports:write`).
- Sin nuevos schemas Pydantic de request/response ⇒ no se espera drift de
  OpenAPI. Si algún route/schema cambia, regenerar el spec (regla CI del repo).

## 9. Plan de pruebas

**Unit `xml_parser`:**
- XML válido completo → payload con escalares + JSONB + `_translations/_releases/_uom/_bore` correctos.
- `<specs><extra><field key=...>` → claves planas en `specs`; `<connections>` → lista.
- Artículo con DN fuera de vocabulario / sin `name_en` → error en esa fila, las demás OK.
- SKU duplicado en el archivo → error en la fila duplicada.
- XML malformado / raíz incorrecta → excepción de archivo.

**Unit applier extendido:**
- `_apply_related` hace upsert de releases/uom/bore/translations.
- Re-apply idempotente (no duplica filas).

**Integración:**
- `preview` con `.xml` → summary/diff esperados.
- `apply` con `.xml` → filas en `products` + tablas relacionadas.
- Worker async con `.xml` (content-type correcto en Storage).

**Regresión:**
- El camino `.xlsx` sigue intacto (suite existente verde).

**Cobertura:** ≥ 70 % (gate CI).

## 10. Fuera de alcance (YAGNI)

- Diffing de colecciones anidadas (ver §7).
- Validación XSD server-side con lxml.
- Edición/preview visual de los bloques ricos en el wizard (solo aceptar `.xml`).
- Soporte de assets/imágenes binarias vía XML.

## 11. Riesgos

- **Differ debe preservar `payload` en filas UPDATE** para que el applier acceda a
  los bloques ricos. Verificar que `RowDiff.payload` se conserva en UPDATE; si no,
  ajustar `compute_diff` para incluirlo (cambio acotado).
- **Orden de upsert**: el producto debe existir (flush) antes de insertar
  releases/uom/bore (FK a `product_sku`). `_apply_related` corre después del
  `repo.create`/update y antes del cierre del savepoint del chunk.
