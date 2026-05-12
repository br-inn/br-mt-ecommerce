"""Unit tests para `app.services.pricing.state_machine` — US-1B-02-01.

Cubre PriceStateMachine.transition() con 8 escenarios de transición válidas
e inválidas, sin IO ni sesión de base de datos.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.services.pricing.state_machine import (
    ALLOWED_TRANSITIONS,
    InvalidTransitionError,
    PriceStateMachine,
    is_valid_transition,
)

pytestmark = pytest.mark.unit

ACTOR_ID: UUID = uuid4()


def make_price(status: str) -> SimpleNamespace:
    """Simula un ORM Price con los atributos mínimos que mutará PriceStateMachine."""
    return SimpleNamespace(
        id=uuid4(),
        status=status,
        approved_by=None,
        approved_at=None,
        rejection_reason=None,
    )


# ---------------------------------------------------------------------------
# Transiciones VÁLIDAS
# ---------------------------------------------------------------------------


def test_draft_to_pending_review() -> None:
    """draft → pending_review es una transición válida (requiere revisión manual)."""
    price = make_price("draft")
    event = PriceStateMachine.transition(price, "pending_review", ACTOR_ID)

    assert price.status == "pending_review"
    assert event.from_status == "draft"
    assert event.to_status == "pending_review"
    assert event.actor_id == ACTOR_ID


def test_draft_to_auto_approved() -> None:
    """draft → auto_approved cuando ninguna regla de excepción se dispara."""
    price = make_price("draft")
    event = PriceStateMachine.transition(price, "auto_approved", ACTOR_ID)

    assert price.status == "auto_approved"
    assert price.approved_by == ACTOR_ID
    assert price.approved_at is not None
    assert event.to_status == "auto_approved"


def test_pending_review_to_approved() -> None:
    """pending_review → approved: Gerente aprueba manualmente."""
    price = make_price("pending_review")
    event = PriceStateMachine.transition(price, "approved", ACTOR_ID, reason="OK margen")

    assert price.status == "approved"
    assert price.approved_by == ACTOR_ID
    assert event.reason == "OK margen"


def test_approved_to_published() -> None:
    """approved → published: precio publicado a canal (US-1B-02-01 target)."""
    price = make_price("approved")
    event = PriceStateMachine.transition(price, "published", ACTOR_ID)

    assert price.status == "published"
    assert price.approved_by == ACTOR_ID
    assert event.from_status == "approved"
    assert event.to_status == "published"


def test_published_to_archived() -> None:
    """published → archived: precio retirado de canal."""
    price = make_price("published")
    event = PriceStateMachine.transition(price, "archived", ACTOR_ID)

    assert price.status == "archived"
    assert event.to_status == "archived"


# ---------------------------------------------------------------------------
# Transiciones INVÁLIDAS — deben lanzar InvalidTransitionError
# ---------------------------------------------------------------------------


def test_draft_to_approved_is_invalid() -> None:
    """draft → approved salta el workflow de revisión — no permitido."""
    price = make_price("draft")
    with pytest.raises(InvalidTransitionError) as exc_info:
        PriceStateMachine.transition(price, "approved", ACTOR_ID)

    assert "draft" in str(exc_info.value)
    assert "approved" in str(exc_info.value)
    assert price.status == "draft"  # no mutó


def test_published_to_draft_is_invalid() -> None:
    """published → draft no existe en el FSM; precio publicado no puede retrogradar."""
    price = make_price("published")
    with pytest.raises(InvalidTransitionError):
        PriceStateMachine.transition(price, "draft", ACTOR_ID)

    assert price.status == "published"  # no mutó


def test_rejected_to_approved_is_invalid() -> None:
    """rejected → approved omite el ciclo de revisión — no permitido."""
    price = make_price("rejected")
    with pytest.raises(InvalidTransitionError) as exc_info:
        PriceStateMachine.transition(price, "approved", ACTOR_ID)

    err = str(exc_info.value)
    assert "rejected" in err
    assert "approved" in err
    assert price.status == "rejected"  # no mutó


# ---------------------------------------------------------------------------
# Cobertura adicional del módulo
# ---------------------------------------------------------------------------


def test_allowed_transitions_has_published_and_archived() -> None:
    """ALLOWED_TRANSITIONS incluye los nuevos estados del sprint 7."""
    assert "published" in ALLOWED_TRANSITIONS
    assert "archived" in ALLOWED_TRANSITIONS
    assert "published" in ALLOWED_TRANSITIONS["approved"]
    assert "archived" in ALLOWED_TRANSITIONS["published"]


def test_is_valid_transition_helper() -> None:
    """Función utilitaria is_valid_transition devuelve bool correcto."""
    assert is_valid_transition("draft", "pending_review") is True
    assert is_valid_transition("archived", "draft") is False
