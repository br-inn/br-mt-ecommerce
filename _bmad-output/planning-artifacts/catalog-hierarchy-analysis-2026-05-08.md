# Análisis de jerarquía de catálogo — Hidrosanitario + Industrial

**Fecha**: 2026-05-08 · **Autor**: psierra + Claude · **Estado**: propuesta para review

> Replanteo de la jerarquía de artículos a partir de los índices impresos de las divisiones **Hidrosanitario** e **Industrial**. Compara con el modelo actual (Stage 1 Opción C, mig. 042) y propone los siguientes pasos.

---

## 1. Lo que muestran las imágenes

### Catálogo Hidrosanitario (índice impreso)

| Nivel visual | Valores observados |
|---|---|
| Sección comercial | Válvulas y filtros · Accesorios y bridas · Automatización de válvulas · Conexiones flexibles · Instrumentos de medición · Accesorios sanitarios · Recambios · Condiciones de venta · Índice de referencias |
| Material (agrupador) | Latón · Acero inoxidable · Fundición · Plástico/PVC · Galvanizado · PPR |
| Tipo funcional | Válvulas esfera · Válvulas retención · Válvulas compuerta · Válvulas escuadra · Válvulas seguridad · Grifos jardín · Grifos lavadora · Reductoras presión · Filtros · Desfangador · Manguitos elásticos … |
| Variante de tipo | Válvula esfera de roscar · de soldar · de empotrar · multicapa · mini |
| Línea / serie comercial | Serie 641 Multicapa compresión · Serie 642 prensar universal · Serie 647 prensar U/RFz · Serie 651 Pex · Serie 87 Roscado · Serie 871 Roscado cromado · Serie 86 Tubería Cu · Serie 88/89/98/99 PE · Serie 66/67 Bicono · MT Garden · Sistema MT Press |

### Catálogo Industrial (índice impreso)

| Nivel visual | Valores observados |
|---|---|
| Sección comercial | Válvulas y filtros · Accesorios y bridas · Automatización de válvulas · Instrumentos de medición · Recambios |
| Material (agrupador) | Acero inoxidable · Latón · Fundición |
| Tipo funcional | Válvulas esfera · Grifos · Válvulas retención · Válvulas compuerta · Filtros · Válvulas mariposa · Válvulas globo · Manguitos elásticos · Bridas · Abarcones · Soldados |
| Línea / serie comercial | Sistema MT Press · Serie 8 Roscado |

### Diferencias clave entre las dos divisiones

- Las **mismas secciones** ("Válvulas y filtros", "Accesorios y bridas", …) aparecen en ambas, pero con productos distintos (PN, calidad, certificaciones).
- Hay líneas exclusivas (MT Garden → solo Hidro; Industrial → tipologías heavy-duty).
- Algunos sistemas (MT Press) viven en ambas divisiones con SKUs diferenciados.

### Anatomía de una página de producto real

Las páginas detalladas (Industrial 1.1 Acero Inoxidable, Hidrosanitario Latón Válvulas Esfera) muestran un nivel **entre Subfamily y SKU** que el índice no exponía: la **serie comercial** opera como bloque visual con identidad propia.

**Estructura top-down de una página**:

| Nivel visual | Contenido | Mapping al modelo |
|---|---|---|
| Strip de cabecera | `MT INDUSTRIAL` · `1 VÁLVULAS Y FILTROS` · `1.1 ACERO INOXIDABLE` | brand · family · material |
| Subsection title | `VÁLVULAS ESFERA / BALL VALVES` + bullets es/en | subfamily + translations |
| **Series banner** | `PN40 PLATINUM SERIES` · color identity · badges (`DZR`, `SINTEF`, `ACS`) · bullets compartidos (`Latón DZR CW602N · Sistema antihielo · Apta solar · Paso total …`) | **`series` (entidad rica nueva)** |
| Parent model row | Código `4104` · nombre largo es/en · descripción técnica · imagen · tags (`PLATINUM ǀ NOFROST ǀ EAN`, `DZR ǀ SINTEF ǀ ACS`) | products(is_parent=true) |
| Variants table | `4104015 ǀ 1/2" ǀ 48 ǀ 12 ǀ PVP` … | products(is_variant=true, parent_sku=4104) |

