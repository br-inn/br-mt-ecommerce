# F2 — FX auto + Snapshots auto · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** El Channel Engine lee FX de `fx_rates` (poblada a diario desde ECB con provenance), y optimize/import crean snapshots auto recuperables con limpieza > 90 d.

**Architecture:** `fx_rates` es la única verdad del FX (source `ecb`=auto, `manual`=override; último activo gana; trigger cierra el anterior). Job diario ECB→`fx_rates`. El loader lee `rate_at('EUR','AED',now)` con fallback a `trade_route_params.fx_rate`. Snapshots auto reutilizan `SnapshotKind.AUTO_PRE_*` (ya en el enum) sin migración de enum. Migración solo: backfill no-destructivo + seed de 2 jobs.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, Celery, httpx + tenacity, pytest (integración Postgres).

**Design:** `docs/superpowers/specs/2026-05-31-pricing-fx-auto-snapshots-f2-design.md`

**Pre-flight (contexto verificado):**
- `FXRate` model: `app/db/models/pricing.py:57-96` (cols: from_currency, to_currency, rate Numeric(18,8), effective_from, effective_to, source String(32) ∈ manual/cbuae/ecb/imported/identity, created_by nullable). Trigger `fx_rates_close_previous_trg` auto-cierra el rate anterior (mig 017).
- `FXRateService`: `app/services/fx/fx_rate_service.py` — `rate_at(from_code, to_code, at: datetime) -> FXRate` (lanza `FXRateNotFoundError`), `create_rate(*, from_code, to_code, rate, effective_from, source='manual', actor: User, allow_retroactive=False, reason=None)` (emite audit, setea `created_by=actor.id`).
- `SnapshotKind` (`app/db/enums.py:231-243`): ya tiene `AUTO_PRE_OPTIMIZATION`, `AUTO_PRE_IMPORT`. `PricingScenario` (`app/db/models/channel_pricing.py:443-496`): `kind` (PG enum), `slot` CHAR(1), `config_jsonb`, `retention_until`, índice único parcial **solo** `kind IN ('manual_a','manual_b')`.
- Provenance helpers (`app/services/pricing/provenance.py`): `record_observation(session, *, source_op, target_table, target_field, value, sku=None, channel_id=None, source_ref=None, observed_at=None)`, `emit_audit(...)`.
- `SourceHealth` (`app/db/models/provenance.py:94-120`): PK `source_op`; cols `last_sync_attempt_at`, `last_sync_success_at`, `last_error`, `freshness_sla_minutes`, `rows_last_sync`, `updated_at`. **F1 ya sembró la fila `tesoreria_fx`** (SLA 1440) — solo UPDATE.
- Job pattern: `JobDefinition` (`app/db/models/job.py:31-96`); template calibrator: task `app/workers/tasks/calibrator.py:76` (`@celery_app.task(name="mt.calibrator.retrain_nightly", bind=True, acks_late=True)`), seed `alembic/versions/20260520_154_seed_calibrator_nightly_job.py`.
- Loader seam: `app/services/pricing/loader.py:39-71` (`load_route_and_fees` → `RouteParams(fx_rate=route_row.fx_rate, ...)`). Engine usa `route.fx_rate` en `engine.py:59,100,122,194` (no se toca).
- `save_scenario` snapshot build: `channel_pricing.py:1339-1373` (dict route/fees/targets/overrides). Handlers: `apply_optimization` (`:880`), `import_catalog` (`:992`), `import_logistics` (`:1187`).
- Alembic head: `20260603_149`. F2 migración: revision `20260603_150`, down_revision `20260603_149`.
- CI: ruff==0.15.14, mypy==2.1.0. Comandos backend desde `mt-pricing-backend/`.

---

### Task 1: Config — constantes FX + retención

**Files:**
- Modify: `app/core/config.py`
- Test: `tests/unit/test_config_fx.py`

