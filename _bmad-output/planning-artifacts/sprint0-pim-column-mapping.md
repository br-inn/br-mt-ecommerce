---
title: "Sprint 0 — Mapping de PIM completo.xlsx al schema products"
status: "draft"
version: "1.0"
created: "2026-05-06"
project_name: "mt-pricing-mdm-phase1"
sprint: "S0"
gating: "diseño y construcción del importer Fase 1a"
inputs:
  - "Documentos referencia de articulos/PIM completo.xlsx (5086 rows × 17 cols)"
  - "Documentos referencia de articulos/catalogo_mt_productos.xlsx (4182 rows × 6 cols)"
  - "Documentos referencia de articulos/Copia de Compatibilidad de Materiales MT V4.xlsx (657 rows × 14 cols)"
  - "prd-mt-pricing-mdm-phase1.md v1.3"
  - "architecture-mt-pricing-mdm-phase1.md v1.3"
---

# Sprint 0 — Mapping de PIM completo.xlsx al schema `products`

> Entregable Sprint 0 que **cierra la decisión de schema** antes de construir el importer Fase 1a (UC-1a-05). Toda la inspección se hizo con `openpyxl read_only=True`. Conteos validados contra la realidad del archivo.

## 0. Validación de conteos vs PRD/arquitectura

| Fuente                                  | PRD/arq dice    | Medido (openpyxl)              | Estado |
|-----------------------------------------|-----------------|--------------------------------|--------|
| `PIM completo.xlsx`                     | 5086 × 17       | 5086 (1 header + 5085 datos) × 17 | OK |
| `catalogo_mt_productos.xlsx`            | 4182 × 6        | 4182 (1 header + 4181 datos) × 6  | OK |
| `Copia de Compatibilidad ... MT V4.xlsx`| 657 × 14        | 657 × 19 columnas físicas; **655 datos + 1 header**; **14 columnas útiles** (cols 0-13), cols 14-18 contienen leyenda y un link → no son datos. **650 productos únicos** (5 pares duplican `Producto` con distinta T °C). | DIFF: 657 filas reales pero solo 655 con datos + 2 vacías; ancho lógico = 14 (PRD correcto), físico = 19 |

Acción: arquitectura debe documentar que la matriz de compatibilidad tiene **650 productos × 11 materiales × 1+ temperaturas** (no 657 productos). Ver Task 7.

---

## Task 1 — Inventario completo de `PIM completo.xlsx`

Sheet único: `sheet1`. **5085 filas de datos**, 17 columnas. **Todos los valores leídos llegan como `str`** desde el archivo (incluyendo numéricos) → el importer debe castear.