**Hallazgos clave de las páginas reales**:

1. **`series` no es solo un agrupador** — es entidad de marketing con: tier nominal (`PLATINUM`, `GOLD`, …), pressure_rating (`PN40`, `PN30`), color identity, badges de certificación default, bullets de spec compartidos por todos los parent models de la serie.

2. **Variant matrix multi-eje**:
   - **Eje obligatorio: tamaño** (`1/4"` → `4"`) — sufijo numérico en el código (4104**015**, 4104**020**, …). Coincide con `parent_sku` / `is_variant` (Wave 2/5).
   - **Eje opcional: color de maneta** (rojo/azul) — produce **parejas de parent models** con códigos distintos (4295 ↔ 42952, 09102 ↔ 0910). NO es padre/hijo, es **display pair**.
   - **Eje opcional: tipo de conexión** (H-H / M-H / M-M) — suele ser un parent model distinto dentro de la misma serie (4104 vs 4504), no variant.

3. **Material aparece en breadcrumb (1.1, 1.2, 1.3)**, NO como sección visual independiente con contenido propio. Confirma Material como **grupo de presentación**, render con `GROUP BY material`.

4. **Tags visuales son derivables**, no propios del SKU:
   - Badges de cert → `product_certifications` (M:N) o `series.default_certifications`.
   - Tags como `PLATINUM`, `NOFROST`, `EAN_CODE` → atributos heredados de la serie. No persistir en cada SKU si son redundantes.

5. **Codes encoden semántica** — prefijos numéricos identifican modelo / serie:
   - `0909` (1-piece reduced bore) ≠ `0910` (2-piece full bore blue) ≠ `09102` (2-piece full bore red)
   - `4104` (PN40 Platinum H-H) ≠ `4504` (PN40 Platinum M-H)
   - `4295` (PN30 Gold red) ↔ `42952` (PN30 Gold blue)
   - El SKU canónico se mantiene como TEXT; no derivar lógica de queries del prefijo.

---

## 2. Modelo actual (lo que ya hay en BD)

Tras el master plan de Catalog Modeling (Wave 1–10) + Stage 1 Opción C (mig. 042):

```
Brand   ────────────────────────────────────  (orthogonal)
                                                                                    
Family  ──→  Subfamily  ──→  ProductType  ──→  Product (SKU)
                                                    │
                                                    ├─ specs (JSONB validado por JSON Schema por family/subfamily — mig. 043)
                                                    ├─ product_materials (1:N por componente)
                                                    ├─ product_connections (1:N puertos)
                                                    ├─ product_assets (10 kinds)
                                                    ├─ product_certifications (M:N)
                                                    ├─ product_applications (M:N)
                                                    ├─ product_compatibility (M:N spare parts)
                                                    ├─ product_tech_tables (1:N P/T, materials matrix, dim by DN)
                                                    └─ series (TEXT escalar — sin tabla)
```

Atributos transversales escalares ya en `products`: `brand`, `family`, `subfamily`, `type`, `material`, `dn`, `pn`, `connection`, `series`, `lifecycle_status`, `is_parent`, `is_variant`, `parent_sku`, `tags[]`.

FKs `brand_id`, `family_id`, `subfamily_id`, `type_id` añadidas como **nullable** en mig. 042 — se promoverán a NOT NULL en Stage 2 cuando los consumidores estén migrados.

---

## 3. Gap analysis — qué falta para representar los catálogos

