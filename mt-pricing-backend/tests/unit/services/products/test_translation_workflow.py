"""Unit tests para `app.services.products.translation_workflow` (US-1A-02-05).

Sin DB: stubeamos `AsyncSession` + repos in-memory. Cobertura:

- State machine: matrix (current, target) — todas las válidas + sample inválidas.
- request_review: ``draft|pending|stale → pending_review``.
- approve: ``pending_review → approved``.
- approve four-eyes: misma persona traductora no puede aprobar.
- reject: ``pending_review → draft`` con reason; reject sin reason → 422.
- mark_stale_for_master_edit: solo afecta filas ``approved`` no-EN; idempotente.
- Transición inválida lanza `InvalidTranslationStateTransition` con código.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from app.services.products.translation_workflow import (
    STALENESS_REASON_MASTER_EN,
    STATE_APPROVED,
    STATE_DRAFT,
    STATE_PENDING_LEGACY,
    STATE_PENDING_REVIEW,
    STATE_STALE,
    InvalidTranslationStateTransition,
    TranslationFourEyesViolation,
    TranslationNotFoundError,
    TranslationRejectMissingReason,
    TranslationWorkflowService,
    assert_transition,
    can_transition,
    list_valid_transitions,
)
from app.services.products.product_service import ProductNotFoundError

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# In-memory doubles
# ---------------------------------------------------------------------------
class _FakeProduct:
    def __init__(self, sku: str) -> None:
        self.sku = sku
        self.deleted_at: datetime | None = None


class _FakeTranslation:
    def __init__(
        self,
        sku: str,
        lang: str,
        status: str = STATE_DRAFT,
        translated_by: UUID | None = None,
    ) -> None:
        self.sku = sku
        self.lang = lang
        self.status = status
        self.name = f"name_{lang}_{sku}"
        self.description: str | None = None
        self.marketing_copy: str | None = None
        self.translated_by = translated_by
        self.translated_at: datetime | None = None
        self.reviewed_by: UUID | None = None
        self.reviewed_at: datetime | None = None
        self.staleness_reason: str | None = None
        self.rejection_reason: str | None = None
        now = datetime.now(tz=timezone.utc)
        self.created_at = now
        self.updated_at = now


class _InMemoryProductRepo:
    def __init__(self, products: dict[str, _FakeProduct]) -> None:
        self._by_sku = products

    async def get_by_sku(self, sku: str) -> _FakeProduct | None:
        return self._by_sku.get(sku)


class _InMemoryTranslationRepo:
    def __init__(self) -> None:
        self.rows: list[_FakeTranslation] = []

    async def get_one(self, sku: str, lang: str) -> _FakeTranslation | None:
        for r in self.rows:
            if r.sku == sku and r.lang == lang:
                return r
        return None

    async def get_for_sku(self, sku: str) -> list[_FakeTranslation]:
        return [r for r in self.rows if r.sku == sku]


class _RecordedAudit:
    """Captura llamadas para inspección en tests."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def record(self, **kw: Any) -> Any:  # mismo shape que AuditRepository.record
        self.events.append(kw)
        return MagicMock()


class _FakeUser:
    def __init__(self, *, role_code: str = "comercial") -> None:
        self.id = uuid4()
        self.email = f"user-{self.id.hex[:6]}@mt.ae"
        role = MagicMock()
        role.code = role_code
        role.permissions_snapshot = ["products:write"]
        self.role = role