| # | Header exacto | Tipo observado | Cardinalidad (uniq) | Nullabilidad | Sample (3-5) | Patrón / formato |
|---|---------------|----------------|---------------------|--------------|--------------|------------------|
| 0 | `Referencia de variante` | text (sku) | 5085 / 5085 (PK natural) | 0 nulos | `001010`, `001015`, `AG0000010`, `01A40026200`, `64750001615` | Mixto: numérico zero-padded (6 dígits), alfanumérico legacy. **Único 100 %** → candidato a PK. |
| 1 | `Cod.Intrastat - AX` | text (HS code) | 58 enums | 2 nulos (0,04 %) | `74122000`, `84818081`, `73071910`, `8481808190`, `73072100` | 8 o 10 dígitos numéricos (HS / TARIC EU). Top: `74122000` (1308), `84818081` (551). |
| 2 | `Nombre ERP - AX` | text | 3912 / 5085 | 1128 nulos (22,2 %) | `m-f 90° bend galvanised 3/8”`, `m-f 90° bend galvanised 1/2”`, `m-f 90° bend galvanised 3/4”` | Inglés, lowercase, contiene specs implícitas (tipo, material, medida). Las 1173 colisiones (5085-3912) son **variantes que comparten descriptor**. |
| 3 | `INDIVIDUAL EAN CODE` | text (EAN-13) | 4177 | 908 nulos (17,9 %) | `8435319100004`, `8435319100011`, `8435319100028` | 13 dígitos. Prefijo MT `8435319...`. Validar check-digit. |
| 4 | `weight unit` | float-as-text (kg) | 1468 | 1 nulo | `0.0661`, `0.1`, `0.19`, `0.3`, `0.54` | Decimal punto, kg. **Igual que `net weight unit` en TODAS las filas inspeccionadas → posible duplicado.** TODO confirmar si difieren en algún SKU. |
| 5 | `net weight unit` | float-as-text (kg) | 1468 | 1 nulo | idem | idem |
| 6 | `High mm` | float-as-text (mm) | 731 | 1 nulo | `4.85`, `5.95`, `8.04`, `9.99`, `11.94` | mm. Header confirma unidad (no requiere conversión). |
| 7 | `Wide mm` | float-as-text (mm) | 692 | 1 nulo | `4.85`, `5.95`, `8.04` | mm. |
| 8 | `Deep mm` | float-as-text (mm) | 624 | 1 nulo | `2.5`, `2.9`, `3.58` | mm. |
| 9 | `EAN CODE BOX` | text (GTIN-14) | 3842 | 1243 nulos (24,4 %) | `28435319100008`, `28435319100015` | 14 dígitos (prefijo `2` indicator + EAN-13). |
| 10 | `qty x box` | int-as-text | 116 enums | 1 nulo | `250`, `180`, `100`, `40`, `20` | Entero, packaging. |
| 11 | `Alto caja (cm) - AX` | float/int-as-text (**cm**) | 75 | 1 nulo | `17`, `38`, `26` | **cm — debe convertirse a mm** para coherencia con `High/Wide/Deep mm`. |
| 12 | `Ancho caja (cm) - AX` | float/int-as-text (cm) | 71 | 1 nulo | `38` | cm → mm. |
| 13 | `Largo caja (cm) - AX` | float/int-as-text (cm) | 86 | 1 nulo | `26` | cm → mm. |
| 14 | `EAN CODE INNER BOX` | text (GTIN-14) | 3786 | 1299 nulos (25,5 %) | `18435319100001`, `18435319100018` | 14 dígitos (prefijo `1`). |
| 15 | `MOQ INNER BOX` | int-as-text | 40 enums | 1 nulo | `10`, `5`, `1` | Entero. |
| 16 | `X PALLET` | int-as-text | 376 | 1 nulo | `11250`, `8100`, `4500` | Entero. Cantidad por palet. |

**Hallazgos transversales**

- 1173 SKUs son variantes que comparten `Nombre ERP - AX` (5085 SKUs vs 3912 nombres). Confirmar si la lógica es 1 SKU = 1 producto vendible (sí, recomendado) o agruparlas en un padre.
- `weight unit` ≈ `net weight unit` parecen idénticas en muestras → probablemente **gross/net** colapsados. TODO: comparar fila a fila para validar.
- ~22 % de filas no tienen `Nombre ERP` → riesgo de SKU sin descripción. Caso típico: artículos legacy o accesorios sin ficha. Plan: enriquecer desde catálogo derivado (`Categoría` + `Medida`) cuando exista intersección.
- Las dimensiones de **producto** vienen en mm; las de **caja** vienen en cm. Convertir cm→mm en el importer para uniformidad.

---

## Task 2 — Mapping a `products` schema

Tabla canónica de mapping (17 columnas Excel → tabla/columna destino).

