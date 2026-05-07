"""TranslationWorkflowService — state machine de aprobación de traducciones.

US-1A-02-05 (Sprint 3).

Estados de `product_translations.status`:

- ``draft``           — autor edita; puede mandar a review.
- ``pending_review``  — esperando aprobador (four-eyes).
- ``approved``        — visible para export/publicación.
- ``stale``           — máster EN cambió; obliga a re-aprobación antes de publicar.

Transiciones permitidas (mapping):

    draft           → pending_review        (request_review por autor)
    pending_review  → approved              (approve por aprobador, con four-eyes)
    pending_review  → draft                 (reject por aprobador, con reason)
    approved        → stale                 (automático cuando master EN cambia,
                                              disparado por trigger DB; expuesto
                                              también via `mark_stale` para tests)
    stale           → pending_review        (autor re-edita y reenvía a review)

Cualquier otra transición lanza :class:`InvalidTranslationStateTransition`
(``code="invalid_translation_state_transition"``, status_code=409).

Constraints adicionales:
- Four-eyes (BR-1a-09): el ``actor`` que ejecuta ``approve`` no puede coincidir
  con ``translated_by`` de la traducción.
- ``reject`` requiere ``reason`` (str no vacío).
- ``mark_stale_for_master_edit`` afecta a TODAS las traducciones no-EN del SKU
  cuyo status sea ``approved`` (idempotente sobre el resto).
- Cada transición emite un AuditEvent específico (ver
  :mod:`app.services.products.translation_audit`).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import ProductTranslation
from app.db.models.user import User
from app.repositories.audit import AuditRepository
from app.repositories.product import (
    ProductRepository,
    ProductTranslationRepository,
)
from app.services.products.product_service import (
    ProductDomainError,
    ProductNotFoundError,
)
from app.services.products.translation_audit import TranslationAuditEmitter

# ---------------------------------------------------------------------------
# Estados + transiciones
# ---------------------------------------------------------------------------
STATE_DRAFT = "draft"
STATE_PENDING_REVIEW = "pending_review"
STATE_APPROVED = "approved"
STATE_STALE = "stale"
# Estado heredado (S1/S2) — equivalente operacional a ``draft`` en el workflow
# nuevo. Se acepta como origen para retro-compat.
STATE_PENDING_LEGACY = "pending"

ALL_STATES: frozenset[str] = frozenset(
    {
        STATE_DRAFT,
        STATE_PENDING_REVIEW,
        STATE_APPROVED,
        STATE_STALE,
        STATE_PENDING_LEGACY,
    }
)

# Mapping (current_state, target_state) -> True si la transición es válida.
_VALID_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {
        # request_review
        (STATE_DRAFT, STATE_PENDING_REVIEW),
        (STATE_PENDING_LEGACY, STATE_PENDING_REVIEW),
        (STATE_STALE, STATE_PENDING_REVIEW),
        # approve
        (STATE_PENDING_REVIEW, STATE_APPROVED),
        # reject
        (STATE_PENDING_REVIEW, STATE_DRAFT),
        # stale (master EN edit)
        (STATE_APPROVED, STATE_STALE),
    }
)

STALENESS_REASON_MASTER_EN = "master_en_changed"


# ---------------------------------------------------------------------------
# Errores de dominio
# ---------------------------------------------------------------------------
class InvalidTranslationStateTransition(ProductDomainError):
    """Transición no permitida en la state machine de traducciones."""

    def __init__(self, *, current: str, target: str) -> None:
        super().__init__(
            code="invalid_translation_state_transition",
            message=(
                f"Transición inválida {current!r} → {target!r}. "
                f"Permitidas: "
                + ", ".join(
                    f"{a}->{b}" for a, b in sorted(_VALID_TRANSITIONS)
                )
                + "."
            ),
            status_code=409,
        )
        self.current = current
        self.target = target


class TranslationFourEyesViolation(ProductDomainError):
    """Aprobador coincide con el traductor (BR-1a-09)."""

    def __init__(self, *, actor_id: UUID) -> None:
        super().__init__(
            code="translation_four_eyes_violation",
            message=(
                f"El usuario {actor_id} no puede aprobar una traducción "
                "que él mismo redactó (regla four-eyes BR-1a-09)."
            ),
            status_code=403,
        )


class TranslationRejectMissingReason(ProductDomainError):
    """``reject`` sin ``reason`` no es admisible (auditoría exige motivo)."""

    def __init__(self) -> None:
        super().__init__(
            code="translation_reject_reason_required",
            message="`reason` es obligatorio para rechazar una traducción.",
            status_code=422,
        )


class TranslationNotFoundError(ProductDomainError):
    def __init__(self, sku: str, lang: str) -> None:
        super().__init__(
            code="translation_not_found",
            message=f"Traducción {lang!r} no existe para {sku!r}.",
            status_code=404,
        )


# ---------------------------------------------------------------------------
# Helpers puros (state machine)
# ---------------------------------------------------------------------------
def can_transition(current: str, target: str) -> bool:
    """Devuelve True si ``current → target`` es una transición permitida."""
    return (current, target) in _VALID_TRANSITIONS


def assert_transition(current: str, target: str) -> None:
    """Lanza :class:`InvalidTranslationStateTransition` si no permitida."""
    if not can_transition(current, target):
        raise InvalidTranslationStateTransition(current=current, target=target)


# ---------------------------------------------------------------------------
# Servicio
# ---------------------------------------------------------------------------
class TranslationWorkflowService:
    """Orquesta transiciones de la state machine + emite audit events.

    No reemplaza :class:`ProductService` (CRUD de traducciones) — vive en
    paralelo y se llama desde los nuevos endpoints
    ``products/{sku}/translations/{lang}/{request-review,reject,mark-stale}``.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.products = ProductRepository(session)
        self.translations = ProductTranslationRepository(session)
        self.audit = AuditRepository(session)
        self.audit_emitter = TranslationAuditEmitter(self.audit)

    # ---------------------------------------------------------- helpers
    async def _ensure_translation(
        self, sku: str, lang: str
    ) -> ProductTranslation:
        prod = await self.products.get_by_sku(sku)
        if prod is None or prod.deleted_at is not None:
            raise ProductNotFoundError(sku)
        existing = await self.translations.get_one(sku, lang)
        if existing is None:
            raise TranslationNotFoundError(sku, lang)
        return existing

    # ---------------------------------------------------------- transitions
    async def request_review(
        self, sku: str, lang: str, actor: User
    ) -> ProductTranslation:
        """``draft|pending|stale`` → ``pending_review`` (autor pide review)."""
        row = await self._ensure_translation(sku, lang)
        previous = row.status
        assert_transition(previous, STATE_PENDING_REVIEW)

        row.status = STATE_PENDING_REVIEW
        row.translated_by = actor.id
        row.translated_at = datetime.now(tz=timezone.utc)
        # Reseteamos staleness_reason si venía de stale.
        _set_optional(row, "staleness_reason", None)
        await self.session.flush()

        await self.audit_emitter.record_transition(
            sku=sku,
            lang=lang,
            previous=previous,
            new=STATE_PENDING_REVIEW,
            action="product.translation.review_requested",
            actor=actor,
        )
        return row

    async def approve(
        self, sku: str, lang: str, actor: User
    ) -> ProductTranslation:
        """``pending_review`` → ``approved`` (con four-eyes)."""
        row = await self._ensure_translation(sku, lang)
        previous = row.status
        assert_transition(previous, STATE_APPROVED)

        if row.translated_by is not None and row.translated_by == actor.id:
            raise TranslationFourEyesViolation(actor_id=actor.id)

        row.status = STATE_APPROVED
        row.reviewed_by = actor.id
        row.reviewed_at = datetime.now(tz=timezone.utc)
        await self.session.flush()

        await self.audit_emitter.record_transition(
            sku=sku,
            lang=lang,
            previous=previous,
            new=STATE_APPROVED,
            action="product.translation.approved",
            actor=actor,
        )
        return row

    async def reject(
        self, sku: str, lang: str, actor: User, *, reason: str
    ) -> ProductTranslation:
        """``pending_review`` → ``draft`` (con motivo obligatorio)."""
        if reason is None or not str(reason).strip():
            raise TranslationRejectMissingReason()

        row = await self._ensure_translation(sku, lang)
        previous = row.status
        assert_transition(previous, STATE_DRAFT)

        row.status = STATE_DRAFT
        row.reviewed_by = actor.id
        row.reviewed_at = datetime.now(tz=timezone.utc)
        _set_optional(row, "rejection_reason", reason.strip())
        await self.session.flush()

        await self.audit_emitter.record_transition(
            sku=sku,
            lang=lang,
            previous=previous,
            new=STATE_DRAFT,
            action="product.translation.rejected",
            actor=actor,
            reason=reason.strip(),
        )
        return row

    async def mark_stale_for_master_edit(
        self,
        sku: str,
        actor: User,
        *,
        reason: str = STALENESS_REASON_MASTER_EN,
    ) -> Sequence[ProductTranslation]:
        """``approved`` → ``stale`` para todas las traducciones no-EN del SKU.

        Idempotente: las traducciones que NO estén en ``approved`` se ignoran.
        Devuelve la lista de filas afectadas (puede estar vacía si ninguna
        estaba aprobada).
        """
        prod = await self.products.get_by_sku(sku)
        if prod is None or prod.deleted_at is not None:
            raise ProductNotFoundError(sku)

        rows = await self.translations.get_for_sku(sku)
        affected: list[ProductTranslation] = []
        for row in rows:
            if row.lang == "en":
                continue
            if row.status != STATE_APPROVED:
                continue
            previous = row.status
            row.status = STATE_STALE
            _set_optional(row, "staleness_reason", reason)
            affected.append(row)
            await self.audit_emitter.record_transition(
                sku=sku,
                lang=row.lang,
                previous=previous,
                new=STATE_STALE,
                action="product.translation.marked_stale",
                actor=actor,
                reason=reason,
            )
        if affected:
            await self.session.flush()
        return affected


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------
def _set_optional(obj: Any, attr: str, value: Any) -> None:
    """``setattr`` defensivo — el atributo puede no existir en SQLAlchemy si la
    migración aún no se aplicó (test puro). En ese caso lo seteamos como
    instance attr (no persistido pero observable en assertions)."""
    try:
        setattr(obj, attr, value)
    except Exception:  # pragma: no cover — defensivo
        object.__setattr__(obj, attr, value)


__all__ = [
    "ALL_STATES",
    "InvalidTranslationStateTransition",
    "STALENESS_REASON_MASTER_EN",
    "STATE_APPROVED",
    "STATE_DRAFT",
    "STATE_PENDING_LEGACY",
    "STATE_PENDING_REVIEW",
    "STATE_STALE",
    "TranslationFourEyesViolation",
    "TranslationNotFoundError",
    "TranslationRejectMissingReason",
    "TranslationWorkflowService",
    "assert_transition",
    "can_transition",
]


def list_valid_transitions() -> Iterable[tuple[str, str]]:
    """Expuesto para tests / OpenAPI examples."""
    return tuple(sorted(_VALID_TRANSITIONS))
