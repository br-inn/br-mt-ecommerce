# F8 — Optimización automática + diff · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Un job detecta cuando re-optimizar el canal cambiaría ≥ umbral de SKUs (por drift de FX/comisión/arancel), guarda un snapshot de revert y registra una alerta + diff — **sin aplicar nada automáticamente**.

**Architecture:** `drift_detector` reconstruye los params del último snapshot, re-optimiza baseline vs actual con `ChannelOptimizer`, y `optimization_diff` cuenta SKUs que cambian esquema/señal. Si ≥ umbral, crea `auto_pre_sync_param` snapshot + fila en `pricing_optimization_runs` (alerta). Endpoints de lectura + ack; revert reutiliza `load_scenario`.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, Celery, pytest (integración Postgres).

**Design:** `docs/superpowers/specs/2026-05-31-pricing-auto-optimization-diff-f8-design.md`

**Pre-flight (verificado):**
- `ChannelOptimizer.full_optimize_catalog_b2c(products, route, fees, schemes) -> list[PriceResult]` y `_b2b(...)` (`app/services/pricing/optimizer.py:95,179`). `PriceResult` (`schemas.py`): `.sku:str`, `.selling_model:SellingModel`, `.fulfillment_scheme:FulfillmentScheme`, `.signal:str`, `.margin_pct`, … (frozen dataclass).
- `ParameterLoader` (`app/services/pricing/loader.py`): `load_route_and_fees(channel_id) -> (RouteParams, ChannelFees, list[SchemeConfig])` (`:40`), `load_product_data(channel_id, ...) -> list[ProductPricingData]` (`:122`). **Confirmar la firma exacta de `load_product_data`** (¿toma `selling_model`?).
- `RouteParams` (frozen): `fx_rate, fx_buffer_pct, freight_rate_per_kg, freight_min_aed, import_tariff_pct, local_warehouse_pct, handling_pct`. `ChannelFees` (frozen): `mt_discount_pct, commission_pct, vat_pct, advertising_pct, returns_pct, storage_multiplier`.
- `build_scenario_config(session, channel_id, selling_model) -> dict` (`app/services/pricing/scenarios.py:46`) → `{"route": {7 keys str}, "fees": {6 keys str}, "targets": [...], "overrides": [...]}`. `create_auto_snapshot(session, *, channel_id, selling_model, kind) -> UUID` (`:107`). `SnapshotKind.AUTO_PRE_SYNC_PARAM` ya existe (`enums.py`).
- `PricingScenario` (`app/db/models/channel_pricing.py:443`): `channel_id, selling_model, slot, config_jsonb, snapshot_at, kind, retention_until`.
- `load_scenario` revert endpoint ya existe (`channel_pricing.py:1406`).
- Task pattern F2: `app/workers/tasks/fx.py` (`@celery_app.task(name=..., bind=True, acks_late=True)`, `asyncio.run(_run())`, `get_sessionmaker()` de `app.db`). Seed jobs: `alembic/versions/20260603_150_fx_backfill_and_jobs.py`.
- `require_permissions("prices:read"|"prices:propose")` (`app/api/deps.py`), patrón de rutas en `channel_pricing.py`.
- Alembic head: `20260603_150`. F8 migración: revision `20260603_151`, down_revision `20260603_150`.
- CI: ruff==0.15.14, mypy. Comandos desde `mt-pricing-backend/`. Sin DB local → integración en CI.

---

### Task 1: Config — umbrales de drift

**Files:** Modify `app/core/config.py`; Test `tests/unit/test_config_drift.py`

- [ ] **Step 1: failing test**
```python
# tests/unit/test_config_drift.py
from decimal import Decimal
from app.core.config import get_settings

def test_drift_settings_defaults() -> None:
    s = get_settings()
    assert s.DRIFT_MIN_SKUS == 1
    assert s.FX_DRIFT_PCT == Decimal("0.5")
    assert s.COMMISSION_DRIFT_PP == Decimal("1.0")
    assert s.TARIFF_DRIFT_PP == Decimal("1.0")
    assert "1" in s.AUTO_OPTIMIZE_CHECK_CRON
```
- [ ] **Step 2: FAIL** (`uv run pytest tests/unit/test_config_drift.py -q`).
- [ ] **Step 3: implement** — añadir al `Settings`:
```python
    # ── Auto-optimization drift (F8) ─────────────────────────────────────
    DRIFT_MIN_SKUS: int = 1
    FX_DRIFT_PCT: Decimal = Decimal("0.5")
    COMMISSION_DRIFT_PP: Decimal = Decimal("1.0")
    TARIFF_DRIFT_PP: Decimal = Decimal("1.0")
    AUTO_OPTIMIZE_CHECK_CRON: str = "30 1 * * *"
```
- [ ] **Step 4: PASS**. **Step 5: commit** — `feat(pricing): config umbrales de drift auto-optimización [F8]`