| # | Columna Excel              | Tabla destino     | Columna destino                          | Transformación                                    | Notas |
|---|----------------------------|-------------------|------------------------------------------|---------------------------------------------------|-------|
| 0 | `Referencia de variante`   | `products`        | `sku` (PK)                               | `TRIM`; conservar zero-padding y mixto alfa-num   | PK natural confirmada (uniq=5085). |
| 1 | `Cod.Intrastat - AX`       | `products`        | `intrastat_code` **(NUEVO)**             | `TRIM`; longitud 8 ó 10                           | Sumar columna al schema. |
| 2 | `Nombre ERP - AX`          | `products`        | `erp_name` **(NUEVO)** + insumo a parser de specs | `TRIM`. Pasar como input a parser/LLM para extraer `type`, `material`, `dn`, `connection`. **NO** mapear directo a `name_en`. | `name_en` (NOT NULL en schema) requiere fuente canónica más limpia (PIM España, traducción humana, o LLM con human-in-the-loop). |
| 3 | `INDIVIDUAL EAN CODE`      | `product_eans` **(NUEVA)** | `(sku, ean_type='individual', ean)`     | Validar check-digit EAN-13                        | Multi-EAN por SKU exige tabla aparte. |
| 4 | `weight unit`              | `products`        | `weight_gross_kg` (a especificar)        | `CAST` text→numeric; unidad `kg` implícita        | TODO confirmar si `weight unit` = peso bruto. |
| 5 | `net weight unit`          | `products`        | `weight_net_kg` (a especificar)          | `CAST` text→numeric                               | TODO confirmar si difiere de bruto en algún SKU. |
| 6 | `High mm`                  | `products`        | `dimensions->>'high_mm'` (JSONB)         | `CAST` text→numeric                               | JSONB `dimensions = {high_mm, wide_mm, deep_mm}`. |
| 7 | `Wide mm`                  | `products`        | `dimensions->>'wide_mm'` (JSONB)         | `CAST` text→numeric                               | idem |
| 8 | `Deep mm`                  | `products`        | `dimensions->>'deep_mm'` (JSONB)         | `CAST` text→numeric                               | idem |
| 9 | `EAN CODE BOX`             | `product_eans`    | `(sku, ean_type='box', ean)`             | Validar check-digit GTIN-14                       |   |
| 10 | `qty x box`               | `products`        | `packaging->>'qty_per_box'` (JSONB)      | `CAST` text→int                                   | JSONB `packaging`. |
| 11 | `Alto caja (cm) - AX`     | `products`        | `packaging->>'box_high_mm'`              | `CAST` text→numeric **× 10** (cm → mm)            | Conversión de unidad. |
| 12 | `Ancho caja (cm) - AX`    | `products`        | `packaging->>'box_wide_mm'`              | idem × 10                                         |   |
| 13 | `Largo caja (cm) - AX`    | `products`        | `packaging->>'box_deep_mm'`              | idem × 10                                         |   |
| 14 | `EAN CODE INNER BOX`      | `product_eans`    | `(sku, ean_type='inner_box', ean)`       | Validar check-digit GTIN-14                       |   |
| 15 | `MOQ INNER BOX`           | `products`        | `packaging->>'moq_inner_box'`            | `CAST` text→int                                   |   |
| 16 | `X PALLET`                | `products`        | `packaging->>'x_pallet'`                 | `CAST` text→int                                   |   |

**Estructura JSONB resultante en `products`**

```jsonc
{
  "dimensions": { "high_mm": 4.85, "wide_mm": 4.85, "deep_mm": 2.5 },
  "packaging":  { "qty_per_box": 250, "box_high_mm": 170, "box_wide_mm": 380, "box_deep_mm": 260, "moq_inner_box": 10, "x_pallet": 11250 }
}
```

**Tabla nueva propuesta**

```sql
CREATE TABLE product_eans (
  sku       TEXT NOT NULL REFERENCES products(sku) ON DELETE CASCADE,
  ean_type  TEXT NOT NULL CHECK (ean_type IN ('individual','box','inner_box')),
  ean       TEXT NOT NULL,
  PRIMARY KEY (sku, ean_type)
);
CREATE INDEX idx_product_eans_ean ON product_eans(ean);
```

---

## Task 3 — Identificación de gaps (campos schema NO presentes en PIM completo)

