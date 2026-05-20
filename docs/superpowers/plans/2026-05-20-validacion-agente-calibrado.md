# Agente de validación calibrado — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Completar el módulo `/catalogo/validacion` y construir un agente de IA semi-autónomo que cierre el lazo del pipeline de matching, arrancando en modo sombra con calibración conformal.

**Architecture:** El agente corre inline al final de `refresh_sku_task`. En modo `shadow` registra su veredicto en `match_agent_decisions` sin tocar la DB; en modo `active` aplica `status` a `match_candidates`. La señal de decisión es conformal (`review_priority` del `ConformalWrapper`) cuando hay un calibrador entrenado, con fallback al signal sin calibrar (`_enhanced.auto_validate`) durante el bootstrap. Cada validación humana escribe `golden_labels` — el dataset de entrenamiento del calibrador.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + Alembic + Celery (backend); Next.js 16 + React 19 + TanStack Query + Playwright (frontend).

**Spec de referencia:** `docs/superpowers/specs/2026-05-20-validacion-agente-calibrado-design.md`

---

## Estructura de ficheros

**Crear:**
- `mt-pricing-backend/app/schemas/match_agent.py` — schemas Pydantic del agente
- `mt-pricing-backend/app/db/models/match_agent.py` — modelos ORM `MatchAgentConfig` + `MatchAgentDecision`
- `mt-pricing-backend/app/repositories/match_agent.py` — repos de config y decisiones
- `mt-pricing-backend/app/services/matching/validation_agent.py` — servicio `MatchValidationAgent`
- `mt-pricing-backend/alembic/versions/<rev>_match_agent.py` — migración (2 tablas)
- `mt-pricing-backend/tests/unit/services/matching/test_validation_agent.py`
- `mt-pricing-backend/tests/integration/test_match_agent_routes.py`
- `mt-pricing-frontend/lib/hooks/matches/use-match-agent.ts` — hooks del agente
- `mt-pricing-frontend/app/(app)/catalogo/validacion/_components/agent-metrics-panel.tsx`
- `mt-pricing-frontend/app/(app)/catalogo/validacion/_components/bulk-accept-bar.tsx`
- `mt-pricing-frontend/app/(app)/catalogo/validacion/_components/discard-reason-dialog.tsx`

**Modificar:**
- `mt-pricing-backend/app/services/matching/match_service.py` — wiring conformal + golden_labels en validate/discard
- `mt-pricing-backend/app/workers/tasks/comparator.py` — invocar el agente
- `mt-pricing-backend/app/api/routes/matches.py` — endpoints `agent/config`, `agent/metrics`, `revert`
- `mt-pricing-backend/app/core/config.py` — flag `MATCH_AGENT_ENABLED`
- `mt-pricing-frontend/lib/api/endpoints/matches.ts` — tipos + cliente del agente
- `mt-pricing-frontend/app/(app)/catalogo/validacion/page.tsx` — dedupe, teclado, navegación, tabs
- `mt-pricing-frontend/app/(app)/catalogo/validacion/_components/candidate-card.tsx` — chips de confianza
- `mt-pricing-frontend/tests/e2e/13-validacion-matches.spec.ts` — arreglar + extender
- `mt-pricing-frontend/tests/e2e/fixtures/seed-extended.ts` — mocks del agente

---

# TRACK 0 — Contratos (bloquea T1/T2/T3)

## Task 1: Schemas Pydantic del agente

**Files:**
- Create: `mt-pricing-backend/app/schemas/match_agent.py`
- Test: `mt-pricing-backend/tests/unit/schemas/test_match_agent_schemas.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/schemas/test_match_agent_schemas.py
"""Tests de schemas del agente de validación."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.match_agent import MatchAgentConfigUpdate, MatchAgentMetrics


def test_config_update_rejects_alpha_out_of_range():
    with pytest.raises(ValidationError):
        MatchAgentConfigUpdate(alpha=1.5)


def test_config_update_accepts_partial():
    upd = MatchAgentConfigUpdate(mode="active")
    assert upd.mode == "active"
    assert upd.alpha is None


def test_metrics_shadow_precision_optional():
    m = MatchAgentMetrics(
        golden_labels_total=10,
        min_labels_gate=200,
        gate_reached=False,
        shadow_decisions=0,
        shadow_precision=None,
        calibrator_version=None,
        calibrator_brier=None,
        calibrator_ece=None,
        calibrator_trained_on=None,
        mode="shadow",
    )
    assert m.gate_reached is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mt-pricing-backend && pytest tests/unit/schemas/test_match_agent_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.schemas.match_agent'`

- [ ] **Step 3: Write the schema module**

```python
# app/schemas/match_agent.py
"""Pydantic schemas — MatchValidationAgent (config, métricas, decisiones).

Alineado con `app/db/models/match_agent.py` y el patrón de los demás schemas
(extra=forbid, from_attributes=True).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

AgentMode = Literal["shadow", "active"]
AgentVerdict = Literal["auto_validate", "auto_discard", "human"]
AgentSignal = Literal["conformal", "bootstrap"]


class MatchAgentConfigResponse(BaseModel):
    """Fila singleton de configuración del agente."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    mode: AgentMode
    alpha: Decimal
    min_labels_gate: int
    updated_at: datetime


class MatchAgentConfigUpdate(BaseModel):
    """Body de PUT /matches/agent/config — todos los campos opcionales."""

    model_config = ConfigDict(extra="forbid")

    mode: AgentMode | None = None
    alpha: Decimal | None = Field(default=None, gt=0, lt=1)
    min_labels_gate: int | None = Field(default=None, ge=1)


class MatchAgentMetrics(BaseModel):
    """Métricas del agente para el panel de la UI."""

    model_config = ConfigDict(extra="forbid")

    golden_labels_total: int
    min_labels_gate: int
    gate_reached: bool
    shadow_decisions: int
    shadow_precision: float | None = Field(
        default=None,
        description="Aciertos / decisiones con human_outcome conocido. None si no hay datos.",
    )
    calibrator_version: str | None = None
    calibrator_brier: float | None = None
    calibrator_ece: float | None = None
    calibrator_trained_on: int | None = None
    mode: AgentMode


class MatchAgentDecisionResponse(BaseModel):
    """Una decisión registrada del agente."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    candidate_id: UUID
    product_sku: str
    verdict: AgentVerdict
    mode: AgentMode
    applied: bool
    signal: AgentSignal
    score: int
    calibrated_confidence: Decimal | None = None
    review_priority: str | None = None
    calibrator_version: str | None = None
    human_outcome: str | None = None
    created_at: datetime
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mt-pricing-backend && pytest tests/unit/schemas/test_match_agent_schemas.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/schemas/match_agent.py mt-pricing-backend/tests/unit/schemas/test_match_agent_schemas.py
git commit -m "feat(matches): add MatchValidationAgent Pydantic schemas"
```

---

## Task 2: Tipos TS del agente (contrato frontend)

**Files:**
- Modify: `mt-pricing-frontend/lib/api/endpoints/matches.ts` (añadir al final, antes del `export const matchesApi`)

- [ ] **Step 1: Añadir los tipos del agente**

En `matches.ts`, tras la interfaz `MatchFilters` (línea ~77), insertar:

```typescript
// --- Agente de validación ---
export type AgentMode = "shadow" | "active";
export type AgentVerdict = "auto_validate" | "auto_discard" | "human";

export interface MatchAgentConfig {
  mode: AgentMode;
  alpha: string;
  min_labels_gate: number;
  updated_at: string;
}

export interface MatchAgentConfigUpdate {
  mode?: AgentMode;
  alpha?: number;
  min_labels_gate?: number;
}

export interface MatchAgentMetrics {
  golden_labels_total: number;
  min_labels_gate: number;
  gate_reached: boolean;
  shadow_decisions: number;
  shadow_precision: number | null;
  calibrator_version: string | null;
  calibrator_brier: number | null;
  calibrator_ece: number | null;
  calibrator_trained_on: number | null;
  mode: AgentMode;
}
```

- [ ] **Step 2: Añadir los métodos del cliente al objeto `matchesApi`**

Dentro del objeto `matchesApi`, tras `clearAll`, añadir:

```typescript
  agentConfig: (): Promise<MatchAgentConfig> =>
    authedFetch<MatchAgentConfig>("/api/v1/matches/agent/config"),
  updateAgentConfig: (body: MatchAgentConfigUpdate): Promise<MatchAgentConfig> =>
    authedFetch<MatchAgentConfig>("/api/v1/matches/agent/config", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  agentMetrics: (): Promise<MatchAgentMetrics> =>
    authedFetch<MatchAgentMetrics>("/api/v1/matches/agent/metrics"),
  revert: (id: string): Promise<MatchCandidate> =>
    authedFetch<MatchCandidate>(`/api/v1/matches/${id}/revert`, { method: "POST" }),
```

- [ ] **Step 3: Verificar typecheck**

Run: `cd mt-pricing-frontend && npx tsc --noEmit`
Expected: sin errores nuevos.

- [ ] **Step 4: Commit**

```bash
git add mt-pricing-frontend/lib/api/endpoints/matches.ts
git commit -m "feat(matches): add agent API types and client methods"
```

---

# TRACK 1 — Backend

## Task 3: Modelos ORM del agente