---

### Task 2: `optimization_diff` — diff puro de resultados

**Files:** Create `app/services/pricing/optimization_diff.py`; Test `tests/unit/services/pricing/test_optimization_diff.py`

- [ ] **Step 1: failing test**
```python
# tests/unit/services/pricing/test_optimization_diff.py
from dataclasses import dataclass
from app.services.pricing.optimization_diff import diff_results

@dataclass
class _R:  # stub con los campos que usa el diff
    sku: str
    fulfillment_scheme: str
    signal: str

def test_diff_counts_scheme_and_signal_changes() -> None:
    old = [_R("A", "CANAL_FULL", "ÓPTIMO"), _R("B", "MERCHANT_MANAGED", "FINO")]
    new = [_R("A", "CANAL_LASTMILE", "ÓPTIMO"), _R("B", "MERCHANT_MANAGED", "FRÁGIL")]
    d = diff_results(old, new)
    assert d.skus_scheme_changed == 1   # A
    assert d.skus_signal_changed == 1   # B
    assert len(d.detail) == 2

def test_diff_no_changes() -> None:
    old = [_R("A", "CANAL_FULL", "ÓPTIMO")]
    new = [_R("A", "CANAL_FULL", "ÓPTIMO")]
    d = diff_results(old, new)
    assert d.skus_scheme_changed == 0 and d.skus_signal_changed == 0 and d.detail == []
```
- [ ] **Step 2: FAIL**.
- [ ] **Step 3: implement** — usa `str(scheme)`/`.value` defensivo para enums o str:
```python
"""Diff puro de dos corridas de optimización (F8)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_DETAIL_CAP = 200


@dataclass
class DiffSummary:
    skus_scheme_changed: int = 0
    skus_signal_changed: int = 0
    detail: list[dict[str, Any]] = field(default_factory=list)


def _scheme(r: Any) -> str:
    s = r.fulfillment_scheme
    return s.value if hasattr(s, "value") else str(s)


def diff_results(old: list[Any], new: list[Any]) -> DiffSummary:
    """Compara por SKU el fulfillment_scheme y la signal entre dos corridas."""
    old_by = {r.sku: r for r in old}
    out = DiffSummary()
    for nr in new:
        orr = old_by.get(nr.sku)
        if orr is None:
            continue
        sch_changed = _scheme(orr) != _scheme(nr)
        sig_changed = orr.signal != nr.signal
        if sch_changed:
            out.skus_scheme_changed += 1
        if sig_changed:
            out.skus_signal_changed += 1
        if (sch_changed or sig_changed) and len(out.detail) < _DETAIL_CAP:
            out.detail.append({
                "sku": nr.sku,
                "old_scheme": _scheme(orr), "new_scheme": _scheme(nr),
                "old_signal": orr.signal, "new_signal": nr.signal,
            })
    return out
```
- [ ] **Step 4: PASS**. **Step 5: commit** — `feat(pricing): optimization_diff (cuenta SKUs cambio esquema/señal) [F8]`

---

### Task 3: `route_fees_from_config` — reconstruir params del baseline

**Files:** Modify `app/services/pricing/scenarios.py`; Test `tests/unit/services/pricing/test_route_fees_from_config.py`

