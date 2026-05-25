# Plan de arquitectura as-built — Compatibilidad y Variantes (sub-recurso CAT)

**Tipo**: RETROSPECTIVO — documenta el diseño ya implementado.

**Fecha**: 2026-05-25

**Dominio**: CAT — sub-recurso: Compatibilidad M:N y Display Pair

---

## Archivos fuente principales

| Archivo | Rol |
|---|---|
| `mt-pricing-backend/app/db/models/compatibility.py` | ORM `ProductCompatibility` — tabla `product_compatibility`. Restricciones DB, relaciones. |
| `mt-pricing-backend/app/db/models/product.py` | Campo `display_pair_sku` (self-FK), relaciones `compatibilities_outgoing/incoming`, `display_pair_rel`. |
| `mt-pricing-backend/app/repositories/compatibility.py` | `CompatibilityRepo` — queries y mutaciones sobre `product_compatibility`. Sincronización bidireccional `replaces/replaced_by`. |
| `mt-pricing-backend/app/services/compatibility/compatibility_service.py` | `CompatibilityService` — orquesta repo + validaciones + auditoría. Excepciones de dominio. |
| `mt-pricing-backend/app/services/compatibility/__init__.py` | Re-exports del módulo de compatibilidad. |
| `mt-pricing-backend/app/services/products/display_pair_service.py` | `DisplayPairService` — operaciones simétricas `set_pair`/`clear_pair` sobre `display_pair_sku`. |
| `mt-pricing-backend/app/services/products/effective_display_service.py` | `EffectiveDisplayService` — calcula unión dedup de tags + certs (serie defaults + product overrides). |
| `mt-pricing-backend/app/api/routes/products.py` | Endpoints REST de compatibilidad M:N montados en `/products/{sku}/compatibility*`. |
| `mt-pricing-backend/app/api/routes/products_display.py` | Endpoints REST de display pair y effective display montados en `/products/{sku}/`. |
| `mt-pricing-backend/app/api/routes/taxonomy_extras.py` | Endpoint `GET /vocabularies/series/{series_id}/spare-parts` (Fase 5 polimórfico). |
| `mt-pricing-backend/app/schemas/compatibility.py` | Schemas Pydantic: `CompatibilityKind`, `CompatibilityOwnerType`, `ProductCompatibilityCreate/Patch/Response`. |
| `mt-pricing-backend/app/schemas/products_display.py` | Schemas Pydantic: `EffectiveDisplayResponse`, `CertificationRef`, `DisplayPairSetRequest`. |

---

## Diseño de la compatibilidad M:N

### Tabla `product_compatibility`

La relación es **intencionalmente unidireccional**. Cada fila representa un enlace
`product_sku → kind → compatible_with_sku`. Los 5 tipos soportados son:

| kind | Semántica |
|---|---|
| `spare_part` | El origen es recambio del destino |
| `accessory` | El origen es accesorio del destino |
| `replaces` | El origen reemplaza al destino (bidireccional) |
| `replaced_by` | El origen es reemplazado por el destino (inverso automático) |
| `compatible_with` | Compatibilidad genérica |

### Sincronización replaces/replaced_by

El mapa `_INVERSE = {"replaces": "replaced_by", "replaced_by": "replaces"}` en
`CompatibilityRepo` gestiona la inserción y eliminación del par semántico. El repo
crea/elimina el inverso automáticamente en el mismo flush. El servicio delega
la sincronización al repo.

### Owner polimórfico (Fase 5)

Los campos `owner_type` (`product`|`variant`|`series`) + `dn_min`/`dn_max` permiten
vincular recambios a una **serie completa** con acotación de calibre. Cuando
`owner_type='series'`, el campo `product_sku` actúa como identificador de la serie.
El endpoint `GET /vocabularies/series/{series_id}/spare-parts` expone este filtro.

---

## Diseño del display pair

### Campo `products.display_pair_sku`