**Files:**
- Create: `mt-pricing-backend/app/db/models/match_agent.py`
- Test: `mt-pricing-backend/tests/unit/db/test_match_agent_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/db/test_match_agent_models.py
"""Tests de los modelos ORM del agente."""
from __future__ import annotations

from app.db.models.match_agent import MatchAgentConfig, MatchAgentDecision


def test_config_tablename():
    assert MatchAgentConfig.__tablename__ == "match_agent_config"


def test_decision_tablename():
    assert MatchAgentDecision.__tablename__ == "match_agent_decisions"


def test_config_columns_present():
    cols = set(MatchAgentConfig.__table__.columns.keys())
    assert {"id", "mode", "alpha", "min_labels_gate", "updated_by", "updated_at"} <= cols


def test_decision_columns_present():
    cols = set(MatchAgentDecision.__table__.columns.keys())
    assert {
        "id", "candidate_id", "product_sku", "verdict", "mode", "applied",
        "signal", "score", "calibrated_confidence", "review_priority",
        "calibrator_version", "human_outcome", "created_at",
    } <= cols
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mt-pricing-backend && pytest tests/unit/db/test_match_agent_models.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the models module**

```python
# app/db/models/match_agent.py
"""MatchAgentConfig + MatchAgentDecision — agente de validación de matches.

MatchAgentConfig: fila singleton (id=1) con la configuración editable del
agente (modo sombra/activo, alpha conformal, gate de labels mínimos).

MatchAgentDecision: serie temporal — un registro por cada veredicto del agente
(sombra o activo). human_outcome se rellena al validar/descartar para medir la
precisión de sombra.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import UuidPkMixin
from app.db.types import UUID_PG

AGENT_MODES: tuple[str, ...] = ("shadow", "active")
AGENT_VERDICTS: tuple[str, ...] = ("auto_validate", "auto_discard", "human")
AGENT_SIGNALS: tuple[str, ...] = ("conformal", "bootstrap")


class MatchAgentConfig(Base):
    """Configuración singleton del agente (siempre id=1)."""

    __tablename__ = "match_agent_config"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    mode: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'shadow'")
    )
    alpha: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), nullable=False, server_default=text("0.02")
    )
    min_labels_gate: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("200")
    )
    updated_by: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_match_agent_config_singleton"),
        CheckConstraint(
            "mode IN ('shadow','active')", name="ck_match_agent_config_mode"
        ),
        CheckConstraint(
            "alpha > 0 AND alpha < 1", name="ck_match_agent_config_alpha"
        ),
        CheckConstraint(
            "min_labels_gate >= 1", name="ck_match_agent_config_gate"
        ),
    )


class MatchAgentDecision(UuidPkMixin, Base):
    """Registro de un veredicto del agente sobre un candidato."""

    __tablename__ = "match_agent_decisions"

    candidate_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("match_candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_sku: Mapped[str] = mapped_column(Text, nullable=False)
    verdict: Mapped[str] = mapped_column(String(16), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    applied: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    signal: Mapped[str] = mapped_column(String(24), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    calibrated_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    review_priority: Mapped[str | None] = mapped_column(String(16))
    calibrator_version: Mapped[str | None] = mapped_column(Text)
    human_outcome: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "verdict IN ('auto_validate','auto_discard','human')",
            name="ck_match_agent_decisions_verdict",
        ),
        CheckConstraint(
            "mode IN ('shadow','active')", name="ck_match_agent_decisions_mode"
        ),
        CheckConstraint(
            "signal IN ('conformal','bootstrap')",
            name="ck_match_agent_decisions_signal",
        ),
        CheckConstraint(
            "human_outcome IS NULL OR human_outcome IN ('validated','discarded')",
            name="ck_match_agent_decisions_outcome",
        ),
        Index("idx_match_agent_decisions_sku", "product_sku"),
        Index("idx_match_agent_decisions_created", "created_at"),
        Index("idx_match_agent_decisions_verdict_mode", "verdict", "mode"),
        Index("idx_match_agent_decisions_candidate", "candidate_id"),
    )
```

> **Nota:** `MatchAgentConfig` define su PK como `SmallInteger` fijo (id=1), por eso no usa `UuidPkMixin`. `MatchAgentDecision` sí usa `UuidPkMixin`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mt-pricing-backend && pytest tests/unit/db/test_match_agent_models.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Registrar el modelo en el metadata de Alembic**

Verificar que `app/db/models/__init__.py` (o el módulo que Alembic importa para `target_metadata`) importe el nuevo módulo. Buscar dónde se importan los otros modelos:

Run: `cd mt-pricing-backend && grep -rn "match_candidate" app/db/models/__init__.py alembic/env.py`

Añadir `from app.db.models.match_agent import MatchAgentConfig, MatchAgentDecision  # noqa: F401` en el mismo fichero donde aparezcan los demás modelos.

- [ ] **Step 6: Commit**

```bash
git add mt-pricing-backend/app/db/models/match_agent.py mt-pricing-backend/tests/unit/db/test_match_agent_models.py mt-pricing-backend/app/db/models/__init__.py
git commit -m "feat(matches): add MatchAgentConfig and MatchAgentDecision ORM models"
```

---

## Task 4: Migración Alembic — tablas del agente

**Files:**
- Create: `mt-pricing-backend/alembic/versions/<rev>_match_agent.py`

> **IMPORTANTE — múltiples heads:** el repo tiene ~10 heads de Alembic divergentes.
> Esta tarea debe delegarse al **agente `db-migrator`** (conoce la convención de
> heads/merges del proyecto). Instrucción para `db-migrator`: "Crea una migración
> que cree las tablas `match_agent_config` y `match_agent_decisions`. Antes,
> ejecuta `alembic heads`; si hay múltiples, crea primero un `alembic merge` de
> todos los heads y encadena la nueva migración a ese merge. Las tablas son
> `public.*` (Alembic, no Supabase). El DDL exacto está abajo."

- [ ] **Step 1: Resolver heads y crear el scaffold de la migración**

Run: `cd mt-pricing-backend && alembic heads`
Si devuelve más de un head: `alembic merge -m "merge heads pre match-agent" heads`
Luego crear el fichero de migración con `down_revision` = el head único resultante.

- [ ] **Step 2: Escribir el `upgrade()` / `downgrade()`**

```python
"""match_agent — tablas match_agent_config + match_agent_decisions.

Crea:
- match_agent_config: fila singleton (id=1) con modo/alpha/gate del agente.
- match_agent_decisions: serie temporal de veredictos del agente.
Seed: una fila en match_agent_config (id=1, mode='shadow', alpha=0.02, gate=200).

