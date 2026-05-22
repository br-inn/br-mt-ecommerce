# PIM Import Pipeline Redesign — Design Spec

**Fecha:** 2026-05-22  
**Autor:** psierra  
**Estado:** Aprobado — listo para plan de implementación  
**Branch objetivo:** `feature/pim-import-pipeline-v2`

---

## 1. Contexto y Motivación

El módulo de importación PIM actual fue diseñado para un Excel fijo de 17 columnas (`PIM completo.xlsx` formato AX legacy). El nuevo archivo de referencia (`PIM completo_JcS_1.xlsx`) tiene **42 columnas** que incluyen:

- Nombres multiidioma (EN, ES, FR, DE, IT, PT)
- Campos técnicos ya presentes en el modelo pero sin cobertura: `hs_code`, `connection`, `bore_mm`, `pressure_max_bar`, `temp_min_c`, `temp_max_c`
- Certificaciones M:N (`product_certifications`)
- URL de imagen, series tags, familia

Además coexisten dos pipelines de apply divergentes (`applier.py` para el wizard sync y `pim_importer.py` para el batch Celery) que han acumulado diferencias. El objetivo es unificarlos y hacer el módulo capaz de cargar **cualquier Excel PIM** via LLM mapping, con garantía de integridad completa.

### Gaps detectados en el análisis

| Área | Problema |
|---|---|
| Column mapper canónico | Solo 17 columnas hardcoded; nuevo PIM tiene 42 |
| Traducciones | Solo `es/ar/en` permitidos por constraint; faltan `fr/de/it/pt` |
| Certifications | Tabla M:N existe pero no hay writer en el pipeline |
| Applier duplicado | `applier.py` y `pim_importer.py` implementan lógica paralela divergente |
| Reconciliación | No hay verificación de que total rows == filas procesadas |
| LLM field catalog | `_AVAILABLE_FIELDS_DOC` incompleto: faltan traducciones, certs, varios escalares |

---

## 2. Arquitectura General

### Flujo actual (a reemplazar)

```
xlsx → detect_header_row → suggest_mapping (LLM) → flat dict → applier.py (sync wizard)
                                                              → pim_importer.py (batch Celery)
```

### Flujo nuevo

```
xlsx bytes
   │
   ├─► detect_header_row()          [sin cambio — ya funciona bien]
   │         │ header_idx, headers, samples
   ▼
   suggest_mapping() LLM            [expandir _AVAILABLE_FIELDS_DOC]
   │         │ list[ColumnMappingItem]
   │         ▼
   │   [usuario revisa mapping en UI — sin cambio de UX]
   │
   ▼
XlsxParser                          [NUEVO — reemplaza parse_xlsx_stream + map_row_with_mapping]
   │         │ Iterator[ParsedProduct]
   ▼
ImportOrchestrator                  [NUEVO — reemplaza applier.py + pim_importer.py]
   ├─► ScalarWriter       → products (upsert, respeta manual_locked_fields)
   ├─► JsonbWriter        → products.dimensions / packaging / specs (merge)
   ├─► TranslationWriter  → product_translations (upsert por sku+lang)
   ├─► CertificationWriter→ certifications get-or-create + product_certifications M:N
   └─► ReconciliationPass → verifica total_excel_rows == sum(all_buckets)
```

Un único `ImportOrchestrator` sirve para wizard sync **y** batch Celery — elimina la duplicación actual.

---

## 3. Componentes Nuevos

### 3.1 `ParsedProduct` — `app/services/importer/parsed_product.py`

Dataclass central del pipeline. Reemplaza el dict plano que producía `map_row_with_mapping`.

```python
@dataclass
class ParsedProduct:
    sku: str
    scalars: dict[str, Any]
    # Campos scalares directos de products: weight, hs_code, connection,
    # bore_mm, pressure_max_bar, temp_min_c, temp_max_c, series, size,
    # material, dn, pn, intrastat_code, erp_name, external_url, family, brand

    jsonb: dict[str, dict[str, Any]]
    # {"dimensions": {"high_mm": ..., "wide_mm": ..., "deep_mm": ...},
    #  "packaging":  {"qty_per_box": ..., "box_high_mm": ..., ...},
    #  "specs":      {"ean_individual": ..., "ean_box": ..., "en_catalogo": ...}}

    translations: dict[str, str]
    # {"en": "Ball valve DN25", "es": "Válvula de bola DN25", "fr": ..., ...}
    # Claves válidas: en, es, fr, de, it, pt, ar

    certifications: list[str]
    # ["CE", "ISO 9001", "WRAS"] — split por coma desde la columna Excel

    errors: list[str]
    # Cast errors no fatales — la fila se persiste parcialmente con los campos OK
```

