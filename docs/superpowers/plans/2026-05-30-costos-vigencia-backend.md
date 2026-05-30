# Costos por esquema — Vigencia por rangos (Backend) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar a la tabla `costs` vigencia por rangos (`valid_from`/`valid_to`) con transición auto-encadenada (timeline continuo), y exponer la API para consultar/gestionar costes por fecha — sin romper el motor de precios.

**Architecture:** Se extiende la tabla `costs` (Enfoque 1): se añaden `valid_from`/`valid_to`, se garantiza no-solape con una constraint de exclusión GiST, el auto-encadenado vive en `cost_service`, el FX se ancla en `valid_from`, y se dropean `status`/`effective_at` (expuestos como hybrids derivados). Todo lo que filtraba `status='active'` pasa a "coste vigente hoy" (as-of today).

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + Alembic (public.*), Postgres `btree_gist`, pytest (testcontainers / pgvector). Spec: `docs/superpowers/specs/2026-05-30-costos-vigencia-modulo-design.md`.

**Entorno de tests (obligatorio):** correr pytest contra un Postgres fresco tipo-CI con overrides de auth hs256 (ver `docs/chat-docs/2026-05-29-proveedores-fase-1-guia-pruebas.md` §3). El contenedor `mt-backend` apunta a Supabase cloud; **no** correr migraciones destructivas ahí sin querer.

**Pre-requisito:** rama nueva desde `main` (`feat/costos-vigencia-backend`).

---

## File Structure

| Archivo | Responsabilidad | Acción |
|---------|-----------------|--------|
| `mt-pricing-backend/alembic/versions/2026053X_120_costs_validity_ranges.py` | Migración: columnas, backfill, exclusión, triggers, drops | Crear |
| `mt-pricing-backend/app/db/models/cost.py` | `valid_from`/`valid_to` reales; `effective_at`/`status`/`valid_to`(viejo) como hybrids | Modificar |
| `mt-pricing-backend/app/schemas/cost.py` (o donde vivan los schemas de cost) | `valid_from`/`valid_to` en Create/Patch/Response; quitar `status`/`effective_at` de entrada | Modificar |
| `mt-pricing-backend/app/services/costs/cost_service.py` | Auto-encadenado, `as_of`, `close`, corrección in-situ | Modificar |
| `mt-pricing-backend/app/repositories/pricing.py` (+ pricing service) | Lookup de coste → "vigente hoy" (as-of) | Modificar |
| `mt-pricing-backend/app/api/routes/costs.py` | POST `valid_from`, PATCH, `/{id}/close`, `/as-of`, list `valid_on`/`include_history`, `?as_of` | Modificar |
| `mt-pricing-backend/app/services/importer_costs/*` | Columna `valid_from`, filas futuras, differ vs as-of(valid_from) | Modificar |
| `mt-pricing-backend/tests/data/test_costs_validity.py` | Tests DB de rangos/exclusión/backfill | Crear |
| `mt-pricing-backend/tests/services/costs/test_cost_validity_service.py` | Tests service (auto-chain/as-of/close) | Crear |
| `mt-pricing-backend/tests/api/test_costs_validity_api.py` | Tests API endpoints nuevos | Crear |

---

## Task 1: Migración — columnas + backfill + exclusión + triggers + drops

**Files:**
- Create: `mt-pricing-backend/alembic/versions/2026053X_120_costs_validity_ranges.py`
- Test: `mt-pricing-backend/tests/data/test_costs_validity.py`

> Obtener el `down_revision` con `cd mt-pricing-backend && uv run alembic heads`. Usar el head actual.

- [ ] **Step 1: Escribir el test de migración (falla)**