- [ ] **Step 1: Write failing test**
```python
# tests/unit/test_config_fx.py
from decimal import Decimal
from app.core.config import get_settings

def test_fx_settings_defaults() -> None:
    s = get_settings()
    assert s.FX_USD_AED_PEG == Decimal("3.6725")
    assert "ecb.europa.eu" in s.ECB_FX_URL
    assert s.AUTO_SNAPSHOT_RETENTION_DAYS == 90
```
- [ ] **Step 2: Run → FAIL** (`uv run pytest tests/unit/test_config_fx.py -q`) — AttributeError.
- [ ] **Step 3: Implement** — añadir al `Settings` (pydantic-settings) en `app/core/config.py`, junto a otras constantes:
```python
    # ── FX (F2) ──────────────────────────────────────────────────────────
    FX_USD_AED_PEG: Decimal = Decimal("3.6725")  # peg UAE Central Bank (1997)
    ECB_FX_URL: str = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
    AUTO_SNAPSHOT_RETENTION_DAYS: int = 90
```
Asegurar `from decimal import Decimal` está importado en el módulo. Si las settings usan tipos `Decimal`, confirmar que pydantic v2 las parsea (ya hay otros `Decimal` en el proyecto; si no, usar `Decimal` con `Field(default=...)`).
- [ ] **Step 4: Run → PASS**.
- [ ] **Step 5: Commit** — `git add app/core/config.py tests/unit/test_config_fx.py && git commit -m "feat(pricing): config FX (peg USD/AED, ECB url, retención snapshots) [F2]"`

---

### Task 2: `EcbFxAdapter` — fetch EUR→AED vía ECB + peg

**Files:**
- Create: `app/services/fx/ecb_adapter.py`
- Test: `tests/unit/services/fx/test_ecb_adapter.py`

ECB XML daily (`eurofxref-daily.xml`) tiene forma:
```xml
<gesmes:Envelope ...><Cube><Cube time='2026-05-30'>
  <Cube currency='USD' rate='1.0856'/> ... </Cube></Cube></gesmes:Envelope>
```
`EUR→AED = eur_usd × FX_USD_AED_PEG`.

- [ ] **Step 1: Write failing test** (httpx mockeado con `respx` o monkeypatch del client):
```python
# tests/unit/services/fx/test_ecb_adapter.py
from decimal import Decimal
import pytest
from app.services.fx.ecb_adapter import EcbFxAdapter, EcbQuote

_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01"
 xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
 <Cube><Cube time="2026-05-30">
  <Cube currency="USD" rate="1.0856"/>
  <Cube currency="GBP" rate="0.8512"/>
 </Cube></Cube></gesmes:Envelope>"""

@pytest.mark.asyncio
async def test_fetch_eur_aed_applies_peg(monkeypatch) -> None:
    async def _fake_get(self, url):  # noqa: ANN001
        class R:
            content = _XML
            def raise_for_status(self) -> None: ...
        return R()
    monkeypatch.setattr("httpx.AsyncClient.get", _fake_get)
    q = await EcbFxAdapter().fetch_eur_aed()
    assert q.eur_usd == Decimal("1.0856")
    assert q.eur_aed == (Decimal("1.0856") * Decimal("3.6725"))
    assert q.ecb_date == "2026-05-30"

@pytest.mark.asyncio
async def test_fetch_raises_when_usd_missing(monkeypatch) -> None:
    bad = _XML.replace(b'currency="USD"', b'currency="ZZZ"')
    async def _fake_get(self, url):  # noqa: ANN001
        class R:
            content = bad
            def raise_for_status(self) -> None: ...
        return R()
    monkeypatch.setattr("httpx.AsyncClient.get", _fake_get)
    with pytest.raises(ValueError, match="USD"):
        await EcbFxAdapter().fetch_eur_aed()
```
- [ ] **Step 2: Run → FAIL** (módulo inexistente).
- [ ] **Step 3: Implement** `app/services/fx/ecb_adapter.py`:
```python
"""Adapter ECB → EUR/USD reference rate; deriva EUR/AED vía peg USD/AED."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

import httpx
from defusedxml.ElementTree import fromstring as safe_fromstring  # XXE/billion-laughs safe
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings

logger = logging.getLogger(__name__)
_NS = {"ref": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}
_TIMEOUT_S = 30.0
_RETRY_ATTEMPTS = 3


@dataclass(frozen=True)
class EcbQuote:
    eur_usd: Decimal
    eur_aed: Decimal
    ecb_date: str
    source_ref: str


class EcbFxAdapter:
    """Descarga el XML diario de ECB y calcula EUR→AED."""

    def __init__(self, url: str | None = None, peg: Decimal | None = None) -> None:
        s = get_settings()
        self._url = url or s.ECB_FX_URL
        self._peg = peg or s.FX_USD_AED_PEG

    @retry(stop=stop_after_attempt(_RETRY_ATTEMPTS),
           wait=wait_exponential(multiplier=1, max=10), reraise=True)
    async def _get(self) -> bytes:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            resp = await client.get(self._url)
            resp.raise_for_status()
            return resp.content

    async def fetch_eur_aed(self) -> EcbQuote:
        raw = await self._get()
        root = safe_fromstring(raw)  # defusedxml — no XXE/entity expansion
        day_cube = root.find(".//ref:Cube[@time]", _NS)
        if day_cube is None:
            raise ValueError("ECB XML: no daily Cube[@time] found")
        ecb_date = day_cube.attrib["time"]
        usd = None
        for c in day_cube.findall("ref:Cube", _NS):
            if c.attrib.get("currency") == "USD":
                usd = Decimal(c.attrib["rate"])
                break
        if usd is None:
            raise ValueError("ECB XML: USD rate not present")
        eur_aed = usd * self._peg
        return EcbQuote(
            eur_usd=usd,
            eur_aed=eur_aed,
            ecb_date=ecb_date,
            source_ref=f"ecb:{ecb_date}:eurusd={usd}:peg={self._peg}",
        )
```
- [ ] **Step 4: Dep `defusedxml`** — verificar que está en `pyproject.toml`; si no, `uv add defusedxml` (parseo XML seguro contra XXE/billion-laughs; ECB es HTTPS pero defensa en profundidad). Re-lock. Luego Run → PASS. (Si el proyecto no tiene `respx`, el monkeypatch de `httpx.AsyncClient.get` basta — verificar imports.)
- [ ] **Step 5: Commit** — `feat(pricing): EcbFxAdapter (EUR→USD ECB + peg USD/AED) [F2]`

