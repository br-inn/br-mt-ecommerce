"""Unit tests para `app.services.products.translation_audit`.

Verifica el shape canónico que la UI del tab Auditoría espera y que cada
transición del workflow emite un único evento con `action` ∈ TRANSLATION_AUDIT_ACTIONS.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.services.products.translation_audit import (
    TRANSLATION_AUDIT_ACTIONS,
    TranslationAuditEmitter,
    build_transition_diff,
    build_transition_payload,
)

pytestmark = pytest.mark.unit


class _StubAuditRepo:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def record(self, **kw: Any) -> Any:
        self.calls.append(kw)
        return MagicMock(id=uuid4())


class _StubUser:
    def __init__(self, *, role_code: str | None = "comercial") -> None:
        self.id = uuid4()
        self.email = f"u-{self.id.hex[:6]}@mt.ae"
        if role_code is None:
            self.role = None
        else:
            role = MagicMock()
            role.code = role_code
            self.role = role


def test_build_transition_payload_minimal() -> None:
    p = build_transition_payload(
        sku="MTBR4001050", lang="es", previous="draft", new="pending_review"
    )
    assert p == {
        "sku": "MTBR4001050",
        "lang": "es",
        "from": "draft",
        "to": "pending_review",
    }


def test_build_transition_payload_with_reason() -> None:
    p = build_transition_payload(
        sku="MTBR4001050",
        lang="ar",
        previous="pending_review",
        new="draft",
        reason="terminología incorrecta",
    )
    assert p["reason"] == "terminología incorrecta"


def test_build_transition_diff_shape() -> None:
    assert build_transition_diff("draft", "pending_review") == {
        "status": {"from": "draft", "to": "pending_review"}
    }


def test_translation_audit_actions_complete_set() -> None:
    expected = {
        "product.translation.review_requested",
        "product.translation.approved",
        "product.translation.rejected",
        "product.translation.marked_stale",
    }
    assert TRANSLATION_AUDIT_ACTIONS == expected


async def test_emitter_records_request_review() -> None:
    repo = _StubAuditRepo()
    user = _StubUser()
    emitter = TranslationAuditEmitter(repo)  # type: ignore[arg-type]

    await emitter.record_transition(
        sku="MTBR4001050",
        lang="es",
        previous="draft",
        new="pending_review",
        action="product.translation.review_requested",
        actor=user,
    )

    assert len(repo.calls) == 1
    call = repo.calls[0]
    assert call["entity_type"] == "product_translation"
    assert call["entity_id"] == "MTBR4001050:es"
    assert call["action"] == "product.translation.review_requested"
    assert call["actor_id"] == user.id
    assert call["actor_email"] == user.email
    assert call["actor_role"] == "comercial"
    assert call["before"] == {"status": "draft"}
    assert call["after"]["from"] == "draft"
    assert call["after"]["to"] == "pending_review"
    assert call["payload_diff"] == {"status": {"from": "draft", "to": "pending_review"}}


async def test_emitter_includes_reason_for_rejected() -> None:
    repo = _StubAuditRepo()
    emitter = TranslationAuditEmitter(repo)  # type: ignore[arg-type]
    await emitter.record_transition(
        sku="MTBR4001050",
        lang="ar",
        previous="pending_review",
        new="draft",
        action="product.translation.rejected",
        actor=_StubUser(),
        reason="vocabulario PIM no coincide",
    )
    call = repo.calls[0]
    assert call["reason"] == "vocabulario PIM no coincide"
    assert call["after"]["reason"] == "vocabulario PIM no coincide"


async def test_emitter_marked_stale_sets_reason() -> None:
    repo = _StubAuditRepo()
    emitter = TranslationAuditEmitter(repo)  # type: ignore[arg-type]
    await emitter.record_transition(
        sku="MTBR4001050",
        lang="ar",
        previous="approved",
        new="stale",
        action="product.translation.marked_stale",
        actor=_StubUser(role_code=None),
        reason="master_en_changed",
    )
    call = repo.calls[0]
    assert call["after"]["to"] == "stale"
    assert call["reason"] == "master_en_changed"
    assert call["actor_role"] is None  # role None is propagated.


async def test_emitter_rejects_unknown_action() -> None:
    repo = _StubAuditRepo()
    emitter = TranslationAuditEmitter(repo)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        await emitter.record_transition(
            sku="MTBR4001050",
            lang="es",
            previous="draft",
            new="approved",
            action="product.translation.something_else",
            actor=_StubUser(),
        )
    assert repo.calls == []