- [ ] **Step 1: failing test**
```python
# tests/unit/services/pricing/test_route_fees_from_config.py
from decimal import Decimal
from app.services.pricing.scenarios import route_fees_from_config

def test_rebuild_route_fees_from_config() -> None:
    cfg = {
        "route": {"fx_rate": "3.90", "fx_buffer_pct": "2.00", "freight_rate_per_kg": "0.05",
                  "freight_min_aed": "50.00", "import_tariff_pct": "4.14",
                  "local_warehouse_pct": "2.00", "handling_pct": "1.50"},
        "fees": {"mt_discount_pct": "15.00", "commission_pct": "11.00", "vat_pct": "5.00",
                 "advertising_pct": "8.00", "returns_pct": "2.00", "storage_multiplier": "1.0"},
    }
    route, fees = route_fees_from_config(cfg)
    assert route.fx_rate == Decimal("3.90") and route.import_tariff_pct == Decimal("4.14")
    assert fees.commission_pct == Decimal("11.00")

def test_rebuild_returns_none_when_empty() -> None:
    assert route_fees_from_config({"route": {}, "fees": {}}) is None
```
- [ ] **Step 2: FAIL**.
- [ ] **Step 3: implement** en `scenarios.py`:
```python
from decimal import Decimal
from app.services.pricing.schemas import RouteParams, ChannelFees

def route_fees_from_config(cfg: dict) -> tuple[RouteParams, ChannelFees] | None:
    """Reconstruye RouteParams+ChannelFees desde un config_jsonb de PricingScenario."""
    r, f = cfg.get("route") or {}, cfg.get("fees") or {}
    if not r or not f:
        return None
    route = RouteParams(
        fx_rate=Decimal(r["fx_rate"]), fx_buffer_pct=Decimal(r["fx_buffer_pct"]),
        freight_rate_per_kg=Decimal(r["freight_rate_per_kg"]),
        freight_min_aed=Decimal(r["freight_min_aed"]),
        import_tariff_pct=Decimal(r["import_tariff_pct"]),
        local_warehouse_pct=Decimal(r["local_warehouse_pct"]),
        handling_pct=Decimal(r["handling_pct"]),
    )
    fees = ChannelFees(
        mt_discount_pct=Decimal(f["mt_discount_pct"]), commission_pct=Decimal(f["commission_pct"]),
        vat_pct=Decimal(f["vat_pct"]), advertising_pct=Decimal(f["advertising_pct"]),
        returns_pct=Decimal(f["returns_pct"]), storage_multiplier=Decimal(f["storage_multiplier"]),
    )
    return route, fees
```
- [ ] **Step 4: PASS**. **Step 5: commit** — `feat(pricing): route_fees_from_config (reconstruye params de snapshot) [F8]`

---

### Task 4: Modelo `PricingOptimizationRun`

**Files:** Create `app/db/models/optimization_run.py`; (registrar en `app/db/models/__init__.py` si aplica)

- [ ] **Step 1: implement** (mirar `app/db/models/provenance.py` para mixins/estilo):
```python
"""Modelo de registro/alerta de drift de optimización (F8)."""
from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, text
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UuidPkMixin
from app.db.types import UUID_PG


class PricingOptimizationRun(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "pricing_optimization_runs"

    channel_id: Mapped[UUID] = mapped_column(
        UUID_PG, ForeignKey("channels.id", name="fk_opt_runs_channel"), nullable=False
    )
    selling_model: Mapped[str] = mapped_column(
        PG_ENUM("b2c", "b2b", name="selling_model", create_type=False), nullable=False
    )
    baseline_snapshot_id: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("pricing_scenarios.id", name="fk_opt_runs_baseline", ondelete="SET NULL"),
        nullable=True,
    )
    revert_snapshot_id: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("pricing_scenarios.id", name="fk_opt_runs_revert", ondelete="SET NULL"),
        nullable=True,
    )
    skus_scheme_changed: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    skus_signal_changed: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    drift_reasons: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    diff_detail: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", name="fk_opt_runs_ack_by", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        Index("idx_opt_runs_lookup", "channel_id", "selling_model", text("detected_at DESC")),
        Index("idx_opt_runs_unack", "channel_id", postgresql_where=text("acknowledged_at IS NULL")),
    )
```
- [ ] **Step 2: commit** — `feat(pricing): modelo PricingOptimizationRun [F8]`

---

### Task 5: Migración `20260603_151` (tabla + seed job)

**Files:** Create `alembic/versions/20260603_151_optimization_runs.py`

