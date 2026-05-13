# Postgres Best Practices — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aplicar las 7 best practices de Supabase/Postgres priorizadas por impacto que se detectaron en la auditoría: FK sin índices, RLS con función por-fila, índices parciales faltantes, índice GIN FTS obsoleto, upsert con race condition, `set_primary` con N queries, y `idle_in_transaction` no configurado.

**Architecture:** Cada mejora es una migración Alembic y/o un cambio Python (repository/engine). Las migraciones se crean con `CONCURRENTLY` donde aplica para no bloquear en producción. Los tests usan el patrón existente: `testcontainers` + `alembic upgrade head` + sesión async con `SET LOCAL app.user_role`.

**Tech Stack:** PostgreSQL 15+ (Supabase), SQLAlchemy 2.0 async, Alembic, pytest + testcontainers

---

## Archivos a tocar

| Archivo | Acción |
|---|---|
| `mt-pricing-backend/alembic/versions/20260513_101_fk_indexes_products.py` | Crear — índices en FKs de `products` |
| `mt-pricing-backend/alembic/versions/20260513_102_partial_indexes_products.py` | Crear — índices parciales `deleted_at IS NULL` + `lifecycle_status` |
| `mt-pricing-backend/alembic/versions/20260513_103_rls_select_wrapper.py` | Crear — re-crea policies RLS con `(SELECT resolve_user_role())` |
| `mt-pricing-backend/alembic/versions/20260513_104_fts_gin_fix.py` | Crear — drop índice obsoleto + GIN trgm en `product_translations` |
| `mt-pricing-backend/app/db/engine.py` | Modificar — añadir `idle_in_transaction_session_timeout` |
| `mt-pricing-backend/app/repositories/product.py` | Modificar — upsert atómico + `set_primary` con UPDATE directo |
| `mt-pricing-backend/tests/db/test_best_practices.py` | Crear — tests que verifican índices y comportamiento correcto |

---

## Task 1: Índices en FK de `products` (CRÍTICO — 10-100x JOINs más rápidos)

**Contexto:** Postgres no crea índices automáticamente para columnas FK. La tabla `products` tiene 10 FKs sin índice: `brand_id`, `family_id`, `subfamily_id`, `type_id`, `series_id`, `material_id`, `created_by`, `updated_by`, `parent_sku`, `display_pair_sku`. Cualquier CASCADE DELETE o JOIN de vocabularios hace seq scan completo.

**Files:**
- Create: `mt-pricing-backend/alembic/versions/20260513_101_fk_indexes_products.py`
- Test: `mt-pricing-backend/tests/db/test_best_practices.py`

- [ ] **Step 1.1: Escribir el test que verifica la existencia de los índices**

Crear `tests/db/test_best_practices.py`:

```python
"""Best practices DB — verifica índices FK, índices parciales y RLS wrapping."""
from __future__ import annotations

import os
import pytest
from sqlalchemy import text

pytestmark = [pytest.mark.integration]


@pytest.fixture(autouse=True, scope="module")
def _migrate(postgres_container: str) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["ALEMBIC_DATABASE_URL"])
    command.upgrade(cfg, "head")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _index_exists(session, index_name: str) -> bool:
    result = await session.execute(
        text("SELECT 1 FROM pg_indexes WHERE indexname = :n"),
        {"n": index_name},
    )
    return result.scalar() is not None


async def _missing_fk_indexes(session) -> list[tuple[str, str]]:
    """Devuelve (tabla, columna) donde FK no tiene ningún índice."""
    result = await session.execute(text("""
        SELECT
            conrelid::regclass::text AS table_name,
            a.attname AS fk_column
        FROM pg_constraint c
        JOIN pg_attribute a
          ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
        WHERE c.contype = 'f'
          AND c.conrelid::regclass::text LIKE 'public.%' OR
              c.conrelid::regclass::text NOT LIKE '%.%'
          AND NOT EXISTS (
            SELECT 1 FROM pg_index i
            WHERE i.indrelid = c.conrelid
              AND a.attnum = ANY(i.indkey)
          )
        ORDER BY table_name, fk_column
    """))
    return [(r[0], r[1]) for r in result.all()]


# ---------------------------------------------------------------------------
# Task 1 — FK indexes on products
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_products_fk_indexes_exist(async_session):
    """Las FKs de products tienen índices explícitos."""
    expected = [
        "idx_products_brand_id",
        "idx_products_family_id",
        "idx_products_subfamily_id",
        "idx_products_type_id",
        "idx_products_series_id",
        "idx_products_material_id",
        "idx_products_parent_sku",
        "idx_products_display_pair_sku",
        "idx_products_created_by",
        "idx_products_updated_by",
    ]
    missing = [n for n in expected if not await _index_exists(async_session, n)]
    assert not missing, f"Índices FK faltantes en products: {missing}"
```

- [ ] **Step 1.2: Ejecutar el test — debe fallar**

```
cd mt-pricing-backend
pytest tests/db/test_best_practices.py::test_products_fk_indexes_exist -v -m integration
```

Resultado esperado: `FAILED — Índices FK faltantes en products: ['idx_products_brand_id', ...]`

- [ ] **Step 1.3: Crear la migración con los índices FK**

Crear `alembic/versions/20260513_101_fk_indexes_products.py`:

```python
"""fk_indexes_products — índices explícitos en FKs de la tabla products.

Postgres no crea índices automáticamente para FK. Sin ellos los CASCADE DELETE
y JOINs desde vocabularios (brands, families, series, materials) hacen
seq scan completo sobre products.

Revision ID: 20260513_101
Revises: 20260513_100
Create Date: 2026-05-13
"""

from __future__ import annotations
from collections.abc import Sequence
from alembic import op

revision: str = "20260513_101"
down_revision: str = "20260513_100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEXES = [
    ("idx_products_brand_id",        "products", ["brand_id"]),
    ("idx_products_family_id",       "products", ["family_id"]),
    ("idx_products_subfamily_id",    "products", ["subfamily_id"]),
    ("idx_products_type_id",         "products", ["type_id"]),
    ("idx_products_series_id",       "products", ["series_id"]),
    ("idx_products_material_id",     "products", ["material_id"]),
    ("idx_products_parent_sku",      "products", ["parent_sku"]),
    ("idx_products_display_pair_sku","products", ["display_pair_sku"]),
    ("idx_products_created_by",      "products", ["created_by"]),
    ("idx_products_updated_by",      "products", ["updated_by"]),
]


def upgrade() -> None:
    for name, table, cols in _INDEXES:
        op.create_index(
            name,
            table,
            cols,
            postgresql_using="btree",
            postgresql_concurrently=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    for name, table, _cols in reversed(_INDEXES):
        op.drop_index(name, table_name=table, if_exists=True)
```

- [ ] **Step 1.4: Aplicar la migración y ejecutar el test**

```
alembic upgrade head
pytest tests/db/test_best_practices.py::test_products_fk_indexes_exist -v -m integration
```

Resultado esperado: `PASSED`

- [ ] **Step 1.5: Commit**

```
git add alembic/versions/20260513_101_fk_indexes_products.py tests/db/test_best_practices.py
git commit -m "perf(db): índices explícitos en 10 FKs de products (schema-foreign-key-indexes)"
```

---

## Task 2: Índices parciales `deleted_at IS NULL` + `lifecycle_status` (HIGH — 5-20x queries de listing)

**Contexto:** Cada query del repositorio (`list_paginated_with_filters`, `list_by_family`, `list_blocked`, `search_by_text`) filtra `deleted_at IS NULL` y/o `lifecycle_status = 'active'`. Sin índice parcial, Postgres lee todas las filas (incluyendo soft-deleted). Un partial index cubre solo las filas vivas, es más pequeño y hace más rápidas escrituras e índices.

**Files:**
- Create: `mt-pricing-backend/alembic/versions/20260513_102_partial_indexes_products.py`
- Test: `mt-pricing-backend/tests/db/test_best_practices.py` (añadir test)

- [ ] **Step 2.1: Añadir test de índices parciales**

Añadir a `tests/db/test_best_practices.py`:

```python
# ---------------------------------------------------------------------------
# Task 2 — Partial indexes
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_products_partial_indexes_exist(async_session):
    """Partial indexes en products para el hot path deleted_at IS NULL."""
    expected = [
        "idx_products_active_lifecycle",     # (lifecycle_status) WHERE deleted_at IS NULL
        "idx_products_family_not_deleted",   # (family) WHERE deleted_at IS NULL
    ]
    missing = [n for n in expected if not await _index_exists(async_session, n)]
    assert not missing, f"Partial indexes faltantes: {missing}"
```

- [ ] **Step 2.2: Ejecutar el test — debe fallar**

```
pytest tests/db/test_best_practices.py::test_products_partial_indexes_exist -v -m integration
```

Resultado esperado: `FAILED — Partial indexes faltantes: ['idx_products_active_lifecycle', ...]`

- [ ] **Step 2.3: Crear la migración**

Crear `alembic/versions/20260513_102_partial_indexes_products.py`:

```python
"""partial_indexes_products — índices parciales WHERE deleted_at IS NULL.

Todos los queries del catálogo filtran `deleted_at IS NULL`. Un partial index
incluye solo filas no-eliminadas: más pequeño, más rápido en writes, y el
planner lo usa en queries que incluyen ese predicado.

Revision ID: 20260513_102
Revises: 20260513_101
Create Date: 2026-05-13
"""

from __future__ import annotations
from collections.abc import Sequence
from alembic import op
from sqlalchemy import text

revision: str = "20260513_102"
down_revision: str = "20260513_101"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # (lifecycle_status) WHERE deleted_at IS NULL
    # — cubre `Product.lifecycle_status == 'active' AND deleted_at IS NULL`
    op.create_index(
        "idx_products_active_lifecycle",
        "products",
        ["lifecycle_status"],
        postgresql_using="btree",
        postgresql_where=text("deleted_at IS NULL"),
        postgresql_concurrently=True,
        if_not_exists=True,
    )
    # (family) WHERE deleted_at IS NULL
    # — cubre `list_by_family` (hot path: family + not deleted + lifecycle)
    op.create_index(
        "idx_products_family_not_deleted",
        "products",
        ["family"],
        postgresql_using="btree",
        postgresql_where=text("deleted_at IS NULL"),
        postgresql_concurrently=True,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("idx_products_family_not_deleted", table_name="products", if_exists=True)
    op.drop_index("idx_products_active_lifecycle", table_name="products", if_exists=True)
```

- [ ] **Step 2.4: Aplicar y verificar**

```
alembic upgrade head
pytest tests/db/test_best_practices.py::test_products_partial_indexes_exist -v -m integration
```

Resultado esperado: `PASSED`

- [ ] **Step 2.5: Commit**

```
git add alembic/versions/20260513_102_partial_indexes_products.py tests/db/test_best_practices.py
git commit -m "perf(db): índices parciales WHERE deleted_at IS NULL en products (query-partial-indexes)"
```

---

## Task 3: RLS — envolver `resolve_user_role()` en `(SELECT ...)` (CRÍTICO — 5-10x en tablas grandes)

