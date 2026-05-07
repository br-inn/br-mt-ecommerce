"""Unit tests for `app.services.matching.match_service` — sin DB.

Estrategia: mockeamos el `AsyncSession` y los repositorios usando una
implementación in-memory de :class:`MatchCandidateRepository` y
:class:`ProductRepository`. Esto permite ejercitar la orquestación
(query → fetch → score → upsert) sin levantar Postgres.

Cobertura:
- ``refresh_candidates`` para SKU canned (Pegler) devuelve 5+3 = 8 candidatos.
- ``refresh_candidates`` clasifica al menos un peer (Pegler exact match) con score ≥70.
- ``refresh_candidates`` lanza MatchSkuNotFoundError si el SKU no existe.
- Idempotencia: dos refresh consecutivos no duplican candidatos.
- ``validate_candidate`` cambia status a 'validated'.
- ``discard_candidate`` cambia status a 'discarded' con reason.
- Transición ilegal (validated → discard) lanza MatchInvalidTransitionError.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from app.services.matching.match_service import (
    MatchCandidateNotFoundError,
    MatchInvalidTransitionError,
    MatchService,
    MatchSkuNotFoundError,
    _classify_candidate,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _FakeProduct:
    def __init__(self, sku: str, **kw: Any) -> None:
        self.sku = sku
        self.name_en = kw.get("name_en", f"Product {sku}")
        self.family = kw.get("family", "ball_valve")
        self.subfamily = kw.get("subfamily")
        self.material = kw.get("material", "brass")
        self.dn = kw.get("dn", "DN50")
        self.pn = kw.get("pn", "PN25")
        self.connection = kw.get("connection", "BSP")
        self.brand = kw.get("brand", "Pegler")
        self.specs = kw.get("specs", {"norma": "EN13828"})


class _FakeMatchRow:
    def __init__(self, **kw: Any) -> None:
        self.id: UUID = kw.get("id", uuid4())
        self.product_sku: str = kw["product_sku"]
        self.channel: str = kw["channel"]
        self.external_id: str = kw["external_id"]
        self.title: str = kw["title"]
        self.brand = kw.get("brand")
        self.price_aed = kw.get("price_aed")
        self.delivery_text = kw.get("delivery_text")
        self.specs_jsonb: dict[str, Any] = kw.get("specs_jsonb", {})
        self.kind: str = kw.get("kind", "unknown")
        self.score: int = kw.get("score", 0)
        self.status: str = kw.get("status", "pending")
        self.validated_by: UUID | None = None
        self.validated_at: datetime | None = None
        self.discarded_reason: str | None = None
        now = datetime.now(tz=timezone.utc)
        self.created_at = now
        self.updated_at = now


class _InMemoryMatchRepo:
    def __init__(self) -> None:
        self._rows: list[_FakeMatchRow] = []

    async def find_by_external(
        self, product_sku: str, channel: str, external_id: str
    ) -> _FakeMatchRow | None:
        for r in self._rows:
            if (
                r.product_sku == product_sku
                and r.channel == channel
                and r.external_id == external_id
            ):
                return r
        return None

    async def upsert_candidate(self, **kw: Any) -> _FakeMatchRow:
        existing = await self.find_by_external(
            kw["product_sku"], kw["channel"], kw["external_id"]
        )
        if existing:
            existing.title = kw["title"]
            existing.brand = kw.get("brand")
            existing.price_aed = kw.get("price_aed")
            existing.delivery_text = kw.get("delivery_text")
            existing.specs_jsonb = kw.get("specs_jsonb", {})
            existing.kind = kw.get("kind", existing.kind)
            existing.score = kw.get("score", existing.score)
            return existing
        row = _FakeMatchRow(**kw, status="pending")
        self._rows.append(row)
        return row

    async def list_with_filters(
        self,
        *,
        sku: str | None = None,
        status: str | None = None,
        channel: str | None = None,
        cursor: UUID | None = None,
        limit: int = 50,
    ) -> tuple[list[_FakeMatchRow], UUID | None]:
        out = list(self._rows)
        if sku is not None:
            out = [r for r in out if r.product_sku == sku]
        if status is not None:
            out = [r for r in out if r.status == status]
        if channel is not None:
            out = [r for r in out if r.channel == channel]
        return out[:limit], None

    async def get(self, candidate_id: UUID) -> _FakeMatchRow | None:
        for r in self._rows:
            if r.id == candidate_id:
                return r
        return None

    async def mark_validated(
        self, candidate_id: UUID, *, user_id: UUID | None
    ) -> _FakeMatchRow | None:
        row = await self.get(candidate_id)
        if row is None:
            return None
        row.status = "validated"
        row.validated_by = user_id
        row.validated_at = datetime.now(tz=timezone.utc)
        row.discarded_reason = None
        return row

    async def mark_discarded(
        self, candidate_id: UUID, *, reason: str | None = None
    ) -> _FakeMatchRow | None:
        row = await self.get(candidate_id)
        if row is None:
            return None
        row.status = "discarded"
        row.discarded_reason = reason
        return row


class _InMemoryProductRepo:
    def __init__(self, products: dict[str, _FakeProduct]) -> None:
        self._by_sku = products

    async def get_by_sku(self, sku: str) -> _FakeProduct | None:
        return self._by_sku.get(sku)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _make_service(
    *, products: dict[str, _FakeProduct] | None = None
) -> tuple[MatchService, _InMemoryMatchRepo]:
    products = products or {
        "MTBR4001050": _FakeProduct("MTBR4001050"),
    }
    fake_session = MagicMock()  # nunca se usa porque mockeamos los repos
    svc = MatchService(fake_session)
    matches_repo = _InMemoryMatchRepo()
    products_repo = _InMemoryProductRepo(products)
    svc._matches_repo = matches_repo  # type: ignore[assignment]
    svc._products_repo = products_repo  # type: ignore[assignment]
    return svc, matches_repo


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
async def test_classify_candidate_thresholds() -> None:
    assert _classify_candidate(80, []) == "peer"
    assert _classify_candidate(50, []) == "drop"
    assert _classify_candidate(20, []) == "unknown"
    # Mismatch crítico → unknown aunque score alto
    assert _classify_candidate(90, ["thread_mismatch"]) == "unknown"


async def test_refresh_candidates_persists_amazon_plus_noon_for_canned_sku() -> None:
    svc, repo = _make_service()
    rows = await svc.refresh_candidates("MTBR4001050")
    # 5 amazon + 3 noon stubs canned para este SKU
    assert len(rows) == 8
    channels = {r.channel for r in rows}
    assert channels == {"amazon_uae", "noon_uae"}
    assert len(repo._rows) == 8


async def test_refresh_candidates_classifies_pegler_exact_match_as_peer() -> None:
    svc, _ = _make_service()
    rows = await svc.refresh_candidates("MTBR4001050")
    pegler_match = next(
        (
            r
            for r in rows
            if (r.brand or "").lower() == "pegler" and r.channel == "amazon_uae"
        ),
        None,
    )
    assert pegler_match is not None
    assert pegler_match.score >= 70
    assert pegler_match.kind == "peer"


async def test_refresh_candidates_unknown_sku_raises() -> None:
    svc, _ = _make_service(products={})
    with pytest.raises(MatchSkuNotFoundError):
        await svc.refresh_candidates("DOES-NOT-EXIST")


async def test_refresh_candidates_idempotent() -> None:
    svc, repo = _make_service()
    await svc.refresh_candidates("MTBR4001050")
    initial = len(repo._rows)
    # Segundo refresh — mismas external_ids → upsert, no duplicados.
    await svc.refresh_candidates("MTBR4001050")
    assert len(repo._rows) == initial


async def test_validate_candidate_changes_status() -> None:
    svc, repo = _make_service()
    rows = await svc.refresh_candidates("MTBR4001050")
    target = rows[0]
    user_id = uuid4()
    updated = await svc.validate_candidate(target.id, user_id=user_id)
    assert updated.status == "validated"
    assert updated.validated_by == user_id
    assert updated.validated_at is not None


async def test_discard_candidate_records_reason() -> None:
    svc, _ = _make_service()
    rows = await svc.refresh_candidates("MTBR4001050")
    target = rows[-1]
    updated = await svc.discard_candidate(target.id, reason="not the same DN")
    assert updated.status == "discarded"
    assert updated.discarded_reason == "not the same DN"


async def test_validate_then_discard_raises_invalid_transition() -> None:
    svc, _ = _make_service()
    rows = await svc.refresh_candidates("MTBR4001050")
    target = rows[0]
    await svc.validate_candidate(target.id, user_id=uuid4())
    with pytest.raises(MatchInvalidTransitionError):
        await svc.discard_candidate(target.id, reason="changed mind")


async def test_discard_then_validate_raises_invalid_transition() -> None:
    svc, _ = _make_service()
    rows = await svc.refresh_candidates("MTBR4001050")
    target = rows[0]
    await svc.discard_candidate(target.id)
    with pytest.raises(MatchInvalidTransitionError):
        await svc.validate_candidate(target.id, user_id=uuid4())


async def test_get_candidate_unknown_id_raises() -> None:
    svc, _ = _make_service()
    with pytest.raises(MatchCandidateNotFoundError):
        await svc.get_candidate(uuid4())


async def test_refresh_persists_scoring_breakdown_in_jsonb() -> None:
    svc, _ = _make_service()
    rows = await svc.refresh_candidates("MTBR4001050")
    for r in rows:
        assert "_scoring" in r.specs_jsonb
        scoring = r.specs_jsonb["_scoring"]
        assert "score" in scoring
        assert "breakdown" in scoring
        assert "weights" in scoring


async def test_refresh_candidates_synthesizes_for_unknown_sku() -> None:
    products = {
        "MT-V-NEW": _FakeProduct(
            "MT-V-NEW",
            material="brass",
            family="ball_valve",
            dn="DN25",
            pn="PN16",
            brand="Arco",
        )
    }
    svc, _ = _make_service(products=products)
    rows = await svc.refresh_candidates("MT-V-NEW")
    assert len(rows) == 8  # 5 amazon synthetic + 3 noon synthetic