---

### Task 3: Relajar `create_rate` para actor de sistema

**Files:**
- Modify: `app/services/fx/fx_rate_service.py`
- Test: `tests/services/fx/test_fx_rate_service_system_actor.py`

- [ ] **Step 1: Write failing test** (integración — DB):
```python
# tests/services/fx/test_fx_rate_service_system_actor.py
from datetime import UTC, datetime
from decimal import Decimal
import pytest
from app.services.fx.fx_rate_service import FXRateService

@pytest.mark.asyncio
async def test_create_rate_accepts_none_actor(db_session) -> None:
    svc = FXRateService(db_session)
    rate = await svc.create_rate(
        from_code="EUR", to_code="AED", rate=Decimal("3.98"),
        effective_from=datetime.now(UTC), source="ecb", actor=None,
    )
    assert rate.rate == Decimal("3.98")
    assert rate.created_by is None
```
- [ ] **Step 2: Run → FAIL** (TypeError: actor required / `actor.id` on None).
- [ ] **Step 3: Implement** — en `create_rate`: cambiar firma `actor: User` → `actor: User | None`. Guardar `created_by` y audit con None-safe:
```python
        if hasattr(new_rate, "created_by"):
            new_rate.created_by = actor.id if actor is not None else None
        ...
        await self.audit.record(
            ...,
            actor_id=actor.id if actor is not None else None,
            actor_email=actor.email if actor is not None else None,
            ...
        )
```
Verificar que `AuditRepository.record` acepta `actor_id=None`/`actor_email=None` (leer su firma; el hash-chain ADR-076 lo permite — `actor_id` es nullable). Si NO los acepta, pasar `actor_email="system@mt.internal"` y `actor_id=None`.
- [ ] **Step 4: Run → PASS**.
- [ ] **Step 5: Commit** — `feat(pricing): create_rate admite actor de sistema (None) [F2]`

---

### Task 4: `fx_sync_service` — orquestación idempotente

**Files:**
- Create: `app/services/fx/fx_sync_service.py`
- Test: `tests/services/fx/test_fx_sync_service.py`