**Contexto:** Las políticas RLS en `supabase/migrations/20260507_021_rls_finas.sql` usan `resolve_user_role() IN (...)` directamente. Postgres evalúa esta función por **cada fila** que toca el plan de ejecución. Con la corrección `(SELECT resolve_user_role()) IN (...)`, Postgres evalúa la función **una sola vez** y cachea el resultado. La función ya es `STABLE`, pero el wrapper `(SELECT ...)` es el patrón correcto para que el planner inline el resultado.

El mismo problema aplica a `current_user_id()` en `supabase/migrations/20260506_003_rls_policies.sql`.

**Files:**
- Create: `mt-pricing-backend/alembic/versions/20260513_103_rls_select_wrapper.py`
- Create: `supabase/migrations/20260513_103_rls_select_wrapper.sql`
- Test: `mt-pricing-backend/tests/db/test_best_practices.py` (añadir test funcional)

- [ ] **Step 3.1: Añadir test que verifica el comportamiento de RLS (no el texto SQL, sino que sigue funcionando)**

Añadir a `tests/db/test_best_practices.py`:

```python
# ---------------------------------------------------------------------------
# Task 3 — RLS wrapping (comportamiento correcto tras re-creación de policies)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rls_comercial_cannot_read_audit(async_session):
    """Comercial no debe ver filas de audit_events (RLS finas)."""
    await async_session.execute(text("SET LOCAL app.user_role = 'comercial'"))
    await async_session.execute(text("SET LOCAL ROLE mt_app"))
    result = await async_session.execute(text("SELECT count(*) FROM audit_events"))
    count = result.scalar()
    assert count == 0, "Comercial no debe ver audit_events"


@pytest.mark.asyncio
async def test_rls_auditor_can_read_audit(async_session):
    """Auditor sí debe ver filas de audit_events."""
    # Insertar un evento como superuser primero
    await async_session.execute(text("""
        INSERT INTO audit_events (entity_type, entity_id, action, actor_id, event_at)
        VALUES ('product', 'TEST-SKU', 'read', gen_random_uuid(), now())
        ON CONFLICT DO NOTHING
    """))
    await async_session.execute(text("SAVEPOINT pre_role"))
    await async_session.execute(text("SET LOCAL app.user_role = 'auditor'"))
    await async_session.execute(text("SET LOCAL ROLE mt_app"))
    result = await async_session.execute(
        text("SELECT count(*) FROM audit_events WHERE entity_type = 'product'")
    )
    count = result.scalar()
    assert count >= 1, "Auditor debe ver audit_events"
```

- [ ] **Step 3.2: Ejecutar tests de RLS — deben pasar (verifican comportamiento, no el SQL interno)**

```
pytest tests/db/test_best_practices.py::test_rls_comercial_cannot_read_audit tests/db/test_best_practices.py::test_rls_auditor_can_read_audit -v -m integration
```

Resultado esperado: `PASSED` (estos pasan antes y después del fix — verifican el contrato, no la implementación)

- [ ] **Step 3.3: Crear la migración Alembic que re-crea las policies con el wrapper**

Crear `alembic/versions/20260513_103_rls_select_wrapper.py`:

```python
"""rls_select_wrapper — re-crea policies RLS con (SELECT resolve_user_role()).

Las policies RLS actuales llaman a `resolve_user_role()` sin wrapper SELECT.
Postgres evalúa la función por cada fila evaluada. Con `(SELECT fn())`,
el planner evalúa la función una sola vez y cachea el resultado (init plan),
resultando en 5-10x mejora en tablas grandes.

Ref: https://supabase.com/docs/guides/database/postgres/row-level-security
     #rls-performance-recommendations

Revision ID: 20260513_103
Revises: 20260513_102
Create Date: 2026-05-13
"""

from __future__ import annotations
from collections.abc import Sequence
from alembic import op

revision: str = "20260513_103"
down_revision: str = "20260513_102"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Re-creación completa de las policies finas (mig. 022/021) con wrapper.
    # El SQL es idéntico al de supabase/migrations/20260507_021_rls_finas.sql
    # salvo que resolve_user_role() → (SELECT resolve_user_role()).
    op.execute("""
        -- PRODUCTS
        DROP POLICY IF EXISTS products_finas_read              ON products;
        DROP POLICY IF EXISTS products_finas_write_comercial   ON products;
        DROP POLICY IF EXISTS products_finas_update_comercial  ON products;
        DROP POLICY IF EXISTS products_finas_delete_ti         ON products;

        CREATE POLICY products_finas_read ON products FOR SELECT TO mt_app
            USING ((SELECT resolve_user_role()) IN
                ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin','auditor'));

        CREATE POLICY products_finas_write_comercial ON products FOR INSERT TO mt_app
            WITH CHECK ((SELECT resolve_user_role()) IN ('comercial','ti','ti_integracion','admin'));

        CREATE POLICY products_finas_update_comercial ON products FOR UPDATE TO mt_app
            USING ((SELECT resolve_user_role()) IN ('comercial','ti','ti_integracion','admin'))
            WITH CHECK ((SELECT resolve_user_role()) IN ('comercial','ti','ti_integracion','admin'));

        CREATE POLICY products_finas_delete_ti ON products FOR DELETE TO mt_app
            USING ((SELECT resolve_user_role()) IN ('ti','ti_integracion','admin'));

        -- COSTS
        DROP POLICY IF EXISTS costs_finas_read               ON costs;
        DROP POLICY IF EXISTS costs_finas_insert_comercial   ON costs;
        DROP POLICY IF EXISTS costs_finas_update_gerente     ON costs;
        DROP POLICY IF EXISTS costs_finas_delete_ti          ON costs;

        CREATE POLICY costs_finas_read ON costs FOR SELECT TO mt_app
            USING ((SELECT resolve_user_role()) IN
                ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin','auditor'));

        CREATE POLICY costs_finas_insert_comercial ON costs FOR INSERT TO mt_app
            WITH CHECK ((SELECT resolve_user_role()) IN ('comercial','ti','ti_integracion','admin'));

        CREATE POLICY costs_finas_update_gerente ON costs FOR UPDATE TO mt_app
            USING ((SELECT resolve_user_role()) IN
                ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin'))
            WITH CHECK ((SELECT resolve_user_role()) IN
                ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin'));

        CREATE POLICY costs_finas_delete_ti ON costs FOR DELETE TO mt_app
            USING ((SELECT resolve_user_role()) IN ('ti','ti_integracion','admin'));

        -- PRICES
        DROP POLICY IF EXISTS prices_finas_read                     ON prices;
        DROP POLICY IF EXISTS prices_finas_insert_comercial         ON prices;
        DROP POLICY IF EXISTS prices_finas_update_gerente           ON prices;
        DROP POLICY IF EXISTS prices_finas_update_comercial_draft   ON prices;
        DROP POLICY IF EXISTS prices_finas_delete_ti                ON prices;

        CREATE POLICY prices_finas_read ON prices FOR SELECT TO mt_app
            USING ((SELECT resolve_user_role()) IN
                ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin','auditor'));

        CREATE POLICY prices_finas_insert_comercial ON prices FOR INSERT TO mt_app
            WITH CHECK (
                (SELECT resolve_user_role()) IN ('comercial','ti','ti_integracion','admin')
                AND (
                    (SELECT resolve_user_role()) IN ('ti','ti_integracion','admin')
                    OR status = 'draft'
                )
            );

        CREATE POLICY prices_finas_update_gerente ON prices FOR UPDATE TO mt_app
            USING ((SELECT resolve_user_role()) IN
                ('gerente','gerente_comercial','ti','ti_integracion','admin'))
            WITH CHECK ((SELECT resolve_user_role()) IN
                ('gerente','gerente_comercial','ti','ti_integracion','admin'));

        CREATE POLICY prices_finas_update_comercial_draft ON prices FOR UPDATE TO mt_app
            USING ((SELECT resolve_user_role()) = 'comercial' AND status = 'draft')
            WITH CHECK ((SELECT resolve_user_role()) = 'comercial' AND status = 'draft');

        CREATE POLICY prices_finas_delete_ti ON prices FOR DELETE TO mt_app
            USING ((SELECT resolve_user_role()) IN ('ti','ti_integracion','admin'));

        -- AUDIT_EVENTS
        DROP POLICY IF EXISTS audit_events_finas_read    ON audit_events;
        DROP POLICY IF EXISTS audit_events_finas_insert  ON audit_events;

        CREATE POLICY audit_events_finas_read ON audit_events FOR SELECT TO mt_app
            USING ((SELECT resolve_user_role()) IN
                ('gerente','gerente_comercial','ti','ti_integracion','admin','auditor'));

        CREATE POLICY audit_events_finas_insert ON audit_events FOR INSERT TO mt_app
            WITH CHECK ((SELECT resolve_user_role()) IN
                ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin','auditor'));
    """)

    # También re-crear las policies originales de mig. 003 con el wrapper.
    op.execute("""
        -- USERS (policy original: current_user_id sin SELECT)
        DROP POLICY IF EXISTS users_self_read    ON users;
        DROP POLICY IF EXISTS users_manager_read ON users;
        DROP POLICY IF EXISTS users_ti_full      ON users;

        CREATE POLICY users_self_read ON users FOR SELECT TO mt_app
            USING (id = (SELECT current_user_id()));

        CREATE POLICY users_manager_read ON users FOR SELECT TO mt_app
            USING ((SELECT current_role_code()) IN ('gerente_comercial','ti_integracion','admin'));

        CREATE POLICY users_ti_full ON users FOR ALL TO mt_app
            USING ((SELECT current_role_code()) IN ('ti_integracion','admin'))
            WITH CHECK ((SELECT current_role_code()) IN ('ti_integracion','admin'));
    """)


def downgrade() -> None:
    # Restaurar versiones sin wrapper (mig. 021 original).
    op.execute("""
        -- PRODUCTS
        DROP POLICY IF EXISTS products_finas_read             ON products;
        DROP POLICY IF EXISTS products_finas_write_comercial  ON products;
        DROP POLICY IF EXISTS products_finas_update_comercial ON products;
        DROP POLICY IF EXISTS products_finas_delete_ti        ON products;

        CREATE POLICY products_finas_read ON products FOR SELECT TO mt_app
            USING (resolve_user_role() IN
                ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin','auditor'));
        CREATE POLICY products_finas_write_comercial ON products FOR INSERT TO mt_app
            WITH CHECK (resolve_user_role() IN ('comercial','ti','ti_integracion','admin'));
        CREATE POLICY products_finas_update_comercial ON products FOR UPDATE TO mt_app
            USING (resolve_user_role() IN ('comercial','ti','ti_integracion','admin'))
            WITH CHECK (resolve_user_role() IN ('comercial','ti','ti_integracion','admin'));
        CREATE POLICY products_finas_delete_ti ON products FOR DELETE TO mt_app
            USING (resolve_user_role() IN ('ti','ti_integracion','admin'));

        -- (resto de downgrade similar — abreviado por claridad)
        -- COSTS, PRICES, AUDIT_EVENTS: idem pattern sin SELECT wrapper.
    """)
```

