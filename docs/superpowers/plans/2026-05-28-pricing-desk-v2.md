# Pricing Desk v2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cerrar las 5 funcionalidades pendientes del Pricing Desk: carga inicial desde el HTML (232 SKUs reales), propuesta de precios al flujo de aprobación con selección por checkbox, UI de import Excel, modal comparador de 3 esquemas y escenarios A/B persistidos.

**Architecture:** Backend gana 2 endpoints nuevos (`POST /prices/propose-selected` + `pricing_scenarios` CRUD) y un script one-shot de seed. Frontend gana 4 componentes nuevos (Excel uploader, scheme comparator modal, scenarios slot UI, row checkbox + bulk action) + 2 hooks. Sin migraciones — todas las tablas necesarias ya existen.

**Tech Stack:** Backend: Python 3.11 + FastAPI + SQLAlchemy 2.0 async + BeautifulSoup4 (parsing HTML). Frontend: Next.js 16 + React 19 + TanStack Table + shadcn Dialog + openapi-typescript.

**Prerequisitos:**
- PR #128 merged a `main` (backend del motor + 13 endpoints)
- PR #130 open / merged (frontend del Pricing Desk básico)
- Datos seed actuales en BD: ruta `es_to_uae`, fees Amazon UAE + Noon UAE, schemes, márgenes por familia

**Spec de referencia:** `docs/superpowers/specs/2026-05-28-channel-pricing-engine-design.md` (secciones 8 y 9 — el flujo de aprobación)

---

## Estructura de ficheros

```
mt-pricing-backend/
├── app/
│   ├── scripts/
│   │   └── seed_amazon_uae_from_html.py            ← CREAR (Task 1, one-shot)
│   ├── services/
│   │   └── pricing/
│   │       └── price_proposer.py                   ← CREAR (Task 2, lógica propose)
│   ├── api/
│   │   └── routes/
│   │       └── channel_pricing.py                  ← MODIFICAR (Tasks 2 y 6, +3 endpoints)
│   └── schemas/
│       └── channel_pricing.py                      ← MODIFICAR (+3 schemas)
└── tests/
    ├── scripts/
    │   └── test_seed_amazon_uae_from_html.py       ← CREAR (Task 1)
    ├── services/pricing/
    │   └── test_price_proposer.py                  ← CREAR (Task 2)
    └── api/
        └── test_channel_pricing.py                 ← MODIFICAR (+tests scenarios/propose)

mt-pricing-frontend/
├── lib/
│   ├── api/
│   │   ├── types.ts                                ← REGENERAR (Task 7)
│   │   └── endpoints/
│   │       └── pricing-desk.ts                     ← MODIFICAR (+ propose + scenarios)
│   └── hooks/pricing-desk/
│       ├── use-propose-prices.ts                   ← CREAR (Task 4)
│       └── use-scenarios.ts                        ← CREAR (Task 6)
├── app/(app)/pricing-desk/
│   ├── page.tsx                                    ← MODIFICAR (Tasks 4, 5, 6)
│   └── _components/
│       ├── catalog-table.tsx                       ← MODIFICAR (checkbox col)
│       ├── propose-button.tsx                      ← CREAR (Task 4)
│       ├── scheme-comparator-modal.tsx             ← CREAR (Task 5)
│       ├── import-excel-section.tsx                ← CREAR (Task 3)
│       └── scenarios-section.tsx                   ← CREAR (Task 6)
└── tests/e2e/
    └── 23-pricing-desk.spec.ts                     ← MODIFICAR (+ scenarios + propose)
```

---

## Task 1: Script seed one-shot del HTML del Pricing Desk

Objetivo: parsear `Documentos referencia de articulos/Herramientas Manuales/MT_Amazon_UAE_App_Pricing_Desk_260526_1947.html`, extraer la constante JavaScript `DATA` con los 232 SKUs y popular `products` (pe_eur, catalog_pvp_eur, weight) + `channel_product_logistics` para Amazon UAE.

**Files:**
- Create: `mt-pricing-backend/app/scripts/seed_amazon_uae_from_html.py`
- Create: `mt-pricing-backend/tests/scripts/test_seed_amazon_uae_from_html.py`
- Create: `mt-pricing-backend/tests/scripts/__init__.py` (si no existe)

**Notas de datos relevantes:**
- Cada SKU del HTML tiene la forma `{"s":"4222015","n":"...","f":"VÁLVULAS DE LATÓN","pe":3.07,"v":41.82,"peso":0.21,"fba_env":1.5,"fba_alm":0.028,"fba_fee":7.2,"rec":"fba"}`.
- `pe` (precio compra MT en EUR) → `products.pe_eur`.
- `v` (techo en AED, ya convertido) → `catalog_pvp_eur = v / fx_rate` (usar fx_rate de `trade_route_params` para `es_to_uae`).
- `peso` → `products.weight`.
- `fba_env`/`fba_alm`/`fba_fee` → `channel_product_logistics.inbound_fee_aed`/`storage_fee_aed`/`fulfillment_fee_aed`.
- `rec` ("fba" o "easyship") → `channel_product_logistics.default_scheme` (mapear: fba→canal_full, easyship→canal_lastmile).
- `units_per_box` no está en el HTML → mantener default `1`.

- [ ] **1.1 Test que aísla la función de parsing**

```python
# tests/scripts/test_seed_amazon_uae_from_html.py
"""Test parsing of the Pricing Desk standalone HTML."""
from pathlib import Path

import pytest

from app.scripts.seed_amazon_uae_from_html import extract_data_array


HTML_SAMPLE = """<html><body><script>
const DATA = [{"s":"4222015","n":"VALVE","f":"LATON","pe":3.07,"v":41.82,"peso":0.21,"fba_env":1.5,"fba_alm":0.028,"fba_fee":7.2,"rec":"fba"},
{"s":"5120020","n":"JOINT","f":"MANGUITOS","pe":7.81,"v":77.97,"peso":0.7,"fba_env":1.8,"fba_alm":112.08,"fba_fee":8.5,"rec":"easyship"}];
const FAMS=[];
</script></body></html>"""


def test_extract_data_array_returns_list_of_dicts():
    rows = extract_data_array(HTML_SAMPLE)
    assert len(rows) == 2
    assert rows[0]["s"] == "4222015"
    assert rows[0]["pe"] == 3.07
    assert rows[0]["rec"] == "fba"


def test_extract_data_array_raises_when_const_missing():
    with pytest.raises(ValueError, match="DATA"):
        extract_data_array("<html>no script here</html>")
```

- [ ] **1.2 Run test → expect FAIL (module missing)**

```bash
docker exec mt-backend sh -c "cd /app && python -m pytest tests/scripts/test_seed_amazon_uae_from_html.py -v --no-cov 2>&1" | tail -10
```
Expected: `ModuleNotFoundError: No module named 'app.scripts.seed_amazon_uae_from_html'`

- [ ] **1.3 Implementar el parser**

