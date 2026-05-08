# Specs JSON Schemas

This directory contains JSON Schema (Draft 2020-12) files that govern the
`products.specs` JSONB column for each product family/subfamily.

## File naming convention

| Pattern | Matches |
|---------|---------|
| `{family}_{subfamily}.json` | Exact family + subfamily (e.g. `valve_ball.json`) |
| `{family}.json` | All subfamilies of a family without a specific file (e.g. `filter.json`) |
| `_default.json` | Catch-all for families without any specific schema |

The `SpecsRegistry` applies the following fallback chain at runtime:

```
{family}_{subfamily} → {family} → _default
```

## How to add a new family schema

1. Create `{family}.json` (or `{family}_{subfamily}.json`) in this directory.
2. Start from the template below.
3. Set `additionalProperties: false` for strict schemas; `true` for permissive ones.
4. Add required fields to the `required` array.
5. Include `title` and `description` on every property — these are used by the
   frontend to auto-render field labels and tooltips.
6. No code changes needed — `SpecsRegistry` discovers files automatically on startup.

### Template

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://mtme-api/schemas/specs/v1/{family}_{subfamily}",
  "title": "My Family Specs",
  "description": "Technical specifications for {family}/{subfamily} products.",
  "type": "object",
  "required": ["dn", "dn_real", "size"],
  "properties": {
    "dn": {
      "type": "string",
      "title": "DN (Nominal Diameter)",
      "description": "Nominal diameter — e.g. DN25",
      "minLength": 1,
      "maxLength": 16
    }
  },
  "additionalProperties": false
}
```

## Schema versioning policy

- The `$id` URI includes `v1/` — e.g. `https://mtme-api/schemas/specs/v1/valve_ball`.
- Breaking changes (removing required fields, narrowing enums) require a new
  version: rename the file to `valve_ball_v2.json` and update the `$id`.
- Additive changes (new optional properties, widening enums) are backwards
  compatible and do not require a version bump.

## Current schemas

| File | Family | Subfamily | Required fields |
|------|--------|-----------|-----------------|
| `_default.json` | any | any | — (catch-all, permissive) |
| `valve_ball.json` | `valve` | `ball` | dn, dn_real, size, materials_body, materials_closure, materials_seats, materials_gaskets |
| `filter.json` | `filter` | — | dn, dn_real, size, materials_body, materials_screen, materials_gaskets |

## Field name mapping (Spanish → English snake_case)

| Excel label | JSON key |
|-------------|----------|
| Materiales Cuerpo | `materials_body` |
| Material Cierre | `materials_closure` |
| Materiales Asientos | `materials_seats` |
| Materiales Tamiz | `materials_screen` |
| Materiales Juntas | `materials_gaskets` |
| Dimensión L | `dim_L` |
| Dimension H | `dim_H` |
| Dimensión H1 | `dim_H1` |
| Dimension W | `dim_W` |
| Dimensión T1/T2/T3 | `dim_T1`, `dim_T2`, `dim_T3` |
| Dimensión S | `dim_S` |
| Dimensión h | `dim_h` |
| Dimensión ISO 5211 | `iso5211_face` |
| Dimensión SCH | `dim_SCH` |
| Dimensión D | `dim_D` |
| Dimensión K | `dim_K` |
| DN real | `dn_real` |
| Kv / Kv1 / Kv2 | `kv` / `kv1` / `kv2` |
| Torque | `torque_nm` |
| Accionador | `actuator` |
| Conexión 1/2/3 | `connections[]` array |
| Dimensión w1/d1/w2/d2 (filter) | `dim_w1`, `dim_d1`, `dim_w2`, `dim_d2` |