| Dimensión del catálogo papel | ¿Modelada hoy? | Comentario |
|---|---|---|
| **División** (Hidrosanitario / Industrial) | ❌ No existe | Es la dimensión que falta. Determina canal, audiencia, presentación, y qué SKUs aparecen en qué catálogo PDF. |
| Sección comercial (Válvulas y filtros, Accesorios y bridas, …) | ✅ → `Family` | Mapping directo; revisar nomenclatura de seeds. |
| Material agrupador (Latón / Inox / Fundición / PVC / Galvanizado / PPR) | ⚠️ Parcial | Hoy `material` es TEXT libre + `product_materials` por componente. No hay vocabulario curado de materiales agrupador. |
| Tipo funcional (Válvulas esfera, Filtros, Bridas, …) | ✅ → `Subfamily` | OK. |
| Variante de tipo (de roscar / de soldar / de empotrar / multicapa) | ✅ → `ProductType` | OK. |
| Serie / sistema comercial (Serie 641, MT Press, MT Garden) | ⚠️ Solo TEXT | Existe `products.series` como string. Falta tabla `series` con metadata (nombre largo, descripción, hero image, sort_order, division a la que pertenece). |
| Brand | ✅ → `Brand` | OK. |
| Aplicaciones / certificaciones | ✅ → `applications`, `certifications` (M:N) | OK. |

---

## 4. Decisión central — ¿División es taxonomía o eje ortogonal?

**Recomendación: eje ortogonal (M:N), no quinto nivel taxonómico.**

Razones:

1. **El mismo SKU puede aparecer en ambas divisiones** (ej. ciertas válvulas de inox roscadas se ofrecen en Hidro e Industrial). Si División fuese padre de Family, habría que duplicar el árbol → product duplicado o productos diferentes con el mismo nombre.
2. **División es canal/audiencia**, no propiedad técnica. Conceptualmente paralelo a "marketplaces donde se publica" o "segmentos comerciales". Encaja como tabla `divisions` + junction `product_divisions` (M:N).
3. **Mantiene Family/Subfamily/ProductType estables** — la taxonomía técnica no se infla con cambios de canal.
4. **Permite filtrado eficiente**: `WHERE EXISTS (SELECT 1 FROM product_divisions WHERE sku=p.sku AND division_code='industrial')`.
5. **Cataloga PDF generado** — al render del catálogo Industrial, hago `JOIN product_divisions ON code='industrial'` y produzco solo el subset; el árbol Family/Subfamily/Type se reordena igual en ambas divisiones.

Alternativa descartada: Division como columna NOT NULL en products → forzaría un SKU por canal → fragmenta el master, rompe stock, pricing y mediarteca.

---

## 5. Decisión secundaria — Material como eje

**Recomendación: vocabulario curado `materials` + atributo en `products` (NO nivel jerárquico).**

Razones:

1. En el catálogo papel Material aparece **entre** Sección y Tipo, pero esa es una decisión de **layout PDF**, no de taxonomía. Un mismo `product_type` ("Válvula esfera de roscar") existe en latón **y** en inox: si Material fuese nivel de árbol, duplicaría product_types o introduciría triplets `(family, material, type)` poco normalizados.
2. Material ya tiene representación granular en `product_materials` (por componente body / gaskets / stem / seats) con trigger denorm a `products.material`.
3. Lo que falta es **un vocabulario controlado** ('laton', 'acero_inoxidable_316', 'fundicion_gjl_250', 'pvc_u', 'ppr', 'galvanizado'), aplicado al `material` principal usado para el agrupador del PDF.
4. **Render PDF**: `GROUP BY family, material, subfamily, product_type, series` reproduce el árbol del catálogo impreso sin estar atado a la BD.

---

## 6. Decisión terciaria — Series como tabla rica

**Recomendación: promover `series` (hoy TEXT) a tabla rica `series` con metadata de marketing, tier, y certificaciones default.**

Razones (refinadas tras ver páginas reales):