```python
# tests/data/test_costs_validity.py
import pytest
from sqlalchemy import text

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

async def test_exclusion_rejects_overlapping_ranges(db_session):
    # Inserta dos costes solapados para la misma clave → debe fallar la exclusión.
    await db_session.execute(text("""
        INSERT INTO costs (id, sku, scheme_code, currency_origin, breakdown, valid_from, valid_to, version)
        VALUES (gen_random_uuid(), :sku, 'FBA', 'AED', '{}'::jsonb, DATE '2026-01-01', DATE '2026-06-30', 1)
    """), {"sku": "_TEST_OVL"})
    with pytest.raises(Exception):  # IntegrityError (ExclusionViolation)
        await db_session.execute(text("""
            INSERT INTO costs (id, sku, scheme_code, currency_origin, breakdown, valid_from, valid_to, version)
            VALUES (gen_random_uuid(), :sku, 'FBA', 'AED', '{}'::jsonb, DATE '2026-06-01', NULL, 2)
        """), {"sku": "_TEST_OVL"})

async def test_columns_exist_and_status_dropped(db_session):
    cols = (await db_session.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_name='costs'"
    ))).scalars().all()
    assert "valid_from" in cols and "valid_to" in cols
    assert "status" not in cols
    assert "effective_at" not in cols
```

> Nota: estos tests requieren un SKU+scheme válidos. Si `costs.sku` tiene FK a `products`, sembrar el producto antes con el fixture `make_product("_TEST_OVL")` y un scheme existente (FBA está seeded). Ajustar el INSERT para incluir las columnas NOT NULL reales (revisar `\d costs`).

- [ ] **Step 2: Correr el test y verque falla**

Run (DB fresca tipo-CI, ver guía de pruebas §3):
```
docker exec -e DATABASE_URL=... -e ALEMBIC_DATABASE_URL=... -e SUPABASE_JWT_VERIFICATION_MODE=hs256 \
  -e SUPABASE_JWT_SECRET='test-jwt-secret-deterministic-32chars!' -e JWT_ALGORITHM=HS256 \
  mt-backend pytest tests/data/test_costs_validity.py -p no:cacheprovider --no-cov -o addopts="" -x
```
Expected: FAIL (las columnas aún no existen / no hay exclusión).

- [ ] **Step 3: Escribir la migración**

```python
# alembic/versions/2026053X_120_costs_validity_ranges.py
"""costs: vigencia por rangos valid_from/valid_to + exclusion GiST

Revision ID: 2026053X_120
Down revision: <HEAD ACTUAL>
"""
from alembic import op
import sqlalchemy as sa

revision = "2026053X_120"
down_revision = "<HEAD ACTUAL>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # 1) Columnas (nullable temporal para backfill)
    op.add_column("costs", sa.Column("valid_from", sa.Date(), nullable=True))
    op.add_column("costs", sa.Column("valid_to", sa.Date(), nullable=True))

    # 2) Backfill: valid_from = effective_at::date
    op.execute("UPDATE costs SET valid_from = effective_at::date")

    # 3) Encadenar valid_to = (siguiente valid_from) - 1 por clave
    op.execute("""
        WITH ordered AS (
          SELECT id,
                 lead(valid_from) OVER (
                   PARTITION BY sku, scheme_code, coalesce(supplier_code,'')
                   ORDER BY valid_from, version
                 ) AS next_from
          FROM costs
        )
        UPDATE costs c
           SET valid_to = (o.next_from - INTERVAL '1 day')::date
          FROM ordered o
         WHERE c.id = o.id AND o.next_from IS NOT NULL
    """)

    # 4) valid_from NOT NULL
    op.alter_column("costs", "valid_from", nullable=False)

    # 5) Quitar unique parcial vieja (status='active') y añadir exclusión
    op.execute("DROP INDEX IF EXISTS idx_costs_active_unique_lookup")
    op.execute("""
        ALTER TABLE costs ADD CONSTRAINT ex_costs_no_overlap
        EXCLUDE USING gist (
          sku WITH =,
          scheme_code WITH =,
          coalesce(supplier_code,'') WITH =,
          daterange(valid_from, valid_to, '[]') WITH &&
        )
    """)

    # 6) FX trigger ancla en valid_from (re-crear la función con NEW.valid_from)
    #    Revisar 20260507_018_costs_engine.py: copiar costs_stamp_fx() cambiando
    #    todas las referencias a NEW.effective_at por NEW.valid_from.
    op.execute("""
        CREATE OR REPLACE FUNCTION costs_stamp_fx() RETURNS trigger AS $$
        DECLARE v_fx uuid;
        BEGIN
          IF NEW.fx_rate_id IS NOT NULL THEN RETURN NEW; END IF;
          IF NEW.currency_origin = 'AED' THEN NEW.fx_rate_id := NULL; RETURN NEW; END IF;
          SELECT fx_rate_at(NEW.currency_origin, 'AED', NEW.valid_from::timestamptz) INTO v_fx;
          IF v_fx IS NULL THEN RAISE EXCEPTION 'fx_rate_not_found_at_effective_at'; END IF;
          NEW.fx_rate_id := v_fx;
          RETURN NEW;
        END $$ LANGUAGE plpgsql;
    """)

    # 7) Dropear status (+ check) y effective_at
    op.execute("ALTER TABLE costs DROP CONSTRAINT IF EXISTS ck_costs_status")
    op.drop_column("costs", "status")
    op.drop_column("costs", "effective_at")


def downgrade() -> None:
    op.add_column("costs", sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("costs", sa.Column("status", sa.String(16), nullable=True))
    op.execute("UPDATE costs SET effective_at = valid_from::timestamptz")
    op.execute("""
        UPDATE costs SET status = CASE
          WHEN valid_to IS NULL OR current_date BETWEEN valid_from AND valid_to
          THEN 'active' ELSE 'superseded' END
    """)
    op.alter_column("costs", "effective_at", nullable=False)
    op.alter_column("costs", "status", nullable=False)
    op.execute("ALTER TABLE costs ADD CONSTRAINT ck_costs_status CHECK (status IN ('active','superseded'))")
    op.execute("ALTER TABLE costs DROP CONSTRAINT IF EXISTS ex_costs_no_overlap")
    op.execute("""CREATE UNIQUE INDEX idx_costs_active_unique_lookup
                  ON costs (sku, scheme_code, supplier_code) WHERE status='active'""")
    # Restaurar costs_stamp_fx con NEW.effective_at (copiar de 018).
    op.drop_column("costs", "valid_to")
    op.drop_column("costs", "valid_from")
```