Self-FK nullable en la tabla `products`. Define un emparejamiento **1:1 simétrico**
entre dos SKUs (color siblings). La relación `display_pair_rel` en el ORM es
`lazy="raise"` (previene lazy-SQL accidental).

### `DisplayPairService`

Gestiona dos operaciones:

- `set_pair(a, b)`: dentro de una sola transacción, limpia parejas previas de
  ambos lados si difieren del nuevo emparejamiento, luego actualiza ambos SKUs.
- `clear_pair(sku)`: nullifica ambos lados. Idempotente si no hay pareja activa.

El servicio NO emite auditoría (no importa `AuditRepository`).

---

## Diseño del effective display

### `EffectiveDisplayService.compute(sku)`

Calcula la unión efectiva de tags y certificaciones para un SKU:

```
tags = series.features_tags (products.tags eliminado mig. 065)

certifications = dedup_by_code(
    product_certifications (overrides — mayor precedencia),
    series.series_certifications (defaults — complementan)
)
```

La deduplicación prioriza overrides del producto (se procesan primero). Las certs
de serie sólo se añaden si su `code` no aparece ya en los overrides.

### Queries en `EffectiveDisplayService`

1. `SELECT product WHERE sku = ?` (para obtener `series_id`).
2. `SELECT product_certifications WHERE product_sku = ?` con `selectinload(certification)`.
3. `SELECT series WHERE id = ? WITH selectinload(series_certifications.certification)`
   (sólo si `product.series_id IS NOT NULL`).

**Total**: 2-3 queries fijas, sin N+1.

---

## Decisiones clave de diseño

### 1. Por qué `display_pair` es 1:1 y no M:N

Los casos de uso son exclusivamente pares binarios de color. Un modelo de válvula
tiene exactamente un color-sibling (rojo ↔ azul). El campo escalar `display_pair_sku`
simplifica las queries de detalle y el JOIN en `_build_product_detail`.

### 2. Por qué la compatibilidad es unidireccional con sólo un inverso automático

El modelo unidireccional evita inconsistencias por fila duplicada (si A es
`spare_part` de B, la vista inversa se consulta; no necesita fila adicional).
La excepción `replaces`/`replaced_by` es semántica: el negocio espera que al
declarar una sustitución, ambas partes la vean de forma inmediata.

### 3. Por qué `effective-display` hace 3 queries en vez de 1 JOIN

El servicio nació como utility separado del flujo principal de `_build_product_detail`.
Usar `selectinload` en lugar de `joinedload` fue apropiado dado que `product_certifications`
es una colección (N filas). El coste es fijo: 2-3 queries sin N+1, cumpliendo Art. 2
de la constitución de arquitectura.

### 4. Error handling: `_raise_compat` vs `_raise_domain`

Los endpoints de compatibilidad en `products.py` usan `_raise_compat` que produce
un dict con `{type, title, status, code}` — más cercano a RFC 7807 que `_raise_domain`.
Los endpoints de display en `products_display.py` usan su propio `_raise_domain` local
que usa `ProblemDetails.model_dump()` — también RFC 7807.

---

## Tests automatizados

| Archivo | Cubre |
|---|---|
| `tests/unit/api/test_compatibility_api.py` | 13 escenarios de los endpoints HTTP de compatibilidad (sin DB). |
| `tests/unit/services/compatibility/test_compatibility_service.py` | Lógica del servicio: validaciones, auditoría, replace_all. |
| `tests/unit/schemas/test_compatibility.py` | Validación Pydantic de schemas. |
| `tests/unit/services/products/test_display_pair_sync.py` | `DisplayPairService`: set_pair, clear_pair, idempotencia. |
| `tests/unit/services/products/test_effective_display.py` | `EffectiveDisplayService`: union dedup de tags y certs. |
| `tests/unit/api/test_products_api_stage3.py` | Endpoints display pair y effective display (sin DB). |
