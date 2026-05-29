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