### 3.2 `XlsxParser` — `app/services/importer/xlsx_parser.py`

Reemplaza `parse_xlsx_stream` + `map_row_with_mapping`. Recibe bytes xlsx + `list[ColumnMappingItem]` (del LLM o canónico) y produce `Iterator[ParsedProduct]` de forma streaming (memory-safe para 5 000+ rows).

**Reconocimiento de prefijos de target:**

| Target field | Destino en ParsedProduct |
|---|---|
| `sku`, `weight`, `hs_code`, `connection`, ... | `scalars` |
| `dimensions.high_mm`, `packaging.qty_per_box`, `specs.*` | `jsonb[prefix][key]` |
| `translations.en`, `translations.fr`, `translations.es`, ... | `translations[lang]` |
| `certifications` | `certifications` (split por coma, strip, deduplicate) |
| `_skip` | ignorado |

Usa el mismo catálogo de `CASTERS` (text, int, decimal, cm_to_mm, ean, bool_check, percent) ya existente en `column_mapper.py`.

Comportamiento ante filas vacías: las salta silenciosamente sin contar como error. Comportamiento ante SKU vacío: cuenta la fila como `error_row`.

### 3.3 `RowWriter` pipeline — `app/services/importer/row_writer.py`

Orquesta los 4 writers sobre un `ParsedProduct`. Compartido entre wizard sync y Celery batch.

```python
class RowWriter:
    async def apply(
        self,
        session: AsyncSession,
        parsed: ParsedProduct,
        locked_fields: set[str],
        actor_id: UUID,
    ) -> WriteResult
    # WriteResult: bucket (inserted|updated|no_change|error|locked), changed_fields, errors
```

**`ScalarWriter`**
- Upsert en `products` por `sku`
- Respeta `manual_locked_fields`: no sobrescribe campos en el set de locked
- Detecta `inserted` vs `updated` vs `no_change` comparando valores actuales

**`JsonbWriter`**
- Merge JSONB: solo actualiza las keys presentes en el mapping, no borra keys existentes
- `{"dimensions": {"high_mm": 50}}` → actualiza solo `high_mm`, deja `wide_mm` intacto

**`TranslationWriter`**
- Upsert por `(sku, lang)` en `product_translations`
- Solo escribe el campo `name` desde el import (description y otros campos editoriales no se tocan)
- `status = 'imported'` para traducciones provenientes del Excel
- Respeta locked si `translations.{lang}` está en `manual_locked_fields`

**`CertificationWriter`**
- Split de `certifications` por coma, strip, lower para normalización
- `get_or_create` en tabla `certifications` por nombre normalizado
- Escribe en `product_certifications` solo las nuevas entradas (no duplica)
- No elimina certificaciones existentes que no estén en el Excel (additive-only)

### 3.4 `ImportOrchestrator` — `app/services/importer/import_orchestrator.py`

Reemplaza `applier.py` (wizard sync) **y** `pim_importer.py` (batch Celery).

```python
class ImportOrchestrator:
    def __init__(self, session: AsyncSession, actor_id: UUID, run_id: UUID | None = None): ...

    async def run_sync(
        self,
        xlsx_bytes: bytes,
        mapping: list[ColumnMappingItem],
        preview_only: bool = False,
        chunk_size: int = 1000,
    ) -> OrchestratorResult

    async def run_batch(
        self,
        source_path: Path,
        mapping: list[ColumnMappingItem] | None = None,
        # None → auto-detect headers + LLM suggest_mapping
    ) -> OrchestratorResult
```

`OrchestratorResult` contiene: `run_id`, counters por bucket, lista de errores (cap 100), y el `ReconciliationResult`.

Commit periódico cada 100 filas (igual que el batch actual). Savepoints por chunk (igual que el wizard actual). Errores por fila no abortan el run.

### 3.5 `ReconciliationPass` — dentro de `ImportOrchestrator`

Paso final obligatorio después de procesar todas las filas.

```python
@dataclass
class ReconciliationResult:
    total_excel_rows: int     # filas en xlsx excl. header + filas vacías
    inserted: int
    updated: int
    no_change: int
    error_rows: int
    locked_rows: int
    accounted_total: int      # suma de todos los buckets
    gap: int                  # total_excel_rows - accounted_total (debe ser 0)
    missing_skus: list[str]   # SKUs presentes en Excel sin bucket asignado
    is_complete: bool         # gap == 0
```

Cálculo basado en **conteo de filas** (no conjuntos de SKUs, para tolerar duplicados en el Excel):