```python
# mt-pricing-backend/app/scripts/seed_amazon_uae_from_html.py
"""One-shot seed: parse the standalone Pricing Desk HTML and populate the DB.

Reads `Documentos referencia de articulos/Herramientas Manuales/MT_Amazon_UAE_App_Pricing_Desk_260526_1947.html`
and inserts/updates:
  - products.pe_eur, catalog_pvp_eur, weight
  - channel_product_logistics (inbound, storage, fulfillment, default_scheme)

Run once:
    docker exec mt-backend python /app/app/scripts/seed_amazon_uae_from_html.py

Idempotent: uses INSERT ... ON CONFLICT DO UPDATE.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal

DATA_RE = re.compile(r"const\s+DATA\s*=\s*(\[.*?\]);", re.DOTALL)
HTML_DEFAULT_PATH = Path(
    "/app/Documentos referencia de articulos/Herramientas Manuales/"
    "MT_Amazon_UAE_App_Pricing_Desk_260526_1947.html"
)

SCHEME_MAP = {"fba": "canal_full", "easyship": "canal_lastmile"}


def extract_data_array(html: str) -> list[dict]:
    """Extract and parse the const DATA = [...] JavaScript array as Python."""
    match = DATA_RE.search(html)
    if not match:
        raise ValueError("Could not find 'const DATA = [...]' in HTML")
    raw = match.group(1)
    return json.loads(raw)


async def seed(session: AsyncSession, html_path: Path = HTML_DEFAULT_PATH) -> dict:
    """Insert/update products + channel_product_logistics from HTML data."""
    html = html_path.read_text(encoding="utf-8")
    rows = extract_data_array(html)

    # Resolve channel_id for amazon_uae
    channel_id = (
        await session.execute(text("SELECT id FROM channels WHERE code = 'amazon_uae'"))
    ).scalar_one()

    # Resolve fx_rate for es_to_uae (to convert techo AED → pvp EUR)
    fx_rate = (
        await session.execute(
            text("SELECT fx_rate FROM trade_route_params WHERE route_code = 'es_to_uae'")
        )
    ).scalar_one()
    fx_rate = Decimal(str(fx_rate))

    upserted_products = 0
    upserted_logistics = 0
    skipped = []

    for row in rows:
        sku = row["s"]
        pe_eur = Decimal(str(row["pe"]))
        techo_aed = Decimal(str(row["v"]))
        catalog_pvp_eur = (techo_aed / fx_rate).quantize(Decimal("0.0001"))
        weight = Decimal(str(row["peso"]))
        default_scheme = SCHEME_MAP.get(row.get("rec", "fba"), "canal_full")

        # Update product only if SKU exists (don't create new products from this script)
        result = await session.execute(
            text("""
                UPDATE products
                SET pe_eur = :pe_eur,
                    catalog_pvp_eur = :catalog_pvp_eur,
                    weight = :weight
                WHERE sku = :sku
            """),
            {
                "pe_eur": pe_eur,
                "catalog_pvp_eur": catalog_pvp_eur,
                "weight": weight,
                "sku": sku,
            },
        )
        if result.rowcount == 0:
            skipped.append({"sku": sku, "reason": "not in products table"})
            continue
        upserted_products += 1

        # Upsert channel_product_logistics
        await session.execute(
            text("""
                INSERT INTO channel_product_logistics
                    (product_sku, channel_id, inbound_fee_aed, storage_fee_aed,
                     fulfillment_fee_aed, default_scheme)
                VALUES
                    (:sku, :channel_id, :inbound, :storage, :fulfillment, :scheme)
                ON CONFLICT (product_sku, channel_id) DO UPDATE SET
                    inbound_fee_aed = EXCLUDED.inbound_fee_aed,
                    storage_fee_aed = EXCLUDED.storage_fee_aed,
                    fulfillment_fee_aed = EXCLUDED.fulfillment_fee_aed,
                    default_scheme = EXCLUDED.default_scheme,
                    updated_at = now()
            """),
            {
                "sku": sku,
                "channel_id": channel_id,
                "inbound": Decimal(str(row["fba_env"])),
                "storage": Decimal(str(row["fba_alm"])),
                "fulfillment": Decimal(str(row["fba_fee"])),
                "scheme": default_scheme,
            },
        )
        upserted_logistics += 1

    await session.commit()
    return {
        "total_rows": len(rows),
        "products_updated": upserted_products,
        "logistics_upserted": upserted_logistics,
        "skipped": skipped,
    }


async def main() -> None:
    async with AsyncSessionLocal() as session:
        report = await seed(session)
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **1.4 Run parsing test → expect PASS**

```bash
docker exec mt-backend sh -c "cd /app && python -m pytest tests/scripts/test_seed_amazon_uae_from_html.py -v --no-cov 2>&1" | tail -10
```
Expected: 2 passed.

- [ ] **1.5 Smoke test del script real contra BD (verifica que cargue los 232 SKUs)**

```bash
docker exec mt-backend python /app/app/scripts/seed_amazon_uae_from_html.py 2>&1 | tail -20
```

Expected output (JSON):
- `"total_rows": 232`
- `"products_updated"` cerca de 232 (puede ser menos si algunos SKUs aún no están en la tabla `products` — eso lo veremos en `skipped`)

Si `products_updated` es 0 (todos los SKUs están en `skipped`), significa que el catálogo no se ha importado todavía y el script no tiene productos que actualizar. En ese caso, reporta DONE_WITH_CONCERNS y el equipo deberá importar primero el catálogo.

- [ ] **1.6 Verificar que los datos llegaron**

```bash
docker exec mt-backend python -c "
import asyncio
from app.db.session import AsyncSessionLocal
from sqlalchemy import text
async def check():
    async with AsyncSessionLocal() as s:
        n_logistics = (await s.execute(text(\"SELECT COUNT(*) FROM channel_product_logistics WHERE channel_id = (SELECT id FROM channels WHERE code='amazon_uae')\"))).scalar()
        n_products_with_pe = (await s.execute(text('SELECT COUNT(*) FROM products WHERE pe_eur IS NOT NULL'))).scalar()
        print(f'logistics amazon_uae: {n_logistics}')
        print(f'products with pe_eur: {n_products_with_pe}')
asyncio.run(check())
"
```
Expected: ambos > 0 (idealmente ~232 o lo que se haya conseguido en seed).

- [ ] **1.7 Commit**

```bash
git add mt-pricing-backend/app/scripts/seed_amazon_uae_from_html.py \
        mt-pricing-backend/tests/scripts/
git commit -m "feat(pricing-desk): one-shot seed script from Pricing Desk HTML (232 SKUs)"
```

---

## Task 2: Backend — endpoint `POST /pricing/{channel_code}/prices/propose-selected`

Crea registros en la tabla `prices` con `status='pending_review'` para la lista de SKUs que el usuario marca con checkbox. El precio propuesto es el actual del Pricing Desk (calculado con el motor + override de margen efectivo).

**Files:**
- Create: `mt-pricing-backend/app/services/pricing/price_proposer.py`
- Create: `mt-pricing-backend/tests/services/pricing/test_price_proposer.py`
- Modify: `mt-pricing-backend/app/api/routes/channel_pricing.py` (+ endpoint)
- Modify: `mt-pricing-backend/app/schemas/channel_pricing.py` (+ schemas)

- [ ] **2.1 Definir los schemas Pydantic**

Añadir al final de `mt-pricing-backend/app/schemas/channel_pricing.py`, ANTES del `__all__`:

```python
# ── Propose selected ──────────────────────────────────────────────────

class ProposeSelectedRequest(BaseModel):
    skus: list[str] = Field(min_length=1, max_length=500)
    selling_model: SellingModel = SellingModel.B2C
    notes: str | None = None


class ProposeSelectedItemResult(BaseModel):
    sku: str
    status: str  # "proposed" | "skipped" | "error"
    price_id: UUID | None = None
    selling_price_aed: float | None = None
    reason: str | None = None


class ProposeSelectedResult(BaseModel):
    total_requested: int
    proposed: int
    skipped: int
    errors: int
    items: list[ProposeSelectedItemResult]
```

Añadir los 3 nombres al `__all__` lexicográficamente.

- [ ] **2.2 Test del servicio**

```python
# mt-pricing-backend/tests/services/pricing/test_price_proposer.py
"""Tests for PriceProposer service."""
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_propose_creates_pending_review_rows(db_session, amazon_uae_channel_id):
    """Proposing 2 SKUs creates 2 rows in prices with status=pending_review."""
    from app.services.pricing.price_proposer import PriceProposer
    from app.db.enums import SellingModel

    # Seed two products + logistics (minimal — bypass Product creation via raw SQL)
    sku1, sku2 = "PROP-001", "PROP-002"
    family_id = (await db_session.execute(text("SELECT id FROM families LIMIT 1"))).scalar_one()
    brand_id = (await db_session.execute(text("SELECT id FROM brands LIMIT 1"))).scalar_one()
    for sku in (sku1, sku2):
        await db_session.execute(
            text("""
                INSERT INTO products (sku, family, family_id, brand_id, pe_eur, catalog_pvp_eur, weight, ceiling_basis, manual_locked_fields, data_quality)
                VALUES (:sku, 'test', :fam, :brand, 3.07, 9.77, 0.21, 'catalog_pvp', '{}', 'partial')
                ON CONFLICT DO NOTHING
            """),
            {"sku": sku, "fam": family_id, "brand": brand_id},
        )
        await db_session.execute(
            text("""
                INSERT INTO channel_product_logistics
                    (product_sku, channel_id, inbound_fee_aed, storage_fee_aed, fulfillment_fee_aed, default_scheme)
                VALUES (:sku, :ch, 1.5, 0.028, 7.2, 'canal_full')
                ON CONFLICT (product_sku, channel_id) DO NOTHING
            """),
            {"sku": sku, "ch": amazon_uae_channel_id},
        )
    await db_session.flush()

    result = await PriceProposer(db_session).propose(
        channel_id=amazon_uae_channel_id,
        skus=[sku1, sku2],
        selling_model=SellingModel.B2C,
        notes="test batch",
        proposed_by="tester@example.com",
    )

    assert result.total_requested == 2
    assert result.proposed == 2
    assert result.errors == 0

    # Verify prices rows
    pending = (await db_session.execute(
        text("SELECT COUNT(*) FROM prices WHERE product_sku IN (:s1, :s2) AND status = 'pending_review'"),
        {"s1": sku1, "s2": sku2},
    )).scalar()
    assert pending == 2


async def test_propose_skips_sku_without_logistics(db_session, amazon_uae_channel_id):
    """SKU without channel_product_logistics is reported as skipped, not error."""
    from app.services.pricing.price_proposer import PriceProposer
    from app.db.enums import SellingModel

    # Product without logistics row
    sku = "PROP-NOLO"
    family_id = (await db_session.execute(text("SELECT id FROM families LIMIT 1"))).scalar_one()
    brand_id = (await db_session.execute(text("SELECT id FROM brands LIMIT 1"))).scalar_one()
    await db_session.execute(
        text("""
            INSERT INTO products (sku, family, family_id, brand_id, pe_eur, catalog_pvp_eur, weight, ceiling_basis, manual_locked_fields, data_quality)
            VALUES (:sku, 'test', :fam, :brand, 3.07, 9.77, 0.21, 'catalog_pvp', '{}', 'partial')
            ON CONFLICT DO NOTHING
        """),
        {"sku": sku, "fam": family_id, "brand": brand_id},
    )
    await db_session.flush()

    result = await PriceProposer(db_session).propose(
        channel_id=amazon_uae_channel_id,
        skus=[sku],
        selling_model=SellingModel.B2C,
        proposed_by="tester@example.com",
    )
    assert result.skipped == 1
    assert result.items[0].status == "skipped"
    assert "logistics" in (result.items[0].reason or "").lower()
```

- [ ] **2.3 Implementar el servicio**

```python
# mt-pricing-backend/app/services/pricing/price_proposer.py
"""Propose computed prices to the approval workflow.

Takes a list of SKUs + selling_model, calls the engine via ParameterLoader +
ChannelOptimizer, and inserts the resulting prices into the `prices` table
with status='pending_review'. The breakdown JSONB carries the full cost
detail for auditability.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import SellingModel
from app.schemas.channel_pricing import (
    ProposeSelectedItemResult,
    ProposeSelectedResult,
)
from app.services.pricing.loader import ParameterLoader
from app.services.pricing.optimizer import ChannelOptimizer


class PriceProposer:
    """Propose prices in bulk for the approval workflow."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def propose(
        self,
        channel_id: uuid.UUID,
        skus: list[str],
        selling_model: SellingModel,
        proposed_by: str,
        notes: str | None = None,
    ) -> ProposeSelectedResult:
        loader = ParameterLoader(self._session)
        route, fees, schemes = await loader.load_route_and_fees(channel_id)
        products = await loader.load_product_data(channel_id, skus=skus)
        margins = await loader.load_effective_margins(channel_id, selling_model, skus)

        # Resolve scheme_code (the `schemes` reference table) — every Pricing Desk
        # proposal uses scheme_code='FBA' by convention, since the canal_full path
        # is the most common. The fulfillment scheme is captured in breakdown.scheme.
        scheme_code = "FBA"

        items: list[ProposeSelectedItemResult] = []
        products_by_sku = {p.sku: p for p in products}

        for sku in skus:
            product = products_by_sku.get(sku)
            if product is None:
                items.append(
                    ProposeSelectedItemResult(
                        sku=sku, status="skipped",
                        reason="product not found or has no channel_product_logistics",
                    )
                )
                continue

            margin = margins.get(sku, Decimal("12"))
            if selling_model == SellingModel.B2C:
                best = ChannelOptimizer.best_scheme_b2c(product, route, fees, schemes, margin)
            else:
                best = ChannelOptimizer.best_scheme_b2b(product, route, fees, schemes, margin)

            if best is None or best.selling_price_aed == Decimal("Infinity"):
                items.append(
                    ProposeSelectedItemResult(
                        sku=sku, status="error",
                        reason="no feasible scheme at current parameters",
                    )
                )
                continue

            price_id = uuid.uuid4()
            await self._session.execute(
                text("""
                    INSERT INTO prices
                        (id, product_sku, channel_id, scheme_code, currency, amount,
                         margin_pct, status, proposed_by, proposed_at, breakdown, notes)
                    VALUES
                        (:id, :sku, :ch, :scheme_code, 'AED', :amount,
                         :margin, 'pending_review', :who, now(), CAST(:breakdown AS jsonb), :notes)
                """),
                {
                    "id": price_id,
                    "sku": sku,
                    "ch": channel_id,
                    "scheme_code": scheme_code,
                    "amount": best.selling_price_aed,
                    "margin": best.margin_pct,
                    "who": proposed_by,
                    "notes": notes,
                    "breakdown": best.breakdown.to_dict() | {
                        "selling_model": selling_model.value,
                        "fulfillment_scheme": best.fulfillment_scheme.value,
                        "scheme_label": best.scheme_label,
                        "ceiling_aed": str(best.ceiling_aed),
                        "is_publishable": best.is_publishable,
                        "signal": best.signal,
                    },
                },
            )
            items.append(
                ProposeSelectedItemResult(
                    sku=sku, status="proposed",
                    price_id=price_id,
                    selling_price_aed=float(best.selling_price_aed),
                )
            )

        await self._session.commit()
        return ProposeSelectedResult(
            total_requested=len(skus),
            proposed=sum(1 for i in items if i.status == "proposed"),
            skipped=sum(1 for i in items if i.status == "skipped"),
            errors=sum(1 for i in items if i.status == "error"),
            items=items,
        )
```

> Si la `prices` tabla actual no tiene una columna `notes`, omitir el campo y la condición. Verificar con `\d prices` o consultando la migración existente antes de implementar.

- [ ] **2.4 Verificar columnas reales de `prices`**

```bash
docker exec mt-backend python -c "
import asyncio
from app.db.session import AsyncSessionLocal
from sqlalchemy import text
async def check():
    async with AsyncSessionLocal() as s:
        cols = (await s.execute(text(\"SELECT column_name FROM information_schema.columns WHERE table_name='prices' ORDER BY ordinal_position\"))).scalars().all()
        print(cols)
asyncio.run(check())
"
```

Si `notes` no existe, eliminar de la query SQL (y del schema). Mismo para `proposed_at` y `proposed_by` — usar los nombres reales.

- [ ] **2.5 Run service tests → expect PASS**

```bash
docker exec mt-backend sh -c "cd /app && python -m pytest tests/services/pricing/test_price_proposer.py -v --no-cov 2>&1" | tail -15
```
Expected: 2 passed.

- [ ] **2.6 Añadir el endpoint REST**

En `mt-pricing-backend/app/api/routes/channel_pricing.py`, después de `apply_optimization`, añadir:

```python
@router.post(
    "/prices/propose-selected",
    operation_id="proposePricesSelected",
    response_model=ProposeSelectedResult,
    dependencies=[Depends(require_permissions("prices:propose"))],
)
async def propose_prices_selected(
    channel_code: str,
    body: ProposeSelectedRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[Any, Depends(get_current_user)],   # adjust to actual dep
):
    """Propose prices for selected SKUs into the approval flow."""
    from app.services.pricing.price_proposer import PriceProposer

    channel_id = await _resolve_channel_id(channel_code, session)
    proposer = PriceProposer(session)
    return await proposer.propose(
        channel_id=channel_id,
        skus=body.skus,
        selling_model=body.selling_model,
        proposed_by=getattr(user, "email", "system"),
        notes=body.notes,
    )
```

Asegurar imports en la cabecera del fichero: `from app.schemas.channel_pricing import ProposeSelectedRequest, ProposeSelectedResult`.

- [ ] **2.7 Test API integration**

Añadir a `mt-pricing-backend/tests/api/test_channel_pricing.py`:

```python
async def test_propose_selected_creates_pending_review_prices(
    cp_client, amazon_uae_channel_id
):
    """POST /prices/propose-selected returns proposed count and inserts prices."""
    resp = await cp_client.post(
        "/api/v1/pricing/amazon_uae/prices/propose-selected",
        json={"skus": ["4222015"], "selling_model": "b2c"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_requested"] == 1
    # Either proposed or skipped — both are valid depending on seed state
    assert data["proposed"] + data["skipped"] + data["errors"] == 1
```

- [ ] **2.8 Run API tests → expect PASS**

```bash
docker exec mt-backend sh -c "cd /app && python -m pytest tests/api/test_channel_pricing.py -v --no-cov 2>&1" | tail -20
```

- [ ] **2.9 Regenerar OpenAPI spec**

```bash
docker exec mt-backend sh -c "cd /app && python -m app.scripts.export_openapi" 2>&1 | tail -3
docker cp mt-backend:/app/_bmad-output/planning-artifacts/mt-api-contract-openapi.json \
  mt-pricing-backend/_bmad-output/planning-artifacts/mt-api-contract-openapi.json
```

- [ ] **2.10 Commit**

```bash
git add mt-pricing-backend/app/services/pricing/price_proposer.py \
        mt-pricing-backend/app/schemas/channel_pricing.py \
        mt-pricing-backend/app/api/routes/channel_pricing.py \
        mt-pricing-backend/tests/services/pricing/test_price_proposer.py \
        mt-pricing-backend/tests/api/test_channel_pricing.py \
        mt-pricing-backend/_bmad-output/planning-artifacts/mt-api-contract-openapi.json
git commit -m "feat(pricing-desk): POST /prices/propose-selected for bulk approval workflow"
```

---

## Task 3: Frontend — UI de importación Excel en panel lateral

**Files:**
- Create: `mt-pricing-frontend/app/(app)/pricing-desk/_components/import-excel-section.tsx`
- Modify: `mt-pricing-frontend/lib/hooks/pricing-desk/` (añadir hooks de import)
- Modify: `mt-pricing-frontend/app/(app)/pricing-desk/_components/side-panel.tsx` (insertar la nueva sección)

- [ ] **3.1 Hook de import**

Crear `mt-pricing-frontend/lib/hooks/pricing-desk/use-import.ts`:

```typescript
"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { pricingDeskApi } from "@/lib/api/endpoints/pricing-desk";

export function useImportCatalog(channelCode: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, confirm }: { file: File; confirm: boolean }) =>
      pricingDeskApi.importCatalog(channelCode, file, confirm),
    onSuccess: (_data, { confirm }) => {
      if (confirm) {
        queryClient.invalidateQueries({ queryKey: ["pricing-desk", "catalog", channelCode] });
      }
    },
  });
}

export function useImportLogistics(channelCode: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, confirm }: { file: File; confirm: boolean }) =>
      pricingDeskApi.importLogistics(channelCode, file, confirm),
    onSuccess: (_data, { confirm }) => {
      if (confirm) {
        queryClient.invalidateQueries({ queryKey: ["pricing-desk", "catalog", channelCode] });
      }
    },
  });
}
```

- [ ] **3.2 Componente `import-excel-section.tsx`**

```tsx
// mt-pricing-frontend/app/(app)/pricing-desk/_components/import-excel-section.tsx
"use client";