- [ ] **Step 4: Correr migración + test (pasa)**

Run: `uv run alembic upgrade head` (contra DB fresca) y luego el pytest del Step 2.
Expected: PASS (exclusión rechaza solape; `status`/`effective_at` ausentes).

- [ ] **Step 5: Verificar downgrade reversible**

Run: `uv run alembic downgrade -1 && uv run alembic upgrade head`
Expected: sin error.

- [ ] **Step 6: Commit**

```bash
git add alembic/versions/2026053X_120_costs_validity_ranges.py tests/data/test_costs_validity.py
git commit -m "feat(costos): migracion vigencia por rangos + exclusion GiST"
```

---

## Task 2: Modelo `Cost` — columnas reales + hybrids de compat

**Files:**
- Modify: `mt-pricing-backend/app/db/models/cost.py`
- Test: `mt-pricing-backend/tests/data/test_costs_validity.py` (añadir)

- [ ] **Step 1: Test (falla)** — el modelo expone `valid_from`/`valid_to` y los hybrids legacy.

```python
async def test_model_hybrids(db_session, make_product):
    from app.db.models.cost import Cost
    await make_product("_HYB")
    c = Cost(sku="_HYB", scheme_code="FBA", currency_origin="AED",
             breakdown={}, valid_from=__import__("datetime").date(2026,1,1))
    db_session.add(c); await db_session.flush()
    assert c.effective_at is not None       # hybrid → valid_from
    assert c.status in ("active", "superseded")  # hybrid derivado por fecha
```

- [ ] **Step 2: Correr → FAIL** (el modelo aún tiene columnas `effective_at`/`status`).

- [ ] **Step 3: Editar el modelo** — quitar columnas `effective_at`/`status`, añadir `valid_from`/`valid_to`, y hybrids:

```python
# en class Cost:
valid_from: Mapped[date] = mapped_column(Date, nullable=False)
valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
# (eliminar mapped_column de effective_at y status)

@hybrid_property
def effective_at(self):
    return self.valid_from

@hybrid_property
def status(self):
    from datetime import date as _d
    today = _d.today()
    if self.valid_to is None or (self.valid_from <= today <= self.valid_to):
        return "active"
    return "superseded"

@hybrid_property
def valid_to_compat(self):  # el viejo hybrid `valid_to` ya es columna real ahora
    return self.valid_to
```
> Quitar el viejo hybrid `valid_to` (ahora es columna). Ajustar `__table_args__`: quitar el índice único parcial (lo gestiona la migración) y dejar `idx_costs_sku_scheme`, `idx_costs_effective_at` → renombrar a `idx_costs_valid_from` o crearlo en la migración.