# ---------------------------------------------------------------------------
# Service factory
# ---------------------------------------------------------------------------
def _make_service(
    *,
    product_skus: list[str] | None = None,
    rows: list[_FakeTranslation] | None = None,
) -> tuple[TranslationWorkflowService, _InMemoryTranslationRepo, _RecordedAudit]:
    product_skus = product_skus or ["MTBR4001050"]
    rows = rows or []
    fake_session = MagicMock()

    # `flush` debe ser un coroutine — patch:
    async def _flush() -> None:
        return None

    fake_session.flush = _flush

    svc = TranslationWorkflowService(fake_session)
    products_repo = _InMemoryProductRepo({sku: _FakeProduct(sku) for sku in product_skus})
    translations_repo = _InMemoryTranslationRepo()
    translations_repo.rows = list(rows)
    audit = _RecordedAudit()

    svc.products = products_repo  # type: ignore[assignment]
    svc.translations = translations_repo  # type: ignore[assignment]
    svc.audit = audit  # type: ignore[assignment]
    # Reemplazamos el emitter por uno que use el audit fake.
    from app.services.products.translation_audit import TranslationAuditEmitter

    svc.audit_emitter = TranslationAuditEmitter(audit)  # type: ignore[arg-type]

    return svc, translations_repo, audit


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------
def test_can_transition_matrix() -> None:
    valid = list(list_valid_transitions())
    # 6 transiciones esperadas (incluida pending_legacy → pending_review).
    assert len(valid) == 6
    assert can_transition(STATE_DRAFT, STATE_PENDING_REVIEW) is True
    assert can_transition(STATE_PENDING_LEGACY, STATE_PENDING_REVIEW) is True
    assert can_transition(STATE_STALE, STATE_PENDING_REVIEW) is True
    assert can_transition(STATE_PENDING_REVIEW, STATE_APPROVED) is True
    assert can_transition(STATE_PENDING_REVIEW, STATE_DRAFT) is True
    assert can_transition(STATE_APPROVED, STATE_STALE) is True

    # Inválidas representativas.
    for fr, to in [
        (STATE_DRAFT, STATE_APPROVED),
        (STATE_APPROVED, STATE_DRAFT),
        (STATE_STALE, STATE_APPROVED),
        (STATE_DRAFT, STATE_STALE),
    ]:
        assert can_transition(fr, to) is False


def test_assert_transition_invalid_raises() -> None:
    with pytest.raises(InvalidTranslationStateTransition) as exc:
        assert_transition(STATE_APPROVED, STATE_DRAFT)
    assert exc.value.code == "invalid_translation_state_transition"
    assert exc.value.status_code == 409


# ---------------------------------------------------------------------------
# request_review
# ---------------------------------------------------------------------------
async def test_request_review_draft_to_pending_review() -> None:
    row = _FakeTranslation("MTBR4001050", "es", status=STATE_DRAFT)
    svc, _repo, audit = _make_service(rows=[row])
    actor = _FakeUser()

    out = await svc.request_review("MTBR4001050", "es", actor)
    assert out.status == STATE_PENDING_REVIEW
    assert out.translated_by == actor.id
    assert out.translated_at is not None
    # Audit emitido.
    assert any(e["action"] == "product.translation.review_requested" for e in audit.events)


async def test_request_review_from_pending_legacy() -> None:
    row = _FakeTranslation("MTBR4001050", "es", status=STATE_PENDING_LEGACY)
    svc, _, _ = _make_service(rows=[row])
    out = await svc.request_review("MTBR4001050", "es", _FakeUser())
    assert out.status == STATE_PENDING_REVIEW


async def test_request_review_from_stale_resets_staleness_reason() -> None:
    row = _FakeTranslation("MTBR4001050", "ar", status=STATE_STALE)
    row.staleness_reason = STALENESS_REASON_MASTER_EN
    svc, _, _ = _make_service(rows=[row])
    out = await svc.request_review("MTBR4001050", "ar", _FakeUser())
    assert out.status == STATE_PENDING_REVIEW
    assert out.staleness_reason is None


async def test_request_review_from_approved_is_invalid() -> None:
    row = _FakeTranslation("MTBR4001050", "es", status=STATE_APPROVED)
    svc, _, _ = _make_service(rows=[row])
    with pytest.raises(InvalidTranslationStateTransition):
        await svc.request_review("MTBR4001050", "es", _FakeUser())


async def test_request_review_unknown_translation_404() -> None:
    svc, _, _ = _make_service(rows=[])
    with pytest.raises(TranslationNotFoundError):
        await svc.request_review("MTBR4001050", "es", _FakeUser())


async def test_request_review_unknown_sku_404() -> None:
    svc, _, _ = _make_service(product_skus=[], rows=[])
    with pytest.raises(ProductNotFoundError):
        await svc.request_review("UNKNOWN", "es", _FakeUser())


# ---------------------------------------------------------------------------
# approve (with four-eyes)
# ---------------------------------------------------------------------------
async def test_approve_pending_review_to_approved() -> None:
    translator = _FakeUser()
    row = _FakeTranslation(
        "MTBR4001050",
        "es",
        status=STATE_PENDING_REVIEW,
        translated_by=translator.id,
    )
    svc, _, audit = _make_service(rows=[row])

    approver = _FakeUser()
    out = await svc.approve("MTBR4001050", "es", approver)
    assert out.status == STATE_APPROVED
    assert out.reviewed_by == approver.id
    assert out.reviewed_at is not None
    assert any(e["action"] == "product.translation.approved" for e in audit.events)


