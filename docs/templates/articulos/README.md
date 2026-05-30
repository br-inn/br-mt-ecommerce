# Plantilla estándar de carga de artículos (XSD)

Esta carpeta contiene la **plantilla estandarizada** para que los usuarios
completen la información de los artículos antes de subirlos al catálogo (PIM).

| Archivo | Para qué sirve |
|---------|----------------|
| `articulos.xsd` | Esquema XML (XSD) — define la estructura, los campos obligatorios/opcionales, los tipos y los valores permitidos (DN, PN, estados, etc.). Es el "contrato" de validación. |
| `articulos-ejemplo.xml` | Ejemplo rellenado. **Cópialo, renómbralo y reemplaza los valores.** Incluye un artículo completo (válvula de bola) y uno parcial. |

## Cómo usar la plantilla

1. **Copia** `articulos-ejemplo.xml` con un nombre nuevo, p. ej. `articulos-2026-06.xml`.
2. **Rellena** un bloque `<article>` por cada SKU. Borra los elementos opcionales
   que no apliques (no los dejes vacíos).
3. **Valida** el archivo contra el esquema antes de entregarlo (ver abajo).
4. Entrega el `.xml` validado al equipo / cárgalo por el flujo de importación.

## Guía de llenado paso a paso

Partiendo de `articulos-ejemplo.xml`, para cada artículo:

1. **`<sku>`** — el código del artículo (clave). Ej. `MT-V-038`. No se puede repetir en el lote.
2. **`<name_en>`** — nombre comercial **en inglés**. Obligatorio.
3. **`<family>`** — familia del producto en inglés (`ball_valve`, `filter`, …). Obligatorio.
4. **Clasificación** (opcional): `subfamily`, `type`, `series`, `brand` (por defecto `MT`).
5. **Datos técnicos transversales** (opcionales): `material`, `dn`, `pn`, `connection`,
   `size`, `temp_min_c`, `temp_max_c`, `pressure_max_bar`, `manufacturing_method`.
6. **Códigos**: `gtin` (EAN), `intrastat_code`, `erp_name`.
7. **Peso**: `weight` + `weight_unit` (`kg`/`g`/`lb`).
8. **Estado**: `lifecycle_status` (por defecto `active`), `revision`, `data_quality`
   (`partial` mientras falten datos; `complete` cuando la ficha esté cerrada).
9. **Bloques estructurados** (cada uno opcional — borra el bloque entero si no aplica):
   - `<dimensions>` — alto/ancho/fondo del producto en mm.
   - `<packaging>` — unidades por caja, medidas de caja, MOQ, unidades por palet.
   - `<specs>` — especificaciones técnicas de la familia (ver más abajo).
   - `<translations>` — traducciones a `es` y/o `ar`.
   - `<releases>` — precio y nombre local por mercado (`UAE`, `KSA`, …).
   - `<uom_conversions>` — equivalencias entre unidades (p. ej. `BOX → EA`).
   - `<bore_dimensions>` — dimensiones de bridas/caras por norma.

### Cómo rellenar `<specs>`

`<specs>` contiene los datos técnicos propios de la familia. La plantilla ya trae
los campos canónicos de **válvula de bola** (materiales, dimensiones `dim_*`, `kv`,
`torque_nm`, `actuator`, conexiones…). Para una familia distinta:

- Rellena solo los campos que apliquen y borra el resto.
- Para cualquier dato **no listado**, usa el bloque libre:

```xml
<extra>
  <field key="mesh_microns">500</field>
  <field key="surface_treatment">nickel_plated</field>
</extra>
```

La clave (`key`) debe ir en inglés y en `snake_case`.

### Referencia rápida de campos con valores cerrados

| Campo | Valores permitidos |
|-------|--------------------|
| `dn` | 8, 10, 15, 20, 25, 32, 40, 50, 65, 80, 100, 125, 150, 200, 250, 300 |
| `pn` | 6, 10, 16, 20, 25, 30, 40, 63, 100 |
| `weight_unit` | kg, g, lb |
| `data_quality` | complete, partial, blocked, migrated_demo |
| `lifecycle_status` | draft, in_review, active, deprecated, replaced, discontinued |
| `manufacturing_method` | forged, cast, machined, welded, molded, extruded, stamped, sintered |
| `actuator` (specs) | lever, handwheel, electric, pneumatic, hydraulic, gear, manual |
| `iso5211_face` (specs) | F03, F05, F07, F10, F12, F14, y pares F03/F05 … F12/F14 |
| `translation@lang` | es, ar |
| `release@market_code` | UAE, KSA, MX, ES, GLOBAL, US, EU |

> Cualquier valor fuera de estas listas hará **fallar la validación** contra el XSD.

## Reglas obligatorias

- **Campos obligatorios** en cada `<article>`: `sku`, `name_en`, `family`.
- **Todos los datos van en inglés** (nombre, descripción, materiales, specs…).
  La única excepción son las traducciones a español/árabe, que van dentro de
  `<translations>` con `lang="es"` o `lang="ar"`.
- **SKU**: mayúsculas, dígitos, guiones y guion bajo (3–64 caracteres). Único en el lote.
- **DN, PN, actuator, iso5211_face, weight_unit, lifecycle_status, data_quality,
  market_code**: sólo aceptan valores de las listas definidas en el XSD.
- **Specs por familia**: rellena los campos técnicos que apliquen. Para claves no
  listadas usa el bloque `<extra><field key="...">valor</field></extra>`.

## Cómo validar el XML contra el XSD

**Con xmllint** (Linux/Mac, o Git Bash en Windows):

```bash
xmllint --noout --schema articulos.xsd articulos-ejemplo.xml
# Salida esperada: "articulos-ejemplo.xml validates"
```

**Con Python** (multiplataforma, requiere `lxml`):

```bash
python -c "from lxml import etree; etree.XMLSchema(etree.parse('articulos.xsd')).assertValid(etree.parse('articulos-ejemplo.xml')); print('OK')"
```

## Origen de los campos (trazabilidad)

El esquema refleja el modelo real del backend:

- Escalares, identidad, lifecycle, traducciones, releases, conversiones UoM y
  dimensiones por norma → `mt-pricing-backend/app/schemas/products.py`.
- Specs técnicos por familia (válvula de bola) → `app/schemas/specs/valve_ball.json`.
- Claves JSONB de `dimensions` / `packaging` / `specs` → `app/services/importer/column_mapper.py`.

> Si el modelo del backend cambia (nuevas enumeraciones, campos o familias),
> regenerar/actualizar `articulos.xsd` para mantenerlo sincronizado.