```python
# El XlsxParser cuenta filas no-vacías conforme las produce (incluyendo duplicados de SKU)
total_excel_rows: int = parser.rows_yielded

# El RowWriter incrementa un counter por cada fila, sin importar su bucket
accounted_total: int = inserted_count + updated_count + no_change_count + error_count + locked_count

gap = total_excel_rows - accounted_total  # debe ser 0

# missing_skus es diagnóstico secundario (ignora duplicados)
skus_in_excel = {p.sku for p in all_parsed_products if p.sku}
skus_accounted = inserted_skus | updated_skus | no_change_skus | error_skus | locked_skus
missing_skus = list(skus_in_excel - skus_accounted)
```

Si `gap > 0`, el resultado se marca como `is_complete=False` y el `ImportRun.status` queda en `completed_with_errors` (no `completed`). Se persiste la lista de `missing_skus` en `ImportRun.errors` para descarga.

### 3.6 `TranslationCompletionService` — `app/services/translations/completion_service.py`

Servicio on-demand para completar traducciones faltantes con Claude.

```python
class TranslationCompletionService:
    async def complete(
        self,
        skus: list[str],           # hasta 50 SKUs por llamada
        target_langs: list[str],   # ["fr", "de", "it", "pt"]
        source_lang: str = "en",
        actor_id: UUID,
        session: AsyncSession,
    ) -> CompletionResult
    # CompletionResult: {completed: int, skipped: int, errors: int, details: list}
```

Estrategia LLM:
- Batch de hasta 20 productos por llamada a Claude (eficiencia de tokens)
- Prompt incluye: nombre en `source_lang`, `erp_name`, `family`, `specs` relevantes
- Respuesta: JSON array `[{sku, lang, name}]`
- Escribe vía `TranslationWriter` con `status='ai_generated'`
- `translated_by = NULL`, `translated_at = now()` (no es un usuario humano)

---

## 4. Cambios al LLM Field Catalog

`mapping_detector._AVAILABLE_FIELDS_DOC` se expande con todos los campos reales del modelo:

```
Scalar fields (products table):
  sku (required), family, subfamily, type, erp_name, intrastat_code, hs_code,
  connection, brand, weight, bore_mm, pressure_max_bar, temp_min_c, temp_max_c,
  series, material, dn, pn, size, revision, external_url, gtin

JSONB sub-fields (dot notation):
  dimensions.high_mm, dimensions.wide_mm, dimensions.deep_mm
  packaging.qty_per_box, packaging.box_high_mm, packaging.box_wide_mm,
  packaging.box_deep_mm, packaging.moq_inner_box, packaging.x_pallet
  specs.<any_key>   ← EANs, flags, values no cubiertos por escalares

Translations (escribe en product_translations.name):
  translations.en, translations.es, translations.fr,
  translations.de, translations.it, translations.pt, translations.ar

Multi-value comma-separated (M:N):
  certifications   ← "CE, ISO 9001, WRAS" → split + get-or-create

Special:
  _skip            ← ignorar esta columna
```

El prompt de `suggest_mapping` también recibe la instrucción explícita de identificar columnas multiidioma por contexto (ej: "Nombre FR" → `translations.fr`).

---

## 5. Migración de Base de Datos

### Migración 155 — Extend translations lang constraint

```sql
-- Añadir soporte FR, DE, IT, PT a product_translations
ALTER TABLE product_translations
  DROP CONSTRAINT ck_translations_lang;

ALTER TABLE product_translations
  ADD CONSTRAINT ck_translations_lang
    CHECK (lang IN ('es', 'ar', 'en', 'fr', 'de', 'it', 'pt'));
```

Código Python: actualizar constante `SUPPORTED_LANGS` y el enum `TranslationLang` en `app/db/models/product.py`.

Añadir valor `'ai_generated'` al enum `TranslationStatus` para distinguir traducciones LLM de humanas.

### Sin más migraciones

Todos los campos técnicos objetivo (`hs_code`, `connection`, `bore_mm`, `pressure_max_bar`, `temp_min_c`, `temp_max_c`, `series`, `size`, `external_url`) ya existen en `products`. La tabla `product_certifications` y su M:N ya existen. No se requieren columnas nuevas.

---

## 6. Nuevos Endpoints API

### `POST /products/translations/complete`

```
Body: { skus: string[], target_langs: string[], source_lang?: string }
Response: { completed: int, skipped: int, errors: int, details: [{sku, lang, status}] }
RBAC: products:write
```

Lanza `TranslationCompletionService.complete()`. Síncrono para batches ≤ 50 SKUs. Para batches mayores, disparar Celery task y devolver `202 Accepted` con `task_id`.