- [ ] **Step 1: Write failing test** (integración, adapter mockeado):
```python
# tests/services/fx/test_fx_sync_service.py
from decimal import Decimal
import pytest
from sqlalchemy import select, text
from app.db.models.provenance import SourceHealth
from app.services.fx import fx_sync_service
from app.services.fx.ecb_adapter import EcbQuote

class _FakeAdapter:
    async def fetch_eur_aed(self):
        return EcbQuote(Decimal("1.085"), Decimal("3.985"), "2026-05-30", "ecb:test")

@pytest.mark.asyncio
async def test_sync_inserts_rate_observation_and_health(db_session, monkeypatch) -> None:
    res = await fx_sync_service.sync_ecb_eur_aed(db_session, adapter=_FakeAdapter())
    assert res["status"] == "ok" and res["inserted"] == 1
    row = (await db_session.execute(text(
        "SELECT rate, source FROM fx_rates WHERE from_currency='EUR' AND to_currency='AED' "
        "AND effective_to IS NULL"))).first()
    assert row.source == "ecb" and row.rate == Decimal("3.985")
    health = (await db_session.execute(
        select(SourceHealth).where(SourceHealth.source_op == "tesoreria_fx"))).scalar_one()
    assert health.last_sync_success_at is not None and health.rows_last_sync == 1

@pytest.mark.asyncio
async def test_sync_idempotent_same_day(db_session) -> None:
    await fx_sync_service.sync_ecb_eur_aed(db_session, adapter=_FakeAdapter())
    res2 = await fx_sync_service.sync_ecb_eur_aed(db_session, adapter=_FakeAdapter())
    assert res2["inserted"] == 0 and res2["status"] == "ok"
```
- [ ] **Step 2: Run → FAIL**.
- [ ] **Step 3: Implement** `app/services/fx/fx_sync_service.py`:
```python
"""Sincroniza EUR→AED desde ECB hacia fx_rates con provenance (F2)."""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import SourceOp
from app.db.models.provenance import SourceHealth
from app.services.fx.ecb_adapter import EcbFxAdapter
from app.services.fx.fx_rate_service import FXRateService
from app.services.pricing.provenance import record_observation

logger = logging.getLogger(__name__)


async def _ecb_rate_exists_today(session: AsyncSession) -> bool:
    today = datetime.now(UTC).date().isoformat()
    row = (
        await session.execute(
            text(
                "SELECT 1 FROM fx_rates WHERE from_currency='EUR' AND to_currency='AED' "
                "AND source='ecb' AND effective_from::date = :d LIMIT 1"
            ),
            {"d": today},
        )
    ).first()
    return row is not None


async def _touch_health(session: AsyncSession, *, success: bool, rows: int,
                        error: str | None) -> None:
    now = datetime.now(UTC)
    await session.execute(
        update(SourceHealth)
        .where(SourceHealth.source_op == SourceOp.TESORERIA_FX.value)
        .values(
            last_sync_attempt_at=now,
            last_sync_success_at=now if success else SourceHealth.last_sync_success_at,
            last_error=None if success else error,
            rows_last_sync=rows,
            updated_at=now,
        )
    )


async def sync_ecb_eur_aed(
    session: AsyncSession, *, adapter: EcbFxAdapter | None = None
) -> dict[str, Any]:
    """Idempotente: si ya hay rate ecb de hoy, no inserta. Nunca lanza al beat."""
    adapter = adapter or EcbFxAdapter()
    try:
        if await _ecb_rate_exists_today(session):
            await _touch_health(session, success=True, rows=0, error=None)
            await session.commit()
            return {"status": "ok", "inserted": 0, "reason": "already_synced_today"}
        quote = await adapter.fetch_eur_aed()
        svc = FXRateService(session)
        await svc.create_rate(
            from_code="EUR", to_code="AED", rate=quote.eur_aed,
            effective_from=datetime.now(UTC), source="ecb", actor=None,
        )
        await record_observation(
            session, source_op=SourceOp.TESORERIA_FX.value,
            target_table="fx_rates", target_field="rate", value=str(quote.eur_aed),
            source_ref=quote.source_ref,
        )
        await _touch_health(session, success=True, rows=1, error=None)
        await session.commit()
        return {"status": "ok", "inserted": 1, "eur_aed": str(quote.eur_aed)}
    except Exception as exc:  # noqa: BLE001 — el beat no debe caer
        logger.exception("fx.sync.failed")
        await session.rollback()
        await _touch_health(session, success=False, rows=0, error=str(exc)[:500])
        await session.commit()
        return {"status": "error", "inserted": 0, "error": str(exc)[:200]}
```
- [ ] **Step 4: Run → PASS**.
- [ ] **Step 5: Commit** — `feat(pricing): fx_sync_service ECB→fx_rates idempotente + source_health [F2]`