async def test_approve_four_eyes_violation_when_same_user() -> None:
    user = _FakeUser()
    row = _FakeTranslation(
        "MTBR4001050",
        "es",
        status=STATE_PENDING_REVIEW,
        translated_by=user.id,
    )
    svc, _, _ = _make_service(rows=[row])

    with pytest.raises(TranslationFourEyesViolation) as exc:
        await svc.approve("MTBR4001050", "es", user)
    assert exc.value.code == "translation_four_eyes_violation"
    assert exc.value.status_code == 403


async def test_approve_from_draft_is_invalid() -> None:
    row = _FakeTranslation("MTBR4001050", "es", status=STATE_DRAFT)
    svc, _, _ = _make_service(rows=[row])
    with pytest.raises(InvalidTranslationStateTransition):
        await svc.approve("MTBR4001050", "es", _FakeUser())


# ---------------------------------------------------------------------------
# reject
# ---------------------------------------------------------------------------
async def test_reject_pending_review_to_draft_with_reason() -> None:
    row = _FakeTranslation("MTBR4001050", "es", status=STATE_PENDING_REVIEW)
    svc, _, audit = _make_service(rows=[row])
    actor = _FakeUser()
    out = await svc.reject("MTBR4001050", "es", actor, reason="terminología incorrecta")
    assert out.status == STATE_DRAFT
    assert out.rejection_reason == "terminología incorrecta"
    assert out.reviewed_by == actor.id
    rec = next(e for e in audit.events if e["action"] == "product.translation.rejected")
    assert rec["reason"] == "terminología incorrecta"


async def test_reject_missing_reason_raises_422() -> None:
    row = _FakeTranslation("MTBR4001050", "es", status=STATE_PENDING_REVIEW)
    svc, _, _ = _make_service(rows=[row])
    with pytest.raises(TranslationRejectMissingReason) as exc:
        await svc.reject("MTBR4001050", "es", _FakeUser(), reason="   ")
    assert exc.value.status_code == 422


async def test_reject_from_approved_is_invalid() -> None:
    row = _FakeTranslation("MTBR4001050", "es", status=STATE_APPROVED)
    svc, _, _ = _make_service(rows=[row])
    with pytest.raises(InvalidTranslationStateTransition):
        await svc.reject("MTBR4001050", "es", _FakeUser(), reason="cualquier motivo")


# ---------------------------------------------------------------------------
# mark_stale_for_master_edit
# ---------------------------------------------------------------------------
async def test_mark_stale_only_affects_approved_non_en() -> None:
    rows = [
        _FakeTranslation("MTBR4001050", "es", status=STATE_APPROVED),
        _FakeTranslation("MTBR4001050", "ar", status=STATE_APPROVED),
        _FakeTranslation("MTBR4001050", "en", status=STATE_APPROVED),
    ]
    svc, _, audit = _make_service(rows=rows)
    affected = await svc.mark_stale_for_master_edit("MTBR4001050", _FakeUser())
    affected_langs = sorted(r.lang for r in affected)
    assert affected_langs == ["ar", "es"]
    assert all(r.status == STATE_STALE for r in affected)
    assert all(r.staleness_reason == STALENESS_REASON_MASTER_EN for r in affected)
    # EN no se toca.
    en_row = next(r for r in rows if r.lang == "en")
    assert en_row.status == STATE_APPROVED
    # Audit por cada idioma afectado.
    stale_actions = [e for e in audit.events if e["action"] == "product.translation.marked_stale"]
    assert len(stale_actions) == 2


async def test_mark_stale_idempotent_when_already_stale_or_draft() -> None:
    rows = [
        _FakeTranslation("MTBR4001050", "es", status=STATE_DRAFT),
        _FakeTranslation("MTBR4001050", "ar", status=STATE_STALE),
    ]
    svc, _, audit = _make_service(rows=rows)
    affected = await svc.mark_stale_for_master_edit("MTBR4001050", _FakeUser())
    assert affected == []
    # No emite audit si nada cambió.
    assert all(e["action"] != "product.translation.marked_stale" for e in audit.events)


async def test_mark_stale_unknown_sku_raises_product_not_found() -> None:
    svc, _, _ = _make_service(product_skus=[])
    with pytest.raises(ProductNotFoundError):
        await svc.mark_stale_for_master_edit("UNKNOWN", _FakeUser())