| Campo schema                          | ¿En PIM completo? | Fuente alternativa                                                                                  | Decisión Sprint 0 |
|---------------------------------------|-------------------|-----------------------------------------------------------------------------------------------------|-------------------|
| `name_en` (NOT NULL)                  | NO (sólo `Nombre ERP - AX` y con 22 % nulos) | (a) Limpieza de `erp_name` con regla; (b) PIM España; (c) traducción LLM con HITL                   | Backfill con `erp_name` saneado; marcar `data_quality='partial'` cuando provenga de auto. |
| `description_en`, `marketing_copy_en` | NO                | Fichas técnicas PDF (MTFT_*); MT-Catalogo.pdf; redacción manual                                     | Captura manual Fase 1.1; OCR/extracción Fase 1.5. |
| `name_es` (en `product_translations`) | NO                | `stock_dubai_v23` sheet `PIM IDIOMAS` (si está); o catálogo derivado `Categoría` + `Medida`; o LLM | Fase 1: cargar desde `PIM IDIOMAS` si disponible; si no, batch LLM con HITL. |
| `name_ar` (en `product_translations`) | NO                | `PIM IDIOMAS` (probablemente vacío); LLM EN→AR con revisión nativa                                  | Fase 1: marcar `pending`; backfill LLM Fase 1.1. |
| `family`, `subfamily` (NOT NULL)      | NO directo        | Catálogo derivado: `Sección` + `Categoría`                                                          | JOIN por `Código`==`Referencia de variante` cuando exista; default `family='unclassified'` con flag manual. |
| `material`                            | NO directo        | Catálogo derivado columna `Material` (9 enums); también inferible de `erp_name` (`galvanised`, `brass`, `ss316`...) | JOIN catálogo prioritario; parser sobre `erp_name` como fallback. |
| `type` (valve type)                   | NO directo        | Catálogo `Categoría` (53 enums tipo `THREADED BALL VALVES`); parser sobre `erp_name`                | JOIN catálogo prioritario. |
| `dn`, `pn`, `connection`              | NO directo        | Parser sobre `erp_name` (`3/8”`, `1/2”`, `DN50`, `PN16`); catálogo `Medida`                         | Parser regex; LLM extraction sobre los que no matchean. |
| `brand`                               | NO                | Asumir `MT` para todos los SKUs del PIM                                                             | Default `brand='MT'` en importer. |
| Imagen producto (`product_images`)    | NO                | PIM España + bucket `product-images` (mirror)                                                       | Fuera de scope del importer Fase 1a. |
| Costes y precios                      | NO                | Archivo separado (Sprint 0 entregable distinto)                                                     | Fuera de scope. |
| Compatibilidad de materiales          | NO                | `Copia de Compatibilidad de Materiales MT V4.xlsx`                                                  | Importer separado FR-MAT-01. |

**Confirmación SKU canónico**: `Referencia de variante` (uniq=5085) **es** el SKU. El formato `MT-V-038-DN50-PN16` mencionado en PRD §187 es un **patrón objetivo del comparador Fase 2**, no el formato actual del PIM. El importer Fase 1 debe respetar el SKU tal cual viene; si se desea normalizar a un formato canónico, hacerlo en columna `sku_canonical` separada (no destructivo).

---

## Task 4 — Reglas de transformación

### 4.1 Casts y unidades
- **Texto → numérico**: cols 4-8, 10-13, 15, 16 vienen como `str` → cast con `try/except`; rechazar fila si falla y reportar.
- **cm → mm** (cols 11, 12, 13): multiplicar × 10 antes de persistir en `packaging.box_*_mm` para uniformidad con dimensiones de producto en mm.
- **Padding numérico**: NO normalizar `Referencia de variante` (puede romper joins con catálogo y costes). Conservar exact-string.

### 4.2 Parsing de `Nombre ERP - AX`
Heurísticas iniciales (Sprint 0 = bocetar; Sprint 1 = implementar):
- `material`: detectar `galvanised`, `brass`, `nickel`, `ss304`, `ss316`, `cast iron`, `pvc`.
- `type`: detectar `bend`, `tee`, `elbow`, `nipple`, `union`, `ball valve`, `gate valve`, `check valve`, `filter`, `reducer`, `socket`, `cap`, `plug`.
- `connection/dn`: regex `(\d+(?:\s+\d+/\d+)?(?:/\d+)?["”])` para roscas BSP en pulgadas; `DN(\d+)` para métricas; `PN(\d+)`.
- **Fallback**: cuando regex no matchea, encolar para LLM extraction (Claude tool-use con JSON schema).

### 4.3 Validaciones
- **EAN-13 / GTIN-14 check-digit**: implementar mod-10 estándar. Rechazar EAN inválido; loggear pero **no abortar la fila** (EAN puede faltar; el resto del producto sigue siendo útil).
- `weight_kg > 0` cuando no nulo.
- `dimensions.{high,wide,deep}_mm > 0` cuando no nulo.
- `Cod.Intrastat`: longitud ∈ {8, 10}, sólo dígitos.
- **Duplicados por SKU**: `Referencia de variante` es uniq=100 % en el archivo actual → no se esperan duplicados, pero el importer debe abortar batch si los detecta.

### 4.4 Defaults
- `brand` default `'MT'`.
- `family` default `'unclassified'` cuando no hay match con catálogo derivado y no se puede inferir.
- `data_quality` default `'partial'`; promover a `'complete'` sólo cuando `name_en`, `family`, `material`, `dn`, `pn`, ≥1 EAN y `weight_net_kg` están presentes.
- `active` default `true`.
- `manual_locked_fields` default `'{}'`.