- [ ] **Step 1: implement** (revision `20260603_151`, down `20260603_150`). Crear tabla con `op.create_table` (replicando columnas del modelo; `selling_model` con `postgresql.ENUM(..., create_type=False)`), índices, FKs. Seed job idempotente:
```python
op.execute("""
    INSERT INTO job_definitions
        (code, task_name, description, owner, schedule_type, cron_expression, timezone, queue, enabled, args, kwargs)
    VALUES
        ('pricing-auto-optimize-check', 'mt.pricing.auto_optimize_check',
         'Detecta drift de params y alerta con diff (no aplica)', 'infra', 'cron',
         '30 1 * * *', 'Asia/Dubai', 'pricing', true, '[]'::jsonb, '{}'::jsonb)
    ON CONFLICT (code) DO NOTHING;
""")
```
`downgrade`: `DELETE FROM job_definitions WHERE code='pricing-auto-optimize-check'` + `op.drop_table("pricing_optimization_runs")`. **`selling_model` enum: `create_type=False`** (ya existe).
- [ ] **Step 2:** `uv run alembic heads` = 1 (`20260603_151`); `uv run alembic check` sin drift (el modelo de Task 4 debe casar 1:1 con la tabla).
- [ ] **Step 3: review** — dispatch **migration-reviewer** sobre el fichero (split public.*, enum create_type=False, índices, reversibilidad). Aplicar correcciones.
- [ ] **Step 4: commit** — `feat(pricing): migración pricing_optimization_runs + seed job [F8]`

---

### Task 6: `drift_detector` — detección + diff

**Files:** Create `app/services/pricing/drift_detector.py`; Test `tests/services/pricing/test_drift_detector.py`

- [ ] **Step 1: failing test** (integración): sembrar canal + un PricingScenario baseline con `commission_pct` distinta a la actual → `detect_drift` devuelve un `DriftResult` con `skus_*` y `should_alert`. Sin baseline → `None`.
```python
# tests/services/pricing/test_drift_detector.py — esqueleto
@pytest.mark.asyncio
async def test_detect_drift_no_baseline_returns_none(db_session, seeded_channel) -> None:
    from app.services.pricing.drift_detector import detect_drift
    res = await detect_drift(db_session, channel_id=seeded_channel.id, selling_model="b2c")
    assert res is None  # sin snapshots → no baseline
```
(Tests de drift positivo: crear un PricingScenario con config_jsonb de comisión baja + productos, y params actuales con comisión alta; afirmar `res.summary.skus_*`. El implementer arma el seed reusando helpers de `test_channel_pricing.py`/`test_loader_cost.py`.)
- [ ] **Step 2: FAIL**.
- [ ] **Step 3: implement**:
```python
"""Detección de drift de optimización (F8): baseline vs actual."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.channel_pricing import PricingScenario
from app.services.pricing.loader import ParameterLoader
from app.services.pricing.optimization_diff import DiffSummary, diff_results
from app.services.pricing.optimizer import ChannelOptimizer
from app.services.pricing.scenarios import route_fees_from_config


@dataclass
class DriftResult:
    summary: DiffSummary
    drift_reasons: dict
    baseline_snapshot_id: UUID
    should_alert: bool


def _optimize(products, route, fees, schemes, selling_model: str):
    if selling_model == "b2b":
        return ChannelOptimizer.full_optimize_catalog_b2b(products, route, fees, schemes)
    return ChannelOptimizer.full_optimize_catalog_b2c(products, route, fees, schemes)


async def detect_drift(
    session: AsyncSession, *, channel_id: UUID, selling_model: str
) -> DriftResult | None:
    baseline = (
        await session.execute(
            select(PricingScenario)
            .where(PricingScenario.channel_id == channel_id,
                   PricingScenario.selling_model == selling_model)
            .order_by(PricingScenario.snapshot_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if baseline is None:
        return None
    rebuilt = route_fees_from_config(baseline.config_jsonb)
    if rebuilt is None:
        return None
    base_route, base_fees = rebuilt

    loader = ParameterLoader(session)
    cur_route, cur_fees, schemes = await loader.load_route_and_fees(channel_id)
    products = await loader.load_product_data(channel_id)  # confirmar firma
    if not products:
        return None

    base_results = _optimize(products, base_route, base_fees, schemes, selling_model)
    cur_results = _optimize(products, cur_route, cur_fees, schemes, selling_model)
    summary = diff_results(base_results, cur_results)

    s = get_settings()
    reasons = {
        "fx_pct": _pct_delta(base_route.fx_rate, cur_route.fx_rate),
        "commission_pp": str(abs(cur_fees.commission_pct - base_fees.commission_pct)),
        "tariff_pp": str(abs(cur_route.import_tariff_pct - base_route.import_tariff_pct)),
    }
    should = (summary.skus_scheme_changed + summary.skus_signal_changed) >= s.DRIFT_MIN_SKUS
    return DriftResult(summary, reasons, baseline.id, should)


def _pct_delta(a: Decimal, b: Decimal) -> str:
    if a == 0:
        return "0"
    return str((abs(b - a) / a * Decimal("100")).quantize(Decimal("0.01")))
```
- [ ] **Step 4: PASS** (en CI). **Step 5: commit** — `feat(pricing): drift_detector (baseline vs actual, reusa optimizer) [F8]`