- [ ] **Step 4: Correr → PASS.**

- [ ] **Step 5: Commit**

```bash
git add app/db/models/cost.py tests/data/test_costs_validity.py
git commit -m "feat(costos): modelo Cost con valid_from/valid_to + hybrids legacy"
```

---

## Task 3: Service — `create_cost(valid_from)` con auto-encadenado

**Files:**
- Modify: `mt-pricing-backend/app/services/costs/cost_service.py`
- Test: `mt-pricing-backend/tests/services/costs/test_cost_validity_service.py`

- [ ] **Step 1: Test (falla)**

```python
import datetime as dt
import pytest
pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

async def test_create_chains_previous(db_session, make_product):
    from app.services.costs.cost_service import CostService
    await make_product("_CHAIN")
    svc = CostService(db_session)
    a = await svc.create_cost(sku="_CHAIN", scheme_code="FBA", supplier_code=None,
                              currency_origin="AED", breakdown={"fob_aed": 100},
                              valid_from=dt.date(2026,1,1))
    b = await svc.create_cost(sku="_CHAIN", scheme_code="FBA", supplier_code=None,
                              currency_origin="AED", breakdown={"fob_aed": 120},
                              valid_from=dt.date(2026,6,1))
    await db_session.refresh(a)
    assert a.valid_to == dt.date(2026,5,31)   # cerrado en D-1
    assert b.valid_to is None                 # nueva abierta
```

- [ ] **Step 2: Correr → FAIL** (`create_cost` no acepta `valid_from`/no encadena).

- [ ] **Step 3: Implementar el auto-encadenado** en `cost_service.create_cost`:

```python
async def create_cost(self, *, sku, scheme_code, supplier_code, currency_origin,
                       breakdown, valid_from, actor=None):
    # Cerrar el rango abierto anterior cuyo valid_from < nuevo
    await self.session.execute(text("""
        UPDATE costs SET valid_to = :d_minus_1
         WHERE sku=:sku AND scheme_code=:scheme
           AND coalesce(supplier_code,'')=coalesce(:sup,'')
           AND valid_to IS NULL AND valid_from < :vf
    """), {"d_minus_1": valid_from - timedelta(days=1), "sku": sku,
           "scheme": scheme_code, "sup": supplier_code, "vf": valid_from})
    cost = Cost(sku=sku, scheme_code=scheme_code, supplier_code=supplier_code,
                currency_origin=currency_origin, breakdown=breakdown,
                valid_from=valid_from, valid_to=None, version=1)
    self.session.add(cost)
    await self.session.flush()   # dispara trigger FX + landed; exclusión valida no-solape
    await self.session.refresh(cost)
    return cost
```
> Conservar la validación de `breakdown` contra el template del scheme (reusar `breakdown_validator`). Mantener emisión de audit. Si la inserción cae en medio (valid_from intermedio), la exclusión rechazará el solape → traducir IntegrityError a 4xx en el route.

- [ ] **Step 4: Correr → PASS.**

- [ ] **Step 5: Commit**

```bash
git add app/services/costs/cost_service.py tests/services/costs/test_cost_validity_service.py
git commit -m "feat(costos): auto-encadenado en create_cost"
```

---

## Task 4: Service — `cost_as_of(date)`

**Files:** Modify `cost_service.py`; Test en `test_cost_validity_service.py`.

- [ ] **Step 1: Test (falla)**

```python
async def test_as_of_returns_right_range(db_session, make_product):
    from app.services.costs.cost_service import CostService
    await make_product("_ASOF")
    svc = CostService(db_session)
    await svc.create_cost(sku="_ASOF", scheme_code="FBA", supplier_code=None,
                          currency_origin="AED", breakdown={"fob_aed":100}, valid_from=dt.date(2026,1,1))
    await svc.create_cost(sku="_ASOF", scheme_code="FBA", supplier_code=None,
                          currency_origin="AED", breakdown={"fob_aed":120}, valid_from=dt.date(2026,6,1))
    r1 = await svc.cost_as_of(sku="_ASOF", scheme_code="FBA", supplier_code=None, on=dt.date(2026,3,1))
    r2 = await svc.cost_as_of(sku="_ASOF", scheme_code="FBA", supplier_code=None, on=dt.date(2026,7,1))
    assert r1.valid_from == dt.date(2026,1,1)
    assert r2.valid_from == dt.date(2026,6,1)
```