1. **Series tiene identidad comercial completa**: banner de color, tier nominal (PLATINUM, GOLD, SILVER, BRONZE), pressure rating, certificaciones default, bullets de spec compartidos.
2. **Series puede agrupar múltiples parent models** — PN40 Platinum incluye 4104 (H-H) y 4504 (M-H) bajo el mismo banner. Relación 1:N de series a products.
3. **Series pertenece a una o más divisiones** (MT Press → ambas; PN40 Platinum → solo Hidro): junction M:N `series_divisions`.
4. **Permite landing pages comerciales** (`/series/pn40-platinum`, `/series/mt-press`) y filtros tipo "muéstrame solo Gold tier".
5. **Backward compat**: `products.series` (TEXT) + `products.series_id` (FK nullable) durante transición, mismo patrón que mig. 042.

### Atributos propuestos de `series`

| Columna | Tipo | Notas |
|---|---|---|
| `code` | TEXT unique | `pn40_platinum`, `pn30_gold`, `mt_press`, `mt_garden`, `serie_641_multicapa` |
| `name_es`, `name_en` | TEXT | "PN40 Platinum Series", "Serie 641 Multicapa Compresión" |
| `tier_id` | FK → `series_tiers` | `platinum`, `gold`, `silver`, `bronze`, `n_a` |
| `pressure_rating_pn` | INT NULL | 40, 30, 16, 10 (bar) — facilita filtros y badges automáticos |
| `temperature_min_c`, `temperature_max_c` | INT NULL | shared specs |
| `banner_color` | TEXT | hex/token — usado por landing y catálogo PDF |
| `hero_image_url` | TEXT | imagen banner |
| `description_es`, `description_en` | TEXT | descripción larga marketing |
| `bullets_es`, `bullets_en` | TEXT[] | spec bullets compartidos por todos los parents |
| `features_tags` | TEXT[] | `nofrost`, `ean_code`, `solar_ready`, `reinforced_body` |
| `sort_order` | INT | orden en catálogo |
| `active` | BOOL | toggle |

### Junctions adicionales

- `series_divisions` (M:N) — qué series aparecen en qué catálogo PDF.
- `series_certifications` (M:N) — paquete default de certificaciones de la serie. Producto hereda; puede sobreescribir vía `product_certifications`.

### Vocab adicional

- `series_tiers` (catálogo cerrado): `platinum`, `gold`, `silver`, `bronze`, `n_a` — con `rank` numérico para ordenar y `display_color` para banner.

### Cómputo de tags visibles en una ficha de SKU

```
visible_tags  = series.features_tags ∪ product.tags
visible_certs = series.default_certifications ∪ product.certifications
```

Esto evita repetir `[DZR | SINTEF | ACS]` en cada SKU de la serie PN40 Platinum: lo declara una vez la serie y todos los SKUs heredan.

---

## 7. Modelo propuesto

```
                ┌─────────────┐
                │  divisions  │  hidrosanitario · industrial
                └──────┬──────┘
                       │ M:N (product_divisions, series_divisions)
                       │
Brand ──┐              │
        │              │
        ▼              ▼
   Family ──→ Subfamily ──→ ProductType ──→ Product (SKU)
                                                │
                                                ├─ series_id (FK nullable → series)
                                                ├─ material_id (FK nullable → materials)  ←── opcional
                                                ├─ specs JSONB
                                                ├─ product_materials (1:N componentes)
                                                ├─ product_connections (1:N)
                                                ├─ product_assets, certifications, applications, compatibility, tech_tables …
                                                └─ product_divisions (M:N → divisions)
```

### Tablas nuevas a añadir