---

### Task 5: Task Celery `mt.fx.sync_daily`

**Files:**
- Create: `app/workers/tasks/fx.py`
- Test: `tests/workers/test_fx_task.py`

- [ ] **Step 1: Write failing test**:
```python
# tests/workers/test_fx_task.py
def test_fx_task_registered() -> None:
    from app.workers.celery_app import celery_app  # ajustar al import real
    assert "mt.fx.sync_daily" in celery_app.tasks
```
(Confirmar el módulo real del `celery_app` — en calibrator.py es `from app.workers... import celery_app`.)
- [ ] **Step 2: Run → FAIL**.
- [ ] **Step 3: Implement** `app/workers/tasks/fx.py` (patrón calibrator):
```python
"""Task diaria: sincroniza FX EUR→AED desde ECB (F2)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.workers.celery_app import celery_app  # ajustar al import real del proyecto
from app.db.session import get_sessionmaker        # ajustar al helper real de sesión async
from app.services.fx.fx_sync_service import sync_ecb_eur_aed

logger = logging.getLogger(__name__)


async def _run() -> dict[str, Any]:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        return await sync_ecb_eur_aed(session)


@celery_app.task(name="mt.fx.sync_daily", bind=True, acks_late=True)
def sync_daily(self) -> dict[str, Any]:  # noqa: ANN001
    result = asyncio.run(_run())
    logger.info("fx.sync.done", extra=result)
    return result
```
Verificar el patrón de sesión async en `calibrator.py` (`_run_retrain`) y replicar el `get_sessionmaker`/`AsyncSessionLocal` exacto. Asegurar que el módulo se **importa** en el autodiscovery de tasks (mirar dónde se listan los `include=[...]` o `autodiscover_tasks` en `celery_app`).
- [ ] **Step 4: Run → PASS**.
- [ ] **Step 5: Commit** — `feat(pricing): task celery mt.fx.sync_daily [F2]`

---

### Task 6: Loader lee `fx_rates` con fallback

**Files:**
- Modify: `app/services/pricing/loader.py`
- Test: `tests/services/pricing/test_loader_fx_source.py`

- [ ] **Step 1: Write failing test** (integración):
```python
# tests/services/pricing/test_loader_fx_source.py
from datetime import UTC, datetime
from decimal import Decimal
import pytest
# helpers: crear canal + trade_route con fx_rate=4.00; crear fx_rates EUR→AED=3.90 source='ecb'

@pytest.mark.asyncio
async def test_loader_prefers_fx_rates(db_session, seeded_channel) -> None:
    # seeded_channel: route_row.fx_rate = Decimal("4.00"); fx_rates EUR→AED activo = 3.90
    from app.services.pricing.loader import ParameterLoader
    route, _fees, _schemes = await ParameterLoader(db_session).load_route_and_fees(seeded_channel.id)
    assert route.fx_rate == Decimal("3.90")  # viene de fx_rates, no del 4.00 manual

@pytest.mark.asyncio
async def test_loader_falls_back_to_route_fx_rate(db_session, channel_without_fx_rates) -> None:
    from app.services.pricing.loader import ParameterLoader
    route, _f, _s = await ParameterLoader(db_session).load_route_and_fees(channel_without_fx_rates.id)
    assert route.fx_rate == Decimal("4.00")  # sin rate en fx_rates → fallback
```
(Reusar fixtures/factories existentes de `tests/services/pricing/`; si no existen, crear helper local que inserte channel + trade_route_params + fx_rates con SQL directo.)
- [ ] **Step 2: Run → FAIL** (loader aún devuelve 4.00 siempre).
- [ ] **Step 3: Implement** — en `load_route_and_fees`, tras obtener `route_row`, intentar `fx_rates`:
```python
        from app.services.fx.fx_rate_service import FXRateService, FXRateNotFoundError
        effective_fx = route_row.fx_rate
        try:
            fx = await FXRateService(self.session).rate_at("EUR", "AED", datetime.now(UTC))
            effective_fx = fx.rate
        except FXRateNotFoundError:
            pass  # fallback: usa route_row.fx_rate (legacy)
        route = RouteParams(
            fx_rate=effective_fx,
            fx_buffer_pct=route_row.fx_buffer_pct,
            ...
        )
```
Importar `datetime, UTC`. Confirmar nombre real de la clase loader (`ParameterLoader`) y que `self.session` existe.
- [ ] **Step 4: Run → PASS**.
- [ ] **Step 5: Commit** — `feat(pricing): engine lee FX de fx_rates con fallback a trade_route [F2]`