### 4.5 Variantes (1 SKU = 1 row vs agrupación)
- Decisión recomendada Fase 1: **1 SKU = 1 fila en `products`** (5085 productos). No agrupar variantes en padre/hijo en Fase 1; agrupación queda para Fase 2 (comparador).
- Las 1173 colisiones de `Nombre ERP - AX` se diferencian por dimensiones/medida/material → la cardinalidad de SKU es la correcta.

---

## Task 5 — Estrategia del importer (Fase 1a, UC-1a-05)

Pipeline en 6 etapas, ejecutado dentro de un `import_run` con `preview JSONB`:

1. **Pre-validation**
   - Verificar nombre/extensión `.xlsx`, sheet `sheet1`, headers exactos (orden + texto literal). Si falta cualquiera, abortar y reportar diff.
   - Conteo de filas razonable (>4500, <6000) para detectar archivos truncados.

2. **Row-by-row validation** (modo `--dry-run`)
   - Aplicar casts, validaciones (4.3), parsing (4.2). Recolectar `errors[]`, `warnings[]`, `skipped[]` por fila.
   - Joins lookup contra catálogo derivado (`Código` → `Sección`/`Categoría`/`Material`).

3. **Diff preview**
   - Comparar contra `products` actual:
     - **NEW**: SKU no existe en BD.
     - **CHANGED**: SKU existe pero ≥1 campo difiere (excluyendo `manual_locked_fields`).
     - **UNCHANGED**: idénticos.
     - **MISSING**: SKU en BD pero no en archivo (no eliminar; sólo flaguear `active=false` candidato).
   - Persistir summary en `import_runs.preview JSONB` (counts + 50 ejemplos de cada bucket).

4. **Batch FX as-of stamping** — N/A en este importer (no toca `costs`/`prices`). Saltar etapa.

5. **Apply** (modo `--commit`)
   - `UPSERT` por `sku`: respetar `manual_locked_fields` (no sobreescribir esos campos).
   - Triggers `audit_products` registran cada cambio en `audit_events`.
   - `product_eans` se reconcilia con DELETE+INSERT por `(sku, ean_type)`.
   - Transacción única; rollback si falla cualquier fila tras apply (después de pasar dry-run).

6. **Post-validation**
   - Conteo: `products WHERE updated_at >= run.start_at` debe matchear filas aplicadas.
   - Reconciliación: % SKUs con `data_quality='complete'`, % con EAN individual, % sin `name_en`.
   - Generar `reconciliation_report.json` y subirlo como artefacto del run.

**Modos**: `--dry-run` (default), `--commit`, `--fail-on-warning`.

---

## Task 6 — Cross-validation con `catalogo_mt_productos.xlsx`

### 6.1 Inventario rápido

| Col | Header        | Cardinalidad | Sample                                  | Uso schema                             |
|-----|---------------|--------------|-----------------------------------------|----------------------------------------|
| 0   | `Sección`     | 7 enums      | `Válvulas y Filtros`                    | → `family` (vocabulario controlado)    |
| 1   | `Material`    | 9 enums      | `Latón`                                 | → `material` (con normalización ES→EN: Latón→brass) |
| 2   | `Categoría`   | 53 enums     | `THREADED BALL VALVES`                  | → `subfamily` o `type`                 |
| 3   | `Código`      | 3863 uniq    | `4504015`                               | JOIN key = `products.sku`              |
| 4   | `Medida`      | 1613 uniq    | `1/2`, `3/4`, `1 1/4`                   | → `dn` / `connection` parseado         |
| 5   | `Página`      | 154 uniq     | `12`                                    | → `specs->>'catalog_page'` (referencia ficha PDF) |

### 6.2 Reglas de unión y reporte de huérfanos (medido)

- **Regla**: `catalogo.Código` (TRIM) `==` `pim.Referencia de variante` (TRIM). Confirmado: ambas son tipo texto, sin zero-pad relevante en catálogo.
- **Cifras reales medidas**:
  - `PIM ∩ Catálogo` = **3178 SKUs** (productos enriquecibles).
  - `PIM only` = **1907 SKUs** (sin sección/material/categoría → quedan en `data_quality='partial'`, requieren parser o captura manual).
  - `Catálogo only` = **685 SKUs** (en catálogo PDF pero **no** en PIM completo → posibles obsoletos, descontinuados o nuevos sin haber entrado a AX). **Reporte de huérfanos a Comercial MT.**
