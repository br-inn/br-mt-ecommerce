# Stage 4 — FK NOT NULL audit + plan

**Fecha**: 2026-05-09 · **Estado**: planificación (NO ejecutar todavía)

> Stage 1 (mig. 042) creó las FKs `brand_id`, `family_id`, `subfamily_id`, `type_id` como **nullable durante la transición**. Stage 3 (migs. 044/045/046) añadió `series_id`, `material_id`, `display_pair_sku` también nullable. Stage 4 promueve a `NOT NULL` aquellas que tengan cobertura suficiente y deja el resto NULLABLE con justificación.

---

## 1. Estado actual de cobertura (snapshot 2026-05-09, 5,085 productos)

| Columna | NULLs | % NULL | Decisión Stage 4 | Notas |
|---|---:|---:|---|---|
| `brand_id` | 0 | 0.00% | **NOT NULL** | Backfill mig. 042 cubrió 100%. |
| `family_id` | 0 | 0.00% | **NOT NULL** | Backfill mig. 042 cubrió 100% (18 valores únicos). |
| `subfamily_id` | 5,084 | 99.98% | **dejar NULLABLE** | Subfamily TEXT estaba vacío en 5085 SKUs; sólo el SKU demo tiene subfamily. Requiere clasificación masiva (Sprint 11+). |
| `type_id` | 5,084 | 99.98% | **dejar NULLABLE** | Idem subfamily. |
| `material_id` | 1,680 | 33.04% | **dejar NULLABLE** | 33% de SKUs sin material. Forzar NOT NULL bloquea inserciones. Promover a NOT NULL solo cuando importer + classifier alcancen ≥99%. |
| `series_id` | 5,084 | 99.98% | **dejar NULLABLE** | Series es opt-in marketing (no todos los SKUs pertenecen a una serie comercial). NULL es válido a largo plazo. |
| `display_pair_sku` | ~5,085 | 100% | **NULLABLE permanente** | Pares de color son la excepción (~10% del catálogo según muestra del catálogo papel). NO promover. |
| `divisions (M:N)` | 5,085 productos sin link | 100% | **dejar opcional** | Importer asignará automáticamente vía PIM_DEFAULT_DIVISIONS o per-run override. NO se enforce vía constraint (no hay NOT NULL en M:N). |

---

## 2. Plan de promoción a NOT NULL

### 2.1. Stage 4a — promover ahora (mig. 048)

**Promover**: `brand_id`, `family_id`.

```sql
ALTER TABLE products
  ALTER COLUMN brand_id SET NOT NULL,
  ALTER COLUMN family_id SET NOT NULL;

-- Eliminar columnas TEXT escalares deprecadas (Stage 1 transición).
-- ⚠ COORDINAR con consumidores: importer, FE list, audit, search.
-- ALTER TABLE products DROP COLUMN brand;        -- ❌ aún usada por list/filter
-- ALTER TABLE products DROP COLUMN family;       -- ❌ aún usada por facets / filtros
```

**Pre-requisitos**:
- ✅ Cobertura 100% verificada.
- ⚠ Auditar consumidores que `INSERT` filas de products: importer (`pim_importer.py`), wizard (`product_service.create`), tests fixtures.
- ⚠ Confirmar que ningún path usa `brand_id=NULL` por accidente. Hoy `ProductCreate.brand_id` no existe en schema (solo `brand: str | None`).

**Migración requerida** (`20260510_048_fk_not_null_brand_family.py`):
```python
def upgrade() -> None:
    # Defensive backfill — fail-fast si quedan NULLs después de mig. 042.
    op.execute("""
        SELECT count(*) AS n FROM products WHERE brand_id IS NULL OR family_id IS NULL;
    """)
    op.alter_column("products", "brand_id", nullable=False)
    op.alter_column("products", "family_id", nullable=False)
```

### 2.2. Stage 4b — diferido (mig. 049, post Sprint 12)

**Promover** después de clasificación masiva: `subfamily_id`, `type_id`, `material_id`.