| Tabla | Cardinalidad | Propósito |
|---|---|---|
| `divisions` | catálogo cerrado (2–4 filas) | hidrosanitario · industrial · ¿gas? · ¿solar? |
| `product_divisions` | M:N | product ↔ division |
| `series` | catálogo curado | MT Press, MT Garden, PN40 Platinum, PN30 Gold, Serie 641… (con tier, pressure_rating, hero, bullets, default certs) |
| `series_tiers` | vocab cerrado | platinum · gold · silver · bronze · n_a (con `rank` y `display_color`) |
| `series_divisions` | M:N | series ↔ divisions (qué series aparecen en qué catálogo) |
| `series_certifications` | M:N | paquete default de cert por serie |
| `materials` | catálogo curado (opt) | vocabulario controlado del agrupador material |
| `display_pairs` (opt) | 1:1 entre 2 parent SKUs | empareja modelos color rojo ↔ azul (4295 ↔ 42952) para render del catálogo |

### Cambios en `products`

- `series_id UUID NULL → series` (FK), coexiste con `series TEXT` durante transición (mismo patrón mig. 042).
- `material_id UUID NULL → materials` (FK), coexiste con `material TEXT`.
- `division_id` **NO** se añade — la relación va por la junction.

### Migrations sugeridas (Stage 3)

- `044_add_divisions_table.py` — `divisions` + `product_divisions` + seed (hidrosanitario, industrial).
- `045_add_series_table.py` — `series` + `series_divisions` + backfill desde `products.series` distinct.
- `046_add_materials_vocab.py` *(opt)* — `materials` + backfill desde `products.material` distinct.

---

## 8. Impacto en componentes existentes

| Componente | Cambio |
|---|---|
| `GET /products` | Acepta query `division=industrial` que filtra vía join. |
| `GET /products/facets` (Wave 10) | Añade facet **division** (count por código). Sigue computando family/subfamily/type/material igual. |
| FacetSidebar (Wave 10 FE) | Toggle "División" en la parte superior — cambia el subset visible globalmente; los demás facets se recomputan dentro de esa división. |
| Importer Daterium / mtspain.net | Mapper debe asignar `division` según fuente o categoría origen. Si el SKU ya existe, **añadir** la división (no sobrescribir), porque puede vivir en ambas. |
| Generador de catálogo PDF (futuro) | Plantilla por división. Query: `WHERE division_code = ? GROUP BY family, material, subfamily, product_type, series ORDER BY sort_order`. |
| Frontend `/catalogo` | Selector de división en header (o tabs). Hidrosanitario por defecto. Persistir en saved view. |
| `parent_sku` resolver (Wave 5) | Sin cambios — la herencia padre/variante es ortogonal a división. |

---

## 9. Plan de adopción sugerido

1. **Spike de validación** (1 día) — listar SKUs reales que aparecen en ambas divisiones; si <5 % del catálogo, simplifica el M:N a "default + override". Si >20 %, M:N obligatorio.
2. **Stage 3 — Wave 11** (2–3 días backend):
   - Mig. 044 `divisions` + `product_divisions`.
   - Mig. 045 `series` + `series_divisions` + backfill.
   - Mig. 046 `materials` (si se decide vocabulario curado).
   - Endpoints CRUD `/admin/divisions`, `/admin/series`, `/admin/materials`.
   - Extender `/products/facets` con dimensión `division`.
3. **Wave 12 frontend** (2 días):
   - Selector de división en header.
   - Páginas de Series (`/series/mt-press`).
   - Filtro material como facet curado.
4. **Wave 13 importer** (1–2 días):
   - Mapper Daterium → asignar division por categoría origen.
   - Importer reusa SKUs y añade divisiones en lugar de duplicar.
5. **Wave 14 generador catálogo PDF** (sprint dedicado, post Sprint 11) — out of scope del replanteo, pero el modelo lo soporta sin cambios.

---

## 10. Preguntas abiertas para alineación