import { useRef, useState } from "react";
import { useImportCatalog, useImportLogistics } from "@/lib/hooks/pricing-desk/use-import";
import type { CatalogImportResult } from "@/lib/api/endpoints/pricing-desk";

interface Props {
  channelCode: string;
}

type Mode = "catalog" | "logistics";

export function ImportExcelSection({ channelCode }: Props) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<Mode>("catalog");
  const [preview, setPreview] = useState<CatalogImportResult | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const catalogImport = useImportCatalog(channelCode);
  const logisticsImport = useImportLogistics(channelCode);

  const isPending = catalogImport.isPending || logisticsImport.isPending;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    setSelectedFile(file);
    setPreview(null);
  };

  const runPreview = async () => {
    if (!selectedFile) return;
    const fn = mode === "catalog" ? catalogImport : logisticsImport;
    const result = await fn.mutateAsync({ file: selectedFile, confirm: false });
    setPreview(result as CatalogImportResult);
  };

  const confirmImport = async () => {
    if (!selectedFile) return;
    const fn = mode === "catalog" ? catalogImport : logisticsImport;
    await fn.mutateAsync({ file: selectedFile, confirm: true });
    setSelectedFile(null);
    setPreview(null);
    if (fileInput.current) fileInput.current.value = "";
  };

  return (
    <section className="border-b border-mt-border p-3">
      <div className="mt-mono mb-2 text-xs font-semibold uppercase tracking-wider text-mt-ink">
        ⬆ Importar Excel
      </div>

      <div className="mb-2 flex gap-1">
        {(["catalog", "logistics"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => {
              setMode(m);
              setPreview(null);
              setSelectedFile(null);
              if (fileInput.current) fileInput.current.value = "";
            }}
            className={
              "flex-1 rounded px-2 py-1 text-[10px] font-bold uppercase tracking-wider transition " +
              (mode === m
                ? "bg-mt-brand text-white"
                : "bg-mt-surface-3 text-mt-ink-2 hover:bg-mt-brand-soft")
            }
          >
            {m === "catalog" ? "Catálogo" : "Logística"}
          </button>
        ))}
      </div>

      <input
        ref={fileInput}
        type="file"
        accept=".xlsx,.xls"
        onChange={handleFileChange}
        className="mb-2 w-full text-xs file:mr-2 file:rounded file:border-0 file:bg-mt-brand file:px-2 file:py-1 file:text-xs file:font-semibold file:text-white hover:file:bg-mt-brand-deep"
      />

      <div className="flex gap-1">
        <button
          type="button"
          onClick={runPreview}
          disabled={!selectedFile || isPending}
          className="flex-1 rounded border border-mt-border bg-white px-2 py-1 text-xs font-semibold text-mt-brand-deep hover:bg-mt-brand-soft disabled:opacity-50"
        >
          {isPending && !preview ? "Procesando…" : "Vista previa"}
        </button>
        <button
          type="button"
          onClick={confirmImport}
          disabled={!preview || isPending}
          className="flex-1 rounded bg-mt-success px-2 py-1 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50"
        >
          Confirmar
        </button>
      </div>

      {preview && (
        <div className="mt-2 rounded border border-mt-border bg-mt-surface-2 p-2 text-[11px]">
          <div className="font-bold text-mt-ink">
            {preview.total_rows} filas — {preview.upserted ?? 0} válidas · {preview.errors.length} errores
          </div>
          {preview.errors.length > 0 && (
            <ul className="mt-1 max-h-32 overflow-auto">
              {preview.errors.slice(0, 5).map((e, i) => (
                <li key={i} className="text-mt-danger">
                  • Fila {(e as { row?: number }).row ?? "?"} ({(e as { sku?: string }).sku}):{" "}
                  {(e as { error?: string }).error}
                </li>
              ))}
              {preview.errors.length > 5 && (
                <li className="text-mt-ink-3">… y {preview.errors.length - 5} más</li>
              )}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
```

- [ ] **3.3 Insertar la sección en `side-panel.tsx`**

Modificar `mt-pricing-frontend/app/(app)/pricing-desk/_components/side-panel.tsx` para añadir `<ImportExcelSection>` entre `OptimizeSection` y el final del aside:

```tsx
import { ImportExcelSection } from "./import-excel-section";
// ...
<OptimizeSection ... />
<ImportExcelSection channelCode={channelCode} />
```

- [ ] **3.4 Verificar compilación**

```bash
cd mt-pricing-frontend && pnpm tsc --noEmit 2>&1 | grep "import-excel\|side-panel\|use-import" | head -10
```
Expected: sin errores.

- [ ] **3.5 Smoke test**

```bash
docker restart mt-frontend && sleep 4
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/pricing-desk
```
Expected: 200/302/307.

- [ ] **3.6 Commit**

```bash
git add mt-pricing-frontend/app/\(app\)/pricing-desk/_components/import-excel-section.tsx \
        mt-pricing-frontend/app/\(app\)/pricing-desk/_components/side-panel.tsx \
        mt-pricing-frontend/lib/hooks/pricing-desk/use-import.ts
git commit -m "feat(pricing-desk): import Excel UI in side panel (catalog + logistics)"
```

---

## Task 4: Frontend — Checkboxes en tabla + botón "Proponer precios seleccionados"

**Files:**
- Create: `mt-pricing-frontend/app/(app)/pricing-desk/_components/propose-button.tsx`
- Create: `mt-pricing-frontend/lib/hooks/pricing-desk/use-propose-prices.ts`
- Modify: `mt-pricing-frontend/lib/api/endpoints/pricing-desk.ts` (+ proposeSelected)
- Modify: `mt-pricing-frontend/app/(app)/pricing-desk/_components/catalog-table.tsx` (col checkbox)
- Modify: `mt-pricing-frontend/app/(app)/pricing-desk/page.tsx` (selección global)

- [ ] **4.1 Añadir método en el wrapper API**

Añadir en `mt-pricing-frontend/lib/api/endpoints/pricing-desk.ts`, en el objeto `pricingDeskApi`:

```typescript
// Inside pricingDeskApi object, between applyOptimization and importCatalog:

/** POST /pricing/{channel_code}/prices/propose-selected */
async proposeSelected(
  channelCode: string,
  body: { skus: string[]; selling_model: SellingModel; notes?: string },
): Promise<{
  total_requested: number;
  proposed: number;
  skipped: number;
  errors: number;
  items: Array<{ sku: string; status: string; selling_price_aed: number | null; reason: string | null }>;
}> {
  const url = `/api/v1/pricing/${encodeURIComponent(channelCode)}/prices/propose-selected`;
  const response = await authedFetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`Propose failed: ${response.status} ${await response.text()}`);
  }
  return response.json();
},
```

- [ ] **4.2 Hook React Query**

```typescript
// mt-pricing-frontend/lib/hooks/pricing-desk/use-propose-prices.ts
"use client";

import { useMutation } from "@tanstack/react-query";
import { pricingDeskApi, type SellingModel } from "@/lib/api/endpoints/pricing-desk";

export function useProposeSelected(channelCode: string) {
  return useMutation({
    mutationFn: ({
      skus,
      sellingModel,
      notes,
    }: {
      skus: string[];
      sellingModel: SellingModel;
      notes?: string;
    }) =>
      pricingDeskApi.proposeSelected(channelCode, {
        skus,
        selling_model: sellingModel,
        ...(notes && { notes }),
      }),
  });
}
```

- [ ] **4.3 Modificar `catalog-table.tsx` para añadir columna checkbox**

Cambios concretos en `mt-pricing-frontend/app/(app)/pricing-desk/_components/catalog-table.tsx`:

1. Añadir al `interface Props`:
```typescript
selectedSkus: Set<string>;
onToggleSku: (sku: string) => void;
onToggleAll: (allCurrentlyShown: string[], selectAll: boolean) => void;
```

2. Añadir una nueva primera columna `<th>` con checkbox "select all":
```tsx
<th className="px-3 py-2 w-8">
  <input
    type="checkbox"
    checked={rows.length > 0 && rows.every((r) => selectedSkus.has(r.sku))}
    onChange={(e) => onToggleAll(rows.map((r) => r.sku), e.target.checked)}
    aria-label="Seleccionar todos"
  />
</th>
```

3. Añadir checkbox en cada `<tr>`:
```tsx
<td className="px-3 py-1.5">
  <input
    type="checkbox"
    checked={selectedSkus.has(r.sku)}
    onChange={() => onToggleSku(r.sku)}
    aria-label={`Seleccionar ${r.sku}`}
  />
</td>
```

4. Ajustar el `colSpan` de la fila vacía: `<td colSpan={10}>` (era 9, ahora 10).

- [ ] **4.4 Componente `propose-button.tsx`**

```tsx
// mt-pricing-frontend/app/(app)/pricing-desk/_components/propose-button.tsx
"use client";

import { useState } from "react";
import { useProposeSelected } from "@/lib/hooks/pricing-desk/use-propose-prices";
import type { SellingModel } from "@/lib/api/endpoints/pricing-desk";

interface Props {
  channelCode: string;
  sellingModel: SellingModel;
  selectedSkus: Set<string>;
  onProposed: () => void;
}

export function ProposeButton({ channelCode, sellingModel, selectedSkus, onProposed }: Props) {
  const [confirming, setConfirming] = useState(false);
  const propose = useProposeSelected(channelCode);
  const [lastResult, setLastResult] = useState<{ proposed: number; skipped: number; errors: number } | null>(null);

  const handleClick = async () => {
    if (selectedSkus.size === 0) return;
    if (!confirming) {
      setConfirming(true);
      setTimeout(() => setConfirming(false), 4000);
      return;
    }
    const result = await propose.mutateAsync({
      skus: Array.from(selectedSkus),
      sellingModel,
    });
    setLastResult({
      proposed: result.proposed,
      skipped: result.skipped,
      errors: result.errors,
    });
    setConfirming(false);
    onProposed();
  };

  const label = (() => {
    if (propose.isPending) return "Enviando…";
    if (confirming) return `¿Proponer ${selectedSkus.size}? — pulsa de nuevo`;
    if (selectedSkus.size === 0) return "Selecciona SKUs para proponer";
    return `↑ Proponer ${selectedSkus.size} a aprobación`;
  })();

  return (
    <div className="flex items-center gap-3 border-b border-mt-border bg-white px-4 py-2">
      <button
        type="button"
        disabled={selectedSkus.size === 0 || propose.isPending}
        onClick={handleClick}
        className={
          "rounded px-3 py-1.5 text-sm font-semibold text-white transition " +
          (confirming ? "bg-mt-warning hover:opacity-90" : "bg-mt-success hover:opacity-90") +
          " disabled:bg-mt-ink-4 disabled:cursor-not-allowed"
        }
      >
        {label}
      </button>
      {lastResult && (
        <span className="mt-mono text-xs text-mt-ink-3">
          {lastResult.proposed} propuestos · {lastResult.skipped} omitidos · {lastResult.errors} con error
        </span>
      )}
    </div>
  );
}
```

- [ ] **4.5 Wire en `page.tsx`**

En `mt-pricing-frontend/app/(app)/pricing-desk/page.tsx`:

1. Añadir estado:
```typescript
const [selectedSkus, setSelectedSkus] = useState<Set<string>>(new Set());

const toggleSku = (sku: string) => {
  setSelectedSkus((prev) => {
    const next = new Set(prev);
    if (next.has(sku)) next.delete(sku); else next.add(sku);
    return next;
  });
};

const toggleAll = (allCurrentlyShown: string[], selectAll: boolean) => {
  setSelectedSkus((prev) => {
    const next = new Set(prev);
    for (const s of allCurrentlyShown) {
      if (selectAll) next.add(s); else next.delete(s);
    }
    return next;
  });
};

const clearSelection = () => setSelectedSkus(new Set());
```

2. Insertar `<ProposeButton>` entre `<FiltersBar>` y `<main>`:
```tsx
import { ProposeButton } from "./_components/propose-button";
// ...
<FiltersBar ... />
<ProposeButton
  channelCode={channelCode}
  sellingModel={sellingModel}
  selectedSkus={selectedSkus}
  onProposed={clearSelection}
/>
<main ...>
  {data && (
    <CatalogTable
      channelCode={channelCode}
      sellingModel={sellingModel}
      rows={data.rows}
      selectedSkus={selectedSkus}
      onToggleSku={toggleSku}
      onToggleAll={toggleAll}
    />
  )}
</main>
```

- [ ] **4.6 Verificar compilación**

```bash
cd mt-pricing-frontend && pnpm tsc --noEmit 2>&1 | grep -E "propose|catalog-table|pricing-desk/page" | head -10
```
Expected: sin errores.

- [ ] **4.7 Commit**

```bash
git add mt-pricing-frontend/lib/api/endpoints/pricing-desk.ts \
        mt-pricing-frontend/lib/hooks/pricing-desk/use-propose-prices.ts \
        mt-pricing-frontend/app/\(app\)/pricing-desk/_components/propose-button.tsx \
        mt-pricing-frontend/app/\(app\)/pricing-desk/_components/catalog-table.tsx \
        mt-pricing-frontend/app/\(app\)/pricing-desk/page.tsx
git commit -m "feat(pricing-desk): row checkboxes + propose selected to approval flow"
```

---

## Task 5: Frontend — Modal comparador 3 esquemas

Botón ▸ al inicio de cada fila que abre un modal con FBA vs Easy Ship vs Self-Ship lado a lado para ese SKU + selling_model.

**Files:**
- Create: `mt-pricing-frontend/app/(app)/pricing-desk/_components/scheme-comparator-modal.tsx`
- Modify: `mt-pricing-frontend/app/(app)/pricing-desk/_components/catalog-table.tsx` (botón ▸)
- Modify: `mt-pricing-frontend/lib/hooks/pricing-desk/` (hook para `getProductPrice`)

- [ ] **5.1 Hook para fetch del producto individual**

Crear `mt-pricing-frontend/lib/hooks/pricing-desk/use-product-price.ts`:

```typescript
"use client";

import { useQuery } from "@tanstack/react-query";
import { pricingDeskApi, type SellingModel } from "@/lib/api/endpoints/pricing-desk";

export function useProductPrice(
  channelCode: string,
  sku: string | null,
  sellingModel: SellingModel,
) {
  return useQuery({
    queryKey: ["pricing-desk", "product-price", channelCode, sku, sellingModel],
    queryFn: () => pricingDeskApi.getProductPrice(channelCode, sku!, sellingModel),
    enabled: !!sku,
    staleTime: 30_000,
  });
}
```

- [ ] **5.2 Modal `scheme-comparator-modal.tsx`**

```tsx
// mt-pricing-frontend/app/(app)/pricing-desk/_components/scheme-comparator-modal.tsx
"use client";

import { useProductPrice } from "@/lib/hooks/pricing-desk/use-product-price";
import { useUpsertMarginOverride } from "@/lib/hooks/pricing-desk/use-margin-targets";
import { SignalBadge } from "./signal-badge";
import type { SellingModel } from "@/lib/api/endpoints/pricing-desk";

interface Props {
  channelCode: string;
  sellingModel: SellingModel;
  sku: string | null;
  onClose: () => void;
}

export function SchemeComparatorModal({ channelCode, sellingModel, sku, onClose }: Props) {
  const { data, isLoading, error } = useProductPrice(channelCode, sku, sellingModel);
  const upsertOverride = useUpsertMarginOverride(channelCode);

  if (!sku) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-mt-ink/70 p-6 backdrop-blur-sm"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="max-h-[90vh] w-full max-w-4xl overflow-auto rounded-lg bg-white p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-baseline justify-between border-b border-mt-border pb-3">
          <div>
            <h2 className="text-lg font-bold text-mt-ink">Comparador de esquemas</h2>
            <p className="text-sm text-mt-ink-3">
              SKU <code className="mt-mono text-mt-brand-deep">{sku}</code> · modelo {sellingModel.toUpperCase()}
            </p>
          </div>
          <button type="button" onClick={onClose} className="text-mt-ink-3 hover:text-mt-ink">
            ✕
          </button>
        </div>

        {isLoading && <p className="text-mt-ink-3">Cargando comparación…</p>}
        {error && (
          <p className="text-mt-danger">Error: {error instanceof Error ? error.message : "unknown"}</p>
        )}

        {data && (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {data.all_schemes.map((r) => (
              <div
                key={r.fulfillment_scheme}
                className={
                  "rounded border-2 p-4 " +
                  (r.fulfillment_scheme === data.best_scheme?.fulfillment_scheme
                    ? "border-mt-brand bg-mt-brand-soft"
                    : "border-mt-border bg-mt-surface-2")
                }
              >
                <div className="mb-2 flex items-baseline justify-between">
                  <span className="font-bold text-mt-ink">{r.scheme_label}</span>
                  {r.fulfillment_scheme === data.best_scheme?.fulfillment_scheme && (
                    <span className="mt-mono rounded bg-mt-brand px-2 py-0.5 text-[10px] font-bold uppercase text-white">
                      Óptimo
                    </span>
                  )}
                </div>

                <dl className="grid grid-cols-2 gap-x-2 gap-y-1 text-xs">
                  <dt className="text-mt-ink-3">Coste op.</dt>
                  <dd className="mt-mono mt-tnum text-right text-mt-ink">{r.cost_op_aed.toFixed(2)}</dd>

                  <dt className="text-mt-ink-3">Precio</dt>
                  <dd className="mt-mono mt-tnum text-right font-bold text-mt-ink">
                    {r.selling_price_aed?.toFixed(2) ?? "—"}
                  </dd>

                  <dt className="text-mt-ink-3">Techo</dt>
                  <dd className="mt-mono mt-tnum text-right text-mt-ink-2">
                    {r.ceiling_aed?.toFixed(2) ?? "—"}
                  </dd>

                  <dt className="text-mt-ink-3">Margen</dt>
                  <dd className="mt-mono mt-tnum text-right text-mt-ink">{r.margin_pct.toFixed(0)}%</dd>

                  <dt className="text-mt-ink-3">Benef./ud</dt>
                  <dd
                    className={
                      "mt-mono mt-tnum text-right font-bold " +
                      (r.benefit_per_unit_aed >= 0 ? "text-mt-success" : "text-mt-danger")
                    }
                  >
                    {r.benefit_per_unit_aed > 0 ? "+" : ""}
                    {r.benefit_per_unit_aed.toFixed(2)}
                  </dd>

                  <dt className="text-mt-ink-3">ROI</dt>
                  <dd className="mt-mono mt-tnum text-right text-mt-ink">{r.roi_pct.toFixed(0)}%</dd>

                  <dt className="text-mt-ink-3">Bajo techo</dt>
                  <dd
                    className={
                      "text-right font-bold " +
                      (r.is_publishable ? "text-mt-success" : "text-mt-danger")
                    }
                  >
                    {r.is_publishable ? "Sí" : "NO"}
                  </dd>

                  <dt className="text-mt-ink-3">Señal</dt>
                  <dd className="text-right">
                    <SignalBadge signal={r.signal} />
                  </dd>
                </dl>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **5.3 Añadir botón ▸ en `catalog-table.tsx`**

Cambios concretos:

1. Añadir prop al `interface Props`: `onOpenComparator: (sku: string) => void;`
2. En cada `<tr>`, justo después del checkbox `<td>`, añadir:
```tsx
<td className="px-2 py-1.5 text-center">
  <button
    type="button"
    onClick={() => onOpenComparator(r.sku)}
    className="text-mt-brand-deep hover:text-mt-brand"
    aria-label={`Comparar esquemas para ${r.sku}`}
    title="Comparar esquemas"
  >
    ▸
  </button>
</td>
```
3. Añadir `<th>` vacío en el header para mantener alineación.
4. Ajustar `colSpan` empty row a 11.

- [ ] **5.4 Wire en `page.tsx`**

```typescript
const [comparatorSku, setComparatorSku] = useState<string | null>(null);
// ...
<CatalogTable ... onOpenComparator={setComparatorSku} />
// ...
<SchemeComparatorModal
  channelCode={channelCode}
  sellingModel={sellingModel}
  sku={comparatorSku}
  onClose={() => setComparatorSku(null)}
/>
```

Importar `SchemeComparatorModal` desde `./_components/scheme-comparator-modal`.

- [ ] **5.5 Verificar y commit**

```bash
cd mt-pricing-frontend && pnpm tsc --noEmit 2>&1 | grep -E "scheme-comparator|catalog-table|pricing-desk/page" | head -10
```

```bash
git add mt-pricing-frontend/app/\(app\)/pricing-desk/_components/scheme-comparator-modal.tsx \
        mt-pricing-frontend/app/\(app\)/pricing-desk/_components/catalog-table.tsx \
        mt-pricing-frontend/app/\(app\)/pricing-desk/page.tsx \
        mt-pricing-frontend/lib/hooks/pricing-desk/use-product-price.ts
git commit -m "feat(pricing-desk): 3-scheme comparator modal per SKU"
```

---

## Task 6: Backend + Frontend — Escenarios A/B

Persistir configuraciones completas (parámetros + márgenes + overrides) en `pricing_scenarios` (tabla ya existe). 2 slots (A/B) por canal + selling_model.

**Files:**
- Modify: `mt-pricing-backend/app/api/routes/channel_pricing.py` (+3 endpoints: save/load/compare)
- Modify: `mt-pricing-backend/app/schemas/channel_pricing.py` (+ schemas)
- Create: `mt-pricing-frontend/lib/hooks/pricing-desk/use-scenarios.ts`
- Create: `mt-pricing-frontend/app/(app)/pricing-desk/_components/scenarios-section.tsx`
- Modify: `mt-pricing-frontend/lib/api/endpoints/pricing-desk.ts` (+3 métodos)
- Modify: `mt-pricing-frontend/app/(app)/pricing-desk/_components/side-panel.tsx` (insertar sección)

- [ ] **6.1 Pydantic schemas**

Añadir en `mt-pricing-backend/app/schemas/channel_pricing.py`:

```python
# ── Pricing Scenarios A/B ─────────────────────────────────────────────

class ScenarioSaveRequest(BaseModel):
    selling_model: SellingModel = SellingModel.B2C
    slot: str = Field(pattern="^[AB]$")
    label: str | None = None


class ScenarioSummary(BaseModel):
    id: UUID
    slot: str
    label: str | None
    snapshot_at: str
    selling_model: SellingModel

    model_config = ConfigDict(from_attributes=True)


class ScenarioDiffItem(BaseModel):
    sku: str
    field: str           # e.g. "selling_price_aed" or "margin_pct"
    a_value: float | None
    b_value: float | None
    delta: float | None
```

Añadir nombres al `__all__`.

- [ ] **6.2 Endpoints**

Añadir en `mt-pricing-backend/app/api/routes/channel_pricing.py`:

```python
@router.put(
    "/scenarios/{slot}",
    operation_id="saveScenario",
    response_model=ScenarioSummary,
    dependencies=[Depends(require_permissions("prices:propose"))],
)
async def save_scenario(
    channel_code: str,
    slot: str,
    body: ScenarioSaveRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Save current params + margins + overrides as scenario A or B."""
    if slot not in ("A", "B"):
        raise HTTPException(400, "slot must be 'A' or 'B'")

    channel_id = await _resolve_channel_id(channel_code, session)

    # Snapshot of current state
    fee_row = (
        await session.execute(
            select(ChannelFeeParams).where(ChannelFeeParams.channel_id == channel_id)
        )
    ).scalars().first()
    route_row = (
        await session.execute(
            select(TradeRouteParams).where(TradeRouteParams.id == fee_row.route_id)
        )
    ).scalars().first() if fee_row else None
    targets = (
        await session.execute(
            select(ChannelMarginTarget).where(
                ChannelMarginTarget.channel_id == channel_id,
                ChannelMarginTarget.selling_model == body.selling_model.value,
            )
        )
    ).scalars().all()
    overrides = (
        await session.execute(
            select(ChannelMarginOverride).where(
                ChannelMarginOverride.channel_id == channel_id,
                ChannelMarginOverride.selling_model == body.selling_model.value,
            )
        )
    ).scalars().all()

    snapshot = {
        "route": {c: str(getattr(route_row, c)) for c in (
            "fx_rate","fx_buffer_pct","freight_rate_per_kg","freight_min_aed",
            "import_tariff_pct","local_warehouse_pct","handling_pct",
        )} if route_row else {},
        "fees": {c: str(getattr(fee_row, c)) for c in (
            "mt_discount_pct","commission_pct","vat_pct","advertising_pct",
            "returns_pct","storage_multiplier",
        )} if fee_row else {},
        "targets": [
            {"family_id": str(t.family_id), "margin": str(t.margin_target_pct)}
            for t in targets
        ],
        "overrides": [
            {"sku": o.product_sku, "margin": str(o.margin_override_pct)}
            for o in overrides
        ],
    }

    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from app.db.models.channel_pricing import PricingScenario
    await session.execute(
        pg_insert(PricingScenario)
        .values(
            channel_id=channel_id,
            selling_model=body.selling_model.value,
            slot=slot,
            label=body.label,
            config_jsonb=snapshot,
        )
        .on_conflict_do_update(
            constraint="uq_pricing_scenarios_slot",
            set_={
                "label": body.label,
                "config_jsonb": snapshot,
                "snapshot_at": text("now()"),
            },
        )
    )
    await session.commit()

    saved = (
        await session.execute(
            select(PricingScenario).where(
                PricingScenario.channel_id == channel_id,
                PricingScenario.selling_model == body.selling_model.value,
                PricingScenario.slot == slot,
            )
        )
    ).scalars().first()

    return ScenarioSummary(
        id=saved.id,
        slot=saved.slot,
        label=saved.label,
        snapshot_at=saved.snapshot_at.isoformat(),
        selling_model=SellingModel(saved.selling_model),
    )


@router.get(
    "/scenarios",
    operation_id="listScenarios",
    response_model=list[ScenarioSummary],
    dependencies=[Depends(require_permissions("prices:read"))],
)
async def list_scenarios(
    channel_code: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    selling_model: SellingModel = Query(default=SellingModel.B2C),
):
    from app.db.models.channel_pricing import PricingScenario
    channel_id = await _resolve_channel_id(channel_code, session)
    rows = (
        await session.execute(
            select(PricingScenario).where(
                PricingScenario.channel_id == channel_id,
                PricingScenario.selling_model == selling_model.value,
            )
        )
    ).scalars().all()
    return [
        ScenarioSummary(
            id=r.id, slot=r.slot, label=r.label,
            snapshot_at=r.snapshot_at.isoformat(),
            selling_model=SellingModel(r.selling_model),
        )
        for r in rows
    ]


@router.post(
    "/scenarios/{slot}/load",
    operation_id="loadScenario",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions("prices:propose"))],
)
async def load_scenario(
    channel_code: str,
    slot: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    selling_model: SellingModel = Query(default=SellingModel.B2C),
):
    """Restore saved scenario: applies its params + margins + overrides."""
    from app.db.models.channel_pricing import PricingScenario
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    channel_id = await _resolve_channel_id(channel_code, session)
    sc = (
        await session.execute(
            select(PricingScenario).where(
                PricingScenario.channel_id == channel_id,
                PricingScenario.selling_model == selling_model.value,
                PricingScenario.slot == slot,
            )
        )
    ).scalars().first()
    if sc is None:
        raise HTTPException(404, f"Scenario {slot} not found")

    cfg = sc.config_jsonb

    # Restore fees
    if cfg.get("fees"):
        await session.execute(
            update(ChannelFeeParams)
            .where(ChannelFeeParams.channel_id == channel_id)
            .values(**{k: float(v) for k, v in cfg["fees"].items()})
        )
    # Restore route (only the channel's route)
    if cfg.get("route"):
        fee_row = (
            await session.execute(
                select(ChannelFeeParams).where(ChannelFeeParams.channel_id == channel_id)
            )
        ).scalars().first()
        if fee_row:
            await session.execute(
                update(TradeRouteParams)
                .where(TradeRouteParams.id == fee_row.route_id)
                .values(**{k: float(v) for k, v in cfg["route"].items()})
            )
    # Restore margin targets — wipe existing for this (channel, selling_model) then re-insert
    await session.execute(
        delete(ChannelMarginTarget).where(
            ChannelMarginTarget.channel_id == channel_id,
            ChannelMarginTarget.selling_model == selling_model.value,
        )
    )
    for t in cfg.get("targets", []):
        await session.execute(
            pg_insert(ChannelMarginTarget)
            .values(
                channel_id=channel_id,
                family_id=t["family_id"],
                selling_model=selling_model.value,
                margin_target_pct=float(t["margin"]),
            )
            .on_conflict_do_nothing()
        )
    # Restore overrides
    await session.execute(
        delete(ChannelMarginOverride).where(
            ChannelMarginOverride.channel_id == channel_id,
            ChannelMarginOverride.selling_model == selling_model.value,
        )
    )
    for o in cfg.get("overrides", []):
        await session.execute(
            pg_insert(ChannelMarginOverride)
            .values(
                product_sku=o["sku"],
                channel_id=channel_id,
                selling_model=selling_model.value,
                margin_override_pct=float(o["margin"]),
                reason=f"loaded from scenario {slot}",
            )
            .on_conflict_do_nothing()
        )
    await session.commit()
```

Asegurar imports en cabecera del fichero: `ScenarioSaveRequest`, `ScenarioSummary`, `delete` desde sqlalchemy.

- [ ] **6.3 Regenerar OpenAPI + import en frontend**

```bash
docker exec mt-backend sh -c "cd /app && python -m app.scripts.export_openapi" 2>&1 | tail -3
docker cp mt-backend:/app/_bmad-output/planning-artifacts/mt-api-contract-openapi.json \
  mt-pricing-backend/_bmad-output/planning-artifacts/mt-api-contract-openapi.json
cd mt-pricing-frontend && pnpm openapi:gen 2>&1 | tail -3
```

- [ ] **6.4 Métodos en wrapper API frontend**

Añadir en `mt-pricing-frontend/lib/api/endpoints/pricing-desk.ts` dentro del objeto `pricingDeskApi`:

```typescript
async listScenarios(channelCode: string, sellingModel: SellingModel = "b2c") {
  const url = `/api/v1/pricing/${encodeURIComponent(channelCode)}/scenarios?selling_model=${sellingModel}`;
  const r = await authedFetch(url);
  if (!r.ok) throw new Error(`List scenarios failed: ${r.status}`);
  return (await r.json()) as Array<{
    id: string; slot: string; label: string | null;
    snapshot_at: string; selling_model: SellingModel;
  }>;
},

async saveScenario(
  channelCode: string,
  slot: "A" | "B",
  body: { selling_model: SellingModel; label?: string },
) {
  const url = `/api/v1/pricing/${encodeURIComponent(channelCode)}/scenarios/${slot}`;
  const r = await authedFetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`Save scenario failed: ${r.status} ${await r.text()}`);
  return r.json();
},

async loadScenario(channelCode: string, slot: "A" | "B", sellingModel: SellingModel = "b2c") {
  const url = `/api/v1/pricing/${encodeURIComponent(channelCode)}/scenarios/${slot}/load?selling_model=${sellingModel}`;
  const r = await authedFetch(url, { method: "POST" });
  if (!r.ok) throw new Error(`Load scenario failed: ${r.status}`);
},
```

- [ ] **6.5 Hook React Query**

```typescript
// mt-pricing-frontend/lib/hooks/pricing-desk/use-scenarios.ts
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { pricingDeskApi, type SellingModel } from "@/lib/api/endpoints/pricing-desk";

export function useScenarios(channelCode: string, sellingModel: SellingModel) {
  return useQuery({
    queryKey: ["pricing-desk", "scenarios", channelCode, sellingModel],
    queryFn: () => pricingDeskApi.listScenarios(channelCode, sellingModel),
    enabled: !!channelCode,
  });
}

export function useSaveScenario(channelCode: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      slot,
      sellingModel,
      label,
    }: {
      slot: "A" | "B";
      sellingModel: SellingModel;
      label?: string;
    }) =>
      pricingDeskApi.saveScenario(channelCode, slot, {
        selling_model: sellingModel,
        ...(label && { label }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pricing-desk", "scenarios", channelCode] });
    },
  });
}

export function useLoadScenario(channelCode: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ slot, sellingModel }: { slot: "A" | "B"; sellingModel: SellingModel }) =>
      pricingDeskApi.loadScenario(channelCode, slot, sellingModel),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pricing-desk", "params", channelCode] });
      qc.invalidateQueries({ queryKey: ["pricing-desk", "margin-targets", channelCode] });
      qc.invalidateQueries({ queryKey: ["pricing-desk", "catalog", channelCode] });
    },
  });
}
```

- [ ] **6.6 Componente `scenarios-section.tsx`**

```tsx
// mt-pricing-frontend/app/(app)/pricing-desk/_components/scenarios-section.tsx
"use client";

import { useState } from "react";
import { useScenarios, useSaveScenario, useLoadScenario } from "@/lib/hooks/pricing-desk/use-scenarios";
import type { SellingModel } from "@/lib/api/endpoints/pricing-desk";

interface Props {
  channelCode: string;
  sellingModel: SellingModel;
}

export function ScenariosSection({ channelCode, sellingModel }: Props) {
  const { data: scenarios } = useScenarios(channelCode, sellingModel);
  const save = useSaveScenario(channelCode);
  const load = useLoadScenario(channelCode);

  const slotA = scenarios?.find((s) => s.slot === "A") ?? null;
  const slotB = scenarios?.find((s) => s.slot === "B") ?? null;

  const renderSlot = (slot: "A" | "B", current: typeof slotA) => (
    <div className="flex flex-col gap-1 rounded border border-mt-border bg-mt-surface-2 p-2 text-xs">
      <div className="flex items-baseline justify-between">
        <span className="font-bold text-mt-ink">Slot {slot}</span>
        {current && (
          <span className="mt-mono text-[10px] text-mt-ink-3">
            {new Date(current.snapshot_at).toLocaleString("es-ES", { dateStyle: "short", timeStyle: "short" })}
          </span>
        )}
      </div>
      {current?.label && <div className="text-[11px] text-mt-ink-2">{current.label}</div>}
      <div className="flex gap-1">
        <button
          type="button"
          onClick={() => {
            const label = window.prompt("Nombre opcional del escenario:") ?? undefined;
            save.mutate({ slot, sellingModel, label });
          }}
          disabled={save.isPending}
          className="flex-1 rounded bg-mt-brand px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-white hover:bg-mt-brand-deep disabled:opacity-50"
        >
          Guardar
        </button>
        <button
          type="button"
          onClick={() => load.mutate({ slot, sellingModel })}
          disabled={!current || load.isPending}
          className="flex-1 rounded border border-mt-border bg-white px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-mt-brand-deep hover:bg-mt-brand-soft disabled:opacity-50"
        >
          Cargar
        </button>
      </div>
    </div>
  );

  return (
    <section className="border-b border-mt-border p-3">
      <div className="mt-mono mb-3 text-xs font-semibold uppercase tracking-wider text-mt-ink">
        Escenarios A/B
      </div>
      <div className="grid grid-cols-2 gap-2">
        {renderSlot("A", slotA)}
        {renderSlot("B", slotB)}
      </div>
    </section>
  );
}
```

- [ ] **6.7 Insertar en `side-panel.tsx`**

```tsx
import { ScenariosSection } from "./scenarios-section";
// ...
<OptimizeSection ... />
<ScenariosSection channelCode={channelCode} sellingModel={sellingModel} />
<ImportExcelSection ... />
```

- [ ] **6.8 Test API smoke**

Añadir a `mt-pricing-backend/tests/api/test_channel_pricing.py`:

```python
async def test_save_and_list_scenarios(cp_client):
    """PUT /scenarios/A then GET /scenarios returns slot A."""
    save_resp = await cp_client.put(
        "/api/v1/pricing/amazon_uae/scenarios/A",
        json={"selling_model": "b2c", "label": "test scenario"},
    )
    assert save_resp.status_code == 200, save_resp.text

    list_resp = await cp_client.get(
        "/api/v1/pricing/amazon_uae/scenarios?selling_model=b2c"
    )
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert any(s["slot"] == "A" for s in data)
```

- [ ] **6.9 Run tests + smoke + commit**

```bash
docker exec mt-backend sh -c "cd /app && python -m pytest tests/api/test_channel_pricing.py::test_save_and_list_scenarios -v --no-cov" 2>&1 | tail -10
cd mt-pricing-frontend && pnpm tsc --noEmit 2>&1 | grep -E "scenarios|side-panel" | head -10
```

```bash
git add mt-pricing-backend/app/api/routes/channel_pricing.py \
        mt-pricing-backend/app/schemas/channel_pricing.py \
        mt-pricing-backend/tests/api/test_channel_pricing.py \
        mt-pricing-backend/_bmad-output/planning-artifacts/mt-api-contract-openapi.json \
        mt-pricing-frontend/lib/api/types.ts \
        mt-pricing-frontend/lib/api/endpoints/pricing-desk.ts \
        mt-pricing-frontend/lib/hooks/pricing-desk/use-scenarios.ts \
        mt-pricing-frontend/app/\(app\)/pricing-desk/_components/scenarios-section.tsx \
        mt-pricing-frontend/app/\(app\)/pricing-desk/_components/side-panel.tsx
git commit -m "feat(pricing-desk): A/B scenarios save + load (backend + frontend)"
```

---

## Task 7: Verificación final + PR

- [ ] **7.1 Backend tests completos**

```bash
docker exec mt-backend sh -c "cd /app && python -m pytest tests/services/pricing/ tests/scripts/ tests/api/test_channel_pricing.py tests/db/test_channel_pricing_models.py -v --no-cov 2>&1" | tail -25
```
Expected: todo pasa. Reportar el total (debería ser ~35-40 tests).

- [ ] **7.2 Frontend tsc + lint + build**

```bash
cd mt-pricing-frontend && pnpm tsc --noEmit 2>&1 | grep "error TS" | head -10
cd mt-pricing-frontend && pnpm lint 2>&1 | grep -E "pricing-desk|propose|scenarios|import-excel" | head -10
cd mt-pricing-frontend && pnpm build 2>&1 | tail -15
```
Expected: tsc + build limpios (lint puede tener warnings pre-existentes, OK; sin errores nuevos).

- [ ] **7.3 Smoke manual del flujo end-to-end**

Abrir `http://localhost:3000/pricing-desk`, autenticarse, y verificar:

1. **Carga inicial**: el catálogo muestra >50 productos con datos reales (no todos en cero).
2. **Comparador**: click en ▸ de cualquier fila → modal con 3 esquemas + "Óptimo" marcado.
3. **Import**: subir un Excel de prueba → ve preview → confirmar → catálogo se actualiza.
4. **Selección + propuesta**: marcar 3 SKUs → click "Proponer X a aprobación" → confirmar → resultado muestra `proposed: 3`.
5. **Escenarios**: pulsar "Guardar" en Slot A → cambiar el FX rate → pulsar "Cargar" en Slot A → el FX vuelve al valor guardado.

- [ ] **7.4 Push + PR**

```bash
git push -u origin feat/pricing-desk-frontend
gh pr view --json url 2>&1
```

Si ya hay un PR abierto (#130), seguir commiteando ahí — el PR se irá actualizando solo con el push. Si no, crear nuevo:

```bash
gh pr create --base main \
  --title "feat(pricing-desk): v2 — propose, import, comparator, scenarios + seed real data" \
  --body "$(cat <<'EOF'
## Summary

- Script one-shot que parsea el HTML del Pricing Desk standalone y carga los 232 SKUs reales (pe_eur, catalog_pvp_eur, peso, tarifas FBA).
- Botón "Proponer N a aprobación" con checkboxes por fila — crea registros en `prices` con `status=pending_review`.
- UI de import Excel (catálogo + logística) con vista previa antes de confirmar.
- Modal comparador FBA vs Easy Ship vs Self-Ship por SKU.
- Escenarios A/B persistidos: guardar / cargar la configuración completa (params + márgenes + overrides) usando la tabla `pricing_scenarios` existente.

## Test plan

- [ ] `docker exec mt-backend python /app/app/scripts/seed_amazon_uae_from_html.py` → carga 232 SKUs sin errores
- [ ] Comparar el catálogo del Pricing Desk con el HTML original — los precios coinciden con los datos reales
- [ ] Modal comparador muestra los 3 esquemas y "Óptimo" marcado
- [ ] Importar Excel de catálogo de prueba → vista previa + confirmar → producto actualizado
- [ ] Marcar 5 SKUs → "Proponer a aprobación" → verificar 5 registros nuevos en `prices` con `status=pending_review`
- [ ] Guardar Slot A → modificar FX rate → Cargar Slot A → FX vuelve al valor guardado
- [ ] `pnpm tsc --noEmit`, `pnpm build` limpios
- [ ] Backend: `pytest tests/services/pricing/ tests/scripts/ tests/api/test_channel_pricing.py` todo verde

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **7.5 Commit cierre (vacío)**

```bash
git commit --allow-empty -m "feat(pricing-desk): v2 complete — all 5 pending features delivered"
git push
```

---

## Checklist de cobertura del scope acordado

| Funcionalidad | Task | Estado al cerrar plan |
|---|---|---|
| Carga inicial desde HTML (one-shot script) | Task 1 | ✅ |
| Proponer precios al flujo de aprobación (checkboxes) | Tasks 2 + 4 | ✅ |
| UI de import Excel | Task 3 | ✅ |
| Modal comparador 3 esquemas | Task 5 | ✅ |
| Escenarios A/B persistidos | Task 6 | ✅ |
| Verificación + PR | Task 7 | ✅ |