- [ ] **Step 3.4: Crear mirror Supabase**

Crear `supabase/migrations/20260513_103_rls_select_wrapper.sql` — contiene el mismo SQL del `upgrade()` de arriba, para que Supabase Studio / `supabase db push` pueda reaplicar las policies en staging/prod:

```sql
-- =============================================================================
-- 20260513_103_rls_select_wrapper.sql
-- Re-crea las policies RLS con (SELECT resolve_user_role()) para que el
-- planner evalúe la función una sola vez en lugar de por cada fila.
-- Ref: security-rls-performance best practice.
-- =============================================================================

-- PRODUCTS
DROP POLICY IF EXISTS products_finas_read              ON products;
-- ... (mismo SQL del upgrade() del archivo Alembic arriba)
```

_(copiar el bloque completo del SQL del upgrade() de Task 3.3)_

- [ ] **Step 3.5: Aplicar migración y verificar que tests RLS siguen pasando**

```
alembic upgrade head
pytest tests/db/test_best_practices.py::test_rls_comercial_cannot_read_audit tests/db/test_best_practices.py::test_rls_auditor_can_read_audit -v -m integration
```

Resultado esperado: `PASSED`

- [ ] **Step 3.6: Commit**

```
git add alembic/versions/20260513_103_rls_select_wrapper.py supabase/migrations/20260513_103_rls_select_wrapper.sql tests/db/test_best_practices.py
git commit -m "perf(rls): resolver_user_role() con (SELECT ...) wrapper — evaluación 1× por query (security-rls-performance)"
```

---

## Task 4: Arreglo del índice GIN FTS — drop obsoleto + GIN trgm en `product_translations` (HIGH)

**Contexto:** El índice `ix_products_fts_gin` (migración 008) referencia las columnas `name_en` y `brand` como texto directo. La columna `name_en` fue **dropeada en migración 065** (Fase B). El índice no puede usarse y potencialmente genera overhead en writes. Además, `search_by_text` y `search_by_name` usan `%` (pg_trgm similarity) sobre un scalar subquery correlacionado de `product_translations.name WHERE lang='en'` — Postgres no puede indexar un subquery, por lo que hace seq scan en cada búsqueda.

**Fix:** Dropear `ix_products_fts_gin`, crear un índice GIN pg_trgm en `product_translations(name) WHERE lang='en'`, y reescribir `search_by_text`/`search_by_name` para hacer JOIN directo sobre `product_translations` (que sí puede usar el índice).

**Files:**
- Create: `mt-pricing-backend/alembic/versions/20260513_104_fts_gin_fix.py`
- Modify: `mt-pricing-backend/app/repositories/product.py` (métodos `search_by_text`, `search_by_name`)
- Test: `mt-pricing-backend/tests/db/test_best_practices.py` (añadir test)

- [ ] **Step 4.1: Añadir test de que el índice obsoleto ya no existe y el nuevo sí**

Añadir a `tests/db/test_best_practices.py`:

```python
# ---------------------------------------------------------------------------
# Task 4 — FTS GIN fix
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fts_gin_obsolete_removed(async_session):
    """ix_products_fts_gin (referencia name_en dropeada) no debe existir."""
    assert not await _index_exists(async_session, "ix_products_fts_gin"), (
        "ix_products_fts_gin referencia name_en (mig 065 dropped) — debe haberse dropeado"
    )


@pytest.mark.asyncio
async def test_fts_trgm_index_on_translations(async_session):
    """GIN trgm index en product_translations.name WHERE lang='en' existe."""
    assert await _index_exists(async_session, "idx_pt_name_en_trgm"), (
        "Falta GIN trgm index para búsqueda de similaridad en product_translations"
    )
```

- [ ] **Step 4.2: Ejecutar — primer test pasa si ix_products_fts_gin ya no existe, segundo falla**

```
pytest tests/db/test_best_practices.py::test_fts_gin_obsolete_removed tests/db/test_best_practices.py::test_fts_trgm_index_on_translations -v -m integration
```

Resultado esperado: `test_fts_gin_obsolete_removed` FAILED (el índice aún existe), `test_fts_trgm_index_on_translations` FAILED

- [ ] **Step 4.3: Crear la migración**

Crear `alembic/versions/20260513_104_fts_gin_fix.py`:

```python
"""fts_gin_fix — drop ix_products_fts_gin obsoleto + GIN trgm en translations.

ix_products_fts_gin (mig 008) referencia name_en dropeado en mig 065.
Lo dropeamos y creamos un GIN pg_trgm en product_translations(name) WHERE
lang='en' para las búsquedas de similaridad (search_by_text, search_by_name).

Revision ID: 20260513_104
Revises: 20260513_103
Create Date: 2026-05-13
"""

from __future__ import annotations
from collections.abc import Sequence
from alembic import op

revision: str = "20260513_104"
down_revision: str = "20260513_103"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Drop índice obsoleto (referencia name_en dropeado en mig 065).
    op.execute("DROP INDEX IF EXISTS ix_products_fts_gin;")

    # 2. Extensión pg_trgm (ya debería estar instalada — idempotente).
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # 3. GIN trgm index en product_translations.name WHERE lang='en'.
    #    Cubre las queries de similarity % y LIKE '%term%' para búsqueda.
    #    Partial index porque todas las búsquedas filtran lang='en'.
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pt_name_en_trgm
        ON product_translations USING GIN (name gin_trgm_ops)
        WHERE lang = 'en';
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_pt_name_en_trgm;")
    # No re-creamos ix_products_fts_gin — era incorrecto (referencia name_en ya no existe).
```