Revision ID: <rev>
Revises: <head>
Create Date: 2026-05-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision: str = "<rev>"
down_revision: str | None = "<head>"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "match_agent_config",
        sa.Column("id", sa.SmallInteger, primary_key=True),
        sa.Column("mode", sa.String(16), nullable=False, server_default=sa.text("'shadow'")),
        sa.Column("alpha", sa.Numeric(4, 3), nullable=False, server_default=sa.text("0.02")),
        sa.Column("min_labels_gate", sa.Integer, nullable=False, server_default=sa.text("200")),
        sa.Column("updated_by", PgUUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("id = 1", name="ck_match_agent_config_singleton"),
        sa.CheckConstraint("mode IN ('shadow','active')", name="ck_match_agent_config_mode"),
        sa.CheckConstraint("alpha > 0 AND alpha < 1", name="ck_match_agent_config_alpha"),
        sa.CheckConstraint("min_labels_gate >= 1", name="ck_match_agent_config_gate"),
    )
    op.execute(
        "INSERT INTO match_agent_config (id, mode, alpha, min_labels_gate) "
        "VALUES (1, 'shadow', 0.02, 200) ON CONFLICT (id) DO NOTHING;"
    )

    op.create_table(
        "match_agent_decisions",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("candidate_id", PgUUID(as_uuid=True), sa.ForeignKey("match_candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_sku", sa.Text, nullable=False),
        sa.Column("verdict", sa.String(16), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("applied", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("signal", sa.String(24), nullable=False),
        sa.Column("score", sa.Integer, nullable=False),
        sa.Column("calibrated_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("review_priority", sa.String(16), nullable=True),
        sa.Column("calibrator_version", sa.Text, nullable=True),
        sa.Column("human_outcome", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("verdict IN ('auto_validate','auto_discard','human')", name="ck_match_agent_decisions_verdict"),
        sa.CheckConstraint("mode IN ('shadow','active')", name="ck_match_agent_decisions_mode"),
        sa.CheckConstraint("signal IN ('conformal','bootstrap')", name="ck_match_agent_decisions_signal"),
        sa.CheckConstraint(
            "human_outcome IS NULL OR human_outcome IN ('validated','discarded')",
            name="ck_match_agent_decisions_outcome",
        ),
    )
    op.create_index("idx_match_agent_decisions_sku", "match_agent_decisions", ["product_sku"])
    op.create_index("idx_match_agent_decisions_created", "match_agent_decisions", ["created_at"])
    op.create_index("idx_match_agent_decisions_verdict_mode", "match_agent_decisions", ["verdict", "mode"])
    op.create_index("idx_match_agent_decisions_candidate", "match_agent_decisions", ["candidate_id"])


def downgrade() -> None:
    op.drop_index("idx_match_agent_decisions_candidate", table_name="match_agent_decisions")
    op.drop_index("idx_match_agent_decisions_verdict_mode", table_name="match_agent_decisions")
    op.drop_index("idx_match_agent_decisions_created", table_name="match_agent_decisions")
    op.drop_index("idx_match_agent_decisions_sku", table_name="match_agent_decisions")
    op.drop_table("match_agent_decisions")
    op.drop_table("match_agent_config")
```

- [ ] **Step 3: Aplicar y verificar la migración**

Run: `cd mt-pricing-backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head`
Expected: upgrade + downgrade + upgrade sin error (reversibilidad verificada).

- [ ] **Step 4: Revisar con el agente migration-reviewer**

Delegar al agente `migration-reviewer` el fichero de migración creado. Corregir lo que reporte (split `public.*`, índices, reversibilidad).

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/alembic/versions/
git commit -m "feat(matches): add match_agent_config + match_agent_decisions migration"
```

---

## Task 5: Repositorios del agente

**Files:**
- Create: `mt-pricing-backend/app/repositories/match_agent.py`
- Test: `mt-pricing-backend/tests/unit/repositories/test_match_agent_repo.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/repositories/test_match_agent_repo.py
"""Tests de los repos del agente (usa la sesión async de fixtures)."""
from __future__ import annotations

import pytest

from app.repositories.match_agent import (
    MatchAgentConfigRepository,
    MatchAgentDecisionRepository,
)

pytestmark = pytest.mark.asyncio


async def test_get_config_returns_singleton(db_session):
    repo = MatchAgentConfigRepository(db_session)
    cfg = await repo.get()
    assert cfg is not None
    assert cfg.id == 1
    assert cfg.mode == "shadow"


async def test_update_config_changes_mode(db_session):
    repo = MatchAgentConfigRepository(db_session)
    updated = await repo.update(mode="active", updated_by=None)
    assert updated.mode == "active"


async def test_count_decisions_empty(db_session):
    repo = MatchAgentDecisionRepository(db_session)
    assert await repo.count_shadow() == 0
```

> **Nota:** este test asume el fixture `db_session` que ya usan los demás tests
> de repos del proyecto, con la migración del Task 4 aplicada (el seed crea la
> fila singleton). Verificar el nombre real del fixture en `tests/conftest.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mt-pricing-backend && pytest tests/unit/repositories/test_match_agent_repo.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the repositories**

```python
# app/repositories/match_agent.py
"""Repositorios de match_agent_config (singleton) y match_agent_decisions."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.match_agent import MatchAgentConfig, MatchAgentDecision


class MatchAgentConfigRepository:
    """Acceso a la fila singleton match_agent_config (id=1)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self) -> MatchAgentConfig | None:
        return await self.session.get(MatchAgentConfig, 1)

    async def update(
        self,
        *,
        mode: str | None = None,
        alpha: Decimal | None = None,
        min_labels_gate: int | None = None,
        updated_by: UUID | None = None,
    ) -> MatchAgentConfig:
        values: dict[str, Any] = {"updated_at": datetime.now(tz=timezone.utc), "updated_by": updated_by}
        if mode is not None:
            values["mode"] = mode
        if alpha is not None:
            values["alpha"] = alpha
        if min_labels_gate is not None:
            values["min_labels_gate"] = min_labels_gate
        await self.session.execute(
            update(MatchAgentConfig).where(MatchAgentConfig.id == 1).values(**values)
        )
        await self.session.flush()
        row = await self.session.get(MatchAgentConfig, 1)
        assert row is not None  # noqa: S101 — el seed garantiza id=1
        return row


class MatchAgentDecisionRepository:
    """CRUD de match_agent_decisions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        *,
        candidate_id: UUID,
        product_sku: str,
        verdict: str,
        mode: str,
        applied: bool,
        signal: str,
        score: int,
        calibrated_confidence: Decimal | None = None,
        review_priority: str | None = None,
        calibrator_version: str | None = None,
    ) -> MatchAgentDecision:
        row = MatchAgentDecision(
            candidate_id=candidate_id,
            product_sku=product_sku,
            verdict=verdict,
            mode=mode,
            applied=applied,
            signal=signal,
            score=score,
            calibrated_confidence=calibrated_confidence,
            review_priority=review_priority,
            calibrator_version=calibrator_version,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def latest_for_candidate(
        self, candidate_id: UUID
    ) -> MatchAgentDecision | None:
        stmt = (
            select(MatchAgentDecision)
            .where(MatchAgentDecision.candidate_id == candidate_id)
            .order_by(MatchAgentDecision.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def set_human_outcome(
        self, candidate_id: UUID, outcome: str
    ) -> None:
        """Rellena human_outcome en la última decisión del candidato."""
        latest = await self.latest_for_candidate(candidate_id)
        if latest is not None:
            latest.human_outcome = outcome
            await self.session.flush()

    async def count_shadow(self) -> int:
        stmt = select(func.count()).select_from(MatchAgentDecision).where(
            MatchAgentDecision.mode == "shadow"
        )
        return int((await self.session.execute(stmt)).scalar_one() or 0)

    async def shadow_precision(self) -> tuple[int, float | None]:
        """Precisión de sombra: aciertos / decisiones con human_outcome conocido.

        Acierto = (verdict=auto_validate Y human_outcome=validated) o
                  (verdict=auto_discard Y human_outcome=discarded).
        """
        stmt = select(
            MatchAgentDecision.verdict, MatchAgentDecision.human_outcome
        ).where(MatchAgentDecision.human_outcome.is_not(None))
        rows = (await self.session.execute(stmt)).all()
        scored = [
            (v, o)
            for v, o in rows
            if v in ("auto_validate", "auto_discard")
        ]
        if not scored:
            return 0, None
        hits = sum(
            1
            for v, o in scored
            if (v == "auto_validate" and o == "validated")
            or (v == "auto_discard" and o == "discarded")
        )
        return len(scored), hits / len(scored)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mt-pricing-backend && pytest tests/unit/repositories/test_match_agent_repo.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/repositories/match_agent.py mt-pricing-backend/tests/unit/repositories/test_match_agent_repo.py
git commit -m "feat(matches): add match agent config + decision repositories"
```

---

## Task 6: `MatchValidationAgent` — función de decisión

**Files:**
- Create: `mt-pricing-backend/app/services/matching/validation_agent.py`
- Test: `mt-pricing-backend/tests/unit/services/matching/test_validation_agent.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/services/matching/test_validation_agent.py
"""Tests de la función de decisión del MatchValidationAgent."""
from __future__ import annotations

from app.services.matching.validation_agent import AgentDecision, decide_verdict


def test_bootstrap_auto_validate_from_enhanced():
    d = decide_verdict(
        score=80,
        enhanced={"auto_validate": True, "method": "deterministic"},
        review_priority=None,
        has_calibrator=False,
    )
    assert d == AgentDecision(verdict="auto_validate", signal="bootstrap")


def test_bootstrap_vision_rejected_is_auto_discard():
    d = decide_verdict(
        score=0,
        enhanced={"auto_validate": False, "method": "vision_rejected"},
        review_priority=None,
        has_calibrator=False,
    )
    assert d.verdict == "auto_discard"


def test_bootstrap_human_queue_when_uncertain():
    d = decide_verdict(
        score=55,
        enhanced={"auto_validate": False, "method": "human_queue"},
        review_priority=None,
        has_calibrator=False,
    )
    assert d.verdict == "human"


def test_conformal_low_priority_auto_validates():
    d = decide_verdict(
        score=70,
        enhanced={"auto_validate": False, "method": "human_queue"},
        review_priority="low",
        has_calibrator=True,
    )
    assert d == AgentDecision(verdict="auto_validate", signal="conformal")


def test_conformal_high_priority_auto_discards():
    d = decide_verdict(
        score=40,
        enhanced={"auto_validate": False, "method": "human_queue"},
        review_priority="high",
        has_calibrator=True,
    )
    assert d.verdict == "auto_discard"


def test_conformal_gray_band_goes_to_human():
    d = decide_verdict(
        score=50,
        enhanced={"auto_validate": False, "method": "human_queue"},
        review_priority=None,
        has_calibrator=True,
    )
    assert d.verdict == "human"


def test_conformal_vision_rejected_still_discards():
    d = decide_verdict(
        score=0,
        enhanced={"auto_validate": False, "method": "vision_rejected"},
        review_priority="low",
        has_calibrator=True,
    )
    assert d.verdict == "auto_discard"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mt-pricing-backend && pytest tests/unit/services/matching/test_validation_agent.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the decision function**

```python
# app/services/matching/validation_agent.py
"""MatchValidationAgent — agente semi-autónomo de validación de matches.

Decide, por cada candidato, un veredicto: auto_validate / auto_discard / human.

Señal de decisión:
- Fase bootstrap (sin calibrador entrenado): usa _enhanced.auto_validate + method.
- Fase calibrada (calibrador activo): usa review_priority del ConformalWrapper.

Filtro negativo duro: method == 'vision_rejected' SIEMPRE descarta, en cualquier fase.

Modo (de match_agent_config):
- shadow: registra el veredicto en match_agent_decisions, NO toca match_candidates.
- active: además aplica status validated/discarded e inyecta specs_jsonb._agent.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.match_candidate import MatchCandidate
from app.repositories.match_agent import (
    MatchAgentConfigRepository,
    MatchAgentDecisionRepository,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentDecision:
    """Veredicto del agente para un candidato."""

    verdict: str  # "auto_validate" | "auto_discard" | "human"
    signal: str  # "conformal" | "bootstrap"


def decide_verdict(
    *,
    score: int,
    enhanced: dict[str, Any],
    review_priority: str | None,
    has_calibrator: bool,
) -> AgentDecision:
    """Función pura de decisión — sin efectos secundarios.

    Args:
        score: score 0-100 del candidato.
        enhanced: bloque specs_jsonb._enhanced (auto_validate, method).
        review_priority: 'low' / 'high' / None — del ConformalWrapper.
        has_calibrator: True si hay un calibrador activo entrenado.
    """
    method = str(enhanced.get("method") or "")

    # Filtro negativo duro — aplica en cualquier fase.
    if method == "vision_rejected":
        signal = "conformal" if has_calibrator else "bootstrap"
        return AgentDecision(verdict="auto_discard", signal=signal)

    if has_calibrator:
        if review_priority == "low":
            return AgentDecision(verdict="auto_validate", signal="conformal")
        if review_priority == "high":
            return AgentDecision(verdict="auto_discard", signal="conformal")
        return AgentDecision(verdict="human", signal="conformal")

    # Bootstrap — signal sin calibrar.
    if enhanced.get("auto_validate") is True:
        return AgentDecision(verdict="auto_validate", signal="bootstrap")
    return AgentDecision(verdict="human", signal="bootstrap")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mt-pricing-backend && pytest tests/unit/services/matching/test_validation_agent.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/services/matching/validation_agent.py mt-pricing-backend/tests/unit/services/matching/test_validation_agent.py
git commit -m "feat(matches): add MatchValidationAgent decision function"
```

---

## Task 7: `MatchValidationAgent` — ejecución (shadow vs active) e idempotencia

**Files:**
- Modify: `mt-pricing-backend/app/services/matching/validation_agent.py`
- Test: `mt-pricing-backend/tests/unit/services/matching/test_validation_agent.py`

- [ ] **Step 1: Write the failing test**

Añadir a `test_validation_agent.py` — incluir estos imports al inicio del fichero:

```python
import pytest
from sqlalchemy import select

from app.db.models.match_agent import MatchAgentDecision


@pytest.mark.asyncio
async def test_agent_shadow_does_not_touch_status(db_session, make_candidate):
    """En modo shadow, el agente registra la decisión pero no cambia status."""
    from app.services.matching.validation_agent import MatchValidationAgent

    cand = await make_candidate(
        score=85, specs_jsonb={"_enhanced": {"auto_validate": True, "method": "deterministic"}}
    )
    agent = MatchValidationAgent(db_session)
    await agent.run(cand.product_sku)
    await db_session.refresh(cand)
    assert cand.status == "pending"  # shadow no aplica


@pytest.mark.asyncio
async def test_agent_active_validates_high_confidence(db_session, make_candidate, set_agent_mode):
    """En modo active, auto_validate cambia el status a validated."""
    from app.services.matching.validation_agent import MatchValidationAgent

    await set_agent_mode("active")
    cand = await make_candidate(
        score=85, specs_jsonb={"_enhanced": {"auto_validate": True, "method": "deterministic"}}
    )
    agent = MatchValidationAgent(db_session)
    await agent.run(cand.product_sku)
    await db_session.refresh(cand)
    assert cand.status == "validated"
    assert cand.specs_jsonb["_agent"]["applied"] is True


@pytest.mark.asyncio
async def test_agent_idempotent(db_session, make_candidate, set_agent_mode):
    """Re-ejecutar el agente no duplica decisiones ni re-aplica."""
    from app.services.matching.validation_agent import MatchValidationAgent

    await set_agent_mode("active")
    cand = await make_candidate(
        score=85, specs_jsonb={"_enhanced": {"auto_validate": True, "method": "deterministic"}}
    )
    agent = MatchValidationAgent(db_session)
    await agent.run(cand.product_sku)
    await agent.run(cand.product_sku)
    # La 2ª corrida ve status != pending y no decide de nuevo.
    decisions = await db_session.execute(
        select(MatchAgentDecision).where(MatchAgentDecision.candidate_id == cand.id)
    )
    assert len(decisions.scalars().all()) == 1
```

> **Nota fixtures:** `make_candidate` y `set_agent_mode` son fixtures nuevos.
> Añadirlos a `tests/conftest.py` o a un `conftest.py` local:
> ```python
> @pytest.fixture
> def make_candidate(db_session):
>     async def _make(**kw):
>         from app.db.models.match_candidate import MatchCandidate
>         defaults = dict(
>             product_sku="TEST-SKU", channel="amazon_uae", external_id="X1",
>             title="t", score=50, status="pending", specs_jsonb={}, kind="unknown",
>         )
>         defaults.update(kw)
>         row = MatchCandidate(**defaults)
>         db_session.add(row); await db_session.flush()
>         return row
>     return _make
>
> @pytest.fixture
> def set_agent_mode(db_session):
>     async def _set(mode):
>         from app.repositories.match_agent import MatchAgentConfigRepository
>         await MatchAgentConfigRepository(db_session).update(mode=mode)
>     return _set
> ```
> El SKU `TEST-SKU` debe existir en `products` o el FK falla — usar un SKU sembrado por los fixtures existentes del proyecto.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mt-pricing-backend && pytest tests/unit/services/matching/test_validation_agent.py -k agent -v`
Expected: FAIL — `MatchValidationAgent` no existe

- [ ] **Step 3: Implementar la clase `MatchValidationAgent`**

Añadir a `validation_agent.py`:

```python
class MatchValidationAgent:
    """Orquesta la decisión + aplicación del agente sobre los candidatos de un SKU."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._config_repo = MatchAgentConfigRepository(session)
        self._decision_repo = MatchAgentDecisionRepository(session)

    async def run(self, sku: str) -> int:
        """Procesa todos los candidatos `pending` de un SKU. Devuelve nº decididos.

        Nunca lanza excepción hacia el caller — si algo falla, loguea y sigue.
        """
        try:
            config = await self._config_repo.get()
            if config is None:
                logger.warning("validation_agent.no_config — skipping")
                return 0
            mode = config.mode

            has_calibrator = await self._has_active_calibrator()

            stmt = select(MatchCandidate).where(
                MatchCandidate.product_sku == sku,
                MatchCandidate.status == "pending",
            )
            candidates = list((await self._session.execute(stmt)).scalars().all())

            decided = 0
            for cand in candidates:
                # Idempotencia: si ya hay una decisión aplicada, saltar.
                existing = await self._decision_repo.latest_for_candidate(cand.id)
                if existing is not None and existing.applied:
                    continue

                specs = dict(cand.specs_jsonb or {})
                enhanced = dict(specs.get("_enhanced") or {})
                review_priority = cand.review_priority

                decision = decide_verdict(
                    score=cand.score,
                    enhanced=enhanced,
                    review_priority=review_priority,
                    has_calibrator=has_calibrator,
                )

                applied = mode == "active" and decision.verdict != "human"
                if applied:
                    self._apply(cand, decision, mode)

                await self._decision_repo.record(
                    candidate_id=cand.id,
                    product_sku=cand.product_sku,
                    verdict=decision.verdict,
                    mode=mode,
                    applied=applied,
                    signal=decision.signal,
                    score=cand.score,
                    calibrated_confidence=cand.calibrated_confidence,
                    review_priority=review_priority,
                    calibrator_version=(
                        await self._active_calibrator_version()
                        if has_calibrator
                        else None
                    ),
                )
                decided += 1

            await self._session.flush()
            logger.info(
                "validation_agent.run.done",
                extra={"sku": sku, "mode": mode, "decided": decided},
            )
            return decided
        except Exception:  # noqa: BLE001 — el agente nunca rompe el worker
            logger.exception("validation_agent.run.error", extra={"sku": sku})
            return 0

    def _apply(self, cand: MatchCandidate, decision: AgentDecision, mode: str) -> None:
        """Aplica el veredicto al candidato (solo modo active)."""
        if decision.verdict == "auto_validate":
            cand.status = "validated"
        elif decision.verdict == "auto_discard":
            cand.status = "discarded"
        else:
            return
        specs = dict(cand.specs_jsonb or {})
        specs["_agent"] = {
            "verdict": decision.verdict,
            "mode": mode,
            "signal": decision.signal,
            "decided_at": datetime.now(tz=timezone.utc).isoformat(),
            "applied": True,
        }
        cand.specs_jsonb = specs

    async def _has_active_calibrator(self) -> bool:
        from app.db.models.golden_label import CalibratorVersion

        stmt = select(CalibratorVersion.id).where(
            CalibratorVersion.is_active.is_(True)
        ).limit(1)
        return (await self._session.execute(stmt)).scalar_one_or_none() is not None

    async def _active_calibrator_version(self) -> str | None:
        from app.db.models.golden_label import CalibratorVersion

        stmt = select(CalibratorVersion.version).where(
            CalibratorVersion.is_active.is_(True)
        ).limit(1)
        return (await self._session.execute(stmt)).scalar_one_or_none()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mt-pricing-backend && pytest tests/unit/services/matching/test_validation_agent.py -v`
Expected: PASS (todos)

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/services/matching/validation_agent.py mt-pricing-backend/tests/
git commit -m "feat(matches): add MatchValidationAgent run/apply with shadow + idempotency"
```

---

## Task 8: Wiring conformal en el scoring

**Files:**
- Modify: `mt-pricing-backend/app/services/matching/match_service.py` (dentro de `refresh_candidates_enhanced`, tras el bloque `_enhanced` en ~línea 1009)
- Test: `mt-pricing-backend/tests/unit/services/matching/test_conformal_wiring.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/services/matching/test_conformal_wiring.py
"""Verifica que populate_conformal escribe las columnas conformal."""
from __future__ import annotations

from app.services.matching.match_service import populate_conformal_fields


class _FakeCand:
    def __init__(self, score):
        self.score = score
        self.calibrated_confidence = None
        self.conf_lower = None
        self.conf_upper = None
        self.review_priority = None


def test_populate_conformal_noop_without_calibrator():
    cand = _FakeCand(score=70)
    populate_conformal_fields(cand, calibrator=None)
    assert cand.review_priority is None
    assert cand.conf_lower is None


def test_populate_conformal_sets_fields_with_calibrator():
    from app.services.matching.calibrator import ConformalWrapper, IsotonicCalibrator

    cal = IsotonicCalibrator().fit([0.1, 0.5, 0.9] * 100, [0, 0, 1] * 100)
    wrapper = ConformalWrapper(calibrator=cal, method="venn_abers")
    wrapper.fit([0.1, 0.5, 0.9] * 100, [0, 0, 1] * 100)
    cand = _FakeCand(score=90)
    populate_conformal_fields(cand, calibrator=wrapper)
    assert cand.calibrated_confidence is not None
    assert cand.conf_lower is not None
    assert cand.conf_upper is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mt-pricing-backend && pytest tests/unit/services/matching/test_conformal_wiring.py -v`
Expected: FAIL — `populate_conformal_fields` no existe

- [ ] **Step 3: Añadir `populate_conformal_fields` a `match_service.py`**

A nivel de módulo en `match_service.py` (tras los imports):

```python
def populate_conformal_fields(candidate: Any, calibrator: Any | None) -> None:
    """Puebla calibrated_confidence/conf_lower/conf_upper/review_priority.

    Si `calibrator` es None (no hay calibrador activo), no hace nada — las
    columnas quedan como estén (NULL en bootstrap).

    Args:
        candidate: MatchCandidate (o stub con .score y las 4 columnas).
        calibrator: ConformalWrapper ya fiteado, o None.
    """
    if calibrator is None:
        return
    from decimal import Decimal as _D

    raw = candidate.score / 100.0
    pred = calibrator.predict_with_interval(raw)
    candidate.calibrated_confidence = _D(str(round(pred.point_estimate, 4)))
    candidate.conf_lower = _D(str(round(pred.lower_bound, 4)))
    candidate.conf_upper = _D(str(round(pred.upper_bound, 4)))
    candidate.review_priority = pred.review_priority
```

- [ ] **Step 4: Invocar el wiring dentro de `refresh_candidates_enhanced`**

En `refresh_candidates_enhanced`, antes del bucle `for candidate in candidates:`, cargar el calibrador una vez:

```python
        # Cargar el calibrador conformal activo (None en fase bootstrap).
        conformal: Any | None = None
        try:
            from app.repositories.golden_labels import (  # noqa: PLC0415
                CalibratorVersionRepository,
                GoldenLabelRepository,
            )
            from app.services.matching.calibrator import ConformalWrapper  # noqa: PLC0415
            from app.services.matching.calibrator_storage import CalibratorStorage  # noqa: PLC0415

            storage = CalibratorStorage(CalibratorVersionRepository(self.session))
            base_cal = await storage.load_active()
            if base_cal is not None:
                labels = await GoldenLabelRepository(self.session).list_for_training()
                if len(labels) >= 200:
                    wrapper = ConformalWrapper(calibrator=base_cal, method="venn_abers")
                    wrapper.fit(
                        [float(row.score) for row in labels],
                        [int(row.label) for row in labels],
                    )
                    conformal = wrapper
        except Exception:  # noqa: BLE001
            logger.warning("refresh_candidates_enhanced.conformal_load_failed", exc_info=True)
            conformal = None
```

Y dentro del bucle, justo después de actualizar `candidate.score` (~línea 1039):

```python
            # Wiring conformal — puebla calibrated_confidence + intervalo.
            populate_conformal_fields(candidate, conformal)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd mt-pricing-backend && pytest tests/unit/services/matching/test_conformal_wiring.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add mt-pricing-backend/app/services/matching/match_service.py mt-pricing-backend/tests/unit/services/matching/test_conformal_wiring.py
git commit -m "feat(matches): wire ConformalWrapper into enhanced scoring"
```

---

## Task 9: Invocar el agente en `refresh_sku_task`

**Files:**
- Modify: `mt-pricing-backend/app/workers/tasks/comparator.py`

- [ ] **Step 1: Invocar el agente tras `refresh_candidates_enhanced`**

En `comparator.py`, dentro de `_run()`, en el bloque `try:` tras
`pairs = await service.refresh_candidates_enhanced(...)` y antes de
`await session.commit()`:

```python
                try:
                    pairs = await service.refresh_candidates_enhanced(sku, mt_image_url=None)
                    count = len(pairs)

                    # Agente de validación — corre inline tras el scoring.
                    if settings.MATCH_AGENT_ENABLED:
                        from app.services.matching.validation_agent import (  # noqa: PLC0415
                            MatchValidationAgent,
                        )
                        agent_decided = await MatchValidationAgent(session).run(sku)
                        logger.info(
                            "comparator.refresh_sku.agent",
                            extra={"sku": sku, "agent_decided": agent_decided},
                        )

                    await session.commit()
```

- [ ] **Step 2: Verificar que no rompe el import**

Run: `cd mt-pricing-backend && python -c "import app.workers.tasks.comparator"`
Expected: sin error.

- [ ] **Step 3: Commit**

```bash
git add mt-pricing-backend/app/workers/tasks/comparator.py
git commit -m "feat(matches): invoke MatchValidationAgent inline in refresh_sku_task"
```

---

## Task 10: golden_labels + label + human_outcome en validate/discard

**Files:**
- Modify: `mt-pricing-backend/app/services/matching/match_service.py` (`validate_candidate`, `discard_candidate`)
- Test: `mt-pricing-backend/tests/unit/services/matching/test_match_service_golden.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/services/matching/test_match_service_golden.py
"""Validar/descartar deben escribir golden_labels + label + human_outcome."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_validate_writes_golden_label(db_session, make_candidate, match_service):
    from app.repositories.golden_labels import GoldenLabelRepository

    cand = await make_candidate(score=80)
    await match_service.validate_candidate(cand.id, user_id=None)
    labels = await GoldenLabelRepository(db_session).list_for_training()
    matching = [l for l in labels if l.candidate_id == cand.id]
    assert len(matching) == 1
    assert matching[0].label == 1
    await db_session.refresh(cand)
    assert cand.label == "accept"


async def test_discard_writes_reject_golden_label(db_session, make_candidate, match_service):
    from app.repositories.golden_labels import GoldenLabelRepository

    cand = await make_candidate(score=20)
    await match_service.discard_candidate(cand.id, reason="tipo incorrecto")
    labels = await GoldenLabelRepository(db_session).list_for_training()
    matching = [l for l in labels if l.candidate_id == cand.id]
    assert len(matching) == 1
    assert matching[0].label == 0
    await db_session.refresh(cand)
    assert cand.label == "reject"
```

> **Fixture `match_service`:** construir `MatchService(db_session, fetchers=[])`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mt-pricing-backend && pytest tests/unit/services/matching/test_match_service_golden.py -v`
Expected: FAIL — golden_labels vacío / `cand.label` None

- [ ] **Step 3: Modificar `validate_candidate` y `discard_candidate`**

Reemplazar el cuerpo de ambos métodos en `match_service.py`:

```python
    async def validate_candidate(
        self, candidate_id: UUID, *, user_id: UUID | None
    ) -> MatchCandidate:
        obj = await self.get_candidate(candidate_id)
        if obj.status == "discarded":
            raise MatchInvalidTransitionError(obj.status, "validated")
        updated = await self._matches_repo.mark_validated(candidate_id, user_id=user_id)
        assert updated is not None
        updated.label = "accept"
        await self._record_human_feedback(updated, label=1, user_id=user_id)
        return updated

    async def discard_candidate(
        self, candidate_id: UUID, *, reason: str | None = None
    ) -> MatchCandidate:
        obj = await self.get_candidate(candidate_id)
        if obj.status == "validated":
            raise MatchInvalidTransitionError(obj.status, "discarded")
        updated = await self._matches_repo.mark_discarded(candidate_id, reason=reason)
        assert updated is not None
        updated.label = "reject"
        await self._record_human_feedback(updated, label=0, user_id=None)
        return updated

    async def _record_human_feedback(
        self, candidate: MatchCandidate, *, label: int, user_id: UUID | None
    ) -> None:
        """Cierra el lazo de feedback: golden_labels + human_outcome del agente."""
        from app.repositories.golden_labels import GoldenLabelRepository  # noqa: PLC0415
        from app.repositories.match_agent import MatchAgentDecisionRepository  # noqa: PLC0415

        await GoldenLabelRepository(self.session).upsert(
            sku=candidate.product_sku,
            candidate_id=candidate.id,
            label=label,
            score=candidate.score / 100.0,
            judged_by=user_id,
        )
        outcome = "validated" if label == 1 else "discarded"
        await MatchAgentDecisionRepository(self.session).set_human_outcome(
            candidate.id, outcome
        )
        await self.session.flush()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mt-pricing-backend && pytest tests/unit/services/matching/test_match_service_golden.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/services/matching/match_service.py mt-pricing-backend/tests/unit/services/matching/test_match_service_golden.py
git commit -m "feat(matches): write golden_labels + label on validate/discard"
```

---

## Task 11: Flag de settings + endpoints `agent/config`

**Files:**
- Modify: `mt-pricing-backend/app/core/config.py` (sección Feature flags, ~línea 115)
- Modify: `mt-pricing-backend/app/api/routes/matches.py`
- Test: `mt-pricing-backend/tests/integration/test_match_agent_routes.py`

- [ ] **Step 1: Añadir el flag de settings**

En `config.py`, tras `HUMAN_QUEUE_ENABLED` (línea 115):

```python
    MATCH_AGENT_ENABLED: bool = True  # agente de validación inline en refresh_sku
```

- [ ] **Step 2: Write the failing test**

```python
# tests/integration/test_match_agent_routes.py
"""Tests de integración de los endpoints del agente."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_get_agent_config(authed_client):
    resp = await authed_client.get("/api/v1/matches/agent/config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] in ("shadow", "active")
    assert "alpha" in body


async def test_put_agent_config_changes_alpha(authed_client):
    resp = await authed_client.put(
        "/api/v1/matches/agent/config", json={"alpha": 0.05}
    )
    assert resp.status_code == 200
    assert float(resp.json()["alpha"]) == 0.05


async def test_put_agent_config_active_blocked_without_labels(authed_client):
    """No se puede pasar a active sin alcanzar el gate de labels."""
    resp = await authed_client.put(
        "/api/v1/matches/agent/config", json={"mode": "active"}
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "labels_gate_not_reached"
```

> **Fixture `authed_client`:** usar el client autenticado con permiso
> `matches:write` que ya emplean los tests de integración del proyecto.

- [ ] **Step 3: Run test to verify it fails**

Run: `cd mt-pricing-backend && pytest tests/integration/test_match_agent_routes.py -k config -v`
Expected: FAIL — endpoints 404

- [ ] **Step 4: Añadir los endpoints a `matches.py`**

Imports nuevos al inicio de `matches.py`:

```python
from app.repositories.golden_labels import GoldenLabelRepository
from app.repositories.match_agent import (
    MatchAgentConfigRepository,
    MatchAgentDecisionRepository,
)
from app.schemas.match_agent import (
    MatchAgentConfigResponse,
    MatchAgentConfigUpdate,
    MatchAgentMetrics,
)
```

Endpoints (añadir tras `clear_all_matches`, antes del `dataset_router`):

```python
@router.get(
    "/agent/config",
    response_model=MatchAgentConfigResponse,
    summary="Configuración del agente de validación",
    operation_id="matchesAgentConfig",
)
async def get_agent_config(
    _user: User = Depends(require_permissions("matches:read")),
    session: AsyncSession = Depends(get_db_session),
) -> MatchAgentConfigResponse:
    cfg = await MatchAgentConfigRepository(session).get()
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "agent_config_missing", "title": "Falta la fila singleton de config."},
        )
    return MatchAgentConfigResponse.model_validate(cfg)


@router.put(
    "/agent/config",
    response_model=MatchAgentConfigResponse,
    summary="Actualizar la configuración del agente",
    operation_id="matchesAgentConfigUpdate",
    responses={409: {"model": ProblemDetails, "description": "Gate de labels no alcanzado"}},
)
async def update_agent_config(
    payload: MatchAgentConfigUpdate,
    user: User = Depends(require_permissions("matches:write")),
    session: AsyncSession = Depends(get_db_session),
) -> MatchAgentConfigResponse:
    repo = MatchAgentConfigRepository(session)
    cfg = await repo.get()
    if cfg is None:
        raise HTTPException(status_code=500, detail={"code": "agent_config_missing", "title": "Config ausente"})

    # Pasar a 'active' exige alcanzar el gate de golden_labels.
    if payload.mode == "active":
        from sqlalchemy import func as _func
        from app.db.models.golden_label import GoldenLabel
        total = int(
            (await session.execute(select(_func.count(GoldenLabel.id)))).scalar_one() or 0
        )
        gate = payload.min_labels_gate or cfg.min_labels_gate
        if total < gate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "labels_gate_not_reached",
                    "title": f"Faltan golden_labels: {total}/{gate}.",
                },
            )

    updated = await repo.update(
        mode=payload.mode,
        alpha=payload.alpha,
        min_labels_gate=payload.min_labels_gate,
        updated_by=user.id,
    )
    await session.commit()
    return MatchAgentConfigResponse.model_validate(updated)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd mt-pricing-backend && pytest tests/integration/test_match_agent_routes.py -k config -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add mt-pricing-backend/app/core/config.py mt-pricing-backend/app/api/routes/matches.py mt-pricing-backend/tests/integration/test_match_agent_routes.py
git commit -m "feat(matches): add MATCH_AGENT_ENABLED flag + agent/config endpoints"
```

---

## Task 12: Endpoint `agent/metrics`

**Files:**
- Modify: `mt-pricing-backend/app/api/routes/matches.py`
- Test: `mt-pricing-backend/tests/integration/test_match_agent_routes.py`

- [ ] **Step 1: Write the failing test**

Añadir a `test_match_agent_routes.py`:

```python
async def test_get_agent_metrics(authed_client):
    resp = await authed_client.get("/api/v1/matches/agent/metrics")
    assert resp.status_code == 200
    body = resp.json()
    assert "golden_labels_total" in body
    assert "gate_reached" in body
    assert body["mode"] in ("shadow", "active")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mt-pricing-backend && pytest tests/integration/test_match_agent_routes.py -k metrics -v`
Expected: FAIL — 404

- [ ] **Step 3: Añadir el endpoint a `matches.py`**

```python
@router.get(
    "/agent/metrics",
    response_model=MatchAgentMetrics,
    summary="Métricas del agente (labels, precisión sombra, salud del calibrador)",
    operation_id="matchesAgentMetrics",
)
async def get_agent_metrics(
    _user: User = Depends(require_permissions("matches:read")),
    session: AsyncSession = Depends(get_db_session),
) -> MatchAgentMetrics:
    from sqlalchemy import func as _func
    from app.db.models.golden_label import GoldenLabel
    from app.repositories.golden_labels import CalibratorVersionRepository

    cfg = await MatchAgentConfigRepository(session).get()
    assert cfg is not None  # noqa: S101 — seed garantiza id=1

    total = int((await session.execute(select(_func.count(GoldenLabel.id)))).scalar_one() or 0)
    decision_repo = MatchAgentDecisionRepository(session)
    shadow_count = await decision_repo.count_shadow()
    _, precision = await decision_repo.shadow_precision()

    active_cal = await CalibratorVersionRepository(session).get_active()

    return MatchAgentMetrics(
        golden_labels_total=total,
        min_labels_gate=cfg.min_labels_gate,
        gate_reached=total >= cfg.min_labels_gate,
        shadow_decisions=shadow_count,
        shadow_precision=precision,
        calibrator_version=active_cal.version if active_cal else None,
        calibrator_brier=float(active_cal.brier_score) if active_cal and active_cal.brier_score is not None else None,
        calibrator_ece=float(active_cal.ece) if active_cal and active_cal.ece is not None else None,
        calibrator_trained_on=active_cal.trained_on_count if active_cal else None,
        mode=cfg.mode,  # type: ignore[arg-type]
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mt-pricing-backend && pytest tests/integration/test_match_agent_routes.py -k metrics -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/api/routes/matches.py mt-pricing-backend/tests/integration/test_match_agent_routes.py
git commit -m "feat(matches): add agent/metrics endpoint"
```

---

## Task 13: Endpoint `revert`

**Files:**
- Modify: `mt-pricing-backend/app/api/routes/matches.py`
- Test: `mt-pricing-backend/tests/integration/test_match_agent_routes.py`

- [ ] **Step 1: Write the failing test**

```python
async def test_revert_agent_decision(authed_client, db_session, make_candidate):
    """Revertir devuelve a pending y limpia _agent."""
    cand = await make_candidate(
        score=85, status="validated",
        specs_jsonb={"_agent": {"verdict": "auto_validate", "applied": True}},
    )
    resp = await authed_client.post(f"/api/v1/matches/{cand.id}/revert")
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


async def test_revert_rejects_human_validated(authed_client, make_candidate):
    """No se puede revertir un candidato sin _agent.applied."""
    cand = await make_candidate(score=85, status="validated", specs_jsonb={})
    resp = await authed_client.post(f"/api/v1/matches/{cand.id}/revert")
    assert resp.status_code == 409
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mt-pricing-backend && pytest tests/integration/test_match_agent_routes.py -k revert -v`
Expected: FAIL — 404

- [ ] **Step 3: Añadir el endpoint**

```python
@router.post(
    "/{candidate_id}/revert",
    response_model=MatchCandidateResponse,
    summary="Revertir una decisión del agente (vuelve a pending)",
    operation_id="matchesRevert",
    responses={409: {"model": ProblemDetails, "description": "No es una decisión del agente"}},
)
async def revert_agent_decision(
    candidate_id: UUID,
    _user: User = Depends(require_permissions("matches:write")),
    session: AsyncSession = Depends(get_db_session),
    service: MatchService = Depends(get_match_service),
) -> MatchCandidateResponse:
    try:
        row = await service.get_candidate(candidate_id)
    except MatchDomainError as e:
        _raise_domain(e)
    agent_block = (row.specs_jsonb or {}).get("_agent")
    if not isinstance(agent_block, dict) or not agent_block.get("applied"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "not_agent_decision", "title": "El candidato no fue resuelto por el agente."},
        )
    specs = dict(row.specs_jsonb or {})
    specs.pop("_agent", None)
    row.specs_jsonb = specs
    row.status = "pending"
    row.label = None
    row.validated_by = None
    row.validated_at = None
    row.discarded_reason = None
    await session.commit()
    await session.refresh(row)
    return _to_response(row)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mt-pricing-backend && pytest tests/integration/test_match_agent_routes.py -v`
Expected: PASS (todos)

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/api/routes/matches.py mt-pricing-backend/tests/integration/test_match_agent_routes.py
git commit -m "feat(matches): add revert endpoint for agent decisions"
```

---

# TRACK 2 — Frontend

## Task 14: Dedupe del hook de cola + borrar código muerto (gaps 3, 4)

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/validacion/page.tsx`

- [ ] **Step 1: Unificar las dos queries de cola en una**

Reemplazar `usePendingSkuQueue` y la query `sku-queue-stats` por un único hook. Borrar ambas definiciones y añadir:

```typescript
function useSkuQueue() {
  return useQuery<{ skus: string[]; stats: Map<string, { count: number; best: number }> }, Error>({
    queryKey: ["matches", "sku-queue"],
    queryFn: async () => {
      const res = await matchesApi.list({ status: "pending", limit: 200, include_total: false });
      const stats = new Map<string, { count: number; best: number }>();
      const skus: string[] = [];
      for (const c of res.items) {
        const prev = stats.get(c.product_sku);
        if (!prev) skus.push(c.product_sku);
        stats.set(c.product_sku, {
          count: (prev?.count ?? 0) + 1,
          best: Math.max(prev?.best ?? 0, c.score),
        });
      }
      return { skus, stats };
    },
    staleTime: 60_000,
  });
}
```

En el componente, reemplazar el uso:

```typescript
  const { data: queueData } = useSkuQueue();
  const queue = React.useMemo(() => queueData?.skus ?? [], [queueData]);
```

Y `queueEntries`:

```typescript
  const queueEntries: SkuQueueEntry[] = React.useMemo(
    () =>
      queue.map((s) => {
        const st = queueData?.stats.get(s);
        return { sku: s, candidateCount: st?.count ?? 0, bestScore: st?.best ?? null };
      }),
    [queue, queueData],
  );
```

- [ ] **Step 2: Borrar el `fmtAED` muerto**

Eliminar la función `fmtAED` de `page.tsx` (línea ~65) — no se usa en este fichero.

- [ ] **Step 3: Verificar typecheck**

Run: `cd mt-pricing-frontend && npx tsc --noEmit`
Expected: sin errores.

- [ ] **Step 4: Commit**

```bash
git add mt-pricing-frontend/app/(app)/catalogo/validacion/page.tsx
git commit -m "perf(validacion): dedupe SKU queue into single query, drop dead code"
```

---

## Task 15: Atajos de teclado V/X (gap 1)

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/validacion/page.tsx`

- [ ] **Step 1: Extender el handler de teclado**

Reemplazar el `useEffect` del listener `onKey` (~línea 196):

```typescript
  React.useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.key === "ArrowRight") goNext();
      if (e.key === "ArrowLeft") goPrev();
      const firstPending = items.find((c) => c.status === "pending");
      if (!firstPending || mutating) return;
      if (e.key === "v" || e.key === "V") validate.mutate(firstPending.id);
      if (e.key === "x" || e.key === "X") discard.mutate({ id: firstPending.id });
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [goNext, goPrev, items, mutating, validate, discard]);
```

- [ ] **Step 2: Verificar typecheck + build**

Run: `cd mt-pricing-frontend && npx tsc --noEmit`
Expected: sin errores.

- [ ] **Step 3: Commit**

```bash
git add mt-pricing-frontend/app/(app)/catalogo/validacion/page.tsx
git commit -m "feat(validacion): wire V/X keyboard shortcuts to validate/discard"
```

---

## Task 16: "Siguiente sin validar" salta al SKU pendiente (gap 2)

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/validacion/page.tsx`

- [ ] **Step 1: Reemplazar `goNext` del botón inferior**

Añadir una función que avanza al siguiente SKU con candidatos pendientes y conectarla al botón "Siguiente sin validar":

```typescript
  const goNextUnvalidated = React.useCallback(() => {
    for (let i = clampedIndex + 1; i < queue.length; i++) {
      const st = queueData?.stats.get(queue[i]!);
      if ((st?.count ?? 0) > 0) {
        setSkuIndex(i);
        return;
      }
    }
    if (canNext) setSkuIndex((x) => x + 1);
  }, [clampedIndex, queue, queueData, canNext]);
```

Cambiar el `onClick` del botón "Siguiente sin validar" de `goNext` a `goNextUnvalidated`.

- [ ] **Step 2: Verificar typecheck**

Run: `cd mt-pricing-frontend && npx tsc --noEmit`
Expected: sin errores.

- [ ] **Step 3: Commit**

```bash
git add mt-pricing-frontend/app/(app)/catalogo/validacion/page.tsx
git commit -m "feat(validacion): 'next unvalidated' skips to next pending SKU"
```

---

## Task 17: Diálogo de motivo de descarte (gap 6)

**Files:**
- Create: `mt-pricing-frontend/app/(app)/catalogo/validacion/_components/discard-reason-dialog.tsx`
- Modify: `mt-pricing-frontend/app/(app)/catalogo/validacion/_components/candidate-card.tsx`

- [ ] **Step 1: Crear el diálogo**

```tsx
// _components/discard-reason-dialog.tsx
"use client";

import * as React from "react";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { MT } from "@/components/mt/tokens";

interface DiscardReasonDialogProps {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onConfirm: (reason: string | undefined) => void;
}

export function DiscardReasonDialog({ open, onOpenChange, onConfirm }: DiscardReasonDialogProps) {
  const [reason, setReason] = React.useState("");

  React.useEffect(() => {
    if (open) setReason("");
  }, [open]);

  return (
    <ConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Descartar candidato"
      description="Indica el motivo del descarte (opcional). Ayuda a auditar el matching."
      confirmLabel="Descartar"
      destructive
      onConfirm={() => onConfirm(reason.trim() || undefined)}
    >
      <textarea
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        rows={3}
        placeholder="Motivo (opcional)…"
        className="mt-2 w-full rounded-[6px] border p-2 text-[12px]"
        style={{ borderColor: MT.border, color: MT.ink2 }}
      />
    </ConfirmDialog>
  );
}
```

> **Verificar:** que `ConfirmDialog` acepta `children`. Si no los renderiza,
> añadir `{children}` en `components/ui/confirm-dialog.tsx` dentro del cuerpo
> del diálogo, entre la `description` y los botones.

- [ ] **Step 2: Conectar el diálogo en `CandidateCard`**

En `candidate-card.tsx`, cambiar `onDiscard` para que abra el diálogo. Añadir estado local y reemplazar el botón "Descartar":

```tsx
  const [discardOpen, setDiscardOpen] = React.useState(false);
```

Reemplazar el `<button>` de descartar (`onClick={onDiscard}`) por `onClick={() => setDiscardOpen(true)}`, y añadir antes del cierre del componente:

```tsx
      <DiscardReasonDialog
        open={discardOpen}
        onOpenChange={setDiscardOpen}
        onConfirm={(reason) => { setDiscardOpen(false); onDiscard(reason); }}
      />
```

Cambiar la firma de la prop: `onDiscard: (reason?: string) => void;` e importar `DiscardReasonDialog`.

- [ ] **Step 3: Actualizar el caller en `page.tsx`**

En `page.tsx`, el `onDiscard` del `CandidateCard`:

```tsx
                    onDiscard={(reason) => discard.mutate({ id: c.id, reason })}
```

- [ ] **Step 4: Verificar typecheck**

Run: `cd mt-pricing-frontend && npx tsc --noEmit`
Expected: sin errores.

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-frontend/app/(app)/catalogo/validacion/
git commit -m "feat(validacion): collect discard reason via dialog"
```

---

## Task 18: Chips de confianza en `CandidateCard` (gap 8)

**Files:**
- Modify: `mt-pricing-frontend/lib/api/endpoints/matches.ts` (añadir campos al tipo)
- Modify: `mt-pricing-frontend/app/(app)/catalogo/validacion/_components/candidate-card.tsx`

- [ ] **Step 1: Añadir los campos conformal al tipo `MatchCandidate`**

En `matches.ts`, en la interfaz `MatchCandidate`, añadir tras `pack_units`:

```typescript
  calibrated_confidence: string | null;
  conf_lower: string | null;
  conf_upper: string | null;
  review_priority: "low" | "high" | null;
```

> **Backend:** verificar que `MatchCandidateResponse` (schema) expone estos
> campos. Como `MatchCandidateBase` usa `from_attributes=True`, añadir los 4
> campos a `MatchCandidateBase` en `app/schemas/matches.py`:
> ```python
>     calibrated_confidence: Decimal | None = None
>     conf_lower: Decimal | None = None
>     conf_upper: Decimal | None = None
>     review_priority: str | None = None
> ```

- [ ] **Step 2: Renderizar el chip de confianza en `CandidateCard`**

En `candidate-card.tsx`, dentro de la columna de precio+score (tras `<ScorePill .../>`), añadir:

```tsx
        {review_priority && (
          <span
            className="inline-flex items-center gap-1 rounded-[4px] border px-1.5 py-0.5 text-[9px] font-semibold"
            style={
              review_priority === "low"
                ? { background: MT.successSoft, color: MT.success, borderColor: MT.successBorder }
                : { background: MT.dangerSoft, color: MT.danger, borderColor: MT.dangerBorder }
            }
            title="Prioridad de revisión derivada del intervalo conformal"
          >
            {review_priority === "low" ? "Agente: validar" : "Agente: descartar"}
          </span>
        )}
        {calibrated_confidence != null && (
          <span className="mt-mono text-[9px]" style={{ color: MT.ink4 }}>
            Conf. calibrada: {Math.round(Number(calibrated_confidence) * 100)}%
          </span>
        )}
```

Añadir `calibrated_confidence` y `review_priority` al destructuring de `candidate` al inicio del componente.

- [ ] **Step 3: Verificar typecheck**

Run: `cd mt-pricing-frontend && npx tsc --noEmit`
Expected: sin errores.

- [ ] **Step 4: Commit**

```bash
git add mt-pricing-frontend/lib/api/endpoints/matches.ts mt-pricing-frontend/app/(app)/catalogo/validacion/_components/candidate-card.tsx mt-pricing-backend/app/schemas/matches.py
git commit -m "feat(validacion): surface calibrated confidence + review priority on cards"
```

---

## Task 19: Hooks del agente (config / métricas / revert)

**Files:**
- Create: `mt-pricing-frontend/lib/hooks/matches/use-match-agent.ts`

- [ ] **Step 1: Crear los hooks**

```typescript
// lib/hooks/matches/use-match-agent.ts
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  matchesApi,
  type MatchAgentConfig,
  type MatchAgentConfigUpdate,
  type MatchAgentMetrics,
  type MatchCandidate,
} from "@/lib/api/endpoints/matches";
import { matchKeys } from "./use-matches";

export function useAgentConfig() {
  return useQuery<MatchAgentConfig, Error>({
    queryKey: ["matches", "agent-config"],
    queryFn: () => matchesApi.agentConfig(),
    staleTime: 60_000,
  });
}

export function useAgentMetrics() {
  return useQuery<MatchAgentMetrics, Error>({
    queryKey: ["matches", "agent-metrics"],
    queryFn: () => matchesApi.agentMetrics(),
    staleTime: 30_000,
  });
}

export function useUpdateAgentConfig() {
  const qc = useQueryClient();
  return useMutation<MatchAgentConfig, Error, MatchAgentConfigUpdate>({
    mutationFn: (body) => matchesApi.updateAgentConfig(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["matches", "agent-config"] });
      void qc.invalidateQueries({ queryKey: ["matches", "agent-metrics"] });
      toast.success("Configuración del agente actualizada");
    },
    onError: (e) => toast.error(`No se pudo actualizar: ${e.message}`),
  });
}

export function useRevertMatch() {
  const qc = useQueryClient();
  return useMutation<MatchCandidate, Error, string>({
    mutationFn: (id) => matchesApi.revert(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: matchKeys.all });
      toast.success("Decisión del agente revertida");
    },
    onError: (e) => toast.error(`No se pudo revertir: ${e.message}`),
  });
}
```

- [ ] **Step 2: Verificar typecheck**

Run: `cd mt-pricing-frontend && npx tsc --noEmit`
Expected: sin errores.

- [ ] **Step 3: Commit**

```bash
git add mt-pricing-frontend/lib/hooks/matches/use-match-agent.ts
git commit -m "feat(validacion): add agent config/metrics/revert hooks"
```

---

## Task 20: Barra de acción en bloque (gap 7)

**Files:**
- Create: `mt-pricing-frontend/app/(app)/catalogo/validacion/_components/bulk-accept-bar.tsx`
- Modify: `mt-pricing-frontend/app/(app)/catalogo/validacion/page.tsx`

- [ ] **Step 1: Crear la barra**

```tsx
// _components/bulk-accept-bar.tsx
"use client";

import * as React from "react";
import { Sparkles } from "lucide-react";
import { MtButton } from "@/components/mt/primitives";
import { MT } from "@/components/mt/tokens";
import type { MatchCandidate } from "@/lib/api/endpoints/matches";

interface BulkAcceptBarProps {
  items: MatchCandidate[];
  busy: boolean;
  onAcceptAll: (ids: string[]) => void;
}

export function BulkAcceptBar({ items, busy, onAcceptAll }: BulkAcceptBarProps) {
  const recommended = React.useMemo(
    () =>
      items.filter(
        (c) =>
          c.status === "pending" &&
          (c.review_priority === "low" ||
            (c.specs_jsonb as Record<string, unknown> | undefined)?._enhanced != null &&
              ((c.specs_jsonb as { _enhanced?: { auto_validate?: boolean } })._enhanced
                ?.auto_validate === true)),
      ),
    [items],
  );

  if (recommended.length === 0) return null;

  return (
    <div
      className="flex items-center justify-between gap-3 border-b px-6 py-2"
      style={{ background: MT.brandSoft, borderColor: MT.brandBorder }}
    >
      <span className="flex items-center gap-1.5 text-[12px] font-medium" style={{ color: MT.brand }}>
        <Sparkles className="size-3.5" />
        El agente recomienda validar {recommended.length} candidato
        {recommended.length !== 1 ? "s" : ""}
      </span>
      <MtButton
        size="sm"
        tone="primary"
        disabled={busy}
        onClick={() => onAcceptAll(recommended.map((c) => c.id))}
      >
        Aceptar {recommended.length} recomendado{recommended.length !== 1 ? "s" : ""}
      </MtButton>
    </div>
  );
}
```

- [ ] **Step 2: Integrar la barra en `page.tsx`**

Importar `BulkAcceptBar` y, tras la `Toolbar` y antes del `isError`, renderizar:

```tsx
      <BulkAcceptBar
        items={items}
        busy={mutating}
        onAcceptAll={(ids) => ids.forEach((id) => validate.mutate(id))}
      />
```

- [ ] **Step 3: Verificar typecheck**

Run: `cd mt-pricing-frontend && npx tsc --noEmit`
Expected: sin errores.

- [ ] **Step 4: Commit**

```bash
git add mt-pricing-frontend/app/(app)/catalogo/validacion/
git commit -m "feat(validacion): add bulk-accept bar for agent-recommended candidates"
```

---

## Task 21: Panel de métricas del agente

**Files:**
- Create: `mt-pricing-frontend/app/(app)/catalogo/validacion/_components/agent-metrics-panel.tsx`
- Modify: `mt-pricing-frontend/app/(app)/catalogo/validacion/page.tsx`

- [ ] **Step 1: Crear el panel**

```tsx
// _components/agent-metrics-panel.tsx
"use client";

import * as React from "react";
import { Bot } from "lucide-react";
import { MtButton } from "@/components/mt/primitives";
import { MT } from "@/components/mt/tokens";
import { useAgentConfig, useAgentMetrics, useUpdateAgentConfig } from "@/lib/hooks/matches/use-match-agent";

export function AgentMetricsPanel() {
  const { data: metrics } = useAgentMetrics();
  const { data: config } = useAgentConfig();
  const update = useUpdateAgentConfig();

  if (!metrics || !config) return null;

  const pct = Math.min(100, Math.round((metrics.golden_labels_total / metrics.min_labels_gate) * 100));

  return (
    <div
      className="flex flex-wrap items-center gap-4 border-b px-6 py-2.5"
      style={{ background: MT.surface2, borderColor: MT.border }}
    >
      <span className="flex items-center gap-1.5 text-[11px] font-semibold uppercase" style={{ color: MT.ink4 }}>
        <Bot className="size-3.5" /> Agente · modo {config.mode === "shadow" ? "sombra" : "activo"}
      </span>
      <span className="text-[11px]" style={{ color: MT.ink3 }}>
        Labels: <b>{metrics.golden_labels_total}</b> / {metrics.min_labels_gate} ({pct}%)
      </span>
      <span className="text-[11px]" style={{ color: MT.ink3 }}>
        Precisión sombra:{" "}
        <b>{metrics.shadow_precision != null ? `${Math.round(metrics.shadow_precision * 100)}%` : "—"}</b>
      </span>
      <span className="text-[11px]" style={{ color: MT.ink3 }}>
        Calibrador: <b>{metrics.calibrator_version ?? "sin entrenar"}</b>
      </span>
      {config.mode === "shadow" && metrics.gate_reached && (
        <MtButton size="sm" tone="primary" disabled={update.isPending}
          onClick={() => update.mutate({ mode: "active" })}>
          Activar agente
        </MtButton>
      )}
      {config.mode === "active" && (
        <MtButton size="sm" disabled={update.isPending}
          onClick={() => update.mutate({ mode: "shadow" })}>
          Volver a sombra
        </MtButton>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Integrar el panel en `page.tsx`**

Importar `AgentMetricsPanel` y renderizarlo justo debajo del workflow header (antes de la Toolbar).

- [ ] **Step 3: Verificar typecheck + build**

Run: `cd mt-pricing-frontend && npx tsc --noEmit`
Expected: sin errores.

- [ ] **Step 4: Commit**

```bash
git add mt-pricing-frontend/app/(app)/catalogo/validacion/
git commit -m "feat(validacion): add agent metrics panel with shadow/active toggle"
```

---

## Task 22: Tab "Auto-validados" + revertir

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/validacion/page.tsx`
- Modify: `mt-pricing-frontend/app/(app)/catalogo/validacion/_components/candidate-card.tsx`

- [ ] **Step 1: Añadir el filtro "Auto-validados"**

En `page.tsx`, el array `FILTER_TABS` no cambia (sigue server-side por `status`), pero
se añade un filtro cliente. Añadir un quinto chip y estado:

```typescript
  const [showAgentOnly, setShowAgentOnly] = React.useState(false);
```

Filtrar los `items` mostrados:

```typescript
  const visibleItems = React.useMemo(
    () =>
      showAgentOnly
        ? items.filter(
            (c) => (c.specs_jsonb as { _agent?: { applied?: boolean } })?._agent?.applied === true,
          )
        : items,
    [items, showAgentOnly],
  );
```

Usar `visibleItems` en lugar de `items` en el render de las cards. Añadir un toggle
chip "Auto-validados" junto a los `FILTER_TABS` que hace `setShowAgentOnly((v) => !v)`.

- [ ] **Step 2: Botón "Revertir" en `CandidateCard`**

En `candidate-card.tsx`, cuando el candidato tiene `_agent.applied`, mostrar un
botón "Revertir" en la columna de decisión. Añadir prop `onRevert?: () => void`:

```tsx
  const agentApplied =
    (specs as { _agent?: { applied?: boolean } })?._agent?.applied === true;
```

Dentro del bloque `isVal`/`isDis`, si `agentApplied && onRevert`, añadir bajo el badge:

```tsx
        {agentApplied && onRevert && (
          <button
            type="button"
            onClick={onRevert}
            className="mt-mono inline-flex h-5 items-center justify-center gap-1 text-[10px] hover:underline"
            style={{ color: MT.ink4 }}
          >
            Revertir decisión del agente
          </button>
        )}
```

- [ ] **Step 3: Conectar `onRevert` en `page.tsx`**

```tsx
  const revert = useRevertMatch();
```

En el render de cada `CandidateCard`: `onRevert={() => revert.mutate(c.id)}`.

- [ ] **Step 4: Verificar typecheck**

Run: `cd mt-pricing-frontend && npx tsc --noEmit`
Expected: sin errores.

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-frontend/app/(app)/catalogo/validacion/
git commit -m "feat(validacion): add auto-validated filter + revert action"
```

---

# TRACK 3 — Pruebas E2E

## Task 23: Arreglar el E2E stale + extender mocks

**Files:**
- Modify: `mt-pricing-frontend/tests/e2e/13-validacion-matches.spec.ts`
- Modify: `mt-pricing-frontend/tests/e2e/fixtures/seed-extended.ts`

- [ ] **Step 1: Alinear el header del test con la página real**

El test espera `/Validación humana asistida/i` pero la página renderiza `Validación`.
Decisión: actualizar el header de la página a un texto descriptivo y dejar el test.
En `page.tsx`, cambiar el `<span>` "Validación" del workflow header por:

```tsx
          <span className="mt-mono text-[10.5px] uppercase tracking-[1px]" style={{ color: MT.ink4 }}>
            Validación humana asistida
          </span>
```

- [ ] **Step 2: Extender los mocks del agente**

En `seed-extended.ts`, dentro de `installMatchesMocks`, añadir rutas mock para los
endpoints nuevos. Localizar la función e insertar:

```typescript
  await page.route("**/api/v1/matches/agent/config", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        mode: "shadow", alpha: "0.020", min_labels_gate: 200,
        updated_at: new Date().toISOString(),
      }),
    }),
  );
  await page.route("**/api/v1/matches/agent/metrics", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        golden_labels_total: 12, min_labels_gate: 200, gate_reached: false,
        shadow_decisions: 5, shadow_precision: 0.8,
        calibrator_version: null, calibrator_brier: null, calibrator_ece: null,
        calibrator_trained_on: null, mode: "shadow",
      }),
    }),
  );