---

### Task 7: `scenarios.py` — `build_scenario_config` + `create_auto_snapshot`

**Files:**
- Create: `app/services/pricing/scenarios.py`
- Test: `tests/services/pricing/test_auto_snapshot.py`

- [ ] **Step 1: Write failing test** (integración):
```python
# tests/services/pricing/test_auto_snapshot.py
import pytest
from sqlalchemy import select
from app.db.models.channel_pricing import PricingScenario
from app.db.enums import SnapshotKind
from app.services.pricing.scenarios import create_auto_snapshot

@pytest.mark.asyncio
async def test_create_auto_snapshot_optimization(db_session, seeded_channel) -> None:
    snap_id = await create_auto_snapshot(
        db_session, channel_id=seeded_channel.id, selling_model="b2c",
        kind=SnapshotKind.AUTO_PRE_OPTIMIZATION,
    )
    await db_session.commit()
    row = (await db_session.execute(
        select(PricingScenario).where(PricingScenario.id == snap_id))).scalar_one()
    assert row.kind == "auto_pre_optimization"
    assert row.retention_until is not None
    assert "route" in row.config_jsonb and "overrides" in row.config_jsonb
```
- [ ] **Step 2: Run → FAIL**.
- [ ] **Step 3: Implement** `app/services/pricing/scenarios.py` — extraer el armado del dict (channel_pricing.py:1339-1373) a `build_scenario_config(session, channel_id, selling_model) -> dict` (con sus queries de route_row/fee_row/targets/overrides), y:
```python
async def create_auto_snapshot(
    session: AsyncSession, *, channel_id: UUID, selling_model: str, kind: SnapshotKind
) -> UUID:
    config = await build_scenario_config(session, channel_id, selling_model)
    retention = datetime.now(UTC) + timedelta(days=get_settings().AUTO_SNAPSHOT_RETENTION_DAYS)
    row = PricingScenario(
        channel_id=channel_id, selling_model=selling_model, slot="A",
        label=f"auto:{kind.value}", config_jsonb=config, kind=kind.value,
        retention_until=retention,
    )
    session.add(row)
    await session.flush()
    return row.id
```
- [ ] **Step 4: Run → PASS**.
- [ ] **Step 5: Commit** — `feat(pricing): scenarios.create_auto_snapshot + build_scenario_config (DRY) [F2]`

---

### Task 8: Cablear auto-snapshots en optimize/import + refactor `save_scenario`

**Files:**
- Modify: `app/api/routes/channel_pricing.py`
- Test: `tests/api/test_auto_snapshot_wiring.py`

- [ ] **Step 1: Write failing test** (API, integración):
```python
# tests/api/test_auto_snapshot_wiring.py — usar client + auth helper existentes
@pytest.mark.asyncio
async def test_optimize_apply_creates_auto_snapshot(client, seeded_channel, auth_headers) -> None:
    # contar scenarios antes
    res = await client.post(f"/api/v1/pricing/{seeded_channel.code}/optimize/apply",
                            json={...minimal valid body...}, headers=auth_headers)
    assert res.status_code == 200
    # tras la llamada existe ≥1 PricingScenario kind='auto_pre_optimization'
```
- [ ] **Step 2: Run → FAIL** (no se crea snapshot).
- [ ] **Step 3: Implement**:
  - En `apply_optimization` (`:880`): **antes** del upsert de `ChannelMarginOverride`, llamar
    `await create_auto_snapshot(session, channel_id=channel_id, selling_model=body.selling_model.value, kind=SnapshotKind.AUTO_PRE_OPTIMIZATION)`.
  - En `import_catalog` (`:992`): **antes** de persistir, `kind=SnapshotKind.AUTO_PRE_IMPORT`.
  - Refactor `save_scenario` para reusar `build_scenario_config` (DRY — borrar el dict inline, llamar al helper).
  - Imports: `from app.services.pricing.scenarios import build_scenario_config, create_auto_snapshot` + `from app.db.enums import SnapshotKind`.