1. **¿Hay más divisiones futuras** (Gas, Solar, Riego)? Si sí, modelar como tabla compensa más que un enum.
2. **Material como vocabulario curado vs TEXT libre** — depende de cuántos materiales distintos tiene el catálogo Daterium real. Si <30, vocabulario curado; si >100 con variantes (316L, 304, 304L, dúplex…), mantener TEXT con sugerencias.
3. **¿"Recambios" (Hidro index pos. 196) es Family o atributo?** Hoy hay `product_compatibility` para spare parts. Si "Recambios" es solo un view del catálogo papel filtrado por `is_spare_part=true`, no necesita Family. Si tiene productos no-spare en esa sección, es Family aparte.
4. **Sistema MT Press en ambas divisiones** — ¿son los mismos SKUs (caso M:N puro) o hay líneas distintas Hidro vs Industrial (Hidro=tubo cobre Inox AISI304, Industrial=AISI316L)? Define el tamaño real del solapamiento.
5. **Sort order del catálogo PDF** — ¿lo mantenemos en la tabla `families.sort_order` (ya existe) o necesitamos `division_sort_order` por si Hidro e Industrial ordenan distinto?
6. **Pares de color (4295 ↔ 42952, 09102 ↔ 0910)** — ¿cómo modelarlos?
   - **Opción A** (recomendada): dos parent SKUs separados con FK opcional `display_pair_sku` que los empareja para el render del catálogo. Preserva el código MT canónico (4295 ≠ 42952). BD simple.
   - **Opción B**: un parent virtual + `variant_attributes JSONB` que combine size×color en cada SKU hijo. Más limpio para filtros pero rompe trazabilidad del código de catálogo.
7. **Conexión H-H / M-H / M-M** — ¿variant axis o parent distinto?
   - Las páginas reales muestran **parents distintos** (4104 vs 4504 son rows separados con su propia descripción y tabla de tamaños).
   - Recomendación: `connection_kind` queda como atributo del parent product (texto/enum). Wave 5 ya lo soporta así sin cambios.
8. **Tier (PLATINUM / GOLD / SILVER / BRONZE)** — ¿enum, vocab o atributo libre?
   - Catálogo MT usa al menos 2 tiers visibles (PLATINUM rojo, GOLD dorado). Vocabulario cerrado en tabla `series_tiers` con `rank` (1=Platinum, 2=Gold, …) y `display_color` para banner.
9. **Tags inheritance** — ¿guardar `tags[]` de marketing en cada SKU o computar en runtime desde la serie?
   - Recomendación: serie publica `features_tags` y SKU mantiene `tags[]` solo para overrides. UI hace `series.features_tags ∪ product.tags`. Ahorra storage y evita drift.
10. **Bullets es/en de la serie** — ¿guardar como `TEXT[]` en `series` o como filas de `series_translations`?
    - Si traducciones se usan ya en `product_translations`, mejor reutilizar el patrón con tabla `series_translations(series_id, lang, bullets[], description, name)` para consistencia.

---

## 11. Resumen de la propuesta

- **Mantener** family → subfamily → product_type como columna vertebral técnica (ya hecho en Stage 1).
- **Mantener** parent_sku/is_variant para variants por tamaño (ya hecho en Wave 2/5).
- **Añadir** `divisions` como eje ortogonal M:N (resuelve Hidrosanitario vs Industrial sin duplicar SKUs).
- **Promover** `series` a tabla **rica** con tier (PLATINUM/GOLD/…), pressure_rating, banner, bullets, certs default y junctions a divisions y certifications.
- **Añadir** `display_pair_sku` opcional para empares de color (4295 ↔ 42952).
- **Curar** vocabulario `materials` (opt, basado en spike Daterium) y `series_tiers` (cerrado).
- **No** modelar Material como nivel jerárquico — es agrupador visual del PDF, render con `GROUP BY`.
- **No** modelar División como columna de products — un SKU puede vivir en varias.
- **No** modelar conexión H-H/M-H/M-M como variant axis — son parent models distintos en el catálogo (4104 vs 4504).

Resultado: el modelo refleja la realidad comercial (un master de SKUs, dos catálogos PDF, series ricas con identidad de marketing, variants por tamaño y display pairs por color) sin fragmentarse en jerarquías paralelas ni duplicar atributos heredables.