```

Verificar que los objetos `FAKE_MATCHES` incluyan los campos nuevos
(`calibrated_confidence`, `conf_lower`, `conf_upper`, `review_priority`) — añadir
`review_priority: null, calibrated_confidence: null, conf_lower: null, conf_upper: null`
a cada objeto si no los tienen.

- [ ] **Step 3: Correr el E2E existente**

Run: `cd mt-pricing-frontend && npx playwright test tests/e2e/13-validacion-matches.spec.ts --config tests/e2e/playwright.config.ts`
Expected: los 4 tests existentes pasan.

- [ ] **Step 4: Commit**

```bash
git add mt-pricing-frontend/app/(app)/catalogo/validacion/page.tsx mt-pricing-frontend/tests/e2e/
git commit -m "test(validacion): fix stale E2E header + extend agent mocks"
```

---

## Task 24: Casos E2E nuevos del módulo y el agente

**Files:**
- Modify: `mt-pricing-frontend/tests/e2e/13-validacion-matches.spec.ts`

- [ ] **Step 1: Añadir los casos nuevos**

Añadir al `test.describe` de `13-validacion-matches.spec.ts`:

```typescript
  test("atajo de teclado V valida el primer pendiente", async ({ page }) => {
    await page.goto("/catalogo/validacion");
    await expect(page.getByText(FAKE_MATCHES[0]!.brand).first()).toBeVisible({ timeout: 15_000 });
    await page.keyboard.press("v");
    await expect(page.getByText(/Validado/i).first()).toBeVisible({ timeout: 5_000 });
  });

  test("panel del agente muestra modo y progreso de labels", async ({ page }) => {
    await page.goto("/catalogo/validacion");
    await expect(page.getByText(/Agente · modo sombra/i)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/Labels:/i)).toBeVisible();
  });

  test("descartar abre diálogo de motivo", async ({ page }) => {
    await page.goto("/catalogo/validacion");
    await expect(page.getByText(FAKE_MATCHES[0]!.brand).first()).toBeVisible({ timeout: 15_000 });
    await page.getByRole("button", { name: /^Descartar$/i }).first().click();
    await expect(page.getByText(/Indica el motivo del descarte/i)).toBeVisible({ timeout: 5_000 });
  });

  test("filtro 'Auto-validados' se puede activar", async ({ page }) => {
    await page.goto("/catalogo/validacion");
    await expect(page.getByText(/Candidatos/i).first()).toBeVisible({ timeout: 15_000 });
    await page.getByRole("button", { name: /Auto-validados/i }).click();
    // Sin candidatos del agente en el seed → empty state.
    await expect(page.getByText(/Sin candidatos/i).first()).toBeVisible({ timeout: 5_000 });
  });