---

### Task 7: Task Celery `mt.pricing.auto_optimize_check`

**Files:** Create `app/workers/tasks/pricing_auto_optimize.py`; Test `tests/workers/test_auto_optimize_task.py`

- [ ] **Step 1: failing test**: registro de la task (`assert "mt.pricing.auto_optimize_check" in celery_app.tasks` tras importar el módulo).
- [ ] **Step 2: FAIL**.
- [ ] **Step 3: implement** (patrón F2 `fx.py` + `pricing_snapshots.py`):
```python
"""Task: detecta drift por canal×modelo y registra alerta + snapshot (F8). No aplica."""
from __future__ import annotations
import asyncio, logging
from typing import Any

from sqlalchemy import select
from app.workers.worker import celery_app          # confirmar import real (F2 usó app.workers.worker)
from app.db import get_sessionmaker
from app.db.enums import SnapshotKind
from app.db.models.channels import Channel
from app.db.models.optimization_run import PricingOptimizationRun
from app.services.pricing.drift_detector import detect_drift
from app.services.pricing.scenarios import create_auto_snapshot

logger = logging.getLogger(__name__)


async def _check_one(session, channel_id, selling_model: str) -> dict[str, Any]:
    res = await detect_drift(session, channel_id=channel_id, selling_model=selling_model)
    if res is None or not res.should_alert:
        return {"channel_id": str(channel_id), "selling_model": selling_model, "alerted": False}
    # dedup D4: ¿run no-ack con mismo diff/baseline ya existe?
    existing = (
        await session.execute(
            select(PricingOptimizationRun).where(
                PricingOptimizationRun.channel_id == channel_id,
                PricingOptimizationRun.selling_model == selling_model,
                PricingOptimizationRun.acknowledged_at.is_(None),
                PricingOptimizationRun.baseline_snapshot_id == res.baseline_snapshot_id,
                PricingOptimizationRun.skus_scheme_changed == res.summary.skus_scheme_changed,
                PricingOptimizationRun.skus_signal_changed == res.summary.skus_signal_changed,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return {"channel_id": str(channel_id), "selling_model": selling_model, "alerted": False, "dedup": True}
    revert_id = await create_auto_snapshot(
        session, channel_id=channel_id, selling_model=selling_model,
        kind=SnapshotKind.AUTO_PRE_SYNC_PARAM,
    )
    session.add(PricingOptimizationRun(
        channel_id=channel_id, selling_model=selling_model,
        baseline_snapshot_id=res.baseline_snapshot_id, revert_snapshot_id=revert_id,
        skus_scheme_changed=res.summary.skus_scheme_changed,
        skus_signal_changed=res.summary.skus_signal_changed,
        drift_reasons=res.drift_reasons, diff_detail=res.summary.detail,
    ))
    return {"channel_id": str(channel_id), "selling_model": selling_model, "alerted": True}


async def _run() -> dict[str, Any]:
    sm = get_sessionmaker()
    out = []
    async with sm() as session:
        channels = (await session.execute(select(Channel.id))).scalars().all()
        for cid in channels:
            for model in ("b2c", "b2b"):
                try:
                    out.append(await _check_one(session, cid, model))
                except Exception:
                    logger.exception("auto_optimize.check.failed", extra={"channel_id": str(cid), "model": model})
                    await session.rollback()
        await session.commit()
    return {"status": "ok", "checks": out}


@celery_app.task(name="mt.pricing.auto_optimize_check", bind=True, acks_late=True)
def auto_optimize_check(self) -> dict[str, Any]:  # noqa: ANN001
    result = asyncio.run(_run())
    logger.info("auto_optimize.check.done", extra={"n": len(result.get("checks", []))})
    return result
```
Asegurar el módulo en el `include`/autodiscovery del worker (como F2). **`asyncio.run` + un solo `commit` al final**; rollback por iteración fallida.
- [ ] **Step 4: PASS** (registro). **Step 5: commit** — `feat(pricing): task mt.pricing.auto_optimize_check [F8]`