- **Diferencia con PRD**: PRD/distillate dice catálogo 5086 vs PIM 4182; los conteos reales son **PIM 5085 vs Catálogo 4181 (3863 únicos por `Código`)**. Corregir distillate.
- Decisión: catálogo derivado **complementa** al PIM (no lo reemplaza). El PIM es el source of truth de identidad; el catálogo aporta clasificación.

---

## Task 7 — Cross-validation con `Compatibilidad de Materiales MT V4`

### 7.1 Estructura medida

- Sheet `Hoja1`, **657 filas físicas** (655 con dato + header + 1 vacía/footer), **19 columnas físicas** (14 lógicas; cols 14-18 = leyenda `A=Excelente`, `B=Buen Resultado`, `C=Ataque moderado`, `D=No Usar`, `*=Sin datos` y un link a tecno-products.com).
- Ancho lógico: `Producto`, `T (Cº)`, **11 materiales** (Latón, Acero al Carbono, Fundición de hierro GG25/GGG40/GGG50, A304/A304L, A316/A316L, EPDM, NBR, FKM/Vitón, PTFE, RPTFE+15%FG, RPTFE+15%Graphite). Total 13 columnas + leyenda → coincide con "14 cols" del PRD si se incluye una columna espaciadora.
- **650 productos químicos únicos** (NO son SKUs MT, son fluidos: `Aceite Crudo`, `Aceite de Castor`, `Aceite de Coco`...). 5 productos repiten con T °C distinta.
- Valores celda: enums {`A`, `B`, `C`, `D`, `*`} (con espacios trailing — limpiar).
- T °C: int o `*` (sin dato) o `None`.

### 7.2 Modelo destino (Fase 1)

```sql
CREATE TABLE material_compatibilities (
  id              BIGSERIAL PRIMARY KEY,
  fluid           TEXT NOT NULL,                   -- ex: 'Aceite Crudo'
  temperature_c   INT,                              -- nullable
  laton           compat_t,
  acero_carbono   compat_t,
  fundicion       compat_t,
  ss304           compat_t,
  ss316           compat_t,
  epdm            compat_t,
  nbr             compat_t,
  fkm             compat_t,
  ptfe            compat_t,
  rptfe_fg15      compat_t,
  rptfe_gr15      compat_t,
  source_row      INT,
  source_file     TEXT NOT NULL DEFAULT 'Copia de Compatibilidad de Materiales MT V4.xlsx',
  imported_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TYPE compat_t AS ENUM ('A','B','C','D','SIN_DATO');
CREATE INDEX idx_compat_fluid ON material_compatibilities(fluid);
```

### 7.3 Relación con SKUs del PIM

- **No hay clave directa**. El producto en la matriz es el **fluido transportado**, no el SKU MT.
- En Fase 1, la tabla se carga independiente y se expone read-only en la ficha de producto: dado un SKU MT con `material='ss316'`, mostrar todas las filas de `material_compatibilities` con celda `ss316='A'` o `'B'` agrupadas por fluido.
- En Fase 2 (grafo) se traduce a edges `material → fluid → grade(A/B/C/D)` para el motor de matching y "deal breakers" (T máx, incompatibilidad química).

---

## Task 8 — Recomendaciones para Sprint 0

### 8.1 Cambios necesarios al schema `products`

Agregar (vía migración Sprint 0/1a):

```sql
ALTER TABLE products
  ADD COLUMN intrastat_code   TEXT,                                              -- Task 2 col 1
  ADD COLUMN erp_name         TEXT,                                              -- Task 2 col 2 (legacy reference)
  ADD COLUMN weight_net_kg    NUMERIC(10,4),                                     -- col 5
  ADD COLUMN weight_gross_kg  NUMERIC(10,4),                                     -- col 4 (TODO confirmar)
  ADD COLUMN dimensions       JSONB NOT NULL DEFAULT '{}'::jsonb,                -- cols 6-8
  ADD COLUMN packaging        JSONB NOT NULL DEFAULT '{}'::jsonb;                -- cols 10-13, 15, 16

CREATE INDEX idx_products_intrastat ON products(intrastat_code);
CREATE INDEX idx_products_dimensions_gin ON products USING gin(dimensions);
CREATE INDEX idx_products_packaging_gin ON products USING gin(packaging);
```