```

- [ ] **Step 2: Correr la suite completa del módulo**

Run: `cd mt-pricing-frontend && npx playwright test tests/e2e/13-validacion-matches.spec.ts --config tests/e2e/playwright.config.ts`
Expected: todos los tests pasan (4 originales + 4 nuevos).

- [ ] **Step 3: Commit**

```bash
git add mt-pricing-frontend/tests/e2e/13-validacion-matches.spec.ts
git commit -m "test(validacion): add E2E coverage for keyboard, agent panel, discard dialog"
```

---

## Task 25: Reentrenamiento nightly del calibrador (Track 1)

Cubre la Fase 2 del spec: el calibrador debe reentrenarse periódicamente desde el
`golden_labels` que crece. La infraestructura (`CalibratorTrainer`, `CalibratorStorage`,
`admin_calibrator.py`) ya existe — esta tarea solo wirea el disparo nightly.

**Files:**
- Modify: `mt-pricing-backend/app/workers/tasks/comparator.py` (o módulo de tasks del calibrador)
- Create: `mt-pricing-backend/alembic/versions/<rev>_seed_calibrator_nightly_job.py`

- [ ] **Step 1: Comprobar si ya existe una task de entrenamiento**

Run: `cd mt-pricing-backend && grep -rn "CalibratorTrainer\|calibrator.*train" app/workers/`
Si ya existe una task Celery que llama a `CalibratorTrainer.train(auto_promote=True)` y
un `job_definition` que la agenda → esta tarea está completa, saltar a Step 5.

- [ ] **Step 2: Crear la task Celery (si no existe)**

Añadir a `app/workers/tasks/comparator.py`:

```python
@celery_app.task(name="mt.comparator.train_calibrator", queue="comparator")
def train_calibrator_task() -> dict[str, Any]:
    """Reentrena el IsotonicCalibrator desde golden_labels y auto-promueve si mejora."""

    async def _run() -> dict[str, Any]:
        from app.core.config import settings
        from app.repositories.golden_labels import (
            CalibratorVersionRepository,
            GoldenLabelRepository,
        )
        from app.services.matching.calibrator_storage import CalibratorStorage
        from app.services.matching.calibrator_trainer import (
            CalibratorTrainer,
            CalibratorTrainingNotReady,
        )
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool

        engine = create_async_engine(str(settings.DATABASE_URL), poolclass=NullPool)
        session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_factory() as session:
                trainer = CalibratorTrainer(
                    golden_repo=GoldenLabelRepository(session),
                    storage=CalibratorStorage(CalibratorVersionRepository(session)),
                )
                try:
                    result = await trainer.train(auto_promote=True)
                    await session.commit()
                    return {"version": result.version, "auto_promoted": result.auto_promoted}
                except CalibratorTrainingNotReady as exc:
                    logger.info("train_calibrator.not_ready", extra={"found": exc.found})
                    return {"not_ready": True, "found": exc.found}
        finally:
            await engine.dispose()

    return _run_async(_run())
