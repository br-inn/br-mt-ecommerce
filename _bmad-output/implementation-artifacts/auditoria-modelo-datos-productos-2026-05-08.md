# Auditoría exhaustiva — Modelo de datos de productos

**Fecha:** 2026-05-08
**Alcance:** `mt-pricing-backend` (SQLAlchemy + Alembic) y `mt-pricing-frontend` (TypeScript types)
**Solicitante:** psierra@br-innovation.com
**Motivo:** sospecha de campos mal clasificados o duplicados — fundamental para refactor previo a Fase 2

---

## TL;DR — 23 problemas catalogados

- **8 duplicaciones reales** (mismo dato en ≥2 lugares sin política clara de fuente de verdad)
- **6 campos mal clasificados** (escalares en `products` que pertenecen a tablas tipadas, vocabularios o `specs` discriminado)
- **3 inconsistencias de naming** (singular vs plural, `revision` ambiguo)
- **2 piezas legacy pendientes de drop** que migración 030 prometió eliminar y siguen vivas
- **4 desincronizaciones backend ↔ frontend** (FE expone <30 % de los campos del modelo y mezcla legacy con nuevo)

**Recomendación general:** congelar nuevas waves de modelado (10/11) hasta consolidar, antes de exponer datos al wizard de creación y a marketplaces (Fase 3).

---

## 1. Inventario completo — tabla `products` (56 columnas)