- [ ] **Step 4: Run → PASS** + correr `tests/` de scenarios existentes (no romper save_scenario).
- [ ] **Step 5: OpenAPI** — no cambia firma/schema, pero por regla CI regenerar y verificar sin diff:
```bash
uv run python -m app.scripts.export_openapi
git diff --quiet _bmad-output/planning-artifacts/mt-api-contract-openapi.json || echo "DRIFT"
```
- [ ] **Step 6: Commit** — `feat(pricing): snapshot auto antes de optimize/import + DRY save_scenario [F2]`

---

### Task 9: Task cleanup snapshots auto

**Files:**
- Create: `app/workers/tasks/pricing_snapshots.py`
- Test: `tests/workers/test_snapshot_cleanup.py`

- [ ] **Step 1: Write failing test** (integración):
```python
# tests/workers/test_snapshot_cleanup.py
@pytest.mark.asyncio
async def test_cleanup_deletes_expired_auto_only(db_session, seeded_channel) -> None:
    # crear: auto vencido (retention_until pasado), auto reciente, manual_a
    from app.services.pricing.snapshot_cleanup import cleanup_expired_auto_snapshots
    deleted = await cleanup_expired_auto_snapshots(db_session)
    await db_session.commit()
    assert deleted == 1  # solo el auto vencido
    # manual_a y auto reciente siguen existiendo
```
- [ ] **Step 2: Run → FAIL**.
- [ ] **Step 3: Implement**:
  - Lógica pura en `app/services/pricing/snapshot_cleanup.py`:
```python
async def cleanup_expired_auto_snapshots(session: AsyncSession) -> int:
    res = await session.execute(text(
        "DELETE FROM pricing_scenarios WHERE kind LIKE 'auto\\_%' ESCAPE '\\' "
        "AND retention_until IS NOT NULL AND retention_until < now()"))
    return res.rowcount or 0
```
  - Task `app/workers/tasks/pricing_snapshots.py` (patrón calibrator, name `mt.pricing.cleanup_auto_snapshots`, asyncio.run → cleanup + commit).
- [ ] **Step 4: Run → PASS**.
- [ ] **Step 5: Commit** — `feat(pricing): cleanup snapshots auto > retención + task celery [F2]`

---

### Task 10: Migración — backfill fx_rates + seed 2 jobs

**Files:**
- Create: `alembic/versions/20260603_150_fx_backfill_and_jobs.py`