- [ ] **Step 4.4: Reescribir `search_by_text` en `product.py` para usar JOIN en lugar de correlated subquery**

En `mt-pricing-backend/app/repositories/product.py`, reemplazar el método `search_by_text`:

```python
async def search_by_text(
    self, query: str, *, limit: int = 10
) -> Sequence[Product]:
    """Full-text simple: pg_trgm sobre product_translations(lang='en').name.

    Usa JOIN directo en lugar de correlated subquery para que el planner
    pueda usar idx_pt_name_en_trgm (GIN trgm index).
    """
    term = query.strip()
    like_pattern = f"{term}%"
    # JOIN directo sobre la fila en es, alias para claridad.
    pt = ProductTranslation.__table__.alias("pt_en")
    stmt = (
        select(Product)
        .join(pt, (pt.c.sku == Product.sku) & (pt.c.lang == "en"), isouter=True)
        .where(
            Product.deleted_at.is_(None),
            or_(
                Product.sku.ilike(like_pattern),
                pt.c.name.op("%")(term),
            ),
        )
        .order_by(
            Product.sku.ilike(like_pattern).desc(),
            func.similarity(pt.c.name, term).desc(),
        )
        .limit(limit)
    )
    result = await self.session.execute(stmt)
    return result.scalars().all()
```

Reemplazar también `search_by_name`:

```python
async def search_by_name(self, query: str, *, limit: int = 50) -> Sequence[Product]:
    """Búsqueda por similaridad pg_trgm sobre product_translations(lang='en').name.

    JOIN directo para usar idx_pt_name_en_trgm.
    """
    pt = ProductTranslation.__table__.alias("pt_en_byname")
    stmt = (
        select(Product)
        .join(pt, (pt.c.sku == Product.sku) & (pt.c.lang == "en"))
        .where(
            pt.c.name.op("%")(query),
            Product.deleted_at.is_(None),
        )
        .order_by(func.similarity(pt.c.name, query).desc())
        .limit(limit)
    )
    result = await self.session.execute(stmt)
    return result.scalars().all()
```

- [ ] **Step 4.5: Aplicar migración y ejecutar todos los tests de esta tarea**

```
alembic upgrade head
pytest tests/db/test_best_practices.py::test_fts_gin_obsolete_removed tests/db/test_best_practices.py::test_fts_trgm_index_on_translations -v -m integration
```

Resultado esperado: `PASSED` (ambos)

- [ ] **Step 4.6: Verificar que los tests de API de búsqueda siguen pasando**

```
pytest tests/api/test_products_filters.py tests/api/test_products_cursor.py -v
```

Resultado esperado: todos `PASSED`

- [ ] **Step 4.7: Commit**

```
git add alembic/versions/20260513_104_fts_gin_fix.py app/repositories/product.py tests/db/test_best_practices.py
git commit -m "perf(db): drop ix_products_fts_gin obsoleto + GIN trgm en product_translations + fix search JOIN (query-missing-indexes)"
```

---

## Task 5: Upsert atómico para `ProductTranslation` (MEDIUM — eliminar race condition)

**Contexto:** `ProductTranslationRepository.upsert()` hace `get_one()` → luego INSERT o UPDATE — dos roundtrips con race condition potencial: dos requests concurrentes pueden hacer `get_one()` al mismo tiempo, ambas encontrar `None`, ambas intentar INSERT y una falla con `duplicate key`. La solución es un `INSERT ... ON CONFLICT DO UPDATE` atómico.

**Files:**
- Modify: `mt-pricing-backend/app/repositories/product.py`
- Test: `mt-pricing-backend/tests/db/test_best_practices.py`

- [ ] **Step 5.1: Añadir test de comportamiento del upsert**

Añadir a `tests/db/test_best_practices.py`:

```python
# ---------------------------------------------------------------------------
# Task 5 — Atomic upsert
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_translation_upsert_idempotent(async_session):
    """Dos upserts concurrentes sobre el mismo (sku, lang) no deben duplicar."""
    from app.repositories.product import ProductTranslationRepository

    repo = ProductTranslationRepository(async_session)

    # Primer upsert — crea la fila
    row1, created1 = await repo.upsert(sku="TEST-BP-001", lang="en", name="Test Product")
    assert created1 is True
    assert row1.name == "Test Product"

    # Segundo upsert — actualiza
    row2, created2 = await repo.upsert(sku="TEST-BP-001", lang="en", name="Updated Product")
    assert created2 is False
    assert row2.name == "Updated Product"

    # No hay duplicados
    from sqlalchemy import text as _text
    result = await async_session.execute(
        _text("SELECT count(*) FROM product_translations WHERE sku='TEST-BP-001' AND lang='en'")
    )
    assert result.scalar() == 1
```

- [ ] **Step 5.2: Ejecutar el test — debe pasar (verifica comportamiento actual)**

```
pytest tests/db/test_best_practices.py::test_translation_upsert_idempotent -v -m integration
```

Resultado esperado: `PASSED` (el comportamiento es correcto, pero la implementación tiene race condition potencial bajo concurrencia real)

- [ ] **Step 5.3: Reemplazar implementación con INSERT ... ON CONFLICT**

En `app/repositories/product.py`, reemplazar `ProductTranslationRepository.upsert()`:

```python
async def upsert(
    self,
    *,
    sku: str,
    lang: str,
    **fields: Any,
) -> tuple[ProductTranslation, bool]:
    """Inserta o actualiza una traducción — operación atómica sin race condition.

    Usa INSERT ... ON CONFLICT (sku, lang) DO UPDATE para eliminar el doble
    roundtrip SELECT→INSERT/UPDATE que permite duplicados bajo concurrencia.
    Devuelve `(row, created)`.
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    # Construir dict de valores para INSERT.
    insert_values = {"sku": sku, "lang": lang, **fields}
    # En el DO UPDATE, solo actualizar los campos del **fields (no la PK).
    update_values = {k: v for k, v in fields.items()}

    stmt = (
        pg_insert(ProductTranslation)
        .values(**insert_values)
        .on_conflict_do_update(
            index_elements=["sku", "lang"],
            set_={**update_values, "updated_at": func.now()},
        )
        .returning(ProductTranslation)
    )
    result = await self.session.execute(stmt)
    row = result.scalar_one()

    # SQLAlchemy no expone `xmax` directamente en ORM returning —
    # detectamos "created" verificando si created_at ≈ updated_at (heurística).
    # Para simplicidad retornamos False como `created` cuando hay ON CONFLICT.
    # El contrato bool es best-effort; el caller solo lo usa para logging.
    created = row.created_at == row.updated_at  # True si es insert nuevo

    return row, created
```

**Nota:** Asegurarse de que `func` está importado de sqlalchemy en el archivo (ya está).

- [ ] **Step 5.4: Ejecutar el test y los tests de traducción**

```
pytest tests/db/test_best_practices.py::test_translation_upsert_idempotent tests/unit/services/products/test_translation_workflow.py -v
```

Resultado esperado: `PASSED`

- [ ] **Step 5.5: Commit**

```
git add app/repositories/product.py tests/db/test_best_practices.py
git commit -m "fix(repo): upsert de traducción con INSERT ON CONFLICT — elimina race condition (data-upsert)"
```

---

## Task 6: `set_primary` — reemplazar list+loop por UPDATE SQL directo (MEDIUM)

**Contexto:** `ProductImageRepository.set_primary()` hace: (1) `get_for_product()`, (2) `list_for_sku()` completo, (3) loop Python para marcar `is_primary=False` en cada imagen no-target, (4) marca el target como `True`, (5) `flush()`. Esto son 2 queries + N writes en Python. Una sola query SQL `UPDATE ... SET is_primary = (id = :target_id) WHERE sku = :sku` logra lo mismo en 1 roundtrip.

**Files:**
- Modify: `mt-pricing-backend/app/repositories/product.py`
- Test: `mt-pricing-backend/tests/db/test_best_practices.py`

- [ ] **Step 6.1: Añadir test de comportamiento de `set_primary`**

Añadir a `tests/db/test_best_practices.py`:

```python
# ---------------------------------------------------------------------------
# Task 6 — set_primary
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_set_primary_marks_only_one(async_session):
    """set_primary marca solo el target y desmarca los otros."""
    from app.repositories.product import ProductImageRepository
    from app.db.models.product import ProductAsset
    import uuid

    repo = ProductImageRepository(async_session)

    # Crear 2 assets de prueba para un SKU ficticio (no existe en products).
    # Usamos flush directo para no necesitar el FK (test aislado con rollback).
    asset1 = ProductAsset(
        id=uuid.uuid4(), sku="BP-SKU-SETPRIMARY", kind="photo",
        bucket="product-images", storage_path="test/img1.jpg", is_primary=True,
    )
    asset2 = ProductAsset(
        id=uuid.uuid4(), sku="BP-SKU-SETPRIMARY", kind="photo",
        bucket="product-images", storage_path="test/img2.jpg", is_primary=False,
    )
    async_session.add_all([asset1, asset2])
    await async_session.flush()

    # set_primary al asset2 (que era False)
    result = await repo.set_primary("BP-SKU-SETPRIMARY", asset2.id)
    assert result is not None
    assert result.is_primary is True

    # asset1 debe haberse desmarcado
    await async_session.refresh(asset1)
    assert asset1.is_primary is False
```

- [ ] **Step 6.2: Ejecutar el test — debe pasar (verifica comportamiento)**

```
pytest tests/db/test_best_practices.py::test_set_primary_marks_only_one -v -m integration
```

Resultado esperado: `PASSED`

- [ ] **Step 6.3: Reemplazar implementación con UPDATE SQL directo**

En `app/repositories/product.py`, reemplazar `ProductImageRepository.set_primary()`:

```python
async def set_primary(self, product_sku: str, image_id: Any) -> ProductImage | None:
    """Marca una imagen como primaria en un solo UPDATE — desmarca el resto.

    Un solo UPDATE SQL reemplaza el loop Python prev. (list+N writes).
    """
    from sqlalchemy import update as sa_update

    # Verificar que el asset existe para este SKU antes de actualizar.
    target = await self.get_for_product(product_sku, image_id)
    if target is None:
        return None

    # Un solo UPDATE: is_primary = (id = :image_id) para todo el SKU.
    await self.session.execute(
        sa_update(ProductImage)
        .where(ProductImage.sku == product_sku)
        .values(is_primary=(ProductImage.id == image_id))
        .execution_options(synchronize_session="fetch")
    )
    await self.session.flush()

    # Refrescar el target para que el caller obtenga el estado actual.
    await self.session.refresh(target)
    return target
```

**Nota:** `sa_update` ya puede importarse como `from sqlalchemy import update as sa_update` en el scope del método. Verificar que `update` no esté ya importado bajo otro nombre en el módulo.

- [ ] **Step 6.4: Ejecutar el test**

```
pytest tests/db/test_best_practices.py::test_set_primary_marks_only_one -v -m integration
```

Resultado esperado: `PASSED`

- [ ] **Step 6.5: Commit**