---

### Task 8: Endpoints list / detalle / ack + schemas

**Files:** Create `app/schemas/optimization_run.py`; Modify `app/api/routes/channel_pricing.py`; Test `tests/api/test_optimization_runs_api.py`

- [ ] **Step 1: failing test** (reusar `cp_client_with_session` de `test_channel_pricing.py`): insertar un `PricingOptimizationRun` para amazon_uae → `GET /pricing/amazon_uae/optimization-runs?selling_model=b2c` lista 1; `POST /…/{id}/ack` → 204 y `acknowledged_at` set.
- [ ] **Step 2: FAIL**.
- [ ] **Step 3: implement**:
  - `app/schemas/optimization_run.py`: `OptimizationRunSummary` (id, selling_model, skus_scheme_changed, skus_signal_changed, detected_at, acknowledged_at) + `OptimizationRunDetail` (+ drift_reasons, diff_detail, baseline_snapshot_id, revert_snapshot_id).
  - Handlers en `channel_pricing.py` (mismo prefix `/pricing/{channel_code}`):
    - `GET /optimization-runs` (`prices:read`): query por channel + `selling_model` + `unacknowledged: bool=False`; orden `detected_at DESC`; devuelve `list[OptimizationRunSummary]`.
    - `GET /optimization-runs/{run_id}` (`prices:read`): `OptimizationRunDetail`; 404 si no existe / no pertenece al canal.
    - `POST /optimization-runs/{run_id}/ack` (`prices:propose`, 204): set `acknowledged_at=now()`, `acknowledged_by=user.id`.
  - Imports: modelo + schemas + `_resolve_channel_id`.
- [ ] **Step 4: PASS** + suite de channel_pricing verde (no romper). **Step 5: OpenAPI** (Task 9).
- [ ] **Step 6: commit** — `feat(pricing): endpoints optimization-runs (list/detalle/ack) [F8]`

---

### Task 9: OpenAPI + regen tipos

- [ ] **Step 1:** `cd mt-pricing-backend && uv run python -m app.scripts.export_openapi` → actualiza `_bmad-output/planning-artifacts/mt-api-contract-openapi.json`. `git add` ese fichero.
- [ ] **Step 2:** regenerar tipos frontend si el repo lo exige: `npx openapi-typescript@7.13.0 <spec> -o mt-pricing-frontend/lib/api/types.ts` (confirmar comando/versión usados en F4). `git add` types.ts.
- [ ] **Step 3: commit** — `chore(api): regenerar OpenAPI spec + tipos para optimization-runs [F8]`

---

### Task 10: Suite + cobertura + verificación final

- [ ] **Step 1:** `uv run pytest tests/unit/services/pricing/test_optimization_diff.py tests/unit/services/pricing/test_route_fees_from_config.py tests/unit/test_config_drift.py tests/workers/test_auto_optimize_task.py -q` (unit, deben pasar local).
- [ ] **Step 2:** integración (CI): drift_detector, task, endpoints.
- [ ] **Step 3:** `uvx ruff@0.15.14 check --fix . && uvx ruff@0.15.14 format .` en ficheros tocados; `uv run mypy app/` (o CI).
- [ ] **Step 4:** OpenAPI sin drift residual; cobertura ≥70%.
- [ ] **Step 5: commit** — `test(pricing): cobertura F8 (diff, drift_detector, task, endpoints)`

---

## Self-Review (cobertura del diseño)
- D1 (drift a nivel resultado, baseline último snapshot) → Task 3 + Task 6. ✅
- D2 (alerta + snapshot, no aplica) → Task 7 (`create_auto_snapshot` + INSERT run, sin upsert overrides). ✅
- D3 (umbrales settings + drift_reasons) → Task 1 + Task 6. ✅
- D4 (idempotencia/dedup, skip sin baseline/sin cambios) → Task 6 (None) + Task 7 (dedup query). ✅
- Tabla + job → Task 4 + Task 5. Endpoints + ack → Task 8. Revert = `load_scenario` existente (sin tarea). ✅
- AC doc 07: drift > umbral dispara optim auto con snapshot + alerta (NO propuesta) ✅; diff antes/después + revert ✅ (diff en run; revert vía load_scenario).
- OpenAPI (rutas nuevas) → Task 9. ✅