### `GET /products/translations/coverage`

```
Query params: ?langs=en,es,fr&family=valves
Response: { total_products: int, coverage: [{lang, count, pct}], missing_by_lang: {fr: 234, de: 445} }
RBAC: products:read
```

---

## 7. Cambios Frontend

### 7.1 Wizard de importación (5 pasos — sin cambio de UX)

El wizard mantiene sus 5 pasos actuales. El único cambio visible: el **Paso 5 (Reporte)** añade un panel de reconciliación:

```
✅ Carga completa
   5 085 filas en Excel
   127 filas creadas · 4 901 actualizadas · 57 sin cambios · 0 errores
   0 filas sin contabilizar

── o ──

⚠️ Carga incompleta — 3 filas sin contabilizar
   [Descargar CSV de filas faltantes]   ← botón de descarga
```

### 7.2 Nuevo tab "Traducciones" en detalle de producto

En la pantalla de detalle de producto (Pantalla 4), añadir un tab "Traducciones":

- Tabla: idioma | nombre actual | estado (pending / imported / ai_generated / reviewed)
- Indicador de cobertura: "4 / 7 idiomas completados"
- Botón "Completar con IA" (activa para langs con `status = pending` o ausentes)
  - Selección de idiomas a completar
  - Confirmación + feedback inline

### 7.3 Indicador de cobertura en lista de productos (opcional en este sprint)

Columna de cobertura de traducciones en la tabla de productos (`/products`). Postergable si el sprint se satura.

---

## 8. Compatibilidad y Migración de Código Existente

| Archivo actual | Destino |
|---|---|
| `column_mapper.py` (EXCEL_COL_TO_FIELD, EXPECTED_HEADERS, map_row) | Mantener para backward-compat; deprecar. El nuevo `XlsxParser` no lo usa. |
| `pim_row_mapper.py` | Deprecar. Sustituido por `XlsxParser` + `ParsedProduct`. |
| `applier.py` | Deprecar. Sustituido por `ImportOrchestrator.run_sync()`. |
| `pim_importer.py` | Deprecar. Sustituido por `ImportOrchestrator.run_batch()`. |
| `importer_service.py` | Actualizar para usar `ImportOrchestrator`. |
| `mapping_detector.py` | Conservar `detect_header_row` + `suggest_mapping`; solo actualizar `_AVAILABLE_FIELDS_DOC`. |
| Tests existentes | Los tests de `column_mapper`, `parser`, `applier` siguen pasando (código no se borra). Añadir nueva suite de tests para los componentes nuevos. |

Los endpoints API existentes (`/imports/analyze`, `/imports/preview`, `/{run_id}/apply`, etc.) **no cambian su contrato**. Solo sus implementaciones internas cambian para usar el nuevo pipeline.

---

## 9. Testing

| Capa | Tests |
|---|---|
| `XlsxParser` | Unit: cada tipo de target field (scalar, jsonb, translations, certifications); filas vacías; EAN inválido |
| `RowWriter` + writers | Unit: insert vs update vs no_change; locked fields respetados; TranslationWriter upsert por lang; CertificationWriter get-or-create |
| `ImportOrchestrator` | Integration: run_sync con preview + apply; run_batch desde fixture |
| `ReconciliationPass` | Unit: gap=0 caso feliz; gap>0 con missing_skus |
| `TranslationCompletionService` | Unit con mock Claude; integration con DB |
| `suggest_mapping` expandido | Unit: nuevas columnas de PIM_JcS_1 resuelven correctamente |

---

## 10. Secuencia de Implementación

1. **Migración 155** — extend lang constraint + `ai_generated` status
2. **`ParsedProduct` dataclass** — central, sin dependencias
3. **`XlsxParser`** — depende de ParsedProduct + CASTERS existentes
4. **Writers** (Scalar, Jsonb, Translation, Certification) — independientes entre sí
5. **`RowWriter` pipeline** — compone los writers
6. **`ReconciliationPass`** — depende de RowWriter counters
7. **`ImportOrchestrator`** — compone XlsxParser + RowWriter + ReconciliationPass
8. **Actualizar `importer_service.py`** — conectar a ImportOrchestrator
9. **Actualizar `_AVAILABLE_FIELDS_DOC`** en mapping_detector
10. **`TranslationCompletionService`** + endpoint `POST /products/translations/complete`
11. **Endpoint `GET /products/translations/coverage`**
12. **Frontend: panel reconciliación en wizard paso 5**
13. **Frontend: tab Traducciones en detalle de producto**