- [ ] **Step 2: Correr → FAIL.**

- [ ] **Step 3: Implementar**

```python
async def cost_as_of(self, *, sku, scheme_code, supplier_code, on):
    stmt = select(Cost).where(
        Cost.sku == sku, Cost.scheme_code == scheme_code,
        func.coalesce(Cost.supplier_code, "") == (supplier_code or ""),
        Cost.valid_from <= on,
        or_(Cost.valid_to.is_(None), Cost.valid_to >= on),
    )
    return (await self.session.execute(stmt)).scalars().first()
```

- [ ] **Step 4: Correr → PASS. Step 5: Commit** `feat(costos): consulta cost_as_of`.

---

## Task 5: Service — `close_cost` (descatalogar) + corrección in-situ

**Files:** Modify `cost_service.py`; Test en `test_cost_validity_service.py`.

- [ ] **Step 1: Test (falla)** — `close_cost(id, valid_to)` cierra la fila abierta; `update_cost(id, breakdown=...)` muta en sitio sin crear versión.

```python
async def test_close_sets_valid_to(db_session, make_product):
    from app.services.costs.cost_service import CostService
    await make_product("_CLOSE")
    svc = CostService(db_session)
    c = await svc.create_cost(sku="_CLOSE", scheme_code="FBA", supplier_code=None,
                              currency_origin="AED", breakdown={"fob_aed":100}, valid_from=dt.date(2026,1,1))
    await svc.close_cost(cost_id=c.id, valid_to=dt.date(2026,12,31))
    await db_session.refresh(c)
    assert c.valid_to == dt.date(2026,12,31)
```

- [ ] **Step 2: FAIL. Step 3: Implementar** `close_cost` (set valid_to) y revisar `update_cost` para que sea corrección in-situ (set breakdown/valid_from, re-flush dispara FX/landed; no supersede). **Step 4: PASS. Step 5: Commit** `feat(costos): close_cost + correccion in-situ`.

---

## Task 6: Adaptar pricing/consumidores a "vigente hoy" (as-of today)

**Files:**
- Modify: `mt-pricing-backend/app/repositories/pricing.py` (`list_costs`), pricing service, `app/services/costs/cost_service.list_for_sku`, y cualquier `WHERE status='active'`.
- Test: regresión en `tests/services/` o `tests/api/` del pricing.

- [ ] **Step 1: Localizar todos los `status='active'` / `status == "active"`**

Run: `grep -rn "status.*active" app/repositories app/services app/api | grep -i cost`

- [ ] **Step 2: Test de regresión (falla si rompe)** — un test que cree un coste vigente hoy y verifique que el pricing/lookup lo encuentra sin `status`.

```python
async def test_pricing_finds_current_cost_without_status(db_session, make_product):
    from app.services.costs.cost_service import CostService
    await make_product("_PR")
    svc = CostService(db_session)
    await svc.create_cost(sku="_PR", scheme_code="FBA", supplier_code=None,
                          currency_origin="AED", breakdown={"fob_aed":100}, valid_from=dt.date(2026,1,1))
    rows = await svc.list_for_sku("_PR", as_of=dt.date.today())
    assert any(r.scheme_code == "FBA" for r in rows)
```

- [ ] **Step 3: Reemplazar los filtros** `status='active'` por la condición de rango
`valid_from <= :today AND (valid_to IS NULL OR valid_to >= :today)`. Añadir parámetro `as_of` (default hoy) donde aplique. **Step 4: Correr toda la suite de pricing → PASS** (`pytest tests/ -k "pricing or cost"`). **Step 5: Commit** `refactor(costos): consumidores usan coste vigente a fecha (as-of)`.

---

## Task 7: API — endpoints de vigencia

**Files:**
- Modify: `mt-pricing-backend/app/api/routes/costs.py`, schemas de cost.
- Test: `mt-pricing-backend/tests/api/test_costs_validity_api.py`

