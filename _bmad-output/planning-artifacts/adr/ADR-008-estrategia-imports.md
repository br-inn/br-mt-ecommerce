# ADR-008: Estrategia de imports (PIM + costos como sources reales; Excel demo como fixture)

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), Comercial Online MT

## Contexto

Aclaración del usuario en sesión 2026-05-06:
- El Excel `stock_dubai_v23` es **datos demo** + spec de modelo de datos + fixture de pruebas. **NO es source operativa** Fase 1.
- Sources reales confirmadas: **archivo PIM** + **archivos de costos** entregados por MT en Sprint 0.
- Tras la carga del PIM real + costos reales, el Excel demo se archiva read-only.

Necesitamos: importers diferenciados, validación cruzada, FX as-of stamping, política de upsert, manejo de conflictos, audit denso.

## Decisión

### Tres importers separados

#### 1. Importer PIM (real)
- Input: archivo entregado por MT en S0 (formato a confirmar; supuesto: XLSX o CSV).
- Tabla destino: `products` + `product_translations`.
- Campos esperados (mínimo): SKU, name_en, family, dn, pn, type, material, image_url, name_es, name_ar, ...
- Política de upsert: por SKU. Si existe → UPDATE de campos no-bloqueados, INSERT en `audit_events` con diff. Si no existe → INSERT.
- Validación pre-apply:
  - SKU formato regex (a definir con MT).
  - `name_en` NOT NULL.
  - DN/PN con vocabulario controlado (vista `valid_dn`, `valid_pn`).
  - Material en enum.
- Diff preview obligatorio antes de apply (UI: "vas a crear N, actualizar M, error K").
- Conflicto: si un campo está marcado `manual_lock=true` en DB (Comercial editó a mano post-import previo), el importer no lo sobrescribe → reporta como `skipped_locked`.

#### 2. Importer Costos (real)
- Input: archivos de costos entregados por MT en S0 (uno o varios; formato a confirmar).
- Tabla destino: `costs` (líneas desglosadas por SKU × esquema × supplier).
- Campos esperados: SKU, scheme_code, supplier_code, FOB, freight, customs, FBA fees, FBM fees, payment fees, marketing, currency, effective_at.
- Validación cruzada con PIM: cada SKU del archivo de costos debe existir en `products`. Si no, reporte `orphan_skus` (no aborta, marca y continúa).
- FX as-of stamping: si `currency != AED`, stampa el FX vigente al `effective_at`. Si no hay FX para esa fecha, aborta el batch con error claro.
- Política upsert: por (SKU, scheme, supplier, effective_at). Versión nueva si cambia el `effective_at`.

#### 3. Importer Excel demo (fixture / spec)
- Input: `stock_dubai_v23_PRESENTACION_2026-05-01.xlsx`.
- Uso: cargar dataset de pruebas para desarrollo, QA, parallel run con el motor de pricing v5.1.
- Política: **read-only post primera carga del PIM real**. El Excel queda renombrado `_ARCHIVE_YYYY-MM-DD`.
- Importer dedicado parser: lee sheets `INVOICE ENRIQUECIDA v5`, `Tarifas FBA & FBM`, `PIM Maestro`, `PIM IDIOMAS`, mapea a `products` + `costs` + `prices` (estos últimos con `migrated, FX inferred` flag).
- **Esto es código throw-away** — vive en `apps/web/src/jobs/imports/excel_legacy/` y se puede borrar tras Fase 1.

### Pipeline común de imports

Todos los importers comparten pipeline:

```
upload (multipart) → store in S3 (raw) → enqueue ImportJob (BullMQ)
        ↓
ImportJob:
  parse  → validate (per-row, fail-fast or fail-soft según importer)
        → diff preview (persist en `import_runs.preview JSONB`)
        → wait for human confirmation (UI shows preview, user clicks Apply)
        → apply (transactional, single PG transaction or chunked si N > 1000)
        → audit (1 fila resumen + N filas por entidad)
        → notify (in-app + email)
```

Tablas de soporte:
- `import_runs (id, type, file_url, uploaded_by, status, started_at, finished_at, summary JSONB, error_log JSONB)`.
- `import_run_rows (run_id, row_index, entity_type, entity_id, action, status, error)`.

### Reglas globales

- **Idempotencia**: cada `ImportJob` tiene `idempotency_key = SHA256(file_content + importer_version)`. Reintento con misma key reusa el mismo run.
- **Atomicidad**: por defecto, "apply" es una transacción Postgres única. Si > 5000 filas, se chunkea con savepoints; en error de chunk, rollback chunk + report parcial + offer "continue without failing chunk" o "rollback all".
- **Audit denso**: cada fila aplicada inserta `audit_events` row con `action='import_apply'`, `before` (snapshot pre), `after` (snapshot post), `diff`, `import_run_id`.
- **Lock**: durante apply, lock advisory (`pg_advisory_lock(hash('import:' || importer_type))`) para evitar dos imports concurrentes del mismo tipo.
- **Worker**: imports corren en proceso worker BullMQ separado del API (no bloquean Next.js process).

### Excel demo workflow específico

- Sólo `admin` puede correrlo (no Comercial / Gerente).
- Escribe a tablas con flag `data_quality='migrated_demo'` y `prices.status='migrated'` (estado terminal no integrable, requiere re-aprobación explícita por SKU para mover a `approved`).
- Tras carga del PIM real: el `admin` ejecuta `archive_excel_legacy` que renombra el archivo en S3 a `_ARCHIVE_YYYY-MM-DD/...` y bloquea futuras ejecuciones del importer demo.

## Alternativas evaluadas

### Alternativa A: Un único importer "todoterreno" con detección de schema
- **Pros**: menos código.
- **Contras**: la fuente real (PIM + costos separados) tiene schemas distintos del Excel demo (sheets distintos). Detección automática es frágil.
- **Veredicto**: descartada.

### Alternativa B: ETL externo (Airbyte, Fivetran, dbt)
- **Pros**: pipeline maduro.
- **Contras**: setup pesado para 3 imports puntuales en Fase 1; lock-in; coste mensual.
- **Veredicto**: descartada Fase 1; revisar Fase 2 cuando se integre PIM/ERP España bidireccional.

### Alternativa C: Carga directa SQL por TI MT (no UI de import)
- **Pros**: máxima velocidad para batch grandes.
- **Contras**: bypasa validación, audit, diff preview. Comercial no puede operar.
- **Veredicto**: descartada como flujo principal; queda como fallback de emergencia con `admin` rol.

## Consecuencias positivas

- Diff preview antes de apply previene errores masivos.
- Audit denso satisface compliance.
- Reuso del pipeline base reduce código.
- Excel demo claramente segregado → no contamina sources reales.

## Consecuencias negativas / riesgos

- Schema del PIM real desconocido hasta S0 → no podemos pre-codificar el parser. Mitigación: S0 entrega muestra; importer se codea S1 contra schema real.
- Upsert con `manual_lock` requiere disciplina de la Comercial (decidir cuándo bloquear). Mitigación: UI muestra claramente qué está locked y por quién.
- Imports muy grandes (Fase 4: 50k SKUs) pueden exceder transacción única. Mitigación: chunk con savepoints, ya considerado.

## Cuándo revisar

- **S0**: una vez recibidos PIM + costos reales, validar formato y ajustar parser plan.
- **S2**: post import real, retro de errores y ajuste de validation rules.
- **Fase 2**: integración bidireccional con PIM España — re-evaluar si vale la pena adoptar Airbyte/dbt.