Origen: [mt-pricing-backend/app/db/models/product.py:50-262](mt-pricing-backend/app/db/models/product.py#L50-L262)

### 1.1 Identidad
| Columna | Tipo | Notas |
|---|---|---|
| `sku` | TEXT PK | OK — alineado con architecture §8.4 |
| `internal_id` | UUID UNIQUE | OK — para joins sintéticos |
| `parent_sku` | TEXT FK→products.sku | Variantes (Wave 2) |
| `is_parent`, `is_variant` | BOOLEAN | OK |
| `revision`, `series` | TEXT | ⚠️ `revision` colide con `product_assets.revision` ([product.py:362](mt-pricing-backend/app/db/models/product.py#L362)) — semántica distinta, mismo nombre |
| `lifecycle_status` | enum (draft/active/deprecated/replaced/discontinued) | ✅ correcto reemplazo |
| `active` | BOOLEAN | 🔴 **LEGACY** — Wave 2 lo reemplazó por `lifecycle_status`, sigue en uso (FE depende de él) |

### 1.2 Comerciales / clasificación
| Columna | Tipo | Notas |
|---|---|---|
| `family` | TEXT NOT NULL | ⚠️ debería ser FK a vocabulario |
| `subfamily`, `type` | TEXT | ⚠️ idem |
| `brand` | TEXT | ⚠️ idem — riesgo "SS316" vs "SS 316" vs "ss-316" |
| `tags` | ARRAY(TEXT) | 🔴 **redundante** con `product_certifications[]` y `product_applications[]` (Wave 4) |

### 1.3 Texto comercial / marketing
| Columna | Notas |
|---|---|
| `name_en` NOT NULL | 🔴 **DUPLICA** `product_translations(lang='en').name` |
| `description_en` | 🔴 **DUPLICA** `product_translations(lang='en').description` |
| `marketing_copy_en` | 🔴 **DUPLICA** `product_translations(lang='en').marketing_copy` |

### 1.4 Técnicos escalares (mezcla cruda)
| Columna | Naturaleza | Problema |
|---|---|---|
| `material` TEXT | escalar | 🔴 duplica `product_materials[]` (M:N con component='body'\|'closure'\|...) |
| `connection` TEXT (libre) | escalar | 🔴 duplica `product_connections[]` (M:N con enum tipado) |
| `dn`, `dn_real` | escalar | ⚠️ ambos sin doc — diferencia semántica unclear |
| `pn` | escalar | OK |
| `size` TEXT | escalar | 🔴 duplica `dimensions` JSONB y `tech_tables.dimensions_by_dn` |
| `temp_min_c`, `temp_max_c` | INT | 🔴 duplican matriz `tech_tables.pressure_temperature` |
| `pressure_max_bar` | NUMERIC | 🔴 idem |
| `manufacturing_method` | TEXT | OK |
| `actuator`, `kv`, `kv2`, `torque_nm`, `iso5211_interface` | escalares | ⚠️ **mal clasificados**: aplican solo a válvulas/actuadores; en una tabla genérica producen NULL para cualquier producto que no sea válvula. Pertenecen a `specs` discriminada por tipo |

### 1.5 Físico / packaging / fiscal
| Columna | Notas |
|---|---|
| `weight` NUMERIC(12,4) + `weight_unit` VARCHAR(8) | OK |
| `dimensions` JSONB | ⚠️ sin schema Pydantic (FE sí lo tipa: `{length, width, height, unit}`) |
| `packaging` JSONB | ⚠️ sin schema Pydantic (FE sí lo tipa: `{qty_x_box, ean_unit, ean_box, moq}`) |
| `specs` JSONB | 🔴 **dict abierto** sin discriminator — meta-bolsa |
| `intrastat_code` TEXT | ⚠️ **mal clasificado**: FE lo modela como objeto `{hs_code, origin_country, net_weight_kg}` — DB tiene un solo TEXT |
| `erp_name` TEXT | ⚠️ debería estar bajo `erp: {…}` en specs |

### 1.6 Imágenes — DEUDA TÉCNICA #1
| Columna en `products` | Estado |
|---|---|
| `image_url` | 🔴 **LEGACY** — migración 030 (Wave 1) prometió drop "en Wave 2", siguen vivas en Wave 10 |
| `image_origin_url` | 🔴 idem — duplica `product_assets.original_url` |
| `image_status` | 🔴 idem — duplica `product_assets.status` |

### 1.7 Editorial extra
- `video_url`, `external_url` — 🔴 duplican `product_assets(kind='video_link')` y `kind='external_url'` que la propia tabla ya soporta como kinds del enum

### 1.8 Audit & data quality
| Columna | Notas |
|---|---|
| `data_quality` VARCHAR(16) | OK |
| `manual_locked_fields` ARRAY(TEXT) | OK |
| `created_at/by`, `updated_at/by`, `deleted_at` | OK (auditoría) |

### 1.9 Embeddings
| Columna | Notas |
|---|---|
| `embedding_text`, `embedding_image` | OK — privados |
| `embedding_model`, `embedding_at` | OK |

---

## 2. Inventario — `product_translations` (18 columnas)

Origen: [product.py:265-312](mt-pricing-backend/app/db/models/product.py#L265-L312)

| Columna | Notas |
|---|---|
| `(sku, lang)` PK | OK; lang ∈ es/ar/en |
| `name`, `description`, `marketing_copy` | 🔴 **duplican** `products.name_en/description_en/marketing_copy_en` cuando lang='en' |
| `meta_title`, `meta_description` | Wave 8 — SEO. OK |
| `applications_text` | ⚠️ ¿qué relación con `product_applications[]` (M:N a vocabulario)? |
| `technical_limits` | ⚠️ texto libre sobre límites técnicos — duplica datos numéricos de `tech_tables.pressure_temperature` |
| `notes` | OK (campo libre) |
| `marketing_features` | ⚠️ **3er campo de marketing** (description, marketing_copy, marketing_features) sin política clara |
| `status`, `translated_by/at`, `reviewed_by/at` | Workflow OK |

---

## 3. Inventario — `product_assets` (27 columnas)

Origen: [product.py:315-416](mt-pricing-backend/app/db/models/product.py#L315-L416)

| Columna | Notas |
|---|---|
| `id`, `sku`, `kind` | PK + FK; `kind` enum 10 valores (photo/banner/datasheet_pdf/exploded_3d/section_drawing/dimension_drawing/certificate_pdf/video_link/external_url/mirror_url) |
| `original_url` | duplica `products.image_origin_url` (legacy) |
| `width`, `height` | aplican solo a photos — OK |
| `status` | duplica `products.image_status` (legacy) |
| `revision` | ⚠️ choca de nombre con `products.revision` |
| `role` | 🔴 **LEGACY** — migración 030 dijo "Wave 2 drops it"; sigue vivo y FE lo expone (`ProductImageRecord.role` en [products.ts](mt-pricing-frontend/lib/api/endpoints/products.ts)) |
| `metadata` (attr `asset_meta`) | OK |
| `variants` JSONB | OK (thumbs/avif/blurhash) |

---

## 4. Tablas relacionadas (Waves 3-7)

| Tabla | Estructura | Solapamiento con `products` |
|---|---|---|
| `product_materials` | (sku, component enum, position, material, …) | 🔴 con `products.material` — hay trigger DB que sincroniza `material` ← `material[component='body', position=0]`; lógica oculta |
| `product_connections` | (sku, position, connection_type enum, …) | 🔴 con `products.connection` (TEXT libre, sin enum) |
| `product_tech_tables` | (sku, kind enum: materials_matrix \| dimensions_by_dn \| pressure_temperature, payload JSONB) | 🔴 `materials_matrix` solapa con `product_materials[]`; `dimensions_by_dn` solapa con `dimensions` JSONB; `pressure_temperature` solapa con `temp_min_c/temp_max_c/pressure_max_bar` |
| `product_certifications` | M:N a vocabulario `certifications` | 🔴 solapa con `tags` ARRAY |
| `product_applications` | M:N a vocabulario `applications` | 🔴 solapa con `tags` ARRAY y con `product_translations.applications_text` |
| `product_compatibility` | (product_sku, compatible_with_sku, kind: spare_part/accessory/replaces/replaced_by/compatible_with) | OK — propósito claro |
| `material_compatibility` | (material_a, material_b, compatibility) | tabla maestra OK |

---

## 5. Frontend — desincronización con backend

Origen: [mt-pricing-frontend/lib/api/endpoints/products.ts](mt-pricing-frontend/lib/api/endpoints/products.ts)

### 5.1 Cobertura de campos
- `ProductListItem` expone **14 campos**; backend tiene **56**. Cobertura ≈ 25 %.
- **No expuestos en FE:** lifecycle_status, revision, series, parent_sku, is_parent, is_variant, dn_real, size, temp_min_c/max_c, pressure_max_bar, manufacturing_method, actuator, kv/kv2, torque_nm, iso5211_interface, tags, video_url, external_url, marketing_copy_en, image_status, image_origin_url, manual_locked_fields, materials[], connections[], tech_tables[], compatibilities[], certifications[], applications[].

### 5.2 Naming/forma divergente
| Concepto | Backend | Frontend |
|---|---|---|
| Peso | `weight` + `weight_unit` (separados) | `weight_kg` (asume kg) |
| Intrastat | `intrastat_code` (TEXT) | `intrastat: {hs_code, origin_country, net_weight_kg}` (objeto) |
| Dimensiones | `dimensions` JSONB libre | `ProductDimensions {length, width, height, unit}` (tipado) |
| Packaging | `packaging` JSONB libre | `ProductPackaging {qty_x_box, ean_unit, ean_box, moq}` (tipado) |
| Imágenes | `ProductAsset` (10 kinds, sin `role`) | `ProductImage` simple **+** `ProductImageRecord` con `role` (legacy) |
| Estado vida | `lifecycle_status` (enum) | `active` (boolean) |
| Traducciones | `name`, `description`, `marketing_copy`, `meta_title`, `meta_description`, `applications_text`, `technical_limits`, `notes`, `marketing_features` | `TranslationUpsertPayload` solo `{name, description}` |

### 5.3 Implicación
La forma del FE es **más limpia que el backend** (intrastat objeto, packaging tipado, dimensions tipado). Esto sugiere que:
1. Hubo un diseño FE-first razonable.
2. El backend acumuló deuda técnica al añadir campos planos sin migrar.
3. El refactor consolidador puede tomar la forma del FE como objetivo.

---

## 6. Catálogo de problemas

| ID | Sev | Tipo | Resumen | Refs |
|---|---|---|---|---|
| **DUP-01** | 🔴 | Duplicación | `name_en/description_en/marketing_copy_en` (products) ↔ `product_translations(lang='en')` | [product.py:61-63](mt-pricing-backend/app/db/models/product.py#L61-L63) |
| **DUP-02** | 🔴 | Legacy | `image_url/image_origin_url/image_status` siguen en `products` después de migración 030 | [product.py:92-94](mt-pricing-backend/app/db/models/product.py#L92-L94) |
| **DUP-03** | 🔴 | Duplicación | `material` escalar + trigger DB ↔ `product_materials[]` ↔ `tech_tables.materials_matrix` | [product.py:68](mt-pricing-backend/app/db/models/product.py#L68) |
| **DUP-04** | 🔴 | Duplicación | `connection` TEXT libre ↔ `product_connections[]` con enum tipado | [product.py:71](mt-pricing-backend/app/db/models/product.py#L71) |
| **DUP-05** | 🔴 | Duplicación | `size` ↔ `dimensions` JSONB ↔ `tech_tables.dimensions_by_dn` ↔ `packaging` (¿incluye W/H/D?) | [product.py:77, 127](mt-pricing-backend/app/db/models/product.py#L77) |
| **DUP-06** | 🔴 | Duplicación | `temp_min_c/temp_max_c/pressure_max_bar` escalares ↔ matriz `tech_tables.pressure_temperature` (sin política nominal-vs-operacional) | [product.py:128-130](mt-pricing-backend/app/db/models/product.py#L128-L130) |
| **DUP-07** | 🟠 | Redundancia | `dn` vs `dn_real` sin documentar diferencia | [product.py:69, 126](mt-pricing-backend/app/db/models/product.py#L69) |
| **DUP-08** | 🟠 | Redundancia | `tags` ARRAY ↔ `product_certifications[]` + `product_applications[]` (M:N formales) | [product.py:139](mt-pricing-backend/app/db/models/product.py#L139) |
| **DUP-09** | 🟠 | Redundancia | `video_url`/`external_url` ↔ kinds `video_link`/`external_url` en `product_assets` | [product.py:142-143](mt-pricing-backend/app/db/models/product.py#L142-L143) |
| **MIS-01** | 🟠 | Mal clasificado | `brand/family/subfamily/type` TEXT libre — sin FK ni vocabulario | [product.py:65-72](mt-pricing-backend/app/db/models/product.py#L65-L72) |
| **MIS-02** | 🟠 | Mal clasificado | `actuator/kv/kv2/torque_nm/iso5211_interface` específicos de válvula en tabla genérica → `specs` discriminado | [product.py:132-136](mt-pricing-backend/app/db/models/product.py#L132-L136) |
| **MIS-03** | 🟠 | Mal clasificado | `specs` JSONB sin schema Pydantic — bolsa abierta sin discriminator por tipo | [product.py:74](mt-pricing-backend/app/db/models/product.py#L74) |
| **MIS-04** | 🟡 | Mal clasificado | `intrastat_code` (TEXT) debería ser objeto (FE ya lo modela así) | [product.py:88](mt-pricing-backend/app/db/models/product.py#L88) |
| **MIS-05** | 🟡 | Mal clasificado | `erp_name` plano — debería estar bajo `erp: {…}` en specs | [product.py:89](mt-pricing-backend/app/db/models/product.py#L89) |
| **MIS-06** | 🟡 | Mal clasificado | `dimensions`/`packaging` JSONB sin tipar en backend (FE sí los tipa) | [product.py:77, 80](mt-pricing-backend/app/db/models/product.py#L77) |
| **INC-01** | 🟡 | Naming | `revision` existe en `products` y en `product_assets` con semántica distinta | [product.py:113, 362](mt-pricing-backend/app/db/models/product.py#L113) |
| **INC-02** | 🟡 | Naming | Singular vs plural: `material/materials`, `connection/connections` (escalar duplicado) | [product.py:68, 71](mt-pricing-backend/app/db/models/product.py#L68) |
| **INC-03** | 🟡 | Naming | 3 campos para texto comercial sin política: `description`, `marketing_copy`, `marketing_features` | [product.py:274, 281](mt-pricing-backend/app/db/models/product.py#L274) |
| **LEG-01** | 🟡 | Legacy | `active` (BOOLEAN) coexiste con `lifecycle_status` — FE aún usa `active` | [product.py:104, 110](mt-pricing-backend/app/db/models/product.py#L104) |
| **LEG-02** | 🟡 | Legacy | `product_assets.role` nullable — migración 030 prometió drop | [product.py:375](mt-pricing-backend/app/db/models/product.py#L375) |
| **FE-01** | 🟠 | Desync | FE expone ~25% del modelo; le falta lifecycle_status, materiales[], conexiones[], tech_tables, compatibilities, etc. | [products.ts](mt-pricing-frontend/lib/api/endpoints/products.ts) |
| **FE-02** | 🟠 | Desync | `ProductImage` simple + `ProductImageRecord` con `role` legacy conviven en FE | [products.ts](mt-pricing-frontend/lib/api/endpoints/products.ts) |
| **FE-03** | 🟡 | Desync | FE usa `weight_kg` cuando backend tiene `weight` + `weight_unit` (asunción FE rompe si unidad ≠ kg) | [products.ts](mt-pricing-frontend/lib/api/endpoints/products.ts) |

---

## 7. Hipótesis de diseño implícito (a confirmar con el equipo)

Para los solapamientos sin documentación, las hipótesis más plausibles son:

| Solapamiento | Hipótesis razonable | Riesgo si la hipótesis falla |
|---|---|---|
| `material` escalar vs `product_materials[]` | Escalar = denormalización del material principal (body, position=0) para listados rápidos | Si el trigger se rompe, los listados muestran un material y el detalle otro |
| `temp_min/max + pressure_max_bar` vs `tech_tables.pressure_temperature` | Escalares = límites nominales del producto; matriz = curva operacional P×T | Sin etiqueta semántica explícita, los importadores y usuarios no saben en cuál escribir |
| `dn` vs `dn_real` | DN = nominal ISO; DN_REAL = paso real medido | Ambigüedad en filtros: `?dn=50` debería filtrar por cuál |
| `name_en/description_en` vs translations(en) | Escalares = "cache" para evitar JOIN en listados; translations = source-of-truth | Si se desincronizan, el listado y el detalle muestran textos distintos |
| `tags` vs certifications[]/applications[] | Tags = libre/auxiliar; M:N = vocabularios formales | Tags terminan duplicando vocabularios → inconsistencias en filtros |

**Recomendación**: cada uno de estos pares necesita una decisión documentada en un ADR.

---

## 8. Plan de refactor sugerido (3 fases)

### Fase A — drop legacy ya prometido (Sprint actual, 1-2 días)
1. **DUP-02 / LEG-02** — completar migración 030: drop `image_url`, `image_origin_url`, `image_status` de `products`; drop `role` de `product_assets`; remover `ProductImage` simple del FE; el backend ya tiene `ProductAsset` como fuente única.
2. **LEG-01** — derivar `active` desde `lifecycle_status IN ('active')` en el FE; planificar drop de columna en próxima migración.

### Fase B — consolidación textual (1 sprint)
3. **DUP-01 / INC-03** — eliminar `name_en/description_en/marketing_copy_en` de `products`; el backend siempre lee/escribe vía `product_translations(lang='en')`. Preservar `name_en` como **vista materializada** o columna generada si los listados lo requieren para performance, **no como columna editable**.
4. Definir política de `description` vs `marketing_copy` vs `marketing_features` (recomendado: dejar `description` técnica + `marketing_copy` libre; deprecar `marketing_features`).

### Fase C — tipado de specs y vocabularios (2 sprints)
5. **MIS-01** — crear vocabularios FK para `brand`, `family`, `subfamily`, `type` (ya existe el patrón en certifications/applications).
6. **MIS-02 / MIS-03** — discriminator `product_type` en `specs` con Pydantic union (`ValveSpec | PipeSpec | AccessorySpec | ActuatorSpec`); migrar `actuator/kv/kv2/torque_nm/iso5211_interface` a `ValveSpec`.
7. **MIS-04 / MIS-05 / MIS-06** — alinear backend con la forma del FE: `intrastat: ProductIntrastat`, `dimensions: ProductDimensions`, `packaging: ProductPackaging`; mover `erp_name` a `specs.erp.name`.
8. **DUP-03/04/05/06/08/09** — eliminar escalares duplicados; el trigger de `material` puede mantenerse como vista materializada solo-lectura. Documentar en ADR la fuente de verdad para cada concepto.
9. **DUP-07** — decidir y documentar `dn` vs `dn_real`; si son la misma cosa, eliminar uno.

### Fase D — alineación FE
10. **FE-01/02/03** — generar tipos TS desde el schema Pydantic backend (codegen) para evitar deriva futura.

---

## 9. Decisiones que el equipo necesita tomar antes de tocar código

1. **¿`name_en` se elimina o se mantiene como vista para performance?** (afecta listados de catálogo)
2. **¿`material` escalar se mantiene como denormalización o se deriva por API?** (afecta el trigger DB que ya existe)
3. **`temp_min_c/max_c/pressure_max_bar` ¿son nominales o operacionales?** Documentar y validar contra `tech_tables.pressure_temperature`.
4. **`dn` vs `dn_real`**: ¿hay diferencia real?
5. **`tags` ARRAY**: ¿se elimina del todo o se reserva para tags libres no-vocabulario?
6. **`description` vs `marketing_copy` vs `marketing_features`**: política única para los 3.
7. **`specs` JSONB**: ¿se acepta tipado discriminado por `product_type` o se mantiene abierto?

---

## 10. Anexos

### A. Archivos auditados
- `mt-pricing-backend/app/db/models/product.py` (423 líneas)
- `mt-pricing-backend/app/db/models/{vocabularies,components,tech_tables,compatibility,material_compatibility}.py`
- `mt-pricing-backend/app/schemas/products.py`
- 12 migraciones Alembic (waves 1, 4, 6, 7, 8, 10): 030_assets_unification → 041_facet_indexes
- `mt-pricing-frontend/lib/api/endpoints/products.ts` (tipos cliente)

### B. No auditado en este pase
- Pipeline ETL (`import_runs`, `datasheet_import_run`) — qué campos rellena en cada importador
- Lógica de canales (`channel_listings`) — qué campos del modelo se publican a cada canal
- Pricing engine (`pricing.py`, `cost.py`) — qué campos del producto consume
- Embeddings: cómo se calculan y qué campos los alimentan

Pueden ser auditorías de seguimiento si el refactor lo requiere.