```

- [ ] **Step 3: Sembrar el schedule en `job_definitions`**

Crear una migración que inserta una fila en `job_definitions` para correr
`mt.comparator.train_calibrator` cada noche (p.ej. `0 3 * * *`). Usar como plantilla
`alembic/versions/20260506_002_seed_worker_heartbeat_jobs.py` (mismo patrón de seed
de `job_definitions`). Delegar a `db-migrator` para encadenar el `down_revision`.

- [ ] **Step 4: Verificar**

Run: `cd mt-pricing-backend && python -c "from app.workers.tasks.comparator import train_calibrator_task"`
Expected: import sin error.

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/workers/tasks/comparator.py mt-pricing-backend/alembic/versions/
git commit -m "feat(matches): nightly calibrator retraining job"
```

---

# Verificación final

- [ ] **Backend:** `cd mt-pricing-backend && pytest tests/unit/services/matching/ tests/integration/test_match_agent_routes.py -v` — todo verde.
- [ ] **Migración:** revisada por `migration-reviewer`; `alembic upgrade head` aplica limpio.
- [ ] **Frontend:** `cd mt-pricing-frontend && npx tsc --noEmit && npx playwright test tests/e2e/13-validacion-matches.spec.ts` — verde.
- [ ] **Redeploy** (CLAUDE.md §Post-Change Deploy):
  - `./infra/scripts/migrate.sh`
  - `docker restart mt-backend mt-worker mt-beat`
  - `docker compose -f docker-compose.dev.yml up -d --build frontend`
  - Verificar: `curl http://localhost:${CADDY_HTTP_PORT:-8081}/health/live`
- [ ] **Smoke manual:** abrir `/catalogo/validacion`, comprobar panel del agente, atajos V/X, diálogo de descarte, barra de bloque.

---

# Notas de ejecución con agentes en paralelo

- **Track 0 (Tasks 1-2)** debe completarse primero — fija los contratos.
- **Track 1 (Tasks 3-13 + 25)**, **Track 2 (Tasks 14-22)** y **Track 3 (Tasks 23-24)**
  pueden ejecutarse en paralelo tras el Track 0. Track 2 depende del contrato de
  API (Track 0), no del código de Track 1 — usa mocks. Track 3 depende de Track 2.
- Dentro de Track 1, las Tasks 3→4→5 son secuenciales (modelo → migración → repo).
  Tasks 6-7 dependen de 5. Tasks 8-13 dependen de 5-7. Task 25 es independiente
  (solo toca la infra del calibrador, que ya existe) — puede ir en cualquier momento.
- Recomendado: `subagent-driven-development` — un subagente fresco por task, con
  revisión entre tasks.