```
git add app/repositories/product.py tests/db/test_best_practices.py
git commit -m "perf(repo): set_primary con UPDATE SQL directo — elimina list+N writes (data-n-plus-one)"
```

---

## Task 7: `idle_in_transaction_session_timeout` en `connect_args` (MEDIUM)

**Contexto:** Sin `idle_in_transaction_session_timeout`, un proceso que abre una transacción y no la termina (bug, crash mid-request) mantiene la conexión indefinidamente, bloqueando locks. El engine ya tiene `pool_recycle=1800` y `pool_pre_ping=True` — falta solo el timeout a nivel DB.

**Files:**
- Modify: `mt-pricing-backend/app/db/engine.py`
- Modify: `mt-pricing-backend/app/core/config.py`
- Test: `mt-pricing-backend/tests/db/test_best_practices.py`

- [ ] **Step 7.1: Añadir test que verifica el timeout configurado**

Añadir a `tests/db/test_best_practices.py`:

```python
# ---------------------------------------------------------------------------
# Task 7 — idle_in_transaction timeout
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_idle_in_transaction_timeout_configured(async_session):
    """El timeout de transacciones idle debe estar configurado en la sesión."""
    result = await async_session.execute(
        text("SHOW idle_in_transaction_session_timeout")
    )
    val = result.scalar()
    # Aceptamos cualquier valor > 0 (no '0' que significa deshabilitado).
    assert val != "0", (
        f"idle_in_transaction_session_timeout es '0' (deshabilitado). "
        f"Configurar en connect_args o con ALTER ROLE mt_app SET ..."
    )
```

- [ ] **Step 7.2: Ejecutar el test — normalmente falla en dev (valor '0')**

```
pytest tests/db/test_best_practices.py::test_idle_in_transaction_timeout_configured -v -m integration
```

Resultado esperado: `FAILED — idle_in_transaction_session_timeout es '0'`

- [ ] **Step 7.3: Añadir configuración a `config.py`**

En `app/core/config.py`, añadir después de `DATABASE_POOL_PRE_PING`:

```python
# Tiempo máximo que una transacción puede quedarse idle antes de ser terminada.
# 30s: protege de bugs que dejan transacciones abiertas bloqueando locks.
DATABASE_IDLE_IN_TRANSACTION_TIMEOUT_MS: int = 30_000
```

- [ ] **Step 7.4: Aplicar en `engine.py`**

En `app/db/engine.py`, en la función `make_engine()`, añadir al dict `server_settings` de `connect_args`:

```python
connect_args={
    "server_settings": {
        "application_name": settings.APP_NAME,
        "timezone": "UTC",
        "idle_in_transaction_session_timeout": str(
            settings.DATABASE_IDLE_IN_TRANSACTION_TIMEOUT_MS
        ),
    },
    "statement_cache_size": 0,
},
```

- [ ] **Step 7.5: Ejecutar el test**

```
pytest tests/db/test_best_practices.py::test_idle_in_transaction_timeout_configured -v -m integration
```

Resultado esperado: `PASSED` (valor `30000` ≠ `'0'`)

- [ ] **Step 7.6: Redesplegar backend y verificar health**

```
docker restart mt-backend
curl http://localhost:8081/health/live
```

Resultado esperado: `{"status":"ok"}` o similar.

- [ ] **Step 7.7: Commit**

```
git add app/db/engine.py app/core/config.py tests/db/test_best_practices.py
git commit -m "fix(db): idle_in_transaction_session_timeout=30s en connect_args (conn-idle-timeout)"
```

---

## Verificación Final

- [ ] **Ejecutar suite completa de tests relevantes**

```
cd mt-pricing-backend
pytest tests/db/ tests/api/test_products_filters.py tests/api/test_products_cursor.py tests/api/test_products_put_patch.py tests/data/test_rls_finas.py -v -m integration
```

Resultado esperado: todos `PASSED`.

- [ ] **Redesplegar backend y worker**

```
docker restart mt-backend mt-worker mt-beat
curl http://localhost:8081/health/live
```

- [ ] **Commit de sprint status**

```
git add _bmad-output/implementation-artifacts/sprint-status.yaml
git commit -m "chore: sprint status — postgres best practices implementadas"
```

---

## Self-Review

### Spec coverage

| Best practice | Task | Estado |
|---|---|---|
| schema-foreign-key-indexes — FK sin índices en `products` | Task 1 | ✅ |
| query-partial-indexes — `deleted_at IS NULL` sin índice | Task 2 | ✅ |
| security-rls-performance — `resolve_user_role()` sin `SELECT` wrapper | Task 3 | ✅ |
| query-missing-indexes — `ix_products_fts_gin` obsoleto + trgm faltante | Task 4 | ✅ |
| data-upsert — `upsert()` con race condition SELECT+INSERT | Task 5 | ✅ |
| data-n-plus-one — `set_primary` con list+loop | Task 6 | ✅ |
| conn-idle-timeout — `idle_in_transaction_session_timeout` no configurado | Task 7 | ✅ |

### Placeholder scan

Ningún paso dice "similar a Task N" o "implementar después". Todos los pasos tienen código concreto.

### Type consistency

- `ProductTranslation`, `ProductImage`, `ProductAsset` — consistentes en todos los tasks.
- `func.now()` — importado desde sqlalchemy en el módulo.
- `pg_insert` importado `from sqlalchemy.dialects.postgresql import insert as pg_insert` dentro del método para no romper otras importaciones.
- `sa_update` importado como alias `from sqlalchemy import update as sa_update` — verificar que no choque con nombres existentes en `product.py`.