- [ ] **Step 1: Implement migración** (revision `20260603_150`, down_revision `20260603_149`):
```python
"""F2: backfill fx_rates desde trade_route_params + seed jobs FX/cleanup."""
from alembic import op

revision = "20260603_150"
down_revision = "20260603_149"
branch_labels = None
depends_on = None

_JOBS = [
    ("fx-sync-daily", "mt.fx.sync_daily",
     "Sync diario EUR→AED desde ECB hacia fx_rates", "0 1 * * *", "default"),
    ("pricing-cleanup-auto-snapshots", "mt.pricing.cleanup_auto_snapshots",
     "Limpieza nightly de snapshots auto vencidos (>90d)", "0 2 * * *", "default"),
]

def upgrade() -> None:
    # 1. Backfill no destructivo: por cada fx_rate distinto en trade_route_params sin rate activo
    #    en fx_rates EUR→AED, insertar source='manual' (preserva el precio actual del engine).
    op.execute("""
        INSERT INTO fx_rates (id, from_currency, to_currency, rate, effective_from, source)
        SELECT gen_random_uuid(), 'EUR', 'AED', t.fx_rate, now(), 'manual'
        FROM (SELECT DISTINCT fx_rate FROM trade_route_params WHERE fx_rate IS NOT NULL) t
        WHERE NOT EXISTS (
            SELECT 1 FROM fx_rates f
            WHERE f.from_currency='EUR' AND f.to_currency='AED' AND f.effective_to IS NULL
        )
        LIMIT 1;
    """)
    # (Solo se necesita 1 rate activo EUR→AED; si hay varios fx_rate manuales distintos,
    #  se toma uno — el engine ahora usa fx_rates como verdad única. El trigger cierra anteriores.)

    # 2. Seed jobs (idempotente)
    for code, task, desc, cron, queue in _JOBS:
        op.execute(f"""
            INSERT INTO job_definitions
                (id, code, task_name, description, owner, schedule_type,
                 cron_expression, timezone, queue, enabled, args, kwargs)
            VALUES
                (gen_random_uuid(), '{code}', '{task}', '{desc}', 'infra', 'cron',
                 '{cron}', 'Asia/Dubai', '{queue}', true, '[]'::jsonb, '{{}}'::jsonb)
            ON CONFLICT (code) DO NOTHING;
        """)

def downgrade() -> None:
    op.execute("DELETE FROM job_definitions WHERE code IN "
               "('fx-sync-daily','pricing-cleanup-auto-snapshots');")
    op.execute("DELETE FROM fx_rates WHERE from_currency='EUR' AND to_currency='AED' "
               "AND source='manual' AND created_by IS NULL;")
```
**Nota backfill:** si hubiera múltiples `fx_rate` distintos entre rutas, el diseño asume FX único por canal EUR→AED (es un peg global, no por-ruta). El `LIMIT 1` + `NOT EXISTS` garantiza un único rate activo. Revisar con migration-reviewer.
- [ ] **Step 2: Verificar** que no rompe el head: `uv run alembic heads` (1 solo head = 20260603_150). `uv run alembic check` (sin drift de modelos — no añadimos columnas, solo data).
- [ ] **Step 3: Review** — dispatch **migration-reviewer** sobre este fichero (split public.*, idempotencia, reversibilidad, índices). Aplicar correcciones.
- [ ] **Step 4: Commit** — `feat(pricing): migración backfill fx_rates + seed jobs FX/cleanup [F2]`

---

### Task 11: Suite + cobertura + verificación final

- [ ] **Step 1:** correr la suite de pricing/fx/workers: `uv run pytest tests/services/fx tests/services/pricing tests/workers/test_fx_task.py tests/workers/test_snapshot_cleanup.py tests/api/test_auto_snapshot_wiring.py -q`
- [ ] **Step 2:** test de **no-regresión de precio** post-backfill: crear un canal con `route.fx_rate=X`, correr el backfill (o sembrar fx_rates EUR→AED=X), pedir `GET /pricing/{code}/product/{sku}` y confirmar que el `landed_aed`/techo es idéntico al pre-F2 (mismo X). Si falla, el seam del loader o el backfill están mal.
- [ ] **Step 3:** lint/format/type CI-exactos:
```bash
uv run ruff check --fix . && uv run ruff format . && uv run mypy app/
```
- [ ] **Step 4:** OpenAPI sin drift (Task 8 Step 5). Cobertura ≥ 70 %: `uv run pytest --cov=app --cov-report=term-missing -q`.
- [ ] **Step 5: Commit** — `test(pricing): cobertura F2 (fx sync, loader, snapshots, no-regresión precio)`

---

## Self-Review (cobertura del diseño)
- D1 (fx_rates única verdad + backfill no destructivo) → Task 6 + Task 10. ✅
- D2 (ECB + peg USD/AED) → Task 1 (peg) + Task 2 (adapter). ✅
- D3 (idempotencia + no-crash) → Task 4 (`_ecb_rate_exists_today`, try/except). ✅
- D4 (snapshots auto reutilizan F1) → Task 7 + Task 8. ✅
- Job diario ECB → Task 5 + Task 10. Cleanup → Task 9 + Task 10. ✅
- Criterios aceptación doc 07: job FX diario `source='ecb'` ✅ (T4/T5/T10); optimize crea snapshot recuperable ✅ (T8); override manual con razón/badge ✅ (manual via `create_rate(source='manual')`, badge lo deriva F4). ✅
- Sin cambios de ruta/schema → OpenAPI sin drift ✅ (T8/T11).
