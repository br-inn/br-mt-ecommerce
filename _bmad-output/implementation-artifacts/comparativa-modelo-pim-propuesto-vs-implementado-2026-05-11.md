# Comparativa: Modelo PIM propuesto (PDF v1.0) vs implementado

**Fecha:** 2026-05-11
**Documentos base:**
- Propuesta: `ModeloDatosPIM_Propuesta.pdf` v1.0 (07/05/2026) — BR-INNOVATION PIM
- Estado actual: `auditoria-modelo-datos-productos-2026-05-08.md`
- Código: `mt-pricing-backend/app/db/models/*.py`, migraciones Alembic waves 1-10

**Pregunta:** ¿evolucionar al modelo del PDF?
**Respuesta corta:** sí, **parcialmente** — adoptar 7 capas estructurales del PDF, **conservar** 5 piezas del actual que son mejores o pesan demasiado para migrar.

---

## 1. Síntesis comparativa por capa

| Capa | PDF propone | Implementado hoy | Gap | Acción |
|---|---|---|---|---|
| **Catálogo** | `families`, `categories`, `series`, `products`, `variants` como tablas con FKs | `products` con `family`/`subfamily`/`type`/`series`/`brand` TEXT libres; `parent_sku`+`is_variant` para variantes | 🔴 falta vocabulario + jerarquía | **Adoptar** (resuelve MIS-01) |
| **Atributos dinámicos** | EAV tipado: `attribute_definitions`+`options`+`family_attributes`+`attribute_values` | `specs` JSONB abierto + columnas escalares (`actuator`, `kv`, `torque_nm`, `iso5211_interface`, etc.) | 🔴 sin tipado, sin plantilla por familia, no filtrable eficientemente | **Adoptar** (resuelve MIS-02, MIS-03) |
| **Tablas técnicas (dimensiones)** | `dimension_columns`+`rows`+`cells` (triplete granular) | `product_tech_tables(kind='dimensions_by_dn', payload JSONB)` + escalar `dimensions` JSONB | 🟠 actual es legible pero no consultable por celda | **Adoptar** (resuelve DUP-05) |
| **Tablas técnicas (P-T)** | `pressure_temperature_points` (filas tipadas) | `tech_tables.pressure_temperature` JSONB + escalares `temp_min_c/max_c/pressure_max_bar` duplicados | 🔴 duplicación documentada | **Adoptar** (resuelve DUP-06) |
| **Tablas técnicas (materiales)** | `material_components` (filas con componente, calidad, norma) | `product_materials` (sku, component enum, position, material, …) + trigger DB que sincroniza escalar `material` | 🟢 equivalente; falta link a `standards` | Extender (no rehacer) |
| **Activos** | `assets` deduplicado por SHA-256 + `asset_links` polimórfico (product/variant/series/family/spare_part, role) | `product_assets` ligado solo a `products` por SKU; `kind` enum 10 valores; `role` legacy | 🟠 actual no soporta asset en serie/familia/recambio | **Adoptar** polimorfismo (resuelve DUP-02 al cerrar migración 030) |
| **Documentos** | `documents` con `type`+`code`+`version`+`language`+`asset_id` | No existe entidad documento; PDFs son `product_assets(kind='datasheet_pdf' \| 'certificate_pdf')` sin versionado | 🔴 falta workflow versión/idioma | **Adoptar** |
| **Normas** | `standards` reutilizables + `product_standards` polimórfica | No modelado | 🔴 ausente | **Adoptar** |
| **Certificaciones** | `certifications` + `product_certifications` polimórfica (product/variant/series) | `product_certifications` M:N a vocabulario `certifications` (solo a sku) | 🟡 actual solo a producto; falta variant/series | **Extender** owner polimórfico |
| **Recambios** | `spare_parts` + `spare_part_compatibilities` con **rango DN** | `product_compatibility(sku→sku, kind: spare_part/accessory/...)` solo 1:1 | 🟠 actual no soporta "este recambio aplica a DN 50-150 de la serie X" | **Adoptar** (escala mejor) |
| **Canales** | `channels` + `channel_rules` (required/regex/range/asset_required/min_quality) + `quality_scores` calculado | `channel_listings` parcial (no auditado a fondo), `data_quality` VARCHAR(16) plano | 🟠 actual no tiene motor de reglas declarativas | **Adoptar** después de Fase 1-3 |
| **i18n** | `product_translations` separada + columnas duales `name_es/name_en` para entidades pequeñas | `product_translations` con **9 columnas editoriales** + duplicación `name_en/description_en/marketing_copy_en` en `products` (DUP-01) | 🟢 actual es más rico (notes, marketing_features, applications_text, technical_limits, meta_*); 🔴 con duplicación | Mantener tabla actual; resolver DUP-01 |
| **Auditoría** | `audit_logs` append-only granular (entity, field, before/after, user, source) | Por-columna: `created_at/by`, `updated_at/by`, `deleted_at`; sin bitácora field-level | 🟠 falta granularidad para "quién cambió qué campo" | **Adoptar** (segunda prioridad) |