- [ ] **Step 1: Tests (fallan)** — uno por endpoint (usar el patrón de auth de `tests/api/test_suppliers_crud.py`: seed user con `costs:read`/`costs:write`, JWT HS256):
  - `POST /costs` con `valid_from` → 201, encadena.
  - `GET /costs/as-of?sku=&scheme_code=&date=` → 200 con la fila correcta; 404 si no hay.
  - `POST /costs/{id}/close` → 200, set valid_to.
  - `PATCH /costs/{id}` → 200 corrección.
  - `GET /costs?valid_on=YYYY-MM-DD` → solo costes vigentes a esa fecha.
  - `GET /costs?include_history=true&sku=&scheme=` → cadena ordenada por valid_from.

```python
# ejemplo (1 de varios)
async def test_post_cost_with_valid_from(client, db_session, seed_costs_user):
    headers = seed_costs_user  # helper que devuelve headers con costs:write
    body = {"sku": "_API1", "scheme_code": "FBA", "currency_origin": "AED",
            "breakdown": {"fob_aed": 100}, "valid_from": "2026-01-01"}
    r = await client.post("/api/v1/costs", json=body, headers=headers)
    assert r.status_code == 201, r.text
    assert r.json()["cost"]["valid_to"] is None
```

- [ ] **Step 2: Correr → FAIL.**

- [ ] **Step 3: Implementar los endpoints** en `routes/costs.py`:
  - Cambiar el body de `POST /costs` a `CostCreate{ ..., valid_from: date }` (quitar `effective_at`).
  - `GET /costs/as-of` → llama `cost_service.cost_as_of`.
  - `POST /costs/{id}/close` → `close_cost`.
  - `PATCH /costs/{id}` → corrección in-situ.
  - `GET /costs` → añadir `valid_on: date | None`, `include_history: bool=False`, `order`.
  - `GET /products/{sku}/costs` y `/costs/missing` → añadir `as_of: date | None` (default hoy).
  - Traducir `IntegrityError` de exclusión → `ProblemDetails` 409 `cost_overlap`.
  - Actualizar schemas: `valid_from`/`valid_to` en Response; quitar `status`/`effective_at` de inputs (dejar en output vía hybrid si algún consumer los lee).

- [ ] **Step 4: Correr → PASS** (`pytest tests/api/test_costs_validity_api.py`).

- [ ] **Step 5: Commit** `feat(costos): API de vigencia (as-of, close, valid_on)`.

---

## Task 8: Importador — columna `valid_from` + filas futuras

**Files:** Modify `app/services/importer_costs/{parser,differ,applier}.py`; Test en `tests/services/` (o el test existente del importer).

- [ ] **Step 1: Test (falla)** — un Excel/lista con `valid_from` (incl. fecha futura) se aplica vía `create_cost` y encadena; el `differ` compara contra `cost_as_of(valid_from)`.
- [ ] **Step 2: FAIL. Step 3: Implementar** — `parser` reconoce columna `valid_from`; `differ` usa `cost_as_of(valid_from)` para decidir CREATE/NO_CHANGE; `applier` llama `create_cost(valid_from=...)`. **Step 4: PASS. Step 5: Commit** `feat(costos): importador con valid_from`.

---

## Task 9: Regenerar OpenAPI

**Files:** `_bmad-output/planning-artifacts/mt-api-contract-openapi.json`

- [ ] **Step 1:** `cd mt-pricing-backend && uv run python -m app.scripts.export_openapi`
- [ ] **Step 2:** `git add _bmad-output/planning-artifacts/mt-api-contract-openapi.json`
- [ ] **Step 3: Commit** `chore(costos): regenerar OpenAPI spec`.

---

## Cierre

- [ ] Correr la suite backend completa contra DB fresca tipo-CI; confirmar 0 regresiones nuevas (los ~37 fallos pre-existentes de entorno RLS/fx no cuentan, ver guía de pruebas §3).
- [ ] Verificar `ruff check` + `ruff format --check` + `mypy app/` limpios.
- [ ] Abrir PR `feat(costos): vigencia por rangos backend` con `## Summary` + `## Test plan`.
- [ ] Plan 2 (frontend del módulo) en un PR posterior.