Y la tabla nueva `product_eans` (DDL en Task 2).

### 8.2 Variantes
- **Recomendación**: 1 SKU = 1 fila en `products`. La diferencia 5085 PIM vs 4182 catálogo se explica por: (a) 3178 intersección, (b) 1907 SKUs en PIM sin entrada en catálogo (variantes de medida, accesorios), (c) 685 huérfanos en catálogo. **No** hay evidencia de necesitar tabla `product_variants` en Fase 1.

### 8.3 Multi-idioma faltante
- `name_es`: orden de fallback → (1) `stock_dubai_v23 PIM IDIOMAS` si existe; (2) catálogo derivado (`Categoría` + `Medida`) traducido por regla; (3) batch LLM con HITL en cola separada.
- `name_ar`: asumir vacío en Sprint 0; backfill LLM EN→AR con revisión nativa Fase 1.1. Marcar `translation_status='pending'` por defecto.

### 8.4 Specs técnicas estructuradas
- **Ruta híbrida** (recomendada):
  1. Parser regex sobre `erp_name` para extraer DN/PN/connection/material (alta precisión, baja cobertura — ~50 % esperado).
  2. JOIN con catálogo derivado para `family/material/type` (cobertura 62,5 % = 3178/5085).
  3. LLM tool-use sobre el resto (Claude con JSON schema validado).
  4. Captura manual para no-matches (cola de Comercial MT).
- OCR de catálogo PDF queda para Fase 1.5+ como mejora; no bloquea Sprint 1.

---

## Task 9 — Cuestiones abiertas para Comercial MT

1. ¿`weight unit` y `net weight unit` son siempre iguales? Si no, ¿cuál es bruto y cuál es neto?
2. ¿Las 908 filas sin `INDIVIDUAL EAN CODE` son SKUs no comercializados o pendientes de asignar?
3. ¿Las 1907 filas `PIM only` (sin entrada en catálogo derivado) están descontinuadas, son nuevas o variantes no catalogadas?
4. ¿Los 685 SKUs `Catálogo only` están descontinuados y deben darse de baja, o falta entrarlos al PIM AX?
5. Confirmar que `Referencia de variante` es **estable** — ¿se renombra alguna vez? ¿Hay historial de cambios de SKU?
6. ¿Existe un export `PIM IDIOMAS` (ES/AR) ya disponible o hay que pedir a IT España un dump?
7. ¿La marca es siempre `MT`? ¿Hay productos OEM revendidos con otra brand?
8. ¿Qué política seguir con SKUs en BD ausentes en el próximo PIM completo: marcar `active=false`, archivar, o dejar?
9. La matriz de compatibilidad `MT V4` está en español con materiales europeos (Latón CW604N etc.) — ¿se quiere mantener nomenclatura ES o normalizar a EN (`brass`, `ss316`)? Afecta la presentación en ficha y al matching Fase 2.
10. Las 22,2 % filas sin `Nombre ERP - AX`: ¿hay un descriptor alternativo en otro export (PIM España, ficha técnica) o quedan sin nombre EN?

---

## Decisiones cerradas en Sprint 0 (registrar como ADR si aplica)

- D-1: SKU canónico = `Referencia de variante` (string, conservar formato exacto).
- D-2: 1 SKU = 1 fila en `products` (no agrupación de variantes en Fase 1).
- D-3: Sumar al schema `intrastat_code`, `erp_name`, `weight_net_kg`, `weight_gross_kg`, `dimensions JSONB`, `packaging JSONB`.
- D-4: Crear tabla `product_eans` (3 tipos: individual, box, inner_box).
- D-5: Crear tabla `material_compatibilities` con 11 cols de material + fluid + temp; indep. de SKU.
- D-6: Convertir cm → mm en `packaging.box_*_mm` durante import.
- D-7: `name_en` se construye desde `erp_name` saneado en Sprint 1; HITL para los 1128 nulos.
- D-8: Diff preview persistido en `import_runs.preview JSONB` antes de cualquier `--commit`.