---

## 2. Lo que NO conviene adoptar literalmente del PDF

| Pieza PDF | Razón para no copiar tal cual |
|---|---|
| **UUID v4 como PK de `products`** | Actual usa `sku TEXT PK` — alineado con architecture §8.4 y clave natural usada en AX/Daterium. Mantener `sku` como PK; añadir `id uuid UNIQUE` solo si `audit_logs` lo necesita. |
| **`product.version` manual ("REVISIÓN 10")** | Actual ya tiene `revision` (semántica colisiona con `product_assets.revision`, ver INC-01). Mejor cerrar la colisión antes de añadir más versionado. |
| **`tags` como entidad formal** | DUP-08: el actual `tags ARRAY` ya es ruido frente a `product_certifications[]` y `product_applications[]`. PDF lo formaliza con `tags`+`product_tags` — no aporta, mejor **eliminar** del actual. |
| **`description_daterium_200 varchar(200)`** | Acoplamiento a un canal específico (Daterium) en el modelo central. Mejor mantener `description` libre y generar la versión 200-char en el adaptador de canal. |
| **`audit_logs` sin FKs** | Aceptable, pero sumar 10-50M filas/3 años con escritura intensa exige diseño cuidado (partitioning mensual desde el día 1 si se adopta). No es prioridad Sprint actual. |
| **Borrar `specs` JSONB completamente** | EAV cubre lo tipado; `specs` JSONB sigue siendo útil para metadatos opacos (overrides ERP, flags marketplace). Mantener como **escape hatch** documentado, no como bolsa principal. |
| **`embedding_*` ausentes en PDF** | Actual los tiene (`embedding_text`, `embedding_image`, `embedding_model`, `embedding_at`). Conservar — el PDF no contempla pricing/search semántico. |
| **`manual_locked_fields ARRAY` ausente en PDF** | Actual lo usa para proteger campos editados manualmente del re-import. Conservar. |

---

## 3. Lo que el actual hace mejor o equivalente

1. **`product_translations` más rico** — 9 columnas editoriales vs propuesta del PDF (que añade `description_daterium_200` y `catalog_notes_html` pero quita `marketing_features`/`notes`/`applications_text` como columnas explícitas).
2. **`lifecycle_status`** (draft/active/deprecated/replaced/discontinued) cubre mejor el ciclo que `status` (draft/review/approved/published/archived) del PDF — son ortogonales en realidad: el PDF mezcla **workflow editorial** con **estado comercial**. **Recomendación:** mantener `lifecycle_status` (comercial) + añadir `editorial_status` separado si se quiere workflow editorial.
3. **`product_compatibility(kind)`** ya cubre `replaces`/`replaced_by`/`compatible_with`/`spare_part`/`accessory` — más expresivo que el `spare_parts` aislado del PDF. Lo que falta es **rango DN**, no la tabla entera.
4. **Embeddings + `import_runs`** — pipeline ETL ya productivo. PDF no lo contempla.
5. **`data_quality` VARCHAR(16)** plano es pobre, pero `quality_scores` del PDF es 10x más infraestructura. Para Fase 1 (interno MT), el actual basta.

---

## 4. Plan de evolución recomendado (5 fases, ~12 semanas)

Reusa el plan del audit 2026-05-08 (Fases A-D) y lo extiende con lo del PDF.

### Fase 0 — Cerrar deuda ya prometida (1-2 días) — sin cambios respecto al audit
- **DUP-02 / LEG-02** — drop `image_url/image_origin_url/image_status` + `product_assets.role`
- **LEG-01** — derivar `active` desde `lifecycle_status` en FE; planificar drop

### Fase 1 — Vocabularios y jerarquía catálogo (1 sprint)
**Toma del PDF:** `families`, `categories` (jerarquía con `parent_id`), `series`
**Resuelve:** MIS-01
- Migrar `products.family/subfamily/type/brand` TEXT → FKs a `families`, `subfamilies` (parent=family), `categories`, `brands`
- Mantener TEXT con view de compatibilidad 1 release
- Frontend: dropdowns en wizard de creación

### Fase 2 — EAV tipado para atributos dinámicos (2 sprints)
**Toma del PDF:** `attribute_definitions`, `attribute_options`, `family_attributes`, `attribute_values`
**Resuelve:** MIS-02, MIS-03
- Seed catálogo PDF §8.1 (≈35 atributos: temp_min, pressure_max, manufacturing_method, material_body, dim_L, dim_H, torque, kv, iso5211_flange, …)
- Plantillas por familia (filter_*, ball_*, butterfly_*) — PDF §8.2
- Triggers `validate_attribute_value_type`, `ensure_family_template`
- Migrar `actuator/kv/kv2/torque_nm/iso5211_interface` → `attribute_values`
- **Mantener** `specs` JSONB como escape hatch
- Frontend: `ProductSpecsCard` deriva de `attribute_values` + `family_attributes`