**Pre-requisitos**:
- Importer Daterium / mtspain conectado y mapeando family→subfamily→type.
- Classifier ML (Wave 5+) asignando `material_id` con confianza ≥0.9.
- Cobertura ≥99% verificada en producción durante 2 semanas.
- UI admin para reclasificar manualmente los SKUs huérfanos restantes.

**No promover nunca** (decisión arquitectónica):
- `series_id` — opt-in comercial, NULL es válido.
- `display_pair_sku` — excepcional, NULL es la norma.

### 2.3. Stage 4c — drop columnas escalares deprecadas (mig. 050)

Una vez los consumidores ya solo leen `brand_id`/`family_id` (no `brand`/`family` TEXT):

```python
def upgrade() -> None:
    # Verificar que no quedan tests / código accediendo a las TEXT cols.
    op.drop_column("products", "brand")
    op.drop_column("products", "family")
    # subfamily / type / material / series TEXT cols — drop en Stage 4d
    # cuando los FKs estén NOT NULL.
```

⚠ Esto rompe queries que usen `WHERE family = 'valves'`. Hay que migrar a JOIN families ON family_id antes.

---

## 3. Cambios en código requeridos antes de Stage 4

| Capa | Cambio | Esfuerzo |
|---|---|---|
| Importer PIM | Resolver `family_id`/`brand_id` desde row mapper antes de insert. | M |
| Importer PIM | Si family no existe en taxonomía, crearla on-the-fly o fallar el row. | S |
| Wizard FE | Selector de family ahora usa `families` API (no enum hardcoded). Hoy lo hace pero verificar. | S |
| Wizard FE | Si Stage 4b activo, requerir subfamily_id + type_id en form validation. | M |
| Repository `list_paginated_with_filters` | Migrar `WHERE family=:family` a JOIN families ON family_id. | M |
| Facets compute | Migrar buckets de `family` (TEXT) a `family_id` (UUID con JOIN). UI muestra `name`. | M |
| Tests fixtures | Actualizar todos los productos de fixture con FKs válidos. | S |
| GraphRAG / search | Re-indexar embeddings con metadata FK-based. | L (Sprint 13+) |
| Audit query | Verificar logs no asumen TEXT escalares. | S |

---

## 4. Riesgos y mitigaciones

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| Importer falla en row con family/brand desconocido | Alta | Stage 4a: pre-crear families/brands en mig. 048; permitir auto-create on-the-fly con WARNING log. |
| Tests rompen por fixtures con TEXT pero sin FK | Alta | Update fixtures en el mismo PR de Stage 4a; CI verde antes de merge. |
| Producción tiene productos con FK NULL escapados de mig. 042 | Baja | Mig 048 hace backfill defensivo + falla si encuentra NULLs. |
| Drop de columnas TEXT rompe BI / dashboards externos | Media | Comunicar a stakeholders 30 días antes; mantener vista compatible `products_with_text_cols` durante 1 sprint. |

---

## 5. Verificación post-Stage 4a

```bash
# Counts deben ser 0
docker exec mt-backend python -c "
import asyncio
from sqlalchemy import text
from app.db.engine import get_sessionmaker
async def main():
    async with get_sessionmaker()() as s:
        n = (await s.execute(text(
            'SELECT count(*) FROM products WHERE brand_id IS NULL OR family_id IS NULL'
        ))).scalar_one()
        print(f'NULLs: {n}')  # esperar 0
asyncio.run(main())"

# Tests verdes
docker exec mt-backend pytest tests/unit -q --no-cov

# Probar insert con brand_id NULL → debe fallar con NOT NULL constraint
```

---

## 6. Resumen ejecutivo

- **Ejecutar ahora (Stage 4a)**: promover `brand_id`, `family_id` a NOT NULL — bajo riesgo, cobertura 100%.
- **Diferir (Stage 4b)**: `subfamily_id`, `type_id`, `material_id` esperan clasificación masiva.
- **Nunca**: `series_id`, `display_pair_sku` quedan NULLABLE permanente.
- **Sprint adicional**: drop columnas TEXT escalares cuando consumidores migrados (Stage 4c).
- **Coordinar**: importer + FE wizard + facets + repos antes de cada promoción.