### Fase 3 — Tablas técnicas estructuradas (1 sprint)
**Toma del PDF:** `dimension_columns/rows/cells`, `pressure_temperature_points`, `actuation_codes`, `material_components.standard_id`
**Resuelve:** DUP-05, DUP-06
- Migrar `product_tech_tables(kind='dimensions_by_dn')` JSONB → triplete `dimension_*`
- Migrar `tech_tables(kind='pressure_temperature')` JSONB → filas `pressure_temperature_points`
- Crear `actuation_codes` seed (libre/maneta/MR/motorizada/neumática)
- Drop escalares duplicados `temp_min_c/max_c/pressure_max_bar` (después de migrar)
- Crear `standards` + link desde `material_components`

### Fase 4 — Assets polimórficos + documentos (1 sprint)
**Toma del PDF:** `assets` deduplicado por SHA-256, `asset_links` polimórfico, `documents` versionado
- Renombrar `product_assets` → `assets` + nueva tabla `asset_links(owner_type, owner_id, role)`
- Roles del PDF: `image_padre`, `banner`, `ficha_pdf`, `manual_pdf`, `ce_pdf`, `exploded_3d`, `section_drawing`, `dimensions_drawing`, `video`, `web_image`
- Mapear `product_assets.kind` → role
- Crear `documents(type, code, version, language, asset_id)` para los PDFs MTFT/MTCE/MTMAN

### Fase 5 — Recambios con rango DN + certificaciones polimórficas (1 sprint)
**Toma del PDF:** `spare_parts`, `spare_part_compatibilities(dn_min, dn_max, owner_type)`; `product_certifications.owner_type`
- Extender `product_compatibility(kind='spare_part')`:
  - opción A: añadir `dn_min/dn_max/owner_type` a la tabla actual
  - opción B: crear `spare_parts` + `spare_part_compatibilities` paralela (PDF tal cual)
  - **Recomendado:** A (menos churn, menos JOINs)
- Migrar `product_certifications.sku` → `owner_type+owner_id` para soportar serie/variant

### Fase 6 (opcional, Fase 2 del programa) — Canales declarativos + audit_logs
**Toma del PDF:** `channels`, `channel_rules`, `quality_scores`, `audit_logs`
- Solo cuando se aborde marketplaces (Fase 3 del programa MT). Hoy no es prioridad.

---

## 5. Decisiones pendientes (bloquean Fase 1)

Las 7 decisiones del audit §9 siguen abiertas; el PDF aporta opinión sobre 4:

| # | Decisión | Postura del PDF | Recomendación |
|---|---|---|---|
| 1 | `name_en` cache vs translations | Solo translations | Eliminar de `products`, view materializada si performance lo exige |
| 2 | `material` escalar denormalizado | No lo contempla (solo `material_components`) | Mantener trigger DB como denormalización solo-lectura; documentar en ADR |
| 3 | `temp_min/max` nominal vs operacional | Nominal en `attribute_values`; operacional en `pressure_temperature_points` | Adoptar separación PDF |
| 4 | `dn` vs `dn_real` | Ambos en `variants` (nominal vs real) | Documentar + mantener ambos |
| 5 | `tags` ARRAY destino | Lo formaliza como entidad | **Eliminar** del actual — vocabularios cubren todo |
| 6 | description vs marketing_copy vs marketing_features | PDF tiene `description_short`+`description_marketing` (+ `_daterium_200`) | Adoptar `description_short`+`marketing_copy`; deprecar `marketing_features` |
| 7 | `specs` JSONB tipado vs abierto | EAV tipado, sin JSONB | Híbrido: EAV principal + JSONB `specs.extras` documentado |

---

## 6. Anti-recomendación: lo que NO hacer

1. **No migrar a UUID PK** — `sku` como clave natural está bien y todo el ETL/Daterium/AX lo asume.
2. **No big-bang** — el modelo del PDF es coherente como diseño greenfield, pero migrar 56 columnas + 7 tablas relacionadas + frontend a la forma del PDF de una vez rompe Sprint 2-3.
3. **No adoptar `audit_logs` antes de Fase 5** — partitioning mensual desde el día 0 es complejidad que ahora no paga; los timestamps por-columna actuales bastan para Fase 1 interno.
4. **No copiar `description_daterium_200`** al modelo central — acoplamiento de canal.

---

## 7. Resumen ejecutivo (3 líneas)

- El PDF es un diseño greenfield coherente; el actual es ese diseño en estado **a medio camino** con duplicaciones legacy.
- **Adoptar:** capa de catálogo (families/categories/series), EAV tipado, tablas técnicas granulares, assets polimórficos, documentos versionados, recambios con rango DN.
- **Conservar del actual:** `sku` como PK, `product_translations` rico, `product_compatibility` extendido, embeddings, `manual_locked_fields`, `import_runs`, `lifecycle_status`.

— Fin del análisis —
